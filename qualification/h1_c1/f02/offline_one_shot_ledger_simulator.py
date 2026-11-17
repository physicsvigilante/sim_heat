"""LOCAL OFFLINE SQLite one-slot concurrency SIMULATOR (NOT native authorization).

Purpose: exercise atomic persistence and duplicate refusal on ONE disposable
filesystem using pure Python SQLite. This is not a live owner-controlled,
protected, cross-host or cross-GitHub-runs reservation. It never prepares a
native plan, invokes omc, launches a model, or grants native permission.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import uuid

ROOT=Path(__file__).resolve().parents[3]
OUT="c1_f02_one_shot_simulation_evidence"
LABEL=re.compile(r"[a-z][a-z0-9-]{0,31}\Z")
CAMPAIGN="H1_C1_F02_SIMULATED_ONLY_ORIGINAL_PR31_V2"
REFERENCE_SHA="0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368"
REFERENCE_SEAL="d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9"
PREVIEW_SHA="7e03896563ae8b4762b56bb8807612a93cddb759145a23fa94326363ea706326"
PR38_REVIEWED_HEAD="f87a9aa025caf5091da8fe3613734b62281ebe1c"
SCHEMA_VERSION=1
TABLE_SQL=("""
CREATE TABLE IF NOT EXISTS local_demo (
    campaign TEXT PRIMARY KEY,
    reference_sha TEXT NOT NULL,
    plan_sha TEXT NOT NULL,
    source_head TEXT NOT NULL,
    nonce TEXT NOT NULL,
    created_utc TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state='SIMULATED_SLOT_CONSUMED'),
    actual_native_auth TEXT NOT NULL CHECK (actual_native_auth='NOT_GRANTED')
)
""")

class SimulatorRefusal(ValueError):
    pass

def need(ok,reason):
    if not ok:
        raise SimulatorRefusal(reason)

def safe_path(database: Path) -> Path:
    p=Path(database).absolute()
    need(p.suffix==".sqlite3" and
         p.name not in (".sqlite3",) and
         not any(part==".." for part in Path(database).parts),
         "unsafe simulation ledger name")
    need(not p.is_symlink() and
         not any(q.is_symlink() for q in (p.parent,*p.parent.parents)),
         "symlink in simulated ledger path")
    need(p.parent.is_dir(), "simulation ledger parent missing")
    return p

def facts(row):
    need(row is not None and len(row)==8, "missing local simulated reservation")
    keys=("campaign","reference_sha","plan_sha","source_head",
          "nonce","created_utc","state","actual_native_auth")
    d=dict(zip(keys,row))
    need(d["campaign"]==CAMPAIGN and
         d["reference_sha"]==REFERENCE_SHA and
         d["plan_sha"]==PREVIEW_SHA and
         d["source_head"]==PR38_REVIEWED_HEAD and
         type(d["nonce"]) is str and len(d["nonce"])==32 and
         all(c in "0123456789abcdef" for c in d["nonce"]) and
         type(d["created_utc"]) is str and d["created_utc"].endswith("+00:00") and
         d["state"]=="SIMULATED_SLOT_CONSUMED" and
         d["actual_native_auth"]=="NOT_GRANTED",
         "simulated record drift / claimed real authority")
    return d

def receipt(status: str, *, recorded: bool, local_token: str | None=None) -> dict:
    return {
        "schema":"sim_heat.c1_f02_local_ledger_simulator/1",
        "status":status,
        "campaign":CAMPAIGN,
        "referenceRawSha256":REFERENCE_SHA,
        "referenceSeal":REFERENCE_SEAL,
        "disabledPreviewRawSha256":PREVIEW_SHA,
        "reviewedOfflinePreviewSourceCommit":PR38_REVIEWED_HEAD,
        "simulatedLocalSlotRecorded":recorded,
        "localDemoNonce":local_token,
        "nativeAllowed":False,
        "nativeExecuted":False,
        "nativeQualified":False,
        "realAcrossRunReservationAllocated":False,
        "ownerNativeLaunchApproved":False,
        "releaseTrustRootComplete":False,
        "sharedAcrossHosts":False,
        "nativeRunnerPresent":False,
        "compilerQueried":False,
        "buildInvoked":False,
        "modelLaunched":False,
        "referenceRegenerated":False,
        "historicalF0Static100xPassed":False,
        "pr32BitwiseRegenerationPassed":False,
        "limitations":[
            "Local SQLite simulation is NOT a trusted native one-shot reservation",
            "Database may be deleted/replaced and is not protected across CI hosts",
            "No owner-authenticated signed release, native host, OMC, or real execution",
            "Crash after local simulated insert consumes local slot, not global launch budget",
        ],
    }

def _open(path):
    con=sqlite3.connect(str(path),timeout=30.0,isolation_level=None)
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA synchronous=FULL")
    return con

def _read(con):
    result=con.execute("SELECT campaign,reference_sha,plan_sha,source_head,"
                       "nonce,created_utc,state,actual_native_auth FROM local_demo").fetchall()
    need(len(result)==1,"local simulated ledger expected exactly one campaign")
    return facts(result[0])

def simulate_once(database: Path):
    """One local SQLite serializable claim; never a native permission token."""
    p=safe_path(database)
    con=_open(p)
    try:
        # Atomic between cooperative SQLite processes on ONE local filesystem.
        con.execute("BEGIN IMMEDIATE")
        con.execute(TABLE_SQL)
        nonce=uuid.uuid4().hex
        utc=datetime.now(timezone.utc).isoformat()
        inserted=con.execute(
            "INSERT INTO local_demo "
            "(campaign,reference_sha,plan_sha,source_head,nonce,created_utc,state,actual_native_auth) "
            "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(campaign) DO NOTHING",
            (CAMPAIGN,REFERENCE_SHA,PREVIEW_SHA,PR38_REVIEWED_HEAD,nonce,utc,
             "SIMULATED_SLOT_CONSUMED","NOT_GRANTED")).rowcount
        row=_read(con)
        con.commit()
        return receipt("SIMULATED_LOCAL_SLOT_CONSUMED_NOT_NATIVE"
                       if inserted==1 else "REFUSED_ALREADY_SIMULATED_LOCALLY",
                       recorded=True,local_token=row["nonce"])
    except (sqlite3.Error,SimulatorRefusal):
        con.rollback()
        raise
    finally:
        con.close()

def inspect_only(database: Path):
    """Read local demo without creating new sqlite database or consuming slot."""
    p=safe_path(database)
    need(p.is_file(),"no local simulation database exists")
    # Connecting read-only ensures inspection cannot silently create a slot.
    con=sqlite3.connect(p.as_uri()+"?mode=ro",uri=True,timeout=5.0)
    try:
        row=_read(con)
        return receipt("LOCAL_SIMULATED_SLOT_PRESENT_NOT_AUTHORITY",
                       recorded=True,local_token=row["nonce"])
    finally:
        con.close()

def cli(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("simulate-local-only","inspect-local-only"))
    parser.add_argument("--label",required=True)
    args=parser.parse_args(argv)
    try:
        need(type(args.label) is str and LABEL.fullmatch(args.label) is not None,
             "unsafe label")
        parent=ROOT/OUT
        need(not parent.is_symlink(),"invalid local simulation scratch")
        if args.action=="simulate-local-only":
            parent.mkdir(exist_ok=True)
        db=parent/(args.label+".sqlite3")
        result=(simulate_once if args.action=="simulate-local-only"
                else inspect_only)(db)
        print(json.dumps(result,sort_keys=True,indent=2,allow_nan=False))
        return 0 if result["status"]=="SIMULATED_LOCAL_SLOT_CONSUMED_NOT_NATIVE" or (
            args.action=="inspect-local-only" and result["status"]==
            "LOCAL_SIMULATED_SLOT_PRESENT_NOT_AUTHORITY") else 3
    except Exception as exc:
        print(json.dumps({
            "schema":"sim_heat.c1_f02_local_ledger_simulator/1",
            "status":"REFUSED_LOCAL_SIMULATOR",
            "reason":type(exc).__name__+": "+str(exc),
            "nativeAllowed":False,"nativeExecuted":False,
            "realAcrossRunReservationAllocated":False,
            "ownerNativeLaunchApproved":False,
        },sort_keys=True))
        return 3

if __name__=="__main__":
    raise SystemExit(cli())
