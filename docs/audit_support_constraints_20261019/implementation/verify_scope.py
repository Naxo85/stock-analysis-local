"""Check the exact implementation against the saved pre-edit tree, offline."""
import ast
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = ROOT/'.tmp/support41_baseline'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def functions(text):
    tree = ast.parse(text)
    return {node.name: ast.dump(node) for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def main():
    archive = OUT/'baseline.zip'
    if not archive.exists():
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as saved:
            for name in ('hashes.json', 'config/codex_analysis.json',
                         'gcp_functions/support_resistances_raw/main.py',
                         'gcp_functions/support_resistances_slim/main.py'):
                saved.write(BASE/name, name)
    with zipfile.ZipFile(archive) as saved:
        baseline = {name: saved.read(name).decode('utf-8') for name in saved.namelist()}
    expected = json.loads(baseline['hashes.json'])
    prompts = {path: digest for path, digest in expected.items()
               if path.startswith('prompts/') and not path.endswith(('_v41.md', '_v14.md', 'revision41.md'))}
    assert all(sha(ROOT/path) == digest for path, digest in prompts.items())
    source_scope = {}
    allowed = {'raw': {'support_resistances_raw', '_cluster_swing_lows'},
               'slim': {'support_resistances_slim', '_fetch_raw', '_build_slim', '_slim_levels'}}
    additions = {'raw': {'_observe_support_origins'}, 'slim': {'_slim_support_origins'}}
    for kind in ('raw', 'slim'):
        relative = f'gcp_functions/support_resistances_{kind}/main.py'
        old, new = functions(baseline[relative]), functions((ROOT/relative).read_text(encoding='utf-8'))
        changed = {name for name in old.keys() & new.keys() if old[name] != new[name]}
        added, removed = new.keys()-old.keys(), old.keys()-new.keys()
        assert changed <= allowed[kind], (kind, changed)
        assert added == additions[kind] and not removed, (kind, added, removed)
        source_scope[kind] = {'changed_functions': sorted(changed), 'added_functions': sorted(added),
                              'unchanged_functions': len(old)-len(changed)}
    before = json.loads(baseline['config/codex_analysis.json'])
    after = json.loads((ROOT/'config/codex_analysis.json').read_text(encoding='utf-8'))
    assert after['routing_revision'] in (40, 41)
    comparison = dict(after, routing_revision=before['routing_revision'])
    assert comparison == before
    assert after['triage_model'] == after['report_model'] == 'gpt-6.1-sol'
    assert after['triage_effort'] == 'medium' and after['report_effort'] == 'high'
    assert after['priority_itv_sessions'] == after['watchlist_itv_sessions'] == 5
    assert after['max_model_parallel'] == 6
    # Original published/reference documents, not the deliberately changed source.
    census = json.loads((OUT.parent/'weights/census.json').read_text(encoding='utf-8'))
    for item in census['files']:
        assert sha(ROOT/item['path']) == item['sha256'], item['path']
    verified = len(census['files'])
    payload = {'ok': True, 'unchanged_legacy_prompt_files': len(prompts),
               'source_scope': source_scope, 'policy_revision': after['routing_revision'],
               'all_other_policy_fields_exact': True, 'original_hashes_checked': verified,
               'baseline_sha256': sha(archive)}
    (OUT/'scope_verification.json').write_text(json.dumps(payload, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(payload, indent=2))


if __name__ == '__main__': main()
