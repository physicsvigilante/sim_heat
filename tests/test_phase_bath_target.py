from decimal import Decimal, localcontext
from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.phase_bath_target import investigate


class PhaseBathTargetTests(TestCase):
    def test_melting_then_warming_and_freezing_then_cooling(self):
        for port, tm, target, opening, inventory, cp in (
            ("cold","273.15","293.15","380","0.5","4200"),
            ("hot","310","290","280","0.1","2100")):
            law = investigate(LINK,port,tm,"334000","0.5","0.1",cp,target)
            with localcontext() as ctx:
                ctx.prec = 100
                d, goal, bath, m, c = map(Decimal,(tm,target,opening,inventory,cp))
                t1 = m*334000/(2*abs(bath-d))
                t2 = Decimal(".3")*c*((bath-d)/(bath-goal)).ln()
                for field,ref in (("plateauDurationBoundsS",t1),("sensibleDurationBoundsS",t2),
                                  ("totalDurationBoundsS",t1+t2)):
                    lo,hi = map(F,law[field])
                    # Endpoint times may be exact rational with nonterminating decimals.
                    if field == "plateauDurationBoundsS":
                        self.assertEqual(lo,F(inventory)*334000/(2*abs(F(opening)-F(tm))))
                        self.assertEqual(hi,lo)
                    else:
                        self.assertTrue(lo <= F(ref) <= hi)
                        self.assertLess(hi-lo,F(1,10**15))
            latent = F(inventory)*334000*(1 if F(target)>F(tm) else -1)
            self.assertEqual(F(law["totalEnergyIntoBathJ"]),latent+F(".6")*F(cp)*(F(target)-F(tm)))

    def test_target_at_or_beyond_open_temperature_and_wrong_direction(self):
        for target in ("380","381","260","273.15"):
            with self.assertRaises(ValueError):
                investigate(LINK,"cold","273.15","334000","0.5","0.1","4200",target)
