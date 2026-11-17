"""SIM_HEAT F02 OFFLINE external-reservation API CONTRACT + UNTRUSTED FAKE.

This is a pure-Python, non-network, nonnative adversarial model. A fake in-memory
compare-and-set tests one-process concurrency and known split-brain/recovery
failures. It is deliberately incapable of authenticating an owner, validating
a host, issuing a permit, invoking OMC or executing a native plan.

No actual native reservation, OMC version query/build/launch, or trusted
external provider is implemented. A real provider MUST be a separate R2
candidate with owner-authenticated release, source, host, budget, and custody.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import secrets
import threading

SCHEMA = "sim_heat.c1_f02_untrusted_external_cas_design/1"
CAMPAIGN = "H1_C1_F02_UNTRUSTED_CAS_SPEC_ONLY"
SOURCE_COMMIT = "ffc96e743a78cb3c63c01d6bf292d1fa84c6164f"
ORIGINAL_MODEL_SHA = "9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435"
MODAL_STUDY_SHA = "b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b"
V2_RAW_SHA = "0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368"
V2_SEAL = "d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9"
DISABLED_PLAN_SHA = "7e03896563ae8b4762b56bb8807612a93cddb759145a23fa94326363ea706326"
DENIAL = "REFUSED_NO_TRUSTED_EXTERNAL_AUTHORITY_OR_OWNER_NATIVE_PERMISSION"
SIMULATION = "UNTRUSTED_MEMORY_CAS_SIMULATION_NOT_NATIVE"
MISSING = (
    "owner_native_launch_approval_for_named_budgets",
    "owner_authenticated_protected_reviewed_reference_release",
    "independent_retained_verified_reference_backup",
    "live_fresh_source_ref_and_signed_commit_attestation",
    "reviewed_nonregenerating_executable_native_adapter",
    "exact_sha_pinned_native_runner_and_executable_plan",
    "trusted_actual_host_image_and_omc_executable_hash",
    "observed_omc_msl_compiler_and_runtime_identity",
    "owner_controlled_shared_external_transactional_store",
    "durable_across_runs_unique_reservation_and_crash_receipts",
    "independent_pre_native_r2_and_post_native_evidence_policy",
)

class GateRefusal(ValueError):
    """This module never grants native permission."""


def need(condition: bool, reason: str):
    if not condition:
        raise GateRefusal(reason)


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def snapshot() -> dict:
    """Fixed offline facts only; neither version nor owner identities observed."""
    return {
        "schema": SCHEMA,
        "campaign": CAMPAIGN,
        "sourceCommit": SOURCE_COMMIT,
        "firstModelSha256": ORIGINAL_MODEL_SHA,
        "modalStudySha256": MODAL_STUDY_SHA,
        "referenceRawSha256": V2_RAW_SHA,
        "referenceCanonicalSeal": V2_SEAL,
        "disabledNativeControlPreviewSha256": DISABLED_PLAN_SHA,
        "simulatedOnly": True,
        "ownerAuthenticatedReleasePresent": False,
        "ownerNativeLaunchAuthorized": False,
        "trustedSharedReservationPresent": False,
        "trustedNativeAdapterPresent": False,
        "compilerOrHostObserved": False,
        "nativeBudget": {
            "omcVersionQueries": 0,
            "modelBuilds": 0,
            "modelLaunches": 0,
            "retries": 0,
        },
    }


def assert_snapshot(value: dict) -> None:
    need(type(value) is dict and canonical(value) == canonical(snapshot()),
         "offline facts/prohibited budget drift")
    for field in ("simulatedOnly",):
        need(value[field] is True, "false claim of simulation status")
    for field in ("ownerAuthenticatedReleasePresent","ownerNativeLaunchAuthorized",
                  "trustedSharedReservationPresent","trustedNativeAdapterPresent",
                  "compilerOrHostObserved"):
        need(value[field] is False, "unsupported native authority claim")
    need(all(type(x) is int and x == 0 for x in value["nativeBudget"].values()),
         "native version/build/launch/retry budget is NOT approved")


def reservation_key(facts: dict) -> str:
    assert_snapshot(facts)
    # Content-addressing here is only the identity of a simulation scenario.
    return hashlib.sha256(canonical(facts)).hexdigest()


class FakeAtomicCAS:
    """One-process volatile fake provider, NEVER authoritative."""
    def __init__(self):
        self._lock = threading.Lock()
        self._records: dict[str, str] = {}

    def fake_put_if_absent(self, key: str, local_nonce: str) -> bool:
        need(type(key) is str and len(key) == 64 and
             all(c in "0123456789abcdef" for c in key),
             "invalid fake scenario key")
        need(type(local_nonce) is str and len(local_nonce)==32 and
             all(c in "0123456789abcdef" for c in local_nonce),
             "invalid fake local nonce")
        with self._lock:
            if key in self._records:
                return False
            self._records[key] = local_nonce
            return True

    def fake_lookup(self, key: str) -> str | None:
        with self._lock:
            return self._records.get(key)

    def fake_reset_unprotected_state(self) -> None:
        """Deliberate attack: recreation permits another fake claim."""
        with self._lock:
            self._records.clear()


class ExternalAuthorityUnavailable:
    """Fail-closed placeholder; NOT an injectable fake/native provider."""
    def reserve_native(self, *_args, **_kwargs):
        raise GateRefusal(DENIAL)

    def validate_native_launch(self, *_args, **_kwargs):
        raise GateRefusal(DENIAL)


def require_native_permission(*_args, **_kwargs):
    """There is no release owner permission or native authority in this module."""
    raise GateRefusal(DENIAL)


def demo_receipt(status: str, **non_authoritative_counts: int | bool) -> dict:
    return {
        "schema": "sim_heat.c1_f02_untrusted_cas_demo_receipt/1",
        "status": status,
        "sourceCommit": SOURCE_COMMIT,
        "referenceSha256": V2_RAW_SHA,
        "referenceSeal": V2_SEAL,
        "simulatorIsTrustedProvider": False,
        "fakeProviderOnly": True,
        "ownerAuthenticated": False,
        "ownerNativeLaunchApproved": False,
        "nativeAllowed": False,
        "nativeExecuted": False,
        "nativeQualified": False,
        "referenceRegenerated": False,
        "realAcrossRunReservationAllocated": False,
        "crossHostAtomicityProved": False,
        "externalStoreConnected": False,
        "compilerQueried": False,
        "buildInvoked": False,
        "modelLaunched": False,
        "originalF0Reference100xPassed": False,
        "pr32BitwiseReferenceRegenerationPassed": False,
        "missingGates": list(MISSING),
        "fakeResults": non_authoritative_counts,
        "limits": [
            "This in-memory fake has no cross-process/cross-host durability",
            "Split-brain distinct fake providers EACH grant a first claim",
            "Reset/recreation can erase fake reservation evidence",
            "Neither a fake receipt nor raw SHA is an owner/native launch token",
        ],
    }


def simulate_contention(*, contenders: int = 16) -> dict:
    need(type(contenders) is int and 2 <= contenders <= 64,
         "bounded local fake contender count required")
    facts = snapshot()
    key = reservation_key(facts)
    provider = FakeAtomicCAS()
    def attempt(_):
        return provider.fake_put_if_absent(key, secrets.token_hex(16))
    with ThreadPoolExecutor(max_workers=contenders) as executor:
        outcomes = list(executor.map(attempt, range(contenders)))
    need(sum(outcomes) == 1 and provider.fake_lookup(key) is not None,
         "fake one-store contention failed")
    return demo_receipt(SIMULATION,
                        contenders=contenders, fakeFirstClaims=sum(outcomes),
                        fakeDuplicateRefusals=contenders-sum(outcomes))


def simulate_split_brain() -> dict:
    """Two isolated stores are the explicit counterexample to native safety."""
    key = reservation_key(snapshot())
    provider_a, provider_b = FakeAtomicCAS(), FakeAtomicCAS()
    a = provider_a.fake_put_if_absent(key, secrets.token_hex(16))
    b = provider_b.fake_put_if_absent(key, secrets.token_hex(16))
    need(a is True and b is True,
         "independent fake stores should demonstrate split-brain hazard")
    return demo_receipt("UNTRUSTED_SPLIT_BRAIN_TWO_FIRST_CLAIMS_NOT_NATIVE",
                        fakeIndependentFirstClaims=int(a)+int(b))


def simulate_reset_attack() -> dict:
    key = reservation_key(snapshot())
    provider = FakeAtomicCAS()
    first = provider.fake_put_if_absent(key, secrets.token_hex(16))
    provider.fake_reset_unprotected_state()
    second = provider.fake_put_if_absent(key, secrets.token_hex(16))
    need(first is True and second is True,
         "fake reset must demonstrate missing durable reservation")
    return demo_receipt("UNTRUSTED_STATE_RESET_TWO_FIRST_CLAIMS_NOT_NATIVE",
                        fakeFirstClaimsBeforeAndAfterReset=int(first)+int(second))


def audit_contract_only() -> dict:
    facts=snapshot()
    assert_snapshot(facts)
    return demo_receipt(DENIAL, canonicalFactSha256=reservation_key(facts))


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "inspect-unavailable-authority",
        "simulate-contention-only",
        "demonstrate-split-brain-only",
        "demonstrate-reset-only",
    ))
    args=parser.parse_args(argv)
    try:
        op={
            "inspect-unavailable-authority": audit_contract_only,
            "simulate-contention-only": simulate_contention,
            "demonstrate-split-brain-only": simulate_split_brain,
            "demonstrate-reset-only": simulate_reset_attack,
        }[args.action]
        print(json.dumps(op(), indent=2, sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({
            "schema": "sim_heat.c1_f02_untrusted_cas_demo_receipt/1",
            "status": "REFUSED_UNTRUSTED_CAS_SIMULATION",
            "reason": type(exc).__name__+": "+str(exc),
            "nativeAllowed": False,"nativeExecuted": False,
            "ownerNativeLaunchApproved": False,
            "realAcrossRunReservationAllocated": False,
        }, sort_keys=True))
        return 3


if __name__=="__main__":
    raise SystemExit(main())
