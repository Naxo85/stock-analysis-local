"""Exact directed option observations. Offline only: no models or publication."""
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys
from unittest.mock import Mock, patch
import pytest
import requests
from flask import Flask

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests'))
from test_support_resistances_slim_evidence import raw,slim
from src.local_runner.technical_preparation import option_origins,require_option_origins,encode_option_origins
from src.local_runner.adaptive_context import model_context,serialize_model_input
from src.local_runner.semantic_sources import source_catalog
from src.local_runner.semantic_report import reference_document,_origin_present,_resolve_facts

INCIDENT=ROOT/'logs/batch/2026-10-16/15-58-24/adaptive/APP'
EXP=['2026-10-16','2026-10-23','2026-10-30']

def original():
    return json.loads((INCIDENT/'input.json').read_text(encoding='utf-8'))

def contract(side,strike,oi='25',gamma='0.01'):
    return ('<option><option_type>'+side+'</option_type><strike>'+str(strike)+'</strike>'
            +('' if oi is None else '<open_interest>'+oi+'</open_interest>')
            +('' if gamma is None else '<greeks><gamma>'+gamma+'</gamma></greeks>')
            +'<bid>0</bid><ask>1.2</ask><bid_date>1792167176000</bid_date></option>')

def wire(url,**kwargs):
    if url.endswith('/expirations'):
        return Mock(text='<expirations>'+''.join('<date>'+e+'</date>' for e in EXP)+'</expirations>')
    assert url.endswith('/chains') and kwargs['params']['greeks']=='true'
    return Mock(text='<options>'+''.join(contract('put',s,'500','0.1') for s in [265,270,275,280,285])
                +contract('put',250)+contract('call',250,'11','0')+'</options>')

def observe(requested=(('put',250.0),),getter=wire):
    with patch.object(raw.requests,'get',side_effect=getter),Flask(__name__).test_request_context('/'):
        return raw._observe_option_origins(requested,'APP',272.33)

def slim_with(rows):
    return slim._build_slim({'latest_price':272.33,'as_of':'2026-10-16T16:14:23+00:00',
                            'option_origins':rows})

def test_original_app_requires_exact_strike_even_outside_top_and_not_anchor_or_prose():
    ctx=original();before=deepcopy(ctx)
    assert ('put',250.0) in option_origins(ctx['reference'])
    assert 250 not in [r['level'] for r in ctx['slim']['levels']['put_walls_top']]
    ref=deepcopy(ctx['reference']);doc=reference_document(ref,verify_projection=True)
    assert doc['plan']['entry']['range']=={'lower':249.5,'upper':250.5}
    assert option_origins({})==[]
    # A typed active CURRENT source selects its identity; archived retired fields
    # and prose/range numbers must not become option contracts.
    with patch('src.local_runner.semantic_report.reference_document',return_value={
        'plan':{'entry':{'range':None,'resolved_facts':doc['plan']['entry']['resolved_facts']},
                'ambitious_entry':{'range':{'lower':2,'upper':3},'reason':'put 999','resolved_facts':[]},
                'resistance':doc['plan']['entry']}}):
        assert option_origins(ref)==[]
    assert ctx==before

@pytest.mark.parametrize('text',['put:0','put:-1','PUT:250','put:nan','call:inf','put:1e3','oops:250','put:250;exec','put:'])
def test_query_rejects_invalid_identity(text):
    with pytest.raises(ValueError):raw._parse_option_origins(text)

def test_query_roundtrip_precision_and_duplicate_identity():
    q=[('put',0.000000123456789),('call',250.125)]
    assert raw._parse_option_origins(encode_option_origins(q))==sorted(q)
    assert raw._parse_option_origins('put:250,put:250.0')==[('put',250.0)]

def test_top_ranking_identical_and_directed_strike_has_no_extra_wire_downloads():
    with patch.object(raw.requests,'get',side_effect=wire) as get,Flask(__name__).test_request_context('/'):
        top=raw._compute_top_putwalls_gamma('APP',272.33,10,3,1,top_n=5)
        assert all(r['level']!=250 for r in top)
        count=get.call_count;assert count==4
        rows=raw._observe_option_origins([('put',250.0),('call',250.0)],'APP',272.33)
        assert get.call_count==count
        assert top==raw._compute_top_putwalls_gamma('APP',272.33,10,3,1,top_n=5)
        assert get.call_count==count
    assert len(rows)==2
    assert all(r['status']=='available' for r in rows)
    assert rows[0]['option_details']['option_type']=='put'
    assert [r['aggregate_oi'] for r in rows[0]['option_details']['by_expiration']]==[25]*3
    assert rows[1]['option_details']['by_expiration'][0]['gamma_usd_millions']==0
    require_option_origins(slim_with(rows),[('put',250.0),('call',250.0)])

