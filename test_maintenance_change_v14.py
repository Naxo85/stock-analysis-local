"""Offline revision14 cases; copied fixtures are not model predictions or receipts."""
from copy import deepcopy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests'))
import test_semantic_report as prior
import test_semantic_contract_v3 as v3
import test_stable_maintenance as sparse
import test_semantic_sources as sources
from src.local_runner.adaptive_context import model_context, serialize_model_input
from src.local_runner.adaptive_maintenance import maintenance_schema
from src.local_runner.adaptive_policy import daily_decision
from src.local_runner.adaptive_repair import repair_context
from src.local_runner.maintenance_change import origin_observations, change_justification_only
from src.local_runner.semantic_report import reference_document, report_schema, _validate_geometry, digest
from src.local_runner.semantic_sources import source_catalog, raise_issues

BATCH = ROOT / 'logs/batch/2026-10-07/13-40-06/adaptive'

def context():
    data = prior.data(); data['routing_revision'] = 14
    return model_context(data)

def handle(data, pointer):
    return next(k for k, r in source_catalog(data).items() if r['pointer'] == pointer)

def review(data, key='entry', basis='prior_error'):
    return {'basis': basis, 'previous_evidence': [handle(data, '/reference/semantic_data/plan/' + key)],
        'current_evidence': [handle(data, '/slim/levels/supports/0')],
        'explanation': 'Error previo demostrado; comparación financiera.'}

def candidate(data, basis='prior_error'):
    payload = sparse.candidate(data); old = reference_document(data['reference'])
    block = prior.level(old['plan']['entry']['range']); block.pop('transition')
    block['evidence'] = block['facts'] = [handle(data, '/slim/levels/supports/0')]
    block['change_review'] = review(data, basis=basis)
    payload['update']['plan']['entry'] = block
    return payload

