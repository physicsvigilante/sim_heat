from fractions import Fraction as F
from unittest import TestCase

from tests.test_join_thermal_networks import LEFT
from tests.test_loaded_thermal_ports import LINK
from tools.body_phase_bath_exchange import investigate as body_phase_investigate
from tools.latent_heat_bath import investigate, phase_inputs, plateau
from tools.phase_shell_sizing import investigate as shell_sizing_investigate
from tools.radial_phase_bath import investigate as radial_phase_investigate
from tools.radial_radiation_shields import investigate_phase_dewar
from tools.terminal_response import investigate as terminal_response


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
        for latent, solid, liquid in (("0", "1", "1"), ("10", "0", "0")):
            with self.assertRaises(ValueError):
                investigate(LINK, "cold", "273.15", latent, solid, liquid, "10")
        with self.assertRaisesRegex(ValueError, "unknown"):
            investigate(LINK, "missing", "273.15", "1", "1", "1", "10")

    def test_f04_pure_phase_regimes_epsilon_limit_and_untouched_caller_isolation(self):
        # 1) Pure solid + melting inflow: epsilon-equivalence criterion (eps in {1e-9, 1e-12}) + exact oracle.
        q_melt = F("213.7")
        pure_s = investigate(LINK, "cold", "273.15", "334000", "1", "0", "100")
        self.assertEqual(pure_s["phaseProcess"], "melting")
        self.assertEqual(pure_s["plateauStatus"], "coexisting")
        self.assertIs(pure_s["exhaustedAtStart"], False)
        self.assertIsNone(pure_s["exhaustedPhase"])
        self.exact(pure_s, "latentEnergyIntoBathBoundsJ", q_melt * 100)
        self.exact(pure_s, "remainingSolidBoundsKg", F(1) - q_melt * 100 / 334000)
        self.exact(pure_s, "remainingLiquidBoundsKg", q_melt * 100 / 334000)
        for eps_s in ("0.000000001", "0.000000000001"):
            eps = F(eps_s)
            ref = investigate(LINK, "cold", "273.15", "334000", "1", eps_s, "100")
            self.assertEqual(pure_s["latentEnergyIntoBathBoundsJ"], ref["latentEnergyIntoBathBoundsJ"])
            self.assertEqual(pure_s["remainingSolidBoundsKg"], ref["remainingSolidBoundsKg"])
            self.assertEqual(pure_s["modeledDurationBoundsS"], ref["modeledDurationBoundsS"])
            self.assertEqual(
                [F(x) for x in pure_s["remainingLiquidBoundsKg"]],
                [F(x) - eps for x in ref["remainingLiquidBoundsKg"]],
            )

        # 2) Pure liquid + freezing outflow mirror: LINK hot=300 K, cold=280 K -> Q_hot = -40 W.
        pure_l = investigate(LINK, "hot", "300", "400", "0", "1", "5")
        self.assertEqual(pure_l["phaseProcess"], "freezing")
        self.assertEqual(pure_l["plateauStatus"], "coexisting")
        self.assertIs(pure_l["exhaustedAtStart"], False)
        self.assertIsNone(pure_l["exhaustedPhase"])
        self.exact(pure_l, "latentEnergyIntoBathBoundsJ", F(-200))
        self.exact(pure_l, "remainingLiquidBoundsKg", F(1, 2))
        self.exact(pure_l, "remainingSolidBoundsKg", F(1, 2))
        for eps_s in ("0.000000001", "0.000000000001"):
            eps = F(eps_s)
            ref = investigate(LINK, "hot", "300", "400", eps_s, "1", "5")
            self.assertEqual(pure_l["latentEnergyIntoBathBoundsJ"], ref["latentEnergyIntoBathBoundsJ"])
            self.assertEqual(pure_l["remainingLiquidBoundsKg"], ref["remainingLiquidBoundsKg"])
            self.assertEqual(
                [F(x) for x in pure_l["remainingSolidBoundsKg"]],
                [F(x) - eps for x in ref["remainingSolidBoundsKg"]],
            )

        # 3) Regime (b): pure phase with outflow leaving coexistence -> exhaustedAtStart=True (including duration == 0).
        for dur_s in ("10", "0"):
            exh_l = investigate(LINK, "cold", "273.15", "10", "0", "1", dur_s)
            self.assertEqual(exh_l["plateauStatus"], "exhausted")
            self.assertIs(exh_l["exhaustedAtStart"], True)
            self.assertEqual(exh_l["exhaustedPhase"], "solid")
            self.assertEqual(exh_l["modeledDurationBoundsS"], ["0", "0"])
            self.assertEqual(exh_l["exhaustionTimeBoundsS"], ["0", "0"])
            self.assertEqual(exh_l["remainingSolidBoundsKg"], ["0", "0"])
            self.assertEqual(exh_l["remainingLiquidBoundsKg"], ["1", "1"])

            exh_s = investigate(LINK, "hot", "300", "400", "1", "0", dur_s)
            self.assertEqual(exh_s["plateauStatus"], "exhausted")
            self.assertIs(exh_s["exhaustedAtStart"], True)
            self.assertEqual(exh_s["exhaustedPhase"], "liquid")
            self.assertEqual(exh_s["modeledDurationBoundsS"], ["0", "0"])
            self.assertEqual(exh_s["exhaustionTimeBoundsS"], ["0", "0"])
            self.assertEqual(exh_s["remainingSolidBoundsKg"], ["1", "1"])
            self.assertEqual(exh_s["remainingLiquidBoundsKg"], ["0", "0"])

        # 4) Regime (c): exact equilibrium with pure solid & pure liquid -> coexisting, inventory unchanged.
        for sol_s, liq_s in (("1", "0"), ("0", "1")):
            eq = investigate(LINK, "cold", "380", "100", sol_s, liq_s, "999")
            self.assertEqual(eq["phaseProcess"], "equilibrium")
            self.assertEqual(eq["plateauStatus"], "coexisting")
            self.assertIs(eq["exhaustedAtStart"], False)
            self.assertIsNone(eq["exhaustedPhase"])
            self.assertEqual(eq["remainingSolidBoundsKg"], [sol_s, sol_s])
            self.assertEqual(eq["remainingLiquidBoundsKg"], [liq_s, liq_s])

        # 5) duration == 0 with regime (a) -> coexisting, exhaustedAtStart=False.
        d0_in = investigate(LINK, "cold", "273.15", "334000", "1", "0", "0")
        self.assertEqual(d0_in["plateauStatus"], "coexisting")
        self.assertIs(d0_in["exhaustedAtStart"], False)

        # 6) Regime (d) CR-11: unresolved sign straddle still refuses even at duration == 0.
        law_star = terminal_response(*LEFT)
        wide_law = {
            **law_star,
            "supplyResponseBoundsWPerK": {
                **law_star["supplyResponseBoundsWPerK"],
                "middle": {"warm": ["-3", "-1"], "middle": ["4", "8"], "cool": ["-5", "-3"]},
            },
        }
        with self.assertRaisesRegex(ValueError, "latent heat-flow direction is unresolved"):
            plateau(wide_law, "middle", "310", "334000", "1", "0", "0")

        # 7) Untouched callers keep allow_pure=False refusal and emit no exhaustedAtStart / exhaustedPhase (CR-12).
        with self.assertRaises(ValueError):
            phase_inputs("273.15", "334000", "1", "0", "10")
        with self.assertRaises(ValueError):
            radial_phase_investigate(
                LINK, "hot", "cold", "273.15", "334000", "1", "0", "100",
                "0.1", [("0.2", "2")], "293.15", "0", "0.0000000567", "1",
                air_k="293.15", h_w_per_m2_k="10",
            )
        with self.assertRaises(ValueError):
            body_phase_investigate(LINK, "hot", "cold", "273.15", "334000", "1", "0", "200", "373.15", "100")

        rpb_ok = radial_phase_investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "5000",
            "0.1", [("0.20", "2")], "293.15", "0", "0.0000000567", "1",
            air_k="293.15", h_w_per_m2_k="10",
        )
        self.assertNotIn("exhaustedAtStart", rpb_ok)
        self.assertNotIn("exhaustedPhase", rpb_ok)
        pss_ok = shell_sizing_investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "1000",
            "0.1", [], "2", ["0.20"], "293.15", "0", "0.0000000567", "1",
            air_k="293.15", h_w_per_m2_k="10",
        )
        self.assertNotIn("exhaustedAtStart", pss_ok["sizes"][0])
        self.assertNotIn("exhaustedPhase", pss_ok["sizes"][0])
        rrs_ok = investigate_phase_dewar(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "300",
            "0.1", [("0.2", "2")], "0.8", "0.5", "0.8", "350", "0.0000000567",
        )
        self.assertNotIn("exhaustedAtStart", rrs_ok)
        self.assertNotIn("exhaustedPhase", rrs_ok)
