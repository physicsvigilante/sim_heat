"""Neutral re-export of the exact-rational interval and conduction kernel.

Re-exports certified primitives from the frozen qualification modules without
moving, editing, or weakening any historical qualification files or pins.
"""
from qualification.h1_n4.static_physical import pi_rational_enclosure
from qualification.h1_n7.verified_junctions import (
    _enclosure_from_verified_barrier as verified_barrier_enclosure,
)
from qualification.h1_n11.rational_dynamic_proof import (
    SCALE,
    TAYLOR,
    Box,
    apply,
    ceil_fraction,
    dot,
    field_unit,
    identity,
    product,
)
from qualification.h1_n13.conduction import (
    ONE,
    ZERO,
    Conduction,
    ExactBindings,
    bounded_centre,
    interval,
    step_matrix,
)

__all__ = [
    "Box",
    "Conduction",
    "ExactBindings",
    "ONE",
    "SCALE",
    "TAYLOR",
    "ZERO",
    "apply",
    "bounded_centre",
    "ceil_fraction",
    "dot",
    "field_unit",
    "identity",
    "interval",
    "pi_rational_enclosure",
    "product",
    "step_matrix",
    "verified_barrier_enclosure",
]
