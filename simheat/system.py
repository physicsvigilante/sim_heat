"""Canonical ``ThermalSystem`` description, governing-equation inspector, and unified dispatch (M03).

Provides:
- ``ThermalSystem`` (schema ``sim_heat.thermal_system/1``): declarative single-source-of-truth
  physical description supporting primitive conduction rods, read-only H1 AST adaptation (zero
  hand-written ``facts.json``), first-class validated ``DerivedLaw`` ingestion, and recursive
  ideal storage-free Schur-complement joins.
- ``describe_equations(system)``: deterministic structural derivation of the governing algebraic,
  ODE, enthalpy, and conservation equations directly from the authored AST.
- ``solve_system(system)``: dispatches to existing certified engines (``multiport``, ``staged``,
  ``multibody``) without reimplementing solver math, returning a unified result envelope
  (``sim_heat.thermal_result/1``) with normalized ``terminationReason``, achieved enclosure widths,
  explicit ``unsupported_regime`` mechanism pairs, and honest ``False`` offline evidence flags.
"""
from __future__ import annotations

from decimal import Decimal
import argparse
from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path
from typing import Any

from simheat.enthalpy import (
    DEFAULT_MAX_EVENTS,
    signed_decimal_input,
    solve_enthalpy_continuation,
)
from simheat.laws import (
    DERIVED_LAW_SCHEMA,
    DerivedLaw,
    ensure_derived_law,
    join_laws,
)
from simheat.radiative_transient import solve_radiative_transient
from simheat.rod_gen import RodGenerationModel, build_rod_generation_model
from simheat.stefan import parse_stefan_spec, solve_stefan_from_law
from tools.multibody_phase_network import solve_from_law as solve_multibody
from tools.multiport_thermal_network import solve_from_law as solve_multiport
from tools.offline_investigation import _expect_exact_keys
from tools.offline_provenance import OFFLINE_FLAG_KEYS
from tools.radiating_surface import decimal_input
from tools.staged_phase_body_network import solve_from_law as solve_staged

THERMAL_SYSTEM_SCHEMA = "sim_heat.thermal_system/1"
RESULT_ENVELOPE_SCHEMA = "sim_heat.thermal_result/1"

VALID_MODES = ("steady", "transient")
VALID_CONTINUATIONS = ("auto", "staged", "first_exhaustion")
VALID_ATTACHMENT_KINDS = (
    "maintained",
    "sensible_body",
    "phase_substance",
    "exterior_surface",
    "radial_shell",
    "stefan_layer",
)


def _resolve_conduction(
    spec: dict[str, Any],
    *,
    top_nodes: list[str] | None = None,
    base_dir: Path | None = None,
    system_id: str | None = None,
    allow_rod_generation: bool = True,
) -> tuple[DerivedLaw, RodGenerationModel | None]:
    """Recursively resolve a declarative conduction specification into a certified ``DerivedLaw``."""
    if not isinstance(spec, dict):
        raise ValueError("conduction specification must be a mapping")
    kind = spec.get("kind")
    if kind is None and "rods" in spec:
        kind = "rods"

    if kind == "rods":
        _expect_exact_keys(
            spec,
            required=("rods",),
            optional=("kind", "nodes", "terminals", "lawId"),
            label="conduction(rods)",
        )
        nodes = spec.get("nodes", top_nodes)
        rods = spec.get("rods")
        terminals = spec.get("terminals")
        if not isinstance(rods, dict):
            raise ValueError("conduction(rods).rods must be a mapping")
        passive_rods: dict[str, dict[str, Any]] = {}
        has_gen = False
        for r_name, r_spec in rods.items():
            if not isinstance(r_spec, dict):
                raise ValueError(f"rods[{r_name}] must be a mapping")
            if "generatedPowerW" in r_spec:
                p_val = decimal_input(r_spec["generatedPowerW"], f"rods[{r_name}].generatedPowerW")
                if p_val > 0:
                    if not allow_rod_generation:
                        raise ValueError(
                            "rod generatedPowerW inside conduction.join is not supported; "
                            "author the connected rod graph directly in conduction.rods"
                        )
                    has_gen = True
                passive_rods[r_name] = {k: v for k, v in r_spec.items() if k != "generatedPowerW"}
            else:
                passive_rods[r_name] = r_spec
        law = DerivedLaw.from_rods(nodes, passive_rods, terminals=terminals, law_id=spec.get("lawId") or system_id)
        rod_gen = build_rod_generation_model(list(nodes), list(law.terminals), rods) if has_gen else None
        return law, rod_gen

    if kind == "h1_study":
        _expect_exact_keys(
            spec,
            required=("kind", "studyPath", "rootPath"),
            optional=("terminals", "lawId"),
            label="conduction(h1_study)",
        )
        study_p = Path(spec["studyPath"])
        root_p = Path(spec["rootPath"])
        if base_dir is not None:
            if not study_p.is_absolute():
                study_p = base_dir / study_p
            if not root_p.is_absolute():
                root_p = base_dir / root_p
        return (
            DerivedLaw.from_h1_study(
                study_p,
                root_p,
                terminals=spec.get("terminals"),
                law_id=spec.get("lawId"),
            ),
            None,
        )

    if kind == "derived_law":
        _expect_exact_keys(spec, required=("kind", "law"), label="conduction(derived_law)")
        return ensure_derived_law(spec["law"]), None

    if kind == "derived_law_ref":
        _expect_exact_keys(
            spec,
            required=("kind", "path"),
            optional=("sha256",),
            label="conduction(derived_law_ref)",
        )
        law_p = Path(spec["path"])
        if base_dir is not None and not law_p.is_absolute():
            law_p = base_dir / law_p
        return DerivedLaw.from_file(law_p, expected_sha256=spec.get("sha256")), None

    if kind == "join":
        _expect_exact_keys(
            spec,
            required=("kind", "left", "right", "contacts"),
            optional=("leftPrefix", "rightPrefix", "lawId"),
            label="conduction(join)",
        )
        left_law, _ = _resolve_conduction(spec["left"], base_dir=base_dir, allow_rod_generation=False)
        right_law, _ = _resolve_conduction(spec["right"], base_dir=base_dir, allow_rod_generation=False)
        return (
            join_laws(
                left_law,
                right_law,
                spec["contacts"],
                left_prefix=spec.get("leftPrefix", "left"),
                right_prefix=spec.get("rightPrefix", "right"),
                law_id=spec.get("lawId") or system_id,
            ),
            None,
        )

    raise ValueError(
        f"unsupported conduction kind {kind!r}; expected one of "
        "('rods', 'h1_study', 'derived_law', 'derived_law_ref', 'join')"
    )


def _decimal_str(raw: str) -> str:
    """Return a clean unsigned SI decimal string (never a Fraction slash string)."""
    return raw.strip()


def _fraction_to_decimal_str(val: Fraction) -> str:
    """Convert an exact terminating rational Fraction to an unsigned decimal string with arbitrary precision."""
    if val < 0:
        raise ValueError(f"negative value {val} cannot be represented as an unsigned decimal")
    if val == 0:
        return "0"
    num = val.numerator
    den = val.denominator
    n2 = 0
    while den % 2 == 0:
        den //= 2
        n2 += 1
    n5 = 0
    while den % 5 == 0:
        den //= 5
        n5 += 1
    if den != 1:
        raise ValueError(f"non-terminating decimal value {val}")
    scale = max(n2, n5)
    scaled = num * (5 ** (scale - n5)) * (2 ** (scale - n2))
    if scale == 0:
        return str(scaled)
    digits = str(scaled).rjust(scale + 1, "0")
    whole = digits[:-scale]
    frac = digits[-scale:].rstrip("0")
    return f"{whole}.{frac}" if frac else whole


