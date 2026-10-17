"""Omitted date recovery; no models, network or production writes."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

from src.local_runner.adaptive_maintenance import apply_update, _refresh_inherited_report_date
from src.local_runner.adaptive_context import model_context, validation_context
from src.local_runner import run_one

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("date_fixture", ROOT / "tests/test_adaptive_maintenance.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class DateRecoveryTests(unittest.TestCase):
    def example(self):
        data, value = fixture.context(), fixture.payload()
        data['routing_revision'] = 4
        value['edits'] = [fixture.edit('Setup: 6 / 10', 'Setup: 6,5 / 10')]
        return data, value

    def test_omitted_inherited_date_refreshed_and_audited_not_sol_age(self):
        data, value = self.example()
        original, original_payload = deepcopy(data), deepcopy(value)
        audit = []
        result = apply_update(value, data, audit=audit)
        self.assertIn('Fecha del análisis: 03-10-2026', result)
        self.assertIn('02-10-2026 · Resultados confirmados', result)
        self.assertEqual(data, original)
        self.assertEqual(value, original_payload)
        self.assertEqual(audit[-1]['method'], 'exact_inherited_maintenance_date_refresh')
        self.assertEqual(audit[-1]['source'], '/prepared_at')
        self.assertEqual(data['sol_reference']['generated_at'], '2026-10-02T10:00:00Z')

    def test_revision3_keeps_old_receipt_semantics(self):
        data, value = self.example()
        data['routing_revision'] = 3
        with self.assertRaisesRegex(ValueError, 'stale_report_date'):
            apply_update(value, data)

    def test_correct_explicit_date_is_not_rewritten(self):
        data, value = self.example()
        value['edits'].insert(0, fixture.payload()['edits'][0])
        audit = []
        result = apply_update(value, data, audit=audit)
        self.assertIn('Fecha del análisis: 03-10-2026', result)
        self.assertFalse(any(row['method'] == 'exact_inherited_maintenance_date_refresh' for row in audit))

    def test_explicit_wrong_date_not_silently_repaired(self):
        for wrong in ('01-10-2026', '04-10-2026', 'bad-date'):
            data, value = self.example()
            value['edits'].append(fixture.edit('Fecha del análisis: 02-10-2026', 'Fecha del análisis: '+wrong))
            with self.subTest(wrong=wrong), self.assertRaisesRegex(ValueError, 'stale_report_date'):
                apply_update(value, data)

    def test_future_malformed_or_missing_inherited_date_not_repaired(self):
        for wrong in ('04-10-2026', 'bad-date', ''):
            data, value = self.example()
            data['reference']['analysis_markdown'] = fixture.MD.replace('Fecha del análisis: 02-10-2026', 'Fecha del análisis: '+wrong)
            value['base_markdown_sha256'] = hashlib.sha256(data['reference']['analysis_markdown'].encode()).hexdigest()
            with self.subTest(wrong=wrong), self.assertRaisesRegex(ValueError, 'stale_report_date'):
                apply_update(value, data)

    def test_missing_or_invalid_prepare_time_not_guessed(self):
        for at in ('', 'invalid'):
            data, value = self.example()
            data['prepared_at'] = at
            with self.subTest(at=at), self.assertRaisesRegex(ValueError, 'missing_prepared_at'):
                apply_update(value, data)

    def test_preserves_wrappers_crlf_and_all_nonfield_dates(self):
        data, _ = self.example()
        for spelling in ('02-10-2026', '02/10/2026', '2026-10-02'):
            raw = fixture.MD.replace('Fecha del análisis: 02-10-2026', '**Fecha del análisis: '+spelling+'**').replace('\n', '\r\n')
            result, audit = _refresh_inherited_report_date(raw, raw, data)
            expected = '2026-10-03' if spelling.startswith('2026') else '03/10/2026' if '/' in spelling else '03-10-2026'
            self.assertEqual(result, raw.replace('**Fecha del análisis: '+spelling+'**', '**Fecha del análisis: '+expected+'**'))
            self.assertEqual(len(audit), 1)

    def test_duplicates_and_protected_fields_still_rejected(self):
        for before, after in (('Setup: 6 / 10', 'Setup: 6 / 10\nFecha del análisis: 03-10-2026'),
                              ('Tesis: 8 / 10', 'Tesis: 1 / 10')):
            data, value = self.example()
            value['edits'] = [fixture.edit(before, after)]
            with self.subTest(before=before), self.assertRaises(ValueError):
                apply_update(value, data)

    def test_retain_does_not_refresh_date(self):
        data, value = self.example()
        value.update(decision='retain', edits=[])
        with self.assertRaisesRegex(ValueError, 'invalid_update_decision'):
            apply_update(value, data)

    def test_date_recovery_does_not_fix_wrong_price(self):
        data, value = self.example()
        value['edits'].append(fixture.edit('Precio de referencia: $100', 'Precio de referencia: $101'))
        with self.assertRaisesRegex(ValueError, 'stale_reference_price'):
            apply_update(value, data)

    def test_saved_NVDA_exact_candidate_full_validation_without_model(self):
        saved = ROOT / 'logs/batch/2026-10-04/07-12-55/adaptive/NVDA'
        if not saved.exists():
            self.skipTest('optional incident artifacts unavailable')
        raw = json.loads((saved/'input.json').read_text(encoding='utf-8'))
        value = json.loads((saved/'triage.response').read_text(encoding='utf-8'))
        original = deepcopy(raw)
        audit = []
        candidate = apply_update(value, model_context(raw), audit=audit)
        validation = run_one.validate_markdown(candidate, authoritative_context=validation_context(raw),
            require_support_strengths=True, require_resistance=True, require_separate_scores=True)
        self.assertTrue(validation.ok, validation.errors)
        self.assertIn('Fecha del análisis: 04-10-2026', candidate)
        self.assertEqual(raw, original)
        self.assertIn('exact_inherited_maintenance_date_refresh', [item['method'] for item in audit])


if __name__ == '__main__':
    unittest.main()
