"""Infer one unknown contact resistance from a steady multilayer wall's measured heat rate."""
import argparse
import json

from tools.composite_layer_stack import prepare_layers
from tools.radiating_surface import decimal_input


def investigate(layers, contacts, left_k, right_k, min_w, max_w):
    left, right = (decimal_input(x, "bath temperature") for x in (left_k, right_k))
    cold, hot = sorted((left, right))
    qlo, qhi = (decimal_input(x, "heat rate magnitude") for x in (min_w, max_w))
    if not 0 < qlo <= qhi or cold == hot:
        raise ValueError("distinct baths and positive ordered heat-rate magnitudes required")
    if len(contacts) != len(layers)-1 or contacts.count("?") != 1:
        raise ValueError("specify each contact and mark exactly one unknown")
    cut = contacts.index("?")
    gaps = [None if x == "?" else decimal_input(x, "contact resistance") for x in contacts]
    prepared, sources = prepare_layers(layers, cold, hot)

    def face(indices, bath, q):
        # Walk inward from a measured bath, across every known resistance on that side.
        sign = 1 if bath == cold else -1
        lo = hi = bath
        for n, i in enumerate(indices):
            material, (glo, ghi), _ = prepared[i]
            delta = sorted((sign*q/glo, sign*q/ghi))
            a = material.potential(lo)+delta[0]
            b = material.potential(hi)+delta[1]
            if a < 0 or b > material.potential(hot):
                raise ValueError("measured rate exceeds the certified layer temperature range")
            lo, hi = material.inverse(a, hot, False), material.inverse(b, hot, True)
            if n+1 < len(indices):
                drop = sign*q*gaps[min(i, indices[n+1])]
                lo, hi = lo+drop, hi+drop
                if lo < cold or hi > hot:
                    raise ValueError("known contact drop exceeds the available temperature difference")
        return lo, hi

    candidates = []
    left_faces, right_faces = [], []
    for q in (qlo, qhi):
        lf = face(range(cut+1), left, q)
        rf = face(range(len(layers)-1, cut, -1), right, q)
        left_faces.extend(lf)
        right_faces.extend(rf)
        warm, cool = (lf, rf) if left > right else (rf, lf)
        candidates.append(((warm[0]-cool[1])/q, (warm[1]-cool[0])/q))
    # The warm face cools and the cool face warms as q grows. On the
    # nonnegative-resistance branch the residual drop divided by q decreases.
    low, high = candidates[1][0], candidates[0][1]
    if high < 0:
        raise ValueError("current incompatible with a passive contact")
    if low < 0:
        raise ValueError("nonnegative contact resistance unresolved over the measured interval")
    return {"schema": "sim_heat.offline_inferred_contact/1", "layers": sources,
            "leftBathK": str(left), "rightBathK": str(right),
            "contactResistancesKPerW": [None if r is None else str(r) for r in gaps],
            "unknownContactAfterLayer": cut+1, "measuredMagnitudeBoundsW": [str(qlo), str(qhi)],
            "contactResistanceBoundsKPerW": list(map(str, (low, high))),
            "leftContactFaceBoundsK": list(map(str, (min(left_faces), max(left_faces)))),
            "rightContactFaceBoundsK": list(map(str, (min(right_faces), max(right_faces)))),
            "nativeExecuted": False, "nativeQualified": False, "independentlyCertifiedReference": False,
            "runnerConsumable": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("left-k", "right-k", "min-w", "max-w"):
        parser.add_argument("--"+name, required=True)
    parser.add_argument("--layer", nargs=7, action="append", required=True,
                        metavar=("STUDY","ROOT","FACTS","SHA256","LEFT_PORT","REF_K","SLOPE_PER_K"))
    parser.add_argument("--contact", action="append", required=True, metavar="K_PER_W_OR_?")
    a = parser.parse_args()
    layers = [(v[:4], *v[4:]) for v in a.layer]
    print(json.dumps(investigate(layers, a.contact, a.left_k, a.right_k, a.min_w, a.max_w), indent=2))
