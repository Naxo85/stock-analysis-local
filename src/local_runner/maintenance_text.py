"""Publication text is an explicit edit, never an internal routing comment."""


def note_edit(payload, revision):
    if revision >= 20:
        return (payload.get('update') or {}).get('public_note')
    text = payload.get('routine_note', '')
    review = (((payload.get('update') or {}).get('change_review') or {}).get('routine_note'))
    return {'text': text, 'review': review} if text else None


def note_text(payload, revision):
    return (note_edit(payload, revision) or {}).get('text', '')


def explanation_texts(explanation):
    if not explanation:
        return []
    values = [explanation.get('setup_reason'), explanation.get('conclusion'),
              *(explanation.get('reasons') or {}).values()]
    return [text for value in values if (text := value.get('text') if isinstance(value, dict) else value)
            and isinstance(text, str) and text.strip()]


def individual_text_edits(explanation):
    if not explanation:
        return {}
    return {key: value for key, value in {**explanation.get('reasons', {}),
            'setup_reason': explanation.get('setup_reason'), 'conclusion': explanation.get('conclusion')}.items()
            if isinstance(value, dict)}


def unpack_explanation(explanation):
    """Internal adapter only; the original response/receipt is never changed."""
    if explanation is None:
        return None
    def text(value):
        return value['text'] if isinstance(value, dict) else value
    return {'setup_reason': text(explanation['setup_reason']), 'conclusion': text(explanation['conclusion']),
            'reasons': {key: text(value) for key, value in explanation['reasons'].items()}}


def unchanged_text_update(payload, context):
    """Exact equality only; no classifier of semantic equivalence or materiality."""
    from src.local_runner.semantic_report import reference_document
    from src.local_runner.text_provenance import texts
    change = payload['update']
    if any(value is not None for value in change['plan'].values()):
        return False
    doc = reference_document(context['reference'], verify_projection=True)
    if change['setup_score'] is not None and change['setup_score'] != doc['summary']['setup_score']:
        return False
    prior = texts(doc)
    for key in ('setup_reason', 'conclusion'):
        if change[key] is not None and change[key] != prior[key]:
            return False
    for key, edit in individual_text_edits(change.get('plan_explanation')).items():
        if edit['text'].strip() and edit['text'] != prior[key]:
            return False
    note = change.get('public_note')
    if note is not None and note['text'].strip() and note['text'] != doc.get('routine_note', ''):
        return False
    return True
