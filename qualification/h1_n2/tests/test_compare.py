"""H1-N2 read-only comparator adversarial tests. ALL CSV DATA IS SYNTHETIC."""
from __future__ import annotations

from copy import deepcopy
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import qualification.h1_n2.compare as n2

from h1 import reference as ref
from h1.model import Refusal
from h1.study import load_study
from h1.verification import candidate_receipt, check_candidate
from qualification.h1_n2.compare import (
    _checks, _companion_contract, _original_inputs, compare_candidates,
    ORIGINAL_MODEL_SHA, ORIGINAL_STUDY_SHA, STATIC_LEGACY_REFUSALS,
)

HERE = Path(__file__).resolve().parents[2] / "h1_n1"


def synthetic_csv(bundle):
    """Reference-centre values are deliberately SYNTHETIC diagnostic inputs."""
    file = io.StringIO()
    writer = csv.writer(file)
    names = sorted(bundle["columns"])
    writer.writerow(["time", *names])
    for i, t in enumerate(bundle["grid"]):
        writer.writerow([format(float(t), ".17g")] +
                        [format(float(bundle["columns"][k][i]), ".17g")
                         for k in names])
    return file.getvalue()


def changed_csv(text, key, row, delta):
    inp = list(csv.reader(io.StringIO(text)))
    pos = inp[0].index(key)
    old = float(inp[row + 1][pos])
    inp[row + 1][pos] = format(old + delta, ".17g")
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerows(inp)
    return out.getvalue()