def _parse_attachment(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise ValueError(f"attachments[{name}] must be a mapping")
    kind = spec.get("kind")
    if kind not in VALID_ATTACHMENT_KINDS:
        raise ValueError(
            f"attachments[{name}] has unsupported kind {kind!r}; expected one of {VALID_ATTACHMENT_KINDS}"
        )

    if kind == "maintained":
        _expect_exact_keys(spec, required=("kind", "temperatureK"), label=f"attachments[{name}]")
        temp = decimal_input(spec["temperatureK"], f"maintained temperature at {name}")
        return {"kind": "maintained", "temperatureK": _decimal_str(spec["temperatureK"]), "temp": temp}

    if kind == "sensible_body":
        _expect_exact_keys(
            spec,
            required=("kind", "initialTemperatureK"),
            optional=("heatCapacityJPerK", "massKg", "specificHeatJPerKgK", "heatInputW"),
            label=f"attachments[{name}]",
        )
        t0 = decimal_input(spec["initialTemperatureK"], f"initial temperature at {name}")
        has_c = "heatCapacityJPerK" in spec
        has_mc = "massKg" in spec or "specificHeatJPerKgK" in spec
        if has_mc and ("massKg" not in spec or "specificHeatJPerKgK" not in spec):
            raise ValueError(f"attachments[{name}] requires both massKg and specificHeatJPerKgK")
        if not has_c and not has_mc:
            raise ValueError(
                f"attachments[{name}] requires heatCapacityJPerK or (massKg and specificHeatJPerKgK)"
            )
        if has_c:
            cap = decimal_input(spec["heatCapacityJPerK"], f"heat capacity at {name}")
            if cap <= 0:
                raise ValueError(f"positive heatCapacityJPerK required at {name}")
            cap_str = _decimal_str(spec["heatCapacityJPerK"])
            if has_mc:
                m = decimal_input(spec["massKg"], f"mass at {name}")
                c = decimal_input(spec["specificHeatJPerKgK"], f"specific heat at {name}")
                if m <= 0 or c <= 0 or m * c != cap:
                    raise ValueError(f"attachments[{name}] massKg * specificHeatJPerKgK disagrees with heatCapacityJPerK")
        else:
            m = decimal_input(spec["massKg"], f"mass at {name}")
            c = decimal_input(spec["specificHeatJPerKgK"], f"specific heat at {name}")
            if m <= 0 or c <= 0:
                raise ValueError(f"positive massKg and specificHeatJPerKgK required at {name}")
            cap = m * c
            cap_str = _fraction_to_decimal_str(cap)
        if "heatInputW" in spec:
            power = signed_decimal_input(spec["heatInputW"], f"heatInputW at {name}")
            power_str = spec["heatInputW"].strip()
        else:
            power = Fraction(0)
            power_str = "0"
        return {
            "kind": "sensible_body",
            "heatCapacityJPerK": cap_str,
            "initialTemperatureK": _decimal_str(spec["initialTemperatureK"]),
            "heatInputW": power_str,
            "capacity": cap,
            "t0": t0,
            "heat_input": power,
        }

    if kind == "phase_substance":
        _expect_exact_keys(
            spec,
            required=(
                "kind",
                "transitionTemperatureK",
                "specificLatentHeatJPerKg",
                "initialSolidKg",
                "initialLiquidKg",
            ),
            optional=(
                "initialTemperatureK",
                "solidSpecificHeatJPerKgK",
                "liquidSpecificHeatJPerKgK",
                "heatInputW",
            ),
            label=f"attachments[{name}]",
        )
        t_tr = decimal_input(spec["transitionTemperatureK"], f"transition temperature at {name}")
        latent = decimal_input(spec["specificLatentHeatJPerKg"], f"specific latent heat at {name}")
        solid = decimal_input(spec["initialSolidKg"], f"initial solid mass at {name}")
        liquid = decimal_input(spec["initialLiquidKg"], f"initial liquid mass at {name}")
        if t_tr <= 0 or latent <= 0 or solid < 0 or liquid < 0 or (solid + liquid) <= 0:
            raise ValueError(f"invalid phase_substance parameters at {name}")
        if "initialTemperatureK" in spec:
            t0 = decimal_input(spec["initialTemperatureK"], f"initial temperature at {name}")
            t0_str = _decimal_str(spec["initialTemperatureK"])
        else:
            t0 = t_tr
            t0_str = _decimal_str(spec["transitionTemperatureK"])
        if t0 < t_tr and (solid <= 0 or liquid != 0):
            raise ValueError(f"subcooled phase_substance at {name} requires positive solid and zero liquid")
        if t0 > t_tr and (liquid <= 0 or solid != 0):
            raise ValueError(f"superheated phase_substance at {name} requires positive liquid and zero solid")
        has_cs = "solidSpecificHeatJPerKgK" in spec
        has_cl = "liquidSpecificHeatJPerKgK" in spec
        if has_cs != has_cl:
            raise ValueError(
                f"attachments[{name}] must specify both solidSpecificHeatJPerKgK and liquidSpecificHeatJPerKgK or neither"
            )
        c_s = c_l = None
        c_s_str = c_l_str = None
        if has_cs:
            c_s = decimal_input(spec["solidSpecificHeatJPerKgK"], f"solid specific heat at {name}")
            c_l = decimal_input(spec["liquidSpecificHeatJPerKgK"], f"liquid specific heat at {name}")
            if c_s <= 0 or c_l <= 0:
                raise ValueError(f"positive solid and liquid specific heats required at {name}")
            c_s_str = _decimal_str(spec["solidSpecificHeatJPerKgK"])
            c_l_str = _decimal_str(spec["liquidSpecificHeatJPerKgK"])
        if "heatInputW" in spec:
            power = signed_decimal_input(spec["heatInputW"], f"heatInputW at {name}")
            power_str = spec["heatInputW"].strip()
        else:
            power = Fraction(0)
            power_str = "0"
        return {
            "kind": "phase_substance",
            "transitionTemperatureK": _decimal_str(spec["transitionTemperatureK"]),
            "specificLatentHeatJPerKg": _decimal_str(spec["specificLatentHeatJPerKg"]),
            "initialSolidKg": _decimal_str(spec["initialSolidKg"]),
            "initialLiquidKg": _decimal_str(spec["initialLiquidKg"]),
            "initialTemperatureK": t0_str,
            "solidSpecificHeatJPerKgK": c_s_str,
            "liquidSpecificHeatJPerKgK": c_l_str,
            "heatInputW": power_str,
            "t_tr": t_tr,
            "t0": t0,
            "latent": latent,
            "solid": solid,
            "liquid": liquid,
            "c_s": c_s,
            "c_l": c_l,
            "heat_input": power,
        }

    if kind == "exterior_surface":
        _expect_exact_keys(
            spec,
            required=("kind", "areaM2", "enclosureTemperatureK", "emissivity", "sigmaWPerM2K4"),
            optional=("airTemperatureK", "convectionCoefficientWPerM2K"),
            label=f"attachments[{name}]",
        )
        decimal_input(spec["areaM2"], f"area at {name}")
        decimal_input(spec["enclosureTemperatureK"], f"enclosure T at {name}")
        decimal_input(spec["emissivity"], f"emissivity at {name}")
        decimal_input(spec["sigmaWPerM2K4"], f"sigma at {name}")
        out = {
            "kind": "exterior_surface",
            "areaM2": _decimal_str(spec["areaM2"]),
            "enclosureTemperatureK": _decimal_str(spec["enclosureTemperatureK"]),
            "emissivity": _decimal_str(spec["emissivity"]),
            "sigmaWPerM2K4": _decimal_str(spec["sigmaWPerM2K4"]),
        }
        if ("airTemperatureK" in spec) != ("convectionCoefficientWPerM2K" in spec):
            raise ValueError(f"attachments[{name}] must provide both airTemperatureK and convectionCoefficientWPerM2K")
        if "airTemperatureK" in spec:
            decimal_input(spec["airTemperatureK"], f"air T at {name}")
            decimal_input(spec["convectionCoefficientWPerM2K"], f"h at {name}")
            out["airTemperatureK"] = _decimal_str(spec["airTemperatureK"])
            out["convectionCoefficientWPerM2K"] = _decimal_str(spec["convectionCoefficientWPerM2K"])
        return out

    if kind == "stefan_layer":
        parsed = parse_stefan_spec(spec, f"attachments[{name}]")
        norm_spec = {
            **{k: (_decimal_str(v) if isinstance(v, str) and k != "kind" else v) for k, v in spec.items()},
            "geometry": {
                k: (_decimal_str(v) if isinstance(v, str) and k != "kind" else v)
                for k, v in spec["geometry"].items()
            },
        }
        return {"kind": "stefan_layer", "spec": norm_spec, "parsed": parsed}

    # radial_shell
    _expect_exact_keys(spec, required=("kind", "geometry", "exterior"), label=f"attachments[{name}]")
    geom = spec["geometry"]
    ext = spec["exterior"]
    if not isinstance(geom, dict) or not isinstance(ext, dict):
        raise ValueError(f"attachments[{name}] geometry and exterior must be mappings")
    g_kind = geom.get("kind")
    if g_kind not in ("sphere", "cylinder"):
        raise ValueError(f"attachments[{name}].geometry.kind must be 'sphere' or 'cylinder'")
    if g_kind == "sphere":
        _expect_exact_keys(
            geom,
            required=("kind", "innerRadiusM", "layers"),
            label=f"attachments[{name}].geometry",
        )
        norm_geom: dict[str, Any] = {"kind": "sphere"}
    else:
        _expect_exact_keys(
            geom,
            required=("kind", "innerRadiusM", "cylinderLengthM", "layers"),
            label=f"attachments[{name}].geometry",
        )
        cyl_len = decimal_input(geom["cylinderLengthM"], f"cylinder length at {name}")
        if cyl_len <= 0:
            raise ValueError(f"positive cylinderLengthM required at {name}")
        norm_geom = {"kind": "cylinder", "cylinderLengthM": _decimal_str(geom["cylinderLengthM"])}
    r_prev = decimal_input(geom["innerRadiusM"], f"inner radius at {name}")
    if r_prev <= 0:
        raise ValueError(f"positive innerRadiusM required at {name}")
    norm_geom["innerRadiusM"] = _decimal_str(geom["innerRadiusM"])
    raw_layers = geom["layers"]
    if not isinstance(raw_layers, list) or not (1 <= len(raw_layers) <= 32):
        raise ValueError(f"attachments[{name}].geometry.layers must be a list of 1 to 32 layer mappings")
    norm_layers = []
    for idx, layer in enumerate(raw_layers):
        if not isinstance(layer, dict):
            raise ValueError(f"attachments[{name}].geometry.layers[{idx}] must be a mapping")
        _expect_exact_keys(
            layer,
            required=("outerRadiusM", "conductivityWPerMK"),
            label=f"attachments[{name}].geometry.layers[{idx}]",
        )
        r_out = decimal_input(layer["outerRadiusM"], f"layer {idx} outerRadiusM at {name}")
        k_val = decimal_input(layer["conductivityWPerMK"], f"layer {idx} conductivityWPerMK at {name}")
        if r_out <= r_prev or k_val <= 0:
            raise ValueError(
                f"attachments[{name}].geometry.layers[{idx}] requires strictly increasing outerRadiusM and positive conductivityWPerMK"
            )
        r_prev = r_out
        norm_layers.append({
            "outerRadiusM": _decimal_str(layer["outerRadiusM"]),
            "conductivityWPerMK": _decimal_str(layer["conductivityWPerMK"]),
        })
    norm_geom["layers"] = norm_layers

    _expect_exact_keys(
        ext,
        required=("enclosureTemperatureK", "emissivity", "sigmaWPerM2K4"),
        optional=("airTemperatureK", "convectionCoefficientWPerM2K"),
        label=f"attachments[{name}].exterior",
    )
    decimal_input(ext["enclosureTemperatureK"], f"enclosure T at {name}")
    eps_val = decimal_input(ext["emissivity"], f"emissivity at {name}")
    sig_val = decimal_input(ext["sigmaWPerM2K4"], f"sigma at {name}")
    if eps_val > 1 or sig_val <= 0:
        raise ValueError(f"attachments[{name}].exterior requires emissivity in [0,1] and positive sigma")
    norm_ext: dict[str, Any] = {
        "enclosureTemperatureK": _decimal_str(ext["enclosureTemperatureK"]),
        "emissivity": _decimal_str(ext["emissivity"]),
        "sigmaWPerM2K4": _decimal_str(ext["sigmaWPerM2K4"]),
    }
    if ("airTemperatureK" in ext) != ("convectionCoefficientWPerM2K" in ext):
        raise ValueError(
            f"attachments[{name}].exterior must provide both airTemperatureK and convectionCoefficientWPerM2K"
        )
    if "airTemperatureK" in ext:
        decimal_input(ext["airTemperatureK"], f"air T at {name}")
        decimal_input(ext["convectionCoefficientWPerM2K"], f"h at {name}")
        norm_ext["airTemperatureK"] = _decimal_str(ext["airTemperatureK"])
        norm_ext["convectionCoefficientWPerM2K"] = _decimal_str(ext["convectionCoefficientWPerM2K"])
    return {"kind": "radial_shell", "geometry": norm_geom, "exterior": norm_ext}


@dataclass(frozen=True)
class ThermalSystem:
    """Validated canonical declarative thermal system."""

    system_id: str
    derived_law: DerivedLaw
    attachments: dict[str, dict[str, Any]]
    mode: str
    duration_s: str | None
    continuation: str
    max_sweeps: int
    initial_steps: int
    observations: tuple[str, ...]
    max_events: int = DEFAULT_MAX_EVENTS
    rod_generation: RodGenerationModel | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, base_dir: str | Path | None = None) -> ThermalSystem:
        if not isinstance(payload, dict):
            raise ValueError("ThermalSystem payload must be a mapping")
        if payload.get("schema") != THERMAL_SYSTEM_SCHEMA:
            raise ValueError(f"ThermalSystem schema must be {THERMAL_SYSTEM_SCHEMA!r}")
        _expect_exact_keys(
            payload,
            required=("schema", "id", "conduction", "attachments", "solve"),
            optional=("nodes",),
            label="ThermalSystem",
        )
        system_id = payload["id"]
        if not isinstance(system_id, str) or not system_id.strip():
            raise ValueError("ThermalSystem id must be a non-empty string")
        base_path = Path(base_dir) if base_dir is not None else None
        top_nodes = payload.get("nodes")
        conduction = payload["conduction"]
        if isinstance(conduction, dict) and conduction.get("kind") in (None, "rods") and "terminals" not in conduction:
            if isinstance(payload["attachments"], dict):
                conduction = {**conduction, "terminals": sorted(payload["attachments"].keys())}
        derived_law, rod_generation = _resolve_conduction(
            conduction,
            top_nodes=top_nodes,
            base_dir=base_path,
            system_id=system_id,
        )

        raw_att = payload["attachments"]
        if not isinstance(raw_att, dict) or set(raw_att) != set(derived_law.terminals):
            raise ValueError(
                f"attachments keys {sorted(raw_att) if isinstance(raw_att, dict) else raw_att!r} "
                f"must match conduction terminals {list(derived_law.terminals)}"
            )
        attachments = {t: _parse_attachment(t, raw_att[t]) for t in derived_law.terminals}

        solve = payload["solve"]
        if not isinstance(solve, dict):
            raise ValueError("solve must be a mapping")
        _expect_exact_keys(
            solve,
            required=("mode",),
            optional=("durationS", "continuation", "maxSweeps", "initialSteps", "maxEvents", "observations"),
            label="solve",
        )
        mode = solve["mode"]
        if mode not in VALID_MODES:
            raise ValueError(f"solve.mode must be one of {VALID_MODES}, got {mode!r}")
        continuation = solve.get("continuation", "auto")
        if continuation not in VALID_CONTINUATIONS:
            raise ValueError(f"solve.continuation must be one of {VALID_CONTINUATIONS}, got {continuation!r}")
        duration_raw = solve.get("durationS")
        if mode == "transient" and duration_raw is None:
            raise ValueError("solve.durationS is required in transient mode")
        if duration_raw is None:
            duration_s = None
        else:
            decimal_input(duration_raw, "solve.durationS")
            duration_s = _decimal_str(duration_raw)
        max_sweeps = solve.get("maxSweeps", 120)
        if isinstance(max_sweeps, bool) or not isinstance(max_sweeps, int) or max_sweeps < 1:
            raise ValueError("solve.maxSweeps must be a positive integer")
        initial_steps = solve.get("initialSteps", 16)
        if isinstance(initial_steps, bool) or not isinstance(initial_steps, int) or not (1 <= initial_steps <= 256):
            raise ValueError("solve.initialSteps must be an integer in [1, 256]")
        max_events = solve.get("maxEvents", DEFAULT_MAX_EVENTS)
        if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 1:
            raise ValueError("solve.maxEvents must be a positive integer")
        obs = tuple(solve.get("observations", ()))
        if any(not isinstance(o, str) or not o for o in obs):
            raise ValueError("solve.observations must contain non-empty strings")

        return cls(
            system_id=system_id,
            derived_law=derived_law,
            attachments=attachments,
            mode=mode,
            duration_s=duration_s,
            continuation=continuation,
            max_sweeps=max_sweeps,
            initial_steps=initial_steps,
            observations=obs,
            max_events=max_events,
            rod_generation=rod_generation,
        )

    @classmethod
    def from_file(cls, path: str | Path) -> ThermalSystem:
        p = Path(path)
        payload = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(payload, base_dir=p.parent)


