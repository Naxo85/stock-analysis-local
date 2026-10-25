"""Revision 18: explicit review coverage, not an inference from feed receipt.

The model judges relevance. Code only tracks which exact inputs were addressed;
it never decides that a headline is harmless or that a price change is material.
"""
from copy import deepcopy

from src.local_runner.adaptive_cache import digest
from src.local_runner.review_memory import read_memory


def review_agenda(context):
    reference = context.get('reference') or {}
    memory = read_memory(reference, context.get('sol_reference', reference))
    coverage = memory.get('coverage', {})
    rows = []
    seen = set()
    for i, article in enumerate((context.get('news') or {}).get('items', [])):
        key = 'article:' + digest(article)
        if key in seen:
            continue
        seen.add(key)
        rows.append({'id': 'n' + str(i + 1), 'key': key, 'kind': 'article',
                     'pointer': '/news/items/' + str(i), 'required': key not in coverage,
                     'previous_assessment': deepcopy(coverage.get(key))})
    if reference.get('analysis_markdown'):
        from src.local_runner.semantic_report import reference_document
        event = reference_document(reference, verify_projection=True).get('next_event')
        day = str((context.get('slim') or {}).get('as_of') or '')[:10]
        if event and event.get('date') and event['date'][:10] <= day:
            key = 'event:' + digest(event)
            prior = coverage.get(key)
            settled = prior and prior.get('event_status') in ('occurred', 'cancelled', 'rescheduled')
            rows.append({'id': 'e1', 'key': key, 'kind': 'due_event',
                         'pointer': '/reference/semantic_data/next_event',
                         'event': deepcopy(event), 'required': not bool(settled),
                         'previous_assessment': deepcopy(prior)})
    return rows


def coverage_schema():
    from src.local_runner.semantic_report import obj
    return {'type': 'array', 'items': obj({
        'items': {'type': 'array', 'items': {'type': 'string'}},
        'assessment': {'type': 'string'},
        'outcome': {'type': 'string', 'enum': ['no_action', 'routine_change', 'critical_change', 'unresolved']},
        'event_status': {'type': 'string', 'enum': ['not_applicable', 'pending', 'occurred', 'cancelled', 'rescheduled', 'uncertain']},
    })}


def coverage_issues(payload, context):
    if context.get('routing_revision', 1) < 18:
        return []
    from src.local_runner.semantic_report import check_schema
    issues = []
    def issue(message):
        issues.append({'field': '/news_review', 'error': 'update_not_allowed_review_coverage: ' + message})
    groups = payload.get('news_review')
    try:
        check_schema(groups, coverage_schema())
    except ValueError:
        issue('Return grouped assessments of the supplied review_agenda items.')
        return issues
    agenda = {row['id']: row for row in review_agenda(context)}
    addressed = set()
    for group in groups:
        if (context.get('routing_revision', 1) >= 19 and not group['items']
                and group['outcome'] == 'no_action' and group['event_status'] == 'not_applicable'):
            # Empty no-work observations assert coverage of NOTHING. Required
            # agenda items are still checked below; no prose matching.
            continue
        if not group['items'] or not group['assessment'].strip():
            issue('Each group needs identified items and an actual assessment.')
        for handle in group['items']:
            if handle not in agenda or handle in addressed:
                issue('Unknown or duplicate item: ' + handle)
                continue
            addressed.add(handle)
            if agenda[handle]['kind'] == 'due_event' and group['event_status'] == 'not_applicable':
                issue('Assess the due event status explicitly: ' + handle)
    missing = [key for key, row in agenda.items() if row['required'] and key not in addressed]
    if missing:
        issue('Unaddressed items (related items may share one assessment): ' + ', '.join(missing))
    return issues


def save_review_coverage(data, context, triage, reviewed_at):
    # Never infer item-level review from a generic feed summary. A rejected
    # triage passed to Sol is not silently promoted into reviewed evidence.
    if coverage_issues(triage, context):
        return
    agenda = {row['id']: row for row in review_agenda(context)}
    coverage = data.setdefault('coverage', {})
    for group in triage.get('news_review', []):
        for handle in group['items']:
            key = agenda[handle]['key']
            if group['outcome'] == 'unresolved':
                coverage.pop(key, None)
                continue
            coverage[key] = {k: deepcopy(group[k]) for k in ('assessment', 'outcome', 'event_status')}
            coverage[key]['reviewed_at'] = reviewed_at


def latest_review_view(context):
    reference = context.get('reference') or {}
    data = read_memory(reference, context.get('sol_reference', reference))
    return deepcopy(data.get('latest_review'))


