"""Revision10 regression/authority tests. No network, models or publications."""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_semantic_report as prior
from src.local_runner import adaptive_stage as stage
from src.local_runner.adaptive_context import model_context, resolve_evidence, serialize_model_input, pack_model_context, unpack_model_context
from src.local_runner.adaptive_maintenance import maintenance_schema, _check_urls
from src.local_runner.adaptive_news_research import collect_news_research, attach_news_research
from src.local_runner.adaptive_repair import repair_context
from src.local_runner.semantic_report import maintenance_document, full_document, report_schema, reference_document, render_document
from src.local_runner.semantic_sources import source_catalog, source_pointer, normalize_plan
from src.local_runner.source_urls import url_identity

ROOT = Path(__file__).resolve().parents[1]
SEC = 'https://www.sec.gov/Archives/edgar/data/0001807794/000162828026065265/xslF345X06/wk-form4_1791321925.xml'
CIK = SEC.replace('/0001807794/', '/1807794/')


def context():
    data = prior.data(); data['routing_revision'] = 10
    return model_context(data)


def candidate(data, *, full=False):
    value = prior.full(data) if full else prior.verdict(data)
    for level in (value['plan'] if full else value['update']['plan']).values():
        level.pop('transition')
    return value


def handle(data, pointer):
    for identifier, record in source_catalog(data).items():
        if pointer == record['pointer'] or pointer.startswith(record['pointer'] + '/'):
            return identifier + pointer[len(record['pointer']):]
    raise AssertionError('Source not catalogued: ' + pointer)


