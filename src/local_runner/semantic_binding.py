"""Runner-owned response/base binding. Never ask a model to echo a checksum."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

from src.local_runner.adaptive_context import model_context, serialize_model_input, compact_json


def _digest(value):
    return hashlib.sha256(compact_json(value).encode()).hexdigest()


def _authority(context):
    # Inputs added AFTER the call (triage/repair history/tool provenance) are not
    # a different frozen base. All financial/source authority remains bound.
    view = model_context(context)
    result = {key: deepcopy(view.get(key)) for key in
              ('symbol', 'routing_revision', 'owned', 'tier', 'prepared_at', 'slim',
               'analyst_quality', 'analyst_summary', 'analyst_actions', 'news',
               'guards', 'review_flags', 'itv')}
    if isinstance(result['news'], dict): result['news'].pop('luna_research', None)
    for key in ('reference', 'sol_reference'):
        reference = view.get(key) or {}
        # Derived mirrors are NOT authority. Authenticated Markdown/typed data
        # are verified by model_context/reference_document before projection.
        result[key] = {name: deepcopy(reference.get(name)) for name in
                       ('symbol', 'analysis_status', 'generated_at', 'analysis_markdown', 'slim_snapshot', 'semantic_data')}
    return result


@dataclass(frozen=True)
class ResponseBinding:
    authority_sha256: str
    response_sha256: str
    input_sha256: str
    kind: str


def bind_response(context, receipt, kind, *, policy=None):
    """Check the ACTUAL input receipt before attaching post-call research."""
    if kind not in ('triage', 'triage_repair', 'report'):
        raise ValueError('invalid_response_binding_kind')
    view = model_context(context)
    if kind != 'report':
        view.pop('research_memory', None)
        from src.local_runner.diff_transport import select_transport
        select_transport(view, policy or {})
    expected = hashlib.sha256(serialize_model_input(view).encode()).hexdigest()
    if receipt.get('exit_code') != 0 or receipt.get('input_sha256') != expected:
        raise ValueError('invalid_response_binding_input_receipt')
    payload = json.loads(receipt['text'])
    return ResponseBinding(_digest(_authority(context)), _digest(payload), expected, kind)


def require_response_binding(payload, context, binding, *, report=False):
    if not isinstance(binding, ResponseBinding):
        raise ValueError('invalid_response_binding_missing')
    expected_kinds = ('report',) if report else ('triage', 'triage_repair')
    if binding.kind not in expected_kinds or binding.response_sha256 != _digest(payload):
        raise ValueError('invalid_response_binding_response')
    if binding.authority_sha256 != _digest(_authority(context)):
        raise ValueError('invalid_response_binding_frozen_authority_changed')
