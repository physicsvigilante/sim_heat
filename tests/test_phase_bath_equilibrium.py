from fractions import Fraction as F
from unittest import TestCase

from tests.test_coupled_phase_baths import LINK
from tools.coupled_phase_baths import investigate


class EquilibriumTests(TestCase):
    def test_all_equilibrium_regimes_and_energy_ledgers(self):
        # One kilogram in each bath, initially half solid and half liquid.
        # With c_hot_solid=2 and c_cold_liquid=3, a 20 K change takes 40 and 60 J.
        for lh,lc,temp,q in ((100,200,300,90),(300,100,320,110),(120,100,310,80),
                             (120,200,300,100),(220,100,320,110)):
            hot = ("hot","320",str(lh),"0.5","0.5")
            cold = ("cold","300",str(lc),"0.5","0.5")
            for a,b in ((hot,cold),(cold,hot)):
                eq = investigate(LINK,a,b,"0",("2","3"))["equilibrium"]
                self.assertEqual(F(eq["commonTemperatureK"]),temp)
                for key,energy,latent,initial in (("hot",-q,lh,320),("cold",q,lc,300)):
                    row=eq["baths"][key]
                    solid,liquid=map(F,(row["solidKg"],row["liquidKg"]))
                    self.assertEqual(solid+liquid,1)
                    self.assertGreaterEqual(min(solid,liquid),0)
                    self.assertEqual(F(row["energyIntoBathJ"]),energy)
                    self.assertEqual(F(row["latentEnergyIntoBathJ"]),(liquid-F(".5"))*latent)
                    self.assertEqual(F(row["sensibleEnergyIntoBathJ"]),(temp-initial)*(2 if key=="hot" else 3))
                    self.assertEqual(F(row["latentEnergyIntoBathJ"])+F(row["sensibleEnergyIntoBathJ"]),energy)

    def test_equal_transitions_leave_inventories_unchanged(self):
        hot=("hot","300","100","1","0.1")
        cold=("cold","300","500","0.2","1")
        eq=investigate(LINK,hot,cold,"1000",("2","3"))["equilibrium"]
        self.assertEqual(eq["commonTemperatureK"],"300")
        self.assertEqual(eq["baths"]["cold"]["solidKg"],"1/5")
        self.assertEqual(eq["baths"]["hot"]["energyIntoBathJ"],"0")
        with self.assertRaises(ValueError):
            investigate(LINK,hot,cold,"1000",("0","3"))
