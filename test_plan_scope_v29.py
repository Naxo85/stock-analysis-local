"""Offline scope migration: real bases/receipts stay immutable; no model calls."""
import json
import hashlib
from copy import deepcopy
from pathlib import Path
from datetime import datetime
from contextlib import ExitStack
from unittest.mock import patch
import pytest
from src.local_runner.plan_scope import BUY_PLAN_KEYS, RETIRED_PLAN_KEYS, migrate_retained
from src.local_runner.semantic_report import (reference_document, report_schema, update_schema,
    maintenance_document, check_schema, render_document, _validate_geometry)
from src.local_runner.semantic_sources import source_catalog
from src.local_runner.adaptive_context import model_context, serialize_model_input, unpack_model_context
from src.local_runner.semantic_binding import bind_response
from src.local_runner.adaptive_maintenance import maintenance_decision
from src.local_runner import adaptive_stage as stage

ROOT=Path(__file__).resolve().parent
BATCH=ROOT/'logs/batch/2026-10-13/09-03-29/adaptive'

def data(symbol='CRDO'):
    result=json.loads((BATCH/symbol/'input.json').read_text(encoding='utf-8'))
    result['routing_revision']=29
    return result

def bound(context, response, kind='triage'):
    view=model_context(context)
    if kind!='report':view.pop('research_memory',None)
    receipt={'text':json.dumps(response),'exit_code':0,
             'input_sha256':hashlib.sha256(serialize_model_input(view).encode()).hexdigest()}
    return bind_response(context,receipt,kind)

def sofi_update():
    context=data('SOFI');context['guards']=[];old=deepcopy(context);old['routing_revision']=28
    old_catalog=source_catalog(old);current=source_catalog(context)
    by_pointer={v['pointer']:k for k,v in current.items()}
    remap={k:by_pointer[v['pointer']] for k,v in old_catalog.items() if v['pointer'] in by_pointer}
    response=json.loads((BATCH/'SOFI/triage.response').read_text(encoding='utf-8'))
    def rewrite(value):
        if isinstance(value,dict):return {k:rewrite(v) for k,v in value.items()}
        if isinstance(value,list):return [rewrite(v) for v in value if not isinstance(v,str) or v not in old_catalog or v in remap]
        return remap.get(value,value) if isinstance(value,str) else value
    response=rewrite(response)
    change=response['update'];change['plan']={k:change['plan'][k] for k in BUY_PLAN_KEYS}
    if change.get('plan_explanation'):
        for key in RETIRED_PLAN_KEYS:change['plan_explanation']['reasons'].pop(key,None)
    return context,response

def test_schemas_only_new_contract_changes():
    assert set(report_schema(29)['properties']['plan']['properties'])==set(BUY_PLAN_KEYS)
    assert set(update_schema(29)['properties']['plan']['properties'])==set(BUY_PLAN_KEYS)
    assert set(report_schema(28)['properties']['plan']['properties'])==set(BUY_PLAN_KEYS+RETIRED_PLAN_KEYS)
    assert 'target' in update_schema(28)['properties']['plan']['properties']
    explanations=update_schema(29)['properties']['plan_explanation']['anyOf'][0]['properties']
    assert not set(RETIRED_PLAN_KEYS)&set(explanations)

@pytest.mark.parametrize('owned',[True,False,None])
def test_no_numeric_stop_required_but_resistance_must_fit_entries(owned):
    plan={k:{'range':{'lower':v,'upper':v+1}} for k,v in zip(BUY_PLAN_KEYS,(90,80,110))}
    _validate_geometry(plan,{'routing_revision':29,'owned':owned})
    plan['resistance']['range']={'lower':85,'upper':86}
    with pytest.raises(ValueError,match='resistance_below_entry'):_validate_geometry(plan,{'routing_revision':29})

def test_all_46_retained_migrations_preserve_remaining_finance_and_dates():
    paths=list(BATCH.glob('*/input.json'));assert len(paths)==46
    for path in paths:
        original=path.read_bytes();context=json.loads(original);ref=context['reference'];before=deepcopy(ref)
        old=reference_document(ref,verify_projection=True)
        result,changed=migrate_retained(ref,context['sol_reference']);assert changed
        doc=reference_document(result,verify_projection=True)
        assert set(doc['plan'])==set(BUY_PLAN_KEYS)
        for key in BUY_PLAN_KEYS:assert doc['plan'][key]==old['plan'][key]
        for key in ('summary','catalysts','next_event','conclusion','fundamental_markdown'):
            assert doc.get(key)==old.get(key)
        assert result['generated_at']==ref['generated_at']
        assert result.get('last_full_report_at')==ref.get('last_full_report_at')
        assert doc['metadata']['snapshot_at']==old['metadata']['snapshot_at']
        assert doc['metadata']['reference_price']==old['metadata']['reference_price']
        assert not set(RETIRED_PLAN_KEYS)&set(result['plan'])
        for label in ('### Stop de gestión','### Stop estructural','### Salida / objetivo principal'):
            assert label not in result['analysis_markdown']
        assert 'Resistencia operativa' in result['analysis_markdown']
        if ref['analysis_markdown'].startswith('Mantenimiento técnico: Luna · '):
            assert result['analysis_markdown'].split('\n\n',1)[0]==ref['analysis_markdown'].split('\n\n',1)[0]
        assert migrate_retained(result,context['sol_reference'])==(result,False)
        context.update(reference=result,routing_revision=29)
        wire=unpack_model_context(json.loads(serialize_model_input(model_context(context))))
        assert set(wire['reference']['semantic_data']['plan'])==set(BUY_PLAN_KEYS)
        assert 'analysis_markdown' not in wire['reference']
        assert 'current_plan_geometry' not in wire['comparison']['deterministic']
        assert not any(v['pointer'].split('/')[-1] in RETIRED_PLAN_KEYS for v in source_catalog(context).values())
        assert ref==before and path.read_bytes()==original

