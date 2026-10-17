"""Revision32 reader selection; never delete or re-score financial history."""
from copy import deepcopy
from datetime import datetime

REVISION = 32


def event_key(event):
    from src.local_runner.semantic_report import digest
    return digest({k: event.get(k) for k in ('date', 'title', 'impact', 'description')})


def review_schema(revision=32):
    if revision >= 33:
        from src.local_runner.catalyst_editorial import review_schema as editorial_schema
        return editorial_schema()
    from src.local_runner.semantic_report import obj, nullable
    return nullable(obj({
        'hidden_catalysts': {'type': 'array', 'items': {'type': 'string', 'pattern': '^c[1-9][0-9]*$'}},
        'hide_next_event': {'type': 'boolean'},
    }))


def catalog(reference):
    from src.local_runner.semantic_report import reference_document
    if not reference.get('analysis_markdown'):
        return {}
    doc = reference_document(reference, verify_projection=True)
    hidden = set((doc.get('reader_presentation') or {}).get('hidden_catalysts', []))
    return {'c' + str(i): {'date': row.get('date'), 'title': row['title'],
                          'currently_visible': event_key(row) not in hidden}
            for i, row in enumerate(doc['catalysts'], 1)}


def full_selection(doc):
    """Strip display choices from financial facts; keep ALL facts internally."""
    if doc.get('metadata', {}).get('source_contract_revision', 1) >= 33:
        from src.local_runner.catalyst_editorial import full_selection as editorial_selection
        return editorial_selection(doc)
    hidden = []
    for row in doc['catalysts']:
        if row.pop('show_in_report', True) is False:
            hidden.append(event_key(row))
    event = doc.get('next_event')
    hide_event = event is not None and event.pop('show_in_report', True) is False
    doc['reader_presentation'] = {'version': REVISION, 'hidden_catalysts': hidden,
        'hidden_next_event': event_key(event) if hide_event else None}


def apply_selection(doc, baseline, review, *, revision=32):
    """Selections address the bound CURRENT list, not a sorted/new/anchor list.

    Invalid presentation-only selectors keep the existing view, with an internal
    warning. They never hide arbitrary news, fail finance or buy a model repair.
    """
    if revision >= 33:
        from src.local_runner.catalyst_editorial import apply_selection as editorial_selection
        return editorial_selection(doc, baseline, review)
    doc.setdefault('reader_presentation', {'version': REVISION,
        'hidden_catalysts': [], 'hidden_next_event': None})
    if review is None:
        return
    source = {'c' + str(i): row for i, row in enumerate(baseline['catalysts'], 1)}
    valid = (isinstance(review, dict) and set(review) == {'hidden_catalysts', 'hide_next_event'}
             and isinstance(review.get('hidden_catalysts'), list)
             and type(review.get('hide_next_event')) is bool
             and all(isinstance(k, str) and k in source for k in review['hidden_catalysts']))
    if not valid:
        doc['reader_presentation']['warning'] = 'invalid_selection_preserved_previous_visibility'
        return
    event = baseline.get('next_event')
    doc['reader_presentation'] = {'version': REVISION,
        'hidden_catalysts': sorted({event_key(source[k]) for k in review['hidden_catalysts']}),
        'hidden_next_event': event_key(event) if event and review['hide_next_event'] else None}


def migrate_payload(payload, baseline, anchor, review, *, revision=32):
    """Re-render naturally published maintenance/retain without re-dating it."""
    from src.local_runner.semantic_report import reference_document, render_document, publication_fields
    from src.local_runner.review_memory import rebind_memory
    doc = reference_document(payload, verify_projection=True)
    if doc.get('fundamental_markdown') is not None:
        return payload, False  # Cannot safely select events from unstructured legacy prose.
    old = reference_document(baseline, verify_projection=True)
    doc['metadata']['reader_format_revision'] = revision
    apply_selection(doc, old, review, revision=revision)
    md = render_document(doc)
    if payload['analysis_markdown'].startswith('Mantenimiento técnico: Luna · '):
        md = payload['analysis_markdown'].split('\n\n', 1)[0] + '\n\n' + md
    if md == payload['analysis_markdown'] and doc == reference_document(payload, verify_projection=True):
        return payload, False
    result = deepcopy(payload)
    generated = datetime.fromisoformat(payload['generated_at'].replace('Z', '+00:00'))
    fields = publication_fields(doc, md, payload, generated)
    result.update({k: v for k, v in fields.items() if k not in ('changes', 'alerts')})
    result['analysis_markdown'] = md
    if 'review_memory' in payload:
        result['review_memory'] = rebind_memory(payload, result, anchor)
    return result, True


