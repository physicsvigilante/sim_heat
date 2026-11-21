from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from tests.test_loaded_thermal_ports import LINK
from tools.radiating_radial_layers import investigate


class InsulationRadiusTests(TestCase):
    def test_derivative_agrees_with_perturbed_nonlinear_solutions(self):
        for shape, radius, ambient, expected in ((None,"0.12","280","increasing"),
                                                  (None,"0.8","280","increasing"),
                                                  (None,"1.4","280","decreasing"),
                                                  ("1","0.8","450","decreasing")):
            with self.subTest(shape=shape,radius=radius,ambient=ambient), mp.workdps(90):
                result = investigate(LINK,"cold","0.1",[(radius,"2")],ambient,"0.8","0.0000000567",
                                     shape,radius_sensitivity=True)["outerRadiusSensitivity"]
                def heat(r):
                    a = mp.mpf("0.1")
                    if shape is None:
                        area, resistance = 4*mp.pi*r**2, (1/a-1/r)/(8*mp.pi)
                    else:
                        area, resistance = 2*mp.pi*r, mp.log(r/a)/(4*mp.pi)
                    total = resistance+mp.mpf("0.5")
                    def residual(t):
                        return (380-t)/total - mp.mpf("0.8")*mp.mpf("0.0000000567")*area*(t**4-int(ambient)**4)
                    return (380-mp.findroot(residual,(380,int(ambient))))/total
                r = mp.mpf(radius)
                # Symmetric perturbation of the independently solved boundary problem.
                h = mp.mpf("1e-28")
                derivative = (heat(r+h)-heat(r-h))/(2*h)
                for name,target in (("outwardHeatRateDerivativeBoundsWPerM",derivative),
                                    ("heatRateMagnitudeDerivativeBoundsWPerM",mp.sign(heat(r))*derivative)):
                    lo,hi = map(F,result[name])
                    self.assertTrue(lo <= F(mp.nstr(target,70)) <= hi)
                    self.assertLess(hi-lo,F(1,10**10))
                self.assertEqual(result["heatRateMagnitudeTrend"],expected)

    def test_zero_drive_or_zero_emissivity(self):
        for ambient,em in (("380","1"),("280","0")):
            result = investigate(LINK,"cold","0.1",[("0.4","1")],ambient,em,"0.0000000567",
                                 radius_sensitivity=True)["outerRadiusSensitivity"]
            self.assertEqual(result["heatRateMagnitudeTrend"],"stationary")
            self.assertEqual(result["heatRateMagnitudeDerivativeBoundsWPerM"],["0","0"])
