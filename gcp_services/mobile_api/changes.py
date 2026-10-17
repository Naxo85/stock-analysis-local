"""Material differences for the mobile feed, based on published report history."""
from __future__ import annotations

from datetime import date, timedelta
from difflib import SequenceMatcher
import math
import re
import unicodedata


MATERIAL_CATALYST_IMPACT = 7
NEW_CATALYST_MAX_AGE_DAYS = 7
MATERIAL_THESIS_DELTA = 0.5
MATERIAL_TARGET_CHANGE = 0.15
STATUS_PATTERNS = {
    'approved': r'\b(?:aprueb\w*|aprob\w*|autoriz\w*)\b',
    'cancelled': r'\b(?:cancel\w*|anulad\w*)\b',
    'delayed': r'\b(?:retras\w*|aplaz\w*|pospon\w*)\b',
    'resolved': r'\b(?:resuel\w*|resolv\w*|resuelt\w*)\b',
    'completed': r'\b(?:complet\w*|finaliz\w*|cerrad\w*)\b',
    'failed': r'\b(?:fall\w*|deneg\w*|rechaz\w*)\b',
    'suspended': r'\b(?:suspend\w*|suspens\w*)\b',
}
TARGET_FROM_RE = re.compile(r'\bfrom\s+\$([\d,.]+)', re.IGNORECASE)
PRICE_SUPPORT_RE = re.compile(r'\b(?:soporte|resistencia)\s+(?:de|en)\s*\$?\d', re.IGNORECASE)
TITLE_NUMBER_RE = re.compile(r'\d+(?:[.,]\d+)?')


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def _visible_title(value):
    return re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', str(value or ''))


def _normalize(value):
    readable = _visible_title(value)
    plain = unicodedata.normalize('NFKD', readable).casefold()
    plain = plain.encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', plain)).strip()


def _similarity(left, right):
    return SequenceMatcher(None, _normalize(left), _normalize(right)).ratio()


def _date(value):
    try:
        return date.fromisoformat(str(value or '')[:10])
    except ValueError:
        return None


def _statuses(item):
    # Explanations are freely paraphrased and may discuss a future outcome.
    normalized = _normalize(item.get('title'))
    return frozenset(name for name, pattern in STATUS_PATTERNS.items() if re.search(pattern, normalized))


def _source_url(item):
    match = re.search(r'\]\((https?://[^)]+)\)', str(item.get('title') or ''))
    return match.group(1).rstrip('/') if match else None


def _title_numbers(item):
    return sorted(number.replace(',', '.') for number in TITLE_NUMBER_RE.findall(_visible_title(item.get('title'))))


def _same_catalyst(current, previous, current_items, previous_items):
    current_url = _source_url(current)
    previous_url = _source_url(previous)
    same_date = bool(current.get('date') and current.get('date') == previous.get('date'))
    similarity = _similarity(current['title'], previous['title'])
    if current_url and previous_url and current_url == previous_url:
        # A single document may describe several events; keep their dates or topics distinct.
        return same_date or similarity >= .65
    if similarity >= .72 or (same_date and similarity >= .45):
        return True
    shared_terms = (set(word for word in _normalize(current['title']).split() if len(word) >= 5)
                    & set(word for word in _normalize(previous['title']).split() if len(word) >= 5))
    if same_date and shared_terms:
        current_on_date = sum(item.get('date') == current['date'] for item in current_items)
        previous_on_date = sum(item.get('date') == current['date'] for item in previous_items)
        return current_on_date == previous_on_date == 1
    return False


def _technical_only(item):
    title = str(item.get('title') or '')
    normalized = _normalize(title)
    return bool(PRICE_SUPPORT_RE.search(title) or
                any(phrase in normalized for phrase in ('entrada ambiciosa', 'washout', 'debilidad tecnica',
                                                       'presion tecnica', 'fuerza relativa', 'gamma negativa',
                                                       'tape debil', 'rsi', 'macd')))


def previous_report(history, current_at):
    entries = history.get('entries', []) if isinstance(history, dict) else []
    eligible = [entry for entry in entries if isinstance(entry, dict)
                and entry.get('analysis_status') == 'ok'
                and str(entry.get('generated_at') or '') < str(current_at or '')]
    return max(eligible, key=lambda item: str(item.get('generated_at') or ''), default=None)


