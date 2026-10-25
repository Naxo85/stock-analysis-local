"""Offline, content-addressed technical observations; never financial model input."""
from copy import deepcopy
from datetime import date, datetime, timedelta
import hashlib
from decimal import Decimal, InvalidOperation
import json
import math
import re
import xml.etree.ElementTree as ET

try:
    from gcp_functions.support_resistances_raw.market_sessions import market_session, latest_completed_session
except ImportError:
    from market_sessions import market_session, latest_completed_session

PROTOCOL = 'technical-observations-v1'
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_DAILY_ROWS = 2000
ENDPOINTS = {'/v1/markets/options/expirations', '/v1/markets/options/chains'}


def text_sha256(text):
    # Hash the captured response.text UTF-8 exactly; not original HTTP bytes.
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def aware(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('archive_timestamp_requires_timezone')
    return result


def _history_coverage(rows, snapshot_at, extra_closures=()):
    if not isinstance(rows, list) or len(rows) > MAX_DAILY_ROWS:
        raise ValueError('archive_daily_rows_limit_or_type')
    end = latest_completed_session(aware(snapshot_at), extra_closures)
    expected = []
    cursor = end
    while len(expected) < 252:
        if market_session(cursor, extra_closures):
            expected.append(cursor.isoformat())
        cursor -= timedelta(days=1)
    expected.reverse()
    valid, invalid, incomplete = [], [], []
    for index, row in enumerate(rows):
        try:
            day = date.fromisoformat(row['date'])
            values = [row[k] for k in ('open', 'high', 'low', 'close', 'volume')]
            if (any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values)
                    or any(v == 0 for v in values[:4])
                    or not row['low'] <= min(row['open'], row['close']) <= max(row['open'], row['close']) <= row['high']
                    or not market_session(day, extra_closures)):
                raise ValueError('invalid_bar')
            if day > end:
                incomplete.append(index)
            else:
                valid.append(day.isoformat())
        except (KeyError, TypeError, ValueError):
            invalid.append(index)
    seen = set(valid)
    duplicates = sorted(day for day in seen if valid.count(day) > 1)
    missing = [day for day in expected if day not in seen]
    return {'requested_sessions': 252, 'received_rows': len(rows),
            'valid_completed_rows': len(valid), 'observed_completed_dates': sorted(seen),
            'expected_first_session': expected[0], 'expected_last_session': expected[-1],
            'last_observed_session': max(seen) if seen else None,
            'missing_expected_sessions': missing, 'invalid_row_indexes': invalid,
            'incomplete_or_future_row_indexes': incomplete, 'duplicate_dates': duplicates,
            'window_complete': not missing and not invalid and not duplicates,
            'calendar': 'shared_nyse_sessions', 'extra_closures': list(extra_closures),
            'adjustment_basis': 'provider_representation_not_independently_verified'}


