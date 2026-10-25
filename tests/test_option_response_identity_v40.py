"""Narrow revision40 acquisition identity checks; all transport is simulated."""
import ast
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import math
import os
from pathlib import Path
import re
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve()
while not (ROOT / 'gcp_functions').is_dir():
    ROOT = ROOT.parent
SOURCE = Path(os.environ.get('RAW_IDENTITY_SOURCE', ROOT / 'gcp_functions/support_resistances_raw/main.py'))
FUNCTIONS = {'_to_float', '_validate_option_chain_identity', '_option_response',
             '_parse_option_contract', '_contract_multiplier', '_tradier_options_chain',
             '_observe_option_origins'}


def contract(**overrides):
    fields = {'symbol': 'CAT261023P00100000', 'root_symbol': 'CAT', 'underlying': 'CAT',
              'expiration_date': '2026-10-23', 'strike': '100', 'option_type': 'put',
              'contract_size': '100', 'open_interest': '100'}
    fields.update(overrides)
    return '<options><option>' + ''.join('<'+key+'>'+value+'</'+key+'>'
        for key, value in fields.items() if value is not None) + '<greeks><gamma>0.01</gamma></greeks></option></options>'


def load(body, archive_enabled=False):
    class Wire:
        text = body
        def raise_for_status(self): pass
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs.get('params')))
        return Wire()
    state = SimpleNamespace(evaluation_archive_enabled=archive_enabled)
    ns = {'math': math, 're': re, 'date': date, 'datetime': datetime, 'timezone': timezone,
          'Decimal': Decimal, 'InvalidOperation': InvalidOperation, 'ET': ET,
          'requests': SimpleNamespace(get=get), 'has_request_context': lambda: True,
          'g': state, 'TRADIER_BASE': 'https://offline.invalid', 'HEADERS_XML': {},
          'CALLWALL_TOP_EXPIRATIONS': 3}
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS]
    assert {node.name for node in selected} == FUNCTIONS
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), 'exec'), ns)
    ns['_tradier_option_expirations'] = lambda symbol: ['2026-10-23']
    return ns, state, calls


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('change,error', [
    ({'underlying': 'OTHER'}, 'underlying_mismatch'),
    ({'underlying_symbol': 'OTHER'}, 'underlying_mismatch'),
    ({'expiration_date': '2026-10-30'}, 'expiration_mismatch'),
])
def test_explicit_request_contradictions_fail_before_cache(enabled, change, error):
    ns, state, calls = load(contract(**change), enabled)
    with pytest.raises(ValueError, match=error):
        ns['_tradier_options_chain']('CAT', '2026-10-23')
    assert len(calls) == 1 and state.option_responses == {}
    assert not hasattr(state, 'option_response_received_at')


@pytest.mark.parametrize('enabled', [False, True])
def test_original_synthetic_other_contract_cannot_become_observed_origin(enabled):
    ns, state, calls = load(contract(symbol='OTHER261030P00100000', root_symbol='OTHER',
                                   underlying='OTHER', expiration_date='2026-10-30'), enabled)
    with pytest.raises(ValueError, match='underlying_mismatch'):
        ns['_observe_option_origins']([('put', 100.0)], 'CAT', 100)
    assert len(calls) == 1 and state.option_responses == {}


@pytest.mark.parametrize('change', [
    {'symbol': 'CAT261030P00100000'},
    {'symbol': 'CAT261030P00100000', 'expiration_date': None},
    {'symbol': 'CAT261023C00100000'},
    {'symbol': 'CAT261023P00101000'},
    {'symbol': 'CAT1261023P00100000', 'root_symbol': 'CAT'},
])
def test_safe_occ_decode_rejects_explicit_contract_field_contradictions(change):
    ns, state, _ = load(contract(**change))
    with pytest.raises(ValueError, match='occ_identity_mismatch'):
        ns['_tradier_options_chain']('CAT', '2026-10-23')
    assert state.option_responses == {}


@pytest.mark.parametrize('change', [
    {},
    {'symbol': 'CAT1261023P00100000', 'root_symbol': 'CAT1'},
    {'symbol': 'CAT   261023P00100000'},
    {'symbol': None, 'root_symbol': 'CAT1'},
    {'symbol': 'provider-specific-not-occ', 'root_symbol': 'CAT1'},
    {'symbol': 'CAT269932P00100000'},  # Invalid date is not safely decodable.
    {'symbol': None, 'root_symbol': None, 'expiration_date': None, 'underlying': None},
    {'symbol': 'CAT261023P00100000', 'root_symbol': None, 'expiration_date': None},
    {'underlying': ' cat ', 'option_type': 'PUT', 'strike': '100.000'},
    {'underlying': None, 'underlying_symbol': None},
    {'underlying': '', 'expiration_date': ''},
])
@pytest.mark.parametrize('enabled', [False, True])
def test_consistent_adjusted_missing_or_unrecognized_identity_preserves_acquisition(change, enabled):
    ns, state, calls = load(contract(**change), enabled)
    first = ns['_tradier_options_chain']('CAT', '2026-10-23')
    second = ns['_tradier_options_chain']('CAT', '2026-10-23')
    assert first == second and len(first) == 1
    assert first[0]['oi'] == 100 and first[0]['gamma'] == .01
    assert len(calls) == 1 and len(state.option_responses) == 1
    assert hasattr(state, 'option_response_received_at') is enabled


def test_consistent_current_origin_retains_values_and_uses_cache():
    ns, _, calls = load(contract())
    ns['_tradier_options_chain']('CAT', '2026-10-23')
    result = ns['_observe_option_origins']([('put', 100.0)], 'CAT', 100)[0]
    assert result['status'] == 'available'
    row = result['option_details']['by_expiration'][0]
    assert row['status'] == 'observed' and row['aggregate_oi'] == 100
    assert row['gamma_usd_millions'] == 1.0 and len(calls) == 1


def test_expiration_endpoint_does_not_require_chain_contract_fields():
    ns, state, calls = load('<expirations><date>2026-10-23</date></expirations>')
    response = ns['_option_response']('https://offline.invalid/v1/markets/options/expirations', params={'symbol':'CAT'})
    assert '<date>2026-10-23</date>' in response.text and len(calls) == 1
    assert len(state.option_responses) == 1


@pytest.mark.parametrize('enabled', [False, True])
def test_explicit_wrong_chain_root_is_not_a_successful_empty_chain(enabled):
    ns, state, calls = load('<garbage/>', enabled)
    with pytest.raises(ValueError, match='chain_structure_mismatch'):
        ns['_tradier_options_chain']('CAT', '2026-10-23')
    assert len(calls) == 1 and state.option_responses == {}


@pytest.mark.parametrize('body', ['<options/>', '<options>null</options>'])
@pytest.mark.parametrize('enabled', [False, True])
def test_legitimate_empty_chain_stays_a_successful_empty_observation(body, enabled):
    ns, state, calls = load(body, enabled)
    assert ns['_tradier_options_chain']('CAT', '2026-10-23') == []
    result = ns['_observe_option_origins']([('put', 100.0)], 'CAT', 100)[0]
    assert result['status'] == 'not_observed' and len(calls) == 1
    assert len(state.option_responses) == 1
