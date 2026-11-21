"""Offline candidate reference for constant-property H1 conduction networks."""
import argparse
from decimal import Decimal
from hashlib import sha256
from fractions import Fraction as F
from math import factorial, isfinite, ulp
import json
from pathlib import Path

from h1.model import Binding, Parser, internal_exports
from h1.reference import networks
from h1.study import checked_path, load_study
from h1.verification import bind_reference
from qualification.h1_n4.static_physical import _decimal_token, parse_facts
from qualification.h1_n5.thermal_graph import assemble
from qualification.h1_n7.verified_junctions import _enclosure_from_verified_barrier
from qualification.h1_n11.rational_dynamic_proof import (
    Box, SCALE, TAYLOR, apply, ceil_fraction, dot, field_unit, identity, product,
)

ZERO = Box.exact(0)
ONE = Box.exact(1)
SCHEMA = "sim_heat.h1_n13.offline_conduction_candidate/1"


def require(ok, message):
    if not ok:
        raise ValueError("h1_n13: " + message)


class ExactBindings(Parser):
    """Replay admitted bindings with exact source decimals and SI conversions."""

    def literal(self):
        start = self.i
        super().literal()
        return F(_decimal_token("".join(self.tokens[start:self.i])))

    def binding(self, expected_type):
        start = self.i
        binding = super().binding(expected_type)
        # The inherited multiply and divide conversions preserve Fractions.
        # Its Celsius offset is a float, so reconstruct that single offset exactly.
        if self.tokens[start:start+5] == ["SimHeat", ".", "Units", ".", "from_degC"]:
            degrees = F(_decimal_token("".join(self.tokens[start+6:self.i-1])))
            return Binding(degrees + F(27315, 100), binding.quantity_type)
        return binding


def check_exact_inputs(study, facts):
    descriptor = study.path.read_bytes()
    require(sha256(descriptor).hexdigest() == study.sha256, "study bytes changed")
    analysis = json.loads(descriptor, parse_float=Decimal)["analysis"]
    require(analysis == facts["analysis"], "exact source analysis differs")
    folder = study.path.parent
    path = checked_path(folder, study.data["model"]["path"], folder, ".mo")
    raw = path.read_bytes()
    require(sha256(raw).hexdigest() == study.model_sha256, "model bytes changed")
    model = ExactBindings(raw.decode("utf8")).parse()
    for group in ("bodies", "boundaries", "rods"):
        for name, record in facts[group].items():
            for key, binding in model.components[name].fields.items():
                require(binding.value == F(record[key]), f"exact source fact differs: {name}.{key}")


def interval(bounds):
    return Box.bounds(*map(F, bounds))


def step_matrix(matrix):
    """Outward Horner exponential; scale to the proven tail domain and square."""
    n = len(matrix)
    rho = max(sum(x.absolute_upper() for x in row) for row in matrix)
    halves = 0
    while rho > F(1, 2):
        halves += 1
        require(halves <= 32, "step exceeds bounded exponential scaling")
        rho /= 2
    x = [[v / (2**halves) for v in row] for row in matrix]
    unit = identity(n)
    h = unit
    for k in range(TAYLOR, 0, -1):
        hx = product(x, h)
        h = [[unit[i][j] + hx[i][j] / k for j in range(n)] for i in range(n)]
    radius = ceil_fraction(2 * rho**(TAYLOR+1) * SCALE / factorial(TAYLOR+1))
    h = [[Box(v.low-radius, v.high+radius) for v in row] for row in h]
    require(all(v == ZERO for v in matrix[-1]), "invalid affine row")
    h[-1] = unit[-1]
    for _ in range(halves):
        h = product(h, h)
    return h


