"""SOFI 13-Oct: original receipts, contextual plan evidence and one-shot repair."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from src.local_runner.adaptive_context import model_context, unpack_model_context
from src.local_runner.semantic_binding import bind_response
from src.local_runner.semantic_report import maintenance_document
from src.local_runner.maintenance_change import validate_change

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'logs/batch/2026-10-13/09-03-29/adaptive/SOFI'

def original(kind='triage'):
    data=json.loads((SOURCE/'input.json').read_text(encoding='utf-8'))
    wire=unpack_model_context(json.loads((SOURCE/(kind+'.input.json')).read_text(encoding='utf-8')))
    for key in ('guards','review_flags','itv','maintenance_handoff','maintenance_repair'):
        if key in wire:data[key]=wire[key]
    receipt=json.loads((SOURCE/(kind+'.receipt.json')).read_text(encoding='utf-8'))
    receipt['text']=(SOURCE/(kind+'.response')).read_text(encoding='utf-8')
    return data,json.loads(receipt['text']),bind_response(data,receipt,kind)

@pytest.mark.parametrize('kind',['triage','triage_repair'])
def test_unchanged_bound_response_now_validates(kind):
    data,response,binding=original(kind)
    before=deepcopy((data,response))
    document=maintenance_document(response,model_context(data),binding=binding)
    assert (data,response)==before
    for key,block in response['update']['plan'].items():
        if block:
            assert document['plan'][key]['range']==block['range']
            assert document['plan'][key]['reason']==block['reason']
            assert document['plan'][key]['strength']==block['strength']
        else:
            prior=data['reference']['plan'][key]
            assert document['plan'][key]['range']==(prior if isinstance(prior,dict) else {'lower':prior,'upper':prior})
    for key in ('management_stop','structural_stop'):
        assert document['plan'][key]['range']['lower']==data['reference']['plan'][key]
    audit=document['plan']['ambitious_entry']['change_review']['resolved_evidence']['current_evidence']
    assert next(r for r in audit if r['source']=='s40')['evidence_role']=='dated_plan_context'
    assert next(r for r in audit if r['source']=='s9')['evidence_role']=='current_market_observation'

@pytest.mark.parametrize('basis',['backing_changed','material_improvement'])
@pytest.mark.parametrize('historical',['s36','s40','s48','s62'])
def test_history_cannot_replace_current_market_evidence(basis,historical):
    data,response,_=original()
    level=deepcopy(response['update']['plan']['ambitious_entry'])
    level['change_review'].update(basis=basis,current_evidence=[historical])
    with pytest.raises(ValueError,match='wrong_scope|missing_current_market_evidence'):
        validate_change(level,'ambitious_entry',model_context(data))

def test_other_previous_block_supplements_but_cannot_replace_subject():
    data,response,_=original();context=model_context(data)
    level=deepcopy(response['update']['plan']['entry'])
    validate_change(level,'entry',context)
    level['change_review']['previous_evidence']=['s36']
    with pytest.raises(ValueError,match='missing_previous_decision_evidence'):
        validate_change(level,'entry',context)

def test_one_repair_gets_all_independent_source_errors():
    data,response,_=original();context=model_context(data)
    level=deepcopy(response['update']['plan']['entry'])
    level['change_review'].update(previous_evidence=['s999','s36'],current_evidence=['s998','s62','s40'])
    with pytest.raises(ValueError) as error: validate_change(level,'entry',context)
    issues=error.value.maintenance_details['issues']
    assert {'s999','s998','s62'} <= {i.get('source') for i in issues}
    assert any('missing_previous_decision_evidence' in i['error'] for i in issues)
    assert any('missing_current_market_evidence' in i['error'] for i in issues)
    assert all(i['field'].startswith('/plan/entry/change_review/') for i in issues)
    assert next(i for i in issues if i.get('source')=='s62')['pointer'].startswith('/sol_reference/')

def test_legacy_behavior_is_unchanged():
    data,response,_=original();data['routing_revision']=27
    from src.local_runner.semantic_sources import source_catalog
    cat=source_catalog(data)
    own=next(k for k,v in cat.items() if v['pointer']=='/reference/semantic_data/plan/entry')
    other=next(k for k,v in cat.items() if v['pointer']=='/reference/semantic_data/plan/ambitious_entry')
    level=deepcopy(response['update']['plan']['entry'])
    level['change_review']['previous_evidence']=[own,other]
    with pytest.raises(ValueError,match='unrelated_previous_block'):validate_change(level,'entry',data)

@pytest.mark.parametrize('mutation',['response','source','base'])
def test_fix_does_not_weaken_original_response_binding(mutation):
    data,response,binding=original()
    if mutation=='response':response['update']['plan']['entry']['range']['lower']=14.1
    elif mutation=='source':data['slim']['price_history']['sessions'][-1]['close']=200
    else:data['reference']['analysis_markdown']+='changed'
    with pytest.raises(ValueError):maintenance_document(response,model_context(data),binding=binding)

def synthetic_binding(data,response):
    # A synthetic offline response; no actual receipt/file is altered or published.
    import hashlib
    from src.local_runner.adaptive_context import serialize_model_input
    view=model_context(data);view.pop('research_memory',None)
    receipt={'exit_code':0,'input_sha256':hashlib.sha256(serialize_model_input(view).encode()).hexdigest(),
             'text':json.dumps(response)}
    return bind_response(data,receipt,'triage')

def test_all_source_errors_survive_full_pipeline_for_single_repair():
    data,response,_=original()
    response['update']['plan']['entry']['change_review'].update(
        previous_evidence=['s999','s36'],current_evidence=['s998','s62','s40'])
    with pytest.raises(ValueError) as error:
        maintenance_document(response,model_context(data),binding=synthetic_binding(data,response))
    issues=error.value.maintenance_details['issues']
    assert {'s999','s998','s62'} <= {i.get('source') for i in issues}
    assert any('missing_previous_decision_evidence' in i['error'] for i in issues)
    assert any('missing_current_market_evidence' in i['error'] for i in issues)

@pytest.mark.parametrize('mutation',['risk','stop_edit','invented_zone','inverted_zone'])
def test_financial_authority_and_live_price_origins_still_checked(mutation):
    data,response,_=original()
    if mutation=='risk':response['risk']['structural_invalidation']=True
    elif mutation=='stop_edit':response['update']['plan']['management_stop']={'range':{'lower':14,'upper':14}}
    elif mutation=='invented_zone':response['update']['plan']['entry']['range']={'lower':14.1,'upper':14.2}
    else:response['update']['plan']['entry']['range']={'lower':14.92,'upper':14.88}
    with pytest.raises(ValueError):
        maintenance_document(response,model_context(data),binding=synthetic_binding(data,response))
