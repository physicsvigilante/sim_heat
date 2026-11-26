"""Certified piecewise-linear enthalpy-mode continuation over passive thermal networks (M04).

Composes any validated connected passive steady conduction law (``DerivedLaw``, pinned H1
terminal response, or Schur-joined network) with arbitrary per-terminal attachments of:
- ``sensible_body`` (or ``lumped_body``): finite heat-capacity body (C_i > 0, T_i(0) >= 0, optional
  signed constant ``heatInputW`` P_i)
- ``phase_substance``: piecewise-linear enthalpy-capable substance (M_i = m_s + m_l > 0, T_tr > 0,
  L > 0, c_s > 0, c_l > 0, T_i(0) >= 0, optional signed constant ``heatInputW`` P_i), transitioning
  sequentially across ``solid`` (H <= 0) <-> ``plateau`` (0 <= H <= M*L) <-> ``liquid`` (H >= M*L)
- ``maintained``: fixed Dirichlet reservoir (T_m >= 0) with exact integrated energy ledger

Uses certified outward-rounded matrix exponentials (``simheat.core.step_matrix``), exact
inhomogeneous Kamke/Mueller maximum-principle cell bounds, 4-iteration local-slope Picard
contraction (capturing slow cooling re-entry and reversing-reservoir hysteresis without global
Lipschitz blowup), exact network-automorphism symmetry proofs for simultaneous ties on exact-point
laws, closed-system energy-ledger projection, and honest ``mode_sequence_uncertain`` stops that
always enclose the physical state up to the modeled stop time.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from qualification.h1_n11.rational_dynamic_proof import apply
from simheat.core import Box, ONE, ZERO, step_matrix
from simheat.laws import validate_terminal_law
from tools.join_thermal_networks import bounds
from tools.multiport_thermal_network import _symmetric_conductances
from tools.offline_investigation import _expect_exact_keys
from tools.offline_provenance import OFFLINE_FLAG_KEYS, SOURCE_HASH_KEYS
from tools.radiating_surface import decimal_input

ENTHALPY_CONTINUATION_SCHEMA = "sim_heat.offline_enthalpy_continuation/1"
EVIDENCE_CATEGORY = "offline_analytical_calculation"
VALID_PORT_KINDS = ("sensible_body", "lumped_body", "phase_substance", "maintained")

MAX_INITIAL_STEPS = 256
DEFAULT_INITIAL_STEPS = 16
DEFAULT_MAX_EVENTS = 32
DEFAULT_MAX_PRUNE_REFINEMENTS = 240
DEFAULT_MAX_BISECT_REFINEMENTS = 96


def signed_decimal_input(value: Any, label: str) -> Fraction:
    """Parse a strict signed SI decimal string into an exact ``Fraction``."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a decimal string")
    raw = value.strip()
    if not raw:
        raise ValueError(f"{label} must be a non-empty decimal string")
    if raw[0] == "-":
        if len(raw) == 1 or raw[1] in "+-":
            raise ValueError(f"{label} has invalid signed decimal format {value!r}")
        return -decimal_input(raw[1:], label)
    if raw[0] == "+":
        raise ValueError(f"{label} must not have a leading '+' sign")
    return decimal_input(raw, label)


