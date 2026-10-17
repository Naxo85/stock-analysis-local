"""Offline contracts and authored alternatives, never a claim of live model quality."""
from copy import deepcopy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_review_operability_v19 as v19
from src.local_runner.adaptive_context import model_context, serialize_model_input, unpack_model_context
from src.local_runner.adaptive_maintenance import maintenance_schema
from src.local_runner.adaptive_policy import daily_decision
from src.local_runner.semantic_report import reference_document, render_document, check_schema
from src.local_runner.maintenance_change import validate_change
from src.local_runner.adaptive_repair import repair_context

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / 'logs/batch/2026-10-08/14-53-35/adaptive'
v14, v16, prior = v19.v14, v19.v16, v19.prior


def context():
    data = v19.context(); data['routing_revision'] = 20
    return model_context(data)


def upgrade(value):
    value = deepcopy(value)
    text = value.pop('routine_note', '')
    if value['update'] is not None:
        change = value['update']
        review = change['change_review'].pop('routine_note')
        change['public_note'] = {'text': text, 'review': review} if text else None
    return value


def candidate(data, decision='update'):
    return upgrade(v19.candidate(data, decision))


def correction(data):
    value = upgrade(v19.correction(data))
    explanation = value['update']['plan_explanation']
    explanation['setup_reason'] = explanation['conclusion'] = None
    for key in explanation['reasons']:
        if key != 'target': explanation['reasons'][key] = None
    return value


def historical_review():
    return dict(basis='prior_error', scope='routine_technical',
        previous_evidence=['/reference/semantic_data/plan/entry'],
        current_evidence=['/reference/semantic_data/metadata'],
        explanation='Correct the internally contradictory dated claim, not the current quote.')


def read(ticker, name='input.json'):
    path = ARCHIVE / ticker / name
    if not path.exists(): raise unittest.SkipTest('Original local fixture absent')
    value = json.loads(path.read_bytes())
    if name == 'input.json':
        # Preflight adds these before the exact model receipt is frozen.
        sent = unpack_model_context(json.loads(path.with_name('triage.input.json').read_bytes()))
        for key in ('guards', 'review_flags', 'itv'):
            if key in sent: value[key] = sent[key]
    return value


