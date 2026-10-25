"""Revision41 acquisition/admission/versioning integration, with no network/model.

Synthetic source observations exercise the real producer -> slim -> runner shape.
Frozen MP/NVDA/TSLA judgments are never rescored here: only the existing evidence
binding contract is exercised. Optional local WDC replay verifies real identity.
"""
import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
from unittest.mock import patch

import pytest

from gcp_functions.support_resistances_raw.support_origins import (
    build_pool, observe_support_origins, canonical_request, request_key,
)
from src.local_runner import adaptive_stage as stage
from src.local_runner.adaptive_context import model_context
from src.local_runner.adaptive_maintenance import maintenance_schema, maintenance_decision
from src.local_runner.adaptive_repair import repair_context
from src.local_runner.maintenance_change import validate_change, review_schema
from src.local_runner.semantic_report import reference_document, report_schema
from src.local_runner.semantic_sources import source_catalog
from src.local_runner.support_origins import support_origins, require_support_origins, encode_support_origins

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'logs/batch/2026-10-18/09-08-40/adaptive'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def load_functions(path, names):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    namespace = {'math': math, 'statistics': statistics, 'datetime': datetime}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def slim_observations(rows, price):
    names = ('_slim_support_origins', '_slim_levels', '_slim_level_evidence', '_num',
             '_signed_distance_pct', '_abs', '_sort_levels', '_cluster_min',
             '_cluster_max', '_list_min', '_list_max')
    ns = load_functions(ROOT / 'gcp_functions/support_resistances_slim/main.py', names)
    return ns['_slim_support_origins'](rows, price)


@pytest.fixture
def available_capture():
    days = [
        {'date': '2026-10-15', 'open': 95., 'high': 100., 'low': 90., 'close': 98., 'volume': 1000.},
        {'date': '2026-10-16', 'open': 106., 'high': 110., 'low': 105., 'close': 108., 'volume': 1200.},
    ]
    requested = [{'type': 'gap_up_lower', 'level': 100., 'date': '2026-10-16'}]
    pool = build_pool(days, [], [{'date': '2026-10-16', 'lower': 100., 'upper': 105., 'size': 5.}])
    as_of = '2026-10-18T09:30:00+00:00'
    observations = observe_support_origins(requested, days, pool, as_of)
    return requested, {'data_contract_revision': 41, 'as_of': as_of,
                       'levels': {'support_origins': slim_observations(observations, 108.)}}


def original(symbol):
    path = BATCH / symbol / 'input.json'
    if not path.is_file():
        pytest.skip('Optional frozen local corpus unavailable')
    return read(path)


@pytest.fixture(scope='module')
def wdc_capture():
    context = original('WDC')
    paths = list((ROOT / 'data/technical_archive/WDC').glob('*.json'))
    archives = [read(path) for path in paths]
    archives = [a for a in archives if a.get('snapshot_at') == context['slim']['as_of']]
    if not archives:
        pytest.skip('Optional same-capture WDC archive unavailable')
    assert len(archives) == 1
    days = archives[0]['daily']['rows']
    ns = load_functions(ROOT / 'gcp_functions/support_resistances_raw/main.py',
                        ('_find_swing_lows', '_cluster_swing_lows', '_find_bullish_gaps', '_to_float', '_median'))
    clusters = ns['_cluster_swing_lows'](ns['_find_swing_lows'](days[-126:], k=2),
                                        .2 * context['slim']['technicals']['atr10'])
    pool = build_pool(days, clusters, ns['_find_bullish_gaps'](days[-252:]))
    requests = support_origins(context['reference'])
    assert requests
    observations = observe_support_origins(requests, days, pool, context['slim']['as_of'])
    assert any(row['status'] == 'available' for row in observations)
    updated = deepcopy(context)
    updated['routing_revision'] = 41
    updated['slim']['data_contract_revision'] = 41
    updated['slim']['levels']['support_origins'] = slim_observations(observations, context['slim']['latest_price'])
    return context, updated, requests


def test_real_producer_slim_available_observation_is_admitted_without_scoring(available_capture):
    requested, slim = available_capture
    before = deepcopy((requested, slim))
    require_support_origins(slim, requested)
    row = slim['levels']['support_origins'][0]
    assert row['status'] == 'available'
    assert row['source_record']['origin_identity']['availability_date'] == '2026-10-16'
    assert 'strength_score' not in row['source_record']
    assert (requested, slim) == before


@pytest.mark.parametrize('status', ['not_observed', 'unavailable'])
def test_scoped_negative_observations_are_admitted_not_financial_failure(available_capture, status):
    requested, slim = available_capture
    row = slim['levels']['support_origins'][0]
    row.update(status=status, level=None, source_record=None, evidence=None,
               observation_reason='scoped_fixture_limitation')
    require_support_origins(slim, requested)


