"""Offline coverage for the versioned volume methodology; no model calls."""
from copy import deepcopy
from contextlib import ExitStack
from datetime import datetime
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from src.local_runner.adaptive_context import model_context, unpack_model_context
from src.local_runner.adaptive_maintenance import maintenance_schema
from src.local_runner import adaptive_stage as stage
from src.local_runner.maintenance_change import validate_change
from src.local_runner.semantic_report import reference_document, _validate_level
from src.local_runner.semantic_sources import source_catalog, normalize_plan
from src.local_runner.volume_arithmetic import calculate, validate_rubric_change
from src.local_runner.volume_rubric import volume_ceiling
ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'logs/batch/2026-10-13/12-41-28/adaptive'


def capture(ticker='HIMS', revision=34):
    folder = BATCH / ticker
    context = json.loads((folder/'input.json').read_text(encoding='utf-8'))
    frozen = unpack_model_context(json.loads((folder/'report.input.json').read_text(encoding='utf-8')))
    for key in ('guards', 'itv', 'review_flags'):
        context[key] = frozen[key]
    context['routing_revision'] = revision
    return context, json.loads((folder/'report.response').read_text(encoding='utf-8'))


def migration():
    context, payload = capture()
    context = model_context(context)
    key = 'ambitious_entry'
    prior = reference_document(context['reference'], verify_projection=True)['plan'][key]
    block = payload['plan'][key]
    catalog = source_catalog(context)
    source = block['volume_calculation']['reaction_source']
    evidence = catalog[source]['value']['evidence']
    calc = calculate(evidence['volume_profile'], evidence['historical_reaction'], block['range'], context['slim']['as_of'], revision=34)
    block['strength']['components']['volumen'] = calc['expected']
    own = next(h for h,r in catalog.items() if r['pointer']=='/reference/semantic_data/plan/'+key)
    block['change_review'] = dict(basis='rubric_change', previous_evidence=[own], current_evidence=[source], explanation='Same measured backing; node distance affects proximity only under34.')
    normalized, issues = normalize_plan({key:block}, {key:prior}, context)
    assert not issues
    return context, normalized[key], prior


@pytest.mark.parametrize('ticker,key,before,after', [('HIMS','ambitious_entry',12,13),('IONQ','ambitious_entry',12,14),('CCJ','entry',15,17)])
def test_exact_captures_change_only_the_ceiling(ticker,key,before,after):
    context,payload=capture(ticker)
    block=payload['plan'][key]
    evidence=source_catalog(model_context(context))[block['volume_calculation']['reaction_source']]['value']['evidence']
    args=(evidence['volume_profile'],evidence['historical_reaction'],block['range'],context['slim']['as_of'])
    old,new=calculate(*args,revision=33),calculate(*args,revision=34)
    assert old['expected']==before and new['expected']==after
    assert old['parts']==new['parts'] and new['expected']==sum(new['parts'].values())
    assert new['rubric_revision']==34 and 'rubric_revision' not in old


def test_historical_quality_and_daily_profile_guards_remain():
    context,payload=capture()
    block=payload['plan']['ambitious_entry']
    evidence=deepcopy(source_catalog(model_context(context))[block['volume_calculation']['reaction_source']]['value']['evidence'])
    profile,reaction=evidence['volume_profile'],evidence['historical_reaction']
    reaction.update(test_count=2,defense_count=2,defense_rate_pct=100)
    result=calculate(profile,reaction,block['range'],context['slim']['as_of'],revision=34)
    assert result['parts']['defense_rate']==2 and result['ceiling']==12
    reaction.update(test_count=10,defense_count=8,defense_rate_pct=80,last_test_date='2026-07-01',median_rebound_5d_pct=20,last_test_rebound_5d_pct=0)
    result=calculate(profile,reaction,block['range'],context['slim']['as_of'],revision=34)
    assert result['parts']['recency']==0 and result['parts']['magnitude']==2 and result['ceiling']==15
    profile['nearest_level']=(block['range']['lower']+block['range']['upper'])/2
    assert calculate(profile,reaction,block['range'],context['slim']['as_of'],revision=34)['parts']['proximity']==3


def test_unavailable_evidence_does_not_earn_free_points():
    assert calculate({'status':'unavailable'},{'status':'available'},{'lower':10,'upper':10},'2026-10-13T12:00:00Z',revision=34) is None
    assert volume_ceiling({},'2026-10-13T12:00:00Z',revision=34)['ceiling_from_this_record']==4


def test_guidance_retains_frozen_formula_and_matches_new_gate():
    context,payload=capture()
    evidence=source_catalog(model_context(context))[payload['plan']['ambitious_entry']['volume_calculation']['reaction_source']]['value']['evidence']
    old=volume_ceiling(evidence,context['slim']['as_of'],revision=33)
    new=volume_ceiling(evidence,context['slim']['as_of'],revision=34)
    assert old['ceiling_from_this_record']==12 and new['ceiling_from_this_record']==18
    assert new['historical_sample_for_above_12'] and 'both_families_for_above_12' not in new


