"""Revalidate frozen receipts without model calls; optionally publish with normal guards.

The failed batch and original inputs remain historical evidence. Recovery has its
own staging directory; it never turns the original failed command into success.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

from src.local_runner import adaptive_stage as stage
from src.local_runner.ownership import recorded_ownership


def recover(root, batch, symbol, *, execute=False):
    source = batch / 'adaptive' / symbol
    if not source.is_dir():
        raise RuntimeError('recovery_source_missing')
    context = stage.read_json(source / 'input.json')
    if context.get('symbol') != symbol:
        raise RuntimeError('recovery_symbol_mismatch')
    original = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in source.iterdir() if p.is_file()}
    recovery = root / 'logs/recoveries' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    work = recovery / 'adaptive' / symbol
    shutil.copytree(source, work)
    budget = recovery / 'codex_budget.json'
    shutil.copy2(batch / 'codex_budget.json', budget)
    audit = {'source_batch': str(batch), 'symbol': symbol, 'original_sha256': original,
             'model_calls_allowed': False, 'executed': False}
    try:
        # All schema, instruction, input and model receipt checks stay enabled.
        review = stage.analyze(root, work, symbol, budget, False, reuse_only=True)
        payload = stage.read_json(work / 'publish/output' / symbol / 'latest.json')
        audit.update(generated_at=payload.get('generated_at'), status='validated',
                     review_status=review['status'])
        if execute:
            owned, evidence = recorded_ownership(symbol)
            if owned is not context.get('owned'):
                raise RuntimeError('recovery_rejected_portfolio_ownership_changed')
            audit['ownership_check'] = evidence
            # Publication lock + unchanged base/anchor/newer-review checks.
            review = stage.publish(root, work, symbol)
            audit.update(status='published', executed=True, published_at=review['published_at'])
    except Exception as exc:
        audit.update(status='failed', error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        audit['original_unchanged'] = original == {
            p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()}
        stage.write_json(recovery / 'recovery.json', audit)
    return recovery, audit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticker')
    parser.add_argument('--batch-dir', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    root = stage.one._find_repo_root(Path.cwd())
    recovery, audit = recover(root, args.batch_dir.resolve(), args.ticker.upper(), execute=args.execute)
    print(json.dumps({'recovery':str(recovery), **audit}, ensure_ascii=False, default=str))


if __name__ == '__main__': main()