def _classify_dispatch(system: ThermalSystem) -> tuple[str | None, list[str] | None, str | None]:
    """Return ``(backend_name, unsupported_pair, unsupported_reason)``."""
    kinds_by_port = {t: system.attachments[t]["kind"] for t in system.derived_law.terminals}
    bodies = [t for t, k in kinds_by_port.items() if k == "sensible_body"]
    phases = [t for t, k in kinds_by_port.items() if k == "phase_substance"]
    exteriors = [t for t, k in kinds_by_port.items() if k in ("exterior_surface", "radial_shell")]
    stefans = [t for t, k in kinds_by_port.items() if k == "stefan_layer"]
    has_rod_gen = system.rod_generation is not None
    non_coex_phases = [
        t for t in phases if system.attachments[t]["t0"] != system.attachments[t]["t_tr"]
    ]
    powered = [
        t
        for t in bodies + phases
        if system.attachments[t].get("heat_input", Fraction(0)) != 0
    ]

    if system.mode == "steady":
        if stefans:
            return (
                None,
                ["steady_mode", "stefan_layer"],
                "Quasi-steady Stefan moving-boundary front requires transient mode.",
            )
        if bodies:
            return (
                None,
                ["steady_mode", "sensible_body"],
                "Steady solves do not accept finite heat-capacity sensible_body attachments (C = 0 != t -> inf).",
            )
        if non_coex_phases:
            return (
                None,
                ["steady_mode", "non_coexisting_phase_substance"],
                "Steady plateau solves require phase_substance attachments to start at T_0 == T_tr.",
            )
        if powered:
            return (
                None,
                ["steady_mode", "heat_input"],
                "Steady multiport solves do not accept prescribed heatInputW power injections.",
            )
        return "multiport", None, None

    # transient mode
    if stefans:
        if len(stefans) > 1:
            return (
                None,
                ["stefan_layer", "multiple_stefan_layers"],
                "Coupled multi-front Stefan layers are not supported (single stefan_layer with maintained terminals only).",
            )
        if exteriors:
            ext_kind = kinds_by_port[exteriors[0]]
            return (
                None,
                [ext_kind, "stefan_layer"],
                f"Coupled transient {ext_kind} + stefan_layer requires a nonlinear moving-boundary integrator.",
            )
        if bodies:
            return (
                None,
                ["stefan_layer", "sensible_body"],
                "Coupled transient stefan_layer + sensible_body is not supported (single stefan_layer with maintained terminals only).",
            )
        if phases:
            return (
                None,
                ["stefan_layer", "phase_substance"],
                "Coupled transient stefan_layer + phase_substance is not supported (single stefan_layer with maintained terminals only).",
            )
        return "stefan", None, None

    def _require_phase_heats(port_list: list[str]) -> None:
        for p_name in port_list:
            p = system.attachments[p_name]
            if p["c_s"] is None or p["c_l"] is None:
                raise ValueError(
                    f"enthalpy continuation at {p_name!r} requires solidSpecificHeatJPerKgK and liquidSpecificHeatJPerKgK"
                )

    if exteriors:
        ext_kind = kinds_by_port[exteriors[0]]
        if not bodies and not phases:
            return (
                None,
                [ext_kind, "transient_mode"],
                f"Transient {ext_kind} solve requires at least one sensible_body or phase_substance attachment (C = 0 != t -> inf).",
            )
        if system.continuation == "first_exhaustion":
            return (
                None,
                ["first_exhaustion", ext_kind],
                f"first_exhaustion mode does not support {ext_kind}; use continuation='auto' or 'staged' for radiative_transient.",
            )
        _require_phase_heats(phases)
        return "radiative_transient", None, None

    if system.continuation == "first_exhaustion":
        if non_coex_phases:
            return (
                None,
                ["first_exhaustion", "non_coexisting_phase_substance"],
                "first_exhaustion mode requires phase_substance ports to start in coexistence (T_0 == T_tr).",
            )
        if powered:
            return (
                None,
                ["first_exhaustion", "heat_input"],
                "first_exhaustion mode does not accept nonzero heatInputW; use continuation='auto' or 'staged'.",
            )
        if has_rod_gen and bodies:
            return (
                None,
                ["first_exhaustion", "rod_generation"],
                "first_exhaustion multibody mode does not accept rod generatedPowerW; use continuation='auto' or 'staged'.",
            )
        if bodies:
            return "multibody", None, None
        if phases:
            return "multiport", None, None

    all_phases_have_heats = bool(phases) and all(
        system.attachments[t]["c_s"] is not None and system.attachments[t]["c_l"] is not None
        for t in phases
    )

    if bodies:
        wants_enthalpy = (
            bool(powered)
            or bool(non_coex_phases)
            or has_rod_gen
            or (system.continuation == "staged" and bool(phases))
            or (system.continuation == "auto" and all_phases_have_heats)
        )
        if wants_enthalpy:
            _require_phase_heats(phases)
            return "enthalpy", None, None
        return "multibody", None, None

    if len(phases) == 1:
        p = system.attachments[phases[0]]
        if powered:
            _require_phase_heats(phases)
            return "enthalpy", None, None
        wants_staged = (
            system.continuation == "staged"
            or p["t0"] != p["t_tr"]
            or (system.continuation == "auto" and p["c_s"] is not None and p["c_l"] is not None)
        )
        if wants_staged:
            if p["c_s"] is None or p["c_l"] is None:
                raise ValueError(
                    f"staged transient at {phases[0]!r} requires solidSpecificHeatJPerKgK and liquidSpecificHeatJPerKgK"
                )
            return "staged", None, None
        return "multiport", None, None

    if len(phases) >= 2:
        wants_enthalpy = (
            bool(powered)
            or bool(non_coex_phases)
            or system.continuation == "staged"
            or (system.continuation == "auto" and all_phases_have_heats)
        )
        if wants_enthalpy:
            _require_phase_heats(phases)
            return "enthalpy", None, None
        return "multiport", None, None

    return (
        None,
        ["transient_mode", "maintained_only"],
        "Transient solve requires at least one sensible_body, phase_substance, or stefan_layer attachment.",
    )


