"""M03 physical composability, DerivedLaw (F-05/F-08), ThermalSystem, H1 AST adapter, and oracles."""
from __future__ import annotations

from fractions import Fraction as F
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import mpmath as mp

import simheat
from simheat.core import Box, Conduction, ExactBindings, pi_rational_enclosure, step_matrix
from simheat.laws import (
    DERIVED_LAW_SCHEMA,
    DerivedLaw,
    join_laws,
    validate_terminal_law,
)
from simheat.system import (
    RESULT_ENVELOPE_SCHEMA,
    THERMAL_SYSTEM_SCHEMA,
    ThermalSystem,
    describe_equations,
    solve_system,
)
from tools.body_phase_bath_exchange import solve_from_law as solve_body_phase_legacy
from tools.join_thermal_networks import investigate as join_legacy_investigate
from tools.latent_heat_bath import plateau as solve_latent_legacy
from tools.multibody_phase_network import solve_from_law as solve_multibody
from tools.multiport_thermal_network import solve_from_law as solve_multiport
from tools.phase_film_calibration import solve_from_law as solve_film_cal_legacy
from tools.phase_shell_conductivity import solve_from_law as solve_shell_k_legacy
from tools.radial_phase_bath import solve_from_law as solve_radial_bath_legacy
from tools.radial_phase_exposure import solve_from_law as solve_radial_exp_legacy
from tools.staged_phase_body_network import solve_from_law as solve_staged
from tools.terminal_response import investigate as terminal_response

ROOT = Path(__file__).resolve().parents[1]
COMPOSITE_WALL_FACTS_SHA = "f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b"
COMPOSITE_WALL_INPUTS = (
    ROOT / "studies/composite_wall/study.json",
    ROOT / "studies/composite_wall",
    ROOT / "studies/composite_wall/facts.json",
    COMPOSITE_WALL_FACTS_SHA,
)


def _in_bounds(val_mpf, pair):
    lo, hi = map(F, pair)
    v = F(mp.nstr(val_mpf, 60))
    return lo <= v <= hi


