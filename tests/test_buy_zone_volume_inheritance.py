"""Offline regressions; no model, publication or original artifact edits."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from src.local_runner.adaptive_context import model_context
from src.local_runner.semantic_binding import bind_response
from src.local_runner.semantic_report import full_document, reference_document, _validate_level
from src.local_runner.semantic_sources import normalize_plan, resolve_source
from src.local_runner.volume_arithmetic import validate, _inherited_buy_volume

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'logs/batch/2026-10-13/12-41-28/adaptive'

def load(folder=RUN/'CRWV'):
    context = json.loads((folder/'input.json').read_text(encoding='utf-8'))
    # analyze adds routing state after preparation: use original recorded values.
    # bind_response below verifies the real receipt, never a fabricated digest.
    call_input = json.loads((folder/'report.input.json').read_text(encoding='utf-8'))
    for key in ('guards', 'review_flags', 'itv'):
        context[key] = call_input[key]
    text = (folder/'report.response').read_text(encoding='utf-8')
    receipt = json.loads((folder/'report.receipt.json').read_text(encoding='utf-8'))
    receipt['text'] = text
    return context, json.loads(text), receipt

def normalized():
    context, response, _ = load()
    view = model_context(context)
    previous = reference_document(view['reference'], verify_projection=True)['plan']
    plan, issues = normalize_plan(response['plan'], previous, view)
    assert not issues
    return view, plan, previous

@pytest.mark.parametrize('ticker', ['CRWV', 'MU'])
def test_original_receipt_reproduces_failure_then_passes_unchanged(ticker):
    context, response, receipt = load(RUN/ticker)
    frozen = deepcopy((context, response, receipt))
    binding = bind_response(context, receipt, 'report')
    with patch('src.local_runner.volume_arithmetic._inherited_buy_volume', return_value=False):
        with pytest.raises(ValueError, match='entry: select_profile_and_reaction_sources'):
            full_document(response, model_context(context), binding=binding)
    doc = full_document(response, model_context(context), binding=binding)
    assert (context, response, receipt) == frozen
    for key, level in response['plan'].items():
        for field in ('range', 'reason', 'strength', 'volume_calculation'):
            assert doc['plan'][key][field] == level[field]
        assert doc['plan'][key]['resolved_facts']
    for field in ('summary', 'next_event', 'conclusion'):
        assert doc[field] == response[field]
    assert doc['catalysts'] == sorted(response['catalysts'], key=lambda r: r['date'] or '', reverse=True)
    assert doc['plan']['entry']['continuity']['transition'] == 'reprioritize'
    assert doc['plan']['entry']['strength']['components']['volumen'] == (10 if ticker == 'CRWV' else 16)
    assert 'volume_calculation_audit' not in doc['plan']['entry']

@pytest.mark.parametrize('maintenance', [False, True])
def test_shared_level_validator_for_both_engines(maintenance):
    context, plan, previous = normalized()
    _validate_level(plan['entry'], 'entry', context, previous['entry'], maintenance=maintenance)
    assert plan['entry']['range'] == previous['ambitious_entry']['range']

@pytest.mark.parametrize('key', ['entry', 'ambitious_entry'])
def test_promotion_and_demotion(key):
    context, plan, previous = normalized()
    other = 'ambitious_entry' if key == 'entry' else 'entry'
    pointer = '/reference/semantic_data/plan/' + other
    level = deepcopy(plan['entry'])
    prior = resolve_source(context, pointer)
    level.update(range=deepcopy(prior['range']), strength=deepcopy(prior['strength']))
    level['evidence'] = [p for p in level['evidence'] if not p.startswith('/reference/semantic_data/')]
    level['evidence'].append(pointer)
    original = deepcopy(level)
    assert _inherited_buy_volume(level, key, context)
    validate(level, key, context, previous[key])
    assert level == original

@pytest.mark.parametrize('change', ['range', 'volume', 'missing', 'anchor', 'descendant'])
def test_cannot_hide_new_or_unproven_calculation(change):
    context, plan, previous = normalized()
    level = plan['entry']; pointer = '/reference/semantic_data/plan/ambitious_entry'
    if change == 'range': level['range']['lower'] += .01
    elif change == 'volume': level['strength']['components']['volumen'] += 1
    else:
        level['evidence'].remove(pointer)
        if change == 'anchor': level['evidence'].append('/sol_reference/semantic_data/plan/ambitious_entry')
        if change == 'descendant': level['evidence'].append(pointer + '/strength/components/volumen')
    with pytest.raises(ValueError, match='select_profile_and_reaction_sources'):
        validate(level, 'entry', context, previous['entry'])

def test_explicit_calculation_still_checked():
    context, plan, previous = normalized()
    plan['entry']['volume_calculation'] = dict(profile_source='unknown', reaction_source='unknown')
    with pytest.raises(ValueError, match='unselected_profile_source'):
        validate(plan['entry'], 'entry', context, previous['entry'])

def test_resistance_and_null_are_not_buying_inheritance():
    context, plan, _ = normalized()
    assert not _inherited_buy_volume(plan['entry'], 'resistance', context)
    plan['entry']['evidence'] = ['/reference/semantic_data/plan/resistance']
    assert not _inherited_buy_volume(plan['entry'], 'entry', context)
    plan['entry']['range'] = None
    assert not _inherited_buy_volume(plan['entry'], 'entry', context)

def test_tampered_current_is_not_authority():
    context, plan, previous = normalized()
    context['reference']['analysis_markdown'] += '\nUNAUTHENTICATED'
    with pytest.raises(ValueError):
        validate(plan['entry'], 'entry', context, previous['entry'])

@pytest.mark.parametrize('revision', [25, 26, 27])
def test_old_contracts_unchanged(revision):
    context, plan, previous = normalized()
    context['routing_revision'] = revision
    with pytest.raises(ValueError, match='select_profile_and_reaction_sources'):
        validate(plan['entry'], 'entry', context, previous['entry'])

@pytest.mark.parametrize('batch', ['11-06-58', '12-41-28'])
def test_successful_originals_unchanged_including_sources_dates_and_text(batch):
    root = ROOT/'logs/batch/2026-10-13'/batch/'adaptive'
    published = sorted(root.glob('*/publish/output/*/latest.json'))
    assert published
    for report in published:
        context, response, receipt = load(root/report.parent.name)
        frozen = deepcopy((context, response, receipt))
        binding = bind_response(context, receipt, 'report')
        view = model_context(context)
        with patch('src.local_runner.volume_arithmetic._inherited_buy_volume', return_value=False):
            old = full_document(response, view, binding=binding)
        new = full_document(response, view, binding=binding)
        assert new == old, report.parent.name
        assert (context, response, receipt) == frozen
