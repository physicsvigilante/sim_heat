"""Tests for the typed offline investigation contract (sim_heat.offline_investigation/1)."""
import contextlib
import copy
from fractions import Fraction as F
import io
import json
from pathlib import Path
import tempfile
from unittest import TestCase

from qualification.h1_n13.conduction import ZERO, interval
from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.body_phase_bath_exchange import investigate as body_investigate
from tools.offline_investigation import (
    CONTRACT_SCHEMA,
    ENDPOINT_MEANING,
    EVIDENCE_CATEGORY,
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
            self.assertEqual(
                record["quantities"]["bathInflowDuringPlateauW"]["signConvention"],
                "into_phase_bath_positive",
            )
            self.assertEqual(
                record["quantities"]["surfaceOutwardHeatRateW"]["signConvention"],
                "outward_from_radial_surface_positive",
            )
            # Round-trip JSON serialization must survive without flag promotion or loss.
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
        # 2-terminal LINK (exhausted solid)
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

        # Malformed radial geometry: sphere with cylinder_length_m, cylinder without length, non-increasing radii
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

        # Tampered serialized record controls
        good = run_investigation(InvestigationRequest(
            composition="body_phase_bath_exchange",
            source=law,
            duration_s="100",
            phase_bath=PhaseBathSpec("cold", "273.15", "334000", "0.1", "0.1"),
            body=LumpedBodySpec("hot", "2000", "320"),
        ))
        for flag in OFFLINE_FLAG_KEYS:
            tampered = copy.deepcopy(good)
            tampered["evidence"][flag] = True
            with self.assertRaisesRegex(ValueError, "must be False"):
                validate_investigation_record(tampered)

        bad_post = copy.deepcopy(good)
        bad_post["status"]["postExhaustionModeled"] = True
        with self.assertRaisesRegex(ValueError, "postExhaustionModeled must be False"):
            validate_investigation_record(bad_post)

        bad_bounds = copy.deepcopy(good)
        bad_bounds["quantities"]["finalBodyTemperatureK"]["bounds"] = ["400", "300"]
        with self.assertRaisesRegex(ValueError, "inverted interval bounds"):
            validate_investigation_record(bad_bounds)

        bad_unit = copy.deepcopy(good)
        bad_unit["quantities"]["finalBodyTemperatureK"]["unit"] = "C"
        with self.assertRaisesRegex(ValueError, "unit must be 'K'"):
            validate_investigation_record(bad_unit)

        bad_hash = copy.deepcopy(good)
        bad_hash["evidence"]["sourceIdentity"][SOURCE_HASH_KEYS[0]] = "0" * 64
        with self.assertRaisesRegex(ValueError, "must match top-level"):
            validate_investigation_record(bad_hash)

    def test_ci_workflow_map_lists_every_workflow_file(self):
        workflow_map = (REPO_ROOT / "docs" / "CI_WORKFLOW_MAP.md").read_text(encoding="utf-8")
        workflows = sorted(p.name for p in (REPO_ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertGreater(len(workflows), 0)
        for name in workflows:
            self.assertIn(name, workflow_map, f"docs/CI_WORKFLOW_MAP.md is missing workflow {name}")
