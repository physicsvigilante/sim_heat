from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.spherical_conduction import investigate


# Independent decimal truncation and successor bound for pi.
PI = F("3.14159265358979323846264338327950288419716939937510582097494459230781640628620899")


class SphericalConductionTests(TestCase):
    def tight(self, bounds, targets):
        lo, hi = map(F,bounds)
        self.assertTrue(lo <= min(targets) <= max(targets) <= hi)
        self.assertLess(hi-lo, F(1,10**12))

    def test_two_materials_with_both_backing_walls(self):
        result = investigate(LINK,LINK,"cold","hot","0.1",(("0.2","2"),("0.4","1")))
        # Each layer has integrated (1/r_i - 1/r_o)/k = 5/2.
        # Solve T = a + b/r in each region. Both supporting walls are 1/2 K/W.
        for pi in (PI, PI+F(1,10**80)):
            q = 100/(1+5/(4*pi))
            self.tight(result["outwardHeatRateBoundsW"], [q])
            for index, row in enumerate(result["surfaces"]):
                radius = F(1,10)*2**index
                self.tight(row["temperatureBoundsK"], [380-q*(F(1,2)+index*F(5,2)/(4*pi))])
                self.tight(row["outwardHeatFluxBoundsWPerM2"], [q/(4*pi*radius**2)])

    def test_splitting_same_material_and_reversing_drive(self):
        whole = investigate(LINK,LINK,"cold","hot","0.1",[("0.4","2")])
        split = investigate(LINK,LINK,"hot","cold","0.1",[("0.2","2"),("0.4","2")])
        a,b = map(F,whole["outwardHeatRateBoundsW"])
        c,d = map(F,split["outwardHeatRateBoundsW"])
        self.assertGreater(a,0)
        self.assertTrue(max(a,-d) <= min(b,-c))
        self.assertLess(abs(b+c),F(1,10**12))
        idle = investigate(LINK,LINK,"cold","cold","0.1",[("0.4","2")])
        self.tight(idle["outwardHeatRateBoundsW"],[0])

    def test_nonphysical_shells_and_bad_source_refused(self):
        for rad, layers in (("0",[("1","2")]), ("1",[]), ("1",[("1","2")]),
                            ("1",[("2","0")]), ("1",[("2","1"),("1.5","1")])):
            with self.assertRaises(ValueError):
                investigate(LINK,LINK,"cold","hot",rad,layers)
        with self.assertRaises(ValueError):
            investigate((*LINK[:-1],"0"*64),LINK,"cold","hot","0.1",[("0.4","2")])
