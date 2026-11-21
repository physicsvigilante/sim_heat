"""Development-exposed fixtures. The post-freeze reviewer selects a separate case."""
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from qualification.h1_n13.conduction import prepare

ROOT = Path(__file__).resolve().parents[2]


def exposed(name):
    case = ROOT / "h1/cases" / name
    facts = ROOT / "h1/reference_cases" / (name+".json")
    return prepare(case/"study.json", case, facts, sha256(facts.read_bytes()).hexdigest())


class ConductionTests(TestCase):
    def test_circular_series_steady(self):
        result = exposed("S1")
        self.assertEqual(result["timeSeconds"], [])
        self.assertEqual(result["integrals"], {})
        area = math.pi * 0.02**2 / 4
        q = 100 / (0.75/(384.928*area) + 1.25/(46.024*area))
        self.assertAlmostEqual(result["requests"]["flow"]["values"][0], q, places=10)
        self.assertAlmostEqual(result["requests"]["junction"]["values"][0],
                               373.15 - q*0.75/(384.928*area), places=10)

    def test_single_body_heat_and_energy_at_every_sample(self):
        result = exposed("D1")
        for i,t in enumerate(result["timeSeconds"]):
            decay = math.exp(-t/2500)
            energy = 30000 * (-math.expm1(-t/2500))
            for group, key, value in (("requests","temperature",353.15-60*decay),
                                      ("exports","rod.port_b.Q_flow",-12*decay),
                                      ("requests","energy",energy),
                                      ("integrals","body.Q_in",energy),
                                      ("integrals","reservoir.Q_to_network",energy)):
                self.assertAlmostEqual(result[group][key]["values"][i], value, delta=1e-8)
        for key in ("nativeExecuted","nativeQualified","runnerConsumable","independentlyCertifiedReference"):
            self.assertIs(result[key], False)

    def test_isolated_storage_and_reversed_flow(self):
        iso = exposed("ISO")
        self.assertEqual(set(iso["integrals"]["body.Q_in"]["values"]), {0.0})
        rev = exposed("REV")
        self.assertLess(rev["requests"]["flow"]["values"][0], 0)
        self.assertLess(rev["requests"]["difference"]["values"][-1], 0)

    def test_refuse_sub_float_physical_drift_or_wrong_pin(self):
        case = ROOT/"h1/cases/D1"
        raw = (ROOT/"h1/reference_cases/D1.json").read_bytes()
        changed = raw.replace(b'"m": 1.0', b'"m": 1.0000000000000000001')
        self.assertNotEqual(raw, changed)
        with TemporaryDirectory() as scratch:
            f = Path(scratch)/"facts.json"
            f.write_bytes(changed)
            for pin, message in ((sha256(raw).hexdigest(), "source bytes differ"),
                                 (sha256(changed).hexdigest(), "exact source fact differs")):
                with self.assertRaisesRegex(ValueError, message):
                    prepare(case/"study.json",case,f,pin)

    def test_original_T_all_sample_inventories(self):
        q = ROOT/"qualification/h1_n1"
        case = q/"inputs/T"
        result = prepare(case/"study.json", case, q/"reference-facts.json",
                         "39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf")
        for group, count in (("exports",77),("requests",8),("integrals",5)):
            self.assertEqual(len(result[group]), count)
            self.assertEqual(set(result[group]), set(result["maxErrorToBudgetBySeries"][group]))
            for name, series in result[group].items():
                self.assertEqual(len(series["values"]), 2401)
                self.assertLessEqual(Fraction(result["maxErrorToBudgetBySeries"][group][name]), 1)
