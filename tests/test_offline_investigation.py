"""Tests for the typed offline investigation contract (sim_heat.offline_investigation/1)."""
import contextlib
import copy
from fractions import Fraction as F
import io
import json
from pathlib import Path
import tempfile
from unittest import TestCase

from qualification.h1_n13.conduction import interval
from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.body_phase_bath_exchange import investigate as body_investigate
from tools.offline_investigation import (
    CONTRACT_SCHEMA,
    EVIDENCE_CATEGORY,
    TERMINAL_LAW_SCHEMA,
    ExteriorExchangeSpec,
    InvestigationRequest,
    LumpedBodySpec,
    PhaseBathSpec,
    PinnedSourceRef,
    RadialGeometrySpec,
    RadialLayerSpec,
    RadialShellPortSpec,
    main as cli_main,
    run_investigation,
    validate_investigation_record,
    validate_pinned_law,
)
from tools.offline_provenance import OFFLINE_FLAG_KEYS, SOURCE_HASH_KEYS
from tools.radial_phase_bath import investigate as radial_investigate
from tools.terminal_response import investigate as terminal_response

REPO_ROOT = Path(__file__).resolve().parent.parent


def _source_ref(inputs):
    return PinnedSourceRef(
        study_path=str(inputs[0]),
        root_path=str(inputs[1]),
        facts_path=str(inputs[2]),
        facts_sha256=str(inputs[3]),
    )


def _source_dict(inputs):
    return {
        "studyPath": str(inputs[0]),
        "rootPath": str(inputs[1]),
        "factsPath": str(inputs[2]),
        "factsSha256": str(inputs[3]),
    }


def _synthetic_law(terminals, imposed, matrix, *, schema=TERMINAL_LAW_SCHEMA):
    return {
        "schema": schema,
        "terminals": list(terminals),
        "imposedTemperaturesK": dict(imposed),
        "supplyResponseBoundsWPerK": matrix,
        "modelSha256": "a" * 64,
        "studySha256": "b" * 64,
        "factsSha256": "c" * 64,
        "nativeExecuted": False,
        "nativeQualified": False,
        "independentlyCertifiedReference": False,
        "runnerConsumable": False,
    }


