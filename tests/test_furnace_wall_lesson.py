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
