"""Acquisition contracts, separate from financial judgments and frozen reports."""
from datetime import date, datetime, timedelta, timezone
from gcp_functions.support_resistances_raw.market_sessions import (
    NY, market_session, latest_completed_session, is_completed_session,
)
import math


def require_price_history(slim):
    """Revision28 acquisition check, never a support/strength decision."""
    history = slim.get('price_history') or {}
    rows = history.get('sessions')
    def invalid():
        raise RuntimeError('incomplete_source_no_model_call: recent_price_history')
    if history.get('status') != 'available' or not isinstance(rows, list) or not rows:
        invalid()
    try:
        snapshot_day = date.fromisoformat(slim['as_of'][:10])
        revised = slim.get('data_contract_revision', 0) >= 40
        snapshot = datetime.fromisoformat(slim['as_of'].replace('Z', '+00:00'))
        if revised and snapshot.tzinfo is None:
            invalid()
        dates = []
        for row in rows:
            day = date.fromisoformat(row['date'])
            if (revised and not is_completed_session(day, snapshot)) or (not revised and day >= snapshot_day):
                invalid()
            dates.append(day)
            for field in ('open', 'high', 'low', 'close', 'volume'):
                value = row[field]
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (field != 'volume' and value == 0):
                    invalid()
            if not row['low'] <= min(row['open'], row['close']) <= max(row['open'], row['close']) <= row['high']:
                invalid()
        if dates != sorted(set(dates)) or history.get('first_session') != rows[0]['date'] or history.get('last_session') != rows[-1]['date']:
            invalid()
        if revised:
            for previous, current in zip(dates, dates[1:]):
                following = previous + timedelta(days=1)
                while not market_session(following):
                    following += timedelta(days=1)
                if current != following:
                    invalid()
            expected = latest_completed_session(snapshot).isoformat()
            if (history.get('observation_policy') != 'completed_nyse_sessions_at_snapshot'
                    or history.get('last_session') != expected
                    or history.get('expected_last_session') != expected
                    or history.get('observed_sessions') != len(rows)
                    or history.get('window_complete') is not (len(rows) == 20)):
                invalid()
        elif history.get('observation_policy') != 'completed_sessions_before_snapshot_utc_day':
            invalid()
    except (KeyError, TypeError, ValueError):
        invalid()


def require_quote_observation(slim):
    quote = slim.get('quote_observation') or {}
    def invalid():
        raise RuntimeError('incomplete_source_no_model_call: quote_observation')
    try:
        snapshot = datetime.fromisoformat(slim['as_of'].replace('Z', '+00:00'))
        stamp = datetime.fromisoformat(quote['provider_timestamp'].replace('Z', '+00:00'))
        price = slim['latest_price']
        if (snapshot.tzinfo is None or stamp.tzinfo is None or quote.get('status') != 'available'
                or type(price) not in (float, int) or not math.isfinite(price) or price <= 0
                or quote.get('source') not in ('bid_ask_mid', 'last_trade')
                or abs(quote['price'] - price) > 0.000051
                or stamp > snapshot + timedelta(seconds=5)):
            invalid()
        local = snapshot.astimezone(NY)
        expected = latest_completed_session(snapshot)
        if market_session(local.date()) and (local.hour, local.minute) >= (9, 30):
            expected = local.date()
        if stamp.astimezone(NY).date() < expected:
            invalid()
    except (KeyError, TypeError, ValueError):
        invalid()


def avwap_anchors(*references):
    dates = set()
    def visit(value):
        if isinstance(value, dict):
            if 'avwap' in str(value.get('type', '')).lower():
                anchor = value.get('date') or value.get('anchor_date') or (value.get('meta') or {}).get('anchor_date')
                if isinstance(anchor, str):
                    try:
                        if date.fromisoformat(anchor).isoformat() == anchor:
                            dates.add(anchor)
                    except ValueError:
                        pass
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    for reference in references:
        visit((reference or {}).get('slim_snapshot') or {})
        # Stored resolved facts can retain a defining dated origin that was
        # already absent from the most recent candidate shortlist.
        visit((reference or {}).get('semantic_report') or {})
    return sorted(dates)


