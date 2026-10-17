"""Offline regressions: real receipts remain immutable; model judgments are mocked.

These tests prove contract/routing/data preservation, not that a future model
will correctly assess every news item or support failure.
"""
from copy import deepcopy
from pathlib import Path
from contextlib import ExitStack
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

import test_review_contract_v18 as v18
from src.local_runner.adaptive_context import model_context, serialize_model_input, unpack_model_context
from src.local_runner.adaptive_maintenance import maintenance_schema
from src.local_runner.adaptive_policy import daily_decision
from src.local_runner.adaptive_policy import maintenance_precheck
from src.local_runner.adaptive_repair import repair_context
from src.local_runner.review_contract import coverage_issues, review_agenda
from src.local_runner.semantic_report import reference_document, render_document, check_schema

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / 'logs/batch/2026-10-08/13-42-25/adaptive'
v14, v15, v16, prior = v18.v14, v18.v15, v18.v16, v18.prior


def context():
    data = v18.context()
    data['routing_revision'] = 19
    return model_context(data)


def candidate(data, decision='update'):
    value = v18.candidate(data, decision)
    if value['update'] is not None:
        value['update']['change_review']['plan_explanation'] = None
    return value


def explanation(data):
    old = reference_document(data['reference'])
    return dict(setup_reason=old['summary']['setup_reason'], conclusion=old['conclusion'],
                reasons={key: block['reason'] for key, block in old['plan'].items()})


def correction(data):
    value = candidate(data)
    value['update']['plan_explanation'] = explanation(data)
    value['update']['plan_explanation']['reasons']['target'] = 'Salida antes de la resistencia seleccionada.'
    value['update']['change_review']['plan_explanation'] = dict(basis='prior_error',
        scope='routine_technical', previous_evidence=['/reference/semantic_data/plan/target'],
        current_evidence=['/reference/semantic_data/plan/resistance'],
        explanation='El motivo heredado del objetivo contradice la resistencia ya seleccionada.')
    return value


def read(ticker, name='input.json'):
    path = ARCHIVE / ticker / name
    if not path.exists():
        raise unittest.SkipTest('Original local archive not available')
    return json.loads(path.read_bytes())


class CoverageTests(unittest.TestCase):
    def empty(self):
        data = context(); data['news']['items'] = []
        return data, dict(news_review=[dict(items=[], assessment='Nada pendiente.',
            outcome='no_action', event_status='not_applicable')])

    def test_empty_no_work_is_not_a_failure_or_coverage(self):
        data, value = self.empty()
        self.assertEqual(review_agenda(data), [])
        self.assertFalse(coverage_issues(value, data))
        saved = v18.record(data, value)
        self.assertFalse(review_agenda(saved))
        self.assertFalse(saved['reference']['review_memory']['data']['coverage'])
        data['routing_revision'] = 18
        self.assertTrue(coverage_issues(value, data))  # frozen contract stays exact

    def test_empty_observation_never_covers_real_pending_articles(self):
        data, value = self.empty()
        data['news']['items'] = [{'headline': 'Relevant supplied article'}]
        self.assertIn('Unaddressed items', str(coverage_issues(value, data)))
        value['news_review'] += v18.coverage(data)
        self.assertFalse(coverage_issues(value, data))

    def test_original_usar_initial_retain_needs_no_model_repair(self):
        data, value = read('USAR'), read('USAR', 'triage.json')
        before = deepcopy((data, value))
        self.assertTrue(coverage_issues(value, data))
        upgraded = deepcopy(data); upgraded['routing_revision'] = 19
        self.assertFalse(review_agenda(upgraded))
        self.assertFalse(coverage_issues(value, upgraded))
        self.assertEqual(daily_decision(value, [], model_context(upgraded)), 'retain')
        self.assertEqual((data, value), before)

    def test_unknown_future_event_is_not_invented_or_accepted(self):
        data = read('USAR'); data['routing_revision'] = 19
        value = read('USAR', 'triage_repair.json')
        self.assertIn('Unknown or duplicate item: e1', str(coverage_issues(value, data)))
        repaired = repair_context(model_context(data), value, 'coverage')
        self.assertIn('news_review=[]', repaired['maintenance_repair']['instruction'])
        self.assertIn('evento futuro', repaired['maintenance_repair']['instruction'])

    def test_empty_group_never_hides_a_declared_material_risk(self):
        data, group = self.empty(); value = candidate(data, 'retain')
        value['news_review'] = group['news_review']
        value['news_review'][0]['outcome'] = 'critical_change'
        self.assertTrue(coverage_issues(value, data))
        self.assertEqual(daily_decision(value, [], data), 'escalate')

    def test_duplicate_and_omitted_real_handles_still_rejected(self):
        data = context(); value = candidate(data, 'retain')
        value['news_review'][0]['items'] *= 2
        self.assertIn('duplicate', str(coverage_issues(value, data)))
        value['news_review'] = []
        self.assertIn('Unaddressed', str(coverage_issues(value, data)))


