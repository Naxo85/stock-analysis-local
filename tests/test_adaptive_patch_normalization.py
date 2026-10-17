"""Offline incident and adversarial replay: no model/publication access."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from contextlib import ExitStack
from datetime import datetime, timedelta
import shutil
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from src.local_runner.adaptive_maintenance import apply_update, LEVEL_LABELS
from src.local_runner.adaptive_patch_normalization import refresh_level_percentages
from src.local_runner.adaptive_context import model_context, validation_context
from src.local_runner.adaptive_policy import maintenance_precheck
from src.local_runner import run_one

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('patch_fixture', ROOT/'tests/test_adaptive_maintenance.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class PatchNormalizationTests(unittest.TestCase):
    def example(self, markdown=None):
        data, value = fixture.context(), fixture.payload()
        data['routing_revision'] = 4
        if markdown is not None:
            data['reference']['analysis_markdown'] = markdown
        value['base_markdown_sha256'] = hashlib.sha256(data['reference']['analysis_markdown'].encode()).hexdigest()
        return data, value

    def test_bare_duplicate_date_resolves_only_report_field_without_mutation(self):
        md = fixture.MD.replace('Guidance mantenido.', 'Guidance del 02-10-2026 mantenido.')
        data, value = self.example(md)
        value['edits'] = [fixture.edit('02-10-2026', '03-10-2026')]
        source, payload = deepcopy(data), deepcopy(value)
        audit = []
        result = apply_update(value, data, audit=audit)
        self.assertIn('Fecha del análisis: 03-10-2026', result)
        self.assertIn('Guidance del 02-10-2026 mantenido.', result)
        self.assertEqual(data, source)
        self.assertEqual(value, payload)
        self.assertEqual(audit[0]['method'], 'field_scoped_report_date_edit')
        self.assertEqual(data['sol_reference']['generated_at'], source['sol_reference']['generated_at'])

    def test_other_ambiguous_or_wrong_date_edits_remain_failures(self):
        data, value = self.example(fixture.MD.replace('Guidance mantenido.', 'Guidance 02-10-2026, $90 y $90.'))
        for before, after in (('02-10-2026', '04-10-2026'), ('$90', '$91'), ('missing', 'new')):
            bad = deepcopy(value)
            bad['edits'] = [fixture.edit(before, after)]
            with self.subTest(before=before), self.assertRaisesRegex(ValueError, 'invalid_update_ambiguous_or_missing_match'):
                apply_update(bad, data)
        data['routing_revision'] = 3
        value['edits'] = [fixture.edit('02-10-2026', '03-10-2026')]
        with self.assertRaisesRegex(ValueError, 'invalid_update_ambiguous_or_missing_match'):
            apply_update(value, data)

    def test_grouped_fields_and_blank_gap_are_editable(self):
        md = fixture.MD.replace('02-10-2026\nPrecio', '02-10-2026\n\nPrecio')
        data, value = self.example(md)
        before = 'Fecha del análisis: 02-10-2026\n\nPrecio de referencia: $100'
        value['edits'] = [fixture.edit(before, before.replace('02-10', '03-10').replace('$100', '$101'))]
        data['slim']['latest_price'] = 101
        result = apply_update(value, data)
        self.assertIn('Precio de referencia: $101', result)
        self.assertIn('Tesis: 8 / 10', result)
        data['routing_revision'] = 3
        with self.assertRaisesRegex(ValueError, 'protected_span'):
            apply_update(value, data)

    def test_group_cannot_swallow_protected_prose_or_heading(self):
        for inserted in ('Secret: protected\n', '## Protected heading\n'):
            md = fixture.MD.replace('02-10-2026\nPrecio', '02-10-2026\n'+inserted+'Precio')
            data, value = self.example(md)
            before = 'Fecha del análisis: 02-10-2026\n'+inserted+'Precio de referencia: $100'
            value['edits'] = [fixture.edit(before, before.replace('02-10', '03-10'))]
            with self.subTest(inserted=inserted), self.assertRaisesRegex(ValueError, 'protected_span'):
                apply_update(value, data)

    def test_group_cannot_change_narrative_thesis_stops_or_duplicate_labels(self):
        cases = [('Narrativa actual: Crecimiento con riesgos conocidos.', 'Narrativa actual: Ningún riesgo.'),
                 ('Tesis: 8 / 10', 'Tesis: 9 / 10'),
                 ('Stop de gestión: $85', 'Stop de gestión: $84'),
                 ('Stop estructural: $70', 'Stop estructural: $69'),
                 ('Motivo: Invalida la estructura profunda.', 'Motivo: Todo está bien.'),
                 ('Precio de referencia: $100', 'Precio de referencia: $100\nPrecio de referencia: $100')]
        for before, after in cases:
            data, value = self.example()
            value['edits'].append(fixture.edit(before, after))
            with self.subTest(before=before), self.assertRaises(ValueError):
                apply_update(value, data)

    def test_percentages_use_actual_ranges_and_price_preserve_other_text(self):
        data, value = self.example()
        data['slim']['latest_price'] = 101
        value['edits'].append(fixture.edit('Precio de referencia: $100', 'Precio de referencia: $101'))
        value['edits'].append(fixture.edit('-10,00% a -8,00%', '-9,33% a -7,11%'))
        audit = []
        result = apply_update(value, data, audit=audit)
        self.assertIn('Entrada: $90-92 (-10,89% a -8,91%', result)
        self.assertIn('Stop de gestión: $85 (-15,84%', result)
        self.assertIn('Stop estructural: $70 (-30,69%', result)
        self.assertIn('Motivo: Invalida la estructura profunda.', result)
        self.assertEqual(len([row for row in audit if row['method'] == 'exact_level_percentage_calculation']), 9)

    def test_percentages_do_not_invent_missing_slots_or_sources(self):
        data, _ = self.example()
        for raw in (fixture.MD.replace('-10,00% a -8,00%', 'missing'),
                    fixture.MD.replace('-10,00% a -8,00%', '-10,00% a -8,00% and 99%')):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'missing_level_percentages'):
                refresh_level_percentages(raw, data, LEVEL_LABELS)
        for price in (None, True, -1, 0, float('nan'), float('inf')):
            data['slim']['latest_price'] = price
            with self.subTest(price=price), self.assertRaisesRegex(ValueError, 'current_price_unavailable'):
                refresh_level_percentages(fixture.MD, data, LEVEL_LABELS)
        data['routing_revision'] = 3
        self.assertEqual(refresh_level_percentages(fixture.MD, data, LEVEL_LABELS), (fixture.MD, []))

    def test_snapshot_refresh_requires_exact_inherited_proven_timestamp(self):
        raw = 'Snapshot técnico: **02-10-2026, 09:01:19 UTC**. Sin precios web.\n'
        md = fixture.MD.replace('Precio de referencia: $100\n', 'Precio de referencia: $100\n'+raw)
        data, value = self.example(md)
        data['reference']['slim_snapshot'] = {'as_of': '2026-10-02T09:01:19+00:00'}
        data['slim']['as_of'] = '2026-10-03T10:02:33+00:00'
        audit = []
        result = apply_update(value, data, audit=audit)
        self.assertIn('Snapshot técnico: **03-10-2026, 10:02:33 UTC**. Sin precios web.', result)
        self.assertIn('02-10-2026 · Resultados confirmados', result)
        self.assertIn('exact_inherited_snapshot_refresh', [row['method'] for row in audit])
        for wrong in ('2026-10-02T09:01:18+00:00', '', '2026-10-02T09:01:19'):
            bad = deepcopy(data)
            bad['reference']['slim_snapshot']['as_of'] = wrong
            with self.subTest(wrong=wrong), self.assertRaisesRegex(ValueError, 'stale_snapshot_banner'):
                apply_update(value, bad)
        explicit = deepcopy(value)
        explicit['edits'].append(fixture.edit(raw, raw.replace('09:01:19', '09:02:19')))
        with self.assertRaisesRegex(ValueError, 'stale_snapshot_banner'):
            apply_update(explicit, data)
        data['routing_revision'] = 3
        with self.assertRaisesRegex(ValueError, 'stale_snapshot_banner'):
            apply_update(value, data)

    def test_fundamental_risks_uncertainty_and_missing_origin_not_repaired(self):
        data, value = self.example()
        for flag in value['risk']:
            bad = deepcopy(value)
            bad['risk'][flag] = True
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'uncertain_or_critical'):
                apply_update(bad, data)
        bad = deepcopy(value)
        bad['uncertainty'] = True
        with self.assertRaisesRegex(ValueError, 'uncertain_or_critical'):
            apply_update(bad, data)
        value['edits'].append(fixture.edit('$90-92', '$95-96'))
        with self.assertRaisesRegex(ValueError, 'unproven_current_entry_origin'):
            apply_update(value, data)

    def test_original_oct5_receipts_pass_full_validation_without_mutating_sources(self):
        batch = ROOT/'logs/batch/2026-10-05/07-57-20/adaptive'
        if not batch.exists():
            self.skipTest('optional incident artifacts unavailable')
        for symbol in ('MU', 'KTOS', 'LRCX', 'MP', 'NVDA', 'OKLO', 'ORCL', 'SPCX', 'SNDK'):
            with self.subTest(symbol=symbol):
                folder = batch/symbol
                before = {name: hashlib.sha256((folder/name).read_bytes()).hexdigest()
                          for name in ('input.json', 'triage.response', 'triage.receipt.json')}
                raw = json.loads((folder/'input.json').read_text(encoding='utf-8'))
                raw.update(maintenance_precheck(raw['reference'], raw['slim'], raw['sol_reference'], owned=raw['owned']))
                value = json.loads((folder/'triage.response').read_text(encoding='utf-8'))
                candidate = apply_update(value, model_context(raw))
                validation = run_one.validate_markdown(candidate, authoritative_context=validation_context(raw),
                    require_support_strengths=True, require_resistance=True, require_separate_scores=True)
                self.assertTrue(validation.ok, validation.errors)
                self.assertEqual(before, {name: hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in before})
        raw = json.loads((batch/'RKLB/input.json').read_text(encoding='utf-8'))
        raw.update(maintenance_precheck(raw['reference'], raw['slim'], raw['sol_reference'], owned=raw['owned']))
        value = json.loads((batch/'RKLB/triage.response').read_text(encoding='utf-8'))
        with self.assertRaisesRegex(ValueError, 'protected_span'):
            apply_update(value, model_context(raw))

    def test_real_MU_staging_reuses_saved_receipt_builds_valid_bundle_no_models(self):
        from src.local_runner import adaptive_stage as stage
        from src.local_runner.adaptive_budget import read_json
        batch = ROOT/'logs/batch/2026-10-05/07-57-20'
        source = batch/'adaptive/MU'
        if not source.exists():
            self.skipTest('optional incident artifacts unavailable')
        raw = read_json(source/'input.json')
        receipt = read_json(source/'triage.receipt.json')
        at = datetime.fromisoformat(raw['prepared_at']) + timedelta(minutes=20)
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return at if tz else at.replace(tzinfo=None)
        hashes = {name: hashlib.sha256((source/name).read_bytes()).hexdigest()
                  for name in ('input.json', 'triage.response', 'triage.receipt.json')}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = root/'batch/adaptive/MU'
            work.mkdir(parents=True)
            for name in ('input.json', 'policy.json', 'instructions.md', 'triage_instructions.md',
                         'triage.response', 'triage.receipt.json'):
                shutil.copyfile(source/name, work/name)
            shutil.copyfile(batch/'codex_budget.json', root/'budget.json')
            with ExitStack() as stack:
                stack.enter_context(patch.object(stage, 'datetime', Clock))
                stack.enter_context(patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL')))
                stack.enter_context(patch.object(stage, 'reserve', side_effect=AssertionError('NO RESERVATION')))
                stack.enter_context(patch.object(stage.one, '_upload', side_effect=AssertionError('NO PUBLICATION')))
                result = stage.analyze(root, work, 'MU', root/'budget.json', False)
            self.assertEqual(result['status'], 'updated')
            output = work/'publish/output/MU'
            payload = read_json(output/'latest.json')
            self.assertEqual(payload['generation_model'], 'gpt-6-luna')
            self.assertEqual(payload['generated_at'], receipt['completed_at'])
            self.assertEqual(payload['last_full_report_at'], raw['sol_reference']['generated_at'])
            self.assertTrue(payload['validation']['ok'])
            self.assertTrue((output/'latest.html').exists())
            with patch.object(stage, 'model_call', side_effect=AssertionError('NO REPEAT')):
                self.assertEqual(stage.analyze(root, work, 'MU', root/'budget.json', False), result)
        self.assertEqual(hashes, {name: hashlib.sha256((source/name).read_bytes()).hexdigest() for name in hashes})


if __name__ == '__main__':
    unittest.main()
