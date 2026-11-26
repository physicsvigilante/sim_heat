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

from simheat.laws import (
    DERIVED_LAW_SCHEMA,
    DerivedLaw,
    ensure_derived_law,
    join_laws,
)
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
)


def _resolve_conduction(
    spec: dict[str, Any],
    *,
    top_nodes: list[str] | None = None,
    base_dir: Path | None = None,
    system_id: str | None = None,
) -> DerivedLaw:
    """Recursively resolve a declarative conduction specification into a certified ``DerivedLaw``."""
    if not isinstance(spec, dict):
        raise ValueError("conduction specification must be a mapping")
    kind = spec.get("kind")
    if kind is None and "rods" in spec:
        kind = "rods"

    if kind == "rods":
        nodes = spec.get("nodes", top_nodes)
        rods = spec.get("rods")
        terminals = spec.get("terminals")
        return DerivedLaw.from_rods(nodes, rods, terminals=terminals, law_id=spec.get("lawId") or system_id)

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
        return DerivedLaw.from_h1_study(
            study_p,
            root_p,
            terminals=spec.get("terminals"),
            law_id=spec.get("lawId"),
        )

    if kind == "derived_law":
        _expect_exact_keys(spec, required=("kind", "law"), label="conduction(derived_law)")
        return ensure_derived_law(spec["law"])

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
        return DerivedLaw.from_file(law_p, expected_sha256=spec.get("sha256"))

    if kind == "join":
        _expect_exact_keys(
            spec,
            required=("kind", "left", "right", "contacts"),
            optional=("leftPrefix", "rightPrefix", "lawId"),
            label="conduction(join)",
        )
        left_law = _resolve_conduction(spec["left"], base_dir=base_dir)
        right_law = _resolve_conduction(spec["right"], base_dir=base_dir)
        return join_laws(
            left_law,
            right_law,
            spec["contacts"],
            left_prefix=spec.get("leftPrefix", "left"),
            right_prefix=spec.get("rightPrefix", "right"),
            law_id=spec.get("lawId") or system_id,
        )

    raise ValueError(
        f"unsupported conduction kind {kind!r}; expected one of "
        "('rods', 'h1_study', 'derived_law', 'derived_law_ref', 'join')"
    )


def _decimal_str(raw: str) -> str:
    """Return a clean unsigned SI decimal string (never a Fraction slash string)."""
    return raw.strip()


