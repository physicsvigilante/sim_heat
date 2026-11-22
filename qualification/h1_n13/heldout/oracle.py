"""Replay: python -B oracle.py first-output.json.gz (standard library only)."""
from decimal import Decimal as D, getcontext
from fractions import Fraction
from hashlib import sha256
import gzip
import json
import math
from pathlib import Path
import sys

getcontext().prec = 80
HERE = Path(__file__).resolve().parent


def expected(t):
    p, q = (-t / 60).exp(), (-t / 15).exp()
    amber, blue = 305 + 10*p + 40*q, 305 + 10*p - 40*q
    joint, bath = 305 + 5*p, D(305)
    amber_energy, blue_energy = 60*(amber-355), 60*(blue-275)
    export = {}
    for rod, a, b, g, flow in (
        ("upper", amber, joint, 2, 10*p + 80*q),
        ("lower", joint, blue, 2, -10*p + 80*q),
        ("feed", bath, joint, 4, -20*p),
        ("link", blue, amber, 1, -80*q),
    ):
        for field, unit, value in (
            ("T_a", "K", a), ("T_b", "K", b), ("G", "W/K", g),
            ("Q_flow", "W", flow), ("port_a.Q_flow", "W", flow),
            ("port_b.Q_flow", "W", -flow),
        ):
            export[rod+"."+field] = unit, D(value)
    for name, temp, rate, energy in (
        ("amber", amber, -10*p - 160*q, amber_energy),
        ("blue", blue, -10*p + 160*q, blue_energy),
    ):
        for field, unit, value in (
            ("T", "K", temp), ("C", "J/K", 60), ("Q_in", "W", rate),
            ("dU", "J", energy),
        ):
            export[name+"."+field] = unit, D(value)
    export["bath.T"] = "K", bath
    export["bath.Q_to_network"] = "W", -20*p
    request = {"joint": ("K", joint), "lowerFlow": ("W", -10*p+80*q),
               "separation": ("K", -80*q), "blueGain": ("J", blue_energy)}
    integrals = {"amber.Q_in": ("J", amber_energy), "blue.Q_in": ("J", blue_energy),
                 "bath.Q_to_network": ("J", -1200*(1-p))}
    return {"exports": export, "requests": request, "integrals": integrals}


def verify(data):
    assert data["schema"] == "sim_heat.h1_n13.offline_conduction_candidate/1"
    assert data["mode"] == "transient"
    for key in ("nativeExecuted", "nativeQualified", "runnerConsumable", "independentlyCertifiedReference"):
        assert data[key] is False
    for name, key in (("facts.json","factsSha256"), ("model.mo","modelSha256"), ("study.json","studySha256")):
        assert data[key] == sha256((HERE / name).read_bytes()).hexdigest()
    assert data["timeSeconds"] == [float(Fraction(i, 10)) for i in range(1201)]
    truth = [expected(D(i)/10) for i in range(1201)]
    result = {}
    for family, inventory in truth[0].items():
        actual = data[family]
        ratios = data["maxErrorToBudgetBySeries"][family]
        assert set(actual) == set(inventory) == set(ratios)
        for name, (unit, initial) in inventory.items():
            assert actual[name]["unit"] == unit
            assert 0 <= Fraction(ratios[name]) <= 1
            values = actual[name]["values"]
            assert len(values) == 1201
            target = [row[family][name][1] for row in truth]
            if unit in ("W/K","J/K"):
                allowance = 64*D.from_float(math.ulp(float(initial)))
                guard = D(0)
                tight = allowance/100
            else:
                scale = max(abs(v) for v in target)
                if unit == "K" and name != "separation":
                    scale = max(D(1), max(abs(v-initial) for v in target))
                allowance = {"K": D("1e-5"), "W": D("1e-6"), "J": D("1e-3")}[unit] + D("1e-6")*scale
                guard = D("1e-65")
                tight = {"K": D("1e-8"), "W": D("1e-8"), "J": D("1e-5")}[unit]
            max_ratio, max_error = D(0), D(0)
            for index, (value, reference) in enumerate(zip(values, target)):
                assert type(value) is float and math.isfinite(value)
                error = abs(D.from_float(value)-reference) + guard
                allowed = allowance/100
                if index == 0 and name in ("amber.T", "blue.T"):
                    allowed = min(allowed, D("1e-8"))
                assert error <= allowed and error <= tight, (family, name, index, error)
                max_ratio = max(max_ratio, error/allowed)
                max_error = max(max_error, error)
            result[family+"."+name] = {"unit":unit, "maxAbsWithGuard":float(max_error),
                                         "maxRatioToOriginalOnePercent":float(max_ratio)}
    return result


if __name__ == "__main__":
    with gzip.open(sys.argv[1], "rt", encoding="utf8") as source:
        print(json.dumps(verify(json.load(source)), indent=2, sort_keys=True))
