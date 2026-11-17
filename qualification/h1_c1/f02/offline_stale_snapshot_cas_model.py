"""F02 OFFLINE STALE-SNAPSHOT CAS DIFFERENTIAL MODEL, NO NATIVE AUTHORITY.

One in-memory Python fake with a lock and version demonstrates why stale
readers need an atomic compare-and-swap. Another fake shows that multiple
unshared providers or erased state can EACH accept a first local claim.
Neither fake proves real cross-host, durable, owner-controlled atomicity.

This file cannot query/build/launch OpenModelica, create a native plan, grant
owner permission, connect to external stores or regenerate reference data.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import secrets
import threading

from qualification.h1_c1.f02 import offline_release_readiness_hold as readiness

SCHEMA="sim_heat.h1_c1_f02_untrusted_stale_snapshot_model/1"
CAMPAIGN="H1_C1_F02_STALE_SNAPSHOT_TOY_NOT_NATIVE"
REVIEWED_TOY_SOURCE_SHA="32cbb7d02b7db0cbc322fb0e7826861fd902a77a"
REFERENCE_RAW_SHA="0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368"
REFERENCE_SEAL="d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9"
REAL_DENIAL="REFUSED_REAL_NATIVE_AUTHORITY_ABSENT"
FAKE_SUCCESS="ONE_UNTRUSTED_VERSIONED_STORE_ONE_TOY_CLAIM"
SPLIT_BRAIN="TWO_UNSHARED_FAKE_STORES_EACH_CLAIM"
RESTORED="FAKE_STORE_RECREATION_RESETS_ONE_SHOT"
NAIVE="STALE_CHECK_THEN_USE_WITHOUT_CAS_DOUBLE_CLAIMS"
UNKNOWN_ACK="FAKE_ACK_LOST_AFTER_COMMIT_NO_RETRY"


class CASRefusal(ValueError):
    pass


def need(ok: bool, reason: str):
    if not ok:
        raise CASRefusal(reason)


@dataclass(frozen=True)
class ObservedToyState:
    """One fake store's current state, NOT a signed receipt or permit."""
    campaign: str
    fake_epoch: str
    version: int
    already_claimed: bool


def check_toy_snapshot(snapshot: ObservedToyState) -> None:
    need(type(snapshot) is ObservedToyState and
         snapshot.campaign == CAMPAIGN and
         type(snapshot.fake_epoch) is str and
         len(snapshot.fake_epoch) == 24 and
         all(c in "0123456789abcdef" for c in snapshot.fake_epoch) and
         type(snapshot.version) is int and snapshot.version in (0,1) and
         snapshot.already_claimed is (snapshot.version == 1),
         "invalid/forged toy snapshot shape or scalar type")


class VolatileVersionedCASFake:
    """Single-memory-object linearization demonstration; NOT a shared provider."""
    def __init__(self) -> None:
        self._lock=threading.Lock()
        self._epoch=secrets.token_hex(12)
        self._version=0
        self._claimed=False

    def observe(self) -> ObservedToyState:
        with self._lock:
            result=ObservedToyState(CAMPAIGN,self._epoch,
                                    self._version,self._claimed)
        check_toy_snapshot(result)
        return result

    def fake_claim_if_unchanged(self, observed: ObservedToyState) -> bool:
        """Atomic for threads on THIS object only; never an owner-native permit."""
        check_toy_snapshot(observed)
        with self._lock:
            matches=(observed.campaign == CAMPAIGN and
                     observed.fake_epoch == self._epoch and
                     observed.version == self._version and
                     observed.already_claimed is self._claimed)
            if not matches or self._claimed:
                return False
            self._claimed=True
            self._version+=1
            return True

    def fake_erase_and_recreate_state(self) -> None:
        """Deliberate hostile reset, proving missing durable custody."""
        with self._lock:
            self._epoch=secrets.token_hex(12)
            self._version=0
            self._claimed=False


def require_real_native_permission(*_args,**_kwargs) -> None:
    """No user signed source/host/plan, OMC budget or real store exists."""
    raise CASRefusal(REAL_DENIAL)


