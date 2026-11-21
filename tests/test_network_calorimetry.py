from fractions import Fraction
import json
from decimal import Decimal, localcontext
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from tools.network_calorimetry import investigate

ROOT = Path(__file__).resolve().parents[1]
D2 = ROOT / "h1/cases/D2"
PIN = "befcb977a08bdb4d3f15d903ebafccf910d83675f8d1a92f1988bca74a8a547a"


class NetworkCalorimetryTests(TestCase):
    def test_two_body_equilibrium_and_finite_time_spread(self):
        result = investigate(D2/"study.json", D2, ROOT/"h1/reference_cases/D2.json", PIN)
        component, = result["components"]
        self.assertEqual(Fraction(component["equilibriumTemperatureK"]), Fraction("308.15"))
        self.assertEqual(component["heatCapacityJPerK"], "2000")
        self.assertEqual(result["finalTimeSeconds"], "9375")
        # G = 0.2 W/K; decay constant G*(1/C_hot + 1/C_cold) = 1/1875 s.
        lo, hi = map(Fraction, component["finalSpreadBoundsK"])
        with localcontext() as ctx:
            ctx.prec = 70
            expected = Fraction(Decimal(60) * Decimal(-5).exp())
        # The two rounded Decimal operations contribute less than 1e-68 K here.
        self.assertLessEqual(lo, expected - Fraction(1, 10**68))
        self.assertGreaterEqual(hi, expected + Fraction(1, 10**68))
        self.assertLess(hi-lo, Fraction(1, 10**10))
        self.assertLessEqual(Fraction(component["maximumStoredEnergyResidualJ"]),
                             Fraction(component["storedEnergyResidualBoundJ"]))

    def test_disconnected_reservoir_cannot_supply_the_isolated_pair(self):
        model = (D2/"model.mo").read_text().replace("equation", """  SimHeat.Body third(m=2,c=400,T_initial=310);
  SimHeat.FixedTemperature bath(T=400);
  SimHeat.RodArea leg(k=10,L=1,A=0.01);
equation
  connect(third.port,leg.port_a);
  connect(bath.port,leg.port_b);""").encode()
        study = json.loads((D2/"study.json").read_bytes())
        study["model"]["sha256"] = sha256(model).hexdigest()
        for slot in ("third.m", "third.c", "third.T_initial", "bath.T", "leg.k", "leg.L", "leg.A"):
            study["provenance"].append(dict(target=slot, kind="illustrative", locator="unit test",
                                            note="Disconnected heated body for component isolation."))
        desc = json.dumps(study).encode()
        facts = json.loads((ROOT/"h1/reference_cases/D2.json").read_bytes())
        facts["nodes"].extend(["thirdNode", "bathNode"])
        facts["bodies"]["third"] = dict(node="thirdNode", m=2, c=400, T_initial=310)
        facts["boundaries"]["bath"] = dict(node="bathNode", T=400)
        facts["rods"]["leg"] = dict(kind="RodArea", a="thirdNode", b="bathNode", k=10, L=1, A=0.01)
        facts.update(modelSha256=sha256(model).hexdigest(), studySha256=sha256(desc).hexdigest())
        raw = json.dumps(facts).encode()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name, data in (("model.mo", model), ("study.json", desc), ("facts.json", raw)):
                (root/name).write_bytes(data)
            components = investigate(root/"study.json", root, root/"facts.json",
                                     sha256(raw).hexdigest())["components"]
        by_status = {c["status"]: c for c in components}
        self.assertEqual(len(components), 2)
        isolated = by_status["isolated"]
        self.assertEqual(isolated["bodies"], ["cold", "hot"])
        self.assertEqual(Fraction(isolated["equilibriumTemperatureK"]), Fraction("308.15"))
        self.assertEqual(by_status["externally_maintained"],
                         {"bodies": ["third"], "reservoirs": ["bath"], "status": "externally_maintained"})

    def test_modified_facts_refused_against_reviewed_pin(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "modified.json"
            path.write_bytes((ROOT/"h1/reference_cases/D2.json").read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "source bytes differ"):
                investigate(D2/"study.json", D2, path, PIN)