def _option_coverage(responses, symbol, expected, source_status):
    if not isinstance(responses, list) or len(responses) > 32:
        raise ValueError('archive_option_response_limit_or_type')
    identities, sampled, validated, listed, contracts, missing_identity = set(), [], [], set(), 0, 0
    structure_errors = []
    for response in responses:
        endpoint, params = response['endpoint'], response['params']
        required = {'symbol', 'expiration', 'greeks'} if endpoint.endswith('/chains') else {'symbol'}
        if (endpoint not in ENDPOINTS or not isinstance(params, dict)
                or set(response) != {'endpoint', 'params', 'received_at', 'body_text', 'body_sha256'}
                or set(params) != required or params.get('symbol') != symbol
                or ('greeks' in params and params['greeks'] not in ('true', 'false'))):
            raise ValueError('archive_option_request_identity')
        if response.get('received_at') is not None:
            aware(response['received_at'])
        identity = (endpoint, canonical(params))
        if identity in identities:
            raise ValueError('archive_duplicate_option_response')
        identities.add(identity)
        body = response['body_text']
        if not isinstance(body, str) or len(body.encode('utf-8')) > MAX_RESPONSE_BYTES:
            raise ValueError('archive_option_response_size')
        if response.get('body_sha256') != text_sha256(body):
            raise ValueError('archive_option_response_digest_mismatch')
        local_errors = []
        try:
            tree = ET.fromstring(body)
        except ET.ParseError:
            tree = None
            local_errors.append('malformed_xml')
        is_chain = endpoint.endswith('/chains')
        expected_root, expected_child = ('options', 'option') if is_chain else ('expirations', 'date')
        if tree is not None:
            if (tree.tag != expected_root or any(child.tag != expected_child for child in tree)
                    or (tree.text or '').strip() not in ('', 'null')):
                local_errors.append('unrecognized_response_structure')
            if not is_chain:
                for node in tree.findall('./date'):
                    try:
                        listed.add(date.fromisoformat(node.text).isoformat())
                    except (TypeError, ValueError):
                        local_errors.append('invalid_listed_expiration')
        if is_chain:
            expiry = params.get('expiration')
            if date.fromisoformat(str(expiry)).isoformat() != expiry:
                raise ValueError('archive_expiration_identity')
            sampled.append(expiry)
            for option in tree.findall('.//option') if tree is not None else []:
                contracts += 1
                if not all(option.findtext(k) for k in ('symbol', 'root_symbol', 'expiration_date', 'strike', 'option_type', 'contract_size')):
                    missing_identity += 1
                    local_errors.append('contract_identity_fields_incomplete')
                try:
                    strike = Decimal(str(option.findtext('strike')))
                    side = option.findtext('option_type')
                    if not strike.is_finite() or strike <= 0 or side not in ('put', 'call'):
                        raise ValueError('invalid_identity')
                    if option.findtext('expiration_date') not in (None, '', expiry):
                        local_errors.append('contract_expiration_mismatch')
                    for key in ('underlying', 'underlying_symbol'):
                        if option.findtext(key) not in (None, '', symbol):
                            local_errors.append('contract_underlying_mismatch')
                    size = option.findtext('contract_size')
                    if size and (not Decimal(size).is_finite() or Decimal(size) <= 0):
                        local_errors.append('contract_multiplier_invalid')
                    root_symbol = option.findtext('root_symbol')
                    if root_symbol and root_symbol != symbol:
                        # Adjusted roots may be legitimate; their mapping is unknown here.
                        local_errors.append('contract_root_mapping_not_verified')
                    contract_symbol = option.findtext('symbol')
                    if contract_symbol:
                        match = re.fullmatch(r'(.+?)(\d{6})([CP])(\d{8})', contract_symbol)
                        if not match:
                            local_errors.append('contract_symbol_not_recognized')
                        elif (match[1] != (root_symbol or symbol)
                              or match[2] != date.fromisoformat(expiry).strftime('%y%m%d')
                              or match[3] != ('P' if side == 'put' else 'C')
                              or Decimal(match[4])/1000 != strike):
                            local_errors.append('contract_symbol_identity_mismatch')
                except (TypeError, ValueError, InvalidOperation):
                    local_errors.append('contract_required_identity_missing_or_invalid')
            if not local_errors:
                validated.append(expiry)
        if local_errors:
            structure_errors.append({'response_index': len(identities)-1, 'reasons': sorted(set(local_errors))})
    expected = list(expected)
    if len(set(expected)) != len(expected) or any(date.fromisoformat(e).isoformat() != e for e in expected):
        raise ValueError('archive_expected_expirations')
    missing = sorted(set(expected) - set(validated))
    expiration_response = any(endpoint.endswith('/expirations') for endpoint, _ in identities)
    no_future = source_status == 'no_future_expirations' and expiration_response and not sampled and not expected and not listed and not structure_errors
    return {'scope': 'successful_cached_responses_only', 'source_capture_status': source_status,
            'expected_sampled_expirations': expected, 'downloaded_chain_expirations': sorted(set(sampled)),
            'validated_chain_expirations': sorted(set(validated)), 'structure_or_identity_issues': structure_errors,
            'missing_expected_expirations': missing, 'response_count': len(responses),
            'wire_contract_count': contracts, 'contracts_missing_identity_fields': missing_identity,
            'sampled_capture_complete': (source_status == 'ok' and expiration_response and bool(expected) and not missing and not structure_errors and set(expected) <= listed) or no_future,
            'market_complete': False, 'includes_failed_requests': False,
            'economic_deliverable_verified': False,
            'oi_effective_at': None, 'simultaneous_observations_verified': False}