class FrozenOriginalComparator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        # Required original source bytes are copied unaltered; the derived
        # study files are labelled analysis-only synthetic test fixtures.
        data = (HERE / "inputs/T/study.json").read_bytes()
        model = (HERE / "inputs/T/model.mo").read_bytes()
        assert sha256(data).hexdigest() == ORIGINAL_STUDY_SHA
        assert sha256(model).hexdigest() == ORIGINAL_MODEL_SHA
        (cls.root / "study.json").write_bytes(data)
        (cls.root / "model.mo").write_bytes(model)
        cls.studies = {"primary": load_study(cls.root / "study.json", cls.root)}
        cls.descriptors = json.loads(data)
        for variant in ("tight", "dense"):
            successor = deepcopy(cls.descriptors)
            successor["id"] += "_N1_" + variant.upper()
            if variant == "tight":
                successor["analysis"]["tolerance"] = 1e-10
            else:
                successor["analysis"]["intervals"] = 4800
            path = cls.root / (variant + ".json")
            path.write_text(json.dumps(successor, sort_keys=True, indent=2) + "\n")
            cls.studies[variant] = load_study(path, cls.root)
        cls.bundles = {}
        cls.csvs = {}
        for name, study in cls.studies.items():
            # The inherited float64 reference has known seven PHYSICAL
            # 100x failures. Here it is used ONLY for synthetic guard tests.
            spec = ref.read_reference(HERE / "reference-facts.json")
            if name != "primary":
                spec["id"] = study.data["id"]
                spec["studySha256"] = study.sha256
                spec["analysis"] = study.data["analysis"]
            cls.bundles[name] = ref.prepare(spec)
            cls.csvs[name] = synthetic_csv(cls.bundles[name])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def compare(self, variant, *, primary_csv=None, companion_csv=None,
                primary_bundle=None, companion_bundle=None,
                primary_receipt=None, companion_receipt=None,
                primary_study=None, companion_study=None,
                primary_seal=None, companion_seal=None):
        x, y = primary_study or self.studies["primary"], companion_study or self.studies[variant]
        a = primary_bundle or self.bundles["primary"]
        b = companion_bundle or self.bundles[variant]
        ac = self.csvs["primary"] if primary_csv is None else primary_csv
        bc = self.csvs[variant] if companion_csv is None else companion_csv
        ar = primary_receipt or candidate_receipt(x, a, ac)
        br = companion_receipt or candidate_receipt(y, b, bc)
        return compare_candidates(x, a, ac, ar, primary_seal or a["seal"],
                                  y, b, bc, br, companion_seal or b["seal"],
                                  variant=variant)

    def test_f01_hashed_original_bytes_are_the_parsed_bytes_even_under_file_race(self):
        # Preserve the true original project files. Each scratch copy changes
        # immediately AFTER its first successful SHA-pinned read. A second
        # read would consume unauthenticated provenance (the review-01 bug).
        raw_facts = (HERE / "reference-facts.json").read_bytes()
        raw_study = (HERE / "inputs/T/study.json").read_bytes()
        raw_model = (HERE / "inputs/T/model.mo").read_bytes()
        expected_facts, expected_study = json.loads(raw_facts), json.loads(raw_study)
        for attack in ("facts", "study"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                facts = root / "h1_n1/reference-facts.json"
                study = root / "h1_n1/inputs/T/study.json"
                model = root / "h1_n1/inputs/T/model.mo"
                for path, raw in ((facts, raw_facts), (study, raw_study), (model, raw_model)):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
                target = facts if attack == "facts" else study
                changed = deepcopy(expected_facts if attack == "facts" else expected_study)
                if attack == "facts":
                    changed["provenance"] = "replacement after SHA check"
                else:
                    changed["provenance"][0]["note"] = "replacement after SHA check"
                tampered = json.dumps(changed, sort_keys=True).encode()
                reads = {facts: 0, study: 0, model: 0}
                real_read = Path.read_bytes

                def change_after_first_read(this):
                    raw = real_read(this)
                    if this in reads:
                        reads[this] += 1
                        if this == target and reads[this] == 1:
                            target.write_bytes(tampered)
                    return raw

                with patch.object(n2, "HERE", root), patch.object(
                        Path, "read_bytes", change_after_first_read):
                    actual_facts, actual_study = n2._original_inputs()

                self.assertEqual(actual_facts, expected_facts)
                self.assertEqual(actual_study, expected_study)
                self.assertEqual(reads, {facts: 1, study: 1, model: 1})
                self.assertNotEqual(sha256(target.read_bytes()).hexdigest(),
                                    n2.ORIGINAL_FACTS_SHA if attack == "facts"
                                    else n2.ORIGINAL_STUDY_SHA)

    def test_f01_file_tampered_before_hash_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = (
                ("h1_n1/reference-facts.json", HERE / "reference-facts.json"),
                ("h1_n1/inputs/T/study.json", HERE / "inputs/T/study.json"),
                ("h1_n1/inputs/T/model.mo", HERE / "inputs/T/model.mo"),
            )
            for target, source in paths:
                dest = root / target
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
            facts = root / "h1_n1/reference-facts.json"
            fake = json.loads(facts.read_bytes())
            fake["provenance"] = "malicious before hash"
            facts.write_text(json.dumps(fake))
            with patch.object(n2, "HERE", root):
                with self.assertRaisesRegex(Refusal, "byte identity mismatch"):
                    n2._original_inputs()

    def test_f02_malformed_public_api_inputs_refuse_not_python_traceback(self):
        first, second = self.studies["primary"], self.studies["dense"]
        a, b = self.bundles["primary"], self.bundles["dense"]
        ac, bc = self.csvs["primary"], self.csvs["dense"]
        ar, br = candidate_receipt(first, a, ac), candidate_receipt(second, b, bc)

        def direct(primary_bundle=a, primary_csv=ac):
            return n2.compare_candidates(
                first, primary_bundle, primary_csv, ar, a["seal"],
                second, b, bc, br, b["seal"], variant="dense")

        for malformed in ({}, [], {"spec": None}, {"spec": {}}):
            with self.subTest(bundle=repr(malformed)):
                with self.assertRaises(Refusal):
                    direct(primary_bundle=malformed)

        huge = deepcopy(a)
        huge["allowances"]["T_Cool.T"] = 10 ** 400
        with self.assertRaises(Refusal):
            direct(primary_bundle=huge)

        with self.assertRaisesRegex(Refusal, "UTF-8"):
            direct(primary_csv=ac + "\ud800")

    def test_canonical_primary_and_companions_are_synthetic_only(self):
        for variant in ("tight", "dense"):
            with self.subTest(variant=variant):
                out = self.compare(variant)
                self.assertEqual(out["status"], "checks_passed")
                self.assertEqual(out["commonSamples"], 2401)
                self.assertEqual((out["exportsCompared"], out["publicObservationsCompared"]), (77, 8))
                self.assertEqual(len(out["checks"]), 85)
                self.assertTrue(all(c["passed"] for c in out["checks"]))
                self.assertFalse(out["nativeExecuted"])
                self.assertFalse(out["nativeQualified"])
                self.assertFalse(out["referenceAccuracyCertified"])
                self.assertFalse(out["runtimeReady"])
                self.assertFalse(out["independentlyCertifiedReference"])
                self.assertEqual(out["nativeExecutionBlockersRetained"], 8)
                self.assertEqual(out["staticCheckingPhysical100xRefusalsRetained"], list(STATIC_LEGACY_REFUSALS))
                self.assertEqual(out["primaryStudySha256"], ORIGINAL_STUDY_SHA)
                self.assertEqual(out["primaryCsvSha256"], sha256(self.csvs["primary"].encode()).hexdigest())
                self.assertIn("request:t_upper_minus_cool", {x["quantity"] for x in out["checks"]})

    def test_real_primary_dense_allowance_mismatch_does_not_widen_primary(self):
        a = self.bundles["primary"]
        b = self.bundles["dense"]
        different = {k for k in a["allowances"]
                     if a["allowances"][k] != b["allowances"][k]}
        self.assertEqual(different, {"T02.Q_flow", "T02.port_a.Q_flow",
                                     "T02.port_b.Q_flow", "T_Warm.Q_to_network"})
        out = self.compare("dense")
        for check in out["checks"][:77]:
            self.assertEqual(check["primaryAllowance"], a["allowances"][check["quantity"]])

    def test_each_candidate_is_independently_checked_before_cross_comparison(self):
        for variant in ("tight", "dense"):
            with self.subTest(variant=variant):
                a = self.bundles[variant]
                csv_bad = changed_csv(self.csvs[variant], "T02.Q_flow", 100, 100*a["allowances"]["T02.Q_flow"])
                own = check_candidate(self.studies[variant], a, csv_bad,
                                      candidate_receipt(self.studies[variant], a, csv_bad),
                                      a["seal"])
                self.assertEqual(own["status"], "checks_failed")
                with self.assertRaisesRegex(Refusal, "independent per-run H1 verification"):
                    self.compare(variant, companion_csv=csv_bad)

    def test_primary_only_difference_failure_even_when_both_runs_individually_pass(self):
        a, b = self.bundles["primary"], self.bundles["dense"]
        eps = a["allowances"]["T_Cool.T"]
        primary = changed_csv(self.csvs["primary"], "T_Cool.T", 100, 0.75*eps)
        companion = changed_csv(self.csvs["dense"], "T_Cool.T", 200, -0.75*eps)
        for name, bundle, data in (("primary", a, primary), ("dense", b, companion)):
            report = check_candidate(self.studies[name], bundle, data,
                                     candidate_receipt(self.studies[name], bundle, data), bundle["seal"])
            self.assertEqual(report["status"], "checks_passed", name)
        out = self.compare("dense", primary_csv=primary, companion_csv=companion)
        self.assertEqual(out["status"], "checks_failed")
        by_name = {x["quantity"]: x for x in out["checks"]}
        self.assertGreater(by_name["T_Cool.T"]["maximumRatio"], 1)
        self.assertEqual(by_name["T_Cool.T"]["primaryAllowance"], eps)
        self.assertFalse(out["nativeQualified"])

    def test_mismatched_physical_facts_cannot_be_approved_even_if_both_specs_agree(self):
        a, b = deepcopy(self.bundles["primary"]), deepcopy(self.bundles["dense"])
        a["spec"]["rods"]["T10"]["k"] = 95.000000000001
        b["spec"]["rods"]["T10"]["k"] = 95.000000000001
        with self.assertRaisesRegex(Refusal, "primary reference facts"):
            _companion_contract(self.studies["primary"], self.studies["dense"], a, b, "dense")

    def test_companion_provenance_and_request_or_analysis_edit_refuses(self):
        a, b = self.bundles["primary"], deepcopy(self.bundles["tight"])
        b["spec"]["provenance"] = "false provenance"
        with self.assertRaisesRegex(Refusal, "companion changed original physical/reference"):
            _companion_contract(self.studies["primary"], self.studies["tight"], a, b, "tight")
        b = deepcopy(self.bundles["tight"])
        b["spec"]["analysis"]["intervals"] = 4800
        with self.assertRaisesRegex(Refusal, "companion changed original physical/reference"):
            _companion_contract(self.studies["primary"], self.studies["tight"], a, b, "tight")
        changed = deepcopy(self.studies["tight"])
        changed.data["requests"][0]["id"] = "other"
        with self.assertRaisesRegex(Refusal, "companion changed non-analysis"):
            _companion_contract(self.studies["primary"], changed, a, self.bundles["tight"], "tight")

    def test_floating_grid_matches_existing_h1_contract_exactly(self):
        # H1 defines grid[i] = float(stop) * (i / intervals), not
        # float(i) * (stop / intervals); do not reject its actual sealed grid.
        for name, s in self.studies.items():
            self.assertEqual(self.bundles[name]["grid"], list(s.grid))
        a = self.bundles["primary"]
        b = deepcopy(self.bundles["dense"])
        b["grid"][101] += 1e-6
        with self.assertRaisesRegex(Refusal, "exact declared planned grid"):
            _companion_contract(self.studies["primary"], self.studies["dense"], a, b, "dense")

    def test_missing_or_unmatched_timestamp_refuses_without_interpolation(self):
        a, b = self.bundles["primary"], deepcopy(self.bundles["dense"])
        b["grid"][200] = 100.00001
        with self.assertRaisesRegex(Refusal, "exact declared planned grid"):
            _companion_contract(self.studies["primary"], self.studies["dense"], a, b, "dense")
        bad = self.csvs["dense"].replace("100,","100.01,",1)
        with self.assertRaises(Refusal):
            self.compare("dense", companion_csv=bad)

    def test_stale_or_edited_bundle_and_candidate_identity_refuses(self):
        bundle = deepcopy(self.bundles["dense"])
        bundle["allowances"]["T_Cool.T"] *= 100
        with self.assertRaisesRegex(Refusal, "reference_identity"):
            self.compare("dense", companion_bundle=bundle)
        receipt = candidate_receipt(self.studies["dense"], self.bundles["dense"], self.csvs["dense"])
        receipt["csvSha256"] = "0" * 64
        with self.assertRaisesRegex(Refusal, "candidate_identity"):
            self.compare("dense", companion_receipt=receipt)

    def test_missing_export_refuses(self):
        text = self.csvs["primary"]
        lines = list(csv.reader(io.StringIO(text)))
        idx = lines[0].index("T10.port_b.Q_flow")
        edited = [[value for j,value in enumerate(line) if j != idx] for line in lines]
        out = io.StringIO()
        csv.writer(out).writerows(edited)
        with self.assertRaisesRegex(Refusal, "missing required output"):
            self.compare("tight", primary_csv=out.getvalue())

    def test_only_declared_variants_and_typed_primary_source(self):
        with self.assertRaisesRegex(Refusal, "undeclared companion"):
            _companion_contract(self.studies["primary"], self.studies["dense"],
                                self.bundles["primary"], self.bundles["dense"], "other")
        self.assertEqual(_original_inputs()[1]["id"], "H1T1TFirstAttemptV1")

    def test_public_difference_has_own_primary_not_summed_allowance(self):
        out = self.compare("dense")
        x = next(k for k in out["checks"] if k["quantity"] == "request:t_upper_minus_cool")
        a = self.bundles["primary"]
        d = [x-y for x,y in zip(a["columns"]["T03.T_a"], a["columns"]["T_Cool.T"])]
        from h1.policy import local_allowance
        self.assertEqual(x["primaryAllowance"], local_allowance("K", max(abs(y) for y in d)))
        self.assertNotEqual(x["primaryAllowance"],
                            a["allowances"]["T03.T_a"] + a["allowances"]["T_Cool.T"])


if __name__ == "__main__":
    unittest.main()
