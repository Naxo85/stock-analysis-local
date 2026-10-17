"""Offline original-incident and no-regression checks. No model/network calls."""
import copy
import json
import logging
from pathlib import Path
import sys
import tempfile
import tarfile
import types
from contextlib import ExitStack
import unittest
from unittest.mock import Mock, patch
from flask import Flask, request
import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests'))
_prior_log_level = logging.getLogger().level
from test_support_resistances_slim_evidence import raw, slim, _daily_bars
logging.getLogger().setLevel(_prior_log_level)
from src.local_runner.technical_preparation import avwap_anchors, require_capture
from src.local_runner.volume_rubric import volume_ceiling, observations
from src.local_runner import adaptive_stage as stage

BATCH = ROOT / 'logs/batch/2026-10-08/19-49-44/adaptive'


class Capture23(unittest.TestCase):
    def invoke_raw(self, module, *, fail_options=False, overview_error=False, no_options=False):
        bars = _daily_bars(260)
        expiry = (raw.datetime.now(raw.timezone.utc) + raw.timedelta(days=7)).date().isoformat()
        def wire(url, **kwargs):
            if url.endswith('/expirations'):
                if no_options:
                    return Mock(text='<expirations/>')
                return Mock(text='<expirations><date>'+expiry+'</date></expirations>')
            self.assertTrue(url.endswith('/chains'))
            return Mock(text='<options>'+''.join(
                '<option><strike>100</strike><option_type>'+kind+'</option_type>'
                '<open_interest>100</open_interest><greeks><gamma>0.01</gamma></greeks>'
                '<bid>2</bid><ask>3</ask><last>2.5</last></option>' for kind in ('call','put'))+'</options>')
        with ExitStack() as stack:
            stack.enter_context(patch.object(module, 'TRADIER_TOKEN', 'offline-fixture'))
            stack.enter_context(patch.object(module, '_tradier_quote', return_value={'last':101,'high':102,'low':99,'volume':1000,'bid':100.9,'ask':101.1}))
            stack.enter_context(patch.object(module, '_tradier_history_daily', return_value=bars))
            publish=stack.enter_context(patch.object(module, '_publish_symbol_json', return_value='offline'))
            get=stack.enter_context(patch.object(module.requests, 'get', side_effect=wire))
            if fail_options:
                helper='_pick_expiration_around_1w' if fail_options is True else fail_options
                stack.enter_context(patch.object(module, helper, side_effect=requests.Timeout('offline')))
            if overview_error:
                stack.enter_context(patch.object(module, '_put_call_oi_views', return_value={'near_term':{'error':'failed'}}))
            stack.enter_context(patch.object(module.tlogger, 'error'))
            stack.enter_context(Flask(__name__).test_request_context('/?symbol=TEST'))
            response, status=module.support_resistances_raw(request)
            return response.get_json(), status, get.call_count, publish.call_count

    def test_whole_capture_matches_deployed_baseline_with_fewer_requests(self):
        previous=types.ModuleType('raw_before23')
        with tarfile.open(ROOT/'.local/raw-before23.tgz') as archive:
            source=archive.extractfile('main.py').read().decode('utf8')
        exec(compile(source,'raw_before23.py','exec'),previous.__dict__)
        logging.getLogger().setLevel(_prior_log_level)
        old, old_status, old_calls, _=self.invoke_raw(previous)
        new, new_status, new_calls, _=self.invoke_raw(raw)
        self.assertEqual((old_status,new_status),(200,200))
        self.assertEqual(new['options'].pop('status'),'ok')
        self.assertEqual(new.pop('observed_origins'),[])
        self.assertEqual(new.pop('price_history')['status'],'available')
        old.pop('as_of'); new.pop('as_of')
        # Revisions26/28/31 intentionally add calibrated reactions, completed
        # history and option quote detail. Their own tests check those fields;
        # all pre23 financial values and ranking must still remain identical.
        def without_reactions(value):
            if isinstance(value, dict):
                return {k: without_reactions(v) for k, v in value.items()
                        if k not in ('historical_reaction','option_details','bid_date','ask_date')}
            if isinstance(value, list):
                return [without_reactions(v) for v in value]
            return value
        new, old = without_reactions(new), without_reactions(old)
        self.assertEqual(new,old)
        self.assertEqual(new_calls,2)
        self.assertGreater(old_calls,new_calls)

    def test_whole_capture_fails_before_mirroring_on_options_error(self):
        result,status,_,published=self.invoke_raw(raw,fail_options=True)
        self.assertEqual(status,502)
        self.assertEqual(result['error'],'options_capture_failed')
        self.assertEqual(published,0)

    def test_no_wall_or_overview_exception_becomes_successful_empty_data(self):
        for helper in ('_compute_callwall_gamma','_compute_top_callwalls_gamma',
                       '_compute_putwall_gamma','_compute_top_putwalls_gamma','_put_call_oi_views'):
            with self.subTest(helper=helper):
                result,status,_,published=self.invoke_raw(raw,fail_options=helper)
                self.assertEqual(status,502)
                self.assertEqual(result['error'],'options_capture_failed')
                self.assertEqual(published,0)
        result,status,_,published=self.invoke_raw(raw,overview_error=True)
        self.assertEqual((status,published),(502,0))

    def test_whole_capture_without_listed_expiries_is_still_successful(self):
        result,status,_,published=self.invoke_raw(raw,no_options=True)
        self.assertEqual((status,published),(200,1))
        self.assertEqual(result['options']['status'],'no_future_expirations')
        require_capture(slim._build_slim(result))

    def test_option_download_reused_inside_request_not_between_requests(self):
        response = Mock(text='<expirations><date>2026-10-16</date></expirations>')
        app = Flask(__name__)
        with patch.object(raw.requests, 'get', return_value=response) as get:
            with app.test_request_context('/'):
                self.assertEqual(raw._tradier_option_expirations('ABC'), ['2026-10-16'])
                raw._tradier_option_expirations('ABC')
                self.assertEqual(get.call_count, 1)
                raw._tradier_option_expirations('XYZ')
                self.assertEqual(get.call_count, 2)
            with app.test_request_context('/'):
                raw._tradier_option_expirations('ABC')
                self.assertEqual(get.call_count, 3)

    def test_error_not_cached_or_mistaken_for_no_options(self):
        app = Flask(__name__)
        bad = Mock(text='<errors><error>Provider failed</error></errors>')
        good = Mock(text='<expirations/>')
        with patch.object(raw.requests, 'get', side_effect=[requests.Timeout(), bad, good]) as get:
            with app.test_request_context('/'):
                with self.assertRaises(requests.Timeout): raw._tradier_option_expirations('ABC')
                with self.assertRaises(ValueError): raw._tradier_option_expirations('ABC')
                self.assertEqual(raw._tradier_option_expirations('ABC'), [])
                raw._tradier_option_expirations('ABC')
                self.assertEqual(get.call_count, 3)

    def test_chain_request_identity_includes_expiry_and_greeks(self):
        response = Mock(text='<options/>')
        with patch.object(raw.requests, 'get', return_value=response) as get:
            with Flask(__name__).test_request_context('/'):
                for expiry in ('2026-10-09', '2026-10-16', '2026-10-09'):
                    raw._tradier_options_chain('ABC', expiry)
                self.assertEqual(get.call_count, 2)

    def test_original_asml_rejected_before_model_not_frozen_for_retry(self):
        data = json.loads((BATCH/'ASML/input.json').read_text(encoding='utf8'))
        original = copy.deepcopy(data)
        with self.assertRaisesRegex(RuntimeError, 'options_capture'):
            require_capture(data['slim'])
        policy = dict(data.get('policy') or {}, routing_revision=23)
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            with patch.object(stage, 'load_policy', return_value=policy), \
                 patch.object(stage, 'load_reference_payload', return_value=data['reference']), \
                 patch.object(stage, 'load_current_report', return_value=data['reference']), \
                 patch.object(stage.one, '_fetch_slim', return_value=data['slim']) as fetch, \
                 patch.object(stage, 'model_call') as model:
                for _ in range(2):
                    with self.assertRaisesRegex(RuntimeError, 'options_capture'):
                        stage.prepare(ROOT, work, 'ASML', False, 'normal')
                self.assertEqual(fetch.call_count, 2)
                model.assert_not_called()
                self.assertFalse((work/'input.json').exists())
        self.assertEqual(data, original)

    def test_successful_no_options_is_valid_instead_of_forced_failure(self):
        require_capture({'options': {'status': 'no_future_expirations', 'expirations': []}})
        require_capture({'options': {'status': 'ok', 'gamma_regime': 'neutral', 'expirations': [{'date':'2026-10-09'}]}})
        for options in ({}, {'status':'error'}, {'status':'ok','expirations':[]},
                        {'status':'no_future_expirations','expirations':[{}]}):
            with self.assertRaises(RuntimeError): require_capture({'options':options})

    def test_exact_anchor_is_observed_even_when_not_in_candidate_list(self):
        bars = _daily_bars()
        anchor = bars[20]['date']
        observed = raw._observe_avwap_anchors([anchor], bars)
        self.assertAlmostEqual(observed[0]['level'], raw._avwap_from_date(bars, anchor), places=4)
        out = slim._build_slim({'latest_price':observed[0]['level']*.99, 'observed_origins':observed,
                               'options':{'status':'no_future_expirations'}})
        self.assertEqual(out['levels']['supports'], [])
        self.assertEqual(out['levels']['observed_origins'][0]['date'], anchor)
        self.assertEqual(out['levels']['observed_origins'][0]['status'], 'available')
        require_capture(out, [anchor])
        with self.assertRaisesRegex(RuntimeError,'avwap_observation_missing'):
            require_capture(out, ['2020-01-01'])

    def test_missing_anchor_does_not_shift_to_later_history(self):
        bars = _daily_bars()
        rows = raw._observe_avwap_anchors(['2020-01-01', '2030-01-01'], bars)
        self.assertTrue(all(row['status']=='unavailable' and row['level'] is None for row in rows))
        bars[30]['volume'] = None
        self.assertEqual(raw._observe_avwap_anchors([bars[20]['date']], bars)[0]['status'], 'unavailable')

    def test_observed_coordinate_is_usable_origin_only_when_available(self):
        from src.local_runner.semantic_report import _origin_present
        context={'routing_revision':23,'slim':{'as_of':'2026-10-08T20:00:00Z',
            'levels':{'observed_origins':[{'level':100,'status':'available'}]}}}
        self.assertTrue(_origin_present({'lower':99,'upper':101},context,'entry'))
        context['slim']['levels']['observed_origins'][0]['status']='unavailable'
        self.assertFalse(_origin_present({'lower':99,'upper':101},context,'entry'))
        context['slim']['levels']['observed_origins'][0]['status']='available'
        context['routing_revision']=22
        self.assertFalse(_origin_present({'lower':99,'upper':101},context,'entry'))

    def test_original_lrcx_requests_defining_gap_date(self):
        data = json.loads((BATCH/'LRCX/input.json').read_text(encoding='utf8'))
        anchors = avwap_anchors(data['reference'], data['sol_reference'])
        self.assertIn('2026-08-04', anchors)
        self.assertEqual(anchors, sorted(set(anchors)))

    def test_slim_forwards_anchor_without_interpreting_it(self):
        response = Mock()
        response.json.return_value = {'symbol':'ABC'}
        with patch.object(slim.requests, 'get', return_value=response) as get:
            slim._fetch_raw('ABC', avwap_anchors='2026-08-04')
        self.assertEqual(get.call_args.kwargs['params'], {'symbol':'ABC','avwap_anchors':'2026-08-04'})