def render(doc):
    from src.local_runner.semantic_report import _reader_prose as prose, _range_text
    from src.common.analysis_validator import format_exact_price, support_strength_category
    from src.local_runner.text_provenance import label as text_date
    from src.local_runner.plan_scope import plan_labels
    meta = doc['metadata']; price = meta['reference_price']
    stamp = datetime.fromisoformat(meta['snapshot_at'].replace('Z', '+00:00'))
    lines = ['# ' + prose(meta['symbol']), 'Fecha del análisis: ' + meta['analysis_date'],
             'Precio de referencia: $' + format_exact_price(price),
             'Captura de datos: ' + stamp.strftime('%d/%m/%Y %H:%M %z'),
             '## Resumen', prose(doc['summary']['narrative'])]
    presentation = doc.get('reader_presentation') or {}
    from src.local_runner.catalyst_editorial import visible_catalysts
    visible = visible_catalysts(doc)
    if visible:
        lines.append('## Catalizadores y riesgos vigentes')
        for e in visible:
            lines += [(e['date'] or 'Fecha no confirmada') + ' · ' + prose(e['title']) +
                      ' · (' + f"{e['impact']:+d}" + ')', prose(e['description'])]
    event = doc.get('next_event')
    if event and event_key(event) != presentation.get('hidden_next_event'):
        assessment = doc.get('event_review') or {}
        past = assessment.get('status') in ('occurred', 'cancelled', 'rescheduled')
        lines += ['## Evento revisado' if past else '## Próximo evento clave',
                  (event['date'] or 'Fecha no confirmada') + ' · ' + prose(event['title']),
                  prose(event['description'])]
        if assessment:
            states = {'occurred': 'ya ocurrido', 'cancelled': 'cancelado', 'rescheduled': 'reprogramado',
                      'pending': 'pendiente', 'uncertain': 'sin confirmar'}
            lines.append('Estado revisado: ' + states[assessment['status']] +
                         ' · ' + prose(str(assessment['reviewed_at'])[:10]) + '.')
    lines.append('## Plan')
    for key, label in plan_labels(max(REVISION, meta.get('source_contract_revision', 0),
                                     meta.get('reader_format_revision', 0))).items():
        level = doc['plan'][key]; zone = level['range']; strength = level['strength']
        lines += ['### ' + label]
        if zone:
            percentages = f"{(zone['lower']/price-1)*100:+.2f}% a {(zone['upper']/price-1)*100:+.2f}%"
            lines.append(_range_text(zone) + ' (' + percentages + ' vs precio de referencia)')
        else:
            lines.append('Sin zona de compra seleccionada'
                         if max(meta.get('source_contract_revision', 0),
                                meta.get('reader_format_revision', 0)) >= 38
                         else 'Sin zona verificable')
        if strength:
            total = sum(strength['components'].values())
            lines.append('Fortaleza: ' + str(total) + '/100 · ' + support_strength_category(total))
        lines.append(prose(level['reason']) + text_date(doc, key))
        if key in ('entry', 'ambitious_entry'):
            from src.local_runner.support_validity import bound_extent
            extent = bound_extent(level)
            if extent:
                lines.append('Extensión inferior estimada: $' + format_exact_price(extent['lower_bound']) +
                             ' · evaluada ' + str(extent['assessed_at'])[:10] + '.')
    news = doc.get('news_note')
    if news:
        lines += ['## Actualización relevante · ' + prose(str(news.get('as_of') or '')[:10]), prose(news['text'])]
    if doc.get('routine_note') and (not news or doc['routine_note'] != news['text']):
        lines += ['## Nota de revisión', prose(doc['routine_note'])]
    return '\n\n'.join(lines) + '\n'
