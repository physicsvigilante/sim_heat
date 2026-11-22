"""Backward-compatible typed offline investigation contract for composed thermal studies.

Scoped to two existing offline analytical compositions:
- ``radial_phase_bath``: steady network + radial insulating shell + coexisting phase bath
- ``body_phase_bath_exchange``: steady network + lumped heat-capacity body + finite phase bath

Preserves exact rational interval enclosures, explicit SI units, terminal ownership,
heat-flow sign conventions, modeled duration limits, and offline provenance flags
without promoting mathematical calculations to native authority.
"""
import argparse
from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path

from tools.body_phase_bath_exchange import solve_from_law as solve_body_phase_bath
from tools.offline_provenance import OFFLINE_FLAG_KEYS, SOURCE_HASH_KEYS, _SHA256_RE, offline_provenance
from tools.radial_phase_bath import solve_from_law as solve_radial_phase_bath
from tools.radiating_surface import decimal_input
from tools.terminal_response import investigate as terminal_response

CONTRACT_SCHEMA = "sim_heat.offline_investigation/1"
EVIDENCE_CATEGORY = "offline_analytical_calculation"
ENDPOINT_MEANING = "exact_rational_closed_enclosure"
SUPPORTED_COMPOSITIONS = ("radial_phase_bath", "body_phase_bath_exchange")
VALID_PLATEAU_STATUSES = ("coexisting", "exhausted", "exhaustion_time_uncertain")
VALID_EXHAUSTED_PHASES = ("solid", "liquid")
VALID_RADIAL_GEOMETRIES = ("sphere", "cylinder")