@pytest.mark.parametrize('mutation', [
    lambda s: s['levels'].pop('support_origins'),
    lambda s: s['levels']['support_origins'].clear(),
    lambda s: s['levels']['support_origins'].append(deepcopy(s['levels']['support_origins'][0])),
    lambda s: s.update(data_contract_revision=40),
    lambda s: s['levels']['support_origins'][0]['requested_identity'].update(level=101.),
    lambda s: s['levels']['support_origins'][0].update(observed_at='2026-10-17T09:30:00+00:00'),
    lambda s: s['levels']['support_origins'][0]['observation_scope'].update(available_is_not_viability=False),
    lambda s: s['levels']['support_origins'][0]['observation_scope'].update(history_last_session='2026-10-19'),
    lambda s: s['levels']['support_origins'][0]['source_record'].update(date='2026-10-15'),
    lambda s: s['levels']['support_origins'][0]['source_record'].update(level=101.),
    lambda s: s['levels']['support_origins'][0]['source_record'].pop('evidence'),
    lambda s: s['levels']['support_origins'][0].update(status='not_observed'),
])
def test_transport_identity_scope_and_negative_positive_mismatches_fail_before_model(available_capture, mutation):
    requested, slim = available_capture
    mutation(slim)
    with pytest.raises(RuntimeError, match='incomplete_source_no_model_call: support_origin_observation'):
        require_support_origins(slim, requested)


def test_empty_request_requires_explicit_41_coverage():
    slim = {'data_contract_revision': 41, 'as_of': '2026-10-18T09:30:00+00:00',
            'levels': {'support_origins': []}}
    require_support_origins(slim, [])
    assert encode_support_origins([]) == '[]'
    slim['levels'].pop('support_origins')
    with pytest.raises(RuntimeError, match='incomplete_source_no_model_call'):
        require_support_origins(slim, [])


def test_extraction_uses_only_authenticated_active_current_and_preserves_identity(wdc_capture):
    context, updated, requests = deepcopy(wdc_capture)
    original_bytes = (BATCH / 'WDC/input.json').read_bytes()
    assert all(canonical_request(r) == r for r in requests)
    assert len({request_key(r) for r in requests}) == len(requests)
    assert json.loads(encode_support_origins(requests)) == requests
    require_support_origins(updated['slim'], requests)
    bad = deepcopy(context['reference'])
    bad['semantic_report']['data']['plan']['entry']['range']['lower'] += .01
    with pytest.raises(ValueError):
        support_origins(bad)
    assert (BATCH / 'WDC/input.json').read_bytes() == original_bytes


def test_extraction_ignores_absent_slots_and_does_not_guess_from_prose():
    origin = {'type': 'gap_up_lower', 'level': 100., 'date': '2026-10-16'}
    active = {'range': {'lower': 99., 'upper': 101.}, 'resolved_facts': [{'value': origin}]}
    inactive = {'range': None, 'resolved_facts': [{'value': dict(origin, level=80.)}]}
    doc = {'plan': {'entry': active, 'ambitious_entry': inactive},
           'summary': {'narrative': 'gap_up_lower 70 from an old anchor'}}
    with patch('src.local_runner.semantic_report.reference_document', return_value=doc) as verify:
        result = support_origins({'analysis_markdown': 'authenticated by mock boundary'})
    verify.assert_called_once_with({'analysis_markdown': 'authenticated by mock boundary'}, verify_projection=True)
    assert result == [origin]


def test_data_ready_keeps_frozen40_while_requiring_41_directed_transport(wdc_capture):
    original_context, updated, requests = deepcopy(wdc_capture)
    policy = read(BATCH / 'WDC/policy.json')
    now = datetime.fromisoformat(updated['slim']['as_of']) + timedelta(minutes=1)
    stage.data_ready(original_context, policy, now)
    stage.data_ready(updated, dict(policy, routing_revision=41), now)
    updated['slim']['levels'].pop('support_origins')
    with pytest.raises(RuntimeError, match='incomplete_source_no_model_call: support_origin_observation'):
        stage.data_ready(updated, dict(policy, routing_revision=41), now)


