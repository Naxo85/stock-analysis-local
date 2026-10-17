"""Run an explicitly requested full-market renewal under the normal worker lock."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_runner import command_worker as worker
from src.local_runner.adaptive_budget import write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--command-id', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    request = worker.CommandRequest.from_payload({
        'id': args.command_id, 'action': worker.ACTION_MARKET, 'max_parallel': 6})
    work = root / 'logs' / 'full_market_launch' / request.command_id
    with worker.local_worker_lock(root / 'logs' / 'command_worker.lock') as acquired:
        if not acquired:
            raise RuntimeError('another_command_worker_is_active')
        if work.exists():
            raise RuntimeError('launch_id_already_used_inspect_before_retry')
        gcloud = worker.require_gcloud()
        if worker.list_pending_commands(gcloud):
            raise RuntimeError('pending_commands_exist_no_duplicate_launch')
        progress = json.loads(worker._gcloud_cat(gcloud,
            f'gs://{worker.BUCKET}/commands/progress/latest.json'))
        if progress.get('status') in ('running', 'starting', 'queued'):
            raise RuntimeError('remote_analysis_active_inspect_before_launch')
        execution = worker.build_execution(request)
        argv = list(execution.argv)
        if '--analysis-mode' in argv:
            index = argv.index('--analysis-mode')
            del argv[index:index + 2]
        execution = worker.CommandExecution(
            argv=tuple(argv) + ('--analysis-mode', 'reference'), label=execution.label)
        write_json(work / 'launch.json', {'id': request.command_id,
            'action': request.action, 'started_at': worker._utc_now().isoformat(),
            'argv': list(execution.argv), 'scope': worker.MARKET_CONFIG_URI,
            'reason': 'Explicit user request: renew all reports as new full baselines.'})
        print('LAUNCH ' + request.command_id, flush=True)
        result = worker.execute_command(request, execution, repo_root=root, dry_run=False)
        write_json(work / 'result.json', result)
        prefix = worker.COMPLETED_PREFIX if result['status'] == 'ok' else worker.FAILED_PREFIX
        local_result = worker.upload_result_json(gcloud_path=gcloud, repo_root=root,
            result=result, destination=worker._gcs_uri(prefix, request.command_id + '.json'))
        worker._run_gcloud(gcloud, 'storage', 'cp', '--content-type=application/json',
                          str(local_result), worker.LATEST_STATUS_URI)
        print('FINISHED ' + result['status'], flush=True)
        return 0 if result['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
