"""Read-only incident fixtures and offline pipelines; no models or publications."""
from copy import deepcopy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_adaptive_audit_v15 as v15
from src.local_runner import adaptive_stage as stage
from src.local_runner.adaptive_cache import reference_key
from src.local_runner.adaptive_context import model_context, serialize_model_input, unpack_model_context
from src.local_runner.review_memory import build_memory, read_memory, memory_view
from src.local_runner.evidence_semantics import technical_observations
from src.local_runner.semantic_report import reference_document, render_document, digest, publication_fields
from src.local_runner.adaptive_budget import write_json, read_json
from src.local_runner.adaptive_current import load_current_report

ROOT = Path(__file__).resolve().parent
BATCH = ROOT / 'logs/batch/2026-10-07/21-27-11/adaptive'


def context():
    raw = v15.v14.prior.data()
    raw['routing_revision'] = 16
    return raw


def note(data, text, scope='routine_news'):
    value = v15.candidate(model_context(data))
    value['routine_note'] = text
    value['update']['change_review']['routine_note'] = {
        'basis': 'prior_error', 'scope': scope, 'previous_evidence': ['/reference'],
        'current_evidence': ['/news'], 'explanation': 'Aclaración documental útil.'}
    return value


def published(data, document):
    md = render_document(document)
    return {**data['reference'], 'analysis_markdown': md,
            **publication_fields(document, md, data['reference'], v15.v14.prior.base.COMPLETED)}


class MemoryTests(unittest.TestCase):
    def test_retain_persists_assessment_without_redating_or_resetting_anchor(self):
        data = context()
        data['news']['items'] = [{'articleId': 'x', 'headline': 'Old news', 'published_at': '2026-10-01'}]
        data['triage'] = {'news': {'assessment': 'Already assessed; routine.'}, 'reason': 'No material change'}
        payload = deepcopy(data['reference'])
        before = deepcopy(payload)
        payload['review_memory'] = build_memory(data, payload, {'status': 'retained', 'reviewed_at': '2026-10-03'})
        self.assertEqual({k: v for k, v in payload.items() if k != 'review_memory'}, before)
        data['reference'] = payload
        view = model_context(data)
        self.assertTrue(view['news']['prior_reviews']['current_items'][0]['previously_assessed_exact_content'])
        self.assertIn('Already assessed', view['news']['prior_reviews']['reviews'][0]['news_assessment']['assessment'])
        self.assertEqual(view['reference']['generated_at'], before['generated_at'])
        self.assertEqual(serialize_model_input(view), serialize_model_input(model_context(view)))
        self.assertNotIn('review_memory', unpack_model_context(json.loads(serialize_model_input(view)))['reference'])

    def test_same_id_changed_contents_is_not_identical_and_old_source_remains(self):
        data = context(); data['news']['items'] = [{'articleId': 'x', 'headline': 'Proposed sale'}]
        data['triage'] = {'news': {'assessment': 'Proposed, not executed'}}
        ref = deepcopy(data['reference'])
        ref['review_memory'] = build_memory(data, ref, {'status': 'retained', 'reviewed_at': 'day1'})
        data['reference'] = ref
        data['news']['items'][0]['headline'] = 'Executed sale with changed terms'
        view = memory_view(data)
        self.assertFalse(view['current_items'][0]['previously_assessed_exact_content'])
        self.assertEqual(len(view['articles']), 1)

    def test_repeated_feed_has_flat_bounded_storage_without_dropping_research(self):
        data = context(); data['news']['items'] = [{'articleId': 'x', 'headline': 'Sale'}]
        data['triage'] = {'news': {'assessment': 'Tax withholding'}, 'routine_note': 'Tax sale'}
        data['news']['luna_research'] = {'calls': [{'retrieved_at': 'day1', 'sources': [
            {'url': 'https://example.test/filing', 'excerpt': 'Tax withholding', 'title': 'Filing'}]}]}
        for i in range(20):
            ref = deepcopy(data['reference'])
            ref['review_memory'] = build_memory(data, ref, {'status': 'retained', 'reviewed_at': str(i)})
            data['reference'] = ref
            data['news'].pop('luna_research', None)
        saved = read_memory(ref, data['sol_reference'])
        self.assertEqual(len(saved['articles']), 1)
        self.assertEqual(len(saved['reviews']), 1)
        self.assertEqual(len(saved['research']), 1)
        self.assertEqual(next(iter(saved['research'].values()))['excerpt'], 'Tax withholding')
        self.assertNotIn('review_memory', json.dumps(saved))

    def test_memory_binding_rejects_other_report_anchor_and_tampering(self):
        data = context(); ref = deepcopy(data['reference'])
        ref['review_memory'] = build_memory(data, ref, {'status': 'retained', 'reviewed_at': 'day1'})
        for kind in ('report', 'anchor', 'data'):
            mutated = deepcopy(ref); anchor = deepcopy(data['sol_reference'])
            if kind == 'report': mutated['analysis_markdown'] += 'different'
            if kind == 'anchor': anchor['generated_at'] = '2099-01-01'
            if kind == 'data': mutated['review_memory']['data']['articles']['fake'] = {}
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'invalid_published_review_memory'):
                read_memory(mutated, anchor)

    def test_full_sol_consumes_prior_memory_and_resets_epoch(self):
        data = context(); data['triage'] = {'news': {'assessment': 'History'}}
        old = deepcopy(data['reference'])
        old['review_memory'] = build_memory(data, old, {'status': 'retained', 'reviewed_at': 'day1'})
        data['reference'] = old
        self.assertTrue(model_context(data)['news']['prior_reviews']['reviews'])
        data.pop('triage')
        full = {**old, 'generated_at': '2026-10-04T10:00:00Z', 'analysis_markdown': 'New full report'}
        full['review_memory'] = build_memory(data, full, {'status': 'regenerated', 'reviewed_at': 'day2'})
        self.assertEqual(read_memory(full, full)['reviews'], {})