class CoherenceTests(unittest.TestCase):
    def test_text_only_correction_preserves_financial_authority(self):
        data = context(); value = correction(data)
        before = deepcopy(value); old = reference_document(data['reference'])
        check_schema(value, maintenance_schema(data))
        doc = v14.v3.document(data, value)
        for key in old['plan']:
            for field in ('range', 'strength'):
                self.assertEqual(doc['plan'][key][field], old['plan'][key][field])
            if key != 'target': self.assertEqual(doc['plan'][key]['reason'], old['plan'][key]['reason'])
        self.assertEqual(doc['summary'], old['summary'])
        self.assertEqual(doc['catalysts'], old['catalysts'])
        self.assertEqual(doc['next_event'], old['next_event'])
        self.assertIn('plan_explanation', doc['commentary_change_review'])
        self.assertNotIn('resolved_evidence', render_document(doc))
        self.assertEqual(value, before)

    def test_original_nbis_can_reconcile_all_stale_text_without_price_edit(self):
        raw = read('NBIS'); raw['routing_revision'] = 19
        data = model_context(raw); value = correction(data)
        old = reference_document(data['reference'])
        self.assertIn('270', old['plan']['target']['reason'])
        self.assertEqual(old['plan']['resistance']['range']['upper'], 250)
        value['update']['plan_explanation']['conclusion'] = read('NBIS', 'triage.json')['update']['conclusion']
        doc = v14.v3.document(data, value)
        self.assertNotIn('270', doc['plan']['target']['reason'])
        # An explicitly dated correction may mention the OLD 270; it is not
        # an active-level assertion. Never turn this into a prose-token gate.
        self.assertEqual(doc['conclusion'], value['update']['plan_explanation']['conclusion'])
        for key in old['plan']:
            self.assertEqual(doc['plan'][key]['range'], old['plan'][key]['range'])
            self.assertEqual(doc['plan'][key]['strength'], old['plan'][key]['strength'])

    def test_no_rewrite_without_actual_prior_error_rationale(self):
        for review in (None, dict(basis='material_improvement', scope='routine_technical',
                previous_evidence=['/reference'], current_evidence=['/slim'], explanation='Prefer another wording')):
            data = context(); value = correction(data)
            value['update']['change_review']['plan_explanation'] = review
            with self.subTest(review=review), self.assertRaises(ValueError):
                v14.v3.document(data, value)

    def test_sources_are_resolved_not_merely_declared(self):
        data = context(); value = correction(data)
        value['update']['change_review']['plan_explanation']['current_evidence'] = ['/reference/nonexistent']
        with self.assertRaisesRegex(ValueError, 'missing_source'):
            v14.v3.document(data, value)

    def test_risk_disguised_as_prose_still_requires_sol(self):
        data = context(); value = correction(data)
        value['update']['change_review']['plan_explanation']['scope'] = 'fundamental_or_structural'
        self.assertEqual(daily_decision(value, [], data), 'escalate')
        with self.assertRaisesRegex(ValueError, 'uncertain_or_critical'):
            v14.v3.document(data, value)

    def test_numeric_and_score_fields_cannot_be_smuggled_in_explanation(self):
        for field in ('management_stop', 'structural_stop', 'setup_score', 'thesis_score'):
            data = context(); value = correction(data)
            value['update']['plan_explanation'][field] = 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                v14.v3.document(data, value)

    def test_range_reconciliation_needs_no_duplicate_review(self):
        data, value = v18.PlanCoherenceTests().proposal(context())
        value['update']['change_review']['plan_explanation'] = None
        value['update']['plan_explanation'] = v18.PlanCoherenceTests().explanation(data)
        doc = v14.v3.document(data, value)
        self.assertEqual(doc['plan']['resistance']['range']['lower'], 120)

    def test_duplicate_prose_authority_still_rejected(self):
        data = context(); value = correction(data)
        value['update']['conclusion'] = 'Another conclusion'
        value['update']['change_review']['conclusion'] = v15.commentary_review('conclusion')
        with self.assertRaisesRegex(ValueError, 'plan_coherence'):
            v14.v3.document(data, value)


