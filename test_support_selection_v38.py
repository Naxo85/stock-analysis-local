"""Selection policy regression: no model judgment fabricated from offline data."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import pytest

from src.local_runner.adaptive_context import model_context
from src.local_runner.adaptive_maintenance import maintenance_decision, maintenance_schema
from src.local_runner.adaptive_repair import repair_context
from src.local_runner.reader_report import migrate_payload
from src.local_runner.semantic_report import reference_document, render_document, report_schema, full_document
from src.local_runner.semantic_sources import source_catalog
from test_plan_scope_v29 import bound
from test_support_validity_v36 import fixture

ROOT=Path(__file__).resolve().parent
BATCH=ROOT/'logs/batch/2026-10-14/16-07-07/adaptive'
ABSENT={'ASTS','CIFR','IREN','LEU','MP','OKLO','QBTS','SOFI','USAR'}

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def published(ticker):
    return read(BATCH/ticker/'publish/output'/ticker/'latest.json')

def test_same_contract_source_catalog_and_risk_authority_without_quality_gate():
    ctx,view,_=fixture(revision=37)
    current=model_context({**ctx,'routing_revision':38})
    assert report_schema(38)==report_schema(37)
    assert maintenance_schema(current)==maintenance_schema(view)
    assert source_catalog(current)==source_catalog(view)
    triage=read(ROOT/'logs/batch/2026-10-14/11-43-17/adaptive/GEV/triage.json')
    assert maintenance_decision(triage,[],current)=='retain'
    for flag in triage['risk']:
        bad=deepcopy(triage);bad['risk'][flag]=True
        assert maintenance_decision(bad,[],current)=='escalate'
    blocked=deepcopy(triage);blocked['evidence_gap']='essential_data'
    assert maintenance_decision(blocked,[],current)=='blocked'
    before=repair_context({**ctx,'routing_revision':37},triage,'update_not_allowed_test')
    after=repair_context({**ctx,'routing_revision':38},triage,'update_not_allowed_test')
    assert 'Seleccion38' not in before['maintenance_repair']['instruction']
    assert 'Seleccion38' in after['maintenance_repair']['instruction']
    assert after['maintenance_repair']['attempt']==1
    assert after['maintenance_repair']['previous_response']==triage

def test_all_original_zones_render_without_inventing_absence_classification_or_numbers():
    both=set();absent=active=under70=0
    paths=list(BATCH.glob('*/publish/output/*/latest.json'));assert len(paths)==46
    for path in paths:
        frozen=path.read_bytes();payload=json.loads(frozen)
        before=reference_document(payload,verify_projection=True)
        assert render_document(before)==payload['analysis_markdown']
        doc=deepcopy(before);doc['metadata']['reader_format_revision']=38
        text=render_document(doc)
        local_absent=sum(z['range'] is None for z in doc['plan'].values())
        assert text.count('Sin zona de compra seleccionada')==local_absent
        assert {k:v for k,v in doc.items() if k!='metadata'}=={k:v for k,v in before.items() if k!='metadata'}
        if local_absent==2:both.add(path.parent.name)
        absent+=local_absent
        for zone in doc['plan'].values():
            assert zone['reason'] in text
            if zone['range']:
                active+=1
                total=sum(zone['strength']['components'].values())
                under70+=total<70
                assert 'Fortaleza: '+str(total)+'/100' in text
        assert path.read_bytes()==frozen
    assert both==ABSENT and (absent,active,under70)==(26,66,53)

@pytest.mark.parametrize('ticker',sorted(ABSENT))
def test_nine_original_receipts_distinguish_historical_origin_from_moving_first_low(ticker):
    path=BATCH/ticker/'input.json';receipt=BATCH/ticker/'report.response'
    frozen=path.read_bytes();response=receipt.read_bytes();ctx=json.loads(frozen)
    supports=ctx['slim']['levels']['supports'];assert supports
    historical=[z for z in supports if z.get('evidence',{}).get('historical_reaction',{}).get('defense_count',0)>0]
    if ticker in {'IREN','MP'}:
        assert len(historical)==1
        level=historical[0];reaction=level['evidence']['historical_reaction']
        assert reaction['defense_count']==1 and reaction['last_test_date']=='2026-07-29'
        assert level['level']<ctx['slim']['latest_price']
        assert level['level']=={'IREN':28.93,'MP':37.81}[ticker]
    else:
        assert not historical
        rolling=next(z for z in supports if z['type']=='52_week_low')
        assert rolling['date']=='2026-10-14'
        assert rolling['evidence']['historical_reaction']['status']=='unavailable'
    # This authenticates the scenario, NOT a rule selecting/rejecting its zones.
    assert path.read_bytes()==frozen and receipt.read_bytes()==response

@pytest.mark.parametrize('ticker',['IREN','MP','ASTS'])
def test_natural_reader_migration_preserves_all_finance_dates_bounds_and_anchor(ticker):
    from src.local_runner.review_memory import read_memory
    payload=published(ticker);original=deepcopy(payload)
    # This published full starts a NEW epoch; input.sol_reference is the old full.
    anchor=payload
    old_memory=read_memory(payload,anchor)
    # The previous epoch MUST still be rejected, not silently rebound.
    previous_anchor=read(BATCH/ticker/'input.json')['sol_reference']
    with pytest.raises(ValueError,match='invalid_published_review_memory'):
        migrate_payload(payload,payload,previous_anchor,None,revision=38)
    doc=reference_document(payload,verify_projection=True)
    migrated,changed=migrate_payload(payload,payload,anchor,None,revision=38)
    assert changed and payload==original
    after=reference_document(migrated,verify_projection=True)
    for key in ('plan','summary','catalysts','next_event','conclusion','text_provenance','support_validity_audit'):
        assert after.get(key)==doc.get(key)
    for key in ('generated_at','last_full_report_at','sol_anchor_sha256','decision','plan','catalysts'):
        assert migrated.get(key)==payload.get(key)
    assert migrated['analysis_markdown'].count('Sin zona de compra seleccionada')==2
    assert read_memory(migrated,anchor)==old_memory
    assert migrate_payload(migrated,migrated,anchor,None,revision=38)==(migrated,False)
    sys.path.insert(0,str(ROOT/'gcp_services/stock_controller/src'))
    from stock_analysis.analysis_worker.reports import parse_analysis_report
    assert parse_analysis_report(ticker,migrated,report_url_template='{ticker}')==parse_analysis_report(ticker,payload,report_url_template='{ticker}')

@pytest.mark.parametrize('ticker',['MP','AUR'])
def test_original_full_receipt38_keeps_absent_or_moderate_decision_and_source_guards(ticker):
    path=BATCH/ticker/'report.response';frozen=path.read_bytes();response=json.loads(frozen)
    ctx=read(BATCH/ticker/'input.json');ctx['routing_revision']=38
    view=model_context(ctx)
    doc=full_document(response,view,binding=bound(ctx,response,'report'))
    old=reference_document(published(ticker),verify_projection=True)
    assert doc['plan']==old['plan']
    assert doc['summary']==old['summary']
    assert doc['metadata']['source_contract_revision']==38
    assert path.read_bytes()==frozen
    if ticker=='AUR':
        assert sum(doc['plan']['entry']['strength']['components'].values())==52
        bad=deepcopy(response);bad['plan']['entry']['evidence']=['s999999']
        with pytest.raises(ValueError):
            full_document(bad,view,binding=bound(ctx,bad,'report'))