def _seal(payload):
    payload = deepcopy(payload)
    payload['archive_id'] = text_sha256(canonical(payload))
    return validate_archive(payload)


def build_capture(symbol, snapshot_at, daily_rows, responses, *, expected_expirations=(),
                  source_status='unknown', history_received_at=None, extra_closures=(), source_revision=None,
                  additional_histories=(), history_request_window=None):
    """Only values already obtained by this raw request; performs no I/O."""
    return _seal({'archive_protocol': PROTOCOL, 'schema_version': 1,
        'symbol': symbol, 'snapshot_at': snapshot_at, 'source_revision': source_revision,
        'origin': 'prospective_raw_capture',
        'additional_downloaded_histories': [dict(deepcopy(item), coverage=_history_coverage(item['rows'], snapshot_at, extra_closures))
                                          for item in additional_histories],
        'daily': {'representation': 'parsed_provider_daily_rows', 'received_at': history_received_at,
                  'request_window': deepcopy(history_request_window),
                  'rows': deepcopy(daily_rows), 'coverage': _history_coverage(daily_rows, snapshot_at, extra_closures)},
        'options': {'representation': 'captured_response_text_utf8', 'responses': deepcopy(responses),
                    'coverage': _option_coverage(responses, symbol, expected_expirations, source_status)}})


