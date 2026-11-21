from fractions import Fraction as F
from unittest import TestCase

from tests.test_join_thermal_networks import LEFT
from tests.test_loaded_thermal_ports import LINK
from tools.coupled_phase_baths import investigate

WARM = ("hot","333.15","200000","0.1","0.45")
COLD = ("cold","273.15","334000","0.5","0.1")


class CoupledBathTests(TestCase):
    def test_common_energy_and_first_event_in_both_directions(self):
        for t in (0,300,750,1000):
            for a,b,sign in ((WARM,COLD,1),(COLD,WARM,-1)):
                r=investigate(LINK,a,b,str(t))
                self.assertEqual(r["firstExhaustingPorts"],["hot"])
                self.assertEqual(r["firstExhaustionTimeBoundsS"],["750"]*2)
                self.assertEqual(r["modeledDurationBoundsS"],[str(min(t,750))]*2)
                self.assertEqual(r["leftToRightHeatRateDuringCoexistenceBoundsW"],[str(120*sign)]*2)
                q=min(t,750)*120
                for name,latent,solid,liquid,energy in (
                    ("hot",200000,F(".1"),F(".45"),-q),("cold",334000,F(".5"),F(".1"),q)):
                    row=r["baths"][name]
                    self.assertEqual(row["latentEnergyIntoBathBoundsJ"],[str(energy)]*2)
                    self.assertEqual(list(map(F,row["remainingSolidBoundsKg"])),[solid-F(energy,latent)]*2)
                    self.assertEqual(list(map(F,row["remainingLiquidBoundsKg"])),[liquid+F(energy,latent)]*2)

    def test_receiver_first_simultaneous_or_no_exhaustion(self):
        for ice,expected in (("0.4",["cold"]),("0.45",["hot","cold"])):
            r=investigate(LINK,WARM,("cold","273.15","200000",ice,"1"),"9999")
            self.assertEqual(r["firstExhaustingPorts"],expected)
            self.assertEqual(r["plateauStatus"],"exhausted")
        r=investigate(LINK,WARM,("cold",*WARM[1:]),"9999")
        self.assertEqual(r["firstExhaustingPorts"],[])
        self.assertIsNone(r["firstExhaustionTimeBoundsS"])
        self.assertEqual(r["baths"]["cold"]["remainingLiquidBoundsKg"],["9/20"]*2)

    def test_refuse_unmodeled_bath_and_invalid_contacts(self):
        for source,a,b in ((LEFT,WARM,COLD),(LINK,WARM,WARM),(LINK,WARM,("cold","273","1","0","1"))):
            with self.assertRaises(ValueError):
                investigate(source,a,b,"0")
