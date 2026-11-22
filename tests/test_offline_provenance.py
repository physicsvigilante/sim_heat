from fractions import Fraction as F
from unittest import TestCase

from qualification.h1_n13.conduction import Box, prepare
from tests.test_join_thermal_networks import FULL
from tests.test_loaded_thermal_ports import LINK
from tests.test_temperature_passages import D1, D1_PIN, ROOT
from tests.test_terminal_response import CASES, STAR, TRIANGLE
from tools.body_phase_bath_exchange import solve_from_law as solve_body_phase
from tools.bounded_passages import read_pinned_facts, series_passages
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
from tools.rod_generation import generation_from_network
from tools.terminal_response import (
    investigate as terminal_response,
    prepare_steady_network,
    response_from_network,
)


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

    def test_prepared_object_producers_refuse_forged_flags_bad_digests_and_mixed_studies(self):
        # Issue #195 F2 witnesses: response_from_network, generation_from_network, series_passages.
        link_facts, link_cand, link_net = prepare_steady_network(*LINK)
        star_dir = CASES / "star"
        star_facts, star_cand, star_net = prepare_steady_network(
            star_dir / "study.json", star_dir, star_dir / "facts.json", STAR,
        )
        d1_path = ROOT / "h1/reference_cases/D1.json"
        d1_facts = read_pinned_facts(d1_path, D1_PIN)
        d1_cand = prepare(D1 / "study.json", D1, d1_path, D1_PIN)

        producers = (
            ("terminal_response.response_from_network",
             link_cand,
             lambda cand: response_from_network(link_facts, cand, link_net)),
            ("rod_generation.generation_from_network",
             link_cand,
             lambda cand: generation_from_network(link_facts, cand, link_net, [("insert", "1")])),
            ("bounded_passages.series_passages",
             d1_cand,
             lambda cand: series_passages(cand, d1_facts, "exports", "body.T",
                                          F("323.15"), ("cooling", "warming"))[3]),
        )
        for name, base_cand, fn in producers:
            with self.subTest(producer=name):
                for flag in OFFLINE_FLAG_KEYS:
                    with self.assertRaisesRegex(ValueError, f"refuses non-False {flag}"):
                        fn({**base_cand, flag: True})
                for key in SOURCE_HASH_KEYS:
                    with self.assertRaisesRegex(ValueError, f"valid 64-hex {key}"):
                        fn({**base_cand, key: "bad"})
                omitted = {k: v for k, v in base_cand.items() if k not in OFFLINE_FLAG_KEYS}
                out = fn(omitted)
                for flag in OFFLINE_FLAG_KEYS:
                    self.assertIs(out[flag], False)

        # Mixed-study witnesses: genuine objects from different studies must be refused,
        # including Y-Delta equivalent STAR vs TRIANGLE that share identical terminal names,
        # boundary temperatures, body inventory, and rod names but differ in graph topology.
        tri_dir = CASES / "triangle"
        _, _, tri_net = prepare_steady_network(
            tri_dir / "study.json", tri_dir, tri_dir / "facts.json", TRIANGLE,
        )
        with self.assertRaisesRegex(ValueError, "identities do not match"):
            response_from_network(star_facts, link_cand, star_net)
        with self.assertRaisesRegex(ValueError, "identities do not match"):
            generation_from_network(star_facts, link_cand, star_net, [("insert", "1")])
        with self.assertRaisesRegex(ValueError, "network does not match"):
            response_from_network(star_facts, star_cand, link_net)
        with self.assertRaisesRegex(ValueError, "network does not match"):
            response_from_network(star_facts, star_cand, tri_net, include_rods=True)
        with self.assertRaisesRegex(ValueError, "network does not match"):
            generation_from_network(star_facts, star_cand, tri_net, [("first", "1")])
        # Mutated ownerless junction inventory (STAR 160 W profiles=True witness) must refuse.
        star_net.junctions = []
        with self.assertRaisesRegex(ValueError, "junctions do not match"):
            generation_from_network(star_facts, star_cand, star_net, [("first", "160")], profiles=True)
        # Inconsistent two-junction interior weights that satisfy individual interval residuals
        # (FULL studies/joined_terminals witness) must still be refused.
        full_facts, full_cand, full_net = prepare_steady_network(*FULL)
        j_warm = next(i for i, n in enumerate(full_net.bodies + full_net.fixed)
                      if full_net.owner[n] == "warmL")
        full_net.weights["centre"][j_warm] = Box.exact(F(9, 20))
        full_net.weights["contact"][j_warm] = Box.bounds(F(0), F(1))
        with self.assertRaisesRegex(ValueError, "certified Dirichlet solution"):
            response_from_network(full_facts, full_cand, full_net)
        with self.assertRaisesRegex(ValueError, "identities do not match"):
            series_passages(d1_cand, link_facts, "exports", "body.T",
                            F("323.15"), ("cooling", "warming"))
