from fractions import Fraction as F
from unittest import TestCase

from scipy.optimize import root

from tests.test_loaded_thermal_ports import LINK
from tools.radiative_gap import investigate


class RadiativeGapTests(TestCase):
    def test_compare_with_separate_radiosities(self):
        law = investigate(LINK, LINK, "cold", "hot", "0.02", "0.8", "0.5", "0.0000000567")
        # Inputs on both sides are the 1/2 K/W wall, backed at 380 K and 280 K.
        # Solve four primitive equations in the two outward radiosities and plate temperatures.
        def residual(state):
            tl, tr, jl, jr = state
            q = .02*(jl-jr)
            return (2*(380-tl)-q, 2*(tr-280)-q,
                    jl-.8*5.67e-8*tl**4-.2*jr, jr-.5*5.67e-8*tr**4-.5*jl)
        sol = root(residual, [375,285,900,600], tol=1e-12)
        self.assertTrue(sol.success)
        tl, tr, jl, jr = sol.x
        for field, target in (("leftToRightHeatRateBoundsW", .02*(jl-jr)),
                              ("leftPlateTemperatureBoundsK", tl), ("rightPlateTemperatureBoundsK", tr)):
            lo, hi = map(F, law[field])
            self.assertLess(hi-lo, F(1,10**12))
            self.assertAlmostEqual(float(lo), target, places=9)
        lo, hi = map(F, law["leftToRightHeatRateBoundsW"])
        def exact_balance(q):
            tl, tr = 380-q/2, 280+q/2
            return q-F(".02")*F(".0000000567")*(tl**4-tr**4)/(F(5,4)+2-1)
        self.assertLessEqual(exact_balance(lo),0)
        self.assertGreaterEqual(exact_balance(hi),0)

    def test_reversing_the_plates_reverses_flow(self):
        def run(a,b,e1,e2):
            return investigate(LINK, LINK, a,b,"0.02",e1,e2,"0.0000000567")
        forward = run("cold","hot","1","0.7")
        backward = run("hot","cold","0.7","1")
        lo, hi = map(F, forward["leftToRightHeatRateBoundsW"])
        self.assertGreater(lo, 0)
        self.assertEqual(list(map(F,backward["leftToRightHeatRateBoundsW"])),[-hi,-lo])
        self.assertEqual(backward["leftPlateTemperatureBoundsK"], forward["rightPlateTemperatureBoundsK"])

    def test_reflecting_plate_equal_drives_and_invalid_emissivity(self):
        for port, le, re in (("hot","0","1"),("hot","1","0"),("cold","1","1")):
            law = investigate(LINK, LINK, "cold", port, "0.02", le, re, "0.0000000567")
            self.assertEqual(law["leftToRightHeatRateBoundsW"], ["0","0"])
            self.assertEqual(law["leftPlateTemperatureBoundsK"], ["380","380"])
        with self.assertRaisesRegex(ValueError, "emissivities"):
            investigate(LINK, LINK, "cold","hot","0.02","1.01","0.5","0.0000000567")
