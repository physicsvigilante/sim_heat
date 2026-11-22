from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from tests.test_join_thermal_networks import LEFT
from tests.test_loaded_thermal_ports import LINK
from tools.variable_conductivity import investigate


class VariableConductivityTests(TestCase):
    def test_parallel_wall_and_reversed_insert(self):
        for slope, rate in (("0", 200), ("0.01", 300), ("-0.005", 150)):
            r = investigate(LINK, "280", slope)
            for name, q in (("facing", rate), ("strip", F(rate, 4)), ("insert", -F(3*rate, 4))):
                self.assertEqual(list(map(F, r["rodHeatFlowBoundsW"][name])), [q]*2)
            # The facing and parallel pair have equal reference resistance, hence
            # half of the integrated material potential drops across each.
            lo, hi = map(F, r["portTemperatureBoundsK"]["strip.port_a"])
            def twice_integral(t):
                return (t-280)*(2+F(slope)*(t-280))
            self.assertTrue(twice_integral(lo) <= twice_integral(F(380))/2 <= twice_integral(hi))
            self.assertLess(hi-lo, F(1, 10**20))
            self.assertEqual(r["portTemperatureBoundsK"]["insert.port_b"], r["portTemperatureBoundsK"]["strip.port_a"])

    def test_three_terminal_junction_from_independent_flux_balance(self):
        r = investigate(LEFT, "300", "0.004")
        with mp.workdps(100):
            legs = ((2, 380, "warm"), (3, 330, "middle"), (5, 280, "cool"))
            def flux(g, temperature, joint):
                k_ratio = 1 + mp.mpf("0.004")*((temperature+joint)/2-300)
                return g*(temperature-joint)*k_ratio
            joint = mp.findroot(lambda t: sum(flux(g, k, t) for g, k, _ in legs), 330)
            for field, expected in [(r["portTemperatureBoundsK"]["first.port_b"], joint)] + [
                    (r["terminalSupplyBoundsW"][name], flux(g, k, joint)) for g, k, name in legs]:
                low, high = map(F, field)
                self.assertLessEqual(low, F(mp.nstr(expected, 85)))
                self.assertGreaterEqual(high, F(mp.nstr(expected, 85)))
                self.assertLess(high-low, F(1, 10**20))

    def test_nonpositive_material_and_invalid_inputs_refused(self):
        for ref, slope in (("280", "-0.01"), ("380", "0.02"), ("0", "0"), ("300", "--0.01")):
            with self.assertRaises(ValueError):
                investigate(LINK, ref, slope)
