"""Fully consumed H1 Modelica subset and connection-based admission.

This module validates authored facts. It neither invokes Modelica nor solves
thermal trajectories. Derived C/G are admission checks, never native results.
"""
from dataclasses import dataclass
import math
import re


class Refusal(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise Refusal(code, message)


SLOTS = {
    'Body': {'m': 'Mass', 'c': 'SpecificHeatCapacity', 'T_initial': 'Temperature'},
    'RodArea': {'k': 'ThermalConductivity', 'L': 'Length', 'A': 'Area'},
    'RodCircular': {'k': 'ThermalConductivity', 'L': 'Length', 'd': 'Length'},
    'FixedTemperature': {'T': 'Temperature'},
}
PORTS = {'Body': ('port',), 'FixedTemperature': ('port',),
         'RodArea': ('port_a', 'port_b'), 'RodCircular': ('port_a', 'port_b')}
TYPES = set(t for fields in SLOTS.values() for t in fields.values())
RESERVED = set('algorithm and annotation block break class connect connector constant '
               'constrainedby der discrete each else elseif elsewhen encapsulated end '
               'enumeration equation expandable extends external false final flow for '
               'function if import impure in initial inner input loop model not operator '
               'or outer output package parameter partial protected public pure record '
               'redeclare replaceable return stream then true type when while within '
               'time Real Integer Boolean String Modelica SimHeat'.split())
IDENT = re.compile(r'[A-Za-z][A-Za-z0-9_]*\Z')
NUMBER = r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?'
TOKEN = re.compile(r'(?P<ws>[ \t\r\n]+)|(?P<comment>//[^\r\n]*|/\*.*?\*/)|'
                   r'(?P<num>' + NUMBER + r')|(?P<id>[A-Za-z][A-Za-z0-9_]*)|'
                   r'(?P<sym>[().,;=+-])', re.DOTALL)


def identifier(value: object) -> bool:
    return isinstance(value, str) and IDENT.fullmatch(value) is not None and value not in RESERVED


@dataclass(frozen=True)
class Binding:
    value: float
    quantity_type: str
    # Parameter dependency chain, used for provenance; not copied solver inputs.
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class Component:
    kind: str
    fields: dict[str, Binding]

    def value(self, slot: str) -> float:
        return self.fields[slot].value


@dataclass(frozen=True)
class Model:
    name: str
    parameters: dict[str, Binding]
    components: dict[str, Component]
    connections: tuple[tuple[str, str], ...]

    def ports(self) -> set[str]:
        return {f'{name}.{p}' for name, c in self.components.items() for p in PORTS[c.kind]}


class Parser:
    def __init__(self, text: str):
        require(len(text.encode('utf-8')) <= 65536, 'resource_limit', 'model exceeds 64 KiB')
        self.tokens = []
        pos = 0
        while pos < len(text):
            match = TOKEN.match(text, pos)
            require(match is not None, 'syntax', f'unsupported token at character {pos}')
            if match.lastgroup not in ('ws', 'comment'):
                self.tokens.append(match.group())
            pos = match.end()
        self.i = 0
        self.parameters = {}
        self.components = {}
        self.names = set()

    def peek(self) -> str:
        return self.tokens[self.i] if self.i < len(self.tokens) else '<EOF>'

    def pop(self, expected: str | None = None) -> str:
        token = self.peek()
        require(token != '<EOF>', 'syntax', 'unexpected end of model')
        require(expected is None or token == expected, 'syntax', f'expected {expected}, got {token}')
        self.i += 1
        return token

    def path(self) -> str:
        parts = [self.pop()]
        require(IDENT.fullmatch(parts[0]) is not None, 'syntax', 'expected name')
        while self.peek() == '.':
            self.pop('.')
            parts.append(self.pop())
            require(IDENT.fullmatch(parts[-1]) is not None, 'syntax', 'expected name segment')
        return '.'.join(parts)

    def new_name(self) -> str:
        name = self.pop()
        require(identifier(name), 'identity', f'invalid/reserved identifier {name}')
        require(name not in self.names, 'identity', f'duplicate identifier {name}')
        self.names.add(name)
        return name

    def literal(self) -> float:
        sign = -1 if self.peek() == '-' else 1
        if self.peek() in ('+', '-'):
            self.pop()
        token = self.pop()
        require(re.fullmatch(NUMBER, token) is not None, 'syntax', 'numeric literal required')
        value = sign * float(token)
        require(math.isfinite(value), 'numerical_domain', 'nonfinite numeric literal')
        # Do not silently turn a nonzero authored number into zero by underflow.
        mantissa = re.split('[eE]', token)[0]
        require(value != 0 or not any(c in '123456789' for c in mantissa),
                'numerical_domain', 'numeric literal underflows to zero')
        return value

    def binding(self, expected_type: str) -> Binding:
        if re.fullmatch(NUMBER, self.peek()) or self.peek() in ('+', '-'):
            return Binding(self.literal(), expected_type)
        name = self.path()
        if name in self.parameters:
            b = self.parameters[name]
            require(b.quantity_type == expected_type, 'units', f'{name} has incompatible quantity type')
            return Binding(b.value, expected_type, (name,) + b.dependencies)
        conversions = {'SimHeat.Units.from_degC': ('Temperature', 1),
                       'SimHeat.Units.from_cm': ('Length', 1),
                       'SimHeat.Units.from_cm2': ('Area', 1),
                       'SimHeat.Units.conductivityFromKcal': ('ThermalConductivity', 2)}
        require(name in conversions, 'syntax', f'unknown parameter or conversion {name}')
        quantity, count = conversions[name]
        require(quantity == expected_type, 'units', 'conversion has incompatible result type')
        self.pop('(')
        x = self.literal()
        if count == 2:
            self.pop(',')
            factor = self.literal()
            require(factor > 0, 'physical_domain', 'calorie factor must be positive')
            x *= factor
        elif name.endswith('from_degC'):
            x += 273.15
        elif name.endswith('from_cm2'):
            x /= 10000
        else:
            x /= 100
        self.pop(')')
        require(math.isfinite(x), 'numerical_domain', 'conversion overflow')
        return Binding(x, expected_type)

    def parse(self) -> Model:
        if self.peek() == 'within':
            self.pop('within'); self.pop(';')
        self.pop('model')
        name = self.new_name()
        while self.peek() not in ('equation', 'end', '<EOF>'):
            if self.peek() == 'parameter':
                self.pop('parameter')
                typename = self.path()
                require(typename.startswith('Modelica.Units.SI.') and typename[18:] in TYPES,
                        'syntax', f'unsupported parameter type {typename}')
                key = self.new_name()
                require(len(self.parameters) < 256, 'resource_limit', 'too many scalar parameters')
                self.pop('=')
                self.parameters[key] = self.binding(typename[18:])
                self.pop(';')
            else:
                constructor = self.path()
                require(constructor.startswith('SimHeat.') and constructor[8:] in SLOTS,
                        'syntax', f'unsupported constructor {constructor}')
                kind = constructor[8:]
                key = self.new_name()
                self.pop('(')
                fields = {}
                while self.peek() != ')':
                    slot = self.pop()
                    require(slot in SLOTS[kind] and slot not in fields, 'parameters', f'invalid/duplicate {slot}')
                    self.pop('=')
                    fields[slot] = self.binding(SLOTS[kind][slot])
                    if self.peek() != ',':
                        break
                    self.pop(',')
                    require(self.peek() != ')', 'syntax', 'trailing comma')
                self.pop(')'); self.pop(';')
                require(fields.keys() == SLOTS[kind].keys(), 'parameters', f'missing parameters for {key}')
                for slot, b in fields.items():
                    require(b.value > 0 and math.isfinite(b.value), 'physical_domain', f'{key}.{slot} must be positive')
                self.components[key] = Component(kind, fields)
                counts = {k: sum(c.kind == k for c in self.components.values()) for k in SLOTS}
                require(counts['Body'] <= 8 and counts['FixedTemperature'] <= 8 and
                        counts['RodArea'] + counts['RodCircular'] <= 32,
                        'resource_limit', 'component limit exceeded')
        connections = []
        if self.peek() == 'equation':
            self.pop('equation')
            while self.peek() != 'end':
                self.pop('connect'); self.pop('(')
                a = self.path(); self.pop(','); b = self.path()
                self.pop(')'); self.pop(';')
                connections.append((a, b))
                require(len(connections) <= 128, 'resource_limit', 'connection limit exceeded')
        self.pop('end'); self.pop(name); self.pop(';')
        require(self.peek() == '<EOF>', 'syntax', 'trailing content after model')
        require(bool(self.components), 'parameters', 'empty model')
        return Model(name, self.parameters, self.components, tuple(connections))


def parse_model(text: str) -> Model:
    return Parser(text).parse()


@dataclass(frozen=True)
class Topology:
    nodes: tuple[tuple[str, ...], ...]
    node_of: dict[str, int]
    # (rod identity, a node, b node, independently checked admitted conductance)
    edges: tuple[tuple[str, int, int, float], ...]
    networks: tuple[tuple[int, ...], ...]
    anchored_nodes: frozenset[int]


def topology(model: Model, mode: str) -> Topology:
    require(mode in ('steady', 'transient'), 'mode', 'unknown mode')
    ports = model.ports()
    parents = {p: p for p in ports}
    def root(p):
        while parents[p] != p:
            parents[p] = parents[parents[p]]
            p = parents[p]
        return p
    connected = set()
    pairs = set()
    for a, b in model.connections:
        require(a in ports and b in ports, 'connection', f'unknown port in {a}, {b}')
        pair = tuple(sorted((a, b)))
        require(a != b and pair not in pairs, 'connection', 'self/duplicate connection')
        pairs.add(pair); connected.update(pair)
        parents[root(a)] = root(b)
    grouped = {}
    for p in sorted(ports):
        grouped.setdefault(root(p), []).append(p)
    nodes = tuple(sorted(tuple(g) for g in grouped.values()))
    require(len(nodes) <= 64, 'resource_limit', 'node limit exceeded')
    node_of = {p: i for i, g in enumerate(nodes) for p in g}
    anchored = set()
    bodies, boundaries, edges = [], [], []
    for i, g in enumerate(nodes):
        owners = [p.split('.')[0] for p in g if model.components[p.split('.')[0]].kind in ('Body', 'FixedTemperature')]
        if len(owners) > 1:
            temperatures = [model.components[o].value('T_initial' if model.components[o].kind == 'Body' else 'T') for o in owners]
            code = 'inconsistent_constraints' if len(set(temperatures)) > 1 else 'unsupported_topology'
            raise Refusal(code, 'multiple storage/boundary owners at one ideal node')
        if owners:
            anchored.add(i)
    for name, c in model.components.items():
        if c.kind == 'Body':
            capacity = c.value('m') * c.value('c')
            require(math.isfinite(capacity) and capacity > 0, 'numerical_domain', 'invalid derived capacity')
            bodies.append(name)
        elif c.kind == 'FixedTemperature':
            require(name + '.port' in connected, 'connection', 'unconnected boundary')
            boundaries.append(name)
        else:
            a, b = name + '.port_a', name + '.port_b'
            require(a in connected and b in connected, 'connection', f'unconnected rod endpoint: {name}')
            i, j = node_of[a], node_of[b]
            require(i != j, 'unsupported_topology', 'rod self-loop')
            area = c.value('A') if c.kind == 'RodArea' else math.pi * c.value('d') * c.value('d') / 4
            conductance = c.value('k') * area / c.value('L')
            require(math.isfinite(area) and area > 0 and math.isfinite(conductance) and conductance > 0,
                    'numerical_domain', 'invalid derived area/conductance')
            edges.append((name, i, j, conductance))
    require((not bodies and edges and boundaries) if mode == 'steady' else bool(bodies),
            'mode', 'steady needs rods/boundaries and no bodies; transient needs a body')
    adjacency = {i: set() for i in range(len(nodes))}
    for _, a, b, _ in edges:
        adjacency[a].add(b); adjacency[b].add(a)
    remaining, networks = set(adjacency), []
    while remaining:
        pending, group = [min(remaining)], set()
        while pending:
            i = pending.pop()
            if i not in group:
                group.add(i); pending.extend(adjacency[i] - group)
        remaining -= group
        require(bool(group & anchored), 'underdetermined', 'floating conductor network')
        networks.append(tuple(sorted(group)))
    return Topology(nodes, node_of, tuple(sorted(edges)), tuple(networks), frozenset(anchored))


def junction_condition(t: Topology) -> float:
    """Scaled 2-norm conditioning preflight; not a physical solution/reference."""
    unknown = [i for i in range(len(t.nodes)) if i not in t.anchored_nodes]
    if not unknown:
        return 1.0
    try:
        import numpy as np
    except ImportError as exc:
        raise Refusal('dependency_missing', 'NumPy needed for junction conditioning') from exc
    index = {node: i for i, node in enumerate(unknown)}
    matrix = np.zeros((len(unknown), len(unknown)))
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        try:
            for _, a, b, g in t.edges:
                for x, y in ((a, b), (b, a)):
                    if x in index:
                        matrix[index[x], index[x]] += g
                        if y in index:
                            matrix[index[x], index[y]] -= g
            d = np.sqrt(np.diag(matrix))
            require(bool(np.all(d > 0)), 'numerical_domain', 'zero junction diagonal')
            scaled = (matrix / d[:, None]) / d[None, :]
            # Reject loss of a nonzero coupling rather than silently dropping it.
            require(not bool(np.any((matrix != 0) & (scaled == 0))), 'numerical_domain', 'scaled coupling underflow')
            condition = float(np.linalg.cond(scaled, 2))
        except (FloatingPointError, np.linalg.LinAlgError) as exc:
            raise Refusal('numerical_domain', 'junction conditioning failed') from exc
    require(math.isfinite(condition) and condition <= 1e8, 'numerical_domain', 'poorly conditioned junction system')
    return condition


def requests(model: Model, authored: list) -> dict:
    """Return every request status; one invalid request refuses the investigation."""
    require(isinstance(authored, list) and len(authored) <= 32, 'request', 'invalid request list')
    ports, seen, results = model.ports(), set(), []
    for item in authored:
        try:
            require(isinstance(item, dict), 'request', 'request must be an object')
            rid, op = item.get('id'), item.get('op')
            require(isinstance(rid, str) and IDENT.fullmatch(rid) is not None and rid not in seen,
                    'request', 'invalid/duplicate request ID')
            seen.add(rid)
            require(op in ('temperature', 'temperatureDifference', 'heatFlow', 'energyChange'), 'unsupported_observation', 'unsupported operation')
            keys = {'id', 'op', 'a', 'b'} if op == 'temperatureDifference' else {'id', 'op', 'target'}
            require(set(item) == keys, 'request', 'unexpected/missing request fields')
            operands = [item['a'], item['b']] if op == 'temperatureDifference' else [item['target']]
            require(all(isinstance(x, str) for x in operands), 'request', 'reference must be a string')
            if op in ('temperature', 'temperatureDifference'):
                valid = all(x in ports for x in operands)
            else:
                c = model.components.get(operands[0])
                valid = c is not None and (c.kind.startswith('Rod') if op == 'heatFlow' else c.kind == 'Body')
            require(valid, 'unknown_observation_target', 'unknown/incompatible target')
            results.append({'id': rid, 'status': 'not_computed', 'unit': 'W' if op == 'heatFlow' else 'J' if op == 'energyChange' else 'K'})
        except Refusal as exc:
            results.append({'id': item.get('id') if isinstance(item, dict) else None,
                            'status': 'refused', 'code': exc.code, 'reason': str(exc)})
    return {'admitted': all(r['status'] != 'refused' for r in results), 'requests': results}


def internal_exports(model: Model) -> tuple[str, ...]:
    """Stable candidate wrapper fields; native availability is still unqualified."""
    fields = {'Body': ('T', 'Q_in', 'dU', 'C'),
              'RodArea': ('T_a', 'T_b', 'Q_flow', 'G'),
              'RodCircular': ('T_a', 'T_b', 'Q_flow', 'G', 'A'),
              'FixedTemperature': ('T', 'Q_to_network')}
    return tuple(sorted(f'{name}.{f}' for name, c in model.components.items() for f in fields[c.kind]))
