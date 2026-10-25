"""Immutable report versions and a generation-checked commit pointer.

Activated only by publication_protocol=manifest-v1, using configured ADC.
Legacy aliases are compatibility copies, never authority.
"""
import json
from datetime import datetime, timezone
from src.local_runner.publication_contract import (PROTOCOL, digest_text, digest_json,
    validate_manifest, verify_artifact)


class GcsStore:
    def __init__(self, bucket, *, auth=None):
        from src.local_runner.publication_auth import storage_client
        self.bucket = storage_client(auth).bucket(bucket)

    def read(self, name):
        from google.api_core.exceptions import NotFound
        blob = self.bucket.blob(name)
        try:
            blob.reload(timeout=60)
            generation = int(blob.generation)
            return blob.download_as_bytes(if_generation_match=generation, timeout=60).decode('utf-8'), generation
        except NotFound:
            return None, 0

    def write(self, name, body, generation):
        # No unconditional overwrite; SDK retries only with preconditions.
        blob = self.bucket.blob(name)
        blob.upload_from_string(body.encode('utf-8'), content_type='application/json; charset=utf-8'
                                if name.endswith('.json') or name.rsplit('/', 1)[-1] in ('json','current','anchor','review')
                                else ('text/html; charset=utf-8' if name.endswith('/html') else 'text/markdown; charset=utf-8'),
                                if_generation_match=generation, timeout=120)


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def make_manifest(symbol, artifacts, review):
    hashes = {k: digest_text(v) for k, v in artifacts.items()}
    version = digest_json({'symbol': symbol, 'artifacts': hashes})
    manifest = {'protocol': PROTOCOL, 'schema_version': 1, 'symbol': symbol,
                'version': version, 'reviewed_at': review.get('reviewed_at'),
                'files': {k: {'name': f'{symbol}/_versions/{version}/{k}', 'sha256': v}
                          for k, v in hashes.items()}}
    return validate_manifest(manifest, symbol)


def _persist_committed_manifest(store, manifest):
    """Only called with a pointer actually observed or just committed by CAS."""
    name = f"{manifest['symbol']}/_versions/{manifest['version']}/manifest.json"
    body = json_text(manifest)
    existing, _ = store.read(name)
    if existing is None:
        try:
            store.write(name, body, 0)
        except Exception:
            existing, _ = store.read(name)
            if existing is None or json.loads(existing) != manifest:
                raise
    elif json.loads(existing) != manifest:
        raise RuntimeError('publication_historical_manifest_collision')


def commit(store, manifest, artifacts, expected_generation, *, before_commit=None, on_committed=None):
    """Write all immutable objects then CAS pointer; retry is safe at every step."""
    pointer = f"{manifest['symbol']}/publication.json"
    raw, generation = store.read(pointer)
    if raw is not None:
        current = validate_manifest(json.loads(raw), manifest['symbol'])
        # Retain the last confirmed descriptor before any writer can replace it.
        _persist_committed_manifest(store, current)
        if current['version'] == manifest['version']:
            # A prior commit may have succeeded before a transport error.
            for kind, entry in current['files'].items():
                body, _ = store.read(entry['name'])
                if body is None:
                    raise RuntimeError('committed_publication_artifact_missing')
                verify_artifact(current, kind, body)
            if on_committed is not None:
                on_committed(current)
            return current
    if generation != expected_generation:
        raise RuntimeError('publication_concurrent_commit')
    historical, _ = store.read(f"{manifest['symbol']}/_versions/{manifest['version']}/manifest.json")
    if historical is not None:
        # Exact old versions cannot acquire a new commit date after a newer version.
        raise RuntimeError('publication_version_already_committed')
    for kind, body in artifacts.items():
        entry = manifest['files'][kind]
        verify_artifact(manifest, kind, body)
        old, old_generation = store.read(entry['name'])
        if old is None:
            try:
                store.write(entry['name'], body, 0)
            except Exception:
                # Another retry may have created the exact same immutable file.
                old, _ = store.read(entry['name'])
                if old is None or digest_text(old) != entry['sha256']:
                    raise
        elif digest_text(old) != entry['sha256']:
            raise RuntimeError('publication_immutable_version_collision')
    for kind, entry in manifest['files'].items():
        stored, _ = store.read(entry['name'])
        if stored is None:
            raise RuntimeError('publication_uploaded_artifact_missing:' + kind)
        verify_artifact(manifest, kind, stored)
    if before_commit is not None:
        before_commit()
    committed = dict(manifest, committed_at=datetime.now(timezone.utc).isoformat())
    store.write(pointer, json_text(committed), expected_generation)
    if on_committed is not None:
        on_committed(committed)
    _persist_committed_manifest(store, committed)
    return committed
