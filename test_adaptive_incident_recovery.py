"""02-Oct incident regressions; no provider calls or real publications."""
import hashlib
import json
import subprocess
import tempfile
import unittest
from copy import deepcopy
from datetime import timedelta, timezone, datetime
from pathlib import Path
from unittest.mock import patch
from test_adaptive_analysis import NOW, ROOT, POLICY, StageTests
from src.common import analysis_validator as validator
from src.local_runner import adaptive_stage as stage, adaptive_budget as budget, adaptive_codex as codex
from src.local_runner.adaptive_context import validation_context, model_context, serialize_model_input
from src.local_runner import run_batch as batch


class ValidationRegressionTests(unittest.TestCase):
    def test_prior_strength_comment_is_not_a_fifth_evidence_factor(self):
        factors = ('AVWAP $1741 y centro Keltner $1743; POC $1749; '
                   'put wall $1740, OI 361; 8 defensas/13 tests, volumen 3+5+2+4+3=17. '
                   'Fortaleza anterior: 78; baja por menor aportacion de opciones.')
        md = ('Fortaleza de Entrada: 76/100 · sólido\n'
              'Desglose de Entrada: estructura 23/25; volumen 17/20; opciones 12/25; '
              'confluencia 13/15; durabilidad 11/15\nFactores de Entrada: ' + factors)
        strength = validator.extract_support_strength(md, 'Entrada')
        self.assertIsNotNone(strength)
        self.assertEqual(strength.score, 76)
        self.assertEqual(strength.factors, factors)
        for presentation in (md.replace('8 defensas/13 tests', 'gamma positivo; 8 defensas/13 tests'),
                             md.replace('. Fortaleza anterior:', '; Fortaleza anterior:')):
            self.assertIsNotNone(validator.extract_support_strength(presentation, 'Entrada'))
        for bad in (md.replace('76/100', '77/100'), md.replace('sólido', 'fuerte'),
                    md.replace('12/25', '12/20'), md.replace(factors, '')):
            with self.subTest(markdown=bad):
                self.assertIsNone(validator.extract_support_strength(bad, 'Entrada'))

    def test_asml_oct3_raw_report_without_rewriting(self):
        work = ROOT / 'logs/batch/2026-10-03/07-48-11/adaptive/ASML'
        if not work.exists():
            self.skipTest('local ASML evidence unavailable')
        original = (work / 'report.response').read_bytes()
        result = validator.validate_markdown(stage.one.normalize_report_dates(original.decode('utf-8')),
            authoritative_context=validation_context(budget.read_json(work / 'input.json')),
            require_support_strengths=True, require_resistance=True, require_separate_scores=True)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(original, (work / 'report.response').read_bytes())

    def test_full_stop_is_cosmetic_not_a_score_change(self):
        line = 'estructura 18/25; volumen 15/20; opciones 18/25; confluencia 12/15; durabilidad 11/15'
        baseline = validator._parse_strength_breakdown(line)
        self.assertEqual(baseline, validator._parse_strength_breakdown(line + '.'))
        self.assertEqual(baseline, validator._parse_strength_breakdown(line + '..'))
        for bad in (line + ' 12/15.', line.replace('11/15', '16/15'),
                    line.replace('11/15', '11/20'), line.replace('; durabilidad 11/15', ''),
                    line + '; durabilidad 11/15.'):
            self.assertIsNone(validator._parse_strength_breakdown(bad), bad)

    def test_no_previous_keyword_needed_in_explicit_change(self):
        for marker in ('Se corrige', 'Se reprioriza', 'Se retira'):
            for zone in ('499-501', '499–501', '499 a 501', '$499-$501'):
                md = f'Entrada: $510-$512\nMotivo: {marker}: **{zone}** sigue vigente o se ha superado.\n'
                self.assertEqual(validator._validate_previous_level_references(md, 'entrada_anterior: 499-501'), [])
                bad = md.replace(zone, '479-481')
                self.assertIn('previous_level_mismatch', validator._validate_previous_level_references(bad, 'entrada_anterior: 499-501')[0])
        md = 'Entrada: $510-$512\nMotivo: Se corrige: cambia el nivel.\nFactores de Entrada: SMA anterior 499-501\n'
        self.assertTrue(validator._validate_previous_level_references(md, 'entrada_anterior: 499-501'))

    def test_app_missing_prior_does_not_invent_ambitious_level(self):
        md = ('Entrada ambiciosa: $275-$276.5\nMotivo: Se corrige: antes figuraba Sin zona verificable. '
              'Tras seleccionar $280, conserva exactamente los precios de la antigua Entrada.\n')
        self.assertEqual(validator._validate_previous_level_references(md, 'entrada_ambiciosa_anterior: no extraida'), [])
        bad = md + 'La Entrada ambiciosa anterior era $250-$251.\n'
        self.assertIn('invented_previous_level', validator._validate_previous_level_references(bad, 'entrada_ambiciosa_anterior: no extraida')[0])

    def test_sixteen_original_incident_responses_without_rewriting(self):
        directory = ROOT / 'logs/batch/2026-10-02/07-50-20/adaptive'
        symbols = ('SNDK', 'TSM', 'MRVL', 'IREN', 'AMAT', 'INOD', 'QBTS', 'HOOD',
                   'QCOM', 'CRDO', 'MU', 'RDDT', 'CCJ', 'USAR', 'APP', 'TSLA')
        if not directory.exists():
            self.skipTest('local incident evidence unavailable')
        for symbol in symbols:
            with self.subTest(symbol=symbol):
                work = directory / symbol
                original = (work / 'report.response').read_bytes()
                context = budget.read_json(work / 'input.json')
                result = validator.validate_markdown(stage.one.normalize_report_dates(original.decode('utf-8')),
                    authoritative_context=validation_context(context), require_support_strengths=True,
                    require_resistance=True, require_separate_scores=True)
                self.assertTrue(result.ok, result.errors)
                self.assertEqual(original, (work / 'report.response').read_bytes())


