"""simheat: composable exact-rational offline thermal network core, laws, and systems."""
from simheat.core import (
    ONE,
    SCALE,
    TAYLOR,
    ZERO,
    Box,
    Conduction,
    ExactBindings,
    apply,
    bounded_centre,
    ceil_fraction,
    dot,
    field_unit,
    identity,
    interval,
    pi_rational_enclosure,
    product,
    step_matrix,
    verified_barrier_enclosure,
)
from simheat.laws import (
    DERIVED_LAW_SCHEMA,
    JOINED_LAW_SCHEMA,
    PINNED_LAW_SCHEMA,
    DerivedLaw,
    ensure_derived_law,
    join_laws,
    validate_terminal_law,
)

_SYSTEM_EXPORTS = (
    "RESULT_ENVELOPE_SCHEMA",
    "THERMAL_SYSTEM_SCHEMA",
    "ThermalSystem",
    "describe_equations",
    "solve_system",
)

_ENTHALPY_EXPORTS = (
    "ENTHALPY_CONTINUATION_SCHEMA",
    "solve_enthalpy_continuation",
)

_STEFAN_EXPORTS = (
    "STEFAN_SCHEMA",
    "solve_stefan_from_law",
)

_ROD_GEN_EXPORTS = (
    "RodGenerationModel",
    "build_rod_generation_model",
)


def __getattr__(name: str):
    if name in _SYSTEM_EXPORTS:
        from simheat import system

        return getattr(system, name)
    if name in _ENTHALPY_EXPORTS:
        from simheat import enthalpy

        return getattr(enthalpy, name)
    if name in _STEFAN_EXPORTS:
        from simheat import stefan

        return getattr(stefan, name)
    if name in _ROD_GEN_EXPORTS:
        from simheat import rod_gen

        return getattr(rod_gen, name)
    raise AttributeError(f"module 'simheat' has no attribute {name!r}")


__all__ = [
    "Box",
    "Conduction",
    "DERIVED_LAW_SCHEMA",
    "DerivedLaw",
    "ENTHALPY_CONTINUATION_SCHEMA",
    "ExactBindings",
    "JOINED_LAW_SCHEMA",
    "ONE",
    "PINNED_LAW_SCHEMA",
    "RESULT_ENVELOPE_SCHEMA",
    "RodGenerationModel",
    "SCALE",
    "STEFAN_SCHEMA",
    "TAYLOR",
    "THERMAL_SYSTEM_SCHEMA",
    "ThermalSystem",
    "ZERO",
    "apply",
    "bounded_centre",
    "build_rod_generation_model",
    "ceil_fraction",
    "describe_equations",
    "dot",
    "ensure_derived_law",
    "field_unit",
    "identity",
    "interval",
    "join_laws",
    "pi_rational_enclosure",
    "product",
    "solve_enthalpy_continuation",
    "solve_stefan_from_law",
    "solve_system",
    "step_matrix",
    "validate_terminal_law",
    "verified_barrier_enclosure",
]
