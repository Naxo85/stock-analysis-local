"""Close a stopped batch's stale RUNNING indicator without resuming the batch."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from src.local_runner.gcs_uploader import require_gcloud


BUCKET = "stock-analysis-reports-naxo85"
STATUS_URI = f"gs://{BUCKET}/commands/status/latest.json"
PROGRESS_URI = f"gs://{BUCKET}/commands/progress/latest.json"


def reconciled_progress(
    progress: dict, status: dict, *, now: datetime | None = None
) -> dict:
    """Keep completed counts intact and close only a matching terminal command."""
    command_id = str(progress.get("command_id") or "")
    if not command_id or command_id != str(status.get("id") or ""):
        raise ValueError("Progress and terminal command IDs differ")
    if progress.get("status") != "running":
        raise ValueError("Progress is not RUNNING")
    if status.get("status") not in {"failed", "ok"}:
        raise ValueError("Command is not terminal")
    try:
        heartbeat = datetime.fromisoformat(str(progress["heartbeat_at"]).replace("Z", "+00:00"))
        finished = datetime.fromisoformat(str(status["finished_at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError) as exc:
        raise ValueError("Missing or invalid heartbeat/finish timestamp") from exc
    if heartbeat.tzinfo is None or finished.tzinfo is None:
        raise ValueError("Heartbeat and finish timestamps must have a timezone")
    if heartbeat > finished:
        raise ValueError("Progress heartbeat is newer than the terminal command; a resumed run may be active")
    completed = int(progress.get("completed") or 0)
    total = int(progress.get("total") or 0)
    if status["status"] == "ok" and completed != total:
        raise ValueError("Successful command has an incomplete progress count")
    result = dict(progress)
    result["status"] = "completed" if status["status"] == "ok" else "failed"
    result["heartbeat_at"] = (now or datetime.now(timezone.utc)).isoformat()
    result["updated_at"] = result["heartbeat_at"]
    result["eta_seconds"] = None
    result["current"] = {"phase": "stopped", "ticker": "", "preparing": [],
                         "analyzing": [], "publishing": []}
    result["reconciliation"] = {
        "reason": "terminal_command_with_stale_progress",
        "command_status": status["status"],
        "command_finished_at": status.get("finished_at"),
        "unpublished": max(0, total - completed),
    }
    return result


def _gcloud_json(gcloud: str, uri: str) -> dict:
    output = subprocess.run(
        [gcloud, "storage", "cat", uri], check=False, capture_output=True,
        text=True, encoding="utf-8", timeout=25,
    )
    if output.returncode:
        raise RuntimeError(
            f"GCS read failed for {uri}: "
            f"{(output.stderr or output.stdout).strip()[:500]}"
        )
    payload = json.loads(output.stdout)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {uri}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command-id", required=True)
    parser.add_argument("--progress-path", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    gcloud = require_gcloud()
    remote_status = _gcloud_json(gcloud, STATUS_URI)
    remote_progress = _gcloud_json(gcloud, PROGRESS_URI)
    local_progress = json.loads(args.progress_path.read_text(encoding="utf-8"))
    if any(
        identifier != args.command_id
        for identifier in (
            str(remote_status.get("id") or ""),
            str(remote_progress.get("command_id") or ""),
            str(local_progress.get("command_id") or ""),
        )
    ):
        raise ValueError("A newer/different command owns a status or progress object")
    if args.verify:
        if remote_status.get("status") != "failed" or remote_progress.get("status") != "failed":
            raise ValueError("Remote command/progress is not closed as failed")
        if remote_progress.get("completed") != local_progress.get("completed"):
            raise ValueError("Local and remote completed counts differ")
        print(f"Verified failed {remote_progress['completed']}/{remote_progress['total']}")
        return 0
    if int(local_progress.get("completed") or 0) < int(remote_progress.get("completed") or 0):
        raise ValueError("Local progress is older than remote progress")
    updated = reconciled_progress(local_progress, remote_status)
    print(
        f"{args.command_id}: {updated['status']} "
        f"{updated['completed']}/{updated['total']} "
        f"unpublished={updated['reconciliation']['unpublished']}"
    )
    if not args.execute:
        return 0
    # Read latest again immediately before the write to avoid clobbering a new run.
    if _gcloud_json(gcloud, STATUS_URI) != remote_status or _gcloud_json(gcloud, PROGRESS_URI) != remote_progress:
        raise RuntimeError("Remote status/progress changed during reconciliation")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as stream:
        json.dump(updated, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    try:
        subprocess.run(
            [gcloud, "storage", "cp", "--content-type=application/json",
             str(temporary), PROGRESS_URI],
            check=True, capture_output=True, text=True, encoding="utf-8", timeout=25,
        )
        args.progress_path.write_text(
            json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    finally:
        temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