class Conduction:
    def __init__(self, graph, components):
        self.components = components
        self.nodes = graph["nodes"]
        rows = graph["nodeEquations"]
        self.bodies = [n for n in self.nodes if rows[n]["kind"] == "body"]
        self.fixed = [n for n in self.nodes if rows[n]["kind"] == "fixed_boundary"]
        self.junctions = [n for n in self.nodes if rows[n]["kind"] == "ownerless_junction"]
        self.owner = {n: rows[n]["owner"] for n in self.bodies + self.fixed}
        self.capacity = {n: Box.exact(F(rows[n]["capacityJPerKExact"])) for n in self.bodies}
        self.initial = {n: F(rows[n]["initialTemperatureKExact"]) for n in self.bodies}
        self.initial.update({n: F(rows[n]["temperatureKExact"]) for n in self.fixed})
        self.origin = min(self.initial.values())
        self.span = max(F(1), max(self.initial.values()) - self.origin)
        self.normal = {n: Box.exact((t-self.origin)/self.span) for n, t in self.initial.items()}
        self.edges = []
        self.area = {}
        self.ports = {name+".port": node for node, name in self.owner.items()}
        rational_edges = []
        for name, rod in graph["rods"].items():
            a, b = rod["fromNode"], rod["toNode"]
            lo, hi = map(F, rod["conductanceWPerKExactPhysicalInterval"])
            rational_edges.append((name, a, b, lo, hi))
            self.edges.append((name, a, b, Box.bounds(lo, hi)))
            if rod["kind"] == "RodCircular":
                self.area[name] = interval(rod["areaM2ExactPhysicalInterval"])
            self.ports[name+".port_a"] = a
            self.ports[name+".port_b"] = b

        # Linearity and preservation of a constant temperature give the
        # Dirichlet influence of each owner from a positive 1 K / 2 K basis.
        self.weights = {n: [] for n in self.nodes}
        for selected in self.bodies + self.fixed:
            known = {n: F(1 + (n == selected)) for n in self.initial}
            boxes, _ = _enclosure_from_verified_barrier(self.junctions, known, rational_edges)
            for n in self.nodes:
                weight = Box.exact(known[n]) if n in known else Box.bounds(*boxes[n])
                self.weights[n].append(weight - ONE)

    def values(self, owner_values):
        return {n: dot(weights, owner_values) for n, weights in self.weights.items()}

    def flows(self, values):
        incoming = {n: ZERO for n in self.nodes}
        signed = {}
        for name, a, b, g in self.edges:
            q = g * (values[a] - values[b])
            signed[name] = q
            incoming[a] = incoming[a] - q
            incoming[b] = incoming[b] + q
        return signed, incoming

    def evolution(self, stop, count):
        # State is normalized body temperature, its integral in t/stop, and 1.
        size = len(self.bodies)
        dim = 2*size + 1
        matrix = [[ZERO for _ in range(dim)] for _ in range(dim)]
        for j in range(size+1):
            owners = [Box.exact(i == j) for i in range(size)]
            owners.extend(self.normal[n] if j == size else ZERO for n in self.fixed)
            _, rates = self.flows(self.values(owners))
            for i, n in enumerate(self.bodies):
                matrix[i][j if j < size else -1] = rates[n] * (stop/count) / self.capacity[n]
        for i in range(size):
            matrix[size+i][i] = Box.exact(F(1, count))
        initial = [self.normal[n] for n in self.bodies] + [ZERO]*size + [ONE]
        return step_matrix(matrix), initial

    def sample(self, state, elapsed, stop, requests):
        size = len(self.bodies)
        owners = state[:size] + [self.normal[n] for n in self.fixed]
        u = self.values(owners)
        temp = {n: x*self.span + self.origin for n, x in u.items()}
        flows, incoming = self.flows(temp)
        require(all(incoming[n].contains_zero() for n in self.junctions), "junction imbalance")
        exports = {}
        for name, a, b, g in self.edges:
            for field, val in (("T_a",temp[a]), ("T_b",temp[b]), ("G",g),
                               ("Q_flow",flows[name]), ("port_a.Q_flow",flows[name]),
                               ("port_b.Q_flow",-flows[name])):
                exports[name+"."+field] = val
            if name in self.area:
                exports[name+".A"] = self.area[name]
        for n, name in self.owner.items():
            exports[name+".T"] = temp[n]
            if n in self.capacity:
                exports[name+".C"] = self.capacity[n]
                exports[name+".Q_in"] = incoming[n]
                exports[name+".dU"] = self.capacity[n] * (temp[n] - self.initial[n])
            else:
                exports[name+".Q_to_network"] = -incoming[n]
        observed = {}
        for r in requests:
            op = r["op"]
            if op == "temperature":
                val = temp[self.ports[r["target"]]]
            elif op == "temperatureDifference":
                val = temp[self.ports[r["a"]]] - temp[self.ports[r["b"]]]
            else:
                suffix = {"heatFlow": ".Q_flow", "energyChange": ".dU"}[op]
                val = exports[r["target"]+suffix]
            observed[r["id"]] = val
        integrals = {}
        if stop is not None:
            # Common temperature offset cancels in every rod difference.
            owner_int = [x*(stop*self.span) for x in state[size:2*size]]
            owner_int.extend(self.normal[n]*(elapsed*self.span) for n in self.fixed)
            _, net = self.flows(self.values(owner_int))
            for n in self.bodies:
                name = self.owner[n]
                integrals[name+".Q_in"] = net[n]
                require((exports[name+".dU"]-net[n]).contains_zero(), "body energy imbalance")
            for n in self.fixed:
                integrals[self.owner[n]+".Q_to_network"] = -net[n]
            for component in self.components:
                stored = sum((exports[self.owner[n]+".dU"] for n in self.bodies if n in component), ZERO)
                supply = sum((-net[n] for n in self.fixed if n in component), ZERO)
                require((stored-supply).contains_zero(), "network energy imbalance")
        else:
            for component in self.components:
                supply = sum((-incoming[n] for n in self.fixed if n in component), ZERO)
                require(supply.contains_zero(), "steady network imbalance")
        return exports, observed, integrals


