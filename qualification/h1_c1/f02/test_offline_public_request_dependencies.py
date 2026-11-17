"""Negative-only public observation DEPENDENCIES, never native or computed data."""
from __future__ import annotations
from copy import deepcopy
import unittest
from unittest import mock

from h1.study import load_study
from h1 import reference
from tools import h1_native_batch
from qualification.h1_c1.f02 import offline_public_request_dependencies as projection
from qualification.h1_c1.f02 import offline_expected_export_coverage as coverage


class OriginalPublicRequestDependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Full approved OFFLINE reference/model/owner-HOLD/source checks ONCE.
        cls.expected=projection.inventory()
        cls.study=load_study(projection.ROOT/coverage.STUDY,
                            projection.ROOT/"h1/cases")
        assert len(cls.expected["publicRequestDependencies"])==9

    def original(self):
        return deepcopy(self.expected)

    def check_candidate(self,x):
        # Legitimate original was already read from full source in setUpClass.
        # Subsequent forged report probes exercise ACTUAL check and canonical
        # byte semantics, not simulated result acceptance.
        with mock.patch.object(projection,"inventory",return_value=self.original()):
            return projection.assert_exact_source_bound(x)

    def refusal(self,x):
        with self.assertRaises(projection.DependencyRefusal):
            self.check_candidate(x)

    def test_original_source_derives_nine_expected_dependent_requests(self):
        r=self.original()
        self.assertEqual(r["status"],projection.STATUS)
        self.assertTrue(r["releaseBlocked"])
        self.assertTrue(r["expectedOnly"])
        self.assertEqual(r["expectedSourceTermCount"],10)
        self.assertEqual(r["directExpectedModelFieldRequests"],8)
        self.assertEqual(r["derivedTemperatureDifferenceRequests"],1)
        self.assertEqual(r["expectedPublicRequestCount"],9)
        self.assertEqual(r["nativeObservationCount"],0)
        self.assertEqual(r["nativePublicRequestsStillNotComputed"],9)
        self.assertEqual(len(r["missingNativeReleaseGates"]),11)
        self.assertTrue(self.check_candidate(r))

    def test_exact_author_request_order_and_operands(self):
        authored=self.study.data["requests"]
        rows=self.original()["publicRequestDependencies"]
        self.assertEqual([x["id"] for x in rows],[x["id"] for x in authored])
        for p,original in zip(rows,authored,strict=True):
            self.assertEqual(p["operation"],original["op"])
            self.assertEqual(p["authoredOperands"],{k:v for k,v in original.items()
                                                    if k not in ("id","op")})
            self.assertIsNone(p["nativeValue"])
            self.assertEqual(p["nativeStatus"],"not_computed")

    def test_direct_source_export_keys_match_original_physical_components(self):
        p={r["id"]:r for r in self.original()["publicRequestDependencies"]}
        wanted={
            "leftTemperature":"leftBuffer.T",
            "rightTemperature":"rightBuffer.T",
            "hotLeadFlow":"hotLead.Q_flow",
            "flatBridgeFlow":"flatBridge.Q_flow",
            "roundBridgeFlow":"roundBridge.Q_flow",
            "coldLeadFlow":"coldLead.Q_flow",
            "leftEnergyChange":"leftBuffer.dU",
            "rightEnergyChange":"rightBuffer.dU",
        }
        for rid,name in wanted.items():
            with self.subTest(rid=rid):
                self.assertEqual(p[rid]["dependencyKind"],
                                 "direct_expected_model_export")
                self.assertEqual(p[rid]["orderedExpectedExportTerms"],
                                 [{"exportName":name,"sign":1}])

    def test_difference_has_explicit_left_minus_right_order(self):
        p={r["id"]:r for r in self.original()["publicRequestDependencies"]}
        d=p["bufferTemperatureDifference"]
        self.assertEqual(d["expectedUnit"],"K")
        self.assertEqual(d["dependencyKind"],
                         "ordered_difference_of_two_expected_exports")
        self.assertEqual(d["orderedExpectedExportTerms"],[
            {"exportName":"leftBuffer.T","sign":1},
            {"exportName":"rightBuffer.T","sign":-1},
        ])
        self.assertEqual(d["sourceRule"],projection.FROZEN_VERIFICATION_RULE)

    def test_port_to_export_rule_respects_frozen_component_port_types(self):
        model=self.study.model
        self.assertEqual(projection._port_key(model,"leftBuffer.port"),"leftBuffer.T")
        self.assertEqual(projection._port_key(model,"rightBuffer.port"),"rightBuffer.T")
        self.assertEqual(projection._port_key(model,"hotBath.port"),"hotBath.T")
        self.assertEqual(projection._port_key(model,"coldBath.port"),"coldBath.T")
        self.assertEqual(projection._port_key(model,"hotLead.port_a"),"hotLead.T_a")
        self.assertEqual(projection._port_key(model,"coldLead.port_b"),"coldLead.T_b")
        for invalid in ("leftBuffer.port_a","hotLead.port","invented.port",
                        "rightBuffer.port.foo","",None):
            with self.subTest(port=invalid):
                with self.assertRaises(projection.DependencyRefusal):
                    projection._port_key(model,invalid)

    def test_dependency_terms_all_ref_original_EXPECTED_reference_fields(self):
        name_to_unit={r["name"]:r["analyticalCheckingUnit"] for r in
                      coverage.inventory()["expectedModelExports"]}
        self.assertEqual(len(name_to_unit),37)
        for row in self.original()["publicRequestDependencies"]:
            for term in row["orderedExpectedExportTerms"]:
                self.assertIn(term["exportName"],name_to_unit)
                self.assertEqual(row["expectedUnit"],name_to_unit[term["exportName"]])
                self.assertIs(type(term["sign"]),int)
                self.assertIn(term["sign"],(-1,1))

    def test_frozen_invalid_authored_operations_and_ports_refused(self):
        s=self.study
        for row in (
            {"op":"pressure","target":"leftBuffer"},
            {"op":"energyChange","target":"hotLead"},
            {"op":"heatFlow","target":"leftBuffer"},
            {"op":"temperature","target":"invented.port"},
            {"op":"temperatureDifference","a":"leftBuffer.port",
             "b":"leftBuffer.port"},
        ):
            with self.subTest(op=row):
                with self.assertRaises(projection.DependencyRefusal):
                    projection._terms(s,row)

    def test_all_reported_native_and_historical_success_fields_false(self):
        r=self.original()
        for key in projection.FALSE_FLAGS:
            with self.subTest(key=key):
                self.assertIs(r[key],False)
        self.assertIsNone(r["nativePublicValues"])
        self.assertEqual(r["nativeExportSeriesObtained"],0)
        self.assertEqual(r["nativeIntegralSeriesObtained"],0)

    def test_fake_direct_export_source_field_refused(self):
        for value in ("fake.T","rightBuffer.T","coldBath.T"):
            x=self.original()
            x["publicRequestDependencies"][0]["orderedExpectedExportTerms"][0]["exportName"]=value
            with self.subTest(value=value):
                self.refusal(x)

    def test_fake_orientation_sign_and_swap_refused(self):
        for change in (0,-1,False,1.0):
            x=self.original()
            x["publicRequestDependencies"][2]["orderedExpectedExportTerms"][0]["sign"]=change
            with self.subTest(sign=repr(change)):
                self.refusal(x)
        x=self.original();x["publicRequestDependencies"][6]["orderedExpectedExportTerms"].reverse()
        self.refusal(x)

    def test_fake_temperature_difference_sign_order_refused(self):
        for pos,sign in ((0,-1),(1,1),(1,True)):
            x=self.original()
            x["publicRequestDependencies"][6]["orderedExpectedExportTerms"][pos]["sign"]=sign
            with self.subTest(index=pos,sign=sign):
                self.refusal(x)
        x=self.original()
        x["publicRequestDependencies"][6]["orderedExpectedExportTerms"].reverse()
        self.refusal(x)

    def test_duplicate_unknown_or_dropped_dependency_refused(self):
        xs=[]
        x=self.original();x["publicRequestDependencies"].pop();xs.append(x)
        x=self.original();x["publicRequestDependencies"][0]=deepcopy(
            x["publicRequestDependencies"][1]);xs.append(x)
        x=self.original();x["publicRequestDependencies"][0]["id"]="invented";xs.append(x)
        x=self.original();x["publicRequestDependencies"].reverse();xs.append(x)
        x=self.original();x["publicRequestDependencies"][0]["orderedExpectedExportTerms"].append(
            {"exportName":"leftBuffer.C","sign":1});xs.append(x)
        for i,x in enumerate(xs):
            with self.subTest(case=i):
                self.refusal(x)

    def test_forged_request_operation_operand_unit_or_rule_refused(self):
        for name,val in (
            ("operation","energyChange"),
            ("expectedUnit","W"),
            ("authoredOperands",{"target":"fake.port"}),
            ("sourceRule","owner_signed_native_qualified"),
            ("dependencyKind","native_numeric_formula"),
        ):
            x=self.original();x["publicRequestDependencies"][0][name]=val
            with self.subTest(name=name):
                self.refusal(x)

    def test_claimed_native_reading_or_observation_refused(self):
        for name,val in (
            ("nativeStatus","computed"),
            ("nativeValue",0),
            ("nativeValue",293.15),
            ("nativeValue",False),
        ):
            x=self.original();x["publicRequestDependencies"][0][name]=val
            with self.subTest(field=name,value=repr(val)):
                self.refusal(x)
        for key,val in (
            ("nativePublicValues",{}),
            ("nativeObservationCount",1),
            ("nativePublicRequestsStillNotComputed",0),
            ("nativeExportSeriesObtained",37),
        ):
            x=self.original();x[key]=val
            with self.subTest(field=key):
                self.refusal(x)

    def test_literal_false_and_zero_type_refusal(self):
        for name in projection.FALSE_FLAGS:
            for value in (0,0.0,1,True):
                x=self.original();x[name]=value
                with self.subTest(field=name,value=repr(value)):
                    self.refusal(x)
        for name in ("expectedSourceTermCount","nativeObservationCount",
                     "nativePublicRequestsStillNotComputed",
                     "directExpectedModelFieldRequests"):
            for value in (False,True,0.0,10.0):
                x=self.original();x[name]=value
                with self.subTest(field=name,value=repr(value)):
                    self.refusal(x)

    def test_reference_source_and_gate_forgery_refused(self):
        for name,value in (
            ("originalModelSha256","f"*64),
            ("modalStudySha256","f"*64),
            ("originalSavedReferenceRawSha256","f"*64),
            ("originalSavedReferenceSeal",
             "c30e8783d39c7b0198c1adf0273ac84568f698f08287f02bf79eeed224830b07"),
            ("releaseBlocked",False),
            ("checkingReferenceOrigin","native_data"),
        ):
            x=self.original();x[name]=value
            with self.subTest(field=name):
                self.refusal(x)
        for mod in ("remove","replace","add"):
            x=self.original()
            if mod=="remove":x["missingNativeReleaseGates"].pop()
            if mod=="replace":x["missingNativeReleaseGates"][0]="completed"
            if mod=="add":x["missingNativeReleaseGates"].append("fakeOwnerSignature")
            with self.subTest(mod=mod):
                self.refusal(x)

    def test_fake_extra_numeric_or_provenance_field_refused(self):
        for path in ("public","top"):
            x=self.original()
            if path=="public":
                x["publicRequestDependencies"][0]["computedNativeSamples"]=[293.15]
            else:
                x["nativeEvidenceKind"]="owner_signed"
            with self.subTest(path=path):
                self.refusal(x)

    def test_original_analytical_samples_are_not_copied_to_report(self):
        text=projection.encoded(self.original())
        self.assertLess(len(text),15_000)
        doc=text.decode("utf-8")
        self.assertNotIn('"columns"',doc)
        self.assertNotIn('"flowIntegrals"',doc)
        self.assertNotIn('"values"',doc)
        self.assertEqual(self.original()["nativeObservationCount"],0)

    def test_original_source_dependency_verification_never_prepares_or_executes(self):
        with mock.patch.object(reference,"prepare",side_effect=AssertionError(
                "original reference regeneration forbidden")), \
             mock.patch.object(h1_native_batch,"prepare",side_effect=AssertionError(
                "frozen native preparation forbidden")), \
             mock.patch.object(h1_native_batch,"execute",side_effect=AssertionError(
                "frozen native execution forbidden")), \
             mock.patch.object(h1_native_batch,"invoke",side_effect=AssertionError(
                "native subprocess forbidden")):
            got=projection.inventory()
        self.assertEqual(got["status"],projection.STATUS)
        self.assertEqual(got["nativeObservationCount"],0)
        self.assertEqual(got["publicRequestDependencies"][6]["nativeStatus"],
                         "not_computed")

    def test_one_offline_description_cli_only(self):
        with mock.patch.object(projection,"inventory",return_value=self.original()), \
             mock.patch("builtins.print"):
            self.assertEqual(projection.main(["describe-dependencies-only"]),0)
        for verb in ("omc","approve","native","build","launch","execute",
                     "reserve-native","run","read-mat","qualify"):
            with self.subTest(verb=verb),mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as ctx:
                    projection.main([verb])
                self.assertEqual(ctx.exception.code,2)


if __name__=="__main__":
    unittest.main()