class Rubric23(unittest.TestCase):
    def test_v23_pipeline_keeps_one_call_and_itv_and_null_entry_contract(self):
        import test_buy_support_v22 as v22
        prior=v22.prior
        fixture=prior.data()
        fixture['routing_revision']=23
        fixture['slim'].setdefault('options',{}).update(status='ok',gamma_regime='positive',expirations=[{'date':'2026-10-16'}])
        from src.local_runner.adaptive_context import model_context
        view=model_context(fixture)
        maintenance,report=v22.no_entry(view),v22.full(view)
        for due in (False,True):
            with patch.object(prior,'data',return_value=copy.deepcopy(fixture)), \
                 patch.object(prior,'verdict',return_value=copy.deepcopy(maintenance)), \
                 patch.object(prior,'full',return_value=copy.deepcopy(report)):
                review,output,calls=prior.SemanticPipelineTests().run_case(revision=23,due=due,expected_entry=None)
            self.assertEqual([kind for kind,_ in calls],['report'] if due else ['triage'])
            self.assertEqual(review['status'],'regenerated' if due else 'updated')
            if not due: self.assertEqual(output['last_full_report_at'],fixture['sol_reference']['generated_at'])
            self.assertIsNone(output['plan']['entry'])

    def evidence(self, distance):
        return {'volume_profile':{'status':'available','nearest_abs_distance_pct':distance},
                'historical_reaction':{'status':'available','test_count':8,'defense_count':6,
                'defense_rate_pct':75,'last_test_date':'2026-10-07','median_rebound_5d_pct':4,
                'defense_min_rebound_pct':2}}

    def test_exact_existing_rubric_boundaries(self):
        for distance, expected in ((5.01,12),(5,15),(4.67,15),(3.01,15),(3,18),(1.51,18),(1.5,20)):
            self.assertEqual(volume_ceiling(self.evidence(distance),'2026-10-08T20:00:00Z')['ceiling_from_this_record'], expected)

    def test_other_gates_remain_required(self):
        data=self.evidence(1)
        data['historical_reaction']['defense_count']=1
        self.assertEqual(volume_ceiling(data,'2026-10-08T20:00:00Z')['ceiling_from_this_record'],12)
        data=self.evidence(1)
        data['historical_reaction']['defense_rate_pct']=50
        self.assertEqual(volume_ceiling(data,'2026-10-08T20:00:00Z')['ceiling_from_this_record'],15)
        self.assertEqual(volume_ceiling({},'2026-10-08T20:00:00Z')['ceiling_from_this_record'],4)

    def test_session_date_not_shifted_back_one_day(self):
        self.assertEqual(volume_ceiling(self.evidence(4.67),'2026-10-08T20:00:00Z')['completed_test_age_sessions'],1)

    def test_original_records_exposed_without_mutating_reports(self):
        for ticker in ('MU','CRDO'):
            data=json.loads((BATCH/ticker/'input.json').read_text(encoding='utf8'))
            before=copy.deepcopy(data)
            result=observations(data)
            self.assertTrue(result['records'])
            self.assertEqual(data,before)
            self.assertIn('NOT assigned scores',result['scope'])
            ceilings=[]
            for side in ('slim','reference','sol_reference'):
                snapshot=data[side] if side=='slim' else data[side].get('slim_snapshot',{})
                for rows in snapshot.get('levels',{}).values():
                    for row in rows:
                        ev=row.get('evidence') or {}
                        if (ev.get('volume_profile') or {}).get('nearest_abs_distance_pct') == (4.67 if ticker=='MU' else 4.75):
                            ceilings.append(volume_ceiling(ev,snapshot.get('as_of'))['ceiling_from_this_record'])
            self.assertIn(15,ceilings)

    def test_new_policy_preserves_old_contracts_and_risk_authority(self):
        old=(ROOT/'prompts/daily_maintenance_semantic_v22.md').read_text(encoding='utf8')
        new=(ROOT/'prompts/daily_maintenance_semantic_v23.md').read_text(encoding='utf8')
        shared=(ROOT/'prompts/adaptive_revision23.md').read_text(encoding='utf8')
        self.assertIn('correction of Sol',old)
        self.assertNotIn('correction of Sol',new)
        self.assertIn('Authorship is not an escalation criterion',shared)
        self.assertIn('Any true flag prevents Luna publication',new)
        self.assertIn('no-entry alone does NOT force a full report',shared)


if __name__ == '__main__': unittest.main()
