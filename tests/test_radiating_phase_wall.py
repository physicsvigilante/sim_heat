from fractions import Fraction
from unittest import TestCase

from mpmath import mp

from tests.test_loaded_thermal_ports import LEFT, LINK
from tools.latent_heat_bath import investigate


class RadiatingPhaseWallTests(TestCase):
    def test_melting_and_freezing_with_free_surface(self):
        for environment in ("240", "350"):
            for port in ("hot", "cold"):
                args = (LINK, port, "300", "200000", "0.2", "0.3")
                exterior = (environment, "0.8", "0.7", "0.0000000567")
                with mp.workdps(95):
                    # Eliminate surface temperature in favour of power INTO the bath.
                    factor = mp.mpf("0.8") * mp.mpf("0.7") * mp.mpf("0.0000000567")
                    q = mp.findroot(lambda q: q - factor * (mp.mpf(environment)**4 -
                                                           (300 + q/2)**4), 0)
                    temp = 300 + q/2
                    end = (40000 if q > 0 else 60000) / abs(q)
                    def check(bounds, expected):
                        lo, hi = map(Fraction, bounds)
                        self.assertLessEqual(lo, Fraction(mp.nstr(expected, 85)))
                        self.assertGreaterEqual(hi, Fraction(mp.nstr(expected, 85)))
                        self.assertLess(hi - lo, Fraction(1, 10**11))
                    for t in (1, 100000):
                        result = investigate(*args, str(t), exterior)
                        surface = result["radiatingSurface"]
                        self.assertNotEqual(surface["port"], port)
                        check(surface["temperatureBoundsK"], temp)
                        check(surface["netHeatToEnclosureBoundsW"], -q)
                        check(result["bathInflowDuringPlateauBoundsW"], q)
                        check(result["exhaustionTimeBoundsS"], end)
                        energy = min(mp.mpf(40000), max(mp.mpf(-60000), q*t))
                        check(result["latentEnergyIntoBathBoundsJ"], energy)
                        check(result["remainingLiquidBoundsKg"], mp.mpf("0.3") + energy/200000)

    def test_absent_exchange_and_scope(self):
        for env, eps in (("300", "1"), ("350", "0")):
            result = investigate(LINK, "hot", "300", "200", "1", "1", "20",
                                 (env, "1", eps, "0.0000000567"))
            self.assertEqual(result["phaseProcess"], "equilibrium")
            self.assertIsNone(result["exhaustionTimeBoundsS"])
            self.assertEqual(result["radiatingSurface"]["temperatureBoundsK"], ["300"] * 2)
        for inputs, exterior in ((LEFT, ("300", "1", "1", "0.0000000567")),
                                 (LINK, ("300", "1", "1.1", "0.0000000567")),
                                 (LINK, ("300", "1"))):
            with self.assertRaises(ValueError):
                investigate(inputs, "hot" if inputs == LINK else "warm", "300", "200",
                            "1", "1", "20", exterior)
