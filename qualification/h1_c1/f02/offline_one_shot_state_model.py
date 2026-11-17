"""F02 PURE MODEL-CHECKER of a HYPOTHETICAL one-shot protocol.

NO EXECUTION. NO NATIVE BUDGET. NO OWNER AUTHORITY. NO REAL ATOMIC STORE.
State transitions are immutable Python data and use only fictional action
labels. They never contact OMC, an external provider, or a Modelica runner.

This checks at-most-once transition rules *assuming a single immutable state
history*. Split-brain/fresh-state resets are exhibited as COUNTEREXAMPLES,
so even a successful model check is NEVER a protected global reservation.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass, replace
import json
from pathlib import Path
from collections import deque

from qualification.h1_c1.f02 import offline_release_readiness_hold as hold

SCHEMA="sim_heat.h1_c1_f02_nonexecuting_state_model/1"
HYPOTHETICAL_ACTIONS=("version","build","launch")
ALL_EVENTS=("claim-version","claim-build","claim-launch",
            "simulate-ok","simulate-failure","crash","outage")
AWAIT=("AWAIT_HYPOTHETICAL_VERSION","AWAIT_HYPOTHETICAL_BUILD",
       "AWAIT_HYPOTHETICAL_LAUNCH")
CONSUMED=("HYPOTHETICAL_VERSION_SLOT_CONSUMED","HYPOTHETICAL_BUILD_SLOT_CONSUMED",
          "HYPOTHETICAL_LAUNCH_SLOT_CONSUMED")
DONE="HYPOTHETICAL_SEQUENCE_FINISHED_NO_OMC"
STOP="HYPOTHETICAL_SEQUENCE_STOPPED_NO_RETRY"
STAGES=AWAIT+CONSUMED+(DONE,STOP)
CONTRACT_SOURCE="47be71571e5cfdf12a5576ebe6f18db355d2dc4b"


class ModelRefusal(ValueError):
    pass


def need(ok: bool, why: str):
    if not ok:
        raise ModelRefusal(why)


@dataclass(frozen=True)
class HypotheticalState:
    phase: str
    simulated_claims: tuple[int,int,int]
    history: tuple[str,...]
    # This is a local protocol model, NEVER a key, permit, or signed identity.
    owner_native_permission: bool = False
    external_durable_store_verified: bool = False
    actual_omc_budget: tuple[int,int,int] = (0,0,0)


def start() -> HypotheticalState:
    return HypotheticalState(AWAIT[0],(0,0,0),())


def check_state(s: HypotheticalState):
    need(type(s) is HypotheticalState and type(s.phase) is str and
         s.phase in STAGES, "invalid fictional state")
    need(type(s.simulated_claims) is tuple and len(s.simulated_claims)==3 and
         all(type(k) is int and k in (0,1) for k in s.simulated_claims),
         "duplicate/nonintegral fictional reservation counts")
    need(type(s.history) is tuple and all(
         type(e) is str and e in ALL_EVENTS for e in s.history),
         "forged/unexpected hypothetical event history")
    need(s.owner_native_permission is False and
         s.external_durable_store_verified is False and
         s.actual_omc_budget==(0,0,0) and
         all(type(k) is int for k in s.actual_omc_budget),
         "real owner, external durable store, or OMC budget is NOT authorized")
    expected={
        AWAIT[0]:(0,0,0),
        CONSUMED[0]:(1,0,0),
        AWAIT[1]:(1,0,0),
        CONSUMED[1]:(1,1,0),
        AWAIT[2]:(1,1,0),
        CONSUMED[2]:(1,1,1),
        DONE:(1,1,1),
    }
    if s.phase in expected:
        need(s.simulated_claims==expected[s.phase],
             "impossible hypothetical claim/phase state")
    need(len(s.history)<=9,"unexpectedly long fictional history")
    # History must be reachable under this exact read-only transition model.
    # This is not a cryptographic provenance check or external persistence.
    if s.phase == AWAIT[0]:
        need(not s.history,"initial state cannot have earlier effects")
    if s.phase == STOP:
        need(len(s.history)>0 and s.history[-1] in
             ("crash","outage","simulate-failure"),
             "stopped state must have an explicit terminal event")
    if s.phase == DONE:
        need(len(s.history)>0 and s.history[-1]=="simulate-ok",
             "complete toy sequence requires final simulated success")
    # Never accept a state whose fake counts/phase were edited to disagree
    # with its fictional event sequence. This is self-consistency only, NOT
    # a signature or a protected native audit ledger.
    phase=AWAIT[0]
    claims=[0,0,0]
    claim_events=("claim-version","claim-build","claim-launch")
    for e in s.history:
        need(phase not in (DONE,STOP),
             "event invented after terminal fictional state")
        if e in claim_events:
            i=claim_events.index(e)
            need(phase==AWAIT[i] and claims[i]==0,
                 "impossible fictional claim history")
            claims[i]=1
            phase=CONSUMED[i]
        elif e=="simulate-ok":
            need(phase in CONSUMED,
                 "fictional success without a consumed slot")
            i=CONSUMED.index(phase)
            phase=AWAIT[i+1] if i<2 else DONE
        elif e=="simulate-failure":
            need(phase in CONSUMED,
                 "fictional failure without a consumed slot")
            phase=STOP
        elif e in ("crash","outage"):
            phase=STOP
    need(phase==s.phase and tuple(claims)==s.simulated_claims,
         "fictional state does not match its complete event history")


def move(s: HypotheticalState, event: str) -> HypotheticalState:
    """Pure transition function: no side effects or native action."""
    check_state(s)
    need(type(event) is str and event in ALL_EVENTS,
         "no executable/native action in fictional protocol")
    need(s.phase not in (DONE,STOP),
         "terminal simulated phase cannot be reset or retried")
    claim_events=("claim-version","claim-build","claim-launch")
    if event in claim_events:
        idx=claim_events.index(event)
        need(s.phase==AWAIT[idx], "out-of-order, duplicate, or retried claim")
        counts=list(s.simulated_claims)
        need(counts[idx]==0,"duplicate hypothetical claim")
        counts[idx]=1
        result=replace(s,phase=CONSUMED[idx],simulated_claims=tuple(counts),
                       history=s.history+(event,))
    elif event=="simulate-ok":
        need(s.phase in CONSUMED,
             "hypothetical outcome without pre-consumed slot")
        idx=CONSUMED.index(s.phase)
        result=replace(s,phase=AWAIT[idx+1] if idx<2 else DONE,
                       history=s.history+(event,))
    elif event=="simulate-failure":
        need(s.phase in CONSUMED,
             "hypothetical failure without pre-consumed slot")
        result=replace(s,phase=STOP,history=s.history+(event,))
    else:  # crash and outage: UNKNOWN outcome => consume, do not retry.
        result=replace(s,phase=STOP,history=s.history+(event,))
    check_state(result)
    need(all(a>=b for a,b in zip(result.simulated_claims,s.simulated_claims)),
         "hypothetical consumed-slot count decreased")
    return result


def exhaustive_model_check(max_depth: int=9, *, root: Path=hold.ROOT) -> dict:
    """Bounded state graph from ONE toy state, with all invalid events refused."""
    need(type(max_depth) is int and 1<=max_depth<=9,
         "bounded MODEL exploration only")
    report=hold.audit(root=root)
    need(report["releaseBlocked"] is True and
         report["status"]==hold.STATUS and
         report["missingRequiredGateCount"]==11 and
         report["nativeAllowed"] is False and
         report["ownerNativeLaunchApproved"] is False and
         report["realAcrossRunReservationAllocated"] is False,
         "actual native release gates must remain MISSING")
    initial=start()
    visited={initial}
    q=deque([(initial,0)])
    accepted=0
    refused=0
    while q:
        current,depth=q.popleft()
        check_state(current)
        if depth>=max_depth:
            continue
        for event in ALL_EVENTS:
            try:
                nxt=move(current,event)
            except ModelRefusal:
                refused+=1
                continue
            accepted+=1
            if nxt not in visited:
                visited.add(nxt)
                q.append((nxt,depth+1))
    states=list(visited)
    need(all(max(s.simulated_claims)<=1 and
             s.owner_native_permission is False and
             s.actual_omc_budget==(0,0,0) and
             s.external_durable_store_verified is False for s in states),
         "toy state invariant violated")
    return {
        **denied_receipt("BOUNDED_HYPOTHETICAL_PROTOCOL_CHECK_NOT_NATIVE"),
        "modelStateCount":len(states),
        "acceptedToyTransitions":accepted,
        "refusedToyTransitions":refused,
        "terminalToyStates":sum(s.phase in (DONE,STOP) for s in states),
        "explorationDepth":max_depth,
        "toyAtMostOnceInvariant":True,
    }


def demonstrate_crash_hold() -> dict:
    s=start()
    s=move(s,"claim-version")
    s=move(s,"crash")
    refused=False
    try:
        move(s,"claim-version")
    except ModelRefusal:
        refused=True
    need(refused and s.simulated_claims==(1,0,0),
         "toy crash must refuse any later local retry")
    return {**denied_receipt("HYPOTHETICAL_CRASH_CONSUMES_LOCAL_SLOT_NO_RETRY"),
            "simulatedClaims":list(s.simulated_claims),
            "retryRefusedInToy":True}


def demonstrate_outage_hold() -> dict:
    s=start()
    s=move(s,"claim-version")
    s=move(s,"simulate-ok")
    s=move(s,"claim-build")
    s=move(s,"outage")
    refused=False
    try:
        move(s,"simulate-ok")
    except ModelRefusal:
        refused=True
    need(refused and s.simulated_claims==(1,1,0),
         "toy outage must fail closed without additional effects")
    return {**denied_receipt("HYPOTHETICAL_OUTAGE_STOPS_TOY_SEQUENCE"),
            "simulatedClaims":list(s.simulated_claims),
            "restartRefusedInToy":True}


def demonstrate_split_brain() -> dict:
    """Two separate roots each allow the same *fictional* first claim."""
    first=move(start(),"claim-version")
    second=move(start(),"claim-version")
    need(first.simulated_claims==second.simulated_claims==(1,0,0),
         "split-brain counterexample must be visible")
    return {**denied_receipt("TWO_FRESH_TOY_STATES_BOTH_CLAIM_NO_GLOBAL_GUARANTEE"),
            "independentFictionalFirstClaims":2,
            "realCrossHostUniquenessProved":False}


def denied_receipt(status: str) -> dict:
    return {
        "schema":SCHEMA,
        "status":status,
        "reviewedOfflineHoldCommit":CONTRACT_SOURCE,
        "referenceRawSha256":"0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368",
        "referenceSeal":"d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9",
        "ownerNativeAuthorized":False,
        "realAtomicExternalReservationPresent":False,
        "ownerNativeLaunchBudget":0,
        "actualOmcVersionQueryBudget":0,
        "actualModelBuildBudget":0,
        "actualModelLaunchBudget":0,
        "actualRetryBudget":0,
        "nativeAllowed":False,
        "nativeExecuted":False,
        "nativeQualified":False,
        "compilerQueried":False,
        "buildInvoked":False,
        "modelLaunched":False,
        "referenceRegenerated":False,
        "originalF0Static100xPassed":False,
        "pr32BitwiseRegenerationPassed":False,
        "releaseBlocked":True,
        "limits":[
            "Pure hypothetical transition model; NOT a native launch runner or permit",
            "At-most-once only within ONE shared toy-state history, never across fresh stores",
            "A crash/outage cannot be treated as evidence of effect success",
            "11 real owner/host/release/atomic-reservation gates remain absent",
        ],
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=(
        "check-hypothetical-only",
        "demonstrate-crash-hold-only",
        "demonstrate-outage-hold-only",
        "demonstrate-split-brain-only",
    ))
    args=parser.parse_args(argv)
    try:
        result={
            "check-hypothetical-only":exhaustive_model_check,
            "demonstrate-crash-hold-only":demonstrate_crash_hold,
            "demonstrate-outage-hold-only":demonstrate_outage_hold,
            "demonstrate-split-brain-only":demonstrate_split_brain
        }[args.action]()
        print(json.dumps(result,sort_keys=True,indent=2,allow_nan=False))
        return 0  # Toy checker was run, NEVER native authorization.
    except Exception as exc:
        print(json.dumps({
            "schema":SCHEMA,"status":"REFUSED_TOY_ONE_SHOT_PROTOCOL",
            "reason":type(exc).__name__+": "+str(exc),
            "releaseBlocked":True,"nativeAllowed":False,
            "ownerNativeAuthorized":False,"nativeExecuted":False,
            "actualModelLaunchBudget":0,
        },sort_keys=True))
        return 3


if __name__=="__main__":
    raise SystemExit(main())
