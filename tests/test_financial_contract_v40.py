"""Revision40 financial contract regressions, entirely offline and read-only originals."""
from copy import deepcopy
from contextlib import ExitStack
from datetime import datetime
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from src.local_runner import adaptive_stage as stage
from src.local_runner.adaptive_context import model_context
from src.local_runner.adaptive_repair import repair_context
from src.local_runner.semantic_sources import normalize_plan, source_catalog
from src.local_runner.semantic_report import (full_document, maintenance_document,
    reference_document, _validate_geometry, report_schema, update_schema)
from src.local_runner.review_contract import reconcile_plan_explanation
from src.local_runner.volume_arithmetic import _inherited_buy_volume, validate
from test_plan_scope_v29 import bound

ROOT = Path(__file__).resolve().parents[1]
# Staged copies can run before installation, without assuming a second repository.
if not (ROOT/'src').is_dir():
    ROOT = next(p for p in Path(__file__).resolve().parents if (p/'src').is_dir())
BATCH = ROOT/'logs/batch/2026-10-16/15-58-24/adaptive'
FULL = ROOT/'logs/batch/2026-10-14/16-07-07/adaptive'

def capture(ticker, *, full=False, revision=40):
    folder = (FULL if full else BATCH)/ticker
    context = json.loads((folder/'input.json').read_text(encoding='utf-8'))
    context['routing_revision'] = revision
    response = json.loads((folder/('report.response' if full else 'triage.response')).read_text(encoding='utf-8'))
    if full and revision >= 40:
        response['thesis_state'] = None  # Counterfactual new schema, never mutate frozen response.
    return context, response

def maintained(context, response):
    return maintenance_document(response, model_context(context), binding=bound(context,response))

@pytest.mark.parametrize('washout', [dict(lower=100,upper=101), dict(lower=99,upper=100),
    dict(lower=100.5,upper=102), dict(lower=102,upper=103)])
def test_duplicate_touching_overlap_and_inversion_only_rejected_in_new_contract(washout):
    plan = {'entry': {'range':dict(lower=100,upper=101)}, 'ambitious_entry':{'range':washout}}
    frozen = deepcopy(plan)
    for revision in (35,36,37,38,39):
        _validate_geometry(plan, {'routing_revision':revision})
    with pytest.raises(ValueError,match='buy_zone_geometry'):
        _validate_geometry(plan, {'routing_revision':40})
    assert plan == frozen

@pytest.mark.parametrize('entry,washout', [(None,None),(None,dict(lower=99,upper=100)),
    (dict(lower=100,upper=101),None), (dict(lower=100,upper=101),dict(lower=99,upper=99.999999999))])
def test_absent_slots_and_arbitrarily_small_positive_gap_are_allowed(entry,washout):
    _validate_geometry({'entry':{'range':entry},'ambitious_entry':{'range':washout}},
                       {'routing_revision':40,'slim':{'atr':999999}})

def test_full_validator_rejects_duplicate_original_zone_without_rescoring():
    context,response=capture('AUR',full=True,revision=39)
    response['plan']['ambitious_entry']=deepcopy(response['plan']['entry'])
    full_document(response,model_context(context),binding=bound(context,response,'report'))
    context['routing_revision']=40
    response['thesis_state']=None
    frozen=deepcopy(response)
    with pytest.raises(ValueError,match='buy_zone_geometry'):
        full_document(response,model_context(context),binding=bound(context,response,'report'))
    assert response==frozen

def test_maintenance_validator_checks_resulting_two_zone_geometry():
    context,response=capture('GEV')
    old=reference_document(context['reference'],verify_projection=True)
    response['update']['plan']['ambitious_entry']['range']=deepcopy(old['plan']['entry']['range'])
    with pytest.raises(ValueError) as exc:
        maintained(context,response)
    assert any('buy_zone_geometry' in row['error'] for row in exc.value.maintenance_details['issues'])

