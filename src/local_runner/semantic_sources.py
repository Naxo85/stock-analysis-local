"""Revision-10 source handles: exact identities, never guessed array offsets.

The registry is rebuilt from frozen originals, not from model output. Values
remain in the input (lossless transport aliases avoid duplicating large rows).
Handles survive array reordering; their scope and complete content are bound.
"""
from copy import deepcopy
import hashlib
import json

from src.local_runner.adaptive_context import resolve_evidence


def source_catalog(context):
    result = {}

    def add(scope, group, pointer, value):
        binding = json.dumps([scope, group, value], ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False)
        # Compact handles reduce repeated input/output tokens. Collision is an
        # integrity error below, never permission to pick an arbitrary source.
        identifier = scope + '_' + group + '_' + hashlib.sha256(binding.encode()).hexdigest()[:16]
        record = {'pointer': pointer, 'value': deepcopy(value)}
        if identifier in result:
            if result[identifier]['value'] != value:
                raise ValueError('invalid_update_source_catalog_collision')
            return  # Identical duplicate is not independent evidence.
        result[identifier] = record

    for scope, root in (('current', '/slim'), ('reference', '/reference/slim_snapshot'),
                        ('sol', '/sol_reference/slim_snapshot')):
        try:
            slim = resolve_evidence(context, root)
        except ValueError:
            continue
        if not isinstance(slim, dict):
            continue
        for kind, rows in (slim.get('levels') or {}).items():
            if isinstance(rows, list):
                for index, row in enumerate(rows):
                    if isinstance(row, dict):
                        add(scope, kind, root + '/levels/' + kind + '/' + str(index), row)
        for name in ('technicals', 'volume_profile', 'options', 'market_state'):
            if name in slim:
                add(scope, name, root + '/' + name, slim[name])
        if context.get('routing_revision', 1) >= 28 and 'price_history' in slim:
            add(scope, 'price_history', root + '/price_history', slim['price_history'])
    if context.get('routing_revision', 1) >= 11:
        from src.local_runner.semantic_report import reference_document
        for scope, side in (('reference_report', 'reference'), ('sol_report', 'sol_reference')):
            reference = context.get(side) or {}
            if reference.get('analysis_markdown'):
                document = reference_document(reference, verify_projection=True)
                for key, level in document['plan'].items():
                    if context.get('routing_revision', 1) >= 29:
                        from src.local_runner.plan_scope import plan_keys
                        if key not in plan_keys(context['routing_revision']):
                            continue
                    if context.get('routing_revision', 1) >= 15:
                        from src.local_runner.financial_projection import financial_level
                        level = financial_level(level)
                    add(scope, key, '/' + side + '/semantic_data/plan/' + key, level)
    if context.get('routing_revision', 1) >= 12:
        # Input-local selectors, NOT checksums the model must transcribe. The
        # actual receipt binds the complete frozen catalog; a selector from a
        # different input has no authority. Sort internal content identities so
        # array reordering cannot change the meaning of an existing selection.
        return {'s' + str(i): result[key] for i, key in enumerate(sorted(result), 1)}
    return result


def source_pointer(token, catalog, *, revision=10):
    if revision >= 11 and token.startswith('/source_catalog/'):
        # The catalog IS an input object: its logical JSON addresses must use
        # the same exact resolution as handles, not a second authority system.
        address = token[len('/source_catalog/'):].split('/')
        identifier = address[0]
        if identifier not in catalog:
            raise ValueError('update_not_allowed_unknown_source_handle: ' + token)
        suffix = address[1:]
        if suffix:
            if suffix[0] != 'value':
                raise ValueError('update_not_allowed_catalog_metadata_not_evidence: ' + token)
            suffix = suffix[1:]
        return catalog[identifier]['pointer'] + ('/' + '/'.join(suffix) if suffix else '')
    if token.startswith('/'):
        return token  # Explicit originals remain possible; no fuzzy correction.
    identifier, separator, suffix = token.partition('/')
    if identifier not in catalog:
        raise ValueError('update_not_allowed_unknown_source_handle: ' + token)
    return catalog[identifier]['pointer'] + ('/' + suffix if separator else '')


def is_report_source(pointer):
    return any(pointer.startswith('/' + side + '/' + field + '/') or pointer == '/' + side + '/' + field
               for side in ('reference', 'sol_reference')
               for field in ('plan', 'decision', 'catalysts', 'next_event', 'semantic_data'))


