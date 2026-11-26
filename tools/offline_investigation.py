"""Backward-compatible typed offline investigation contract for composed thermal studies.

Scoped to two existing offline analytical compositions:
- ``radial_phase_bath``: steady network + radial insulating shell + coexisting phase bath
- ``body_phase_bath_exchange``: steady network + lumped heat-capacity body + finite phase bath

Preserves exact rational interval enclosures, explicit SI units, terminal ownership,
active vs. source-law boundary conditions, heat-flow sign conventions, modeled duration
limits, and offline provenance flags without promoting mathematical calculations to
native authority.
"""
import argparse
from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path

from simheat.laws import (
    _parse_rational_str,
    _verify_joint_passive_feasibility,
    parse_interval_bounds,
)
from tools.body_phase_bath_exchange import solve_from_law as solve_body_phase_bath
from tools.offline_provenance import OFFLINE_FLAG_KEYS, SOURCE_HASH_KEYS, _SHA256_RE, offline_provenance
from tools.radial_phase_bath import solve_from_law as solve_radial_phase_bath
from tools.radiating_surface import decimal_input
from tools.terminal_response import investigate as terminal_response

CONTRACT_SCHEMA = "sim_heat.offline_investigation/1"
TERMINAL_LAW_SCHEMA = "sim_heat.offline_terminal_response/1"
UNDERLYING_SCHEMAS = {
    "radial_phase_bath": "sim_heat.offline_radial_phase_bath/1",
    "body_phase_bath_exchange": "sim_heat.offline_body_phase_bath_exchange/1",
}
EVIDENCE_CATEGORY = "offline_analytical_calculation"
ENDPOINT_MEANING = "exact_rational_closed_enclosure"
SUPPORTED_COMPOSITIONS = ("radial_phase_bath", "body_phase_bath_exchange")
VALID_PLATEAU_STATUSES = ("coexisting", "exhausted", "exhaustion_time_uncertain")
VALID_EXHAUSTED_PHASES = ("solid", "liquid")
VALID_RADIAL_GEOMETRIES = ("sphere", "cylinder")
VALID_PHASE_PROCESSES = {
    "radial_phase_bath": frozenset({"melting", "freezing", "equilibrium"}),
    "body_phase_bath_exchange": frozenset({
        "melting",
        "freezing",
        "equilibrium",
        "reversing_melting_to_freezing",
        "reversing_freezing_to_melting",
    }),
}