def _fraction_to_decimal_str(val: Fraction) -> str:
    """Convert an exact terminating binary/decimal Fraction (e.g. m * c) to a decimal string."""
    d = Decimal(val.numerator) / Decimal(val.denominator)
    if Fraction(d) != val:
        raise ValueError(f"non-terminating decimal value {val}")
    return format(d.normalize(), "f")


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
            optional=("heatCapacityJPerK", "massKg", "specificHeatJPerKgK"),
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
        return {
            "kind": "sensible_body",
            "heatCapacityJPerK": cap_str,
            "initialTemperatureK": _decimal_str(spec["initialTemperatureK"]),
            "capacity": cap,
            "t0": t0,
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
        return {
            "kind": "phase_substance",
            "transitionTemperatureK": _decimal_str(spec["transitionTemperatureK"]),
            "specificLatentHeatJPerKg": _decimal_str(spec["specificLatentHeatJPerKg"]),
            "initialSolidKg": _decimal_str(spec["initialSolidKg"]),
            "initialLiquidKg": _decimal_str(spec["initialLiquidKg"]),
            "initialTemperatureK": t0_str,
            "solidSpecificHeatJPerKgK": c_s_str,
            "liquidSpecificHeatJPerKgK": c_l_str,
            "t_tr": t_tr,
            "t0": t0,
            "latent": latent,
            "solid": solid,
            "liquid": liquid,
            "c_s": c_s,
            "c_l": c_l,
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

    # radial_shell
    _expect_exact_keys(spec, required=("kind", "geometry", "exterior"), label=f"attachments[{name}]")
    geom = spec["geometry"]
    ext = spec["exterior"]
    if not isinstance(geom, dict) or not isinstance(ext, dict):
        raise ValueError(f"attachments[{name}] geometry and exterior must be mappings")
    return {"kind": "radial_shell", "geometry": geom, "exterior": ext}


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
        derived_law = _resolve_conduction(
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
            optional=("durationS", "continuation", "maxSweeps", "initialSteps", "observations"),
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
        initial_steps = solve.get("initialSteps", 16)
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
    non_coex_phases = [
        t for t in phases if system.attachments[t]["t0"] != system.attachments[t]["t_tr"]
    ]

    if system.mode == "steady":
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
        return "multiport", None, None

    # transient mode
    if exteriors:
        ext_kind = kinds_by_port[exteriors[0]]
        partner = "sensible_body" if bodies else ("phase_substance" if phases else "transient_mode")
        return (
            None,
            [ext_kind, partner],
            f"Coupled transient {ext_kind} + {partner} requires a nonlinear transient integrator (deferred beyond M03).",
        )

    if bodies:
        if non_coex_phases:
            return (
                None,
                ["sensible_body", "non_coexisting_phase_substance"],
                "Coupled multi-body transient with subcooled/superheated phase_substance requires M04 enthalpy-mode continuation.",
            )
        if system.continuation == "staged":
            return (
                None,
                ["sensible_body", "staged_continuation"],
                "Multi-body post-exhaustion staged continuation is deferred to M04.",
            )
        return "multibody", None, None

    if len(phases) == 1:
        p = system.attachments[phases[0]]
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
        if non_coex_phases:
            return (
                None,
                ["multi_phase_substance", "non_coexisting_phase_substance"],
                "Multiple phase_substance ports outside coexistence require M04 enthalpy-mode continuation.",
            )
        if system.continuation == "staged":
            return (
                None,
                ["multi_phase_substance", "staged_continuation"],
                "Simultaneous multi-bath post-exhaustion staging is deferred to M04.",
            )
        return "multiport", None, None

    return (
        None,
        ["transient_mode", "maintained_only"],
        "Transient solve requires at least one sensible_body or phase_substance attachment.",
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

    terminal_eqs: dict[str, str] = {}
    for t in terms:
        att = sys_obj.attachments[t]
        kind = att["kind"]
        if kind == "maintained":
            terminal_eqs[t] = (
                f"T[{t}] = {att['temperatureK']} K; "
                f"Q_in[{t}] = -Q_supply[{t}] (into maintained reservoir positive)"
            )
        elif kind == "sensible_body":
            terminal_eqs[t] = (
                f"{att['heatCapacityJPerK']} * dT[{t}]/dt = -Q_supply[{t}], "
                f"T[{t}](0) = {att['initialTemperatureK']} K (into body positive)"
            )
        elif kind == "phase_substance":
            if backend == "staged":
                m_tot = att["solid"] + att["liquid"]
                terminal_eqs[t] = (
                    f"Piecewise enthalpy H[{t}] (M = {m_tot} kg, T_tr = {att['transitionTemperatureK']} K, "
                    f"L = {att['specificLatentHeatJPerKg']} J/kg, c_s = {att['solidSpecificHeatJPerKgK']}, "
                    f"c_l = {att['liquidSpecificHeatJPerKgK']}): "
                    f"dH[{t}]/dt = -Q_supply[{t}], T[{t}](0) = {att['initialTemperatureK']} K"
                )
            else:
                terminal_eqs[t] = (
                    f"T[{t}] = {att['transitionTemperatureK']} K during coexistence; "
                    f"dH[{t}]/dt = -Q_supply[{t}], "
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
                f"Q_out[{t}] = -Q_supply[{t}] = {att['areaM2']} * "
                f"[{h_term}{att['emissivity']}*{att['sigmaWPerM2K4']}*(T[{t}]^4 - {att['enclosureTemperatureK']}^4)] "
                "(outward positive)"
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
                f"Q_out[{t}] = -Q_supply[{t}] = G_shell({g.get('kind')}, r_in={g.get('innerRadiusM')}, "
                f"{len(g.get('layers', []))} layers)*(T[{t}] - T_s[{t}]) = "
                f"A_out[{t}]*[{h_term}{e.get('emissivity')}*{e.get('sigmaWPerM2K4')}*"
                f"(T_s[{t}]^4 - {e.get('enclosureTemperatureK')}^4)] (outward positive)"
            )

    if sys_obj.mode == "steady":
        conservation = "Global steady conservation: sum_i Q_supply[i] = 0 W"
    else:
        conservation = (
            "Global transient energy ledger on [0, t_stop]: "
            "sum_bodies C_i*(T_i(t_stop) - T_i(0)) + sum_phases DeltaH_k + sum_maintained E_in,m = 0 J"
        )

    lines = list(conduction_lines) + ["Terminal constitutive equations:"]
    for t in terms:
        lines.append(f"  [{t}] {terminal_eqs[t]}")
    lines.append(conservation)
    if unsup_pair is not None:
        lines.append(f"Dispatch status: unsupported_regime {unsup_pair} ({unsup_reason})")
    else:
        lines.append(f"Selected certified backend: {backend}")

    return {
        "systemId": sys_obj.system_id,
        "mode": sys_obj.mode,
        "terminals": terms,
        "derivedLawSha256": law.content_sha256,
        "selectedBackend": backend,
        "unsupportedRegime": None if unsup_pair is None else {"pair": unsup_pair, "reason": unsup_reason},
        "conductionSummary": {
            "lineageKind": law.lineage.get("kind"),
            "exactPointLaw": law.is_exact_point,
            "signConvention": "Q_supply[i] = sum_j W[i][j] * T[j] positive into network",
            "eliminatedJunctions": law.lineage.get("eliminatedJunctions", []),
            "contacts": law.lineage.get("contacts", []),
        },
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


def solve_system(system: ThermalSystem | dict[str, Any], *, include_equations: bool = True) -> dict[str, Any]:
    """Solve a ``ThermalSystem`` through existing certified backends and return a unified envelope."""
    sys_obj = system if isinstance(system, ThermalSystem) else ThermalSystem.from_dict(system)
    eq_report = describe_equations(sys_obj)
    backend, unsup_pair, unsup_reason = _classify_dispatch(sys_obj)

    law_summary = {
        "schema": DERIVED_LAW_SCHEMA,
        "contentSha256": sys_obj.derived_law.content_sha256,
        "terminals": list(sys_obj.derived_law.terminals),
        "exactPointLaw": sys_obj.derived_law.is_exact_point,
        "lineage": sys_obj.derived_law.lineage,
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

    if backend == "multiport":
        mp_ports = _to_multiport_ports(sys_obj)
        raw = solve_multiport(
            sys_obj.derived_law,
            mp_ports,
            duration_s=sys_obj.duration_s,
            max_sweeps=sys_obj.max_sweeps,
        )
        meta = raw["solverMetadata"]
        ps = raw.get("phaseSystem")
        status = ps["plateauStatus"] if ps is not None else "resolved"
        widths = {
            "maxTemperatureWidthK": meta["maxTemperatureWidthK"],
            "maxHeatRateWidthW": meta["maxHeatRateWidthW"],
        }
        return {
            **base_envelope,
            "status": status,
            "terminationReason": meta["terminationReason"],
            "achievedWidths": widths,
            "backendResult": raw,
        }

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
        )
        traj = raw["trajectory"]
        tf_lo, tf_hi = map(Fraction, traj["finalTemperatureBoundsK"])
        status = traj["finalStage"]
        term_reason = (
            "mode_sequence_uncertain" if status == "stage_boundary_uncertain" else "resolved"
        )
        return {
            **base_envelope,
            "status": status,
            "terminationReason": term_reason,
            "achievedWidths": {
                "finalTemperatureWidthK": str(tf_hi - tf_lo),
                "modeledDurationWidthS": "0",
            },
            "backendResult": raw,
        }

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
