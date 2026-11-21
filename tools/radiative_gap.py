"""Steady radiative exchange between two diffuse gray plates on thermal networks."""
import argparse
from fractions import Fraction
from itertools import product
from math import isqrt
import json

from tools.loaded_thermal_ports import link_conductance
from tools.radiating_surface import decimal_input, physical_port
from tools.terminal_response import investigate as terminal_response


def gap_rate(left, right, rl, rr, coefficient, conductance=0):
    # Zero flow gives open temperatures. At the direct-contact flow the
    # plate temperatures coincide. Both endpoints are physical in kelvin.
    lo, hi = sorted((Fraction(0), (left-right)/(rl+rr)))
    for _ in range(64):
        mid = (lo+hi)/2
        tl, tr = left-mid*rl, right+mid*rr
        residual = mid-conductance*(tl-tr)-coefficient*(tl**4-tr**4)
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
                left_emissivity, right_emissivity, sigma, shield_emissivities=None, support_inputs=None, *, shield_stack=None):
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
    if shield_stack is not None and shield_emissivities is not None:
        raise ValueError("choose one shield specification")
    if shield_stack is not None and (not isinstance(shield_stack, (tuple, list)) or not shield_stack):
        raise ValueError("a shield stack requires at least one shield")
    pairs = ([shield_emissivities] if shield_emissivities is not None else shield_stack) or []
    shields = []
    gaps = []
    previous = el
    for faces in pairs:
        if not isinstance(faces, (tuple, list)) or len(faces) != 2:
            raise ValueError("supply both shield face emissivities")
        front, back = (decimal_input(e, "shield emissivity") for e in faces)
        if max(front, back) > 1:
            raise ValueError("shield emissivities must be in [0,1]")
        shields.append((front, back))
        gaps.append(gap_coefficient(area*constant, previous, front))
        previous = back
    gaps.append(gap_coefficient(area*constant, previous, er))
    coefficient = 1/sum(1/k for k in gaps) if all(gaps) else Fraction(0)
    qlo = qhi = Fraction(0)
    support_g = (Fraction(0),)
    if support_inputs is not None:
        support = terminal_response(*support_inputs)
        support_g = link_conductance(support).span()
    if coefficient or support_inputs is not None:
        brackets = [gap_rate(a,b,c,d,coefficient,g) for a,b,c,d,g in product(ol,ot,rl,rr,support_g)]
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

    hull_low, hull_high = min(ol[0],ot[0]), max(ol[1],ot[1])
    def plate(key):
        lo, hi = map(Fraction, result[key])
        return max(hull_low,lo), min(hull_high,hi)

    if shields:
        left_plate = plate("leftPlateTemperatureBoundsK")
        right_plate = plate("rightPlateTemperatureBoundsK")
        breaks = [i for i, k in enumerate(gaps) if not k]
        cumulative = Fraction(0)
        records = []
        for i, (front, back) in enumerate(shields):
            if not breaks:
                cumulative += 1/gaps[i]
                weight = coefficient*cumulative
                moments = [(1-weight)*l**4 + weight*r**4
                           for l, r in zip(left_plate, right_plate, strict=True)]
                bounds = fourth_root_bounds(*moments)
            elif i < breaks[0]:
                bounds = list(map(str, left_plate))
            elif i >= breaks[-1]:
                bounds = list(map(str, right_plate))
            else:
                bounds = None
            records.append({"leftEmissivity": str(front), "rightEmissivity": str(back),
                            "temperatureBoundsK": bounds,
                            "temperatureStatus": "undetermined" if bounds is None else "bounded"})
        if shield_stack is not None:
            result["schema"] = "sim_heat.offline_radiation_shield_stack/1"
            result["shieldsLeftToRight"] = records
        else:
            record, = records
            result["schema"] = "sim_heat.offline_radiation_shield/1"
            result["gap"].update(shieldLeftEmissivity=record["leftEmissivity"],
                                 shieldRightEmissivity=record["rightEmissivity"])
            result["shieldTemperatureBoundsK"] = record["temperatureBoundsK"]
            result["shieldTemperatureStatus"] = record["temperatureStatus"]
    if support_inputs is not None:
        result["schema"] = ("sim_heat.offline_supported_shield_stack/1" if shield_stack is not None
                            else "sim_heat.offline_supported_radiative_gap/1")
        sources["support"] = {k: support[k] for k in ("modelSha256", "studySha256", "factsSha256")}
        result["supportTerminalsLeftToRight"] = support["terminals"]
        ll, lh = plate("leftPlateTemperatureBoundsK")
        tl, th = plate("rightPlateTemperatureBoundsK")
        conduction = [g*d for g,d in product(support_g, (ll-th, lh-tl))]
        radiation = [coefficient*(ll**4-th**4), coefficient*(lh**4-tl**4)]
        # Tighten each pathway using conservation of the total through-rate.
        clo, chi = min(conduction), max(conduction)
        rlo, rhi = radiation
        result["supportHeatRateBoundsW"] = [str(max(clo,qlo-rhi)),str(min(chi,qhi-rlo))]
        result["radiativeHeatRateBoundsW"] = [str(max(rlo,qlo-chi)),str(min(rhi,qhi-clo))]
    return result



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256")
    for side in ("left", "right"):
        for field in fields:
            parser.add_argument("--"+side+"-"+field, required=True)
    for field in ("left-port", "right-port", "area-m2", "left-emissivity", "right-emissivity", "sigma"):
        parser.add_argument("--"+field, required=True)
    parser.add_argument('--shield', nargs=2, action='append', metavar=('LEFT','RIGHT'), help='repeat once per shield in left-to-right order')
    parser.add_argument('--shield-emissivities', nargs=2, metavar=('LEFT','RIGHT'))
    parser.add_argument("--support", nargs=4, metavar=("STUDY","ROOT","FACTS","SHA256"))
    args = vars(parser.parse_args())
    def inputs(side):
        return tuple(args[side+"_"+s.replace("-", "_")] for s in fields)
    print(json.dumps(investigate(inputs("left"), inputs("right"), args["left_port"], args["right_port"],
                                 args["area_m2"], args["left_emissivity"], args["right_emissivity"],
                                 args["sigma"], args["shield_emissivities"], args["support"], shield_stack=args["shield"]), indent=2))
