"""Scope-only removal; no model calls or live publication."""
from copy import deepcopy
from contextlib import ExitStack
from datetime import datetime
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from src.local_runner.plan_scope import migrate_retained, SUPPORT_KEYS
from src.local_runner.semantic_report import (reference_document, report_schema, update_schema,
    full_document, maintenance_document, render_document, publication_fields, validation_result)
from src.local_runner.semantic_sources import source_catalog
from src.local_runner.adaptive_context import model_context, unpack_model_context, serialize_model_input
from src.local_runner.adaptive_repair import repair_context
from test_plan_scope_v29 import bound, sofi_update
from src.local_runner import adaptive_stage as stage

ROOT=Path(__file__).resolve().parent
FOLDER=ROOT/'logs/adaptive_individual/20261013T152809317353/ASTS'

def original():
    context=json.loads((FOLDER/'input.json').read_text(encoding='utf-8'))
    payload=json.loads((FOLDER/'report.response').read_text(encoding='utf-8'))
    return context,payload

def remap(context,response):
    old=source_catalog(context)
    context['routing_revision']=35
    new={v['pointer']:k for k,v in source_catalog(context).items()}
    def rec(v):
        if isinstance(v,dict):return {k:rec(x) for k,x in v.items()}
        if isinstance(v,list):return [rec(x) for x in v]
        return new[old[v]['pointer']] if isinstance(v,str) and v in old else v
    return rec(response)

def test_schema_both_roles_and_repair_remove_calculation_not_just_prose():
    for schema in (report_schema,update_schema):
        assert set(schema(35)['properties']['plan']['properties'])==set(SUPPORT_KEYS)
        assert 'resistance' in schema(34)['properties']['plan']['properties']
    explanation=update_schema(35)['properties']['plan_explanation']['anyOf'][0]['properties']['reasons']['properties']
    assert set(explanation)==set(SUPPORT_KEYS)
    instruction=repair_context({'routing_revision':35},{},'update_not_allowed_test')['maintenance_repair']['instruction']
    assert 'Solo entry y ambitious_entry' in instruction and 'Rubrica34' in instruction
    assert 'Una sola resistencia relevante' not in instruction and 'y resistance;' not in instruction
    context,_=original();context['routing_revision']=35
    wire=unpack_model_context(json.loads(serialize_model_input(model_context(context))))
    for key in ('reference','sol_reference'):
        assert set(wire[key]['semantic_data']['plan'])==set(SUPPORT_KEYS)
        assert not {'analysis_markdown','plan','semantic_report'} & wire[key].keys()

def test_original_full_finance_and_consumer_work_without_resistance():
    context,payload=original();before=deepcopy(context)
    payload['plan']={k:payload['plan'][k] for k in SUPPORT_KEYS}
    payload=remap(context,payload)
    doc=full_document(payload,model_context(context),binding=bound(context,payload,'report'))
    assert set(doc['plan'])==set(SUPPORT_KEYS)
    assert validation_result(doc).ok and validation_result(doc).resistance_range is None
    assert '### Resistencia' not in render_document(doc)
    fields=publication_fields(doc,render_document(doc),context['reference'],datetime.fromisoformat(context['prepared_at']))
    assert not any(k.startswith('resistance') for k in fields['plan'])
    import sys
    sys.path.insert(0,str(ROOT/'gcp_services/stock_controller/src'))
    from stock_analysis.analysis_worker.reports import parse_analysis_report
    record=parse_analysis_report('ASTS',{**context['reference'],**fields,'report_schema_version':7},report_url_template='{ticker}')
    assert record.resistance is None and record.resistance_strength is None
    assert context['reference']==before['reference'] and context['sol_reference']==before['sol_reference']

def test_real_maintenance_retains_buying_decisions_and_risk_authority():
    context,response=sofi_update()
    response['reader_review']=None
    response['update']['plan'].pop('resistance')
    if response['update']['plan_explanation']:
        response['update']['plan_explanation']['reasons'].pop('resistance')
    response=remap(context,response)
    doc=maintenance_document(response,model_context(context),binding=bound(context,response))
    assert set(doc['plan'])==set(SUPPORT_KEYS)
    from src.local_runner.adaptive_maintenance import maintenance_decision
    for flag in response['risk']:
        bad=deepcopy(response);bad['risk'][flag]=True
        assert maintenance_decision(bad,[],model_context(context))=='escalate'

