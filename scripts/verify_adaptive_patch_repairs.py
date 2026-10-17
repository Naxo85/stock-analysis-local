"""Saved incident replay and explicit isolated Luna checks; never publish/run batch."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_runner.adaptive_budget import read_json, write_json, check_quota, read_codex_rate_limits
from src.local_runner.adaptive_context import model_context, validation_context
from src.local_runner.adaptive_policy import load_policy, maintenance_precheck, itv_state
from src.local_runner.adaptive_maintenance import apply_update, maintenance_schema, maintenance_decision
from src.local_runner.adaptive_codex import call_codex
from src.local_runner.adaptive_preflight import check
from src.local_runner import run_one
from scripts.verify_adaptive_maintenance import instructions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-dir', type=Path, required=True)
    parser.add_argument('--execute-luna', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    policy = load_policy(root)
    source = args.batch_dir.resolve()/'adaptive'
    work = root/'logs/adaptive_patch_evaluation'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    contexts, replay = {}, []
    for folder in sorted(source.iterdir()):
        raw = read_json(folder/'input.json')
        raw.update(maintenance_precheck(raw['reference'], raw['slim'], raw['sol_reference'], owned=raw['owned']))
        raw['itv'] = itv_state(raw['sol_reference'], owned=raw['owned'], priority=raw['tier']=='priority',
                              now=datetime.fromisoformat(raw['prepared_at']), policy=read_json(folder/'policy.json'))
        contexts[folder.name] = raw
        verdict = read_json(folder/'triage.json')
        if verdict.get('decision') != 'update':
            continue
        hashes = {name: hashlib.sha256((folder/name).read_bytes()).hexdigest()
                  for name in ('input.json', 'triage.response', 'triage.receipt.json')}
        row = {'symbol': folder.name, 'source_hashes': hashes, 'model_called': False}
        try:
            audit = []
            candidate = apply_update(verdict, model_context(raw), audit=audit)
            validation = run_one.validate_markdown(candidate, authoritative_context=validation_context(raw),
                require_support_strengths=True, require_resistance=True, require_separate_scores=True)
            row.update(validation=validation.to_dict(), normalizations=audit,
                       candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest())
        except ValueError as exc:
            row.update(error=str(exc))
        replay.append(row)
        print(json.dumps({'symbol': folder.name, 'replay_ok': row.get('validation', {}).get('ok', False),
                          'error': row.get('error')}, ensure_ascii=True), flush=True)
    write_json(work/'replay.json', {'model_called': False, 'published': False, 'rows': replay})
    if not args.execute_luna:
        print(str(work), flush=True)
        return
    check(root, policy)
    check_quota(read_codex_rate_limits(cwd=root))
    selected = {symbol: deepcopy(contexts[symbol]) for symbol in ('RKLB', 'CRWV', 'MRVL')}
    critical = deepcopy(contexts['RKLB'])
    at = datetime.fromisoformat(critical['prepared_at']) - timedelta(seconds=1)
    critical['news']['items'].append({'articleId': 'synthetic-patch-critical-guidance', 'providerCode': 'EVAL',
        'published_at': at.isoformat(), 'headline': 'RKLB: la compañía recorta su previsión anual de ingresos un 35% y comunica riesgo material de liquidez.',
        'source': 'SYNTHETIC EVALUATION ONLY, NOT REAL NEWS'})
    critical['news']['count'] = len(critical['news']['items'])
    selected['critical_news'] = critical
    prefix = instructions(root)
    def run(name):
        raw = selected[name]
        raw.update(evaluation_only=True, evaluation_scenario=name)
        view = model_context(raw)
        view.pop('research_memory', None)
        artifact = work/name
        write_json(artifact/'context.json', raw)
        counterfactual = ('\nEVALUATION HARNESS: Treat supplied synthetic critical news as hypothetical facts under the SAME policy. '
            'Synthetic labels disclose provenance, not a reason to deny the premise. Never publish this fixture.\n') if name=='critical_news' else ''
        receipt = call_codex(workspace=root/'.local/codex-analysis-workspace', artifacts=artifact, kind='triage',
            instructions=prefix+counterfactual, data=view, model=policy['triage_model'], effort=policy['triage_effort'],
            timeout=policy['triage_timeout_seconds'], schema=maintenance_schema(view), max_parallel=policy['max_model_parallel'])
        value = json.loads(receipt['text'])
        decision = maintenance_decision(value, raw['guards'], view)
        row = {'scenario': name, 'decision': decision, 'reason': value['reason'], 'usage': receipt['usage'],
               'model': receipt['model'], 'effort': receipt['reasoning_effort'], 'published': False,
               'passed': decision=='escalate' if name=='critical_news' else decision in ('retain', 'update')}
        if decision=='update':
            try:
                audit = []
                candidate = apply_update(value, view, audit=audit)
                validation = run_one.validate_markdown(candidate, authoritative_context=validation_context(view),
                    require_support_strengths=True, require_resistance=True, require_separate_scores=True)
                write_json(artifact/'validation.json', validation.to_dict())
                row.update(normalizations=audit, candidate_valid=validation.ok)
                row['passed'] = row['passed'] and validation.ok
            except ValueError as exc:
                row.update(error=str(exc), passed=False)
        write_json(artifact/'outcome.json', row)
        print(json.dumps(row, ensure_ascii=True), flush=True)
        return row
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run, selected))
    write_json(work/'summary.json', {'evaluation_only': True, 'published': False, 'results': results,
                                   'passed': all(row['passed'] for row in results)})
    print(str(work), flush=True)
    if not all(row['passed'] for row in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
