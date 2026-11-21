from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from tests.test_composite_wall import CASE, FACTS_PIN
from tests.test_steady_bridge import CASE as BRIDGE, BASE, CHANGED
from tools.resistance_sensitivity import investigate
from tools.terminal_resistance import measure


class ResistanceSensitivityTests(TestCase):
    def assert_encloses(self, interval, expected):
        lo, hi = map(Fraction, interval)
        self.assertLessEqual(lo, expected)
        self.assertGreaterEqual(hi, expected)
        self.assertLess(hi-lo, Fraction(1, 10**12))

    def test_same_fractional_resistance_change_has_different_effects(self):
        result = investigate(CASE/"study.json", CASE, CASE/"facts.json", FACTS_PIN)
        for rod, slope, relative in (("facing", 1, Fraction(1, 2)),
                                     ("strip", Fraction(1, 16), Fraction(1, 8)),
                                     ("insert", Fraction(9, 16), Fraction(3, 8))):
            self.assert_encloses(result["rods"][rod]["resistanceDerivativeBounds"], slope)
            self.assert_encloses(result["rods"][rod]["relativeSensitivityBounds"], relative)

    def test_bridge_crossbar_only_matters_after_unbalancing(self):
        for prefix, pin, expected in (("", BASE, 0), ("changed_", CHANGED, Fraction(10,185)**2)):
            result = investigate(BRIDGE/(prefix+"study.json"), BRIDGE,
                                 BRIDGE/(prefix+"facts.json"), pin)
            self.assert_encloses(result["rods"]["link"]["resistanceDerivativeBounds"], expected)

    def test_full_engine_insert_length_perturbation(self):
        # Positive and negative length changes give rigorous one-sided slopes for
        # R_total = R_facing + R_strip*R_insert/(R_strip+R_insert), a concave function.
        for length, delta in (("0.1001", Fraction(1,3000)), ("0.0999", Fraction(-1,3000))):
            with TemporaryDirectory() as scratch:
                root = Path(scratch)
                model = (CASE/"model.mo").read_bytes()
                changed = model.replace(b"insert(k=30, L=0.1,", f"insert(k=30, L={length},".encode())
                self.assertNotEqual(changed, model)
                (root/"model.mo").write_bytes(changed)
                study = json.loads((CASE/"study.json").read_bytes())
                study["model"]["sha256"] = sha256(changed).hexdigest()
                descriptor = json.dumps(study).encode()
                (root/"study.json").write_bytes(descriptor)
                facts = json.loads((CASE/"facts.json").read_bytes())
                facts["rods"]["insert"]["L"] = float(length)
                facts.update(studySha256=sha256(descriptor).hexdigest(),modelSha256=sha256(changed).hexdigest())
                raw = json.dumps(facts).encode()
                (root/"facts.json").write_bytes(raw)
                interval = measure(root/"study.json", root, root/"facts.json",
                                   sha256(raw).hexdigest())["resistanceBoundsKPerW"]
                secant = [(Fraction(r)-Fraction(1,2))/delta for r in interval]
                slope = Fraction(9,16)
                if delta > 0:
                    self.assertLess(max(secant), slope)
                else:
                    self.assertGreater(min(secant), slope)
                self.assertLess(max(abs(s-slope) for s in secant), Fraction(1,5000))

    def test_refuse_a_third_maintained_terminal(self):
        from tests.test_terminal_response import CASES, STAR
        root = CASES / "star"
        with self.assertRaisesRegex(ValueError, "two-terminal"):
            investigate(root/"study.json", root, root/"facts.json", STAR)