def _require_nonempty_str(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _parse_rational_str(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a rational string")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"{label} must be a valid rational string") from exc


def parse_interval_bounds(pair, label):
    """Validate a 2-element exact rational closed enclosure [low, high] with low <= high."""
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        raise ValueError(f"{label} must be a 2-element [low, high] rational interval")
    low = _parse_rational_str(pair[0], f"{label} lower bound")
    high = _parse_rational_str(pair[1], f"{label} upper bound")
    if low > high:
        raise ValueError(f"{label} has inverted interval bounds: {low} > {high}")
    return low, high


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


def validate_interval_quantity(record, *, label="interval", expected_unit=None):
    """Validate a serialized interval quantity dictionary."""
    if not isinstance(record, dict):
        raise ValueError(f"{label} must be an interval record mapping")
    required = {"bounds", "unit", "owner", "signConvention", "endpointMeaning"}
    if set(record) != required:
        raise ValueError(f"{label} must contain exact keys {sorted(required)}")
    low, high = parse_interval_bounds(record["bounds"], f"{label}.bounds")
    unit = _require_nonempty_str(record["unit"], f"{label}.unit")
    if expected_unit is not None and unit != expected_unit:
        raise ValueError(f"{label}.unit must be {expected_unit!r}, got {unit!r}")
    _require_nonempty_str(record["owner"], f"{label}.owner")
    _require_nonempty_str(record["signConvention"], f"{label}.signConvention")
    if record["endpointMeaning"] != ENDPOINT_MEANING:
        raise ValueError(f"{label}.endpointMeaning must be {ENDPOINT_MEANING!r}")
    return low, high


def validate_pinned_law(law):
    """Validate a prebuilt pinned terminal-response law mapping before composition."""
    provenance = offline_provenance(law)
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
    for row_name in terminals:
        row = matrix[row_name]
        if not isinstance(row, dict) or set(row) != terminal_set:
            raise ValueError(f"supplyResponseBoundsWPerK[{row_name}] columns must match terminals")
        for col_name in terminals:
            parse_interval_bounds(
                row[col_name], f"supplyResponseBoundsWPerK[{row_name}][{col_name}]"
            )
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
    if "studyPath" in src or "factsSha256" in src and "terminals" not in src:
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
            "innerRadiusM": rs.geometry.inner_radius_m,
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
                    "kind": rs.geometry.kind,
                    "innerRadiusM": rs.geometry.inner_radius_m,
                    "cylinderLengthM": rs.geometry.cylinder_length_m,
                    "layers": [
                        {"outerRadiusM": l.outer_radius_m, "conductivityWPerMK": l.conductivity_w_per_m_k}
                        for l in rs.geometry.layers
                    ],
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
            "imposedTemperaturesK": {t: str(law["imposedTemperaturesK"][t]) for t in terminals},
            "portRoles": port_roles,
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
    """Verify schema, offline provenance, intervals, and status semantics on a serialized record."""
    if not isinstance(record, dict):
        raise ValueError("investigation record must be a mapping")
    if record.get("schema") != CONTRACT_SCHEMA:
        raise ValueError(f"expected schema {CONTRACT_SCHEMA!r}")
    comp = record.get("composition")
    if comp not in SUPPORTED_COMPOSITIONS:
        raise ValueError(f"unsupported composition {comp!r}")

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

    status = record.get("status")
    if not isinstance(status, dict):
        raise ValueError("status mapping required")
    if status.get("plateauStatus") not in VALID_PLATEAU_STATUSES:
        raise ValueError("invalid status.plateauStatus")
    if status.get("postExhaustionModeled") is not False:
        raise ValueError("status.postExhaustionModeled must be False")
    ex_phase = status.get("exhaustedPhase")
    if status["plateauStatus"] == "exhausted":
        if ex_phase not in VALID_EXHAUSTED_PHASES:
            raise ValueError("exhausted plateauStatus requires exhaustedPhase in ('solid', 'liquid')")
    elif ex_phase is not None:
        raise ValueError("non-exhausted plateauStatus must have exhaustedPhase=None")

    req_dur = _parse_rational_str(status.get("requestedDurationS"), "status.requestedDurationS")
    mod_lo, mod_hi = validate_interval_quantity(
        status.get("modeledDurationS"), label="status.modeledDurationS", expected_unit="s"
    )
    if mod_lo < 0 or mod_hi > req_dur:
        raise ValueError("modeledDurationS must lie within [0, requestedDurationS]")
    if status.get("exhaustionTimeS") is not None:
        ex_lo, _ = validate_interval_quantity(
            status["exhaustionTimeS"], label="status.exhaustionTimeS", expected_unit="s"
        )
        if ex_lo < 0:
            raise ValueError("exhaustionTimeS must be nonnegative")
    if status.get("reversalTimeS") is not None:
        rev_lo, _ = validate_interval_quantity(
            status["reversalTimeS"], label="status.reversalTimeS", expected_unit="s"
        )
        if rev_lo < 0:
            raise ValueError("reversalTimeS must be nonnegative")

    quantities = record.get("quantities")
    if not isinstance(quantities, dict):
        raise ValueError("quantities mapping required")
    for q_key, unit in (
        ("latentEnergyIntoBathJ", "J"),
        ("remainingSolidKg", "kg"),
        ("remainingLiquidKg", "kg"),
    ):
        validate_interval_quantity(quantities.get(q_key), label=f"quantities.{q_key}", expected_unit=unit)

    if comp == "radial_phase_bath":
        for q_key, unit in (
            ("bathInflowDuringPlateauW", "W"),
            ("surfaceOutwardHeatRateW", "W"),
            ("exposedAreaM2", "m2"),
        ):
            validate_interval_quantity(quantities.get(q_key), label=f"quantities.{q_key}", expected_unit=unit)
        surfs = quantities.get("surfaceTemperaturesK")
        if not isinstance(surfs, list) or len(surfs) < 2:
            raise ValueError("radial_phase_bath requires at least two surface temperature entries")
        for idx, surf in enumerate(surfs):
            if not isinstance(surf, dict) or "radiusM" not in surf:
                raise ValueError(f"surfaceTemperaturesK[{idx}] missing radiusM")
            validate_interval_quantity(
                surf.get("temperatureK"), label=f"surfaceTemperaturesK[{idx}].temperatureK", expected_unit="K"
            )
        res_inflows = quantities.get("maintainedReservoirInflowsW")
        if not isinstance(res_inflows, dict):
            raise ValueError("maintainedReservoirInflowsW mapping required")
        for name, item in res_inflows.items():
            validate_interval_quantity(
                item, label=f"maintainedReservoirInflowsW.{name}", expected_unit="W"
            )
        for opt_key in ("netHeatToAirW", "netHeatToEnclosureW"):
            if opt_key in quantities:
                validate_interval_quantity(
                    quantities[opt_key], label=f"quantities.{opt_key}", expected_unit="W"
                )
        geom = record.get("geometry")
        if not isinstance(geom, dict) or geom.get("kind") not in VALID_RADIAL_GEOMETRIES:
            raise ValueError("radial_phase_bath geometry.kind must be 'sphere' or 'cylinder'")
    else:
        for q_key, unit in (
            ("bodyEquilibriumTemperatureK", "K"),
            ("bodyTimeConstantS", "s"),
            ("initialBathInflowW", "W"),
            ("asymptoticBathInflowW", "W"),
            ("finalBodyTemperatureK", "K"),
            ("bodyEnergyChangeJ", "J"),
        ):
            validate_interval_quantity(quantities.get(q_key), label=f"quantities.{q_key}", expected_unit=unit)
        geom = record.get("geometry")
        if not isinstance(geom, dict) or geom.get("kind") != "lumped_network_port":
            raise ValueError("body_phase_bath_exchange geometry.kind must be 'lumped_network_port'")
    net = record.get("network")
    if (not isinstance(net, dict) or not isinstance(net.get("terminals"), list)
            or not isinstance(net.get("portRoles"), dict)
            or set(net["portRoles"]) != set(net["terminals"])):
        raise ValueError("network.terminals and network.portRoles must match exactly")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, help="Path to a JSON offline investigation request")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.request).read_text(encoding="utf-8"))
    print(json.dumps(run_investigation(payload), indent=2))


if __name__ == "__main__":
    main()
