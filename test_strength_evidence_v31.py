"""No network, model calls, publication or original-artifact edits."""
import ast
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'tests'))
from test_support_resistances_slim_evidence import raw, slim
from src.local_runner.adaptive_context import model_context, serialize_model_input
from src.local_runner.evidence_semantics import technical_observations
from src.local_runner.semantic_report import report_schema, update_schema
from src.local_runner.adaptive_repair import repair_context

ROOT = Path(__file__).resolve().parent
ORIGINALS = ROOT / 'logs/batch/2026-10-13/11-06-58/adaptive'
BASELINE = ROOT / 'logs/deploy_history28'

def without_added(value):
    if isinstance(value, dict):
        return {k: without_added(v) for k, v in value.items()
                if k not in ('option_details', 'bid_date', 'ask_date')}
    if isinstance(value, list):
        return [without_added(v) for v in value]
    return value

def old_function(name):
    tree = ast.parse((BASELINE / 'raw-source/main.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = dict(raw.__dict__)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<baseline>', 'exec'), namespace)
    return namespace[name]

def chains():
    def row(side, strike, oi, gamma, bid, ask):
        return dict(option_type=side, strike=strike, oi=oi, gamma=gamma,
                    bid=bid, ask=ask, bid_date='1791898200000', ask_date=None)
    return {
        '2026-10-16': [row(s, 100, 100, .03, 1, 1.2) for s in ('call','put')]
                     + [row('put', 99, 10, .01, 0, .5)],
        '2026-10-23': [row(s, 100, 70, .02, None, None) for s in ('call','put')]
                     + [row('put', 99, 5, 0, 1, .5)],
        '2026-10-30': [row(s, 110, 12, .01, .2, .3) for s in ('call','put')],
    }

@pytest.mark.parametrize('name,extra', [
    ('_compute_callwall_gamma', dict(today_high=102, tol_mult=.2)),
    ('_compute_putwall_gamma', dict(today_low=98, tol_mult=.2)),
    ('_compute_top_callwalls_gamma', dict(top_n=5)),
    ('_compute_top_putwalls_gamma', dict(top_n=5)),
])
def test_aggregate_ranking_expiry_clusters_identical_to_live28(name, extra):
    capture = chains()
    with patch.object(raw, '_tradier_option_expirations', return_value=list(capture)), \
         patch.object(raw, '_tradier_options_chain', side_effect=lambda s, e: capture[e]) as get:
        old = old_function(name)('TEST', last_price=101, atr10=2, top_expirations=3, cluster_atr=1, **extra)
        old_count = get.call_count
        get.reset_mock()
        new = getattr(raw, name)('TEST', last_price=101, atr10=2, top_expirations=3, cluster_atr=1, **extra)
        assert get.call_count == old_count == 3
    assert without_added(new) == old
    for wall in new if isinstance(new, list) else [new]:
        detail = wall['option_details']
        assert detail['sampled_expirations'] == list(capture)
        observed = detail['by_expiration']
        assert sum(r['aggregate_oi'] or 0 for r in observed) == wall['oi']
        assert sum(r['gamma_usd_millions'] or 0 for r in observed) == pytest.approx(wall['gamma_usd_millions'], abs=.00051)
        if wall['level'] == 100:
            assert observed[2]['status'] == 'not_observed'
            assert observed[2]['aggregate_oi'] is None
            assert observed[1]['aggregate_oi'] == 70
            assert observed[1]['observed_contracts'][0]['bid'] is None

def test_zero_gamma_and_bad_quotes_are_visible_not_liquidity_verdicts():
    detail = raw._wall_option_details(99, 'put', chains(), 101)
    zero = detail['by_expiration'][1]
    assert zero['aggregate_oi'] == 0
    assert zero['observed_contracts'][0]['oi'] == 5
    assert zero['observed_contracts'][0]['included_in_wall_aggregate'] is False
    assert zero['observed_contracts'][0]['bid'] > zero['observed_contracts'][0]['ask']
    assert 'liquid' not in json.dumps(detail)
    assert detail['by_expiration'][0]['observed_contracts'][0]['bid'] == 0

def test_slim_carries_exact_detail_in_both_routes():
    detail = raw._wall_option_details(100, 'put', chains(), 101)
    wall = dict(level=100, expiration='2026-10-16', option_details=detail)
    source = dict(symbol='TEST', latest_price=101, put_walls_top=[wall],
                  supports=[dict(level=100, type='put_wall_gamma', meta=wall)])
    result = slim._build_slim(source)
    # Existing slim cleaning omits nulls; missing stays unknown, never zero.
    assert result['levels']['put_walls_top'][0]['option_details'] == slim._clean(detail)
    assert result['levels']['supports'][0]['option_details'] == slim._clean(detail)
    assert result['levels']['put_walls_top'][0]['option_details']['by_expiration'][2]['status'] == 'not_observed'
    assert 'aggregate_oi' not in result['levels']['put_walls_top'][0]['option_details']['by_expiration'][2]

def test_no_original_capture_financial_field_changed_by_slim_addition():
    source = json.loads((BASELINE/'raw-smoke.json').read_text(encoding='utf-8'))
    tree = ast.parse((BASELINE/'slim-source/main.py').read_text(encoding='utf-8'))
    namespace = dict(slim.__dict__)
    exec(compile(tree, '<slim-baseline>', 'exec'), namespace)
    assert without_added(slim._build_slim(source)) == namespace['_build_slim'](source)

