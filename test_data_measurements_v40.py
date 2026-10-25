"""Offline acquisition regressions: no broker, paid model or publication."""
import asyncio
import json
from ib_insync import IB
import sys
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests'))
from test_support_resistances_slim_evidence import raw, slim
from src.local_runner.ibkr_analyst_probe import _request_complete_historical_news, require_complete_news_payload
from src.local_runner import ibkr_news_update, ibkr_analyst_update
from src.local_runner.technical_preparation import require_price_history, require_capture
from gcp_functions.support_resistances_raw.market_sessions import latest_completed_session, market_session


def dt(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


class FakeIB(IB):
    """Use the real wrapper/future protocol without a broker or socket."""
    def __init__(self, result, terminal=False, error=None):
        super().__init__()
        # Freeze the bound-method object so the original identity assertion stays exact.
        self.wrapper.historicalNewsEnd = self.wrapper.historicalNewsEnd
        self.result, self.terminal, self.error = result, terminal, error
        self.client.getReqId = lambda: 17
        self.client.reqHistoricalNews = self._historical_request

    def _historical_request(self, req_id, *args):
        assert self.RaiseRequestErrors is True
        if self.error:
            raise self.error
        if self.result is None:
            self.wrapper._endReq(req_id, asyncio.TimeoutError(), success=False)
            return
        self.wrapper._results[req_id] = self.result
        if self.terminal is not None:
            self.wrapper.historicalNewsEnd(req_id, self.terminal)
        else:
            self.wrapper._endReq(req_id)


@pytest.mark.parametrize('count', [0, 1, 300])
def test_completed_news_including_saturated_empty_has_actual_terminal(count):
    ib = FakeIB([object()] * count)
    original = ib.wrapper.historicalNewsEnd
    rows, coverage = _request_complete_historical_news(ib, 1, 'DJ-N', '', '', 300)
    assert len(rows) == count and coverage['has_more'] is False
    require_complete_news_payload({'coverage': coverage})
    assert ib.wrapper.historicalNewsEnd is original and not ib.RaiseRequestErrors


@pytest.mark.parametrize('result,terminal,error,reason', [
    (None, None, None, 'timeout'),
    ([], None, None, 'terminal coverage unknown'),
    ([1], True, None, 'provider_has_more'),
    ([], False, RuntimeError('denied'), 'failed'),
])
def test_news_incomplete_or_error_never_becomes_completed_empty(result, terminal, error, reason):
    ib = FakeIB(result, terminal, error)
    original = ib.wrapper.historicalNewsEnd
    with pytest.raises(RuntimeError, match=reason):
        _request_complete_historical_news(ib, 1, 'DJ-N', '', '', 300)
    assert ib.wrapper.historicalNewsEnd is original and not ib.RaiseRequestErrors


def test_news_compactor_rejects_unverified_payload():
    with pytest.raises(RuntimeError, match='coverage_not_verified'):
        ibkr_news_update._compact_payload({'headlines': [], 'generated_at': '2026-10-17'})


@pytest.mark.parametrize('snapshot,expected', [
    ('2026-10-16T16:14:23Z','2026-10-15'),
    ('2026-10-16T20:00:00Z','2026-10-16'),
    ('2026-10-17T01:00:00Z','2026-10-16'),
    ('2026-10-19T12:00:00Z','2026-10-16'),
    ('2026-11-27T17:59:59Z','2026-11-25'),
    ('2026-11-27T18:00:00Z','2026-11-27'),
    ('2026-12-24T18:00:00Z','2026-12-24'),
    ('2026-12-25T20:00:00Z','2026-12-24'),
    ('2026-07-03T20:00:00Z','2026-07-02'),
    ('2026-03-09T19:59:59Z','2026-03-06'),
    ('2026-03-09T20:00:00Z','2026-03-09'),
])
def test_calendar_boundaries_dst_holiday_weekend_and_early_close(snapshot, expected):
    assert latest_completed_session(dt(snapshot)).isoformat() == expected


def bars_ending(day, count=21):
    rows = []
    while len(rows) < count:
        if market_session(day):
            rows.append({'date': day.isoformat(), 'open': 100, 'high': 102, 'low': 98,
                         'close': 100, 'volume': 100})
        day -= timedelta(days=1)
    return list(reversed(rows))


def test_volume_partial_does_not_change_closed_mean_or_last_close_zero_is_observed():
    rows = bars_ending(date(2026, 10, 16), 22)
    rows[-2]['volume'] = 0
    rows[-1]['volume'] = 999999
    with patch.object(raw, '_snapshot_time', return_value=dt('2026-10-16T16:00:00Z')):
        volume = raw._volume_20d_package(rows, {'volume': 999999})
    assert volume['avg_20d'] == 95
    assert volume['last_complete_day'] == {'date': '2026-10-15', 'shares': 0, 'rel_to_20d': 0}
    assert volume['current_session']['comparable_to_avg_20d'] is False


def test_history_current_close_and_short_available_history_are_explicit_not_fabricated():
    now = dt('2026-10-16T20:01:00Z')
    rows = bars_ending(date(2026, 10, 16), 3)
    history = raw._recent_price_history(rows, now)
    assert history['window_complete'] is False and history['observed_sessions'] == 3
    require_price_history({'data_contract_revision': 40, 'as_of': now.isoformat(), 'price_history': history})
    stale = raw._recent_price_history(rows[:-1], now)
    assert stale['reason'] == 'stale_daily_history'
    with pytest.raises(RuntimeError, match='recent_price_history'):
        require_price_history({'data_contract_revision': 40, 'as_of': now.isoformat(), 'price_history': stale})


@pytest.mark.parametrize('value',[0.5,1,1.01,100])
def test_expected_move_units_are_field_contract_not_magnitude(value):
    result = slim._build_slim({'options': {'expected_move_1w': {'percent': value},
                                         'summary_by_expiration': [{'date':'2026-10-23', 'expected_move': {'percent': value}}]}})
    assert result['options']['expected_move_1w_pct'] == value
    assert result['options']['expirations'][0]['expected_move_pct'] == value * 100


def option(side='put', strike=100, oi='10', gamma='0.01', size='100'):
    return ('<option><option_type>'+side+'</option_type><strike>'+str(strike)+'</strike>'
            + ('' if oi is None else '<open_interest>'+oi+'</open_interest>')
            + ('<greeks><updated_at>2026-10-16T15:00:00Z</updated_at>'
               + ('' if gamma is None else '<gamma>'+gamma+'</gamma>') + '</greeks>')
            + '<contract_size>'+size+'</contract_size><symbol>EXACT_OPTION</symbol>'
            + '<bid>1</bid><ask>2</ask><bid_date>1792167176000</bid_date></option>')


def chain(xml):
    with patch.object(raw, '_option_response', return_value=Mock(text='<options>'+xml+'</options>')):
        return raw._tradier_options_chain('TEST', '2026-10-23')


def test_missing_gamma_does_not_erase_oi_quotes_or_exact_identity():
    rows = chain(option(gamma=None) + option(side='call', gamma=None))
    assert len(rows) == 2 and rows[0]['gamma'] is None and rows[0]['oi'] == 10
    assert rows[0]['symbol'] == 'EXACT_OPTION' and rows[0]['greeks_updated_at']
    with patch.object(raw, '_tradier_options_chain', return_value=rows):
        summary = raw._put_call_oi_overview_for_exp_list('TEST', ['2026-10-23'], 'test')
        em = raw._expected_move_1w_via_straddle('TEST', '2026-10-23', 100)
    assert summary['total_put_oi'] == 10 and em['move_abs'] == 3


@pytest.mark.parametrize('value,expected',[(None,None),('-1',None),('nan',None),('0',0)])
def test_unknown_oi_is_not_successful_zero(value, expected):
    rows = chain(option(oi=value))
    assert rows[0]['oi'] == expected
    with patch.object(raw, '_tradier_options_chain', return_value=rows):
        overview = raw._put_call_oi_overview_for_exp_list('TEST', ['2026-10-23'], 'test')
        maximum_pain = raw._max_pain_for_expiration('TEST','2026-10-23')
    assert overview['total_put_oi'] == expected
    assert maximum_pain is None


def test_multiplier_provided_controls_gamma_without_dealer_sign_inference():
    rows = chain(option(size='10'))
    with patch.object(raw, '_tradier_options_chain', return_value=rows), patch.object(raw, '_tradier_option_expirations', return_value=['2026-10-23']):
        gamma = raw._dealer_gamma_summary('TEST', 100, 3)
    assert gamma['gex_total_usd_millions'] == -0.01
    assert gamma['gamma_regime'] is None
    assert gamma['assumed_standard_multiplier_contracts'] == 0


def test_above_quote_put_never_becomes_zero_distance_lower_support():
    result = raw._trend_bias_confidence_1_2w(100, {}, {}, {}, [], [{'distance': 3}])
    assert result['features_flat']['nearest_put_wall_dist_pct'] is None
    assert not any(r['code'] == 'PUTWALL_NEAR' for r in result['rules_triggered'])
    below = raw._trend_bias_confidence_1_2w(100, {}, {}, {}, [], [{'distance': 3}, {'distance': -2}])
    assert below['features_flat']['nearest_put_wall_dist_pct'] == 2


@pytest.mark.parametrize('bid,ask,last,expected',[(0,0,10,10),(12,10,11,11),(-1,1,0,None),(0,0,-1,None),(9,11,12,10)])
def test_numeric_quote_does_not_use_zero_crossed_or_negative_book(bid, ask, last, expected):
    assert raw._extract_latest_price({'bid':bid,'ask':ask,'last':last}) == expected


def test_undated_stale_book_and_previous_close_cannot_masquerade_as_live_quote():
    now = dt('2026-10-16T16:00:00Z')
    old = int(dt('2026-10-15T16:00:00Z').timestamp()*1000)
    current = int(now.timestamp()*1000)
    assert raw._quote_observation({'bid':9,'ask':11,'bid_date':old,'ask_date':old,'prevclose':10},now)['status'] == 'unavailable'
    good = raw._quote_observation({'bid':11,'ask':9,'last':10,'trade_date':current},now)
    assert good['price'] == 10 and good['source'] == 'last_trade'
    assert raw._quote_observation({'last':10},now)['status'] == 'unavailable'


def test_new_measurement_context_has_no_synthetic_probabilities_or_directional_confidence():
    source = {'data_contract_revision':40,'options': {'status':'ok','capture':{'status':'complete'},
              'dealer_gamma':{'gex_total_usd_millions':12,'gamma_regime':'positive'},
              'atm_straddle':{'move_abs':2, 'expiration':'2026-10-23'},
              'summary_by_expiration':[{'date':'2026-10-23','expected_move':{'percent':0.005}}]},
              'supports':[{'level':100,'strength_score':9,'meta':{'prob_touch_1w_pct':20}}]}
    result = slim._build_slim(raw._measurement_contract(source))
    text = json.dumps(result)
    assert 'trend_1_2w' not in result and 'gamma_regime' not in result['options']
    assert result['options']['gamma_concentration']['dealer_position_sign'] == 'unknown'
    assert 'strength_score' not in result['levels']['supports'][0]
    assert 'prob_touch_1w_pct' not in result['levels']['supports'][0]
    assert result['options']['expirations'][0]['expected_move_pct'] == 0.5


def test_legacy_frozen_capture_builder_retains_its_schema_and_input_is_not_mutated():
    source = {'options':{'dealer_gamma':{'gamma_regime':'positive'},'expected_move_1w':{'percent':0.5}},
              'trend_1_2w':{'bias':20,'confidence':80}}
    before = deepcopy(source)
    result = slim._build_slim(source)
    assert source == before and result['trend_1_2w']['confidence'] == 80
    assert 'data_contract_revision' not in result


@pytest.mark.parametrize('producer', ['news','analyst'])
def test_failed_coverage_preserves_last_good_and_does_not_stamp_freshness(tmp_path, producer):
    latest = tmp_path / 'latest.json'
    original = {'as_of':'2026-10-15T20:00:00Z','summary_active':{},'earnings':{}}
    latest.write_text(json.dumps(original), encoding='utf8')
    now = dt('2026-10-16T16:00:00Z')
    incomplete = {'headlines':[], 'coverage':{'status':'unknown'}, 'generated_at':now.isoformat()}
    if producer == 'news':
        with patch.object(ibkr_news_update,'_find_repo_root',return_value=tmp_path), \
             patch.object(ibkr_news_update,'_window_start',return_value=(now,'test')), \
             patch.object(ibkr_news_update,'fetch_ibkr_analyst_headlines',return_value=incomplete), \
             patch.object(ibkr_news_update,'_write_json') as write_json:
            with pytest.raises(RuntimeError,match='coverage_not_verified'):
                ibkr_news_update.main(['TEST'])
            write_json.assert_not_called()
    else:
        with patch.object(ibkr_analyst_update,'_find_repo_root',return_value=tmp_path), \
             patch.object(ibkr_analyst_update,'_current_path',return_value=latest), \
             patch.object(ibkr_analyst_update,'_load_earnings_context',return_value={}), \
             patch.object(ibkr_analyst_update,'_update_start',return_value=now), \
             patch.object(ibkr_analyst_update,'_fetch_provider',return_value=incomplete), \
             patch.object(ibkr_analyst_update,'_write_raw_probe') as write_raw:
            with pytest.raises(RuntimeError,match='coverage_not_verified'):
                ibkr_analyst_update.main(['TEST','--no-seed'])
            write_raw.assert_not_called()
    assert json.loads(latest.read_text(encoding='utf8')) == original


def test_capture40_requires_quote_and_verified_options_but_not_dealer_sign():
    now=dt('2026-10-16T16:00:00Z')
    quote=raw._quote_observation({'last':100,'trade_date':int(now.timestamp()*1000)},now)
    source={'data_contract_revision':40,'as_of':now.isoformat(),'latest_price':100,
            'quote_observation':quote,'options':{'status':'ok','capture':{'status':'complete'},
            'expirations':[{'date':'2026-10-23'}],'gamma_concentration':{'dealer_position_sign':'unknown'}}}
    require_capture(source)
    incomplete=deepcopy(source);incomplete['options'].pop('capture')
    with pytest.raises(RuntimeError,match='options_capture'):require_capture(incomplete)
    incomplete=deepcopy(source);incomplete['quote_observation'].pop('provider_timestamp')
    with pytest.raises(RuntimeError,match='quote_observation'):require_capture(incomplete)


def test_ohlcv_invalid_or_duplicate_or_open_rows_never_admitted():
    now=dt('2026-10-16T16:00:00Z')
    rows=bars_ending(date(2026,10,15),20)
    for field,value in [('high',1),('volume',None),('open',0)]:
        invalid=deepcopy(rows);invalid[-1][field]=value
        assert raw._recent_price_history(invalid,now)['status']=='unavailable'
    assert raw._recent_price_history(rows+rows[-1:],now)['status']=='unavailable'
    assert raw._recent_price_history(rows[:5]+rows[6:],now)['reason']=='missing_recent_session'
    history=raw._recent_price_history(rows,now)
    history['sessions'][-1]['date']='2026-10-16'
    with pytest.raises(RuntimeError,match='recent_price_history'):
        require_price_history({'data_contract_revision':40,'as_of':now.isoformat(),'price_history':history})
