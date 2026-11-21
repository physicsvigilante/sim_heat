from fractions import Fraction
from unittest import TestCase

from mpmath import mp

from tests.test_join_thermal_networks import LEFT, RIGHT
from tools.latent_heat_bath import investigate


class SupportedPhaseBathTests(TestCase):
    def test_competing_fluxes_on_equivalent_star_and_triangle(self):
        for network in (LEFT, RIGHT):
            for enclosure, mode in ((310, "freezing"), (420, "melting")):
                result = investigate(network, "middle", "300", "200000", "0.2", "0.3", "1000",
                                     (str(enclosure), "1", "0.8", "0.0000000567"), "warm")
                with mp.workdps(100):
                    # Direct balance of three rods joined at a single junction.
                    def joint(face):
                        return (2*face + 3*300 + 5*280) / 10
                    factor = mp.mpf("0.8") * mp.mpf("0.0000000567")
                    face = mp.findroot(lambda t: 2*(t-joint(t)) - factor*(enclosure**4-t**4), 310)
                    support = 5*(joint(face)-280)
                    bath = 3*(joint(face)-300)
                    def check(pair, expected):
                        low, high = map(Fraction, pair)
                        reference = Fraction(mp.nstr(expected, 90))
                        self.assertTrue(low <= reference <= high)
                        self.assertLess(high-low, Fraction(1, 10**11))
                    self.assertEqual(result["phaseProcess"], mode)
                    self.assertEqual(set(result["maintainedReservoirInflowBoundsW"]), {"cool"})
                    check(result["maintainedReservoirInflowBoundsW"]["cool"], support)
                    check(result["radiatingSurface"]["netHeatToEnclosureBoundsW"], -support-bath)
                    check(result["bathInflowDuringPlateauBoundsW"], bath)
                    check(result["radiatingSurface"]["temperatureBoundsK"], face)
                    check(result["remainingLiquidBoundsKg"], mp.mpf("0.3") + bath/200)
                    check(result["exhaustionTimeBoundsS"], (40000 if bath > 0 else -60000)/bath)

    def test_equal_drive_and_invalid_face(self):
        args = (LEFT, "middle", "280", "200000", "0.2", "0.3", "1")
        exterior = ("280", "1", "0.8", "0.0000000567")
        result = investigate(*args, exterior, "warm")
        self.assertEqual(result["bathInflowDuringPlateauBoundsW"], ["0", "0"])
        self.assertIsNone(result["exhaustionTimeBoundsS"])
        for settings in ((exterior, "middle"), (exterior, "absent"), (exterior, None), (None, "warm")):
            with self.assertRaises(ValueError):
                investigate(*args, *settings)