def test_old_context_contract_exact_and_new_detail_reaches_source_catalog():
    for ticker in ('CAT', 'IBKR', 'ASML', 'HIMS', 'TSLA'):
        context = json.loads((ORIGINALS/ticker/'input.json').read_text(encoding='utf-8'))
        original = deepcopy(context)
        old = model_context(context)
        assert 'not supplied by these rows' in old['comparison']['technical_evidence_semantics']['option_wall_contract']
        context['routing_revision'] = 31
        detail = raw._wall_option_details(100, 'put', chains(), 101)
        context['slim']['levels']['put_walls_top'][0]['option_details'] = detail
        new = model_context(context)
        contract = new['comparison']['technical_evidence_semantics']['option_wall_contract']
        assert 'when supplied' in contract and 'UNKNOWN' in contract
        assert 'not supplied by these rows' not in contract
        assert any(r['value'].get('option_details') == detail for r in new['source_catalog'].values()
                   if isinstance(r.get('value'), dict))
        # Already frozen <=30 contexts keep their serialization; no live mutation.
        assert serialize_model_input(model_context(original)) == serialize_model_input(old)
    assert report_schema(31) == report_schema(30)
    assert update_schema(31) == update_schema(30)

def test_repair_same_authority_no_score_target():
    context = json.loads((ORIGINALS/'CAT/input.json').read_text(encoding='utf-8'))
    context['routing_revision'] = 30
    old = repair_context(context, {}, 'test')['maintenance_repair']['instruction']
    context['routing_revision'] = 31
    new = repair_context(context, {}, 'test')['maintenance_repair']['instruction']
    assert new.startswith(old)
    assert 'No dupliques penalizaciones' in new
    assert 'sin inflar puntuaciones' in new

def test_complete_mocked_capture_preserves_prices_dates_paths_and_request_count():
    import types
    from test_capture_routing_v23 import Capture23
    previous = types.ModuleType('raw_history28')
    exec(compile((BASELINE/'raw-source/main.py').read_text(encoding='utf-8'),
                 '<raw-baseline>', 'exec'), previous.__dict__)
    case = Capture23()
    old, old_status, old_calls, old_publish = case.invoke_raw(previous)
    new, new_status, new_calls, new_publish = case.invoke_raw(raw)
    assert (old_status, new_status, old_calls, new_calls, old_publish, new_publish) == (200,200,2,2,1,1)
    old.pop('as_of'); new.pop('as_of')  # Only wall-clock capture creation differs.
    assert without_added(new) == old
    assert new['put_walls_top'][0]['option_details']['by_expiration'][0]['observed_contracts']

def test_all_original_report_inputs_and_outputs_remain_untouched():
    import hashlib
    from src.local_runner.semantic_report import full_document
    from src.local_runner.semantic_binding import bind_response
    for folder in ORIGINALS.iterdir():
        if not (folder/'report.response').exists():
            continue
        context = json.loads((folder/'input.json').read_text(encoding='utf-8'))
        response = json.loads((folder/'report.response').read_text(encoding='utf-8'))
        old_view = model_context(context)
        old_serialized = serialize_model_input(old_view)
        original_bytes = (folder/'report.response').read_bytes()
        context['routing_revision'] = 31
        view = model_context(context)
        receipt = dict(text=json.dumps(response), exit_code=0,
                       input_sha256=hashlib.sha256(serialize_model_input(view).encode()).hexdigest())
        doc = full_document(deepcopy(response), view, binding=bind_response(context,receipt,'report'))
        assert doc['plan']['entry']['range'] == response['plan']['entry']['range']
        for key in ('entry','ambitious_entry','resistance'):
            assert doc['plan'][key]['strength'] == response['plan'][key]['strength']
        assert (folder/'report.response').read_bytes() == original_bytes
        assert serialize_model_input(model_context(json.loads((folder/'input.json').read_text(encoding='utf-8')))) == old_serialized

def test_preparation_freezes_shared_evidence_in_both_roles(tmp_path):
    from contextlib import ExitStack
    from datetime import datetime
    from src.local_runner import adaptive_stage as stage
    from src.local_runner.adaptive_policy import load_policy
    context = json.loads((ORIGINALS/'CAT/input.json').read_text(encoding='utf-8'))
    policy = load_policy(ROOT)
    policy['routing_revision'] = 31
    work = tmp_path/'CAT'; work.mkdir()
    with ExitStack() as stack:
        clock = stack.enter_context(patch.object(stage, 'datetime', wraps=datetime))
        clock.now.return_value = datetime.fromisoformat(context['prepared_at'])
        for name, value in [('load_policy',policy), ('load_reference_payload',context['sol_reference']),
                            ('load_current_report',context['reference']), ('load_research',None)]:
            stack.enter_context(patch.object(stage,name,return_value=value))
        for name, value in [('_fetch_slim',context['slim']), ('_load_analyst_quality',{}),
                            ('load_compact_analyst_summary',{}), ('load_recent_analyst_actions',context['analyst_actions']),
                            ('load_recent_news',context['news']), ('_load_system_prompt','legacy')]:
            stack.enter_context(patch.object(stage.one,name,return_value=value))
        stack.enter_context(patch.object(stage,'call_codex',side_effect=AssertionError('NO MODEL')))
        stage.prepare(ROOT,work,'CAT',context['owned'],context['tier'])
        for name in ('instructions.md','triage_instructions.md'):
            text = (work/name).read_text(encoding='utf-8')
            assert 'STRENGTH EVIDENCE31' in text and 'AUTHORING BUDGETS' in text
            assert 'no score target' in text and 'same rubric' in text
        frozen = {p.name:p.read_bytes() for p in work.iterdir()}
        stage.prepare(ROOT,work,'CAT',context['owned'],context['tier'])
        assert frozen == {p.name:p.read_bytes() for p in work.iterdir()}