def describe_equations(system: ThermalSystem | dict[str, Any]) -> dict[str, Any]:
    """Deterministically derive governing equations and sign conventions from a ``ThermalSystem``."""
    sys_obj = system if isinstance(system, ThermalSystem) else ThermalSystem.from_dict(system)
    law = sys_obj.derived_law
    backend, unsup_pair, unsup_reason = _classify_dispatch(sys_obj)

    terms = list(law.terminals)
    conduction_lines = [
        f"Conduction network ({law.lineage.get('kind')}): terminals = {terms}",
        "Sign convention: Q_supply[i] = sum_j W[i][j] * T[j]  (W, positive INTO conduction network)",
    ]
    if law.lineage.get("eliminatedJunctions"):
        conduction_lines.append(
            f"Schur/Kron eliminated internal junctions: {law.lineage['eliminatedJunctions']}"
        )
    if law.lineage.get("kind") == "schur_join":
        conduction_lines.append(
            f"Schur-complement joined contacts: {law.lineage['contacts']}"
        )
    for i in terms:
        row_terms = []
        for j in terms:
            lo, hi = law.matrix[i][j]
            coeff = str(lo) if lo == hi else f"[{lo}, {hi}]"
            row_terms.append(f"({coeff})*T[{j}]")
        conduction_lines.append(f"  Q_supply[{i}] = " + " + ".join(row_terms))
    if sys_obj.rod_generation is not None:
        rg = sys_obj.rod_generation
        conduction_lines.append(
            f"Uniform rod heat generation (total P_gen = {rg.total_generated_power_w} W) "
            "Norton-reduced to terminal injections I_Norton[i] (positive into terminal):"
        )
        for i in terms:
            ilo, ihi = rg.terminal_injections_w[i]
            val = str(ilo) if ilo == ihi else f"[{ilo}, {ihi}]"
            conduction_lines.append(f"  I_Norton[{i}] = {val} W")

    terminal_eqs: dict[str, str] = {}
    for t in terms:
        att = sys_obj.attachments[t]
        kind = att["kind"]
        norton_term = f" + I_Norton[{t}]" if sys_obj.rod_generation is not None else ""
        if kind == "maintained":
            terminal_eqs[t] = (
                f"T[{t}] = {att['temperatureK']} K; "
                f"Q_in[{t}] = -Q_supply[{t}]{norton_term} (into maintained reservoir positive)"
            )
        elif kind == "sensible_body":
            p_term = f" + ({att['heatInputW']} W)" if att["heat_input"] != 0 else ""
            terminal_eqs[t] = (
                f"{att['heatCapacityJPerK']} * dT[{t}]/dt = -Q_supply[{t}]{norton_term}{p_term}, "
                f"T[{t}](0) = {att['initialTemperatureK']} K (into body positive)"
            )
        elif kind == "phase_substance":
            p_term = f" + ({att['heatInputW']} W)" if att["heat_input"] != 0 else ""
            if backend in ("staged", "enthalpy", "radiative_transient"):
                m_tot = att["solid"] + att["liquid"]
                terminal_eqs[t] = (
                    f"Piecewise enthalpy H[{t}] (M = {m_tot} kg, T_tr = {att['transitionTemperatureK']} K, "
                    f"L = {att['specificLatentHeatJPerKg']} J/kg, c_s = {att['solidSpecificHeatJPerKgK']}, "
                    f"c_l = {att['liquidSpecificHeatJPerKgK']}): "
                    f"dH[{t}]/dt = -Q_supply[{t}]{norton_term}{p_term}, T[{t}](0) = {att['initialTemperatureK']} K"
                )
            else:
                terminal_eqs[t] = (
                    f"T[{t}] = {att['transitionTemperatureK']} K during coexistence; "
                    f"dH[{t}]/dt = -Q_supply[{t}]{norton_term}{p_term}, "
                    f"m_s(0) = {att['initialSolidKg']} kg, m_l(0) = {att['initialLiquidKg']} kg, "
                    f"L = {att['specificLatentHeatJPerKg']} J/kg (into phase bath positive)"
                )
        elif kind == "exterior_surface":
            h_term = (
                f"{att['convectionCoefficientWPerM2K']}*(T[{t}] - {att['airTemperatureK']}) + "
                if "airTemperatureK" in att
                else ""
            )
            terminal_eqs[t] = (
                f"Q_out[{t}] = -Q_supply[{t}]{norton_term} = {att['areaM2']} * "
                f"[{h_term}{att['emissivity']}*{att['sigmaWPerM2K4']}*(T[{t}]^4 - {att['enclosureTemperatureK']}^4)] "
                "(outward positive)"
            )
        elif kind == "stefan_layer":
            sp = att["spec"]
            g = sp["geometry"]
            g_kind = g["kind"]
            if g_kind == "planar":
                terminal_eqs[t] = (
                    f"Quasi-steady planar Stefan front at {t}: rho*L*A*ds/dt = "
                    f"(T_tr - T_eq_eff)/(R_ext + s/(k*A)), "
                    f"T_tr={sp['transitionTemperatureK']} K, s(0)={g['initialThicknessM']} m, "
                    f"k={sp['layerConductivityWPerMK']} W/(m*K), A={g['areaM2']} m^2"
                )
            elif g_kind == "cylinder":
                terminal_eqs[t] = (
                    f"Quasi-steady cylindrical Stefan front at {t}: rho*L*2*pi*r*L_c*dr/dt = "
                    f"(T_tr - T_eq_eff)/(R_ext + ln(r/r0)/(2*pi*k*L_c)), "
                    f"T_tr={sp['transitionTemperatureK']} K, r0={g['coreRadiusM']} m, r(0)={g['initialOuterRadiusM']} m"
                )
            else:
                terminal_eqs[t] = (
                    f"Quasi-steady spherical Stefan front at {t}: rho*L*4*pi*r^2*dr/dt = "
                    f"(T_tr - T_eq_eff)/(R_ext + (1/r0 - 1/r)/(4*pi*k)), "
                    f"T_tr={sp['transitionTemperatureK']} K, r0={g['coreRadiusM']} m, r(0)={g['initialOuterRadiusM']} m"
                )
        else:  # radial_shell
            g = att["geometry"]
            e = att["exterior"]
            h_term = (
                f"{e['convectionCoefficientWPerM2K']}*(T_s[{t}] - {e['airTemperatureK']}) + "
                if "airTemperatureK" in e
                else ""
            )
            terminal_eqs[t] = (
                f"Q_out[{t}] = -Q_supply[{t}]{norton_term} = G_shell({g.get('kind')}, r_in={g.get('innerRadiusM')}, "
                f"{len(g.get('layers', []))} layers)*(T[{t}] - T_s[{t}]) = "
                f"A_out[{t}]*[{h_term}{e.get('emissivity')}*{e.get('sigmaWPerM2K4')}*"
                f"(T_s[{t}]^4 - {e.get('enclosureTemperatureK')}^4)] (outward positive)"
            )

    has_rod_gen = sys_obj.rod_generation is not None
    if sys_obj.mode == "steady":
        conservation = (
            f"Global steady conservation: sum_i Q_out[i] = {sys_obj.rod_generation.total_generated_power_w} W (rod heat generation)"
            if has_rod_gen
            else "Global steady conservation: sum_i Q_supply[i] = 0 W"
        )
    elif backend == "stefan":
        conservation = (
            "Quasi-steady Stefan moving-boundary latent balance: "
            "rho * L * dV_solid/dt = (T_tr - T_eq_eff) / (R_ext + R_layer(front)) "
            "(sensible storage inside growing layer neglected)"
        )
    else:
        has_power = any(
            sys_obj.attachments[t].get("heat_input", Fraction(0)) != 0 for t in terms
        )
        if has_power and has_rod_gen:
            rhs = f"(sum_n P_n + {sys_obj.rod_generation.total_generated_power_w}) * t_stop J"
        elif has_rod_gen:
            rhs = f"{sys_obj.rod_generation.total_generated_power_w} * t_stop J"
        elif has_power:
            rhs = "sum_n P_n * t_stop J"
        else:
            rhs = "0 J"
        ext_term = " + sum_exteriors E_out,e" if backend == "radiative_transient" else ""
        conservation = (
            "Global transient energy ledger on [0, t_stop]: "
            f"sum_bodies C_i*(T_i(t_stop) - T_i(0)) + sum_phases DeltaH_k + sum_maintained E_in,m{ext_term} = {rhs}"
        )

    lines = list(conduction_lines) + ["Terminal constitutive equations:"]
    for t in terms:
        lines.append(f"  [{t}] {terminal_eqs[t]}")
    lines.append(conservation)
    if unsup_pair is not None:
        lines.append(f"Dispatch status: unsupported_regime {unsup_pair} ({unsup_reason})")
    else:
        lines.append(f"Selected certified backend: {backend}")

    conduction_summary: dict[str, Any] = {
        "lineageKind": law.lineage.get("kind"),
        "exactPointLaw": law.is_exact_point,
        "signConvention": "Q_supply[i] = sum_j W[i][j] * T[j] positive into network",
        "eliminatedJunctions": list(law.lineage.get("eliminatedJunctions", ())),
        "contacts": [dict(c) for c in law.lineage.get("contacts", ())],
    }
    if sys_obj.rod_generation is not None:
        conduction_summary["rodGenerationTotalPowerW"] = str(sys_obj.rod_generation.total_generated_power_w)

    return {
        "systemId": sys_obj.system_id,
        "mode": sys_obj.mode,
        "terminals": terms,
        "derivedLawSha256": law.content_sha256,
        "selectedBackend": backend,
        "unsupportedRegime": None if unsup_pair is None else {"pair": unsup_pair, "reason": unsup_reason},
        "conductionSummary": conduction_summary,
        "terminalEquations": terminal_eqs,
        "conservationEquation": conservation,
        "equationsText": "\n".join(lines),
    }


