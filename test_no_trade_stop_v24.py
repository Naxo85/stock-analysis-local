"""No model calls: applicability, original USAR replay and publication regression."""
from copy import deepcopy
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import test_buy_support_v22 as v22
from src.local_runner import adaptive_stage as stage
from src.local_runner.semantic_report import reference_document, render_document

ROOT = Path(__file__).resolve().parent
BATCH = ROOT / 'logs/batch/2026-10-09/06-40-36'


def fixture():
    data = v22.context()
    data.update(routing_revision=24, owned=False)
    value = v22.full(data)
    value['plan']['management_stop'].update(range=None, strength=None,
        reason='No aplicable: sin posicion y sin ninguna compra activa.')
    return data, value


def document(data, value):
    return v22.v14.v3.document(data, value, full=True)


class NoTradeStopTests(unittest.TestCase):
    def test_no_trade_absence_and_existing_stops_both_valid(self):
        data, value = fixture()
        before = deepcopy((data, value))
        doc = document(data, value)
        self.assertIsNone(doc['plan']['management_stop']['range'])
        self.assertIn('Stop de gesti\u00f3n: No aplicable', render_document(doc))
        self.assertEqual((data, value), before)
        old = v22.full(data)
        self.assertEqual(document(data, old)['plan']['management_stop']['range'],
                         old['plan']['management_stop']['range'])

    def test_explicit_no_position_required_not_falsy_or_unknown(self):
        for ownership in (True, None, 0, '', 'false'):
            data, value = fixture(); data['owned'] = ownership
            with self.subTest(ownership=ownership), self.assertRaisesRegex(ValueError, 'missing_applicable_management_stop'):
                document(data, value)
        data, value = fixture(); data.pop('owned')
        with self.assertRaises(ValueError): document(data, value)

    def test_either_purchase_requires_protection_and_other_risk_fields_remain(self):
        for key in ('entry', 'ambitious_entry'):
            data, value = fixture()
            value['plan'][key] = v22.full(data, absent=False)['plan'][key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'missing_applicable_management_stop'):
                document(data, value)
        for key in ('structural_stop', 'target', 'resistance'):
            data, value = fixture(); value['plan'][key].update(range=None, strength=None)
            with self.subTest(key=key), self.assertRaises(ValueError): document(data, value)

    def test_reason_evidence_strength_and_binding_are_not_bypassed(self):
        for field, bad in (('reason', ''), ('evidence', []), ('evidence', ['s999999']),
                           ('strength', {'components': {}, 'factors': 'invalid'})):
            data, value = fixture(); value['plan']['management_stop'][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError): document(data, value)
        from src.local_runner.semantic_report import full_document
        data, value = fixture()
        with self.assertRaises(ValueError): full_document(value, data)

    def test_old_pre_no_entry_contract_still_rejects(self):
        data, value = fixture(); data['routing_revision'] = 21
        with self.assertRaisesRegex(ValueError, 'missing_required_level'): document(data, value)

    def test_maintenance_cannot_remove_protected_stop(self):
        data, value = fixture()
        update = v22.no_entry(data)
        update['update']['plan']['management_stop'] = value['plan']['management_stop']
        with self.assertRaises(ValueError): v22.v21.document(data, update)

    def test_maintenance_inherits_absence_but_cannot_add_unprotected_purchase(self):
        data, value = fixture(); doc = document(data, value)
        payload = v22.v21.v20.v16.published(data, doc)
        view = v22.model_context({**data, 'reference': payload})
        retain = v22.v21.candidate(view, 'retain')
        self.assertEqual(v22.daily_decision(retain, [], view), 'retain')
        update = v22.no_entry(view)
        update['update']['plan']['entry'] = v22.v14.candidate(view)['update']['plan']['entry']
        update['update']['plan']['entry'].update(range={'lower': 90, 'upper': 92},
            strength=v22.prior.level({'lower':90,'upper':92})['strength'])
        with self.assertRaisesRegex(ValueError, 'missing_applicable_management_stop'):
            v22.v21.document(view, update)

    def test_consumer_no_trade_cells_empty_and_unchanged_other_fields(self):
        sys.path.insert(0, str(ROOT / 'gcp_services/stock_controller/src'))
        from stock_analysis.analysis_worker.reports import parse_analysis_report
        from stock_analysis.controller.analysis_sheet import build_analysis_value_requests
        data, value = fixture(); doc = document(data, value)
        payload = v22.v21.v20.v16.published(data, doc)
        payload.update(analysis_status='ok', validation={'ok':True}, report_schema_version=7)
        record = parse_analysis_report(payload['symbol'], payload, report_url_template='{ticker}')
        self.assertEqual((record.entry, record.washout, record.entry_stop, record.washout_stop), (None,)*4)
        self.assertEqual(reference_document(payload, verify_projection=True), doc)
        layout={'sheet':{'sheet_id':1}, 'table_template':{},
            'format_rules':{'entry_proximity':[], 'resistance_proximity':[]},
            'blocks':[{'table_name':'Demo','start_column':'A','header_row':1,
                       'tickers':[payload['symbol']], 'palette':{'body':'#FFFFFF'}}]}
        requests=build_analysis_value_requests(layout,{payload['symbol']:record},
            ticker_rows={payload['symbol']:1},prices={})
        self.assertTrue(requests)
        original=v22.full(data); olddoc=document(data, original)
        oldpayload=v22.v21.v20.v16.published(data, olddoc)
        oldpayload.update(analysis_status='ok',validation={'ok':True},report_schema_version=7)
        self.assertEqual(record,parse_analysis_report(payload['symbol'], oldpayload,report_url_template='{ticker}'))

    def test_original_usar_replays_exact_receipt_without_model_or_source_refresh(self):
        from datetime import datetime, timezone
        clock = patch.object(stage, 'datetime', wraps=datetime)
        clock.start().now.return_value = datetime(2026,10,9,7,30,tzinfo=timezone.utc)
        self.addCleanup(clock.stop)
        original=BATCH/'adaptive/USAR'
        hashes={p.name:p.read_bytes() for p in original.iterdir() if p.is_file()}
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory)/'USAR'; shutil.copytree(original,work)
            shutil.copy2(BATCH/'codex_budget.json',Path(directory)/'budget.json')
            with patch.object(stage,'call_codex',side_effect=AssertionError('NO MODEL')), \
                 patch.object(stage,'save_research'), \
                 patch.object(stage.one,'_fetch_slim',side_effect=AssertionError('NO REFRESH')):
                review=stage.analyze(ROOT,work,'USAR',Path(directory)/'budget.json',False,reuse_only=True)
            payload=json.loads((work/'publish/output/USAR/latest.json').read_text(encoding='utf8'))
            response=json.loads((work/'report.response').read_text(encoding='utf8'))
            receipt=json.loads((work/'report.receipt.json').read_text(encoding='utf8'))
            self.assertEqual(review['status'],'regenerated')
            self.assertEqual(payload['generated_at'],receipt['completed_at'])
            doc=reference_document(payload,verify_projection=True)
            for key,block in response['plan'].items():
                for field in ('range','reason','strength'):
                    self.assertEqual(doc['plan'][key][field],block[field])
            self.assertEqual(doc['summary'],response['summary'])
            self.assertEqual(doc['catalysts'],response['catalysts'])
            self.assertEqual(doc['next_event'],response['next_event'])
            self.assertEqual(doc['conclusion'],response['conclusion'])
        self.assertEqual(hashes,{p.name:p.read_bytes() for p in original.iterdir() if p.is_file()})

    def test_all_45_published_reports_keep_projection_and_sheet_values(self):
        sys.path.insert(0,str(ROOT/'gcp_services/stock_controller/src'))
        from stock_analysis.analysis_worker.reports import parse_analysis_report
        count=0
        for path in (BATCH/'adaptive').glob('*/publish/output/*/latest.json'):
            payload=json.loads(path.read_text(encoding='utf8'))
            before=deepcopy(payload)
            doc=reference_document(payload,verify_projection=True)
            self.assertIsNotNone(doc)
            parse_analysis_report(payload['symbol'],payload,report_url_template='{ticker}')
            self.assertEqual(payload,before)
            count+=1
        self.assertEqual(count,45)

    def test_recovery_without_receipt_fails_before_any_model_admission(self):
        data,value=fixture()
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory)
            (work/'instructions.md').write_text('frozen',encoding='utf8')
            policy={**v22.prior.base.POLICY,'routing_revision':24}
            with patch.object(stage,'call_codex',side_effect=AssertionError('NO MODEL')), \
                 patch.object(stage,'reserve',side_effect=AssertionError('NO ADMISSION')):
                with self.assertRaisesRegex(RuntimeError,'recovery_requires_existing_successful_receipt'):
                    stage.model_call(ROOT,work,'TEST',work/'budget.json',policy,'report',data,reuse_only=True)

    def test_preparation_clarifies_both_roles_only_for_new_revision(self):
        data,_=fixture()
        data['slim'].setdefault('options',{}).update(status='ok',gamma_regime='positive',
            expirations=[{'date':'2026-10-16'}])
        for revision in (23,24):
            with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
                work=Path(directory)/'CAT';work.mkdir()
                stack.enter_context(patch.object(stage,'datetime',v22.prior.base.FrozenClock))
                for name,value in {'load_policy':{**v22.prior.base.POLICY,'routing_revision':revision},
                    'load_reference_payload':data['sol_reference'],'load_current_report':data['reference'],
                    'load_research':None}.items():stack.enter_context(patch.object(stage,name,return_value=value))
                for name,value in {'_fetch_slim':data['slim'],'_load_analyst_quality':{},
                    'load_compact_analyst_summary':{},'load_recent_analyst_actions':data['analyst_actions'],
                    'load_recent_news':data['news'],'_load_system_prompt':'legacy'}.items():
                    stack.enter_context(patch.object(stage.one,name,return_value=value))
                stage.prepare(ROOT,work,'CAT',False,'tracking')
                for name in ('instructions.md','triage_instructions.md'):
                    text=(work/name).read_text(encoding='utf8')
                    self.assertEqual('REVISION24' in text,revision==24)
        repair=v22.repair_context(data,v22.no_entry(data),'bad')['maintenance_repair']['instruction']
        self.assertIn('Aclaracion24',repair)


if __name__ == '__main__': unittest.main()