@pytest.mark.parametrize('oi,gamma,expected', [('0','0.01',0),(None,'0.01',None),('10',None,10),('-1','0.01',None)])
def test_zero_and_incomplete_contracts_are_preserved_not_missing(oi,gamma,expected):
    def get(url,**kw):
        return wire(url,**kw) if url.endswith('/expirations') else Mock(text='<options>'+contract('put',250,oi,gamma)+'</options>')
    row=observe(getter=get)[0];assert row['status']=='available'
    exp=row['option_details']['by_expiration'][0]
    assert exp['aggregate_oi']==expected
    assert exp['observed_contracts'][0]['oi']==expected
    if gamma is None or expected is None:assert exp['gamma_usd_millions'] is None
    assert exp['observed_contracts'][0]['bid']==0
    assert exp['observed_contracts'][0]['ask_date'] is None
    require_option_origins(slim_with([row]),[('put',250.0)])

def test_absent_contract_empty_expiries_and_bad_identity_are_different_observations():
    absent=observe([('put',999.0)])[0]
    assert absent['status']=='not_observed'
    assert absent['option_details']['by_expiration'][0]['aggregate_oi'] is None
    empty=observe(getter=lambda url,**kw:Mock(text='<expirations/>'))[0]
    assert empty['status']=='not_observed' and empty['reason']=='no_future_expirations'
    def get(url,**kw):
        return wire(url,**kw) if url.endswith('/expirations') else Mock(text='<options><option><option_type>put</option_type></option></options>')
    unknown=observe(getter=get)[0]
    assert unknown['status']=='unavailable'
    for row in [absent,empty,unknown]:require_option_origins(slim_with([row]),[(row['option_details']['option_type'],row['level'])])

def test_download_failure_is_not_successful_absence():
    def get(url,**kw):
        if url.endswith('/chains'):raise requests.Timeout('offline')
        return wire(url,**kw)
    with pytest.raises(requests.Timeout):observe(getter=get)

def test_slim_forwards_exact_query_without_changing_old_requests():
    from flask import request
    with patch.object(slim,'_fetch_raw',return_value={}) as fetch,Flask(__name__).test_request_context('/?symbol=APP&option_origins=put:250'):
        result,status=slim.support_resistances_slim(request)
        assert status==200
        fetch.assert_called_once_with('APP',avwap_anchors='',option_origins='put:250')

def test_missing_observation_is_rejected_before_admission_not_frozen_app_recovery():
    ctx=original();requested=option_origins(ctx['reference'])
    with pytest.raises(RuntimeError,match='incomplete_source_no_model_call: option_origin'):
        require_option_origins(ctx['slim'],requested)
    rows=observe(requested);out=slim_with(rows)
    require_option_origins(out,requested)
    bad=deepcopy(out);bad['levels']['option_origins'][0]['level']=999
    with pytest.raises(RuntimeError):require_option_origins(bad,requested)
    bad=deepcopy(out);bad['levels']['option_origins'][0]['status']='not_observed'
    with pytest.raises(RuntimeError):require_option_origins(bad,requested)

def test_current_catalog_observations_and_positive_origin_guard_are_separate():
    ctx=original();frozen=serialize_model_input(model_context(ctx));ctx['routing_revision']=39
    ctx['slim']['levels']['option_origins']=slim_with(observe())['levels']['option_origins']
    view=model_context(ctx);catalog=source_catalog(view)
    pointer=next(r['pointer'] for r in catalog.values() if r['pointer'].startswith('/slim/levels/option_origins/'))
    assert _origin_present({'lower':249.5,'upper':250.5},view,'entry')
    level={'facts':[pointer+'/option_details/by_expiration/0/aggregate_oi']}
    facts=_resolve_facts(level,view)
    assert facts[0]['value']==25 and facts[0]['options_record']['level']==250
    bad=deepcopy(view);bad['slim']['levels']['option_origins'][0]=slim_with(observe([('put',999.0)]))['levels']['option_origins'][0]
    assert not _origin_present({'lower':998.9,'upper':999.1},bad,'entry')
    assert serialize_model_input(model_context(original()))==frozen

