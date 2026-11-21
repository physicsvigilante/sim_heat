"""Steady heat current through a series of two-terminal rod networks and imperfect contacts."""
import argparse
from fractions import Fraction
import json
from math import isqrt

from tools.join_variable_conductors import Material
from tools.radiating_surface import decimal_input, radiative_properties
from tools.terminal_response import investigate as terminal_response


class SolidPotential(Material):
    def inverse(self, value, hot, upper):
        return temperature(self, value, hot, upper)


class RadiationPotential:
    def __init__(self, cold):
        self.cold = cold

    def potential(self, t):
        return t**4-self.cold**4

    def inverse(self, value, hot, upper):
        if value >= self.potential(hot):
            return hot
        scale = 1 << 96
        fourth = (value+self.cold**4)*scale**4
        ticks = isqrt(isqrt(fourth.numerator//fourth.denominator))
        return min(hot, max(self.cold, Fraction(ticks+int(upper), scale)))


def temperature(material, value, hot, upper):
    """Invert the integrated conductivity within the bath range, rounding outwards."""
    cold = material.origin
    if value <= 0:
        return cold
    if value >= material.potential(hot):
        return hot
    if not material.slope:
        return cold+value/material.factor
    # For either slope sign the physical root is 2v/(f + sqrt(f²+2av)).
    square = material.factor**2+2*material.slope*value
    scale = 1 << 96
    root = isqrt(square.numerator*scale**2//square.denominator)
    sqrt_bound = Fraction(root if upper else root+1, scale)
    result = cold+2*value/(material.factor+sqrt_bound)
    # Rounding the propagated temperatures bounds the size of later fractions.
    ticks = result*scale
    rounded = -(-ticks.numerator//ticks.denominator) if upper else ticks.numerator//ticks.denominator
    return max(cold, min(hot, Fraction(rounded, scale)))


def investigate(layers, contacts, left_k, right_k, *, radiation=None):
    left = decimal_input(left_k, "left bath temperature")
    right = decimal_input(right_k, "right bath temperature")
    exterior = None
    if radiation is not None:
        area, eps, sigma = radiative_properties(*radiation)
        coefficient = area*eps*sigma
        exterior = {"enclosureTemperatureK": str(right), "areaM2": str(area),
                    "emissivity": str(eps), "sigmaWPerM2K4": str(sigma)}
        if not coefficient:
            right = left
    cold, hot = sorted((left, right))
    if not layers or len(contacts) != len(layers)-1:
        raise ValueError("one contact resistance between each adjacent pair of layers required")
    gaps = [decimal_input(r, "contact resistance") for r in contacts]
    prepared = []
    records = []
    for inputs, inlet, ref, slope in layers:
        law = terminal_response(*inputs, include_rods=True)
        if len(law["terminals"]) != 2 or inlet not in law["terminals"]:
            raise ValueError("each layer requires two terminals and a named left terminal")
        outlet, = set(law["terminals"])-{inlet}
        conductance = tuple(map(Fraction, law["supplyResponseBoundsWPerK"][inlet][inlet]))
        if conductance[0] <= 0:
            raise ValueError("unresolved layer conductance")
        material = SolidPotential(ref, slope, cold, hot)
        prepared.append((material, conductance, law["rodResponseBoundsWPerK"]))
        records.append({"leftTerminal": inlet, "rightTerminal": outlet,
                        "referenceTemperatureK": str(material.reference), "relativeSlopePerK": str(material.slope),
                        **{k: law[k] for k in ("studySha256", "factsSha256", "modelSha256")}})

    # March from the cold boundary. Each contact adds qR and each layer adds
    # q/G in its own conductivity potential. Every step is increasing in q.
    physical_gaps = gaps.copy()
    if exterior and coefficient:
        prepared.append((RadiationPotential(cold), (coefficient, coefficient), {}))
        gaps.append(Fraction(0))
    indices = list(range(len(prepared)))
    if left > right:
        indices.reverse()
    def march(q, upper, faces=None):
        t = cold
        for n, i in enumerate(indices):
            m, g, _ = prepared[i]
            needed = m.potential(t)+q/g[0 if upper else 1]
            residual = needed-m.potential(hot)
            next_t = m.inverse(needed, hot, upper)
            if faces is not None:
                faces[i] = (t, next_t) if left <= right else (next_t, t)
            if n+1 < len(indices):
                t = min(hot, next_t+q*gaps[min(i, indices[n+1])])
        return residual

    maximum = min(g[1]*m.potential(hot) for m,g,_ in prepared)
    if sum(gaps):
        maximum = min(maximum, (hot-cold)/sum(gaps))

    def current(upper):
        lo, hi = Fraction(0), maximum
        for _ in range(96):
            mid = (lo+hi)/2
            # The upper temperature envelope reaches the hot boundary first.
            if march(mid, not upper) < 0:
                lo = mid
            else:
                hi = mid
        return hi if upper else lo

    qlo, qhi = current(False), current(True)
    low_faces, high_faces = {}, {}
    march(qlo, False, low_faces)
    march(qhi, True, high_faces)
    signed = (qlo, qhi) if left >= right else (-qhi, -qlo)
    for i, record in enumerate(records):
        for j, key in enumerate(("leftFaceTemperatureBoundsK", "rightFaceTemperatureBoundsK")):
            record[key] = list(map(str, (low_faces[i][j], high_faces[i][j])))
        _, g, rods = prepared[i]
        flows = {}
        for rod, row in rods.items():
            products = [q*gain/conductance for gain in map(Fraction, row[record["leftTerminal"]])
                        for q in signed for conductance in g]
            flows[rod] = list(map(str, (min(products), max(products))))
        record["rodHeatFlowBoundsW"] = flows
    records[0]["leftFaceTemperatureBoundsK"] = [str(left)]*2
    if not exterior:
        records[-1]["rightFaceTemperatureBoundsK"] = [str(right)]*2
    extra = {}
    if exterior:
        extra = {"exterior": exterior, "surfaceTemperatureBoundsK": records[-1]["rightFaceTemperatureBoundsK"],
                 "netHeatToEnclosureBoundsW": list(map(str, signed))}
    schema = "sim_heat.offline_radiating_layer_stack/1" if exterior else "sim_heat.offline_composite_layer_stack/1"
    return {"schema": schema, "layers": records, **extra,
            "contactResistancesKPerW": list(map(str, physical_gaps)), "leftToRightHeatRateBoundsW": list(map(str, signed)),
            "nativeExecuted": False, "nativeQualified": False, "independentlyCertifiedReference": False,
            "runnerConsumable": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left-k", required=True)
    parser.add_argument("--right-k", required=True)
    parser.add_argument("--layer", nargs=7, action="append", required=True,
                        metavar=("STUDY","ROOT","FACTS","SHA256","LEFT_PORT","REF_K","SLOPE_PER_K"))
    parser.add_argument("--contact", action="append", default=[], metavar="K_PER_W")
    parser.add_argument("--radiation", nargs=3, metavar=("AREA_M2","EMISSIVITY","SIGMA"),
                        help="radiate to the enclosure at --right-k")
    args = parser.parse_args()
    layers = [(values[:4], *values[4:]) for values in args.layer]
    print(json.dumps(investigate(layers, args.contact, args.left_k, args.right_k, radiation=args.radiation), indent=2))
