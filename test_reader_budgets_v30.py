"""Offline checks only: no models, remote publication or live batch mutation."""
import hashlib
import json
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from src.local_runner import adaptive_stage as stage
from src.local_runner.adaptive_context import model_context, serialize_model_input
from src.local_runner.adaptive_policy import load_policy
from src.local_runner.adaptive_repair import repair_context
from src.local_runner.semantic_binding import bind_response
from src.local_runner.semantic_report import (
    check_schema, full_document, render_document, report_schema, update_schema,
)

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT / 'logs/batch/2026-10-13/11-06-58/adaptive/MRVL'


def fixture():
    return json.loads((ORIGINAL / 'input.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('revision', [29, 30])
def test_prepare_freezes_correct_both_role_prompts(tmp_path, revision):
    context = fixture()
    policy = load_policy(ROOT)
    policy['routing_revision'] = revision
    work = tmp_path / 'MRVL'
    work.mkdir()
    with ExitStack() as stack:
        clock = stack.enter_context(patch.object(stage, 'datetime', wraps=datetime))
        clock.now.return_value = datetime.fromisoformat(context['prepared_at'])
        for name, result in [
            ('load_policy', policy), ('load_reference_payload', context['sol_reference']),
            ('load_current_report', context['reference']), ('load_research', None),
        ]:
            stack.enter_context(patch.object(stage, name, return_value=result))
        for name, result in [
            ('_fetch_slim', context['slim']), ('_load_analyst_quality', {}),
            ('load_compact_analyst_summary', {}),
            ('load_recent_analyst_actions', context['analyst_actions']),
            ('load_recent_news', context['news']), ('_load_system_prompt', 'legacy'),
        ]:
            stack.enter_context(patch.object(stage.one, name, return_value=result))
        stack.enter_context(patch.object(stage, 'call_codex', side_effect=AssertionError('NO MODEL')))
        stack.enter_context(patch.object(stage, 'run_bounded', side_effect=AssertionError('NO PROCESS')))
        stage.prepare(ROOT, work, 'MRVL', context['owned'], context['tier'])
        for name in ('instructions.md', 'triage_instructions.md'):
            text = (work / name).read_text(encoding='utf-8')
            if revision == 30:
                assert 'AUTHORING BUDGETS' in text
                assert '2 short sentences, 45 words total' in text
                assert 'not proof of present defense' in ' '.join(text.split())
                assert 'five-session forward window' in text
                assert 'No word count, compulsory' not in text
                assert 'preferiblemente, en el Motivo' not in text
                assert 'integra brevemente el motivo en' not in text
                assert text.rstrip().endswith('Do not claim old reports were shortened.')
            else:
                assert 'AUTHORING BUDGETS' not in text
                assert text == (ORIGINAL / name).read_text(encoding='utf-8')
        frozen = {p.name: p.read_bytes() for p in work.iterdir()}
        policy['routing_revision'] = 30
        stage.prepare(ROOT, work, 'MRVL', context['owned'], context['tier'])
        assert frozen == {p.name: p.read_bytes() for p in work.iterdir()}


def test_same_financial_schema_and_no_length_rejection():
    assert report_schema(30) == report_schema(29)
    assert update_schema(30) == update_schema(29)
    response = json.loads((ORIGINAL / 'report.response').read_text(encoding='utf-8'))
    response['summary']['narrative'] *= 10
    check_schema(response, report_schema(30))  # No new style-driven failure/repair.


def test_original_mrvl_financial_content_and_rendering_unchanged():
    originals = {p: p.read_bytes() for p in (
        ORIGINAL / 'input.json', ORIGINAL / 'report.response',
        ORIGINAL / 'instructions.md', ORIGINAL / 'triage_instructions.md',
    )}
    response = json.loads(originals[ORIGINAL / 'report.response'])
    docs = []
    for revision in (29, 30):
        context = fixture()
        context['routing_revision'] = revision
        view = model_context(context)
        receipt = {
            'text': json.dumps(response), 'exit_code': 0,
            'input_sha256': hashlib.sha256(serialize_model_input(view).encode()).hexdigest(),
        }
        document = full_document(deepcopy(response), view,
            binding=bind_response(context, receipt, 'report'))
        docs.append(document)
        rendered = render_document(document)
        if revision == 30:
            assert 'Precio en la captura: por debajo de la zona.' in rendered
            assert 'ubicación, no confirmación de ruptura ni ejecución' not in rendered
        else:
            assert 'ubicación, no confirmación de ruptura ni ejecución' in rendered
        # No truncation, hiding, rewritten claims or changed prices to force brevity.
        assert response['summary']['narrative'] in rendered
        for key in ('entry', 'ambitious_entry', 'resistance'):
            assert response['plan'][key]['reason'] in rendered
    for key in ('summary', 'plan', 'catalysts', 'next_event', 'conclusion'):
        assert docs[0][key] == docs[1][key]
    assert all(p.read_bytes() == value for p, value in originals.items())


def test_rubric_is_not_changed_by_editorial_revision():
    old = (ROOT / 'prompts/stock_analysis_semantic_v7.md').read_text(encoding='utf-8')
    new = (ROOT / 'prompts/stock_analysis_semantic_v8.md').read_text(encoding='utf-8')
    start, end = 'Fortaleza obligatoria de los soportes', 'Si la evidencia esencial no'
    assert old.split(start)[1].split(end)[0] == new.split(start)[1].split(end)[0]


def test_repair_preserves_legacy_contract_and_new_editorial_scope():
    context = fixture()
    old = repair_context(context, {}, 'test')['maintenance_repair']['instruction']
    context['routing_revision'] = 30
    new = repair_context(context, {}, 'test')['maintenance_repair']['instruction']
    assert new.startswith(old)
    assert 'revision30' not in old and 'revision30' in new
    assert '2 frases/45 palabras' in new
    assert 'No reescribas texto protegido por estilo' in new
    assert 'sin regla automatica de porcentaje/ATR/cierres' in new
