"""Adversarial tests: F02 pre-native release readiness is ALWAYS BLOCKED."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from h1 import reference
from tools import h1_native_batch
from qualification.h1_c1.f02 import offline_release_readiness_hold as gate
from qualification.h1_c1.f02 import offline_external_cas_contract as cas


class F02ReadinessHoldTests(unittest.TestCase):
    def original(self):
        doc,digest=gate.read_absence()
        self.assertEqual(len(digest),64)
        self.assertEqual(gate.git_blob((gate.ROOT/gate.RECORD).read_bytes()),
                         gate.PINNED_RECORD_GIT_BLOB)
        return doc

    def test_valid_source_and_reference_still_produce_explicit_native_hold(self):
        receipt=gate.audit()
        self.assertEqual(receipt["status"],gate.STATUS)
        self.assertIs(receipt["releaseBlocked"],True)
        self.assertIs(receipt["readOnlyScientificSourceIdentityVerified"],True)
        self.assertEqual(receipt["sourcePinsVerified"],23)
        self.assertEqual(receipt["referenceChannels"],37)
        self.assertEqual(receipt["referenceGridSamples"],4001)
        self.assertEqual(receipt["flowIntegralHistories"],4)
        self.assertEqual(receipt["publicRequests"],9)
        self.assertEqual(receipt["approvedArchivedReferenceRawSha256"],gate.f02.REF_SHA)
        self.assertEqual(receipt["approvedArchivedReferenceSeal"],gate.f02.REF_SEAL)
        self.assertEqual(receipt["missingRequiredGateCount"],11)
        self.assertEqual(tuple(receipt["missingRequiredNativeReleaseGates"]),
                         cas.MISSING)
        for key in ("nativeAllowed","nativeExecuted","nativeQualified",
                    "nativePlanApproved","ownerIdentityAuthenticatedExternally",
                    "ownerNativeLaunchApproved","trustedReleaseReady",
                    "realAcrossRunReservationAllocated",
                    "ownerControlledExternalStoreConnected",
                    "compilerOrHostObserved","compilerQueried","buildInvoked",
                    "modelLaunched","referenceRegenerated",
                    "originalF0Static100xPassed",
                    "pr32BitwiseReproductionPassed"):
            with self.subTest(key=key):
                self.assertIs(receipt[key],False)

    def test_all_unprovided_owner_host_store_adapter_gates_are_null(self):
        record=self.original()
        self.assertEqual(set(record["unresolvedNativeReleaseGates"]),set(cas.MISSING))
        self.assertTrue(all(x is None for x in
                            record["unresolvedNativeReleaseGates"].values()))
        self.assertEqual(len(record["unresolvedNativeReleaseGates"]),11)

    def test_forged_release_or_native_permission_flags_refuse(self):
        source=self.original()
        for k in ("ownerIdentityAuthenticatedExternally","referenceRegenerated",
                  "originalFrozenF0Static100xPassed","pr32BitwiseReproductionPassed",
                  "nativeAllowed","nativeExecuted","nativeQualified",
                  "nativePlanApproved","ownerNativeLaunchApproved",
                  "trustedReleaseReady","realAcrossRunReservationAllocated"):
            for claimed in (True,0,0.0,1):
                with self.subTest(field=k,claimed=repr(claimed)):
                    forged=deepcopy(source)
                    forged[k]=claimed
                    with self.assertRaises(gate.ReadinessRefusal):
                        gate.validate_absence(forged)

    def test_forged_single_missing_native_gate_refuses_all_eleven(self):
        source=self.original()
        for field in cas.MISSING:
            with self.subTest(field=field):
                forged=deepcopy(source)
                forged["unresolvedNativeReleaseGates"][field]="CLAIMED_COMPLETE"
                with self.assertRaisesRegex(gate.ReadinessRefusal,"gate was filled"):
                    gate.validate_absence(forged)

    def test_missing_or_extra_trust_gate_refuses(self):
        source=self.original()
        missing=deepcopy(source)
        missing["unresolvedNativeReleaseGates"].pop(cas.MISSING[0])
        with self.assertRaises(gate.ReadinessRefusal):
            gate.validate_absence(missing)
        extra=deepcopy(source)
        extra["unresolvedNativeReleaseGates"]["nativeBudgetGranted"]=None
        with self.assertRaises(gate.ReadinessRefusal):
            gate.validate_absence(extra)

    def test_science_source_seal_or_owner_scope_swap_refuses(self):
        source=self.original()
        replacements={
            "reviewedOfflineSourceCommit":"f"*40,
            "reviewedOfflineSourceTree":"f"*40,
            "frozenOriginalF0Commit":"f"*40,
            "originalFirstModelSha256":"f"*64,
            "modalStudySha256":"f"*64,
            "approvedArchivedReferenceRawSha256":"f"*64,
            "approvedArchivedReferenceSeal":
                "c30e8783d39c7b0198c1adf0273ac84568f698f08287f02bf79eeed224830b07",
            "ownerDirectionScope":"native_launch_allowed",
        }
        for k,v in replacements.items():
            with self.subTest(field=k):
                forged=deepcopy(source)
                forged[k]=v
                with self.assertRaises(gate.ReadinessRefusal):
                    gate.validate_absence(forged)

    def test_any_file_byte_change_refuses_independent_git_blob(self):
        original=(gate.ROOT/gate.RECORD).read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"absence.json"
            path.write_bytes(original+b"\n")
            with self.assertRaisesRegex(gate.ReadinessRefusal,"exact pinned Git"):
                gate.read_absence(path)

    def test_duplicate_key_refused_even_if_attacker_updates_mocked_git_pin(self):
        original=(gate.ROOT/gate.RECORD).read_text()
        target='"nativeAllowed": false'
        self.assertEqual(original.count(target),1)
        changed=original.replace(target,
            '"nativeAllowed": true, "nativeAllowed": false',1).encode()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"absence.json"
            p.write_bytes(changed)
            with mock.patch.object(gate,"PINNED_RECORD_GIT_BLOB",gate.git_blob(changed)):
                with self.assertRaisesRegex(gate.ReadinessRefusal,"duplicate owner/readiness"):
                    gate.read_absence(p)

    def test_nan_inf_metadata_refused_after_mocked_git_pin(self):
        raw=(gate.ROOT/gate.RECORD).read_text()
        for constant in ("NaN","Infinity","-Infinity"):
            with self.subTest(value=constant):
                changed=raw.replace('"nativeAllowed": false',
                                    '"nativeAllowed": '+constant,1).encode()
                with tempfile.TemporaryDirectory() as tmp:
                    p=Path(tmp)/"absence.json"
                    p.write_bytes(changed)
                    with mock.patch.object(gate,"PINNED_RECORD_GIT_BLOB",
                                           gate.git_blob(changed)):
                        with self.assertRaisesRegex(gate.ReadinessRefusal,
                                                    "nonfinite readiness"):
                            gate.read_absence(p)

    def test_offline_source_binding_refusal_must_stop_audit(self):
        with mock.patch.object(gate.f02,"audit",
                               side_effect=gate.ReadinessRefusal("frozen file changed")):
            with self.assertRaisesRegex(gate.ReadinessRefusal,"frozen file changed"):
                gate.audit()

    def test_fake_provider_must_remain_default_deny(self):
        forged=cas.audit_contract_only()
        forged["externalStoreConnected"]=True
        with mock.patch.object(gate.fake_contract,"audit_contract_only",
                               return_value=forged):
            with self.assertRaisesRegex(gate.ReadinessRefusal,"not be mistaken"):
                gate.audit()

    def test_missing_gate_list_cannot_be_silently_shortened(self):
        forged=cas.audit_contract_only()
        forged["missingGates"]=forged["missingGates"][:9]
        with mock.patch.object(gate.fake_contract,"audit_contract_only",
                               return_value=forged):
            with self.assertRaisesRegex(gate.ReadinessRefusal,"not be mistaken"):
                gate.audit()

    def test_no_reference_generator_native_runner_or_subprocess(self):
        with mock.patch.object(reference,"prepare",side_effect=AssertionError(
            "regenerating exact reviewed V2 forbidden")), \
             mock.patch.object(h1_native_batch,"prepare",side_effect=AssertionError(
            "native preparation not permitted")), \
             mock.patch.object(h1_native_batch,"execute",side_effect=AssertionError(
            "native execution not permitted")), \
             mock.patch.object(h1_native_batch,"invoke",side_effect=AssertionError(
            "no subprocess/native query permitted")):
            self.assertEqual(gate.audit()["status"],gate.STATUS)

    def test_only_inspect_holding_gate_cli_exists(self):
        with mock.patch("builtins.print"):
            self.assertEqual(gate.main(["inspect-pre-native-hold-only"]),0)
        for command in ("execute","approve","reserve-native","native",
                        "build","omc","launch","ready","release","run"):
            with self.subTest(action=command),mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as ctx:
                    gate.main([command])
                self.assertEqual(ctx.exception.code,2)

    def test_cannot_hide_an_old_failed_reference_or_regeneration(self):
        source=self.original()
        for field in ("originalFrozenF0Static100xPassed","pr32BitwiseReproductionPassed"):
            with self.subTest(field=field):
                v=deepcopy(source)
                v[field]=True
                with self.assertRaises(gate.ReadinessRefusal):
                    gate.validate_absence(v)


if __name__=="__main__":
    unittest.main()