def _entry(kind, change_type, title, detail='', impact=None, event_date=None, at=None):
    return {'kind': kind, 'change_type': change_type, 'title': title, 'detail': detail,
            'impact': impact, 'event_date': event_date, 'at': at}


def _recent_new_catalyst(item, at):
    event_day = _date(item.get('date'))
    analysis_day = _date(at)
    return not event_day or not analysis_day or event_day >= analysis_day - timedelta(days=NEW_CATALYST_MAX_AGE_DAYS)


def _catalyst_changes(current, previous, at):
    current_items = [item for item in current if isinstance(item, dict) and item.get('title') and not _technical_only(item)]
    previous_items = [item for item in previous if isinstance(item, dict) and item.get('title') and not _technical_only(item)]
    result = []
    used = set()
    for item in current_items:
        candidates = [(index, old) for index, old in enumerate(previous_items) if index not in used]
        matching = [(index, old) for index, old in candidates
                    if _same_catalyst(item, old, current_items, previous_items)]
        best = max(matching, key=lambda pair: (
            int(bool(_source_url(item)) and _source_url(item) == _source_url(pair[1])),
            int(bool(item.get('date')) and item.get('date') == pair[1].get('date')),
            _similarity(item['title'], pair[1]['title'])), default=None)
        old = None
        if best is not None:
            index, candidate = best
            used.add(index)
            old = candidate
        impact = _number(item.get('impact'))
        old_impact = _number(old.get('impact')) if old else None
        if old is None:
            if impact is not None and abs(impact) >= MATERIAL_CATALYST_IMPACT and _recent_new_catalyst(item, at):
                result.append(_entry('catalyst', 'new', item['title'], item.get('explanation') or '', impact, item.get('date'), at))
            continue
        if max(abs(impact or 0), abs(old_impact or 0)) < MATERIAL_CATALYST_IMPACT:
            continue
        date_changed = bool(item.get('date') and old.get('date') and item['date'] != old['date'])
        status_changed = _statuses(item) != _statuses(old) and bool(_statuses(item))
        old_numbers = _title_numbers(old)
        new_numbers = _title_numbers(item)
        numbers_changed = bool(old_numbers and new_numbers and len(old_numbers) == len(new_numbers)
                               and old_numbers != new_numbers)
        if date_changed or status_changed or numbers_changed:
            previous_detail = []
            if numbers_changed:
                previous_detail.append(f"Titular anterior: {old['title']}.")
            if date_changed:
                previous_detail.append(f"Fecha anterior: {old['date']}.")
            detail = ' '.join(part for part in [item.get('explanation') or '', *previous_detail] if part)
            result.append(_entry('catalyst', 'updated', item['title'], detail, impact, item.get('date'), at))
    analysis_day = _date(at)
    for index, old in enumerate(previous_items):
        impact = _number(old.get('impact'))
        event_day = _date(old.get('date'))
        if index not in used and impact is not None and abs(impact) >= MATERIAL_CATALYST_IMPACT and event_day and analysis_day and event_day >= analysis_day:
            result.append(_entry('catalyst', 'removed', f"Deja de figurar: {old['title']}",
                                 'No aparece en el último informe. La ausencia no confirma que se haya cancelado; revisa el análisis.',
                                 impact, old.get('date'), at))
    return result


def _event_change(current, previous, at):
    if not isinstance(current, dict) or not current.get('title') or current.get('is_routine_market_event'):
        return []
    event_day = _date(current.get('date'))
    analysis_day = _date(at)
    if not event_day or (analysis_day and event_day < analysis_day):
        return []
    old = previous if isinstance(previous, dict) and previous.get('title') else None
    if old is None:
        return [_entry('event', 'new', current['title'], current.get('explanation') or '', event_date=current.get('date'), at=at)]
    same_title = _similarity(current['title'], old['title']) >= .72
    date_changed = current.get('date') != old.get('date')
    status_changed = _statuses(current) != _statuses(old) and bool(_statuses(current))
    if same_title and not date_changed and not status_changed:
        return []
    detail = current.get('explanation') or ''
    if date_changed and old.get('date'):
        detail = f"{detail} Fecha anterior: {old['date']}.".strip()
    if not same_title:
        detail = f"{detail} Sustituye: {old['title']}.".strip()
    return [_entry('event', 'updated', current['title'], detail, event_date=current.get('date'), at=at)]


