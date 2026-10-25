"""Read-only check of the explicitly restored model policy and old receipts."""
from pathlib import Path
import hashlib, json, sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.local_runner.adaptive_policy import load_policy

policy = load_policy(ROOT)
expected = {'triage_model': 'gpt-6.1-sol', 'triage_effort': 'medium',
    'report_model': 'gpt-6.1-sol', 'report_effort': 'high',
    'routing_revision': 41, 'maintenance_context_transport': 'pointer-diff-v1',
    'volume_calculation_guidance': 'selected-sources-v1',
    'priority_itv_sessions': 5, 'watchlist_itv_sessions': 5,
    'max_model_parallel': 6}
for key, value in expected.items(): assert policy[key] == value, key
old = json.loads((ROOT/'docs/audit_sol_input_cost_20261023/results.json').read_text(encoding='utf-8'))
for file, sha in old['hashes'].items():
    assert hashlib.sha256(Path(file).read_bytes()).hexdigest() == sha, file
out = {'policy_sha256': hashlib.sha256((ROOT/'config/codex_analysis.json').read_bytes()).hexdigest(),
    'effective_policy': expected, 'historical_files_unchanged': len(old['hashes']),
    'limits': 'Future preparations load this policy. Frozen attempts retain their original policy. No model/batch run.'}
Path(__file__).with_name('policy_check.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps(out, indent=2))
