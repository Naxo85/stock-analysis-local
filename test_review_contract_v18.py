"""Offline contract tests; archived incidents are read only, no model calls."""
from copy import deepcopy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_review_continuity_v16 as v16
from src.local_runner.adaptive_context import model_context, serialize_model_input, unpack_model_context
from src.local_runner.adaptive_policy import maintenance_precheck, daily_decision
from src.local_runner.adaptive_maintenance import maintenance_schema
from src.local_runner.review_contract import review_agenda, coverage_issues, review_contract_only
from src.local_runner.review_memory import build_memory, read_memory
from src.local_runner.semantic_report import reference_document, render_document
from src.local_runner.semantic_sources import raise_issues

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / 'logs/batch/2026-10-08'
v15 = v16.v15
v14 = v15.v14
prior = v14.prior


def context():
    data = v16.context()
    data['routing_revision'] = 18
    data['news']['items'] = [{'articleId': 'a', 'headline': 'Supplier published results'}]
    return data


def coverage(data, status='not_applicable'):
    agenda = review_agenda(data)
    return [{'items': [row['id'] for row in agenda],
             'assessment': 'Related items evaluated; no change in the issuer decision.',
             'outcome': 'no_action', 'event_status': status}] if agenda else []


def candidate(data, decision='update'):
    value = v15.candidate(model_context(data))
    value['news_review'] = coverage(data)
    value['update']['plan_explanation'] = None
    if decision == 'retain':
        value.update(decision='retain', update=None)
    return value


def record(data, value, at='2026-10-03T12:00:00Z', status='retained'):
    data = deepcopy(data)
    data['triage'] = value
    payload = deepcopy(data['reference'])
    payload['review_memory'] = build_memory(data, payload, {'status': status, 'reviewed_at': at})
    data['reference'] = payload
    return data


class ReviewContractTests(unittest.TestCase):
    def test_generic_summary_does_not_mark_feed_reviewed(self):
        data = context(); value = candidate(data, 'retain'); value['news_review'] = []
        self.assertTrue(coverage_issues(value, data))
        saved = record(data, value)
        self.assertTrue(review_agenda(saved)[0]['required'])
        self.assertFalse(model_context(saved)['news']['prior_reviews']['current_items'][0]['previously_assessed_exact_content'])

    def test_legacy_seen_receipt_not_an_item_assessment_after_upgrade(self):
        data = context(); data['routing_revision'] = 17
        data = record(data, {'news': {'assessment': 'Generic summary'}})
        self.assertTrue(model_context(data)['news']['prior_reviews']['current_items'][0]['previously_assessed_exact_content'])
        data['routing_revision'] = 18
        self.assertTrue(review_agenda(data)[0]['required'])

    def test_exact_grouped_coverage_persists_but_changed_content_is_new(self):
        data = context(); data['news']['items'] *= 2
        value = candidate(data, 'retain')
        self.assertEqual(len(review_agenda(data)), 1)
        self.assertFalse(coverage_issues(value, data))
        data = record(data, value)
        self.assertFalse(review_agenda(data)[0]['required'])
        data['news']['items'][0] = {**data['news']['items'][0], 'headline': 'Changed guidance'}
        agenda = review_agenda(data)
        self.assertTrue(agenda[0]['required']); self.assertFalse(agenda[1]['required'])

    def test_unresolved_is_not_settled_or_automatically_critical(self):
        data = context(); value = candidate(data, 'retain')
        value['news_review'][0]['outcome'] = 'unresolved'
        self.assertEqual(daily_decision(value, [], model_context(data)), 'retain')
        data = record(data, value)
        self.assertTrue(review_agenda(data)[0]['required'])
        value['news_review'][0]['outcome'] = 'critical_change'
        self.assertEqual(daily_decision(value, [], model_context(data)), 'escalate')
        value['evidence_gap'] = 'essential_data'
        self.assertEqual(daily_decision(value, [], model_context(data)), 'blocked')

    def test_latest_retain_snapshot_separate_from_report_date_and_anchor(self):
        data = context(); old = deepcopy(data['reference'])
        data = record(data, candidate(data, 'retain'))
        data['slim']['latest_price'] += 1
        view = model_context(data)
        reviewed = view['comparison']['latest_published_review']
        self.assertEqual(reviewed['slim_snapshot']['latest_price'], data['slim']['latest_price'] - 1)
        self.assertEqual(reviewed['outcome'], 'retained')
        self.assertEqual(view['reference']['generated_at'], old['generated_at'])
        self.assertEqual(view['reference']['analysis_markdown'], old['analysis_markdown'])
        self.assertEqual(serialize_model_input(view), serialize_model_input(model_context(view)))

    def test_memory_stays_flat_and_retain_does_not_erase_assessment(self):
        data = context()
        for _ in range(5): data = record(data, candidate(data, 'retain'))
        memory = read_memory(data['reference'], data['sol_reference'])
        self.assertEqual(len(memory['coverage']), 1)
        self.assertNotIn('review_memory', json.dumps(memory))
        self.assertEqual(len(memory['reviews']), 1)

    def test_schema_stable_across_tickers_and_legacy_unchanged(self):
        data = context()
        self.assertEqual(maintenance_schema(data), maintenance_schema({'routing_revision': 18}))
        self.assertNotIn('news_review', maintenance_schema({'routing_revision': 17})['properties'])
        self.assertNotIn('key', model_context(data)['news']['review_agenda'][0])

    def test_mixed_nonfinancial_issues_do_not_route_sol_but_geometry_does(self):
        issues = [{'field': '/news_review', 'error': 'update_not_allowed_review_coverage: missing'},
                  {'field': '/plan', 'error': 'update_not_allowed_change_not_established: quote_only'}]
        try: raise_issues(issues)
        except ValueError as exc:
            self.assertTrue(review_contract_only(exc))
            exc.maintenance_details['issues'].append({'field': '/plan', 'error': 'update_not_allowed_target_below_entry'})
            self.assertFalse(review_contract_only(exc))


