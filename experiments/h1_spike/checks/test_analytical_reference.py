"""Standalone reference arithmetic; does NOT exercise Modelica or its solver."""
import math
import unittest


class ThermalReferenceChecks(unittest.TestCase):
    def test_illustration_123_unit_converted_steady(self):
        a = math.pi * (0.02 ** 2) / 4
        g_cu = 0.092 * 4184.0 * a / 0.75
        g_st = 0.011 * 4184.0 * a / 1.25
        q = 100 / (1 / g_cu + 1 / g_st)
        junction_celsius = 100 - q / g_cu
        self.assertAlmostEqual(junction_celsius, 46000 / 493, places=11)
        self.assertAlmostEqual(q, math.pi * 253 / 3081250 * 4184, places=10)
        self.assertAlmostEqual((100 - junction_celsius) * g_cu, (junction_celsius - 0) * g_st, places=10)

    def test_d1_reference(self):
        cap, conductance = 1.0 * 500.0, 100.0 * .001 / .5
        self.assertAlmostEqual(cap / conductance, 2500.0)
        t = 2500.0
        temp = 353.15 + (293.15 - 353.15) * math.exp(-t / 2500.0)
        energy = cap * (temp - 293.15)
        flow = conductance * (353.15 - temp)
        self.assertGreater(flow, 0)
        self.assertGreater(energy, 0)
        self.assertAlmostEqual(energy, 30000 * (1 - math.exp(-1)))

    def test_d2_reference(self):
        c1, c2, conductance = 500.0, 1500.0, 0.2
        tau = 1 / (conductance * (1 / c1 + 1 / c2))
        equilibrium = (c1 * 353.15 + c2 * 293.15) / (c1 + c2)
        self.assertAlmostEqual(tau, 1875.0)
        self.assertAlmostEqual(equilibrium, 308.15)
        for t in (0, tau, 5 * tau):
            delta = 60 * math.exp(-t / tau)
            t1 = equilibrium + c2 / (c1 + c2) * delta
            t2 = equilibrium - c1 / (c1 + c2) * delta
            self.assertAlmostEqual(c1 * (t1 - 353.15) + c2 * (t2 - 293.15), 0, places=9)
            self.assertAlmostEqual(t1 - t2, delta, places=11)

    def test_d2_conductivity_revision(self):
        c1, c2 = 500.0, 1500.0
        base_g = 0.2
        revised_g = 0.4
        self.assertAlmostEqual(1/(base_g * (1/c1+1/c2)), 1875.0)
        self.assertAlmostEqual(1/(revised_g * (1/c1+1/c2)), 937.5)
        self.assertAlmostEqual((c1*353.15+c2*293.15)/(c1+c2), 308.15)


if __name__ == "__main__":
    unittest.main()
