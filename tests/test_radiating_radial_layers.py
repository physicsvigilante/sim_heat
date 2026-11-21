from fractions import Fraction
from unittest import TestCase

from mpmath import mp

from tests.test_loaded_thermal_ports import LINK
from tools.radiating_radial_layers import investigate


class RadiatingRadialTests(TestCase):
    def test_two_layers_emitting_and_absorbing(self):
        layers = [("0.2","2"),("0.4","1")]
        for length, enclosure in ((None,"280"),("1","450")):
            with self.subTest(length=length):
                actual = investigate(LINK,"cold","0.1",layers,enclosure,"0.8","0.0000000567",length)
                with mp.workdps(110):
                    radii = list(map(mp.mpf,("0.1","0.2","0.4")))
                    if length is None:
                        areas = [4*mp.pi*r*r for r in radii]
                        drops = [(1/a-1/b)/(4*mp.pi*k) for a,b,k in zip(radii,radii[1:],(2,1))]
                    else:
                        areas = [2*mp.pi*r for r in radii]
                        drops = [mp.log(b/a)/(2*mp.pi*k) for a,b,k in zip(radii,radii[1:],(2,1))]
                    total = mp.mpf("0.5")+sum(drops)
                    def balance(t):
                        return (380-t)/total-areas[-1]*mp.mpf("0.8")*mp.mpf("0.0000000567")*(t**4-int(enclosure)**4)
                    surface = mp.findroot(balance, (380,int(enclosure)))
                    q = (380-surface)/total
                    pairs = [(actual["outwardHeatRateBoundsW"], q)]
                    for i,row in enumerate(actual["surfaces"]):
                        pairs.extend(((row["temperatureBoundsK"],380-q*(mp.mpf("0.5")+sum(drops[:i]))),
                                      (row["outwardHeatFluxBoundsWPerM2"],q/areas[i])))
                    for endpoints,value in pairs:
                        lo,hi = map(Fraction,endpoints)
                        self.assertTrue(lo <= Fraction(mp.nstr(value,95)) <= hi)
                        self.assertLess(hi-lo,Fraction(1,10**11))

    def test_perfect_reflector_and_invalid_geometry(self):
        result = investigate(LINK,"cold","0.1",[("0.2","2")],"280","0","0.0000000567")
        self.assertEqual(result["outwardHeatRateBoundsW"],["0","0"])
        for row in result["surfaces"]:
            self.assertEqual(row["temperatureBoundsK"],["380","380"])
        for radius, em in (("0.1","1.1"),("0.2","1")):
            with self.assertRaises(ValueError):
                investigate(LINK,"cold",radius,[("0.2","2")],"280",em,"0.0000000567")

    def test_mixed_air_and_enclosure_have_opposing_heat_flows(self):
        for length in (None, "1"):
            result = investigate(LINK, "cold", "0.1", [("0.2","2")], "280", "0.8",
                                 "0.0000000567", length, air_k="450", h_w_per_m2_k="12")
            with mp.workdps(110):
                r = mp.mpf("0.2")
                area = 4*mp.pi*r*r if length is None else 2*mp.pi*r
                shell_r = 5/(8*mp.pi) if length is None else mp.log(2)/(4*mp.pi)
                total = mp.mpf("0.5") + shell_r
                def radiation(t):
                    return area*mp.mpf("0.00000004536")*(t**4-280**4)
                def conv(t):
                    return area*12*(t-450)
                t = mp.findroot(lambda temp: (380-temp)/total-radiation(temp)-conv(temp), 375)
                for limits, expected in [(result["surfaces"][-1]["temperatureBoundsK"],t),
                                         (result["outwardHeatRateBoundsW"],(380-t)/total),
                                         (result["netHeatToAirBoundsW"],conv(t)),
                                         (result["netHeatToEnclosureBoundsW"],radiation(t))]:
                    lo, hi = map(Fraction, limits)
                    self.assertTrue(lo <= Fraction(mp.nstr(expected,95)) <= hi)
                    self.assertLess(hi-lo, Fraction(1,10**11))

    def test_pure_convection_critical_radius_and_partial_options(self):
        args = (LINK, "cold", "0.1", [("0.2","2")], "280", "0", "0.0000000567")
        # At radius k/h for a cylinder and 2k/h for a sphere, the added
        # conduction resistance exactly offsets the increase in outer area.
        for length, h in (("1","10"), (None,"20")):
            r = investigate(*args, length, radius_sensitivity=True, air_k="280", h_w_per_m2_k=h)
            self.assertEqual(r["outerRadiusSensitivity"]["heatRateMagnitudeTrend"], "stationary")
            self.assertEqual(r["netHeatToEnclosureBoundsW"], ["0","0"])
        with self.assertRaisesRegex(ValueError, "together"):
            investigate(*args, air_k="280")
