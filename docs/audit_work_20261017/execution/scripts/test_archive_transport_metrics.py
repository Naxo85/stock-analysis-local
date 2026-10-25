"""Record mocked transport costs; never contacts a provider."""
import hashlib
import importlib.util
import json
from pathlib import Path
from src.local_runner.technical_archive import canonical, validate_archive
ROOT = Path.cwd()
def test_archive_mock_transport_costs():
    spec = importlib.util.spec_from_file_location('archive_fixture', ROOT/'tests/test_technical_archive_v40.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw, slim = module.raw_modules()
    before, requests_before, mirror_before = module.invoke_raw(raw, False, False)
    after, requests_after, mirror_after = module.invoke_raw(raw, True, True)
    archive = after.pop('_evaluation_archive')
    assert before == after and mirror_before == mirror_after
    clean_before = slim._build_slim(before)
    clean_after = slim._build_slim(after)
    assert clean_before == clean_after
    assert requests_before == requests_after
    validate_archive(archive)
    def size(value): return len(canonical(value).encode('utf-8'))
    result = {'scope': 'synthetic_CAT_270_rows_one_option_contract_mocked_provider',
      'provider_option_request_count_off': requests_before, 'provider_option_request_count_on': requests_after,
      'provider_history_requests': 'stubbed identically; individual adapter additionally verified by test_provider_history_receipts_keep_symbol_window_and_rows_without_headers',
      'clean_financial_raw_identical': before == after, 'published_mirror_identical': mirror_before == mirror_after,
      'clean_slim_identical': clean_before == clean_after, 'clean_slim_bytes': size(clean_before),
      'archive_bytes_canonical': size(archive), 'raw_bytes_without_sidecar': size(before),
      'raw_bytes_with_sidecar': size(dict(after, _evaluation_archive=archive)),
      'slim_bytes_with_sidecar': size(dict(clean_after, _evaluation_archive=archive)),
      'model_context_sha256': hashlib.sha256(canonical(clean_before).encode('utf-8')).hexdigest(),
      'scope_limits': 'No live latency, provider fee, chain-size distribution or token-count estimate.'}
    (ROOT/'.tmp/audit_execution_20261017/archive_mock_transport_results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
