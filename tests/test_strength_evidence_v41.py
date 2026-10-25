"""Evidence41 changes model guidance, not scores/authority by deterministic fiat.

These offline replays do not test a model's financial judgment. They verify that
the new revision keeps the existing validators, numerical outputs and immutable
originals usable without a prose gate or an automatic score adjustment.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from src.local_runner.adaptive_context import model_context, serialize_model_input
from src.local_runner.adaptive_maintenance import maintenance_decision
from src.local_runner.adaptive_news_research import attach_news_research
from src.local_runner.semantic_binding import bind_response
from src.local_runner.semantic_report import maintenance_document, reference_document


ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'logs/batch/2026-10-18/09-08-40/adaptive'


def original(ticker):
    paths = [BATCH / ticker / name for name in (
        'input.json', 'triage.response', 'review.json', 'triage.receipt.json')]
    if any(not path.is_file() for path in paths):
        pytest.skip('Frozen local corpus unavailable')
    blobs = [path.read_bytes() for path in paths]
    context, response, review, receipt = [json.loads(blob) for blob in blobs]
    for key in ('guards', 'itv', 'review_flags'):
        context[key] = deepcopy(review[key])
    receipt['text'] = blobs[1].decode('utf-8')
    return paths, blobs, context, response, receipt


def prepared(context, payload, receipt, ticker, revision):
    context = deepcopy(context)
    context['routing_revision'] = revision
    receipt = deepcopy(receipt)
    if revision != 40:
        # A synthetic in-memory receipt permits the paired revision comparison;
        # the revision40 side must authenticate its ACTUAL frozen call receipt.
        receipt_view = model_context(context)
        receipt_view.pop('research_memory', None)
        receipt['input_sha256'] = hashlib.sha256(
            serialize_model_input(receipt_view).encode()).hexdigest()
    binding = bind_response(context, receipt, 'triage')
    attach_news_research(context, BATCH / ticker, 'triage', receipt, payload)
    return model_context(context), binding


def replay(context, payload, receipt, ticker, revision):
    view, binding = prepared(context, payload, receipt, ticker, revision)
    return maintenance_document(deepcopy(payload), view, binding=binding)


def finance(document):
    return {
        'plan': {key: {field: block.get(field) for field in ('range', 'strength', 'reason')}
                 for key, block in document['plan'].items()},
        'summary': document.get('summary'),
        'thesis_state': document.get('thesis_state'),
    }


def test_frozen_strength31_overlay_bytes_remain_original():
    assert hashlib.sha256((ROOT / 'prompts/strength_evidence_v31.md').read_bytes()).hexdigest() == (
        '62e8e966139fa4fa514ceb20d07e20b0f5e561c7f069d63e068d8fa5d115afbe')


@pytest.mark.parametrize('ticker', ['APP', 'CAT', 'COIN', 'IONQ', 'IREN', 'QBTS', 'SPCX', 'TSLA'])
def test_original_updates_keep_exact_finance_without_automatic_41_rescoring(ticker):
    paths, blobs, context, response, receipt = original(ticker)
    original_objects = deepcopy((context, response))
    assert response['decision'] == 'update'
    prior = replay(context, response, receipt, ticker, 40)
    new = replay(context, response, receipt, ticker, 41)
    assert finance(new) == finance(prior)
    assert (context, response) == original_objects
    assert [path.read_bytes() for path in paths] == blobs


@pytest.mark.parametrize('ticker', ['MP', 'NVDA', 'KTOS', 'CRWV', 'RKLB'])
def test_frozen_retains_are_not_rerouted_by_low_scores_or_legacy_factor_text(ticker):
    paths, blobs, context, response, receipt = original(ticker)
    original_objects = deepcopy((context, response))
    assert response['decision'] == 'retain'
    expected = reference_document(context['reference'], verify_projection=True)
    for revision in (40, 41):
        view, _ = prepared(context, response, receipt, ticker, revision)
        assert maintenance_decision(response, context['guards'], view) == 'retain'
        assert finance(reference_document(view['reference'], verify_projection=True)) == finance(expected)
    assert (context, response) == original_objects
    assert [path.read_bytes() for path in paths] == blobs