class PlanCoherenceTests(unittest.TestCase):
    def proposal(self, data=None):
        data = deepcopy(data) if data is not None else context()
        data['slim']['levels']['resistances'] = [{'level': 120}]
        view = model_context(data); value = candidate(view)
        block = prior.level({'lower': 120, 'upper': 120}); block.pop('transition')
        block['evidence'] = block['facts'] = [v14.handle(view, '/slim/levels/resistances/0')]
        block['change_review'] = v14.review(view, 'resistance')
        block['change_review']['current_evidence'] = block['evidence'][:]
        value['update']['plan']['resistance'] = block
        return view, value

    def explanation(self, data):
        old = reference_document(data['reference'])
        return {'setup_reason': 'Mismo juicio; resistencia seleccionada actualizada.',
                'conclusion': 'Esperar la entrada principal; salida antes de la resistencia seleccionada.',
                'reasons': {key: 'Fundamento conservado; coherente con la resistencia seleccionada.'
                            for key in old['plan']}}

    def test_changed_range_cannot_inherit_stale_dependent_explanations(self):
        data, value = self.proposal()
        with self.assertRaisesRegex(ValueError, 'plan_coherence'):
            v14.v3.document(data, value)
        value['update']['plan_explanation'] = self.explanation(data)
        doc = v14.v3.document(data, value); old = reference_document(data['reference'])
        self.assertEqual(doc['plan']['resistance']['range'], {'lower': 120, 'upper': 120})
        self.assertEqual(doc['conclusion'], value['update']['plan_explanation']['conclusion'])
        self.assertEqual(doc['plan']['target']['reason'], value['update']['plan_explanation']['reasons']['target'])
        for key in old['plan']:
            if key != 'resistance':
                for field in ('range', 'strength'):
                    self.assertEqual(doc['plan'][key][field], old['plan'][key][field])
        self.assertEqual(doc['summary']['setup_score'], old['summary']['setup_score'])
        self.assertNotIn('plan_explanation_review', render_document(doc))

    def test_no_explanation_rewrite_without_a_range_change(self):
        data = model_context(context()); value = candidate(data)
        value['update']['plan_explanation'] = self.explanation(data)
        with self.assertRaisesRegex(ValueError, 'plan_coherence'): v14.v3.document(data, value)

    def test_news_only_update_preserves_all_plan_text(self):
        data = model_context(context()); value = v16.note(data, 'A useful news clarification.')
        value['news_review'] = coverage(data); value['update']['plan_explanation'] = None
        doc = v14.v3.document(data, value); old = reference_document(data['reference'])
        self.assertEqual(doc['conclusion'], old['conclusion'])
        for key in old['plan']:
            self.assertEqual(doc['plan'][key]['reason'], old['plan'][key]['reason'])

    def test_setup_score_can_change_with_justification_and_one_prose_authority(self):
        data, value = self.proposal()
        value['update']['plan_explanation'] = self.explanation(data)
        value['update']['setup_score'] = 6.5
        value['update']['change_review']['setup'] = v15.commentary_review()
        doc = v14.v3.document(data, value)
        self.assertEqual(doc['summary']['setup_score'], 6.5)
        self.assertEqual(doc['summary']['setup_reason'], value['update']['plan_explanation']['setup_reason'])


