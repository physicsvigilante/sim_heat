"""Steady radiative exchange between two diffuse gray plates on thermal networks."""
import argparse
from fractions import Fraction
from itertools import product
from math import isqrt
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


def gap_coefficient(area_sigma, first, second):
    return area_sigma/(1/first+1/second-1) if first and second else Fraction(0)


def fourth_root_bounds(low, high):
    scale = 10**18
    lower = isqrt(isqrt(int(low*scale**4)))
    upper = isqrt(isqrt(int(high*scale**4)))
    if Fraction(upper, scale)**4 < high:
        upper += 1
    return [str(Fraction(lower, scale)), str(Fraction(upper, scale))]


def investigate(left_inputs, right_inputs, left_port, right_port, area_m2,
                left_emissivity, right_emissivity, sigma, shield_emissivities=None):
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
    if shield_emissivities is None:
        coefficient = gap_coefficient(area*constant, el, er)
    else:
        if not isinstance(shield_emissivities, (tuple, list)) or len(shield_emissivities) != 2:
            raise ValueError("supply both shield face emissivities")
        sl, sr = (decimal_input(e, "shield emissivity") for e in shield_emissivities)
        if max(sl,sr) > 1:
            raise ValueError("shield emissivities must be in [0,1]")
        kl = gap_coefficient(area*constant, el, sl)
        kr = gap_coefficient(area*constant, sr, er)
        coefficient = kl*kr/(kl+kr) if kl+kr else Fraction(0)
    qlo = qhi = Fraction(0)
    if coefficient:
        brackets = [gap_rate(a,b,c,d,coefficient) for a,b,c,d in product(ol,ot,rl,rr)]
        qlo, qhi = min(x[0] for x in brackets), max(x[1] for x in brackets)
    ldrop = [q*r for q,r in product((qlo,qhi), rl)]
    rrise = [q*r for q,r in product((qlo,qhi), rr)]
    sources = {side: {k: law[k] for k in ("modelSha256", "studySha256", "factsSha256")}
               for side, law in (("left", left), ("right", right))}
    result = {"schema": "sim_heat.offline_radiative_gap/1", "sources": sources,
            "leftPort": left_port, "rightPort": right_port,
            "gap": {"overlapAreaM2": str(area), "leftEmissivity": str(el),
                    "rightEmissivity": str(er), "sigmaWPerM2K4": str(constant)},
            "leftToRightHeatRateBoundsW": [str(qlo), str(qhi)],
            "leftPlateTemperatureBoundsK": [str(ol[0]-max(ldrop)),str(ol[1]-min(ldrop))],
            "rightPlateTemperatureBoundsK": [str(ot[0]+min(rrise)),str(ot[1]+max(rrise))],
            "nativeExecuted": False, "nativeQualified": False,
            "independentlyCertifiedReference": False, "runnerConsumable": False}

    if shield_emissivities is not None:
        result["schema"] = "sim_heat.offline_radiation_shield/1"
        result["gap"].update(shieldLeftEmissivity=str(sl), shieldRightEmissivity=str(sr))
        # At equilibrium Ts^4 is the coefficient-weighted mean of the two
        # plate fourth powers. Both may be clipped to the physical open-temperature hull.
        hull_low, hull_high = min(ol[0],ot[0]), max(ol[1],ot[1])
        def plate(key):
            lo, hi = map(Fraction, result[key])
            return max(hull_low,lo), min(hull_high,hi)
        if kl+kr:
            moments = [(kl*l**4+kr*r**4)/(kl+kr) for l,r in zip(
                plate("leftPlateTemperatureBoundsK"), plate("rightPlateTemperatureBoundsK"), strict=True)]
            result["shieldTemperatureBoundsK"] = fourth_root_bounds(*moments)
            result["shieldTemperatureStatus"] = "bounded"
        else:
            result["shieldTemperatureBoundsK"] = None
            result["shieldTemperatureStatus"] = "undetermined"
    return result



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256")
    for side in ("left", "right"):
        for field in fields:
            parser.add_argument("--"+side+"-"+field, required=True)
    for field in ("left-port", "right-port", "area-m2", "left-emissivity", "right-emissivity", "sigma"):
        parser.add_argument("--"+field, required=True)
    parser.add_argument('--shield-emissivities', nargs=2, metavar=('LEFT','RIGHT'))
    args = vars(parser.parse_args())
    def inputs(side):
        return tuple(args[side+"_"+s.replace("-", "_")] for s in fields)
    print(json.dumps(investigate(inputs("left"), inputs("right"), args["left_port"], args["right_port"],
                                 args["area_m2"], args["left_emissivity"], args["right_emissivity"],
                                 args["sigma"], args["shield_emissivities"]), indent=2))
