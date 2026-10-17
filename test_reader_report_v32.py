"""Offline reader projection, memory and natural publication-path regressions."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import sys
import pytest

from src.local_runner import adaptive_stage as stage
from src.local_runner.reader_report import catalog, event_key, apply_selection, full_selection, migrate_payload
from src.local_runner.semantic_report import (reference_document, render_document, full_document,
    publication_fields, report_schema, check_schema)
from src.local_runner.adaptive_context import model_context, serialize_model_input, unpack_model_context
from src.local_runner.adaptive_maintenance import maintenance_schema, maintenance_decision
from src.local_runner.semantic_binding import bind_response
from src.local_runner.review_memory import read_memory
import test_plan_scope_v29 as old_tests

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT/'logs/batch/2026-10-13/12-41-28/adaptive/MRVL'

def original():
    return json.loads((SOURCE/'publish/output/MRVL/latest.json').read_text(encoding='utf-8'))

def payload32():
    ref = original()
    doc = reference_document(ref, verify_projection=True)
    doc['metadata']['reader_format_revision'] = 32
    return ref, doc

def test_only_reader_sections_removed_not_financial_data():
    ref, doc = payload32(); before = deepcopy(doc)
    text = render_document(doc)
    assert '## Resumen' in text and doc['summary']['narrative'] in text
    for absent in ('Motivo de Tesis:', 'Tesis:', 'Setup:', 'Motivo de Setup:',
                   '## 4)', 'Conclusión sencilla', 'Precio en la captura:', 'Desglose de', 'Factores de'):
        assert absent not in text
    for key in ('entry', 'ambitious_entry', 'resistance'):
        assert doc['plan'][key]['reason'] in text
    assert doc == before
    fields = publication_fields(doc, text, ref, datetime.fromisoformat(ref['generated_at']))
    assert fields['decision'] == ref['decision']
    assert fields['plan'] == ref['plan']
    assert fields['catalysts'] == ref['catalysts']
    sys.path.insert(0, str(ROOT/'gcp_services/stock_controller/src'))
    from stock_analysis.analysis_worker.reports import parse_analysis_report
    new = {**ref, **fields, 'analysis_markdown': text}
    assert parse_analysis_report('MRVL', new, report_url_template='{ticker}') == parse_analysis_report('MRVL', ref, report_url_template='{ticker}')

def test_visibility_is_semantic_selection_not_age_or_score_cutoff():
    _, doc = payload32()
    doc['catalysts'] = [dict(date='2020-01-01', title='Old debt still matters', impact=-8,
                           description='Unresolved obligation', show_in_report=True),
                        dict(date='2020-01-01', title='Old minor background', impact=5,
                             description='Absorbed story', show_in_report=False),
                        dict(date='2026-10-13', title='Recent trivial item', impact=5,
                             description='Not decision relevant', show_in_report=False)]
    doc['next_event']['show_in_report'] = False
    full_selection(doc); text = render_document(doc)
    assert 'Old debt still matters' in text
    assert 'Old minor background' not in text and 'Recent trivial item' not in text
    assert '## Próximo evento' not in text
    assert len(doc['catalysts']) == 3 and doc['next_event'] is not None
    assert 'show_in_report' not in json.dumps(doc['catalysts'])

def test_reorder_cannot_hide_a_different_fact_and_changed_event_resurfaces():
    _, doc = payload32(); base = deepcopy(doc)
    hidden = doc['catalysts'][0]; event = doc['next_event']
    apply_selection(doc, base, dict(hidden_catalysts=['c1'], hide_next_event=True))
    doc['catalysts'].reverse()
    assert hidden['title'] not in render_document(doc)
    doc['next_event']['date'] = '2027-01-01'
    assert '## Próximo evento clave' in render_document(doc)
    apply_selection(doc, base, dict(hidden_catalysts=[], hide_next_event=False))
    assert hidden['title'] in render_document(doc)

@pytest.mark.parametrize('review', [{}, {'hidden_catalysts':['c999'],'hide_next_event':False},
    {'hidden_catalysts':['c1'],'hide_next_event':'yes'}, {'hidden_catalysts':[None],'hide_next_event':False}])
def test_bad_display_selectors_do_not_fail_finance_or_hide_news(review):
    _, doc = payload32(); base = deepcopy(doc)
    apply_selection(doc, base, review)
    assert doc['reader_presentation']['warning']
    assert all(e['title'] in render_document(doc) for e in doc['catalysts'])

def test_retained_migration_keeps_dates_values_memory_and_all_news_in_next_input():
    ref = original(); before = deepcopy(ref)
    result, changed = migrate_payload(ref, ref, ref, dict(hidden_catalysts=['c1'], hide_next_event=False))
    assert changed and ref == before
    old = reference_document(ref, verify_projection=True)
    new = reference_document(result, verify_projection=True)
    for key in ('summary','plan','catalysts','next_event','conclusion','text_provenance'):
        assert new.get(key) == old.get(key)
    assert result['generated_at'] == ref['generated_at']
    assert result.get('last_full_report_at') == ref.get('last_full_report_at')
    assert read_memory(result, ref) == read_memory(ref, ref)
    again, changed = migrate_payload(result, result, ref, None)
    assert not changed and again == result
    context = json.loads((SOURCE/'input.json').read_text(encoding='utf-8'))
    context.update(reference=result, sol_reference=ref, routing_revision=32)
    wire = unpack_model_context(json.loads(serialize_model_input(model_context(context))))
    assert wire['reference']['semantic_data']['catalysts'] == old['catalysts']
    assert wire['reader_catalog']['c1']['currently_visible'] is False

def test_full32_binds_finance_and_keeps_hidden_catalysts():
    context = json.loads((SOURCE/'input.json').read_text(encoding='utf-8')); context['routing_revision']=32
    response = json.loads((SOURCE/'report.response').read_text(encoding='utf-8'))
    for row in response['catalysts']: row['show_in_report'] = False
    response['catalysts'][0]['show_in_report'] = True
    response['next_event']['show_in_report'] = False
    before = deepcopy(response)
    check_schema(response, report_schema(32))
    doc = full_document(response, model_context(context), binding=old_tests.bound(context,response,'report'))
    assert response == before
    assert len(doc['catalysts']) == len(response['catalysts'])
    assert doc['summary'] == response['summary']
    assert len(doc['reader_presentation']['hidden_catalysts']) == len(doc['catalysts'])-1
    assert doc['next_event'] is not None
    assert '## Próximo evento' not in render_document(doc)
    with pytest.raises(ValueError):
        changed = deepcopy(response); changed['summary']['setup_score']=8
        full_document(changed,model_context(context),binding=old_tests.bound(context,response,'report'))

def test_reader_review_does_not_bypass_risk_or_create_financial_update():
    context = old_tests.data(); context['routing_revision']=32
    response = json.loads((old_tests.BATCH/'CRDO/triage.response').read_text(encoding='utf-8'))
    response['reader_review'] = dict(hidden_catalysts=['c1'], hide_next_event=False)
    assert maintenance_decision(response, [], model_context(context)) == 'retain'
    for flag in response['risk']:
        bad=deepcopy(response); bad['risk'][flag]=True
        assert maintenance_decision(bad,[],model_context(context))=='escalate'
    response['reader_review']={'malformed':'presentation only'}
    assert maintenance_decision(response,[],model_context(context))=='retain'
    assert 'reader_review' not in maintenance_schema({'routing_revision':31})['properties']
    assert report_schema(31) == report_schema(30)

@pytest.mark.parametrize('flag', [None, 'false', 0])
def test_full_bad_editorial_flag_shows_fact_instead_of_failing_ticker(flag):
    context=json.loads((SOURCE/'input.json').read_text(encoding='utf-8'));context['routing_revision']=32
    response=json.loads((SOURCE/'report.response').read_text(encoding='utf-8'))
    response['catalysts'][0]['show_in_report']=flag
    doc=full_document(response,model_context(context),binding=old_tests.bound(context,response,'report'))
    assert not doc['reader_presentation']['hidden_catalysts']
    assert all(e['title'] in render_document(doc) for e in doc['catalysts'])

def test_update_path_keeps_protected_narrative_and_finance():
    from src.local_runner.semantic_report import maintenance_document
    context,response=old_tests.sofi_update();context['routing_revision']=32
    response['reader_review']=dict(hidden_catalysts=['c1'],hide_next_event=False)
    doc=maintenance_document(response,model_context(context),binding=old_tests.bound(context,response))
    prior=reference_document(context['reference'],verify_projection=True)
    apply_selection(doc,prior,response['reader_review'])
    assert doc['summary']['narrative']==prior['summary']['narrative']
    assert doc['catalysts']==prior['catalysts']
    assert doc['next_event']==prior['next_event']
    assert prior['catalysts'][0]['title'] not in render_document(doc)
    for key,block in response['update']['plan'].items():
        if block:assert doc['plan'][key]['range']==block['range']

def test_prepare32_freezes_both_roles_and_does_not_rewrite31(tmp_path):
    from contextlib import ExitStack
    context=old_tests.data();policy=json.loads((ROOT/'config/codex_analysis.json').read_text())
    policy['routing_revision']=32; work=tmp_path/'CRDO';work.mkdir()
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
            assert 'READER REPORT32' in (work/name).read_text(encoding='utf-8')
        frozen={p.name:p.read_bytes() for p in work.iterdir()}
        policy['routing_revision']=31
        stage.prepare(ROOT,work,'CRDO',context['owned'],context['tier'])
        assert frozen=={p.name:p.read_bytes() for p in work.iterdir()}
    # Existing report31 has exactly the same renderer behavior.
    ref=original();doc=reference_document(ref,verify_projection=True)
    assert render_document(doc)==ref['analysis_markdown']

def test_retain_pipeline_stages_formats_without_extra_model_or_itv_reset(tmp_path):
    context=old_tests.data();context['routing_revision']=32
    policy=json.loads((ROOT/'config/codex_analysis.json').read_text());policy['routing_revision']=32
    work=tmp_path/'adaptive/CRDO';work.mkdir(parents=True)
    from src.local_runner.adaptive_budget import write_json,read_json
    write_json(work/'input.json',context);write_json(work/'policy.json',policy)
    response=json.loads((old_tests.BATCH/'CRDO/triage.response').read_text(encoding='utf-8'))
    response['reader_review']=dict(hidden_catalysts=['c1'],hide_next_event=True)
    calls=[]
    def call(root,work,symbol,budget,policy,kind,supplied,**kwargs):
        calls.append(kind); assert kind=='triage'
        view=model_context(supplied);view.pop('research_memory',None)
        text=json.dumps(response);(work/'triage.response').write_text(text,encoding='utf-8')
        return dict(text=text,exit_code=0,completed_at=context['prepared_at'],
                    input_sha256=hashlib.sha256(serialize_model_input(view).encode()).hexdigest(),
                    model=policy['triage_model'],usage={})
    with patch.object(stage,'model_call',side_effect=call), patch.object(stage,'itv_state',return_value={'due':False,'age_sessions':1}), patch.object(stage,'maintenance_precheck',return_value={'guards':[],'review_flags':[]}):
        with patch.object(stage,'datetime',wraps=datetime) as clock:
            clock.now.return_value=datetime.fromisoformat(context['prepared_at'])
            review=stage.analyze(tmp_path,work,'CRDO',tmp_path/'budget.json',False)
    assert calls==['triage'] and review['status']=='retained' and review['presentation_changed']
    output=work/'publish/output/CRDO'
    payload=read_json(output/'latest.json'); md=(output/'latest.md').read_text(encoding='utf-8')
    html=(output/'latest.html').read_text(encoding='utf-8')
    assert md==payload['analysis_markdown'] and 'Motivo de Tesis:' not in md
    assert 'Motivo de Tesis:' not in html and 'Conclusión sencilla' not in html
    assert payload['generated_at']==context['reference']['generated_at']
    read_memory(payload,context['sol_reference'])
    with patch.object(stage,'_read_json_gcs',side_effect=[context['reference'],context['sol_reference']]), patch.object(stage.one,'_upload') as upload, patch.object(stage,'_copy_json'), patch.object(stage,'save_reference_payload') as anchor:
        stage._publish_locked(tmp_path,work,'CRDO')
    upload.assert_called_once();anchor.assert_not_called()
