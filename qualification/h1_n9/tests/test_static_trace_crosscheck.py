"""Bounded source-identity and static-bit refusal tests, no native execution."""
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from qualification.h1_n1 import certified_reference as n1
from qualification.h1_n4.static_physical import create_static_candidate
from qualification.h1_n9.static_trace_crosscheck import (
    FACTS, ROOT, CrosscheckRefusal, ORIGINAL_GRID_HASHES,
    check_static_samples, verify_historical_grid, audit,
)


class StaticTraceCrosscheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.physical = create_static_candidate(
            FACTS.read_bytes(), expected_sha256=n1.FACTS_SHA256)
        cls.columns = {name: [float.fromhex(item["binary64Hex"])]*2
                       for name,item in cls.physical["exports"].items()}
        cls.units = {name: item["unit"]
                     for name,item in cls.physical["exports"].items()}

    def test_exact_source_physical_centres_and_original_t1t_legacy_failure(self):
        self.assertEqual(len(self.physical["exports"]), 14)
        self.assertEqual(check_static_samples(
            self.columns, self.units, self.physical, 2), 28)
        self.assertEqual(self.physical["sourceFactsSha256"], n1.FACTS_SHA256)
        self.assertEqual(self.physical["originalModelSha256"], n1.MODEL_SHA256)
        self.assertEqual(self.physical["originalStudySha256"], n1.STUDY_SHA256)
        # Published original checking value demonstrably fails the exact P
        # budget, while the reviewed generic N4 candidate has a distinct bit.
        centre = self.physical["exports"]["T10.G"]["binary64Hex"]
        self.assertEqual(centre, "0x1.f9db22d0e5604p-6")
        self.assertNotEqual(centre, "0x1.f9db22d0e5602p-6")

    def test_one_bit_drift_at_later_sample_refuses(self):
        changed = deepcopy(self.columns)
        changed["T10.G"][1] = math.nextafter(changed["T10.G"][1], math.inf)
        with self.assertRaisesRegex(CrosscheckRefusal, "T10.G at sample 1"):
            check_static_samples(changed, self.units, self.physical, 2)

    def test_swapped_units_missing_field_or_truncated_trace_refuse(self):
        changed = dict(self.units)
        changed["T06.A"] = "W"
        with self.assertRaisesRegex(CrosscheckRefusal, "static unit"):
            check_static_samples(self.columns, changed, self.physical, 2)
        changed = dict(self.columns)
        changed.pop("T06.G")
        with self.assertRaisesRegex(CrosscheckRefusal, "missing static"):
            check_static_samples(changed, self.units, self.physical, 2)
        changed = deepcopy(self.columns)
        changed["T06.G"] = changed["T06.G"][:1]
        with self.assertRaisesRegex(CrosscheckRefusal, "incomplete full-grid"):
            check_static_samples(changed, self.units, self.physical, 2)

    def test_boolean_forged_approval_and_falsely_passed_export_refuse(self):
        changed = deepcopy(self.columns)
        changed["T_Plug.C"][0] = True
        with self.assertRaises(CrosscheckRefusal):
            check_static_samples(changed, self.units, self.physical, 2)
        elevated = deepcopy(self.physical)
        elevated["nativeExecuted"] = True
        with self.assertRaisesRegex(CrosscheckRefusal, "N4 static evidence"):
            check_static_samples(self.columns, self.units, elevated, 2)
        elevated = deepcopy(self.physical)
        elevated["exports"]["T10.G"]["physical100x"] = "PASS_NATIVE"
        with self.assertRaisesRegex(CrosscheckRefusal, "invalid per-quantity"):
            check_static_samples(self.columns, self.units, elevated, 2)

    def test_wrong_grid_and_changed_hash_cannot_be_considered_original_N1(self):
        self.assertEqual(set(ORIGINAL_GRID_HASHES), {2400, 4800})
        with self.assertRaisesRegex(CrosscheckRefusal, "originally reviewed"):
            verify_historical_grid(b'{"forged":true}', 2400, self.physical)
        with self.assertRaisesRegex(CrosscheckRefusal, "unexpected trace"):
            verify_historical_grid(b'{"forged":true}', 9999, self.physical)

    def test_no_overwrite_or_in_repo_reference_output(self):
        with self.assertRaisesRegex(CrosscheckRefusal, "NEW scratch directory"):
            audit(out=ROOT/"qualification"/"h1_n1"/"forbidden")
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(CrosscheckRefusal, "NEW scratch directory"):
                audit(out=Path(temp))


if __name__ == "__main__":
    unittest.main()