def _to_multiport_ports(system: ThermalSystem) -> dict[str, dict[str, Any]]:
    ports: dict[str, dict[str, Any]] = {}
    for t in system.derived_law.terminals:
        att = system.attachments[t]
        kind = att["kind"]
        if kind == "maintained":
            ports[t] = {"kind": "maintained", "temperatureK": att["temperatureK"]}
        elif kind == "phase_substance":
            ports[t] = {
                "kind": "phase_bath",
                "transitionTemperatureK": att["transitionTemperatureK"],
                "specificLatentHeatJPerKg": att["specificLatentHeatJPerKg"],
                "initialSolidKg": att["initialSolidKg"],
                "initialLiquidKg": att["initialLiquidKg"],
            }
        elif kind == "exterior_surface":
            entry = {
                "kind": "radiating_surface",
                "areaM2": att["areaM2"],
                "enclosureTemperatureK": att["enclosureTemperatureK"],
                "emissivity": att["emissivity"],
                "sigmaWPerM2K4": att["sigmaWPerM2K4"],
            }
            if "airTemperatureK" in att:
                entry["airTemperatureK"] = att["airTemperatureK"]
                entry["convectionCoefficientWPerM2K"] = att["convectionCoefficientWPerM2K"]
            ports[t] = entry
        elif kind == "radial_shell":
            ports[t] = {
                "kind": "radial_shell",
                "geometry": att["geometry"],
                "exterior": att["exterior"],
            }
        else:
            raise ValueError(f"internal error: unsupported multiport attachment kind {kind!r}")
    return ports


