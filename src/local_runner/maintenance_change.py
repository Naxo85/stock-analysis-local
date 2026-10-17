"""Revision14: evidence for changing a judgment is not evidence for its replacement.

The model still judges financial meaning. This checks the declared decision and
its exact source bindings, never keywords, punctuation or price thresholds.
"""
from copy import deepcopy

BASES = ('backing_changed', 'prior_error', 'material_improvement',
         'missing_from_snapshot', 'quote_only', 'no_material_change', 'unresolved')
UNSUPPORTED = frozenset(('missing_from_snapshot', 'quote_only', 'no_material_change', 'unresolved'))
PREFIX = 'update_not_allowed_change_not_established:'


def review_schema(revision=1):
    from src.local_runner.semantic_report import obj
    sources = {'type': 'array', 'items': {'type': 'string', 'pattern': r'^s[1-9][0-9]*$'}}
    bases = [*BASES, 'rubric_change'] if revision >= 34 else list(BASES)
    return obj({'basis': {'type': 'string', 'enum': bases},
                'previous_evidence': deepcopy(sources), 'current_evidence': deepcopy(sources),
                'explanation': {'type': 'string'}})


def commentary_review_schema():
    from src.local_runner.semantic_report import obj
    schema = review_schema()
    for key in ('previous_evidence', 'current_evidence'):
        schema['properties'][key]['items'] = {'type': 'string',
            'pattern': r'^/(?:reference|slim|news|analyst_actions)(?:/|$)'}
    schema['properties']['scope'] = {'type': 'string', 'enum': [
        'routine_technical', 'routine_news', 'fundamental_or_structural']}
    schema['required'].append('scope')
    return obj(schema['properties'])


def commentary_requires_sol(payload):
    change = payload.get('update') or {}
    reviews = change.get('change_review') or {}
    values = list(reviews.values()) if isinstance(reviews, dict) else []
    values.append((change.get('public_note') or {}).get('review'))
    from src.local_runner.maintenance_text import individual_text_edits
    values.extend(edit.get('review') for edit in individual_text_edits(change.get('plan_explanation')).values())
    return any(isinstance(item, dict) and item.get('scope') == 'fundamental_or_structural'
               for item in values)


