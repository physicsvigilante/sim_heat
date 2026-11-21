"""Steady radial conduction through concentric spherical layers between thermal ports."""
import argparse
import json

from qualification.h1_n4.static_physical import pi_rational_enclosure
from qualification.h1_n13.conduction import Box
from tools.join_thermal_networks import bounds
from tools.loaded_thermal_ports import port_equivalent
from tools.radiating_surface import decimal_input
from tools.terminal_response import investigate as terminal_response


def investigate(inner_inputs, outer_inputs, inner_port, outer_port, inner_radius_m, layers):
    radius = decimal_input(inner_radius_m, "inner radius")
    if radius <= 0 or not isinstance(layers, (tuple, list)) or not 1 <= len(layers) <= 32:
        raise ValueError("positive inner radius and one to 32 layers required")
    radii = [radius]
    material = []
    # Divide a signed outward heat rate by 4*pi*r^2 for its local flux.
    four_pi = 4*Box.bounds(*pi_rational_enclosure())
    accumulated = Box.exact(0)
    radial_resistances = [accumulated]
    for pair in layers:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("each layer needs an outer radius and conductivity")
        outer = decimal_input(pair[0], "outer radius")
        k = decimal_input(pair[1], "conductivity")
        if outer <= radius or k <= 0:
            raise ValueError("layer radii must increase and conductivity must be positive")
        resistance = Box.exact((1/radius-1/outer)/k)/four_pi
        accumulated += resistance
        material.append({"outerRadiusM": str(outer), "conductivityWPerMK": str(k),
                         "resistanceBoundsKPerW": bounds(resistance)})
        radii.append(outer)
        radial_resistances.append(accumulated)
        radius = outer

    inner, outer = (terminal_response(*args) for args in (inner_inputs, outer_inputs))
    ti, ri = port_equivalent(inner, inner_port)
    to, ro = port_equivalent(outer, outer_port)
    rate = (ti-to)/(ri+accumulated+ro)
    surfaces = []
    for r, resistance in zip(radii, radial_resistances, strict=True):
        temperature = ti-rate*(ri+resistance)
        flux = rate*(1/r**2)/four_pi
        surfaces.append({"radiusM": str(r), "temperatureBoundsK": bounds(temperature),
                         "outwardHeatFluxBoundsWPerM2": bounds(flux)})
    sources = {side: {key: law[key] for key in ("modelSha256", "studySha256", "factsSha256")}
               for side, law in (("inner", inner), ("outer", outer))}
    return {"schema": "sim_heat.offline_spherical_conduction/1", "sources": sources,
            "innerPort": inner_port, "outerPort": outer_port, "layers": material,
            "surfaces": surfaces, "shellResistanceBoundsKPerW": bounds(accumulated),
            "outwardHeatRateBoundsW": bounds(rate), "nativeExecuted": False,
            "nativeQualified": False, "independentlyCertifiedReference": False,
            "runnerConsumable": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256")
    for side in ("inner", "outer"):
        for field in (*fields, "port"):
            parser.add_argument("--"+side+"-"+field, required=True)
    parser.add_argument("--inner-radius-m", required=True)
    parser.add_argument("--layer", nargs=2, metavar=("OUTER_RADIUS_M","K_W_PER_M_K"),
                        action="append", required=True)
    args = vars(parser.parse_args())
    def inputs(side):
        return tuple(args[side+"_"+field.replace("-", "_")] for field in fields)
    print(json.dumps(investigate(inputs("inner"), inputs("outer"), args["inner_port"], args["outer_port"],
                                 args["inner_radius_m"], args["layer"]), indent=2))