def test_real_maintenance_numbers_survive_three_field_contract():
    context,response=sofi_update();check_schema(response['update'],update_schema(29))
    before=deepcopy(context)
    document=maintenance_document(response,model_context(context),binding=bound(context,response))
    assert set(document['plan'])==set(BUY_PLAN_KEYS)
    for key in BUY_PLAN_KEYS:
        candidate=response['update']['plan'][key]
        if candidate:assert document['plan'][key]['range']==candidate['range']
    assert context==before
    for flag in response['risk']:
        bad=deepcopy(response);bad['risk'][flag]=True
        assert maintenance_decision(bad,[],model_context(context))=='escalate'
    bad=deepcopy(response);bad['update']['plan']['target']=None
    with pytest.raises(ValueError):maintenance_document(bad,model_context(context),binding=bound(context,bad))
    binding=bound(context,response);context['slim']['latest_price']+=1
    with pytest.raises(ValueError,match='binding'):maintenance_document(response,model_context(context),binding=binding)

@pytest.mark.parametrize('revision',[29,35,36])
def test_retention_pipeline_stages_all_formats_rebinds_memory_without_full_or_new_date(tmp_path,revision):
    context=data();context['routing_revision']=revision
    policy=json.loads((ROOT/'config/codex_analysis.json').read_text());policy['routing_revision']=revision
    work=tmp_path/'adaptive/CRDO';work.mkdir(parents=True)
    from src.local_runner.adaptive_budget import write_json,read_json
    from src.local_runner.review_memory import read_memory
    write_json(work/'input.json',context);write_json(work/'policy.json',policy)
    response=json.loads((BATCH/'CRDO/triage.response').read_text(encoding='utf-8'))
    assert response['decision']=='retain'
    if revision>=35:response['reader_review']=None
    calls=[]
    def call(root,work,symbol,budget,policy,kind,supplied,**kwargs):
        calls.append(kind);assert kind=='triage'
        view=model_context(supplied);view.pop('research_memory',None)
        if revision>=36:
            from src.local_runner.semantic_sources import source_catalog
            token=next(k for k,v in source_catalog(view).items() if v['pointer']=='/slim/price_history')
            response['support_validity_review']={'entry':{'lower_bound':100,
                'reason':'Fixture extent, no financial change.','current_evidence':[token]},'ambitious_entry':None}
        text=json.dumps(response);(work/'triage.response').write_text(text,encoding='utf-8')
        return {'text':text,'exit_code':0,'completed_at':context['prepared_at'],
                'input_sha256':hashlib.sha256(serialize_model_input(view).encode()).hexdigest(),
                'model':policy['triage_model'],'usage':{}}
    with patch.object(stage,'model_call',side_effect=call),patch.object(stage,'itv_state',return_value={'due':False,'age_sessions':1}),patch.object(stage,'maintenance_precheck',return_value={'guards':[],'review_flags':[]}):
        with patch.object(stage,'datetime',wraps=datetime) as clock:
            clock.now.return_value=datetime.fromisoformat(context['prepared_at'])
            review=stage.analyze(tmp_path,work,'CRDO',tmp_path/'budget.json',False)
    assert calls==['triage'] and review['status']=='retained' and review['presentation_changed']
    output=work/'publish/output/CRDO'
    assert all((output/('latest.'+ext)).exists() for ext in ('md','html','json'))
    payload=read_json(output/'latest.json')
    assert payload['generated_at']==context['reference']['generated_at']
    if revision>=35:
        assert set(reference_document(payload,verify_projection=True)['plan'])=={'entry','ambitious_entry'}
        assert '### Resistencia' not in payload['analysis_markdown']
    if revision>=36:
        # This original case has both purchases absent: a display review must
        # never manufacture an extent or bring a withdrawn purchase back.
        assert 'entry_support_validity' not in payload['plan']
        assert 'Extensión inferior estimada' not in payload['analysis_markdown']
    read_memory(payload,context['sol_reference'])
    with patch.object(stage,'_read_json_gcs',side_effect=[context['reference'],context['sol_reference']]),patch.object(stage.one,'_upload') as upload,patch.object(stage,'_copy_json'),patch.object(stage,'save_reference_payload') as anchor:
        stage._publish_locked(tmp_path,work,'CRDO')
    upload.assert_called_once();anchor.assert_not_called()