class TextContractTests(unittest.TestCase):
    def document(self, data, value): return v14.v3.document(data, value)

    def test_schema_requires_atomic_note_and_has_no_ambiguous_root_note(self):
        data = context(); value = correction(data)
        check_schema(value, maintenance_schema(data))
        for kind in ('root', 'old_review', 'no_review', 'null_review'):
            bad = deepcopy(value)
            if kind == 'root': bad['routine_note'] = 'Internal comment'
            elif kind == 'old_review': bad['update']['change_review']['routine_note'] = None
            else:
                bad['update']['public_note'] = {'text': 'New note'}
                if kind == 'null_review': bad['update']['public_note']['review'] = None
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                check_schema(bad, maintenance_schema(data))

    def test_internal_reason_never_becomes_public_note_or_triggers_update(self):
        data = context(); value = candidate(data)
        value['reason'] = 'INTERNAL: no note needed, fixed nothing.'
        self.assertEqual(daily_decision(value, [], data), 'retain')
        value = correction(data); value['reason'] = 'INTERNAL: do not publish this.'
        self.assertNotIn('INTERNAL', render_document(self.document(data, value)))

    def test_partial_edit_inherits_other_financial_text_and_prices(self):
        data = context(); value = correction(data); before = deepcopy(value)
        old = reference_document(data['reference']); doc = self.document(data, value)
        self.assertEqual(doc['summary'], old['summary'])
        self.assertEqual(doc['conclusion'], old['conclusion'])
        self.assertIn('conclusion_provenance', doc)
        for key in old['plan']:
            for field in ('range', 'strength'):
                self.assertEqual(doc['plan'][key][field], old['plan'][key][field])
            if key != 'target':
                self.assertEqual(doc['plan'][key]['reason'], old['plan'][key]['reason'])
                self.assertNotIn('reason_reviewed_at', doc['plan'][key])
        self.assertEqual(doc['plan']['target']['reason_reviewed_at'], data['slim']['as_of'])
        self.assertEqual(value, before)  # The exact model response binding is not rewritten.

    def test_null_explanation_is_no_edit_and_independent_fields_do_not_conflict(self):
        data = context(); value = correction(data)
        value['update']['plan_explanation']['reasons']['target'] = None
        value['update']['change_review']['plan_explanation'] = None
        value['update']['public_note'] = dict(text='Historical correction.', review=historical_review())
        self.document(data, value)
        value = correction(data)
        value['update']['setup_reason'] = 'Independent setup correction, no score change.'
        value['update']['change_review']['setup'] = historical_review()
        self.assertEqual(self.document(data, value)['summary']['setup_reason'], value['update']['setup_reason'])

    def test_historical_change_proof_does_not_authorize_invented_level(self):
        data = context(); value = candidate(data)
        block = v14.candidate(data)['update']['plan']['entry']
        block['range'] = {'lower': 700, 'upper': 701}
        block['change_review']['current_evidence'] = [v14.handle(data, '/reference/semantic_data/plan/entry')]
        value['update']['plan']['entry'] = block
        with self.assertRaises(ValueError): self.document(data, value)

    def test_empty_or_identical_text_cannot_erase_or_redate_unchanged_content(self):
        data = context(); value = correction(data); old = reference_document(data['reference'])
        value['update']['plan_explanation']['conclusion'] = old['conclusion']
        value['update']['plan_explanation']['reasons']['entry'] = '  '
        doc = self.document(data, value)
        self.assertEqual(doc['plan']['entry']['reason'], old['plan']['entry']['reason'])
        self.assertIn('conclusion_provenance', doc)

    def test_historical_proof_applies_to_all_commentary_fields(self):
        for key in ('public_note', 'setup', 'conclusion'):
            data = context(); value = candidate(data); change = value['update']
            if key == 'public_note':
                change[key] = dict(text='Dated factual correction.', review=historical_review())
            else:
                change['setup_reason' if key == 'setup' else key] = 'Dated factual correction.'
                change['change_review'][key] = historical_review()
            with self.subTest(key=key):
                doc = self.document(data, value)
                self.assertEqual(doc['summary']['setup_score'], reference_document(data['reference'])['summary']['setup_score'])

    def test_old_proof_is_not_current_backing_and_unknown_paths_still_fail(self):
        for kind, error in (('backing_changed', 'wrong_scope_current_evidence'),
                            ('missing', 'missing_source')):
            data = context(); value = candidate(data); review = historical_review()
            if kind == 'backing_changed': review['basis'] = kind
            else: review['current_evidence'] = ['/reference/nonexistent']
            value['update']['public_note'] = dict(text='Correction.', review=review)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, error):
                self.document(data, value)

    def test_protected_note_and_protected_numeric_changes_still_rejected(self):
        data = context(); value = candidate(data); review = historical_review()
        review['scope'] = 'fundamental_or_structural'
        value['update']['public_note'] = dict(text='Structural risk.', review=review)
        self.assertEqual(daily_decision(value, [], data), 'escalate')
        with self.assertRaises(ValueError): self.document(data, value)
        for field in ('management_stop', 'structural_stop', 'setup_score', 'thesis_score'):
            value = correction(data); value['update']['plan_explanation'][field] = 10
            with self.subTest(field=field), self.assertRaises(ValueError): self.document(data, value)

    def test_level_prior_error_can_use_historical_proof_but_not_backing_change(self):
        data = context()
        handle = v14.handle(data, '/reference/semantic_data/plan/entry')
        level = {'change_review': dict(basis='prior_error', previous_evidence=[handle],
                 current_evidence=[handle], explanation='Historical correction, not a new live origin.')}
        validate_change(level, 'entry', data)
        # The prior ENTRY remains the decision being changed; another dated
        # block may prove a relational error in that decision.
        level['change_review']['current_evidence'] = [v14.handle(data, '/reference/semantic_data/plan/target')]
        validate_change(level, 'entry', data)
        level['change_review']['basis'] = 'backing_changed'
        with self.assertRaisesRegex(ValueError, 'wrong_scope_current_evidence'):
            validate_change(level, 'entry', data)

    def test_note_null_preserves_original_note_date_across_multiple_updates(self):
        data = context(); value = candidate(data)
        value['update']['public_note'] = dict(text='Historical factual clarification.', review=historical_review())
        first = self.document(data, value)
        note_at = first['routine_note_at']
        for day in ('2026-10-04T12:00:00Z', '2026-10-05T12:00:00Z'):
            data['reference'] = v16.published(data, first); data['slim']['as_of'] = day
            data = model_context(data)
            first = self.document(data, correction(data))
            self.assertEqual(first['routine_note'], 'Historical factual clarification.')
            self.assertEqual(first['routine_note_at'], note_at)
            self.assertIn(str(note_at)[:10], render_document(first))
        view = model_context({**data, 'reference': v16.published(data, first)})
        self.assertEqual(view['reference']['semantic_data']['routine_note_at'], note_at)

    def test_routine_news_memory_survives_no_note_edit(self):
        data = context(); value = candidate(data)
        review = historical_review(); review['scope'] = 'routine_news'
        value['update']['public_note'] = dict(text='Tax withholding, not open-market sale.', review=review)
        first = self.document(data, value); data['reference'] = v16.published(data, first)
        next_doc = self.document(model_context(data), correction(model_context(data)))
        self.assertEqual(next_doc['news_note'], first['news_note'])
        self.assertEqual(render_document(next_doc).count('Tax withholding'), 1)