def _require_nonempty_str(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def interval_quantity(pair, *, unit, owner, sign_convention, label="interval"):
    """Construct a validated, self-describing rational interval record."""
    low, high = parse_interval_bounds(pair, label)
    return {
        "bounds": [str(low), str(high)],
        "unit": _require_nonempty_str(unit, "unit"),
        "owner": _require_nonempty_str(owner, "owner"),
        "signConvention": _require_nonempty_str(sign_convention, "signConvention"),
        "endpointMeaning": ENDPOINT_MEANING,
    }


def validate_interval_quantity(
    record,
    *,
    label="interval",
    expected_unit=None,
    expected_owner=None,
    expected_sign=None,
    expected_bounds=None,
    nonnegative=False,
    positive=False,
):
    """Validate a serialized interval quantity dictionary against schema, domain, and raw bounds."""
    if not isinstance(record, dict):
        raise ValueError(f"{label} must be an interval record mapping")
    required = {"bounds", "unit", "owner", "signConvention", "endpointMeaning"}
    if set(record) != required:
        raise ValueError(f"{label} must contain exact keys {sorted(required)}")
    low, high = parse_interval_bounds(record["bounds"], f"{label}.bounds")
    if positive and low <= 0:
        raise ValueError(f"{label}.bounds must be strictly positive, got [{low}, {high}]")
    if nonnegative and low < 0:
        raise ValueError(f"{label}.bounds must be nonnegative, got [{low}, {high}]")
    unit = _require_nonempty_str(record["unit"], f"{label}.unit")
    if expected_unit is not None and unit != expected_unit:
        raise ValueError(f"{label}.unit must be {expected_unit!r}, got {unit!r}")
    owner = _require_nonempty_str(record["owner"], f"{label}.owner")
    if expected_owner is not None and owner != expected_owner:
        raise ValueError(f"{label}.owner must be {expected_owner!r}, got {owner!r}")
    sign = _require_nonempty_str(record["signConvention"], f"{label}.signConvention")
    if expected_sign is not None and sign != expected_sign:
        raise ValueError(f"{label}.signConvention must be {expected_sign!r}, got {sign!r}")
    if record["endpointMeaning"] != ENDPOINT_MEANING:
        raise ValueError(f"{label}.endpointMeaning must be {ENDPOINT_MEANING!r}")
    if expected_bounds is not None:
        exp_lo, exp_hi = parse_interval_bounds(expected_bounds, f"{label} expected bounds")
        if (low, high) != (exp_lo, exp_hi):
            raise ValueError(
                f"{label}.bounds [{low}, {high}] does not match rawResult [{exp_lo}, {exp_hi}]"
            )
    return low, high


def validate_pinned_law(law):
    """Validate a prebuilt pinned terminal-response law mapping for schema, provenance, and passivity."""
    provenance = offline_provenance(law)
    if law.get("schema") != TERMINAL_LAW_SCHEMA:
        raise ValueError(f"pinned law schema must be {TERMINAL_LAW_SCHEMA!r}")
    terminals = law.get("terminals")
    if (not isinstance(terminals, list) or len(terminals) < 2
            or any(not isinstance(t, str) or not t for t in terminals)
            or len(set(terminals)) != len(terminals)):
        raise ValueError("pinned law requires at least two unique terminal names")
    terminal_set = set(terminals)

    imposed = law.get("imposedTemperaturesK")
    if not isinstance(imposed, dict) or set(imposed) != terminal_set:
        raise ValueError("pinned law imposedTemperaturesK must match terminals exactly")
    for name, temp_str in imposed.items():
        temp = _parse_rational_str(temp_str, f"imposedTemperaturesK[{name}]")
        if temp < 0:
            raise ValueError(f"imposedTemperaturesK[{name}] must be nonnegative")

    matrix = law.get("supplyResponseBoundsWPerK")
    if not isinstance(matrix, dict) or set(matrix) != terminal_set:
        raise ValueError("pinned law supplyResponseBoundsWPerK rows must match terminals exactly")

    parsed = {}
    for row_name in terminals:
        row = matrix[row_name]
        if not isinstance(row, dict) or set(row) != terminal_set:
            raise ValueError(f"supplyResponseBoundsWPerK[{row_name}] columns must match terminals")
        parsed[row_name] = {}
        for col_name in terminals:
            parsed[row_name][col_name] = parse_interval_bounds(
                row[col_name], f"supplyResponseBoundsWPerK[{row_name}][{col_name}]"
            )

    # Interval-compatible passive conduction checks:
    # 1. Diagonal positivity and off-diagonal non-positivity.
    for i in terminals:
        d_lo, _ = parsed[i][i]
        if d_lo <= 0:
            raise ValueError(f"passive terminal response requires positive diagonal at {i!r}")
        for j in terminals:
            if i != j and parsed[i][j][1] > 0:
                raise ValueError(
                    f"passive terminal response requires non-positive off-diagonal at ({i!r}, {j!r})"
                )

    # 2. Pairwise interval reciprocity: M[i][j] and M[j][i] must overlap.
    for idx_i, i in enumerate(terminals):
        for j in terminals[idx_i + 1:]:
            ij_lo, ij_hi = parsed[i][j]
            ji_lo, ji_hi = parsed[j][i]
            if max(ij_lo, ji_lo) > min(ij_hi, ji_hi):
                raise ValueError(
                    f"nonreciprocal passive terminal response between {i!r} and {j!r}"
                )

    # 3. Necessary row/column zero-sum conservation checks.
    for i in terminals:
        row_lo = sum((parsed[i][j][0] for j in terminals), Fraction(0))
        row_hi = sum((parsed[i][j][1] for j in terminals), Fraction(0))
        if row_lo > 0 or row_hi < 0:
            raise ValueError(f"passive terminal response row {i!r} violates zero-sum conservation")
        col_lo = sum((parsed[j][i][0] for j in terminals), Fraction(0))
        col_hi = sum((parsed[j][i][1] for j in terminals), Fraction(0))
        if col_lo > 0 or col_hi < 0:
            raise ValueError(f"passive terminal response column {i!r} violates zero-sum conservation")

    # 4. Exact joint rational feasibility of a reciprocal passive zero-sum matrix and connectivity.
    _verify_joint_passive_feasibility(terminals, parsed)

    return provenance


@dataclass(frozen=True)
class PinnedSourceRef:
    study_path: str
    root_path: str
    facts_path: str
    facts_sha256: str

    def __post_init__(self):
        _require_nonempty_str(self.study_path, "study_path")
        _require_nonempty_str(self.root_path, "root_path")
        _require_nonempty_str(self.facts_path, "facts_path")
        _require_nonempty_str(self.facts_sha256, "facts_sha256")
        if not _SHA256_RE.fullmatch(self.facts_sha256):
            raise ValueError("facts_sha256 must be a 64-lowercase-hex SHA-256 digest")

    def resolve_law(self):
        law = terminal_response(self.study_path, self.root_path, self.facts_path, self.facts_sha256)
        validate_pinned_law(law)
        return law


@dataclass(frozen=True)
class PhaseBathSpec:
    port: str
    transition_k: str
    latent_heat_j_per_kg: str
    solid_kg: str
    liquid_kg: str

    def __post_init__(self):
        _require_nonempty_str(self.port, "phase_bath.port")
        for field_name, label in (
            ("transition_k", "transition temperature"),
            ("latent_heat_j_per_kg", "specific latent heat"),
            ("solid_kg", "initial solid mass"),
            ("liquid_kg", "initial liquid mass"),
        ):
            val = decimal_input(getattr(self, field_name), label)
            if val <= 0:
                raise ValueError(f"positive {label} required")


@dataclass(frozen=True)
class RadialLayerSpec:
    outer_radius_m: str
    conductivity_w_per_m_k: str

    def __post_init__(self):
        r = decimal_input(self.outer_radius_m, "layer outer radius")
        k = decimal_input(self.conductivity_w_per_m_k, "layer conductivity")
        if r <= 0 or k <= 0:
            raise ValueError("positive layer outer radius and conductivity required")


@dataclass(frozen=True)
class RadialGeometrySpec:
    kind: str
    inner_radius_m: str
    layers: tuple
    cylinder_length_m: str | None = None

    def __post_init__(self):
        if self.kind not in VALID_RADIAL_GEOMETRIES:
            raise ValueError(f"radial geometry kind must be one of {VALID_RADIAL_GEOMETRIES}")
        r_in = decimal_input(self.inner_radius_m, "inner radius")
        if r_in <= 0:
            raise ValueError("positive inner radius required")
        if not isinstance(self.layers, tuple) or not self.layers:
            raise ValueError("at least one radial layer is required")
        prev = r_in
        for idx, layer in enumerate(self.layers):
            if not isinstance(layer, RadialLayerSpec):
                raise ValueError(f"layer[{idx}] must be a RadialLayerSpec")
            r_out = decimal_input(layer.outer_radius_m, f"layer[{idx}] outer radius")
            if r_out <= prev:
                raise ValueError("radial layer outer radii must strictly increase from inner radius")
            prev = r_out
        if self.kind == "sphere":
            if self.cylinder_length_m is not None:
                raise ValueError("sphere geometry does not accept cylinder_length_m")
        else:
            if self.cylinder_length_m is None:
                raise ValueError("cylinder geometry requires cylinder_length_m")
            length = decimal_input(self.cylinder_length_m, "cylinder length")
            if length <= 0:
                raise ValueError("positive cylinder length required")


@dataclass(frozen=True)
class ExteriorExchangeSpec:
    enclosure_k: str
    emissivity: str
    sigma_w_per_m2_k4: str
    air_k: str | None = None
    h_w_per_m2_k: str | None = None

    def __post_init__(self):
        decimal_input(self.enclosure_k, "enclosure temperature")
        eps = decimal_input(self.emissivity, "emissivity")
        sigma = decimal_input(self.sigma_w_per_m2_k4, "Stefan-Boltzmann constant")
        if eps > 1 or sigma <= 0:
            raise ValueError("positive sigma and emissivity in [0,1] required")
        if (self.air_k is None) != (self.h_w_per_m2_k is None):
            raise ValueError("supply air_k and h_w_per_m2_k together")
        if self.air_k is not None:
            decimal_input(self.air_k, "air temperature")
            decimal_input(self.h_w_per_m2_k, "convective heat transfer coefficient")


@dataclass(frozen=True)
class RadialShellPortSpec:
    surface_port: str
    geometry: RadialGeometrySpec
    exterior: ExteriorExchangeSpec

    def __post_init__(self):
        _require_nonempty_str(self.surface_port, "radial_shell.surface_port")
        if not isinstance(self.geometry, RadialGeometrySpec):
            raise ValueError("radial_shell.geometry must be a RadialGeometrySpec")
        if not isinstance(self.exterior, ExteriorExchangeSpec):
            raise ValueError("radial_shell.exterior must be an ExteriorExchangeSpec")


@dataclass(frozen=True)
class LumpedBodySpec:
    port: str
    heat_capacity_j_per_k: str
    initial_temperature_k: str

    def __post_init__(self):
        _require_nonempty_str(self.port, "body.port")
        cap = decimal_input(self.heat_capacity_j_per_k, "heat capacity")
        decimal_input(self.initial_temperature_k, "initial body temperature")
        if cap <= 0:
            raise ValueError("positive heat capacity required")


@dataclass(frozen=True)
class InvestigationRequest:
    composition: str
    source: object
    duration_s: str
    phase_bath: PhaseBathSpec
    radial_shell: RadialShellPortSpec | None = None
    body: LumpedBodySpec | None = None

    def __post_init__(self):
        if self.composition not in SUPPORTED_COMPOSITIONS:
            raise ValueError(f"unsupported composition {self.composition!r}; expected one of {SUPPORTED_COMPOSITIONS}")
        if not isinstance(self.source, (PinnedSourceRef, dict)):
            raise ValueError("source must be a PinnedSourceRef or validated pinned law mapping")
        decimal_input(self.duration_s, "duration")
        if not isinstance(self.phase_bath, PhaseBathSpec):
            raise ValueError("phase_bath must be a PhaseBathSpec")
        if self.composition == "radial_phase_bath":
            if not isinstance(self.radial_shell, RadialShellPortSpec) or self.body is not None:
                raise ValueError("radial_phase_bath requires radial_shell and forbids body")
            if self.phase_bath.port == self.radial_shell.surface_port:
                raise ValueError("phase_bath.port and radial_shell.surface_port must be distinct")
        else:
            if not isinstance(self.body, LumpedBodySpec) or self.radial_shell is not None:
                raise ValueError("body_phase_bath_exchange requires body and forbids radial_shell")
            if self.phase_bath.port == self.body.port:
                raise ValueError("phase_bath.port and body.port must be distinct")


def _expect_exact_keys(mapping, required, optional=(), *, label):
    if not isinstance(mapping, dict):
        raise ValueError(f"{label} must be a JSON object")
    keys = set(mapping)
    req = set(required)
    allowed = req | set(optional)
    missing = sorted(req - keys)
    extra = sorted(keys - allowed)
    if missing:
        raise ValueError(f"{label} missing required keys: {missing}")
    if extra:
        raise ValueError(f"{label} has unsupported keys: {extra}")


def request_from_dict(payload):
    """Parse and strictly validate a JSON-compatible investigation request dictionary."""
    _expect_exact_keys(
        payload,
        required=("composition", "source", "durationS", "phaseBath"),
        optional=("radialShell", "body"),
        label="request",
    )
    src = payload["source"]
    if not isinstance(src, dict):
        raise ValueError("request.source must be a JSON object")
    if "studyPath" in src or ("factsSha256" in src and "terminals" not in src):
        _expect_exact_keys(
            src,
            required=("studyPath", "rootPath", "factsPath", "factsSha256"),
            label="request.source",
        )
        source = PinnedSourceRef(
            study_path=src["studyPath"],
            root_path=src["rootPath"],
            facts_path=src["factsPath"],
            facts_sha256=src["factsSha256"],
        )
    else:
        validate_pinned_law(src)
        source = src

    pb = payload["phaseBath"]
    _expect_exact_keys(
        pb,
        required=("port", "transitionTemperatureK", "specificLatentHeatJPerKg", "initialSolidKg", "initialLiquidKg"),
        label="request.phaseBath",
    )
    phase_bath = PhaseBathSpec(
        port=pb["port"],
        transition_k=pb["transitionTemperatureK"],
        latent_heat_j_per_kg=pb["specificLatentHeatJPerKg"],
        solid_kg=pb["initialSolidKg"],
        liquid_kg=pb["initialLiquidKg"],
    )

    radial_shell = None
    if payload.get("radialShell") is not None:
        rs = payload["radialShell"]
        _expect_exact_keys(
            rs,
            required=("surfacePort", "geometry", "exterior"),
            label="request.radialShell",
        )
        g = rs["geometry"]
        _expect_exact_keys(
            g,
            required=("kind", "innerRadiusM", "layers"),
            optional=("cylinderLengthM",),
            label="request.radialShell.geometry",
        )
        if not isinstance(g["layers"], list) or not g["layers"]:
            raise ValueError("request.radialShell.geometry.layers must be a non-empty list")
        layers = []
        for idx, layer in enumerate(g["layers"]):
            _expect_exact_keys(
                layer,
                required=("outerRadiusM", "conductivityWPerMK"),
                label=f"request.radialShell.geometry.layers[{idx}]",
            )
            layers.append(RadialLayerSpec(layer["outerRadiusM"], layer["conductivityWPerMK"]))
        geom = RadialGeometrySpec(
            kind=g["kind"],
            inner_radius_m=g["innerRadiusM"],
            layers=tuple(layers),
            cylinder_length_m=g.get("cylinderLengthM"),
        )
        ext = rs["exterior"]
        _expect_exact_keys(
            ext,
            required=("enclosureTemperatureK", "emissivity", "sigmaWPerM2K4"),
            optional=("airTemperatureK", "convectionCoefficientWPerM2K"),
            label="request.radialShell.exterior",
        )
        exterior = ExteriorExchangeSpec(
            enclosure_k=ext["enclosureTemperatureK"],
            emissivity=ext["emissivity"],
            sigma_w_per_m2_k4=ext["sigmaWPerM2K4"],
            air_k=ext.get("airTemperatureK"),
            h_w_per_m2_k=ext.get("convectionCoefficientWPerM2K"),
        )
        radial_shell = RadialShellPortSpec(
            surface_port=rs["surfacePort"],
            geometry=geom,
            exterior=exterior,
        )

    body = None
    if payload.get("body") is not None:
        b = payload["body"]
        _expect_exact_keys(
            b,
            required=("port", "heatCapacityJPerK", "initialBodyTemperatureK"),
            label="request.body",
        )
        body = LumpedBodySpec(
            port=b["port"],
            heat_capacity_j_per_k=b["heatCapacityJPerK"],
            initial_temperature_k=b["initialBodyTemperatureK"],
        )

    return InvestigationRequest(
        composition=payload["composition"],
        source=source,
        duration_s=payload["durationS"],
        phase_bath=phase_bath,
        radial_shell=radial_shell,
        body=body,
    )


def _port_roles(terminals, phase_port, partner_port, partner_role):
    roles = {}
    for t in terminals:
        if t == phase_port:
            roles[t] = "phase_bath"
        elif t == partner_port:
            roles[t] = partner_role
        else:
            roles[t] = "maintained_reservoir"
    return roles


def _active_boundary_conditions(
    terminals, port_roles, source_ref_temps, composition, raw
):
    active = {}
    for t in terminals:
        role = port_roles[t]
        if role == "phase_bath":
            active[t] = {
                "role": "phase_bath",
                "constraint": "clamped_during_coexistence",
                "temperatureK": raw["transitionTemperatureK"],
            }
        elif role == "radial_surface":
            active[t] = {
                "role": "radial_surface",
                "constraint": "released_to_radial_shell",
                "innerFaceTemperatureBoundsK": list(
                    raw["radialShell"]["surfaces"][0]["temperatureBoundsK"]
                ),
            }
        elif role == "lumped_body":
            active[t] = {
                "role": "lumped_body",
                "constraint": "released_to_lumped_body",
                "initialTemperatureK": raw["initialBodyTemperatureK"],
                "finalTemperatureBoundsK": list(raw["finalBodyTemperatureBoundsK"]),
            }
        else:
            active[t] = {
                "role": "maintained_reservoir",
                "constraint": "fixed_dirichlet",
                "temperatureK": source_ref_temps[t],
            }
    return active


def run_investigation(request):
    """Execute a validated InvestigationRequest through the existing offline solver."""
    if isinstance(request, dict):
        request = request_from_dict(request)
    elif not isinstance(request, InvestigationRequest):
        raise ValueError("request must be an InvestigationRequest or dict")

    prepared_from_files = isinstance(request.source, PinnedSourceRef)
    law = request.source.resolve_law() if prepared_from_files else request.source
    validate_pinned_law(law)

    terminals = list(law["terminals"])
    source_ref_temps = {t: str(law["imposedTemperaturesK"][t]) for t in terminals}
    pb = request.phase_bath
    if pb.port not in terminals:
        raise ValueError(f"phase bath port {pb.port!r} is not in pinned network terminals {terminals}")

    if request.composition == "radial_phase_bath":
        rs = request.radial_shell
        if rs.surface_port not in terminals:
            raise ValueError(
                f"radial surface port {rs.surface_port!r} is not in pinned network terminals {terminals}"
            )
        layer_pairs = [(l.outer_radius_m, l.conductivity_w_per_m_k) for l in rs.geometry.layers]
        raw = solve_radial_phase_bath(
            law,
            pb.port,
            rs.surface_port,
            pb.transition_k,
            pb.latent_heat_j_per_kg,
            pb.solid_kg,
            pb.liquid_kg,
            request.duration_s,
            rs.geometry.inner_radius_m,
            layer_pairs,
            rs.exterior.enclosure_k,
            rs.exterior.emissivity,
            rs.exterior.sigma_w_per_m2_k4,
            rs.geometry.cylinder_length_m,
            air_k=rs.exterior.air_k,
            h_w_per_m2_k=rs.exterior.h_w_per_m2_k,
        )
        provenance = offline_provenance(raw)
        shell = raw["radialShell"]
        exhausted_phase = None
        if raw["plateauStatus"] == "exhausted":
            if raw["phaseProcess"] == "melting":
                exhausted_phase = "solid"
            elif raw["phaseProcess"] == "freezing":
                exhausted_phase = "liquid"

        quantities = {
            "bathInflowDuringPlateauW": interval_quantity(
                raw["bathInflowDuringPlateauBoundsW"],
                unit="W",
                owner=f"phase_bath:{pb.port}",
                sign_convention="into_phase_bath_positive",
                label="bathInflowDuringPlateauBoundsW",
            ),
            "surfaceOutwardHeatRateW": interval_quantity(
                shell["outwardHeatRateBoundsW"],
                unit="W",
                owner=f"radial_surface:{rs.surface_port}",
                sign_convention="outward_from_radial_surface_positive",
                label="outwardHeatRateBoundsW",
            ),
            "latentEnergyIntoBathJ": interval_quantity(
                raw["latentEnergyIntoBathBoundsJ"],
                unit="J",
                owner=f"phase_bath:{pb.port}",
                sign_convention="into_phase_bath_positive",
                label="latentEnergyIntoBathBoundsJ",
            ),
            "remainingSolidKg": interval_quantity(
                raw["remainingSolidBoundsKg"],
                unit="kg",
                owner=f"phase_bath:{pb.port}",
                sign_convention="mass_nonnegative",
                label="remainingSolidBoundsKg",
            ),
            "remainingLiquidKg": interval_quantity(
                raw["remainingLiquidBoundsKg"],
                unit="kg",
                owner=f"phase_bath:{pb.port}",
                sign_convention="mass_nonnegative",
                label="remainingLiquidBoundsKg",
            ),
            "exposedAreaM2": interval_quantity(
                shell["exposedAreaBoundsM2"],
                unit="m2",
                owner=f"radial_surface:{rs.surface_port}",
                sign_convention="area_positive",
                label="exposedAreaBoundsM2",
            ),
            "surfaceTemperaturesK": [
                {
                    "radiusM": surf["radiusM"],
                    "temperatureK": interval_quantity(
                        surf["temperatureBoundsK"],
                        unit="K",
                        owner=f"radial_surface:{rs.surface_port}@r={surf['radiusM']}m",
                        sign_convention="absolute_temperature_nonnegative",
                        label="surface.temperatureBoundsK",
                    ),
                }
                for surf in shell["surfaces"]
            ],
            "maintainedReservoirInflowsW": {
                name: interval_quantity(
                    pair,
                    unit="W",
                    owner=f"maintained_reservoir:{name}",
                    sign_convention="into_maintained_reservoir_positive",
                    label=f"maintainedReservoirInflowBoundsW[{name}]",
                )
                for name, pair in raw.get("maintainedReservoirInflowBoundsW", {}).items()
            },
        }
        if "netHeatToAirBoundsW" in shell:
            quantities["netHeatToAirW"] = interval_quantity(
                shell["netHeatToAirBoundsW"],
                unit="W",
                owner=f"radial_surface:{rs.surface_port}",
                sign_convention="outward_from_radial_surface_positive",
                label="netHeatToAirBoundsW",
            )
        if "netHeatToEnclosureBoundsW" in shell:
            quantities["netHeatToEnclosureW"] = interval_quantity(
                shell["netHeatToEnclosureBoundsW"],
                unit="W",
                owner=f"radial_surface:{rs.surface_port}",
                sign_convention="outward_from_radial_surface_positive",
                label="netHeatToEnclosureBoundsW",
            )

        geometry_block = {
            "kind": shell["geometry"],
            "cylinderLengthM": shell["cylinderLengthM"],
            "innerRadiusM": shell["surfaces"][0]["radiusM"],
            "layers": shell["layers"],
            "exposedAreaM2": quantities["exposedAreaM2"],
        }
        inputs_block = {
            "durationS": raw["requestedDurationS"],
            "phaseBath": {
                "port": pb.port,
                "transitionTemperatureK": raw["transitionTemperatureK"],
                "specificLatentHeatJPerKg": raw["specificLatentHeatJPerKg"],
                "initialSolidKg": raw["initialSolidKg"],
                "initialLiquidKg": raw["initialLiquidKg"],
            },
            "radialShell": {
                "surfacePort": rs.surface_port,
                "geometry": {
                    "kind": shell["geometry"],
                    "innerRadiusM": shell["surfaces"][0]["radiusM"],
                    "cylinderLengthM": shell["cylinderLengthM"],
                    "layers": shell["layers"],
                },
                "exterior": {
                    "enclosureTemperatureK": shell["enclosureTemperatureK"],
                    "emissivity": shell["emissivity"],
                    "sigmaWPerM2K4": shell["sigmaWPerM2K4"],
                    "airTemperatureK": shell.get("airTemperatureK"),
                    "convectionCoefficientWPerM2K": shell.get("convectionCoefficientWPerM2K"),
                },
            },
        }
        port_roles = _port_roles(terminals, pb.port, rs.surface_port, "radial_surface")
        assumptions = [
            "Pinned steady linear conduction network terminates at the radial shell inner face.",
            "Phase bath stays isothermal at transitionTemperatureK while solid and liquid coexist.",
            "No post-exhaustion sensible heating or cooling is modeled beyond first phase exhaustion.",
            "Offline analytical rational-interval calculation; not a native OpenModelica simulation.",
        ]
        if shell["geometry"] == "cylinder":
            assumptions.append("1D radial cylindrical conduction; axial end-effects are neglected.")
        reversal_q = None
    else:
        body = request.body
        if body.port not in terminals:
            raise ValueError(f"body port {body.port!r} is not in pinned network terminals {terminals}")
        raw = solve_body_phase_bath(
            law,
            pb.port,
            body.port,
            pb.transition_k,
            pb.latent_heat_j_per_kg,
            pb.solid_kg,
            pb.liquid_kg,
            body.heat_capacity_j_per_k,
            body.initial_temperature_k,
            request.duration_s,
        )
        provenance = offline_provenance(raw)
        exhausted_phase = raw["exhaustedPhase"]
        quantities = {
            "bodyEquilibriumTemperatureK": interval_quantity(
                raw["bodyEquilibriumTemperatureBoundsK"],
                unit="K",
                owner=f"body:{body.port}",
                sign_convention="absolute_temperature_nonnegative",
                label="bodyEquilibriumTemperatureBoundsK",
            ),
            "bodyTimeConstantS": interval_quantity(
                raw["bodyTimeConstantBoundsS"],
                unit="s",
                owner=f"body:{body.port}",
                sign_convention="positive_time_constant",
                label="bodyTimeConstantBoundsS",
            ),
            "initialBathInflowW": interval_quantity(
                raw["initialBathInflowBoundsW"],
                unit="W",
                owner=f"phase_bath:{pb.port}",
                sign_convention="into_phase_bath_positive",
                label="initialBathInflowBoundsW",
            ),
            "asymptoticBathInflowW": interval_quantity(
                raw["asymptoticBathInflowBoundsW"],
                unit="W",
                owner=f"phase_bath:{pb.port}",
                sign_convention="into_phase_bath_positive",
                label="asymptoticBathInflowBoundsW",
            ),
            "finalBodyTemperatureK": interval_quantity(
                raw["finalBodyTemperatureBoundsK"],
                unit="K",
                owner=f"body:{body.port}",
                sign_convention="absolute_temperature_nonnegative",
                label="finalBodyTemperatureBoundsK",
            ),
            "bodyEnergyChangeJ": interval_quantity(
                raw["bodyEnergyChangeBoundsJ"],
                unit="J",
                owner=f"body:{body.port}",
                sign_convention="into_body_positive",
                label="bodyEnergyChangeBoundsJ",
            ),
            "latentEnergyIntoBathJ": interval_quantity(
                raw["latentEnergyIntoBathBoundsJ"],
                unit="J",
                owner=f"phase_bath:{pb.port}",
                sign_convention="into_phase_bath_positive",
                label="latentEnergyIntoBathBoundsJ",
            ),
            "remainingSolidKg": interval_quantity(
                raw["remainingSolidBoundsKg"],
                unit="kg",
                owner=f"phase_bath:{pb.port}",
                sign_convention="mass_nonnegative",
                label="remainingSolidBoundsKg",
            ),
            "remainingLiquidKg": interval_quantity(
                raw["remainingLiquidBoundsKg"],
                unit="kg",
                owner=f"phase_bath:{pb.port}",
                sign_convention="mass_nonnegative",
                label="remainingLiquidBoundsKg",
            ),
        }
        geometry_block = {"kind": "lumped_network_port"}
        inputs_block = {
            "durationS": raw["requestedDurationS"],
            "phaseBath": {
                "port": pb.port,
                "transitionTemperatureK": raw["transitionTemperatureK"],
                "specificLatentHeatJPerKg": raw["specificLatentHeatJPerKg"],
                "initialSolidKg": raw["initialSolidKg"],
                "initialLiquidKg": raw["initialLiquidKg"],
            },
            "body": {
                "port": body.port,
                "heatCapacityJPerK": raw["heatCapacityJPerK"],
                "initialBodyTemperatureK": raw["initialBodyTemperatureK"],
            },
        }
        port_roles = _port_roles(terminals, pb.port, body.port, "lumped_body")
        assumptions = [
            "Ideal lumped heat-capacity body coupled through a storage-free pinned conduction network.",
            "Phase bath stays isothermal at transitionTemperatureK while solid and liquid coexist.",
            "No post-exhaustion sensible heating or cooling is modeled beyond first phase exhaustion.",
            "Offline analytical rational-interval calculation; not a native OpenModelica simulation.",
        ]
        reversal_q = (
            None
            if raw["reversalTimeBoundsS"] is None
            else interval_quantity(
                raw["reversalTimeBoundsS"],
                unit="s",
                owner=f"phase_bath:{pb.port}",
                sign_convention="elapsed_time_nonnegative",
                label="reversalTimeBoundsS",
            )
        )

    exhaustion_q = (
        None
        if raw["exhaustionTimeBoundsS"] is None
        else interval_quantity(
            raw["exhaustionTimeBoundsS"],
            unit="s",
            owner=f"phase_bath:{pb.port}",
            sign_convention="elapsed_time_nonnegative",
            label="exhaustionTimeBoundsS",
        )
    )
    modeled_duration_q = interval_quantity(
        raw["modeledDurationBoundsS"],
        unit="s",
        owner="investigation",
        sign_convention="elapsed_time_nonnegative",
        label="modeledDurationBoundsS",
    )

    maintained_temps = {
        t: source_ref_temps[t] for t in terminals if port_roles[t] == "maintained_reservoir"
    }
    active_bcs = _active_boundary_conditions(
        terminals, port_roles, source_ref_temps, request.composition, raw
    )

    record = {
        "schema": CONTRACT_SCHEMA,
        "composition": request.composition,
        "underlyingSchema": raw["schema"],
        "evidence": {
            "category": EVIDENCE_CATEGORY,
            "sourceIdentity": {
                **{k: provenance[k] for k in SOURCE_HASH_KEYS},
                "preparedFromFiles": prepared_from_files,
            },
            **{k: False for k in OFFLINE_FLAG_KEYS},
        },
        "network": {
            "terminals": terminals,
            "portRoles": port_roles,
            "sourceLawReferenceTemperaturesK": source_ref_temps,
            "maintainedReservoirTemperaturesK": maintained_temps,
            "activeBoundaryConditions": active_bcs,
            "supplyMatrixUnit": "W/K",
            "supplyMatrixSignConvention": "supply_into_network_per_unit_terminal_temperature_rise",
        },
        "inputs": inputs_block,
        "geometry": geometry_block,
        "status": {
            "phaseProcess": raw["phaseProcess"],
            "plateauStatus": raw["plateauStatus"],
            "exhaustedPhase": exhausted_phase,
            "postExhaustionModeled": False,
            "requestedDurationS": raw["requestedDurationS"],
            "modeledDurationS": modeled_duration_q,
            "exhaustionTimeS": exhaustion_q,
            "reversalTimeS": reversal_q,
        },
        "quantities": quantities,
        "assumptions": assumptions,
        "rawResult": raw,
        **provenance,
    }
    validate_investigation_record(record)
    return record


def validate_investigation_record(record):
    """Verify schema, provenance, ports, active boundaries, status, quantities, and rawResult parity."""
    if not isinstance(record, dict):
        raise ValueError("investigation record must be a mapping")
    if record.get("schema") != CONTRACT_SCHEMA:
        raise ValueError(f"expected schema {CONTRACT_SCHEMA!r}")
    comp = record.get("composition")
    if comp not in SUPPORTED_COMPOSITIONS:
        raise ValueError(f"unsupported composition {comp!r}")

    expected_underlying = UNDERLYING_SCHEMAS[comp]
    if record.get("underlyingSchema") != expected_underlying:
        raise ValueError(f"underlyingSchema must be {expected_underlying!r}")

    top_prov = offline_provenance(record)
    ev = record.get("evidence")
    if not isinstance(ev, dict) or ev.get("category") != EVIDENCE_CATEGORY:
        raise ValueError("evidence.category must be offline_analytical_calculation")
    for flag in OFFLINE_FLAG_KEYS:
        if ev.get(flag) is not False:
            raise ValueError(f"evidence.{flag} must be False")
    src_id = ev.get("sourceIdentity")
    if not isinstance(src_id, dict) or not isinstance(src_id.get("preparedFromFiles"), bool):
        raise ValueError("evidence.sourceIdentity must include boolean preparedFromFiles")
    for key in SOURCE_HASH_KEYS:
        if src_id.get(key) != top_prov[key]:
            raise ValueError(f"evidence.sourceIdentity.{key} must match top-level {key}")

    raw = record.get("rawResult")
    raw_prov = offline_provenance(raw)
    if raw_prov != top_prov:
        raise ValueError("rawResult provenance must match top-level provenance")
    if raw.get("schema") != expected_underlying:
        raise ValueError(f"rawResult.schema must be {expected_underlying!r}")

    # Validate network, portRoles cardinality, source reference temps, and active boundary conditions.
    net = record.get("network")
    if not isinstance(net, dict):
        raise ValueError("network mapping required")
    terminals = net.get("terminals")
    if (not isinstance(terminals, list) or len(terminals) < 2
            or any(not isinstance(t, str) or not t for t in terminals)
            or len(set(terminals)) != len(terminals)):
        raise ValueError("network.terminals requires at least two unique terminal names")
    terminal_set = set(terminals)

    partner_role = "radial_surface" if comp == "radial_phase_bath" else "lumped_body"
    port_roles = net.get("portRoles")
    if not isinstance(port_roles, dict) or set(port_roles) != terminal_set:
        raise ValueError("network.terminals and network.portRoles must match exactly")
    phase_ports = [t for t, r in port_roles.items() if r == "phase_bath"]
    partner_ports = [t for t, r in port_roles.items() if r == partner_role]
    maintained_ports = [t for t, r in port_roles.items() if r == "maintained_reservoir"]
    allowed_roles = {"phase_bath", partner_role, "maintained_reservoir"}
    if (any(r not in allowed_roles for r in port_roles.values())
            or len(phase_ports) != 1 or len(partner_ports) != 1):
        raise ValueError(
            f"network.portRoles must contain exactly one phase_bath, one {partner_role}, "
            "and maintained_reservoir for all remaining ports"
        )
    phase_port = phase_ports[0]
    partner_port = partner_ports[0]
    if raw.get("phaseBathPort") != phase_port:
        raise ValueError("network phase_bath port must match rawResult.phaseBathPort")
    if comp == "radial_phase_bath":
        shell = raw.get("radialShell")
        if not isinstance(shell, dict) or shell.get("innerPort") != partner_port:
            raise ValueError("network radial_surface port must match rawResult.radialShell.innerPort")
    else:
        if raw.get("bodyPort") != partner_port:
            raise ValueError("network lumped_body port must match rawResult.bodyPort")

    ref_temps = net.get("sourceLawReferenceTemperaturesK")
    if not isinstance(ref_temps, dict) or set(ref_temps) != terminal_set:
        raise ValueError("network.sourceLawReferenceTemperaturesK must match terminals exactly")
    for t, val in ref_temps.items():
        if _parse_rational_str(val, f"sourceLawReferenceTemperaturesK[{t}]") < 0:
            raise ValueError(f"sourceLawReferenceTemperaturesK[{t}] must be nonnegative")

    maint_temps = net.get("maintainedReservoirTemperaturesK")
    if not isinstance(maint_temps, dict) or set(maint_temps) != set(maintained_ports):
        raise ValueError("network.maintainedReservoirTemperaturesK must match maintained_reservoir ports")
    for t in maintained_ports:
        if maint_temps[t] != ref_temps[t]:
            raise ValueError(
                f"network.maintainedReservoirTemperaturesK[{t}] must match sourceLawReferenceTemperaturesK[{t}]"
            )

    expected_active = _active_boundary_conditions(terminals, port_roles, ref_temps, comp, raw)
    if net.get("activeBoundaryConditions") != expected_active:
        raise ValueError("network.activeBoundaryConditions does not match active boundary state")
    if net.get("supplyMatrixUnit") != "W/K":
        raise ValueError("network.supplyMatrixUnit must be 'W/K'")
    if net.get("supplyMatrixSignConvention") != "supply_into_network_per_unit_terminal_temperature_rise":
        raise ValueError("invalid network.supplyMatrixSignConvention")

    # Validate status and reconcile with rawResult.
    status = record.get("status")
    if not isinstance(status, dict):
        raise ValueError("status mapping required")
    phase_process = status.get("phaseProcess")
    if phase_process not in VALID_PHASE_PROCESSES[comp]:
        raise ValueError(f"invalid status.phaseProcess {phase_process!r} for {comp}")
    if phase_process != raw.get("phaseProcess"):
        raise ValueError("status.phaseProcess must match rawResult.phaseProcess")
    if status.get("plateauStatus") not in VALID_PLATEAU_STATUSES:
        raise ValueError("invalid status.plateauStatus")
    if status["plateauStatus"] != raw.get("plateauStatus"):
        raise ValueError("status.plateauStatus must match rawResult.plateauStatus")
    if status.get("postExhaustionModeled") is not False:
        raise ValueError("status.postExhaustionModeled must be False")

    ex_phase = status.get("exhaustedPhase")
    if comp == "body_phase_bath_exchange":
        expected_ex_phase = raw.get("exhaustedPhase")
    else:
        if status["plateauStatus"] == "exhausted":
            expected_ex_phase = "solid" if phase_process == "melting" else (
                "liquid" if phase_process == "freezing" else None
            )
        else:
            expected_ex_phase = None
    if status["plateauStatus"] == "exhausted":
        if ex_phase not in VALID_EXHAUSTED_PHASES or ex_phase != expected_ex_phase:
            raise ValueError("exhausted plateauStatus requires matching exhaustedPhase in ('solid', 'liquid')")
    elif ex_phase is not None:
        raise ValueError("non-exhausted plateauStatus must have exhaustedPhase=None")

    if status.get("requestedDurationS") != raw.get("requestedDurationS"):
        raise ValueError("status.requestedDurationS must match rawResult.requestedDurationS")
    req_dur = _parse_rational_str(status.get("requestedDurationS"), "status.requestedDurationS")
    mod_lo, mod_hi = validate_interval_quantity(
        status.get("modeledDurationS"),
        label="status.modeledDurationS",
        expected_unit="s",
        expected_owner="investigation",
        expected_sign="elapsed_time_nonnegative",
        expected_bounds=raw.get("modeledDurationBoundsS"),
        nonnegative=True,
    )
    if mod_hi > req_dur:
        raise ValueError("modeledDurationS must lie within [0, requestedDurationS]")

    raw_exh = raw.get("exhaustionTimeBoundsS")
    if raw_exh is None:
        if status.get("exhaustionTimeS") is not None:
            raise ValueError("status.exhaustionTimeS must be None when rawResult.exhaustionTimeBoundsS is None")
    else:
        validate_interval_quantity(
            status.get("exhaustionTimeS"),
            label="status.exhaustionTimeS",
            expected_unit="s",
            expected_owner=f"phase_bath:{phase_port}",
            expected_sign="elapsed_time_nonnegative",
            expected_bounds=raw_exh,
            nonnegative=True,
        )

    if comp == "radial_phase_bath":
        if status.get("reversalTimeS") is not None:
            raise ValueError("radial_phase_bath must have status.reversalTimeS=None")
    else:
        raw_rev = raw.get("reversalTimeBoundsS")
        is_reversing = phase_process.startswith("reversing_")
        if is_reversing != (raw_rev is not None):
            raise ValueError("reversing phaseProcess must correspond to non-None reversalTimeBoundsS")
        if raw_rev is None:
            if status.get("reversalTimeS") is not None:
                raise ValueError("status.reversalTimeS must be None for non-reversing process")
        else:
            validate_interval_quantity(
                status.get("reversalTimeS"),
                label="status.reversalTimeS",
                expected_unit="s",
                expected_owner=f"phase_bath:{phase_port}",
                expected_sign="elapsed_time_nonnegative",
                expected_bounds=raw_rev,
                nonnegative=True,
            )

    # Validate inputs reconciliation with rawResult.
    inputs = record.get("inputs")
    if not isinstance(inputs, dict) or inputs.get("durationS") != raw.get("requestedDurationS"):
        raise ValueError("inputs.durationS must match rawResult.requestedDurationS")
    pb_in = inputs.get("phaseBath")
    expected_pb_in = {
        "port": phase_port,
        "transitionTemperatureK": raw.get("transitionTemperatureK"),
        "specificLatentHeatJPerKg": raw.get("specificLatentHeatJPerKg"),
        "initialSolidKg": raw.get("initialSolidKg"),
        "initialLiquidKg": raw.get("initialLiquidKg"),
    }
    if pb_in != expected_pb_in:
        raise ValueError("inputs.phaseBath does not match rawResult")

    # Validate quantities (exact unit, owner, signConvention, domain, and rawResult bounds).
    quantities = record.get("quantities")
    if not isinstance(quantities, dict):
        raise ValueError("quantities mapping required")
    validate_interval_quantity(
        quantities.get("latentEnergyIntoBathJ"),
        label="quantities.latentEnergyIntoBathJ",
        expected_unit="J",
        expected_owner=f"phase_bath:{phase_port}",
        expected_sign="into_phase_bath_positive",
        expected_bounds=raw.get("latentEnergyIntoBathBoundsJ"),
    )
    validate_interval_quantity(
        quantities.get("remainingSolidKg"),
        label="quantities.remainingSolidKg",
        expected_unit="kg",
        expected_owner=f"phase_bath:{phase_port}",
        expected_sign="mass_nonnegative",
        expected_bounds=raw.get("remainingSolidBoundsKg"),
        nonnegative=True,
    )
    validate_interval_quantity(
        quantities.get("remainingLiquidKg"),
        label="quantities.remainingLiquidKg",
        expected_unit="kg",
        expected_owner=f"phase_bath:{phase_port}",
        expected_sign="mass_nonnegative",
        expected_bounds=raw.get("remainingLiquidBoundsKg"),
        nonnegative=True,
    )

    geom = record.get("geometry")
    if comp == "radial_phase_bath":
        shell = raw["radialShell"]
        validate_interval_quantity(
            quantities.get("bathInflowDuringPlateauW"),
            label="quantities.bathInflowDuringPlateauW",
            expected_unit="W",
            expected_owner=f"phase_bath:{phase_port}",
            expected_sign="into_phase_bath_positive",
            expected_bounds=raw.get("bathInflowDuringPlateauBoundsW"),
        )
        validate_interval_quantity(
            quantities.get("surfaceOutwardHeatRateW"),
            label="quantities.surfaceOutwardHeatRateW",
            expected_unit="W",
            expected_owner=f"radial_surface:{partner_port}",
            expected_sign="outward_from_radial_surface_positive",
            expected_bounds=shell.get("outwardHeatRateBoundsW"),
        )
        validate_interval_quantity(
            quantities.get("exposedAreaM2"),
            label="quantities.exposedAreaM2",
            expected_unit="m2",
            expected_owner=f"radial_surface:{partner_port}",
            expected_sign="area_positive",
            expected_bounds=shell.get("exposedAreaBoundsM2"),
            positive=True,
        )
        surfs = quantities.get("surfaceTemperaturesK")
        raw_surfs = shell.get("surfaces")
        if not isinstance(surfs, list) or not isinstance(raw_surfs, list) or len(surfs) != len(raw_surfs) or len(surfs) < 2:
            raise ValueError("radial_phase_bath surfaceTemperaturesK must match rawResult.radialShell.surfaces")
        for idx, (surf, raw_surf) in enumerate(zip(surfs, raw_surfs)):
            if not isinstance(surf, dict) or surf.get("radiusM") != raw_surf.get("radiusM"):
                raise ValueError(f"surfaceTemperaturesK[{idx}].radiusM must match rawResult")
            validate_interval_quantity(
                surf.get("temperatureK"),
                label=f"surfaceTemperaturesK[{idx}].temperatureK",
                expected_unit="K",
                expected_owner=f"radial_surface:{partner_port}@r={raw_surf['radiusM']}m",
                expected_sign="absolute_temperature_nonnegative",
                expected_bounds=raw_surf.get("temperatureBoundsK"),
                nonnegative=True,
            )
        res_inflows = quantities.get("maintainedReservoirInflowsW")
        raw_res_inflows = raw.get("maintainedReservoirInflowBoundsW", {})
        if not isinstance(res_inflows, dict) or set(res_inflows) != set(raw_res_inflows) or set(res_inflows) != set(maintained_ports):
            raise ValueError("maintainedReservoirInflowsW keys must match maintained_reservoir ports and rawResult")
        for name, raw_pair in raw_res_inflows.items():
            validate_interval_quantity(
                res_inflows[name],
                label=f"maintainedReservoirInflowsW.{name}",
                expected_unit="W",
                expected_owner=f"maintained_reservoir:{name}",
                expected_sign="into_maintained_reservoir_positive",
                expected_bounds=raw_pair,
            )
        for q_key, raw_key in (
            ("netHeatToAirW", "netHeatToAirBoundsW"),
            ("netHeatToEnclosureW", "netHeatToEnclosureBoundsW"),
        ):
            if (q_key in quantities) != (raw_key in shell):
                raise ValueError(f"quantities.{q_key} presence must match rawResult.radialShell.{raw_key}")
            if q_key in quantities:
                validate_interval_quantity(
                    quantities[q_key],
                    label=f"quantities.{q_key}",
                    expected_unit="W",
                    expected_owner=f"radial_surface:{partner_port}",
                    expected_sign="outward_from_radial_surface_positive",
                    expected_bounds=shell[raw_key],
                )
        if (not isinstance(geom, dict)
                or geom.get("kind") not in VALID_RADIAL_GEOMETRIES
                or geom.get("kind") != shell.get("geometry")
                or geom.get("cylinderLengthM") != shell.get("cylinderLengthM")
                or geom.get("innerRadiusM") != raw_surfs[0].get("radiusM")
                or geom.get("layers") != shell.get("layers")
                or geom.get("exposedAreaM2") != quantities["exposedAreaM2"]):
            raise ValueError("radial_phase_bath geometry does not match rawResult.radialShell")
        rs_in = inputs.get("radialShell")
        expected_exterior = {
            "enclosureTemperatureK": shell.get("enclosureTemperatureK"),
            "emissivity": shell.get("emissivity"),
            "sigmaWPerM2K4": shell.get("sigmaWPerM2K4"),
            "airTemperatureK": shell.get("airTemperatureK"),
            "convectionCoefficientWPerM2K": shell.get("convectionCoefficientWPerM2K"),
        }
        if (not isinstance(rs_in, dict)
                or set(rs_in) != {"surfacePort", "geometry", "exterior"}
                or rs_in.get("surfacePort") != partner_port
                or rs_in.get("geometry") != {
                    "kind": shell["geometry"],
                    "innerRadiusM": raw_surfs[0]["radiusM"],
                    "cylinderLengthM": shell["cylinderLengthM"],
                    "layers": shell["layers"],
                }):
            raise ValueError("inputs.radialShell does not match rawResult.radialShell")
        if rs_in.get("exterior") != expected_exterior:
            raise ValueError("inputs.radialShell.exterior does not match rawResult.radialShell")
        if set(inputs) != {"durationS", "phaseBath", "radialShell"}:
            raise ValueError("radial_phase_bath inputs must contain exact keys durationS, phaseBath, radialShell")
    else:
        for q_key, raw_key, unit, owner, sign, nonneg, pos in (
            ("bodyEquilibriumTemperatureK", "bodyEquilibriumTemperatureBoundsK", "K", f"body:{partner_port}", "absolute_temperature_nonnegative", True, False),
            ("bodyTimeConstantS", "bodyTimeConstantBoundsS", "s", f"body:{partner_port}", "positive_time_constant", False, True),
            ("initialBathInflowW", "initialBathInflowBoundsW", "W", f"phase_bath:{phase_port}", "into_phase_bath_positive", False, False),
            ("asymptoticBathInflowW", "asymptoticBathInflowBoundsW", "W", f"phase_bath:{phase_port}", "into_phase_bath_positive", False, False),
            ("finalBodyTemperatureK", "finalBodyTemperatureBoundsK", "K", f"body:{partner_port}", "absolute_temperature_nonnegative", True, False),
            ("bodyEnergyChangeJ", "bodyEnergyChangeBoundsJ", "J", f"body:{partner_port}", "into_body_positive", False, False),
        ):
            validate_interval_quantity(
                quantities.get(q_key),
                label=f"quantities.{q_key}",
                expected_unit=unit,
                expected_owner=owner,
                expected_sign=sign,
                expected_bounds=raw.get(raw_key),
                nonnegative=nonneg,
                positive=pos,
            )
        if not isinstance(geom, dict) or geom != {"kind": "lumped_network_port"}:
            raise ValueError("body_phase_bath_exchange geometry must be {'kind': 'lumped_network_port'}")
        expected_body_in = {
            "port": partner_port,
            "heatCapacityJPerK": raw.get("heatCapacityJPerK"),
            "initialBodyTemperatureK": raw.get("initialBodyTemperatureK"),
        }
        if inputs.get("body") != expected_body_in:
            raise ValueError("inputs.body does not match rawResult")
        if set(inputs) != {"durationS", "phaseBath", "body"}:
            raise ValueError("body_phase_bath_exchange inputs must contain exact keys durationS, phaseBath, body")

    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, help="Path to a JSON offline investigation request")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.request).read_text(encoding="utf-8"))
    print(json.dumps(run_investigation(payload), indent=2))


if __name__ == "__main__":
    main()
