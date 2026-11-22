from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.body_phase_bath_exchange import solve_from_law as solve_body_phase
from tools.latent_heat_bath import phase_inputs, plateau_state
from tools.offline_provenance import OFFLINE_FLAG_KEYS, SOURCE_HASH_KEYS, offline_provenance
from tools.phase_film_calibration import solve_from_law as solve_film_cal
from tools.phase_shell_conductivity import solve_from_law as solve_shell_k
from tools.phase_shell_sizing import select_from_law as size_phase_shell
from tools.radial_exposure_sizing import select_from_law as size_exposure
from tools.radial_phase_bath import solve_from_law as solve_radial_phase
from tools.radial_phase_exposure import solve_from_law as solve_radial_exposure
from tools.radial_radiation_shields import solve as solve_shields, solve_phase_dewar
from tools.radiating_radial_layers import solve as solve_radial
from tools.radiating_surface import exterior_balance, physical_port
from tools.terminal_response import investigate as terminal_response


class OfflineProvenanceTests(TestCase):
    def setUp(self):
        self.law = terminal_response(*LINK)

    def test_helper_validates_digests_and_refuses_forged_or_malformed_flags(self):
        stamped = offline_provenance(self.law)
        for key in SOURCE_HASH_KEYS:
            self.assertEqual(stamped[key], self.law[key])
        for key in OFFLINE_FLAG_KEYS:
            self.assertIs(stamped[key], False)

        # Omitted flags on an otherwise valid law are stamped False explicitly.
        minimal = {k: self.law[k] for k in SOURCE_HASH_KEYS}
        stamped_min = offline_provenance(minimal)
        for key in OFFLINE_FLAG_KEYS:
            self.assertIs(stamped_min[key], False)

        # Forged True or wrong-type provenance flags must be refused.
        for flag in OFFLINE_FLAG_KEYS:
            for bad in (True, "false", 0, 1, None):
                with self.subTest(flag=flag, bad=bad):
                    with self.assertRaisesRegex(ValueError, f"refuses non-False {flag}"):
                        offline_provenance({**self.law, flag: bad})

        # Missing or malformed SHA-256 digests must be refused.
        for key in SOURCE_HASH_KEYS:
            for bad in (None, "", "abc123", "A" * 64, "g" * 64):
                with self.subTest(key=key, bad=bad):
                    with self.assertRaisesRegex(ValueError, f"valid 64-hex {key}"):
                        offline_provenance({**self.law, key: bad})

        with self.assertRaisesRegex(ValueError, "mapping required"):
            offline_provenance("not-a-dict")

    def test_direct_programmatic_solvers_refuse_forged_flags_and_stamp_omitted_flags_false(self):
        callers = (
            ("radiating_radial_layers.solve",
             lambda law: solve_radial(law, "cold", "0.1", [("0.2", "2")], "280", "0.8", "0.0000000567")),
            ("radial_phase_bath.solve_from_law",
             lambda law: solve_radial_phase(law, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                                            "0.1", [("0.2", "2")], "300", "0.8", "0.0000000567",
                                            air_k="293.15", h_w_per_m2_k="10")),
            ("phase_shell_sizing.size_from_law",
             lambda law: size_phase_shell(law, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                                          "0.1", [], "2", ["0.2"], "300", "0.8", "0.0000000567",
                                          air_k="293.15", h_w_per_m2_k="10")),
            ("radial_phase_exposure.solve_from_law",
             lambda law: solve_radial_exposure(law, "hot", "cold", "273.15", "334000", "0.02", "0.03",
                                               "0.1", [("0.2", "2")], "0.8", "0.0000000567",
                                               [("day", "293.15", "10", "300", "60")])),
            ("radial_exposure_sizing.size_from_law",
             lambda law: size_exposure(law, "hot", "cold", "273.15", "334000", "0.02", "0.03",
                                       "0.1", [], "2", ["0.2"], "0.8", "0.0000000567",
                                       [("day", "293.15", "10", "300", "60")])),
            ("phase_film_calibration.solve_from_law",
             lambda law: solve_film_cal(law, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                                        ("0.0095", "0.0096"), "0.1", [("0.2", "2")], "293.15", "300",
                                        "0.8", "0.0000000567")),
            ("phase_shell_conductivity.solve_from_law",
             lambda law: solve_shell_k(law, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                                       ("0.0095", "0.0096"), "0.1", [("0.2", "?")], "300", "0.8",
                                       "0.0000000567", air_k="293.15", h_w_per_m2_k="10")),
            ("radial_radiation_shields.solve",
             lambda law: solve_shields(law, "cold", "0.1", [("0.2", "2")], "0.8", "0.5", "0.8",
                                       "280", "0.0000000567", shields=[("0.3", "0.1", "0.1")])),
            ("radial_radiation_shields.solve_phase_dewar",
             lambda law: solve_phase_dewar(law, "hot", "cold", "273.15", "334000", "0.02", "0.03", "120",
                                           "0.1", [("0.2", "2")], "0.8", "0.5", "0.8", "350",
                                           "0.0000000567", shields=[("0.3", "0.1", "0.1")])),
            ("body_phase_bath_exchange.solve_from_law",
             lambda law: solve_body_phase(law, "hot", "cold", "273.15", "334000", "0.02", "0.03",
                                          "200", "373.15", "20")),
            ("radiating_surface.exterior_balance",
             lambda law: exterior_balance(law, "cold", *physical_port(law, "cold"),
                                          F("280"), F("1"), F("0.8"), F("0.0000000567"),
                                          air_k=None, h_w_per_m2_k=None)),
            ("latent_heat_bath.plateau_state",
             lambda law: plateau_state(law, "cold", phase_inputs("273.15", "334000", "0.5", "0.1", "10"),
                                       F("10"), F("10"), {})),
        )
        omitted_flags_law = {k: v for k, v in self.law.items() if k not in OFFLINE_FLAG_KEYS}
        for name, fn in callers:
            with self.subTest(solver=name):
                for forged in OFFLINE_FLAG_KEYS:
                    with self.assertRaisesRegex(ValueError, f"refuses non-False {forged}"):
                        fn({**self.law, forged: True})
                out = fn(omitted_flags_law)
                for flag in OFFLINE_FLAG_KEYS:
                    self.assertIs(out[flag], False)