class OriginalIncidentTests(unittest.TestCase):
    def read(self, batch, ticker, name='input.json'):
        path = ARCHIVE / batch / 'adaptive' / ticker / name
        if not path.exists(): self.skipTest('Optional original archive absent')
        return json.loads(path.read_bytes())

    def test_cifr_removes_both_percentage_routes_not_risk_guards(self):
        raw = self.read('11-31-14', 'CIFR')
        args = (raw['reference'], raw['slim'], raw['sol_reference'])
        self.assertIn('price_move_ge_8pct_since_report', maintenance_precheck(*args, owned=False, revision=17)['guards'])
        for price in (raw['slim']['latest_price'], raw['reference']['latest_price'] * 1.2,
                      raw['sol_reference']['latest_price'] * 1.2):
            slim = {**raw['slim'], 'latest_price': price}
            new = maintenance_precheck(raw['reference'], slim, raw['sol_reference'], owned=False, revision=18)
            self.assertNotIn('price_move_ge_8pct_since_report', json.dumps(new))
        sofi = self.read('11-31-14', 'SOFI')
        guards = maintenance_precheck(sofi['reference'], sofi['slim'], sofi['sol_reference'], owned=True, revision=18)['guards']
        self.assertIn('price_below_management_stop', guards)

    def test_mu_due_event_and_already_present_headline_need_explicit_review(self):
        raw = self.read('09-32-38', 'MU'); raw['routing_revision'] = 18
        agenda = review_agenda(raw)
        headline = next(row for row in agenda if row['kind'] == 'article'
                        and 'Samsung' in raw['news']['items'][int(row['id'][1:])-1].get('headline', '')
                        and 'Micron' in raw['news']['items'][int(row['id'][1:])-1].get('headline', ''))
        self.assertTrue(headline['required'])
        self.assertEqual(next(row for row in agenda if row['id'] == 'e1')['event']['date'], '2026-10-08')
        value = {'news_review': []}
        self.assertIn('e1', str(coverage_issues(value, raw)))
        value['news_review'] = coverage(raw, 'occurred')
        self.assertFalse(coverage_issues(value, raw))
        saved = record(raw, value)
        self.assertFalse(next(row for row in review_agenda(saved) if row['id'] == 'e1')['required'])
        value['news_review'] = coverage(raw, 'pending')
        pending = record(raw, value)
        self.assertTrue(next(row for row in review_agenda(pending) if row['id'] == 'e1')['required'])

    def test_nbis_retained_snapshot_exposes_existing_alternative(self):
        old = self.read('09-32-38', 'NBIS'); new = self.read('11-31-14', 'NBIS')
        old['routing_revision'] = 18
        saved = record(old, {'news_review': coverage(old, 'pending'), 'levels': {'assessment': 'Retained existing plan'}})
        new['reference'] = saved['reference']; new['routing_revision'] = 18
        view = model_context(new)['comparison']['latest_published_review']
        self.assertEqual(view['slim_snapshot'], old['slim'])
        self.assertEqual(view['assessments']['levels']['assessment'], 'Retained existing plan')
        self.assertIn('249.835', json.dumps(view['slim_snapshot']))

    def test_mu_event_status_does_not_mutate_protected_event(self):
        from src.local_runner.review_contract import record_event_assessment
        raw = self.read('11-31-14', 'MU'); raw['routing_revision'] = 18
        doc = reference_document(raw['reference']); before = deepcopy(doc['next_event'])
        record_event_assessment(doc, {'news_review': coverage(raw, 'occurred')}, raw)
        doc['metadata']['source_contract_revision'] = 18
        self.assertEqual(doc['next_event'], before)
        self.assertIn('ya ocurrido', render_document(doc))
        self.assertIn('antecedente fechado', render_document(doc))

    def test_frozen17_input_receipts_unchanged(self):
        paths = list((ARCHIVE / '11-31-14/adaptive').glob('*/triage.input.json'))
        if not paths: self.skipTest('Optional original archives absent')
        for path in paths:
            sent = unpack_model_context(json.loads(path.read_bytes()))
            raw = json.loads(path.with_name('input.json').read_bytes())
            for key in ('guards', 'review_flags', 'itv'):
                if key in sent: raw[key] = sent[key]
            raw.pop('research_memory', None)
            receipt = json.loads(path.with_name('triage.receipt.json').read_bytes())
            self.assertEqual(hashlib.sha256(serialize_model_input(model_context(raw)).encode()).hexdigest(), receipt['input_sha256'])


