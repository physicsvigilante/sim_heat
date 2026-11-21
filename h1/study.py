"""Read-only descriptors, provenance and narrow conductivity revisions."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from .model import (Refusal, Model, Topology, identifier, require, parse_model,
                    topology, junction_condition, requests, internal_exports, IDENT)
from .policy import analysis_grid


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exact_keys(value: object, keys: set[str], code: str) -> None:
    require(isinstance(value, dict) and set(value) == keys, code, 'unexpected/missing object fields')


def digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def strict_json(text: str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'descriptor', f'duplicate JSON key {key}')
            result[key] = value
        return result
    def bad_constant(value):
        raise Refusal('descriptor', f'nonfinite JSON constant {value}')
    def finite_float(token):
        value = float(token)
        require(math.isfinite(value), 'descriptor', 'nonfinite JSON number')
        return value
    def bounded_int(token):
        require(len(token.lstrip('-')) <= 4300, 'descriptor', 'oversized JSON integer')
        return int(token)
    try:
        value = json.loads(text, object_pairs_hook=pairs,
                           parse_constant=bad_constant, parse_float=finite_float,
                           parse_int=bounded_int)
    except Refusal:
        raise
    except (ValueError, OverflowError, RecursionError) as exc:
        # Includes legal exponent overflow, Python's integer-length guard and
        # excessive nesting. These are descriptor refusals, not tracebacks.
        raise Refusal('descriptor', 'invalid/oversized/too deeply nested JSON') from exc
    require(isinstance(value, dict), 'descriptor', 'study must be an object')
    return value


def checked_path(base: Path, name: str, root: Path, suffix: str) -> Path:
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name and '\x00' not in name,
            'path', 'portable relative path required')
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.suffix == suffix, 'path', 'unexpected path type')
    candidate = base / name
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise Refusal('path', 'unreadable path') from exc
    require(resolved.is_relative_to(root.resolve()) and resolved.is_file(), 'path', 'path escapes allowed root')
    # No symlinks, including intermediate path components.
    require(not any(p.is_symlink() for p in (candidate, *candidate.parents)), 'path', 'symlink refused')
    return resolved


@dataclass(frozen=True)
class Study:
    path: Path
    data: dict
    sha256: str
    model_sha256: str
    model: Model
    topology: Topology
    grid: tuple[float, ...]
    request_report: dict
    condition: float


def check_provenance(model: Model, records: list) -> None:
    require(isinstance(records, list) and len(records) <= 2048, 'provenance', 'invalid provenance list')
    slots = {f'{name}.{slot}': binding for name, c in model.components.items() for slot, binding in c.fields.items()}
    valid = set(slots) | set(model.parameters) | set(model.components) | {'@model'}
    kinds = {'source_given', 'source_diagram', 'solution_assumption', 'adopted_assumption', 'unit_convention', 'illustrative'}
    targets = set()
    regime = False
    for r in records:
        exact_keys(r, {'target', 'kind', 'locator', 'note'}, 'provenance')
        require(all(isinstance(v, str) and v.strip() for v in r.values()), 'provenance', 'nonempty strings required')
        require(r['target'] in valid and r['kind'] in kinds, 'provenance', 'unknown target/kind')
        targets.add(r['target'])
        regime |= r['target'] == '@model' and r['kind'] in ('adopted_assumption', 'solution_assumption')
    require(regime, 'provenance', 'model regime/assumptions record missing')
    for slot, b in slots.items():
        require(slot in targets or bool(set(b.dependencies) & targets), 'provenance', f'unattributed physical slot {slot}')
    # This checks links, not whether notes faithfully interpret the original source.


def compare_revision(parent: Study, child: Study, target: str) -> None:
    require(isinstance(target, str) and target.count('.') == 1, 'revision', 'invalid revision target')
    name, slot = target.split('.')
    require(slot == 'k' and name in parent.model.components and parent.model.components[name].kind.startswith('Rod'),
            'revision', 'only an existing rod conductivity can change')
    require(parent.data['mode'] == child.data['mode'], 'revision', 'mode changed')
    a, b = parent.model, child.model
    require(a.components.keys() == b.components.keys(), 'revision', 'component identities changed')
    require(parent.topology.nodes == child.topology.nodes, 'revision', 'connection topology changed')
    changed = []
    for key in a.components:
        ca, cb = a.components[key], b.components[key]
        require(ca.kind == cb.kind, 'revision', 'component type changed')
        for field in ca.fields:
            if ca.value(field) != cb.value(field):
                changed.append(f'{key}.{field}')
    require(changed == [target], 'revision', f'expected only {target}, got {changed}')


def load_study(path: Path, root: Path, seen: tuple[Path, ...] = ()) -> Study:
    """Validate offline only; this function never writes or invokes a compiler."""
    root = root.resolve(strict=True)
    path = path.absolute()
    base = root
    if not path.is_relative_to(root):
        # Locate the same root along the supplied spelling (e.g. an 8.3 name).
        # Keep that spelling so checked_path can inspect every original component.
        try:
            base = next(parent for parent in path.parents if parent.samefile(root))
        except (StopIteration, OSError, ValueError) as exc:
            raise Refusal('path', 'study outside case root') from exc
        root = base.resolve(strict=True)
    relative = path.relative_to(base).as_posix()
    path = checked_path(base, relative, root, '.json')
    require(path not in seen and len(seen) < 16, 'revision', 'cyclic/too deep parent chain')
    require(path.stat().st_size <= 262144, 'resource_limit', 'study exceeds 256 KiB')
    raw = path.read_bytes()
    try:
        data = strict_json(raw.decode('utf-8'))
    except UnicodeError as exc:
        raise Refusal('descriptor', 'study is not UTF-8') from exc
    keys = {'schema', 'id', 'model', 'mode', 'requests', 'analysis', 'provenance'}
    require(set(data) in (keys, keys | {'revision'}), 'descriptor', 'unexpected/missing study fields')
    require(data['schema'] == 'sim_heat.study/1' and isinstance(data['id'], str) and IDENT.fullmatch(data['id']) is not None, 'descriptor', 'bad schema/identity')
    exact_keys(data['model'], {'path', 'sha256'}, 'descriptor')
    require(digest(data['model']['sha256']), 'descriptor', 'bad model hash')
    model_path = checked_path(path.parent, data['model']['path'], path.parent, '.mo')
    require(model_path.stat().st_size <= 65536, 'resource_limit', 'model exceeds 64 KiB')
    model_raw = model_path.read_bytes()
    require(sha256(model_raw) == data['model']['sha256'], 'identity', 'model hash mismatch')
    try:
        model = parse_model(model_raw.decode('utf-8'))
    except UnicodeError as exc:
        raise Refusal('syntax', 'model is not UTF-8') from exc
    graph = topology(model, data['mode'])
    condition = junction_condition(graph)
    grid = analysis_grid(data['mode'], data['analysis'])
    check_provenance(model, data['provenance'])
    report = requests(model, data['requests'])
    study = Study(path, data, sha256(raw), sha256(model_raw), model, graph, grid, report, condition)
    if 'revision' in data:
        rev = data['revision']
        exact_keys(rev, {'parentStudyPath', 'parentStudySha256', 'parentModelSha256', 'target', 'reason', 'origin'}, 'revision')
        require(rev['origin'] == 'hypothetical' and isinstance(rev['reason'], str) and rev['reason'].strip(),
                'revision', 'hypothetical origin and reason required')
        require(digest(rev['parentStudySha256']) and digest(rev['parentModelSha256']), 'revision', 'bad parent hashes')
        parent_path = checked_path(path.parent, rev['parentStudyPath'], root, '.json')
        parent = load_study(parent_path, root, seen + (path,))
        require(parent.sha256 == rev['parentStudySha256'] and parent.model_sha256 == rev['parentModelSha256'],
                'revision', 'stale parent identity')
        compare_revision(parent, study, rev['target'])
    return study


def report(study: Study) -> dict:
    return {'stage': 'offline_validation', 'nativeExecuted': False,
            'admitted': study.request_report['admitted'],
            'modelSha256': study.model_sha256, 'studySha256': study.sha256,
            'nodes': study.topology.nodes, 'networks': study.topology.networks,
            'scaledJunctionCondition': study.condition,
            'requests': study.request_report['requests'],
            'internalExports': internal_exports(study.model),
            'limits': ['native runtime/export not qualified', 'source fidelity not established by parser',
                       'no numerical or physical-result acceptance']}