class M03CoreAndDerivedLawTests(unittest.TestCase):
    def test_neutral_core_reexports_without_touching_qualification(self):
        from qualification.h1_n11.rational_dynamic_proof import Box as QualBox
        from qualification.h1_n13.conduction import Conduction as QualConduction, step_matrix as qual_step

        self.assertIs(Box, QualBox)
        self.assertIs(Conduction, QualConduction)
        self.assertIs(step_matrix, qual_step)
        self.assertIs(simheat.Box, QualBox)
        self.assertTrue(callable(ExactBindings))
        pi_lo, pi_hi = pi_rational_enclosure()
        self.assertLess(pi_lo, F(31415926535897932384626433832796, 10**31))
        self.assertGreater(pi_hi, F(31415926535897932384626433832795, 10**31))

    def test_from_rods_exact_and_interval_enclose_all_corner_realizations(self):
        # Exact composite wall: G_facing=4, G_strip=1, G_insert=3 => G_eff = 4*4/8 = 2 W/K.
        exact_law = DerivedLaw.from_rods(
            nodes=["hot", "interface", "cold"],
            terminals=["hot", "cold"],
            rods={
                "facing": {"kind": "rod_area", "a": "hot", "b": "interface", "k": "20", "L": "0.1", "A": "0.02"},
                "strip": {"kind": "rod_area", "a": "interface", "b": "cold", "k": "10", "L": "0.1", "A": "0.01"},
                "insert": {"kind": "rod_area", "a": "cold", "b": "interface", "k": "30", "L": "0.1", "A": "0.01"},
            },
        )
        self.assertTrue(exact_law.is_exact_point)
        self.assertEqual(exact_law.matrix["hot"]["hot"], (F(2), F(2)))
        self.assertEqual(exact_law.matrix["hot"]["cold"], (F(-2), F(-2)))
        self.assertEqual(exact_law.matrix["cold"]["hot"], (F(-2), F(-2)))
        self.assertEqual(exact_law.matrix["cold"]["cold"], (F(2), F(2)))

        # Interval 3-terminal star with internal junction: verify enclosure of all 8 conductance corners.
        k_intervals = {
            "r1": ("19", "21"),
            "r2": ("9", "11"),
            "r3": ("28", "32"),
        }
        star_interval = DerivedLaw.from_rods(
            nodes=["a", "b", "c", "j"],
            terminals=["a", "b", "c"],
            rods={
                "r1": {"kind": "rod_area", "a": "a", "b": "j", "k": {"low": "19", "high": "21"}, "L": "1", "A": "1"},
                "r2": {"kind": "rod_area", "a": "b", "b": "j", "k": {"low": "9", "high": "11"}, "L": "1", "A": "1"},
                "r3": {"kind": "rod_area", "a": "c", "b": "j", "k": {"low": "28", "high": "32"}, "L": "1", "A": "1"},
            },
        )
        self.assertFalse(star_interval.is_exact_point)
        for k1 in k_intervals["r1"]:
            for k2 in k_intervals["r2"]:
                for k3 in k_intervals["r3"]:
                    corner = DerivedLaw.from_rods(
                        nodes=["a", "b", "c", "j"],
                        terminals=["a", "b", "c"],
                        rods={
                            "r1": {"kind": "rod_area", "a": "a", "b": "j", "k": k1, "L": "1", "A": "1"},
                            "r2": {"kind": "rod_area", "a": "b", "b": "j", "k": k2, "L": "1", "A": "1"},
                            "r3": {"kind": "rod_area", "a": "c", "b": "j", "k": k3, "L": "1", "A": "1"},
                        },
                    )
                    for i in ("a", "b", "c"):
                        for j in ("a", "b", "c"):
                            val = corner.matrix[i][j][0]
                            lo, hi = star_interval.matrix[i][j]
                            self.assertTrue(lo <= val <= hi, f"corner {(k1,k2,k3)} missed ({i},{j}): {val} not in [{lo},{hi}]")

    def test_h1_ast_adapter_matches_facts_backed_law_without_facts_json(self):
        # 1. Composite wall steady H1 study: exact match against facts.json-backed terminal_response.
        ast_law = DerivedLaw.from_h1_study(
            ROOT / "studies/composite_wall/study.json",
            ROOT / "studies/composite_wall",
        )
        facts_law = terminal_response(*COMPOSITE_WALL_INPUTS)
        self.assertEqual(list(ast_law.terminals), sorted(facts_law["terminals"]))
        for i in ast_law.terminals:
            for j in ast_law.terminals:
                self.assertEqual(
                    [str(ast_law.matrix[i][j][0]), str(ast_law.matrix[i][j][1])],
                    facts_law["supplyResponseBoundsWPerK"][i][j],
                )
        self.assertEqual(ast_law.lineage["kind"], "h1_study_ast")

        # 2. H1 S1 study (RodCircular + SimHeat.Units.from_degC / conductivityFromKcal / from_cm).
        s1_law = DerivedLaw.from_h1_study(ROOT / "h1/cases/S1/study.json", ROOT / "h1/cases")
        self.assertEqual(set(s1_law.terminals), {"hot", "cold"})
        self.assertEqual(s1_law.reference_temperatures_k["hot"], F(37315, 100))
        self.assertEqual(s1_law.reference_temperatures_k["cold"], F(27315, 100))
        # Independent exact check for S1 series circular rods (d = 0.02 m => A = pi*1e-4 m^2).
        pi_lo, pi_hi = pi_rational_enclosure()
        k_cu = F("0.092") * F(4184)
        k_st = F("0.011") * F(4184)
        g_cu = Box.bounds(pi_lo, pi_hi) * F(1, 10000) * k_cu / F("0.75")
        g_st = Box.bounds(pi_lo, pi_hi) * F(1, 10000) * k_st / F("1.25")
        g_series = (g_cu * g_st) / (g_cu + g_st)
        g_mid = (g_series.span()[0] + g_series.span()[1]) / 2
        d_lo, d_hi = s1_law.matrix["hot"]["hot"]
        self.assertTrue(d_lo <= g_mid <= d_hi)

        # 3. Transient H1 study with finite Body (D1): extracts conduction law honestly.
        d1_law = DerivedLaw.from_h1_study(ROOT / "h1/cases/D1/study.json", ROOT / "h1/cases")
        self.assertEqual(len(d1_law.terminals), 2)
        self.assertEqual(d1_law.lineage["studyMode"], "transient")

    def test_serialization_and_tamper_refusals(self):
        law = DerivedLaw.from_rods(
            nodes=["a", "b"],
            rods={"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1"}},
        )
        payload = law.to_dict()
        self.assertEqual(payload["schema"], DERIVED_LAW_SCHEMA)
        roundtrip = DerivedLaw.from_dict(payload)
        self.assertEqual(roundtrip.content_sha256, law.content_sha256)

        # Tampering matrix without updating contentSha256 must fail closed.
        tampered = json.loads(json.dumps(payload))
        tampered["supplyResponseBoundsWPerK"]["a"]["a"] = ["11", "11"]
        with self.assertRaisesRegex(ValueError, "contentSha256 mismatch"):
            DerivedLaw.from_dict(tampered)

        # Promoting any offline flag must fail closed.
        bad_flag = json.loads(json.dumps(payload))
        bad_flag["nativeQualified"] = True
        with self.assertRaisesRegex(ValueError, "refuses non-False nativeQualified"):
            DerivedLaw.from_dict(bad_flag)

        # Disconnected rod network must fail closed.
        with self.assertRaisesRegex(ValueError, "single connected component"):
            DerivedLaw.from_rods(
                nodes=["a", "b", "c"],
                rods={"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1"}},
            )


