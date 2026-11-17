"""Offline adversarial source tests for an UNTRUSTED versioned CAS fake."""
from __future__ import annotations
from dataclasses import replace
import json
import unittest
from unittest import mock

from h1 import reference
from tools import h1_native_batch
from qualification.h1_c1.f02 import offline_stale_snapshot_cas_model as toy


class StaleSnapshotCASOfflineTests(unittest.TestCase):
    def assert_nonnative(self,x):
        toy.validate_receipt(x)
        self.assertTrue(x["releaseBlocked"])
        self.assertFalse(x["ownerNativeLaunchApproved"])
        self.assertFalse(x["durableOneShotReservationAllocated"])
        self.assertFalse(x["crossHostAtomicityEstablished"])
        self.assertEqual(x["referenceRawSha256"],toy.REFERENCE_RAW_SHA)
        self.assertEqual(x["referenceCanonicalSeal"],toy.REFERENCE_SEAL)

    def test_versioned_fake_one_first_fifteen_stale_reader_refusals(self):
        x=toy.fake_stale_reader_race(contenders=16)
        self.assertEqual(x["status"],toy.FAKE_SUCCESS)
        self.assertEqual(x["fakeCounts"]["oneFakeFirstClaims"],1)
        self.assertEqual(x["fakeCounts"]["staleRefusals"],15)
        self.assertEqual(x["fakeCounts"]["finalFakeVersion"],1)
        self.assert_nonnative(x)

    def test_one_object_fake_contention_at_boundaries(self):
        for n in (2,8,32):
            with self.subTest(n=n):
                x=toy.fake_stale_reader_race(contenders=n)
                self.assertEqual(x["fakeCounts"]["oneFakeFirstClaims"],1)
                self.assertEqual(x["fakeCounts"]["staleRefusals"],n-1)

    def test_invalid_contention_count_and_types_are_refused(self):
        for n in (0,1,-1,33,True,False,16.0,None,"16"):
            with self.subTest(value=repr(n)):
                with self.assertRaises(toy.CASRefusal):
                    toy.fake_stale_reader_race(contenders=n)

    def test_two_CAS_calls_using_same_stale_snapshot_refuse_second(self):
        p=toy.VolatileVersionedCASFake()
        old=p.observe()
        self.assertEqual((old.version,old.already_claimed),(0,False))
        self.assertTrue(p.fake_claim_if_unchanged(old))
        self.assertFalse(p.fake_claim_if_unchanged(old))
        self.assertEqual((p.observe().version,p.observe().already_claimed),(1,True))

    def test_fresh_read_of_claimed_fake_does_not_grant_duplicate(self):
        p=toy.VolatileVersionedCASFake()
        self.assertTrue(p.fake_claim_if_unchanged(p.observe()))
        self.assertFalse(p.fake_claim_if_unchanged(p.observe()))

    def test_wrong_epoch_fake_snapshot_refused(self):
        a,b=toy.VolatileVersionedCASFake(),toy.VolatileVersionedCASFake()
        self.assertFalse(a.fake_claim_if_unchanged(b.observe()))
        self.assertTrue(a.fake_claim_if_unchanged(a.observe()))

    def test_two_independent_fakes_each_accept_claim(self):
        x=toy.fake_split_brain()
        self.assertEqual(x["status"],toy.SPLIT_BRAIN)
        self.assertEqual(x["fakeCounts"]["distinctFakeStoreFirstClaims"],2)
        self.assertEqual(x["fakeCounts"]["globallySharedStoreCount"],0)
        self.assert_nonnative(x)

    def test_nonatomic_stale_check_then_use_exhibits_double_claim(self):
        x=toy.fake_stale_check_then_use()
        self.assertEqual(x["status"],toy.NAIVE)
        self.assertEqual(x["fakeCounts"]["unprotectedStaleReadFirstClaims"],2)
        self.assertIs(x["fakeCounts"]["linearizableCASActuallyUsed"],False)
        self.assert_nonnative(x)

    def test_resetting_fake_state_allows_second_claim_but_old_epoch_refuses(self):
        x=toy.fake_reset_attack()
        self.assertEqual(x["status"],toy.RESTORED)
        self.assertEqual(x["fakeCounts"]["firstClaimsBeforeAndAfterReset"],2)
        self.assertIs(x["fakeCounts"]["oldEpochReplayDenied"],True)
        self.assert_nonnative(x)

    def test_lost_ack_does_not_authorize_repeat_on_one_fake(self):
        x=toy.fake_lost_ack_after_commit()
        self.assertEqual(x["status"],toy.UNKNOWN_ACK)
        self.assertIs(x["fakeCounts"]["fakeCommitOccurred"],True)
        self.assertIs(x["fakeCounts"]["fakeRepeatClaimAccepted"],False)
        self.assertIs(x["fakeCounts"]["newExternalPermitIssued"],False)
        self.assertIs(x["fakeCounts"]["callerCanInferNativeEffect"],False)
        self.assert_nonnative(x)

    def test_malformed_fake_snapshot_scalar_types_refuse(self):
        p=toy.VolatileVersionedCASFake()
        good=p.observe()
        for change in (
            {"version":True},{"version":0.0},{"version":2},
            {"already_claimed":1},{"already_claimed":True},
            {"fake_epoch":"g"*24},{"fake_epoch":"a"*23},
            {"campaign":"NATIVE_APPROVED"},
        ):
            with self.subTest(change=change):
                s=replace(good,**change)
                with self.assertRaises(toy.CASRefusal):
                    p.fake_claim_if_unchanged(s)
        self.assertEqual(p.observe().version,0)

    def test_forged_boolean_or_float_native_budget_refused(self):
        good=toy.fake_stale_reader_race()
        for field in ("actualOmcVersionQueryBudget","actualModelBuildBudget",
                      "actualModelLaunchBudget","actualRetryBudget"):
            for val in (True,False,0.0,1):
                with self.subTest(field=field,value=repr(val)):
                    y={**good,field:val}
                    with self.assertRaises(toy.CASRefusal):
                        toy.validate_receipt(y)
        for field in ("nativeAllowed","nativeExecuted","nativeQualified",
                      "ownerAuthenticated","ownerNativeLaunchApproved",
                      "realExternalCASConnected","ownerControlledStoreAvailable",
                      "durableOneShotReservationAllocated","crossHostAtomicityEstablished",
                      "compilerVersionQueried","modelBuildInvoked","modelLaunched",
                      "referenceRegenerated","originalF0Static100xPassed",
                      "pr32BitwiseRegenerationPassed"):
            for val in (1,0,0.0,True):
                with self.subTest(field=field,value=repr(val)):
                    y={**good,field:val}
                    with self.assertRaises(toy.CASRefusal):
                        toy.validate_receipt(y)

    def test_native_permission_is_unconditionally_denied(self):
        for input_arg in (None,toy.fake_split_brain(),toy.fake_stale_reader_race(),
                          {"ownerNativeLaunchApproved":True}):
            with self.subTest(input=type(input_arg).__name__):
                with self.assertRaisesRegex(toy.CASRefusal,toy.REAL_DENIAL):
                    toy.require_real_native_permission(input_arg)

    def test_readiness_AUDIT_must_remain_blocked(self):
        actual=toy.audited_fake_run()
        self.assertEqual(actual["status"],toy.FAKE_SUCCESS)
        self.assert_nonnative(actual)
        with mock.patch.object(toy.readiness,"audit",return_value={
            "status":"READY","releaseBlocked":False,
            "missingRequiredGateCount":0,"nativeAllowed":True,
            "realAcrossRunReservationAllocated":True,
        }):
            with self.assertRaisesRegex(toy.CASRefusal,"STILL MISSING"):
                toy.audited_fake_run()

    def test_no_reference_regeneration_native_runner_or_shell(self):
        with mock.patch.object(reference,"prepare",side_effect=AssertionError(
                "reference numerical regeneration forbidden")), \
             mock.patch.object(h1_native_batch,"prepare",side_effect=AssertionError(
                "native prepare forbidden")), \
             mock.patch.object(h1_native_batch,"execute",side_effect=AssertionError(
                "native execution forbidden")), \
             mock.patch.object(h1_native_batch,"invoke",side_effect=AssertionError(
                "native subprocess forbidden")):
            self.assert_nonnative(toy.audited_fake_run())
            self.assert_nonnative(toy.fake_split_brain())
            self.assert_nonnative(toy.fake_reset_attack())
            self.assert_nonnative(toy.fake_lost_ack_after_commit())

    def test_only_offline_demo_CLI_actions_accepted(self):
        for action in ("audit-stale-fake-only","demonstrate-naive-stale-read-only",
                       "demonstrate-split-brain-only","demonstrate-reset-only",
                       "demonstrate-ack-loss-only"):
            with self.subTest(action=action),mock.patch("builtins.print"):
                self.assertEqual(toy.main([action]),0)
        for action in ("omc","approve","native","release","execute",
                       "build","launch","reserve-native","run","retry"):
            with self.subTest(forbidden=action),mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as e:
                    toy.main([action])
                self.assertEqual(e.exception.code,2)


if __name__=="__main__":
    unittest.main()
