from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from tests.test_join_thermal_networks import LEFT
from tests.test_loaded_thermal_ports import LINK
from tools.phase_exposure_sequence import investigate


class ExposureTests(TestCase):
    def test_reverse_direction_and_exhaust_carried_inventory(self):
        schedule = [("420", "1000"), ("310", "1000"), ("310", "3000"), ("420", "1")]
        result = investigate(LEFT, "middle", "warm", "300", "200000", "0.2", "0.3",
                             ("1", "0.8", "0.0000000567"), schedule)
        self.assertEqual(len(result["requestedStages"]), 4)
        self.assertEqual(len(result["stages"]), 3)
        with mp.workdps(100):
            energy = mp.mpf(0)
            for (env, duration), stage in zip(schedule, result["stages"]):
                # Junction balance at the 2, 3 and 5 W/K legs.
                def joint(face):
                    return (2*face + 2300)/10
                face = mp.findroot(lambda t: 2*(t-joint(t)) +
                                   mp.mpf("0.00000004536")*(t**4-int(env)**4), 330)
                q = 3*(joint(face)-300)
                time = int(duration)
                if energy + q*time < -60000:
                    time = (-60000-energy)/q
                    energy = mp.mpf(-60000)
                else:
                    energy += q*time
                for field, value in (("bathInflowBoundsW", q), ("endBoundsS", int(stage["startS"])+time),
                                     ("cumulativeEnergyIntoBathBoundsJ", energy),
                                     ("liquidMassBoundsKg", mp.mpf("0.3")+energy/200000)):
                    low, high = map(F, stage[field])
                    expected = F(mp.nstr(value, 85))
                    self.assertTrue(low <= expected <= high)
                    self.assertLess(high-low, F(1, 10**10))
        self.assertEqual(result["stages"][-1]["plateauStatus"], "exhausted")

    def test_exact_switch_boundary_equal_drive_and_refusals(self):
        args = (LINK, "hot", "cold", "200", "1000", "1", "1", ("1", "1", "0.000002"))
        stages = investigate(*args, [("200", "3"), ("0", "2"), ("0", "3"), ("250", "1")])["stages"]
        self.assertEqual(len(stages), 3)
        self.assertEqual(stages[0]["bathInflowBoundsW"], ["0"]*2)
        self.assertEqual(stages[-1]["endBoundsS"], ["8"]*2)
        self.assertEqual(stages[-1]["liquidMassBoundsKg"], ["0"]*2)
        for schedule in ([], [("0", "0")], [("0", "5"), ("bad", "1")], [("100",)]):
            with self.assertRaises(ValueError):
                investigate(*args, schedule)

    def test_switch_inside_event_enclosure_stops_at_possible_depletion(self):
        from unittest.mock import patch
        args = (LINK, "hot", "cold", "200", "10", "1", "1", ("1", "1", "0.000002"))
        with patch("tools.phase_exposure_sequence.plateau_power", return_value=(F(1), F(2), {})):
            stages = investigate(*args, [("210", "2"), ("220", "4"), ("200", "1")])["stages"]
        self.assertEqual(len(stages), 2)
        self.assertEqual(stages[-1]["plateauStatus"], "exhaustion_time_uncertain")
        self.assertEqual(stages[-1]["endBoundsS"], ["5", "6"])
        self.assertEqual(stages[-1]["solidMassBoundsKg"], ["0", "2/5"])