def require_capture(slim, anchors=()):
    """Reject transport/incomplete captures before any model input is frozen.

    Not every asset has options. Explicit successful no-future-expirations is
    valid; missing fields after an exception are not the same market fact.
    """
    revised = slim.get('data_contract_revision', 0) >= 40
    if revised:
        require_quote_observation(slim)
    options = slim.get('options') or {}
    status = options.get('status')
    if status == 'no_future_expirations':
        if options.get('expirations'):
            raise RuntimeError('incomplete_source_no_model_call: contradictory_options_status')
    elif (status != 'ok' or not options.get('expirations')
          or (revised and (options.get('capture') or {}).get('status') != 'complete')
          or (not revised and not options.get('gamma_regime'))):
        raise RuntimeError('incomplete_source_no_model_call: options_capture')
    rows = (slim.get('levels') or {}).get('observed_origins') or []
    for anchor in anchors:
        matches = [row for row in rows if row.get('date') == anchor
                   and row.get('type') == 'avwap_observation']
        if len(matches) != 1 or matches[0].get('status') not in ('available', 'unavailable'):
            raise RuntimeError('incomplete_source_no_model_call: avwap_observation_missing')
        row = matches[0]
        if row['status'] == 'available' and (type(row.get('level')) not in (int, float) or row['level'] <= 0):
            raise RuntimeError('incomplete_source_no_model_call: invalid_avwap_observation')
        if row['status'] == 'unavailable' and not row.get('observation_reason'):
            raise RuntimeError('incomplete_source_no_model_call: unexplained_avwap_absence')


def option_origins(reference):
    """Identities cited by CURRENT active buying zones, not old anchor/retired plans.

    A dated record requests a fresh observation; it never becomes live evidence.
    Include cited option comparisons conservatively: do not guess the defining
    strike from prose or round a price range to a convenient contract.
    """
    from src.local_runner.semantic_report import reference_document
    if not (reference or {}).get('analysis_markdown'):
        return []
    doc = reference_document(reference, verify_projection=True)
    identities = set()
    def visit(record):
        if not isinstance(record, dict):
            return
        detail = record.get('option_details') or {}
        side, strike = detail.get('option_type'), detail.get('strike')
        if not detail:
            kind = record.get('type')
            side = 'put' if kind in ('put_wall', 'put_wall_gamma') else 'call' if kind in ('call_wall', 'call_wall_gamma') else None
            strike = record.get('level')
        if side in ('put', 'call') and type(strike) in (int, float) and math.isfinite(strike) and strike > 0:
            identities.add((side, float(strike)))
    for key in ('entry', 'ambitious_entry'):
        zone = doc['plan'].get(key) or {}
        if not zone.get('range'):
            continue
        for fact in zone.get('resolved_facts') or []:
            visit(fact.get('options_record'))
        for row in (zone.get('support_validity') or {}).get('sources') or []:
            visit(row.get('value'))
    return sorted(identities)


def require_option_origins(slim, requested):
    """Coverage before model admission, not a viability/strength/routing rule."""
    if not requested:
        return
    def invalid():
        raise RuntimeError('incomplete_source_no_model_call: option_origin_observation')
    rows = (slim.get('levels') or {}).get('option_origins')
    if not isinstance(rows, list) or len(rows) != len(requested):
        invalid()
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            invalid()
        detail = row.get('option_details') or {}
        identity = (detail.get('option_type'), detail.get('strike'))
        if (identity[0] not in ('put', 'call') or type(identity[1]) not in (int, float)
                or not math.isfinite(identity[1]) or identity[1] <= 0):
            invalid()
        if (row.get('type') != 'option_origin_observation' or identity not in requested
                or identity in seen or row.get('level') != identity[1]
                or row.get('status') not in ('available', 'not_observed', 'unavailable')
                or not row.get('reason') or detail.get('scope') != 'parsed_contracts_in_sampled_expirations'):
            invalid()
        expirations, observations = detail.get('sampled_expirations'), detail.get('by_expiration')
        if (not isinstance(expirations, list) or not isinstance(observations, list)
                or [r.get('expiration') for r in observations if isinstance(r, dict)] != expirations
                or any(not isinstance(r, dict) or r.get('status') not in ('observed', 'not_observed', 'unavailable')
                       or not isinstance(r.get('observed_contracts'), list) for r in observations)):
            invalid()
        try:
            if len(set(expirations)) != len(expirations) or any(date.fromisoformat(e).isoformat() != e for e in expirations):
                invalid()
        except (ValueError, TypeError):
            invalid()
        expected_status = ('unavailable' if any(r['status'] == 'unavailable' for r in observations)
                           else 'available' if any(r['status'] == 'observed' for r in observations) else 'not_observed')
        if row['status'] != expected_status or any((r['status'] == 'observed') != bool(r['observed_contracts']) for r in observations if r['status'] != 'unavailable'):
            invalid()
        seen.add(identity)


def encode_option_origins(requested):
    from decimal import Decimal
    return ','.join(side + ':' + format(Decimal(str(strike)), 'f') for side, strike in requested)
