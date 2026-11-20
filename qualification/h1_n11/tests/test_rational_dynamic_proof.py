"""Independent-source H1 N11 rational physical interval proof candidate tests.

No native execution, no reference promotion or altered physical acceptance
allowances. Positive tests exercise exact rational containment and source
equations; negatives challenge proof premises and direct result comparison.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as F
from math import inf, nextafter
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from qualification.h1_n11 import rational_dynamic_proof as n11


class RationalDynamicProofTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts,cls.requests=n11.first_source()
        cls.physical=n11.build_physics(cls.facts)

    def test_outward_integer_operations_contain_exact_negative_and_positive_fractions(self):
        a=n11.Box.bounds(F(-2,3),F(5,7))
        b=n11.Box.bounds(F(4,11),F(7,8))
        exact_sum=a+b
        for x,y in ((F(-2,3),F(4,11)),(F(5,7),F(7,8))):
            self.assertTrue(exact_sum.contains(x+y))
            self.assertTrue((a*b).contains(x*y))
        self.assertTrue((a/b).contains(F(-2,3)/F(4,11)))
        with self.assertRaisesRegex(n11.ProofRefusal,"includes zero"):
            a.inverse()
        self.assertTrue(n11.Box.exact(F(1,3)).contains(F(1,3)))
        self.assertTrue(n11.Box.exact(-F(5,7)).contains(-F(5,7)))

    def test_independent_pi_enclosure_and_source_geometry(self):
        pi=n11.pi_bounds()
        self.assertLess(F(3),F(pi.low,n11.SCALE))
        self.assertGreater(F(4),F(pi.high,n11.SCALE))
        # A separate high-precision decimal evaluation is only a sanity
        # check; the actual proof uses the alternating-series rational tail.
        from mpmath import mp
        with mp.workdps(105):
            self.assertTrue(pi.contains(F(str(mp.pi))))
        p=self.physical
        self.assertEqual((len(p["bnames"]),len(p["fnames"]),len(p["junctions"])),(3,2,2))
        self.assertEqual(set(p["areas"]),{"T06"})
        self.assertTrue(p["G"]["T10"].contains(F(247,8000)))
        self.assertTrue(p["capacities"]["T_Plug"].contains(F(1599,10)))
        with mp.workdps(105):
            self.assertTrue(p["areas"]["T06"].contains(
                F(str(mp.pi))*F(16,1000)**2/4))

    def test_original_initial_signed_flow_and_thermal_balance(self):
        values,req,integrals=n11.sample_physics(
            self.physical,self.physical["start"],F(0),self.requests)
        self.assertEqual((len(values),len(req),len(integrals)),(77,8,5))
        self.assertLess(values["T06.Q_flow"].high,0)
        self.assertTrue(values["T_Collar.T"].contains(F(303)))
        self.assertTrue(values["T_Plug.T"].contains(F(318)))
        self.assertTrue(values["T_Ridge.T"].contains(F(337)))
        self.assertTrue(values["T_Collar.dU"].contains_zero())
        self.assertTrue(values["T_Plug.dU"].contains_zero())
        self.assertTrue(all(v.contains_zero() for v in integrals.values()))
        self.assertTrue((req["t_upper_minus_cool"]-
                         (values["T03.T_a"]-values["T_Cool.T"])).contains_zero())

    def test_rigorous_horner_remainder_is_bounded_and_affine(self):
        H,proof=n11.verified_exponential_step(self.physical["matrix"],2400)
        self.assertEqual(proof["hornerDegree"],24)
        self.assertTrue(proof["lastAffineRowPremiseChecked"])
        self.assertEqual(H[-1],[n11.Box.exact(int(i==6)) for i in range(7)])
        self.assertTrue(n11.apply(H,self.physical["start"])[-1].contains(1))
        for grid in (2400,4800):
            _,p=n11.verified_exponential_step(self.physical["matrix"],grid)
            self.assertTrue(F(p["rhoMax"])<=F(1,2))
            self.assertGreater(F(p["globalMatrixEntryRemainderUpper"]),0)

    def test_forged_affine_final_row_or_wrong_square_shape_refuses(self):
        changed=deepcopy(self.physical["matrix"])
        changed[-1][0]=n11.Box.exact(F(1,10**9))
        with self.assertRaisesRegex(n11.ProofRefusal,"nonzero affine"):
            n11.verified_exponential_step(changed,2400)
        changed=deepcopy(self.physical["matrix"])
        changed[-1][0]=n11.Box.bounds(-F(1,10**12),F(1,10**12))
        with self.assertRaisesRegex(n11.ProofRefusal,"nonzero affine"):
            n11.verified_exponential_step(changed,2400)
        with self.assertRaises(n11.ProofRefusal):
            n11.verified_exponential_step([[n11.Box.exact(0)]],2400)

    def test_later_sample_one_ulp_and_nonfinite_or_bool_values_refuse(self):
        # Avoid the power-of-two binade crossing, where nextafter's new
        # ULP doubles; 0.625 has the same ULP on either neighboring value.
        val=0.625
        exact=n11.Box.exact(F.from_float(val))
        ratio,width=n11.compare_float(val,exact,"W/K","T10.G",2400)
        self.assertEqual(ratio,0)
        self.assertEqual(width,0)
        with self.assertRaisesRegex(n11.ProofRefusal,"T10.G @ 2400"):
            n11.compare_float(nextafter(val,inf),exact,"W/K","T10.G",2400)
        for value in (True,inf,float("nan"),"0.5"):
            with self.subTest(value=value),self.assertRaises(n11.ProofRefusal):
                n11.compare_float(value,exact,"W/K","T10.G",2400)
        with self.assertRaisesRegex(n11.ProofRefusal,"T06.Q_flow"):
            n11.compare_float(1e-5,n11.Box.exact(F(0)),"W",
                              "T06.Q_flow",1)

    def test_wrong_rod_kind_or_mutated_facts_refuse_before_proof(self):
        changed=deepcopy(self.facts)
        changed["rods"]["T06"]["kind"]="Radiation"
        with self.assertRaisesRegex(n11.ProofRefusal,"unsupported rod kind"):
            n11.build_physics(changed)
        with TemporaryDirectory() as tmp:
            bogus=Path(tmp)/"reference-facts.json"
            bogus.write_bytes(n11.FACTS.read_bytes()+b" ")
            with patch.object(n11,"FACTS",bogus):
                with self.assertRaisesRegex(n11.ProofRefusal,"SHA-256 changed"):
                    n11.first_source()

    def test_original_legacy_native_hold_and_output_safety(self):
        self.assertEqual(list(n11.NATIVE_HOLD),
                         ["T02.G","T06.A","T06.G","T07.G","T08.G","T10.G","T_Plug.C"])
        with self.assertRaisesRegex(n11.ProofRefusal,"outside source"):
            n11.audit(output=n11.ROOT/"qualification/h1_n11/forbidden")
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(n11.ProofRefusal,"NEW location"):
                n11.audit(output=Path(tmp))


if __name__=="__main__":
    import unittest
    unittest.main()