def validate_commentary_changes(payload, context):
    """Evidence/scope contract, NOT a classifier of arbitrary model prose."""
    from src.local_runner.semantic_sources import resolve_source
    from src.local_runner.semantic_report import digest
    from src.local_runner.maintenance_text import note_edit, note_text
    change = payload['update']
    revision = context.get('routing_revision', 1)
    changed = {'setup': change['setup_score'] is not None or change['setup_reason'] is not None,
               'conclusion': change['conclusion'] is not None,
               'routine_note': bool(note_text(payload, revision).strip())}
    if 19 <= context.get('routing_revision', 1) < 21:
        # A prose-only correction has its own evidence. Range changes already
        # carry block-level justification; they need no duplicate explanation
        # review unless the model is also correcting a previously wrong claim.
        from src.local_runner.semantic_report import reference_document
        old = reference_document(context['reference'], verify_projection=True)['plan']
        moved = any(level is not None and level['range'] != old[key]['range']
                    for key, level in change['plan'].items())
        from src.local_runner.maintenance_text import explanation_texts
        has_text = (change.get('plan_explanation') is not None if revision < 20
                    else bool(explanation_texts(change.get('plan_explanation'))))
        changed['plan_explanation'] = (has_text and
            (not moved or change['change_review'].get('plan_explanation') is not None))
    issues, audit = [], {}
    for key, edited in changed.items():
        review = ((note_edit(payload, revision) or {}).get('review') if revision >= 20 and key == 'routine_note'
                  else change['change_review'][key])
        try:
            if not edited:
                if review is not None:
                    raise ValueError(PREFIX + ' ' + key + ': review_without_edit')
                continue
            if review is None:
                raise ValueError(PREFIX + ' ' + key + ': missing_review')
            if review['basis'] in UNSUPPORTED or not review['explanation'].strip():
                raise ValueError(PREFIX + ' ' + key + ': ' + review['basis'])
            if review['scope'] == 'fundamental_or_structural':
                raise ValueError('update_not_allowed_uncertain_or_critical')
            if key == 'setup' and review['scope'] != 'routine_technical':
                raise ValueError(PREFIX + ' setup: wrong_scope')
            if key == 'plan_explanation' and (review['scope'] != 'routine_technical'
                                             or review['basis'] != 'prior_error'):
                raise ValueError(PREFIX + ' plan_explanation: requires_routine_prior_error')
            resolved = {}
            historical_correction = revision >= 20 and review['basis'] == 'prior_error'
            for field, roots in (('previous_evidence', ('/reference',)),
                                 ('current_evidence', ('/reference', '/slim', '/news', '/analyst_actions') if historical_correction else
                                  ('/reference', '/slim') if key == 'plan_explanation' else
                                  ('/slim',) if key == 'setup' else
                                  ('/slim', '/news', '/analyst_actions'))):
                if not review[field]:
                    raise ValueError(PREFIX + ' ' + key + ': missing_' + field)
                resolved[field] = []
                for pointer in review[field]:
                    if not any(pointer == root or pointer.startswith(root + '/') for root in roots):
                        raise ValueError(PREFIX + ' ' + key + ': wrong_scope_' + field)
                    try:
                        value = resolve_source(context, pointer)
                    except ValueError as exc:
                        raise ValueError(PREFIX + ' ' + key + ': missing_source') from exc
                    resolved[field].append({'pointer': pointer, 'value_sha256': digest(value)})
            audit[key] = {**deepcopy(review), 'resolved_evidence': resolved}
        except ValueError as exc:
            field = ('/update/public_note/review' if revision >= 20 and key == 'routine_note'
                     else '/update/change_review/' + key)
            issues.append({'field': field, 'error': str(exc)})
    if revision >= 21:
        from src.local_runner.maintenance_text import individual_text_edits
        from src.local_runner.text_provenance import origins
        from src.local_runner.semantic_report import reference_document
        old = reference_document(context['reference'], verify_projection=True)
        frames = origins(context)
        moved = any(level is not None and level['range'] != old['plan'][key]['range']
                    for key, level in change['plan'].items())
        for key, edit in individual_text_edits(change.get('plan_explanation')).items():
            review = edit['review']
            try:
                if not edit['text'].strip():
                    continue  # Blank is not authority to erase existing rationale.
                if review['scope'] != 'routine_technical':
                    raise ValueError('update_not_allowed_uncertain_or_critical')
                if review['basis'] in UNSUPPORTED or not review['explanation'].strip():
                    raise ValueError(PREFIX + ' ' + key + ': missing_change_basis')
                if not moved and review['basis'] != 'prior_error':
                    raise ValueError(PREFIX + ' ' + key + ': unchanged_plan_requires_prior_error')
                resolved = {}
                for field, roots in (('previous_evidence', ('/reference',)),
                        ('current_evidence', ('/reference', '/slim', '/news', '/analyst_actions')
                         if review['basis'] == 'prior_error' else ('/slim',))):
                    if not review[field]:
                        raise ValueError(PREFIX + ' ' + key + ': missing_' + field)
                    resolved[field] = []
                    for pointer in review[field]:
                        if not any(pointer == root or pointer.startswith(root + '/') for root in roots):
                            raise ValueError(PREFIX + ' ' + key + ': wrong_scope_' + field)
                        try:
                            value = resolve_source(context, pointer)
                        except ValueError as exc:
                            raise ValueError(PREFIX + ' ' + key + ': missing_source') from exc
                        resolved[field].append({'pointer': pointer, 'value_sha256': digest(value)})
                audit['text/' + key] = {**deepcopy(review), 'observation_frame': frames[key],
                                        'resolved_evidence': resolved}
            except ValueError as exc:
                issues.append({'field': '/update/plan_explanation/' + key, 'error': str(exc)})
    return issues, audit


def validate_change(level, key, context):
    """Check rationale independently of live origin/geometry of the new level.

    Presence of references cannot prove the truth of a model's causal assessment.
    Do not silently infer a missing reason, substitute a price, or force retention.
    """
    if context.get('routing_revision', 1) >= 28:
        return _validate_plan_change(level, key, context)
    from src.local_runner.semantic_sources import source_catalog
    from src.local_runner.semantic_report import digest
    review = level['change_review']
    if review['basis'] in UNSUPPORTED:
        raise ValueError(PREFIX + ' ' + key + ': ' + review['basis'])
    if not review['explanation'].strip():
        raise ValueError(PREFIX + ' ' + key + ': missing_explanation')
    catalog = source_catalog(context)
    resolved = {}
    for field, root in (('previous_evidence', '/reference/'), ('current_evidence', '/slim/')):
        selected = review[field]
        if not selected:
            raise ValueError(PREFIX + ' ' + key + ': missing_' + field)
        records = []
        for token in selected:
            if token not in catalog:
                raise ValueError('update_not_allowed_source_reference: update_not_allowed_unknown_source_handle: ' + token)
            record = catalog[token]
            allowed = record['pointer'].startswith(root) or (
                context.get('routing_revision', 1) >= 20 and field == 'current_evidence'
                and review['basis'] == 'prior_error' and record['pointer'].startswith('/reference/'))
            if not allowed:
                raise ValueError(PREFIX + ' ' + key + ': wrong_scope_' + field)
            # An unrelated old report block cannot stand in for the decision
            # being changed; historical snapshots may contain its actual origin.
            if ('/semantic_data/plan/' in record['pointer'] and not record['pointer'].endswith('/' + key)
                    and (context.get('routing_revision', 1) < 20 or field == 'previous_evidence')):
                raise ValueError(PREFIX + ' ' + key + ': unrelated_previous_block')
            # Frozen inputs already preserve full records. Do not recursively
            # embed the previous plan's change audits on every maintenance.
            records.append({'source': token, 'pointer': record['pointer'],
                            'value_sha256': digest(record['value'])})
        resolved[field] = records
    review['resolved_evidence'] = resolved  # Audit only, not human Markdown.


