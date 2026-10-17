"""Narrow deterministic patch repairs; never change levels or model judgments."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import math
import re

from src.common.analysis_validator import _extract_line_value, extract_range
from src.local_runner.report_dates import parse_report_date

SNAPSHOT_LABELS = ('Snapshot técnico congelado', 'Snapshot técnico', 'Instantánea técnica', 'Snapshot')


def contiguous_editable_spans(markdown, allowed):
    """Adjacent editable fields may share an edit, but never protected prose."""
    merged = []
    for left, right in sorted(allowed):
        if merged and (left <= merged[-1][1] or not markdown[merged[-1][1]:left].strip()):
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    return merged


def locate_report_date_edit(baseline, before, after, context, layout):
    """Resolve only an exact bare report-date edit, not arbitrary duplicates.

    The policy already requires the maintenance date to equal prepared_at.
    Other occurrences (snapshot/catalyst/history) are explicitly untouched.
    """
    if context.get('routing_revision', 1) < 4:
        return None
    spelling = r'(?:\d{2}[-/]\d{2}[-/]\d{4}|\d{4}-\d{2}-\d{2})'
    if not re.fullmatch(spelling, before) or not re.fullmatch(spelling, after):
        return None
    try:
        day = datetime.fromisoformat(str(context.get('prepared_at') or '').replace('Z', '+00:00')).date()
    except ValueError:
        return None
    if parse_report_date(after) != day:
        return None
    field = (_extract_line_value(baseline, 'Fecha del análisis') or '').strip().strip('*').strip()
    if field != before or parse_report_date(before) is None or parse_report_date(before) > day:
        return None
    summary_start = layout['sections'][0][1]
    matches = []
    for start, end, raw, clean in layout['lines']:
        if start < summary_start and clean.split(':', 1)[0].casefold() == 'fecha del análisis' and raw.count(before) == 1:
            position = start + raw.index(before)
            matches.append((position, position + len(before)))
    return matches[0] if len(matches) == 1 else None


def refresh_level_percentages(candidate, context, labels):
    """Percentages are derived data: exact selected ranges / frozen price.

    Never select/round a level, fix a stop or infer an origin. Revision 8 also
    renders absent percentage slots from the exact selected numeric range;
    partial/extra slots and malformed layouts still fail. Full validation follows.
    """
    if context.get('routing_revision', 1) < 4:
        return candidate, []
    price = (context.get('slim') or {}).get('latest_price')
    if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
        raise ValueError('update_not_allowed_current_price_unavailable')
    price_decimal = Decimal(str(price))
    replacements, audit, offset = [], [], 0
    for raw in candidate.splitlines(keepends=True):
        clean = raw.strip().lstrip('-*•# ').replace('*', '').strip()
        label = clean.split(':', 1)[0]
        if label in labels:
            zone = extract_range(candidate, label)
            if zone is not None:
                found = list(re.finditer(r'([+−-]?\d+(?:[.,]\d+)?)\s*%', raw))
                levels = [zone.lower] if zone.lower == zone.upper else [zone.lower, zone.upper]
                if not found and context.get('routing_revision', 1) >= 8:
                    # Only a complete leading numeric level field qualifies.
                    # Do not append arithmetic to absent zones or prose claims.
                    head = re.match(r'^\s*[-*• ]*[^:\n]+:\s*\**\$?\s*\d+(?:[.,]\d+)*'
                                    r'(?:\s*(?:-|–|—|a)\s*\$?\s*\d+(?:[.,]\d+)*)?\**', raw)
                    if head is None:
                        raise ValueError('update_not_allowed_missing_level_percentages')
                    rendered = ['{:.2f}%'.format(((Decimal(str(level)) / price_decimal - 1) * 100)
                        .quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)) for level in levels]
                    suffix = ' (' + ' a '.join(rendered) + ')'
                    replacements.append((offset + head.end(), offset + head.end(), suffix))
                    audit.append({'method': 'render_missing_derived_level_percentages', 'field': label,
                        'levels': levels, 'price': price, 'after': suffix, 'source': '/slim/latest_price',
                        'line_sha256': hashlib.sha256(raw.encode()).hexdigest()})
                    offset += len(raw)
                    continue
                if len(found) != len(levels):
                    raise ValueError('update_not_allowed_missing_level_percentages')
                for match, level in zip(found, levels):
                    before = match[1]
                    precision = len(re.split(r'[.,]', before)[1]) if re.search(r'[.,]', before) else 0
                    exact = (Decimal(str(level)) / price_decimal - 1) * 100
                    rounded = exact.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
                    after = format(rounded, f'.{precision}f')
                    if ',' in before:
                        after = after.replace('.', ',')
                    if before.startswith('+') and rounded >= 0:
                        after = '+' + after
                    if before.startswith('−'):
                        after = after.replace('-', '−')
                    if before != after:
                        replacements.append((offset + match.start(1), offset + match.end(1), after))
                        audit.append({'method': 'exact_level_percentage_calculation', 'field': label,
                            'before': before, 'after': after, 'level': level, 'price': price,
                            'source': '/slim/latest_price', 'line_sha256': hashlib.sha256(raw.encode()).hexdigest()})
        offset += len(raw)
    for start, end, after in reversed(replacements):
        candidate = candidate[:start] + after + candidate[end:]
    return candidate, audit


def refresh_inherited_snapshot(baseline, candidate, context, old_layout, new_layout):
    """Refresh a byte-identical visible timestamp proven by the old slim.

    Only front-matter snapshot fields, not dates inside historical judgments.
    Explicit model changes, malformed/multiple times or an unproven old banner
    remain untouched for the existing gate to reject. No fabricated timestamp.
    """
    if context.get('routing_revision', 1) < 4:
        return candidate, []
    try:
        old_at = datetime.fromisoformat(str((context.get('reference') or {}).get('slim_snapshot', {}).get('as_of') or '').replace('Z', '+00:00'))
        new_at = datetime.fromisoformat(str((context.get('slim') or {}).get('as_of') or '').replace('Z', '+00:00'))
        if old_at.tzinfo is None or new_at.tzinfo is None or new_at < old_at:
            return candidate, []
        old_at, new_at = old_at.astimezone(timezone.utc), new_at.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return candidate, []
    fields = tuple(label.casefold() for label in SNAPSHOT_LABELS if label != 'Snapshot')
    for label in fields:
        old_lines = [(a, b, raw) for a, b, raw, clean in old_layout['lines']
                     if a < old_layout['sections'][0][1] and clean.split(':', 1)[0].casefold() == label]
        new_lines = [(a, b, raw) for a, b, raw, clean in new_layout['lines']
                     if a < new_layout['sections'][0][1] and clean.split(':', 1)[0].casefold() == label]
        if len(old_lines) != 1 or len(new_lines) != 1 or old_lines[0][2] != new_lines[0][2]:
            continue
        start, end, raw = new_lines[0]
        dates = list(re.finditer(r'\d{2}[-/]\d{2}[-/]\d{4}|\d{4}-\d{2}-\d{2}', raw))
        times = list(re.finditer(r'\d{2}:\d{2}(?::\d{2})?', raw))
        if len(dates) != 1 or len(times) != 1 or parse_report_date(dates[0][0]) != old_at.date():
            continue
        date, time = dates[0], times[0]
        fmt = '%H:%M:%S' if time[0].count(':') == 2 else '%H:%M'
        if time[0] != old_at.strftime(fmt):
            continue
        date_fmt = '%Y-%m-%d' if date[0][4:5] == '-' else '%d/%m/%Y' if '/' in date[0] else '%d-%m-%Y'
        updated = raw
        for a, b, value in sorted(((date.start(), date.end(), new_at.strftime(date_fmt)),
                                   (time.start(), time.end(), new_at.strftime(fmt))), reverse=True):
            updated = updated[:a] + value + updated[b:]
        if updated != raw:
            return candidate[:start] + updated + candidate[end:], [{
                'method': 'exact_inherited_snapshot_refresh', 'field': label,
                'source': '/slim/as_of', 'old_source': '/reference/slim_snapshot/as_of',
                'old': old_at.isoformat(), 'new': new_at.isoformat(),
                'before_sha256': hashlib.sha256(raw.encode()).hexdigest()}]
    return candidate, []


def refresh_derived_market_fields(baseline, candidate, context, layout):
    """Revision 8 owns reference price, positional state and inherited quotes.

    These are arithmetic/metadata, not model judgments. Levels, stops, prose,
    source data and the full Sol anchor never change. Explicit bad prices or
    unproven quote banners are left for the ordinary gates to reject.
    """
    if context.get('routing_revision', 1) < 8:
        return candidate, []
    slim = context.get('slim') or {}
    price = slim.get('latest_price')
    if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
        raise ValueError('update_not_allowed_current_price_unavailable')
    edits, audit = [], []
    for start, end, raw, clean in layout['lines']:
        label = clean.split(':', 1)[0]
        updated = raw
        if label == 'Precio de referencia' and start < layout['sections'][0][1]:
            inherited = [line for line in baseline.splitlines(keepends=True)
                         if line.strip().lstrip('-*•# ').replace('*', '').split(':', 1)[0].strip() == label]
            if len(inherited) == 1 and raw == inherited[0]:
                match = re.search(r':\s*\**\$?\s*(\d+(?:[.,]\d+)*)', raw)
                old_price = (context.get('reference') or {}).get('slim_snapshot', {}).get('latest_price')
                if match and isinstance(old_price, (int, float)) and not isinstance(old_price, bool) and math.isfinite(old_price):
                    token = match[1]
                    # A separator may be decimal or thousands; frozen old data
                    # disambiguates it, never a guessed locale.
                    choices = [Decimal(token.replace(',', '.'))] if token.count(',') + token.count('.') <= 1 else []
                    choices.append(Decimal(token.replace(',', '').replace('.', '')))
                    if Decimal(str(old_price)) in choices:
                        updated = raw[:match.start(1)] + format(Decimal(str(price)), 'f') + raw[match.end(1):]
        elif label == 'Estado actual':
            zone = extract_range(candidate, 'Entrada')
            match = re.search(r':\s*\**(por encima|por debajo|dentro)(?: de la zona)?'
                              r'(?: según el mid(?: de \$?\d+(?:[.,]\d+)*)?)?', raw, re.IGNORECASE)
            if zone is not None and match:
                state = 'por encima' if price > zone.upper else 'por debajo' if price < zone.lower else 'dentro'
                replacement = state + ' de la zona'
                if 'según el mid' in match[0].casefold():
                    replacement += ' según el mid'
                updated = raw[:match.start(1)] + replacement + raw[match.end():]
        elif label == 'Snapshot' and start < layout['sections'][0][1]:
            # Verify the complete old banner against its old snapshot before
            # copying current quote values. Never excuse a fabricated quote.
            inherited = [line for line in baseline.splitlines(keepends=True) if line == raw]
            field = quote_snapshot_field(layout)
            old_slim = (context.get('reference') or {}).get('slim_snapshot') or {}
            if field is not None and inherited:
                try:
                    validate_quote_snapshot(layout, {'slim': old_slim})
                    at = datetime.fromisoformat(str(slim.get('as_of') or '').replace('Z', '+00:00'))
                    old_at = datetime.fromisoformat(str(old_slim.get('as_of') or '').replace('Z', '+00:00'))
                    if at.tzinfo is None or old_at.tzinfo is None or at < old_at:
                        raise ValueError('unproven_time')
                    at = at.astimezone(timezone.utc)
                    values = {'date': at.strftime('%d-%m-%Y'), 'time': at.strftime('%H:%M')}
                    for key in ('bid', 'ask', 'spread'):
                        token = field[2][key]
                        source = (slim.get('market_state') or {}).get('spread_pct' if key == 'spread' else key)
                        if isinstance(source, bool) or not isinstance(source, (int, float)) or not math.isfinite(source):
                            raise ValueError('unproven_quote')
                        precision = len(token.partition('.')[2])
                        values[key] = format(Decimal(str(source)).quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP), f'.{precision}f')
                    # Match locations are in clean text: replace complete field,
                    # retaining its exact surrounding Markdown delimiters.
                    old_clean, new_clean = clean, clean
                    for key, token in sorted(((key, field[2].span(key)) for key in values), key=lambda pair: pair[1][0], reverse=True):
                        a, b = token
                        new_clean = new_clean[:a] + values[key] + new_clean[b:]
                    updated = raw.replace(old_clean, new_clean, 1)
                except (ValueError, TypeError):
                    pass  # Validation still rejects stale/unproven banners.
        if updated != raw:
            edits.append((start, end, updated))
            audit.append({'method': 'render_derived_market_field', 'field': label,
                'before_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                'after_sha256': hashlib.sha256(updated.encode()).hexdigest(), 'source': '/slim'})
    for start, end, updated in reversed(edits):
        candidate = candidate[:start] + updated + candidate[end:]
    return candidate, audit


def validate_typed_snapshot_fields(layout, context):
    '''Validate each recognised front-matter timestamp as data, not a substring.'''
    if context.get('routing_revision', 1) < 8:
        return
    fields = [row for row in layout['lines'] if row[0] < layout['sections'][0][1]
              and row[3].split(':', 1)[0].casefold() in
              {label.casefold() for label in SNAPSHOT_LABELS if label != 'Snapshot'}]
    if not fields:
        return
    try:
        at = datetime.fromisoformat(str((context.get('slim') or {}).get('as_of') or '').replace('Z', '+00:00'))
        if at.tzinfo is None: raise ValueError()
        at = at.astimezone(timezone.utc)
    except (TypeError, ValueError):
        raise ValueError('update_not_allowed_missing_snapshot_time') from None
    seen = set()
    for _, _, raw, clean in fields:
        label = clean.split(':', 1)[0].casefold()
        if label in seen:
            raise ValueError('update_not_allowed_ambiguous_snapshot_banner')
        seen.add(label)
        dates = re.findall(r'\d{2}[-/]\d{2}[-/]\d{4}|\d{4}-\d{2}-\d{2}', clean)
        times = re.findall(r'\d{2}:\d{2}(?::\d{2})?', clean)
        if len(dates) != 1 or len(times) != 1:
            raise ValueError('update_not_allowed_ambiguous_snapshot_banner')
        fmt = '%H:%M:%S' if times[0].count(':') == 2 else '%H:%M'
        if parse_report_date(dates[0]) != at.date() or times[0] != at.strftime(fmt):
            raise ValueError('update_not_allowed_stale_snapshot_banner')


def normalize_factor_qualifier(candidate, context):
    """A final absence disclaimer is not a fifth evidence factor.

    Only these observed, explicit negative qualifiers are punctuation-normalized;
    a genuine fifth factor stays untouched and fails the full report validator.
    """
    if context.get('routing_revision', 1) < 4:
        return candidate, []
    qualifiers = {
        'sin dominio excepcional demostrado frente a vecinos.',
        'rechazos históricos no disponibles y ningún POC/HVN a ≤5% del bloque.',
    }
    changes, result = [], []
    for raw in candidate.splitlines(keepends=True):
        clean = raw.strip().lstrip('-*•# ').replace('*', '').strip()
        if (re.match(r'^Factores de (?:Entrada|Entrada ambiciosa|Resistencia):', clean)
                and raw.count(';') == 4
                and raw.rsplit(';', 1)[1].strip().replace('*', '') in qualifiers
                and all(part.strip() for part in raw.split(';'))):
            position = raw.rfind(';')
            updated = raw[:position] + ',' + raw[position + 1:]
            changes.append({'method': 'negative_factor_qualifier_separator',
                            'before_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                            'after_sha256': hashlib.sha256(updated.encode()).hexdigest()})
            raw = updated
        result.append(raw)
    return ''.join(result), changes


_QUOTE_SNAPSHOT = re.compile(
    r'^Snapshot: (?P<date>\d{2}-\d{2}-\d{4}), (?P<time>\d{2}:\d{2}) UTC\. '
    r'Mid indicativo; bid \$(?P<bid>\d+\.\d{2,}), ask \$(?P<ask>\d+\.\d{2,}) '
    r'y spread (?P<spread>\d+\.\d{3,})%\. No se utilizan precios web\.$')


def quote_snapshot_field(layout):
    lines = [(a, b, raw, clean) for a, b, raw, clean in layout['lines']
             if clean.split(':', 1)[0].casefold() == 'snapshot']
    if not lines:
        return None
    if len(lines) != 1 or lines[0][0] >= layout['sections'][0][1]:
        raise ValueError('update_not_allowed_ambiguous_quote_snapshot')
    start, end, raw, clean = lines[0]
    match = _QUOTE_SNAPSHOT.fullmatch(clean)
    if match is None:
        raise ValueError('update_not_allowed_unrecognized_quote_snapshot')
    return start, end, match


def validate_quote_snapshot(layout, context):
    field = quote_snapshot_field(layout)
    if field is None:
        return
    _, _, match = field
    slim = context.get('slim') or {}
    try:
        market_at = datetime.fromisoformat(str(slim.get('as_of') or '').replace('Z', '+00:00'))
        if market_at.tzinfo is None:
            raise ValueError()
        market_at = market_at.astimezone(timezone.utc)
    except ValueError:
        raise ValueError('update_not_allowed_missing_snapshot_time') from None
    if match['date'] != market_at.strftime('%d-%m-%Y') or match['time'] != market_at.strftime('%H:%M'):
        raise ValueError('update_not_allowed_stale_snapshot_banner')
    state = slim.get('market_state') or {}
    for field_name, source_name in (('bid', 'bid'), ('ask', 'ask'), ('spread', 'spread_pct')):
        value, token = state.get(source_name), match[field_name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('update_not_allowed_unproven_quote_snapshot')
        precision = len(token.partition('.')[2])
        rounded = Decimal(str(value)).quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
        if Decimal(token) != rounded:
            raise ValueError('update_not_allowed_stale_quote_snapshot')
