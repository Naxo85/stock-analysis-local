"""Durable local integrity of completed model answers (not provider signatures)."""
import hashlib
import json
from pathlib import Path

from src.local_runner.codex_call_evidence import inspect as inspect_call


def text_digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def authenticate_response(work: Path, kind: str, receipt: dict) -> str:
    response = (work / f'{kind}.response').read_text(encoding='utf-8')
    if receipt.get('exit_code') != 0 or not response.strip():
        raise RuntimeError('model_response_not_successful')
    expected = receipt.get('response_sha256')
    if expected is not None and expected != text_digest(response):
        raise RuntimeError('model_response_digest_mismatch')
    if receipt.get('cache_reused'):
        origin = receipt.get('origin_receipt') or {}
        if not expected or origin.get('response_sha256') != expected:
            raise RuntimeError('cached_response_origin_not_authenticated')
        return response
    path = work / f'{kind}.events.jsonl'
    events = path.read_text(encoding='utf-8') if path.exists() else ''
    if receipt.get('events_sha256') is not None:
        if receipt['events_sha256'] != text_digest(events):
            raise RuntimeError('model_response_events_digest_mismatch')
    if expected is None:
        # Frozen receipts are never rewritten. Their original complete single
        # turn and final message are independent evidence of the answer.
        if inspect_call(events, response).get('state') != 'completed':
            raise RuntimeError('legacy_model_response_not_authenticated_by_events')
    call_path = work / f'{kind}.call.json'
    if call_path.exists():
        call = json.loads(call_path.read_text(encoding='utf-8'))
        for key in ('input_sha256', 'instructions_sha256', 'schema_sha256',
                    'model', 'reasoning_effort', 'research_enabled'):
            if call.get(key) != receipt.get(key):
                raise RuntimeError('model_response_call_contract_mismatch')
    return response
