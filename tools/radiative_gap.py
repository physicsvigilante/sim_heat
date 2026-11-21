"""Steady radiative exchange between two diffuse gray plates on thermal networks."""
import argparse
from fractions import Fraction
from itertools import product
import json

from tools.radiating_surface import decimal_input, physical_port
from tools.terminal_response import investigate as terminal_response


def gap_rate(left, right, rl, rr, coefficient):
    # Zero flow gives open temperatures. At the direct-contact flow the
    # plate temperatures coincide. Both endpoints are physical in kelvin.
    lo, hi = sorted((Fraction(0), (left-right)/(rl+rr)))
    for _ in range(64):
        mid = (lo+hi)/2
        tl, tr = left-mid*rl, right+mid*rr
        residual = mid-coefficient*(tl**4-tr**4)
        if residual == 0:
            return mid, mid
        if residual < 0:
            lo = mid
        else:
            hi = mid
    return lo, hi


def investigate(left_inputs, right_inputs, left_port, right_port, area_m2,
                left_emissivity, right_emissivity, sigma):
    area = decimal_input(area_m2, "overlap area")
    el = decimal_input(left_emissivity, "left emissivity")
    er = decimal_input(right_emissivity, "right emissivity")
    constant = decimal_input(sigma, "Stefan-Boltzmann constant")
    if area <= 0 or constant <= 0 or max(el, er) > 1:
        raise ValueError("positive area and sigma and emissivities in [0,1] required")
    left, right = (terminal_response(*args) for args in (left_inputs, right_inputs))
    ol, rl = physical_port(left, left_port)
    ot, rr = physical_port(right, right_port)
    # Reciprocal gray-surface radiation resistance for equal areas and F12=1.
    coefficient = area*constant/(1/el+1/er-1) if el and er else Fraction(0)
    qlo = qhi = Fraction(0)
    if coefficient:
        brackets = [gap_rate(a,b,c,d,coefficient) for a,b,c,d in product(ol,ot,rl,rr)]
        qlo, qhi = min(x[0] for x in brackets), max(x[1] for x in brackets)
    ldrop = [q*r for q,r in product((qlo,qhi), rl)]
    rrise = [q*r for q,r in product((qlo,qhi), rr)]
    sources = {side: {k: law[k] for k in ("modelSha256", "studySha256", "factsSha256")}
               for side, law in (("left", left), ("right", right))}
    return {"schema": "sim_heat.offline_radiative_gap/1", "sources": sources,
            "leftPort": left_port, "rightPort": right_port,
            "gap": {"overlapAreaM2": str(area), "leftEmissivity": str(el),
                    "rightEmissivity": str(er), "sigmaWPerM2K4": str(constant)},
            "leftToRightHeatRateBoundsW": [str(qlo), str(qhi)],
            "leftPlateTemperatureBoundsK": [str(ol[0]-max(ldrop)),str(ol[1]-min(ldrop))],
            "rightPlateTemperatureBoundsK": [str(ot[0]+min(rrise)),str(ot[1]+max(rrise))],
            "nativeExecuted": False, "nativeQualified": False,
            "independentlyCertifiedReference": False, "runnerConsumable": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256")
    for side in ("left", "right"):
        for field in fields:
            parser.add_argument("--"+side+"-"+field, required=True)
    for field in ("left-port", "right-port", "area-m2", "left-emissivity", "right-emissivity", "sigma"):
        parser.add_argument("--"+field, required=True)
    args = vars(parser.parse_args())
    def inputs(side):
        return tuple(args[side+"_"+s.replace("-", "_")] for s in fields)
    print(json.dumps(investigate(inputs("left"), inputs("right"), args["left_port"], args["right_port"],
                                 args["area_m2"], args["left_emissivity"], args["right_emissivity"],
                                 args["sigma"]), indent=2))
