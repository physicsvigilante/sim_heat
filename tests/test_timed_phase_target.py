from fractions import Fraction as F
from unittest import TestCase

from tests.test_join_thermal_networks import LEFT, RIGHT
from tools.latent_heat_bath import investigate as forward
from tools.phase_balance_temperature import investigate


class TimedPhaseTargetTests(TestCase):
    def test_inventory_mass_energy_and_forward_bracket(self):
        for network in (LEFT, RIGHT):
            for process, q in (("melt", 20), ("freeze", -20)):
                target = (process, "0.1", "1000", "200000", "0.1", "0.3")
                result = investigate(network, "middle", "warm", "300", "1", "0.8", "0.0000000567", target)
                ledger = result["phaseTarget"]
                self.assertEqual(F(ledger["energyIntoBathJ"]), 1000*q)
                self.assertEqual(F(result["requiredBathInflowW"]), q)
                self.assertEqual(F(ledger["finalSolidKg"]), F("0.1") - F(q, 200))
                self.assertEqual(F(ledger["finalLiquidKg"]), F("0.3") + F(q, 200))
                joint = 300 + F(q, 3)
                radiant = q + 5*(joint-280)
                face = joint + radiant/2
                fourth = face**4 + radiant/(F(".8")*F("0.0000000567"))
                lo, hi = map(F, result["requiredEnclosureTemperatureBoundsK"])
                self.assertTrue(lo**4 <= fourth <= hi**4)
                self.assertLess(hi - lo, F(1, 10**15))
                # At neighbouring integral temperatures the forward rates bracket the target.
                below = lo.numerator // lo.denominator
                for env, less in ((below, True), (below+1, False)):
                    out = forward(network, "middle", "300", "200000", "0.1", "0.3", "1000",
                                  (str(env), "1", "0.8", "0.0000000567"), "warm")
                    lower, upper = map(F, out["bathInflowDuringPlateauBoundsW"])
                    self.assertTrue(upper < q if less else lower > q)
                    if process == "melt":
                        self.assertEqual(out["plateauStatus"], "coexisting" if less else "exhausted")

    def test_refuse_inventory_duration_and_unreachable_targets(self):
        for spec in (("melt", "0.2", "1", "100", "0.1", "1"),
                     ("freeze", "0.2", "1", "100", "1", "0.1"),
                     ("melt", "0.1", "0", "100", "1", "1"),
                     ("freeze", "1", "1", "200000", "1", "1"),
                     ("steam", "1", "1", "100", "1", "1"),
                     ("melt", "1", "1")):
            with self.assertRaises(ValueError):
                investigate(LEFT, "middle", "warm", "300", "1", "0.8", "0.0000000567", spec)