def _validate_plan_change(level, key, context):
    """Separate live evidence from authenticated constraints on the same plan.

    A promotion can cite both prior buying zones; a protected stop is contextual
    authority, not a new live origin. Neither can replace current market evidence.
    Collect every independent binding error for the existing single repair.
    """
    from src.local_runner.semantic_sources import source_catalog, raise_issues
    from src.local_runner.semantic_report import digest
    review = level['change_review']
    catalog, issues, resolved = source_catalog(context), [], {}
    base = '/plan/' + key + '/change_review'
    def problem(field, message, token=None, pointer=None):
        item = {'field': base + '/' + field, 'error': PREFIX + ' ' + key + ': ' + message}
        if token is not None: item['source'] = token
        if pointer is not None: item['pointer'] = pointer
        issues.append(item)
    if review['basis'] in UNSUPPORTED:
        problem('basis', review['basis'])
    if not review['explanation'].strip():
        problem('explanation', 'missing_explanation')
    if review['basis'] == 'rubric_change':
        from src.local_runner.volume_arithmetic import validate_rubric_change
        try:
            validate_rubric_change(level, key, context)
        except ValueError as exc:
            problem('basis', str(exc))
    for field in ('previous_evidence', 'current_evidence'):
        records, anchors = [], []
        selected = review[field]
        if not selected: problem(field, 'missing_' + field)
        for index, token in enumerate(selected):
            location = field + '/' + str(index)
            if token not in catalog:
                issues.append({'field': base + '/' + location, 'source': token,
                    'error': 'update_not_allowed_source_reference: update_not_allowed_unknown_source_handle: ' + token})
                continue
            record = catalog[token]
            pointer = record['pointer']
            own = pointer == '/reference/semantic_data/plan/' + key
            prior_capture = pointer.startswith('/reference/slim_snapshot/')
            prior_plan = pointer.startswith('/reference/semantic_data/plan/')
            live = pointer.startswith('/slim/')
            historical_correction = review['basis'] == 'prior_error'
            if field == 'previous_evidence':
                allowed = pointer.startswith('/reference/')
                anchor = own or prior_capture
            else:
                allowed = live or prior_plan or (historical_correction and pointer.startswith('/reference/'))
                anchor = live or (historical_correction and pointer.startswith('/reference/'))
            if not allowed:
                problem(location, 'wrong_scope_' + field, token, pointer)
                continue
            anchors.append(anchor)
            role = ('current_market_observation' if live else
                    'dated_plan_context' if prior_plan else 'dated_reference_evidence')
            records.append({'source': token, 'pointer': pointer,
                            'value_sha256': digest(record['value']), 'evidence_role': role})
        if selected and not any(anchors):
            problem(field, 'missing_previous_decision_evidence' if field == 'previous_evidence'
                    else 'missing_current_market_evidence')
        resolved[field] = records
    raise_issues(issues)
    review['resolved_evidence'] = resolved


def change_justification_only(error):
    issues = getattr(error, 'maintenance_details', {}).get('issues') or []
    return bool(issues) and all(row.get('error', '').startswith(PREFIX) for row in issues)


def origin_observations(context):
    """Exact in-zone records with short handles; absence has unknown coverage.

    No inferred support loss, live expiry, relative quality or automatic decision.
    Includes all rows, including inactive ones: the model must inspect their state.
    """
    from src.local_runner.semantic_report import reference_document, EDITABLE
    from src.local_runner.semantic_sources import source_catalog
    if not (context.get('reference') or {}).get('analysis_markdown'):
        return {}
    plan = reference_document(context['reference'], verify_projection=True)['plan']
    catalog = source_catalog(context)
    zones = {}
    from src.local_runner.plan_scope import editable_keys
    for key in editable_keys(context.get('routing_revision', 1)):
        zone = plan[key]['range']
        rows = {'previous': [], 'current': []}
        if zone:
            for handle, record in catalog.items():
                pointer, value = record['pointer'], record['value']
                scope = ('current' if pointer.startswith('/slim/levels/') else
                         'previous' if pointer.startswith('/reference/slim_snapshot/levels/') else None)
                price = value.get('level') if isinstance(value, dict) else None
                if scope and type(price) in (int, float) and zone['lower'] <= price <= zone['upper']:
                    rows[scope].append({'source': handle, 'type': value.get('type'),
                        'level': price, 'expiration': value.get('expiration'), 'active': value.get('active')})
        zones[key] = {'range': deepcopy(zone), **rows}
    return {'zones': zones, 'meaning': 'Exact listed observations, not an exhaustive census or invalidation. '
            'An absent old gap/range/wall has UNKNOWN status, not lost backing. Inspect full sources, '
            'expiry, independent backing and evidence of real change before replacing or re-scoring. '
            'Historical records remain dated, never asserted live; no automatic retain or escalation.'}