def _to_multibody_ports(system: ThermalSystem) -> dict[str, dict[str, Any]]:
    ports: dict[str, dict[str, Any]] = {}
    for t in system.derived_law.terminals:
        att = system.attachments[t]
        kind = att["kind"]
        if kind == "maintained":
            ports[t] = {"kind": "maintained", "temperatureK": att["temperatureK"]}
        elif kind == "sensible_body":
            ports[t] = {
                "kind": "lumped_body",
                "heatCapacityJPerK": att["heatCapacityJPerK"],
                "initialBodyTemperatureK": att["initialTemperatureK"],
            }
        elif kind == "phase_substance":
            ports[t] = {
                "kind": "phase_bath",
                "transitionTemperatureK": att["transitionTemperatureK"],
                "specificLatentHeatJPerKg": att["specificLatentHeatJPerKg"],
                "initialSolidKg": att["initialSolidKg"],
                "initialLiquidKg": att["initialLiquidKg"],
            }
        else:
            raise ValueError(f"internal error: unsupported multibody attachment kind {kind!r}")
    return ports


def _to_enthalpy_ports(system: ThermalSystem) -> dict[str, dict[str, Any]]:
    ports: dict[str, dict[str, Any]] = {}
    for t in system.derived_law.terminals:
        att = system.attachments[t]
        kind = att["kind"]
        if kind == "maintained":
            ports[t] = {"kind": "maintained", "temperatureK": att["temperatureK"]}
        elif kind == "sensible_body":
            entry: dict[str, Any] = {
                "kind": "sensible_body",
                "heatCapacityJPerK": att["heatCapacityJPerK"],
                "initialTemperatureK": att["initialTemperatureK"],
            }
            if att["heat_input"] != 0:
                entry["heatInputW"] = att["heatInputW"]
            ports[t] = entry
        elif kind == "phase_substance":
            entry = {
                "kind": "phase_substance",
                "transitionTemperatureK": att["transitionTemperatureK"],
                "specificLatentHeatJPerKg": att["specificLatentHeatJPerKg"],
                "solidSpecificHeatJPerKgK": att["solidSpecificHeatJPerKgK"],
                "liquidSpecificHeatJPerKgK": att["liquidSpecificHeatJPerKgK"],
                "initialSolidKg": att["initialSolidKg"],
                "initialLiquidKg": att["initialLiquidKg"],
                "initialTemperatureK": att["initialTemperatureK"],
            }
            if att["heat_input"] != 0:
                entry["heatInputW"] = att["heatInputW"]
            ports[t] = entry
        else:
            raise ValueError(f"internal error: unsupported enthalpy attachment kind {kind!r}")
    return ports


