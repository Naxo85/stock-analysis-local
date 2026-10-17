from pathlib import Path
from copy import deepcopy
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import test_semantic_contract_v3 as v3
from src.local_runner.adaptive_context import model_context
from src.local_runner.volume_arithmetic import calculate, validate
from src.local_runner.semantic_report import level_schema, render_document
from src.local_runner.semantic_sources import source_catalog, normalize_plan
from src.local_runner.adaptive_repair import repairable_update_error
BATCH = ROOT / 'logs/batch/2026-10-09/10-10-37/adaptive'

def fixture(ticker='AUR', revision=25):
    context = json.loads((BATCH / ticker / 'input.json').read_text(encoding='utf-8'))
    context['routing_revision'] = revision
    value = json.loads((BATCH / ticker / 'triage.json').read_text(encoding='utf-8'))
    block = value['update']['plan']['entry']
    block['volume_calculation'] = None
    for item in value['update']['plan'].values():
        if item is not None:
            item.setdefault('volume_calculation', None)
    context = model_context(context)
    catalog = source_catalog(context)
    zone = block['range']
    sources = [h for h in block['evidence'] if h in catalog and
               catalog[h]['pointer'].startswith('/slim/levels/') and
               zone['lower'] <= catalog[h]['value'].get('level', -1) <= zone['upper'] and
               (catalog[h]['value'].get('evidence') or {}).get('historical_reaction', {}).get('status') == 'available']
    block['volume_calculation'] = dict(profile_source=sources[0], reaction_source=sources[0])
    return context, value

