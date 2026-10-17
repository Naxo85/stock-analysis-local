"""Runner-owned observation frames; never infer paragraph dates from prose."""
from copy import deepcopy
from datetime import datetime


def texts(doc):
    return {'setup_reason': doc['summary']['setup_reason'], 'conclusion': doc['conclusion'],
            **{key: level['reason'] for key, level in doc['plan'].items()}}


def frame(doc):
    meta = doc.get('metadata') or {}
    return {'status': 'known' if meta.get('snapshot_at') else 'unknown', 'snapshot_at': meta.get('snapshot_at'),
            'reference_price': meta.get('reference_price')}


def origins(context, key='reference'):
    from src.local_runner.semantic_report import reference_document
    ref = context.get(key) or {}
    if not ref.get('analysis_markdown'):
        return {}
    doc = reference_document(ref, verify_projection=True)
    anchor = context.get('sol_reference') or {}
    anchor_doc = reference_document(anchor, verify_projection=True) if anchor.get('analysis_markdown') else None
    anchor_text = texts(anchor_doc) if anchor_doc else {}
    result = deepcopy(doc.get('text_provenance') or {})
    for field, text in texts(doc).items():
        if field in result:
            continue
        anchor_origin = ((anchor_doc.get('text_provenance') or {}).get(field) or frame(anchor_doc)) if anchor_doc else None
        prior = doc.get('conclusion_provenance') if field == 'conclusion' else None
        if prior:
            result[field] = {'status': 'known' if prior.get('snapshot_at') else 'unknown', 'snapshot_at': prior.get('snapshot_at'),
                             'reference_price': prior.get('reference_price')}
        elif (anchor_doc and text == anchor_text.get(field)
              and anchor_origin.get('status') == 'known'):
            # Older full-copy contracts stamped reason_reviewed_at even when
            # copying the same words. That is not a new observation of the claim.
            result[field] = deepcopy(anchor_origin)
        elif field in doc['plan'] and doc['plan'][field].get('reason_reviewed_at'):
            at = doc['plan'][field]['reason_reviewed_at']
            result[field] = {'status': 'known', 'snapshot_at': at,
                            'reference_price': frame(doc)['reference_price'] if at == frame(doc)['snapshot_at'] else None}
        else:
            result[field] = {'status': 'unknown', 'snapshot_at': None, 'reference_price': None}
    return result


def stamp(doc, context, *, full=False):
    if full:
        doc['text_provenance'] = {key: frame(doc) for key in texts(doc)}
        return
    from src.local_runner.semantic_report import reference_document
    old = reference_document(context['reference'], verify_projection=True)
    previous = texts(old)
    inherited = origins(context)
    doc['text_provenance'] = {key: deepcopy(inherited[key]) if text == previous[key] else frame(doc)
                              for key, text in texts(doc).items()}


def label(doc, key):
    origin = (doc.get('text_provenance') or {}).get(key)
    if not origin or origin == frame(doc):
        return ''
    if origin.get('status') == 'unknown':
        return ' [juicio heredado; fecha original no registrada]'
    at = origin.get('snapshot_at')
    try:
        at = datetime.fromisoformat(at.replace('Z', '+00:00')).strftime('%d/%m/%Y %H:%M %z')
    except (ValueError, AttributeError):
        at = at or 'fecha no registrada'
    return ' [juicio del ' + str(at) + ']'
