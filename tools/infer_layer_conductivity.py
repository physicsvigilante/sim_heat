"""Infer the common conductivity multiplier of one buried two-terminal layer."""
import argparse
import json

from tools.composite_layer_stack import prepare_layers
from tools.infer_wall_contact import walk_to_face
from tools.radiating_surface import decimal_input


def investigate(layers, contacts, left_k, right_k, min_w, max_w, unknown_layer):
    left, right = (decimal_input(x, "bath temperature") for x in (left_k, right_k))
    cold, hot = sorted((left, right))
    qlo, qhi = (decimal_input(x, "heat rate magnitude") for x in (min_w, max_w))
    if not 0 < qlo <= qhi or cold == hot:
        raise ValueError("distinct baths and positive ordered heat-rate magnitudes required")
    if type(unknown_layer) is not int or not 1 <= unknown_layer <= len(layers):
        raise ValueError("unknown layer must be a one-based layer number")
    if len(contacts) != len(layers)-1:
        raise ValueError("one known contact resistance per interface required")
    gaps = [decimal_input(x, "contact resistance") for x in contacts]
    prepared, sources = prepare_layers(layers, cold, hot)
    index = unknown_layer-1
    material, (base_lo, base_hi), _ = prepared[index]

    def surface(indices, bath, q):
        lo, hi = walk_to_face(prepared, gaps, indices, bath, q, cold, hot)
        if indices:
            jump = q*gaps[min(indices[-1], index)]
            sign = 1 if bath == cold else -1
            lo, hi = lo+sign*jump, hi+sign*jump
            if lo < cold or hi > hot:
                raise ValueError("known contact drop exceeds the available temperature difference")
        return lo, hi

    left_faces, right_faces, conductances = [], [], []
    for q in (qlo, qhi):
        a = surface(range(index), left, q)
        b = surface(range(len(layers)-1,index,-1), right, q)
        left_faces.extend(a)
        right_faces.extend(b)
        warm, cool = (a,b) if left > right else (b,a)
        drop_lo = material.potential(warm[0])-material.potential(cool[1])
        drop_hi = material.potential(warm[1])-material.potential(cool[0])
        if drop_lo <= 0:
            raise ValueError("finite positive conductivity unresolved at measured heat rate")
        conductances.append((q/drop_hi, q/drop_lo))
    # Increasing the measured current reduces the potential drop available to
    # the unknown layer. Its required reference conductance therefore increases.
    lo, hi = conductances[0][0], conductances[-1][1]
    return {"schema": "sim_heat.offline_inferred_layer_conductivity/1", "unknownLayer": unknown_layer,
            "layers": sources, "leftBathK": str(left), "rightBathK": str(right),
            "contactResistancesKPerW": list(map(str, gaps)), "measuredMagnitudeBoundsW": list(map(str, (qlo,qhi))),
            "effectiveReferenceConductanceBoundsWPerK": list(map(str, (lo, hi))),
            "commonRodConductivityMultiplierBounds": list(map(str, (lo/base_hi, hi/base_lo))),
            "leftLayerFaceBoundsK": list(map(str, (min(left_faces), max(left_faces)))),
            "rightLayerFaceBoundsK": list(map(str, (min(right_faces), max(right_faces)))),
            "nativeExecuted": False, "nativeQualified": False, "independentlyCertifiedReference": False,
            "runnerConsumable": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("left-k", "right-k", "min-w", "max-w"):
        parser.add_argument("--"+name, required=True)
    parser.add_argument("--unknown-layer", required=True, type=int)
    parser.add_argument("--layer", nargs=7, action="append", required=True,
                        metavar=("STUDY","ROOT","FACTS","SHA256","LEFT_PORT","REF_K","SLOPE_PER_K"))
    parser.add_argument("--contact", action="append", default=[], metavar="K_PER_W")
    a = parser.parse_args()
    layers = [(v[:4], *v[4:]) for v in a.layer]
    print(json.dumps(investigate(layers, a.contact, a.left_k, a.right_k, a.min_w, a.max_w, a.unknown_layer), indent=2))
