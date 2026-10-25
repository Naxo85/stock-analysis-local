"""Reader33 regression: real ASTS archive, no model call or publication."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
import hashlib
import json
import pytest

from src.local_runner import adaptive_stage as stage
from src.local_runner.reader_report import apply_selection, migrate_payload, event_key
from src.local_runner.catalyst_editorial import assessment_schema, visible_catalysts
from src.local_runner.semantic_report import (reference_document, render_document, full_document,
    report_schema, check_schema, publication_fields)
from src.local_runner.adaptive_context import model_context, serialize_model_input, unpack_model_context
from src.local_runner.adaptive_maintenance import maintenance_decision, maintenance_schema
from src.local_runner.review_memory import read_memory
from src.local_runner.adaptive_budget import write_json, read_json
import test_plan_scope_v29 as old
import test_reader_report_v32 as previous

ROOT=Path(__file__).resolve().parent
ASTS=ROOT/'logs/adaptive_individual/20261013T144923435879/ASTS'

def original():
    return json.loads((ASTS/'publish/output/ASTS/latest.json').read_text(encoding='utf-8'))

def decision(role, rationale='Concrete present mechanism or reason for background', brief=None, covered_by=None):
    return dict(role=role,rationale=rationale,brief=brief,covered_by=covered_by)

def selection(ref):
    rows=reference_document(ref,verify_projection=True)['catalysts']
    ids={r['title']:'c'+str(i) for i,r in enumerate(rows,1)}
    competition='SpaceX amplía su apuesta por espectro'
    launch='Envío reportado de BlueBird 14–16'
    integration='TELUS valida la integración'
    choices=[]
    for title,id in ids.items():
        if title in (competition,launch,integration):
            c=decision('driver',brief='Efecto vigente distinto: '+title+'.')
        elif title in ('Piper cuestiona los lanzamientos','Lectura favorable de Deutsche Bank',
                       'Autorización competitiva para SpaceX'):
            c=decision('covered',covered_by=ids[competition])
        elif title=='William Blair recorta ingresos previstos':
            c=decision('covered',covered_by=ids[launch])
        else:
            c=decision('background')
        choices.append(dict(id=id,**c))
    return dict(catalysts=choices,hide_next_event=False)

def test_original_asts_eleven_facts_become_three_topics_without_deleting_or_redating():
    ref=original();before=deepcopy(ref)
    payload,changed=migrate_payload(ref,ref,ref,selection(ref),revision=33)
    assert changed and ref==before
    prior=reference_document(ref,verify_projection=True)
    doc=reference_document(payload,verify_projection=True)
    assert len(prior['catalysts'])==len(doc['catalysts'])==11
    assert len(visible_catalysts(doc))==3
    for key in ('summary','plan','catalysts','next_event','conclusion','text_provenance'):
        assert doc.get(key)==prior.get(key)
    for key in ('generated_at','decision','plan','catalysts','next_event'):
        assert payload[key]==ref[key]
    text=render_document(doc)
    for row in visible_catalysts(doc): assert row['description'] in text
    for row in doc['catalysts']:
        assert row['description'] not in text  # Reader briefs, not full archive records.
    read_memory(payload,ref)
    again,changed=migrate_payload(payload,payload,ref,None,revision=33)
    assert not changed and again==payload
    context=json.loads((ASTS/'input.json').read_text(encoding='utf-8'))
    context.update(reference=payload,sol_reference=ref,routing_revision=33)
    wire=unpack_model_context(json.loads(serialize_model_input(model_context(context))))
    assert wire['reference']['semantic_data']['catalysts']==prior['catalysts']
    assert sum(x['currently_visible'] for x in wire['reader_catalog'].values())==3
    # Existing consumers see identical financial values.
    import sys
    sys.path.insert(0,str(ROOT/'gcp_services/stock_controller/src'))
    from stock_analysis.analysis_worker.reports import parse_analysis_report
    assert parse_analysis_report('ASTS',payload,report_url_template='{ticker}') == parse_analysis_report('ASTS',ref,report_url_template='{ticker}')

def test_full33_uses_same_financial_response_with_separate_editorial_assessments():
    context=json.loads((ASTS/'input.json').read_text(encoding='utf-8'));context['routing_revision']=33
    response=json.loads((ASTS/'report.response').read_text(encoding='utf-8'))
    ref=original();rows=reference_document(ref,verify_projection=True)['catalysts']
    titles={'c'+str(i):r['title'] for i,r in enumerate(rows,1)}
    choices={titles[r['id']]:{k:v for k,v in r.items() if k!='id'} for r in selection(ref)['catalysts']}
    for choice in choices.values():
        if choice['covered_by']:choice['covered_by']=titles[choice['covered_by']]
    for row in response['catalysts']:
        row.pop('show_in_report')
        row['reader_assessment']=choices[row['title']]
    before=deepcopy(response)
    check_schema(response,report_schema(33))
    doc=full_document(response,model_context(context),binding=old.bound(context,response,'report'))
    assert response==before and len(visible_catalysts(doc))==3
    prior=reference_document(ref,verify_projection=True)
    assert doc['catalysts']==prior['catalysts']
    assert doc['summary']==prior['summary']
    assert doc['plan']==prior['plan']
    assert 'reader_assessment' not in json.dumps(doc['catalysts'])
    tampered=deepcopy(response);tampered['catalysts'][0]['impact']=-10
    with pytest.raises(ValueError):
        full_document(tampered,model_context(context),binding=old.bound(context,response,'report'))

@pytest.mark.parametrize('bad',['unknown','missing','duplicate','cycle','blank','financial_extra'])
def test_bad_editorial_contract_preserves_previous_view_without_paid_repair(bad):
    ref=original();view=selection(ref)
    prior=reference_document(ref,verify_projection=True);doc=deepcopy(prior)
    if bad=='unknown':view['catalysts'][0]['covered_by']='c999'
    if bad=='missing':view['catalysts'].pop()
    if bad=='duplicate':view['catalysts'].append(deepcopy(view['catalysts'][0]))
    if bad=='cycle':
        view['catalysts'][2]=dict(id='c3',**decision('covered',covered_by='c1'))
    if bad=='blank':view['catalysts'][2]['brief']=''
    if bad=='financial_extra':view['catalysts'][2]['impact']=-10
    apply_selection(doc,prior,view,revision=33)
    assert doc['reader_presentation']['warning']
    assert visible_catalysts(doc)==prior['catalysts']
    context=old.data();context['routing_revision']=33
    response=json.loads((old.BATCH/'CRDO/triage.response').read_text(encoding='utf-8'))
    response['reader_review']=view
    assert maintenance_decision(response,[],model_context(context))=='retain'
    for flag in response['risk']:
        changed=deepcopy(response);changed['risk'][flag]=True
        assert maintenance_decision(changed,[],model_context(context))=='escalate'

def test_old_material_risk_survives_and_recent_noise_can_be_background_no_quota():
    _,doc=previous.payload32()
    doc['catalysts']=[dict(date='2020-01-01',title='Debt due tomorrow',impact=-9,description='Material covenant'),
                      dict(date='2026-10-13',title='Repeated PR',impact=5,description='No changed consequence')]
    baseline=deepcopy(doc)
    review=dict(catalysts=[dict(id='c1',**decision('driver',brief='Old debt has a payment due tomorrow.')),
                            dict(id='c2',**decision('background'))],hide_next_event=False)
    apply_selection(doc,baseline,review,revision=33)
    assert [e['title'] for e in visible_catalysts(doc)]==['Debt due tomorrow']
    review['catalysts'][0]=dict(id='c1',**decision('background'))
    apply_selection(doc,baseline,review,revision=33)
    assert visible_catalysts(doc)==[]  # no minimum and no automatic numerical priority
    assert len(doc['catalysts'])==2

def test_group_identity_survives_reorder_but_never_hides_changed_facts():
    ref=original();doc=reference_document(ref,verify_projection=True)
    apply_selection(doc,deepcopy(doc),selection(ref),revision=33)
    expected=visible_catalysts(doc)
    doc['catalysts'].reverse()
    assert sorted(visible_catalysts(doc),key=lambda x:x['title'])==sorted(expected,key=lambda x:x['title'])
    doc['catalysts'][0]['description']='Changed financial fact'
    assert len(visible_catalysts(doc))==11  # discard now-stale briefs, keep all current facts

def test_full_missing_editorial_assessment_does_not_break_finance():
    context=json.loads((ASTS/'input.json').read_text(encoding='utf-8'));context['routing_revision']=33
    response=json.loads((ASTS/'report.response').read_text(encoding='utf-8'))
    for row in response['catalysts']:row.pop('show_in_report')
    doc=full_document(response,model_context(context),binding=old.bound(context,response,'report'))
    assert doc['reader_presentation']['warning']
    assert len(visible_catalysts(doc))==11

def test_contract33_replaces_archive_instruction_both_roles_and_keeps_frozen32(tmp_path):
    context=old.data();policy=json.loads((ROOT/'config/codex_analysis.json').read_text());policy['routing_revision']=33
    work=tmp_path/'CRDO';work.mkdir()
    with ExitStack() as stack:
        clock=stack.enter_context(patch.object(stage,'datetime',wraps=datetime))
        clock.now.return_value=datetime.fromisoformat(context['prepared_at'])
        for name,result in [('load_policy',policy),('load_reference_payload',context['sol_reference']),
                            ('load_current_report',context['reference']),('load_research',None)]:
            stack.enter_context(patch.object(stage,name,return_value=result))
        for name,result in [('_fetch_slim',context['slim']),('_load_analyst_quality',{}),
            ('load_compact_analyst_summary',{}),('load_recent_analyst_actions',context['analyst_actions']),
            ('load_recent_news',context['news']),('_load_system_prompt','legacy')]:
            stack.enter_context(patch.object(stage.one,name,return_value=result))
        stack.enter_context(patch.object(stage,'call_codex',side_effect=AssertionError('NO MODEL')))
        stage.prepare(ROOT,work,'CRDO',context['owned'],context['tier'])
        for name in ('instructions.md','triage_instructions.md'):
            text=(work/name).read_text(encoding='utf-8')
            assert 'CATALYST EDITORIAL33' in text
            assert 'La narrativa desde el último earnings debe integrarse aquí' not in text
            assert 'Each catalyst includes show_in_report:boolean' not in text
            assert 'reader_assessment' in text
        frozen={p.name:p.read_bytes() for p in work.iterdir()}
        policy['routing_revision']=32
        stage.prepare(ROOT,work,'CRDO',context['owned'],context['tier'])
        assert frozen=={p.name:p.read_bytes() for p in work.iterdir()}
    ref=original()
    assert render_document(reference_document(ref,verify_projection=True))==ref['analysis_markdown']
    v8=(ROOT/'prompts/stock_analysis_semantic_v8.md').read_text(encoding='utf-8')
    v9=(ROOT/'prompts/stock_analysis_semantic_v9.md').read_text(encoding='utf-8')
    assert v8.split('\nCatalizadores\n')[0]==v9.split('\nCatalizadores:')[0]
    assert v8.split('\nPróximo evento clave\n')[1]==v9.split('\nPróximo evento clave\n')[1]

def test_retain33_stages_digest_with_one_existing_call_and_unchanged_finance(tmp_path):
    context=old.data();context['routing_revision']=33
    policy=json.loads((ROOT/'config/codex_analysis.json').read_text());policy['routing_revision']=33
    work=tmp_path/'adaptive/CRDO';work.mkdir(parents=True)
    write_json(work/'input.json',context);write_json(work/'policy.json',policy)
    response=json.loads((old.BATCH/'CRDO/triage.response').read_text(encoding='utf-8'))
    rows=reference_document(context['reference'],verify_projection=True)['catalysts']
    choices=[dict(id='c'+str(i),**(decision('driver',brief=row['description']) if i==1 else decision('background'))) for i,row in enumerate(rows,1)]
    response['reader_review']=dict(catalysts=choices,hide_next_event=False)
    check_schema(response['reader_review'],maintenance_schema(model_context(context))['properties']['reader_review'])
    calls=[]
    def call(root,work,symbol,budget,policy,kind,supplied,**kwargs):
        calls.append(kind);assert kind=='triage'
        view=model_context(supplied);view.pop('research_memory',None)
        text=json.dumps(response);(work/'triage.response').write_text(text,encoding='utf-8')
        return dict(text=text,exit_code=0,completed_at=context['prepared_at'],
                    input_sha256=hashlib.sha256(serialize_model_input(view).encode()).hexdigest(),
                    model=policy['triage_model'],usage={})
    with patch.object(stage,'model_call',side_effect=call), patch.object(stage,'itv_state',return_value={'due':False,'age_sessions':1}), patch.object(stage,'maintenance_precheck',return_value={'guards':[],'review_flags':[]}):
        with patch.object(stage, 'datetime', wraps=datetime) as clock:
            clock.now.return_value=datetime.fromisoformat(context['prepared_at'])
            review=stage.analyze(tmp_path,work,'CRDO',tmp_path/'budget.json',False)
    assert calls==['triage'] and review['status']=='retained'
    payload=read_json(work/'publish/output/CRDO/latest.json')
    assert payload['generated_at']==context['reference']['generated_at']
    assert payload['catalysts']==context['reference']['catalysts']
    assert len(visible_catalysts(reference_document(payload,verify_projection=True)))==1
    read_memory(payload,context['sol_reference'])
