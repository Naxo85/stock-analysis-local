"""Resume one interrupted market command and reconcile its remote result."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.local_runner import command_worker as worker


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command-file", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    checkpoint = args.checkpoint.resolve()
    if not checkpoint.is_relative_to(root / "logs" / "batch"):
        raise RuntimeError("checkpoint_outside_batch_logs")
    state = worker._read_json_file(checkpoint)
    request = worker.CommandRequest.from_payload(worker._read_json_file(args.command_file))
    progress = worker._read_json_file(checkpoint.with_name("sheet_progress.json"))
    if progress.get("command_id") != request.command_id:
        raise RuntimeError("checkpoint_command_mismatch")
    if request.action != worker.ACTION_MARKET:
        raise RuntimeError("resume_supports_market_only")
    execution = worker.build_execution(request)
    execution = worker.CommandExecution(
        argv=execution.argv + ("--resume-pipeline-from", str(checkpoint)),
        label=execution.label,
    )
    with worker.local_worker_lock(root / "logs" / "command_worker.lock") as acquired:
        if not acquired:
            raise RuntimeError("another_command_worker_is_active")
        print(f"RECOVERY {request.command_id}: {len(state['ticker_order'])} tickers; {checkpoint}", flush=True)
        result = worker.execute_command(request, execution, repo_root=root, dry_run=False)
        gcloud = worker.require_gcloud()
        prefix = worker.COMPLETED_PREFIX if result["status"] == "ok" else worker.FAILED_PREFIX
        result["resumed_from_checkpoint"] = str(checkpoint)
        local_result = worker.upload_result_json(
            gcloud_path=gcloud, repo_root=root, result=result,
            destination=worker._gcs_uri(prefix, request.command_id + ".json"),
        )
        worker._run_gcloud(gcloud, "storage", "cp", "--content-type=application/json",
                           str(local_result), worker.LATEST_STATUS_URI)
        print(f"RECOVERY {result['status']}: {result.get('batch_success')}/{result.get('batch_total')}", flush=True)
        return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