class M03PhysicalComposabilityTests(unittest.TestCase):
    def test_assembly1_radial_phase_vessel_steady_composability(self):
        system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "assembly1_radial_phase_vessel",
            "nodes": ["hot", "junction", "bath", "vessel_in"],
            "conduction": {
                "rods": {
                    "facing": {"kind": "rod_area", "a": "hot", "b": "junction", "k": {"low": "19.5", "high": "20.5"}, "L": "0.1", "A": "0.02"},
                    "strip": {"kind": "rod_area", "a": "junction", "b": "bath", "k": "10", "L": "0.1", "A": "0.01"},
                    "insert": {"kind": "rod_area", "a": "junction", "b": "vessel_in", "k": "30", "L": "0.1", "A": "0.01"},
                }
            },
            "attachments": {
                "hot": {"kind": "maintained", "temperatureK": "400"},
                "bath": {
                    "kind": "phase_substance",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "initialTemperatureK": "273.15",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "0.5",
                },
                "vessel_in": {
                    "kind": "radial_shell",
                    "geometry": {
                        "kind": "sphere",
                        "innerRadiusM": "0.1",
                        "layers": [
                            {"outerRadiusM": "0.11", "conductivityWPerMK": "400"},
                            {"outerRadiusM": "0.14", "conductivityWPerMK": "0.04"},
                        ],
                    },
                    "exterior": {
                        "airTemperatureK": "300",
                        "convectionCoefficientWPerM2K": "10",
                        "enclosureTemperatureK": "300",
                        "emissivity": "0.8",
                        "sigmaWPerM2K4": "0.0000000567",
                    },
                },
            },
            "solve": {"mode": "steady", "durationS": "600"},
        }
        eq = describe_equations(system)
        self.assertEqual(eq["selectedBackend"], "multiport")
        self.assertIn("Q_supply[bath]", eq["equationsText"])
        self.assertIn("G_shell(sphere", eq["terminalEquations"]["vessel_in"])

        res = solve_system(system)
        self.assertEqual(res["schema"], RESULT_ENVELOPE_SCHEMA)
        self.assertEqual(res["backend"], "multiport")
        self.assertEqual(res["terminationReason"], "converged")
        self.assertEqual(res["status"], "coexisting")
        raw = res["backendResult"]
        bal_lo, bal_hi = map(F, raw["systemEnergyBalanceBoundsW"])
        self.assertTrue(bal_lo <= 0 <= bal_hi)
        # Vessel inner temp must sit strictly between bath (273.15 K) and hot (400 K),
        # enclosing both exact endpoints k_facing = 19.5 and k_facing = 20.5.
        t_lo, t_hi = map(F, raw["ports"]["vessel_in"]["innerFaceTemperatureBoundsK"])
        self.assertGreater(t_lo, F("273.15"))
        self.assertLess(t_hi, F("400"))
        for k_pt in ("19.5", "20.5"):
            pt_sys = json.loads(json.dumps(system))
            pt_sys["conduction"]["rods"]["facing"]["k"] = k_pt
            pt_res = solve_system(pt_sys)
            pt_lo, pt_hi = map(F, pt_res["backendResult"]["ports"]["vessel_in"]["innerFaceTemperatureBoundsK"])
            self.assertLessEqual(t_lo, pt_lo)
            self.assertGreaterEqual(t_hi, pt_hi)

    def test_assembly2_joined_derived_law_equivalence_against_unreduced_full_graph_and_mpmath(self):
        # Principal M03 witness (F-05): join two independent subnetworks into a DerivedLaw
        # and pass directly to BOTH multibody (transient) and multiport (steady) with ZERO glue.
        left_spec = {
            "kind": "rods",
            "nodes": ["hot", "body_a", "splice", "jl"],
            "terminals": ["hot", "body_a", "splice"],
            "rods": {
                "l1": {"kind": "rod_area", "a": "hot", "b": "jl", "k": "24", "L": "0.2", "A": "0.01"},
                "l2": {"kind": "rod_area", "a": "body_a", "b": "jl", "k": "18", "L": "0.15", "A": "0.01"},
                "l3": {"kind": "rod_area", "a": "splice", "b": "jl", "k": "30", "L": "0.1", "A": "0.01"},
            },
        }
        right_spec = {
            "kind": "rods",
            "nodes": ["splice", "body_b", "ice_bath", "jr"],
            "terminals": ["splice", "body_b", "ice_bath"],
            "rods": {
                "r1": {"kind": "rod_area", "a": "splice", "b": "jr", "k": "20", "L": "0.1", "A": "0.01"},
                "r2": {"kind": "rod_area", "a": "body_b", "b": "jr", "k": "16", "L": "0.2", "A": "0.01"},
                "r3": {"kind": "rod_area", "a": "ice_bath", "b": "jr", "k": "15", "L": "0.15", "A": "0.01"},
            },
        }

        joined_system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "assembly2_joined_multibody_ice",
            "conduction": {
                "kind": "join",
                "left": left_spec,
                "right": right_spec,
                "contacts": [{"leftPort": "splice", "rightPort": "splice"}],
            },
            "attachments": {
                "left.hot": {"kind": "maintained", "temperatureK": "390"},
                "left.body_a": {"kind": "sensible_body", "heatCapacityJPerK": "1200", "initialTemperatureK": "350"},
                "right.body_b": {"kind": "sensible_body", "heatCapacityJPerK": "800", "initialTemperatureK": "310"},
                "right.ice_bath": {
                    "kind": "phase_substance",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "initialTemperatureK": "273.15",
                    "initialSolidKg": "0.5",
                    "initialLiquidKg": "0",
                },
            },
            "solve": {"mode": "transient", "durationS": "120", "initialSteps": 16},
        }

        # Unreduced full-graph oracle (single connected rod graph with splice as an internal junction!).
        full_graph_system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "assembly2_full_graph_oracle",
            "nodes": ["left.hot", "left.body_a", "right.body_b", "right.ice_bath", "jl", "jr", "splice"],
            "conduction": {
                "kind": "rods",
                "terminals": ["left.hot", "left.body_a", "right.body_b", "right.ice_bath"],
                "rods": {
                    "l1": {"kind": "rod_area", "a": "left.hot", "b": "jl", "k": "24", "L": "0.2", "A": "0.01"},
                    "l2": {"kind": "rod_area", "a": "left.body_a", "b": "jl", "k": "18", "L": "0.15", "A": "0.01"},
                    "l3": {"kind": "rod_area", "a": "splice", "b": "jl", "k": "30", "L": "0.1", "A": "0.01"},
                    "r1": {"kind": "rod_area", "a": "splice", "b": "jr", "k": "20", "L": "0.1", "A": "0.01"},
                    "r2": {"kind": "rod_area", "a": "right.body_b", "b": "jr", "k": "16", "L": "0.2", "A": "0.01"},
                    "r3": {"kind": "rod_area", "a": "right.ice_bath", "b": "jr", "k": "15", "L": "0.15", "A": "0.01"},
                },
            },
            "attachments": joined_system["attachments"],
            "solve": joined_system["solve"],
        }

        res_joined = solve_system(joined_system)
        res_full = solve_system(full_graph_system)

        self.assertEqual(res_joined["backend"], "multibody")
        self.assertEqual(res_joined["status"], "coexisting")
        self.assertEqual(res_joined["derivedLaw"]["lineage"]["kind"], "schur_join")
        # Exact point rods => Schur-joined DerivedLaw MUST produce identical rational results to full graph!
        for b in ("left.body_a", "right.body_b"):
            self.assertEqual(
                res_joined["backendResult"]["ports"][b]["finalBodyTemperatureBoundsK"],
                res_full["backendResult"]["ports"][b]["finalBodyTemperatureBoundsK"],
            )
        self.assertEqual(
            res_joined["backendResult"]["ports"]["right.ice_bath"]["latentEnergyIntoBathBoundsJ"],
            res_full["backendResult"]["ports"]["right.ice_bath"]["latentEnergyIntoBathBoundsJ"],
        )

        # Independent 80-digit mpmath matrix-exponential oracle on the reduced 2-body ODE!
        sys_obj = ThermalSystem.from_dict(joined_system)
        w = sys_obj.derived_law.matrix
        with mp.workdps(80):
            # Bodies: a (C=1200, T0=350), b (C=800, T0=310); Fixed: hot=390, ice=273.15
            w_aa = mp.mpf(str(w["left.body_a"]["left.body_a"][0]))
            w_ab = mp.mpf(str(w["left.body_a"]["right.body_b"][0]))
            w_bb = mp.mpf(str(w["right.body_b"]["right.body_b"][0]))
            w_ah = mp.mpf(str(w["left.body_a"]["left.hot"][0]))
            w_ai = mp.mpf(str(w["left.body_a"]["right.ice_bath"][0]))
            w_bh = mp.mpf(str(w["right.body_b"]["left.hot"][0]))
            w_bi = mp.mpf(str(w["right.body_b"]["right.ice_bath"][0]))
            t_h, t_i = mp.mpf("390"), mp.mpf("273.15")
            c_a, c_b = mp.mpf("1200"), mp.mpf("800")
            # Augmented 3x3 linear system d/dt [T_a, T_b, 1]^T = M [T_a, T_b, 1]^T
            mat = mp.matrix([
                [-w_aa / c_a, -w_ab / c_a, -(w_ah * t_h + w_ai * t_i) / c_a],
                [-w_ab / c_b, -w_bb / c_b, -(w_bh * t_h + w_bi * t_i) / c_b],
                [mp.mpf(0), mp.mpf(0), mp.mpf(0)],
            ])
            vec_end = mp.expm(mat * mp.mpf("120")) * mp.matrix([mp.mpf("350"), mp.mpf("310"), mp.mpf("1")])
            self.assertTrue(
                _in_bounds(vec_end[0], res_joined["backendResult"]["ports"]["left.body_a"]["finalBodyTemperatureBoundsK"])
            )
            self.assertTrue(
                _in_bounds(vec_end[1], res_joined["backendResult"]["ports"]["right.body_b"]["finalBodyTemperatureBoundsK"])
            )

        # Same joined DerivedLaw passed directly to multiport (steady) with ZERO glue code!
        joined_law = sys_obj.derived_law
        mp_res = solve_multiport(
            joined_law,
            {
                "left.hot": {"kind": "maintained", "temperatureK": "390"},
                "left.body_a": {
                    "kind": "radiating_surface",
                    "areaM2": "0.1",
                    "enclosureTemperatureK": "300",
                    "emissivity": "0",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "300",
                    "convectionCoefficientWPerM2K": "15",
                },
                "right.body_b": {"kind": "maintained", "temperatureK": "310"},
                "right.ice_bath": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "0.5",
                    "initialLiquidKg": "0",
                },
            },
            duration_s="120",
        )
        self.assertEqual(mp_res["solverMetadata"]["terminationReason"], "exact_linear")
        bal_lo, bal_hi = map(F, mp_res["systemEnergyBalanceBoundsW"])
        self.assertTrue(bal_lo <= 0 <= bal_hi)

    def test_legacy_join_thermal_networks_output_passes_directly_into_all_three_engines(self):
        # F-05 direct regression: raw output of tools/join_thermal_networks.py works in multiport, multibody, staged!
        joined_legacy = join_legacy_investigate(
            COMPOSITE_WALL_INPUTS, COMPOSITE_WALL_INPUTS, "cold", "hot"
        )
        self.assertEqual(joined_legacy["schema"], "sim_heat.offline_joined_terminal_response/1")

        # 1. multiport
        mp_out = solve_multiport(
            joined_legacy,
            {
                "left.hot": {"kind": "maintained", "temperatureK": "400"},
                "right.cold": {"kind": "maintained", "temperatureK": "300"},
            },
        )
        # Series of two 2 W/K walls => 1 W/K => 100 W into right.cold.
        self.assertEqual(mp_out["ports"]["right.cold"]["inflowFromNetworkBoundsW"], ["100", "100"])

        # 2. multibody
        mb_out = solve_multibody(
            joined_legacy,
            {
                "left.hot": {"kind": "lumped_body", "heatCapacityJPerK": "1000", "initialBodyTemperatureK": "380"},
                "right.cold": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "0",
                },
            },
            "20",
        )
        self.assertEqual(mb_out["phaseSystem"]["plateauStatus"], "coexisting")

        # 3. staged
        st_out = solve_staged(
            joined_legacy,
            "right.cold",
            "250",
            "273.15",
            "334000",
            "2100",
            "4200",
            "0.5",
            "0",
            "200",
            maintained_temperatures_k={"left.hot": "380"},
        )
        self.assertEqual(st_out["portEquivalent"]["portResistanceBoundsKPerW"], ["1", "1"])

    def test_interval_and_multicontact_m_matrix_joins_enclose_unreduced_corners(self):
        # Two 4-terminal laws joined across TWO simultaneous contacts (c1, c2) with interval conductances!
        left_iv = DerivedLaw.from_rods(
            nodes=["a", "b", "c1", "c2"],
            rods={
                "r1": {"kind": "rod_area", "a": "a", "b": "c1", "k": {"low": "9", "high": "11"}, "L": "1", "A": "1"},
                "r2": {"kind": "rod_area", "a": "b", "b": "c2", "k": "8", "L": "1", "A": "1"},
                "r3": {"kind": "rod_area", "a": "c1", "b": "c2", "k": "4", "L": "1", "A": "1"},
            },
        )
        right_iv = DerivedLaw.from_rods(
            nodes=["c1", "c2", "d", "e"],
            rods={
                "s1": {"kind": "rod_area", "a": "c1", "b": "d", "k": "6", "L": "1", "A": "1"},
                "s2": {"kind": "rod_area", "a": "c2", "b": "e", "k": {"low": "11", "high": "13"}, "L": "1", "A": "1"},
                "s3": {"kind": "rod_area", "a": "c1", "b": "c2", "k": "3", "L": "1", "A": "1"},
            },
        )
        joined_2c = join_laws(left_iv, right_iv, [("c1", "c1"), ("c2", "c2")])
        self.assertEqual(set(joined_2c.terminals), {"left.a", "left.b", "right.d", "right.e"})
        # Verify joined 2-contact interval matrix encloses all 4 exact corner realizations of the unreduced graph!
        for k_l in ("9", "11"):
            for k_r in ("11", "13"):
                full_corner = DerivedLaw.from_rods(
                    nodes=["left.a", "left.b", "right.d", "right.e", "c1", "c2"],
                    terminals=["left.a", "left.b", "right.d", "right.e"],
                    rods={
                        "r1": {"kind": "rod_area", "a": "left.a", "b": "c1", "k": k_l, "L": "1", "A": "1"},
                        "r2": {"kind": "rod_area", "a": "left.b", "b": "c2", "k": "8", "L": "1", "A": "1"},
                        "r3": {"kind": "rod_area", "a": "c1", "b": "c2", "k": "4", "L": "1", "A": "1"},
                        "s1": {"kind": "rod_area", "a": "c1", "b": "right.d", "k": "6", "L": "1", "A": "1"},
                        "s2": {"kind": "rod_area", "a": "c2", "b": "right.e", "k": k_r, "L": "1", "A": "1"},
                        "s3": {"kind": "rod_area", "a": "c1", "b": "c2", "k": "3", "L": "1", "A": "1"},
                    },
                )
                for i in joined_2c.terminals:
                    for j in joined_2c.terminals:
                        val = full_corner.matrix[i][j][0]
                        lo, hi = joined_2c.matrix[i][j]
                        self.assertTrue(lo <= val <= hi, f"2-contact join corner {(k_l,k_r)} missed ({i},{j})")

    def test_assembly3_staged_calorimeter_via_h1_ast_adapter_without_facts_json(self):
        system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "assembly3_h1_ast_staged",
            "conduction": {
                "kind": "h1_study",
                "studyPath": str(ROOT / "studies/composite_wall/study.json"),
                "rootPath": str(ROOT / "studies/composite_wall"),
            },
            "attachments": {
                "hot": {"kind": "maintained", "temperatureK": "380"},
                "cold": {
                    "kind": "phase_substance",
                    "initialTemperatureK": "250",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0.5",
                    "initialLiquidKg": "0",
                },
            },
            "solve": {"mode": "transient", "continuation": "staged", "durationS": "500"},
        }
        res = solve_system(system)
        self.assertEqual(res["backend"], "staged")
        self.assertEqual(res["terminationReason"], "resolved")
        self.assertEqual(res["derivedLaw"]["lineage"]["kind"], "h1_study_ast")

        # Compare against direct facts.json-backed staged solver: identical enclosures!
        facts_law = terminal_response(*COMPOSITE_WALL_INPUTS)
        direct = solve_staged(
            facts_law, "cold", "250", "273.15", "334000", "2100", "4200", "0.5", "0", "500"
        )
        self.assertEqual(
            res["backendResult"]["trajectory"]["finalTemperatureBoundsK"],
            direct["trajectory"]["finalTemperatureBoundsK"],
        )
        self.assertEqual(
            res["backendResult"]["trajectory"]["transitionEntryTimeBoundsS"],
            direct["trajectory"]["transitionEntryTimeBoundsS"],
        )
        self.assertEqual(
            res["backendResult"]["trajectory"]["remainingSolidBoundsKg"],
            direct["trajectory"]["remainingSolidBoundsKg"],
        )

    def test_structured_unsupported_regime_and_cli_roundtrip(self):
        base_rods = {
            "kind": "rods",
            "nodes": ["a", "b"],
            "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1"}},
        }
        # 1. steady + sensible_body -> unsupported_regime
        r1 = solve_system({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "u1",
            "conduction": base_rods,
            "attachments": {
                "a": {"kind": "maintained", "temperatureK": "400"},
                "b": {"kind": "sensible_body", "heatCapacityJPerK": "500", "initialTemperatureK": "300"},
            },
            "solve": {"mode": "steady"},
        })
        self.assertEqual(r1["status"], "unsupported_regime")
        self.assertEqual(r1["terminationReason"], "unsupported_regime")
        self.assertEqual(r1["unsupportedMechanismPair"], ["steady_mode", "sensible_body"])
        self.assertIs(r1["nativeExecuted"], False)

        # 2. transient + radial_shell + sensible_body -> unsupported_regime
        r2 = solve_system({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "u2",
            "conduction": base_rods,
            "attachments": {
                "a": {
                    "kind": "radial_shell",
                    "geometry": {"kind": "sphere", "innerRadiusM": "0.1", "layers": [{"outerRadiusM": "0.12", "conductivityWPerMK": "1"}]},
                    "exterior": {"enclosureTemperatureK": "300", "emissivity": "0.5", "sigmaWPerM2K4": "0.0000000567"},
                },
                "b": {"kind": "sensible_body", "heatCapacityJPerK": "500", "initialTemperatureK": "350"},
            },
            "solve": {"mode": "transient", "durationS": "10"},
        })
        self.assertEqual(r2["status"], "unsupported_regime")
        self.assertEqual(r2["unsupportedMechanismPair"], ["radial_shell", "sensible_body"])

        # 3. transient + sensible_body + subcooled phase_substance -> unsupported_regime (M04 scope)
        r3 = solve_system({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "u3",
            "conduction": base_rods,
            "attachments": {
                "a": {"kind": "sensible_body", "heatCapacityJPerK": "500", "initialTemperatureK": "350"},
                "b": {
                    "kind": "phase_substance",
                    "initialTemperatureK": "250",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "0",
                },
            },
            "solve": {"mode": "transient", "durationS": "10"},
        })
        self.assertEqual(r3["status"], "unsupported_regime")
        self.assertEqual(r3["unsupportedMechanismPair"], ["sensible_body", "non_coexisting_phase_substance"])

        # 4. CLI roundtrip (--equations-only and full solve)
        sys_doc = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "cli_smoke",
            "conduction": base_rods,
            "attachments": {
                "a": {"kind": "maintained", "temperatureK": "400"},
                "b": {"kind": "sensible_body", "massKg": "2", "specificHeatJPerKgK": "500", "initialTemperatureK": "300"},
            },
            "solve": {"mode": "transient", "durationS": "10"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sys.json"
            p.write_text(json.dumps(sys_doc), encoding="utf-8")
            eq_run = subprocess.run(
                [sys.executable, "-B", "-m", "simheat.system", "--system", str(p), "--equations-only"],
                cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(eq_run.returncode, 0, eq_run.stderr)
            eq_out = json.loads(eq_run.stdout)
            self.assertEqual(eq_out["selectedBackend"], "multibody")

            solve_run = subprocess.run(
                [sys.executable, "-B", "-m", "simheat.system", "--system", str(p)],
                cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(solve_run.returncode, 0, solve_run.stderr)
            solve_out = json.loads(solve_run.stdout)
            self.assertEqual(solve_out["schema"], RESULT_ENVELOPE_SCHEMA)
            self.assertEqual(solve_out["status"], "resolved")
            self.assertIs(solve_out["nativeExecuted"], False)

    def test_f08_legacy_direct_call_entry_points_refuse_non_passive_laws(self):
        # F-08 negative controls: non-passive (non-zero row sum / asymmetric / positive off-diagonal)
        # law MUST be refused by every legacy direct-call solve_from_law / plateau entry point!
        good = terminal_response(*COMPOSITE_WALL_INPUTS)
        bad_non_passive = {
            **good,
            "supplyResponseBoundsWPerK": {
                "hot": {"hot": ["2", "2"], "cold": ["-1", "-1"]},
                "cold": {"hot": ["-1", "-1"], "cold": ["2", "2"]},
            },
        }
        bad_pos_offdiag = {
            **good,
            "supplyResponseBoundsWPerK": {
                "hot": {"hot": ["2", "2"], "cold": ["1", "1"]},
                "cold": {"hot": ["1", "1"], "cold": ["2", "2"]},
            },
        }

        for bad_law in (bad_non_passive, bad_pos_offdiag):
            with self.assertRaises(ValueError):
                solve_body_phase_legacy(bad_law, "cold", "hot", "273.15", "334000", "1", "1", "500", "350", "10")
            with self.assertRaises(ValueError):
                solve_radial_bath_legacy(
                    bad_law, "hot", "cold", "273.15", "334000", "1", "1", "10",
                    "0.1", [("0.12", "1")], "300", "0.5", "0.0000000567",
                )
            with self.assertRaises(ValueError):
                solve_radial_exp_legacy(
                    bad_law, "hot", "cold", "273.15", "334000", "1", "1",
                    "0.1", [("0.12", "1")], "0.5", "0.0000000567",
                    [("s1", "300", "10", "300", "10")],
                )
            with self.assertRaises(ValueError):
                solve_film_cal_legacy(
                    bad_law, "hot", "cold", "273.15", "334000", "1", "1", "10",
                    ["0.01", "0.02"], "0.1", [("0.12", "1")], "300", "300", "0.5", "0.0000000567",
                )
            with self.assertRaises(ValueError):
                solve_shell_k_legacy(
                    bad_law, "hot", "cold", "273.15", "334000", "1", "1", "10",
                    ["0.01", "0.02"], "0.1", [("0.12", "unknown")], "300", "0.5", "0.0000000567",
                )
            with self.assertRaises(ValueError):
                solve_latent_legacy(bad_law, "cold", "273.15", "334000", "1", "1", "10")

    def test_review_hardening_regressions_m03_r01_through_r08(self):
        # M03-R01: direct DerivedLaw(...) forgery and in-place matrix mutation must both fail closed.
        valid_law = DerivedLaw.from_rods(
            nodes=["a", "b"],
            rods={"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "2", "L": "1", "A": "1"}},
        )
        with self.assertRaises(TypeError):
            valid_law.matrix["a"]["a"] = (F(100), F(100))  # type: ignore[index]
        with self.assertRaises(ValueError):
            DerivedLaw(
                terminals=("a", "b"),
                matrix={"a": {"a": (F(100), F(100)), "b": (F(-2), F(-2))}, "b": {"a": (F(-2), F(-2)), "b": (F(100), F(100))}},
                lineage={"kind": "forged"},
                content_sha256="0" * 64,
            )

        # M03-R02: unknown keys on conduction(rods) or rod specs must be refused fail-closed.
        with self.assertRaisesRegex(ValueError, "unexpected"):
            DerivedLaw.from_rods(
                nodes=["a", "b"],
                rods={"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1", "temperatureSlopeAlpha": "0.05"}},
            )
        with self.assertRaisesRegex(ValueError, "unexpected"):
            ThermalSystem.from_dict({
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "bad_key",
                "conduction": {
                    "kind": "rods",
                    "nodes": ["a", "b"],
                    "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1"}},
                    "unexpectedTopKey": True,
                },
                "attachments": {
                    "a": {"kind": "maintained", "temperatureK": "400"},
                    "b": {"kind": "maintained", "temperatureK": "300"},
                },
                "solve": {"mode": "steady"},
            })

        # M03-R03: bogus radial_shell payloads must fail at ThermalSystem.from_dict before describe_equations.
        for bad_shell in (
            {"kind": "radial_shell", "geometry": {}, "exterior": {}},
            {
                "kind": "radial_shell",
                "geometry": {"kind": "sphere", "innerRadiusM": "0.1", "layers": "not_a_list"},
                "exterior": {"enclosureTemperatureK": "300", "emissivity": "0.5", "sigmaWPerM2K4": "0.0000000567"},
            },
            {
                "kind": "radial_shell",
                "geometry": {"kind": "sphere", "innerRadiusM": "0.1", "layers": [{"outerRadiusM": "0.12", "conductivityWPerMK": "1"}]},
                "exterior": {"enclosureTemperatureK": "300", "emissivity": "0.5", "sigmaWPerM2K4": "0.0000000567", "airTemperatureK": "300"},
            },
        ):
            with self.assertRaises(ValueError):
                ThermalSystem.from_dict({
                    "schema": THERMAL_SYSTEM_SCHEMA,
                    "id": "bad_shell",
                    "conduction": {"kind": "rods", "nodes": ["a", "b"], "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1"}}},
                    "attachments": {"a": {"kind": "maintained", "temperatureK": "400"}, "b": bad_shell},
                    "solve": {"mode": "steady"},
                })

        # M03-R04: DerivedLaw.from_dict(good_pinned_law) must work across ALL 6 legacy entry points!
        good_dl = DerivedLaw.from_dict(terminal_response(*COMPOSITE_WALL_INPUTS))
        self.assertEqual(
            solve_radial_bath_legacy(
                good_dl, "hot", "cold", "273.15", "334000", "1", "1", "10",
                "0.1", [("0.12", "1")], "300", "0.5", "0.0000000567",
            )["schema"],
            "sim_heat.offline_radial_phase_bath/1",
        )
        self.assertEqual(
            solve_radial_exp_legacy(
                good_dl, "hot", "cold", "273.15", "334000", "1", "1",
                "0.1", [("0.12", "1")], "0.5", "0.0000000567",
                [("s1", "300", "10", "300", "10")],
            )["schema"],
            "sim_heat.offline_radial_phase_exposure/1",
        )

        # M03-R05: H1 model with component named junction_1 plus an internal ownerless junction must not collide.
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp).resolve(strict=True)
            mo = (
                "within;\n"
                "model JunctionCollision\n"
                "  SimHeat.FixedTemperature junction_1(T=400);\n"
                "  SimHeat.FixedTemperature cold(T=300);\n"
                "  SimHeat.RodArea r1(k=10, L=1, A=1);\n"
                "  SimHeat.RodArea r2(k=10, L=1, A=1);\n"
                "equation\n"
                "  connect(junction_1.port, r1.port_a);\n"
                "  connect(r1.port_b, r2.port_a);\n"
                "  connect(r2.port_b, cold.port);\n"
                "end JunctionCollision;\n"
            )
            mo_path = tdir / "model.mo"
            mo_path.write_bytes(mo.encode("utf-8"))
            st = {
                "schema": "sim_heat.study/1",
                "id": "JunctionCollision",
                "model": {"path": "model.mo", "sha256": sha256(mo_path.read_bytes()).hexdigest()},
                "mode": "steady",
                "requests": [{"id": "q", "op": "heatFlow", "target": "r1"}],
                "analysis": {},
                "provenance": [
                    {"target": target, "kind": "illustrative", "locator": "test", "note": "test"}
                    for target in ("junction_1.T", "cold.T", "r1.k", "r1.L", "r1.A", "r2.k", "r2.L", "r2.A")
                ] + [{"target": "@model", "kind": "adopted_assumption", "locator": "test", "note": "test"}],
            }
            st_path = tdir / "study.json"
            st_path.write_text(json.dumps(st), encoding="utf-8")
            j_law = DerivedLaw.from_h1_study(st_path, tdir)
            self.assertEqual(set(j_law.terminals), {"junction_1", "cold"})
            self.assertEqual(j_law.matrix["junction_1"]["junction_1"], (F(5), F(5)))

        # M03-R07: >28-digit terminating massKg * specificHeatJPerKgK must succeed exactly.
        hi_prec = ThermalSystem.from_dict({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "high_prec_mc",
            "conduction": {"kind": "rods", "nodes": ["a", "b"], "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1"}}},
            "attachments": {
                "a": {"kind": "maintained", "temperatureK": "400"},
                "b": {
                    "kind": "sensible_body",
                    "massKg": "1.00000000000001",
                    "specificHeatJPerKgK": "4200.000000000003",
                    "initialTemperatureK": "300",
                },
            },
            "solve": {"mode": "transient", "durationS": "1"},
        })
        self.assertEqual(
            F(hi_prec.attachments["b"]["heatCapacityJPerK"]),
            F("1.00000000000001") * F("4200.000000000003"),
        )

        # M03-R08: invalid maxSweeps / initialSteps must be refused regardless of mode.
        for bad_solve in (
            {"mode": "steady", "initialSteps": -999},
            {"mode": "steady", "initialSteps": True},
            {"mode": "transient", "durationS": "1", "maxSweeps": "not_an_int"},
            {"mode": "transient", "durationS": "1", "maxSweeps": 0},
        ):
            with self.assertRaises(ValueError):
                ThermalSystem.from_dict({
                    "schema": THERMAL_SYSTEM_SCHEMA,
                    "id": "bad_solve",
                    "conduction": {"kind": "rods", "nodes": ["a", "b"], "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1"}}},
                    "attachments": {
                        "a": {"kind": "maintained", "temperatureK": "400"},
                        "b": {"kind": "maintained", "temperatureK": "300"},
                    },
                    "solve": bad_solve,
                })

        # M03-R10: direct DerivedLaw(...) with forged legacy_provenance, extra keys, or bad law_id must fail closed.
        for bad_kwargs in (
            {
                "legacy_provenance": {
                    "modelSha256": "a" * 64,
                    "studySha256": "b" * 64,
                    "factsSha256": "c" * 64,
                    "nativeQualified": True,
                }
            },
            {
                "legacy_provenance": {
                    "modelSha256": "a" * 64,
                    "studySha256": "b" * 64,
                    "factsSha256": "c" * 64,
                    "ports": "OVERWRITTEN",
                }
            },
            {"legacy_provenance": {"modelSha256": "bad", "studySha256": "bad", "factsSha256": "bad"}},
            {"law_id": ""},
            {"law_id": 123},
        ):
            with self.assertRaises(ValueError):
                DerivedLaw(
                    terminals=valid_law.terminals,
                    matrix=valid_law.matrix,
                    lineage=valid_law.lineage,
                    content_sha256=valid_law.content_sha256,
                    **bad_kwargs,
                )


if __name__ == "__main__":
    unittest.main()
