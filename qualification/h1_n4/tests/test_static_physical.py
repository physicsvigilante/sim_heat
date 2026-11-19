"""Adversarial OFFLINE H1 static law checks: NO NATIVE RESULTS OR BUNDLES."""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction as F
from hashlib import sha256
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from qualification.h1_n4 import static_physical as n4
from qualification.h1_n1 import check_plan as n1

N1=Path(__file__).resolve().parents[2]/"h1_n1"
FACTS=N1/"reference-facts.json"
PIN="39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf"

def raw_and_sha(obj):
    raw=(json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
    return raw,sha256(raw).hexdigest()

def small_graph():
    return {
      "schema":"sim_heat.reference/1","id":"GenericH1BranchGraph",
      "mode":"transient","modelSha256":"a"*64,"studySha256":"b"*64,
      "analysis":{"startTime":0,"stopTime":2400,"intervals":2400,"solver":"dassl","tolerance":1e-8},
      "provenance":"SYNTHETIC INDEPENDENT GRAPH for generic checking tests, not textbook or native data",
      "nodes":["HotNode","InnerNode","ColdNode"],
      "bodies":{"Block":{"node":"InnerNode","m":0.5,"c":900,"T_initial":310}},
      "boundaries":{"Hot":{"node":"HotNode","T":360},
                    "Cold":{"node":"ColdNode","T":290}},
      "rods":{"Bar":{"kind":"RodArea","a":"HotNode","b":"InnerNode",
                      "k":40,"L":0.25,"A":0.002},
              "Tube":{"kind":"RodCircular","a":"InnerNode","b":"ColdNode",
                       "k":80,"L":0.5,"d":0.01}}
    }

class StaticPhysicalCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=FACTS.read_bytes()
        assert sha256(cls.raw).hexdigest()==PIN
        cls.candidate=n4.create_static_candidate(cls.raw,expected_sha256=PIN)

    def test_original_source_all_14_physically_certified_candidates_but_not_native(self):
        r=self.candidate
        self.assertEqual(r["sourceFactsSha256"],PIN)
        self.assertEqual(r["staticExports"],14)
        self.assertEqual(len(r["exports"]),14)
        self.assertEqual({x for x in r["exports"] if x.endswith(".C")},
                         {"T_Ridge.C","T_Collar.C","T_Plug.C"})
        self.assertEqual({x for x in r["exports"] if x.endswith(".A")},{"T06.A"})
        self.assertEqual(len([x for x in r["exports"] if x.endswith(".G")]),10)
        self.assertTrue(all(x["physical100x"]=="PASS_CANDIDATE_NOT_NATIVE_QUALIFIED"
                            for x in r["exports"].values()))
        for key in ("independentlyCertifiedReference","nativeExecuted","nativeQualified",
                    "runtimeReady","referenceAccuracyCertified","generalH1DynamicsQualified",
                    "historicalReferenceRegenerated","referenceBundleWritten",
                    "externalOwnerApprovalVerified"):
            self.assertIs(r[key],False,key)
        self.assertTrue(r["candidateValuesOnly"])

    def test_original_exact_source_against_predeclared_n1_physical_witnesses(self):
        original_plan=json.loads((N1/"plan.json").read_text())
        diagnostic=n1.arithmetic_diagnostics(original_plan,FACTS)
        self.assertEqual(diagnostic["staticExports"],14)
        self.assertEqual(set(diagnostic["physical100xFailures"]),
          {"T02.G","T06.A","T06.G","T07.G","T08.G","T10.G","T_Plug.C"})
        for old in diagnostic["rows"]:
            with self.subTest(export=old["export"]):
                candidate=self.candidate["exports"][old["export"]]
                self.assertEqual(candidate["binary64Hex"],old["correctlyRoundedPhysicalWitnessHex"])
                self.assertEqual(candidate["physicalLowerRational"],old["physicalEnclosure"][0])
                self.assertEqual(candidate["physicalUpperRational"],old["physicalEnclosure"][1])
                self.assertEqual(candidate["physical100x"],"PASS_CANDIDATE_NOT_NATIVE_QUALIFIED")
                self.assertTrue(old["witnessPhysical100x"])
                self.assertFalse(old["witnessAdopted"])
        self.assertFalse(self.candidate["referenceBundleWritten"])

    def test_unfamiliar_supported_branch_from_source_facts_without_new_code(self):
        raw,digest=raw_and_sha(small_graph())
        result=n4.create_static_candidate(raw,expected_sha256=digest)
        self.assertEqual(set(result["exports"]),{"Block.C","Bar.G","Tube.A","Tube.G"})
        self.assertEqual(result["exports"]["Block.C"]["binary64Hex"],float(450).hex())
        self.assertEqual(result["exports"]["Bar.G"]["binary64Hex"],float(0.32).hex())
        self.assertTrue(result["exports"]["Tube.A"]["binary64Hex"].startswith("0x"))
        self.assertTrue(result["exports"]["Tube.G"]["binary64Hex"].startswith("0x"))
        self.assertEqual(result["sourceStudyId"],"GenericH1BranchGraph")
        self.assertFalse(result["generalH1DynamicsQualified"])

    def test_steady_graph_without_body_does_not_require_new_law(self):
        spec=small_graph()
        spec["id"]="GenericH1Steady"
        spec["mode"]="steady"
        spec["analysis"]={}
        spec["bodies"]={}
        spec["rods"]={"Bar":{"kind":"RodArea","a":"HotNode","b":"ColdNode",
                               "k":50,"L":0.25,"A":0.001}}
        spec["nodes"]=["HotNode","ColdNode"]
        raw,digest=raw_and_sha(spec)
        r=n4.create_static_candidate(raw,expected_sha256=digest)
        self.assertEqual(r["staticExports"],1)
        self.assertEqual(set(r["exports"]),{"Bar.G"})

    def test_binary64_ties_exact_round_to_even_and_subnormal_boundary(self):
        self.assertEqual(n4.rn_even_binary64(F(1)+F(1,2**53)),F(1))
        self.assertEqual(n4.rn_even_binary64(F(1)+3*F(1,2**53)),
                         F(1)+F(1,2**51))
        self.assertEqual(n4.rn_even_binary64(F(1,2**1074)),F(1,2**1074))
        self.assertEqual(n4.rn_even_binary64(F(1,2**1075)),F(0))
        self.assertEqual(n4.ulp_positive(F(1)),F(1,2**52))
        with self.assertRaisesRegex(n4.PhysicalRefusal,"binary64 overflow"):
            n4.rn_even_binary64(F(2**1024))

    def test_rational_pi_enclosure_and_rounding_are_proven_without_float_pi(self):
        a,b=n4.pi_rational_enclosure()
        self.assertLess(a,b)
        self.assertLess(b-a,F(1,10**48))
        self.assertLess(a,F(31415926535897932384626433832796,10**31))
        self.assertGreater(b,F(31415926535897932384626433832795,10**31))
        self.assertEqual(n4.rn_even_binary64(a),n4.rn_even_binary64(b))
        self.assertEqual(float(n4.rn_even_binary64(a)).hex(),"0x1.921fb54442d18p+1")
        with self.assertRaises(n4.PhysicalRefusal):
            n4.pi_rational_enclosure(0)
        with self.assertRaises(n4.PhysicalRefusal):
            n4.pi_rational_enclosure(True)

    def test_physical_error_gate_detects_one_ulp_but_not_nearest(self):
        row=self.candidate["exports"]["T10.G"]
        true_bounds=(F(row["physicalLowerRational"]),F(row["physicalUpperRational"]))
        center=F.from_float(float.fromhex(row["binary64Hex"]))
        self.assertTrue(n4.physical_budget(center,true_bounds)[0])
        bumped=center+n4.ulp_positive(center)
        self.assertFalse(n4.physical_budget(bumped,true_bounds)[0])
        self.assertGreater(n4.physical_budget(bumped,true_bounds)[1],
                           n4.physical_budget(bumped,true_bounds)[2]/100)

    def test_hash_original_or_mutated_source_refuses_before_calculation(self):
        with self.assertRaisesRegex(n4.PhysicalRefusal,"source bytes"):
            n4.create_static_candidate(self.raw+b" ",expected_sha256=PIN)
        with self.assertRaisesRegex(n4.PhysicalRefusal,"source bytes"):
            n4.create_static_candidate(self.raw,expected_sha256="f"*64)
        with self.assertRaisesRegex(n4.PhysicalRefusal,"source SHA-256"):
            n4.create_static_candidate(self.raw,expected_sha256=None)

    def test_invalid_geometry_types_nodes_and_unsupported_kinds_refuse(self):
        cases={
            "unknown_geometry":lambda s:s["rods"]["Tube"].update(A=0.4),
            "rod_without_d":lambda s:s["rods"]["Tube"].pop("d"),
            "unknown_law":lambda s:s["rods"]["Tube"].update(kind="RodPower"),
            "negative_k":lambda s:s["rods"]["Tube"].update(k=-1),
            "zero_length":lambda s:s["rods"]["Bar"].update(L=0),
            "bool_area":lambda s:s["rods"]["Bar"].update(A=True),
            "bad_endpoint":lambda s:s["rods"]["Bar"].update(b="Unbound"),
            "same_endpoint":lambda s:s["rods"]["Bar"].update(b="HotNode"),
            "unattributed":lambda s:s["nodes"].append("Unused"),
            "bad_body_mass":lambda s:s["bodies"]["Block"].update(m="0.5"),
            "overlap_owner":lambda s:s["boundaries"]["Hot"].update(node="InnerNode"),
            "bad_mode":lambda s:s.update(mode="gas"),
            "unrecognized_body_slot":lambda s:s["bodies"]["Block"].update(C=123),
        }
        for label,edit in cases.items():
            with self.subTest(case=label):
                spec=small_graph()
                edit(spec)
                raw,digest=raw_and_sha(spec)
                with self.assertRaises(n4.PhysicalRefusal):
                    n4.create_static_candidate(raw,expected_sha256=digest)

    def test_duplicate_json_nonfinite_and_exponent_bomb_refused(self):
        for raw in (b'{"a":1,"a":2}',b'{"x":NaN}',
                    b'{"x":Infinity}',b'{"x":1e9999}',b'{"x":-1e9999}'):
            with self.subTest(raw=raw):
                with self.assertRaises(n4.PhysicalRefusal):
                    n4.parse_facts(raw,expected_sha256=sha256(raw).hexdigest())
        with self.assertRaises(n4.PhysicalRefusal):
            n4.parse_facts(b"x"*300000,expected_sha256=sha256(b"x"*300000).hexdigest())

    def test_readonly_candidate_has_no_apparatus_specific_identity_or_native_imports(self):
        content=(Path(__file__).resolve().parents[1]/"static_physical.py").read_text()
        for forbidden in ("T_Ridge","T06","T10","Modelica","import subprocess",
                          "h1_native_batch","reference.prepare(","SimHeat.mo"):
            if forbidden=="Modelica":
                continue  # only the docstring's negative claim names it
            self.assertNotIn(forbidden,content)
        self.assertNotIn("from qualification.h1_n1.check_plan",content)
        self.assertEqual(self.candidate["schema"],n4.SCHEMA)
        self.assertNotIn("seal",self.candidate)

if __name__=="__main__":
    unittest.main()
