from fractions import Fraction as F
from unittest import TestCase

from tests.test_join_thermal_networks import LEFT
from tests.test_loaded_thermal_ports import LINK
from tools.latent_heat_bath import investigate


class LatentBathTests(TestCase):
    def exact(self, result, field, value):
        self.assertEqual(list(map(F,result[field])),[value,value])

    def test_finite_ice_inventory_and_time_cap(self):
        q, initial = F("213.7"), F("0.5")
        for seconds in (0,600,1000):
            r = investigate(LINK,"cold","273.15","334000","0.5","0.1",str(seconds))
            end = initial*334000/q
            modeled = min(end,seconds)
            self.exact(r,"exhaustionTimeBoundsS",end)
            self.exact(r,"modeledDurationBoundsS",modeled)
            self.exact(r,"latentEnergyIntoBathBoundsJ",q*modeled)
            self.exact(r,"remainingSolidBoundsKg",initial-q*modeled/334000)
            self.exact(r,"remainingLiquidBoundsKg",F("0.1")+q*modeled/334000)
            self.assertEqual(r["plateauStatus"],"exhausted" if seconds >= end else "coexisting")

    def test_freezing_multibath_star_and_endpoint_equality(self):
        # For a 340 K bath at the middle leg, the star centre is
        # (2*380 + 5*280 + 3*340)/10 = 318 K. Bath loses 66 W.
        r = investigate(LEFT,"middle","340","330000","1","0.1","500")
        for field,value in (("bathInflowDuringPlateauBoundsW",-66),("exhaustionTimeBoundsS",500),
                            ("remainingSolidBoundsKg",F("1.1")),("remainingLiquidBoundsKg",0)):
            lo,hi = map(F,r[field])
            self.assertTrue(lo <= value <= hi)
            self.assertLess(hi-lo,F(1,10**12))
        self.assertEqual(r["phaseProcess"],"freezing")
        # Use exact two-terminal values to exercise a definitely exhausted endpoint.
        r = investigate(LINK,"hot","300","400","1","1","10")
        self.assertEqual(r["plateauStatus"],"exhausted")
        self.exact(r,"remainingLiquidBoundsKg",0)

    def test_equilibrium_and_invalid_inventory(self):
        r = investigate(LINK,"cold","380","100","1","1","999")
        self.assertIsNone(r["exhaustionTimeBoundsS"])
        self.assertEqual(r["phaseProcess"],"equilibrium")
        self.exact(r,"remainingLiquidBoundsKg",1)
        for latent,solid in (("0","1"),("10","0")):
            with self.assertRaises(ValueError):
                investigate(LINK,"cold","273.15",latent,solid,"1","10")
        with self.assertRaisesRegex(ValueError,"unknown"):
            investigate(LINK,"missing","273.15","1","1","1","10")
