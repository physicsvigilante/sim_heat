"""Offline exact Dirichlet junctions; neither dynamics nor native evidence."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from qualification.h1_n6 import exact_junctions as n6
from qualification.h1_n5 import thermal_graph as n5


def source(**parts):
    default={
        "schema":"sim_heat.reference/1",
        "id":"NewBridgeWithJunctions",
        "mode":"steady",
        "modelSha256":"1"*64,
        "studySha256":"2"*64,
        "provenance":"SYNTHETIC independent reviewer-inspired graph, not Modelica/native output",
        "analysis":{},
        "nodes":["Hot","Cold","J1","J2"],
        "bodies":{},
        "boundaries":{"Heater":{"node":"Hot","T":410},
                      "Cooler":{"node":"Cold","T":300}},
        "rods":{
            "R1":{"kind":"RodArea","a":"Hot","b":"J1","k":10,"L":1,"A":0.1},
            "R2":{"kind":"RodArea","a":"J1","b":"Cold","k":20,"L":1,"A":0.1},
            "R3":{"kind":"RodArea","a":"Hot","b":"J2","k":20,"L":1,"A":0.1},
            "R4":{"kind":"RodArea","a":"J2","b":"Cold","k":10,"L":1,"A":0.1},
            "R5":{"kind":"RodArea","a":"J1","b":"J2","k":30,"L":1,"A":0.1},
        }
    }
    default.update(parts)
    return default


def raw_and_pin(x):
    raw=(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
    return raw,sha256(raw).hexdigest()


def transient():
    x=source()
    x["id"]="TransientAreaGraphAndIsolatedBody"
    x["mode"]="transient"
    x["analysis"]={"startTime":0,"stopTime":2400,"intervals":2400,
                   "solver":"dassl","tolerance":1e-8}
    x["nodes"]=["Hot","Cold","J","B","I"]
    x["bodies"]={
        "Plate":{"node":"B","m":0.5,"c":600,"T_initial":325},
        "Isolated":{"node":"I","m":0.1,"c":500,"T_initial":315},
    }
    x["boundaries"]={"Heater":{"node":"Hot","T":370},
                     "Cooler":{"node":"Cold","T":290}}
    x["rods"]={
        "HotLeg":{"kind":"RodArea","a":"Hot","b":"J","k":10,"L":1,"A":0.1},
        "MidLeg":{"kind":"RodArea","a":"J","b":"B","k":10,"L":1,"A":0.1},
        "ColdLeg":{"kind":"RodArea","a":"B","b":"Cold","k":10,"L":1,"A":0.1},
    }
    return x


class ExactJunctionSnapshot(unittest.TestCase):
    def solve(self, data, temps=None):
        raw,pin=raw_and_pin(data)
        return n6.solve_snapshot(raw,expected_sha256=pin,
                                 body_node_temperatures={} if temps is None else temps)

    def test_independent_bridge_two_junction_exact_rational_solution(self):
        r=self.solve(source())
        self.assertEqual(r["status"],"EXACT_JUNCTION_EQUILIBRIUM_ONLY_NO_TRAJECTORY")
        self.assertEqual(r["rodDomain"],"RodArea_ONLY")
        self.assertEqual(r["junctionsSolved"],2)
        self.assertEqual(r["junctionSolvedTemperaturesKExact"],
                         {"J1":"3140/9","J2":"3250/9"})
        self.assertEqual({k:v["heatFlowWExact"] for k,v in r["rodHeatFlows"].items()},
                         {"R1":"550/9","R2":"880/9","R3":"880/9",
                          "R4":"550/9","R5":"-110/3"})
        self.assertEqual(r["boundarySupplyWExact"],
                         {"Hot":"1430/9","Cold":"-1430/9"})
        self.assertEqual(r["junctionResidualWExact"],{"J1":"0","J2":"0"})
        self.assertEqual(r["totalNodeOutwardHeatFlowWExact"],"0")
        self.assertEqual(set(r["instantaneousBodyRateKPerSExact"]),set())
        self.assertTrue(r["junctionsAlgebraicallySolved"])
        self.assertFalse(r["timeTrajectoryComputed"])
        self.assertFalse(r["initialValueProblemSolved"])
        self.assertTrue(r["bodyRatesConditionalOnUserAssumedBodyTemperatures"])

    def test_independent_bridge_input_guess_residual_not_silently_preserved(self):
        x=source()
        raw,pin=raw_and_pin(x)
        trial=n5.evaluate_trial(raw,expected_sha256=pin,temperatures={
            "Hot":"410","Cold":"300","J1":"350","J2":"360"})
        self.assertEqual(trial["nodeBalances"]["J1"]["outgoingHeatFlowWInterval"],["10","10"])
        self.assertEqual(trial["nodeBalances"]["J2"]["outgoingHeatFlowWInterval"],["-10","-10"])
        solved=n6.solve_snapshot(raw,expected_sha256=pin,body_node_temperatures={})
        self.assertNotEqual(solved["junctionSolvedTemperaturesKExact"]["J1"],"350")
        self.assertNotEqual(solved["junctionSolvedTemperaturesKExact"]["J2"],"360")
        self.assertTrue(all(F(v)==0 for v in solved["junctionResidualWExact"].values()))
        self.assertFalse(trial["junctionEquilibriumProved"])

    def test_transient_one_body_with_one_junction_and_isolated_body(self):
        r=self.solve(transient(),{"B":"320","I":"315"})
        self.assertEqual(r["junctionSolvedTemperaturesKExact"],{"J":"345"})
        self.assertEqual({k:v["heatFlowWExact"] for k,v in r["rodHeatFlows"].items()},
                         {"HotLeg":"25","MidLeg":"25","ColdLeg":"30"})
        self.assertEqual(r["instantaneousBodyRateKPerSExact"],
                         {"B":"-1/60","I":"0"})
        self.assertEqual(r["boundarySupplyWExact"],
                         {"Hot":"25","Cold":"-30"})
        self.assertEqual(r["outgoingNodeHeatFlowWExact"]["B"],"5")
        self.assertEqual(r["junctionResidualWExact"],{"J":"0"})
        self.assertEqual(r["knownBodyTemperatureKExact"],{"B":"320","I":"315"})
        self.assertFalse(r["generalH1DynamicsQualified"])
        self.assertTrue(r["bodyRatesConditionalOnUserAssumedBodyTemperatures"])

    def test_changed_body_temperature_recalculates_all_junctions_without_code_change(self):
        first=self.solve(transient(),{"B":"320","I":"315"})
        second=self.solve(transient(),{"B":"340","I":"315"})
        self.assertEqual(first["junctionSolvedTemperaturesKExact"]["J"],"345")
        self.assertEqual(second["junctionSolvedTemperaturesKExact"]["J"],"355")
        self.assertNotEqual(first["instantaneousBodyRateKPerSExact"]["B"],
                            second["instantaneousBodyRateKPerSExact"]["B"])
        self.assertEqual(first["instantaneousBodyRateKPerSExact"]["I"],"0")
        self.assertEqual(second["instantaneousBodyRateKPerSExact"]["I"],"0")

    def test_oriented_rod_reversal_changes_label_but_not_physical_node_balance(self):
        x=source()
        base=self.solve(x)
        y=deepcopy(x)
        y["rods"]["R5"]["a"],y["rods"]["R5"]["b"]=y["rods"]["R5"]["b"],y["rods"]["R5"]["a"]
        rev=self.solve(y)
        self.assertEqual(base["junctionSolvedTemperaturesKExact"],
                         rev["junctionSolvedTemperaturesKExact"])
        self.assertEqual(base["boundarySupplyWExact"],rev["boundarySupplyWExact"])
        self.assertEqual(base["outgoingNodeHeatFlowWExact"],
                         rev["outgoingNodeHeatFlowWExact"])
        self.assertEqual(base["rodHeatFlows"]["R5"]["heatFlowWExact"],"-110/3")
        self.assertEqual(rev["rodHeatFlows"]["R5"]["heatFlowWExact"],"110/3")
        self.assertEqual(rev["rodHeatFlows"]["R5"]["fromNode"],"J2")

    def test_parallel_rods_as_two_physical_ports_have_unique_zero_flux_junction(self):
        x=source()
        x.update(id="ParallelSourceAndJunction",nodes=["Hot","J"],
                 boundaries={"Source":{"node":"Hot","T":400}},
                 rods={"A":{"kind":"RodArea","a":"Hot","b":"J","k":10,"L":1,"A":0.1},
                       "B":{"kind":"RodArea","a":"Hot","b":"J","k":20,"L":1,"A":0.1}})
        r=self.solve(x)
        self.assertEqual(r["junctionSolvedTemperaturesKExact"],{"J":"400"})
        self.assertEqual(r["rodHeatFlows"]["A"]["heatFlowWExact"],"0")
        self.assertEqual(r["rodHeatFlows"]["B"]["heatFlowWExact"],"0")
        self.assertEqual(r["boundarySupplyWExact"],{"Hot":"0"})

    def test_chain_with_three_unknown_junctions_and_no_app_specific_constants(self):
        x=source()
        x.update(id="FourSeriesRods",nodes=["H","J1","J2","J3","C"],
                 boundaries={"Start":{"node":"H","T":400},"End":{"node":"C","T":300}})
        rods={}
        edges=[("H","J1"),("J1","J2"),("J2","J3"),("J3","C")]
        for i,(a,b) in enumerate(edges):
            rods["Path"+str(i)]={"kind":"RodArea","a":a,"b":b,
                                  "k":10,"L":1,"A":0.1}
        x["rods"]=rods
        r=self.solve(x)
        self.assertEqual(r["junctionSolvedTemperaturesKExact"],
                         {"J1":"375","J2":"350","J3":"325"})
        self.assertEqual(set(x["rods"]),set(r["rodHeatFlows"]))
        self.assertEqual(r["boundarySupplyWExact"],{"H":"25","C":"-25"})

    def test_zero_unknown_junctions_does_not_claim_time_solution(self):
        x=source()
        x.update(id="DirectTwoReservoirs",nodes=["H","C"],
                 boundaries={"Source":{"node":"H","T":400},
                             "Sink":{"node":"C","T":300}},
                 rods={"Leg":{"kind":"RodArea","a":"H","b":"C",
                              "k":20,"L":1,"A":0.1}})
        r=self.solve(x)
        self.assertEqual(r["junctionsSolved"],0)
        self.assertEqual(r["junctionSolvedTemperaturesKExact"],{})
        self.assertEqual(r["rodHeatFlows"]["Leg"]["heatFlowWExact"],"200")
        self.assertEqual(r["status"],"EXACT_JUNCTION_EQUILIBRIUM_ONLY_NO_TRAJECTORY")
        self.assertFalse(r["timeTrajectoryComputed"])

    def test_circular_conductor_refuses_even_when_junctions_are_simple(self):
        x=source()
        x["rods"]["R1"]={"kind":"RodCircular","a":"Hot","b":"J1",
                          "k":100,"d":0.02,"L":1}
        raw,pin=raw_and_pin(x)
        with self.assertRaisesRegex(n6.JunctionRefusal,"circular conductor"):
            n6.solve_snapshot(raw,expected_sha256=pin,body_node_temperatures={})
        # The inherited N5 trial remains supported for that circular source.
        trial=n5.evaluate_trial(raw,expected_sha256=pin,
                                temperatures={"Hot":"410","Cold":"300","J1":"350","J2":"360"})
        self.assertTrue(trial["rodFlowFromToW"]["R1"]["qFromToWExactPhysicalInterval"])
        self.assertFalse(trial["timeTrajectoryComputed"])

    def test_trial_body_temperature_requires_complete_ascii_exact_inputs(self):
        x=transient()
        invalid=[
            {"I":"315"}, # missing a required body
            {"B":"320","I":"315","Spurious":"310"},
            {"B":320,"I":"315"},
            {"B":" 320 ","I":"315"},
            {"B":"3_20","I":"315"},
            {"B":"٣٢٠","I":"315"},  # Arabic-Indic digits
            {"B":"NaN","I":"315"},
            {"B":"Infinity","I":"315"},
            {"B":"0","I":"315"},
            {"B":"-320","I":"315"},
            {"B":"1e999","I":"315"},
            {"B":"1e-9999","I":"315"},
        ]
        for case in invalid:
            with self.subTest(values=case):
                with self.assertRaises(n6.JunctionRefusal):
                    self.solve(x,case)
        accepted=self.solve(x,{"B":"3.20e2","I":"+315.0"})
        self.assertEqual(accepted["knownBodyTemperatureKExact"],{"B":"320","I":"315"})

    def test_original_model_study_and_raw_source_hashes_cannot_be_invented(self):
        x=source()
        raw,pin=raw_and_pin(x)
        with self.assertRaises(n6.JunctionRefusal):
            n6.solve_snapshot(raw+b" ",expected_sha256=pin,body_node_temperatures={})
        with self.assertRaises(n6.JunctionRefusal):
            n6.solve_snapshot(raw,expected_sha256="f"*64,body_node_temperatures={})
        bad=deepcopy(x)
        bad["rods"]["R1"]["b"]="MissingJunction"
        raw2,pin2=raw_and_pin(bad)
        with self.assertRaises(n6.JunctionRefusal):
            n6.solve_snapshot(raw2,expected_sha256=pin2,body_node_temperatures={})

    def test_singular_or_unbounded_exact_linear_system_refuses_not_regularizes(self):
        with self.assertRaisesRegex(n6.JunctionRefusal,"not positive definite"):
            n6._solve_positive_dirichlet_laplacian([[F(1),F(1)],
                                                    [F(1),F(1)]],[F(1),F(2)])
        with self.assertRaisesRegex(n6.JunctionRefusal,"not positive definite"):
            n6._solve_positive_dirichlet_laplacian([[F(0)]],[F(1)])
        with patch.object(n6,"MAX_JUNCTIONS",1):
            with self.assertRaisesRegex(n6.JunctionRefusal,"bounded unknown"):
                self.solve(source())
        with patch.object(n6,"MAX_FRACTION_BITS",32):
            with self.assertRaisesRegex(n6.JunctionRefusal,"bounded proof"):
                n6.bounded(F(1,10**20))

    def test_new_labels_are_not_native_reference_or_dynamic_solutions(self):
        r=self.solve(source())
        for key in ("timeTrajectoryComputed","initialValueProblemSolved",
                    "allGridAccuracyCertified","referenceBundleWritten",
                    "referenceAccuracyCertified","independentlyCertifiedReference",
                    "fullGrid77Plus8Plus5Certified","runtimeReady","nativeExecuted",
                    "nativeQualified","sourceInterpretationIndependentlyAuthenticated",
                    "externalOwnerApprovalVerified","generalH1DynamicsQualified"):
            self.assertIs(r[key],False,key)
        self.assertTrue(r["junctionsAlgebraicallySolved"])
        self.assertTrue(r["bodyRatesConditionalOnUserAssumedBodyTemperatures"])
        source_text=(Path(__file__).resolve().parents[1]/"exact_junctions.py").read_text()
        for forbidden in ("import subprocess","import scipy","import OpenModelica",
                          "h1_native_batch","reference.prepare("):
            self.assertNotIn(forbidden,source_text)


if __name__ == "__main__":
    unittest.main()
