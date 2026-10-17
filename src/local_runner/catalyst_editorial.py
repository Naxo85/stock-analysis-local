"""Reader33: causal digest separate from the complete, dated financial facts."""
from copy import deepcopy


def assessment_schema():
    from src.local_runner.semantic_report import obj, nullable
    text = nullable({'type': 'string'})
    return obj({'role': {'type': 'string', 'enum': ['driver', 'background', 'covered']},
                'rationale': {'type': 'string'}, 'brief': deepcopy(text),
                'covered_by': deepcopy(text)})


def review_schema():
    from src.local_runner.semantic_report import obj, nullable
    row = assessment_schema()
    row['properties']['id'] = {'type': 'string', 'pattern': '^c[1-9][0-9]*$'}
    row['required'].append('id')
    return nullable(obj({'catalysts': {'type': 'array', 'items': row},
                         'hide_next_event': {'type': 'boolean'}}))


def _nonempty(text):
    return isinstance(text, str) and bool(text.strip())


def _assess(rows, choices):
    """Only validate editorial references/shapes, never classify financial prose.

    Unknown/ambiguous references cannot hide another fact. A broken editorial
    choice falls back to the previous view, without a financial failure/repair.
    """
    from src.local_runner.reader_report import event_key
    fields = {'role', 'rationale', 'brief', 'covered_by'}
    if set(rows) != set(choices):
        return None
    result = {}
    for key, row in rows.items():
        choice = choices[key]
        if not isinstance(choice, dict) or set(choice) != fields:
            return None
        role = choice['role']; target = choice['covered_by']
        if not _nonempty(choice['rationale']):
            return None
        if role == 'driver':
            if not _nonempty(choice['brief']) or target is not None:
                return None
        elif role == 'background':
            if choice['brief'] is not None or target is not None:
                return None
        elif role == 'covered':
            if (choice['brief'] is not None or not isinstance(target, str)
                    or target == key or target not in choices
                    or not isinstance(choices[target], dict)
                    or choices[target].get('role') != 'driver'):
                return None
        else:
            return None
        identity = event_key(row)
        if identity in result:  # Ambiguous identical facts: preserve visibility.
            return None
        result[identity] = {**deepcopy(choice),
            'covered_by': event_key(rows[target]) if target is not None else None}
    return result


def _install(doc, assessment, hide_event):
    from src.local_runner.reader_report import event_key
    event = doc.get('next_event')
    doc['reader_presentation'] = {'version': 33, 'assessments': assessment,
        'hidden_catalysts': sorted(k for k, v in assessment.items() if v['role'] != 'driver'),
        'hidden_next_event': event_key(event) if hide_event and event else None}


def full_selection(doc):
    rows = {}; choices = {}; ambiguous = False
    for row in doc['catalysts']:
        key = row['title']
        ambiguous |= key in rows
        rows[key] = row
        choices[key] = row.pop('reader_assessment', None)
    event = doc.get('next_event')
    hide_event = event is not None and event.pop('show_in_report', True) is False
    assessment = None if ambiguous else _assess(rows, choices)
    if assessment is None:
        _install(doc, {}, hide_event)
        doc['reader_presentation']['warning'] = 'invalid_editorial_assessment_showing_facts'
    else:
        _install(doc, assessment, hide_event)


def apply_selection(doc, baseline, review):
    if review is None:
        return
    valid = (isinstance(review, dict) and set(review) == {'catalysts', 'hide_next_event'}
             and isinstance(review['catalysts'], list) and type(review['hide_next_event']) is bool)
    choices = {}
    if valid:
        for choice in review['catalysts']:
            if (not isinstance(choice, dict) or not isinstance(choice.get('id'), str)
                    or choice['id'] in choices):
                valid = False
                break
            choices[choice['id']] = {k: v for k, v in choice.items() if k != 'id'}
    rows = {'c' + str(i): row for i, row in enumerate(baseline['catalysts'], 1)}
    assessment = _assess(rows, choices) if valid else None
    if assessment is None:
        doc.setdefault('reader_presentation', {'version': 33, 'hidden_catalysts': [],
                                              'hidden_next_event': None})
        doc['reader_presentation']['warning'] = 'invalid_editorial_assessment_preserved_previous_view'
        return
    _install(doc, assessment, review['hide_next_event'])
    # Visibility of the event is bound to the reviewed baseline, not a new event.
    from src.local_runner.reader_report import event_key
    event = baseline.get('next_event')
    doc['reader_presentation']['hidden_next_event'] = (
        event_key(event) if event and review['hide_next_event'] else None)


def visible_catalysts(doc):
    from src.local_runner.reader_report import event_key
    presentation = doc.get('reader_presentation') or {}
    assessment = presentation.get('assessments') or {}
    facts = {event_key(e) for e in doc['catalysts']}
    # A brief may summarize covered members. Do not reuse it after a member
    # changed/disappeared: its source group no longer has the same identity.
    if not set(assessment).issubset(facts):
        return deepcopy(doc['catalysts'])
    hidden = set(presentation.get('hidden_catalysts', []))
    result = []
    for row in doc['catalysts']:
        key = event_key(row)
        if key in hidden:
            continue
        copy = deepcopy(row)
        selected = assessment.get(key) or {}
        if selected.get('role') == 'driver':
            copy['description'] = selected['brief']
        result.append(copy)
    return result
