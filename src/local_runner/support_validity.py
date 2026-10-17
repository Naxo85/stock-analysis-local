"""Dated, model-assessed buying extent for live presentation, not a stop.

Invalid/missing display evidence removes the extension; it never creates a
paid repair or escalation. Financial plan authority stays separate.
"""
from copy import deepcopy
from datetime import datetime
import math

REVISION = 36
KEYS = ('entry', 'ambitious_entry')


def review_schema():
    from src.local_runner.semantic_report import obj, nullable
    item = nullable(obj({
        'lower_bound': nullable({'type': 'number', 'exclusiveMinimum': 0}),
        'reason': {'type': 'string'},
        'current_evidence': {'type': 'array', 'items': {'type': 'string', 'pattern': r'^s[1-9][0-9]*$'}},
    }))
    return nullable(obj({key: deepcopy(item) for key in KEYS}))


def bound_extent(level):
    """Only finite, positive bounds attached to this exact active range."""
    if not isinstance(level, dict):
        return None
    zone, extent = level.get('range'), level.get('support_validity')
    if not isinstance(zone, dict) or not isinstance(extent, dict) or extent.get('range') != zone:
        return None
    bound = extent.get('lower_bound')
    if (type(bound) not in (int, float) or not math.isfinite(bound)
            or bound <= 0 or bound > zone['lower']
            or not isinstance(extent.get('reason'), str) or not extent['reason'].strip()
            or not extent.get('assessed_at')):
        return None
    return deepcopy(extent)


def apply_review(doc, baseline, review, context):
    """Null inherits only an unchanged zone; explicit null bound clears it.

    The runner copies exact current sources and supplies date/range. Malformed
    input cannot silently preserve an old favorable extension.
    """
    from src.local_runner.semantic_sources import source_catalog
    catalog = source_catalog(context)
    valid_review = review is None or (isinstance(review, dict) and set(review) == set(KEYS))
    audit = {}
    for key in KEYS:
        level = doc['plan'][key]
        prior = ((baseline or {}).get('plan') or {}).get(key) or {}
        inherited = bound_extent(prior) if prior.get('range') == level.get('range') else None
        choice = review.get(key) if valid_review and isinstance(review, dict) else None
        level.pop('support_validity', None)
        if not level.get('range'):
            continue
        if not valid_review:
            audit[key] = 'invalid_review_no_lower_extension'
            continue
        if choice is None:
            if inherited:
                level['support_validity'] = inherited
            continue
        if (not isinstance(choice, dict) or set(choice) != {'lower_bound', 'reason', 'current_evidence'}
                or not isinstance(choice.get('reason'), str) or not choice['reason'].strip()
                or not isinstance(choice.get('current_evidence'), list)):
            audit[key] = 'invalid_extent_no_lower_extension'
            continue
        bound = choice['lower_bound']
        if bound is None:
            audit[key] = {'lower_bound': None, 'reason': choice['reason'], 'assessed_at': context['prepared_at']}
            continue
        if (type(bound) not in (int, float) or not math.isfinite(bound)
                or bound <= 0 or bound > level['range']['lower']):
            audit[key] = 'invalid_bound_no_lower_extension'
            continue
        sources = []
        for token in choice['current_evidence']:
            row = catalog.get(token) if isinstance(token, str) else None
            if (not row or not row['pointer'].startswith('/slim/') or not row['value']
                    or (isinstance(row['value'], dict) and row['value'].get('status')
                        in ('unavailable', 'failed', 'missing', 'error'))):
                sources = []
                break
            sources.append(deepcopy(row))
        if not sources:
            audit[key] = 'unverified_current_sources_no_lower_extension'
            continue
        level['support_validity'] = {
            'lower_bound': bound, 'range': deepcopy(level['range']),
            'reason': choice['reason'], 'assessed_at': context['prepared_at'],
            'sources': sources,
        }
    if audit:
        doc['support_validity_audit'] = audit
    else:
        doc.pop('support_validity_audit', None)


def migrate_payload(payload, baseline, anchor, review, context):
    """Natural retain/update publication; a display bound does not re-date finance."""
    from src.local_runner.semantic_report import reference_document, render_document, publication_fields
    from src.local_runner.review_memory import rebind_memory
    doc = reference_document(payload, verify_projection=True)
    old = reference_document(baseline, verify_projection=True)
    before = deepcopy(doc)
    apply_review(doc, old, review, context)
    if doc == before:
        return payload, False
    md = render_document(doc)
    if payload['analysis_markdown'].startswith('Mantenimiento técnico: Luna · '):
        md = payload['analysis_markdown'].split('\n\n', 1)[0] + '\n\n' + md
    result = deepcopy(payload)
    generated = datetime.fromisoformat(payload['generated_at'].replace('Z', '+00:00'))
    result.update({key: value for key, value in publication_fields(doc, md, payload, generated).items()
                   if key not in ('changes', 'alerts')})
    result['analysis_markdown'] = md
    if 'review_memory' in payload:
        result['review_memory'] = rebind_memory(payload, result, anchor)
    return result, True
