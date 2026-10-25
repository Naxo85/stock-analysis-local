"""Seal the validated staging bundle; recheck before every external write."""
import json
from pathlib import Path

from src.local_runner.publication_contract import digest_text, digest_json
from src.local_runner.receipt_integrity import authenticate_response


def _review_core(review):
    return {k: v for k, v in review.items() if k not in ('bundle_manifest_sha256', 'published_at')}


def seal_bundle(work: Path, symbol: str, review: dict):
    source = work / 'publish' / 'output' / symbol
    files = {}
    for name in ('latest.json', 'latest.md', 'latest.html'):
        path = source / name
        if path.exists():
            files[name] = digest_text(path.read_text(encoding='utf-8'))
    if 'latest.json' not in files:
        raise RuntimeError('publication_bundle_json_missing')
    evidence = {}
    for kind in ('triage', 'triage_repair', 'report'):
        receipt = work / (kind + '.receipt.json')
        if receipt.exists():
            value = json.loads(receipt.read_text(encoding='utf-8'))
            if value.get('exit_code') == 0:
                # Real calls and reconstructed legacy receipts must authenticate.
                authenticate_response(work, kind, value)
            for suffix in ('receipt.json', 'response', 'input.json', 'events.jsonl', 'call.json'):
                path = work / (kind + '.' + suffix)
                if path.exists():
                    evidence[path.name] = digest_text(path.read_text(encoding='utf-8'))
    for name in ('input.json', 'policy.json', 'instructions.md', 'triage_instructions.md'):
        path = work / name
        if path.exists():
            evidence[name] = digest_text(path.read_text(encoding='utf-8'))
    manifest = {'schema_version': 1, 'symbol': symbol, 'files': files,
                'evidence': evidence, 'review_sha256': digest_json(_review_core(review))}
    (work / 'bundle.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    review['bundle_manifest_sha256'] = digest_json(manifest)
    return manifest


def verify_bundle(work: Path, symbol: str, review: dict, *, return_artifacts=False):
    path = work / 'bundle.manifest.json'
    if not path.exists() or not review.get('bundle_manifest_sha256'):
        raise RuntimeError('publication_bundle_requires_receipt_revalidation')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if (manifest.get('symbol') != symbol or manifest.get('schema_version') != 1
            or digest_json(manifest) != review['bundle_manifest_sha256']
            or manifest.get('review_sha256') != digest_json(_review_core(review))):
        raise RuntimeError('publication_bundle_manifest_mismatch')
    source = work / 'publish' / 'output' / symbol
    actual = {p.name for p in source.glob('latest.*') if p.is_file()}
    if actual != set(manifest['files']):
        raise RuntimeError('publication_bundle_file_set_changed')
    artifacts = {name: (source / name).read_text(encoding='utf-8') for name in manifest['files']}
    for name, digest in manifest['files'].items():
        if digest_text(artifacts[name]) != digest:
            raise RuntimeError('publication_bundle_artifact_changed:' + name)
    evidence = {}
    for name, digest in manifest['evidence'].items():
        path = work / name
        if not path.exists():
            raise RuntimeError('publication_bundle_evidence_changed:' + name)
        evidence[name] = path.read_text(encoding='utf-8')
        if digest_text(evidence[name]) != digest:
            raise RuntimeError('publication_bundle_evidence_changed:' + name)
    payload = json.loads(artifacts['latest.json'])
    if 'latest.md' in manifest['files']:
        if artifacts['latest.md'] != payload.get('analysis_markdown'):
            raise RuntimeError('publication_bundle_markdown_mismatch')
    return (manifest, artifacts, evidence) if return_artifacts else manifest


def materialize_snapshot(work: Path, symbol: str, manifest: dict, artifacts: dict):
    """Legacy CLI uploads receive only this verified copy, not mutable staging."""
    root = work / 'validated_publication' / digest_json(manifest)
    target = root / 'output' / symbol
    target.mkdir(parents=True, exist_ok=True)
    for name, body in artifacts.items():
        path = target / name
        path.write_text(body, encoding='utf-8')
        if digest_text(path.read_text(encoding='utf-8')) != manifest['files'][name]:
            raise RuntimeError('publication_snapshot_write_mismatch')
    return root
