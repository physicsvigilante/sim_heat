from decimal import Decimal, localcontext
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from qualification.h1_n13.conduction import prepare
from tests.test_body_relaxation import ARGS as LOADED
from tests.test_network_calorimetry import D2, PIN, ROOT
from tools.isolated_pair_exchange import investigate

ARGS = D2/"study.json", D2, ROOT/"h1/reference_cases/D2.json", PIN


class IsolatedPairTests(TestCase):
    def encloses(self, bounds, expected):
        lo, hi = map(Fraction, bounds)
        self.assertTrue(lo <= expected <= hi)
        self.assertLess(hi-lo, Fraction(1, 10**10))

    def test_signed_exchange_and_full_difference_history(self):
        law = investigate(*ARGS)
        self.assertEqual((law["fromBody"], law["toBody"]), ("cold", "hot"))
        self.assertEqual(Fraction(law["equilibriumTemperatureK"]), Fraction("308.15"))
        self.assertEqual(Fraction(law["asymptoticHeatFromFirstToSecondJ"]), -22500)
        self.encloses(law["initialHeatFromFirstToSecondBoundsW"], -12)
        self.encloses(law["differenceTimeConstantBoundsSeconds"], 1875)
        full = prepare(*ARGS)
        difference = full["requests"]["difference"]["values"]
        radius = Fraction(full["maxErrorToBudgetBySeries"]["requests"]["difference"])/10**8
        self.assertEqual(len(difference), 1001)
        with localcontext() as ctx:
            ctx.prec = 80
            for i, sample in enumerate(difference):
                expected = Decimal(60)*(-Decimal(i)/200).exp()
                self.assertLessEqual(abs(Fraction(sample)-Fraction(expected)), radius+Fraction(1,10**74))

    def test_reversed_parallel_path_with_equal_starting_temperatures(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = (D2/"model.mo").read_text().replace("353.15", "293.15").replace(
                "equation", """  SimHeat.RodArea extra(k=300,L=1,A=0.001);
equation
  connect(cold.port, extra.port_a);
  connect(extra.port_b, hot.port);""").encode()
            study = json.loads(ARGS[0].read_bytes())
            study["model"]["sha256"] = sha256(model).hexdigest()
            for field in ("k", "L", "A"):
                study["provenance"].append(dict(target="extra."+field, kind="illustrative",
                                                locator="pair test", note="Additional parallel path."))
            descriptor = json.dumps(study).encode()
            facts = json.loads(ARGS[2].read_bytes())
            facts["bodies"]["hot"]["T_initial"] = 293.15
            facts["rods"]["extra"] = dict(kind="RodArea", k=300, L=1, A=0.001, a="right", b="left")
            facts.update(modelSha256=sha256(model).hexdigest(), studySha256=sha256(descriptor).hexdigest())
            raw = json.dumps(facts).encode()
            for name, data in (("model.mo", model), ("study.json", descriptor), ("facts.json", raw)):
                (root/name).write_bytes(data)
            law = investigate(root/"study.json", root, root/"facts.json", sha256(raw).hexdigest())
            self.encloses(law["effectiveConductanceBoundsWPerK"], Fraction(1,2))
            self.encloses(law["differenceTimeConstantBoundsSeconds"], 750)
            self.assertEqual(Fraction(law["asymptoticHeatFromFirstToSecondJ"]), 0)
            self.encloses(law["initialHeatFromFirstToSecondBoundsW"], 0)

    def test_externally_maintained_network_refused(self):
        with self.assertRaisesRegex(ValueError, "isolated transient pair"):
            investigate(*LOADED)
