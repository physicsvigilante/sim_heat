"""SQLite OFFLINE one-slot concurrency demonstration tests, never native."""
from __future__ import annotations
import multiprocessing as mp
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from qualification.h1_c1.f02 import offline_one_shot_ledger_simulator as demo


def _parallel_claim(db: str, result_queue) -> None:
    try:
        result=demo.simulate_once(Path(db))
        result_queue.put(result["status"])
    except Exception as exc:
        result_queue.put("ERROR:"+type(exc).__name__+":"+str(exc))


def _claim_then_exit(db: str) -> None:
    result=demo.simulate_once(Path(db))
    assert result["status"]=="SIMULATED_LOCAL_SLOT_CONSUMED_NOT_NATIVE"
    os._exit(29)


class OfflineSQLiteOneShotSimulationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="simheat-local-lock-")
        self.path=Path(self.tmp.name)/"one-local.sqlite3"

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_claim_and_readonly_inspection_still_nonnative(self):
        result=demo.simulate_once(self.path)
        self.assertEqual(result["status"],"SIMULATED_LOCAL_SLOT_CONSUMED_NOT_NATIVE")
        inspection=demo.inspect_only(self.path)
        self.assertEqual(inspection["status"],"LOCAL_SIMULATED_SLOT_PRESENT_NOT_AUTHORITY")
        self.assertEqual(inspection["localDemoNonce"],result["localDemoNonce"])
        self.assertEqual(result["referenceRawSha256"],demo.REFERENCE_SHA)
        self.assertEqual(result["referenceSeal"],demo.REFERENCE_SEAL)
        for k in (
            "nativeAllowed","nativeExecuted","nativeQualified",
            "realAcrossRunReservationAllocated","ownerNativeLaunchApproved",
            "releaseTrustRootComplete","sharedAcrossHosts",
            "nativeRunnerPresent","compilerQueried","buildInvoked",
            "modelLaunched","referenceRegenerated",
            "historicalF0Static100xPassed","pr32BitwiseRegenerationPassed"
        ):
            self.assertIs(result[k],False,k)

    def test_duplicate_claim_refused_even_after_sqlite_reopen(self):
        first=demo.simulate_once(self.path)
        for _ in range(4):
            second=demo.simulate_once(self.path)
            self.assertEqual(second["status"],"REFUSED_ALREADY_SIMULATED_LOCALLY")
            self.assertEqual(second["localDemoNonce"],first["localDemoNonce"])
        self.assertEqual(demo.inspect_only(self.path)["localDemoNonce"],
                         first["localDemoNonce"])

    def test_cross_process_concurrency_on_single_local_filesystem(self):
        if "fork" not in mp.get_all_start_methods():
            self.skipTest("Linux CI fork required for isolated child process demo")
        context=mp.get_context("fork")
        q=context.Queue()
        processes=[context.Process(target=_parallel_claim,args=(str(self.path),q))
                   for _ in range(10)]
        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=30)
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)
            self.assertEqual(p.exitcode,0,"pure-Python local claim worker failed")
        statuses=[q.get(timeout=5) for _ in processes]
        self.assertEqual(statuses.count("SIMULATED_LOCAL_SLOT_CONSUMED_NOT_NATIVE"),1,
                         statuses)
        self.assertEqual(statuses.count("REFUSED_ALREADY_SIMULATED_LOCALLY"),9,
                         statuses)
        self.assertEqual(demo.inspect_only(self.path)["status"],
                         "LOCAL_SIMULATED_SLOT_PRESENT_NOT_AUTHORITY")

    def test_crash_after_local_commit_cannot_restore_local_slot(self):
        if "fork" not in mp.get_all_start_methods():
            self.skipTest("Linux CI fork required for demo")
        p=mp.get_context("fork").Process(target=_claim_then_exit,
                                         args=(str(self.path),))
        p.start()
        p.join(timeout=20)
        if p.is_alive():
            p.terminate()
            p.join(timeout=5)
        self.assertEqual(p.exitcode,29)
        self.assertEqual(demo.simulate_once(self.path)["status"],
                         "REFUSED_ALREADY_SIMULATED_LOCALLY")

    def test_missing_database_inspection_refuses_without_creating(self):
        with self.assertRaisesRegex(demo.SimulatorRefusal,"no local simulation database"):
            demo.inspect_only(self.path)
        self.assertFalse(self.path.exists())

    def test_tampered_scientific_identity_refuses_on_read(self):
        demo.simulate_once(self.path)
        with sqlite3.connect(self.path) as con:
            con.execute("UPDATE local_demo SET reference_sha=?",
                        ("f"*64,))
        with self.assertRaisesRegex(demo.SimulatorRefusal,"simulated record drift"):
            demo.inspect_only(self.path)
        with self.assertRaises(demo.SimulatorRefusal):
            demo.simulate_once(self.path)

    def test_symlinked_local_db_refused(self):
        other=self.path.parent/"actual.sqlite3"
        demo.simulate_once(other)
        self.path.symlink_to(other)
        with self.assertRaisesRegex(demo.SimulatorRefusal,"symlink"):
            demo.simulate_once(self.path)
        with self.assertRaisesRegex(demo.SimulatorRefusal,"symlink"):
            demo.inspect_only(self.path)

    def test_symlinked_parent_refused(self):
        demo.simulate_once(self.path)
        other=self.path.parent/"linked"
        other.symlink_to(self.path.parent,target_is_directory=True)
        with self.assertRaisesRegex(demo.SimulatorRefusal,"symlink"):
            demo.inspect_only(other/self.path.name)

    def test_invalid_paths_refuse(self):
        for path in (self.path.with_suffix(".json"),
                     self.path.parent/".."/"outside.sqlite3",
                     self.path.parent/".sqlite3"):
            with self.subTest(path=str(path)),self.assertRaises(demo.SimulatorRefusal):
                demo.simulate_once(path)

    def test_local_db_deletion_can_reset_demo_is_not_global_lock(self):
        first=demo.simulate_once(self.path)
        self.path.unlink()
        second=demo.simulate_once(self.path)
        self.assertEqual(first["status"],"SIMULATED_LOCAL_SLOT_CONSUMED_NOT_NATIVE")
        self.assertEqual(second["status"],"SIMULATED_LOCAL_SLOT_CONSUMED_NOT_NATIVE")
        self.assertNotEqual(first["localDemoNonce"],second["localDemoNonce"])
        self.assertIs(second["sharedAcrossHosts"],False)
        self.assertIs(second["realAcrossRunReservationAllocated"],False)

    def test_no_native_or_owner_approval_apis(self):
        self.assertFalse(hasattr(demo,"execute"))
        self.assertFalse(hasattr(demo,"run_omc"))
        self.assertFalse(hasattr(demo,"grant_native"))
        for action in ("execute","build","launch","native","approve",
                       "reserve-native","omc"):
            with self.subTest(action=action),mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as err:
                    demo.cli([action,"--label","safedemo"])
                self.assertEqual(err.exception.code,2)

    def test_cli_simulate_only_then_refuse_repeat(self):
        name="sim-local-demo"
        from qualification.h1_c1.f02.offline_one_shot_ledger_simulator import OUT,ROOT
        parent=ROOT/OUT
        parent.mkdir(exist_ok=True)
        path=parent/(name+".sqlite3")
        if path.exists():
            path.unlink()
        try:
            with mock.patch("builtins.print"):
                self.assertEqual(demo.cli(["simulate-local-only","--label",name]),0)
                self.assertEqual(demo.cli(["simulate-local-only","--label",name]),3)
                self.assertEqual(demo.cli(["inspect-local-only","--label",name]),0)
        finally:
            if path.exists():
                path.unlink()

if __name__=="__main__":
    unittest.main()
