"""Offline export of existing dated inputs: no acquisition or model calls."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import time
from src.local_runner.archive_technical_observations import export_file, write_archive
from src.local_runner.technical_archive import validate_archive
ROOT = Path.cwd()
WORK = ROOT / '.tmp/audit_execution_20261017'
def sha(body):
    return hashlib.sha256(body).hexdigest()
def stats(values):
    return {'count': len(values), 'total': sum(values), 'min': min(values), 'median': statistics.median(values), 'max': max(values)}
def test_export_originals_preserves_evidence():
    start = time.perf_counter()
    comparison_body = (WORK/'candidate_comparison.json').read_bytes()
    comparison = json.loads(comparison_body)
    paths = list(dict.fromkeys(item['path'] for item in comparison))
    rows = []
    skipped = []
    original_digests = {}
    for relative in paths:
        path = ROOT / relative
        body = path.read_bytes()
        original_digests[relative] = sha(body)
        document = json.loads(body)
        history = (document.get('slim', {}).get('price_history') or {}).get('sessions') or []
        if not history:
            skipped.append(relative)
            continue
        exported = export_file(path, WORK/'archive_originals')
        archive_body = Path(exported['path']).read_bytes()
        archive = validate_archive(json.loads(archive_body))
        assert archive['daily']['rows'] == history
        assert archive['source_file_sha256'] == sha(body)
        assert archive['snapshot_at'] == document['slim']['as_of']
        assert archive['origin'] == 'derived_local_document'
        assert archive['options']['coverage']['full_chain_reconstruction'] is False
        assert archive['options']['coverage']['market_complete'] is False
        assert exported['history_252_complete'] is False
        assert exported['sampled_options_complete'] is False
        assert sha(archive_body) == exported['sha256']
        assert export_file(path, WORK/'archive_originals') == exported
        rows.append({'source': relative, 'source_sha256_before': sha(body),
            'source_sha256_after': sha(path.read_bytes()), 'source_bytes': len(body),
            'symbol': archive['symbol'], 'history_rows': len(history),
            'selected_option_records': len(archive['options']['records']),
            'history_coverage': archive['daily']['coverage'], **exported})
    unchanged = all(sha((ROOT/p).read_bytes()) == digest for p,digest in original_digests.items())
    assert unchanged
    assert len(rows) == 184
    assert Counter(r['history_rows'] for r in rows) == {20: 184}
    assert len({row['archive_id'] for row in rows}) == 184
    spec = importlib.util.spec_from_file_location('archive_fixture', ROOT/'tests/test_technical_archive_v40.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fixture = module.capture()
    fixture_exported = write_archive(WORK/'archive_fixture', fixture)
    result = {'created_at': datetime.now(timezone.utc).isoformat(),
        'comparison_sha256': sha(comparison_body), 'comparison_rows': len(comparison),
        'unique_source_paths': len(paths), 'history_inputs_exported': len(rows),
        'without_stored_history': len(skipped), 'all_598_original_hashes_unchanged': unchanged,
        'source_bytes': stats([r['source_bytes'] for r in rows]),
        'archive_bytes': stats([r['bytes'] for r in rows]),
        'history_rows_distribution': dict(Counter(r['history_rows'] for r in rows)),
        'snapshot_dates': dict(Counter(r['snapshot_at'][:10] for r in rows)),
        'history_252_complete_count': sum(r['history_252_complete'] for r in rows),
        'sampled_options_complete_count': sum(r['sampled_options_complete'] for r in rows),
        'selected_option_records': stats([r['selected_option_records'] for r in rows]),
        'fixture': {'scope': 'synthetic_270_daily_rows_one_contract_two_cached_responses', **fixture_exported},
        'local_export_seconds_including_validation_and_repeat': round(time.perf_counter()-start, 3),
        'scope': 'local_files_only_no_new_acquisition_no_models_no_retrospective_full_chain',
        'source_code_sha256': {p: sha((ROOT/p).read_bytes()) for p in (
          'src/local_runner/technical_archive.py', 'src/local_runner/archive_technical_observations.py')},
        'rows': rows}
    (WORK/'archive_replay_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (WORK/'archive_original_example.json').write_text(json.dumps(next(r for r in rows if r['symbol']=='CAT' and r['snapshot_at'].startswith('2026-10-16')), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
