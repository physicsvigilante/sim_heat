"""Steady radial conduction through concentric spherical or cylindrical layers."""
import argparse
from fractions import Fraction
import json

from qualification.h1_n4.static_physical import pi_rational_enclosure
from qualification.h1_n13.conduction import Box
from tools.join_thermal_networks import bounds
from tools.loaded_thermal_ports import port_equivalent
from tools.radiating_surface import decimal_input
from tools.terminal_response import investigate as terminal_response


def log_mantissa_bounds(x):
    """Bound log(x) on [1,2] by summing the positive atanh series."""
    z = (x-1)/(x+1)
    z2 = z*z
    power = z
    partial = Fraction(0)
    for n in range(64):
        partial += 2*power/(2*n+1)
        power *= z2
    return Box.bounds(partial, partial+2*power/(129*(1-z2)))


def radial_log(ratio):
    # Choose m and n with ratio = m * 2^n and 1 <= m < 2.
    n = ratio.numerator.bit_length()-ratio.denominator.bit_length()
    if ratio < 2**n:
        n -= 1
    return log_mantissa_bounds(ratio/(2**n)) + n*log_mantissa_bounds(Fraction(2))


def investigate(inner_inputs, outer_inputs, inner_port, outer_port, inner_radius_m, layers, cylinder_length_m=None):
    radius = decimal_input(inner_radius_m, "inner radius")
    if radius <= 0 or not isinstance(layers, (tuple, list)) or not 1 <= len(layers) <= 32:
        raise ValueError("positive inner radius and one to 32 layers required")
    radii = [radius]
    material = []
    pi = Box.bounds(*pi_rational_enclosure())
    length = None
    if cylinder_length_m is not None:
        length = decimal_input(cylinder_length_m, "cylinder length")
        if length <= 0:
            raise ValueError("cylinder length must be positive")
    accumulated = Box.exact(0)
    radial_resistances = [accumulated]
    for pair in layers:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("each layer needs an outer radius and conductivity")
        outer = decimal_input(pair[0], "outer radius")
        k = decimal_input(pair[1], "conductivity")
        if outer <= radius or k <= 0:
            raise ValueError("layer radii must increase and conductivity must be positive")
        if length is None:
            resistance = Box.exact((1/radius-1/outer)/k)/(4*pi)
        else:
            resistance = radial_log(outer/radius)*(1/(k*length))/(2*pi)
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
        if length is None:
            flux = rate*(1/r**2)/(4*pi)
        else:
            flux = rate*(1/(2*length*r))/pi
        surfaces.append({"radiusM": str(r), "temperatureBoundsK": bounds(temperature),
                         "outwardHeatFluxBoundsWPerM2": bounds(flux)})
    sources = {side: {key: law[key] for key in ("modelSha256", "studySha256", "factsSha256")}
               for side, law in (("inner", inner), ("outer", outer))}
    result = {"schema": "sim_heat.offline_spherical_conduction/1", "sources": sources,
            "innerPort": inner_port, "outerPort": outer_port, "layers": material,
            "surfaces": surfaces, "shellResistanceBoundsKPerW": bounds(accumulated),
            "outwardHeatRateBoundsW": bounds(rate), "nativeExecuted": False,
            "nativeQualified": False, "independentlyCertifiedReference": False,
            "runnerConsumable": False}

    if length is not None:
        result.update(schema="sim_heat.offline_cylindrical_conduction/1", cylinderLengthM=str(length))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256")
    for side in ("inner", "outer"):
        for field in (*fields, "port"):
            parser.add_argument("--"+side+"-"+field, required=True)
    parser.add_argument("--inner-radius-m", required=True)
    parser.add_argument("--layer", nargs=2, metavar=("OUTER_RADIUS_M","K_W_PER_M_K"),
                        action="append", required=True)
    parser.add_argument("--cylinder-length-m", help="use radial cylindrical layers with insulated ends")
    args = vars(parser.parse_args())
    def inputs(side):
        return tuple(args[side+"_"+field.replace("-", "_")] for field in fields)
    print(json.dumps(investigate(inputs("inner"), inputs("outer"), args["inner_port"], args["outer_port"],
                                 args["inner_radius_m"], args["layer"], args["cylinder_length_m"]), indent=2))