def test_method_migration_passes_shared_financial_checks():
    context,block,prior=migration()
    original=deepcopy((context['reference'],context['sol_reference']))
    validate_change(block,'ambitious_entry',context)
    _validate_level(block,'ambitious_entry',context,prior,maintenance=True)
    assert block['volume_calculation_audit']['expected']==13
    assert sum(block['strength']['components'].values())==70
    assert block['range']==prior['range'] and (context['reference'],context['sol_reference'])==original


@pytest.mark.parametrize('mutation,error',[('range','same_active_zone'),('structure','other_component_changed'),('volume','not_exact_method_delta'),('no_calculation','explicit_calculation'),('no_previous','prior_decision'),('no_current','selected_current_sources'),('old_revision','wrong_revision_or_level')])
def test_migration_authority_cannot_hide_other_changes(mutation,error):
    context,block,_=migration()
    if mutation=='range':block['range']['lower']-=0.01
    elif mutation=='structure':block['strength']['components']['estructura']-=1
    elif mutation=='volume':block['strength']['components']['volumen']+=1
    elif mutation=='no_calculation':block['volume_calculation']=None
    elif mutation=='no_previous':block['change_review']['previous_evidence']=[]
    elif mutation=='no_current':block['change_review']['current_evidence']=[]
    else:context['routing_revision']=33
    with pytest.raises(ValueError,match=error):validate_rubric_change(block,'ambitious_entry',context)


def test_method_migration_cannot_repeat():
    context,block,prior=migration()
    prior['volume_calculation_audit']={'rubric_revision':34}
    with patch('src.local_runner.semantic_report.reference_document',return_value={'plan':{'ambitious_entry':prior}}):
        with pytest.raises(ValueError,match='already_migrated'):validate_rubric_change(block,'ambitious_entry',context)


def test_new_basis_is_scoped_to_level_schema34():
    context,_=capture()
    update=maintenance_schema(model_context(context))['properties']['update']['anyOf'][0]
    level=update['properties']['plan']['properties']['entry']['anyOf'][0]
    assert 'rubric_change' in level['properties']['change_review']['properties']['basis']['enum']
    assert 'rubric_change' not in update['properties']['public_note']['anyOf'][0]['properties']['review']['properties']['basis']['enum']
    context['routing_revision']=33
    old=maintenance_schema(model_context(context))['properties']['update']['anyOf'][0]
    assert 'rubric_change' not in old['properties']['plan']['properties']['entry']['anyOf'][0]['properties']['change_review']['properties']['basis']['enum']


def test_preparation_versions_both_roles_and_preserves_frozen_work(tmp_path):
    context,_=capture()
    policy=json.loads((ROOT/'config/codex_analysis.json').read_text(encoding='utf-8'));policy['routing_revision']=34
    work=tmp_path/'HIMS';work.mkdir()
    with ExitStack() as stack:
        clock=stack.enter_context(patch.object(stage,'datetime',wraps=datetime));clock.now.return_value=datetime.fromisoformat(context['prepared_at'])
        for name,value in [('load_policy',policy),('load_reference_payload',context['sol_reference']),('load_current_report',context['reference']),('load_research',None)]:stack.enter_context(patch.object(stage,name,return_value=value))
        for name,value in [('_fetch_slim',context['slim']),('_load_analyst_quality',{}),('load_compact_analyst_summary',{}),('load_recent_analyst_actions',context['analyst_actions']),('load_recent_news',context['news']),('_load_system_prompt','legacy')]:stack.enter_context(patch.object(stage.one,name,return_value=value))
        stack.enter_context(patch.object(stage,'call_codex',side_effect=AssertionError('NO MODEL')))
        stage.prepare(ROOT,work,'HIMS',context['owned'],context['tier'])
        for name in ('instructions.md','triage_instructions.md'):
            text=(work/name).read_text(encoding='utf-8')
            assert 'VOLUME RUBRIC34' in text and 'revisión34' in text and 'CATALYST EDITORIAL33' in text
            assert 'Sin evidencia de ambas familias —un POC/HVN' not in text
        frozen={p.name:p.read_bytes() for p in work.iterdir()}
        policy['routing_revision']=33
        stage.prepare(ROOT,work,'HIMS',context['owned'],context['tier'])
        assert frozen=={p.name:p.read_bytes() for p in work.iterdir()}
        oldwork=tmp_path/'old33';oldwork.mkdir()
        stage.prepare(ROOT,oldwork,'HIMS',context['owned'],context['tier'])
        oldtext=(oldwork/'instructions.md').read_text(encoding='utf-8')
        assert 'VOLUME RUBRIC34' not in oldtext and 'Sin evidencia de ambas familias —un POC/HVN' in oldtext


