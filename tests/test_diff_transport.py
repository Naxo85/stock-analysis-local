"""Lossless transport and frozen-contract tests; no model/network calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.local_runner.adaptive_context import (
    compact_json, model_context, pack_model_context, serialize_model_input, unpack_model_context,
)
from src.local_runner.adaptive_delta import deterministic_comparison
from src.local_runner.diff_transport import FIELD, VERSION, INSTRUCTIONS
from src.local_runner.financial_projection import model_input_view

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    old = {'as_of': '2026-10-20T12:00:00Z', 'latest_price': 100,
           'metrics': {'zero': 0, 'null': None, 'removed': 4, 'a/b~c': 1},
           'levels': {'supports': [{'level': 95, 'oi': 123}]}}
    new = deepcopy(old)
    new.update(as_of='2026-10-21T12:00:00Z', latest_price=99.99)
    new['metrics'].update(zero=None, null=0, added=None, **{'a/b~c': 2})
    del new['metrics']['removed']
    new['levels']['supports'][0]['oi'] = 0
    reference = {'slim_snapshot': old}
    context = {'routing_revision': 4, 'reference': reference,
               'sol_reference': deepcopy(reference), 'slim': new}
    context['comparison'] = {'deterministic': deterministic_comparison(context)}
    return context


class DiffTransportTests(unittest.TestCase):
    def test_exact_roundtrip_preserves_null_zero_absence_arrays_and_escaped_paths(self):
        data = fixture(); data[FIELD] = VERSION
        original = deepcopy(data)
        text = serialize_model_input(data)
        self.assertEqual(unpack_model_context(json.loads(text)), data)
        self.assertEqual(data, original)
        packed = json.loads(text)
        for row in packed['comparison']['deterministic']['since_current']['changes']:
            self.assertNotIn('previous', row)
            self.assertNotIn('current', row)

    def test_no_opt_in_keeps_legacy_serializer_exact(self):
        data = fixture()
        legacy = compact_json(pack_model_context(model_input_view(data)))
        self.assertEqual(serialize_model_input(data), legacy)
        self.assertNotIn(FIELD, json.loads(legacy))

    def test_literal_source_text_not_interpreted_as_diff(self):
        data = fixture(); data[FIELD] = VERSION
        data['news'] = {'items': [{'previous_pointer': '/slim/nope',
                                  'previous_present': True, 'previous': 'literal text'}]}
        self.assertEqual(unpack_model_context(json.loads(serialize_model_input(data))), data)

    def test_mismatch_missing_origin_and_wrong_scope_fail_before_model(self):
        for mutation in ('value', 'missing', 'scope', 'flag', 'null_type'):
            data = fixture(); data[FIELD] = VERSION
            row = data['comparison']['deterministic']['since_current']['changes'][0]
            if mutation == 'value': row['current'] = 'invented'
            if mutation == 'missing': row['current_pointer'] = '/slim/does_not_exist'
            if mutation == 'scope': row['current_pointer'] = '/reference/slim_snapshot/latest_price'
            if mutation == 'flag': row['current_present'] = 1
            if mutation == 'null_type': row['current'] = False
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                serialize_model_input(data)

    def test_unknown_version_and_copied_values_in_compact_input_are_rejected(self):
        data = fixture(); data[FIELD] = 'future'
        with self.assertRaisesRegex(ValueError, 'unsupported_context_transport'):
            serialize_model_input(data)
        data[FIELD] = VERSION
        packed = json.loads(serialize_model_input(data))
        packed['comparison']['deterministic']['since_current']['changes'][0]['current'] = 123
        with self.assertRaisesRegex(ValueError, 'unexpected_value_copy'):
            unpack_model_context(packed)

    def test_present_null_cannot_be_mislabeled_absent(self):
        data = fixture(); data[FIELD] = VERSION
        rows = data['comparison']['deterministic']['since_current']['changes']
        row = next(r for r in rows if r['current_pointer'] == '/slim/metrics/zero')
        self.assertIsNone(row['current'])
        row['current_present'] = False
        with self.assertRaisesRegex(ValueError, 'presence_mismatch'):
            serialize_model_input(data)

    def test_real46_inputs_roundtrip_and_original_receipts_stay_bound(self):
        folder = ROOT / 'logs/batch/2026-10-21/06-52-46/adaptive'
        files = sorted(folder.glob('*/triage.input.json'))
        if not files: self.skipTest('local historical corpus unavailable')
        self.assertEqual(len(files), 46)
        for file in files:
            with self.subTest(ticker=file.parent.name):
                raw = file.read_bytes()
                receipt = json.loads(file.with_name('triage.receipt.json').read_text(encoding='utf-8'))
                self.assertEqual(hashlib.sha256(raw).hexdigest(), receipt['input_sha256'])
                context = unpack_model_context(json.loads(raw))
                legacy = compact_json(pack_model_context(model_input_view(context)))
                self.assertEqual(serialize_model_input(context), legacy)
                context[FIELD] = VERSION
                packed = serialize_model_input(context)
                self.assertEqual(unpack_model_context(json.loads(packed)), model_input_view(context))
                self.assertEqual(file.read_bytes(), raw)

    def test_stage_selects_only_frozen_maintenance_opt_in_including_repair(self):
        from src.local_runner import adaptive_stage as stage
        from src.local_runner.adaptive_policy import load_policy
        for kind, enabled in [('triage', True), ('triage_repair', True), ('report', True), ('triage', False)]:
            with self.subTest(kind=kind, enabled=enabled), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); work = root / 'T'; work.mkdir()
                (work/'instructions.md').write_text('frozen full', encoding='utf-8')
                (work/'triage_instructions.md').write_text('frozen maintenance', encoding='utf-8')
                policy = load_policy(ROOT); policy.pop('maintenance_context_transport', None)
                if enabled: policy['maintenance_context_transport'] = VERSION
                context = fixture(); context['symbol'] = 'T'
                prepared_context = model_context(context)
                # Abort before admission, quota or any CLI call; inspect assembly.
                with patch.object(stage, 'model_context', return_value=prepared_context), \
                     patch.object(stage, 'reserve', side_effect=RuntimeError('STOP_BEFORE_MODEL')), \
                     patch.object(stage, 'triage_key', return_value='key') as key, \
                     patch.object(stage, 'load_triage', return_value=None), \
                     patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL')):
                    with self.assertRaisesRegex(RuntimeError, 'STOP_BEFORE_MODEL'):
                        stage.model_call(root, work, 'T', root/'budget.json', policy, kind, context)
                if kind == 'triage':
                    assembled, _, instructions, _, _ = key.call_args.args
                    self.assertEqual(assembled.get(FIELD), VERSION if enabled else None)
                    self.assertEqual(INSTRUCTIONS in instructions, enabled)
                self.assertEqual(prepared_context.get(FIELD), VERSION if enabled and kind != 'report' else None)
                self.assertNotIn(FIELD, context)

    def test_compact_receipt_recovery_uses_frozen_contract_and_rejects_migration(self):
        from src.local_runner import adaptive_stage as stage
        from src.local_runner.adaptive_policy import load_policy, validate_policy
        for kind in ['triage', 'triage_repair']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);work=root/'T';work.mkdir()
                (work/'triage_instructions.md').write_text('frozen instructions',encoding='utf-8')
                policy=load_policy(ROOT);policy['maintenance_context_transport']=VERSION
                context=fixture();context['symbol']='T'
                def fake(**kwargs):
                    text='{}'
                    receipt={'exit_code':0,'usage':{'input_tokens':1,'output_tokens':1},
                        'model':kwargs['model'],'reasoning_effort':kwargs['effort'],
                        'research_enabled':kwargs['research'],
                        'input_sha256':hashlib.sha256(serialize_model_input(kwargs['data']).encode()).hexdigest(),
                        'instructions_sha256':hashlib.sha256(kwargs['instructions'].encode()).hexdigest(),
                        'schema_sha256':hashlib.sha256(json.dumps(kwargs['schema'],sort_keys=True).encode()).hexdigest(),
                        'response_sha256':hashlib.sha256(text.encode()).hexdigest()}
                    (work/(kind+'.response')).write_text(text,encoding='utf-8')
                    (work/(kind+'.receipt.json')).write_text(json.dumps(receipt),encoding='utf-8')
                    return {**receipt,'text':text}
                with patch.object(stage,'reserve',return_value='T:'+kind) as reserve, \
                     patch.object(stage,'finish'),patch.object(stage,'load_triage',return_value=None), \
                     patch.object(stage,'save_triage'),patch.object(stage,'call_codex',side_effect=fake) as cli:
                    first=stage.model_call(root,work,'T',root/'budget.json',policy,kind,context)
                    second=stage.model_call(root,work,'T',root/'budget.json',policy,kind,context)
                    self.assertEqual(first,second)
                    self.assertEqual(cli.call_count,1)
                    self.assertEqual(reserve.call_count,1)
                    legacy={k:v for k,v in policy.items() if k!='maintenance_context_transport'}
                    with self.assertRaisesRegex(RuntimeError,'context_mismatch'):
                        stage.model_call(root,work,'T',root/'budget.json',legacy,kind,context)
                with self.assertRaisesRegex(ValueError,'unsupported_maintenance_context_transport'):
                    validate_policy({**policy,'maintenance_context_transport':'typo'})


if __name__ == '__main__': unittest.main()