def receipt(status: str, fake_counts: dict | None=None) -> dict:
    return {
        "schema":SCHEMA,
        "status":status,
        "reviewedPriorToySourceCommit":REVIEWED_TOY_SOURCE_SHA,
        "referenceRawSha256":REFERENCE_RAW_SHA,
        "referenceCanonicalSeal":REFERENCE_SEAL,
        "fakeCounts":fake_counts or {},
        "untrustedInMemoryDemonstration":True,
        "ownerAuthenticated":False,
        "nativeAllowed":False,
        "nativeExecuted":False,
        "nativeQualified":False,
        "ownerNativeLaunchApproved":False,
        "realExternalCASConnected":False,
        "ownerControlledStoreAvailable":False,
        "durableOneShotReservationAllocated":False,
        "crossHostAtomicityEstablished":False,
        "compilerVersionQueried":False,
        "modelBuildInvoked":False,
        "modelLaunched":False,
        "referenceRegenerated":False,
        "actualOmcVersionQueryBudget":0,
        "actualModelBuildBudget":0,
        "actualModelLaunchBudget":0,
        "actualRetryBudget":0,
        "originalF0Static100xPassed":False,
        "pr32BitwiseRegenerationPassed":False,
        "releaseBlocked":True,
        "limitations":[
            "Stale snapshot results are only modeled on one in-memory fake object",
            "Different fake instances can each claim the same campaign",
            "Erased or recreated fake memory can restore the first local claim",
            "A lost acknowledgement cannot prove any native effect or authorize retry",
            "No owner authentication, live release, durable external store, or real OMC budget",
        ],
    }


def validate_receipt(x: dict) -> None:
    """Never coerce fake JSON into native authority."""
    need(type(x) is dict and x.get("schema") == SCHEMA and
         x.get("referenceRawSha256") == REFERENCE_RAW_SHA and
         x.get("referenceCanonicalSeal") == REFERENCE_SEAL and
         x.get("releaseBlocked") is True and
         x.get("untrustedInMemoryDemonstration") is True,
         "untrusted receipt/source identity invalid")
    for name in ("ownerAuthenticated","nativeAllowed","nativeExecuted",
                 "nativeQualified","ownerNativeLaunchApproved",
                 "realExternalCASConnected","ownerControlledStoreAvailable",
                 "durableOneShotReservationAllocated","crossHostAtomicityEstablished",
                 "compilerVersionQueried","modelBuildInvoked","modelLaunched",
                 "referenceRegenerated","originalF0Static100xPassed",
                 "pr32BitwiseRegenerationPassed"):
        need(x.get(name) is False,
             "fake/native release claim changed: "+name)
    for name in ("actualOmcVersionQueryBudget","actualModelBuildBudget",
                 "actualModelLaunchBudget","actualRetryBudget"):
        need(type(x.get(name)) is int and x[name] == 0,
             "real OMC budget must be literal JSON integer zero")


def fake_stale_reader_race(*, contenders: int=16) -> dict:
    """Many threads act on the SAME already-read snapshot of ONE toy store."""
    need(type(contenders) is int and 2<=contenders<=32,
         "bounded fictional contender count")
    fake=VolatileVersionedCASFake()
    stale=fake.observe()
    need(stale.version==0 and stale.already_claimed is False,
         "initial fake snapshot unexpectedly claimed")
    with ThreadPoolExecutor(max_workers=contenders) as workers:
        outcomes=list(workers.map(
            fake.fake_claim_if_unchanged,[stale]*contenders))
    need(sum(outcomes)==1 and
         fake.observe().version==1 and
         fake.observe().already_claimed is True,
         "shared-FAKE stale-snapshot CAS did not serialize correctly")
    result=receipt(FAKE_SUCCESS,{
        "contenders":contenders,
        "oneFakeFirstClaims":sum(outcomes),
        "staleRefusals":contenders-sum(outcomes),
        "finalFakeVersion":fake.observe().version,
    })
    validate_receipt(result)
    return result


def fake_stale_check_then_use() -> dict:
    """Unsafe check/read detached from write: both act on the same OLD read."""
    fake=VolatileVersionedCASFake()
    stale=fake.observe()
    # A real store would need a linearizable versioned check at effect time.
    # This purposely models two actors trusting a stale unprotected read.
    naive_first_claims=int(not stale.already_claimed)+int(not stale.already_claimed)
    need(naive_first_claims==2,
         "deliberate non-atomic stale check-then-use counterexample missing")
    result=receipt(NAIVE,{
        "unprotectedStaleReadFirstClaims":naive_first_claims,
        "linearizableCASActuallyUsed":False,
    })
    validate_receipt(result)
    return result


