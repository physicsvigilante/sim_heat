from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from tests.test_coupled_phase_baths import LINK
from tools.coupled_phase_baths import investigate


class TransferTimeTests(TestCase):
    def test_piecewise_passage_including_exact_boundaries(self):
        # Each bath has 1 kg, with 60 J available by freezing and 50 J by melting.
        hot=("hot","320","120","0.5","0.5")
        cold=("cold","300","100","0.5","0.5")
        for a,b in ((hot,cold),(cold,hot)):
            for target in (0,30,50,55,60,70):
                out=investigate(LINK,a,b,"0",("2","3"),str(target))["transferPassage"]
                pts=sorted({0,target,min(target,50),min(target,60)})
                self.assertEqual(len(out["segments"]),len(pts)-1)
                with mp.workdps(110):
                    def reciprocal_flow(e):
                        th=mp.mpf(320)-max(mp.mpf(0),e-60)/2
                        tc=mp.mpf(300)+max(mp.mpf(0),e-50)/3
                        return 1/(2*(th-tc))
                    exact=sum(mp.quad(reciprocal_flow,[i,j]) for i,j in zip(pts,pts[1:]))
                    lo,hi=map(F,out["durationBoundsS"])
                    self.assertTrue(lo <= F(mp.nstr(exact,100)) <= hi)
                    self.assertLess(hi-lo,F(1,10**12))
                self.assertEqual(F(out["terminalTemperaturesK"]["hot"]),320-max(F(0),F(target-60))/2)

    def test_simultaneous_transition_does_not_create_empty_segment(self):
        a=("hot","320","100","0.5","0.5")
        b=("cold","300","100","0.5","0.5")
        r=investigate(LINK,a,b,"0",("2","3"),"60")
        self.assertEqual(len(r["transferPassage"]["segments"]),2)
        for e in ("74","75"):
            with self.assertRaisesRegex(ValueError,"strictly below"):
                investigate(LINK,a,b,"0",("2","3"),e)
        with self.assertRaisesRegex(ValueError,"specific heats"):
            investigate(LINK,a,b,"0",None,"1")