@pytest.mark.parametrize('revision', [40, 41])
def test_preparation_freezes_correct_roles_and_resume_does_not_upgrade(tmp_path, wdc_capture, revision):
    original_context, updated, requests = deepcopy(wdc_capture)
    context = updated if revision == 41 else original_context
    policy = dict(read(BATCH / 'WDC/policy.json'), routing_revision=revision, technical_archive_enabled=False)
    now = datetime.fromisoformat(context['slim']['as_of']) + timedelta(minutes=1)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz else now.replace(tzinfo=None)
    work = tmp_path / str(revision) / 'WDC'
    work.mkdir(parents=True)
    with patch.object(stage, 'datetime', Clock), \
         patch.object(stage, 'load_policy', return_value=policy), \
         patch.object(stage, 'load_reference_payload', return_value=context['sol_reference']), \
         patch.object(stage, 'load_current_report', return_value=context['reference']), \
         patch.object(stage, 'load_research', return_value=None), \
         patch.object(stage.one, '_fetch_slim', return_value=context['slim']) as fetch, \
         patch.object(stage.one, '_load_analyst_quality', return_value=context['analyst_quality']), \
         patch.object(stage.one, 'load_compact_analyst_summary', return_value=context['analyst_summary']), \
         patch.object(stage.one, 'load_recent_analyst_actions', return_value=context['analyst_actions']), \
         patch.object(stage.one, 'load_recent_news', return_value=context['news']), \
         patch.object(stage.one, '_load_system_prompt', return_value='LEGACY_PLACEHOLDER'), \
         patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL')):
        stage.prepare(ROOT, work, 'WDC', context['owned'], context['tier'])
    kwargs = fetch.call_args.kwargs
    assert ('support_origins' in kwargs) is (revision == 41)
    if revision == 41:
        assert kwargs['support_origins'] == requests
    daily = (work / 'triage_instructions.md').read_text(encoding='utf-8')
    full = (work / 'instructions.md').read_text(encoding='utf-8')
    for text in (daily, full):
        assert f'REVISION{revision} — explicit publication' in text
        assert f'STRENGTH EVIDENCE{41 if revision == 41 else 31}' in text
        assert ('SUPPORT ORIGINS41' in text) is (revision == 41)
        assert ('FUENTES DEL CONTRATO14' in text) is (revision == 41)
    assert read(work / 'policy.json')['routing_revision'] == revision
    frozen = {p.name: p.read_bytes() for p in work.iterdir() if p.is_file()}
    with patch.object(stage, 'load_policy', side_effect=AssertionError('FROZEN POLICY')), \
         patch.object(stage.one, '_fetch_slim', side_effect=AssertionError('NO REFRESH')), \
         patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL')):
        stage.prepare(ROOT, work, 'WDC', context['owned'], context['tier'])
    assert {p.name: p.read_bytes() for p in work.iterdir() if p.is_file()} == frozen


def test_41_keeps_financial_output_schema_and_single_repair_contract():
    assert report_schema(41) == report_schema(40)
    assert maintenance_schema({'routing_revision': 41}) == maintenance_schema({'routing_revision': 40})
    assert review_schema(41) == review_schema(40)
    context = original('MP')
    context['guards'] = []
    payload = read(BATCH / 'MP/triage.response')
    for revision in (40, 41):
        context['routing_revision'] = revision
        repair = repair_context(model_context(context), payload, 'fixture_source_binding_error')
        assert repair['maintenance_repair']['attempt'] == 1
        assert ('Contrato41' in repair['maintenance_repair']['instruction']) is (revision == 41)
        assert maintenance_decision(payload, [], model_context(context)) == 'retain'


@pytest.mark.parametrize('symbol,slot,strike', [('MP', 'entry', 38.), ('NVDA', 'ambitious_entry', 210.),
                                               ('TSLA', 'ambitious_entry', 355.)])
def test_same_support_knowledge_basis_accepts_exact_current_sources_without_inventing_scores(symbol, slot, strike):
    context = original(symbol)
    original_objects = deepcopy(context)
    context['routing_revision'] = 41
    view = model_context(context)
    block = deepcopy(reference_document(view['reference'], verify_projection=True)['plan'][slot])
    old_finance = {k: deepcopy(block[k]) for k in ('range', 'strength', 'reason')}
    catalog = source_catalog(view)
    previous = next(key for key, row in catalog.items()
                    if row['pointer'] == '/reference/semantic_data/plan/' + slot)
    current = next(key for key, row in catalog.items()
                   if row['pointer'].startswith('/slim/levels/put_walls_top/') and row['value'].get('level') == strike)
    block['change_review'] = {'basis': 'material_improvement', 'previous_evidence': [previous],
                              'current_evidence': [current],
                              'explanation': 'Contrato offline: evidencia actual aplicable para revisar una limitación previa; no propone puntuación.'}
    validate_change(block, slot, view)
    assert {k: block[k] for k in old_finance} == old_finance
    assert block['change_review']['resolved_evidence']['current_evidence'][0]['evidence_role'] == 'current_market_observation'
    block['change_review']['current_evidence'] = [previous]
    with pytest.raises(ValueError, match='missing_current_market_evidence'):
        validate_change(block, slot, view)
    context['routing_revision'] = original_objects['routing_revision']
    assert context == original_objects
