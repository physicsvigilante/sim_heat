"""Source-only view of an admitted H1 composition; never execute native physics.

The output is a deterministic description of authored components, port topology,
input values and *not_computed* observation requests. It contains no solver
readings, predicted temperatures, heat flows, geometry or interpolation.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from .model import Refusal, SLOTS, parse_model, requests as check_requests, require, topology as build_topology
from .study import Study, checked_path, load_study, sha256, strict_json

UNITS = {
    'Mass': 'kg', 'SpecificHeatCapacity': 'J/(kg K)', 'Temperature': 'K',
    'ThermalConductivity': 'W/(m K)', 'Length': 'm', 'Area': 'm2',
}
DISCLAIMERS = (
    'Admitted source facts and logical connections only; no native solver has run.',
    'Graph positions are layout, not a physical apparatus or geometric measurement.',
    'Port_a/port_b orientation is authored connectivity, not measured heat-flow direction.',
    'Every requested physical observation is not_computed; no predicted values are supplied.',
    'Provenance notes and parser admission do not independently certify textbook/source fidelity.',
)


def _pinned_bytes(path: Path, limit: int, expected: str) -> bytes:
    """Hash the same bounded buffer used to derive the preview."""
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, 'resource_limit', 'source exceeds admission size limit')
    require(sha256(raw) == expected, 'identity', 'source changed since admission')
    return raw


def build_source_preview(study: Study) -> dict:
    """Build a shape-independent source payload solely from admitted H1 objects."""
    # Nested Study facts are caller-mutable. Derive every displayed fact from
    # the descriptor and model buffers authenticated by the admission digests.
    case = study.path.parent
    descriptor = checked_path(case, study.path.name, case, '.json')
    data = strict_json(_pinned_bytes(descriptor, 262144, study.sha256).decode('utf-8'))
    require(data['model']['sha256'] == study.model_sha256, 'identity', 'model pin drift')
    path = checked_path(case, data['model']['path'], case, '.mo')
    model = parse_model(_pinned_bytes(path, 65536, study.model_sha256).decode('utf-8'))
    topology = build_topology(model, data['mode'])
    report = check_requests(model, data['requests'])
    require(report['admitted'], 'request', 'refused requests cannot be previewed')
    require(all(r['status'] == 'not_computed' for r in report['requests']),
            'request', 'source preview requires uncomputed requests')
    node_of = {i: f'node_{i}' for i in range(len(topology.nodes))}
    nodes = []
    for i, ports in enumerate(topology.nodes):
        owners = [p.split('.')[0] for p in ports
                  if model.components[p.split('.')[0]].kind in ('Body', 'FixedTemperature')]
        require(len(set(owners)) <= 1, 'unsupported_topology', 'multiple node owners')
        owner = owners[0] if owners else None
        role = ('junction' if owner is None else
                'body' if model.components[owner].kind == 'Body' else 'boundary')
        nodes.append({'id': node_of[i], 'ports': list(ports), 'owner': owner,
                      'role': role, 'label': owner or f'Ideal junction {i + 1}'})
    components = []
    for name, comp in sorted(model.components.items()):
        inputs = [{'name': key, 'quantityType': SLOTS[comp.kind][key],
                   'siUnit': UNITS[SLOTS[comp.kind][key]], 'sourceValue': comp.fields[key].value}
                  for key in sorted(comp.fields)]
        citations = []
        for record in data['provenance']:
            # H1 also admits attribution through a bound scalar parameter.
            # Retain its ORIGINAL target and the effective fields it supports;
            # never substitute the parameter record with a fabricated slot fact.
            affected = [f'{name}.{key}' for key, binding in sorted(comp.fields.items())
                        if record['target'] == f'{name}.{key}'
                        or record['target'] in binding.dependencies]
            if affected:
                citations.append({**record, 'appliesTo': affected})
        # Component-wide assumptions are legal H1 provenance targets, but are
        # not evidence for any individual scalar slot. Preserve their original
        # records separately, including repeated records and original order.
        component_citations = [dict(record) for record in data['provenance']
                               if record['target'] == name]
        components.append({'id': name, 'kind': comp.kind, 'inputs': inputs,
                           'sourceProvenance': citations,
                           'componentProvenance': component_citations})
    rods = []
    for name, a, b, _ in topology.edges:
        rods.append({'id': name, 'from': node_of[a], 'to': node_of[b],
                     'portA': name + '.port_a', 'portB': name + '.port_b'})
    requests = []
    authored = {r['id']: r for r in data['requests']}
    for result in report['requests']:
        request = authored[result['id']]
        endpoints = ([request['a'], request['b']] if request['op'] == 'temperatureDifference'
                     else [request['target']])
        requests.append({'id': result['id'], 'operation': request['op'],
                         'targets': endpoints, 'unit': result['unit'], 'status': 'not_computed'})
    return {
        'schema': 'sim_heat.viewer.admitted_source/1',
        'status': 'admitted_source_only', 'studyId': data['id'],
        'modelName': model.name, 'mode': data['mode'],
        'source': {
            'studySha256': study.sha256, 'modelSha256': study.model_sha256,
            'evidenceKind': 'authored_source_only', 'nativeExecuted': False,
            'nativeQualified': False, 'sourceFidelityQualified': False,
            'publicRequestStatus': 'not_computed',
        },
        'components': components, 'nodes': nodes, 'rods': rods, 'requests': requests,
        'modelProvenance': [dict(r) for r in data['provenance'] if r['target'] == '@model'],
        'disclaimers': list(DISCLAIMERS),
    }


def serialized(payload: dict) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', type=Path)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, help='Outside the authored case root; stdout if omitted')
    args = parser.parse_args()
    try:
        loaded = load_study(args.study, args.root)
        result = serialized(build_source_preview(loaded))
        if args.out:
            out = args.out.resolve()
            root = args.root.resolve(strict=True)
            require(not out.is_relative_to(root), 'path', 'refuse overwriting authored case files')
            # Write only after admission completes, and replace atomically.
            out.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix='.source-preview-', dir=out.parent)
            try:
                with os.fdopen(fd, 'wb') as file:
                    file.write(result)
                os.replace(temporary, out)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        else:
            import sys
            sys.stdout.buffer.write(result)
        return 0
    except (Refusal, OSError, ValueError) as exc:
        import sys
        print(json.dumps({'stage': 'source_preview', 'admitted': False,
                          'nativeExecuted': False, 'code': getattr(exc, 'code', 'input_error'),
                          'reason': str(exc)}, allow_nan=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
