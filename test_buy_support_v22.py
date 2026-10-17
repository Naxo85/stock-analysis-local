"""Offline policy/contract regressions; authored decisions are not model forecasts."""
from copy import deepcopy
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_chain_audit_v21 as v21
from src.local_runner.adaptive_context import model_context
from src.local_runner.adaptive_policy import daily_decision, maintenance_precheck, load_policy
from src.local_runner.adaptive_repair import repair_context
from src.local_runner.semantic_report import reference_document, render_document, validation_result

ROOT = Path(__file__).resolve().parent
v14, prior = v21.v20.v14, v21.v20.prior
ORIGINAL_FULL = prior.full


def context():
    data = v21.context(); data['routing_revision'] = 22
    return model_context(data)


def no_entry(data):
    value = v21.candidate(data)
    for key in ('entry', 'ambitious_entry'):
        block = deepcopy(v14.candidate(data)['update']['plan']['entry'])
        block.update(range=None, strength=None,
                     reason='Sin entrada valida: soporte perdido; alternativas inferiores no defendibles.')
        block['change_review'] = v14.review(data, key, 'backing_changed')
        value['update']['plan'][key] = block
    value['update']['plan_explanation'] = dict(setup_reason=None, conclusion=None,
        reasons={key: None for key in reference_document(data['reference'])['plan']})
    return value


def full(data, *, absent=True):
    value = ORIGINAL_FULL(data)
    for key, block in value['plan'].items():
        block.pop('transition', None)
        block['evidence'] = [v14.handle(data, '/slim/levels/supports/0')]
        block['facts'] = []
        if absent and key in ('entry', 'ambitious_entry'):
            block.update(range=None, strength=None, reason='Sin soporte de compra defendible ahora.')
    return value


class ContractTests(unittest.TestCase):
    def test_full_publication_reaches_sheet_as_blank_without_touching_other_fields(self):
        import sys
        sys.path.insert(0, str(ROOT / 'gcp_services/stock_controller/src'))
        from stock_analysis.analysis_worker.reports import parse_analysis_report
        from stock_analysis.controller.analysis_sheet import build_analysis_value_requests, build_strength_border_requests
        data = context(); doc = v14.v3.document(data, full(data), full=True)
        payload = v21.v20.v16.published(data, doc)
        payload['analysis_status'] = 'ok'; payload['validation'] = {'ok': True}
        payload['report_schema_version'] = 7
        record = parse_analysis_report(payload['symbol'], payload, report_url_template='{ticker}')
        self.assertIsNone(record.entry); self.assertIsNone(record.washout)
        self.assertIsNone(record.entry_stop); self.assertIsNone(record.washout_stop)
        layout = {'sheet': {'sheet_id': 1}, 'table_template': {},
            'format_rules': {'entry_proximity': [], 'resistance_proximity': []},
            'blocks': [{'table_name': 'Demo', 'start_column': 'A', 'header_row': 1,
                       'tickers': [payload['symbol']], 'palette': {'body': '#FFFFFF'}}]}
        rows = {payload['symbol']: 1}; records = {payload['symbol']: record}
        cells = build_analysis_value_requests(layout, records, ticker_rows=rows, prices={})[0]['updateCells']['rows'][0]['values']
        for cell in cells[:2]:
            self.assertEqual(cell['userEnteredValue'], {'stringValue': ''})
            self.assertEqual(cell['note'], '')
        borders = build_strength_border_requests(layout, records, ticker_rows=rows)
        for border in borders:
            item = border['updateBorders']
            if item['range']['startColumnIndex'] in (9, 10):
                self.assertEqual(item['top']['style'], 'NONE')
        data2 = model_context({**data, 'reference': payload})
        replacement = v21.candidate(data2)
        replacement['update']['plan']['entry'] = v14.candidate(data2)['update']['plan']['entry']
        replacement['update']['plan']['entry'].update(range={'lower': 90, 'upper': 92},
            strength=prior.level({'lower': 90, 'upper': 92})['strength'])
        replacement['update']['plan_explanation'] = dict(setup_reason=None, conclusion=None,
            reasons={key: None for key in reference_document(payload)['plan']})
        restored = v21.document(data2, replacement)
        self.assertIsNotNone(restored['plan']['entry']['range'])

    def test_no_entry_maintenance_preserves_risk_and_fundamentals_and_publication(self):
        data = context(); value = no_entry(data); before = deepcopy((data, value))
        old = reference_document(data['reference']); doc = v21.document(data, value)
        for key in ('entry', 'ambitious_entry'):
            self.assertIsNone(doc['plan'][key]['range'])
            self.assertIsNone(doc['plan'][key]['strength'])
            self.assertEqual(doc['plan'][key]['continuity']['transition'], 'remove')
        for key in ('management_stop', 'structural_stop', 'target', 'resistance'):
            for field in ('range', 'reason', 'strength'):
                self.assertEqual(doc['plan'][key][field], old['plan'][key][field])
        for key in ('summary', 'catalysts', 'next_event', 'fundamental_markdown'):
            self.assertEqual(doc[key], old[key])
        md = render_document(doc)
        self.assertIn('Entrada: Sin zona verificable', md)
        self.assertNotIn('Estado en el snapshot:', md)
        self.assertIsNone(validation_result(doc).entry_range)
        published = v21.v20.v16.published(data, doc)
        self.assertIsNone(published['plan']['entry'])
        self.assertIsNone(published['plan']['entry_strength_score'])
        self.assertEqual(reference_document(published, verify_projection=True), doc)
        data2 = model_context({**data, 'reference': published})
        guards = maintenance_precheck(published, data2['slim'], data2['sol_reference'], owned=False, revision=22)
        self.assertNotIn('unparseable_prior_entry', guards['guards'])
        self.assertEqual(daily_decision(v21.candidate(data2, 'retain'), [], data2), 'retain')
        self.assertEqual((data, value), before)

    def test_full_report_allows_no_entry_but_frozen21_does_not(self):
        data = context(); value = full(data)
        doc = v14.v3.document(data, value, full=True)
        self.assertIsNone(doc['plan']['entry']['range'])
        data['routing_revision'] = 21
        with self.assertRaisesRegex(ValueError, 'missing_required_level'):
            v14.v3.document(data, value, full=True)
        with self.assertRaisesRegex(ValueError, 'missing_required_level'):
            v21.document(data, no_entry(data))

    def test_absent_entry_still_requires_reason_evidence_and_justification(self):
        for issue in ('reason', 'evidence', 'quote_only', 'unknown_source', 'strength'):
            data = context(); value = no_entry(data); block = value['update']['plan']['entry']
            if issue in ('reason', 'evidence'): block[issue] = '' if issue == 'reason' else []
            elif issue == 'quote_only': block['change_review']['basis'] = 'quote_only'
            elif issue == 'unknown_source': block['evidence'] = ['s9999999']
            else: block['strength'] = v14.candidate(data)['update']['plan']['entry']['strength']
            with self.subTest(issue=issue), self.assertRaises(ValueError): v21.document(data, value)

    def test_same_quote_crossing_does_not_force_relocation_or_full_report(self):
        for price in (89.99, 90, 91, 92.01):
            data = context(); data['slim']['latest_price'] = price; before = deepcopy(data['reference'])
            guards = maintenance_precheck(data['reference'], data['slim'], data['sol_reference'], owned=False, revision=22)
            self.assertNotIn('price_move_ge_8pct_since_report', guards['guards'])
            self.assertEqual(daily_decision(v21.candidate(data, 'retain'), [], data), 'retain')
            self.assertEqual(data['reference'], before)

    def test_lower_replacement_allowed_and_geometry_still_enforced_for_both_entries(self):
        data = context(); value = no_entry(data)
        block = v14.candidate(data)['update']['plan']['entry']
        block['range'] = {'lower': 80, 'upper': 82}
        value['update']['plan']['entry'] = block
        doc = v21.document(data, value)
        self.assertEqual(doc['plan']['entry']['range'], block['range'])
        for key in ('entry', 'ambitious_entry'):
            for bad in ({'lower': 1, 'upper': 2}, {'lower': 1000, 'upper': 1001}):
                report = full(data); report['plan'][key] = deepcopy(full(data, absent=False)['plan'][key])
                report['plan'][key]['range'] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    v14.v3.document(data, report, full=True)

    def test_risk_and_tampered_report_do_not_become_safe_no_entry(self):
        data = context(); value = no_entry(data); value['risk']['structural_invalidation'] = True
        self.assertEqual(daily_decision(value, [], data), 'escalate')
        with self.assertRaises(ValueError): v21.document(data, value)
        doc = v21.document(data, no_entry(data)); published = v21.v20.v16.published(data, doc)
        published['semantic_report']['data']['plan']['entry']['range'] = {'lower': 1, 'upper': 2}
        with self.assertRaises(ValueError):
            maintenance_precheck(published, data['slim'], data['sol_reference'], owned=False, revision=22)

    def test_repair_keeps_same_policy_and_no_automatic_break_threshold(self):
        data = context(); text = repair_context(data, no_entry(data), 'bad')['maintenance_repair']['instruction']
        for required in ('schema22', 'perforacion marginal', 'range=null', 'autoridad'):
            self.assertIn(required, text)


