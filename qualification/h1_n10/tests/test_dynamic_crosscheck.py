"""Source-exact high-precision dynamic equation probes; no OMC or output adoption."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from mpmath import mp

from qualification.h1_n10.dynamic_crosscheck import (
    ROOT, ReplayRefusal, assemble, compare_value, compare_grid,
    load_original, snapshot, audit,
)


class DynamicCrosscheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts, cls.requests = load_original()

    def test_original_generic_laplacian_owns_only_original_physical_facts(self):
        with mp.workdps(90):
            system=assemble(self.facts)
            self.assertEqual(system["ode"].rows, 7)
            self.assertEqual(system["ode"].cols, 7)
            self.assertTrue(all(system["ode"][6,j]==0 for j in range(7)))
            self.assertEqual(len(system["jnodes"]), 2)
            self.assertEqual(len(system["conductances"]), 10)
            self.assertEqual(set(system["areas"]), {"T06"})
            self.assertEqual(system["capacities"]["T_Ridge"],mp.mpf("147.2"))
            self.assertEqual(system["capacities"]["T_Collar"],mp.mpf("199.2"))
            # mpmath separately rounds input and product at current decimal
            # precision. Compare 90-dps *numerical* values at a much tighter
            # tolerance than any physical reference acceptance threshold.
            self.assertTrue(mp.almosteq(system["capacities"]["T_Plug"],
                                        mp.mpf("159.9"), abs_eps=mp.mpf("1e-80")))
            self.assertTrue(mp.almosteq(system["areas"]["T06"],
                                       mp.pi*mp.mpf("0.016")**2/4))

    def test_first_source_instant_signed_flows_and_no_precomputed_energy(self):
        with mp.workdps(90):
            system=assemble(self.facts)
            exports,public,integrals=snapshot(system,system["state0"],mp.zero,self.requests)
            self.assertEqual((len(exports),len(public),len(integrals)),(77,8,5))
            self.assertEqual(set(integrals),{
                "T_Ridge.Q_in","T_Plug.Q_in","T_Collar.Q_in",
                "T_Warm.Q_to_network","T_Cool.Q_to_network"})
            self.assertEqual(exports["T_Collar.T"],mp.mpf("303"))
            self.assertEqual(exports["T_Plug.T"],mp.mpf("318"))
            self.assertLess(exports["T06.Q_flow"],0)
            self.assertEqual(exports["T06.Q_flow"],
                             -15*system["conductances"]["T06"])
            self.assertEqual(public["t_collar_to_plug"],exports["T06.Q_flow"])
            self.assertEqual(public["t_upper_minus_cool"],
                             exports["T03.T_a"]-exports["T_Cool.T"])
            self.assertEqual(exports["T_Ridge.dU"],0)
            self.assertEqual(exports["T_Collar.dU"],0)
            self.assertEqual(exports["T_Plug.dU"],0)
            self.assertTrue(all(x==0 for x in integrals.values()))

    def test_reversing_conductor_does_not_change_body_evolution(self):
        altered=deepcopy(self.facts)
        altered["rods"]["T06"]["a"],altered["rods"]["T06"]["b"]=(
            altered["rods"]["T06"]["b"],altered["rods"]["T06"]["a"])
        with mp.workdps(80):
            before=assemble(self.facts)
            after=assemble(altered)
            self.assertEqual(before["ode"],after["ode"])
            original,_,_=snapshot(before,before["state0"],mp.zero,self.requests)
            reversed_,_,_=snapshot(after,after["state0"],mp.zero,self.requests)
            self.assertEqual(original["T06.Q_flow"],-reversed_["T06.Q_flow"])
            self.assertEqual(original["T06.T_a"],reversed_["T06.T_b"])
            self.assertEqual(original["T06.T_b"],reversed_["T06.T_a"])

    def test_generic_isolated_pair_conserves_thermal_body_energy(self):
        # A second, unfamiliar H1 graph with NO fixed boundary or junction;
        # this does not alter the exact pinned public audit source.
        toy={
            "nodes":["A","B"],
            "bodies":{
                "A":{"node":"A","m":Decimal("0.2"),
                     "c":Decimal("900"),"T_initial":Decimal("336.15")},
                "B":{"node":"B","m":Decimal("0.35"),
                     "c":Decimal("420"),"T_initial":Decimal("296.15")}},
            "boundaries":{},
            "rods":{"link":{"kind":"RodArea","a":"A","b":"B",
                             "k":Decimal("80"),"A":Decimal("0.0005"),
                             "L":Decimal("0.2")}},
        }
        with mp.workdps(80):
            system=assemble(toy)
            self.assertEqual(system["jnodes"],[])
            self.assertEqual(system["ode"].rows,5)
            advanced=mp.expm(system["ode"]*mp.mpf(120))*system["state0"]
            exports,_,_=snapshot(system,advanced,mp.mpf(120),[])
            net_energy=exports["A.dU"]+exports["B.dU"]
            self.assertLess(abs(net_energy),mp.mpf("1e-60"))
            self.assertLess(exports["A.dU"],0)
            self.assertGreater(exports["B.dU"],0)

    def test_dynamic_error_outside_one_hundredth_allowance_refuses(self):
        with mp.workdps(80):
            self.assertEqual(compare_value(303.,mp.mpf(303),"K","T_Collar.T",1,2400),0)
            with self.assertRaisesRegex(ReplayRefusal,"T_Collar.T at sample 1"):
                compare_value(303.0001,mp.mpf(303),"K","T_Collar.T",1,2400)
            with self.assertRaisesRegex(ReplayRefusal,"T06.Q_flow at sample 300"):
                compare_value(0.00001,mp.zero,"W","T06.Q_flow",300,2400)
            with self.assertRaisesRegex(ReplayRefusal,"T10.G"):
                centre=float.fromhex("0x1.f9db22d0e5604p-6")
                changed=math.nextafter(centre,math.inf)
                compare_value(changed,mp.mpf(centre),"W/K","T10.G",1,2400)

    def test_invalid_grid_and_native_output_path_refuse(self):
        with self.assertRaisesRegex(ReplayRefusal,"missing pinned original grid"):
            compare_grid({"report":{"gridIntervals":3000},"grid":[]},
                         2400,self.facts,self.requests)
        with self.assertRaisesRegex(ReplayRefusal,"outside-repository"):
            audit(output=ROOT/"qualification"/"h1_n10"/"forbidden")
        with TemporaryDirectory() as scratch:
            with self.assertRaisesRegex(ReplayRefusal,"outside-repository"):
                audit(output=Path(scratch))


if __name__=="__main__":
    unittest.main()