def _to_radiative_transient_ports(system: ThermalSystem) -> dict[str, dict[str, Any]]:
    ports: dict[str, dict[str, Any]] = {}
    for t in system.derived_law.terminals:
        att = system.attachments[t]
        kind = att["kind"]
        if kind == "maintained":
            ports[t] = {"kind": "maintained", "temperatureK": att["temperatureK"]}
        elif kind == "sensible_body":
            entry: dict[str, Any] = {
                "kind": "sensible_body",
                "heatCapacityJPerK": att["heatCapacityJPerK"],
                "initialTemperatureK": att["initialTemperatureK"],
            }
            if att["heat_input"] != 0:
                entry["heatInputW"] = att["heatInputW"]
            ports[t] = entry
        elif kind == "phase_substance":
            entry = {
                "kind": "phase_substance",
                "transitionTemperatureK": att["transitionTemperatureK"],
                "specificLatentHeatJPerKg": att["specificLatentHeatJPerKg"],
                "solidSpecificHeatJPerKgK": att["solidSpecificHeatJPerKgK"],
                "liquidSpecificHeatJPerKgK": att["liquidSpecificHeatJPerKgK"],
                "initialSolidKg": att["initialSolidKg"],
                "initialLiquidKg": att["initialLiquidKg"],
                "initialTemperatureK": att["initialTemperatureK"],
            }
            if att["heat_input"] != 0:
                entry["heatInputW"] = att["heatInputW"]
            ports[t] = entry
        elif kind == "exterior_surface":
            entry = {
                "kind": "exterior_surface",
                "areaM2": att["areaM2"],
                "enclosureTemperatureK": att["enclosureTemperatureK"],
                "emissivity": att["emissivity"],
                "sigmaWPerM2K4": att["sigmaWPerM2K4"],
            }
            if "airTemperatureK" in att:
                entry["airTemperatureK"] = att["airTemperatureK"]
                entry["convectionCoefficientWPerM2K"] = att["convectionCoefficientWPerM2K"]
            ports[t] = entry
        elif kind == "radial_shell":
            ports[t] = {
                "kind": "radial_shell",
                "geometry": att["geometry"],
                "exterior": att["exterior"],
            }
        else:
            raise ValueError(f"internal error: unsupported radiative_transient attachment kind {kind!r}")
    return ports


def _extract_terminal_temps(
    sys_obj: ThermalSystem, backend: str, raw: dict[str, Any]
) -> dict[str, tuple[Fraction, Fraction]]:
    """Extract certified terminal temperature spans (lo, hi) from any backend result."""
    temps: dict[str, tuple[Fraction, Fraction]] = {}
    if backend == "multiport":
        for t in sys_obj.derived_law.terminals:
            p = raw["ports"][t]
            b = p["innerFaceTemperatureBoundsK"] if p["kind"] == "radial_shell" else p["temperatureBoundsK"]
            temps[t] = (Fraction(b[0]), Fraction(b[1]))
        return temps
    if backend == "enthalpy":
        for t in sys_obj.derived_law.terminals:
            p = raw["ports"][t]
            if p["kind"] == "maintained":
                v = Fraction(p["temperatureK"])
                temps[t] = (v, v)
            else:
                b = p["finalTemperatureBoundsK"]
                temps[t] = (Fraction(b[0]), Fraction(b[1]))
        return temps
    if backend == "radiative_transient":
        for t in sys_obj.derived_law.terminals:
            p = raw["ports"][t]
            if p["kind"] == "maintained":
                v = Fraction(p["temperatureK"])
                temps[t] = (v, v)
            elif p["kind"] == "radial_shell":
                b = p["innerFaceTemperatureBoundsK"]
                temps[t] = (Fraction(b[0]), Fraction(b[1]))
            else:
                b = p["finalTemperatureBoundsK"]
                temps[t] = (Fraction(b[0]), Fraction(b[1]))
        return temps
    if backend == "staged":
        sp = raw["substancePort"]
        b = raw["trajectory"]["finalTemperatureBoundsK"]
        temps[sp] = (Fraction(b[0]), Fraction(b[1]))
        for t, val in raw["network"]["maintainedReservoirTemperaturesK"].items():
            v = Fraction(val)
            temps[t] = (v, v)
        return temps
    if backend == "stefan":
        sp = raw["network"]["stefanPort"]
        b = raw["stefan"]["finalPortTemperatureBoundsK"]
        temps[sp] = (Fraction(b[0]), Fraction(b[1]))
        for t, val in raw["network"]["maintainedReservoirTemperaturesK"].items():
            v = Fraction(val)
            temps[t] = (v, v)
        return temps
    raise RuntimeError(f"cannot extract terminal temperatures for backend {backend!r}")


