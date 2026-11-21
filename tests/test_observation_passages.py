from fractions import Fraction
import math
from unittest import TestCase

from tests.test_network_calorimetry import D2, PIN, ROOT
from tests.test_temperature_passages import D1, D1_PIN
from tools.observation_passages import investigate
from tools.bounded_passages import series_passages


class ObservationPassageTests(TestCase):
    def test_differential_observation_with_one_kelvin_threshold(self):
        result = investigate(D2/"study.json", D2, ROOT/"h1/reference_cases/D2.json",
                             PIN, "difference", "1", "K")
        event, = result["passages"]
        self.assertEqual(event["direction"], "decreasing")
        lo, hi = map(Fraction, event["timeBoundsSeconds"])
        self.assertLess(lo, 1875 * math.log(60))
        self.assertGreater(hi, 1875 * math.log(60))
        self.assertEqual(hi-lo, Fraction(75, 8))

    def test_stored_energy_halfway_through_warming(self):
        args = (D1/"study.json", D1, ROOT/"h1/reference_cases/D1.json", D1_PIN)
        result = investigate(*args, "energy", "15000", "J")
        event, = result["passages"]
        self.assertEqual(event["direction"], "increasing")
        lo, hi = map(Fraction, event["timeBoundsSeconds"])
        self.assertLess(lo, 2500 * math.log(2))
        self.assertGreater(hi, 2500 * math.log(2))
        with self.assertRaisesRegex(ValueError, "threshold unit differs"):
            investigate(*args, "energy", "15000", "W")
        with self.assertRaisesRegex(ValueError, "unknown study observation"):
            investigate(*args, "undeclared", "15000", "J")

    def test_joule_uncertainty_can_hide_an_apparent_passage(self):
        # With the same ratio, the joule error bound is 1e-5 and the watt bound is 1e-8.
        candidate = {key: False for key in ("nativeExecuted", "nativeQualified",
                                             "independentlyCertifiedReference", "runnerConsumable")}
        candidate.update(modelSha256="test", studySha256="test", factsSha256="test",
                         requests={"value": {"unit": "J", "values": [-1e-6, 1e-6]}},
                         maxErrorToBudgetBySeries={"requests": {"value": "1"}})
        facts = {"analysis": {"stopTime": 1, "intervals": 1}}
        def read():
            return series_passages(candidate, facts, "requests", "value", 0,
                                   ("decreasing", "increasing"))
        events, overlaps, radius, _ = read()
        self.assertEqual((events, overlaps, radius), ([], 2, Fraction(1, 10**5)))
        candidate["requests"]["value"]["unit"] = "W"
        events, overlaps, radius, _ = read()
        self.assertEqual((len(events), overlaps, radius), (1, 0, Fraction(1, 10**8)))
