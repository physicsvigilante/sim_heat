from unittest import TestCase
from unittest.mock import patch

from tools import wall_reversal_lesson as lesson


class WallLessonChecks(TestCase):
    def test_corrupt_branch_and_bath_are_rejected(self):
        original = lesson.investigate
        for side, field, component, value in (
            ("left", "rodHeatFlowBoundsW", "insert", ["0", "0"]),
            ("right", "terminalSupplyBoundsW", "cold", ["120", "120"]),
            ("left", "rodHeatFlowBoundsW", "strip", ["0", "100"]),
            ("right", "rodHeatFlowBoundsW", "facing", ["121", "119"]),
        ):
            def corrupted(*args):
                result = original(*args)
                if component in result[side][field]:
                    result[side][field][component] = value
                return result
            with self.subTest(side=side, component=component), patch.object(lesson, "investigate", corrupted):
                with self.assertRaisesRegex(ValueError, component):
                    lesson.replay()
