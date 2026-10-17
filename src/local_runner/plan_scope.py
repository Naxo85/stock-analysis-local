"""Versioned user-facing plan scope, independent of frozen legacy contracts."""

BUY_PLAN_REVISION = 29
BUY_PLAN_KEYS = ('entry', 'ambitious_entry', 'resistance')
RETIRED_PLAN_KEYS = ('management_stop', 'structural_stop', 'target')
SUPPORT_ONLY_REVISION = 35
SUPPORT_KEYS = ('entry', 'ambitious_entry')


def plan_keys(revision):
    return SUPPORT_KEYS if revision >= SUPPORT_ONLY_REVISION else BUY_PLAN_KEYS


def plan_labels(revision):
    from src.local_runner.semantic_report import LABELS
    if revision < BUY_PLAN_REVISION:
        return LABELS
    return {key: ('Resistencia operativa' if key == 'resistance' else LABELS[key])
            for key in plan_keys(revision)}


def editable_keys(revision):
    from src.local_runner.semantic_report import EDITABLE
    return plan_keys(revision) if revision >= BUY_PLAN_REVISION else EDITABLE


def project_plan(doc, revision=29):
    """Drop retired structured fields in a COPY, never alter financial judgments."""
    from copy import deepcopy
    result = deepcopy(doc)
    result['plan'] = {key: result['plan'][key] for key in plan_keys(revision)}
    for key in (*RETIRED_PLAN_KEYS, *(('resistance',) if revision >= 35 else ())):
        (result.get('text_provenance') or {}).pop(key, None)
    return result


def migrate_retained(reference, anchor, revision=29):
    """Presentation/scope migration of a reviewed retain, not a new analysis.

    Values, strengths, prose, observation frames and report/ITV dates stay exact.
    The original six-field report and anchor remain in the frozen input/archive.
    """
    from copy import deepcopy
    from datetime import datetime
    from src.local_runner.semantic_report import reference_document, render_document, publication_fields
    doc = reference_document(reference, verify_projection=True)
    scope_revision = SUPPORT_ONLY_REVISION if revision >= SUPPORT_ONLY_REVISION else BUY_PLAN_REVISION
    if set(doc['plan']) == set(plan_keys(scope_revision)):
        return deepcopy(reference), False
    removed = sorted(set(doc['plan']) - set(plan_keys(scope_revision)))
    doc = project_plan(doc, scope_revision)
    # Scope migration is presentation, not a new financial/rubric observation.
    if scope_revision == BUY_PLAN_REVISION:
        doc['metadata']['source_contract_revision'] = BUY_PLAN_REVISION
    else:
        doc['metadata']['reader_format_revision'] = scope_revision
    doc['scope_migration'] = {'from_report_at': reference['generated_at'],
                              'removed_fields': removed,
                              'financial_values_unchanged': True}
    md = render_document(doc)
    if reference['analysis_markdown'].startswith('Mantenimiento técnico: Luna · '):
        # Preserve the dated disclosure that fundamental prose was inherited.
        md = reference['analysis_markdown'].split('\n\n', 1)[0] + '\n\n' + md
    generated = datetime.fromisoformat(reference['generated_at'].replace('Z', '+00:00'))
    fields = publication_fields(doc, md, reference, generated)
    payload = deepcopy(reference)
    payload.update({key: value for key, value in fields.items() if key not in ('changes', 'alerts')})
    payload['analysis_markdown'] = md
    from src.local_runner.review_memory import rebind_memory
    payload['review_memory'] = rebind_memory(reference, payload, anchor)
    return payload, True
