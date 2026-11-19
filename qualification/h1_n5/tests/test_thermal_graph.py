"""Checking-only generic H1 thermal balance and trial snapshot controls."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
import json
from pathlib import Path
import unittest

from qualification.h1_n5 import thermal_graph as n5
from qualification.h1_n4 import static_physical as n4

ORIGINAL=Path(__file__).resolve().parents[2]/"h1_n1/reference-facts.json"
PIN="39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf"

def compact(obj):
    raw=(json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
    return raw, sha256(raw).hexdigest()

def steady_chain():
    return {
        "schema":"sim_heat.reference/1","id":"UnfamiliarSerialJunction",
        "mode":"steady","modelSha256":"1"*64,"studySha256":"2"*64,
        "analysis":{},"provenance":"SYNTHETIC graph fixture, no physical simulator output",
        "nodes":["HotNode","Junction","ColdNode"],
        "bodies":{},
        "boundaries":{"Source":{"node":"HotNode","T":400},
                      "Sink":{"node":"ColdNode","T":300}},
        "rods":{"First":{"kind":"RodArea","a":"HotNode","b":"Junction",
                         "k":10,"A":0.1,"L":1},
                "Second":{"kind":"RodArea","a":"Junction","b":"ColdNode",
                          "k":10,"A":0.1,"L":1}},
    }

def transient_network():
    return {
        "schema":"sim_heat.reference/1","id":"NewThermalGraphWithIsolatedBody",
        "mode":"transient","modelSha256":"3"*64,"studySha256":"4"*64,
        "analysis":{"startTime":0,"stopTime":2400,"intervals":2400,"solver":"dassl","tolerance":1e-8},
        "provenance":"SYNTHETIC transient physical source facts, not a native result",
        "nodes":["Warm","Junction","BodyNode","Cool","FloatingBody"],
        "bodies":{"Mass":{"node":"BodyNode","m":0.5,"c":600,"T_initial":325},
                  "Isolated":{"node":"FloatingBody","m":0.1,"c":500,"T_initial":315}},
        "boundaries":{"WarmSource":{"node":"Warm","T":370},
                      "ColdSink":{"node":"Cool","T":290}},
        "rods":{"HotLeg":{"kind":"RodArea","a":"Warm","b":"Junction",
                          "k":10,"A":0.1,"L":1},
                "MidLeg":{"kind":"RodArea","a":"Junction","b":"BodyNode",
                          "k":10,"A":0.1,"L":1},
                "ColdLeg":{"kind":"RodArea","a":"BodyNode","b":"Cool",
                           "k":10,"A":0.1,"L":1},
                "Round":{"kind":"RodCircular","a":"Warm","b":"BodyNode",
                         "k":80,"d":0.01,"L":0.5}},
    }

class GenericGraphBalance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=ORIGINAL.read_bytes()
        assert sha256(cls.original).hexdigest()==PIN

    def test_original_t1_topology_generic_node_law_counts_and_source_identity(self):
        a=n5.assemble(self.original,expected_sha256=PIN)
        self.assertEqual(a["rodCount"],10)
        self.assertEqual((a["bodies"],a["boundaries"],a["junctions"]),(3,2,2))
        self.assertEqual(len(a["nodes"]),7)
        self.assertEqual(a["sourceFactsSha256"],PIN)
        self.assertEqual(a["staticPhysicalCandidateSchema"],n4.SCHEMA)
        self.assertEqual(a["schema"],n5.SCHEMA)
        self.assertTrue(a["structuralRodEnergyAntisymmetry"])
        self.assertTrue(a["structuralIdentityOnlyNotIntegratedConservationProof"])
        self.assertEqual(a["nodeEquations"]["J_Upper"]["kind"],"ownerless_junction")
        self.assertEqual(a["nodeEquations"]["R"]["kind"],"body")
        self.assertEqual(a["nodeEquations"]["W"]["kind"],"fixed_boundary")
        for rod in a["rods"].values():
            self.assertGreater(F(rod["conductanceWPerKExactPhysicalInterval"][0]),0)
        for key in ("nativeExecuted","nativeQualified","runtimeReady",
                    "referenceAccuracyCertified","independentlyCertifiedReference",
                    "fullGrid77Plus8Plus5Certified","graphDynamicSolverImplemented",
                    "externalOwnerApprovalVerified"):
            self.assertIs(a[key],False,key)

    def test_unfamiliar_steady_serial_junction_physical_heat_supply(self):
        raw,pin=compact(steady_chain())
        a=n5.assemble(raw,expected_sha256=pin)
        self.assertEqual(set(a["rods"]),{"First","Second"})
        self.assertEqual(a["nodeEquations"]["Junction"]["portIncidence"],2)
        for rod in a["rods"].values():
            self.assertEqual(rod["conductanceWPerKExactPhysicalInterval"],["1","1"])
        values={"HotNode":"400","Junction":"350","ColdNode":"300"}
        t=n5.evaluate_trial(raw,expected_sha256=pin,temperatures=values)
        self.assertEqual(t["rodFlowFromToW"]["First"]["qFromToWExactPhysicalInterval"],["50","50"])
        self.assertEqual(t["rodFlowFromToW"]["Second"]["qFromToWExactPhysicalInterval"],["50","50"])
        self.assertEqual(t["nodeBalances"]["Junction"]["outgoingHeatFlowWInterval"],["0","0"])
        self.assertTrue(t["nodeBalances"]["Junction"]["zeroWithinResidualInterval"])
        self.assertEqual(t["nodeBalances"]["HotNode"]["boundaryHeatSupplyWInterval"],["50","50"])
        self.assertEqual(t["nodeBalances"]["ColdNode"]["boundaryHeatSupplyWInterval"],["-50","-50"])
        self.assertFalse(t["junctionEquilibriumProved"]) # zero for this TRIAL is not a general solver.
        self.assertFalse(t["timeTrajectoryComputed"])

    def test_trial_nonzero_algebraic_residual_remains_visible_not_repaired(self):
        raw,pin=compact(steady_chain())
        t=n5.evaluate_trial(raw,expected_sha256=pin,temperatures={
            "HotNode":"400","Junction":"340","ColdNode":"300"})
        self.assertEqual(t["rodFlowFromToW"]["First"]["qFromToWExactPhysicalInterval"],["60","60"])
        self.assertEqual(t["rodFlowFromToW"]["Second"]["qFromToWExactPhysicalInterval"],["40","40"])
        self.assertEqual(t["nodeBalances"]["Junction"]["outgoingHeatFlowWInterval"],["-20","-20"])
        self.assertFalse(t["nodeBalances"]["Junction"]["zeroWithinResidualInterval"])
        self.assertEqual(t["nodeBalances"]["Junction"]["interpretation"],
                         "algebraic_residual_not_automatically_solved")

    def test_rod_orientation_reversal_changes_flow_label_not_node_balance(self):
        original=steady_chain()
        raw,pin=compact(original)
        input_t={"HotNode":"400","Junction":"350","ColdNode":"300"}
        t=n5.evaluate_trial(raw,expected_sha256=pin,temperatures=input_t)
        other=deepcopy(original)
        other["rods"]["First"]["a"],other["rods"]["First"]["b"] = (
            other["rods"]["First"]["b"],other["rods"]["First"]["a"])
        raw2,pin2=compact(other)
        reversed_t=n5.evaluate_trial(raw2,expected_sha256=pin2,temperatures=input_t)
        self.assertEqual(reversed_t["rodFlowFromToW"]["First"]["qFromToWExactPhysicalInterval"],["-50","-50"])
        self.assertEqual(reversed_t["nodeBalances"],t["nodeBalances"])
        self.assertEqual(reversed_t["rodFlowFromToW"]["Second"],t["rodFlowFromToW"]["Second"])

    def test_two_parallel_rods_have_two_physical_ports_and_add_supply(self):
        source=steady_chain()
        source["rods"]["Second"]={"kind":"RodArea","a":"HotNode","b":"Junction",
                                  "k":10,"A":0.1,"L":1}
        # No return rod: node Junction is ownerless with two real ports, valid
        # for a trial that deliberately has a nonzero algebraic residual.
        source["nodes"]=["HotNode","Junction"]
        source["boundaries"].pop("Sink")
        # steady requires at least a maintained boundary and rods.
        raw,pin=compact(source)
        a=n5.assemble(raw,expected_sha256=pin)
        self.assertEqual(a["nodeEquations"]["Junction"]["portIncidence"],2)
        t=n5.evaluate_trial(raw,expected_sha256=pin,temperatures={"HotNode":"400","Junction":"350"})
        self.assertEqual(t["nodeBalances"]["HotNode"]["boundaryHeatSupplyWInterval"],["100","100"])
        self.assertEqual(t["nodeBalances"]["Junction"]["outgoingHeatFlowWInterval"],["-100","-100"])
        self.assertFalse(t["nodeBalances"]["Junction"]["zeroWithinResidualInterval"])

    def test_transient_mixed_graph_body_derivative_and_isolated_body(self):
        raw,pin=compact(transient_network())
        a=n5.assemble(raw,expected_sha256=pin)
        self.assertEqual((a["bodies"],a["boundaries"],a["junctions"]),(2,2,1))
        self.assertEqual(a["nodeEquations"]["BodyNode"]["capacityJPerKExact"],"300")
        self.assertEqual(a["nodeEquations"]["FloatingBody"]["portIncidence"],0)
        trial={"Warm":"370","Junction":"340","BodyNode":"320","Cool":"290",
               "FloatingBody":"315"}
        t=n5.evaluate_trial(raw,expected_sha256=pin,temperatures=trial)
        self.assertEqual(t["nodeBalances"]["FloatingBody"]["dTdtKPerSInterval"],["0","0"])
        # HotLeg: 30W into J; MidLeg: 20W from J to body; residual at J=-10W.
        self.assertEqual(t["nodeBalances"]["Junction"]["outgoingHeatFlowWInterval"],["-10","-10"])
        self.assertFalse(t["nodeBalances"]["Junction"]["zeroWithinResidualInterval"])
        circular=t["rodFlowFromToW"]["Round"]["qFromToWExactPhysicalInterval"]
        self.assertLess(F(circular[0]),F(circular[1])) # rigorous exact pi interval
        self.assertGreater(F(circular[0]),0)
        self.assertEqual(t["nodeBalances"]["BodyNode"]["interpretation"],
                         "instantaneous_trial_derivative_not_integrated_state")
        self.assertFalse(t["graphDynamicSolverImplemented"])

    def test_signed_circular_heat_flow_interval_negative_delta_is_ordered(self):
        source=transient_network()
        source["rods"]["Round"]["a"],source["rods"]["Round"]["b"] = (
            source["rods"]["Round"]["b"],source["rods"]["Round"]["a"])
        raw,pin=compact(source)
        t=n5.evaluate_trial(raw,expected_sha256=pin,temperatures={
            "Warm":"370","Junction":"340","BodyNode":"320","Cool":"290",
            "FloatingBody":"315"})
        values=list(map(F,t["rodFlowFromToW"]["Round"]["qFromToWExactPhysicalInterval"]))
        self.assertLess(values[0],values[1])
        self.assertLess(values[1],0)
        self.assertEqual(t["rodFlowFromToW"]["Round"]["deltaTKExact"],"-50")

    def test_trial_at_all_equal_temperatures_has_zero_flux_when_boundaries_equal(self):
        source=steady_chain()
        source["boundaries"]["Source"]["T"]=350
        source["boundaries"]["Sink"]["T"]=350
        raw,pin=compact(source)
        t=n5.evaluate_trial(raw,expected_sha256=pin,temperatures={
            "HotNode":"350","Junction":"350","ColdNode":"350"})
        self.assertTrue(all(x["qFromToWExactPhysicalInterval"]==["0","0"]
                            for x in t["rodFlowFromToW"].values()))
        self.assertTrue(all(x["outgoingHeatFlowWInterval"]==["0","0"]
                            for x in t["nodeBalances"].values()))

    def test_trial_requires_complete_exact_kelvin_values_and_fixed_boundaries(self):
        raw,pin=compact(steady_chain())
        good={"HotNode":"400","Junction":"350","ColdNode":"300"}
        cases=[
            {"Junction":"350","ColdNode":"300"}, # missing hot
            {**good,"Extra":"1"}, # unexpected
            {**good,"Junction":350.0}, # float not exact input
            {**good,"Junction":"NaN"},
            {**good,"Junction":"Infinity"},
            {**good,"Junction":"-20"},
            {**good,"Junction":"0"},
            {**good,"Junction":"1e999"},
            {**good,"Junction":"1e-9999"},
            {**good,"HotNode":"401"}, # fixed boundary mismatch
            {**good,"ColdNode":"299"},
        ]
        for case in cases:
            with self.subTest(case=str(case)):
                with self.assertRaises(n5.GraphRefusal):
                    n5.evaluate_trial(raw,expected_sha256=pin,temperatures=case)
        with self.assertRaises(n5.GraphRefusal):
            n5.evaluate_trial(raw,expected_sha256=pin,temperatures=[])
        with self.assertRaises(n5.GraphRefusal):
            n5.evaluate_trial(raw,expected_sha256=pin,temperatures=None)

    def test_hash_and_invalid_source_refusal_remains_original(self):
        raw,pin=compact(steady_chain())
        with self.assertRaises(n5.GraphRefusal):
            n5.assemble(raw+b"unreviewed",expected_sha256=pin)
        with self.assertRaises(n5.GraphRefusal):
            n5.assemble(raw,expected_sha256="0"*64)
        with self.assertRaises(n5.GraphRefusal):
            n5.assemble("invalid str",expected_sha256=pin)
        changed=steady_chain()
        changed["rods"]["Second"]["b"]="UnknownNode"
        raw2,pin2=compact(changed)
        with self.assertRaises(n5.GraphRefusal):
            n5.assemble(raw2,expected_sha256=pin2)

    def test_output_is_inspectable_not_certified_and_no_native_imports(self):
        path=Path(__file__).resolve().parents[1]/"thermal_graph.py"
        code=path.read_text()
        for token in ("import subprocess","import h1_native_batch",
                      "from h1.reference","def solve(", "scipy.integrate"):
            self.assertNotIn(token,code)
        raw,pin=compact(transient_network())
        r=n5.evaluate_trial(raw,expected_sha256=pin,temperatures={
            "Warm":"370","Junction":"340","BodyNode":"320","Cool":"290",
            "FloatingBody":"315"})
        for key in ("nativeExecuted","nativeQualified","runtimeReady",
                    "referenceAccuracyCertified","independentlyCertifiedReference",
                    "externalOwnerApprovalVerified","fullGrid77Plus8Plus5Certified",
                    "sourceInterpretationIndependentlyAuthenticated"):
            self.assertIs(r[key],False,key)
        self.assertEqual(r["schema"],n5.TRIAL_SCHEMA)
        self.assertEqual(r["stage"],"user_assumed_temperatures_no_time_solution")
        self.assertTrue(r["rodAntisymmetryByConstruction"])

if __name__=="__main__":
    unittest.main()