def test_full_handler_same_requests_and_no_changed_top_for_directed_capture():
    from test_capture_routing_v23 import Capture23
    case=Capture23();baseline,status,calls,pub=case.invoke_raw(raw)
    with patch.object(raw,'_parse_option_origins',return_value=[('put',250.0)]):
        directed,status2,calls2,pub2=case.invoke_raw(raw)
    assert (status,status2,calls,calls2,pub,pub2)==(200,200,2,2,1,1)
    row=directed.pop('option_origins')[0]
    assert row['status']=='not_observed'
    baseline.pop('as_of');directed.pop('as_of')
    assert directed==baseline

def test_raw_handler_observation_error_fails_before_mirroring():
    from test_capture_routing_v23 import Capture23
    with patch.object(raw,'_parse_option_origins',return_value=[('put',250.0)]),patch.object(raw,'_observe_option_origins',side_effect=requests.Timeout()):
        result,status,_,pub=Capture23().invoke_raw(raw)
    assert (status,pub)==(502,0)
    assert result['component']=='option_origins'

def test_prepare39_acquires_before_freezing_and_preserves38_receipts(tmp_path):
    from src.local_runner import adaptive_stage as stage
    ctx=original();policy=json.loads((ROOT/'config/codex_analysis.json').read_text());policy['routing_revision']=39
    work=tmp_path/'APP';work.mkdir()
    supplied=deepcopy(ctx['slim']);supplied['levels']['option_origins']=slim_with(observe(option_origins(ctx['reference'])))['levels']['option_origins']
    with ExitStack() as stack:
        clock=stack.enter_context(patch.object(stage,'datetime',wraps=datetime));clock.now.return_value=datetime.fromisoformat(ctx['prepared_at'])
        for name,value in [('load_policy',policy),('load_reference_payload',ctx['sol_reference']),('load_current_report',ctx['reference']),('load_research',None)]:stack.enter_context(patch.object(stage,name,return_value=value))
        fetch=stack.enter_context(patch.object(stage.one,'_fetch_slim',return_value=supplied))
        for name,value in [('_load_analyst_quality',{}),('load_compact_analyst_summary',{}),('load_recent_analyst_actions',ctx['analyst_actions']),('load_recent_news',ctx['news']),('_load_system_prompt','legacy')]:stack.enter_context(patch.object(stage.one,name,return_value=value))
        stack.enter_context(patch.object(stage,'call_codex',side_effect=AssertionError('NO MODEL')))
        stage.prepare(ROOT,work,'APP',ctx['owned'],ctx['tier'])
        assert ('put',250.0) in fetch.call_args.kwargs['option_origins']
        for name in ['instructions.md','triage_instructions.md']:assert 'OPTION ORIGINS39' in (work/name).read_text(encoding='utf-8')
        before={p.name:p.read_bytes() for p in work.iterdir()}
        policy['routing_revision']=38;stage.prepare(ROOT,work,'APP',ctx['owned'],ctx['tier'])
        assert before=={p.name:p.read_bytes() for p in work.iterdir()}
    # Actual blocked38 input/response are immutable, not silently promoted to39.
    original_bytes=(INCIDENT/'input.json').read_bytes()
    assert json.loads(original_bytes)['routing_revision']==38


def test_original_blocked38_admission_is_not_refreshed_or_rewritten(tmp_path):
    from src.local_runner import adaptive_stage as stage
    work=tmp_path/'APP';work.mkdir()
    for name in ['input.json','policy.json','failure.json','triage.response','triage.receipt.json','instructions.md','triage_instructions.md']:
        (work/name).write_bytes((INCIDENT/name).read_bytes())
    frozen={p.name:p.read_bytes() for p in work.iterdir()}
    with patch.object(stage,'load_policy',side_effect=AssertionError('frozen contract must return first')),patch.object(stage.one,'_fetch_slim',side_effect=AssertionError('NO NEW CAPTURE')):
        stage.prepare(ROOT,work,'APP',False,'normal')
    assert frozen=={p.name:p.read_bytes() for p in work.iterdir()}


@pytest.mark.parametrize('kind',['zero','expired','call','not_observed'])
def test_negative_or_ineligible_observation_does_not_become_positive_origin(kind):
    ctx=original();ctx['routing_revision']=39
    row=slim_with(observe())['levels']['option_origins'][0]
    if kind=='zero':
        for item in row['option_details']['by_expiration']:item.update(aggregate_oi=0,gamma_usd_millions=0)
    elif kind=='expired':
        for item in row['option_details']['by_expiration']:item['expiration']='2026-10-01'
    elif kind=='call':row['option_details']['option_type']='call'
    else:row['status']='not_observed'
    ctx['slim']['levels']['option_origins']=[row]
    assert not _origin_present({'lower':249.5,'upper':250.5},ctx,'entry')
