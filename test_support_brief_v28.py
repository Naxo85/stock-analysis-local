"""Offline acquisition/editorial regressions, not a simulated financial verdict."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
import pytest
import importlib.util
_spec = importlib.util.spec_from_file_location('evidence_fixture_v28', Path(__file__).parent/'tests/test_support_resistances_slim_evidence.py')
_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixture)
raw, slim = _fixture.raw, _fixture.slim
from src.local_runner.technical_preparation import require_price_history
from src.local_runner import adaptive_stage as stage
from src.local_runner.adaptive_context import model_context
from src.local_runner.adaptive_repair import repair_context
from src.local_runner.semantic_sources import source_catalog

ROOT = Path(__file__).resolve().parent
BATCH = ROOT/'logs/batch/2026-10-13/08-03-29/adaptive'

def bars():
    return [dict(date=f'2026-09-{d:02}',open=100.,high=103.,low=98.,close=99.,volume=1000.) for d in range(1,26)]

def capture():
    return {'as_of':'2026-10-13T08:00:00+00:00','price_history':raw._recent_price_history(bars())}

def test_sessions_are_observations_not_automatic_decisions():
    rows=bars(); before=deepcopy(rows)
    history=raw._recent_price_history(rows)
    assert len(history['sessions'])==20 and rows==before
    assert history['sessions']==rows[-20:]
    assert not any(k in history for k in ('broken','viable','score','decision'))
    require_price_history(capture())
    result=slim._build_slim({'symbol':'TEST','price_history':history})
    assert result['price_history']==history

def test_live_day_excluded_and_old_raw_not_guessed():
    rows=bars()+[dict(bars()[-1],date=datetime.now(timezone.utc).date().isoformat(),close=999)]
    assert raw._recent_price_history(rows)==raw._recent_price_history(bars())
    assert slim._build_slim({'symbol':'TEST'})['price_history']['status']=='unavailable'

@pytest.mark.parametrize('field,value',[('low',101),('high',97),('open',None),('close',float('nan')),('volume',-1)])
def test_bad_history_never_becomes_support_loss(field,value):
    rows=bars();rows[-1][field]=value
    assert raw._recent_price_history(rows)['status']=='unavailable'
    bad=capture();bad['price_history']['sessions'][-1][field]=value
    with pytest.raises(RuntimeError,match='recent_price_history'):require_price_history(bad)

@pytest.mark.parametrize('mutation',['missing','duplicate','reversed','future','metadata'])
def test_acquisition_contract(mutation):
    data=capture();history=data['price_history'];rows=history['sessions']
    if mutation=='missing':data.pop('price_history')
    if mutation=='duplicate':rows.append(rows[-1])
    if mutation=='reversed':rows.reverse()
    if mutation=='future':rows[-1]['date']='2026-10-13'
    if mutation=='metadata':history['last_session']='2026-09-01'
    with pytest.raises(RuntimeError,match='recent_price_history'):require_price_history(data)

@pytest.mark.parametrize('ticker',['LRCX','RKLB','AMD','CLS','SOFI','GEV','CRDO'])
def test_actual_inputs_old_handles_and_financial_authority_unchanged(ticker):
    data=json.loads((BATCH/ticker/'input.json').read_text(encoding='utf-8'));before=deepcopy(data)
    old=source_catalog(data)
    data['slim']['price_history']=capture()['price_history']
    assert source_catalog(data)==old
    data['routing_revision']=28
    view=model_context(data)
    assert view['comparison']['contract']=='adaptive-semantic-context-v28'
    assert any(v['pointer']=='/slim/price_history' for v in source_catalog(data).values())
    assert data['reference']==before['reference'] and data['sol_reference']==before['sol_reference']
    assert data['slim']['latest_price']==before['slim']['latest_price']

@pytest.mark.parametrize('revision',[27,28])
def test_preparation_both_roles_repair_and_frozen_contract(tmp_path,revision):
    data=json.loads((BATCH/'CRDO/input.json').read_text(encoding='utf-8'))
    policy=json.loads((ROOT/'config/codex_analysis.json').read_text());policy['routing_revision']=revision
    data['slim']['price_history']=capture()['price_history']
    original={p.name:p.read_bytes() for p in (BATCH/'CRDO').glob('*instructions.md')}
    work=tmp_path/'CRDO';work.mkdir()
    with ExitStack() as stack:
        clock=stack.enter_context(patch.object(stage,'datetime',wraps=datetime))
        clock.now.return_value=datetime.fromisoformat(data['prepared_at'])
        for name,result in [('load_policy',policy),('load_reference_payload',data['sol_reference']),('load_current_report',data['reference']),('load_research',None)]:
            stack.enter_context(patch.object(stage,name,return_value=result))
        for name,result in [('_fetch_slim',data['slim']),('_load_analyst_quality',{}),('load_compact_analyst_summary',{}),('load_recent_analyst_actions',data['analyst_actions']),('load_recent_news',data['news']),('_load_system_prompt','legacy')]:
            stack.enter_context(patch.object(stage.one,name,return_value=result))
        stack.enter_context(patch.object(stage,'call_codex',side_effect=AssertionError('NO MODEL')))
        stage.prepare(ROOT,work,'CRDO',data['owned'],data['tier'])
        for name in ('instructions.md','triage_instructions.md'):
            text=(work/name).read_text(encoding='utf-8')
            assert ('REVISION28' in text)==(revision==28)
            if revision==27:assert (work/name).read_bytes()==original[name]
            else:
                assert 'one short paragraph' in text and 'NOT a grace period' in text
                assert 'NOT a word-count validator' in text
        frozen={p.name:p.read_bytes() for p in work.iterdir()}
        stage.prepare(ROOT,work,'CRDO',data['owned'],data['tier'])
        assert frozen=={p.name:p.read_bytes() for p in work.iterdir()}
    assert original=={p.name:p.read_bytes() for p in (BATCH/'CRDO').glob('*instructions.md')}
    instruction=repair_context({'routing_revision':revision},{},'test')['maintenance_repair']['instruction']
    assert ('Revision28' in instruction)==(revision==28)

def test_missing_history_blocks_new_preparation_only():
    data=json.loads((BATCH/'CRDO/input.json').read_text(encoding='utf-8'))
    policy=json.loads((ROOT/'config/codex_analysis.json').read_text())
    now=datetime.fromisoformat(data['prepared_at'])
    stage.data_ready(data,policy,now)
    data['routing_revision']=28
    with pytest.raises(RuntimeError,match='recent_price_history'):stage.data_ready(data,policy,now)

def test_all_original_reports_keep_content_prices_dates_and_render():
    from src.local_runner.semantic_report import reference_document, render_document, publication_fields
    from src.local_runner.financial_projection import financial_document
    paths=list(BATCH.glob('*/publish/output/*/latest.json'))
    assert len(paths)==46
    for path in paths:
        payload=json.loads(path.read_text(encoding='utf-8'));before=deepcopy(payload)
        doc=reference_document(payload,verify_projection=True);saved=deepcopy(doc)
        markdown=render_document(doc)
        published=publication_fields(doc,markdown,{},datetime.fromisoformat(payload['generated_at']))
        assert financial_document(published['semantic_report']['data'])==financial_document(doc)
        assert doc==saved and payload==before
        for key in ('entry','ambitious_entry','resistance','management_stop','structural_stop','target'):
            assert published['plan'][key]==payload['plan'][key]
        for key in ('thesis_score','thesis_reason','setup_score','setup_reason','narrative'):
            assert published['decision'][key]==payload['decision'][key]

def test_new_history_can_be_cited_in_a_change_justification():
    from src.local_runner.maintenance_change import validate_change
    data=json.loads((BATCH/'LRCX/input.json').read_text(encoding='utf-8'))
    data['routing_revision']=28;data['slim']['price_history']=capture()['price_history']
    catalog=source_catalog(data)
    current=next(k for k,v in catalog.items() if v['pointer']=='/slim/price_history')
    prior=next(k for k,v in catalog.items() if v['pointer']=='/reference/semantic_data/plan/entry')
    review={'basis':'backing_changed','previous_evidence':[prior],'current_evidence':[current],
        'explanation':'Fixture evidence selection only; no automatic financial loss conclusion.'}
    validate_change({'change_review':review},'entry',data)
    assert review['resolved_evidence']['current_evidence'][0]['pointer']=='/slim/price_history'

