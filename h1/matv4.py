"""Read-only, generic OpenModelica MAT-v4 result normalization.

Converts *recorded* MAT data_1 parameters and data_2 trajectories (including
signed aliases) to an auditable candidate CSV consumed by the existing checker.
Does not import physical model laws, reference answers or estimate missing data.
No output of this module implies native acceptance.
"""
from __future__ import annotations

from collections import defaultdict
import csv
from io import BytesIO, StringIO
import hashlib
import math
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from scipy.io.matlab import matfile_version

from .decoder import decode_csv
from .model import Refusal, require

MAX_BYTES = 20 * 1024 * 1024
MAX_SIGNALS = 4096
MAX_POINTS = 40002


def _matrix(mapping: dict, key: str, transpose: bool) -> np.ndarray:
    require(key in mapping, 'mat_schema', f'MAT missing {key}')
    a = mapping[key]
    require(isinstance(a, np.ndarray) and a.ndim == 2, 'mat_schema', f'invalid MAT matrix {key}')
    return a.T if transpose else a


def _text_rows(a: np.ndarray, what: str) -> list[str]:
    require(a.ndim == 2 and 0 < a.shape[0] <= MAX_SIGNALS and 0 < a.shape[1] <= 4096,
            'mat_schema', f'invalid character matrix shape {what}')
    require(a.dtype.kind in ('U', 'S', 'i', 'u'), 'mat_schema', f'unsupported characters in {what}')
    result = []
    for row in a:
        if a.dtype.kind in ('i', 'u'):
            require(all(0 <= int(x) <= 127 for x in row), 'mat_schema', 'non-ASCII MAT name')
            chars = ''.join(chr(int(x)) for x in row)
        else:
            decoded = [x.decode('ascii', 'strict') if isinstance(x, bytes) else str(x) for x in row]
            require(all(len(x) <= 1 and x.isascii() for x in decoded), 'mat_schema', 'non-ASCII MAT name')
            chars = ''.join(decoded)
        result.append(chars.rstrip('\x00 '))
    return result


def _orientation(raw: np.ndarray) -> bool:
    """Return True for stored binTrans format; reject malformed/ambiguous header."""
    candidates = []
    for trans in (False, True):
        a = raw.T if trans else raw
        if a.ndim != 2 or a.shape[0] != 4:
            continue
        try:
            rows = _text_rows(a, 'Aclass')
        except (Refusal, UnicodeError):
            continue
        if rows[0] == 'Atrajectory' and rows[1] == '1.1' and rows[2] == '' and rows[3] in ('binTrans', 'binNormal'):
            if trans == (rows[3] == 'binTrans'):
                candidates.append(trans)
    require(len(candidates) == 1, 'mat_schema', 'unrecognized or inconsistent Aclass orientation')
    return candidates[0]


def _real_data(a: np.ndarray, key: str) -> np.ndarray:
    require(a.ndim == 2 and a.size <= MAX_SIGNALS * MAX_POINTS, 'mat_schema', f'invalid {key} size')
    require(a.dtype == np.dtype('float64'), 'mat_precision', f'{key} must contain double precision native data')
    require(np.isfinite(a).all(), 'result_schema', f'nonfinite {key} output')
    return a