class IncidentTests(unittest.TestCase):
    def test_both_original_amat_attempts_remain_failed_and_immutable(self):
        data = model_context(read('AMAT'))
        for name, expected in (('triage.json', 'wrong_scope_current_evidence'),
                               ('triage_repair.json', 'missing_review')):
            value = read('AMAT', name); before = deepcopy(value)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, expected):
                v14.v3.document(data, value)
            self.assertEqual(value, before)

    def test_authored_amat_correction_keeps_valid_historical_comparison(self):
        # Not an automatic conversion or a simulated live judgment: the first
        # proposal misread A -> B as a wrong current price. Fix only the genuine
        # same-snapshot contradiction and keep the dated historical note.
        raw = read('AMAT'); raw['routing_revision'] = 20; data = model_context(raw)
        for name in ('triage.json', 'triage_repair.json'):
            value = upgrade(read('AMAT', name)); change = value['update']
            value['reason'] = 'Correct only the dated entry-location contradiction.'
            change['public_note'] = None
            explanation = change['plan_explanation']
            explanation['setup_reason'] = explanation['conclusion'] = None
            for key in explanation['reasons']:
                if key != 'entry': explanation['reasons'][key] = None
            old = reference_document(data['reference'])
            with self.subTest(name=name):
                doc = v14.v3.document(data, value)
                self.assertEqual(doc['routine_note'], old['routine_note'])
                self.assertIn('520.08', doc['routine_note'])
                self.assertEqual(doc['conclusion'], old['conclusion'])
                self.assertIn('conclusion_provenance', doc)
                for key in old['plan']:
                    self.assertEqual(doc['plan'][key]['range'], old['plan'][key]['range'])
                    self.assertEqual(doc['plan'][key]['strength'], old['plan'][key]['strength'])

    def test_nbis_text_only_correction_no_price_change(self):
        raw = v19.read('NBIS'); raw['routing_revision'] = 20; data = model_context(raw)
        value = correction(data)
        value['update']['plan_explanation']['conclusion'] = v19.read('NBIS', 'triage.json')['update']['conclusion']
        doc = v14.v3.document(data, value)
        self.assertNotIn('270', doc['plan']['target']['reason'])
        self.assertEqual(doc['plan']['target']['range'], reference_document(data['reference'])['plan']['target']['range'])

    def test_mrna_retain_records_assessment_not_publication(self):
        data = v19.read('MRNA'); data['routing_revision'] = 20
        value = v19.read('MRNA', 'triage.json'); value.update(decision='retain', update=None)
        value = upgrade(value)
        for group in value['news_review']: group['outcome'] = 'no_action'
        before = deepcopy(data['reference']); saved = v19.v18.record(data, value)
        self.assertEqual({k: v for k, v in saved['reference'].items() if k != 'review_memory'},
                         {k: v for k, v in before.items() if k != 'review_memory'})
        self.assertEqual(daily_decision(value, [], model_context(data)), 'retain')

    def test_all_original19_receipts_are_byte_exact(self):
        paths = list(ARCHIVE.glob('*/triage.input.json'))
        if not paths: self.skipTest('Original archive absent')
        for path in paths:
            with self.subTest(ticker=path.parent.name):
                original = path.read_bytes(); sent = unpack_model_context(json.loads(original))
                raw = json.loads(path.with_name('input.json').read_bytes())
                for key in ('guards', 'review_flags', 'itv'):
                    if key in sent: raw[key] = sent[key]
                raw.pop('research_memory', None)
                receipt = json.loads(path.with_name('triage.receipt.json').read_bytes())
                self.assertEqual(hashlib.sha256(serialize_model_input(model_context(raw)).encode()).hexdigest(), receipt['input_sha256'])
                self.assertEqual(path.read_bytes(), original)