class PreparationTests(unittest.TestCase):
    def test_no_entry_pipeline_one_maintenance_call_and_full_only_for_itv(self):
        data = prior.data(); data['routing_revision'] = 22
        view = model_context(data)
        maintenance, report = no_entry(view), full(view)
        for due in (False, True):
            with patch.object(prior, 'verdict', return_value=deepcopy(maintenance)), \
                 patch.object(prior, 'full', return_value=deepcopy(report)):
                review, output, calls = prior.SemanticPipelineTests().run_case(
                    revision=22, due=due, expected_entry=None)
            self.assertEqual(review['status'], 'regenerated' if due else 'updated')
            self.assertEqual([kind for kind, _ in calls], ['report'] if due else ['triage'])
            self.assertIsNone(output['plan']['entry'])
            if not due:
                self.assertEqual(output['last_full_report_at'], prior.data()['sol_reference']['generated_at'])

    def test_both_roles_receive22_and_21_keeps_its_frozen_policy(self):
        data = context(); stage = v21.v20.v16.stage
        for revision in (21, 22):
            with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
                work = Path(directory) / 'CAT'; work.mkdir()
                stack.enter_context(patch.object(stage, 'datetime', prior.base.FrozenClock))
                for name, value in {'load_policy': {**prior.base.POLICY, 'routing_revision': revision},
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
                    self.assertIn('REVISION' + str(revision), text)
                    if revision == 22:
                        self.assertIn('BUY-THE-DIP SUPPORTS, NOT RECLAIM ENTRIES', text)
                        self.assertIn('for BOTH entry and ambitious_entry', text)
                        self.assertNotIn('only absent ambitious zone', text)
                        self.assertNotIn('If that conditional trade already existed', text)
                    else:
                        self.assertNotIn('BUY-THE-DIP SUPPORTS', text)


if __name__ == '__main__': unittest.main()