class ChangeReviewTests(unittest.TestCase):
    def test_supported_change_preserves_others_and_hides_audit(self):
        data = context(); value = candidate(data); original = deepcopy(value)
        doc = v3.document(data, value); before = reference_document(data['reference'])
        for key in ('ambitious_entry', 'target', 'resistance', 'structural_stop', 'management_stop'):
            for field in ('range', 'strength', 'reason'):
                self.assertEqual(doc['plan'][key][field], before['plan'][key][field])
        audit = doc['plan']['entry']['change_review']['resolved_evidence']['current_evidence'][0]
        self.assertEqual(audit['value_sha256'], digest(source_catalog(data)[audit['source']]['value']))
        self.assertNotIn('value', audit)
        self.assertNotIn('change_review', prior.render_document(doc))
        self.assertEqual(value, original)

    def test_unsupported_reason_rejects_valid_new_zone_and_same_zone_rescoring(self):
        for basis in ('missing_from_snapshot', 'quote_only', 'no_material_change', 'unresolved'):
            for zone in ({'lower': 80, 'upper': 82}, {'lower': 90, 'upper': 92}):
                data = context(); value = candidate(data, basis)
                value['update']['plan']['entry']['range'] = zone
                value['update']['plan']['entry']['strength']['components']['estructura'] = 8
                with self.subTest(basis=basis, zone=zone), self.assertRaisesRegex(ValueError, 'change_not_established'):
                    v3.document(data, value)

    def test_missing_wrong_scope_or_unrelated_previous_evidence_rejected(self):
        data = context()
        for field, selection in (('previous_evidence', []), ('current_evidence', []),
                ('previous_evidence', [handle(data, '/slim/levels/supports/0')]),
                ('current_evidence', [handle(data, '/reference/semantic_data/plan/entry')]),
                ('previous_evidence', [handle(data, '/reference/semantic_data/plan/target')])):
            value = candidate(data); value['update']['plan']['entry']['change_review'][field] = selection
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'change_not_established'):
                v3.document(data, value)

    def test_forged_catalog_rejected(self):
        data = context(); value = candidate(data)
        data['source_catalog']['s999999'] = {'pointer': '/slim/levels/supports/0', 'value': {'level': 90}}
        value['update']['plan']['entry']['change_review']['current_evidence'] = ['s999999']
        with self.assertRaisesRegex(ValueError, 'unknown_source_handle'): v3.document(data, value)

    def test_repair_has_exact_selectors_and_can_withdraw_edit(self):
        data = context(); feedback = repair_context(data, candidate(data), 'update_not_allowed_change_not_established')
        block = maintenance_schema(feedback)['properties']['update']['anyOf'][0]['properties']['plan']['properties']['entry']['anyOf'][0]
        for field in ('previous_evidence', 'current_evidence'):
            self.assertEqual(block['properties']['change_review']['properties'][field]['items']['enum'], list(source_catalog(data)))
        self.assertIn('POR QUE cambiar', feedback['maintenance_repair']['instruction'])
        self.assertIn('retain', feedback['maintenance_repair']['instruction'])

    def test_stable_schema_sol_unchanged_and_no_prose_gate(self):
        self.assertEqual(maintenance_schema({'routing_revision': 14}), maintenance_schema(context()))
        self.assertEqual(report_schema(14), report_schema(13))
        self.assertNotEqual(maintenance_schema({'routing_revision': 13}), maintenance_schema(context()))
        for text in ('Soporte: algo.', 'Soporte; algo', 'Ausente no prueba invalidez; error previo distinto.'):
            data = context(); value = candidate(data)
            value['update']['plan']['entry']['change_review']['explanation'] = text
            self.assertEqual(v3.document(data, value)['plan']['entry']['range'], {'lower': 90, 'upper': 92})

    def test_optional_absence_not_forced_by_any_lower_support(self):
        data = context(); plan = reference_document(data['reference'])['plan']
        plan['ambitious_entry']['range'] = None; plan['ambitious_entry']['strength'] = None
        _validate_geometry(plan, data)
        with self.assertRaisesRegex(ValueError, 'ambitious_entry_unavailable'):
            _validate_geometry(plan, {**data, 'routing_revision': 13})
        plan['target']['range'] = {'lower': 80, 'upper': 80}
        with self.assertRaisesRegex(ValueError, 'target_below_entry'): _validate_geometry(plan, data)

    def test_retain_never_overrides_risk_guards_or_missing_essential_data(self):
        data = context(); value = sparse.candidate(data); value.update(decision='retain', update=None)
        self.assertEqual(daily_decision(value, [], data), 'retain')
        self.assertEqual(daily_decision(value, ['guard'], data), 'escalate')
        value['risk']['structural_invalidation'] = True
        self.assertEqual(daily_decision(value, [], data), 'escalate')
        value['risk']['structural_invalidation'] = False; value['evidence_gap'] = 'essential_data'
        self.assertEqual(daily_decision(value, [], data), 'blocked')

    def test_mixed_financial_errors_are_not_declared_justification_only(self):
        try: raise_issues([{'field': '/plan/entry', 'error': 'update_not_allowed_change_not_established: entry'}])
        except ValueError as exc:
            self.assertTrue(change_justification_only(exc))
            exc.maintenance_details['issues'].append({'field': '/plan', 'error': 'update_not_allowed_target_below_entry'})
            self.assertFalse(change_justification_only(exc))

    def test_original_cat_cites_810_as_800_and_leu_absence_not_invalidation(self):
        for ticker in ('CAT', 'LEU'):
            folder = BATCH / ticker
            if not folder.exists(): self.skipTest('Optional fixtures absent')
            paths = [folder / n for n in ('input.json', 'triage.json', 'triage_repair.json', 'triage.receipt.json')]
            original = {p: p.read_bytes() for p in paths}
            data = json.loads(original[paths[0]]); data['routing_revision'] = 14
            view = model_context(data); observation = origin_observations(view)
            rows = observation['zones']['ambitious_entry']['current']
            self.assertIn('UNKNOWN status', observation['meaning'])
            if ticker == 'CAT':
                self.assertFalse(any(r['level'] == 800 and r['type'] == 'put_wall' for r in rows))
                self.assertTrue(any(r['level'] == 800 for r in observation['zones']['ambitious_entry']['previous']))
                selected = json.loads(original[paths[2]])['update']['plan']['ambitious_entry']['evidence'][0]
                self.assertEqual(source_catalog(view)[selected]['value']['level'], 810)
            else: self.assertFalse(any(r['level'] == 143.845 for r in rows))
            response = json.loads(original[paths[2]])
            # Human-labelled counterfactual COPY, not a real model14 response.
            response['update']['plan']['ambitious_entry']['change_review'] = review(view, 'ambitious_entry', 'missing_from_snapshot')
            with self.assertRaisesRegex(ValueError, 'change_not_established'): v3.document(view, response)
            self.assertEqual({p: p.read_bytes() for p in paths}, original)

    def test_frozen_13_input_receipts_exact(self):
        for ticker in ('CAT', 'LEU'):
            folder = BATCH / ticker
            if not folder.exists(): self.skipTest('Optional fixtures absent')
            data = json.loads((folder / 'input.json').read_bytes())
            observed = json.loads((folder / 'review.json').read_bytes())
            for field in ('guards', 'itv', 'review_flags'): data[field] = observed[field]
            view = model_context(data); view.pop('research_memory', None)
            receipt = json.loads((folder / 'triage.receipt.json').read_bytes())
            self.assertEqual(hashlib.sha256(serialize_model_input(view).encode()).hexdigest(), receipt['input_sha256'])