class PipelineTests(unittest.TestCase):
    def run_case(self, choices=('retain',), *, due=False, empty=False):
        original_verdict, original_full = prior.verdict, prior.full
        actions = iter(choices)
        def verdict(data, decision='update'):
            choice = next(actions)
            with patch.object(prior, 'verdict', original_verdict):
                value = candidate(data, 'retain')
                if choice in ('correction', 'badsource'):
                    value = correction(data)
                    if choice == 'badsource':
                        value['update']['change_review']['plan_explanation']['current_evidence'] = ['/reference/missing']
                if choice == 'news':
                    value = candidate(data)
                    value['update']['public_note'] = dict(text='Factual clarification.', review=historical_review())
            if choice == 'missing': value['news_review'] = []
            if empty: value['news_review'] = []
            return value
        def full(data):
            value = original_full(data)
            for level in value['plan'].values():
                level['evidence'] = [v14.handle(model_context(data), '/slim/levels/supports/0')]
            return value
        raw = prior.data(); raw['news']['items'] = [] if empty else [{'articleId': 'one', 'headline': 'Results'}]
        with patch.object(prior, 'data', return_value=raw), patch.object(prior, 'verdict', side_effect=verdict), \
             patch.object(prior, 'full', side_effect=full):
            return prior.SemanticPipelineTests().run_case(revision=20, due=due)

    def test_retain_note_correction_itv_no_extra_calls(self):
        for choices, due, empty, status, expected in [
            (('retain',), False, False, 'retained', ['triage']),
            (('retain',), False, True, 'retained', ['triage']),
            (('news',), False, False, 'updated', ['triage']),
            (('correction',), False, False, 'updated', ['triage']),
            ((), True, False, 'regenerated', ['report'])]:
            with self.subTest(choices=choices, due=due, empty=empty):
                review, _, calls = self.run_case(choices, due=due, empty=empty)
                self.assertEqual(review['status'], status)
                self.assertEqual([kind for kind, _ in calls], expected)

    def test_single_repair_corrects_or_withdraws_but_repeated_real_error_visible(self):
        for choices, expected in [(('badsource', 'correction'), 'updated'), (('badsource', 'retain'), 'retained')]:
            review, _, calls = self.run_case(choices)
            self.assertEqual(review['status'], expected)
            self.assertEqual([kind for kind, _ in calls], ['triage', 'triage_repair'])
        with self.assertRaisesRegex(RuntimeError, 'review_contract_failed_no_sol'):
            self.run_case(('badsource', 'badsource'))

    def test_repair_uses_current_publication_contract(self):
        data = context(); value = correction(data)
        text = repair_context(data, value, 'historical source mismatch')['maintenance_repair']['instruction']
        self.assertIn('public_note', text)
        self.assertIn('null', text)

    def test_preparation_freezes_new_consolidated_policy_for_both_models(self):
        data = context(); stage = v16.stage
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            work = Path(directory) / 'CAT'; work.mkdir()
            stack.enter_context(patch.object(stage, 'datetime', prior.base.FrozenClock))
            for name, value in {'load_policy': {**prior.base.POLICY, 'routing_revision': 20},
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
                self.assertIn('REVISION20', text)
                self.assertNotIn('REVISION19', text)
                self.assertNotIn('REVISION15 OVERRIDE', text)
                self.assertNotIn('SEMANTIC OUTPUT CONTRACT v6', text)
                self.assertNotIn('Setup fields BOTH', text)
                self.assertIn('OPERABILITY BEFORE CONTINUITY', text)
                self.assertIn('public_note', text)


if __name__ == '__main__': unittest.main()