def test_prepare_29_both_roles_and_freeze_without_model(tmp_path):
    context=data();policy=json.loads((ROOT/'config/codex_analysis.json').read_text());policy['routing_revision']=29
    work=tmp_path/'CRDO';work.mkdir()
    with ExitStack() as stack:
        clock=stack.enter_context(patch.object(stage,'datetime',wraps=datetime));clock.now.return_value=datetime.fromisoformat(context['prepared_at'])
        for name,result in [('load_policy',policy),('load_reference_payload',context['sol_reference']),('load_current_report',context['reference']),('load_research',None)]:stack.enter_context(patch.object(stage,name,return_value=result))
        for name,result in [('_fetch_slim',context['slim']),('_load_analyst_quality',{}),('load_compact_analyst_summary',{}),('load_recent_analyst_actions',context['analyst_actions']),('load_recent_news',context['news']),('_load_system_prompt','legacy')]:stack.enter_context(patch.object(stage.one,name,return_value=result))
        stack.enter_context(patch.object(stage,'call_codex',side_effect=AssertionError('NO MODEL')))
        stage.prepare(ROOT,work,'CRDO',context['owned'],context['tier'])
        for name in ('instructions.md','triage_instructions.md'):
            text=(work/name).read_text(encoding='utf-8')
            assert 'REVISION29' in text and 'THREE' in text
            assert 'all SIX' not in text and 'Stops remain' not in text
        frozen={p.name:p.read_bytes() for p in work.iterdir()}
        stage.prepare(ROOT,work,'CRDO',context['owned'],context['tier'])
        assert frozen=={p.name:p.read_bytes() for p in work.iterdir()}

def test_full_report_and_consumer_only_three_fields():
    from src.local_runner.semantic_report import full_document,publication_fields,validation_result
    source=ROOT/'logs/batch/2026-10-13/08-03-29/adaptive/CRDO'
    context=json.loads((source/'input.json').read_text(encoding='utf-8'))
    response=json.loads((source/'report.response').read_text(encoding='utf-8'))
    old_catalog=source_catalog(context);context['routing_revision']=29
    by_pointer={v['pointer']:k for k,v in source_catalog(context).items()}
    def remap(value):
        if isinstance(value,dict):return {k:remap(v) for k,v in value.items()}
        if isinstance(value,list):return [remap(v) for v in value
            if not isinstance(v,str) or v not in old_catalog or old_catalog[v]['pointer'] in by_pointer]
        return by_pointer[old_catalog[value]['pointer']] if isinstance(value,str) and value in old_catalog else value
    response['plan']={k:remap(response['plan'][k]) for k in BUY_PLAN_KEYS}
    doc=full_document(response,model_context(context),binding=bound(context,response,'report'))
    assert validation_result(doc).ok
    generated=datetime.fromisoformat(context['prepared_at'])
    fields=publication_fields(doc,render_document(doc),context['reference'],generated)
    payload={**context['reference'],**fields,'report_schema_version':7,'generated_at':generated.isoformat()}
    import sys
    sys.path.insert(0,str(ROOT/'gcp_services/stock_controller/src'))
    from stock_analysis.analysis_worker.reports import parse_analysis_report
    record=parse_analysis_report('CRDO',payload,report_url_template='{ticker}')
    assert record.entry_stop is None and record.washout_stop is None
    assert record.resistance is not None
    assert not set(RETIRED_PLAN_KEYS)&set(fields['plan'])

@pytest.mark.parametrize('owned',[True,False,None])
def test_retired_stop_crossings_no_longer_route_to_full(owned):
    from src.local_runner.adaptive_policy import maintenance_precheck
    source=ROOT/'logs/batch/2026-10-09/15-39-36/adaptive/ASTS/input.json'
    context=json.loads(source.read_text(encoding='utf-8'))
    def check(revision):return maintenance_precheck(context['reference'],context['slim'],context['sol_reference'],owned=owned,revision=revision)
    assert 'price_below_structural_stop' in check(28)['guards']
    current=check(29)
    assert not any('stop' in guard for guard in current['guards'])
    assert not any('stop' in flag['code'] for flag in current['review_flags'])

def test_29_repair_does_not_reintroduce_retired_fields():
    from src.local_runner.adaptive_repair import repair_context
    from src.local_runner.adaptive_maintenance import maintenance_schema
    context=data();context['maintenance_repair']={'rejection':'test'}
    schema=maintenance_schema(context)
    plan=schema['properties']['update']['anyOf'][0]['properties']['plan']['properties']
    assert set(plan)==set(BUY_PLAN_KEYS)
    repair=repair_context(context,{},'test')['maintenance_repair']['instruction']
    assert '29' in repair and 'sin stops ni objetivo duplicado' in repair.lower()
