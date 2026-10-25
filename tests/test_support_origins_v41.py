"""Source41 directed origin contract: no network/model/publication in tests."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from flask import Flask, request
import pytest

from test_support_resistances_slim_evidence import raw, slim
from gcp_functions.support_resistances_raw.support_origins import (
    canonical_request, parse_support_origins, request_key, observe_support_origins)

ROOT = Path(__file__).resolve().parents[1]
AT = datetime.fromisoformat('2026-10-18T10:00:00+00:00')
REQUESTS = {
    'CLS': {'type': 'range_bottom_3_6m', 'level': 290.88, 'date': '2026-08-19', 'touches': 2},
    'WDC': {'type': 'gap_up_lower', 'level': 312.2, 'date': '2026-04-08'},
    'LRCX': {'type': 'range_bottom_3_6m', 'level': 251.89, 'date': '2026-07-29', 'touches': 2},
}


def original(ticker):
    path = ROOT/'logs/batch/2026-10-18/09-08-40/adaptive'/ticker/'input.json'
    if not path.exists():
        pytest.skip('local archived corpus unavailable')
    inp = json.loads(path.read_text(encoding='utf-8'))
    for archive_path in (ROOT/'data/technical_archive'/ticker).glob('*.json'):
        archive = json.loads(archive_path.read_text(encoding='utf-8'))
        if archive['snapshot_at'] == inp['slim']['as_of']:
            return inp, archive['daily']['rows']
    pytest.skip('matching technical archive unavailable')


def observe(ticker, requests=None, rows=None):
    inp, saved = original(ticker)
    return raw._observe_support_origins(requests or [REQUESTS[ticker]], saved if rows is None else rows,
        inp['slim']['technicals']['atr10'], datetime.fromisoformat(inp['slim']['as_of']),
        inp['slim']['volume_profile'])


@pytest.mark.parametrize('ticker', REQUESTS)
def test_original_omitted_origin_reobserved_with_exact_dates_and_source_record(ticker):
    inp, bars = original(ticker)
    before = deepcopy(bars)
    with patch.object(raw.requests, 'get', side_effect=AssertionError('no network')):
        observations, pool = observe(ticker)
    observation = observations[0]
    assert bars == before
    assert observation['status'] == 'available'
    assert observation['requested_identity'] == REQUESTS[ticker]
    assert observation['source_record']['level'] == REQUESTS[ticker]['level']
    assert observation['observation_scope']['available_is_not_viability'] is True
    assert all(item['level'] != observation['level'] for item in inp['slim']['levels']['supports'])
    projected = slim._build_slim({'data_contract_revision': 41, 'latest_price': inp['slim']['latest_price'],
                                 'support_origins': observations})['levels']['support_origins'][0]
    assert projected['source_record']['date'] == REQUESTS[ticker]['date']
    assert projected['source_record']['origin_identity']['availability_date'] <= '2026-10-16'
    assert projected['evidence'] == projected['source_record']['evidence']
    assert 'strength_score' not in projected['source_record']
    assert 'prob_touch_1w_pct' not in projected['source_record']


def test_lrcx_directed_origin_is_independent_of_both_5pct_and_winner():
    inp, rows = original('LRCX')
    atr = raw._atr10_from_daily(rows)
    clusters = raw._cluster_swing_lows(raw._find_swing_lows(rows[-126:]), .2 * atr)
    winner = raw._select_range_bottom_cluster(clusters, inp['slim']['latest_price'], None,
        .2 * atr, raw._median([row['volume'] for row in rows[-126:]]), 0)
    assert round(winner['level'], 4) == 264.54
    assert observe('LRCX')[0][0]['level'] == 251.89
    assert raw.MIN_RANGE_DISTANCE_PCT == raw.MIN_GAP_DISTANCE_PCT == raw.MIN_AVWAP_DISTANCE_PCT == .05


@pytest.mark.parametrize('bad', [None, {}, 'null', 'false', '[{}]', '[{"type":"other"}]',
    '[{"type":"gap_up_lower","level":312.2,"level":300,"date":"2026-04-08"}]'])
def test_invalid_request_is_not_interpreted_as_an_origin(bad):
    if bad is None:
        assert parse_support_origins(bad) == []
    else:
        with pytest.raises(ValueError):
            parse_support_origins(bad)


@pytest.mark.parametrize('field,value', [('level', True), ('level', float('nan')), ('level', 0),
    ('date', '2026-4-8'), ('date', '2026-02-30'), ('touches', True), ('touches', 1), ('typo', 3)])
def test_invalid_numeric_dates_or_fields_rejected(field, value):
    row = dict(REQUESTS['CLS']); row[field] = value
    with pytest.raises(ValueError):
        canonical_request(row)


def test_dedup_and_order_independent_request_identity():
    a, b = REQUESTS['CLS'], REQUESTS['WDC']
    assert parse_support_origins(json.dumps([b, a, a])) == parse_support_origins([a, b])
    assert request_key(a) == request_key(dict(reversed(list(a.items()))))


@pytest.mark.parametrize('field,value', [('level', 290.8801), ('date', '2026-08-18'), ('touches', 3)])
def test_no_nearest_level_date_or_touch_substitution(field, value):
    bad = dict(REQUESTS['CLS']); bad[field] = value
    obs = observe('CLS', [bad])[0][0]
    assert obs['status'] == 'not_observed'
    assert obs['observation_reason'] == 'legacy_identity_not_reconstructed_in_current_pool'
    assert obs['level'] is obs['source_record'] is None


def test_ambiguous_pool_and_missing_history_are_unavailable_not_loss():
    _, bars = original('CLS')
    observations, pool = observe('CLS')
    matching = observations[0]['source_record']
    duplicate = observe_support_origins([REQUESTS['CLS']], bars, [matching, matching], AT.isoformat())[0]
    assert duplicate['status'] == 'unavailable'
    assert duplicate['observation_reason'] == 'ambiguous_legacy_identity'
    missing = observe('CLS', rows=bars[-20:])[0][0]
    assert missing['status'] == 'unavailable' and 'insufficient_history' in missing['observation_reason']


def test_new_identity_reconstructs_exact_members_when_ranking_pool_changes():
    _, bars = original('CLS')
    record = observe('CLS')[0][0]['source_record']
    directed = dict(REQUESTS['CLS'], origin_identity=record['meta']['origin_identity'])
    result = observe_support_origins([directed], bars, [], AT.isoformat())[0]
    assert result['status'] == 'available' and result['level'] == 290.88
    assert result['source_record']['meta']['origin_identity'] == directed['origin_identity']


@pytest.mark.parametrize('mutation', ['missing_bar', 'invalid_bar', 'adjusted_value', 'duplicate_date', 'missing_confirmation'])
def test_dated_identity_does_not_relabel_broken_or_changed_history(mutation):
    _, bars = original('CLS'); bars = deepcopy(bars)
    record = observe('CLS')[0][0]['source_record']
    identity = record['meta']['origin_identity']
    directed = dict(REQUESTS['CLS'], origin_identity=identity)
    index = next(i for i, row in enumerate(bars) if row['date'] == identity['formation_dates'][0])
    if mutation == 'missing_bar': del bars[index - 1]
    elif mutation == 'invalid_bar': bars[index]['low'] = None
    elif mutation == 'adjusted_value': bars[index]['low'] -= 1
    elif mutation == 'duplicate_date': bars.insert(index, deepcopy(bars[index]))
    else: bars = bars[:index + 2]
    result = observe_support_origins([directed], bars, [], AT.isoformat())[0]
    assert result['status'] == 'unavailable'
    assert result['source_record'] is None and result['level'] is None


def test_future_rows_cannot_complete_pivot_confirmation():
    inp, bars = original('CLS')
    identity = observe('CLS')[0][0]['source_record']['meta']['origin_identity']
    cutoff = identity['formation_dates'][-1]
    directed = dict(REQUESTS['CLS'], origin_identity=identity)
    observed_at = datetime.fromisoformat(cutoff + 'T20:30:00+00:00')
    result = raw._observe_support_origins([directed], bars, 20, observed_at)[0][0]
    assert result['status'] == 'unavailable' and result['source_record'] is None


def test_slim_opt_in_preserves_exact_query_and_legacy_omits_new_field():
    for query in ['', '&support_origins=[]']:
        with patch.object(slim, '_fetch_raw', return_value={}) as fetch:
            with Flask('origins').test_request_context('/?symbol=CLS' + query):
                response, status = slim.support_resistances_slim(request)
        assert status == 200
        assert ('support_origins' in fetch.call_args.kwargs) is bool(query)
        assert 'support_origins' not in response.get_json()['levels']
    with patch.object(slim.requests, 'get') as get:
        get.return_value.json.return_value = {}
        slim._fetch_raw('CLS', support_origins='[]')
        assert get.call_args.kwargs['params'] == {'symbol': 'CLS', 'support_origins': '[]'}


def test_all_frozen_typed_origins_replay_without_mutating_originals():
    audit = ROOT/'docs/audit_support_constraints_20261019/discovery/discovery_replay.json'
    if not audit.exists(): pytest.skip('audit unavailable')
    rows = json.loads(audit.read_text(encoding='utf-8'))['results']
    checked = omitted = 0
    for row in rows:
        requests = [canonical_request({k: v for k, v in item['prior_identity'].items() if v is not None})
                    for item in row['targeted_current_origin_check']]
        if not requests: continue
        observations, _ = observe(row['symbol'], requests)
        assert all(item['status'] == 'available' for item in observations)
        checked += len(requests)
        omitted += sum(not item['selected_in_current_slim'] for item in row['targeted_current_origin_check'])
    assert checked == 20 and omitted == 9


def test_full_handler_opt_in_reuses_same_acquisition_preserves_ranking_and_legacy():
    from test_technical_archive_v40 import invoke_raw, bars, AT as fixture_at
    baseline, count, _ = invoke_raw(raw, False, False)
    _, pool = raw._observe_support_origins([], bars(), 3, datetime.fromisoformat(fixture_at))
    source = next(item for item in pool if item['type'] == 'range_bottom_3_6m')
    identity = raw._support_source_identity(source)
    query = '&support_origins=' + quote(json.dumps([identity]))
    context = Flask.test_request_context
    def directed_context(app, path, *args, **kwargs):
        return context(app, path + query, *args, **kwargs)
    with patch.object(Flask, 'test_request_context', directed_context):
        observed, observed_count, _ = invoke_raw(raw, False, False)
    assert count == observed_count
    assert observed['support_origins'][0]['status'] == 'available'
    assert observed['call_walls_top'] == baseline['call_walls_top']
    assert observed['put_walls_top'] == baseline['put_walls_top']
    projected_baseline = slim._build_slim(baseline)
    projected_observed = slim._build_slim(observed)
    projected_observed['levels'].pop('support_origins')
    for support in projected_observed['levels']['supports']:
        support.pop('origin_identity', None)
        support.pop('origin_details', None)
    assert projected_observed == projected_baseline
    observed.pop('support_origins')
    for support in observed['supports']:
        support['meta'].pop('origin_identity', None)
    assert observed == baseline
    assert 'support_origins' not in baseline


def test_invalid_query_fails_before_any_acquisition_or_mirror():
    with patch.object(raw, '_tradier_quote') as acquire, patch.object(raw, '_publish_symbol_json') as mirror:
        with Flask('invalid-support').test_request_context('/?symbol=CLS&support_origins=oops'):
            response, status = raw.support_resistances_raw(request)
    assert status == 400 and response.get_json()['error'] == 'invalid_support_origins'
    acquire.assert_not_called(); mirror.assert_not_called()


@pytest.mark.parametrize('ticker,missing_date', [('WDC', '2026-04-09'), ('CLS', '2026-08-24'),
                                               ('WDC', '2026-10-16'), ('CLS', '2026-10-16')])
def test_missing_post_formation_session_does_not_invent_complete_reactions(ticker, missing_date):
    _, bars = original(ticker)
    incomplete = [row for row in bars if row['date'] != missing_date]
    observation = observe(ticker, rows=incomplete)[0][0]
    assert observation['status'] == 'available'
    meta = observation['source_record']['meta']
    assert meta['historical_reaction']['status'] == 'unavailable'
    assert meta['historical_reaction']['reason'] == 'missing_historical_session'
    if ticker == 'WDC':
        assert meta['gap_history_status'] == 'unavailable_missing_following_session'
        assert 'filled' not in meta and 'touches_since_gap' not in meta


def test_unverified_formation_is_not_promoted_to_ordinary_candidate_identity():
    _, bars = original('WDC')
    incomplete = [row for row in bars if row['date'] != '2026-04-07']
    _, pool = observe('WDC', rows=incomplete)
    assert not any(record['type'] == 'gap_up_lower' and record['meta']['gap_date'] == '2026-04-08'
                   for record in pool)


def test_slim_legacy_level_function_has_no_new_identity_fields():
    record = slim._slim_levels([{'type': 'gap_up_lower', 'level': 10, 'meta': {}}], 12)[0]
    assert 'origin_identity' not in record and 'origin_details' not in record
