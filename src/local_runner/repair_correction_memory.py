"""Restore correction metadata from immutable originals; never generate/review.

Only the published review_memory binding is repaired. Dates, content, evidence,
anchor, review history and failed-batch evidence are preserved byte-for-value.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from src.local_runner import adaptive_stage as stage
from src.local_runner.correct_volume_arithmetic import build
from src.local_runner.review_memory import read_memory
from src.local_runner.semantic_sources import source_catalog


def reconstruct(correction):
    audit = stage.read_json(correction / 'correction.json')
    if audit.get('status') != 'published' or not audit.get('original_unchanged'):
        raise RuntimeError('repair_requires_published_correction_audit')
    symbol = audit['symbol']
    original = Path(audit['source_batch']) / 'adaptive' / symbol
    hashes = {str(p.relative_to(original)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in original.rglob('*') if p.is_file()}
    # Older correction receipts recorded only top-level originals. Authenticate
    # exactly their declared scope; derived publication files were not included.
    if any(hashes.get(name) != value for name, value in audit['original_sha256'].items()):
        raise RuntimeError('repair_original_evidence_changed')
    context = stage.read_json(correction / 'input.json')
    previous = stage.read_json(original / 'publish/output' / symbol / 'latest.json')
    published = stage.read_json(correction / 'publish/output' / symbol / 'latest.json')
    if stage.reference_key(previous) != published['maintenance']['base_report_sha256']:
        raise RuntimeError('repair_previous_report_changed')
    anchor = context['sol_reference']
    pointer = published['manual_correction']['source_pointer']
    selectors = [key for key, value in source_catalog(context).items() if value['pointer'] == pointer]
    if len(selectors) != 1:
        raise RuntimeError('repair_ambiguous_original_source')
    expected, _, _ = build(previous, anchor, context, selectors[0],
                            datetime.fromisoformat(published['generated_at']))
    probe = deepcopy(published)
    probe['review_memory'] = expected['review_memory']
    if probe != expected or published.get('review_memory') != previous.get('review_memory'):
        raise RuntimeError('repair_not_exclusively_stale_correction_memory')
    read_memory(expected, anchor)
    return symbol, published, expected, anchor


def repair(root, correction, execute=False):
    symbol, published, expected, anchor = reconstruct(correction)
    work = root / 'logs/memory_repairs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') / symbol
    work.mkdir(parents=True)
    audit = {'symbol': symbol, 'correction': str(correction), 'model_calls': 0,
             'generated_at': published['generated_at'], 'executed': False, 'status': 'checking'}
    uris = {'report': f'gs://{stage.TEST_BUCKET}/{symbol}/latest.json',
            'mirror': f'gs://{stage.SHEET_REPORT_MIRROR_BUCKET}/{stage.SHEET_REPORT_MIRROR_PREFIX}/{symbol}.json',
            'current': stage.current_uri(symbol)}
    try:
        with stage._exclusive_read_lock(root / 'output' / symbol / 'adaptive_publish.lock'):
            remote_anchor = stage._read_json_gcs(f'gs://{stage.TEST_BUCKET}/_analysis_state/{symbol}/reference.json')
            if remote_anchor != anchor:
                raise RuntimeError('repair_anchor_changed')
            writes = {}
            for name, uri in uris.items():
                actual = stage._read_json_gcs(uri)
                if not actual:
                    raise RuntimeError('repair_missing_' + name)
                baseline = deepcopy(published)
                if name == 'current':
                    baseline.update(sol_anchor_sha256=stage.reference_key(anchor),
                                    last_full_report_at=anchor['generated_at'])
                normalized = deepcopy(actual)
                normalized['review_memory'] = baseline['review_memory']
                # Analyst backfill refreshes this independent receipt timestamp
                # without a new report. Preserve its live value; no other
                # analyst field, report date, judgment or review may differ.
                summary = normalized.get('analyst_ratings_summary')
                prior_summary = baseline.get('analyst_ratings_summary')
                if isinstance(summary, dict) and isinstance(prior_summary, dict):
                    if 'as_of' in prior_summary:
                        summary['as_of'] = prior_summary['as_of']
                if normalized != baseline or actual['review_memory'] not in (
                        published['review_memory'], expected['review_memory']):
                    raise RuntimeError('repair_changed_' + name)
                candidate = deepcopy(actual)
                candidate['review_memory'] = deepcopy(expected['review_memory'])
                read_memory(candidate, anchor)
                stage.write_json(work / (name + '.before.json'), actual)
                stage.write_json(work / (name + '.after.json'), candidate)
                writes[name] = candidate
            audit['status'] = 'validated'
            if execute:
                # Recheck the whole snapshot before the first write. Do not
                # overwrite an independent refresh that raced with staging.
                for name, uri in uris.items():
                    if stage._read_json_gcs(uri) != stage.read_json(work / (name + '.before.json')):
                        raise RuntimeError('repair_concurrent_change_' + name)
                for name, uri in uris.items():
                    stage._copy_json(work / (name + '.after.json'), uri)
                for name, uri in uris.items():
                    if stage._read_json_gcs(uri) != writes[name]:
                        raise RuntimeError('repair_readback_mismatch_' + name)
                stage.write_json(root / 'output' / symbol / 'latest.json', writes['report'])
                stage.write_json(root / 'data/analysis_state' / symbol / 'current.json', writes['current'])
                audit.update(status='repaired', executed=True)
    except Exception as exc:
        audit.update(status='failed', error=str(exc))
        raise
    finally:
        stage.write_json(work / 'audit.json', audit)
    return work, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--correction-dir', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    work, audit = repair(Path.cwd(), args.correction_dir.resolve(), args.execute)
    print(json.dumps({'work': str(work), **audit}))


if __name__ == '__main__':
    main()