def solve_system(
    system: ThermalSystem | dict[str, Any],
    *,
    include_equations: bool = True,
    rod_probe: tuple[str, str | Fraction] | None = None,
) -> dict[str, Any]:
    """Solve a ``ThermalSystem`` through existing certified backends and return a unified envelope."""
    sys_obj = system if isinstance(system, ThermalSystem) else ThermalSystem.from_dict(system)
    eq_report = describe_equations(sys_obj)
    backend, unsup_pair, unsup_reason = _classify_dispatch(sys_obj)

    parsed_probe: tuple[str, Fraction] | None = None
    if rod_probe is not None:
        r_name, x_raw = rod_probe
        x_val = x_raw if isinstance(x_raw, Fraction) else decimal_input(x_raw, "rod_probe position")
        if not (0 <= x_val <= 1):
            raise ValueError("rod_probe position fraction must be in [0, 1]")
        parsed_probe = (r_name, x_val)

    law_summary = {
        "schema": DERIVED_LAW_SCHEMA,
        "contentSha256": sys_obj.derived_law.content_sha256,
        "terminals": list(sys_obj.derived_law.terminals),
        "exactPointLaw": sys_obj.derived_law.is_exact_point,
        "lineage": sys_obj.derived_law.to_dict()["lineage"],
    }
    base_envelope: dict[str, Any] = {
        "schema": RESULT_ENVELOPE_SCHEMA,
        "systemId": sys_obj.system_id,
        "mode": sys_obj.mode,
        "backend": backend,
        "derivedLaw": law_summary,
        **({} if not include_equations else {"equations": eq_report}),
        **{k: False for k in OFFLINE_FLAG_KEYS},
    }

    if unsup_pair is not None:
        return {
            **base_envelope,
            "status": "unsupported_regime",
            "terminationReason": "unsupported_regime",
            "unsupportedMechanismPair": unsup_pair,
            "reason": unsup_reason,
            "achievedWidths": {},
            "backendResult": None,
        }

    rg = sys_obj.rod_generation
    if parsed_probe is not None and rg is None:
        raise ValueError("rod_probe requires a conduction.rods network with positive generatedPowerW")
    inj_arg = None if rg is None else rg.terminal_injections_w
    gen_tot_arg = None if rg is None else rg.total_generated_power_w

    def _with_rod_gen(env: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
        if rg is None:
            return env
        term_temps = _extract_terminal_temps(sys_obj, backend, raw)
        env["rodGenerationSummary"] = rg.recover_profiles(term_temps, probe=parsed_probe)
        return env

    if backend == "multiport":
        mp_ports = _to_multiport_ports(sys_obj)
        raw = solve_multiport(
            sys_obj.derived_law,
            mp_ports,
            duration_s=sys_obj.duration_s,
            max_sweeps=sys_obj.max_sweeps,
            terminal_injections_w=inj_arg,
            total_generated_power_w=gen_tot_arg,
        )
        meta = raw["solverMetadata"]
        ps = raw.get("phaseSystem")
        status = ps["plateauStatus"] if ps is not None else "resolved"
        widths = {
            "maxTemperatureWidthK": meta["maxTemperatureWidthK"],
            "maxHeatRateWidthW": meta["maxHeatRateWidthW"],
        }
        return _with_rod_gen(
            {
                **base_envelope,
                "status": status,
                "terminationReason": meta["terminationReason"],
                "achievedWidths": widths,
                "backendResult": raw,
            },
            raw,
        )

    if backend == "multibody":
        mb_ports = _to_multibody_ports(sys_obj)
        raw = solve_multibody(
            sys_obj.derived_law,
            mb_ports,
            sys_obj.duration_s,
            initial_steps=sys_obj.initial_steps,
        )
        meta = raw["solverMetadata"]
        ps = raw.get("phaseSystem")
        status = ps["plateauStatus"] if ps is not None else "resolved"
        widths = {
            "modeledDurationWidthS": meta["modeledDurationWidthS"],
        }
        return {
            **base_envelope,
            "status": status,
            "terminationReason": meta["terminationReason"],
            "achievedWidths": widths,
            "backendResult": raw,
        }

    if backend == "staged":
        phase_port = next(
            t for t in sys_obj.derived_law.terminals if sys_obj.attachments[t]["kind"] == "phase_substance"
        )
        p = sys_obj.attachments[phase_port]
        maintained = {
            t: sys_obj.attachments[t]["temperatureK"]
            for t in sys_obj.derived_law.terminals
            if t != phase_port
        }
        raw = solve_staged(
            sys_obj.derived_law,
            phase_port,
            p["initialTemperatureK"],
            p["transitionTemperatureK"],
            p["specificLatentHeatJPerKg"],
            p["solidSpecificHeatJPerKgK"],
            p["liquidSpecificHeatJPerKgK"],
            p["initialSolidKg"],
            p["initialLiquidKg"],
            sys_obj.duration_s,
            maintained_temperatures_k=maintained,
            port_norton_injection_w=None if inj_arg is None else inj_arg[phase_port],
        )
        traj = raw["trajectory"]
        tf_lo, tf_hi = map(Fraction, traj["finalTemperatureBoundsK"])
        status = traj["finalStage"]
        term_reason = (
            "mode_sequence_uncertain" if status == "stage_boundary_uncertain" else "resolved"
        )
        return _with_rod_gen(
            {
                **base_envelope,
                "status": status,
                "terminationReason": term_reason,
                "achievedWidths": {
                    "finalTemperatureWidthK": str(tf_hi - tf_lo),
                    "modeledDurationWidthS": "0",
                },
                "backendResult": raw,
            },
            raw,
        )

    if backend == "enthalpy":
        ent_ports = _to_enthalpy_ports(sys_obj)
        raw = solve_enthalpy_continuation(
            sys_obj.derived_law,
            ent_ports,
            sys_obj.duration_s,
            initial_steps=sys_obj.initial_steps,
            max_events=sys_obj.max_events,
            terminal_injections_w=inj_arg,
            total_generated_power_w=gen_tot_arg,
        )
        meta = raw["solverMetadata"]
        return _with_rod_gen(
            {
                **base_envelope,
                "status": raw["status"],
                "terminationReason": meta["terminationReason"],
                "achievedWidths": {
                    "maxFinalTemperatureWidthK": meta["maxFinalTemperatureWidthK"],
                    "modeledDurationWidthS": meta["modeledDurationWidthS"],
                },
                "backendResult": raw,
            },
            raw,
        )

    if backend == "radiative_transient":
        rt_ports = _to_radiative_transient_ports(sys_obj)
        raw = solve_radiative_transient(
            sys_obj.derived_law,
            rt_ports,
            sys_obj.duration_s,
            initial_steps=sys_obj.initial_steps,
            max_events=sys_obj.max_events,
            max_sweeps=sys_obj.max_sweeps,
            terminal_injections_w=inj_arg,
            total_generated_power_w=gen_tot_arg,
        )
        meta = raw["solverMetadata"]
        return _with_rod_gen(
            {
                **base_envelope,
                "status": raw["status"],
                "terminationReason": meta["terminationReason"],
                "achievedWidths": {
                    "maxFinalTemperatureWidthK": meta["maxFinalTemperatureWidthK"],
                    "modeledDurationWidthS": meta["modeledDurationWidthS"],
                },
                "backendResult": raw,
            },
            raw,
        )

    if backend == "stefan":
        stefan_port = next(
            t for t in sys_obj.derived_law.terminals if sys_obj.attachments[t]["kind"] == "stefan_layer"
        )
        maintained = {
            t: sys_obj.attachments[t]["temperatureK"]
            for t in sys_obj.derived_law.terminals
            if t != stefan_port
        }
        raw = solve_stefan_from_law(
            sys_obj.derived_law,
            stefan_port,
            sys_obj.attachments[stefan_port]["spec"],
            sys_obj.duration_s,
            maintained_temperatures_k=maintained,
            port_norton_injection_w=None if inj_arg is None else inj_arg[stefan_port],
        )
        meta = raw["solverMetadata"]
        return _with_rod_gen(
            {
                **base_envelope,
                "status": raw["stefan"]["status"],
                "terminationReason": meta["terminationReason"],
                "achievedWidths": {
                    "finalThicknessWidthM": meta["finalThicknessWidthM"],
                    "modeledDurationWidthS": meta["modeledDurationWidthS"],
                },
                "backendResult": raw,
            },
            raw,
        )

    raise RuntimeError(f"unexpected backend {backend!r}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", required=True, help="Path to a ThermalSystem JSON file")
    parser.add_argument(
        "--equations-only",
        action="store_true",
        help="Derive and print governing equations without invoking a solver",
    )
    args = parser.parse_args()
    sys_obj = ThermalSystem.from_file(args.system)
    if args.equations_only:
        print(json.dumps(describe_equations(sys_obj), indent=2))
    else:
        print(json.dumps(solve_system(sys_obj), indent=2))
