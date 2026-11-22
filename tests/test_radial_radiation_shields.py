from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from qualification.h1_n13.conduction import interval
from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.radial_phase_bath import investigate as unshielded_phase_bath
from tools.radial_radiation_shields import investigate, investigate_phase_dewar
from tools.radiating_radial_layers import investigate as unshielded_radial


class RadialRadiationShieldsTests(TestCase):
    def test_blackbody_enclosure_without_shields_matches_radiating_radial_layers(self):
        for length, enc_k in ((None, "280"), ("1", "450")):
            with self.subTest(length=length, enc_k=enc_k):
                base = unshielded_radial(
                    LINK, "cold", "0.1", [("0.2", "2"), ("0.4", "1")],
                    enc_k, "0.8", "0.0000000567", cylinder_length_m=length,
                )
                shielded = investigate(
                    LINK, "cold", "0.1", [("0.2", "2"), ("0.4", "1")],
                    "0.8", "0.6", "1", enc_k, "0.0000000567",
                    shields=(), cylinder_length_m=length,
                )
                self.assertEqual(shielded["shieldsInnerToOuter"], [])
                self.assertFalse(shielded["nativeExecuted"])
                self.assertFalse(shielded["nativeQualified"])
                for key_s, key_b in (("outwardHeatRateBoundsW", "outwardHeatRateBoundsW"),):
                    s_lo, s_hi = map(F, shielded[key_s])
                    b_lo, b_hi = map(F, base[key_b])
                    self.assertLessEqual(max(s_lo, b_lo), min(s_hi, b_hi))
                    self.assertLess(max(s_hi, b_hi) - min(s_lo, b_lo), F(1, 10**12))
                ts_lo, ts_hi = map(F, shielded["surfaces"][-1]["temperatureBoundsK"])
                tb_lo, tb_hi = map(F, base["surfaces"][-1]["temperatureBoundsK"])
                self.assertLessEqual(max(ts_lo, tb_lo), min(ts_hi, tb_hi))
                self.assertLess(max(ts_hi, tb_hi) - min(ts_lo, tb_lo), F(1, 10**12))

    def test_spherical_and_cylindrical_multishield_independent_mpmath(self):
        # Verify 2 concentric asymmetric shields against 110-digit mpmath in both geometries,
        # for both outward (hot core -> cold enclosure) and inward (cold core <- hot enclosure) flow.
        cases = (
            (None, "280", [("0.25", "0.2", "0.3"), ("0.32", "0.15", "0.25")], "0.5", "0.6"),
            ("1", "450", [("0.25", "0.2", "0.3"), ("0.32", "0.15", "0.25")], "0.5", "0.6"),
        )
        for length, enc_k, shields, r_enc, eps_enc in cases:
            with self.subTest(length=length, enc_k=enc_k):
                res = investigate(
                    LINK, "cold", "0.1", [("0.2", "2")], "0.8", r_enc, eps_enc,
                    enc_k, "0.0000000567", shields=shields, cylinder_length_m=length,
                )
                q_lo, q_hi = map(F, res["outwardHeatRateBoundsW"])
                ts_lo, ts_hi = map(F, res["surfaces"][-1]["temperatureBoundsK"])
                t1_lo, t1_hi = map(F, res["shieldsInnerToOuter"][0]["temperatureBoundsK"])
                t2_lo, t2_hi = map(F, res["shieldsInnerToOuter"][1]["temperatureBoundsK"])

                with mp.workdps(110):
                    sigma = mp.mpf("0.0000000567")
                    t_open = mp.mpf("380")
                    t_env = mp.mpf(enc_k)
                    r_port = mp.mpf("0.5")
                    if length is None:
                        r_shell = (mp.mpf(1) / mp.mpf("0.1") - mp.mpf(1) / mp.mpf("0.2")) / (4 * mp.pi * 2)
                        area = lambda r: 4 * mp.pi * r * r
                    else:
                        r_shell = mp.log(mp.mpf("0.2") / mp.mpf("0.1")) / (2 * mp.pi * mp.mpf(length) * 2)
                        area = lambda r: 2 * mp.pi * mp.mpf(length) * r
                    r_tot = r_port + r_shell

                    r0, r1, r2, r3 = map(mp.mpf, ("0.2", "0.25", "0.32", r_enc))
                    rg0 = 1 / (area(r0) * mp.mpf("0.8")) + (1 / mp.mpf("0.2") - 1) / area(r1)
                    rg1 = 1 / (area(r1) * mp.mpf("0.3")) + (1 / mp.mpf("0.15") - 1) / area(r2)
                    rg2 = 1 / (area(r2) * mp.mpf("0.25")) + (1 / mp.mpf(eps_enc) - 1) / area(r3)
                    rg_tot = rg0 + rg1 + rg2

                    t_s = mp.findroot(
                        lambda t: (t_open - t) / r_tot - sigma * (t**4 - t_env**4) / rg_tot,
                        (t_open + t_env) / 2,
                    )
                    q_exact = (t_open - t_s) / r_tot
                    t1_exact = (t_s**4 - q_exact * rg0 / sigma) ** mp.mpf("0.25")
                    t2_exact = (t1_exact**4 - q_exact * rg1 / sigma) ** mp.mpf("0.25")

                    self.assertTrue(q_lo <= F(mp.nstr(q_exact, 95)) <= q_hi)
                    self.assertTrue(ts_lo <= F(mp.nstr(t_s, 95)) <= ts_hi)
                    self.assertTrue(t1_lo <= F(mp.nstr(t1_exact, 95)) <= t1_hi)
                    self.assertTrue(t2_lo <= F(mp.nstr(t2_exact, 95)) <= t2_hi)
                    self.assertLess(q_hi - q_lo, F(1, 10**6))

    def test_inner_placed_concentric_shield_reduces_heat_leak_more_than_outer_placed(self):
        # For concentric spheres/cylinders, a smaller-radius shield has smaller area A_1,
        # hence higher radiative resistance (2/eps - 1)/A_1 and lower heat leak |Q|.
        for length in (None, "1"):
            with self.subTest(length=length):
                inner_shield = investigate(
                    LINK, "cold", "0.1", [("0.2", "2")], "0.5", "0.6", "0.5",
                    "280", "0.0000000567", shields=[("0.22", "0.1", "0.1")],
                    cylinder_length_m=length,
                )
                outer_shield = investigate(
                    LINK, "cold", "0.1", [("0.2", "2")], "0.5", "0.6", "0.5",
                    "280", "0.0000000567", shields=[("0.55", "0.1", "0.1")],
                    cylinder_length_m=length,
                )
                self.assertLess(F(inner_shield["outwardHeatRateBoundsW"][1]),
                                F(outer_shield["outwardHeatRateBoundsW"][0]))

    def test_perfect_reflector_breaks_and_undetermined_isolated_shield(self):
        # Single perfect mirror on outer face of shield 0 -> Q = 0, shield 0 equilibrates
        # to inner shell (380 K), shield 1 equilibrates to enclosure (280 K).
        one_break = investigate(
            LINK, "cold", "0.1", [("0.2", "2")], "0.8", "0.5", "0.8",
            "280", "0.0000000567",
            shields=[("0.25", "0.5", "0"), ("0.35", "0.5", "0.5")],
        )
        self.assertEqual(one_break["outwardHeatRateBoundsW"], ["0", "0"])
        self.assertEqual(one_break["effectiveRadiativeConductanceBoundsWPerK4"], ["0", "0"])
        self.assertEqual(one_break["shieldsInnerToOuter"][0]["temperatureBoundsK"], ["380", "380"])
        self.assertEqual(one_break["shieldsInnerToOuter"][0]["temperatureStatus"], "bounded")
        self.assertEqual(one_break["shieldsInnerToOuter"][1]["temperatureBoundsK"], ["280", "280"])
        self.assertEqual(one_break["shieldsInnerToOuter"][1]["temperatureStatus"], "bounded")

        # Two-sided perfect mirror on shield 0 -> breaks at gaps 0 and 1 -> shield 0 undetermined,
        # shield 1 coupled to enclosure (280 K).
        isolated = investigate(
            LINK, "cold", "0.1", [("0.2", "2")], "0.8", "0.5", "0.8",
            "280", "0.0000000567",
            shields=[("0.25", "0", "0"), ("0.35", "0.5", "0.5")],
        )
        self.assertEqual(isolated["outwardHeatRateBoundsW"], ["0", "0"])
        self.assertIsNone(isolated["shieldsInnerToOuter"][0]["temperatureBoundsK"])
        self.assertEqual(isolated["shieldsInnerToOuter"][0]["temperatureStatus"], "undetermined")
        self.assertEqual(isolated["shieldsInnerToOuter"][1]["temperatureBoundsK"], ["280", "280"])

        # Exact isothermal equilibrium with active shields: zero heat rate, exact shield T.
        iso = investigate(
            LINK, "cold", "0.1", [("0.2", "2")], "0.8", "0.5", "0.8",
            "380", "0.0000000567", shields=[("0.25", "0.2", "0.3"), ("0.35", "0.4", "0.5")],
        )
        self.assertEqual(iso["outwardHeatRateBoundsW"], ["0", "0"])
        for s in iso["shieldsInnerToOuter"]:
            self.assertEqual(s["temperatureBoundsK"], ["380", "380"])
            self.assertEqual(s["temperatureStatus"], "bounded")

    def test_dewar_phase_bath_hold_time_extended_by_shields_and_star_balance(self):
        # Spherical ice Dewar facing a 350 K blackbody enclosure: unshielded vs 2 low-eps shields.
        bare = unshielded_phase_bath(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "300",
            "0.1", [("0.2", "2")], "350", "0.8", "0.0000000567",
        )
        dewar_bare = investigate_phase_dewar(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "300",
            "0.1", [("0.2", "2")], "0.8", "0.5", "1", "350", "0.0000000567",
            shields=(),
        )
        for key in ("remainingSolidBoundsKg", "exhaustionTimeBoundsS"):
            d_lo, d_hi = map(F, dewar_bare[key])
            b_lo, b_hi = map(F, bare[key])
            self.assertLessEqual(max(d_lo, b_lo), min(d_hi, b_hi))
            self.assertLess(max(d_hi, b_hi) - min(d_lo, b_lo), F(1, 10**12))

        dewar_shielded = investigate_phase_dewar(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "300",
            "0.1", [("0.2", "2")], "0.8", "0.5", "0.8", "350", "0.0000000567",
            shields=[("0.25", "0.05", "0.05"), ("0.35", "0.05", "0.05")],
        )
        self.assertEqual(dewar_shielded["schema"], "sim_heat.offline_radial_shielded_phase_bath/1")
        self.assertEqual(dewar_shielded["plateauStatus"], "coexisting")
        # Shields drastically extend exhaustion time and leave much more ice intact.
        self.assertGreater(F(dewar_shielded["exhaustionTimeBoundsS"][0]),
                           10 * F(dewar_bare["exhaustionTimeBoundsS"][1]))
        self.assertGreater(F(dewar_shielded["remainingSolidBoundsKg"][0]),
                           F(dewar_bare["remainingSolidBoundsKg"][1]))

        # Multi-reservoir STAR Dewar obeys steady energy conservation.
        case = CASES / "star"
        inputs = (case / "study.json", case, case / "facts.json", STAR)
        star_dewar = investigate_phase_dewar(
            inputs, "warm", "cool", "300", "1000", "1", "1", "10",
            "0.1", [("0.2", "2")], "0.8", "0.5", "0.7", "260", "0.0000000567",
            shields=[("0.3", "0.1", "0.2")],
        )
        bal = (interval(star_dewar["bathInflowDuringPlateauBoundsW"])
               + interval(star_dewar["maintainedReservoirInflowBoundsW"]["middle"])
               + interval(star_dewar["shieldedRadialShell"]["outwardHeatRateBoundsW"]))
        self.assertTrue(bal.low <= 0 <= bal.high)

    def test_refusals_for_invalid_radii_emissivities_and_ports(self):
        # Non-increasing shield radii.
        with self.assertRaisesRegex(ValueError, "strictly increasing concentric radii"):
            investigate(LINK, "cold", "0.1", [("0.2", "2")], "0.8", "0.5", "0.8",
                        "280", "0.0000000567", shields=[("0.2", "0.2", "0.2")])
        with self.assertRaisesRegex(ValueError, "strictly increasing concentric radii"):
            investigate(LINK, "cold", "0.1", [("0.2", "2")], "0.8", "0.5", "0.8",
                        "280", "0.0000000567", shields=[("0.3", "0.2", "0.2"), ("0.3", "0.2", "0.2")])

        # Enclosure radius not exceeding outermost shell/shield.
        with self.assertRaisesRegex(ValueError, "enclosure radius must exceed"):
            investigate(LINK, "cold", "0.1", [("0.2", "2")], "0.8", "0.2", "0.8",
                        "280", "0.0000000567", shields=())
        with self.assertRaisesRegex(ValueError, "enclosure radius must exceed"):
            investigate(LINK, "cold", "0.1", [("0.2", "2")], "0.8", "0.3", "0.8",
                        "280", "0.0000000567", shields=[("0.3", "0.2", "0.2")])

        # Emissivities > 1 or sigma <= 0.
        with self.assertRaisesRegex(ValueError, "emissivities in"):
            investigate(LINK, "cold", "0.1", [("0.2", "2")], "1.1", "0.5", "0.8",
                        "280", "0.0000000567")
        with self.assertRaisesRegex(ValueError, "emissivities in"):
            investigate(LINK, "cold", "0.1", [("0.2", "2")], "0.8", "0.5", "0.8",
                        "280", "0.0000000567", shields=[("0.3", "1.2", "0.2")])
        with self.assertRaisesRegex(ValueError, "positive sigma"):
            investigate(LINK, "cold", "0.1", [("0.2", "2")], "0.8", "0.5", "0.8",
                        "280", "0")

        # Malformed shield entry and duplicate phase/surface ports.
        with self.assertRaisesRegex(ValueError, "radius, inner emissivity, and outer emissivity"):
            investigate(LINK, "cold", "0.1", [("0.2", "2")], "0.8", "0.5", "0.8",
                        "280", "0.0000000567", shields=[("0.3", "0.2")])
        with self.assertRaisesRegex(ValueError, "distinct phase and shell ports"):
            investigate_phase_dewar(
                LINK, "hot", "hot", "273.15", "334000", "0.02", "0.03", "300",
                "0.1", [("0.2", "2")], "0.8", "0.5", "0.8", "350", "0.0000000567",
            )
