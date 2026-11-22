import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from qualification.h1_n13.conduction import prepare


CASE = Path(__file__).resolve().parents[1] / "studies/composite_wall"
FACTS_PIN = "f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b"


class CompositeWallTests(TestCase):
    def test_series_drop_parallel_split_and_reversed_insert(self):
        result = prepare(CASE / "study.json", CASE, CASE / "facts.json", FACTS_PIN)
        self.assertEqual(result["requests"], {
            "interfaceT": {"unit": "K", "values": [330]},
            "facingRate": {"unit": "W", "values": [200]},
            "stripRate": {"unit": "W", "values": [50]},
            "insertRate": {"unit": "W", "values": [-150]},
        })
        for boundary, expected in (("hot", 200), ("cold", -200)):
            self.assertEqual(result["exports"][boundary + ".Q_to_network"],
                             {"unit": "W", "values": [expected]})
        self.assertIs(result["nativeExecuted"], False)

    def test_refuse_reference_with_wrong_strip_area(self):
        facts = json.loads((CASE / "facts.json").read_bytes())
        facts["rods"]["strip"]["A"] = 0.02
        with TemporaryDirectory() as scratch:
            changed = Path(scratch) / "facts.json"
            data = json.dumps(facts).encode()
            changed.write_bytes(data)
            with self.assertRaisesRegex(ValueError, r"reference fact differs: strip\.A$"):
                prepare(CASE / "study.json", CASE, changed, sha256(data).hexdigest())