def test_full34_and_maintenance34_use_the_same_exact_arithmetic():
    import hashlib
    from src.local_runner.adaptive_context import serialize_model_input
    from src.local_runner.semantic_binding import bind_response
    from src.local_runner.semantic_report import full_document, maintenance_document
    context, payload = capture()
    view = model_context(context)
    payload['plan']['ambitious_entry']['strength']['components']['volumen'] = 13
    receipt = dict(text=json.dumps(payload), exit_code=0, input_sha256=hashlib.sha256(serialize_model_input(view).encode()).hexdigest())
    full = full_document(payload, view, binding=bind_response(context, receipt, 'report'))
    assert full['plan']['ambitious_entry']['volume_calculation_audit']['expected'] == 13
    bad = deepcopy(payload)
    bad['plan']['ambitious_entry']['strength']['components']['volumen'] = 12
    receipt['text'] = json.dumps(bad)
    with pytest.raises(ValueError, match='expected=13, received=12'):
        full_document(bad, view, binding=bind_response(context, receipt, 'report'))
    context, block, prior = migration()
    # Build a complete current schema around a real recorded maintenance verdict.
    response = json.loads((ROOT/'logs/batch/2026-10-13/09-03-29/adaptive/HIMS/triage.response').read_text(encoding='utf-8'))
    raw_context, _ = capture()
    _, full_payload = capture()
    raw = full_payload['plan']['ambitious_entry']
    raw['strength']['components']['volumen'] = 13
    raw['change_review'] = deepcopy(block['change_review'])
    raw['change_review'].pop('resolved_evidence', None)
    response.update(decision='update', reader_review=None,
        update=dict(setup_score=None, setup_reason=None,
                    plan=dict(entry=None, ambitious_entry=raw, resistance=None),
                    conclusion=None, change_review=dict(setup=None, conclusion=None, plan_explanation=None),
                    plan_explanation=None, public_note=None))
    current_view = model_context(raw_context)
    triage_view = deepcopy(current_view)
    triage_view.pop("research_memory", None)
    receipt = dict(text=json.dumps(response), exit_code=0,
        input_sha256=hashlib.sha256(serialize_model_input(triage_view).encode()).hexdigest())
    maintenance = maintenance_document(response, current_view, binding=bind_response(raw_context, receipt, 'triage'))
    assert maintenance['plan']['ambitious_entry']['volume_calculation_audit']['expected'] == 13
    assert maintenance['plan']['ambitious_entry']['range'] == prior['range']
    assert maintenance['summary'] == reference_document(current_view['reference'], verify_projection=True)['summary']


def test_support_history_cannot_be_used_as_resistance_rejections34():
    context, block, prior = migration()
    with pytest.raises(ValueError, match='reaction_direction_not_applicable'):
        _validate_level(block, 'resistance', context, prior, maintenance=False)


def test_repair34_explains_method_permission_without_changing_frozen33():
    from src.local_runner.adaptive_repair import repair_context
    context, _ = capture()
    instruction = repair_context(context, {}, 'update_not_allowed_volume_arithmetic')['maintenance_repair']['instruction']
    assert 'Rubrica34' in instruction and 'rubric_change' in instruction
    context['routing_revision'] = 33
    assert 'Rubrica34' not in repair_context(context, {}, 'update_not_allowed_volume_arithmetic')['maintenance_repair']['instruction']


@pytest.mark.parametrize('revision,expected', [(33,15),(34,17)])
def test_explicit_manual_builder_uses_its_frozen_rubric(revision,expected):
    from src.local_runner.correct_volume_arithmetic import build
    context,payload=capture('CCJ',revision=revision)
    selector=payload['plan']['entry']['volume_calculation']['reaction_source']
    # Observe the real arithmetic inside the pure builder, without publishing.
    observed=[]
    def audited_calculation(*args,**kwargs):
        value=calculate(*args,**kwargs)
        observed.append(value['expected'])
        raise RuntimeError('observed_calculation_only')
    with patch('src.local_runner.correct_volume_arithmetic.calculate',side_effect=audited_calculation):
        with pytest.raises(RuntimeError,match='observed_calculation_only'):
            build(context['reference'],context['sol_reference'],context,selector,datetime.fromisoformat(context['prepared_at']))
    assert observed==[expected]


def test_current_loader_preserves_frozen34_and_rejects_future(tmp_path):
    from src.local_runner.adaptive_policy import load_policy, require_activation
    active=load_policy(ROOT)
    # Deployment activation is not a property of the frozen volume34 formula.
    require_activation(active)
    assert active['triage_model']=='gpt-6-luna' and active['report_model']=='gpt-6.1-sol'
    assert active['triage_effort']==active['report_effort']=='high'
    assert active['max_model_parallel']==6
    assert active['priority_itv_sessions']==active['watchlist_itv_sessions']==5
    folder=tmp_path/'config';folder.mkdir()
    for revision in (33,34,35,36,37,38,39,40,41,42):
        candidate={**active,'routing_revision':revision}
        if revision < 41:
            candidate.pop('volume_calculation_guidance', None)
        if revision < 40:
            candidate['technical_archive_enabled'] = False
        (folder/'codex_analysis.json').write_text(json.dumps(candidate),encoding='utf-8')
        if revision==42:
            with pytest.raises(ValueError,match='unsupported_routing_revision'):load_policy(tmp_path)
        else:assert load_policy(tmp_path)==candidate
