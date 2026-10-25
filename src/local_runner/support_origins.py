"""Revision41: CURRENT gap/range identities and acquisition coverage.

These records request observations, not retention, strength or buying viability.
Only authenticated active CURRENT supplies requests; no prose/nearest-price guess.
"""
from copy import deepcopy
from datetime import date, datetime
import json
import math

from gcp_functions.support_resistances_raw.support_origins import (
    canonical_request, parse_support_origins, request_key,
)

KINDS = ('range_bottom_3_6m', 'gap_up_lower')


def support_origins(reference):
    from src.local_runner.semantic_report import reference_document
    if not (reference or {}).get('analysis_markdown'):
        return []
    doc = reference_document(reference, verify_projection=True)
    requests = {}

    def visit(value):
        if isinstance(value, dict):
            kind = value.get('type')
            if kind in KINDS:
                # Select identity fields only. Counts/dates must actually exist;
                # incomplete legacy records cannot authorize a nearby match.
                item = {name: deepcopy(value[name]) for name in
                        ('type', 'level', 'date', 'touches', 'origin_identity') if name in value}
                if kind == 'gap_up_lower':
                    item.pop('touches', None)
                try:
                    item = canonical_request(item)
                except (ValueError, TypeError):
                    return
                requests[request_key(item)] = item
                return
            if kind == 'support_origin_observation':
                # Even a scoped negative observation preserves the requested
                # historical identity; it never becomes a positive live origin.
                prior = value.get('requested_identity')
                if isinstance(prior, dict):
                    visit(prior)
                return
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for key in ('entry', 'ambitious_entry'):
        level = doc['plan'].get(key) or {}
        if not level.get('range'):
            continue
        visit(level.get('resolved_facts') or [])
        visit((level.get('support_validity') or {}).get('sources') or [])
    return parse_support_origins(list(requests.values()))


def encode_support_origins(requested):
    return json.dumps(parse_support_origins(requested), sort_keys=True,
                      separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def require_support_origins(slim, requested):
    """Check exact requested coverage before admission, including empty requests.

    Unavailable/ambiguous/not observed are legitimate scoped results, not financial
    failure. Missing or mismatched transport is a data failure before any model.
    """
    def invalid():
        raise RuntimeError('incomplete_source_no_model_call: support_origin_observation')
    try:
        if type(slim.get('data_contract_revision')) is not int or slim['data_contract_revision'] < 41:
            invalid()
        expected = {request_key(row): row for row in parse_support_origins(requested)}
        rows = (slim.get('levels') or {}).get('support_origins')
        if not isinstance(rows, list) or len(rows) != len(expected):
            invalid()
        snapshot = datetime.fromisoformat(slim['as_of'].replace('Z', '+00:00'))
        if snapshot.tzinfo is None:
            invalid()
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                invalid()
            request = row.get('requested_identity')
            identity = request_key(canonical_request(request))
            if identity not in expected or request != expected[identity] or identity in seen:
                invalid()
            if (row.get('type') != 'support_origin_observation'
                    or row.get('origin_type') != request['type']
                    or row.get('status') not in ('available', 'not_observed', 'unavailable')
                    or not isinstance(row.get('observation_reason'), str)
                    or not row['observation_reason'].strip()
                    or row.get('observed_at') != slim['as_of']):
                invalid()
            scope = row.get('observation_scope') or {}
            if scope.get('available_is_not_viability') is not True or not scope.get('method'):
                invalid()
            first, last = scope.get('history_first_session'), scope.get('history_last_session')
            if first is not None or last is not None:
                if not first or not last or date.fromisoformat(first) > date.fromisoformat(last):
                    invalid()
                from gcp_functions.support_resistances_raw.market_sessions import is_completed_session
                if not is_completed_session(date.fromisoformat(last), snapshot):
                    invalid()
            source = row.get('source_record')
            if row['status'] == 'available':
                price = row.get('level')
                if (type(price) not in (int, float) or not math.isfinite(price) or price <= 0
                        or not isinstance(source, dict) or source.get('type') != request['type']
                        or source.get('level') != price or not first or not last):
                    invalid()
                current = {key: source[key] for key in ('type', 'level', 'date', 'touches', 'origin_identity')
                           if key in source}
                if current['type'] == 'gap_up_lower':
                    current.pop('touches', None)
                current = canonical_request(current)
                for key in ('type', 'level', 'date', 'touches'):
                    if key in request and current.get(key) != request[key]:
                        invalid()
                origin = current.get('origin_identity')
                if not origin or ('origin_identity' in request and origin != request['origin_identity']):
                    invalid()
                if not first <= origin['availability_date'] <= last:
                    invalid()
                if not isinstance(source.get('evidence'), dict):
                    invalid()
            elif row.get('level') is not None or source is not None:
                invalid()
            seen.add(identity)
    except (KeyError, TypeError, ValueError, AttributeError):
        invalid()