class NotesTests(unittest.TestCase):
    def test_news_survives_technical_update_in_report_and_next_model_input(self):
        data = model_context(context()); first = note(data, 'La venta fue fiscal; no una compra.')
        doc = v15.v14.v3.document(data, first)
        data['reference'] = published(data, doc)
        old_news = deepcopy(doc['news_note'])
        data['slim']['as_of'] = '2026-10-03T12:00:00Z'
        second = note(data, 'Cambio técnico confirmado.', 'routine_technical')
        new = v15.v14.v3.document(model_context(data), second)
        self.assertEqual(new['news_note'], old_news)
        self.assertIn('La venta fue fiscal', render_document(new))
        self.assertIn('Cambio técnico confirmado', render_document(new))
        self.assertEqual(new['summary'], doc['summary'])
        for key in doc['plan']:
            self.assertEqual(new['plan'][key]['range'], doc['plan'][key]['range'])
        data['reference'] = published(data, new)
        view = unpack_model_context(json.loads(serialize_model_input(model_context(data))))
        self.assertEqual(view['reference']['semantic_data']['news_note'], old_news)
        self.assertIn('La venta fue fiscal', view['reference']['semantic_data']['note_history'][0]['text'])

    def test_legacy15_news_note_imported_by_declared_scope_not_text_keywords(self):
        data = model_context(context())
        doc = v15.v14.v3.document(data, note(data, 'Original'))
        doc['routine_note'] = 'Texto libre: coma, punto; corrección importante.'
        doc.pop('news_note', None)
        doc['metadata']['source_contract_revision'] = 15
        doc['commentary_change_review'] = {'routine_note': {'scope': 'routine_news'}}
        data['reference'] = published(data, doc)
        out = v15.v14.v3.document(model_context(data), note(data, 'Sólo técnica.', 'routine_technical'))
        self.assertEqual(out['news_note']['text'], doc['routine_note'])
        self.assertEqual(render_document(out).count('Texto libre'), 1)

    def test_new_cumulative_news_replaces_visible_note_but_preserves_dated_history(self):
        data = model_context(context())
        first = v15.v14.v3.document(data, note(data, 'Propuesta, aún no ejecutada.'))
        data['reference'] = published(data, first)
        second = v15.v14.v3.document(model_context(data), note(data, 'Ejecución confirmada después de la propuesta.'))
        text = render_document(second)
        self.assertNotIn('Propuesta, aún no ejecutada.', text)
        self.assertEqual(text.count('Ejecución confirmada'), 1)
        self.assertEqual(second['note_history'][0]['text'], 'Propuesta, aún no ejecutada.')


