"""Size identical diffuse-gray radiation shields for a steady heat-leak limit."""
import argparse
from fractions import Fraction
from itertools import product
import json
from math import ceil

from tools.loaded_thermal_ports import link_conductance
from tools.radiating_surface import decimal_input, physical_port
from tools.terminal_response import investigate as terminal_response


def required_count(left, right, rl, rr, support_g, limit, area_sigma, faces):
    """Smallest count for these exact port parameters, or None if no finite count works."""
    if left < right:
        left, right, rl, rr = right, left, rr, rl
    if left - right <= limit*(rl + rr):
        return 0
    hot, cold = left - limit*rl, right + limit*rr
    available = limit - support_g*(hot - cold)
    if available < 0:
        return None
    el, er, front, back = faces
    if not el or not er:
        return 0
    # At the target current the conduction drops fix the plate temperatures.
    # The actual current is <= target exactly when the gap carries <= target
    # at those temperatures (the load-line residual increases with current).
    numerator = area_sigma*(hot**4 - cold**4)
    bare = 1/el + 1/er - 1
    if numerator <= available*bare:
        return 0
    if not front or not back:
        return 1
    if not available:
        return None
    increment = 1/front + 1/back - 1
    return ceil((numerator/available - bare)/increment)


def investigate(left_inputs, right_inputs, left_port, right_port, area_m2, left_emissivity,
                right_emissivity, sigma, shield_faces, max_heat_w, support_inputs=None):
    if not isinstance(shield_faces, (tuple, list)) or len(shield_faces) != 2:
        raise ValueError("one emissivity for each face of the repeated shield required")
    area = decimal_input(area_m2, "overlap area")
    constant = decimal_input(sigma, "Stefan-Boltzmann constant")
    limit = decimal_input(max_heat_w, "maximum heat leak")
    faces = [decimal_input(x, "emissivity") for x in (left_emissivity, right_emissivity, *shield_faces)]
    if not area or not constant or max(faces) > 1:
        raise ValueError("positive area and sigma and emissivities in [0,1] required")
    laws = {"left": terminal_response(*left_inputs), "right": terminal_response(*right_inputs)}
    ol, rl = physical_port(laws["left"], left_port)
    ot, rr = physical_port(laws["right"], right_port)
    bypass = (Fraction(0),)
    if support_inputs is not None:
        laws["support"] = terminal_response(*support_inputs)
        bypass = link_conductance(laws["support"]).span()
    counts = [required_count(a, b, c, d, g, limit, area*constant, faces)
              for a, b, c, d, g in product(ol, ot, rl, rr, bypass)]
    # A zero drive can also be inside overlapping open-temperature intervals.
    if max(ol[0], ot[0]) <= min(ol[1], ot[1]):
        counts.append(0)
    finite = [n for n in counts if n is not None]
    least = min(finite, default=None)
    greatest = max(finite) if len(finite) == len(counts) else None
    status = ("no_finite_count" if least is None else
              "resolved" if least == greatest else "bounded_by_port_uncertainty")
    return {
        "schema": "sim_heat.offline_shield_count_design/1", "status": status,
        "minimumRequiredCountBounds": [least, greatest], "guaranteedSufficientCount": greatest,
        "maximumHeatLeakW": str(limit), "overlapAreaM2": str(area), "sigmaWPerM2K4": str(constant),
        "leftEmissivity": str(faces[0]), "rightEmissivity": str(faces[1]),
        "repeatedShieldFaceEmissivities": list(map(str, faces[2:])),
        "leftPort": left_port, "rightPort": right_port,
        "sources": {side: {key: law[key] for key in ("studySha256", "factsSha256", "modelSha256")}
                    for side, law in laws.items()},
        "nativeExecuted": False, "nativeQualified": False,
        "independentlyCertifiedReference": False, "runnerConsumable": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for side in ("left", "right"):
        parser.add_argument("--" + side, nargs=4, required=True, metavar=("STUDY", "ROOT", "FACTS", "SHA256"))
    for field in ("left-port", "right-port", "area-m2", "left-emissivity", "right-emissivity", "sigma", "max-heat-w"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--shield", nargs=2, required=True, metavar=("LEFT", "RIGHT"))
    parser.add_argument("--support", nargs=4, metavar=("STUDY", "ROOT", "FACTS", "SHA256"))
    args = parser.parse_args()
    print(json.dumps(investigate(args.left, args.right, args.left_port, args.right_port, args.area_m2,
                                 args.left_emissivity, args.right_emissivity, args.sigma,
                                 args.shield, args.max_heat_w, args.support), indent=2))
