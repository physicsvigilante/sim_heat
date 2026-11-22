"""Replay the JEE furnace-wall problem, contact repair and variable-material check."""
from fractions import Fraction
import json
from pathlib import Path

from tools.composite_layer_stack import investigate


def residual(q):
    """Power balance for the repaired contact, in watts."""
    return q-Fraction(1,10**8)*((610-q)**4-300**4)


def replay():
    root = Path(__file__).resolve().parents[1] / "studies/composite_wall"
    inputs = (root/"study.json", root, root/"facts.json",
              "f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b")
    results = {}
    default_refs = ("566.25", "443.75")
    for name, contact, refs, slopes in (
        ("furnace", "0.2", default_refs, ("0", "0")),
        ("perfectContact", "0", default_refs, ("0", "0")),
        ("variableConductivity", "0.2", default_refs, ("0.001", "-0.001")),
        ("unequalPanelDrops", "0.2", ("285", "312.5"), ("0.0025", "-0.002")),
    ):
        layers = [(inputs, "hot", ref, slope) for ref, slope in zip(refs, slopes)]
        result = investigate(layers, [contact], "610", "300", radiation=("0.2","1","0.00000005"))
        if list(map(Fraction, result["contactResistancesKPerW"])) != [Fraction(contact)]:
            raise ValueError("contact resistance differs from the lesson input")
        for panel, ref, slope in zip(result["layers"], refs, slopes, strict=True):
            source_fields = ("leftTerminal", "rightTerminal", "factsSha256", "studySha256", "modelSha256")
            expected_source = ("hot", "cold", inputs[3],
                               "3ddc9873ec055709ce27a2a2cd302a663e71dbcbbac939a96d4a17d252f5f418",
                               "e6b0edff0f0274bad86736d07aa938be3e4ba8766b134776f8f9b8c2e74c6fe9")
            if tuple(panel[k] for k in source_fields) != expected_source:
                raise ValueError("panel source or terminal orientation differs from the study")
            if (Fraction(panel["referenceTemperatureK"]), Fraction(panel["relativeSlopePerK"])) != (
                    Fraction(ref), Fraction(slope)):
                raise ValueError("panel material differs from the lesson input")
        qlo, qhi = map(Fraction, result["netHeatToEnclosureBoundsW"])
        if result["leftToRightHeatRateBoundsW"] != result["netHeatToEnclosureBoundsW"]:
            raise ValueError("conducted and radiated heat rates differ")
        if name == "perfectContact":
            # Each solid has resistance 1/2 K/W, so Ts = 610 - q.
            if not (175 < qlo <= qhi < 310 and residual(qlo) <= 0 <= residual(qhi)):
                raise ValueError("perfect-contact current differs from the heat balance")
        elif not qlo <= 175 <= qhi:
            raise ValueError("furnace current differs from 175 W")
        if qhi-qlo > Fraction(1,10**10):
            raise ValueError("heat current unresolved")

        # Effective panel resistances here are derived for the specific worked states.
        first, second = ((Fraction(2,7), Fraction(5,7)) if name == "unequalPanelDrops"
                         else (Fraction(1,2), Fraction(1,2)))
        face_offsets = ((0, first), (first+Fraction(contact), first+Fraction(contact)+second))
        for layer, (left_r, right_r) in zip(result["layers"], face_offsets, strict=True):
            checks = [(layer["leftFaceTemperatureBoundsK"], 610, -left_r),
                      (layer["rightFaceTemperatureBoundsK"], 610, -right_r)]
            checks.extend((layer["rodHeatFlowBoundsW"][rod], 0, factor)
                          for rod, factor in (("facing",1),("strip",Fraction(1,4)),("insert",Fraction(-3,4))))
            for values, offset, factor in checks:
                a,b = map(Fraction, values)
                if not 0 <= b-a <= Fraction(1,10**10):
                    raise ValueError("layer observable unresolved")
                if name == "perfectContact" and factor:
                    low, high = sorted(((a-offset)/factor, (b-offset)/factor))
                    valid = 0 <= low <= high < 310 and residual(low) <= 0 <= residual(high)
                else:
                    valid = a <= offset+factor*175 <= b
                if not valid:
                    raise ValueError("layer temperature or signed rod flow differs from the worked solution")
        if result["surfaceTemperatureBoundsK"] != result["layers"][-1]["rightFaceTemperatureBoundsK"]:
            raise ValueError("radiating surface differs from outer face")
        results[name] = result
    return results


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2))