class IncidentTests(unittest.TestCase):
    def original(self, ticker):
        path = BATCH / ticker / 'input.json'
        if not path.exists(): self.skipTest('Optional frozen production fixture absent')
        return path, json.loads(path.read_text(encoding='utf8'))

    def test_coin_label_change_does_not_claim_contract_disappeared(self):
        path, data = self.original('COIN'); before = path.read_bytes()
        rows = technical_observations(data)['wall_observations']
        row = next(r for r in rows if r['level'] == 180 and 'put_walls_top' in r['current_pointer'])
        self.assertEqual(row['previous_dominant_expirations'], ['2026-10-16'])
        self.assertEqual(row['dominant_expiration'], '2026-10-09')
        self.assertNotIn('backing_lost', row)
        self.assertIn('NOT the expiry', technical_observations(data)['option_wall_contract'])
        self.assertEqual(path.read_bytes(), before)

    def test_ktos_first_test_is_observation_not_forced_move_or_rescore(self):
        path, data = self.original('KTOS'); before = path.read_bytes()
        semantics = technical_observations(data)
        row = semantics['support_extrema'][0]['observation']
        self.assertEqual(row['level'], 40.925)
        self.assertTrue(row['testing_now'])
        self.assertIn('not a completed defense', semantics['rolling_extrema_contract'])
        self.assertNotIn('decision', semantics)
        self.assertEqual(path.read_bytes(), before)

    def test_all_frozen15_triage_receipts_unchanged_and16_projection_small(self):
        paths = list(BATCH.glob('*/triage.input.json'))
        if not paths: self.skipTest('Optional frozen production fixtures absent')
        for path in paths:
            original = path.read_bytes(); sent = unpack_model_context(json.loads(original))
            raw = json.loads(path.with_name('input.json').read_text(encoding='utf8'))
            for key in ('guards', 'review_flags', 'itv'):
                if key in sent: raw[key] = sent[key]
            raw.pop('research_memory', None)  # Not part of Luna's model input.
            receipt = json.loads(path.with_name('triage.receipt.json').read_text(encoding='utf8'))
            self.assertEqual(hashlib.sha256(serialize_model_input(model_context(raw)).encode()).hexdigest(), receipt['input_sha256'])
            # A COPY for measuring the new projection, never a relabelled receipt.
            raw['routing_revision'] = 16
            self.assertLess(len(serialize_model_input(model_context(raw))), 1048576)
            self.assertEqual(path.read_bytes(), original)