def test_tln_original_citation_in_review_inherits13_without_modifying_payload():
    context,response=capture('TLN',revision=39)
    with pytest.raises(ValueError,match='select_profile_and_reaction_sources'):
        maintained(context,response)
    context['routing_revision']=40
    before=deepcopy((context,response))
    result=maintained(context,response)
    assert result['plan']['entry']['strength']['components']['volumen']==13
    assert 'volume_calculation_audit' not in result['plan']['entry']
    assert (context,response)==before
    for key in ('range','strength','reason','volume_calculation'):
        assert result['plan']['entry'][key]==response['update']['plan']['entry'][key]

@pytest.mark.parametrize('mutation', ['anchor','descendant','missing','unknown','range','volume'])
def test_review_citation_cannot_borrow_wrong_authority_or_changed_volume(mutation):
    context,response=capture('TLN')
    view=model_context(context)
    prior=reference_document(context['reference'],verify_projection=True)['plan']
    plans,issues=normalize_plan(response['update']['plan'],prior,view)
    assert not issues
    block=plans['entry']; catalog=source_catalog(view)
    pointer='/reference/semantic_data/plan/ambitious_entry'
    own=next(h for h,row in catalog.items() if row['pointer']==pointer)
    selected=block['change_review']['previous_evidence']; assert own in selected
    if mutation=='range': block['range']['lower']-=.01
    elif mutation=='volume': block['strength']['components']['volumen']+=1
    else:
        selected.remove(own)
        if mutation=='anchor': selected.append(next(h for h,row in catalog.items() if row['pointer']=='/sol_reference/semantic_data/plan/ambitious_entry'))
        if mutation=='descendant': selected.append(own+'/strength/components/volumen')
        if mutation=='unknown': selected.append('s999999')
    assert not _inherited_buy_volume(block,'entry',view)
    with pytest.raises(ValueError,match='select_profile_and_reaction_sources'):
        validate(block,'entry',view,prior['entry'])

def test_tln_current_digest_and_live_change_evidence_still_required():
    context,response=capture('TLN')
    context['reference']['analysis_markdown']+='\nUNAUTHENTICATED'
    with pytest.raises(ValueError): maintained(context,response)
    context,response=capture('TLN')
    response['update']['plan']['entry']['change_review']['current_evidence']=[]
    with pytest.raises(ValueError,match='missing_current_evidence'): maintained(context,response)

@pytest.mark.parametrize('ticker',['GEV','LEU','LRCX','QBTS','RKLB','SOFI','SPCX'])
def test_original_changed_plans_no_longer_require_empty_certificate(ticker):
    context,response=capture(ticker,revision=39)
    with pytest.raises(ValueError,match='plan_coherence'): maintained(context,response)
    context['routing_revision']=40
    frozen=deepcopy(response)
    result=maintained(context,response)
    assert response==frozen
    for key,block in response['update']['plan'].items():
        if block is not None:
            for field in ('range','strength','reason'):
                assert result['plan'][key][field]==block[field]

def test_empty_certificate_does_not_add_review_stamp_or_authority():
    context,response=capture('GEV')
    expected=maintained(context,response)
    response['update']['plan_explanation']={'setup_reason':None,'conclusion':None,
        'reasons':{'entry':None,'ambitious_entry':None}}
    assert maintained(context,response)==expected

def test_text_edits_still_require_evidence_and_preserve_protected_schema():
    context,response=capture('GEV')
    response['update']['plan_explanation']={'setup_reason':None,'conclusion':None,
        'reasons':{'entry': {'text':'Nueva afirmación sin evidencia.', 'review':{
            'basis':'material_improvement','scope':'routine_technical',
            'previous_evidence':[],'current_evidence':[],'explanation':'Cambio.'}},'ambitious_entry':None}}
    with pytest.raises(ValueError): maintained(context,response)
    context,response=capture('GEV')
    response['update']['thesis_score']=100
    with pytest.raises(ValueError): maintained(context,response)