def plan_explanation_schema(revision=18):
    from src.local_runner.semantic_report import obj, LABELS, nullable
    from src.local_runner.plan_scope import plan_labels
    def text():
        if revision >= 21:
            from src.local_runner.maintenance_change import commentary_review_schema
            return nullable(obj({'text': {'type': 'string'}, 'review': commentary_review_schema()}))
        return nullable({'type': 'string'}) if revision >= 20 else {'type': 'string'}
    return obj({'setup_reason': text(), 'conclusion': text(),
                'reasons': obj({key: {'type': 'null'} if revision >= 21 and key == 'structural_stop'
                                else text() for key in plan_labels(revision)})})


def reconcile_plan_explanation(doc, change, old_plan, context):
    """Atomic dependent prose; never copy/replace prices inside free text."""
    from src.local_runner.adaptive_maintenance import _check_urls, _evidence
    issues = []
    explanation = change.get('plan_explanation')
    changed = any(doc['plan'][key]['range'] != prior['range'] for key, prior in old_plan.items())
    def issue(message):
        issues.append({'field': '/update/plan_explanation',
                       'error': 'update_not_allowed_plan_coherence: ' + message})
    revision = context.get('routing_revision', 1)
    if changed and explanation is None and revision < 40:
        issue('Changed ranges require one coherent explanation of the resulting plan, including inherited levels and conclusion.')
    if explanation is None:
        return issues
    partial = context.get('routing_revision', 1) >= 20
    from src.local_runner.maintenance_text import explanation_texts
    texts = explanation_texts(explanation) if partial else [
        explanation['setup_reason'], explanation['conclusion'], *explanation['reasons'].values()]
    if partial and not texts and (not changed or revision >= 40):
        return issues  # An explicit set of nulls is no text edit, not missing proof.
    if not changed and context.get('routing_revision', 1) < 19:
        issue('Do not rewrite the plan explanation without a range change. Use the existing justified commentary fields if needed.')
        return issues
    if not changed and context.get('routing_revision', 1) < 21:
        review = (change.get('change_review') or {}).get('plan_explanation')
        if not review or review.get('basis') != 'prior_error':
            issue('With unchanged ranges, identify the existing factual/relational error; do not rewrite for style or completeness.')
            return issues
    duplicate = any(change[key] is not None and (not partial or
                    explanation[key] and explanation[key].strip()) for key in ('conclusion', 'setup_reason'))
    if duplicate:
        issue('Use plan_explanation as the single prose authority, not duplicate setup_reason/conclusion.')
        return issues
    if revision >= 40:
        for key, reason in explanation['reasons'].items():
            block = change['plan'].get(key)
            if block is not None and reason and reason.strip() and reason != block['reason']:
                issue('Use the edited level block as the single reason authority: ' + key)
        if issues:
            return issues
    if not partial and any(not text.strip() for text in texts):
        issue('Keep the financial rationale for every part of the plan.')
        return issues
    try:
        _check_urls('\n'.join(texts), context['reference']['analysis_markdown'],
                    _evidence(context, ['/slim', '/reference'], edits=False), canonical=True)
    except ValueError as exc:
        issues.append({'field': '/update/plan_explanation', 'error': str(exc)})
    if not partial or explanation['setup_reason'] and explanation['setup_reason'].strip():
        doc['summary']['setup_reason'] = explanation['setup_reason']
    if not partial or (explanation['conclusion'] and explanation['conclusion'].strip()
                       and explanation['conclusion'] != doc['conclusion']):
        doc['conclusion'] = explanation['conclusion']
        doc.pop('conclusion_provenance', None)
    for key, reason in explanation['reasons'].items():
        if partial and (not reason or not reason.strip() or reason == doc['plan'][key]['reason']):
            continue  # Inherit candidate block + its existing provenance, not an empty reason.
        doc['plan'][key]['reason'] = reason
        doc['plan'][key]['reason_reviewed_at'] = context['slim'].get('as_of')
    # Audit stays internal; no source records or reconciliation text dumps.
    doc['plan_explanation_review'] = {'reviewed_at': context['slim'].get('as_of'),
                                    'scope': 'dependent_prose_only'}
    return issues


def record_event_assessment(doc, payload, context):
    # The original event remains a dated Sol judgment. Attach the explicit
    # later status, rather than silently editing the protected event payload.
    if coverage_issues(payload, context):
        return
    for group in payload.get('news_review', []):
        if 'e1' in group['items'] and group['event_status'] != 'not_applicable':
            doc['event_review'] = {'reviewed_at': context['slim'].get('as_of'),
                                   'status': group['event_status'],
                                   'event_key': 'event:' + digest(doc['next_event'])}


def review_contract_only(error):
    issues = getattr(error, 'maintenance_details', {}).get('issues') or []
    def routine(row):
        reason = row.get('error', '')
        return reason.startswith(('update_not_allowed_review_coverage:',
            'update_not_allowed_plan_coherence:', 'update_not_allowed_change_not_established:')) or (
            reason.startswith('update_not_allowed_source_reference: ')
            and 'update_not_allowed_unknown_source_handle:' in reason)
    return bool(issues) and all(routine(row) for row in issues)
