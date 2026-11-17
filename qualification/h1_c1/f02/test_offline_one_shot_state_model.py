"""Regression and adversarial tests for a HYPOTHETICAL, nonnative F02 model."""
from __future__ import annotations
from dataclasses import replace
import itertools
import json
import unittest
from unittest import mock

from h1 import reference
from tools import h1_native_batch
from qualification.h1_c1.f02 import offline_one_shot_state_model as model


class OfflineOneShotProtocolModelTests(unittest.TestCase):
    def test_legitimate_toy_three_step_sequence_with_distinct_consumed_slots(self):
        s=model.start()
        for step,ix in (("version",0),("build",1),("launch",2)):
            s=model.move(s,"claim-"+step)
            self.assertEqual(s.phase,model.CONSUMED[ix])
            self.assertEqual(s.simulated_claims[ix],1)
            s=model.move(s,"simulate-ok")
            self.assertEqual(s.phase,model.AWAIT[ix+1] if ix<2 else model.DONE)
        self.assertEqual(s.simulated_claims,(1,1,1))
        self.assertEqual(len(s.history),6)
        with self.assertRaises(model.ModelRefusal):
            model.move(s,"claim-launch")
        self.assertIs(s.owner_native_permission,False)
        self.assertIs(s.external_durable_store_verified,False)
        self.assertEqual(s.actual_omc_budget,(0,0,0))

    def test_success_requires_reservation_before_fictional_effect(self):
        for event in ("simulate-ok","simulate-failure","claim-build","claim-launch"):
            with self.subTest(event=event),self.assertRaises(model.ModelRefusal):
                model.move(model.start(),event)

    def test_duplicate_first_claim_does_not_create_second_slot(self):
        s=model.move(model.start(),"claim-version")
        self.assertEqual(s.simulated_claims,(1,0,0))
        for e in ("claim-version","claim-build","claim-launch"):
            with self.subTest(e=e),self.assertRaises(model.ModelRefusal):
                model.move(s,e)

    def test_failed_version_consumes_slot_and_stops_all_retries(self):
        s=model.move(model.start(),"claim-version")
        s=model.move(s,"simulate-failure")
        self.assertEqual(s.phase,model.STOP)
        self.assertEqual(s.simulated_claims,(1,0,0))
        for event in model.ALL_EVENTS:
            with self.subTest(event=event),self.assertRaises(model.ModelRefusal):
                model.move(s,event)

    def test_failed_build_retains_prior_counts_and_denies_launch(self):
        s=model.start()
        for e in ("claim-version","simulate-ok","claim-build","simulate-failure"):
            s=model.move(s,e)
        self.assertEqual(s.phase,model.STOP)
        self.assertEqual(s.simulated_claims,(1,1,0))
        with self.assertRaises(model.ModelRefusal):
            model.move(s,"claim-launch")

    def test_crash_after_first_claim_denies_retry(self):
        x=model.demonstrate_crash_hold()
        self.assertEqual(x["status"],"HYPOTHETICAL_CRASH_CONSUMES_LOCAL_SLOT_NO_RETRY")
        self.assertEqual(x["simulatedClaims"],[1,0,0])
        self.assertIs(x["retryRefusedInToy"],True)
        self.assertIs(x["nativeAllowed"],False)

    def test_outage_after_second_claim_denies_restart(self):
        x=model.demonstrate_outage_hold()
        self.assertEqual(x["simulatedClaims"],[1,1,0])
        self.assertIs(x["restartRefusedInToy"],True)
        self.assertIs(x["releaseBlocked"],True)

    def test_crash_before_any_toy_claim_stops_just_this_history(self):
        s=model.move(model.start(),"crash")
        self.assertEqual(s.phase,model.STOP)
        self.assertEqual(s.simulated_claims,(0,0,0))
        with self.assertRaises(model.ModelRefusal):
            model.move(s,"claim-version")

    def test_two_fresh_states_can_reclaim_the_same_toy_campaign(self):
        # THIS IS THE COUNTEREXAMPLE to a real external owner-controlled lock.
        x=model.demonstrate_split_brain()
        self.assertEqual(x["status"],
                         "TWO_FRESH_TOY_STATES_BOTH_CLAIM_NO_GLOBAL_GUARANTEE")
        self.assertEqual(x["independentFictionalFirstClaims"],2)
        self.assertIs(x["realCrossHostUniquenessProved"],False)
        self.assertIs(x["realAtomicExternalReservationPresent"],False)

    def test_full_bounded_graph_holds_only_under_one_state_history(self):
        x=model.exhaustive_model_check(max_depth=9)
        self.assertEqual(x["status"],"BOUNDED_HYPOTHETICAL_PROTOCOL_CHECK_NOT_NATIVE")
        self.assertTrue(x["toyAtMostOnceInvariant"])
        self.assertGreater(x["modelStateCount"],8)
        self.assertGreater(x["acceptedToyTransitions"],8)
        self.assertGreater(x["refusedToyTransitions"],8)
        self.assertEqual(x["explorationDepth"],9)
        self.assertIs(x["releaseBlocked"],True)
        for name in ("nativeAllowed","nativeExecuted","nativeQualified",
                     "ownerNativeAuthorized","realAtomicExternalReservationPresent",
                     "compilerQueried","buildInvoked","modelLaunched",
                     "referenceRegenerated","originalF0Static100xPassed",
                     "pr32BitwiseRegenerationPassed"):
            self.assertIs(x[name],False,name)

    def test_model_exploration_budget_limits_refuse_wrong_types(self):
        for bound in (0,-1,10,False,True,9.0,None):
            with self.subTest(bound=repr(bound)):
                with self.assertRaises(model.ModelRefusal):
                    model.exhaustive_model_check(max_depth=bound)

    def test_forged_real_owner_or_native_budget_refuses(self):
        original=model.start()
        claims=(
            {"owner_native_permission":True},
            {"external_durable_store_verified":True},
            {"actual_omc_budget":(1,0,0)},
            {"actual_omc_budget":(0,1,0)},
            {"actual_omc_budget":(0,0,1)},
            {"actual_omc_budget":(False,0,0)},
            {"actual_omc_budget":(0.0,0,0)},
        )
        for change in claims:
            with self.subTest(change=change):
                forged=replace(original,**change)
                with self.assertRaises(model.ModelRefusal):
                    model.check_state(forged)

    def test_invented_phase_or_claim_counters_refused(self):
        cases=(
            {"phase":model.CONSUMED[0]},
            {"phase":model.AWAIT[1]},
            {"simulated_claims":(1,0,0)},
            {"simulated_claims":(True,0,0)},
            {"simulated_claims":(0.0,0,0)},
            {"history":("claim-launch",)},
            {"history":("simulate-ok",)},
            {"history":("claim-version","claim-version")},
            {"history":("claim-version","simulate-ok","claim-launch")},
            {"phase":model.STOP, "history":("crash","claim-version")},
            {"phase":model.DONE, "history":("simulate-ok",)},
        )
        for change in cases:
            with self.subTest(change=change):
                with self.assertRaises(model.ModelRefusal):
                    model.check_state(replace(model.start(),**change))

    def test_future_events_after_crash_outage_completion_are_refused(self):
        roots=(
            model.move(model.start(),"crash"),
            model.move(model.start(),"outage"),
        )
        done=model.start()
        for e in ("claim-version","simulate-ok",
                  "claim-build","simulate-ok",
                  "claim-launch","simulate-ok"):
            done=model.move(done,e)
        for state in (*roots,done):
            for event in model.ALL_EVENTS:
                with self.subTest(phase=state.phase,event=event):
                    with self.assertRaises(model.ModelRefusal):
                        model.move(state,event)

    def test_malformed_event_or_actual_native_action_never_admitted(self):
        for event in ("omc","build","execute","launch","approve",
                      "reserve-native","reference.prepare",True,None,0):
            with self.subTest(event=repr(event)):
                with self.assertRaises(model.ModelRefusal):
                    model.move(model.start(),event)

    def test_missing_real_release_hold_blocks_model_check(self):
        with mock.patch.object(model.hold,"audit",
                               side_effect=model.ModelRefusal("owner trust absent")):
            with self.assertRaises(model.ModelRefusal):
                model.exhaustive_model_check()

    def test_no_native_runner_or_reference_generator_invocations(self):
        with mock.patch.object(reference,"prepare",side_effect=AssertionError(
             "reference regeneration forbidden")), \
             mock.patch.object(h1_native_batch,"prepare",side_effect=AssertionError(
             "native prepare forbidden")), \
             mock.patch.object(h1_native_batch,"execute",side_effect=AssertionError(
             "native execute forbidden")), \
             mock.patch.object(h1_native_batch,"invoke",side_effect=AssertionError(
             "native subprocess forbidden")):
            self.assertTrue(model.exhaustive_model_check()["toyAtMostOnceInvariant"])
            self.assertIs(model.demonstrate_crash_hold()["releaseBlocked"],True)
            self.assertIs(model.demonstrate_outage_hold()["releaseBlocked"],True)
            self.assertIs(model.demonstrate_split_brain()["releaseBlocked"],True)

    def test_cli_bounded_actions_and_no_native_actions(self):
        for action in ("check-hypothetical-only","demonstrate-crash-hold-only",
                       "demonstrate-outage-hold-only","demonstrate-split-brain-only"):
            with self.subTest(action=action),mock.patch("builtins.print"):
                self.assertEqual(model.main([action]),0)
        for action in ("omc","approve","execute","launch","build","native",
                       "reserve-native","retry","reset-real-store","prepare","run"):
            with self.subTest(action=action),mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as x:
                    model.main([action])
                self.assertEqual(x.exception.code,2)


if __name__=="__main__":
    unittest.main()
