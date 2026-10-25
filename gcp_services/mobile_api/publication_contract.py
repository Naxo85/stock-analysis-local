"""Portable manifest-v1 reader contract. Financial payloads stay immutable."""
import hashlib
import json
import re

PROTOCOL = 'manifest-v1'
KINDS = {'json', 'md', 'html', 'current', 'anchor', 'review'}


def digest_text(value):
    # Text mode on Windows normalizes CRLF; transport line endings are not facts.
    return hashlib.sha256(value.replace('\r\n', '\n').encode('utf-8')).hexdigest()


def digest_json(value):
    return digest_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def validate_manifest(value, symbol):
    if (not isinstance(value, dict) or value.get('protocol') != PROTOCOL
            or value.get('schema_version') != 1 or value.get('symbol') != symbol
            or not re.fullmatch('[0-9a-f]{64}', str(value.get('version', '')))
            or set(value.get('files', {})) != KINDS):
        raise ValueError('invalid_publication_manifest')
    for kind, item in value['files'].items():
        expected = f"{symbol}/_versions/{value['version']}/{kind}"
        if (not isinstance(item, dict) or item.get('name') != expected
                or not re.fullmatch('[0-9a-f]{64}', str(item.get('sha256', '')))):
            raise ValueError('invalid_publication_artifact_identity')
    expected_version = digest_json({'symbol': symbol, 'artifacts': {k: v['sha256'] for k, v in value['files'].items()}})
    if value['version'] != expected_version:
        raise ValueError('publication_version_content_mismatch')
    return value


def verify_artifact(manifest, kind, text):
    if digest_text(text) != manifest['files'][kind]['sha256']:
        raise ValueError('publication_artifact_digest_mismatch:' + kind)
    return text


def with_attempt(payload, attempt, manifest=None):
    result = dict(payload)
    if manifest:
        result['publication_version'] = manifest['version']
    if isinstance(attempt, dict) and attempt.get('symbol') == payload.get('symbol'):
        result['latest_attempt'] = dict(attempt)
    return result


def attempt_notice(attempt, *, has_report=True):
    if not isinstance(attempt, dict) or attempt.get('status') not in ('failed', 'blocked', 'pending'):
        return ''
    labels = {'failed': 'falló', 'blocked': 'quedó bloqueado', 'pending': 'está pendiente de publicación'}
    return (f"El último intento {labels[attempt['status']]} ({attempt.get('at') or 'fecha desconocida'}). "
            + ('Se conserva el último informe válido con su fecha original.' if has_report
             else 'Todavía no hay un informe válido disponible.'))


class PublicationVersionNotFound(ValueError):
    pass


class InvalidPublicationVersion(ValueError):
    pass


def read_committed(read_text, symbol, kind='json', *, version=None):
    """Absent current pointer permits legacy, never an explicit historical query."""
    if version is not None and (not re.fullmatch('[0-9a-f]{64}', str(version))
            or not re.fullmatch('[A-Z0-9][A-Z0-9.-]{0,19}', symbol)):
        raise InvalidPublicationVersion('invalid_requested_publication_version')
    if version is not None:
        raw = read_text(f'{symbol}/_versions/{version}/manifest.json')
        if raw is not None:
            manifest = validate_manifest(json.loads(raw), symbol)
            if manifest['version'] != version or not manifest.get('committed_at'):
                raise ValueError('historical_publication_version_mismatch_or_uncommitted')
        else:
            # A CAS can be acknowledged before the historical copy is written.
            raw = read_text(f'{symbol}/publication.json')
            manifest = validate_manifest(json.loads(raw), symbol) if raw is not None else None
            if manifest is None or manifest['version'] != version or not manifest.get('committed_at'):
                raise PublicationVersionNotFound('requested_publication_version_not_found')
    else:
        raw = read_text(f'{symbol}/publication.json')
        manifest = validate_manifest(json.loads(raw), symbol) if raw is not None else None
        if manifest is not None and not manifest.get('committed_at'):
            raise ValueError('publication_pointer_not_committed')
    if manifest is None:
        return None, None
    body = read_text(manifest['files'][kind]['name'])
    if body is None:
        raise ValueError('publication_artifact_missing:' + kind)
    return verify_artifact(manifest, kind, body), manifest


def read_attempt(read_text, symbol):
    raw = read_text(f'{symbol}/attempt.json')
    if raw is None:
        return None
    value = json.loads(raw)
    if (not isinstance(value, dict) or value.get('symbol') != symbol
            or value.get('schema_version') != 1
            or value.get('status') not in ('pending', 'failed', 'blocked', 'succeeded')):
        raise ValueError('invalid_latest_attempt')
    return value
