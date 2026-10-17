"""Offline cases: price extent must not mutate finance or buy another call."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from src.local_runner.support_validity import apply_review, bound_extent, migrate_payload
from src.local_runner.semantic_report import full_document, reference_document, render_document, report_schema
from src.local_runner.semantic_sources import source_catalog
from src.local_runner.adaptive_context import model_context
from src.local_runner.adaptive_maintenance import maintenance_schema, maintenance_decision
from test_plan_scope_v29 import bound

ROOT = Path(__file__).resolve().parent
BATCH = ROOT / 'logs/batch/2026-10-14/11-43-17/adaptive'

def fixture(ticker='GEV',revision=36):
    context = json.loads((BATCH/ticker/'input.json').read_text(encoding='utf-8'))
    context['routing_revision'] = revision
    view = model_context(context)
    token = next(k for k,v in source_catalog(view).items() if v['pointer']=='/slim/price_history')
    return context,view,token

def review(token, floor=98.8):
    return {'entry': {'lower_bound': floor, 'reason': 'Observed reaction boundary; display estimate.',
                      'current_evidence': [token]}, 'ambitious_entry': None}

@pytest.mark.parametrize('revision',[36,37,38])
def test_versioned_contract_and_no_stop_or_extra_routing_guard(revision):
    context,view,_ = fixture(revision=revision)
    assert 'support_validity_review' in report_schema(36)['properties']
    assert 'support_validity_review' not in report_schema(35)['properties']
    assert 'support_validity_review' in maintenance_schema(view)['properties']
    old = {**view, 'routing_revision': 35}
    assert 'support_validity_review' not in maintenance_schema(old)['properties']
    triage=json.loads((BATCH/'GEV/triage.json').read_text(encoding='utf-8'))
    triage['support_validity_review']={'nonsense':True}
    assert maintenance_decision(triage,[],view)=='retain'

def test_revision37_keeps_schema_and_repair_authority_without_confirmation_requirement():
    from src.local_runner.adaptive_repair import repair_context
    _,view,_=fixture(revision=36)
    assert report_schema(37)==report_schema(36)
    assert maintenance_schema({**view,'routing_revision':37})==maintenance_schema(view)
    previous={'decision':'retain'}
    frozen=repair_context({'routing_revision':36},previous,'update_not_allowed_test')
    current=repair_context({'routing_revision':37},previous,'update_not_allowed_test')
    assert current['maintenance_repair']['previous_response']==previous
    assert 'Vigencia37' not in frozen['maintenance_repair']['instruction']
    assert 'sin exigir rebote actual ni test exactamente en el limite' in current['maintenance_repair']['instruction']
    assert current['maintenance_repair']['attempt']==1

def test_original37_cases_accept_prospective_estimates_and_preserve_known_bounds():
    latest=ROOT/'logs/batch/2026-10-14/16-07-07/adaptive'
    paths=list(latest.glob('*/input.json'));assert len(paths)==46
    active=known=unknown=0
    for path in paths:
        frozen=path.read_bytes();ctx=json.loads(frozen)
        response_path=path.parent/'report.response';response_frozen=response_path.read_bytes()
        published_path=path.parent/'publish/output'/path.parent.name/'latest.json'
        published_frozen=published_path.read_bytes()
        original=reference_document(json.loads(published_frozen),verify_projection=True)
        ctx['routing_revision']=37;view=model_context(ctx)
        token=next(k for k,v in source_catalog(view).items() if v['pointer']=='/slim/price_history')
        doc=deepcopy(original);choices={}
        for key,zone in original['plan'].items():
            if not zone['range']:
                choices[key]=None;continue
            active+=1
            if bound_extent(zone):
                known+=1;choices[key]=None
            else:
                unknown+=1
                # Synthetic OFFLINE estimate, not a quote or observed source scalar.
                # Its legitimacy is model judgment; the runner checks binding/sources.
                choices[key]={'lower_bound':zone['range']['lower']*.987654321,
                              'reason':'Prospective fixture estimate derived from supplied history.',
                              'current_evidence':[token]}
        apply_review(doc,original,choices,view)
        for key,zone in original['plan'].items():
            assert {k:v for k,v in doc['plan'][key].items() if k!='support_validity'}=={k:v for k,v in zone.items() if k!='support_validity'}
            if bound_extent(zone):assert doc['plan'][key]['support_validity']==zone['support_validity']
            elif zone['range']:assert bound_extent(doc['plan'][key]) is not None
            else:assert bound_extent(doc['plan'][key]) is None
        for key in ('summary','catalysts','next_event','metadata','reader_presentation'):
            assert doc.get(key)==original.get(key)
        assert path.read_bytes()==frozen and response_path.read_bytes()==response_frozen
        assert published_path.read_bytes()==published_frozen
    assert (active,known,unknown)==(66,19,47)

@pytest.mark.parametrize('value', [False,0,-1,float('nan'),float('inf'),1003,'990'])
def test_invalid_extent_is_not_financial_failure_or_inherited_green(value):
    context,view,token=fixture()
    doc=reference_document(context['reference'],verify_projection=True);original=deepcopy(doc)
    apply_review(doc, original, review(token,value),view)
    assert bound_extent(doc['plan']['entry']) is None
    assert doc['summary']==original['summary']
    assert doc['plan']['entry']['range']==original['plan']['entry']['range']
    assert doc['plan']['entry']['strength']==original['plan']['entry']['strength']

def test_current_source_copy_and_unknown_or_historical_selector_do_not_color():
    context,view,token=fixture();original=reference_document(context['reference'],verify_projection=True)
    doc=deepcopy(original);apply_review(doc,original,review(token,990),view)
    extent=bound_extent(doc['plan']['entry'])
    assert extent['sources']==[source_catalog(view)[token]]
    assert extent['assessed_at']==context['prepared_at']
    for invalid in ('s999999',next(k for k,v in source_catalog(view).items() if v['pointer'].startswith('/reference/'))):
        bad=review(invalid,990);apply_review(doc,original,bad,view)
        assert bound_extent(doc['plan']['entry']) is None


def test_explicitly_unavailable_source_cannot_enable_a_lower_extension():
    context,view,token=fixture();doc=reference_document(context['reference'],verify_projection=True)
    catalog=source_catalog(view);catalog[token]['value']={'status':'unavailable'}
    with patch('src.local_runner.semantic_sources.source_catalog',return_value=catalog):
        apply_review(doc,deepcopy(doc),review(token,990),view)
    assert bound_extent(doc['plan']['entry']) is None

def test_removed_changed_and_promoted_zones_do_not_borrow_extent():
    context,view,token=fixture();doc=reference_document(context['reference'],verify_projection=True)
    apply_review(doc,None,review(token,990),view);original=deepcopy(doc)
    apply_review(doc,original,None,view)
    assert doc['plan']['entry']['support_validity']==original['plan']['entry']['support_validity']
    doc['plan']['entry']['range']={'lower':900,'upper':902}
    apply_review(doc,original,None,view)
    assert bound_extent(doc['plan']['entry']) is None
    doc['plan']['entry']['range']=None
    apply_review(doc,original,review(token,990),view)
    assert 'support_validity' not in doc['plan']['entry']

def test_all_original_retains_keep_finance_dates_anchor_and_frozen_files():
    for path in BATCH.glob('*/input.json'):
        frozen=path.read_bytes();ctx=json.loads(frozen);ctx['routing_revision']=36
        ref=ctx['reference'];before=reference_document(ref,verify_projection=True);v=model_context(ctx)
        token=next(k for k,r in source_catalog(v).items() if r['pointer']=='/slim/price_history')
        zones={k:({'lower_bound':z['range']['lower'], 'reason':'No below-range extension justified.',
                   'current_evidence':[token]} if z['range'] else None) for k,z in before['plan'].items()}
        result,changed=migrate_payload(ref,ref,ctx['sol_reference'],zones,v)
        after=reference_document(result,verify_projection=True)
        assert result['generated_at']==ref['generated_at']
        assert result.get('last_full_report_at')==ref.get('last_full_report_at')
        assert result.get('sol_anchor_sha256')==ref.get('sol_anchor_sha256')
        for k in ('summary','catalysts','next_event','conclusion','metadata','reader_presentation'):
            assert after.get(k)==before.get(k)
        for k,z in after['plan'].items():
            assert {n:x for n,x in z.items() if n!='support_validity'}==before['plan'][k]
        assert path.read_bytes()==frozen
        assert migrate_payload(result,result,ctx['sol_reference'],None,v)==(result,False)

def test_original_full_generates_and_renders_bound_without_changing_finance():
    context,view,token=fixture('ASML')
    response=json.loads((BATCH/'ASML/report.response').read_text(encoding='utf-8'))
    original=full_document(response,view,binding=bound(context,response,'report'))
    response['support_validity_review']=review(token,1682)
    doc=full_document(response,view,binding=bound(context,response,'report'))
    assert doc['plan']['entry']['range']==original['plan']['entry']['range']
    assert doc['plan']['entry']['strength']==original['plan']['entry']['strength']
    assert doc['summary']==original['summary']
    assert '1682' in render_document(doc)
    assert 'sources' not in render_document(doc)
    assert doc['plan']['entry']['support_validity']['lower_bound']==1682


@pytest.mark.parametrize('revision',[36,37,38])
def test_stage_retain_with_active_zone_calls_once_and_stages_bound_without_redating(tmp_path,revision):
    import hashlib
    from src.local_runner import adaptive_stage as stage
    from src.local_runner.adaptive_budget import write_json,read_json
    from src.local_runner.adaptive_context import serialize_model_input
    context,_,_=fixture(revision=revision);policy=json.loads((ROOT/'config/codex_analysis.json').read_text())
    policy['routing_revision']=revision;work=tmp_path/'adaptive/GEV';work.mkdir(parents=True)
    write_json(work/'input.json',context);write_json(work/'policy.json',policy)
    response=json.loads((BATCH/'GEV/triage.response').read_text(encoding='utf-8'));calls=[]
    def call(root,work,symbol,budget,policy,kind,supplied,**kwargs):
        calls.append(kind);assert kind=='triage'
        view=model_context(supplied);view.pop('research_memory',None)
        token=next(k for k,v in source_catalog(view).items() if v['pointer']=='/slim/price_history')
        response['support_validity_review']=review(token,990)
        text=json.dumps(response);(work/'triage.response').write_text(text,encoding='utf-8')
        return dict(text=text,exit_code=0,completed_at=context['prepared_at'],model=policy['triage_model'],usage={},
                    input_sha256=hashlib.sha256(serialize_model_input(view).encode()).hexdigest())
    with patch.object(stage,'model_call',side_effect=call),patch.object(stage,'itv_state',return_value={'due':False}),patch.object(stage,'maintenance_precheck',return_value={'guards':[],'review_flags':[]}),patch.object(stage,'datetime',wraps=datetime) as clock:
        clock.now.return_value=datetime.fromisoformat(context['prepared_at'])
        result=stage.analyze(tmp_path,work,'GEV',tmp_path/'budget.json',False)
    assert calls==['triage'] and result['status']=='retained'
    p=read_json(work/'publish/output/GEV/latest.json')
    assert p['generated_at']==context['reference']['generated_at']
    assert p['plan']['entry_support_validity']['lower_bound']==990
    for ext in ['md','html','json']:assert (work/('publish/output/GEV/latest.'+ext)).exists()