class VolumeArithmeticTests(unittest.TestCase):
    def setUp(self):
        from datetime import datetime, timezone
        from unittest.mock import patch
        clock = patch('src.local_runner.adaptive_stage.datetime', wraps=datetime)
        mocked = clock.start()
        mocked.now.return_value = datetime(2026,10,9,12,tzinfo=timezone.utc)
        self.addCleanup(clock.stop)

    def test_real_aur_rejected_and_corrected_without_price_or_score_changes(self):
        context, value = fixture()
        with self.assertRaisesRegex(ValueError, 'expected=12, received=11') as error:
            v3.document(context, value)
        self.assertTrue(repairable_update_error(str(error.exception)))
        original = deepcopy(value)
        value['update']['plan']['entry']['strength']['components']['volumen'] = 12
        doc = v3.document(context, value)
        entry = doc['plan']['entry']
        self.assertEqual(sum(entry['strength']['components'].values()), 63)
        self.assertEqual(entry['volume_calculation_audit']['parts'],
            dict(proximity=2, repetition=3, defense_rate=2, magnitude=2, recency=3))
        self.assertEqual(entry['range'], original['update']['plan']['entry']['range'])
        self.assertNotIn('volume_calculation', render_document(doc))
        before = context['reference']['semantic_report']['data']
        for key in ('management_stop', 'structural_stop', 'target', 'ambitious_entry', 'resistance'):
            self.assertEqual(doc['plan'][key]['range'], before['plan'][key]['range'])
        self.assertEqual(doc['summary'], before['summary'])

    def test_real_lrcx_and_mrvl_corrections_still_pass(self):
        for ticker, expected in [('LRCX', 11), ('MRVL', 14)]:
            context, value = fixture(ticker)
            doc = v3.document(context, value)
            self.assertEqual(doc['plan']['entry']['volume_calculation_audit']['expected'], expected)

    def test_old_schema_and_receipts_unchanged(self):
        self.assertNotIn('volume_calculation', level_schema(24)['properties'])
        context = json.loads((BATCH / 'AUR/input.json').read_text(encoding='utf-8'))
        value = json.loads((BATCH / 'AUR/triage.json').read_text(encoding='utf-8'))
        context = model_context(context)
        self.assertEqual(v3.document(context, value)['plan']['entry']['strength']['components']['volumen'], 11)

    def test_null_cannot_hide_available_arithmetic_but_exact_inheritance_can(self):
        context, value = fixture()
        block = value['update']['plan']['entry']; block['volume_calculation'] = None
        with self.assertRaisesRegex(ValueError, 'select_profile_and_reaction'):
            v3.document(context, value)
        block['strength']['components']['volumen'] = 12
        self.assertEqual(v3.document(context, value)['plan']['entry']['strength']['components']['volumen'], 12)

    def test_unselected_or_unknown_sources_fail(self):
        for handle in ('s999999', 's1'):
            context, value = fixture()
            value['update']['plan']['entry']['volume_calculation']['profile_source'] = handle
            with self.assertRaisesRegex(ValueError, 'unselected_profile_source'):
                v3.document(context, value)

    def test_unavailable_is_not_zero_or_support_loss(self):
        self.assertIsNone(calculate({'status':'unavailable'}, {'status':'available'}, {'lower':1,'upper':1}, '2026-10-09T12:00:00Z'))

    def test_magnitude_boundaries_and_last_rebound_cap(self):
        context, value = fixture()
        record = source_catalog(context)[value['update']['plan']['entry']['volume_calculation']['reaction_source']]['value']
        profile = record['evidence']['volume_profile']
        reaction = deepcopy(record['evidence']['historical_reaction'])
        reaction['defense_min_rebound_pct'] = 2
        for median, expected in [(1.999,0),(2,1),(2.9999,1),(3,2),(3.9999,2),(4,3),(6,4)]:
            reaction['median_rebound_5d_pct'] = median
            result = calculate(profile, reaction, value['update']['plan']['entry']['range'], context['slim']['as_of'])
            self.assertEqual(result['parts']['magnitude'], expected)
        reaction['last_test_rebound_5d_pct'] = 1.99
        self.assertEqual(calculate(profile,reaction,value['update']['plan']['entry']['range'],context['slim']['as_of'])['parts']['magnitude'], 2)

    def test_center_distance_uses_node_without_rounded_record_distance(self):
        context, value = fixture('MRVL')
        row = source_catalog(context)[value['update']['plan']['entry']['volume_calculation']['profile_source']]['value']
        result = calculate(row['evidence']['volume_profile'],row['evidence']['historical_reaction'],value['update']['plan']['entry']['range'],context['slim']['as_of'])
        self.assertEqual(result['parts']['proximity'],2)
        self.assertGreater(float(result['node_distance_pct']),1.5)



    def test_full_sol_uses_same_validator_and_preserves_valid_report(self):
        context = json.loads((BATCH / 'NVDA/input.json').read_text(encoding='utf-8'))
        context['routing_revision'] = 25; context = model_context(context)
        value = json.loads((BATCH / 'NVDA/report.response').read_text(encoding='utf-8'))
        for block in value['plan'].values():
            block['volume_calculation'] = None
        doc = v3.document(context, value, full=True)
        self.assertEqual(doc['summary']['thesis_score'],7.6)
        entry = value['plan']['entry']
        row = next(h for h in entry['evidence'] if h in source_catalog(context) and
            source_catalog(context)[h]['pointer'].startswith('/slim/levels/') and
            (source_catalog(context)[h]['value'].get('evidence') or {}).get('historical_reaction',{}).get('status') == 'available')
        entry['volume_calculation'] = dict(profile_source=row,reaction_source=row)
        entry['strength']['components']['volumen'] = 1
        with self.assertRaisesRegex(ValueError, 'volume_arithmetic'):
            v3.document(context,value,full=True)

    def test_profile_boundaries_daily_cap_and_existing_ceiling(self):
        context, value = fixture()
        row = source_catalog(context)[value['update']['plan']['entry']['volume_calculation']['profile_source']]['value']
        reaction = deepcopy(row['evidence']['historical_reaction'])
        reaction.update(defense_count=9,test_count=10,defense_rate_pct=90,
            median_rebound_5d_pct=8,defense_min_rebound_pct=2,last_test_rebound_5d_pct=8)
        zone = dict(lower=100,upper=100)
        for node, proximity in [(100,3),(100.75,3),(101.5,3),(101.50001,2),(103,2),(103.00001,1),(105,1),(105.00001,0)]:
            calc = calculate(dict(status='available',nearest_level=node),reaction,zone,context['slim']['as_of'])
            self.assertEqual(calc['parts']['proximity'],proximity)
            if node > 105:
                self.assertEqual(calc['expected'],12)
        reaction.update(defense_count=2,test_count=2,defense_rate_pct=100)
        calc=calculate(dict(status='available',nearest_level=100),reaction,zone,context['slim']['as_of'])
        self.assertEqual(calc['parts']['defense_rate'],2)
        self.assertEqual(calc['ceiling'],12)

    def test_source_handles_survive_array_reordering_and_historical_date(self):
        context, value = fixture()
        catalog = source_catalog(context)
        source = value['update']['plan']['entry']['volume_calculation']['reaction_source']
        before = catalog[source]['value']
        context['slim']['levels']['put_walls_top'].reverse()
        self.assertEqual(source_catalog(context)[source]['value'], before)
        value['update']['plan']['entry']['strength']['components']['volumen'] = 12
        self.assertEqual(v3.document(context,value)['plan']['entry']['volume_calculation_audit']['expected'],12)

    def test_missing_fields_cannot_be_invented_and_protected_fields_not_mutated(self):
        context, value = fixture()
        record=source_catalog(context)[value['update']['plan']['entry']['volume_calculation']['reaction_source']]['value']
        profile=record['evidence']['volume_profile'];reaction=deepcopy(record['evidence']['historical_reaction'])
        for field in ('defense_count','last_test_rebound_5d_pct'):
            invalid=deepcopy(reaction);invalid.pop(field)
            with self.assertRaisesRegex(ValueError,'incomplete_numeric'):
                calculate(profile,invalid,value['update']['plan']['entry']['range'],context['slim']['as_of'])
        invalid=deepcopy(reaction);invalid['last_test_date']='2099-01-01'
        with self.assertRaisesRegex(ValueError,'observation_date'):
            calculate(profile,invalid,value['update']['plan']['entry']['range'],context['slim']['as_of'])



    def test_manual_correction_preserves_authority_dates_and_consumer_projection(self):
        from datetime import datetime, timezone
        from src.local_runner.correct_volume_arithmetic import build
        from src.local_runner.semantic_report import reference_document
        current=json.loads((BATCH/'AUR/publish/output/AUR/latest.json').read_text(encoding='utf-8'))
        context=json.loads((BATCH/'AUR/input.json').read_text(encoding='utf-8'))
        anchor=context['sol_reference']
        original=deepcopy((current,anchor,context))
        payload,review,md=build(current,anchor,context,'s13',datetime(2026,10,9,12,tzinfo=timezone.utc))
        self.assertEqual((current,anchor,context),original)
        self.assertEqual(payload['plan']['entry_strength_score'],63)
        self.assertEqual(payload['generation_provider'],'manual')
        self.assertEqual(review['model_calls'],[])
        self.assertEqual(payload['last_full_report_at'],current['last_full_report_at'])
        old=reference_document(current,verify_projection=True)
        corrected=reference_document(payload,verify_projection=True)
        self.assertEqual(corrected['text_provenance'],old['text_provenance'])
        self.assertEqual(corrected['summary'],old['summary'])
        self.assertEqual(corrected['metadata'],old['metadata'])
        self.assertEqual(corrected['conclusion'],old['conclusion'])
        self.assertEqual(corrected['plan']['entry']['reason'],old['plan']['entry']['reason'])
        sys.path.insert(0,str(ROOT/'gcp_services/stock_controller/src'))
        from stock_analysis.analysis_worker.reports import parse_analysis_report
        record=parse_analysis_report('AUR',payload,report_url_template='{ticker}')
        self.assertEqual(record.entry_strength,63)



    def test_one_repair_then_visible_failure_without_full_sol(self):
        import hashlib
        import tempfile
        from contextlib import ExitStack
        from unittest.mock import patch
        from src.local_runner import adaptive_stage as stage
        from src.local_runner.adaptive_context import serialize_model_input
        context,value=fixture()
        # Offline responses are test fixtures, never written as real model receipts.
        for corrected in (True,False):
            calls=[]
            def call(repo,work,symbol,budget,policy,kind,data,**kwargs):
                calls.append(kind)
                self.assertIn(kind,('triage','triage_repair'))
                candidate=deepcopy(value)
                if kind=='triage_repair' and corrected:
                    candidate['update']['plan']['entry']['strength']['components']['volumen']=12
                view=model_context(data);view.pop('research_memory',None)
                return dict(text=json.dumps(candidate),exit_code=0,
                    input_sha256=hashlib.sha256(serialize_model_input(view).encode()).hexdigest(),
                    completed_at='2026-10-09T12:00:00+00:00',model='offline-test-fixture')
            with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
                work=Path(directory)/'AUR';work.mkdir()
                policy=json.loads((ROOT/'config/codex_analysis.json').read_text(encoding='utf-8'));policy['routing_revision']=25
                stage.write_json(work/'input.json',context);stage.write_json(work/'policy.json',policy)
                stack.enter_context(patch.object(stage,'model_call',side_effect=call))
                stack.enter_context(patch.object(stage,'itv_state',return_value={'due':False}))
                stack.enter_context(patch.object(stage,'save_research'))
                if corrected:
                    review=stage.analyze(ROOT,work,'AUR',Path(directory)/'budget.json',False)
                    self.assertEqual(review['status'],'updated')
                    self.assertEqual(stage.read_json(work/'publish/output/AUR/latest.json')['plan']['entry_strength_score'],63)
                else:
                    with self.assertRaisesRegex(RuntimeError,'volume_arithmetic_failed_no_sol'):
                        stage.analyze(ROOT,work,'AUR',Path(directory)/'budget.json',False)
                    self.assertEqual(stage.read_json(work/'update_rejected.json')['next'],'failed_volume_arithmetic_no_sol')
                self.assertEqual(calls,['triage','triage_repair'])

    def test_mixed_risk_error_is_not_classified_as_arithmetic_only(self):
        from src.local_runner.volume_arithmetic import arithmetic_only, PREFIX
        error=ValueError(PREFIX+'entry')
        self.assertTrue(arithmetic_only(error))
        error.maintenance_details={'issues':[{'error':PREFIX+'entry'},{'error':'update_not_allowed_uncertain_or_critical'}]}
        self.assertFalse(arithmetic_only(error))



    def test_new_preparation_adds_contract_without_mutating_frozen24(self):
        import tempfile
        from contextlib import ExitStack
        from unittest.mock import patch
        from src.local_runner import adaptive_stage as stage
        data=json.loads((BATCH/'AUR/input.json').read_text(encoding='utf-8'))
        policy=json.loads((ROOT/'config/codex_analysis.json').read_text(encoding='utf-8'));policy['routing_revision']=25
        files=['instructions.md','triage_instructions.md','policy.json']
        frozen={name:(BATCH/'AUR'/name).read_bytes() for name in files}
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            work=Path(directory)/'AUR';work.mkdir()
            for name,result in [('load_policy',policy),('load_reference_payload',data['sol_reference']),
                                ('load_current_report',data['reference']),('load_research',None)]:
                stack.enter_context(patch.object(stage,name,return_value=result))
            for name,result in [('_fetch_slim',data['slim']),('_load_analyst_quality',{}),
                ('load_compact_analyst_summary',{}),('load_recent_analyst_actions',data['analyst_actions']),
                ('load_recent_news',data['news']),('_load_system_prompt','legacy')]:
                stack.enter_context(patch.object(stage.one,name,return_value=result))
            stack.enter_context(patch.object(stage,'call_codex',side_effect=AssertionError('NO MODEL')))
            stage.prepare(ROOT,work,'AUR',data['owned'],data['tier'])
            for name in ('instructions.md','triage_instructions.md'):
                self.assertIn('Revision25',(work/name).read_text(encoding='utf-8'))
                self.assertIn('>=1,5x=2',(work/name).read_text(encoding='utf-8'))
            self.assertEqual(stage.read_json(work/'policy.json')['routing_revision'],25)
        self.assertEqual(frozen,{name:(BATCH/'AUR'/name).read_bytes() for name in files})

if __name__ == '__main__': unittest.main()