def test_one_reason_authority_prevents_second_overwrite_of_edited_level():
    context,response=capture('GEV')
    doc=maintained(context,response)
    old=reference_document(context['reference'],verify_projection=True)['plan']
    change=deepcopy(response['update'])
    change['plan_explanation']={'setup_reason':None,'conclusion':None,
        'reasons':{'entry':None,'ambitious_entry':'A contradictory second authoring path.'}}
    before=deepcopy(doc)
    issues=reconcile_plan_explanation(doc,change,old,model_context(context))
    assert any('single reason authority' in row['error'] for row in issues)
    assert doc==before

def test_schema_shape_stays_same_as39_and_repair_is_versioned():
    new=report_schema(40)
    assert 'thesis_state' in new['required']
    del new['properties']['thesis_state'];new['required'].remove('thesis_state')
    assert new==report_schema(39)
    assert update_schema(40)==update_schema(39)
    context,_=capture('GEV',revision=39)
    old=repair_context(context,{},'update_not_allowed_plan_coherence')['maintenance_repair']['instruction']
    context['routing_revision']=40
    new=repair_context(context,{},'update_not_allowed_plan_coherence')['maintenance_repair']['instruction']
    assert 'Contrato40' not in old and 'certificado vacio' in new
    assert 'Volumen exactos' in new and 'sin solapamiento' in new

@pytest.mark.parametrize('revision',[38,39,40])
def test_real_preparation_assembly_and_frozen_reuse(tmp_path,revision):
    context,_=capture('TLN',revision=revision)
    policy=json.loads((ROOT/'config/codex_analysis.json').read_text(encoding='utf-8'))
    policy['routing_revision']=revision
    work=tmp_path/str(revision); work.mkdir()
    with ExitStack() as stack:
        clock=stack.enter_context(patch.object(stage,'datetime',wraps=datetime));clock.now.return_value=datetime.fromisoformat(context['prepared_at'])
        for name,value in [('load_policy',policy),('load_reference_payload',context['sol_reference']),('load_current_report',context['reference']),('load_research',None),('_news_gap',False),('data_ready',None)]:
            stack.enter_context(patch.object(stage,name,return_value=value))
        for name,value in [('_fetch_slim',context['slim']),('_load_analyst_quality',{}),('load_compact_analyst_summary',{}),('load_recent_analyst_actions',context['analyst_actions']),('load_recent_news',context['news']),('_load_system_prompt','legacy')]:
            stack.enter_context(patch.object(stage.one,name,return_value=value))
        stack.enter_context(patch.object(stage,'run_bounded',side_effect=AssertionError('NO NETWORK')))
        stack.enter_context(patch.object(stage,'call_codex',side_effect=AssertionError('NO MODEL')))
        # This test isolates prompt assembly; source-admission has separate coverage.
        stack.enter_context(patch('src.local_runner.technical_preparation.require_option_origins',return_value=None))
        stage.prepare(ROOT,work,'TLN',context['owned'],context['tier'])
        for name in ('instructions.md','triage_instructions.md'):
            text=(work/name).read_text(encoding='utf-8')
            assert ('stronger <=3% gate' in text)==(revision<40)
            assert ('REVISION40' in text)==(revision>=40)
            assert text.count('VOLUME RUBRIC34 —')==1
        frozen={p.name:p.read_bytes() for p in work.iterdir()}
        policy['routing_revision']=40
        stage.prepare(ROOT,work,'TLN',context['owned'],context['tier'])
        assert frozen=={p.name:p.read_bytes() for p in work.iterdir()}


@pytest.mark.parametrize('flag',['thesis_change','critical_catalyst','structural_invalidation','requires_research'])
def test_maintenance_risk_authority_survives_certificate_removal(flag):
    context,response=capture('GEV')
    response['risk'][flag]=True
    with pytest.raises(ValueError): maintained(context,response)


