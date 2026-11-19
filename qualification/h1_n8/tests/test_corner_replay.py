"""Independent source-level corner checks of reviewed N7 interval proof, OFFLINE."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
import json
from pathlib import Path
import unittest

from qualification.h1_n7 import verified_junctions as n7
from qualification.h1_n8 import corner_replay as n8

T1=Path(__file__).resolve().parents[2]/"h1_n1/reference-facts.json"
T1_SHA="39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf"

def four_junction_facts():
    """Fresh developer fixture precisely instantiating Chat B PR68 novel law graph.

    Rod ArcX_J4 has k=800, d=0.1, L=3, so G=2*Pi/3 exactly.
    NEVER use an unrepresentable 800/3 float as source conductivity.
    """
    return {
        "schema":"sim_heat.reference/1",
        "id":"ReviewerFourJunctionCircularAndTwoIslands",
        "mode":"transient",
        "modelSha256":"1"*64,"studySha256":"2"*64,
        "analysis":{"startTime":0,"stopTime":2400,"intervals":2400,
                    "solver":"dassl","tolerance":1e-8},
        "provenance":"SYNTHETIC independently proposed multi-junction checking case, never native",
        "nodes":["H","C","M","X","Y","I","J1","J2","J3","J4"],
        "bodies":{
            "Mass":{"node":"M","m":0.75,"c":480,"T_initial":350},
            "WarmBody":{"node":"X","m":0.5,"c":500,"T_initial":375},
            "CoolBody":{"node":"Y","m":0.6,"c":400,"T_initial":310},
            "IsolatedBody":{"node":"I","m":0.25,"c":400,"T_initial":315},
        },
        "boundaries":{
            "Heater":{"node":"H","T":420},
            "Cooler":{"node":"C","T":275},
        },
        "rods":{
            "ArcH_J1":{"kind":"RodCircular","a":"H","b":"J1",
                       "k":400,"d":0.1,"L":1},
            "ParallelJ1_H":{"kind":"RodArea","a":"J1","b":"H",
                            "k":10,"A":0.1,"L":1},
            "ArcJ2_J1":{"kind":"RodCircular","a":"J2","b":"J1",
                        "k":300,"d":0.1,"L":1},
            "LinkJ2_J3":{"kind":"RodArea","a":"J2","b":"J3",
                         "k":10,"A":0.2,"L":1},
            "LoopJ3_J1":{"kind":"RodArea","a":"J3","b":"J1",
                         "k":10,"A":0.05,"L":1},
            "ArcC_J2":{"kind":"RodCircular","a":"C","b":"J2",
                       "k":200,"d":0.1,"L":1},
            "ToMass":{"kind":"RodArea","a":"J3","b":"M",
                      "k":10,"A":0.4,"L":1},
            "ColdJ1":{"kind":"RodArea","a":"C","b":"J1",
                      "k":10,"A":0.08,"L":1},
            "MassJ2":{"kind":"RodArea","a":"M","b":"J2",
                      "k":10,"A":0.02,"L":1},
            "ArcX_J4":{"kind":"RodCircular","a":"X","b":"J4",
                       "k":800,"d":0.1,"L":3},
            "J4_Y":{"kind":"RodArea","a":"J4","b":"Y",
                    "k":10,"A":0.14,"L":1},
        }
    }

def area_chain():
    return {
        "schema":"sim_heat.reference/1","id":"CrossCheckAreaChain",
        "mode":"steady","modelSha256":"3"*64,"studySha256":"4"*64,
        "analysis":{},"provenance":"SYNTHETIC exact rational source test only",
        "nodes":["Hot","J","Cold"],"bodies":{},
        "boundaries":{"HotSource":{"node":"Hot","T":410},
                      "ColdSource":{"node":"Cold","T":300}},
        "rods":{"A":{"kind":"RodArea","a":"Hot","b":"J",
                    "k":10,"A":0.1,"L":1},
                "B":{"kind":"RodArea","a":"J","b":"Cold",
                    "k":20,"A":0.1,"L":1}},
    }

def serialize(spec):
    raw=(json.dumps(spec,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
    return raw,sha256(raw).hexdigest()

class IndependentCornerReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw,cls.pin=serialize(four_junction_facts())
        cls.assumptions={"M":"350","X":"375","Y":"310","I":"315"}
        cls.report=n7.solve_snapshot(cls.raw,expected_sha256=cls.pin,
                                     body_node_temperatures=cls.assumptions)

    def cross(self,reported=None,raw=None,pin=None,assumptions=None):
        return n8.replay(self.raw if raw is None else raw,
                         expected_sha256=self.pin if pin is None else pin,
                         body_node_temperatures=(
                            self.assumptions if assumptions is None else assumptions),
                         reported=self.report if reported is None else reported)

    def test_independent_four_junction_sixteen_corners_full_source(self):
        r=self.cross()
        self.assertEqual(r["status"],
                         "OFFLINE_INDEPENDENT_SOURCE_CORNER_AND_SIGNED_BARRIER_CROSSCHECK_PASS")
        self.assertEqual(r["endpointCornersChecked"],16)
        self.assertEqual(r["junctionsCompared"],4)
        self.assertEqual(r["uncertainCircularRods"],4)
        self.assertEqual(len(r["cornerReadouts"]),16)
        self.assertTrue(r["universalRowComparisonVerified"])
        self.assertTrue(r["cornerChecksAloneNotUniversalProof"])
        self.assertTrue(r["universalEnclosureFollowsPositiveDirichletInverse"])
        self.assertGreater(r["negativeUnknownGradientContributionsChecked"],0)
        self.assertEqual(self.report["junctionsEnclosed"],4)
        self.assertEqual(len(self.report["rodHeatFlows"]),11)
        self.assertTrue(self.report["hasCircularConductor"])
        self.assertFalse(self.report["timeTrajectoryComputed"])
        self.assertFalse(r["unfamiliarCompositionIndependentlyQualified"])

    def test_four_circular_source_coefficients_are_exact_nonfloats(self):
        lo,hi=n8.pi_bounds()
        self.assertLess(hi-lo,F(1,10**50))
        self.assertEqual((lo,hi),tuple(n8.pi_bounds()))
        _,_,junctions,edges,circles=n8._source_graph(
            self.raw,self.pin,self.assumptions)
        self.assertEqual(set(junctions),{"J1","J2","J3","J4"})
        self.assertEqual(set(circles),
                         {"ArcH_J1","ArcJ2_J1","ArcC_J2","ArcX_J4"})
        byname={x[0]:x for x in edges}
        self.assertEqual(byname["ArcH_J1"][3:],(lo,hi))
        self.assertEqual(byname["ArcJ2_J1"][3:],(F(3,4)*lo,F(3,4)*hi))
        self.assertEqual(byname["ArcC_J2"][3:],(F(1,2)*lo,F(1,2)*hi))
        self.assertEqual(byname["ArcX_J4"][3:],(F(2,3)*lo,F(2,3)*hi))
        self.assertEqual(byname["LoopJ3_J1"][3:],(F(1,2),F(1,2)))
        self.assertEqual(byname["J4_Y"][3:],(F(7,5),F(7,5)))

    def test_review_centre_ranges_and_separate_island_and_isolated_body(self):
        self.cross()
        approx={"J1":376.640520647,"J2":340.757515497,
                "J3":349.205429433,"J4":348.958296834}
        for name,value in approx.items():
            lo,hi=map(F,self.report["junctionTemperatureEnclosuresK"][name])
            self.assertLess(float(lo),value+1e-7)
            self.assertGreater(float(hi),value-1e-7)
            self.assertLess(hi-lo,F(1,10**6))
        # Separate island J4 has only known X=375, Y=310 anchors.
        j4=tuple(map(F,self.report["junctionTemperatureEnclosuresK"]["J4"]))
        self.assertTrue(F(310)<j4[0]<j4[1]<F(375))
        self.assertEqual(self.report["nodeBalanceEnclosures"]["I"]["conditionalDTdtKPerSInterval"],
                         ["0","0"])
        self.assertEqual(self.report["junctionsEnclosed"],4)

    def test_actual_N7_output_refuses_forged_junction_and_barrier_bounds(self):
        fake=deepcopy(self.report)
        centre=next(row["nominalProofCentreK"] for row in fake["proof"]["rows"]
                    if row["junctionNode"]=="J1")
        fake["junctionTemperatureEnclosuresK"]["J1"]=[centre,centre]
        with self.assertRaises(n8.CornerRefusal):
            self.cross(reported=fake)
        wrong=deepcopy(self.report)
        row=next(row for row in wrong["proof"]["rows"] if row["junctionNode"]=="J2")
        row["lowerBoundOnAllPhysicalLaplacianBarrierW"]="999999"
        with self.assertRaisesRegex(n8.CornerRefusal,"barrier|lower|signed"):
            self.cross(reported=wrong)
        wrong=deepcopy(self.report)
        row=next(row for row in wrong["proof"]["rows"] if row["junctionNode"]=="J1")
        self.assertGreater(F(row["residualAbsoluteBoundW"]),0)
        row["residualAbsoluteBoundW"]="0"
        with self.assertRaisesRegex(n8.CornerRefusal,"source-residual"):
            self.cross(reported=wrong)

    def test_crosschecker_rejects_narrowing_the_universal_interval(self):
        fake=deepcopy(self.report)
        row=next(r for r in fake["proof"]["rows"] if r["junctionNode"]=="J1")
        centre=F(row["nominalProofCentreK"])
        barrier=F(row["verifiedBarrierRadiusK"])
        self.assertGreater(barrier,0)
        published=tuple(map(F,fake["junctionTemperatureEnclosuresK"]["J1"]))
        # Deliberately remove part of the rigorously proved left envelope.
        fake["junctionTemperatureEnclosuresK"]["J1"]=[
            str((published[0]+centre)/2), str(published[1])]
        with self.assertRaisesRegex(n8.CornerRefusal,"universal certified envelope"):
            self.cross(reported=fake)

    def test_claimed_midpoint_centre_must_solve_independently_rebuilt_source_matrix(self):
        fake=deepcopy(self.report)
        row=next(r for r in fake["proof"]["rows"] if r["junctionNode"]=="J3")
        row["nominalProofCentreK"]=str(F(row["nominalProofCentreK"])+F(1,10**80))
        with self.assertRaisesRegex(n8.CornerRefusal,"midpoint proof centre"):
            self.cross(reported=fake)

    def test_n8_f01_all_false_native_and_proof_authority_fields_are_enforced(self):
        """Old N8 falsely PASSED an untrusted N7 report with omitted claims."""
        blocked=(
            "sourceInterpretationIndependentlyAuthenticated",
            "ownerApprovedExpectedReferenceManifestVerified",
            "independentlyCertifiedReference","referenceAccuracyCertified",
            "referenceBundleWritten","allGrid77Plus8Plus5Certified",
            "nativeExecuted","nativeQualified","runtimeReady",
            "timeTrajectoryComputed","initialValueProblemSolved",
            "generalH1DynamicsQualified","fullSystemAlgebraicAndDynamicStateSolved",
        )
        for name in blocked:
            for mode in ("promote","remove"):
                with self.subTest(field=name,mode=mode):
                    fake=deepcopy(self.report)
                    if mode=="promote":
                        fake[name]=True
                    else:
                        fake.pop(name)
                    with self.assertRaises(n8.CornerRefusal):
                        self.cross(reported=fake)
        for name in ("proofIsIndependentNativeCertificate",
                     "nominalCentresArePhysicalAnswers"):
            for mode in ("promote","remove"):
                with self.subTest(proof=name,mode=mode):
                    fake=deepcopy(self.report)
                    if mode=="promote":
                        fake["proof"][name]=True
                    else:
                        fake["proof"].pop(name)
                    with self.assertRaises(n8.CornerRefusal):
                        self.cross(reported=fake)
        attack=deepcopy(self.report)
        attack["independentlyCertifiedReference"]=True
        attack["allGrid77Plus8Plus5Certified"]=True
        attack["proof"]["proofIsIndependentNativeCertificate"]=True
        with self.assertRaises(n8.CornerRefusal):
            self.cross(reported=attack)

    def test_n8_f02_untrusted_rod_direction_G_and_sign_labels_must_match_source(self):
        """Numerically valid q bounds do not authenticate the rod's direction."""
        original=self.report["rodHeatFlows"]["ArcX_J4"]
        self.assertEqual((original["fromNode"],original["toNode"]),("X","J4"))
        attacks=(
            ("from",lambda r:r.__setitem__("fromNode","J4")),
            ("to",lambda r:r.__setitem__("toNode","X")),
            ("both",lambda r:r.update(fromNode="J4",toNode="X")),
            ("positive",lambda r:r.__setitem__("positiveFromTo",False)),
            ("positive_type",lambda r:r.__setitem__("positiveFromTo",1)),
            ("orientation",lambda r:r.__setitem__("orientation","q_to_from=G*(T_from-T_to)")),
            ("G_zero",lambda r:r.__setitem__("conductanceWPerKExactPhysicalInterval",["0","0"])),
            ("G_swapped",lambda r:r.__setitem__(
                "conductanceWPerKExactPhysicalInterval",
                list(reversed(r["conductanceWPerKExactPhysicalInterval"])))),
            ("G_drift",lambda r:r.__setitem__(
                "conductanceWPerKExactPhysicalInterval",
                ["1","2"])),
            ("missing_from",lambda r:r.pop("fromNode")),
            ("missing_G",lambda r:r.pop("conductanceWPerKExactPhysicalInterval")),
        )
        for name,mutate in attacks:
            with self.subTest(attack=name):
                fake=deepcopy(self.report)
                mutate(fake["rodHeatFlows"]["ArcX_J4"])
                with self.assertRaises(n8.CornerRefusal):
                    self.cross(reported=fake)
        joint=deepcopy(self.report)
        joint["rodHeatFlows"]["ArcX_J4"].update(
            fromNode="J4",toNode="X",
            conductanceWPerKExactPhysicalInterval=["0","0"])
        with self.assertRaises(n8.CornerRefusal):
            self.cross(reported=joint)

    def test_n8_f02_reported_body_boundary_source_and_node_enclosure_labels_checked(self):
        """A PASS must not silently endorse unvalidated attached Kelvin metadata."""
        checks=(
            ("body_value",lambda r:r["bodyTemperatureAssumptionsKExact"].__setitem__("M","999")),
            ("boundary_value",lambda r:r["fixedBoundaryTemperaturesKExact"].__setitem__("H","999")),
            ("model_hash",lambda r:r.__setitem__("graphSourceModelSha256","f"*64)),
            ("study_hash",lambda r:r.__setitem__("graphSourceStudySha256","f"*64)),
            ("node_interval",lambda r:r["allNodeTemperatureKExactPhysicalEnclosures"].__setitem__(
                "J1",["0","0"])),
            ("missing_node",lambda r:r["allNodeTemperatureKExactPhysicalEnclosures"].pop("J2")),
            ("body_status",lambda r:r.__setitem__("bodyRatesConditionalOnUserAssumedTemperatures",False)),
            ("false_circular",lambda r:r.__setitem__("hasCircularConductor",False)),
        )
        for name,mutate in checks:
            with self.subTest(attack=name):
                fake=deepcopy(self.report)
                mutate(fake)
                with self.assertRaises(n8.CornerRefusal):
                    self.cross(reported=fake)

    def test_native_and_source_trust_forgery_refuses(self):
        for name in ("nativeQualified","nativeExecuted","referenceAccuracyCertified"):
            fake=deepcopy(self.report)
            fake[name]=True
            with self.subTest(name=name):
                with self.assertRaises(n8.CornerRefusal):
                    self.cross(reported=fake)
        wrong=deepcopy(self.report)
        wrong["junctionTemperatureEnclosuresK"].pop("J3")
        with self.assertRaisesRegex(n8.CornerRefusal,"inventory"):
            self.cross(reported=wrong)
        with self.assertRaises(n8.CornerRefusal):
            self.cross(raw=self.raw+b" ")
        with self.assertRaises(n8.CornerRefusal):
            self.cross(pin="0"*64)

    def test_area_only_corner_replay_is_exact_singleton(self):
        raw,pin=serialize(area_chain())
        r=n7.solve_snapshot(raw,expected_sha256=pin,body_node_temperatures={})
        proof=n8.replay(raw,expected_sha256=pin,body_node_temperatures={},reported=r)
        self.assertEqual(proof["endpointCornersChecked"],1)
        self.assertEqual(proof["uncertainCircularRods"],0)
        self.assertEqual(proof["junctionsCompared"],1)
        self.assertEqual(r["junctionTemperatureEnclosuresK"]["J"],
                         ["1010/3","1010/3"])

    def test_original_t1_known_known_pi_rod_has_zero_junction_radius(self):
        raw=T1.read_bytes()
        self.assertEqual(sha256(raw).hexdigest(),T1_SHA)
        body={"R":"337","B":"303","P":"318"}
        result=n7.solve_snapshot(raw,expected_sha256=T1_SHA,
                                 body_node_temperatures=body)
        replay=n8.replay(raw,expected_sha256=T1_SHA,
                         body_node_temperatures=body,reported=result)
        self.assertEqual(replay["uncertainCircularRods"],1)
        self.assertEqual(replay["endpointCornersChecked"],2)
        self.assertEqual(replay["junctionsCompared"],2)
        self.assertEqual(result["junctionTemperatureEnclosuresK"]["J_Lower"],
                         ["8453032705655/25123167961"]*2)
        self.assertEqual(result["junctionTemperatureEnclosuresK"]["J_Upper"],
                         ["8454784897015/25123167961"]*2)
        self.assertTrue(all(row["residualAbsoluteBoundW"]=="0"
                            for row in result["proof"]["rows"]))
        t06=result["rodHeatFlows"]["T06"]
        lo,hi=(F(s) for s in t06["heatFlowWExactPhysicalEnclosure"])
        self.assertLess(lo,hi)
        self.assertFalse(result["timeTrajectoryComputed"])

    def test_source_orientation_reversals_preserve_enclosures(self):
        altered=four_junction_facts()
        for name in ("ArcJ2_J1","ArcX_J4","MassJ2"):
            rod=altered["rods"][name]
            rod["a"],rod["b"]=rod["b"],rod["a"]
        raw,pin=serialize(altered)
        result=n7.solve_snapshot(raw,expected_sha256=pin,
                                 body_node_temperatures=self.assumptions)
        self.assertEqual(self.report["junctionTemperatureEnclosuresK"],
                         result["junctionTemperatureEnclosuresK"])
        self.assertEqual(n8.replay(raw,expected_sha256=pin,
                                   body_node_temperatures=self.assumptions,
                                   reported=result)["endpointCornersChecked"],16)
        for name in ("ArcJ2_J1","ArcX_J4","MassJ2"):
            original=list(map(F,self.report["rodHeatFlows"][name]["heatFlowWExactPhysicalEnclosure"]))
            swapped=list(map(F,result["rodHeatFlows"][name]["heatFlowWExactPhysicalEnclosure"]))
            self.assertEqual(swapped,[-original[1],-original[0]])

    def test_corner_checker_is_not_an_independent_native_or_full_graph_certificate(self):
        out=self.cross()
        for name in ("nativeExecuted","nativeQualified","referenceAccuracyCertified",
                     "independentlyCertifiedReference","fullGrid77Plus8Plus5Certified",
                     "referenceBundleWritten","ownerApprovedSourceManifestVerified",
                     "timeTrajectoryComputed","unfamiliarCompositionIndependentlyQualified"):
            self.assertIs(out[name],False,name)
        self.assertEqual(out["schema"],n8.SCHEMA)
        self.assertEqual(out["sourceFactsSha256"],self.pin)

if __name__=="__main__":
    unittest.main()
