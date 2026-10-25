"""Archive existing local observations, without fetches, models or publication.

python -m src.local_runner.archive_technical_observations --input FILE --output-root DIR
The producer sidecar is never returned as technical model context.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile

from src.local_runner.technical_archive import (PROTOCOL, MAX_ARCHIVE_BYTES,
    build_partial, canonical, validate_archive)

SIDECAR = '_evaluation_archive'
SIDECAR_ERROR = '_evaluation_archive_error'


def write_archive(root, archive):
    validate_archive(archive)
    root = Path(root).resolve()
    target = root / archive['symbol'] / (archive['archive_id'] + '.json')
    if not target.resolve().is_relative_to(root):
        raise ValueError('technical_archive_path_escape')
    target.parent.mkdir(parents=True, exist_ok=True)
    body = (canonical(archive) + '\n').encode('utf-8')
    descriptor, temporary = tempfile.mkstemp(prefix='.archive-', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            if target.read_bytes() != body:
                raise ValueError('technical_archive_immutable_collision')
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {'path': str(target), 'archive_id': archive['archive_id'], 'bytes': len(body),
            'sha256': hashlib.sha256(body).hexdigest(), 'origin': archive['origin'],
            'snapshot_at': archive['snapshot_at'],
            'history_252_complete': archive['daily']['coverage']['window_complete'],
            'sampled_options_complete': archive['options']['coverage']['sampled_capture_complete']}


def extract_for_model(payload, *, archive_root=None, symbol=None, source_sha256=None, failure_path=None):
    """Always remove sidecar, even when local storage is disabled."""
    clean = deepcopy({key: value for key, value in payload.items() if key not in (SIDECAR, SIDECAR_ERROR)})
    archive = payload.get(SIDECAR)
    if symbol is not None and clean.get('symbol') not in (None, symbol):
        raise ValueError('slim_endpoint_symbol_mismatch')
    if archive_root is None:
        return clean
    source_hash = source_sha256 or hashlib.sha256(canonical(clean).encode('utf-8')).hexdigest()
    try:
        if payload.get(SIDECAR_ERROR) is not None:
            raise ValueError('producer_archive_unavailable: ' + canonical(payload[SIDECAR_ERROR]))
        archive = validate_archive(archive) if archive is not None else build_partial(clean, source_hash)
        if (archive['symbol'] != (symbol or clean.get('symbol')) or archive['snapshot_at'] != clean.get('as_of')
                or ('data_contract_revision' in clean and archive.get('source_revision') != clean['data_contract_revision'])):
            raise ValueError('technical_archive_snapshot_identity_mismatch')
        write_archive(archive_root, archive)
    except Exception as exc:
        # Research storage is not a financial gate or a reason for another fetch.
        failure = {'status': 'failed', 'at': datetime.now(timezone.utc).isoformat(),
                   'source_sha256': source_hash, 'error_type': type(exc).__name__, 'error': str(exc),
                   'analysis_continues': True, 'financial_validation': 'existing_guards_unchanged'}
        target = Path(failure_path) if failure_path is not None else Path(archive_root)/('failure-'+source_hash+'.json')
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(failure, ensure_ascii=False), encoding='utf-8')
        except OSError:
            logging.exception('technical_archive_failure_record_unavailable')
        logging.warning('technical_archive_failed: %s', json.dumps(failure, ensure_ascii=False))
    return clean


def export_file(source, output_root):
    path = Path(source)
    if path.stat().st_size > MAX_ARCHIVE_BYTES * 2:
        raise ValueError('technical_archive_input_size_limit')
    body = path.read_bytes()
    document = json.loads(body)
    source_hash = hashlib.sha256(body).hexdigest()
    if document.get('archive_protocol') == PROTOCOL:
        archive = validate_archive(document)
    elif SIDECAR in document:
        archive = validate_archive(document[SIDECAR])
        if (archive['symbol'] != document.get('symbol') or archive['snapshot_at'] != document.get('as_of')
                or ('data_contract_revision' in document and archive.get('source_revision') != document['data_contract_revision'])):
            raise ValueError('technical_archive_snapshot_identity_mismatch')
    else:
        archive = build_partial(document, source_hash)
    return write_archive(output_root, archive)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output-root', required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(export_file(args.input, args.output_root), ensure_ascii=False))


if __name__ == '__main__':
    main()
