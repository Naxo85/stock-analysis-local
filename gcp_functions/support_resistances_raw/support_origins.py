"""Revision41 exact observations of requested dated support origins.

This module performs no I/O and makes no financial viability judgment. A legacy
coordinate is a matching constraint, never substituted for a fresh observation.
"""
from copy import deepcopy
from datetime import date, timedelta
import json
import math
import statistics

try:
    from .market_sessions import market_session
except ImportError:
    from market_sessions import market_session

RANGE = 'range_bottom_3_6m'
GAP = 'gap_up_lower'
METHODS = {RANGE: 'swing_lows_k2_dated_members_v1', GAP: 'strict_bullish_gap_dated_bars_v1'}
MAX_ORIGINS = 64


def _date(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError('invalid_support_origin_date')
    return value


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def canonical_request(item):
    if not isinstance(item, dict) or set(item) - {'type', 'level', 'date', 'touches', 'origin_identity'}:
        raise ValueError('invalid_support_origin_fields')
    kind = item.get('type')
    if kind not in METHODS or not _number(item.get('level')):
        raise ValueError('invalid_support_origin_identity')
    result = {'type': kind, 'level': item['level'], 'date': _date(item.get('date'))}
    if kind == RANGE:
        if type(item.get('touches')) is not int or not 2 <= item['touches'] <= 126:
            raise ValueError('invalid_support_origin_touches')
        result['touches'] = item['touches']
    elif item.get('touches') is not None:
        raise ValueError('gap_origin_has_no_touch_count_identity')
    identity = item.get('origin_identity')
    if identity is not None:
        keys = {'schema_version', 'origin_type', 'method', 'formation_dates', 'confirmation_dates', 'availability_date'}
        if (not isinstance(identity, dict) or set(identity) != keys
                or type(identity['schema_version']) is not int or identity['schema_version'] != 1
                or identity['origin_type'] != kind or identity['method'] != METHODS[kind]):
            raise ValueError('invalid_support_origin_metadata')
        formation, confirmed = identity['formation_dates'], identity['confirmation_dates']
        expected = result['touches'] if kind == RANGE else 2
        if (not isinstance(formation, list) or len(formation) != expected
                or not isinstance(confirmed, list) or len(confirmed) != (expected if kind == RANGE else 1)):
            raise ValueError('invalid_support_origin_dates')
        for value in formation + confirmed:
            _date(value)
        if (formation != sorted(set(formation)) or confirmed != sorted(set(confirmed))
                or formation[-1] != result['date']
                or _date(identity['availability_date']) != confirmed[-1]
                or (kind == GAP and confirmed != [formation[-1]])
                or (kind == RANGE and any(a >= b for a, b in zip(formation, confirmed)))):
            raise ValueError('inconsistent_support_origin_dates')
        result['origin_identity'] = deepcopy(identity)
    return result


def request_key(item):
    return json.dumps(canonical_request(item), sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def parse_support_origins(value):
    if value is None or value == '':
        return []
    if isinstance(value, str):
        if len(value) > 65536:
            raise ValueError('support_origin_request_too_large')
        def unique(pairs):
            result = {}
            for key, child in pairs:
                if key in result:
                    raise ValueError('duplicate_support_origin_json_key')
                result[key] = child
            return result
        try:
            value = json.loads(value, object_pairs_hook=unique)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError('invalid_support_origin_json') from error
    if not isinstance(value, list) or len(value) > MAX_ORIGINS:
        raise ValueError('invalid_support_origin_list')
    records = {request_key(item): canonical_request(item) for item in value}
    return [records[key] for key in sorted(records)]


def valid_bar(row):
    values = [row.get(key) for key in ('open', 'high', 'low', 'close', 'volume')]
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        return False
    op, hi, lo, cl, volume = values
    return lo > 0 and lo <= min(op, cl) <= max(op, cl) <= hi and volume >= 0


def _identity(kind, members, rows):
    positions = {row['date']: index for index, row in enumerate(rows)}
    confirmed = ([rows[positions[value] + 2]['date'] for value in members]
                 if kind == RANGE else [members[-1]])
    return {'schema_version': 1, 'origin_type': kind, 'method': METHODS[kind],
            'formation_dates': members, 'confirmation_dates': confirmed,
            'availability_date': confirmed[-1]}


def _contiguous(rows):
    for before, after in zip(rows, rows[1:]):
        following = date.fromisoformat(before['date']) + timedelta(days=1)
        while not market_session(following):
            following += timedelta(days=1)
        if following.isoformat() != after['date']:
            return False
    return True


def continuous_history(rows, expected_last_session=None):
    """Coverage only; valid OHLCV and an observed origin are separate checks."""
    return bool(rows) and _contiguous(rows) and (
        expected_last_session is None or rows[-1]['date'] == expected_last_session)


def _range_record(cluster, rows):
    members = sorted(cluster.get('member_dates') or [])
    if not members:
        return None
    identity = _identity(RANGE, members, rows)
    return {'type': RANGE, 'level': round(cluster['level'], 4),
            'meta': {'first_touch_date': members[0], 'last_touch_date': members[-1],
                     'touches': len(members), 'origin_identity': identity,
                     'selection': 'directed_observation_not_support_verdict'}}


def _gap_record(gap, rows):
    positions = {row['date']: index for index, row in enumerate(rows)}
    index = positions[gap['date']]
    if index == 0:
        return None
    members = [rows[index - 1]['date'], gap['date']]
    return {'type': GAP, 'level': round(gap['lower'], 4),
            'meta': {'gap_date': gap['date'], 'gap_lower': round(gap['lower'], 4),
                     'gap_upper': round(gap['upper'], 4), 'gap_size': round(gap['size'], 4),
                     'origin_identity': _identity(GAP, members, rows),
                     'selection': 'directed_observation_not_support_verdict'}}


def source_identity(record):
    meta = record.get('meta') or {}
    kind = record.get('type')
    item = {'type': kind, 'level': record.get('level'),
            'date': meta.get('last_touch_date') if kind == RANGE else meta.get('gap_date')}
    if kind == RANGE:
        item['touches'] = meta.get('touches')
    return canonical_request(item)


def build_pool(rows, clusters, gaps):
    return [record for record in
            [_range_record(cluster, rows) for cluster in clusters if cluster['touches'] >= 2]
            + [_gap_record(gap, rows) for gap in gaps] if record is not None]


def _dated_record(requested, rows):
    """Reobserve the exact dated formation, independent of current clustering."""
    identity = requested['origin_identity']
    dates = [row['date'] for row in rows]
    if len(dates) != len(set(dates)):
        return None, 'ambiguous_history_dates'
    positions = {value: index for index, value in enumerate(dates)}
    if any(value not in positions for value in identity['formation_dates'] + identity['confirmation_dates']):
        return None, 'insufficient_history_for_dated_identity'
    members = identity['formation_dates']
    if requested['type'] == GAP:
        a, b = [positions[value] for value in members]
        if (b != a + 1 or not all(valid_bar(rows[i]) for i in [a, b])
                or not _contiguous(rows[a:b + 1])):
            return None, 'invalid_or_noncontiguous_gap_history'
        if rows[b]['low'] <= rows[a]['high']:
            return None, 'dated_formation_not_reproduced'
        result = _gap_record({'date': members[-1], 'lower': rows[a]['high'],
                              'upper': rows[b]['low'], 'size': rows[b]['low'] - rows[a]['high']}, rows)
    else:
        for value, confirmation in zip(members, identity['confirmation_dates']):
            index = positions[value]
            if (index < 2 or index + 2 >= len(rows) or rows[index + 2]['date'] != confirmation
                    or not all(valid_bar(row) for row in rows[index - 2:index + 3])
                    or not _contiguous(rows[index - 2:index + 3])):
                return None, 'insufficient_or_invalid_pivot_confirmation'
            if any(rows[index]['low'] > rows[j]['low'] for j in [index - 2, index - 1, index + 1, index + 2]):
                return None, 'dated_formation_not_reproduced'
        result = _range_record({'member_dates': members,
            'level': statistics.median(rows[positions[value]]['low'] for value in members)}, rows)
    if result['meta']['origin_identity'] != identity:
        return None, 'dated_identity_not_reproduced'
    if result['level'] != requested['level']:
        return None, 'source_values_changed_unverified'
    return result, None


def verified_origin_identity(record, rows):
    """Return metadata only if its exact dated formation can be reproduced."""
    request = dict(source_identity(record), origin_identity=record['meta']['origin_identity'])
    reproduced, _ = _dated_record(request, rows)
    return deepcopy(reproduced['meta']['origin_identity']) if reproduced else None


def observe_support_origins(requested, rows, pool, observed_at):
    """Rows must be completed sessions at observed_at; caller owns the clock."""
    result = []
    dates = [row.get('date') for row in rows]
    for request in parse_support_origins(requested):
        record, reason = None, None
        status = 'unavailable'
        if not rows:
            reason = 'insufficient_history'
        elif len(dates) != len(set(dates)):
            reason = 'ambiguous_history_dates'
        elif 'origin_identity' in request:
            record, reason = _dated_record(request, rows)
        else:
            matches = [candidate for candidate in pool if source_identity(candidate) == request]
            if len(matches) > 1:
                reason = 'ambiguous_legacy_identity'
            elif len(matches) == 1:
                # Validate formation/confirmation, not merely the selector's output.
                richer = dict(request, origin_identity=matches[0]['meta']['origin_identity'])
                record, reason = _dated_record(richer, rows)
            elif request['date'] < rows[0]['date'] or request['date'] > rows[-1]['date']:
                reason = 'insufficient_history_for_legacy_identity'
            else:
                status, reason = 'not_observed', 'legacy_identity_not_reconstructed_in_current_pool'
        if record is not None:
            status, reason = 'available', 'exact_origin_observed'
        result.append({'type': 'support_origin_observation', 'origin_type': request['type'],
            'requested_identity': deepcopy(request), 'status': status, 'observation_reason': reason,
            'level': record['level'] if record else None, 'observed_at': observed_at,
            'observation_scope': {'history_first_session': rows[0]['date'] if rows else None,
                'history_last_session': rows[-1]['date'] if rows else None,
                'method': 'exact_dated_formation' if 'origin_identity' in request else 'exact_legacy_current_pool',
                'range_pool_sessions': min(126, len(rows)), 'gap_pool_sessions': min(252, len(rows)),
                'available_is_not_viability': True},
            'source_record': record})
    return result