def fake_split_brain() -> dict:
    """Both isolated toy stores return the SAME unclaimed campaign key."""
    a,b=VolatileVersionedCASFake(),VolatileVersionedCASFake()
    sa,sb=a.observe(),b.observe()
    accepted=int(a.fake_claim_if_unchanged(sa))+int(b.fake_claim_if_unchanged(sb))
    need(accepted==2, "two isolated fake stores should both grant a claim")
    result=receipt(SPLIT_BRAIN,{
        "distinctFakeStoreFirstClaims":accepted,
        "globallySharedStoreCount":0,
    })
    validate_receipt(result)
    return result


def fake_reset_attack() -> dict:
    fake=VolatileVersionedCASFake()
    old=fake.observe()
    first=fake.fake_claim_if_unchanged(old)
    fake.fake_erase_and_recreate_state()
    need(fake.fake_claim_if_unchanged(old) is False,
         "old epoch should be refused after a fake reset")
    second=fake.fake_claim_if_unchanged(fake.observe())
    need(first is True and second is True,
         "resettable fake must demonstrate repeated first claims")
    result=receipt(RESTORED,{
        "firstClaimsBeforeAndAfterReset":int(first)+int(second),
        "oldEpochReplayDenied":True,
    })
    validate_receipt(result)
    return result


def fake_lost_ack_after_commit() -> dict:
    """An unknown ack is an ambiguous outcome, NEVER a permission to retry."""
    fake=VolatileVersionedCASFake()
    old=fake.observe()
    committed=fake.fake_claim_if_unchanged(old)
    need(committed is True,"fake first claim failed")
    # Pretend the network reply was lost; the caller has no signed outcome.
    # A later old-snapshot CAS attempt MUST be refused on this same fake.
    retry_accepted=fake.fake_claim_if_unchanged(old)
    need(retry_accepted is False and fake.observe().already_claimed,
         "lost-ack fake retry cannot restore a consumed slot")
    result=receipt(UNKNOWN_ACK,{
        "fakeCommitOccurred":True,
        "callerCanInferNativeEffect":False,
        "fakeRepeatClaimAccepted":retry_accepted,
        "newExternalPermitIssued":False,
    })
    validate_receipt(result)
    return result


def audited_fake_run() -> dict:
    # Inherited PR41 read-only source/release audit MUST say HOLD.
    hold=readiness.audit()
    need(hold["status"] == readiness.STATUS and
         hold["missingRequiredGateCount"]==11 and
         hold["releaseBlocked"] is True and
         hold["nativeAllowed"] is False and
         hold["realAcrossRunReservationAllocated"] is False,
         "owner/host/release/native gates are STILL MISSING")
    result=fake_stale_reader_race()
    need(result["nativeAllowed"] is False,"fake results cannot authorize native")
    return result


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=(
        "audit-stale-fake-only",
        "demonstrate-naive-stale-read-only",
        "demonstrate-split-brain-only",
        "demonstrate-reset-only",
        "demonstrate-ack-loss-only",
    ))
    args=parser.parse_args(argv)
    try:
        method={
            "audit-stale-fake-only":audited_fake_run,
            "demonstrate-naive-stale-read-only":fake_stale_check_then_use,
            "demonstrate-split-brain-only":fake_split_brain,
            "demonstrate-reset-only":fake_reset_attack,
            "demonstrate-ack-loss-only":fake_lost_ack_after_commit,
        }[args.action]
        print(json.dumps(method(),sort_keys=True,indent=2,allow_nan=False))
        return 0  # Successful FAKE inspection, not actual authority.
    except Exception as exc:
        print(json.dumps({
            "schema":SCHEMA,"status":"REFUSED_UNTRUSTED_STALE_SNAPSHOT_MODEL",
            "reason":type(exc).__name__+": "+str(exc),
            "nativeAllowed":False,"nativeExecuted":False,
            "ownerNativeLaunchApproved":False,
            "durableOneShotReservationAllocated":False,
            "releaseBlocked":True,
        },sort_keys=True))
        return 3


if __name__=="__main__":
    raise SystemExit(main())
