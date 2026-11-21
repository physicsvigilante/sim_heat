"""Infer two contact resistances using a thermometer at an ideal internal joint."""
import argparse
import json

from tools.infer_wall_contact import investigate as infer_contact
from tools.radiating_surface import decimal_input


def investigate(layers, contacts, left_k, right_k, min_w, max_w, probe_after, probe_k):
    """The probe measures a common face temperature and exchanges zero heat."""
    if type(probe_after) is not int or not 1 <= probe_after < len(layers):
        raise ValueError("probe must be located between two layers")
    if len(contacts) != len(layers) - 1:
        raise ValueError("one contact per interface required")
    joint = contacts[probe_after - 1]
    if joint == "?" or decimal_input(joint, "probe joint resistance") != 0:
        raise ValueError("the thermometer requires an ideal joint with one common temperature")
    left = decimal_input(left_k, "left bath temperature")
    right = decimal_input(right_k, "right bath temperature")
    probe = decimal_input(probe_k, "probe temperature")
    if not min(left, right) < probe < max(left, right):
        raise ValueError("a passive probe must lie strictly between the bath temperatures")

    segments = (
        (0, layers[:probe_after], contacts[:probe_after - 1], left_k, probe_k),
        (probe_after, layers[probe_after:], contacts[probe_after:], probe_k, right_k),
    )
    inferred = []
    sources = []
    for offset, panels, interfaces, start, end in segments:
        result = infer_contact(panels, interfaces, start, end, min_w, max_w)
        sources.extend(result["layers"])
        inferred.append({
            "afterLayer": offset + result["unknownContactAfterLayer"],
            "resistanceBoundsKPerW": result["contactResistanceBoundsKPerW"],
            "leftFaceBoundsK": result["leftContactFaceBoundsK"],
            "rightFaceBoundsK": result["rightContactFaceBoundsK"],
        })
    return {
        "schema": "sim_heat.offline_probed_contacts/1",
        "layers": sources,
        "contactResistancesKPerW": [None if r == "?" else str(decimal_input(r, "contact resistance"))
                                    for r in contacts],
        "leftBathK": str(left), "rightBathK": str(right),
        "probeAfterLayer": probe_after, "probeTemperatureK": str(probe),
        "measuredMagnitudeBoundsW": result["measuredMagnitudeBoundsW"],
        "inferredContacts": inferred,
        "nativeExecuted": False, "nativeQualified": False,
        "independentlyCertifiedReference": False, "runnerConsumable": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("left-k", "right-k", "min-w", "max-w", "probe-k"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--probe-after", type=int, required=True)
    parser.add_argument("--layer", nargs=7, action="append", required=True,
                        metavar=("STUDY", "ROOT", "FACTS", "SHA256", "LEFT_PORT", "REF_K", "SLOPE_PER_K"))
    parser.add_argument("--contact", action="append", required=True, metavar="K_PER_W_OR_?")
    args = parser.parse_args()
    layers = [(v[:4], *v[4:]) for v in args.layer]
    print(json.dumps(investigate(layers, args.contact, args.left_k, args.right_k,
                                 args.min_w, args.max_w, args.probe_after, args.probe_k), indent=2))