def build_partial(document, source_sha256):
    """Export dated originals honestly; selected detail is never a full chain."""
    source = document.get('slim') or document.get('slim_snapshot') or document
    symbol, snapshot = source.get('symbol') or document.get('symbol'), source.get('as_of')
    rows = (source.get('price_history') or {}).get('sessions') or []
    selected = []
    def visit(value, path):
        if isinstance(value, dict):
            if 'option_details' in value:
                selected.append({'path': path, 'record': deepcopy(value)})
                return
            for key, child in value.items():
                visit(child, path + '/' + str(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path + '/' + str(index))
    for key in ('levels', 'supports', 'resistances', 'put_walls_top', 'call_walls_top', 'option_origins'):
        visit(source.get(key), '/' + key)
    return _seal({'archive_protocol': PROTOCOL, 'schema_version': 1,
        'symbol': symbol, 'snapshot_at': snapshot, 'source_revision': source.get('data_contract_revision'),
        'origin': 'derived_local_document', 'source_file_sha256': source_sha256,
        'daily': {'representation': 'published_subset', 'received_at': None, 'request_window': None, 'rows': deepcopy(rows),
                  'coverage': _history_coverage(rows, snapshot)},
        'options': {'representation': 'selected_derived_records', 'records': selected,
                    'summary': deepcopy(source.get('options') or {}),
                    'coverage': {'sampled_capture_complete': False, 'market_complete': False,
                                 'reason': 'original_wire_responses_not_present',
                                 'oi_effective_at': None, 'full_chain_reconstruction': False}}})


def validate_archive(archive):
    if (not isinstance(archive, dict) or archive.get('archive_protocol') != PROTOCOL
            or archive.get('schema_version') != 1
            or not re.fullmatch('[A-Z0-9][A-Z0-9.-]{0,19}', str(archive.get('symbol', '')))):
        raise ValueError('invalid_technical_archive_identity')
    allowed = {'archive_protocol', 'schema_version', 'symbol', 'snapshot_at', 'source_revision',
               'origin', 'daily', 'options', 'archive_id'}
    if archive.get('origin') == 'derived_local_document':
        allowed.add('source_file_sha256')
    if archive.get('origin') == 'prospective_raw_capture':
        allowed.add('additional_downloaded_histories')
    if set(archive) != allowed:
        raise ValueError('technical_archive_unexpected_fields')
    core = {k: v for k, v in archive.items() if k != 'archive_id'}
    encoded = canonical(core)
    if len(encoded.encode('utf-8')) > MAX_ARCHIVE_BYTES:
        raise ValueError('technical_archive_size_limit')
    if archive.get('archive_id') != text_sha256(encoded):
        raise ValueError('technical_archive_digest_mismatch')
    aware(archive['snapshot_at'])
    daily = archive['daily']
    if set(daily) != {'representation', 'received_at', 'request_window', 'rows', 'coverage'}:
        raise ValueError('technical_archive_unexpected_daily_fields')
    if daily['request_window'] is not None:
        window = daily['request_window']
        if set(window) != {'start', 'end'} or date.fromisoformat(window['start']) > date.fromisoformat(window['end']):
            raise ValueError('technical_archive_history_request_window')
    if daily.get('received_at') is not None:
        aware(daily['received_at'])
    expected = _history_coverage(daily['rows'], archive['snapshot_at'], daily['coverage'].get('extra_closures', ()))
    if expected != daily['coverage']:
        raise ValueError('technical_archive_history_coverage_mismatch')
    options = archive['options']
    if archive['origin'] == 'prospective_raw_capture':
        if daily['representation'] != 'parsed_provider_daily_rows':
            raise ValueError('technical_archive_history_representation')
        if set(options) != {'representation', 'responses', 'coverage'}:
            raise ValueError('technical_archive_unexpected_option_fields')
        additional = archive['additional_downloaded_histories']
        if not isinstance(additional, list) or len(additional) > 16:
            raise ValueError('technical_archive_history_request_limit')
        for item in additional:
            if (set(item) != {'symbol', 'request_start', 'request_end', 'received_at', 'rows', 'coverage'}
                    or not re.fullmatch('[A-Z0-9][A-Z0-9.-]{0,19}', str(item.get('symbol', '')))):
                raise ValueError('technical_archive_additional_history_identity')
            for key in ('request_start', 'request_end'):
                date.fromisoformat(item[key])
            aware(item['received_at'])
            if item['coverage'] != _history_coverage(item['rows'], archive['snapshot_at'], item['coverage'].get('extra_closures', ())):
                raise ValueError('technical_archive_additional_history_coverage')
        expected = _option_coverage(options['responses'], archive['symbol'],
            options['coverage']['expected_sampled_expirations'], options['coverage']['source_capture_status'])
        if options['representation'] != 'captured_response_text_utf8' or options['coverage'] != expected:
            raise ValueError('technical_archive_options_coverage_mismatch')
    elif archive['origin'] == 'derived_local_document':
        partial_coverage = {'sampled_capture_complete': False, 'market_complete': False,
                            'reason': 'original_wire_responses_not_present',
                            'oi_effective_at': None, 'full_chain_reconstruction': False}
        if (set(options) != {'representation', 'records', 'summary', 'coverage'}
                or options['coverage'] != partial_coverage
                or not isinstance(options['records'], list)
                or not re.fullmatch('[0-9a-f]{64}', archive.get('source_file_sha256', ''))
                or daily['representation'] != 'published_subset'
                or options['representation'] != 'selected_derived_records'
                or options['coverage'].get('sampled_capture_complete') is not False
                or options['coverage'].get('full_chain_reconstruction') is not False):
            raise ValueError('technical_archive_partial_scope_mismatch')
    else:
        raise ValueError('technical_archive_origin')
    return archive