class PipelineTests(unittest.TestCase):
    def run_pipeline(self, *args, **kwargs):
        cls = v15.v14.prior.SemanticPipelineTests
        run = cls.run_case
        def revision16(instance, **options):
            options['revision'] = 16
            return run(instance, **options)
        with patch.object(cls, 'run_case', revision16):
            return v15.AuditPipelineTests().run_pipeline(*args, **kwargs)

    def test_prepare_freezes16_for_both_models_and_keeps15_unchanged(self):
        data = context()
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            work = Path(directory) / 'CAT'; work.mkdir()
            stack.enter_context(patch.object(stage, 'datetime', v15.v14.prior.base.FrozenClock))
            for name, value in {'load_policy': {**v15.v14.prior.base.POLICY, 'routing_revision': 16},
                'load_reference_payload': data['sol_reference'], 'load_current_report': data['reference'],
                'load_research': None}.items(): stack.enter_context(patch.object(stage, name, return_value=value))
            for name, value in {'_fetch_slim': data['slim'], '_load_analyst_quality': {},
                'load_compact_analyst_summary': {}, 'load_recent_analyst_actions': data['analyst_actions'],
                'load_recent_news': data['news'], '_load_system_prompt': 'legacy'}.items():
                stack.enter_context(patch.object(stage.one, name, return_value=value))
            stage.prepare(ROOT, work, 'CAT', False, 'tracking')
            for filename in ('instructions.md', 'triage_instructions.md'):
                text = (work / filename).read_text(encoding='utf8')
                self.assertIn('REVISION16', text)
                self.assertIn('DOMINANT by gamma, not exclusive', text)
                self.assertIn('A report is not an exhaustive news log', text)
        v15.AuditPipelineTests().test_new_preparation_freezes_override_for_both_models()

    def test_update_retain_itv_and_repair_withdrawal_no_added_model_calls(self):
        for choices, kwargs, expected, calls in [
            (('prior_error',), {}, 'updated', ['triage']),
            (('retain',), {}, 'retained', ['triage']),
            ((), {'due': True}, 'regenerated', ['report']),
            (('quote_only', 'retain'), {}, 'retained', ['triage', 'triage_repair'])]:
            with self.subTest(expected=expected, choices=choices):
                review, payload, observed = self.run_pipeline(choices, **kwargs)
                self.assertEqual(review['status'], expected)
                self.assertEqual([kind for kind, _ in observed], calls)
                self.assertIn('review_memory', payload)
                anchor = payload if expected == 'regenerated' else context()['sol_reference']
                read_memory(payload, anchor)

    def test_retain_publication_updates_review_state_not_report_or_anchor(self):
        review, payload, _ = self.run_pipeline(('retain',))
        data = context()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); work = root / 'batch/adaptive/CAT'
            write_json(work / 'review.json', review)
            write_json(work / 'publish/output/CAT/latest.json', payload)
            def remote(uri):
                return data['sol_reference'] if uri.endswith('reference.json') else data['reference']
            with patch.object(stage, '_read_json_gcs', side_effect=remote), \
                 patch.object(stage, '_copy_json') as copy, patch.object(stage.one, '_upload') as upload, \
                 patch.object(stage, 'save_reference_payload') as save:
                stage.publish(root, work, 'CAT')
                stage.publish(root, work, 'CAT')
            upload.assert_not_called(); save.assert_not_called()
            self.assertEqual(copy.call_count, 4)
            saved = read_json(root / 'data/analysis_state/CAT/current.json')
            self.assertEqual(saved['generated_at'], data['reference']['generated_at'])
            self.assertEqual(saved['analysis_markdown'], data['reference']['analysis_markdown'])
            self.assertEqual(saved['last_full_report_at'], data['sol_reference']['generated_at'])
            with patch('src.local_runner.adaptive_current.read_text_gcs', return_value=json.dumps(saved)):
                loaded = load_current_report(root, 'CAT', data['sol_reference'])
            self.assertTrue(read_memory(loaded, data['sol_reference'])['reviews'])

    def test_old_retain_cannot_overwrite_newer_review_with_same_report_date(self):
        review, payload, _ = self.run_pipeline(('retain',))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); work = root / 'batch/adaptive/CAT'
            write_json(work / 'review.json', review)
            write_json(work / 'publish/output/CAT/latest.json', payload)
            current = deepcopy(payload); current['daily_review']['reviewed_at'] = '2099-01-01T00:00:00Z'
            with patch.object(stage, '_read_json_gcs', return_value=current), \
                 patch.object(stage, '_copy_json') as copy, patch.object(stage.one, '_upload') as upload:
                with self.assertRaisesRegex(RuntimeError, 'newer_review_exists'):
                    stage.publish(root, work, 'CAT')
            copy.assert_not_called(); upload.assert_not_called()

    def test_failed_state_upload_does_not_seed_unpublished_local_memory(self):
        review, payload, _ = self.run_pipeline(('retain',))
        data = context()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); work = root / 'batch/adaptive/CAT'
            write_json(work / 'review.json', review)
            write_json(work / 'publish/output/CAT/latest.json', payload)
            state = root / 'data/analysis_state/CAT/current.json'
            write_json(state, data['reference']); before = state.read_bytes()
            def remote(uri):
                return data['sol_reference'] if uri.endswith('reference.json') else data['reference']
            def upload(source, uri):
                if uri.endswith('/current.json'): raise RuntimeError('state upload failed')
            with patch.object(stage, '_read_json_gcs', side_effect=remote), \
                 patch.object(stage, '_copy_json', side_effect=upload):
                with self.assertRaisesRegex(RuntimeError, 'state upload failed'):
                    stage.publish(root, work, 'CAT')
            self.assertEqual(state.read_bytes(), before)
            self.assertNotIn('published_at', read_json(work / 'review.json'))


if __name__ == '__main__': unittest.main()