def thesis_fixture():
    return {'status':'no_determinable','premise':'La ejecución comercial depende de contratos confirmados.',
            'assessment':'La fuente suministrada no resuelve el impacto sobre esa premisa.',
            'evidence':[{'source':'/news','observation':'La cobertura disponible limita la conclusión.'}]}

@pytest.mark.parametrize('status',['vigente','deteriorada','rota','no_determinable'])
def test_thesis_status_is_explicit_and_not_derived_from_low_score(status):
    from src.local_runner.thesis_state import establish
    context,response=capture('AUR',full=True)
    value=thesis_fixture();value['status']=status
    frozen=deepcopy(value)
    result=establish(value,model_context(context))
    assert result['status']==status and result['assessed_at']==context['slim']['as_of']
    assert result['evidence_audit'][0]['value_sha256'] and value==frozen
    assert establish(None,context) is None

@pytest.mark.parametrize('mutation',['empty_premise','empty_assessment','no_evidence','empty_observation','wrong_pointer','missing_pointer','javascript','credentials','unknown_state'])
def test_thesis_evidence_and_no_model_timestamp_contract(mutation):
    from src.local_runner.thesis_state import establish
    context,_=capture('AUR',full=True)
    value=thesis_fixture()
    if mutation=='empty_premise':value['premise']=' '
    elif mutation=='empty_assessment':value['assessment']=''
    elif mutation=='no_evidence':value['evidence']=[]
    elif mutation=='empty_observation':value['evidence'][0]['observation']=''
    elif mutation=='wrong_pointer':value['evidence'][0]['source']='/guards'
    elif mutation=='missing_pointer':value['evidence'][0]['source']='/news/nonexistent'
    elif mutation=='javascript':value['evidence'][0]['source']='javascript:alert(1)'
    elif mutation=='credentials':value['evidence'][0]['source']='https://user:password@example.com/report'
    else:value['status']='good'
    with pytest.raises(ValueError,match='thesis_state'):establish(value,model_context(context))


def test_full40_establishes_state_publication_and_projection_without_claiming_url_verified():
    from src.local_runner.semantic_report import publication_fields,render_document
    from src.local_runner.financial_projection import financial_document
    context,response=capture('AUR',full=True)
    response['thesis_state']=thesis_fixture()
    response['thesis_state']['evidence'].append({'source':'https://example.com/disclosure','observation':'Synthetic disclosed reference; not fetched.'})
    response['summary']['thesis_score']=3.5
    doc=full_document(response,model_context(context),binding=bound(context,response,'report'))
    state=doc['thesis_state']
    assert state['status']=='no_determinable' and doc['summary']['thesis_score']==3.5
    assert state['evidence_audit'][1]['kind']=='public_reference_not_independently_verified'
    projected=financial_document(doc,40)['thesis_state']
    assert 'evidence_audit' not in projected and projected['assessed_at']==state['assessed_at']
    assert 'thesis_state' not in financial_document(doc,39)
    fields=publication_fields(doc,render_document(doc),{},datetime.fromisoformat(context['prepared_at']))
    assert fields['decision']['thesis_state']=={key:state[key] for key in ('status','premise','assessment','assessed_at')}
    assert fields['semantic_report']['data']['thesis_state']==state
    response['thesis_state']['assessed_at']='2099-01-01'
    with pytest.raises(ValueError):full_document(response,model_context(context),binding=bound(context,response,'report'))


def test_maintenance_inherits_exact_thesis_state_and_date_without_edit_authority():
    from src.local_runner.semantic_report import digest
    from src.local_runner.thesis_state import establish
    context,response=capture('GEV')
    state=establish(thesis_fixture(),model_context(context))
    state['assessed_at']='2026-10-01T12:00:00Z'
    base=context['reference']['semantic_report']
    base['data']['thesis_state']=deepcopy(state)
    base['data_sha256']=digest(base['data'])
    result=maintained(context,response)
    assert result['thesis_state']==state
    response['update']['thesis_state']=None
    with pytest.raises(ValueError):maintained(context,response)