def test_retained_scope_migration_exact_dates_prices_scores_memory_and_next_review():
    context,_=original()
    for path in (ROOT/'logs/batch/2026-10-13/12-41-28/adaptive').glob('*/input.json'):
        frozen=path.read_bytes();case=json.loads(frozen);ref=case['reference'];anchor=case['sol_reference']
        before=reference_document(ref,verify_projection=True)
        migrated,changed=migrate_retained(ref,anchor,35)
        assert changed
        doc=reference_document(migrated,verify_projection=True)
        assert set(doc['plan'])==set(SUPPORT_KEYS)
        for key in SUPPORT_KEYS:assert doc['plan'][key]==before['plan'][key]
        for key in ('summary','catalysts','next_event','conclusion','reader_presentation'):
            assert doc.get(key)==before.get(key)
        assert migrated['generated_at']==ref['generated_at']
        assert migrated.get('last_full_report_at')==ref.get('last_full_report_at')
        assert doc['metadata']['source_contract_revision']==before['metadata']['source_contract_revision']
        assert '### Resistencia' not in migrated['analysis_markdown']
        assert migrate_retained(migrated,anchor,35)==(migrated,False)
        case.update(reference=migrated,routing_revision=35)
        view=unpack_model_context(model_context(case))
        assert all(row['label']!='Resistencia operativa' for row in view['comparison']['plan_source_inventory']['zones'])
        assert 'resistance' not in view['comparison']['plan_origin_observations']['zones']
        assert not any(v['pointer'].endswith('/plan/resistance') for v in source_catalog(case).values())
        assert path.read_bytes()==frozen

@pytest.mark.parametrize('revision',[35,36,37,38])
def test_prepare_replaces_conflicting_prompts_and_freezes_older_contract(tmp_path,revision):
    context,_=original();policy=json.loads((ROOT/'config/codex_analysis.json').read_text());policy['routing_revision']=revision
    work=tmp_path/'ASTS';work.mkdir()
    with ExitStack() as stack:
        clock=stack.enter_context(patch.object(stage,'datetime',wraps=datetime));clock.now.return_value=datetime.fromisoformat(context['prepared_at'])
        for name,result in [('load_policy',policy),('load_reference_payload',context['sol_reference']),('load_current_report',context['reference']),('load_research',None)]:stack.enter_context(patch.object(stage,name,return_value=result))
        for name,result in [('_fetch_slim',context['slim']),('_load_analyst_quality',{}),('load_compact_analyst_summary',{}),('load_recent_analyst_actions',context['analyst_actions']),('load_recent_news',context['news']),('_load_system_prompt','legacy')]:stack.enter_context(patch.object(stage.one,name,return_value=result))
        stack.enter_context(patch.object(stage,'call_codex',side_effect=AssertionError('NO MODEL')))
        stage.prepare(ROOT,work,'ASTS',context['owned'],context['tier'])
        for name in ('instructions.md','triage_instructions.md'):
            text=(work/name).read_text(encoding='utf-8')
            assert 'REVISION35' in text and 'VOLUME RUBRIC34' in text
            assert ('SUPPORT VALIDITY36' in text)==(revision==36)
            assert ('SUPPORT VALIDITY37' in text)==(revision>=37)
            assert ('SELECCION38' in text)==(revision>=38)
            if revision>=38:
                assert 'no son requisitos acumulativos obligatorios' in text
                assert 'no una zona “aceptable”' not in text
                assert 'Sin alternativa apta usa Sin zona verificable' not in text
            for old in ('all THREE','one operational resistance','Resistencia operativa única','three-zone plan'):
                assert old not in text
        frozen={p.name:p.read_bytes() for p in work.iterdir()}
        policy['routing_revision']=34
        stage.prepare(ROOT,work,'ASTS',context['owned'],context['tier'])
        assert frozen=={p.name:p.read_bytes() for p in work.iterdir()}
        policy['routing_revision']=38
        stage.prepare(ROOT,work,'ASTS',context['owned'],context['tier'])
        assert frozen=={p.name:p.read_bytes() for p in work.iterdir()}