class RecoveryTests(unittest.TestCase):
    def test_resume_routes_use_frozen_baselines_without_reading_all_remote_references(self):
        from types import SimpleNamespace
        from src.local_runner import adaptive_policy as policy
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            budget.write_json(root / 'adaptive/CAT/input.json', {'reference':self.context()['reference']})
            with patch.object(policy, 'load_policy', return_value=POLICY), \
                    patch('src.local_runner.analysis_state.load_reference_payload', side_effect=AssertionError('REMOTE READ FORBIDDEN')):
                routes = policy.routes_for([SimpleNamespace(ticker='CAT',owned=False)], root, resume_dir=root)
            self.assertEqual(routes[0].ticker, 'CAT')

    def test_terminal_capacity_retry_archives_artifacts_and_reuses_success_on_next_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / 'work'
            work.mkdir()
            (work / 'instructions.md').write_text('stable',encoding='utf-8')
            (work / 'report.response').write_text('',encoding='utf-8')
            events = json.dumps({'type':'turn.failed','error':{'message':'Selected model is at capacity'}})
            (work / 'report.events.jsonl').write_text(events,encoding='utf-8')
            budget.write_json(work / 'report.receipt.json', {
                'exit_code':1,'usage':None,'model':POLICY['report_model'],
                'reasoning_effort':POLICY['report_effort'],
                'research_enabled':POLICY['report_web_research_enabled'],
                'input_sha256':hashlib.sha256(serialize_model_input(model_context(self.context())).encode()).hexdigest(),
                'instructions_sha256':hashlib.sha256(codex.report_instructions('stable',research=POLICY['report_web_research_enabled']).encode()).hexdigest(),
                'schema_sha256':hashlib.sha256(json.dumps(None,sort_keys=True).encode()).hexdigest()})
            ledger = root / 'budget.json'
            budget.write_json(ledger, {'policy':POLICY, 'calls':{'CAT:report':{'status':'failed','error':'capacity'}}})
            def generate(**kw):
                value = {'text':'completed report', 'exit_code':0, 'usage':{'input_tokens':10,'output_tokens':2},
                    'model':kw['model'],'reasoning_effort':kw['effort'],'research_enabled':kw['research'],
                    'input_sha256':hashlib.sha256(serialize_model_input(kw['data']).encode()).hexdigest(),
                    'instructions_sha256':hashlib.sha256(kw['instructions'].encode()).hexdigest(),
                    'schema_sha256':hashlib.sha256(json.dumps(kw['schema'],sort_keys=True).encode()).hexdigest()}
                (work / 'report.response').write_text(value['text'],encoding='utf-8')
                budget.write_json(work / 'report.receipt.json',{k:v for k,v in value.items() if k != 'text'})
                return value
            with patch.object(budget, 'read_codex_rate_limits', return_value={'primary':{'used_percent':20}}), \
                    patch.object(stage, 'call_codex', side_effect=generate) as model:
                first = stage.model_call(root,work,'CAT',ledger,POLICY,'report',self.context())
                second = stage.model_call(root,work,'CAT',ledger,POLICY,'report',self.context())
            self.assertEqual(first['text'],second['text'])
            self.assertEqual(model.call_count,1)
            self.assertEqual(next((work / 'failed_calls').glob('*/report.events.jsonl')).read_text(encoding='utf-8'),events)
            self.assertEqual(len(budget.read_json(ledger)['failed_call_history']['CAT:report']),1)

    def test_adaptive_model_summary_uses_real_receipts_not_planned_luna(self):
        result = {'ticker':'CAT','status':'ok','route':{'model':'gpt-6-luna','reason':'adaptive_luna_sol_itv'},
            'analysis_workflow':{'strategy':'adaptive-codex-v1','status':'regenerated',
                'receipts':[{'model':'gpt-6.1-sol'}]}}
        usage = batch._batch_model_usage([result])
        self.assertEqual(usage['base'],{'Sol':['CAT']})
        self.assertEqual(usage['reviews'],{})
        result['status'] = 'failed'
        result.pop('analysis_workflow')
        self.assertEqual(batch._batch_model_usage([result])['base'],{})

    def test_resume_keeps_checkpoint_order_after_completed_itvs_change_ranking(self):
        from types import SimpleNamespace
        records = [SimpleNamespace(ticker=s) for s in ('CAT','GOOG','TSLA')]
        routes = [SimpleNamespace(ticker=s) for s in ('TSLA','CAT','GOOG')]
        ordered = batch._order_adaptive_resume_routes(routes, records)
        self.assertEqual([r.ticker for r in ordered], ['CAT','GOOG','TSLA'])
        with self.assertRaisesRegex(RuntimeError, 'route set differs'):
            batch._order_adaptive_resume_routes(routes[:-1], records)

    def context(self):
        value = StageTests().context()
        for key in ('news', 'analyst_actions'):
            value[key]['generated_at'] = NOW.isoformat()
        value['news']['window'] = {'start': NOW.isoformat()}
        return value

    def test_transient_terminal_failure_only(self):
        events = '\n'.join(json.dumps(e) for e in (
            {'type':'turn.started'}, {'type':'item.completed','item':{'type':'web_search'}},
            {'type':'turn.failed','error':{'message':'Selected model is at capacity. Please try a different model.'}}))
        self.assertTrue(codex.retryable_failure(1, events, ''))
        for code, log, response in ((0, events, ''), (None, events, ''), (1, events, 'completed report'),
                (1, events + '\n{"type":"turn.completed"}', ''), (1, events + '\ninvalid', ''),
                (1, '{"type":"turn.started"}', ''), (1, '{"type":"turn.failed","error":{"message":"usage limit"}}', '')):
            self.assertFalse(codex.retryable_failure(code, log, response))

    def test_retry_keeps_history_and_quota_and_crash_protection(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(budget, 'read_codex_rate_limits', return_value={'primary':{'used_percent':50}}) as quota:
            path = Path(tmp) / 'budget.json'
            options = dict(ticker='INTC', kind='report', itv=False, policy=POLICY, root=ROOT)
            key = budget.reserve(path, **options)
            with self.assertRaisesRegex(RuntimeError, 'already_reserved'):
                budget.reserve(path, **options, retry_failed=True)
            budget.finish(path, key, receipt={'retryable_failure':True}, error='capacity')
            self.assertEqual(budget.reserve(path, **options, retry_failed=True), key)
            ledger = budget.read_json(path)
            self.assertEqual(ledger['failed_call_history'][key][0]['error'], 'capacity')
            self.assertEqual(ledger['calls'][key]['status'], 'reserved')
            self.assertEqual(quota.call_count, 2)

    def test_prepare_backfills_actual_gap_and_keeps_old_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / 'adaptive/CAT'
            context = self.context()
            context['news']['window']['start'] = (NOW + timedelta(days=1)).isoformat()
            budget.write_json(work / 'input.json', context)
            budget.write_json(work / 'failure.json', {'error_message':'news_coverage_gap_since_full_report'})
            updated = deepcopy(context['news'])
            updated['window']['start'] = (NOW - timedelta(days=1)).isoformat()
            with patch.object(stage, 'load_policy', return_value=POLICY), patch.object(stage, 'data_ready'), \
                    patch.object(stage, 'load_reference_payload', return_value=context['reference']), \
                    patch.object(stage.one, '_fetch_slim', return_value=context['slim']), \
                    patch.object(stage.one, '_load_analyst_quality', return_value={}), \
                    patch.object(stage.one, 'load_compact_analyst_summary', return_value={}), \
                    patch.object(stage.one, 'load_recent_analyst_actions', return_value=context['analyst_actions']), \
                    patch.object(stage.one, 'load_recent_news', side_effect=[context['news'], updated]), \
                    patch.object(stage.one, '_load_system_prompt', return_value='stable'), \
                    patch.object(stage, 'run_bounded', return_value=subprocess.CompletedProcess([],0,'backfilled','')) as fetch:
                stage.prepare(root, work, 'CAT', False, 'tracking')
            self.assertIn('--since', fetch.call_args.args[0])
            self.assertFalse(stage._news_gap(budget.read_json(work / 'input.json')))
            self.assertEqual(budget.read_json(next((work / 'input_history').glob('*.json'))), context)

    def test_prepare_never_refreshes_a_reserved_input_even_without_receipt(self):
        for individual in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                work = root / ('CAT' if individual else 'adaptive/CAT')
                context = self.context()
                budget.write_json(work / 'input.json', context)
                budget.write_json(work / 'failure.json', {'error_message':'missing_support_data'})
                budget.write_json(root / 'codex_budget.json', {'calls':{'CAT:report':{'status':'reserved'}}})
                with patch.object(stage, 'load_reference_payload') as ref:
                    stage.prepare(root, work, 'CAT', False, 'tracking')
                ref.assert_not_called()
                self.assertEqual(budget.read_json(work / 'input.json'), context)

    def test_missing_support_not_frozen_as_successful_preparation(self):
        context = self.context()
        context['slim']['levels']['supports'] = []
        with self.assertRaisesRegex(RuntimeError, 'missing_support_data'):
            stage.data_ready(context, POLICY, NOW)

    def test_progress_serializes_and_counts_adaptive_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'pipeline_state.json'
            tracker = batch._PipelineTracker(path, tickers=('CAT',), source='test', started_at=NOW, resume=False)
            task = batch.PipelineTask('CAT', 1)
            review = {'status':'regenerated', 'generation_provider':'codex', 'analysis_status':'ok'}
            for phase in ('prepare','analyze','publish'):
                tracker.stage_finished(task, phase, {'status':'ok', 'adaptive_review':review, 'exit_code':0})
            state = budget.read_json(path)
            self.assertEqual(state['tickers']['CAT']['attempts']['1']['stages']['analyze']['adaptive_review'], review)
            progress = batch._pipeline_progress_payload(state, command_id='test', command_action='analyze_market', generation_provider='codex')
            self.assertEqual(progress['counts']['regenerated_reports'], 1)
            self.assertEqual(progress['counts']['retained_reports'], 0)


if __name__ == '__main__':
    unittest.main()