class OfflineInvestigationContractTests(TestCase):
    def test_radial_phase_bath_link_cylinder_and_sphere_parity(self):
        # Reproduce the cylindrical critical-radius worked cases (0.12 / 0.20 / 0.50 m)
        # through the shared typed adapter and verify exact parity with radial_phase_bath.
        for r_out in ("0.12", "0.20", "0.50"):
            direct = radial_investigate(
                LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "5000",
                "0.1", [(r_out, "2")], "293.15", "0", "0.0000000567", "1",
                air_k="293.15", h_w_per_m2_k="10",
            )
            req = InvestigationRequest(
                composition="radial_phase_bath",
                source=_source_ref(LINK),
                duration_s="5000",
                phase_bath=PhaseBathSpec("hot", "273.15", "334000", "0.02", "0.03"),
                radial_shell=RadialShellPortSpec(
                    surface_port="cold",
                    geometry=RadialGeometrySpec(
                        kind="cylinder",
                        inner_radius_m="0.1",
                        layers=(RadialLayerSpec(r_out, "2"),),
                        cylinder_length_m="1",
                    ),
                    exterior=ExteriorExchangeSpec(
                        enclosure_k="293.15",
                        emissivity="0",
                        sigma_w_per_m2_k4="0.0000000567",
                        air_k="293.15",
                        h_w_per_m2_k="10",
                    ),
                ),
            )
            record = run_investigation(req)
            self.assertEqual(record["schema"], CONTRACT_SCHEMA)
            self.assertEqual(record["composition"], "radial_phase_bath")
            self.assertEqual(record["rawResult"], direct)
            self.assertEqual(record["geometry"]["kind"], "cylinder")
            self.assertEqual(record["geometry"]["cylinderLengthM"], "1")
            self.assertEqual(record["evidence"]["category"], EVIDENCE_CATEGORY)
            self.assertTrue(record["evidence"]["sourceIdentity"]["preparedFromFiles"])
            for flag in OFFLINE_FLAG_KEYS:
                self.assertIs(record[flag], False)
                self.assertIs(record["evidence"][flag], False)
            self.assertIs(record["status"]["postExhaustionModeled"], False)

            # P2-1: source-law reference temps are separated from active boundary conditions.
            self.assertNotIn("imposedTemperaturesK", record["network"])
            self.assertEqual(
                record["network"]["sourceLawReferenceTemperaturesK"],
                {"hot": "380", "cold": "280"},
            )
            self.assertEqual(record["network"]["maintainedReservoirTemperaturesK"], {})
            self.assertEqual(
                record["network"]["activeBoundaryConditions"]["hot"],
                {
                    "role": "phase_bath",
                    "constraint": "clamped_during_coexistence",
                    "temperatureK": direct["transitionTemperatureK"],
                },
            )
            self.assertEqual(
                record["network"]["activeBoundaryConditions"]["cold"]["constraint"],
                "released_to_radial_shell",
            )
            self.assertEqual(
                record["quantities"]["bathInflowDuringPlateauW"]["signConvention"],
                "into_phase_bath_positive",
            )
            self.assertEqual(
                record["quantities"]["surfaceOutwardHeatRateW"]["signConvention"],
                "outward_from_radial_surface_positive",
            )
            round_tripped = json.loads(json.dumps(record))
            self.assertTrue(validate_investigation_record(round_tripped))

    def test_radial_phase_bath_star_three_terminal_energy_balance_and_roles(self):
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        direct = radial_investigate(
            star_inputs, "cool", "warm", "273.15", "334000", "0.05", "0.05", "600",
            "0.1", [("0.2", "2")], "290", "0.8", "0.0000000567",
        )
        payload = {
            "composition": "radial_phase_bath",
            "source": _source_dict(star_inputs),
            "durationS": "600",
            "phaseBath": {
                "port": "cool",
                "transitionTemperatureK": "273.15",
                "specificLatentHeatJPerKg": "334000",
                "initialSolidKg": "0.05",
                "initialLiquidKg": "0.05",
            },
            "radialShell": {
                "surfacePort": "warm",
                "geometry": {
                    "kind": "sphere",
                    "innerRadiusM": "0.1",
                    "layers": [{"outerRadiusM": "0.2", "conductivityWPerMK": "2"}],
                },
                "exterior": {
                    "enclosureTemperatureK": "290",
                    "emissivity": "0.8",
                    "sigmaWPerM2K4": "0.0000000567",
                },
            },
        }
        record = run_investigation(payload)
        self.assertEqual(record["rawResult"], direct)
        self.assertEqual(
            record["network"]["portRoles"],
            {"warm": "radial_surface", "middle": "maintained_reservoir", "cool": "phase_bath"},
        )
        self.assertEqual(
            record["network"]["sourceLawReferenceTemperaturesK"],
            {"warm": "380", "middle": "330", "cool": "280"},
        )
        self.assertEqual(record["network"]["maintainedReservoirTemperaturesK"], {"middle": "330"})
        self.assertEqual(
            record["network"]["activeBoundaryConditions"]["middle"],
            {"role": "maintained_reservoir", "constraint": "fixed_dirichlet", "temperatureK": "330"},
        )
        self.assertEqual(
            record["network"]["activeBoundaryConditions"]["cool"]["temperatureK"],
            direct["transitionTemperatureK"],
        )
        self.assertEqual(
            record["network"]["activeBoundaryConditions"]["warm"]["constraint"],
            "released_to_radial_shell",
        )
        self.assertEqual(record["geometry"]["kind"], "sphere")
        self.assertIsNone(record["geometry"]["cylinderLengthM"])

        # Steady energy balance: Q_into_bath + Q_into_maintained + Q_outward_surface contains 0.
        q_bath = interval(record["quantities"]["bathInflowDuringPlateauW"]["bounds"])
        q_surf = interval(record["quantities"]["surfaceOutwardHeatRateW"]["bounds"])
        q_mid = interval(record["quantities"]["maintainedReservoirInflowsW"]["middle"]["bounds"])
        self.assertEqual(
            record["quantities"]["maintainedReservoirInflowsW"]["middle"]["signConvention"],
            "into_maintained_reservoir_positive",
        )
        total = q_bath + q_surf + q_mid
        self.assertLessEqual(total.span()[0], F(0))
        self.assertGreaterEqual(total.span()[1], F(0))

    def test_body_phase_bath_exchange_link_and_star_reversing_parity(self):
        # 2-terminal LINK (exhausted solid; composed temps 350/273.15 differ from source 380/280)
        direct_link = body_investigate(
            LINK, "cold", "hot", "273.15", "334000", "0.005", "0.05", "4000", "350", "50000",
        )
        req_link = InvestigationRequest(
            composition="body_phase_bath_exchange",
            source=_source_ref(LINK),
            duration_s="50000",
            phase_bath=PhaseBathSpec("cold", "273.15", "334000", "0.005", "0.05"),
            body=LumpedBodySpec("hot", "4000", "350"),
        )
        rec_link = run_investigation(req_link)
        self.assertEqual(rec_link["rawResult"], direct_link)
        self.assertEqual(rec_link["status"]["plateauStatus"], "exhausted")
        self.assertEqual(rec_link["status"]["exhaustedPhase"], "solid")
        self.assertEqual(rec_link["geometry"]["kind"], "lumped_network_port")
        self.assertEqual(
            rec_link["network"]["sourceLawReferenceTemperaturesK"],
            {"hot": "380", "cold": "280"},
        )
        self.assertEqual(rec_link["network"]["maintainedReservoirTemperaturesK"], {})
        self.assertEqual(
            rec_link["network"]["activeBoundaryConditions"]["cold"],
            {
                "role": "phase_bath",
                "constraint": "clamped_during_coexistence",
                "temperatureK": direct_link["transitionTemperatureK"],
            },
        )
        self.assertEqual(
            rec_link["network"]["activeBoundaryConditions"]["hot"],
            {
                "role": "lumped_body",
                "constraint": "released_to_lumped_body",
                "initialTemperatureK": "350",
                "finalTemperatureBoundsK": direct_link["finalBodyTemperatureBoundsK"],
            },
        )
        self.assertEqual(
            rec_link["quantities"]["bodyEnergyChangeJ"]["signConvention"],
            "into_body_positive",
        )
        self.assertTrue(validate_investigation_record(json.loads(json.dumps(rec_link))))

        # 3-terminal STAR (genuine reversing melting-to-freezing via prebuilt law)
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        star_law = terminal_response(*star_inputs)
        direct_star = body_investigate(
            star_inputs, "cool", "warm", "350", "334000", "0.05", "0.05", "1000", "450", "5000",
        )
        rec_star = run_investigation({
            "composition": "body_phase_bath_exchange",
            "source": star_law,
            "durationS": "5000",
            "phaseBath": {
                "port": "cool",
                "transitionTemperatureK": "350",
                "specificLatentHeatJPerKg": "334000",
                "initialSolidKg": "0.05",
                "initialLiquidKg": "0.05",
            },
            "body": {
                "port": "warm",
                "heatCapacityJPerK": "1000",
                "initialBodyTemperatureK": "450",
            },
        })
        self.assertEqual(rec_star["rawResult"], direct_star)
        self.assertEqual(rec_star["status"]["phaseProcess"], "reversing_melting_to_freezing")
        self.assertIsNotNone(rec_star["status"]["reversalTimeS"])
        self.assertFalse(rec_star["evidence"]["sourceIdentity"]["preparedFromFiles"])
        self.assertEqual(
            rec_star["network"]["portRoles"],
            {"warm": "lumped_body", "middle": "maintained_reservoir", "cool": "phase_bath"},
        )
        self.assertEqual(rec_star["network"]["maintainedReservoirTemperaturesK"], {"middle": "330"})
        self.assertTrue(validate_investigation_record(json.loads(json.dumps(rec_star))))

    def test_cli_entry_point_for_both_compositions(self):
        payload = {
            "composition": "body_phase_bath_exchange",
            "source": _source_dict(LINK),
            "durationS": "100",
            "phaseBath": {
                "port": "cold",
                "transitionTemperatureK": "273.15",
                "specificLatentHeatJPerKg": "334000",
                "initialSolidKg": "0.1",
                "initialLiquidKg": "0.1",
            },
            "body": {
                "port": "hot",
                "heatCapacityJPerK": "2000",
                "initialBodyTemperatureK": "320",
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            req_path = Path(tmp) / "req.json"
            req_path.write_text(json.dumps(payload), encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli_main(["--request", str(req_path)])
            out = json.loads(buf.getvalue())
            self.assertEqual(out["schema"], CONTRACT_SCHEMA)
            self.assertTrue(validate_investigation_record(out))

    def test_passive_law_validation_refuses_nonreciprocal_and_unphysical_matrices(self):
        # P2-3 exact asymmetric two-terminal witness (nonreciprocal response: 1 vs 2 W/K).
        asymmetric = _synthetic_law(
            ["hot", "cold"],
            {"hot": "320", "cold": "273.15"},
            {
                "hot": {"hot": ["1", "1"], "cold": ["-1", "-1"]},
                "cold": {"hot": ["-2", "-2"], "cold": ["2", "2"]},
            },
        )
        with self.assertRaisesRegex(ValueError, "nonreciprocal"):
            validate_pinned_law(asymmetric)
        with self.assertRaisesRegex(ValueError, "nonreciprocal"):
            run_investigation({
                "composition": "body_phase_bath_exchange",
                "source": asymmetric,
                "durationS": "1",
                "phaseBath": {
                    "port": "cold",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "0.1",
                    "initialLiquidKg": "0.1",
                },
                "body": {
                    "port": "hot",
                    "heatCapacityJPerK": "1000",
                    "initialBodyTemperatureK": "320",
                },
            })

        # Wrong schema
        bad_schema = _synthetic_law(
            ["hot", "cold"],
            {"hot": "320", "cold": "273.15"},
            {
                "hot": {"hot": ["1", "1"], "cold": ["-1", "-1"]},
                "cold": {"hot": ["-1", "-1"], "cold": ["1", "1"]},
            },
            schema="sim_heat.wrong/1",
        )
        with self.assertRaisesRegex(ValueError, "pinned law schema"):
            validate_pinned_law(bad_schema)

        # Non-zero row sum
        bad_row_sum = _synthetic_law(
            ["hot", "cold"],
            {"hot": "320", "cold": "273.15"},
            {
                "hot": {"hot": ["2", "2"], "cold": ["-1", "-1"]},
                "cold": {"hot": ["-1", "-1"], "cold": ["1", "1"]},
            },
        )
        with self.assertRaisesRegex(ValueError, "zero-sum conservation"):
            validate_pinned_law(bad_row_sum)

        # Positive off-diagonal
        bad_offdiag = _synthetic_law(
            ["hot", "cold"],
            {"hot": "320", "cold": "273.15"},
            {
                "hot": {"hot": ["1", "1"], "cold": ["1", "1"]},
                "cold": {"hot": ["1", "1"], "cold": ["1", "1"]},
            },
        )
        with self.assertRaisesRegex(ValueError, "non-positive off-diagonal"):
            validate_pinned_law(bad_offdiag)

        # Disconnected 3-terminal network
        disconnected = _synthetic_law(
            ["a", "b", "c"],
            {"a": "350", "b": "300", "c": "280"},
            {
                "a": {"a": ["1", "1"], "b": ["-1", "-1"], "c": ["0", "0"]},
                "b": {"a": ["-1", "-1"], "b": ["1", "1"], "c": ["0", "0"]},
                "c": {"a": ["0", "0"], "b": ["0", "0"], "c": ["1", "1"]},
            },
        )
        with self.assertRaisesRegex(ValueError, "zero-sum conservation|disconnected"):
            validate_pinned_law(disconnected)

        # P2-B exact three-terminal impossible matrix: passes pairwise reciprocity,
        # individual row/column zero-sum checks, and connectivity, yet has NO
        # jointly consistent passive reciprocal zero-sum matrix (M_aa=5 > 2+2=4).
        impossible_three = _synthetic_law(
            ["a", "b", "c"],
            {"a": "350", "b": "300", "c": "280"},
            {
                "a": {"a": ["5", "5"], "b": ["-10", "-1"], "c": ["-2", "-1"]},
                "b": {"a": ["-2", "-1"], "b": ["2", "3"], "c": ["-1", "-1"]},
                "c": {"a": ["-10", "-1"], "b": ["-1", "-1"], "c": ["2", "3"]},
            },
        )
        with self.assertRaisesRegex(ValueError, "jointly consistent"):
            validate_pinned_law(impossible_three)

        # Sneakier three-terminal jointly infeasible matrix where every individual
        # vertex's reciprocal-edge sum [2, 4] contains its diagonal, yet row a
        # forces g_ab = 2 while row b forces g_ab = 1.
        coupled_infeasible = _synthetic_law(
            ["a", "b", "c"],
            {"a": "350", "b": "300", "c": "280"},
            {
                "a": {"a": ["4", "4"], "b": ["-2", "-1"], "c": ["-2", "-1"]},
                "b": {"a": ["-2", "-1"], "b": ["2", "2"], "c": ["-2", "-1"]},
                "c": {"a": ["-2", "-1"], "b": ["-2", "-1"], "c": ["2", "4"]},
            },
        )
        with self.assertRaisesRegex(ValueError, "jointly consistent"):
            validate_pinned_law(coupled_infeasible)

        # Legitimate overlapping independent interval enclosures (2- and 3-terminal) MUST be accepted.
        overlapping = _synthetic_law(
            ["hot", "cold"],
            {"hot": "320", "cold": "273.15"},
            {
                "hot": {"hot": ["9/10", "11/10"], "cold": ["-11/10", "-9/10"]},
                "cold": {"hot": ["-105/100", "-95/100"], "cold": ["95/100", "105/100"]},
            },
        )
        validate_pinned_law(overlapping)

        overlapping_three = _synthetic_law(
            ["a", "b", "c"],
            {"a": "350", "b": "300", "c": "280"},
            {
                "a": {"a": ["3", "7/2"], "b": ["-2", "-1"], "c": ["-2", "-1"]},
                "b": {"a": ["-11/5", "-9/10"], "b": ["2", "3"], "c": ["-3/2", "-1/2"]},
                "c": {"a": ["-2", "-1"], "b": ["-3/2", "-1/2"], "c": ["2", "3"]},
            },
        )
        validate_pinned_law(overlapping_three)

        # Forced-zero bridge four-terminal witness: g_hi(ac)=1 looks connected
        # individually, but fixed diagonals d_a=1, d_c=1 with g_ab=g_cd=1 force
        # g_ac=0 in every feasible realization, leaving {a,b} and {c,d} disjoint.
        forced_zero_bridge = _synthetic_law(
            ["a", "b", "c", "d"],
            {"a": "350", "b": "330", "c": "300", "d": "280"},
            {
                "a": {"a": ["1", "1"], "b": ["-1", "-1"], "c": ["-1", "0"], "d": ["0", "0"]},
                "b": {"a": ["-1", "-1"], "b": ["1", "1"], "c": ["0", "0"], "d": ["0", "0"]},
                "c": {"a": ["-1", "0"], "b": ["0", "0"], "c": ["1", "1"], "d": ["-1", "-1"]},
                "d": {"a": ["0", "0"], "b": ["0", "0"], "c": ["-1", "-1"], "d": ["1", "1"]},
            },
        )
        with self.assertRaisesRegex(ValueError, "disconnected"):
            validate_pinned_law(forced_zero_bridge)

        # Widening diagonals a and c to [1, 2] permits g_ac > 0 (e.g. 1/2) while
        # Phase-I zero-vector extreme point still has g_ac = 0; MUST be accepted!
        widened_bridge = copy.deepcopy(forced_zero_bridge)
        widened_bridge["supplyResponseBoundsWPerK"]["a"]["a"] = ["1", "2"]
        widened_bridge["supplyResponseBoundsWPerK"]["c"]["c"] = ["1", "2"]
        validate_pinned_law(widened_bridge)

    def test_negative_controls_malformed_ports_geometry_intervals_and_provenance(self):
        law = terminal_response(*LINK)

        # Unknown composition
        with self.assertRaisesRegex(ValueError, "unsupported composition"):
            run_investigation({
                "composition": "unknown_solver",
                "source": law,
                "durationS": "10",
                "phaseBath": {
                    "port": "hot",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "0.1",
                    "initialLiquidKg": "0.1",
                },
            })

        # Duplicate ports
        with self.assertRaisesRegex(ValueError, "distinct"):
            InvestigationRequest(
                composition="body_phase_bath_exchange",
                source=law,
                duration_s="10",
                phase_bath=PhaseBathSpec("hot", "273.15", "334000", "0.1", "0.1"),
                body=LumpedBodySpec("hot", "1000", "320"),
            )

        # Unknown port in pinned network
        with self.assertRaisesRegex(ValueError, "not in pinned network"):
            run_investigation(InvestigationRequest(
                composition="body_phase_bath_exchange",
                source=law,
                duration_s="10",
                phase_bath=PhaseBathSpec("nonexistent", "273.15", "334000", "0.1", "0.1"),
                body=LumpedBodySpec("hot", "1000", "320"),
            ))

        # Malformed radial geometry
        with self.assertRaisesRegex(ValueError, "sphere geometry"):
            RadialGeometrySpec("sphere", "0.1", (RadialLayerSpec("0.2", "2"),), cylinder_length_m="1")
        with self.assertRaisesRegex(ValueError, "cylinder geometry requires"):
            RadialGeometrySpec("cylinder", "0.1", (RadialLayerSpec("0.2", "2"),))
        with self.assertRaisesRegex(ValueError, "strictly increase"):
            RadialGeometrySpec("sphere", "0.2", (RadialLayerSpec("0.1", "2"),))

        # Malformed source digest in PinnedSourceRef
        with self.assertRaisesRegex(ValueError, "64-lowercase-hex"):
            PinnedSourceRef("a", "b", "c", "not-a-sha256")

        # Inverted interval in prebuilt law
        bad_law = copy.deepcopy(law)
        bad_law["supplyResponseBoundsWPerK"]["hot"]["hot"] = ["5", "1"]
        with self.assertRaisesRegex(ValueError, "inverted interval bounds"):
            validate_pinned_law(bad_law)

        # Forged provenance flag in prebuilt law
        for flag in OFFLINE_FLAG_KEYS:
            forged = copy.deepcopy(law)
            forged[flag] = True
            with self.assertRaisesRegex(ValueError, "refuses non-False"):
                validate_pinned_law(forged)

    def test_one_field_at_a_time_serialization_tamper_controls(self):
        good = run_investigation(InvestigationRequest(
            composition="body_phase_bath_exchange",
            source=_source_ref(LINK),
            duration_s="50000",
            phase_bath=PhaseBathSpec("cold", "273.15", "334000", "0.005", "0.05"),
            body=LumpedBodySpec("hot", "4000", "350"),
        ))

        # Every offline flag refused when forged True
        for flag in OFFLINE_FLAG_KEYS:
            tampered = copy.deepcopy(good)
            tampered["evidence"][flag] = True
            with self.assertRaisesRegex(ValueError, "must be False"):
                validate_investigation_record(tampered)

        # P2-2 individual semantic mutations (one field at a time)
        mutations = [
            ("wrong_sign_convention", lambda r: r["quantities"]["bodyEnergyChangeJ"].__setitem__("signConvention", "into_phase_bath_positive"), "signConvention"),
            ("wrong_owner", lambda r: r["quantities"]["bodyEnergyChangeJ"].__setitem__("owner", "phase_bath:cold"), "owner"),
            ("negative_mass_domain", lambda r: r["quantities"]["remainingSolidKg"].__setitem__("bounds", ["-1", "-1"]), "nonnegative"),
            ("duplicate_port_role", lambda r: r["network"]["portRoles"].__setitem__("hot", "phase_bath"), "exactly one"),
            ("mismatched_phase_process", lambda r: r["status"].__setitem__("phaseProcess", "freezing"), "must match rawResult.phaseProcess"),
            ("unconnected_bounds_tamper", lambda r: r["quantities"]["finalBodyTemperatureK"].__setitem__("bounds", ["300", "300"]), "does not match rawResult"),
            ("inverted_bounds", lambda r: r["quantities"]["finalBodyTemperatureK"].__setitem__("bounds", ["400", "300"]), "inverted interval bounds"),
            ("wrong_unit", lambda r: r["quantities"]["finalBodyTemperatureK"].__setitem__("unit", "C"), "unit must be 'K'"),
            ("post_exhaustion_true", lambda r: r["status"].__setitem__("postExhaustionModeled", True), "postExhaustionModeled must be False"),
            ("wrong_underlying_schema", lambda r: r.__setitem__("underlyingSchema", "sim_heat.wrong/1"), "underlyingSchema"),
            ("tampered_active_bc", lambda r: r["network"]["activeBoundaryConditions"]["cold"].__setitem__("temperatureK", "280"), "activeBoundaryConditions"),
            ("tampered_geometry", lambda r: r["geometry"].__setitem__("kind", "sphere"), "geometry"),
            ("tampered_inputs", lambda r: r["inputs"]["body"].__setitem__("initialBodyTemperatureK", "380"), "inputs.body"),
            ("tampered_source_hash", lambda r: r["evidence"]["sourceIdentity"].__setitem__(SOURCE_HASH_KEYS[0], "0" * 64), "must match top-level"),
        ]
        for label, mutate, pattern in mutations:
            with self.subTest(mutation=label):
                tampered = copy.deepcopy(good)
                mutate(tampered)
                with self.assertRaisesRegex(ValueError, pattern):
                    validate_investigation_record(tampered)

        # P2-A: radial exterior input tamper controls (non-convecting STAR + convecting LINK).
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        star_radial = run_investigation(InvestigationRequest(
            composition="radial_phase_bath",
            source=_source_ref(star_inputs),
            duration_s="600",
            phase_bath=PhaseBathSpec("cool", "273.15", "334000", "0.05", "0.05"),
            radial_shell=RadialShellPortSpec(
                surface_port="warm",
                geometry=RadialGeometrySpec("sphere", "0.1", (RadialLayerSpec("0.2", "2"),)),
                exterior=ExteriorExchangeSpec("290", "0.8", "0.0000000567"),
            ),
        ))
        link_conv_radial = run_investigation(InvestigationRequest(
            composition="radial_phase_bath",
            source=_source_ref(LINK),
            duration_s="5000",
            phase_bath=PhaseBathSpec("hot", "273.15", "334000", "0.02", "0.03"),
            radial_shell=RadialShellPortSpec(
                surface_port="cold",
                geometry=RadialGeometrySpec("cylinder", "0.1", (RadialLayerSpec("0.20", "2"),), cylinder_length_m="1"),
                exterior=ExteriorExchangeSpec("293.15", "0", "0.0000000567", air_k="293.15", h_w_per_m2_k="10"),
            ),
        ))
        radial_mutations = [
            ("star_emissivity_3", star_radial, lambda r: r["inputs"]["radialShell"]["exterior"].__setitem__("emissivity", "3")),
            ("star_enclosure_0", star_radial, lambda r: r["inputs"]["radialShell"]["exterior"].__setitem__("enclosureTemperatureK", "0")),
            ("star_sigma_1", star_radial, lambda r: r["inputs"]["radialShell"]["exterior"].__setitem__("sigmaWPerM2K4", "1")),
            ("star_spurious_air", star_radial, lambda r: r["inputs"]["radialShell"]["exterior"].__setitem__("airTemperatureK", "300")),
            ("link_air_tamper", link_conv_radial, lambda r: r["inputs"]["radialShell"]["exterior"].__setitem__("airTemperatureK", "350")),
            ("link_h_tamper", link_conv_radial, lambda r: r["inputs"]["radialShell"]["exterior"].__setitem__("convectionCoefficientWPerM2K", "25")),
            ("link_h_null", link_conv_radial, lambda r: r["inputs"]["radialShell"]["exterior"].__setitem__("convectionCoefficientWPerM2K", None)),
        ]
        for label, base_rec, mutate in radial_mutations:
            with self.subTest(mutation=label):
                tampered = copy.deepcopy(base_rec)
                mutate(tampered)
                with self.assertRaisesRegex(ValueError, "inputs.radialShell.exterior"):
                    validate_investigation_record(tampered)

    def test_ci_workflow_map_lists_every_workflow_file(self):
        workflow_map = (REPO_ROOT / "docs" / "CI_WORKFLOW_MAP.md").read_text(encoding="utf-8")
        workflows = sorted(p.name for p in (REPO_ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertGreater(len(workflows), 0)
        for name in workflows:
            self.assertIn(name, workflow_map, f"docs/CI_WORKFLOW_MAP.md is missing workflow {name}")
