"""Published review memory, independent of report age and full Sol age.

Only published reviews enter the next input, including retain. Flat exact-content
deduplication avoids nested audit graphs; this is NOT a cached routing verdict.
"""
from copy import deepcopy

from src.local_runner.adaptive_cache import digest, reference_key


def read_memory(reference, anchor):
    saved = reference.get('review_memory')
    if saved is None:
        return {'articles': {}, 'reviews': {}, 'research': {}}
    if (not isinstance(saved, dict) or saved.get('version') != 1
            or saved.get('report_key') != reference_key(reference)
            or saved.get('anchor_key') != reference_key(anchor)
            or not isinstance(saved.get('data'), dict)
            or saved.get('data_sha256') != digest(saved['data'])
            or not isinstance(saved['data'].get('articles'), dict)
            or not isinstance(saved['data'].get('reviews'), dict)
            or not isinstance(saved['data'].get('research'), dict)):
        raise ValueError('invalid_published_review_memory')
    return deepcopy(saved['data'])


def rebind_memory(previous, payload, anchor):
    """Carry authenticated history across a non-model correction, not a new review.

    Validate the old binding first. Never bless an arbitrary digest on a changed
    report, refresh review dates, invent coverage, or reset the full-report epoch.
    """
    data = read_memory(previous, anchor)
    return {'version': 1, 'report_key': reference_key(payload),
            'anchor_key': reference_key(anchor), 'data': data,
            'data_sha256': digest(data)}


def build_memory(context, payload, review):
    regenerated = review['status'] == 'regenerated'
    anchor = payload if regenerated else context.get('sol_reference', context['reference'])
    # Full Sol consumed the prior history; start a new review epoch.
    data = {'articles': {}, 'reviews': {}, 'research': {}} if regenerated else read_memory(context['reference'], anchor)
    triage = context.get('triage')
    if isinstance(triage, dict):
        article_keys = []
        for article in (context.get('news') or {}).get('items', []):
            key = digest(article)
            data['articles'][key] = deepcopy(article)
            article_keys.append(key)
        # Identical feeds replace their dated assessment, not an ever-growing
        # stream of repeated snapshots. Changed contents remain distinct.
        key = digest(sorted(set(article_keys)))
        data['reviews'][key] = {
            'reviewed_at': review['reviewed_at'], 'article_keys': sorted(set(article_keys)),
            'outcome': review['status'], 'news_assessment': deepcopy(triage.get('news')),
            'decision_reason': triage.get('reason'),
            'published_note': ((triage.get('update') or {}).get('public_note') or {}).get('text')
                if context.get('routing_revision', 1) >= 20 and review['status'] == 'updated' else
                triage.get('routine_note') if review['status'] == 'updated' else None,
            'meaning': ('Historical model assessment, not independently verified fact or a current '
                        'routing instruction. A Sol outcome is NOT endorsement of the Luna reason.'),
        }
        # Keep discovery evidence independently of the latest assessment of a
        # feed. A later no-search retain must not erase earlier useful excerpts.
        for call in ((context.get('news') or {}).get('luna_research') or {}).get('calls', []):
            for source in call.get('sources', []):
                observations = source.get('observations') or [source]
                for observation in observations:
                    evidence = {k: deepcopy(observation.get(k)) for k in
                                ('url', 'title', 'excerpt', 'page_content', 'published_at')}
                    evidence['url'] = evidence['url'] or source.get('url')
                    if not evidence['url']:
                        continue
                    source_key = digest(evidence)
                    data['research'].setdefault(source_key, {
                        **evidence, 'retrieved_at': observation.get('retrieved_at') or call.get('retrieved_at'),
                        'meaning': 'Historical tool excerpt, not independent verification; retrieval is not event date.'})
    if context.get('routing_revision', 1) >= 18:
        from src.local_runner.review_contract import save_review_coverage
        if isinstance(triage, dict) and not regenerated:
            save_review_coverage(data, context, triage, review['reviewed_at'])
        data['latest_review'] = {
            'reviewed_at': review['reviewed_at'], 'outcome': review['status'],
            'owned': context.get('owned'), 'slim_snapshot': deepcopy(context['slim']),
            'assessments': {key: deepcopy(triage.get(key)) for key in
                ('setup', 'levels', 'news', 'events')} if isinstance(triage, dict) and not regenerated else {},
            'meaning': 'Last published review, including retain. Historical judgment, not proof of correctness; report age and full Sol ITV remain independent.',
        }
    return {'version': 1, 'report_key': reference_key(payload), 'anchor_key': reference_key(anchor),
            'data': data, 'data_sha256': digest(data)}


def memory_view(context):
    reference = context.get('reference') or {}
    data = read_memory(reference, context.get('sol_reference', reference))
    articles = (context.get('news') or {}).get('items', [])
    return {
        'meaning': ('Already assessed is not newly occurred, not proof of immateriality and not '
                    'permission to skip current review. Check changed facts, exposure and omissions. '
                    'Retain reviews do not change report dates or reset ITV.'),
        'current_items': [{'pointer': '/news/items/' + str(i),
                           'previously_assessed_exact_content': (
                               'article:' + digest(item) in data.get('coverage', {})
                               if context.get('routing_revision', 1) >= 18 else digest(item) in data['articles'])}
                          for i, item in enumerate(articles)],
        # Old sources allow comparison of different headlines on the same event.
        'articles': data['articles'], 'reviews': list(data['reviews'].values()),
        'research': list(data['research'].values()),
    }


def maintain_notes(doc, payload, context):
    """Separate durable news clarification from the replaceable technical note.

    Historical notes are dated claims, never refreshed facts. The model maintains
    the cumulative news clarification via its existing note field. Technical-only
    edits cannot erase it. Prior notes stay flat, deduplicated in model history.
    """
    old_note = doc.get('routine_note') or ''
    old_at = (doc.get('metadata') or {}).get('snapshot_at') or context['reference'].get('generated_at')
    if context.get('routing_revision', 1) >= 20:
        old_at = doc.get('routine_note_at') or old_at
    old_scope = ((doc.get('commentary_change_review') or {}).get('routine_note') or {}).get('scope')
    history = deepcopy(doc.get('note_history') or [])
    if old_note and not any(row['text'] == old_note for row in history):
        history.append({'text': old_note, 'as_of': old_at, 'scope': old_scope or 'historical_unknown'})
    doc['note_history'] = history
    if old_note and old_scope == 'routine_news' and not doc.get('news_note'):
        doc['news_note'] = {'text': old_note, 'as_of': old_at}
    from src.local_runner.maintenance_text import note_edit
    edit = note_edit(payload, context.get('routing_revision', 1))
    if context.get('routing_revision', 1) >= 20 and edit is None:
        if old_note:
            doc['routine_note_at'] = old_at
        return  # No publication edit: keep the old note and its original date.
    new_note = (edit or {}).get('text', '')
    new_scope = ((edit or {}).get('review') or {}).get('scope')
    if new_note and new_scope == 'routine_news':
        doc['news_note'] = {'text': new_note, 'as_of': context['slim'].get('as_of')}
    doc['routine_note'] = new_note
    if context.get('routing_revision', 1) >= 20:
        doc['routine_note_at'] = context['slim'].get('as_of') if new_note != old_note else old_at
