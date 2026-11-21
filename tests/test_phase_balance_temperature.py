from fractions import Fraction as F
from unittest import TestCase

from tests.test_join_thermal_networks import LEFT, RIGHT
from tests.test_loaded_thermal_ports import LINK
from tools.latent_heat_bath import investigate as forward
from tools.phase_balance_temperature import investigate


class BalanceTemperatureTests(TestCase):
    def test_zero_bath_flux_with_emission_and_absorption(self):
        sigma = "0.0000000567"
        for network in (LEFT, RIGHT):
            for transition in (270, 300):
                # Zero current through the middle leg pins the joint at the bath.
                # The two remaining legs are 2 W/K at the face and 5 at the support.
                power = 5 * (transition - 280)
                face = transition + F(power, 2)
                moment = face**4 + power / (F(".8") * F(sigma))
                r = investigate(network, "middle", "warm", str(transition), "1", "0.8", sigma)
                for field, expected in (("netHeatFromEnclosureBoundsW", power),
                                        ("surfaceTemperatureBoundsK", face)):
                    lo, hi = map(F, r[field])
                    self.assertTrue(lo <= expected <= hi)
                lo, hi = map(F, r["balanceEnclosureTemperatureBoundsK"])
                self.assertTrue(lo**4 <= moment <= hi**4)
                self.assertLessEqual(hi - lo, F(2, 10**18))
                below = lo.numerator // lo.denominator
                for env, mode in ((below, "freezing"), (below+1, "melting")):
                    out = forward(network, "middle", str(transition), "200000", "0.2", "0.3", "1",
                                  (str(env), "1", "0.8", sigma), "warm")
                    self.assertEqual(out["phaseProcess"], mode)

    def test_no_support_and_unreachable_balances(self):
        r = investigate(LINK, "hot", "cold", "300", "1", "0.8", "0.0000000567")
        self.assertEqual(r["balanceEnclosureTemperatureBoundsK"], ["300", "300"])
        for bath, face, temp, eps, message in (
                ("middle", "middle", "300", "1", "distinct"),
                ("middle", "unknown", "300", "1", "distinct"),
                ("middle", "warm", "100", "1", "surface temperature"),
                ("middle", "warm", "270", "0.01", "fourth power"),
                ("middle", "warm", "280", "0", "emissivity")):
            with self.assertRaisesRegex(ValueError, message):
                investigate(LEFT, bath, face, temp, "1", eps, "0.0000000567")
