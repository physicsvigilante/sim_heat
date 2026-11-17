"""OFFLINE expected 37/4/9 inventory, never real Modelica observations."""
from copy import deepcopy
import json
import unittest
from unittest import mock

from h1 import reference
from h1.study import load_study
from h1.model import internal_exports
from tools import h1_native_batch
from qualification.h1_c1.f02 import offline_expected_export_coverage as coverage


class OriginalExpectedCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Once, fully run the inherited original saved-reference/model/owner
        # read-only source checks. No reference generation or native runner.
        cls.report=coverage.inventory()
        cls.study=load_study(coverage.ROOT/coverage.STUDY,
                             coverage.ROOT/"h1/cases")

    def original(self):
        return deepcopy(self.report)

    def validate_without_new_bundle_read(self,report):
        # The original end-to-end source was independently validated above.
        # Additional forged JSON cases exercise actual source readback contract.
        with mock.patch.object(coverage,"inventory",return_value=self.original()):
            return coverage.assert_exact_expected(report)

    def test_actual_source_and_reference_expected_only(self):
        r=self.original()
        self.assertEqual(r["status"],coverage.STATUS)
        self.assertIs(r["releaseBlocked"],True)
        self.assertEqual((r["expectedModelExportCount"],
                          r["expectedIntegralCount"],
                          r["publicRequestCount"]),(37,4,9))
        self.assertEqual(r["analyticalGridSamples"],4001)
        self.assertEqual(r["nativeObservationCount"],0)
        self.assertEqual(r["nativeExportSeriesObtained"],0)
        self.assertEqual(r["nativeIntegralSeriesObtained"],0)
        self.assertEqual(r["nativePublicRequestsStillNotComputed"],9)
        self.assertEqual(r["referenceOrigin"],"analytical_reference_only")
        self.assertEqual(r["referenceUse"],"approved_for_offline_checking_only")
        self.assertEqual(r["sourcePinsVerified"],23)
        self.assertEqual(len(r["missingNativeReleaseGates"]),11)
        self.assertTrue(self.validate_without_new_bundle_read(r))

    def test_all_37_export_names_derive_exactly_from_original_model(self):
        expected=tuple(internal_exports(self.study.model))
        names=tuple(item["name"] for item in self.report["expectedModelExports"])
        self.assertEqual(expected,names)
        self.assertEqual(len(set(names)),37)
        for row in self.report["expectedModelExports"]:
            self.assertEqual(row["nativeStatus"],"not_computed")
            self.assertIsNone(row["observedNativeSamples"])
            self.assertEqual(row["savedAnalyticalReferenceSamples"],4001)
            self.assertTrue(row["analyticalCheckingUnit"])

    def test_all_four_integrals_derive_from_thermal_stores_and_baths(self):
        expected=coverage._integral_names(self.study)
        names=tuple(x["name"] for x in self.report["expectedFlowIntegrals"])
        self.assertEqual(names,expected)
        self.assertEqual(len(set(names)),4)
        self.assertTrue(any(x.endswith(".Q_in") for x in names))
        self.assertTrue(any(x.endswith(".Q_to_network") for x in names))
        for row in self.report["expectedFlowIntegrals"]:
            self.assertIsNone(row["observedNativeSamples"])
            self.assertEqual(row["savedAnalyticalIntegralSamples"],4001)
            self.assertEqual(row["nativeStatus"],"not_computed")

    def test_nine_public_requests_retain_original_author_order_and_units(self):
        records=self.report["publicRequests"]
        expected=self.study.data["requests"]
        self.assertEqual([r["id"] for r in records],
                         [r["id"] for r in expected])
        for got,authored,checked in zip(records,expected,
                                        self.study.request_report["requests"],
                                        strict=True):
            self.assertEqual(got["operation"],authored["op"])
            self.assertEqual(got["id"],authored["id"])
            self.assertEqual(got["unit"],checked["unit"])
            self.assertEqual(got["authoredOperands"],
                             {k:v for k,v in authored.items()
                              if k not in ("id","op")})
            self.assertIsNone(got["nativeValue"])
            self.assertEqual(got["nativeStatus"],"not_computed")

    def test_all_permission_qualifier_and_old_history_flags_literal_false(self):
        r=self.original()
        for field in coverage.REAL_NATIVE_FALSE:
            with self.subTest(field=field):
                self.assertIs(r[field],False)
        self.assertIs(r["releaseBlocked"],True)

    def test_reference_numeric_series_are_not_copied_to_coverage_receipt(self):
        r=self.original()
        for row in r["expectedModelExports"]:
            self.assertEqual(set(row),{
                "name","analyticalCheckingUnit","savedAnalyticalReferenceSamples",
                "nativeStatus","observedNativeSamples"
            })
        for row in r["expectedFlowIntegrals"]:
            self.assertEqual(set(row),{
                "name","savedAnalyticalIntegralSamples",
                "nativeStatus","observedNativeSamples"
            })
        for row in r["publicRequests"]:
            self.assertEqual(set(row),{
                "id","operation","authoredOperands","unit","nativeStatus","nativeValue"
            })
        self.assertNotIn('"columns"',coverage.encoded(r).decode())
        self.assertNotIn('"flowIntegrals"',coverage.encoded(r).decode())
        self.assertTrue(self.validate_without_new_bundle_read(r))

    def test_export_name_deletion_duplication_reorder_and_alias_refused(self):
        variants=[]
        x=self.original();x["expectedModelExports"].pop();variants.append(x)
        x=self.original();x["expectedModelExports"][1]=deepcopy(x["expectedModelExports"][0]);variants.append(x)
        x=self.original();x["expectedModelExports"][0]["name"]="fakeModel.Q";variants.append(x)
        x=self.original();x["expectedModelExports"].reverse();variants.append(x)
        for i,x in enumerate(variants):
            with self.subTest(case=i),self.assertRaises(coverage.CoverageRefusal):
                self.validate_without_new_bundle_read(x)

    def test_fake_observed_native_export_series_never_passes(self):
        changes=[
            ("nativeStatus","computed"),
            ("observedNativeSamples",4001),
            ("observedNativeSamples",0),
        ]
        for name,val in changes:
            with self.subTest(field=name,value=val):
                x=self.original();x["expectedModelExports"][0][name]=val
                with self.assertRaises(coverage.CoverageRefusal):
                    self.validate_without_new_bundle_read(x)

    def test_fake_observed_integral_series_never_passes(self):
        for name,val in [("nativeStatus","qualified"),
                         ("observedNativeSamples",4001),
                         ("observedNativeSamples",0.0)]:
            with self.subTest(field=name):
                x=self.original();x["expectedFlowIntegrals"][0][name]=val
                with self.assertRaises(coverage.CoverageRefusal):
                    self.validate_without_new_bundle_read(x)

    def test_fake_nine_public_request_values_never_pass(self):
        for key,val in [("nativeStatus","computed"),("nativeValue",0),
                        ("nativeValue",333.15),("nativeValue",True)]:
            with self.subTest(key=key):
                x=self.original();x["publicRequests"][0][key]=val
                with self.assertRaises(coverage.CoverageRefusal):
                    self.validate_without_new_bundle_read(x)

    def test_forged_request_id_operation_unit_or_operand_refused(self):
        for field,val in (("id","invented"),("operation","heatFlow"),
                          ("unit","kg"),("authoredOperands",{"target":"new.thing"})):
            x=self.original();x["publicRequests"][0][field]=val
            with self.subTest(field=field),self.assertRaises(coverage.CoverageRefusal):
                self.validate_without_new_bundle_read(x)

    def test_bool_numeric_loosened_type_on_native_and_expected_counts_refused(self):
        for field in ("nativeObservationCount","nativeExportSeriesObtained",
                      "nativeIntegralSeriesObtained",
                      "nativePublicRequestsStillNotComputed",
                      "expectedModelExportCount","expectedIntegralCount",
                      "publicRequestCount","analyticalGridSamples"):
            for value in (False,True,0.0,37.0,4001.0):
                with self.subTest(field=field,value=repr(value)):
                    x=self.original();x[field]=value
                    with self.assertRaises(coverage.CoverageRefusal):
                        self.validate_without_new_bundle_read(x)

    def test_all_native_authorization_true_or_numeric_zero_refused(self):
        for field in coverage.REAL_NATIVE_FALSE:
            for value in (True,0,0.0,1):
                with self.subTest(field=field,value=repr(value)):
                    x=self.original();x[field]=value
                    with self.assertRaises(coverage.CoverageRefusal):
                        self.validate_without_new_bundle_read(x)

    def test_reference_sha_seal_missing_gate_list_and_observation_claim_refused(self):
        for k,val in (
            ("originalSavedReferenceSeal","c30e8783d39c7b0198c1adf0273ac84568f698f08287f02bf79eeed224830b07"),
            ("originalSavedReferenceRawSha256","f"*64),
            ("originalModelSha256","f"*64),
            ("modalStudySha256","f"*64),
            ("referenceOrigin","native_omc"),
            ("releaseBlocked",False),
            ("nativePublicRequestsStillNotComputed",0),
        ):
            with self.subTest(field=k):
                x=self.original();x[k]=val
                with self.assertRaises(coverage.CoverageRefusal):
                    self.validate_without_new_bundle_read(x)
        for mutation in ("remove","fill","extra"):
            x=self.original()
            if mutation=="remove":x["missingNativeReleaseGates"].pop()
            elif mutation=="fill":x["missingNativeReleaseGates"][0]="signed"
            else:x["missingNativeReleaseGates"].append("not-real-owner-key")
            with self.subTest(gateMutation=mutation):
                with self.assertRaises(coverage.CoverageRefusal):
                    self.validate_without_new_bundle_read(x)

    def test_returned_expected_inventory_is_not_an_authority_token(self):
        x=self.original()
        x["status"]="NATIVE_QUALIFIED"
        x["nativeQualified"]=True
        with self.assertRaises(coverage.CoverageRefusal):
            self.validate_without_new_bundle_read(x)
        x=self.original();x["publicRequests"][0]["nativeValue"]=float("inf")
        with self.assertRaises(coverage.CoverageRefusal):
            self.validate_without_new_bundle_read(x)

    def test_no_reference_generator_or_native_runner_called(self):
        # Source validation in class setup already actually exercised read-only
        # saved original Option A data and original H1 parser.
        with mock.patch.object(reference,"prepare",side_effect=AssertionError(
                 "forbidden reference numerical generation")), \
             mock.patch.object(h1_native_batch,"prepare",side_effect=AssertionError(
                 "forbidden native preparation")), \
             mock.patch.object(h1_native_batch,"execute",side_effect=AssertionError(
                 "forbidden native execute")), \
             mock.patch.object(h1_native_batch,"invoke",side_effect=AssertionError(
                 "forbidden native subprocess")):
            r=coverage.inventory()
        self.assertEqual(r["status"],coverage.STATUS)
        self.assertEqual(r["nativeObservationCount"],0)

    def test_only_expected_offline_CLI_has_success_case(self):
        with mock.patch.object(coverage,"inventory",return_value=self.original()), \
             mock.patch("builtins.print"):
            self.assertEqual(coverage.main(["describe-expected-only"]),0)
        for action in ("omc","native","execute","build","launch",
                       "approve","reserve-native","qualify","decode-mat","run"):
            with self.subTest(action=action), mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as ctx:
                    coverage.main([action])
                self.assertEqual(ctx.exception.code,2)


if __name__=="__main__":
    unittest.main()