class PipelineTests(unittest.TestCase):
    def test_preparation_freezes_v6_without_changing_old_contracts(self):
        data = context(); stage = prior.stage
        originals = {p: p.read_bytes() for p in (ROOT / 'prompts').glob('*_v5.md')}
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            work = Path(directory) / 'CAT'; work.mkdir()
            replacements = {'datetime': prior.base.FrozenClock,
                'load_policy': {**prior.base.POLICY, 'routing_revision': 14},
                'load_reference_payload': data['sol_reference'], 'load_current_report': data['reference'],
                'load_research': None}
            for name, value in replacements.items():
                stack.enter_context(patch.object(stage, name, value) if name == 'datetime' else patch.object(stage, name, return_value=value))
            for name, value in {'_fetch_slim': data['slim'], '_load_analyst_quality': {},
                'load_compact_analyst_summary': {}, 'load_recent_analyst_actions': data['analyst_actions'],
                'load_recent_news': data['news'], '_load_system_prompt': 'LEGACY FORMAT'}.items():
                stack.enter_context(patch.object(stage.one, name, return_value=value))
            stack.enter_context(patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL')))
            stage.prepare(ROOT, work, 'CAT', False, 'tracking')
            for filename in ('instructions.md', 'triage_instructions.md'):
                text = (work / filename).read_text(encoding='utf8')
                self.assertIn('SEMANTIC OUTPUT CONTRACT v6', text)
                self.assertNotIn('pero convierte el nivel en huérfano', text)
            self.assertIn('CHANGE JUSTIFICATION', (work / 'triage_instructions.md').read_text(encoding='utf8'))
        self.assertEqual({p: p.read_bytes() for p in originals}, originals)

    def run_pipeline(self, bases, **kwargs):
        old_verdict, old_full = prior.verdict, prior.full; choices = iter(bases)
        def verdict(data, decision='update'):
            basis = next(choices)
            if basis == 'retain': return old_verdict(data, 'retain')
            result = old_verdict(data, decision)
            for name, block in (result.get('update') or {}).get('plan', {}).items():
                block['evidence'] = [handle(data, '/slim/levels/supports/0')]
                block['change_review'] = review(data, name, basis)
            return result
        def full(data):
            result = old_full(data)
            for block in result['plan'].values(): block['evidence'] = [handle(data, '/slim/levels/supports/0')]
            return result
        with patch.object(prior, 'verdict', side_effect=verdict), patch.object(prior, 'full', side_effect=full):
            return prior.SemanticPipelineTests().run_case(revision=14, **kwargs)

    def test_one_repair_can_retain_without_redating(self):
        result, output, calls = self.run_pipeline(['missing_from_snapshot', 'retain'])
        self.assertEqual(result['status'], 'retained')
        self.assertEqual([k for k, _ in calls], ['triage', 'triage_repair'])
        self.assertEqual(output['generated_at'], prior.data()['reference']['generated_at'])

    def test_repeat_unjustified_change_no_sol(self):
        with self.assertRaisesRegex(RuntimeError, 'change_justification_failed_no_sol'):
            self.run_pipeline(['missing_from_snapshot', 'missing_from_snapshot'])

    def test_supported_luna_change(self):
        result, _, calls = self.run_pipeline(['prior_error'])
        self.assertEqual(result['status'], 'updated'); self.assertEqual([k for k, _ in calls], ['triage'])

    def test_itv_calls_sol(self):
        result, _, calls = self.run_pipeline([], due=True)
        self.assertEqual(result['status'], 'regenerated'); self.assertEqual([k for k, _ in calls], ['report'])

    def test_mixed_financial_failure_keeps_sol_route(self):
        result, _, calls = self.run_pipeline(['missing_from_snapshot', 'missing_from_snapshot'], initial_bad=True, repair_bad=True)
        self.assertEqual(result['status'], 'regenerated')
        self.assertEqual([k for k, _ in calls], ['triage', 'triage_repair', 'report'])

if __name__ == '__main__': unittest.main()