def decode_mat_bytes(raw: bytes, required: tuple[str, ...], grid: tuple[float, ...], *,
                     maximum_shift: float | None = None) -> dict:
    """Parse an OpenModelica MAT-v4 file to canonical CSV + exact source records.

    Required names originate from the generic physical export registry. Every
    canonical quantity is backed by a MAT data_1/data_2 row, never a formula.
    """
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_BYTES, 'mat_schema', 'MAT file missing or oversized')
    require(len(required) == len(set(required)) and 'time' not in required and bool(required),
            'result_schema', 'invalid required outputs')
    try:
        version = matfile_version(BytesIO(raw))
        require(version == (0, 0), 'mat_schema', 'only MATLAB v4 result files admitted')
        variables = loadmat(BytesIO(raw), chars_as_strings=False, squeeze_me=False,
                            struct_as_record=False)
    except (OSError, ValueError, TypeError, IndexError, MemoryError) as exc:
        raise Refusal('mat_schema', 'invalid/unreadable MATLAB v4 data') from exc
    require(set(variables) - {'__header__', '__version__', '__globals__'} ==
            {'Aclass', 'name', 'description', 'dataInfo', 'data_1', 'data_2'},
            'mat_schema', 'unexpected or missing MAT data groups')
    trans = _orientation(variables['Aclass'])
    names = _text_rows(_matrix(variables, 'name', trans), 'name')
    require('time' in names and len(names) == len(set(names)) and all(names) and
            len(names) <= MAX_SIGNALS, 'result_schema', 'invalid/duplicate native variable names')
    info = _matrix(variables, 'dataInfo', trans)
    require(info.ndim == 2 and info.shape == (len(names), 4) and
            info.dtype.kind in ('i', 'u'), 'mat_schema', 'invalid dataInfo table')
    data1 = _real_data(_matrix(variables, 'data_1', trans), 'data_1')
    data2 = _real_data(_matrix(variables, 'data_2', trans), 'data_2')
    require(data1.shape[1] in (1, 2), 'mat_schema', 'unsupported time-invariant parameter layout')
    require(2 <= data2.shape[1] <= MAX_POINTS and 1 <= data2.shape[0] <= MAX_SIGNALS,
            'mat_schema', 'invalid sampled variable matrix')
    require('time' not in required and set(required) <= set(names),
            'result_schema', 'missing required MAT variable: ' + ', '.join(sorted(set(required) - set(names))))

    index = {name: i for i, name in enumerate(names)}
    time_rec = info[index['time']]
    require((int(time_rec[0]) == 0 or (int(time_rec[0]) == 2 and abs(int(time_rec[1])) == 1)) and
            abs(int(time_rec[1])) in (0, 1), 'mat_schema', 'time not recorded as abscissa')
    times = data2[0, :].tolist()
    # All dataInfo references, including unused native variables, should remain structurally sound.
    for name, rec in zip(names, info):
        channel, signed = int(rec[0]), int(rec[1])
        require(channel in (0, 1, 2), 'mat_schema', f'bad channel for {name}')
        if channel == 0:
            require(name == 'time' and abs(signed) <= 1, 'mat_schema', 'unexpected abscissa')
            continue
        limit = data1.shape[0] if channel == 1 else data2.shape[0]
        require(1 <= abs(signed) <= limit, 'mat_schema', f'out-of-range alias index {name}')
    require(all(int(info[index[k], 0]) in (1, 2) for k in required),
            'mat_schema', 'required output mapped to nonvalue abscissa')
    # A MAT file may use data_1 row 1 for start/stop *time*, which is not
    # a parameter. Check equality only for rows that back required outputs.
    if data1.shape[1] == 2:
        parameter_rows = {abs(int(info[index[k], 1])) - 1 for k in required
                          if int(info[index[k], 0]) == 1}
        for j in parameter_rows:
            require(data1[j, 0] == data1[j, 1], 'parameter_inconsistent',
                    f'time-invariant MAT data_1 endpoints differ at row {j+1}')
    columns = {'time': tuple(float(t) for t in times)}
    channels = defaultdict(list)
    for name, rec in zip(names, info):
        channel, signed = int(rec[0]), int(rec[1])
        if channel in (1, 2):
            channels[(channel, abs(signed))].append(name)
    provenance = {}
    for name in required:
        record = info[index[name]]
        channel, signed = int(record[0]), int(record[1]); row_index = abs(signed) - 1
        if channel == 1:
            native = np.full(len(times), data1[row_index, 0], dtype=float)
        else:
            native = data2[row_index]
        if signed < 0:
            native = -native
        columns[name] = tuple(float(x) for x in native)
        provenance[name] = {
            'origin': 'mat_parameter' if channel == 1 else 'mat_trajectory',
            'matTable': 'data_1' if channel == 1 else 'data_2',
            'oneBasedRow': row_index + 1,
            'negatedAlias': signed < 0,
            'sharedChannelNames': sorted(channels[(channel, abs(signed))]),
            'channelIsIndependentMeasurement': len(channels[(channel, abs(signed))]) == 1,
        }
    stream = StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(('time',) + required)
    for i in range(len(times)):
        writer.writerow([format(columns[k][i], '.17g') for k in ('time',) + required])
    text = stream.getvalue()
    # Reuse *same* numeric/time/duplicate policy as the published checker.
    decoded = decode_csv(text, required, grid, maximum_shift=maximum_shift)
    return {
        'schema': 'sim_heat.matv4_adapter/1',
        'rawMatSha256': hashlib.sha256(raw).hexdigest(),
        'rawSizeBytes': len(raw),
        'matOrientation': 'binTrans' if trans else 'binNormal',
        'columnProvenance': provenance,
        'canonicalCsvSha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'canonicalCsv': text,
        'decoded': decoded,
        'nativeQualified': False,
    }


def decode_mat_file(path: Path, required: tuple[str, ...], grid: tuple[float, ...], *,
                    maximum_shift: float | None = None) -> dict:
    p = Path(path)
    require(p.is_file() and not p.is_symlink() and p.stat().st_size <= MAX_BYTES,
            'mat_schema', 'missing/oversized/symlink MAT file')
    return decode_mat_bytes(p.read_bytes(), required, grid, maximum_shift=maximum_shift)
