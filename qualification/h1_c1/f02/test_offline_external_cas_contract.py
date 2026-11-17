"""Adversarial OFFLINE tests for an UNTRUSTED external-CAS contract FAKE."""
from __future__ import annotations

import concurrent.futures
from copy import deepcopy
import json
import secrets
import unittest
from unittest import mock

from qualification.h1_c1.f02 import offline_external_cas_contract as cas


class UntrustedExternalCASContractTests(unittest.TestCase):
    def test_snapshot_is_disabled_and_exact_scientific_identity(self):
        x=cas.snapshot()
        cas.assert_snapshot(x)
        self.assertEqual(x["referenceRawSha256"],cas.V2_RAW_SHA)
        self.assertEqual(x["referenceCanonicalSeal"],cas.V2_SEAL)
        self.assertEqual(x["sourceCommit"],cas.SOURCE_COMMIT)
        self.assertEqual(x["disabledNativeControlPreviewSha256"],
                         cas.DISABLED_PLAN_SHA)
        for k in ("ownerAuthenticatedReleasePresent",
                  "ownerNativeLaunchAuthorized",
                  "trustedSharedReservationPresent",
                  "trustedNativeAdapterPresent","compilerOrHostObserved"):
            self.assertIs(x[k],False,k)
        for k,v in x["nativeBudget"].items():
            self.assertIs(type(v),int,k)
            self.assertEqual(v,0,k)

    def test_contract_reports_every_required_gate_missing(self):
        x=cas.audit_contract_only()
        self.assertEqual(x["status"],cas.DENIAL)
        self.assertEqual(len(x["missingGates"]),11)
        self.assertEqual(len(set(x["missingGates"])),11)
        self.assertEqual(x["fakeResults"]["canonicalFactSha256"],
                         cas.reservation_key(cas.snapshot()))
        for key in ("nativeAllowed","nativeExecuted","ownerNativeLaunchApproved",
                    "realAcrossRunReservationAllocated","crossHostAtomicityProved",
                    "externalStoreConnected","compilerQueried","buildInvoked",
                    "modelLaunched","originalF0Reference100xPassed",
                    "pr32BitwiseReferenceRegenerationPassed"):
            self.assertIs(x[key],False,key)

    def test_fake_contention_one_success_fifteen_refusals(self):
        report=cas.simulate_contention(contenders=16)
        self.assertEqual(report["status"],cas.SIMULATION)
        self.assertEqual(report["fakeResults"]["fakeFirstClaims"],1)
        self.assertEqual(report["fakeResults"]["fakeDuplicateRefusals"],15)
        self.assertIs(report["crossHostAtomicityProved"],False)
        self.assertIs(report["realAcrossRunReservationAllocated"],False)

    def test_fake_concurrency_multiple_counts(self):
        for count in (2,8,32,64):
            with self.subTest(contenders=count):
                x=cas.simulate_contention(contenders=count)
                self.assertEqual(x["fakeResults"]["fakeFirstClaims"],1)
                self.assertEqual(x["fakeResults"]["fakeDuplicateRefusals"],count-1)
                self.assertFalse(x["nativeAllowed"])

    def test_two_isolated_fake_providers_each_accept_once(self):
        x=cas.simulate_split_brain()
        self.assertEqual(x["status"],
                         "UNTRUSTED_SPLIT_BRAIN_TWO_FIRST_CLAIMS_NOT_NATIVE")
        self.assertEqual(x["fakeResults"]["fakeIndependentFirstClaims"],2)
        self.assertIs(x["realAcrossRunReservationAllocated"],False)

    def test_fake_state_reset_allows_two_claims(self):
        x=cas.simulate_reset_attack()
        self.assertEqual(x["status"],
                         "UNTRUSTED_STATE_RESET_TWO_FIRST_CLAIMS_NOT_NATIVE")
        self.assertEqual(x["fakeResults"]["fakeFirstClaimsBeforeAndAfterReset"],2)
        self.assertFalse(x["crossHostAtomicityProved"])

    def test_same_fake_store_refuses_new_nonce(self):
        p=cas.FakeAtomicCAS()
        key=cas.reservation_key(cas.snapshot())
        first,second=secrets.token_hex(16),secrets.token_hex(16)
        self.assertTrue(p.fake_put_if_absent(key,first))
        self.assertFalse(p.fake_put_if_absent(key,second))
        self.assertEqual(p.fake_lookup(key),first)

    def test_fake_nonce_format_is_not_owner_authentication(self):
        p=cas.FakeAtomicCAS()
        key=cas.reservation_key(cas.snapshot())
        forged="a"*32
        self.assertTrue(p.fake_put_if_absent(key,forged))
        self.assertEqual(p.fake_lookup(key),forged)
        self.assertFalse(cas.audit_contract_only()["ownerAuthenticated"])
        with self.assertRaises(cas.GateRefusal):
            cas.require_native_permission(forged)

    def test_external_authority_placeholder_always_refuses(self):
        provider=cas.ExternalAuthorityUnavailable()
        for action in (provider.reserve_native, provider.validate_native_launch,
                       cas.require_native_permission):
            with self.subTest(action=action.__name__):
                with self.assertRaisesRegex(cas.GateRefusal,
                                             "REFUSED_NO_TRUSTED_EXTERNAL"):
                    action(cas.snapshot(), owner_signature="simulated-only")

    def test_forged_budget_and_owner_release_flags_refused(self):
        for path,value in [
            ("ownerNativeLaunchAuthorized",True),
            ("ownerAuthenticatedReleasePresent",True),
            ("trustedSharedReservationPresent",True),
            ("trustedNativeAdapterPresent",True),
            ("compilerOrHostObserved",True),
            ("simulatedOnly",False),
            ("sourceCommit","f"*40),
            ("referenceRawSha256","f"*64),
            ("referenceCanonicalSeal","f"*64),
            ("disabledNativeControlPreviewSha256","f"*64),
        ]:
            with self.subTest(path=path):
                y=deepcopy(cas.snapshot())
                y[path]=value
                with self.assertRaises(cas.GateRefusal):
                    cas.reservation_key(y)
        for key in ("omcVersionQueries","modelBuilds","modelLaunches","retries"):
            for value in (1,True,0.0):
                with self.subTest(key=key,value=repr(value)):
                    y=cas.snapshot()
                    y["nativeBudget"][key]=value
                    with self.assertRaises(cas.GateRefusal):
                        cas.assert_snapshot(y)

    def test_forged_status_does_not_turn_fake_receipt_into_native_permit(self):
        x=cas.simulate_split_brain()
        x["status"]="OWNER_APPROVED_NATIVE"
        x["nativeAllowed"]=True
        with self.assertRaises(cas.GateRefusal):
            cas.require_native_permission(x)

    def test_fake_key_type_and_nonce_shape_rejected(self):
        p=cas.FakeAtomicCAS()
        key=cas.reservation_key(cas.snapshot())
        for candidate in ("x"*64,"f"*63,0,None,True):
            with self.subTest(candidate=repr(candidate)):
                with self.assertRaises(cas.GateRefusal):
                    p.fake_put_if_absent(candidate,secrets.token_hex(16))
        for candidate in ("nonce","0"*31,"G"*32,0,None,True):
            with self.subTest(nonce=repr(candidate)):
                with self.assertRaises(cas.GateRefusal):
                    p.fake_put_if_absent(key,candidate)

    def test_contention_bounds_refused(self):
        for count in (0,1,65,-1,True,16.0,"16",None):
            with self.subTest(contenders=repr(count)):
                with self.assertRaises(cas.GateRefusal):
                    cas.simulate_contention(contenders=count)

    def test_cli_has_only_audit_and_fake_simulation(self):
        with mock.patch("builtins.print") as output:
            for action in ("inspect-unavailable-authority",
                           "simulate-contention-only",
                           "demonstrate-split-brain-only",
                           "demonstrate-reset-only"):
                self.assertEqual(cas.main([action]),0)
        for forbidden in ("native","reserve-native","approve","omc",
                          "execute","build","launch","prepare","run"):
            with self.subTest(action=forbidden),mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as exc:
                    cas.main([forbidden])
                self.assertEqual(exc.exception.code,2)

    def test_no_network_modelica_or_approved_launch_capability(self):
        from h1 import reference
        from tools import h1_native_batch
        with mock.patch.object(reference,"prepare",side_effect=AssertionError(
                "numerical reference generator MUST NOT run")), \
             mock.patch.object(h1_native_batch,"prepare",side_effect=AssertionError(
                "native batch prepare MUST NOT run")), \
             mock.patch.object(h1_native_batch,"execute",side_effect=AssertionError(
                "native batch execute MUST NOT run")), \
             mock.patch.object(h1_native_batch,"invoke",side_effect=AssertionError(
                "subprocess MUST NOT run")):
            cas.simulate_contention(contenders=8)
            cas.simulate_split_brain()
            cas.simulate_reset_attack()
            cas.audit_contract_only()
            with self.assertRaises(cas.GateRefusal):
                cas.require_native_permission()

    def test_fake_receipt_is_not_a_native_permission_even_with_one_claim(self):
        x=cas.simulate_contention(contenders=8)
        self.assertTrue(x["fakeProviderOnly"])
        self.assertIs(x["simulatorIsTrustedProvider"],False)
        self.assertIs(x["ownerAuthenticated"],False)
        self.assertIs(x["nativeAllowed"],False)
        self.assertEqual(x["fakeResults"]["fakeFirstClaims"],1)
        with self.assertRaises(cas.GateRefusal):
            cas.ExternalAuthorityUnavailable().validate_native_launch(x)


if __name__=="__main__":
    unittest.main()
