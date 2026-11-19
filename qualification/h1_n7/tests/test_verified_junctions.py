"""Offline source-exact rational enclosure and fail-closed junction tests."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from qualification.h1_n4 import static_physical as n4
from qualification.h1_n5 import thermal_graph as n5
from qualification.h1_n6 import exact_junctions as n6
from qualification.h1_n7 import verified_junctions as n7

ORIGINAL=Path(__file__).resolve().parents[2]/"h1_n1/reference-facts.json"
ORIGINAL_PIN="39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf"

def raw_and_pin(facts):
    raw=(json.dumps(facts,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
    return raw,sha256(raw).hexdigest()

def single_circular():
    # k*pi*d^2/(4L) = 400*pi*(0.1)^2/4 = pi W/K.
    return {
        "schema":"sim_heat.reference/1","id":"CircularSerialOneJunction",
        "mode":"steady","modelSha256":"a"*64,"studySha256":"b"*64,
        "analysis":{},"provenance":"SYNTHETIC precise Pi junction case, not native",
        "nodes":["H","J","C"],"bodies":{},
        "boundaries":{"Warm":{"node":"H","T":400},
                      "Cold":{"node":"C","T":300}},
        "rods":{
            "Round":{"kind":"RodCircular","a":"H","b":"J",
                     "k":400,"d":0.1,"L":1},
            "Square":{"kind":"RodArea","a":"J","b":"C",
                      "k":10,"A":0.1,"L":1},
        },
    }

def bridge_area():
    return {
        "schema":"sim_heat.reference/1","id":"IndependentAreaBridge",
        "mode":"steady","modelSha256":"c"*64,"studySha256":"d"*64,
        "analysis":{},"provenance":"SYNTHETIC exact area bridge",
        "nodes":["Hot","Cold","J1","J2"],"bodies":{},
        "boundaries":{"Warm":{"node":"Hot","T":410},
                      "Cool":{"node":"Cold","T":300}},
        "rods":{
            "E1":{"kind":"RodArea","a":"Hot","b":"J1","k":10,"L":1,"A":0.1},
            "E2":{"kind":"RodArea","a":"J1","b":"Cold","k":20,"L":1,"A":0.1},
            "E3":{"kind":"RodArea","a":"Hot","b":"J2","k":20,"L":1,"A":0.1},
            "E4":{"kind":"RodArea","a":"J2","b":"Cold","k":10,"L":1,"A":0.1},
            "E5":{"kind":"RodArea","a":"J1","b":"J2","k":30,"L":1,"A":0.1},
        },
    }

def double_circular():
    spec=single_circular()
    spec["id"]="TwoUnknownCircularBridge"
    spec["nodes"]=["H","J1","J2","C"]
    spec["rods"]={
        "Round1":{"kind":"RodCircular","a":"H","b":"J1",
                  "k":400,"d":0.1,"L":1},
        "Middle":{"kind":"RodArea","a":"J1","b":"J2",
                  "k":10,"A":0.1,"L":1},
        "Round2":{"kind":"RodCircular","a":"J2","b":"C",
                  "k":200,"d":0.1,"L":1},
    }
    return spec

def pair(values):
    return tuple(F(s) for s in values)


class VerifiedCircularJunctions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_original=ORIGINAL.read_bytes()
        assert sha256(cls.raw_original).hexdigest()==ORIGINAL_PIN

    def run_case(self,facts,body=None):
        raw,pin=raw_and_pin(facts)
        return n7.solve_snapshot(raw,expected_sha256=pin,
                                 body_node_temperatures={} if body is None else body)

    def test_original_t1_circular_network_now_enclosed_but_not_dynamics(self):
        r=n7.solve_snapshot(self.raw_original,expected_sha256=ORIGINAL_PIN,
                            body_node_temperatures={"R":"337","B":"303","P":"318"})
        self.assertTrue(r["hasCircularConductor"])
        self.assertEqual(r["junctionsEnclosed"],2)
        self.assertEqual(set(r["junctionTemperatureEnclosuresK"]),{"J_Upper","J_Lower"})
        self.assertTrue(r["proof"]["barrierCertified"])
        self.assertFalse(r["proof"]["nominalCentresArePhysicalAnswers"])
        for name,values in r["junctionTemperatureEnclosuresK"].items():
            lo,hi=pair(values)
            self.assertLessEqual(hi-lo,F(1,10**6),name)
            self.assertGreaterEqual(lo,F(289))
            self.assertLessEqual(hi,F(367))
            self.assertTrue(r["nodeBalanceEnclosures"][name][
                            "junctionResidualExactlyZeroByVerifiedEquation"])
            residual=pair(r["nodeBalanceEnclosures"][name]["outwardHeatFlowWIndependentIntervalSum"])
            self.assertLessEqual(residual[0],0)
            self.assertGreaterEqual(residual[1],0)
        self.assertEqual(r["sourceFactsSha256"],ORIGINAL_PIN)
        self.assertTrue(r["physicalPiNotReplacedByNumericalMidpoint"])
        self.assertFalse(r["timeTrajectoryComputed"])
        self.assertFalse(r["fullGrid77Plus8Plus5Certified"])

    def test_simple_pi_one_junction_rigorous_analytical_enclosure(self):
        r=self.run_case(single_circular())
        self.assertEqual(r["junctionsEnclosed"],1)
        low,high=pair(r["junctionTemperatureEnclosuresK"]["J"])
        pi_lo,pi_hi=n4.pi_rational_enclosure()
        def exact_j(pi):
            return (400*pi+300)/(pi+1)
        # Exact endpoint bounds are monotone in positive Pi; this is a
        # rigorous independent enclosure test, not a float π approximation.
        self.assertLessEqual(low,exact_j(pi_lo))
        self.assertGreaterEqual(high,exact_j(pi_hi))
        self.assertLess(high-low,F(1,10**6))
        self.assertGreater(high,low)
        self.assertTrue(r["proof"]["trueJunctionEnclosedForAllAdmissibleConductances"])
        self.assertEqual(r["rodHeatFlows"]["Round"]["conductanceWPerKExactPhysicalInterval"],
                         [str(pi_lo),str(pi_hi)])
        self.assertTrue(r["junctionEquilibriumExistsUniqueWithinEnclosures"])
        self.assertFalse(r["referenceAccuracyCertified"])

    def test_reversed_circular_rod_preserves_junction_enclosures_and_signs(self):
        original=single_circular()
        first=self.run_case(original)
        changed=deepcopy(original)
        changed["rods"]["Round"]["a"],changed["rods"]["Round"]["b"]=(
            changed["rods"]["Round"]["b"],changed["rods"]["Round"]["a"])
        second=self.run_case(changed)
        self.assertEqual(first["junctionTemperatureEnclosuresK"],
                         second["junctionTemperatureEnclosuresK"])
        f1=pair(first["rodHeatFlows"]["Round"]["heatFlowWExactPhysicalEnclosure"])
        f2=pair(second["rodHeatFlows"]["Round"]["heatFlowWExactPhysicalEnclosure"])
        self.assertEqual(f1,(-f2[1],-f2[0]))
        self.assertGreater(f1[0],0)
        self.assertLess(f2[1],0)

    def test_area_only_matches_reviewed_n6_point_solution_without_loss(self):
        facts=bridge_area()
        raw,pin=raw_and_pin(facts)
        exact=n6.solve_snapshot(raw,expected_sha256=pin,body_node_temperatures={})
        enclosed=n7.solve_snapshot(raw,expected_sha256=pin,body_node_temperatures={})
        self.assertFalse(enclosed["hasCircularConductor"])
        self.assertEqual(enclosed["junctionsEnclosed"],2)
        for node,temp in exact["junctionSolvedTemperaturesKExact"].items():
            self.assertEqual(enclosed["junctionTemperatureEnclosuresK"][node],[temp,temp])
        self.assertTrue(all(z["residualAbsoluteBoundW"]=="0"
                            for z in enclosed["proof"]["rows"]))
        self.assertEqual(enclosed["rodHeatFlows"]["E5"]["heatFlowWExactPhysicalEnclosure"],
                         ["-110/3","-110/3"])
        self.assertTrue(enclosed["proof"]["barrierCertified"])

    def test_two_unknown_circular_bridge_enclosed_and_port_conserved(self):
        r=self.run_case(double_circular())
        self.assertEqual(r["junctionsEnclosed"],2)
        self.assertEqual(set(r["junctionTemperatureEnclosuresK"]),{"J1","J2"})
        self.assertTrue(r["hasCircularConductor"])
        for name in ("J1","J2"):
            lo,hi=pair(r["junctionTemperatureEnclosuresK"][name])
            self.assertGreaterEqual(lo,F(300))
            self.assertLessEqual(hi,F(400))
            self.assertLess(hi-lo,F(1,10**6))
            self.assertTrue(r["nodeBalanceEnclosures"][name]["junctionResidualExactlyZeroByVerifiedEquation"])
        self.assertTrue(r["structuralRodEnergyAntisymmetry"])
        self.assertFalse(r["initialValueProblemSolved"])

    def test_no_junction_all_known_circular_flux_stays_interval(self):
        facts=single_circular()
        facts["id"]="CircularDirectTwoBoundaries"
        facts["nodes"]=["H","C"]
        facts["boundaries"]={"Warm":{"node":"H","T":400},
                             "Cold":{"node":"C","T":300}}
        facts["rods"]={"Round":{"kind":"RodCircular","a":"H","b":"C",
                                 "k":400,"d":0.1,"L":1}}
        r=self.run_case(facts)
        self.assertEqual(r["junctionsEnclosed"],0)
        self.assertEqual(r["proof"]["algorithm"],"NO_UNKNOWN_JUNCTIONS")
        self.assertEqual(r["junctionTemperatureEnclosuresK"],{})
        pi_lo,pi_hi=n4.pi_rational_enclosure()
        self.assertEqual(r["rodHeatFlows"]["Round"]["heatFlowWExactPhysicalEnclosure"],
                         [str(100*pi_lo),str(100*pi_hi)])
        self.assertFalse(r["timeTrajectoryComputed"])

    def test_equal_temperatures_are_exact_singletons_even_with_circular_rods(self):
        facts=double_circular()
        facts["boundaries"]["Warm"]["T"]=350
        facts["boundaries"]["Cold"]["T"]=350
        r=self.run_case(facts)
        self.assertEqual(r["junctionTemperatureEnclosuresK"],
                         {"J1":["350","350"],"J2":["350","350"]})
        self.assertTrue(all(z["heatFlowWExactPhysicalEnclosure"]==["0","0"]
                            for z in r["rodHeatFlows"].values()))
        self.assertTrue(all(z["residualAbsoluteBoundW"]=="0" for z in r["proof"]["rows"]))

    def test_trial_transient_body_rate_is_only_conditional_and_enclosed(self):
        spec=single_circular()
        spec["id"]="TransientCircularMass"
        spec["mode"]="transient"
        spec["analysis"]={"startTime":0,"stopTime":2400,"intervals":2400,
                          "solver":"dassl","tolerance":1e-8}
        spec["nodes"].append("BodyNode")
        spec["bodies"]={"Mass":{"node":"BodyNode","m":0.5,"c":500,
                                "T_initial":315}}
        spec["rods"]["BodyLeg"]={"kind":"RodArea","a":"J","b":"BodyNode",
                                 "k":10,"A":0.1,"L":1}
        r=self.run_case(spec,{"BodyNode":"320"})
        self.assertEqual(r["bodyTemperatureAssumptionsKExact"],{"BodyNode":"320"})
        body=r["nodeBalanceEnclosures"]["BodyNode"]
        lo,hi=pair(body["conditionalDTdtKPerSInterval"])
        self.assertLessEqual(lo,hi)
        self.assertTrue(r["bodyRatesConditionalOnUserAssumedTemperatures"])
        self.assertFalse(r["timeTrajectoryComputed"])
        self.assertFalse(r["fullSystemAlgebraicAndDynamicStateSolved"])

    def test_rational_comparison_refuses_unverified_wide_interval(self):
        known={"Hot":F(400),"Cold":F(300)}
        # With 10:1 uncertain G, the enclosure is too wide to teach as
        # a sharply resolved instant. Never accept a midpoint as exact.
        edges=[("Wide","Hot","J",F(1),F(10)),
               ("Link","J","Cold",F(1),F(1))]
        with self.assertRaisesRegex(n7.IntervalJunctionRefusal,
                                    "barrier|precision"):
            n7._enclosure_from_verified_barrier(["J"],known,edges)

    def test_fail_closed_when_midpoint_solver_is_forged_or_singular(self):
        with patch.object(n6,"_solve_positive_dirichlet_laplacian",return_value=[F(0)]):
            with self.assertRaisesRegex(n7.IntervalJunctionRefusal,"nominal rational centre"):
                self.run_case(single_circular())
        with patch.object(n7,"MAX_JUNCTIONS",0):
            with self.assertRaisesRegex(n7.IntervalJunctionRefusal,"unsupported unknown"):
                self.run_case(single_circular())
        with self.assertRaises(n7.IntervalJunctionRefusal):
            n7._enclosure_from_verified_barrier(["J"],{},[("Bad","J","Free",F(1),F(1))])

    def test_enclosure_uncertainty_is_not_mislabeled_as_global_conservation_proof(self):
        r=self.run_case(single_circular())
        row=r["nodeBalanceEnclosures"]["J"]
        interval=pair(row["outwardHeatFlowWIndependentIntervalSum"])
        self.assertLess(interval[0],0)
        self.assertGreater(interval[1],0)
        self.assertTrue(row["junctionResidualExactlyZeroByVerifiedEquation"])
        self.assertIn("correlated",row["note"])
        self.assertTrue(r["structuralRodEnergyAntisymmetry"])
        self.assertFalse(r["allGrid77Plus8Plus5Certified"])

    def test_source_identity_and_ascii_temperature_failures(self):
        raw,pin=raw_and_pin(single_circular())
        with self.assertRaises(n7.IntervalJunctionRefusal):
            n7.solve_snapshot(raw+b" ",expected_sha256=pin,body_node_temperatures={})
        with self.assertRaises(n7.IntervalJunctionRefusal):
            n7.solve_snapshot(raw,expected_sha256="0"*64,body_node_temperatures={})
        with self.assertRaises(n7.IntervalJunctionRefusal):
            n7.solve_snapshot(raw,expected_sha256=pin,body_node_temperatures={"Unused":"300"})
        facts=single_circular()
        facts["rods"]["Round"]["d"]=-0.01
        raw2,pin2=raw_and_pin(facts)
        with self.assertRaises(n7.IntervalJunctionRefusal):
            n7.solve_snapshot(raw2,expected_sha256=pin2,body_node_temperatures={})
        from qualification.h1_n6.tests.test_exact_junctions import transient as n6_transient
        transient=n6_transient()
        raw3,pin3=raw_and_pin(transient)
        for bad in ({"B":" 320 ","I":"315"},{"B":"٣٢٠","I":"315"},
                    {"B":"320","I":"3_15"},{"B":320,"I":"315"},
                    {"B":"NaN","I":"315"}):
            with self.subTest(bad=bad):
                with self.assertRaises(n7.IntervalJunctionRefusal):
                    n7.solve_snapshot(raw3,expected_sha256=pin3,
                                      body_node_temperatures=bad)

    def test_flags_refuse_native_or_full_trajectory_authority(self):
        r=self.run_case(single_circular())
        self.assertEqual(r["status"],"VERIFIED_INTERVAL_ALGEBRAIC_JUNCTIONS_ONLY_NO_TRAJECTORY")
        for key in ("sourceInterpretationIndependentlyAuthenticated",
                    "ownerApprovedExpectedReferenceManifestVerified",
                    "independentlyCertifiedReference","referenceAccuracyCertified",
                    "referenceBundleWritten","allGrid77Plus8Plus5Certified",
                    "nativeExecuted","nativeQualified","runtimeReady",
                    "timeTrajectoryComputed","initialValueProblemSolved",
                    "generalH1DynamicsQualified",
                    "fullSystemAlgebraicAndDynamicStateSolved"):
            self.assertIs(r[key],False,key)
        self.assertFalse(r["proof"]["proofIsIndependentNativeCertificate"])
        self.assertFalse(r["proof"]["nominalCentresArePhysicalAnswers"])

if __name__=="__main__":
    unittest.main()