def _validate_positive_int(value: Any, label: str, *, upper: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    if upper is not None and value > upper:
        raise ValueError(f"{label} must be an integer in [1, {upper}]")
    return value


def _box_union(boxes: list[Box]) -> Box:
    return Box.bounds(min(b.span()[0] for b in boxes), max(b.span()[1] for b in boxes))


@dataclass(frozen=True)
class _PortSpec:
    name: str
    kind: str  # "sensible_body", "phase_substance", "maintained"
    t0: Fraction
    capacity: Fraction = Fraction(0)
    t_tr: Fraction = Fraction(0)
    latent: Fraction = Fraction(0)
    c_s: Fraction = Fraction(0)
    c_l: Fraction = Fraction(0)
    solid0: Fraction = Fraction(0)
    liquid0: Fraction = Fraction(0)
    heat_input: Fraction = Fraction(0)

    @property
    def total_mass(self) -> Fraction:
        return self.solid0 + self.liquid0

    @property
    def cap_s(self) -> Fraction:
        return self.total_mass * self.c_s

    @property
    def cap_l(self) -> Fraction:
        return self.total_mass * self.c_l

    @property
    def e_latent(self) -> Fraction:
        return self.total_mass * self.latent

    @property
    def h0(self) -> Fraction:
        """Initial enthalpy relative to pure solid at T_tr (for phase_substance) or 0."""
        if self.kind != "phase_substance":
            return Fraction(0)
        if self.t0 < self.t_tr:
            return self.cap_s * (self.t0 - self.t_tr)
        if self.t0 > self.t_tr:
            return self.e_latent + self.cap_l * (self.t0 - self.t_tr)
        return self.liquid0 * self.latent

    def enthalpy_from_temp(self, mode: str, t_box: Box) -> Box:
        """Exact enthalpy box relative to pure solid at T_tr for sensible modes."""
        if self.kind == "sensible_body":
            return Box.exact(self.capacity) * (t_box - self.t0)
        if mode == "solid":
            return Box.exact(self.cap_s) * (t_box - self.t_tr)
        if mode == "liquid":
            return Box.exact(self.e_latent) + Box.exact(self.cap_l) * (t_box - self.t_tr)
        raise ValueError(f"enthalpy_from_temp called on non-sensible mode {mode!r}")

    def temp_from_enthalpy(self, mode: str, h_box: Box) -> Box:
        """Exact temperature box from enthalpy box relative to pure solid at T_tr."""
        if self.kind == "sensible_body":
            return Box.exact(self.t0) + h_box / self.capacity
        if mode == "solid":
            return Box.exact(self.t_tr) + h_box / self.cap_s
        if mode == "liquid":
            return Box.exact(self.t_tr) + (h_box - self.e_latent) / self.cap_l
        return Box.exact(self.t_tr)

    def symmetry_signature(self) -> tuple[Any, ...]:
        return (
            self.kind,
            self.t_tr,
            self.latent,
            self.c_s,
            self.c_l,
            self.total_mass,
            self.heat_input,
        )


def _parse_ports(terminals: list[str], ports: dict[str, Any]) -> tuple[dict[str, _PortSpec], list[str], list[str], list[str]]:
    if not isinstance(ports, dict) or set(ports) != set(terminals):
        raise ValueError("ports mapping must assign an attachment to every terminal in the pinned network")

    parsed: dict[str, _PortSpec] = {}
    body_ports: list[str] = []
    phase_ports: list[str] = []
    maintained_ports: list[str] = []

    for name in terminals:
        spec = ports[name]
        if not isinstance(spec, dict):
            raise ValueError(f"port {name!r} specification must be a mapping")
        kind = spec.get("kind")
        if kind not in VALID_PORT_KINDS:
            raise ValueError(f"port {name!r} has unsupported kind {kind!r}; expected one of {VALID_PORT_KINDS}")

        if kind in ("sensible_body", "lumped_body"):
            _expect_exact_keys(
                spec,
                required=("kind",),
                optional=(
                    "heatCapacityJPerK",
                    "massKg",
                    "specificHeatJPerKgK",
                    "initialTemperatureK",
                    "initialBodyTemperatureK",
                    "heatInputW",
                ),
                label=f"ports[{name}]",
            )
            has_t = "initialTemperatureK" in spec
            has_bt = "initialBodyTemperatureK" in spec
            if has_t == has_bt:
                raise ValueError(
                    f"ports[{name}] must provide exactly one of initialTemperatureK or initialBodyTemperatureK"
                )
            t0 = decimal_input(
                spec["initialTemperatureK"] if has_t else spec["initialBodyTemperatureK"],
                f"initial temperature at {name}",
            )
            has_c = "heatCapacityJPerK" in spec
            has_mc = "massKg" in spec or "specificHeatJPerKgK" in spec
            if has_mc and ("massKg" not in spec or "specificHeatJPerKgK" not in spec):
                raise ValueError(f"ports[{name}] requires both massKg and specificHeatJPerKgK")
            if not has_c and not has_mc:
                raise ValueError(f"ports[{name}] requires heatCapacityJPerK or (massKg and specificHeatJPerKgK)")
            if has_c:
                cap = decimal_input(spec["heatCapacityJPerK"], f"heat capacity at {name}")
                if cap <= 0:
                    raise ValueError(f"positive heat capacity required at {name}")
                if has_mc:
                    m = decimal_input(spec["massKg"], f"mass at {name}")
                    c = decimal_input(spec["specificHeatJPerKgK"], f"specific heat at {name}")
                    if m <= 0 or c <= 0 or m * c != cap:
                        raise ValueError(f"ports[{name}] massKg * specificHeatJPerKgK disagrees with heatCapacityJPerK")
            else:
                m = decimal_input(spec["massKg"], f"mass at {name}")
                c = decimal_input(spec["specificHeatJPerKgK"], f"specific heat at {name}")
                if m <= 0 or c <= 0:
                    raise ValueError(f"positive massKg and specificHeatJPerKgK required at {name}")
                cap = m * c
            power = signed_decimal_input(spec["heatInputW"], f"heatInputW at {name}") if "heatInputW" in spec else Fraction(0)
            parsed[name] = _PortSpec(name=name, kind="sensible_body", t0=t0, capacity=cap, heat_input=power)
            body_ports.append(name)

        elif kind == "phase_substance":
            _expect_exact_keys(
                spec,
                required=(
                    "kind",
                    "transitionTemperatureK",
                    "specificLatentHeatJPerKg",
                    "solidSpecificHeatJPerKgK",
                    "liquidSpecificHeatJPerKgK",
                    "initialSolidKg",
                    "initialLiquidKg",
                ),
                optional=("initialTemperatureK", "heatInputW"),
                label=f"ports[{name}]",
            )
            t_tr = decimal_input(spec["transitionTemperatureK"], f"transition temperature at {name}")
            latent = decimal_input(spec["specificLatentHeatJPerKg"], f"specific latent heat at {name}")
            c_s = decimal_input(spec["solidSpecificHeatJPerKgK"], f"solid specific heat at {name}")
            c_l = decimal_input(spec["liquidSpecificHeatJPerKgK"], f"liquid specific heat at {name}")
            solid0 = decimal_input(spec["initialSolidKg"], f"initial solid mass at {name}")
            liquid0 = decimal_input(spec["initialLiquidKg"], f"initial liquid mass at {name}")
            if min(t_tr, latent, c_s, c_l) <= 0 or solid0 < 0 or liquid0 < 0 or (solid0 + liquid0) <= 0:
                raise ValueError(f"invalid phase_substance parameters at {name}")
            t0 = (
                decimal_input(spec["initialTemperatureK"], f"initial temperature at {name}")
                if "initialTemperatureK" in spec
                else t_tr
            )
            if t0 < t_tr and (solid0 <= 0 or liquid0 != 0):
                raise ValueError(f"subcooled phase_substance at {name} requires positive solid and zero liquid")
            if t0 > t_tr and (liquid0 <= 0 or solid0 != 0):
                raise ValueError(f"superheated phase_substance at {name} requires positive liquid and zero solid")
            power = signed_decimal_input(spec["heatInputW"], f"heatInputW at {name}") if "heatInputW" in spec else Fraction(0)
            parsed[name] = _PortSpec(
                name=name,
                kind="phase_substance",
                t0=t0,
                t_tr=t_tr,
                latent=latent,
                c_s=c_s,
                c_l=c_l,
                solid0=solid0,
                liquid0=liquid0,
                heat_input=power,
            )
            phase_ports.append(name)

        else:  # maintained
            _expect_exact_keys(spec, required=("kind", "temperatureK"), label=f"ports[{name}]")
            temp = decimal_input(spec["temperatureK"], f"maintained temperature at {name}")
            parsed[name] = _PortSpec(name=name, kind="maintained", t0=temp)
            maintained_ports.append(name)

    if not body_ports and not phase_ports:
        raise ValueError("at least one sensible_body or phase_substance port is required")
    return parsed, body_ports, phase_ports, maintained_ports


class _ModeEvolution:
    """Certified matrix-exponential evolution for one fixed affine enthalpy mode."""

    def __init__(
        self,
        terminals: list[str],
        specs: dict[str, _PortSpec],
        modes: dict[str, str],
        t_init: dict[str, Box],
        h_init: dict[str, Box],
        w_net: dict[tuple[str, str], tuple[Fraction, Fraction]],
    ):
        self.terminals = list(terminals)
        self.specs = specs
        self.modes = dict(modes)
        self.t_init = dict(t_init)
        self.h_init = dict(h_init)
        self.w_net = w_net
        self.w_box = {k: Box.bounds(v[0], v[1]) for k, v in w_net.items()}

        self.sensible = [n for n in self.terminals if modes[n] in ("body", "solid", "liquid")]
        self.clamped = [n for n in self.terminals if modes[n] in ("plateau", "maintained")]
        self.s_idx = {n: i for i, n in enumerate(self.sensible)}
        self.n = len(self.sensible)

        self.caps: dict[str, Fraction] = {}
        for n in self.sensible:
            sp = specs[n]
            if modes[n] == "body":
                self.caps[n] = sp.capacity
            elif modes[n] == "solid":
                self.caps[n] = sp.cap_s
            else:
                self.caps[n] = sp.cap_l

        self.clamped_t: dict[str, Fraction] = {}
        for n in self.clamped:
            sp = specs[n]
            self.clamped_t[n] = sp.t_tr if modes[n] == "plateau" else sp.t0

        lows = [t_init[n].span()[0] for n in self.sensible] + list(self.clamped_t.values())
        highs = [t_init[n].span()[1] for n in self.sensible] + list(self.clamped_t.values())
        self.t_min_0 = min(lows)
        self.t_max_0 = max(highs)
        self.origin = self.t_min_0
        self.span = max(Fraction(1), self.t_max_0 - self.t_min_0)

        # Inhomogeneous Kamke/Mueller comparison rates: T_lo(a) + r_min*h <= T(t) <= T_hi(a) + r_max*h.
        self.r_max = max([Fraction(0)] + [specs[n].heat_input / self.caps[n] for n in self.sensible])
        self.r_min = min([Fraction(0)] + [specs[n].heat_input / self.caps[n] for n in self.sensible])
        self.total_power = sum((specs[n].heat_input for n in self.terminals if specs[n].kind != "maintained"), Fraction(0))
        self.passive_sensible = all(specs[n].heat_input == 0 for n in self.sensible)

        self.u0 = [(t_init[n] - self.origin) / self.span for n in self.sensible]
        self.u_clamped = {c: Box.exact((t - self.origin) / self.span) for c, t in self.clamped_t.items()}
        self.y0 = self.u0 + [ZERO] * self.n + [ONE]

        dim = 2 * self.n + 1
        self.base_a = [[ZERO for _ in range(dim)] for _ in range(dim)]
        for i, b in enumerate(self.sensible):
            cap = Box.exact(self.caps[b])
            diag_w = ZERO
            affine_u = Box.exact(specs[b].heat_input / self.span)
            for other in self.terminals:
                if other == b:
                    continue
                wb = self.w_box[(b, other)]
                diag_w = diag_w + wb
                if other in self.s_idx:
                    self.base_a[i][self.s_idx[other]] = wb / cap
                else:
                    affine_u = affine_u + wb * self.u_clamped[other]
            self.base_a[i][i] = -diag_w / cap
            self.base_a[i][-1] = affine_u / cap
            self.base_a[self.n + i][i] = ONE

        self._cache: dict[Fraction, tuple[dict[str, Box], dict[str, Box], dict[str, Box]]] = {}

    def state_at(self, dt: Fraction) -> tuple[dict[str, Box], dict[str, Box], dict[str, Box]]:
        if dt in self._cache:
            return self._cache[dt]

        if dt == 0 or self.n == 0:
            t_map = {n: self.t_init[n] for n in self.sensible}
            int_map = {n: self.t_init[n] * dt for n in self.sensible}
        elif self.t_min_0 == self.t_max_0 and self.passive_sensible:
            t_map = {n: Box.exact(self.t_min_0) for n in self.sensible}
            int_map = {n: Box.exact(self.t_min_0 * dt) for n in self.sensible}
        else:
            dim = 2 * self.n + 1
            scaled = [[self.base_a[r][c] * dt for c in range(dim)] for r in range(dim)]
            for i in range(self.n):
                scaled[self.n + i][i] = ONE
            y = apply(step_matrix(scaled), self.y0)
            t_bound_lo = self.t_min_0 + self.r_min * dt
            t_bound_hi = self.t_max_0 + self.r_max * dt
            t_map = {}
            int_map = {}
            for i, n in enumerate(self.sensible):
                raw_t = y[i] * self.span + self.origin
                lo = max(t_bound_lo, raw_t.span()[0])
                hi = min(t_bound_hi, raw_t.span()[1])
                if lo > hi:
                    raise ValueError(f"temperature enclosure for {n!r} violated inhomogeneous maximum principle")
                t_map[n] = Box.bounds(lo, hi)
                int_map[n] = (y[self.n + i] * self.span + self.origin) * dt

        for c in self.clamped:
            t_map[c] = Box.exact(self.clamped_t[c])

        q_map: dict[str, Box] = {}
        for n in self.terminals:
            q = Box.exact(self.specs[n].heat_input) if self.specs[n].kind != "maintained" else ZERO
            for other in self.terminals:
                if other == n:
                    continue
                q = q + self.w_box[(n, other)] * (t_map[other] - t_map[n])
            q_map[n] = q

        h_map: dict[str, Box] = {}
        for n in self.sensible:
            h_map[n] = self.specs[n].enthalpy_from_temp(self.modes[n], t_map[n])

        for c in self.clamped:
            tc = self.clamped_t[c]
            de = Box.exact(self.specs[c].heat_input * dt) if self.specs[c].kind != "maintained" else ZERO
            for s in self.sensible:
                de = de + self.w_box[(c, s)] * (int_map[s] - tc * dt)
            for oc in self.clamped:
                if oc == c:
                    continue
                de = de + self.w_box[(c, oc)] * ((self.clamped_t[oc] - tc) * dt)
            h_map[c] = self.h_init[c] + de

        # Verify stage energy conservation: sum_sensible C_i*(T_i(dt) - T_i(0)) + sum_clamped (H_c(dt) - H_c(0)) - P*dt ni 0.
        du_sens = sum(
            (Box.exact(self.caps[n]) * (t_map[n] - self.t_init[n]) for n in self.sensible),
            ZERO,
        )
        dh_clamped = sum((h_map[c] - self.h_init[c] for c in self.clamped), ZERO)
        if not (du_sens + dh_clamped - Box.exact(self.total_power * dt)).contains_zero():
            raise ValueError("enthalpy-mode stage energy conservation check failed")

        res = (t_map, h_map, q_map)
        self._cache[dt] = res
        return res

    def subinterval(self, a: Fraction, b: Fraction) -> tuple[dict[str, Box], dict[str, Box], dict[str, Box]]:
        if a == b:
            return self.state_at(a)
        h = b - a
        ta, ha, _ = self.state_at(a)
        tb, hb, _ = self.state_at(b)

        t_sub: dict[str, Box] = {}
        for c in self.clamped:
            t_sub[c] = Box.exact(self.clamped_t[c])

        if self.n > 0:
            t_lo_a = min([ta[n].span()[0] for n in self.sensible] + list(self.clamped_t.values()))
            t_hi_a = max([ta[n].span()[1] for n in self.sensible] + list(self.clamped_t.values()))
            cell_lo = t_lo_a + self.r_min * h
            cell_hi = t_hi_a + self.r_max * h
            cell_span = cell_hi - cell_lo

            for n in self.sensible:
                sum_w_hi = sum(self.w_net[(n, o)][1] for o in self.terminals if o != n)
                v_max = (sum_w_hi * cell_span + abs(self.specs[n].heat_input)) / self.caps[n]
                vh = v_max * h
                lo = max(cell_lo, ta[n].span()[0] - vh, tb[n].span()[0] - vh)
                hi = min(cell_hi, ta[n].span()[1] + vh, tb[n].span()[1] + vh)
                if lo > hi:
                    raise ValueError(f"subinterval temperature enclosure for {n!r} is inconsistent")
                t_sub[n] = Box.bounds(lo, hi)

            # 4-iteration local-slope Picard contraction using exact ODE derivatives on [a, b].
            for _ in range(4):
                changed = False
                next_t = dict(t_sub)
                for n in self.sensible:
                    q_n = Box.exact(self.specs[n].heat_input)
                    for other in self.terminals:
                        if other == n:
                            continue
                        q_n = q_n + self.w_box[(n, other)] * (t_sub[other] - t_sub[n])
                    dlo, dhi = (q_n / self.caps[n]).span()
                    tlo = max(
                        t_sub[n].span()[0],
                        ta[n].span()[0] + min(Fraction(0), dlo) * h,
                        tb[n].span()[0] - max(Fraction(0), dhi) * h,
                    )
                    thi = min(
                        t_sub[n].span()[1],
                        ta[n].span()[1] + max(Fraction(0), dhi) * h,
                        tb[n].span()[1] - min(Fraction(0), dlo) * h,
                    )
                    if tlo > thi:
                        raise ValueError(f"Picard local-slope contraction inconsistency for {n!r}")
                    if (tlo, thi) != t_sub[n].span():
                        changed = True
                    next_t[n] = Box.bounds(tlo, thi)
                t_sub = next_t
                if not changed:
                    break

        q_sub: dict[str, Box] = {}
        for n in self.terminals:
            q = Box.exact(self.specs[n].heat_input) if self.specs[n].kind != "maintained" else ZERO
            for other in self.terminals:
                if other == n:
                    continue
                q = q + self.w_box[(n, other)] * (t_sub[other] - t_sub[n])
            q_sub[n] = q

        h_sub: dict[str, Box] = {}
        for n in self.sensible:
            h_sub[n] = self.specs[n].enthalpy_from_temp(self.modes[n], t_sub[n])

        for c in self.clamped:
            qlo, qhi = q_sub[c].span()
            alo, ahi = ha[c].span()
            blo, bhi = hb[c].span()
            elo = max(alo + min(Fraction(0), qlo) * h, blo - max(Fraction(0), qhi) * h)
            ehi = min(ahi + max(Fraction(0), qhi) * h, bhi - min(Fraction(0), qlo) * h)
            if elo > ehi:
                raise ValueError(f"subinterval enthalpy enclosure for {c!r} is inconsistent")
            h_sub[c] = Box.bounds(elo, ehi)

        return t_sub, h_sub, q_sub


def _node_event_check(
    sp: _PortSpec,
    mode: str,
    t_box: Box,
    h_box: Box,
    q_box: Box,
    *,
    t_init_box: Box,
    h_init_box: Box,
    at_start: bool,
) -> tuple[bool, str | None, set[str]]:
    """Return ``(safe, certified_target_mode, possible_hit_modes)`` for one terminal."""
    if sp.kind != "phase_substance":
        return True, None, set()
    qlo, qhi = q_box.span()

    if mode == "solid":
        tlo, thi = t_box.span()
        if tlo >= sp.t_tr:
            return False, "plateau", {"plateau"}
        if thi < sp.t_tr:
            return True, None, set()
        if at_start and t_init_box.span() == (sp.t_tr, sp.t_tr) and qhi < 0:
            return True, None, set()
        return False, None, {"plateau"}

    if mode == "liquid":
        tlo, thi = t_box.span()
        if thi <= sp.t_tr:
            return False, "plateau", {"plateau"}
        if tlo > sp.t_tr:
            return True, None, set()
        if at_start and t_init_box.span() == (sp.t_tr, sp.t_tr) and qlo > 0:
            return True, None, set()
        return False, None, {"plateau"}

    # plateau: H in (0, M*L)
    hlo, hhi = h_box.span()
    ml = sp.e_latent
    cert: str | None = None
    if hlo >= ml:
        cert = "liquid"
    elif hhi <= 0:
        cert = "solid"
    hit_liq = hhi >= ml
    hit_sol = hlo <= 0
    if at_start:
        if h_init_box.span() == (Fraction(0), Fraction(0)) and qlo > 0:
            hit_sol = False
            if cert == "solid":
                cert = None
        if h_init_box.span() == (ml, ml) and qhi < 0:
            hit_liq = False
            if cert == "liquid":
                cert = None
    hits: set[str] = set()
    if hit_liq:
        hits.add("liquid")
    if hit_sol:
        hits.add("solid")
    return (not hits), cert, hits


def _project_closed_ledger(
    terminals: list[str],
    specs: dict[str, _PortSpec],
    modes: dict[str, str],
    t_map: dict[str, Box],
    h_map: dict[str, Box],
    t_lo: Fraction,
    t_hi: Fraction,
    total_power: Fraction,
    snapped: set[str],
) -> tuple[dict[str, Box], dict[str, Box]]:
    """Sound projection onto exact closed-system energy conservation hyperplane."""
    expected_dh = Box.bounds(t_lo, t_hi) * total_power
    dh_boxes: dict[str, Box] = {}
    for n in terminals:
        sp = specs[n]
        if sp.kind == "sensible_body":
            dh_boxes[n] = Box.exact(sp.capacity) * (t_map[n] - sp.t0)
        else:
            dh_boxes[n] = h_map[n] - sp.h0

    for _ in range(2):
        for n in terminals:
            if n in snapped:
                continue
            other = sum((dh_boxes[o] for o in terminals if o != n), ZERO)
            from_ledger = expected_dh - other
            lo = max(dh_boxes[n].span()[0], from_ledger.span()[0])
            hi = min(dh_boxes[n].span()[1], from_ledger.span()[1])
            if lo > hi:
                raise ValueError(f"closed-system energy ledger projection inconsistent at {n!r}")
            dh_boxes[n] = Box.bounds(lo, hi)

    new_t = dict(t_map)
    new_h = dict(h_map)
    for n in terminals:
        if n in snapped:
            continue
        sp = specs[n]
        if sp.kind == "sensible_body":
            cand_t = Box.exact(sp.t0) + dh_boxes[n] / sp.capacity
            lo = max(t_map[n].span()[0], cand_t.span()[0])
            hi = min(t_map[n].span()[1], cand_t.span()[1])
            if lo <= hi:
                new_t[n] = Box.bounds(lo, hi)
                new_h[n] = sp.enthalpy_from_temp("body", new_t[n])
        else:
            cand_h = dh_boxes[n] + sp.h0
            h_lo = max(h_map[n].span()[0], cand_h.span()[0])
            h_hi = min(h_map[n].span()[1], cand_h.span()[1])
            if modes[n] == "plateau":
                h_lo = max(Fraction(0), h_lo)
                h_hi = min(sp.e_latent, h_hi)
            elif modes[n] == "solid":
                h_hi = min(Fraction(0), h_hi)
            else:
                h_lo = max(sp.e_latent, h_lo)
            if h_lo <= h_hi:
                new_h[n] = Box.bounds(h_lo, h_hi)
                new_t[n] = sp.temp_from_enthalpy(modes[n], new_h[n])
    return new_t, new_h


def _can_prove_simultaneous_symmetry(
    cand_nodes: list[str],
    cand_targets: dict[str, set[str]],
    specs: dict[str, _PortSpec],
    modes: dict[str, str],
    t_init: dict[str, Box],
    h_init: dict[str, Box],
    terminals: list[str],
    w_net: dict[tuple[str, str], tuple[Fraction, Fraction]],
) -> str | None:
    """Return shared target mode iff exact network-automorphism symmetry proves simultaneous crossing."""
    if len(cand_nodes) < 2:
        return None
    # Require exact point conductance law across every pair.
    if any(lo != hi for lo, hi in w_net.values()):
        return None
    # Every candidate must have the same single target mode and same current mode.
    targets = set()
    for p in cand_nodes:
        if len(cand_targets[p]) != 1:
            return None
        targets |= cand_targets[p]
    if len(targets) != 1:
        return None
    shared_target = next(iter(targets))

    ref = cand_nodes[0]
    ref_sig = specs[ref].symmetry_signature()
    ref_mode = modes[ref]
    ref_t = t_init[ref].span()
    ref_h = h_init[ref].span()
    if ref_t[0] != ref_t[1] or ref_h[0] != ref_h[1]:
        return None

    for p in cand_nodes[1:]:
        if specs[p].symmetry_signature() != ref_sig:
            return None
        if modes[p] != ref_mode:
            return None
        if t_init[p].span() != ref_t or h_init[p].span() != ref_h:
            return None

    # Every transposition (p_a <-> p_b) must leave W exactly invariant.
    for idx_a, p_a in enumerate(cand_nodes):
        for p_b in cand_nodes[idx_a + 1:]:
            for u in terminals:
                if u == p_a or u == p_b:
                    continue
                if w_net[(p_a, u)] != w_net[(p_b, u)]:
                    return None
    return shared_target


def _clip_state_to_modes(
    terminals: list[str],
    specs: dict[str, _PortSpec],
    modes: dict[str, str],
    t_map: dict[str, Box],
    h_map: dict[str, Box],
) -> tuple[dict[str, Box], dict[str, Box]]:
    """Clip phase-substance states to their active mode's physical domain (sound post-union tightening)."""
    ct = dict(t_map)
    ch = dict(h_map)
    for n in terminals:
        sp = specs[n]
        if sp.kind != "phase_substance":
            continue
        md = modes[n]
        if md == "plateau":
            hlo, hhi = ch[n].span()
            lo = max(Fraction(0), min(sp.e_latent, hlo))
            hi = max(Fraction(0), min(sp.e_latent, hhi))
            ch[n] = Box.bounds(lo, hi)
            ct[n] = Box.exact(sp.t_tr)
        elif md == "solid":
            tlo, thi = ct[n].span()
            hi = min(sp.t_tr, thi)
            lo = min(hi, tlo)
            ct[n] = Box.bounds(lo, hi)
            ch[n] = sp.enthalpy_from_temp("solid", ct[n])
        elif md == "liquid":
            tlo, thi = ct[n].span()
            lo = max(sp.t_tr, tlo)
            hi = max(lo, thi)
            ct[n] = Box.bounds(lo, hi)
            ch[n] = sp.enthalpy_from_temp("liquid", ct[n])
    return ct, ch


def _global_conservation_residual(
    terminals: list[str],
    specs: dict[str, _PortSpec],
    t_map: dict[str, Box],
    h_map: dict[str, Box],
    t_lo: Fraction,
    t_hi: Fraction,
    total_power: Fraction,
) -> Box:
    """Compute signed global energy conservation residual (must contain zero)."""
    total_du = ZERO
    for n in terminals:
        sp = specs[n]
        if sp.kind == "sensible_body":
            total_du = total_du + Box.exact(sp.capacity) * (t_map[n] - sp.t0)
        elif sp.kind == "phase_substance":
            total_du = total_du + (h_map[n] - sp.h0)
        else:  # maintained: h_map[n] holds cumulative E_in_maintained
            total_du = total_du + h_map[n]
    return total_du - Box.bounds(t_lo, t_hi) * total_power


def _phase_masses_from_state(sp: _PortSpec, mode: str, h_box: Box) -> tuple[Box, Box]:
    if mode == "solid":
        return Box.exact(sp.total_mass), ZERO
    if mode == "liquid":
        return ZERO, Box.exact(sp.total_mass)
    hlo, hhi = h_box.span()
    ml_lo = max(Fraction(0), min(sp.total_mass, hlo / sp.latent))
    ml_hi = max(Fraction(0), min(sp.total_mass, hhi / sp.latent))
    return Box.bounds(sp.total_mass - ml_hi, sp.total_mass - ml_lo), Box.bounds(ml_lo, ml_hi)


def _format_port_outputs(
    terminals: list[str],
    specs: dict[str, _PortSpec],
    modes: dict[str, str],
    t_map: dict[str, Box],
    h_map: dict[str, Box],
    q_init: dict[str, Box],
) -> tuple[dict[str, Any], dict[str, Any]]:
    active_bcs: dict[str, Any] = {}
    ports_out: dict[str, Any] = {}
    for n in terminals:
        sp = specs[n]
        if sp.kind == "sensible_body":
            tf = t_map[n]
            du = Box.exact(sp.capacity) * (tf - sp.t0)
            active_bcs[n] = {
                "role": "sensible_body",
                "constraint": "coupled_lumped_transient_ode",
                "initialTemperatureK": str(sp.t0),
                "finalTemperatureBoundsK": bounds(tf),
                "heatInputW": str(sp.heat_input),
            }
            ports_out[n] = {
                "kind": "sensible_body",
                "heatCapacityJPerK": str(sp.capacity),
                "initialTemperatureK": str(sp.t0),
                "heatInputW": str(sp.heat_input),
                "finalTemperatureBoundsK": bounds(tf),
                "bodyEnergyChangeBoundsJ": bounds(du),
                "energySignConvention": "into_body_positive",
            }
        elif sp.kind == "maintained":
            e_m = h_map[n]
            active_bcs[n] = {
                "role": "maintained",
                "constraint": "fixed_dirichlet",
                "temperatureK": str(sp.t0),
            }
            ports_out[n] = {
                "kind": "maintained",
                "temperatureK": str(sp.t0),
                "initialInflowFromNetworkBoundsW": bounds(q_init[n]),
                "integratedEnergyIntoReservoirBoundsJ": bounds(e_m),
                "energySignConvention": "into_maintained_reservoir_positive",
            }
        else:  # phase_substance
            md = modes[n]
            tf = t_map[n]
            hf = h_map[n]
            ms_box, ml_box = _phase_masses_from_state(sp, md, hf)
            dh = hf - sp.h0
            active_bcs[n] = {
                "role": "phase_substance",
                "constraint": "piecewise_linear_enthalpy_mode",
                "initialTemperatureK": str(sp.t0),
                "transitionTemperatureK": str(sp.t_tr),
                "finalMode": md,
                "finalTemperatureBoundsK": bounds(tf),
                "heatInputW": str(sp.heat_input),
            }
            ports_out[n] = {
                "kind": "phase_substance",
                "transitionTemperatureK": str(sp.t_tr),
                "specificLatentHeatJPerKg": str(sp.latent),
                "solidSpecificHeatJPerKgK": str(sp.c_s),
                "liquidSpecificHeatJPerKgK": str(sp.c_l),
                "initialTemperatureK": str(sp.t0),
                "initialSolidKg": str(sp.solid0),
                "initialLiquidKg": str(sp.liquid0),
                "totalMassKg": str(sp.total_mass),
                "heatInputW": str(sp.heat_input),
                "initialEnthalpyRelativeToPureSolidAtTransitionJ": str(sp.h0),
                "finalMode": md,
                "finalTemperatureBoundsK": bounds(tf),
                "finalEnthalpyRelativeToPureSolidAtTransitionBoundsJ": bounds(hf),
                "enthalpyChangeBoundsJ": bounds(dh),
                "remainingSolidBoundsKg": bounds(ms_box),
                "remainingLiquidBoundsKg": bounds(ml_box),
                "energySignConvention": "into_substance_positive",
            }
    return active_bcs, ports_out


def solve_enthalpy_continuation(
    law: Any,
    ports: dict[str, Any],
    duration_s: str,
    *,
    initial_steps: int = DEFAULT_INITIAL_STEPS,
    max_events: int = DEFAULT_MAX_EVENTS,
    max_prune_refinements: int = DEFAULT_MAX_PRUNE_REFINEMENTS,
    max_bisect_refinements: int = DEFAULT_MAX_BISECT_REFINEMENTS,
) -> dict[str, Any]:
    """Solve coupled multi-body / multi-phase linear enthalpy-mode continuation over a validated law."""
    _validate_positive_int(initial_steps, "initial_steps", upper=MAX_INITIAL_STEPS)
    _validate_positive_int(max_events, "max_events")
    _validate_positive_int(max_prune_refinements, "max_prune_refinements")
    _validate_positive_int(max_bisect_refinements, "max_bisect_refinements")

    resolved_law, provenance = validate_terminal_law(law)
    engine_law = resolved_law.to_engine_law()
    terminals = list(engine_law["terminals"])
    specs, body_ports, phase_ports, maintained_ports = _parse_ports(terminals, ports)
    duration = decimal_input(duration_s, "duration")
    w_net = _symmetric_conductances(terminals, engine_law)
    is_closed = len(maintained_ports) == 0
    total_power = sum((specs[n].heat_input for n in terminals if specs[n].kind != "maintained"), Fraction(0))

    # Compute exact initial temperatures, enthalpies, and initial net fluxes Q_init.
    t_cur: dict[str, Box] = {}
    h_cur: dict[str, Box] = {}
    modes: dict[str, str] = {}
    for n in terminals:
        sp = specs[n]
        t_cur[n] = Box.exact(sp.t0)
        if sp.kind == "maintained":
            modes[n] = "maintained"
            h_cur[n] = ZERO
        elif sp.kind == "sensible_body":
            modes[n] = "body"
            h_cur[n] = ZERO
        else:
            h_cur[n] = Box.exact(sp.h0)
            if sp.t0 < sp.t_tr:
                modes[n] = "solid"
            elif sp.t0 > sp.t_tr:
                modes[n] = "liquid"
            else:
                modes[n] = "plateau"

    q_init: dict[str, Box] = {}
    for n in terminals:
        q = Box.exact(specs[n].heat_input) if specs[n].kind != "maintained" else ZERO
        for other in terminals:
            if other == n:
                continue
            q = q + Box.bounds(*w_net[(n, other)]) * (specs[other].t0 - specs[n].t0)
        q_init[n] = q

    source_ref_temps = (
        {t: str(resolved_law.reference_temperatures_k[t]) for t in terminals}
        if resolved_law.reference_temperatures_k is not None
        else None
    )
    source_identity = (
        {k: provenance[k] for k in SOURCE_HASH_KEYS}
        if all(k in provenance for k in SOURCE_HASH_KEYS)
        else {
            "derivedLawSchema": provenance["derivedLawSchema"],
            "derivedLawSha256": provenance["derivedLawSha256"],
            "derivedLawLineage": provenance["derivedLawLineage"],
        }
    )

    events_out: list[dict[str, Any]] = []
    total_prunes = 0
    total_bisects = 0

    def _finish(
        status: str,
        termination_reason: str,
        stop_reason: str | None,
        mod_lo: Fraction,
        mod_hi: Fraction,
        final_t: dict[str, Box],
        final_h: dict[str, Box],
        final_modes: dict[str, str],
        *,
        unresolved_candidates: list[str] | None = None,
    ) -> dict[str, Any]:
        # Physical absolute temperature check (only flag if provably negative Kelvin).
        for n in terminals:
            if final_t[n].span()[1] < 0:
                raise ValueError(f"negative absolute temperature reached at port {n!r}")
        residual = _global_conservation_residual(
            terminals, specs, final_t, final_h, mod_lo, mod_hi, total_power
        )
        if not residual.contains_zero():
            raise ValueError(f"global energy conservation check failed: residual={bounds(residual)}")

        active_bcs, ports_out = _format_port_outputs(
            terminals, specs, final_modes, final_t, final_h, q_init
        )
        max_t_width = max((final_t[n].span()[1] - final_t[n].span()[0]) for n in terminals)
        return {
            "schema": ENTHALPY_CONTINUATION_SCHEMA,
            "evidence": {
                "category": EVIDENCE_CATEGORY,
                "sourceIdentity": source_identity,
                **{k: False for k in OFFLINE_FLAG_KEYS},
            },
            "network": {
                "terminals": terminals,
                "portKinds": {t: specs[t].kind for t in terminals},
                "sourceLawReferenceTemperaturesK": source_ref_temps,
                "activeBoundaryConditions": active_bcs,
            },
            "status": status,
            "requestedDurationS": str(duration),
            "modeledDurationBoundsS": [str(mod_lo), str(mod_hi)],
            "postExhaustionModeled": True,
            "events": events_out,
            "ports": ports_out,
            "energyConservationResidualBoundsJ": bounds(residual),
            "solverMetadata": {
                "terminationReason": termination_reason,
                "stopReason": stop_reason,
                "eventsCommitted": len(events_out),
                "pruneRefinementsUsed": total_prunes,
                "bisectRefinementsUsed": total_bisects,
                "modeledDurationWidthS": str(mod_hi - mod_lo),
                "maxFinalTemperatureWidthK": str(max_t_width),
                "unresolvedCandidatePorts": unresolved_candidates or [],
            },
            **provenance,
        }

    # Trivial zero-duration or exact global thermal equilibrium (all T equal & all P == 0).
    all_temps_equal = len({specs[n].t0 for n in terminals}) == 1
    all_powers_zero = all(specs[n].heat_input == 0 for n in terminals)
    if duration == 0 or (all_temps_equal and all_powers_zero):
        return _finish("complete", "resolved", None, duration, duration, t_cur, h_cur, modes)

    # Resolve pure-phase boundary starts at t = 0 (T0 == T_tr with solid0 == 0 or liquid0 == 0).
    unresolved_start: list[str] = []
    for n in phase_ports:
        sp = specs[n]
        if sp.t0 != sp.t_tr:
            continue
        if sp.solid0 > 0 and sp.liquid0 > 0:
            continue
        q0_lo, q0_hi = q_init[n].span()
        if sp.liquid0 == 0:
            # Pure solid at T_tr (H == 0)
            if q0_lo > 0:
                modes[n] = "plateau"
            elif q0_hi < 0:
                modes[n] = "solid"
            else:
                unresolved_start.append(n)
        else:
            # Pure liquid at T_tr (H == M*L)
            if q0_lo > 0:
                modes[n] = "liquid"
            elif q0_hi < 0:
                modes[n] = "plateau"
            else:
                unresolved_start.append(n)

    if unresolved_start:
        return _finish(
            "mode_sequence_uncertain",
            "mode_sequence_uncertain",
            "unresolved_initial_boundary_departure",
            Fraction(0),
            Fraction(0),
            t_cur,
            h_cur,
            modes,
            unresolved_candidates=unresolved_start,
        )

    t_lo = Fraction(0)
    t_hi = Fraction(0)

    for _stage in range(max_events + 1):
        evo = _ModeEvolution(terminals, specs, modes, t_cur, h_cur, w_net)
        rem_hi = duration - t_lo
        rem_lo = max(Fraction(0), duration - t_hi)

        # Verify strict boundary departure on restart for any phase node sitting at its mode boundary.
        t0_s, h0_s, q0_s = evo.state_at(Fraction(0))
        bad_depart: list[str] = []
        for n in phase_ports:
            sp = specs[n]
            md = modes[n]
            qlo, qhi = q0_s[n].span()
            if md == "plateau":
                if h_cur[n].span()[0] == 0 and qlo <= 0:
                    bad_depart.append(n)
                elif h_cur[n].span()[1] == sp.e_latent and qhi >= 0:
                    bad_depart.append(n)
            elif md == "solid":
                if t_cur[n].span()[1] >= sp.t_tr and qhi >= 0:
                    bad_depart.append(n)
            elif md == "liquid":
                if t_cur[n].span()[0] <= sp.t_tr and qlo <= 0:
                    bad_depart.append(n)
        if bad_depart:
            return _finish(
                "mode_sequence_uncertain",
                "mode_sequence_uncertain",
                "unresolved_boundary_departure",
                t_lo,
                t_hi,
                t_cur,
                h_cur,
                modes,
                unresolved_candidates=bad_depart,
            )

        if not phase_ports or rem_hi == 0:
            tf, hf, _ = evo.subinterval(rem_lo, rem_hi)
            if is_closed:
                tf, hf = _project_closed_ledger(terminals, specs, modes, tf, hf, duration, duration, total_power, set())
            return _finish("complete", "resolved", None, duration, duration, tf, hf, modes)

        # Uniform initial grid over [0, rem_hi].
        grid = [rem_hi * k / initial_steps for k in range(initial_steps + 1)]
        first_unsafe: int | None = None
        for k in range(initial_steps):
            ts, hs, qs = evo.subinterval(grid[k], grid[k + 1])
            if not all(
                _node_event_check(
                    specs[n],
                    modes[n],
                    ts[n],
                    hs[n],
                    qs[n],
                    t_init_box=t_cur[n],
                    h_init_box=h_cur[n],
                    at_start=(grid[k] == 0),
                )[0]
                for n in phase_ports
            ):
                first_unsafe = k
                break

        if first_unsafe is None:
            tf, hf, _ = evo.subinterval(rem_lo, rem_hi)
            tf, hf = _clip_state_to_modes(terminals, specs, modes, tf, hf)
            if is_closed:
                tf, hf = _project_closed_ledger(terminals, specs, modes, tf, hf, duration, duration, total_power, set())
            return _finish("complete", "resolved", None, duration, duration, tf, hf, modes)

        # Scan grid for earliest certified crossing point cert_hi.
        cert_hi: Fraction | None = None
        stop_idx = initial_steps
        for k in range(first_unsafe + 1, initial_steps + 1):
            tk, hk, qk = evo.state_at(grid[k])
            if any(
                _node_event_check(
                    specs[n],
                    modes[n],
                    tk[n],
                    hk[n],
                    qk[n],
                    t_init_box=t_cur[n],
                    h_init_box=h_cur[n],
                    at_start=False,
                )[1]
                is not None
                for n in phase_ports
            ):
                cert_hi = grid[k]
                stop_idx = k
                break

        intervals: list[tuple[Fraction, Fraction]] = []
        for k in range(first_unsafe, stop_idx):
            ts, hs, qs = evo.subinterval(grid[k], grid[k + 1])
            if not all(
                _node_event_check(
                    specs[n],
                    modes[n],
                    ts[n],
                    hs[n],
                    qs[n],
                    t_init_box=t_cur[n],
                    h_init_box=h_cur[n],
                    at_start=(grid[k] == 0),
                )[0]
                for n in phase_ports
            ):
                intervals.append((grid[k], grid[k + 1]))

        bisect_tol = max(Fraction(1, 10**9), rem_hi / (10**9))
        sep_tol = max(Fraction(1, 10**11), rem_hi / (10**11))
        uncertain_tol = max(Fraction(1, 10**6), rem_hi / (10**6))
        prune_used = 0
        bisect_used = 0
        budget_exhausted = False

        # Phase 1: left-to-right pruning of earlier safe/near-miss cells.
        while intervals:
            if cert_hi is not None and len(intervals) == 1 and intervals[0][1] == cert_hi:
                break
            a, b = intervals[0]
            if cert_hi is None and b - a <= uncertain_tol:
                break
            if prune_used >= max_prune_refinements:
                budget_exhausted = True
                break
            prune_used += 1
            total_prunes += 1
            intervals.pop(0)
            mid = (a + b) / 2
            tm, hm, qm = evo.state_at(mid)
            if any(
                _node_event_check(
                    specs[n],
                    modes[n],
                    tm[n],
                    hm[n],
                    qm[n],
                    t_init_box=t_cur[n],
                    h_init_box=h_cur[n],
                    at_start=False,
                )[1]
                is not None
                for n in phase_ports
            ):
                cert_hi = mid
                intervals = [(lo, min(hi, mid)) for lo, hi in intervals if lo < mid]
                tl, hl, ql = evo.subinterval(a, mid)
                if not all(
                    _node_event_check(
                        specs[n],
                        modes[n],
                        tl[n],
                        hl[n],
                        ql[n],
                        t_init_box=t_cur[n],
                        h_init_box=h_cur[n],
                        at_start=(a == 0),
                    )[0]
                    for n in phase_ports
                ):
                    intervals.insert(0, (a, mid))
                continue

            new_front: list[tuple[Fraction, Fraction]] = []
            tl, hl, ql = evo.subinterval(a, mid)
            if not all(
                _node_event_check(
                    specs[n],
                    modes[n],
                    tl[n],
                    hl[n],
                    ql[n],
                    t_init_box=t_cur[n],
                    h_init_box=h_cur[n],
                    at_start=(a == 0),
                )[0]
                for n in phase_ports
            ):
                new_front.append((a, mid))
            tr_m, hr_m, qr_m = evo.subinterval(mid, b)
            if not all(
                _node_event_check(
                    specs[n],
                    modes[n],
                    tr_m[n],
                    hr_m[n],
                    qr_m[n],
                    t_init_box=t_cur[n],
                    h_init_box=h_cur[n],
                    at_start=(mid == 0),
                )[0]
                for n in phase_ports
            ):
                new_front.append((mid, b))
            intervals = new_front + intervals

        def _collect_candidates(cur_intervals: list[tuple[Fraction, Fraction]], cur_cert_hi: Fraction) -> dict[str, set[str]]:
            cands_map: dict[str, set[str]] = {}
            tend, hend, qend = evo.state_at(cur_cert_hi)
            for n in phase_ports:
                _, _, h_set = _node_event_check(
                    specs[n],
                    modes[n],
                    tend[n],
                    hend[n],
                    qend[n],
                    t_init_box=t_cur[n],
                    h_init_box=h_cur[n],
                    at_start=False,
                )
                for ia, ib in cur_intervals:
                    ts_c, hs_c, qs_c = evo.subinterval(ia, ib)
                    _, _, h2 = _node_event_check(
                        specs[n],
                        modes[n],
                        ts_c[n],
                        hs_c[n],
                        qs_c[n],
                        t_init_box=t_cur[n],
                        h_init_box=h_cur[n],
                        at_start=(ia == 0),
                    )
                    h_set |= h2
                if h_set:
                    cands_map[n] = h_set
            return cands_map

        # Phase 2: bisect certified event bracket (continuing to sep_tol if needed to separate non-symmetric ties).
        while cert_hi is not None and intervals:
            cur_width = cert_hi - intervals[0][0]
            if cur_width <= bisect_tol:
                cands_now = _collect_candidates(intervals, cert_hi)
                if len(cands_now) <= 1 or cur_width <= sep_tol:
                    break
                if (
                    _can_prove_simultaneous_symmetry(
                        list(cands_now.keys()), cands_now, specs, modes, t_cur, h_cur, terminals, w_net
                    )
                    is not None
                ):
                    break
            if bisect_used >= max_bisect_refinements:
                budget_exhausted = True
                break
            if len(intervals) > 1 and intervals[-1][1] == cert_hi and intervals[-1][1] - intervals[-1][0] > sep_tol:
                idx = len(intervals) - 1
            else:
                idx = 0
            a, b = intervals.pop(idx)
            if b - a <= sep_tol:
                intervals.insert(idx, (a, b))
                break
            bisect_used += 1
            total_bisects += 1
            mid = (a + b) / 2
            tm, hm, qm = evo.state_at(mid)
            if any(
                _node_event_check(
                    specs[n],
                    modes[n],
                    tm[n],
                    hm[n],
                    qm[n],
                    t_init_box=t_cur[n],
                    h_init_box=h_cur[n],
                    at_start=False,
                )[1]
                is not None
                for n in phase_ports
            ):
                cert_hi = mid
                intervals = [(lo, min(hi, mid)) for lo, hi in intervals if lo < mid]
                tl, hl, ql = evo.subinterval(a, mid)
                if not all(
                    _node_event_check(
                        specs[n],
                        modes[n],
                        tl[n],
                        hl[n],
                        ql[n],
                        t_init_box=t_cur[n],
                        h_init_box=h_cur[n],
                        at_start=(a == 0),
                    )[0]
                    for n in phase_ports
                ):
                    intervals.insert(min(idx, len(intervals)), (a, mid))
                continue

            new_cells: list[tuple[Fraction, Fraction]] = []
            tl, hl, ql = evo.subinterval(a, mid)
            if not all(
                _node_event_check(
                    specs[n],
                    modes[n],
                    tl[n],
                    hl[n],
                    ql[n],
                    t_init_box=t_cur[n],
                    h_init_box=h_cur[n],
                    at_start=(a == 0),
                )[0]
                for n in phase_ports
            ):
                new_cells.append((a, mid))
            tr_m, hr_m, qr_m = evo.subinterval(mid, b)
            if not all(
                _node_event_check(
                    specs[n],
                    modes[n],
                    tr_m[n],
                    hr_m[n],
                    qr_m[n],
                    t_init_box=t_cur[n],
                    h_init_box=h_cur[n],
                    at_start=(mid == 0),
                )[0]
                for n in phase_ports
            ):
                new_cells.append((mid, b))
            intervals[idx:idx] = new_cells

        # All unsafe cells pruned away -> no event on [0, rem_hi]!
        if not intervals and cert_hi is None:
            tf, hf, _ = evo.subinterval(rem_lo, rem_hi)
            tf, hf = _clip_state_to_modes(terminals, specs, modes, tf, hf)
            if is_closed:
                tf, hf = _project_closed_ledger(terminals, specs, modes, tf, hf, duration, duration, total_power, set())
            return _finish("complete", "resolved", None, duration, duration, tf, hf, modes)

        safe_hi = intervals[0][0] if intervals else cert_hi
        assert safe_hi is not None

        # Helper to build certified state hull over unsafe cells + an optional end point/window.
        def _hull_over(extra_states: list[tuple[dict[str, Box], dict[str, Box]]]) -> tuple[dict[str, Box], dict[str, Box]]:
            t_list: list[dict[str, Box]] = []
            h_list: list[dict[str, Box]] = []
            for ia, ib in intervals:
                ts_u, hs_u, _ = evo.subinterval(ia, ib)
                t_list.append(ts_u)
                h_list.append(hs_u)
            for et, eh in extra_states:
                t_list.append(et)
                h_list.append(eh)
            t_u = {n: _box_union([d[n] for d in t_list]) for n in terminals}
            h_u = {n: _box_union([d[n] for d in h_list]) for n in terminals}
            return _clip_state_to_modes(terminals, specs, modes, t_u, h_u)

        # Unresolved event existence or horizon ordering (cert_hi is None or cert_hi > rem_lo).
        if cert_hi is None or cert_hi > rem_lo:
            t_hor, h_hor, _ = evo.subinterval(rem_lo, rem_hi)
            extras = [(t_hor, h_hor)]
            if cert_hi is not None:
                tc_e, hc_e, _ = evo.state_at(cert_hi)
                extras.append((tc_e, hc_e))
            t_stop, h_stop = _hull_over(extras)
            cands_unc: list[str] = []
            for n in phase_ports:
                hit = False
                for ia, ib in intervals:
                    ts_u, hs_u, qs_u = evo.subinterval(ia, ib)
                    if not _node_event_check(
                        specs[n], modes[n], ts_u[n], hs_u[n], qs_u[n],
                        t_init_box=t_cur[n], h_init_box=h_cur[n], at_start=(ia == 0),
                    )[0]:
                        hit = True
                        break
                if not hit and cert_hi is not None:
                    tc_e, hc_e, qc_e = evo.state_at(cert_hi)
                    if not _node_event_check(
                        specs[n], modes[n], tc_e[n], hc_e[n], qc_e[n],
                        t_init_box=t_cur[n], h_init_box=h_cur[n], at_start=False,
                    )[0]:
                        hit = True
                if hit:
                    cands_unc.append(n)
            term = "refinement_budget" if budget_exhausted else "mode_sequence_uncertain"
            reason = "refinement_budget" if budget_exhausted else "event_existence_or_horizon_unresolved"
            return _finish(
                "mode_sequence_uncertain",
                term,
                reason,
                min(duration, t_lo + safe_hi),
                duration,
                t_stop,
                h_stop,
                modes,
                unresolved_candidates=cands_unc,
            )

        # Event IS certified before rem_lo in union(intervals) U {cert_hi}.
        cand_targets = _collect_candidates(intervals, cert_hi)
        cand_nodes = list(cand_targets.keys())
        tc_e, hc_e, _ = evo.state_at(cert_hi)
        t_ev, h_ev = _hull_over([(tc_e, hc_e)])

        # Check event count budget BEFORE committing another transition.
        if len(events_out) >= max_events:
            return _finish(
                "mode_sequence_uncertain",
                "refinement_budget",
                "max_events_budget_reached",
                t_lo + safe_hi,
                min(duration, t_hi + cert_hi),
                t_ev,
                h_ev,
                modes,
                unresolved_candidates=cand_nodes,
            )

        ev_group: list[tuple[str, str]] = []
        symmetry_proven = False
        if len(cand_nodes) == 1:
            only = cand_nodes[0]
            if len(cand_targets[only]) != 1:
                return _finish(
                    "mode_sequence_uncertain",
                    "mode_sequence_uncertain",
                    "ambiguous_target_mode",
                    t_lo + safe_hi,
                    min(duration, t_hi + cert_hi),
                    t_ev,
                    h_ev,
                    modes,
                    unresolved_candidates=cand_nodes,
                )
            ev_group = [(only, next(iter(cand_targets[only])))]
        else:
            sym_target = _can_prove_simultaneous_symmetry(
                cand_nodes, cand_targets, specs, modes, t_cur, h_cur, terminals, w_net
            )
            if sym_target is None:
                term = "refinement_budget" if budget_exhausted else "mode_sequence_uncertain"
                return _finish(
                    "mode_sequence_uncertain",
                    term,
                    "overlapping_event_brackets",
                    t_lo + safe_hi,
                    min(duration, t_hi + cert_hi),
                    t_ev,
                    h_ev,
                    modes,
                    unresolved_candidates=cand_nodes,
                )
            symmetry_proven = True
            ev_group = [(p, sym_target) for p in cand_nodes]

        # Commit certified event(s): snap crossing node(s) to exact threshold and advance elapsed time.
        new_t_lo = t_lo + safe_hi
        new_t_hi = min(duration, t_hi + cert_hi)
        old_modes = dict(modes)
        snapped: set[str] = set()
        for ev_node, ev_target in ev_group:
            sp_ev = specs[ev_node]
            t_ev[ev_node] = Box.exact(sp_ev.t_tr)
            if ev_target == "plateau":
                h_ev[ev_node] = ZERO if old_modes[ev_node] == "solid" else Box.exact(sp_ev.e_latent)
            elif ev_target == "solid":
                h_ev[ev_node] = ZERO
            else:  # liquid
                h_ev[ev_node] = Box.exact(sp_ev.e_latent)
            modes[ev_node] = ev_target
            snapped.add(ev_node)

        if is_closed:
            t_ev, h_ev = _project_closed_ledger(
                terminals, specs, modes, t_ev, h_ev, new_t_lo, new_t_hi, total_power, snapped
            )

        ev_residual = _global_conservation_residual(
            terminals, specs, t_ev, h_ev, new_t_lo, new_t_hi, total_power
        )
        if not ev_residual.contains_zero():
            raise ValueError(f"event conservation check failed: residual={bounds(ev_residual)}")

        events_out.append({
            "index": len(events_out),
            "ports": [p for p, _ in ev_group],
            "transitions": {p: {"from": old_modes[p], "to": tgt} for p, tgt in ev_group},
            "simultaneousSymmetryProven": symmetry_proven,
            "timeBoundsS": [str(new_t_lo), str(new_t_hi)],
            "localBracketWidthS": str(cert_hi - safe_hi),
            "temperaturesBoundsK": {n: bounds(t_ev[n]) for n in terminals},
            "enthalpiesBoundsJ": {
                n: bounds(h_ev[n]) for n in terminals if specs[n].kind == "phase_substance"
            },
            "energyConservationResidualBoundsJ": bounds(ev_residual),
        })

        t_lo = new_t_lo
        t_hi = new_t_hi
        t_cur = t_ev
        h_cur = h_ev

    return _finish(
        "mode_sequence_uncertain",
        "refinement_budget",
        "max_events_budget_reached",
        t_lo,
        t_hi,
        t_cur,
        h_cur,
        modes,
    )
