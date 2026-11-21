"""Regression for preview identity after H1 study admission."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import unittest

from h1.source_preview import build_source_preview
from h1.study import load_study


class PreviewIdentityTests(unittest.TestCase):
    def test_mass_is_bound_to_admitted_model_bytes(self):
        case = Path(__file__).resolve().parents[1] / 'h1/cases/D1'
        study = load_study(case / 'study.json', case)
        expected_hash = sha256((case / 'model.mo').read_bytes()).hexdigest()
        fields = study.model.components['body'].fields

        for mutated in (False, True):
            with self.subTest(mutated=mutated):
                if mutated:
                    fields['m'] = replace(fields['m'], value=987.0)
                    study.data['provenance'][0]['note'] = 'changed after admission'
                preview = build_source_preview(study)
                body = next(c for c in preview['components'] if c['id'] == 'body')
                mass = next(p for p in body['inputs'] if p['name'] == 'm')
                self.assertEqual(preview['source']['modelSha256'], expected_hash)
                self.assertEqual(mass['sourceValue'], 1.0)
                self.assertNotIn('changed after admission', str(preview))
