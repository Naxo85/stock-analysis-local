"""Financial model view, separate from immutable internal provenance.

Never rewrite a stored report or authenticate a trimmed copy as the original.
Original envelopes remain in frozen input.json for local binding/validation.
"""
from copy import deepcopy


def financial_level(level):
    result = {key: deepcopy(level[key]) for key in ('range', 'reason', 'strength') if key in level}
    if isinstance(level.get('support_validity'), dict):
        # Full source copies remain in the bound local audit, not recursively
        # supplied again as current financial evidence on each daily review.
        result['support_validity'] = {key: deepcopy(value) for key, value in level['support_validity'].items()
                                      if key in ('lower_bound', 'range', 'reason', 'assessed_at')}
    return result


def financial_document(document, revision=15):
    result = {key: deepcopy(value) for key, value in document.items() if key in (
        'summary', 'fundamental_markdown', 'catalysts', 'next_event', 'conclusion',
        'routine_note', 'routine_note_at', 'metadata', 'conclusion_provenance', 'news_note', 'note_history', 'event_review', 'text_provenance', 'reader_presentation')}
    result['plan'] = {key: financial_level(value) for key, value in document['plan'].items()}
    if revision >= 29:
        from src.local_runner.plan_scope import project_plan
        result = project_plan(result, revision)
    return result


def model_input_view(context):
    if context.get('routing_revision', 1) < 15:
        return context
    from src.local_runner.semantic_report import reference_document
    result = deepcopy(context)
    for key in ('reference', 'sol_reference'):
        ref = result.get(key) or {}
        if ref.get('analysis_markdown'):
            # Verify the ORIGINAL envelope before separating the financial view.
            doc = reference_document(context[key], verify_projection=True)
            ref['semantic_data'] = financial_document(doc, context.get('routing_revision', 15))
            ref.pop('semantic_report', None)
            if context.get('routing_revision', 1) >= 16:
                ref.pop('review_memory', None)
            if context.get('routing_revision', 1) >= 29:
                # Typed financial content is sufficient: do not send the old
                # six-field Markdown and mirrors as a contradictory second plan.
                for field in ('analysis_markdown', 'plan', 'decision'):
                    ref.pop(field, None)
    result['financial_view_contract'] = (
        'Financial judgments, full Markdown and snapshots are retained. Internal '
        'receipt/provenance graphs are stored locally, not recursively supplied as '
        'financial evidence. Historical judgments are dated, not live corroboration.')
    if context.get('routing_revision', 1) >= 29:
        result['financial_view_contract'] = (
            'Authenticated typed financial content replaces duplicate Markdown and mirrors. '
            'Only entry, ambitious_entry and one operational resistance belong to the current plan. '
            'Retired stop/target fields remain solely in the immutable local archive. '
            'Legacy prose is dated evidence, not permission to reinstate retired fields.')
    if context.get('routing_revision', 1) >= 35:
        result['financial_view_contract'] = (
            'Authenticated typed content replaces duplicate Markdown and mirrors. '
            'Only entry and ambitious_entry belong to the plan. Do not select, calculate, '
            'score or maintain resistance, targets or stops. Archived fields are not current tasks. '
            'Assess buying-support viability and material risk without a numeric exit plan.')
    return result