def _thesis_change(report, previous, at):
    decision = report.get('decision') or {}
    current = _number(decision.get('thesis_score'))
    old = _number(previous.get('thesis_score')) if isinstance(previous, dict) else None
    if current is None or old is None or abs(current - old) < MATERIAL_THESIS_DELTA:
        return []
    title = f'Tesis {old:g} → {current:g}'
    return [_entry('score', 'updated', title, decision.get('thesis_reason') or decision.get('narrative') or '', at=at)]


def _analyst_changes(report, at):
    source = report.get('analyst_recent_actions') or {}
    if source.get('status') != 'ok':
        return []
    result = []
    seen = set()
    for action in source.get('actions') or []:
        if not isinstance(action, dict):
            continue
        kind = action.get('event_type')
        firm = str(action.get('firm') or '').strip()
        published = action.get('published_at')
        if not firm or not published or (at and str(published) > str(at)):
            continue
        identity = action.get('articleId') or (firm, kind, published)
        if identity in seen:
            continue
        seen.add(identity)
        rating = str(action.get('rating') or '').strip()
        target = _number(action.get('target'))
        if kind in ('rating_upgraded', 'rating_downgraded'):
            verb = 'mejora' if kind == 'rating_upgraded' else 'rebaja'
            title = f'{firm} {verb} su recomendación' + (f' a {rating}' if rating else '')
        elif kind in ('price_target_raised', 'price_target_lowered') and target is not None:
            match = TARGET_FROM_RE.search(str(action.get('headline') or ''))
            try:
                previous = float(match[1].replace(',', '')) if match else None
            except ValueError:
                previous = None
            if not previous or abs(target / previous - 1) < MATERIAL_TARGET_CHANGE:
                continue
            verb = 'sube' if kind == 'price_target_raised' else 'recorta'
            title = f'{firm} {verb} su precio objetivo a ${target:g}'
        else:
            continue
        result.append(_entry('analyst', kind, title, action.get('headline') or '', at=published))
    return result


def material_changes(report, history=None):
    """Return only meaningful news from a valid published report."""
    at = report.get('generated_at')
    previous = previous_report(history, at)
    output = []
    if previous is not None:
        output.extend(_thesis_change(report, previous, at))
        if isinstance(previous.get('catalysts'), list) and all(isinstance(item, dict) for item in previous['catalysts']):
            output.extend(_catalyst_changes(report.get('catalysts') or [], previous['catalysts'], at))
        else:
            for item in (report.get('changes') or {}).get('new_catalysts') or []:
                impact = _number(item.get('impact')) if isinstance(item, dict) else None
                if impact is not None and abs(impact) >= MATERIAL_CATALYST_IMPACT and not _technical_only(item) and _recent_new_catalyst(item, at):
                    output.append(_entry('catalyst', 'new', item.get('title') or '', item.get('explanation') or '', impact, item.get('date'), at))
        if previous.get('next_event') is None or isinstance(previous.get('next_event'), dict):
            output.extend(_event_change(report.get('next_event'), previous.get('next_event'), at))
    else:
        # Older archives may be absent. The report's own comparison is still useful.
        delta = report.get('changes') or {}
        if delta.get('score_change_material') and not delta.get('score_basis_changed'):
            impact = _number(delta.get('score_delta'))
            if impact is not None and abs(impact) >= MATERIAL_THESIS_DELTA:
                old = _number(delta.get('previous_score'))
                current = _number((report.get('decision') or {}).get('thesis_score'))
                if old is not None and current is not None:
                    output.append(_entry('score', 'updated', f'Tesis {old:g} → {current:g}',
                                         (report.get('decision') or {}).get('thesis_reason') or '', at=at))
        for item in delta.get('new_catalysts') or []:
            impact = _number(item.get('impact')) if isinstance(item, dict) else None
            if impact is not None and abs(impact) >= MATERIAL_CATALYST_IMPACT and not _technical_only(item) and _recent_new_catalyst(item, at):
                output.append(_entry('catalyst', 'new', item.get('title') or '', item.get('explanation') or '', impact, item.get('date'), at))
    output.extend(_analyst_changes(report, at))
    return output
