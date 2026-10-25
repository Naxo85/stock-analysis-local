"""Prospective research archive; only mocked transport and copied local originals."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import types
from unittest.mock import Mock, patch
from contextlib import ExitStack
import pytest
from flask import Flask, request
from src.local_runner.technical_archive import (build_capture, build_partial, canonical,
    text_sha256, validate_archive, MAX_RESPONSE_BYTES)
from src.local_runner.archive_technical_observations import (extract_for_model, export_file, write_archive)
from gcp_functions.support_resistances_raw.market_sessions import market_session, latest_completed_session

ROOT = Path.cwd()
AT = '2026-10-16T20:30:00+00:00'
EXP = '2026-10-23'


def bars(count=270):
    day = latest_completed_session(datetime.fromisoformat(AT))
    result = []
    while len(result) < count:
        if market_session(day):
            result.append({'date': day.isoformat(), 'open': 100., 'high': 102., 'low': 99., 'close': 101., 'volume': 10000})
        day -= timedelta(days=1)
    return list(reversed(result))


def responses():
    contract = ('<option><symbol>CAT261023P00100000</symbol><root_symbol>CAT</root_symbol>'
                '<expiration_date>'+EXP+'</expiration_date><strike>100</strike><option_type>put</option_type>'
                '<contract_size>100</contract_size><open_interest>0</open_interest>'
                '<bid>1</bid><ask>2</ask><greeks><gamma>0.02</gamma><updated_at>2026-10-16T20:00:00Z</updated_at></greeks></option>')
    result = []
    for endpoint, params, body in (
        ('expirations', {'symbol': 'CAT'}, '<expirations><date>'+EXP+'</date></expirations>'),
        ('chains', {'symbol': 'CAT', 'expiration': EXP, 'greeks': 'true'}, '<options>'+contract+'</options>')):
        result.append({'endpoint': '/v1/markets/options/'+endpoint, 'params': params,
            'received_at': '2026-10-16T20:30:01+00:00', 'body_text': body, 'body_sha256': text_sha256(body)})
    return result


def capture(rows=None, wire=None, **kwargs):
    return build_capture('CAT', AT, bars() if rows is None else rows,
        responses() if wire is None else wire, expected_expirations=[EXP],
        source_status='ok', source_revision=40, **kwargs)


def reseal(value):
    value['archive_id'] = text_sha256(canonical({k:v for k,v in value.items() if k != 'archive_id'}))
    return value


def test_capture_preserves_received_rows_exact_xml_and_identity(tmp_path):
    original_rows, original_wire = bars(), responses()
    archive = capture(original_rows, original_wire)
    assert archive['daily']['rows'] == original_rows
    assert archive['daily']['coverage']['received_rows'] == 270
    assert archive['daily']['coverage']['window_complete']
    assert archive['options']['responses'] == original_wire
    assert archive['options']['coverage']['sampled_capture_complete']
    assert not archive['options']['coverage']['market_complete']
    assert archive['options']['coverage']['oi_effective_at'] is None
    assert archive['options']['coverage']['wire_contract_count'] == 1
    first = write_archive(tmp_path, archive)
    assert write_archive(tmp_path, deepcopy(archive)) == first
    assert validate_archive(json.loads(Path(first['path']).read_text(encoding='utf-8'))) == archive


@pytest.mark.parametrize('case', ['short', 'gap', 'duplicate', 'invalid'])
def test_history_never_fills_missing_or_invalid_observations(case):
    rows = bars(252)
    if case == 'short': rows = rows[-20:]
    if case == 'gap': rows.pop(120)
    if case == 'duplicate': rows.append(deepcopy(rows[-1]))
    if case == 'invalid': rows[0]['close'] = None
    archive = capture(rows)
    assert archive['daily']['rows'] == rows
    assert archive['daily']['coverage']['window_complete'] is False


def test_uncompleted_bar_preserved_but_excluded_from_252_window():
    rows = bars(252)
    rows.append(dict(rows[-1], date='2026-10-19'))
    archive = capture(rows)
    assert archive['daily']['coverage']['window_complete']
    assert archive['daily']['coverage']['incomplete_or_future_row_indexes'] == [252]


@pytest.mark.parametrize('case', ['body', 'coverage', 'identity', 'headers', 'too_large'])
def test_invalid_archive_does_not_pass_as_complete(case):
    archive = capture()
    if case == 'body': archive['options']['responses'][1]['body_text'] += 'x'
    elif case == 'coverage': archive['daily']['coverage']['received_rows'] = 252
    elif case == 'identity': archive['options']['responses'][1]['params']['symbol'] = 'OTHER'
    elif case == 'headers': archive['options']['responses'][1]['headers'] = {'Authorization': 'fixture-never-secret'}
    else:
        archive['options']['responses'][1]['body_text'] = 'x'*(MAX_RESPONSE_BYTES+1)
        archive['options']['responses'][1]['body_sha256'] = text_sha256(archive['options']['responses'][1]['body_text'])
    reseal(archive)
    with pytest.raises((ValueError, KeyError)):
        validate_archive(archive)


def test_missing_expiration_and_identity_remain_explicit():
    wire = responses()
    incomplete = capture(wire=wire[:1])
    assert not incomplete['options']['coverage']['sampled_capture_complete']
    assert incomplete['options']['coverage']['missing_expected_expirations'] == [EXP]
    wire[1]['body_text'] = wire[1]['body_text'].replace('<contract_size>100</contract_size>', '')
    wire[1]['body_sha256'] = text_sha256(wire[1]['body_text'])
    archive = capture(wire=wire)
    assert archive['options']['coverage']['contracts_missing_identity_fields'] == 1
    assert archive['options']['coverage']['sampled_capture_complete'] is False
    assert '<contract_size>' not in archive['options']['responses'][1]['body_text']


def test_no_future_expirations_requires_successful_empty_response():
    wire = responses()[:1]
    wire[0]['body_text'] = '<expirations/>'
    wire[0]['body_sha256'] = text_sha256(wire[0]['body_text'])
    archive = build_capture('CAT', AT, bars(), wire, source_status='no_future_expirations')
    assert archive['options']['coverage']['sampled_capture_complete']
    unknown = build_capture('CAT', AT, bars(), [], source_status='no_future_expirations')
    assert not unknown['options']['coverage']['sampled_capture_complete']


def test_downloaded_benchmark_has_own_identity_time_and_coverage():
    item = {'symbol': 'SPY', 'request_start': '2026-01-01', 'request_end': '2026-10-16',
            'received_at': '2026-10-16T20:30:03+00:00', 'rows': bars(60)}
    archive = capture(additional_histories=[item])
    benchmark = archive['additional_downloaded_histories'][0]
    assert benchmark['rows'] == item['rows'] and benchmark['symbol'] == 'SPY'
    assert benchmark['received_at'] != archive['snapshot_at']
    assert not benchmark['coverage']['window_complete']
    assert archive['daily']['coverage']['window_complete']


def test_existing_original_export_is_partial_and_original_unchanged(tmp_path):
    original = ROOT/'logs/batch/2026-10-16/15-58-24/adaptive/CAT/input.json'
    if not original.exists(): pytest.skip('original local corpus unavailable')
    before = original.read_bytes()
    result = export_file(original, tmp_path)
    archived = json.loads(Path(result['path']).read_text(encoding='utf-8'))
    assert original.read_bytes() == before
    assert result['origin'] == 'derived_local_document'
    assert len(archived['daily']['rows']) == 20
    assert not result['history_252_complete'] and not result['sampled_options_complete']
    assert archived['options']['records'] and not archived['options']['coverage']['full_chain_reconstruction']


def test_sidecar_is_removed_when_off_and_invalid_enabled_capture_is_visible(tmp_path):
    clean = {'symbol': 'CAT', 'as_of': AT, 'latest_price': 101}
    payload = dict(clean, _evaluation_archive={'invalid': True})
    assert extract_for_model(payload) == clean
    assert '_evaluation_archive' in payload  # No mutation of caller-owned original.
    assert extract_for_model(payload, archive_root=tmp_path) == clean
    failures = list(tmp_path.glob('failure-*.json'))
    assert len(failures) == 1 and json.loads(failures[0].read_text())['status'] == 'failed'
    assert not (tmp_path/'CAT').exists()


def test_fetch_slim_extracts_and_archives_before_returning_context(tmp_path):
    from src.local_runner import run_one
    clean = {'symbol': 'CAT', 'as_of': AT, 'data_contract_revision':40, 'latest_price':101}
    payload = dict(clean, _evaluation_archive=capture())
    requested = []
    def fetch(request, **kwargs):
        requested.append(request.full_url)
        return BytesIO(json.dumps(payload).encode())
    with patch.object(run_one, 'urlopen', side_effect=fetch):
        assert run_one._fetch_slim('CAT') == clean
        assert run_one._fetch_slim('CAT', archive_root=tmp_path) == clean
    assert 'evaluation_archive' not in requested[0] and 'evaluation_archive=1' in requested[1]
    assert len(list((tmp_path/'CAT').glob('*.json'))) == 1


def test_missing_sidecar_exports_observed_subset_without_claiming_full_capture(tmp_path):
    document = {'symbol':'CAT', 'as_of':AT, 'price_history':{'sessions':bars(20)}, 'levels':{}}
    assert extract_for_model(document, archive_root=tmp_path) == document
    archive = json.loads(next((tmp_path/'CAT').glob('*.json')).read_text())
    assert not archive['daily']['coverage']['window_complete']
    assert archive['origin'] == 'derived_local_document'


def test_policy_off_by_default_and_rejects_old_revision_opt_in(tmp_path):
    from src.local_runner.adaptive_policy import load_policy
    policy = json.loads((ROOT/'config/codex_analysis.json').read_text(encoding='utf-8'))
    # Test omission/default independently of the live commissioned policy.
    policy.pop('technical_archive_enabled', None)
    policy['routing_revision'] = 39
    path = tmp_path/'config/codex_analysis.json'; path.parent.mkdir()
    path.write_text(json.dumps(policy))
    assert not load_policy(tmp_path).get('technical_archive_enabled', False)
    policy['technical_archive_enabled'] = True
    path.write_text(json.dumps(policy))
    with pytest.raises(ValueError, match='new_preparation40'): load_policy(tmp_path)
    policy['routing_revision'] = 40; path.write_text(json.dumps(policy))
    assert load_policy(tmp_path)['technical_archive_enabled'] is True


def raw_modules():
    # Standalone tests must not depend on another module's SDK stub/import order.
    import google
    genai = types.ModuleType('google.genai')
    genai.Client = lambda **kwargs: object()
    genai_types = types.ModuleType('google.genai.types')
    genai_types.GenerateContentConfig = object
    genai_types.ThinkingConfig = object
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'google.genai': genai, 'google.genai.types': genai_types}), patch.object(google, 'genai', genai, create=True):
            spec.loader.exec_module(module)
        return module
    return (load('archive_raw_test', ROOT/'gcp_functions/support_resistances_raw/main.py'),
            load('archive_slim_test', ROOT/'gcp_functions/support_resistances_slim/main.py'))


def invoke_raw(raw, requested, enabled):
    fixed = datetime.fromisoformat(AT)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return fixed if tz else fixed.replace(tzinfo=None)
        @classmethod
        def utcnow(cls): return fixed.replace(tzinfo=None)
    stamp = int(fixed.timestamp()*1000)
    wire = {row['endpoint']: row['body_text'] for row in responses()}
    def get(url, **kwargs):
        return Mock(text=wire[url.removeprefix(raw.TRADIER_BASE)])
    mirrors = []
    with ExitStack() as stack:
        stack.enter_context(patch.object(raw, 'datetime', Clock))
        stack.enter_context(patch.object(raw, 'TRADIER_TOKEN', 'offline-fixture'))
        stack.enter_context(patch.object(raw, '_tradier_quote', return_value={'last':101,'high':102,'low':99,'volume':1000,'bid':100.9,'ask':101.1,'bid_date':stamp,'ask_date':stamp,'trade_date':stamp}))
        stack.enter_context(patch.object(raw, '_tradier_history_daily', return_value=bars()))
        stack.enter_context(patch.object(raw, '_publish_symbol_json', side_effect=lambda symbol, value: mirrors.append(deepcopy(value)) or 'offline'))
        network = stack.enter_context(patch.object(raw.requests, 'get', side_effect=get))
        stack.enter_context(patch.dict(raw.os.environ, {'EVALUATION_ARCHIVE_ENABLED': 'true' if enabled else 'false'}))
        stack.enter_context(Flask('archive').test_request_context('/?symbol=CAT'+('&evaluation_archive=1' if requested else '')))
        response, status = raw.support_resistances_raw(request)
        assert status == 200, response.get_json()
        return response.get_json(), network.call_count, mirrors


def test_raw_opt_in_uses_same_downloads_and_never_changes_mirror_or_slim():
    raw, slim = raw_modules()
    baseline, count, mirror = invoke_raw(raw, False, False)
    disabled, disabled_count, _ = invoke_raw(raw, True, False)
    unrequested, unrequested_count, _ = invoke_raw(raw, False, True)
    enabled, enabled_count, enabled_mirror = invoke_raw(raw, True, True)
    archive = enabled.pop('_evaluation_archive')
    assert baseline == disabled == unrequested == enabled
    assert count == disabled_count == unrequested_count == enabled_count
    assert mirror == enabled_mirror and '_evaluation_archive' not in mirror[0]
    assert archive['daily']['coverage']['window_complete']
    assert archive['options']['coverage']['response_count'] == count
    assert slim._build_slim(dict(enabled, _evaluation_archive=archive)) == slim._build_slim(baseline)


def test_slim_carries_sidecar_only_when_requested():
    raw, slim = raw_modules()
    response, _, _ = invoke_raw(raw, True, True)
    for requested in (False, True):
        with patch.object(slim, '_fetch_raw', return_value=response) as fetch:
            with Flask('slim-archive').test_request_context('/?symbol=CAT'+('&evaluation_archive=1' if requested else '')):
                payload, status = slim.support_resistances_slim(request)
                assert status == 200
                assert ('_evaluation_archive' in payload.get_json()) is requested
                assert fetch.call_args.kwargs.get('evaluation_archive', False) is requested


def test_portable_archive_contract_copy_matches():
    assert (ROOT/'src/local_runner/technical_archive.py').read_bytes() == (ROOT/'gcp_functions/support_resistances_raw/technical_archive.py').read_bytes()


def test_provider_history_receipts_keep_symbol_window_and_rows_without_headers():
    from flask import g
    raw, _ = raw_modules()
    rows = bars(20)
    with patch.object(raw.requests, 'get', return_value=Mock(json=lambda:{'history':{'day':deepcopy(rows)}})) as network:
        with Flask('history-receipt').test_request_context('/'):
            g.evaluation_archive_enabled = True
            raw._tradier_history_daily('CAT', '2026-09-01', '2026-10-16')
            raw._tradier_history_daily('SPY', '2026-09-01', '2026-10-16')
            saved = deepcopy(g.downloaded_daily_histories)
    assert network.call_count == 2
    assert [item['symbol'] for item in saved] == ['CAT', 'SPY']
    assert all(item['rows'] == rows and item['received_at'] for item in saved)
    assert all(set(item) == {'symbol','request_start','request_end','received_at','rows'} for item in saved)


def test_archive_wrong_source_revision_rejected_before_model_return(tmp_path):
    payload = {'symbol':'CAT','as_of':AT,'data_contract_revision':39,'_evaluation_archive':capture()}
    clean = {key:value for key,value in payload.items() if key != '_evaluation_archive'}
    assert extract_for_model(payload, archive_root=tmp_path) == clean
    failure = json.loads(next(tmp_path.glob('failure-*.json')).read_text())
    assert failure['analysis_continues'] and 'identity_mismatch' in failure['error']


def test_new_prepare_freezes_only_clean_slim_and_never_refreshes_frozen_input(tmp_path):
    from src.local_runner import adaptive_stage as stage
    raw, slim = raw_modules()
    supplied, _, _ = invoke_raw(raw, True, True)
    clean = slim._build_slim(supplied)
    transported = dict(clean, _evaluation_archive=supplied['_evaluation_archive'])
    shutil.copytree(ROOT/'prompts', tmp_path/'prompts')
    work = tmp_path/'work'; work.mkdir()
    policy = json.loads((ROOT/'config/codex_analysis.json').read_text(encoding='utf-8'))
    policy.update(routing_revision=40, technical_archive_enabled=True)
    with ExitStack() as stack:
        stack.enter_context(patch.object(stage, 'load_policy', return_value=policy))
        stack.enter_context(patch.object(stage, 'load_reference_payload', return_value={}))
        stack.enter_context(patch.object(stage, 'data_ready'))
        stack.enter_context(patch.object(stage, 'load_research', return_value={}))
        stack.enter_context(patch.object(stage.one, '_load_system_prompt', return_value='frozen fixture'))
        for name in ('_load_analyst_quality', 'load_compact_analyst_summary', 'load_recent_analyst_actions', 'load_recent_news'):
            stack.enter_context(patch.object(stage.one, name, return_value={}))
        fetch = stack.enter_context(patch.object(stage.one, 'urlopen', side_effect=lambda *a, **kw:BytesIO(json.dumps(transported).encode())))
        model = stack.enter_context(patch.object(stage, 'call_codex', side_effect=AssertionError('model forbidden')))
        stage.prepare(tmp_path, work, 'CAT', False, 'tracking')
        frozen = (work/'input.json').read_bytes()
        assert json.loads(frozen)['slim'] == clean and b'_evaluation_archive' not in frozen
        assert len(list((tmp_path/'data/technical_archive/CAT').glob('*.json'))) == 1
        stage.prepare(tmp_path, work, 'CAT', False, 'tracking')
        assert (work/'input.json').read_bytes() == frozen
        assert fetch.call_count == 1 and model.call_count == 0


@pytest.mark.parametrize('body', [
    '<garbage/>', '<options><garbage/></options>',
    responses()[1]['body_text'].replace(EXP, '2026-10-30'),
    responses()[1]['body_text'].replace('<root_symbol>CAT</root_symbol>', '<root_symbol>OTHER</root_symbol>'),
    responses()[1]['body_text'].replace('<option>', '<option><underlying>OTHER</underlying>'),
    responses()[1]['body_text'].replace('CAT261023P00100000', 'CAT261023P00200000'),
    '<options><option><option_type>put</option_type></option></options>',
])
def test_contradictory_wire_is_preserved_but_never_claimed_complete(body):
    wire = responses(); wire[1]['body_text'] = body; wire[1]['body_sha256'] = text_sha256(body)
    archive = capture(wire=wire)
    assert archive['options']['responses'][1]['body_text'] == body
    assert not archive['options']['coverage']['sampled_capture_complete']
    assert archive['options']['coverage']['structure_or_identity_issues']
    assert archive['options']['coverage']['missing_expected_expirations'] == [EXP]


def test_recognized_empty_chain_preserves_zero_observed_contracts():
    wire = responses(); wire[1]['body_text'] = '<options/>'; wire[1]['body_sha256'] = text_sha256('<options/>')
    archive = capture(wire=wire)
    assert archive['options']['coverage']['sampled_capture_complete']
    assert archive['options']['coverage']['wire_contract_count'] == 0


def test_derived_coverage_cannot_claim_market_complete_after_rehash():
    archive = build_partial({'symbol':'CAT','as_of':AT,'price_history':{'sessions':bars(20)}}, 'a'*64)
    archive['options']['coverage']['market_complete'] = True
    with pytest.raises(ValueError, match='partial_scope'):
        validate_archive(reseal(archive))


def test_storage_failure_warns_and_persists_outside_model_without_retry(tmp_path, caplog):
    clean = {'symbol':'CAT','as_of':AT,'data_contract_revision':40}
    payload = dict(clean, _evaluation_archive=capture())
    destination = tmp_path/'work/technical_archive_failure.json'
    with patch('src.local_runner.archive_technical_observations.write_archive', side_effect=PermissionError('fixture')) as write:
        assert extract_for_model(payload, archive_root=tmp_path/'data', failure_path=destination) == clean
    assert write.call_count == 1
    assert json.loads(destination.read_text())['analysis_continues']
    assert 'technical_archive_failed' in caplog.text


def test_actual_slim_wrong_symbol_is_rejected_independently_of_archiving():
    with pytest.raises(ValueError, match='slim_endpoint_symbol_mismatch'):
        extract_for_model({'symbol':'OTHER','as_of':AT}, symbol='CAT')


def test_producer_archive_failure_does_not_fail_financial_response():
    raw, slim = raw_modules()
    with patch('gcp_functions.support_resistances_raw.technical_archive.build_capture', side_effect=ValueError('technical_archive_size_limit')):
        failed, _, mirrors = invoke_raw(raw, True, True)
    assert '_evaluation_archive_error' in failed and '_evaluation_archive' not in failed
    assert '_evaluation_archive_error' not in mirrors[0]
    assert '_evaluation_archive_error' not in slim._build_slim(failed)


def test_producer_archive_error_is_removed_and_saved_outside_model(tmp_path):
    clean = {'symbol':'CAT','as_of':AT}
    payload = dict(clean, _evaluation_archive_error={'status':'failed','error':'too_large'})
    assert extract_for_model(payload) == clean
    assert extract_for_model(payload, archive_root=tmp_path) == clean
    failure = json.loads(next(tmp_path.glob('failure-*.json')).read_text())
    assert 'producer_archive_unavailable' in failure['error'] and failure['analysis_continues']


def test_primary_request_window_and_same_symbol_additional_history_are_preserved():
    request_window = {'start':'2025-09-01', 'end':'2026-10-16'}
    extra = {'symbol':'CAT', 'request_start':'2026-06-01','request_end':'2026-10-16',
             'received_at':'2026-10-16T20:31:00+00:00','rows':bars(60)}
    archive = capture(history_request_window=request_window, additional_histories=[extra])
    assert archive['daily']['request_window'] == request_window
    assert archive['additional_downloaded_histories'][0]['symbol'] == 'CAT'
    assert len(archive['additional_downloaded_histories'][0]['rows']) == 60
    wrong = deepcopy(archive); wrong['daily']['representation'] = 'http_wire_exact'
    with pytest.raises(ValueError, match='representation'):
        validate_archive(reseal(wrong))