class MemoryPolicyTests(unittest.TestCase):
    def test_mrna_research_can_be_retained_without_republishing(self):
        data = read('MRNA'); data['routing_revision'] = 19
        # Human-authored alternate judgment, NOT a prediction of a live model.
        value = read('MRNA', 'triage.json')
        value.update(decision='retain', update=None, routine_note='')
        for group in value['news_review']: group['outcome'] = 'no_action'
        value['news']['assessment'] = 'Filing clarification of old headline; CURRENT never asserted an open-market purchase.'
        before = deepcopy(data['reference'])
        saved = v18.record(data, value)
        after = saved['reference']
        self.assertEqual({k: v for k, v in after.items() if k != 'review_memory'},
                         {k: v for k, v in before.items() if k != 'review_memory'})
        self.assertFalse(coverage_issues(value, data))
        self.assertTrue(after['review_memory']['data']['coverage'])
        self.assertEqual(daily_decision(value, [], model_context(data)), 'retain')

    def test_iren_quote_alone_does_not_force_relocation_or_sol(self):
        path = ROOT / 'logs/adaptive_individual/20261008T135951761832/IREN/input.json'
        if not path.exists(): self.skipTest('IREN original receipt absent')
        data = json.loads(path.read_bytes())
        self.assertLess(data['slim']['latest_price'], data['reference']['plan']['ambitious_entry']['lower'])
        for revision in (18, 19):
            guards = maintenance_precheck(data['reference'], data['slim'], data['sol_reference'],
                owned=False, revision=revision)['guards']
            self.assertNotIn('price_move_ge_8pct_since_report', guards)
            self.assertNotIn('price_below_management_stop', guards)
        prompt = (ROOT / 'prompts/adaptive_revision19.md').read_text(encoding='utf8')
        for principle in ('OPERABILITY BEFORE CONTINUITY', 'Historical origin, current support behavior',
                          'stop above a long', 'ambitious_entry=null', 'completed sessions',
                          'not proof of current support', 'do not infer a sale'):
            self.assertIn(principle, prompt)

    def test_revision19_schema_stable_and_frozen18_schema_unchanged(self):
        a = maintenance_schema(context()); b = maintenance_schema({**context(), 'symbol': 'IREN'})
        self.assertEqual(a, b)
        self.assertNotIn('plan_explanation', v18.candidate(v18.context())['update']['change_review'])
        view = context()
        self.assertEqual(serialize_model_input(view), serialize_model_input(model_context(view)))

    def test_frozen18_input_receipts_are_byte_exact(self):
        paths = list(ARCHIVE.glob('*/triage.input.json'))
        if not paths: self.skipTest('Original local archive absent')
        for path in paths:
            with self.subTest(ticker=path.parent.name):
                sent = unpack_model_context(json.loads(path.read_bytes()))
                raw = json.loads(path.with_name('input.json').read_bytes())
                for key in ('guards', 'review_flags', 'itv'):
                    if key in sent: raw[key] = sent[key]
                raw.pop('research_memory', None)
                receipt = json.loads(path.with_name('triage.receipt.json').read_bytes())
                self.assertEqual(hashlib.sha256(serialize_model_input(model_context(raw)).encode()).hexdigest(),
                                 receipt['input_sha256'])