def bounded_centre(box, unit):
    lo, hi = box.span()
    centre = float((lo+hi)/2)
    require(isfinite(centre), "nonfinite reference centre")
    error = max(abs(F(centre)-lo), abs(F(centre)-hi))
    # Use conservative absolute floors, including the stricter initial K bound.
    limits = {"K": F(1,10**8), "W": F(1,10**8), "J": F(1,10**5)}
    if unit in limits:
        limit = limits[unit]
    else:
        require(unit in ("W/K","J/K","m2") and centre > 0, "invalid static constant")
        limit = F(64,100)*F(ulp(centre))
    require(error <= limit, "outward enclosure exceeds output budget in " + unit)
    return centre, error/limit


def prepare(study_path, root, facts_path, expected_facts_sha):
    """Generate candidates from independently supplied source facts on their exact grid."""
    study = load_study(Path(study_path), Path(root))
    require(study.request_report["admitted"], "refused investigation")
    p = Path(facts_path)
    require(p.is_file() and p.stat().st_size <= 262144 and
            not any(q.is_symlink() for q in (p, *p.parents)), "invalid source facts path")
    raw = p.read_bytes()
    facts = parse_facts(raw, expected_sha256=expected_facts_sha)
    bind_reference(study, json.loads(raw))
    check_exact_inputs(study, facts)
    network = Conduction(assemble(raw, expected_sha256=expected_facts_sha), networks(facts))
    units = {r["id"]:r["unit"] for r in study.request_report["requests"]}
    names = set(internal_exports(study.model))
    families = {k: {} for k in ("exports", "requests", "integrals")}
    maxima = {k: {} for k in families}
    grid = []
    stop = None
    count = 0
    state = []
    if facts["mode"] == "transient":
        count = facts["analysis"]["intervals"]
        stop = F(facts["analysis"]["stopTime"])
        step, state = network.evolution(stop, count)
    for i in range(count+1):
        elapsed = stop*i/count if count else None
        if count:
            grid.append(float(elapsed))
        samples = network.sample(state, elapsed, stop, study.data["requests"])
        require(set(samples[0]) == names and set(samples[1]) == units.keys(), "output inventory drift")
        for family, items in zip(families, samples):
            for name, box in items.items():
                unit = field_unit(name) if family == "exports" else units[name] if family == "requests" else "J"
                centre, ratio = bounded_centre(box, unit)
                series = families[family].setdefault(name, {"unit":unit, "values":[]})
                series["values"].append(centre)
                maxima[family][name] = max(maxima[family].get(name, F(0)), ratio)
        if i < count:
            state = apply(step, state)
    return {"schema":SCHEMA, "mode":facts["mode"], "timeSeconds":grid,
            "studySha256":study.sha256, "modelSha256":study.model_sha256,
            "factsSha256":expected_facts_sha, **families,
            "maxErrorToBudgetBySeries":{k:{n:str(v) for n,v in d.items()} for k,d in maxima.items()},
            "nativeExecuted":False, "nativeQualified":False, "runnerConsumable":False,
            "independentlyCertifiedReference":False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("study", "root", "facts", "facts-sha256"):
        parser.add_argument("--"+arg, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.study, args.root, args.facts, args.facts_sha256),
                     sort_keys=True, allow_nan=False))
