from decimal import Decimal, localcontext
from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tests.test_spherical_conduction import PI
from tools.spherical_conduction import investigate, radial_log


class CylindricalTests(TestCase):
    def test_log_bounds_for_thin_and_widely_separated_radii(self):
        for ratio in (F(10**30+1,10**30),F(2),F(64,3),F(10**29)):
            lo, hi = radial_log(ratio).span()
            with localcontext() as ctx:
                ctx.prec = 110
                target = F((Decimal(ratio.numerator)/Decimal(ratio.denominator)).ln())
            self.assertTrue(lo <= target <= hi)
            self.assertLess(hi-lo,F(1,10**55))

    def test_pipe_heat_budget_and_flux(self):
        law = investigate(LINK,LINK,"cold","hot","0.1",[("0.2","2"),("0.4","1")],"1")
        with localcontext() as ctx:
            ctx.prec = 110
            log2 = F(Decimal(2).ln())
        q = 100/(1+3*log2/(4*PI))
        for row, r, drop in zip(law["surfaces"],map(F,(".1",".2",".4")),
                                (0, log2/(4*PI), 3*log2/(4*PI)), strict=True):
            for key, expected in (("temperatureBoundsK",380-q*(F(1,2)+drop)),
                                  ("outwardHeatFluxBoundsWPerM2",q/(2*PI*r))):
                lo,hi = map(F,row[key])
                self.assertTrue(lo <= expected <= hi)
                self.assertLess(hi-lo,F(1,10**12))
        lo,hi = map(F,law["outwardHeatRateBoundsW"])
        self.assertTrue(lo <= q <= hi)
        self.assertEqual(law["cylinderLengthM"],"1")

    def test_length_refusal(self):
        with self.assertRaisesRegex(ValueError,"length"):
            investigate(LINK,LINK,"cold","hot","0.1",[("0.2","1")],"0")
