"""Root regressions AUR/RDDT/SPCX: offline binding and typed source classes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_semantic_report as prior
import test_semantic_sources as sources_prior
from src.local_runner.adaptive_context import model_context, serialize_model_input
from src.local_runner.adaptive_maintenance import maintenance_schema, apply_update
from src.local_runner.semantic_binding import bind_response, require_response_binding
from src.local_runner.semantic_report import maintenance_document, full_document, render_document, reference_document, publication_fields
from src.local_runner.semantic_sources import source_catalog, source_pointer, resolve_source

ROOT = Path(__file__).resolve().parents[1]


def context():
    data = prior.data(); data['routing_revision'] = 11
    return model_context(data)


def candidate(data, *, full=False):
    payload = prior.full(data) if full else prior.verdict(data)
    payload.pop('base_markdown_sha256', None)
    for item in (payload['plan'] if full else payload['update']['plan']).values(): item.pop('transition', None)
    return payload


def receipt(data, payload, kind='triage'):
    view = model_context(data)
    if kind != 'report': view.pop('research_memory', None)
    return {'text': json.dumps(payload), 'exit_code': 0,
            'input_sha256': hashlib.sha256(serialize_model_input(view).encode()).hexdigest()}


def document(data, payload, *, full=False):
    binding = bind_response(data, receipt(data, payload, 'report' if full else 'triage'), 'report' if full else 'triage')
    return (full_document if full else maintenance_document)(payload, data, binding=binding)


def address(data, pointer):
    for identifier, row in source_catalog(data).items():
        if pointer == row['pointer'] or pointer.startswith(row['pointer'] + '/'):
            return '/source_catalog/' + identifier + '/value' + pointer[len(row['pointer']):]
    raise AssertionError(pointer)


class RunnerBindingTests(unittest.TestCase):
    def test_new_preparation_freezes_v3_without_touching_old_prompts(self):
        sources_prior.SourceContractTests().check_preparation(11)

    def test_model_no_longer_echoes_base_hash_but_legacy_schema_stays_exact(self):
        data = context(); value = candidate(data)
        self.assertNotIn('base_markdown_sha256', maintenance_schema(data)['properties'])
        self.assertIn('base_markdown_sha256', maintenance_schema({'routing_revision': 10})['properties'])
        self.assertEqual(document(data, value)['plan']['entry']['range'], {'lower': 90, 'upper': 92})
        value['base_markdown_sha256'] = 'anything'
        with self.assertRaisesRegex(ValueError, 'typed_data'): document(data, value)

    def test_missing_or_wrong_input_receipt_is_integrity_error(self):
        data = context(); value = candidate(data)
        for bad in ({}, {**receipt(data, value), 'input_sha256': 'wrong'},
                    {**receipt(data, value), 'exit_code': 1}):
            with self.subTest(receipt=bad.get('exit_code')), self.assertRaisesRegex(ValueError, 'input_receipt'):
                bind_response(data, bad, 'triage')
        with self.assertRaisesRegex(ValueError, 'binding_missing'): maintenance_document(value, data)

    def test_bound_response_cannot_be_replaced(self):
        data = context(); value = candidate(data)
        binding = bind_response(data, receipt(data, value), 'triage')
        for field in ('setup_score', 'risk', 'decision'):
            changed = deepcopy(value)
            if field == 'setup_score': changed['update']['setup_score'] = 9
            if field == 'risk': changed['risk']['thesis_change'] = True
            if field == 'decision': changed.update(decision='retain', update=None)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'binding_response'):
                maintenance_document(changed, data, binding=binding)

    def test_frozen_base_anchor_sources_and_identity_cannot_change(self):
        data = context(); value = candidate(data)
        binding = bind_response(data, receipt(data, value), 'triage')
        for field in ('reference', 'sol_reference', 'slim', 'news', 'symbol', 'owned'):
            changed = deepcopy(data)
            if field in ('reference', 'sol_reference'): changed[field]['generated_at'] = '2026-10-01T00:00:00+00:00'
            elif field == 'slim': changed[field]['latest_price'] += 1
            elif field == 'news': changed[field]['items'].append({'headline': 'new source'})
            elif field == 'owned': changed[field] = not changed[field]
            else: changed[field] = 'OTHER'
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'frozen_authority_changed'):
                maintenance_document(value, changed, binding=binding)

    def test_tool_attachment_and_feedback_are_not_new_frozen_base(self):
        data = context(); value = candidate(data)
        binding = bind_response(data, receipt(data, value), 'triage')
        data['news']['luna_research'] = {'calls': []}
        data['triage'] = deepcopy(value)
        data['maintenance_repair_history'] = [{'reason': 'diagnostic'}]
        require_response_binding(value, data, binding)

    def test_report_and_maintenance_bindings_are_not_interchangeable(self):
        data = context(); value = candidate(data)
        binding = bind_response(data, receipt(data, value, 'report'), 'report')
        with self.assertRaisesRegex(ValueError, 'binding_response'):
            maintenance_document(value, data, binding=binding)

    def test_old_receipt_cannot_be_relabelled_as_new_contract(self):
        data = context(); value = candidate(data)
        old = deepcopy(data); old['routing_revision'] = 10
        with self.assertRaisesRegex(ValueError, 'input_receipt'):
            bind_response(data, receipt(old, value), 'triage')

    def test_publication_still_refuses_changed_base_anchor_or_newer_report(self):
        review, output, _ = prior.SemanticPipelineTests().run_case(revision=11)
        data = prior.data()
        for change, expected in (('base', 'current_report_changed'), ('anchor', 'sol_anchor_changed'),
                                 ('newer', 'newer_report_exists'), ('invalid_anchor', 'invalid_sol_anchor')):
            current, anchor = deepcopy(data['reference']), deepcopy(data['sol_reference'])
            if change == 'base': current['analysis_markdown'] += '\nChanged since preparation'
            if change == 'anchor': anchor['analysis_markdown'] += '\nNew full authority'
            if change == 'newer': current['generated_at'] = '2099-01-01T00:00:00+00:00'
            if change == 'invalid_anchor': anchor['analysis_status'] = 'failed'
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); work = root/'batch/adaptive/CAT'
                prior.write_json(work/'review.json', review)
                prior.write_json(work/'publish/output/CAT/latest.json', output)
                with patch.object(prior.stage, '_read_json_gcs', side_effect=[current, anchor]), \
                     patch.object(prior.stage.one, '_upload', side_effect=AssertionError('NO UPLOAD')) as upload:
                    with self.assertRaisesRegex(RuntimeError, expected):
                        prior.stage._publish_locked(root, work, 'CAT')
                    upload.assert_not_called()

    def test_pipeline_update_repair_sol_retain_ITV_and_corruption(self):
        fixture = prior.SemanticPipelineTests()
        for options, expected in (({}, ['triage']), ({'initial_bad': True}, ['triage', 'triage_repair']),
                ({'initial_bad': True, 'repair_bad': True}, ['triage', 'triage_repair', 'report']),
                ({'due': True}, ['report']), ({'retain': True}, ['triage']), ({'escalate': True}, ['triage', 'report'])):
            with self.subTest(options=options):
                _, _, calls = fixture.run_case(revision=11, **options)
                self.assertEqual([kind for kind, _ in calls], expected)
        fixture.run_case(revision=11, corrupt=True)


class SourceClassTests(unittest.TestCase):
    def test_catalog_address_node_and_handle_are_same_exact_source(self):
        data = context(); pointer = '/slim/levels/supports/0'; catalog = source_catalog(data)
        canonical = address(data, pointer); identifier = canonical.split('/')[2]
        for token in (canonical, '/source_catalog/' + identifier, identifier):
            self.assertEqual(source_pointer(token, catalog, revision=11), pointer)
            value = candidate(data); value['update']['plan']['entry']['evidence'] = [token]
            value['update']['plan']['entry']['facts'] = [token]
            self.assertEqual(document(data, value)['plan']['entry']['resolved_facts'][0]['value'], 90)
        self.assertEqual(source_pointer(canonical + '/level', catalog, revision=11), pointer + '/level')

    def test_catalog_metadata_missing_ID_and_missing_field_never_guessed(self):
        data = context(); canonical = address(data, '/slim/levels/supports/0')
        for bad in (canonical.replace('/value', '/pointer'), '/source_catalog/unknown/value', canonical + '/nonexistent'):
            value = candidate(data); value['update']['plan']['entry']['facts'] = [bad]
            with self.subTest(source=bad), self.assertRaisesRegex(ValueError, 'source_reference'):
                document(data, value)

    def test_catalog_projection_roundtrip_keeps_authenticated_typed_report(self):
        data = context(); doc = document(data, candidate(data)); md = render_document(doc)
        data['reference'].update(publication_fields(doc, md, data['reference'], prior.base.COMPLETED), analysis_markdown=md)
        projected = model_context(data)
        self.assertEqual(model_context(projected), projected)
        self.assertEqual(source_catalog(projected), source_catalog(data))
        self.assertEqual(reference_document(projected['reference'], verify_projection=True), doc)

    def test_historical_report_values_stay_dated_in_audit_not_current_facts(self):
        data = context(); value = candidate(data, full=True)
        value['plan']['management_stop']['facts'] = ['/reference/plan/management_stop']
        value['plan']['structural_stop']['facts'] = ['/reference/plan/structural_stop']
        doc = document(data, value, full=True)
        for key in ('management_stop', 'structural_stop'):
            fact = doc['plan'][key]['resolved_facts'][0]
            self.assertTrue(fact['historical'])
            self.assertEqual(fact['source_kind'], 'historical_report')
            self.assertEqual(fact['as_of'], data['reference']['generated_at'])
            self.assertEqual(len(fact['report_markdown_sha256']), 64)
        self.assertNotIn('> Antecedente del informe', render_document(doc))

    def test_catalog_report_object_is_verified_historical_evidence(self):
        data = context(); value = candidate(data)
        token = address(data, '/reference/semantic_data/plan/entry')
        value['update']['plan']['entry']['evidence'] = [token, '/slim']
        value['update']['plan']['entry']['facts'] = [token]
        doc = document(data, value)
        facts = doc['plan']['entry']['resolved_facts']
        self.assertTrue(facts)
        self.assertTrue(all(fact['source_kind'] == 'historical_report' for fact in facts))
        self.assertEqual(next(fact['value'] for fact in facts if fact['pointer'].endswith('/range/lower')), 90)

    def test_canonical_report_evidence_uses_authority_even_without_legacy_mirror(self):
        data = context(); data['reference'].pop('plan', None)
        value = candidate(data)
        value['update']['plan']['entry']['evidence'] = ['/reference/plan/entry', '/slim']
        value['update']['plan']['entry']['facts'] = ['/reference/plan/entry']
        self.assertEqual(document(data, value)['plan']['entry']['resolved_facts'][0]['value'], 90)

    def test_legacy_mirror_and_projected_cache_cannot_forge_a_report_fact(self):
        data = context()
        true = reference_document(data['reference'], verify_projection=True)['plan']['structural_stop']['range']['lower']
        data['reference'].setdefault('plan', {})['structural_stop'] = 9999
        data['reference']['semantic_data']['plan']['structural_stop']['range']['lower'] = 8888
        self.assertEqual(resolve_source(data, '/reference/plan/structural_stop'), true)
        self.assertEqual(resolve_source(data, '/reference/semantic_data/plan/structural_stop/range/lower'), true)

    def test_corrupted_persisted_typed_binding_is_not_hidden_by_projected_cache(self):
        data = context(); doc = document(data, candidate(data)); md = render_document(doc)
        data['reference'].update(publication_fields(doc, md, data['reference'], prior.base.COMPLETED), analysis_markdown=md)
        data = model_context(data)
        data['reference']['semantic_report']['data']['plan']['structural_stop']['range']['lower'] = 9999
        with self.assertRaisesRegex(ValueError, 'semantic_base_integrity'):
            resolve_source(data, '/reference/plan/structural_stop')

    def test_history_cannot_authorize_a_new_current_origin(self):
        data = context(); value = candidate(data)
        value['update']['plan']['entry']['range'] = {'lower': 94, 'upper': 95}
        value['update']['plan']['entry']['facts'] = ['/reference/plan/entry']
        value['update']['plan']['entry']['evidence'] = ['/reference/plan/entry']
        with self.assertRaisesRegex(ValueError, 'unproven_current_level_origin'): document(data, value)

    def test_missing_or_invalid_report_authority_never_becomes_evidence(self):
        data = context()
        for mutate in ('failed', 'missing', 'unknown'):
            changed = deepcopy(data)
            if mutate == 'failed': changed['reference']['analysis_status'] = 'failed'
            if mutate == 'missing': changed['reference']['analysis_markdown'] = ''
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                resolve_source(changed, '/reference/plan/not_a_field' if mutate == 'unknown' else '/reference/plan/structural_stop')


class OriginalIncidentTests(unittest.TestCase):
    def test_original_incidents_counterfactual_no_financial_or_artifact_edits(self):
        batch = ROOT / 'logs/batch/2026-10-07/09-12-17/adaptive'
        if not batch.exists(): self.skipTest('Original production artifacts absent')
        for symbol, name, full in (('AUR', 'triage.response', False), ('RDDT', 'triage.response', False),
                                   ('RDDT', 'triage_repair.response', False), ('SPCX', 'report.response', True)):
            work = batch / symbol
            originals = {file: file.read_bytes() for file in work.iterdir() if file.is_file()}
            data = json.loads(originals[work/'input.json']); data['routing_revision'] = 11
            value = json.loads(originals[work/name]); before = deepcopy(value)
            value.pop('base_markdown_sha256', None)  # NEW schema only, never edit old receipt.
            doc = document(model_context(data), value, full=full)
            chosen = before['plan'] if full else before['update']['plan']
            with self.subTest(symbol=symbol, name=name):
                for key, item in chosen.items():
                    for field in ('range', 'reason', 'strength'):
                        self.assertEqual(doc['plan'][key][field], item[field])
                if full:
                    self.assertEqual(doc['summary'], before['summary'])
                    self.assertEqual(doc['catalysts'], sorted(before['catalysts'], key=lambda event: event['date'] or '', reverse=True))
                else: self.assertEqual(doc['summary']['setup_score'], before['update']['setup_score'])
                self.assertEqual({file: file.read_bytes() for file in originals}, originals)

    def test_original_revision10_hash_contract_still_rejects_AUR(self):
        work = ROOT / 'logs/batch/2026-10-07/09-12-17/adaptive/AUR'
        if not work.exists(): self.skipTest('Original production artifacts absent')
        data = json.loads((work/'input.json').read_bytes()); data['routing_revision'] = 10
        value = json.loads((work/'triage.response').read_bytes())
        with self.assertRaisesRegex(ValueError, 'invalid_update_base_hash'):
            maintenance_document(value, model_context(data))


if __name__ == '__main__': unittest.main()
