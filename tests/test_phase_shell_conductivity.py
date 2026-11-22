from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from qualification.h1_n13.conduction import interval
from tests.test_loaded_thermal_ports import LINK
from tests.test_phase_film_calibration import outward_decimal_band
from tests.test_terminal_response import CASES, STAR
from tools.phase_shell_conductivity import investigate, solve_from_law
from tools.radial_phase_bath import investigate as forward_phase
from tools.terminal_response import investigate as terminal_response


class PhaseShellConductivityTests(TestCase):
    def test_spherical_and_cylindrical_round_trips_across_exchange_modes(self):
        cases = (
            # (length, air_k, h, enc_k, eps, dur, k_true)
            (None, "293.15", "10", "300", "0.8", "120", "2"),       # spherical melting, mixed warm
            (None, "260", "5", "340", "0.8", "100", "2"),           # spherical melting, opposing fluxes
            (None, None, None, "320", "0.8", "100", "1.5"),         # spherical melting, pure radiation
            (None, "293.15", "10", "300", "0", "120", "2"),         # spherical melting, pure convection
            ("1", "310", "2", "240", "0.8", "200", "1.2"),          # cylindrical freezing, opposing fluxes
            ("1", "260", "5", "340", "0.8", "50", "0.75"),          # cylindrical melting, opposing fluxes
            ("1", None, None, "240", "0.9", "120", "1.5"),          # cylindrical freezing, pure radiation
            ("1", "250", "6", "300", "0", "150", "2"),              # cylindrical freezing, pure convection
        )
        for length, air, h, enc, eps, dur, k_true in cases:
            with self.subTest(length=length, air=air, h=h, enc=enc, eps=eps, k=k_true):
                fwd = forward_phase(
                    LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", dur,
                    "0.1", [("0.2", k_true)], enc, eps, "0.0000000567",
                    cylinder_length_m=length, air_k=air, h_w_per_m2_k=h,
                )
                self.assertEqual(fwd["plateauStatus"], "coexisting")
                slo, shi = map(F, fwd["remainingSolidBoundsKg"])
                m_band = outward_decimal_band(F("0.02") - shi, F("0.02") - slo, digits=12)

                inv = investigate(
                    LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", dur, m_band,
                    "0.1", [("0.2", "?")], enc, eps, "0.0000000567",
                    cylinder_length_m=length, air_k=air, h_w_per_m2_k=h,
                )
                k_lo, k_hi = map(F, inv["inferredConductivityBoundsWPerMK"])
                self.assertTrue(k_lo <= F(k_true) <= k_hi)
                self.assertLess(k_hi - k_lo, F(1, 10**6))
                self.assertEqual(inv["geometry"], "sphere" if length is None else "cylinder")
                self.assertEqual(inv["unknownLayerIndex"], 0)
                self.assertIsNone(inv["layers"][0]["conductivityWPerMK"])
                self.assertFalse(inv["nativeExecuted"])
                self.assertFalse(inv["nativeQualified"])
                if air is None:
                    self.assertNotIn("airTemperatureK", inv)
                else:
                    self.assertEqual(inv["airTemperatureK"], str(F(air)))
                    self.assertEqual(inv["convectionCoefficientWPerM2K"], str(F(h)))

                bal = interval(inv["inferredBathInflowBoundsW"]) + interval(inv["outwardHeatRateBoundsW"])
                self.assertTrue(bal.low <= 0 <= bal.high)

    def test_multilayer_buried_unknown_layer_at_each_position(self):
        true_layers = [("0.15", "3"), ("0.22", "1.2"), ("0.30", "0.8")]
        for length, air, h, enc, dur in (
            (None, "293.15", "10", "310", "120"),
            ("1", "310", "4", "240", "150"),
        ):
            fwd = forward_phase(
                LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", dur,
                "0.1", true_layers, enc, "0.8", "0.0000000567",
                cylinder_length_m=length, air_k=air, h_w_per_m2_k=h,
            )
            self.assertEqual(fwd["plateauStatus"], "coexisting")
            slo, shi = map(F, fwd["remainingSolidBoundsKg"])
            m_band = outward_decimal_band(F("0.02") - shi, F("0.02") - slo, digits=12)

            for idx, (_, k_true) in enumerate(true_layers):
                with self.subTest(length=length, unknown_index=idx):
                    masked = [(r, "?" if i == idx else k) for i, (r, k) in enumerate(true_layers)]
                    inv = investigate(
                        LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", dur, m_band,
                        "0.1", masked, enc, "0.8", "0.0000000567",
                        cylinder_length_m=length, air_k=air, h_w_per_m2_k=h,
                    )
                    k_lo, k_hi = map(F, inv["inferredConductivityBoundsWPerMK"])
                    self.assertTrue(k_lo <= F(k_true) <= k_hi)
                    self.assertLess(k_hi - k_lo, F(1, 10**5))
                    self.assertEqual(inv["unknownLayerIndex"], idx)
                    self.assertEqual(len(inv["layers"]), 3)
                    self.assertIsNone(inv["layers"][idx]["conductivityWPerMK"])

    def test_independent_mpmath_check_for_wide_measurement_band(self):
        # Spherical ice vessel, melting band [0.009, 0.010] kg in 120 s with known h=10, eps=0.8.
        inv = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
            ("0.009", "0.010"), "0.1", [("0.2", "?")], "300", "0.8", "0.0000000567",
            air_k="293.15", h_w_per_m2_k="10",
        )
        k_lo, k_hi = map(F, inv["inferredConductivityBoundsWPerMK"])
        with mp.workdps(110):
            area = mp.mpf("0.16") * mp.pi
            geom = (mp.mpf(1) / mp.mpf("0.1") - mp.mpf(1) / mp.mpf("0.2")) / (4 * mp.pi)
            sigma = mp.mpf("0.0000000567")
            r_port = mp.mpf("0.5")
            for dm_str in ("0.009", "0.0095", "0.010"):
                q_phase = mp.mpf(dm_str) * 334000 / 120
                q_shell = -q_phase
                flux = q_shell / area
                t_s = mp.findroot(
                    lambda t: 10 * (t - mp.mpf("293.15")) + mp.mpf("0.8") * sigma * (t**4 - mp.mpf("300")**4) - flux,
                    mp.mpf("290"),
                )
                r_shell = (mp.mpf("273.15") - t_s) / q_shell - r_port
                k_val = geom / r_shell
                self.assertTrue(k_lo <= F(mp.nstr(k_val, 95)) <= k_hi)

    def test_multi_reservoir_star_inverse_conductivity(self):
        case = CASES / "star"
        inputs = (case / "study.json", case, case / "facts.json", STAR)
        fwd = forward_phase(
            inputs, "warm", "cool", "300", "1000", "1", "1", "10",
            "0.1", [("0.2", "2")], "260", "0.8", "0.0000000567",
            air_k="280", h_w_per_m2_k="6",
        )
        self.assertEqual(fwd["plateauStatus"], "coexisting")
        slo, shi = map(F, fwd["remainingSolidBoundsKg"])
        m_band = outward_decimal_band(F(1) - shi, F(1) - slo, digits=12)

        inv = investigate(
            inputs, "warm", "cool", "300", "1000", "1", "1", "10", m_band,
            "0.1", [("0.2", "?")], "260", "0.8", "0.0000000567",
            air_k="280", h_w_per_m2_k="6",
        )
        k_lo, k_hi = map(F, inv["inferredConductivityBoundsWPerMK"])
        self.assertTrue(k_lo <= F(2) <= k_hi)
        self.assertLess(k_hi - k_lo, F(1, 10**6))

        bal = (interval(inv["inferredBathInflowBoundsW"])
               + interval(inv["maintainedReservoirInflowBoundsW"]["middle"])
               + interval(inv["outwardHeatRateBoundsW"]))
        self.assertTrue(bal.low <= 0 <= bal.high)

    def test_refusals_for_unidentifiability_unphysical_measurements_and_invalid_inputs(self):
        # Exhausted solid or liquid inventory.
        for bad_mass in (("0.01", "0.02"), ("-0.03", "-0.01"), ("0.025", "0.026")):
            with self.assertRaisesRegex(ValueError, "strictly below initial"):
                investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                            bad_mass, "0.1", [("0.2", "?")], "300", "0.8", "0.0000000567",
                            air_k="293.15", h_w_per_m2_k="10")

        # Unordered mass bounds and zero duration.
        with self.assertRaisesRegex(ValueError, "ordered melted mass"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                        ("0.010", "0.009"), "0.1", [("0.2", "?")], "300", "0.8", "0.0000000567",
                        air_k="293.15", h_w_per_m2_k="10")
        with self.assertRaisesRegex(ValueError, "positive exposure duration"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "0",
                        ("0.005", "0.006"), "0.1", [("0.2", "?")], "300", "0.8", "0.0000000567",
                        air_k="293.15", h_w_per_m2_k="10")

        # Zero or sign-straddling shell heat rate cannot identify layer conductivity
        # (including exact opposing convection/radiation equilibrium).
        for zero_band in (("0", "0"), ("-0.001", "0.001")):
            with self.assertRaisesRegex(ValueError, "nonzero shell heat rate"):
                investigate(LINK, "hot", "cold", "300", "334000", "0.02", "0.03", "100",
                            zero_band, "0.1", [("0.2", "?")], "290", "1", "0.00000005",
                            air_k="351.3595", h_w_per_m2_k="1")

        # Adiabatic exterior (both h=0 and eps=0, or omitted air/h with eps=0).
        with self.assertRaisesRegex(ValueError, "nonzero exterior heat exchange"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                        ("0.005", "0.005"), "0.1", [("0.2", "?")], "300", "0", "0.0000000567",
                        air_k="293.15", h_w_per_m2_k="0")
        with self.assertRaisesRegex(ValueError, "nonzero exterior heat exchange"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                        ("0.005", "0.005"), "0.1", [("0.2", "?")], "300", "0", "0.0000000567")

        # Partial air_k / h specification.
        with self.assertRaisesRegex(ValueError, "together"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                        ("0.005", "0.005"), "0.1", [("0.2", "?")], "300", "0.8", "0.0000000567",
                        air_k="293.15")

        # Measured melt rate exceeds even the k_u = infinity (zero layer resistance) limit,
        # both for a single layer and when a known layer already accounts for more resistance.
        with self.assertRaisesRegex(ValueError, "positive thermal resistance"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                        ("0.018", "0.019"), "0.1", [("0.2", "?")], "300", "0.8", "0.0000000567",
                        air_k="293.15", h_w_per_m2_k="10")
        with self.assertRaisesRegex(ValueError, "positive thermal resistance"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                        ("0.0095", "0.0096"), "0.1", [("0.15", "0.2"), ("0.2", "?")], "300", "0.8", "0.0000000567",
                        air_k="293.15", h_w_per_m2_k="10")

        # Wrong-sign heat flow (melting when both air and enclosure are colder than the bath).
        with self.assertRaisesRegex(ValueError, "positive thermal resistance"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                        ("0.005", "0.005"), "0.1", [("0.2", "?")], "250", "0.8", "0.0000000567",
                        air_k="250", h_w_per_m2_k="10")

        # Extreme freezing rate implying negative Kelvin inner shell temperature.
        with self.assertRaisesRegex(ValueError, "inner shell temperature must be nonnegative"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "0.1",
                        ("-0.029", "-0.029"), "0.1", [("0.2", "?")], "250", "0.8", "0.0000000567",
                        air_k="250", h_w_per_m2_k="10")

        # Extreme melting rate implying negative Kelvin outer surface temperature (flux < min_flux).
        with self.assertRaisesRegex(ValueError, "outer surface temperature must be nonnegative"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "1", "1", "10",
                        ("0.5", "0.5"), "0.1", [("0.2", "?")], "280", "0.8", "0.0000000567",
                        air_k="280", h_w_per_m2_k="10")

        # Layer specification errors: zero unknowns, two unknowns, non-increasing radii, non-positive known k.
        for bad_layers, msg in (
            ([("0.2", "2")], "exactly one unknown layer"),
            ([("0.15", "?"), ("0.2", "?")], "exactly one unknown layer"),
            ([("0.1", "?")], "strictly increasing"),
            ([("0.15", "0"), ("0.2", "?")], "positive conductivity"),
        ):
            with self.assertRaisesRegex(ValueError, msg):
                investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                            ("0.0095", "0.0096"), "0.1", bad_layers, "300", "0.8", "0.0000000567",
                            air_k="293.15", h_w_per_m2_k="10")

        # Distinct ports and thermally decoupled ports.
        with self.assertRaisesRegex(ValueError, "distinct phase and shell ports"):
            investigate(LINK, "hot", "hot", "273.15", "334000", "0.02", "0.03", "120",
                        ("0.0095", "0.0096"), "0.1", [("0.2", "?")], "300", "0.8", "0.0000000567",
                        air_k="293.15", h_w_per_m2_k="10")

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
                           ("0.0095", "0.0096"), "0.1", [("0.2", "?")], "300", "0.8", "0.0000000567",
                           air_k="293.15", h_w_per_m2_k="10")
