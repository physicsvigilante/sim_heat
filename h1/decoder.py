"""Candidate CSV shape decoder; only synthetic exports have been tested.

No interpretation of compiler aliases, no fallback calculations, no native
verification verdict. Callers must preserve original raw bytes separately.
"""
import csv
import io
import math
from .model import require
from .policy import match_grid


def decode_csv(text: str, required: tuple[str, ...], grid: tuple[float, ...], *,
               maximum_shift: float | None = None) -> dict:
    require(len(text.encode('utf-8')) <= 20 * 1024 * 1024, 'resource_limit', 'CSV exceeds 20 MiB')
    require(len(required) == len(set(required)) and 'time' not in required,
            'result_schema', 'invalid required export set')
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        from .model import Refusal
        raise Refusal('result_schema', 'malformed CSV') from exc
    require(2 <= len(rows) <= 40003, 'result_schema', 'empty/oversized CSV')
    header = rows[0]
    require(len(header) <= 4096 and len(header) == len(set(header)) and all(header),
            'result_schema', 'duplicate/empty/oversized headers')
    require('time' in header and set(required) <= set(header), 'result_schema', 'missing required output')
    names = ('time',) + required
    positions = [header.index(name) for name in names]
    canonical = []
    for row in rows[1:]:
        require(len(row) == len(header), 'result_schema', 'truncated/oversized row')
        try:
            values = tuple(float(row[i]) for i in positions)
        except ValueError as exc:
            from .model import Refusal
            raise Refusal('result_schema', 'nonnumeric required output') from exc
        require(all(math.isfinite(x) for x in values), 'result_schema', 'nonfinite required output')
        if canonical and values[0] == canonical[-1][0]:
            require(values == canonical[-1], 'ambiguous_output', 'conflicting duplicate timestamp')
        else:
            canonical.append(values)
    match_grid(grid, tuple(row[0] for row in canonical), maximum_shift=maximum_shift)
    return {'columns': {name: tuple(row[i] for row in canonical) for i, name in enumerate(names)},
            'duplicateRowsCollapsed': len(rows) - 1 - len(canonical),
            'ignoredExtraColumns': [name for name in header if name not in names],
            'status': 'decoded_only', 'numericallyAccepted': False}