class PipelineTests(unittest.TestCase):
    def run_case(self, choices=('retain',), *, due=False, empty=False):
        original_verdict, original_full = prior.verdict, prior.full
        actions = iter(choices)
        def verdict(data, decision='update'):
            choice = next(actions)
            with patch.object(prior, 'verdict', original_verdict):
                value = candidate(data, 'retain')
                if choice == 'correction': value = correction(data)
                if choice == 'news':
                    value = v16.note(data, 'New relevant factual clarification.')
                    value['update']['change_review']['plan_explanation'] = None
                    value['update']['plan_explanation'] = None
                    value['news_review'] = v18.coverage(data)
            if choice == 'missing': value['news_review'] = []
            if empty:
                value['news_review'] = [dict(items=[], assessment='No pending news.',
                    outcome='no_action', event_status='not_applicable')]
            return value
        def full(data):
            value = original_full(data)
            for level in value['plan'].values():
                level['evidence'] = [v14.handle(model_context(data), '/slim/levels/supports/0')]
            return value
        raw = prior.data()
        raw['news']['items'] = [] if empty else [{'articleId': 'one', 'headline': 'Results announced'}]
        with patch.object(prior, 'data', return_value=raw), patch.object(prior, 'verdict', side_effect=verdict), \
             patch.object(prior, 'full', side_effect=full):
            return prior.SemanticPipelineTests().run_case(revision=19, due=due)

    def test_empty_agenda_retains_with_one_call_no_repair(self):
        review, payload, calls = self.run_case(empty=True)
        self.assertEqual(review['status'], 'retained')
        self.assertEqual([kind for kind, _ in calls], ['triage'])

    def test_retention_news_coherence_and_itv_call_counts_unchanged(self):
        for choices, due, status, expected in [
            (('retain',), False, 'retained', ['triage']),
            (('news',), False, 'updated', ['triage']),
            (('correction',), False, 'updated', ['triage']),
            ((), True, 'regenerated', ['report'])]:
            with self.subTest(status=status, choices=choices):
                review, _, calls = self.run_case(choices, due=due)
                self.assertEqual(review['status'], status)
                self.assertEqual([kind for kind, _ in calls], expected)

    def test_real_missing_coverage_still_has_one_repair_not_silent_retain(self):
        review, _, calls = self.run_case(('missing', 'retain'))
        self.assertEqual(review['status'], 'retained')
        self.assertEqual([kind for kind, _ in calls], ['triage', 'triage_repair'])
        with self.assertRaisesRegex(RuntimeError, 'review_contract_failed_no_sol'):
            self.run_case(('missing', 'missing'))

    def test_new_policy_frozen_for_both_models_only(self):
        data = context(); stage = v16.stage
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            work = Path(directory) / 'CAT'; work.mkdir()
            stack.enter_context(patch.object(stage, 'datetime', prior.base.FrozenClock))
            for name, value in {'load_policy': {**prior.base.POLICY, 'routing_revision': 19},
                'load_reference_payload': data['sol_reference'], 'load_current_report': data['reference'],
                'load_research': None}.items(): stack.enter_context(patch.object(stage, name, return_value=value))
            for name, value in {'_fetch_slim': data['slim'], '_load_analyst_quality': {},
                'load_compact_analyst_summary': {}, 'load_recent_analyst_actions': data['analyst_actions'],
                'load_recent_news': data['news'], '_load_system_prompt': 'legacy'}.items():
                stack.enter_context(patch.object(stage.one, name, return_value=value))
            stack.enter_context(patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL')))
            stage.prepare(ROOT, work, 'CAT', False, 'tracking')
            for name in ('instructions.md', 'triage_instructions.md'):
                text = (work / name).read_text(encoding='utf8')
                self.assertIn('REVISION19', text)
                self.assertNotIn('REVISION18', text)
                self.assertIn('REVIEW IS NOT PUBLICATION', text)
                self.assertIn('OPERABILITY BEFORE CONTINUITY', text)


if __name__ == '__main__': unittest.main()