class PipelineTests(unittest.TestCase):
    def run_pipeline(self, responses=('retain',), *, due=False):
        original_verdict, original_full = prior.verdict, prior.full
        choices = iter(responses)
        def verdict(data, decision='update'):
            choice = next(choices)
            with patch.object(prior, 'verdict', original_verdict):
                value = candidate(data, 'retain')
            if choice == 'missing': value['news_review'] = []
            elif choice == 'absent': value.pop('news_review')
            elif choice == 'update':
                with patch.object(prior, 'verdict', original_verdict):
                    value = v16.note(data, 'Useful dated clarification.')
                value['news_review'] = coverage(data)
                value['update']['plan_explanation'] = None
            elif choice.startswith('move_'):
                with patch.object(prior, 'verdict', original_verdict):
                    view, value = PlanCoherenceTests().proposal(data)
                # Same frozen input as the mock runner, not a replacement receipt.
                value['news_review'] = coverage(data)
                if choice == 'move_valid':
                    value['update']['plan_explanation'] = PlanCoherenceTests().explanation(data)
                elif choice == 'move_bad_source':
                    value['update']['plan']['resistance']['evidence'] = ['s999999']
            return value
        def full(data):
            value = original_full(data)
            for level in value['plan'].values(): level['evidence'] = [v14.handle(model_context(data), '/slim/levels/supports/0')]
            return value
        raw = prior.data()
        raw['news']['items'] = [{'articleId': 'one', 'headline': 'Results announced'}]
        raw['slim']['levels']['resistances'] = [{'level': 120}]
        with patch.object(prior, 'data', return_value=raw), patch.object(prior, 'verdict', side_effect=verdict), \
             patch.object(prior, 'full', side_effect=full):
            return prior.SemanticPipelineTests().run_case(revision=18, due=due)

    def test_retain_update_itv_have_no_added_routine_calls(self):
        for responses, due, status, calls in [
            (('retain',), False, 'retained', ['triage']),
            (('update',), False, 'updated', ['triage']),
            ((), True, 'regenerated', ['report'])]:
            with self.subTest(status=status):
                review, payload, observed = self.run_pipeline(responses, due=due)
                self.assertEqual(review['status'], status)
                self.assertEqual([kind for kind, _ in observed], calls)
                self.assertIn('latest_review', payload['review_memory']['data'])

    def test_one_coverage_repair_also_for_retain(self):
        for missing in ('missing', 'absent'):
            review, payload, calls = self.run_pipeline((missing, 'retain'))
            self.assertEqual(review['status'], 'retained')
            self.assertEqual([kind for kind, _ in calls], ['triage', 'triage_repair'])
            self.assertIn('coverage', payload['review_memory']['data'])
            self.assertEqual(payload['generated_at'], prior.data()['reference']['generated_at'])

    def test_repeated_omission_stays_visible_not_paid_sol(self):
        with self.assertRaisesRegex(RuntimeError, 'review_contract_failed_no_sol'):
            self.run_pipeline(('missing', 'missing'))

    def test_range_edit_has_one_coherence_repair_or_can_be_withdrawn(self):
        for second, status in [('move_valid', 'updated'), ('retain', 'retained')]:
            review, _, calls = self.run_pipeline(('move_missing', second))
            self.assertEqual(review['status'], status)
            self.assertEqual([kind for kind, _ in calls], ['triage', 'triage_repair'])

    def test_source_and_coherence_errors_share_one_repair(self):
        review, _, calls = self.run_pipeline(('move_bad_source', 'move_valid'))
        self.assertEqual(review['status'], 'updated')
        self.assertEqual([kind for kind, _ in calls], ['triage', 'triage_repair'])
        issues = calls[1][1]['maintenance_repair']['validation_details']['issues']
        self.assertIn('unknown_source_handle', str(issues))
        self.assertIn('plan_coherence', str(issues))

    def test_preparation_freezes18_for_both_models(self):
        data = context(); stage = v16.stage
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            work = Path(directory) / 'CAT'; work.mkdir()
            stack.enter_context(patch.object(stage, 'datetime', prior.base.FrozenClock))
            for name, value in {'load_policy': {**prior.base.POLICY, 'routing_revision': 18},
                'load_reference_payload': data['sol_reference'], 'load_current_report': data['reference'],
                'load_research': None}.items(): stack.enter_context(patch.object(stage, name, return_value=value))
            for name, value in {'_fetch_slim': data['slim'], '_load_analyst_quality': {},
                'load_compact_analyst_summary': {}, 'load_recent_analyst_actions': data['analyst_actions'],
                'load_recent_news': data['news'], '_load_system_prompt': 'legacy'}.items():
                stack.enter_context(patch.object(stage.one, name, return_value=value))
            stack.enter_context(patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL')))
            stage.prepare(ROOT, work, 'CAT', False, 'tracking')
            for name in ('instructions.md', 'triage_instructions.md'):
                self.assertIn('REVISION18', (work / name).read_text(encoding='utf8'))


if __name__ == '__main__': unittest.main()