class SourceContractTests(unittest.TestCase):
    def test_schema_versioned_stable_and_no_model_continuity_label(self):
        schema = maintenance_schema(context())
        self.assertEqual(schema, maintenance_schema({'routing_revision': 10, 'symbol': 'OTHER'}))
        self.assertNotIn('"transition"', json.dumps(schema))
        self.assertIn('"transition"', json.dumps(maintenance_schema({'routing_revision': 9})))
        self.assertNotEqual(report_schema(9), report_schema(10))
        prior.check_schema(candidate(context()), schema)
        prior.check_schema(candidate(context(), full=True), report_schema(10))

    def test_catalog_is_content_and_scope_bound_not_array_position(self):
        data = context(); before = deepcopy(data)
        pointer = '/slim/levels/supports/0'
        identifier = handle(data, pointer)
        data['slim']['levels']['supports'].reverse()
        self.assertEqual(source_pointer(identifier, source_catalog(data)), '/slim/levels/supports/1')
        data['slim']['levels']['supports'][1]['level'] = 89
        with self.assertRaisesRegex(ValueError, 'unknown_source_handle'):
            source_pointer(identifier, source_catalog(data))
        self.assertEqual(before['slim']['levels']['supports'][0]['level'], 90)
        self.assertTrue(all(len(key.rsplit('_', 1)[1]) == 16 for key in source_catalog(data)))

    def test_model_catalog_is_not_authority_and_input_transport_lossless(self):
        data = context(); original = deepcopy(data)
        value = candidate(data)
        selected = handle(data, '/slim/levels/supports/0')
        value['update']['plan']['entry']['facts'] = [selected]
        data['source_catalog'][selected]['value'] = {'level': 999}
        data['source_catalog'][selected]['pointer'] = '/slim/levels/supports/1'
        doc = maintenance_document(value, data)
        self.assertEqual(doc['plan']['entry']['resolved_facts'][0]['value'], 90)
        self.assertEqual(unpack_model_context(pack_model_context(original)), original)
        self.assertIn('source_catalog', serialize_model_input(original))

    def test_whole_current_and_historical_sources_are_copied_not_rejected(self):
        data = context()
        row = {'type': 'put_wall', 'level': 90, 'expiration': '2026-10-16',
               'oi': 12345, 'oi_share_pct': 11, 'gamma_share_pct': 19,
               'evidence': {'historical_reaction': {'days': 3, 'bounce': 4, 'unknown': None}}}
        data['slim']['levels']['put_walls_top'] = [row]
        data['reference']['slim_snapshot'] = deepcopy(data['slim'])
        value = candidate(data); entry = value['update']['plan']['entry']
        entry['facts'] = [handle(data, '/slim/levels/put_walls_top/0'),
                          handle(data, '/reference/slim_snapshot/levels/put_walls_top/0/evidence/historical_reaction')]
        entry['evidence'] = [handle(data, '/slim/levels/put_walls_top/0')]
        doc = maintenance_document(value, data)
        facts = doc['plan']['entry']['resolved_facts']
        self.assertEqual(next(f['value'] for f in facts if f['pointer'].endswith('/oi')), 12345)
        self.assertTrue(all(f['options_record']['expiration'] == '2026-10-16' for f in facts))
        self.assertEqual(sum(f['historical'] for f in facts), 2)
        self.assertTrue(any(f['historical'] for f in facts))
        self.assertFalse(any(label in render_document(doc) for label in ('> Evidencia actual', '> Evidencia histórica')))

    def test_expired_and_conflicting_full_objects_still_rejected(self):
        for conflict in (False, True):
            data = context()
            row = {'type': 'put_wall', 'level': 90, 'expiration': '2026-10-16' if conflict else '2026-09-01', 'oi': 100}
            data['slim']['levels']['put_walls_top'] = [row]
            if conflict: data['slim']['levels']['put_walls_top'].append({**row, 'oi': 200})
            value = candidate(data); value['update']['plan']['entry']['facts'] = [handle(data, '/slim/levels/put_walls_top/0')]
            with self.subTest(conflict=conflict), self.assertRaisesRegex(ValueError, 'conflicting_wall|expired_or_inactive'):
                maintenance_document(value, data)

    def test_comparison_is_supplemental_never_primary_or_live_fact(self):
        data = context(); value = candidate(data)
        value['update']['plan']['entry']['evidence'].append('/comparison')
        self.assertEqual(maintenance_document(value, data)['plan']['entry']['range'], {'lower': 90, 'upper': 92})
        value['update']['plan']['entry']['evidence'] = ['/comparison']
        with self.assertRaisesRegex(ValueError, 'missing_primary_level_evidence'):
            maintenance_document(value, data)
        value = candidate(data); value['update']['plan']['entry']['facts'] = ['/comparison/current_markdown_sha256']
        with self.assertRaisesRegex(ValueError, 'unproven_technical_fact_source'):
            maintenance_document(value, data)

    def test_all_missing_references_reported_without_guessing_indices(self):
        data = context(); value = candidate(data)
        value['update']['plan']['entry']['facts'] = ['/slim/levels/supports/9/level', 'current_supports_unknown']
        value['update']['plan']['resistance']['facts'] = ['/slim/levels/resistances/5/level']
        original = deepcopy(value)
        with self.assertRaises(ValueError) as raised:
            maintenance_document(value, data)
        details = raised.exception.maintenance_details
        self.assertEqual(len([row for row in details['issues'] if 'source' in row]), 3)
        feedback = repair_context(data, value, str(raised.exception), validation_details=details)
        self.assertEqual(feedback['maintenance_repair']['validation_details'], details)
        self.assertEqual(feedback['maintenance_repair']['attempt'], 1)
        self.assertIn('TODOS', feedback['maintenance_repair']['instruction'])
        self.assertEqual(value, original)

    def test_missing_required_ranges_remain_financial_errors_not_crashes(self):
        data = context(); value = candidate(data)
        value['update']['plan']['entry'].update(range=None, strength=None)
        with self.assertRaisesRegex(ValueError, 'missing_required_level') as raised:
            maintenance_document(value, data)
        self.assertTrue(raised.exception.maintenance_details['issues'])

    def test_continuity_is_mechanical_without_changing_numerical_choices(self):
        data = context(); plan = candidate(data)['update']['plan']
        old = reference_document(data['reference'])['plan']
        for zone, previous, expected in (({'lower': 90, 'upper': 92}, {'lower': 90, 'upper': 92}, 'keep'),
                ({'lower': 91, 'upper': 93}, {'lower': 90, 'upper': 92}, 'correct'),
                ({'lower': 80, 'upper': 82}, {'lower': 90, 'upper': 92}, 'reprioritize'),
                ({'lower': 80, 'upper': 82}, None, 'new'), (None, {'lower': 90, 'upper': 92}, 'remove')):
            chosen = deepcopy(plan); chosen['entry']['range'] = zone
            previous_plan = deepcopy(old); previous_plan['entry']['range'] = previous
            normalized, issues = normalize_plan(chosen, previous_plan, data)
            self.assertFalse(issues)
            self.assertEqual(normalized['entry']['transition'], expected)
            self.assertEqual(normalized['entry']['range'], zone)
            self.assertNotIn('transition', chosen['entry'])

    def test_both_models_and_one_repair_integration_keep_authority(self):
        fixture = prior.SemanticPipelineTests()
        for options, expected in (({}, ['triage']), ({'initial_bad': True}, ['triage', 'triage_repair']),
                ({'initial_bad': True, 'repair_bad': True}, ['triage', 'triage_repair', 'report']),
                ({'due': True}, ['report']), ({'retain': True}, ['triage']), ({'escalate': True}, ['triage', 'report'])):
            with self.subTest(options=options):
                review, payload, calls = fixture.run_case(revision=10, **options)
                self.assertEqual([kind for kind, _ in calls], expected)
                if review['status'] != 'retained': self.assertEqual(payload['decision']['thesis_score'], 8)
        fixture.run_case(revision=10, corrupt=True)

    def test_full_sol_still_has_wider_financial_authority(self):
        data = context(); value = candidate(data, full=True)
        value['plan']['entry']['range'] = {'lower': 94, 'upper': 95}
        self.assertEqual(full_document(value, data)['plan']['entry']['range'], {'lower': 94, 'upper': 95})
        luna = candidate(data); luna['update']['plan']['entry']['range'] = value['plan']['entry']['range']
        with self.assertRaisesRegex(ValueError, 'unproven_current_level_origin'):
            maintenance_document(luna, data)

    def test_materiality_prompt_distinguishes_exposure_from_pending_threat(self):
        prompt = (ROOT / 'prompts/daily_maintenance_semantic_v2.md').read_text(encoding='utf-8')
        self.assertIn('EXPOSURE BEFORE MATERIALITY', prompt)
        self.assertIn('sole/critical', prompt)
        self.assertIn('routine', prompt)
        self.assertNotIn('WDC', prompt)

    def test_new_preparation_freezes_v2_while_old_files_are_untouched(self):
        self.check_preparation(10)

    def check_preparation(self, revision):
        data = prior.data()
        originals = {name: (ROOT / 'prompts' / name).read_bytes() for name in
                     ('stock_analysis_semantic.md', 'daily_maintenance_semantic.md', 'semantic_report_contract.md',
                      'stock_analysis_semantic_v2.md', 'daily_maintenance_semantic_v2.md', 'semantic_report_contract_v2.md')}
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            work = Path(directory) / 'CAT'; work.mkdir()
            stack.enter_context(patch.object(stage, 'datetime', prior.base.FrozenClock))
            stack.enter_context(patch.object(stage, 'load_policy', return_value={**prior.base.POLICY, 'routing_revision': revision}))
            stack.enter_context(patch.object(stage, 'load_reference_payload', return_value=data['sol_reference']))
            stack.enter_context(patch.object(stage, 'load_current_report', return_value=data['reference']))
            stack.enter_context(patch.object(stage, 'load_research', return_value=None))
            stack.enter_context(patch.object(stage.one, '_fetch_slim', return_value=data['slim']))
            stack.enter_context(patch.object(stage.one, '_load_analyst_quality', return_value={}))
            stack.enter_context(patch.object(stage.one, 'load_compact_analyst_summary', return_value={}))
            stack.enter_context(patch.object(stage.one, 'load_recent_analyst_actions', return_value=data['analyst_actions']))
            stack.enter_context(patch.object(stage.one, 'load_recent_news', return_value=data['news']))
            stack.enter_context(patch.object(stage.one, '_load_system_prompt', return_value='LEGACY FORMAT'))
            stack.enter_context(patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL')))
            stage.prepare(ROOT, work, 'CAT', False, 'tracking')
            daily = (work / 'triage_instructions.md').read_text(encoding='utf-8')
            full = (work / 'instructions.md').read_text(encoding='utf-8')
            version = 'v5' if revision >= 13 else 'v4' if revision >= 12 else 'v3' if revision >= 11 else 'v2'
            self.assertIn('SEMANTIC OUTPUT CONTRACT ' + version, daily)
            self.assertIn('SEMANTIC OUTPUT CONTRACT ' + version, full)
            self.assertIn('EXPOSURE BEFORE MATERIALITY', daily)
            self.assertNotIn('LEGACY FORMAT', full)
            self.assertEqual(prior.read_json(work / 'policy.json')['routing_revision'], revision)
        self.assertEqual({name: (ROOT / 'prompts' / name).read_bytes() for name in originals}, originals)

    def test_all_financial_failures_across_levels_are_in_single_feedback(self):
        data = context(); value = candidate(data)
        value['update']['plan']['entry']['range'] = {'lower': 92, 'upper': 90}
        value['update']['plan']['ambitious_entry']['strength']['components']['volumen'] = 0
        value['update']['plan']['ambitious_entry']['strength']['factors'] = ' '
        value['update']['plan']['resistance']['facts'] = ['/not_a_source']
        value['update']['plan']['target']['range'] = {'lower': 80, 'upper': 80}
        with self.assertRaises(ValueError) as raised: maintenance_document(value, data)
        errors = raised.exception.maintenance_details['issues']
        for field in ('/plan/entry', '/plan/ambitious_entry', '/plan/resistance', '/plan'):
            self.assertTrue(any(row['field'] == field or row['field'].startswith(field + '/') for row in errors), field)

    def test_direct_missing_wall_index_is_never_shifted(self):
        data = context()
        data['slim']['levels']['put_walls_top'] = [{'type': 'put_wall', 'level': value, 'expiration': '2026-10-16', 'oi': 100}
                                                for value in (85, 86, 87, 88, 90)]
        value = candidate(data); value['update']['plan']['entry']['facts'] = ['/slim/levels/put_walls_top/5/level']
        with self.assertRaisesRegex(ValueError, 'source_reference'):
            maintenance_document(value, data)
        value['update']['plan']['entry']['facts'] = [handle(data, '/slim/levels/put_walls_top/4')]
        facts = maintenance_document(value, data)['plan']['entry']['resolved_facts']
        self.assertEqual(next(row['value'] for row in facts if row['pointer'].endswith('/level')), 90)

    def test_explicit_null_fact_still_unavailable_not_confirmation(self):
        data = context(); data['slim'].setdefault('technicals', {})['not_known'] = None
        value = candidate(data); value['update']['plan']['entry']['facts'] = ['/slim/technicals/not_known']
        with self.assertRaisesRegex(ValueError, 'non_scalar_technical_fact'): maintenance_document(value, data)

    def test_guards_risks_and_protected_authority_not_weakened(self):
        data = context(); value = candidate(data)
        for risk in value['risk']:
            altered = deepcopy(value); altered['risk'][risk] = True
            with self.subTest(risk=risk), self.assertRaisesRegex(ValueError, 'uncertain_or_critical'):
                maintenance_document(altered, data)
        with self.assertRaisesRegex(ValueError, 'uncertain_or_critical'):
            maintenance_document(value, {**data, 'guards': ['hard_guard']})
        altered = deepcopy(value); altered['update']['plan']['structural_stop'] = deepcopy(altered['update']['plan']['target'])
        with self.assertRaisesRegex(ValueError, 'typed_data'): maintenance_document(altered, data)

    def test_schema_revision9_matches_original_receipt_digest(self):
        work = ROOT / 'logs/batch/2026-10-07/07-50-26/adaptive/CRDO'
        if not work.exists(): self.skipTest('Production originals absent')
        receipt = json.loads((work / 'triage.receipt.json').read_bytes())
        schema = maintenance_schema({'routing_revision': 9})
        self.assertEqual(hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest(), receipt['schema_sha256'])


class CitationIdentityTests(unittest.TestCase):
    def test_only_numeric_CIK_padding_is_equivalent(self):
        self.assertEqual(url_identity(SEC), url_identity(CIK))
        for wrong in (CIK.replace('/1807794/', '/1807795/'), CIK.replace('000162828026065265', '000162828026065266'),
                      CIK.replace('wk-form4', 'another'), CIK + '?query=1', CIK.replace('www.sec.gov', 'sec.gov'),
                      CIK.replace('https:', 'http:'), CIK.replace('www.sec.gov', 'evil.test')):
            with self.subTest(wrong=wrong): self.assertNotEqual(url_identity(SEC), url_identity(wrong))
        self.assertNotEqual(url_identity(SEC.replace('www.sec.gov', 'example.test')),
                            url_identity(CIK.replace('www.sec.gov', 'example.test')))

    def test_validation_uses_same_resource_identity_only_in_new_contract(self):
        _check_urls(CIK, '', [{'url': SEC}], canonical=True)
        with self.assertRaisesRegex(ValueError, 'unsupported_url'):
            _check_urls(CIK, '', [{'url': SEC}])
        with self.assertRaisesRegex(ValueError, 'unsupported_url'):
            _check_urls(CIK.replace('wk-form4', 'another'), '', [{'url': SEC}], canonical=True)

    def test_completed_tool_provenance_keeps_actual_URL_not_snippet(self):
        text = json.dumps({'type': 'item.completed', 'item': {'type': 'web_search', 'id': 'real',
            'results': [{'url': SEC, 'snippet': 'also https://invented.test/not-observed'}]}})
        receipt = {'luna_news_events_sha256': hashlib.sha256(text.encode()).hexdigest(), 'web_search_count': 1}
        payload = {'reason': CIK + ' https://invented.test/not-observed'}
        result = collect_news_research(text, receipt, payload, revision=10)
        self.assertEqual([item['url'] for item in result['sources']], [SEC])
        self.assertEqual(collect_news_research(text, receipt, payload)['sources'], [])
        for altered in (text.replace('item.completed', 'item.started'),):
            record = {**receipt, 'luna_news_events_sha256': hashlib.sha256(altered.encode()).hexdigest(), 'web_search_count': 0}
            self.assertEqual(collect_news_research(altered, record, payload, revision=10)['sources'], [])


class ProductionCounterfactualTests(unittest.TestCase):
    def test_six_avoidable_escalations_preserve_financial_choices_TSLA_stays_rejected(self):
        batch = ROOT / 'logs/batch/2026-10-07/07-50-26/adaptive'
        if not batch.exists(): self.skipTest('Production originals absent in checkout')
        # Explicit human-audited intended strikes for this evaluation ONLY.
        # Production normalization never shifts a pointer or chooses a neighbor.
        intended = {'IBKR': 84, 'AMD': 600, 'NBIS': 210}
        for symbol in ('CRDO', 'LRCX', 'IBKR', 'AMD', 'CIFR', 'NBIS', 'TSLA'):
            work = batch / symbol
            paths = [work / name for name in ('input.json', 'triage.response', 'triage.receipt.json', 'policy.json', 'triage.events.jsonl')]
            original = {path: path.read_bytes() for path in paths if path.exists()}
            data = json.loads(original[paths[0]]); data['routing_revision'] = 10
            value = json.loads(original[paths[1]])
            original_finance = deepcopy(value['update'])
            for level in value['update']['plan'].values():
                level.pop('transition')
                for field in ('facts', 'evidence'):
                    selected = []
                    for pointer in level[field]:
                        if symbol in intended and pointer.startswith('/slim/levels/put_walls_top/5/'):
                            self.assertEqual(resolve_evidence(data, '/slim/levels/put_walls_top/4/level'), intended[symbol])
                            pointer = pointer.replace('/put_walls_top/5/', '/put_walls_top/4/')
                        try: pointer = handle(data, pointer)
                        except AssertionError: pass  # Noncatalogue roots remain explicit, not remapped.
                        selected.append(pointer)
                    level[field] = selected
            receipt = json.loads(original[paths[2]])
            attach_news_research(data, work, 'triage', {**receipt, 'research_enabled': True}, value)
            with self.subTest(symbol=symbol):
                if symbol == 'TSLA':
                    with self.assertRaisesRegex(ValueError, 'unproven_current_level_origin'):
                        maintenance_document(value, model_context(data))
                else:
                    doc = maintenance_document(value, model_context(data))
                    for key, chosen in original_finance['plan'].items():
                        for field in ('range', 'reason', 'strength'):
                            self.assertEqual(doc['plan'][key][field], chosen[field])
                    self.assertEqual(doc['summary']['setup_score'], original_finance['setup_score'])
                self.assertEqual({path: path.read_bytes() for path in original}, original)


if __name__ == '__main__':
    unittest.main()
