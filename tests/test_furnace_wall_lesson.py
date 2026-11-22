from unittest import TestCase
from unittest.mock import patch

from tools import furnace_wall_lesson as lesson


class FurnaceReplayTests(TestCase):
    def test_controls_detect_perturbed_panels_and_contact(self):
        original = lesson.investigate
        for contact, component in (("0.2","insert"), ("0","strip")):
            def changed(layers, contacts, *args, **kwargs):
                result = original(layers, contacts, *args, **kwargs)
                if contacts == [contact]:
                    result["layers"][1]["rodHeatFlowBoundsW"][component] = ["0","0"]
                return result
            with self.subTest(contact=contact), patch.object(lesson, "investigate", changed):
                with self.assertRaisesRegex(ValueError, "signed rod flow"):
                    lesson.replay()

    def test_material_and_contact_substitutions(self):
        original = lesson.investigate
        for mutation in ("flat", "wrong_contact", "forged_slopes"):
            def changed(layers, contacts, *args, **kwargs):
                substituted = [(v[0], v[1], v[2], "0") for v in layers]
                result = original(layers if mutation == "wrong_contact" else substituted, contacts, *args, **kwargs)
                if mutation == "wrong_contact" and contacts == ["0"]:
                    result["contactResistancesKPerW"] = ["7"]
                if mutation == "forged_slopes":
                    for record, layer in zip(result["layers"], layers):
                        record["relativeSlopePerK"] = str(lesson.Fraction(layer[3]))
                return result
            with self.subTest(mutation=mutation), patch.object(lesson, "investigate", changed):
                with self.assertRaises(ValueError):
                    lesson.replay()