def resolve_source(context, pointer):
    """Historical report facts come from verified authority, NEVER old mirrors.

    This is a distinct source class, not permission to use a prior report as
    current technical corroboration. All live-origin gates still use slim only.
    """
    if context.get('routing_revision', 1) >= 11 and is_report_source(pointer):
        from src.local_runner.semantic_report import reference_document
        side = pointer.split('/')[1]
        reference = context.get(side) or {}
        if reference.get('analysis_status') != 'ok' or not reference.get('analysis_markdown'):
            raise ValueError('invalid_historical_report_authority')
        document = reference_document(reference, verify_projection=True)
        if context.get('routing_revision', 1) >= 15:
            from src.local_runner.financial_projection import financial_document
            document = financial_document(document, context.get('routing_revision', 15))
        plan = {}
        for key, level in document['plan'].items():
            zone = deepcopy(level['range'])
            plan[key] = zone['lower'] if zone and key in ('management_stop', 'structural_stop', 'target') else zone
            plan[key + '_reason'] = level['reason']
            if key in ('entry', 'ambitious_entry', 'resistance'):
                prefix = 'washout' if key == 'ambitious_entry' else key
                strength = level['strength']
                plan[prefix + '_strength_score'] = sum(strength['components'].values()) if strength else None
                plan[prefix + '_strength_breakdown'] = deepcopy(strength['components']) if strength else {}
                plan[prefix + '_strength_factors'] = strength['factors'] if strength else level['reason']
        authority = {'plan': plan, 'decision': {**document['summary'], 'score': document['summary']['thesis_score']},
                     'catalysts': document['catalysts'], 'next_event': document['next_event'], 'semantic_data': document}
        return resolve_evidence({side: authority}, pointer)
    return resolve_evidence(context, pointer)


def scalar_pointers(pointer, value):
    """A source object is copied mechanically, not rejected for its packaging.

    Null children are unavailable, never numeric confirmation. Explicit scalar
    null facts still fail the existing financial validator.
    """
    if isinstance(value, dict):
        return [child for key, item in value.items() for child in scalar_pointers(
            pointer + '/' + key.replace('~', '~0').replace('/', '~1'), item)]
    if isinstance(value, list):
        return [child for index, item in enumerate(value) for child in scalar_pointers(
            pointer + '/' + str(index), item)]
    return [pointer] if value is not None else []


def normalize_plan(plan, previous, context):
    """Resolve selected sources and derive continuity without choosing prices.

    Returns all independent source errors for the ONE directed correction. The
    source catalog supplied in model input is not trusted as authority here.
    """
    catalog = source_catalog(context)
    result, issues = deepcopy(plan), []
    for key, level in result.items():
        prior = (previous or {}).get(key) or {}
        old, zone = prior.get('range'), level['range']
        if zone == old:
            transition = 'keep'
        elif zone is None:
            transition = 'remove'
        elif old is None:
            transition = 'new'
        elif max(zone['lower'], old['lower']) <= min(zone['upper'], old['upper']):
            transition = 'correct'
        else:
            transition = 'reprioritize'
        level['transition'] = transition
        for field in ('evidence', 'facts'):
            resolved = []
            for token in level[field]:
                try:
                    pointer = source_pointer(token, catalog, revision=context.get('routing_revision', 10))
                    value = resolve_source(context, pointer)
                    if field == 'facts' and isinstance(value, (dict, list)):
                        resolved.extend(scalar_pointers(pointer, value))
                    else:
                        resolved.append(pointer)
                except ValueError as exc:
                    issues.append({'field': '/plan/' + key + '/' + field, 'source': token,
                                   'error': 'update_not_allowed_source_reference: ' + str(exc)})
            level[field] = list(dict.fromkeys(resolved))
    return result, issues


def raise_issues(issues):
    if issues:
        error = ValueError(issues[0]['error'])
        error.maintenance_details = {'issues': issues,
            'instruction': 'Correct ALL listed issues. Keep unaffected financial choices; use exact source_catalog handles. '
                           'Never infer a neighboring index or treat missing sources as harmless.'}
        raise error


def source_selection_only(error):
    """A missing selector is a transport failure, not a financial research need.

    Mixed financial/source issues are NOT classified here. Never infer that a
    missing financial origin, expired option or critical uncertainty is harmless.
    """
    issues = getattr(error, 'maintenance_details', {}).get('issues') or []
    return bool(issues) and all(
        row.get('error', '').startswith('update_not_allowed_source_reference: ')
        and 'update_not_allowed_unknown_source_handle:' in row['error']
        for row in issues)
