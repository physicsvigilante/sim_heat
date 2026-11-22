from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from qualification.h1_n13.conduction import interval
from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.phase_film_calibration import investigate, solve_from_law
from tools.radial_phase_bath import investigate as forward_phase
from tools.terminal_response import investigate as terminal_response


def outward_decimal_band(low_f, high_f, digits=12):
    scale = 10**digits
    lo_tick = int(low_f * scale)
    if F(lo_tick, scale) > low_f:
        lo_tick -= 1
    hi_tick = int(high_f * scale)
    if F(hi_tick, scale) < high_f:
        hi_tick += 1

    def fmt(tick):
        sign = "-" if tick < 0 else ""
        mag = abs(tick)
        return f"{sign}{mag // scale}.{mag % scale:0{digits}d}"

    return (fmt(lo_tick), fmt(hi_tick))


class PhaseFilmCalibrationTests(TestCase):
    def test_spherical_and_cylindrical_round_trip_with_opposing_fluxes(self):
        cases = (
            # (length, air_k, h_true, enc_k, duration_s)
            (None, "293.15", "10", "300", "120"),     # spherical melting, both warm
            (None, "260", "5", "340", "100"),         # spherical melting, cold air vs hot enclosure
            ("1", "310", "2", "240", "200"),          # cylindrical freezing, warm air vs cold enclosure
            ("1", "260", "5", "340", "50"),           # cylindrical melting, cold air vs hot enclosure
        )
        for length, air, h_true, enc, dur in cases:
            with self.subTest(length=length, air=air, h=h_true, enc=enc):
                fwd = forward_phase(
                    LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", dur,
                    "0.1", [("0.2", "2")], enc, "0.8", "0.0000000567",
                    cylinder_length_m=length, air_k=air, h_w_per_m2_k=h_true,
                )
                self.assertEqual(fwd["plateauStatus"], "coexisting")
                slo, shi = map(F, fwd["remainingSolidBoundsKg"])
                # Converted mass = initial_solid - remaining_solid
                m_band = outward_decimal_band(F("0.02") - shi, F("0.02") - slo, digits=12)

                inv = investigate(
                    LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", dur, m_band,
                    "0.1", [("0.2", "2")], air, enc, "0.8", "0.0000000567",
                    cylinder_length_m=length,
                )
                h_lo, h_hi = map(F, inv["convectionCoefficientBoundsWPerM2K"])
                self.assertTrue(h_lo <= F(h_true) <= h_hi)
                self.assertLess(h_hi - h_lo, F(1, 10**6))
                self.assertEqual(inv["geometry"], "sphere" if length is None else "cylinder")
                self.assertFalse(inv["nativeExecuted"])
                self.assertFalse(inv["nativeQualified"])

                # Energy balance checks: Q_phase + Q_shell = 0 and Q_shell = Q_air + Q_enc
                b_net = interval(inv["inferredBathInflowBoundsW"]) + interval(inv["outwardHeatRateBoundsW"])
                self.assertTrue(b_net.low <= 0 <= b_net.high)
                b_ext = (interval(inv["outwardHeatRateBoundsW"])
                         - interval(inv["netHeatToAirBoundsW"])
                         - interval(inv["netHeatToEnclosureBoundsW"]))
                self.assertTrue(b_ext.low <= 0 <= b_ext.high)

    def test_independent_mpmath_check_for_wide_measurement_band(self):
        # Spherical ice vessel, melting band [0.009, 0.010] kg in 120 s.
        inv = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
            ("0.009", "0.010"), "0.1", [("0.2", "2")], "293.15", "300", "0.8", "0.0000000567",
        )
        h_lo, h_hi = map(F, inv["convectionCoefficientBoundsWPerM2K"])
        with mp.workdps(110):
            r_tot = mp.mpf("0.5") + 5 / (8 * mp.pi)
            area = mp.mpf("0.16") * mp.pi
            sigma = mp.mpf("0.0000000567")
            for dm_str in ("0.009", "0.0095", "0.010"):
                q_phase = mp.mpf(dm_str) * 334000 / 120
                q_shell = -q_phase
                t_s = mp.mpf("273.15") - r_tot * q_shell
                q_rad = area * mp.mpf("0.8") * sigma * (t_s**4 - mp.mpf("300")**4)
                h_val = (q_shell - q_rad) / (area * (t_s - mp.mpf("293.15")))
                self.assertTrue(h_lo <= F(mp.nstr(h_val, 95)) <= h_hi)

    def test_exact_zero_melt_identifies_opposing_film_and_zero_film(self):
        # Zero net melting at 300 K with 290 K enclosure and 351.3595 K air:
        # radiation loss 51.3595 W/m^2 must be balanced by convection -> exact h = 1.
        r1 = investigate(
            LINK, "hot", "cold", "300", "334000", "0.02", "0.03", "100",
            ("0", "0"), "0.1", [("0.2", "2")], "351.3595", "290", "1", "0.00000005",
        )
        h_lo, h_hi = map(F, r1["convectionCoefficientBoundsWPerM2K"])
        self.assertTrue(h_lo <= F(1) <= h_hi)
        self.assertLess(h_hi - h_lo, F(1, 10**50))
        self.assertEqual(r1["outwardHeatRateBoundsW"], ["0", "0"])
        self.assertEqual(r1["outerSurfaceTemperatureBoundsK"], ["300", "300"])

        # Zero melting with eps=0 (or env==300) and air != 300 K -> exact h = 0.
        for eps, env in (("0", "290"), ("1", "300")):
            r0 = investigate(
                LINK, "hot", "cold", "300", "334000", "0.02", "0.03", "100",
                ("0", "0"), "0.1", [("0.2", "2")], "350", env, eps, "0.00000005",
            )
            self.assertEqual(r0["convectionCoefficientBoundsWPerM2K"], ["0", "0"])

    def test_multi_reservoir_star_inverse_calibration(self):
        case = CASES / "star"
        inputs = (case / "study.json", case, case / "facts.json", STAR)
        fwd = forward_phase(
            inputs, "warm", "cool", "300", "1000", "1", "1", "10",
            "0.1", [("0.2", "2")], "260", "0.8", "0.0000000567",
            air_k="280", h_w_per_m2_k="6",
        )
        slo, shi = map(F, fwd["remainingSolidBoundsKg"])
        m_band = outward_decimal_band(F(1) - shi, F(1) - slo, digits=12)

        inv = investigate(
            inputs, "warm", "cool", "300", "1000", "1", "1", "10", m_band,
            "0.1", [("0.2", "2")], "280", "260", "0.8", "0.0000000567",
        )
        h_lo, h_hi = map(F, inv["convectionCoefficientBoundsWPerM2K"])
        self.assertTrue(h_lo <= F(6) <= h_hi)
        self.assertLess(h_hi - h_lo, F(1, 10**6))

        bal = (interval(inv["inferredBathInflowBoundsW"])
               + interval(inv["maintainedReservoirInflowBoundsW"]["middle"])
               + interval(inv["outwardHeatRateBoundsW"]))
        self.assertTrue(bal.low <= 0 <= bal.high)

    def test_refusals_for_exhaustion_unidentifiability_and_invalid_inputs(self):
        # Exhausted solid or liquid inventory cannot identify the steady plateau rate.
        for bad_mass in (("0.01", "0.02"), ("-0.03", "-0.01"), ("0.025", "0.026")):
            with self.assertRaisesRegex(ValueError, "strictly below initial"):
                investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                            bad_mass, "0.1", [("0.2", "2")], "293.15", "300", "0.8", "0.0000000567")

        # Unordered melted mass bounds.
        with self.assertRaisesRegex(ValueError, "ordered melted mass"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                        ("0.010", "0.009"), "0.1", [("0.2", "2")], "293.15", "300", "0.8", "0.0000000567")

        # Zero duration.
        with self.assertRaisesRegex(ValueError, "positive exposure duration"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "0",
                        ("0.005", "0.006"), "0.1", [("0.2", "2")], "293.15", "300", "0.8", "0.0000000567")

        # Surface temperature equals air temperature -> unidentifiable h.
        with self.assertRaisesRegex(ValueError, "nonzero difference from air"):
            investigate(LINK, "hot", "cold", "300", "334000", "0.02", "0.03", "100",
                        ("0", "0"), "0.1", [("0.2", "2")], "300", "290", "0.8", "0.0000000567")

        # Incompatible sign -> implied h < 0 (melting when both air and enclosure are colder).
        with self.assertRaisesRegex(ValueError, "nonnegative convection coefficient"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                        ("0.005", "0.005"), "0.1", [("0.2", "2")], "250", "250", "0.8", "0.0000000567")

        # Extreme freezing rate implying negative Kelvin outer surface temperature.
        with self.assertRaisesRegex(ValueError, "nonnegative in Kelvin"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "0.1",
                        ("-0.029", "-0.029"), "0.1", [("0.2", "2")], "250", "250", "0.8", "0.0000000567")

        # Thermally decoupled phase and shell ports (zero mutual conductance).
        law = terminal_response(*LINK)
        decoupled = {
            **law,
            "supplyResponseBoundsWPerK": {
                **law["supplyResponseBoundsWPerK"],
                "hot": {**law["supplyResponseBoundsWPerK"]["hot"], "cold": ["0", "0"]},
            },
        }
        with self.assertRaisesRegex(ValueError, "not thermally coupled"):
            solve_from_law(decoupled, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                           ("0.005", "0.005"), "0.1", [("0.2", "2")], "293.15", "300", "0.8", "0.0000000567")
