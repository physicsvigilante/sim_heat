from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from tests.test_join_thermal_networks import LEFT, RIGHT
from tests.test_loaded_thermal_ports import LINK
from tools.phase_exposure_sequence import investigate


class ReservoirEnergyTests(TestCase):
    def test_closed_inventory_still_transfers_energy_to_the_cold_support(self):
        with mp.workdps(100):
            def powers(env):
                def joint(face):
                    return (2*face + 2300)/10
                face = mp.findroot(lambda t: 2*(t-joint(t)) +
                                   mp.mpf("0.00000004536")*(t**4-env**4), 330)
                return 3*(joint(face)-300), 5*(joint(face)-280)
            q1, p1 = powers(420)
            q2, p2 = powers(310)
            duration = -1000*q1/q2
            def encloses(pair, expected):
                low, high = map(F, pair)
                self.assertTrue(low <= F(mp.nstr(expected, 85)) <= high)
                self.assertLess(high-low, F(1, 10**10))
            for network in (LEFT, RIGHT):
                result = investigate(network, "middle", "warm", "300", "200000", "0.2", "0.3",
                                     ("1", "0.8", "0.0000000567"), [("420", "1000")], "310", True)
                for row, q, p, t in ((result["stages"][0], q1, p1, 1000),
                                     (result["inventoryRecovery"], q2, p2, duration)):
                    encloses(row["energyIntoSupportsBoundsJ"]["cool"], p*t)
                    encloses(row["energyIntoEnclosureBoundsJ"], -(q+p)*t)
                total = result["reservoirEnergy"]
                encloses(total["energyIntoSupportsBoundsJ"]["cool"], p1*1000+p2*duration)
                encloses(total["energyIntoEnclosuresBoundsJ"], -(p1*1000+p2*duration))
                self.assertEqual(total["energyIntoBathBoundsJ"], ["0", "0"])

    def test_only_modeled_time_contributes_at_depletion(self):
        args = (LINK, "hot", "cold", "200", "1000", "1", "1", ("1", "1", "0.000002"))
        row = investigate(*args, [("200", "10"), ("0", "500"), ("300", "30")],
                          track_reservoir_energy=True)
        self.assertEqual(len(row["stages"]), 2)
        self.assertEqual(row["stages"][1]["endBoundsS"], ["15", "15"])
        self.assertEqual(row["reservoirEnergy"], {"energyIntoEnclosuresBoundsJ": ["1000", "1000"],
                                                  "energyIntoSupportsBoundsJ": {},
                                                  "energyIntoBathBoundsJ": ["-1000", "-1000"]})
