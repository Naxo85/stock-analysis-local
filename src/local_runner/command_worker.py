"""Process stock-analysis commands from a GCS-backed queue."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from src.local_runner.gcs_uploader import CONTENT_TYPE_JSON, require_gcloud


BUCKET = "stock-analysis-reports-naxo85"
COMMAND_ROOT = "commands"
PENDING_PREFIX = f"{COMMAND_ROOT}/pending"
RUNNING_PREFIX = f"{COMMAND_ROOT}/running"
COMPLETED_PREFIX = f"{COMMAND_ROOT}/completed"
FAILED_PREFIX = f"{COMMAND_ROOT}/failed"
LATEST_STATUS_URI = f"gs://{BUCKET}/{COMMAND_ROOT}/status/latest.json"
TRADING_CONFIG_URI = f"gs://{BUCKET}/config/tickers.json"
CORE_CONFIG_URI = f"gs://{BUCKET}/config/tickers_core.json"
DEFAULT_MAX_PARALLEL = 6
MAX_PARALLEL = 8
LOCK_STALE_SECONDS = 4 * 60 * 60
OUTPUT_TAIL_CHARS = 12_000
GCLOUD_TIMEOUT_SECONDS = 60

ACTION_TICKER = "analyze_ticker"
ACTION_TRADING = "analyze_trading"
ACTION_CORE = "analyze_core"
ALLOWED_ACTIONS = {ACTION_TICKER, ACTION_TRADING, ACTION_CORE}

COMMAND_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
TICKER_RE = re.compile(r"^[A-Z0-9.-]{1,15}$")


@dataclass(frozen=True)
class CommandRequest:
    command_id: str
    action: str
    ticker: str | None
    max_parallel: int
    created_at: str | None

    @classmethod
    def from_payload(
        cls,
        payload: Any,
        *,
        fallback_id: str | None = None,
    ) -> "CommandRequest":
        if not isinstance(payload, dict):
            raise ValueError("invalid_command: expected a JSON object")

        command_id = str(payload.get("id") or fallback_id or "").strip()
        if not COMMAND_ID_RE.fullmatch(command_id):
            raise ValueError("invalid_command_id")

        action = str(payload.get("action") or "").strip()
        if action not in ALLOWED_ACTIONS:
            raise ValueError(
                "invalid_action: expected analyze_ticker, analyze_trading, or analyze_core"
            )

        ticker: str | None = None
        if action == ACTION_TICKER:
            ticker = str(payload.get("ticker") or "").strip().upper()
            if not TICKER_RE.fullmatch(ticker):
                raise ValueError("invalid_ticker")

        raw_parallel = payload.get("max_parallel", DEFAULT_MAX_PARALLEL)
        if isinstance(raw_parallel, bool):
            raise ValueError("invalid_max_parallel")

        try:
            max_parallel = int(raw_parallel)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_max_parallel") from exc

        if not 1 <= max_parallel <= MAX_PARALLEL:
            raise ValueError(f"invalid_max_parallel: expected 1-{MAX_PARALLEL}")

        created_at_value = payload.get("created_at")
        created_at = str(created_at_value) if created_at_value else None

        return cls(
            command_id=command_id,
            action=action,
            ticker=ticker,
            max_parallel=max_parallel,
            created_at=created_at,
        )


@dataclass(frozen=True)
class CommandExecution:
    argv: tuple[str, ...]
    label: str


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())

    if args.command_file:
        payload = _read_json_file(args.command_file)
        request = CommandRequest.from_payload(
            payload,
            fallback_id=args.command_file.stem,
        )
        execution = build_execution(request)
        result = execute_command(
            request,
            execution,
            repo_root=repo_root,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] in {"ok", "dry_run"} else 1

    lock_path = repo_root / "logs" / "command_worker.lock"
    with local_worker_lock(lock_path) as acquired:
        if not acquired:
            print("WORKER_BUSY: another command worker is active")
            return 0

        return process_one_gcs_command(repo_root=repo_root)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process one stock-analysis command from GCS."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--once",
        action="store_true",
        help="Process at most one pending command from GCS, then exit.",
    )
    source.add_argument(
        "--command-file",
        type=Path,
        help="Process a local command JSON file for diagnostics.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print a local command without executing it.",
    )
    args = parser.parse_args(argv)

    if args.once and args.dry_run:
        parser.error("--dry-run is only supported with --command-file")

    return args


def process_one_gcs_command(*, repo_root: Path) -> int:
    gcloud_path = require_gcloud()
    print("QUEUE: consultando órdenes pendientes en GCS...", flush=True)
    pending = list_pending_commands(gcloud_path)

    if not pending:
        print("NO_COMMANDS: no hay órdenes pendientes.", flush=True)
        return 0

    pending_uri = pending[0]
    object_name = pending_uri.rsplit("/", 1)[-1]
    fallback_id = Path(object_name).stem
    running_uri = _gcs_uri(RUNNING_PREFIX, object_name)
    print(f"QUEUE: orden encontrada: {fallback_id}", flush=True)
    print("QUEUE: reclamando orden...", flush=True)

    try:
        _run_gcloud(gcloud_path, "storage", "mv", pending_uri, running_uri)
    except subprocess.CalledProcessError:
        print(f"COMMAND_NOT_CLAIMED: {pending_uri}", flush=True)
        return 0

    print(f"QUEUE: orden reclamada en running: {fallback_id}", flush=True)

    raw_payload: Any = None
    request: CommandRequest | None = None
    started = _utc_now()

    try:
        raw_payload = json.loads(_gcloud_cat(gcloud_path, running_uri))
        request = CommandRequest.from_payload(raw_payload, fallback_id=fallback_id)
        execution = build_execution(request)
        print(
            f"QUEUE: iniciando {request.action} ({execution.label}).",
            flush=True,
        )
        print("QUEUE: no cierres esta ventana hasta ver OK o FAILED.", flush=True)
        result = execute_command(
            request,
            execution,
            repo_root=repo_root,
            dry_run=False,
        )
    except Exception as exc:
        result = {
            "id": request.command_id if request else fallback_id,
            "action": request.action if request else _payload_action(raw_payload),
            "status": "failed",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "started_at": started.isoformat(),
            "finished_at": _utc_now().isoformat(),
        }

    destination_prefix = (
        COMPLETED_PREFIX if result.get("status") == "ok" else FAILED_PREFIX
    )
    result_uri = _gcs_uri(destination_prefix, f"{fallback_id}.json")

    try:
        local_result_path = upload_result_json(
            gcloud_path=gcloud_path,
            repo_root=repo_root,
            result=result,
            destination=result_uri,
        )
        try:
            _run_gcloud(
                gcloud_path,
                "storage",
                "cp",
                f"--content-type={CONTENT_TYPE_JSON}",
                str(local_result_path),
                LATEST_STATUS_URI,
            )
        except Exception as exc:
            print(f"WARNING: no se pudo actualizar latest status: {exc}", flush=True)
        _run_gcloud(gcloud_path, "storage", "rm", running_uri)
    except Exception as exc:
        print(f"FAILED_TO_FINALIZE {fallback_id}: {exc}")
        return 1

    if result.get("status") == "ok":
        print(f"OK COMMAND {fallback_id}: {result.get('label', '')}")
        return 0

    print(
        f"FAILED COMMAND {fallback_id}: "
        f"{result.get('error_type', 'failed')} - "
        f"{result.get('error_message', '')}"
    )
    return 1


def list_pending_commands(gcloud_path: str) -> list[str]:
    pattern = _gcs_uri(PENDING_PREFIX, "*.json")
    completed = subprocess.run(
        [gcloud_path, "storage", "ls", pattern],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=GCLOUD_TIMEOUT_SECONDS,
    )

    if completed.returncode != 0:
        combined = f"{completed.stdout}\n{completed.stderr}".lower()
        if "matched no objects" in combined or "not found" in combined:
            return []
        raise RuntimeError(
            f"gcs_list_failed: {completed.stderr.strip() or completed.stdout.strip()}"
        )

    return sorted(
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip().endswith(".json")
    )


def build_execution(request: CommandRequest) -> CommandExecution:
    base = (sys.executable, "-m")

    if request.action == ACTION_TICKER:
        assert request.ticker is not None
        return CommandExecution(
            argv=base
            + (
                "src.local_runner.run_one",
                request.ticker,
                "--run-full",
            ),
            label=request.ticker,
        )

    if request.action == ACTION_TRADING:
        return CommandExecution(
            argv=base
            + (
                "src.local_runner.run_batch",
                "--from-gcs",
                "--upload-real",
                "--max-parallel",
                str(request.max_parallel),
            ),
            label="TRADING",
        )

    if request.action == ACTION_CORE:
        return CommandExecution(
            argv=base
            + (
                "src.local_runner.run_batch",
                "--config-gcs",
                CORE_CONFIG_URI,
                "--upload-real",
                "--max-parallel",
                str(request.max_parallel),
            ),
            label="CORE",
        )

    raise ValueError(f"unsupported_action: {request.action}")


def execute_command(
    request: CommandRequest,
    execution: CommandExecution,
    *,
    repo_root: Path,
    dry_run: bool,
) -> dict[str, Any]:
    started = _utc_now()

    if dry_run:
        return {
            "id": request.command_id,
            "action": request.action,
            "ticker": request.ticker,
            "label": execution.label,
            "status": "dry_run",
            "argv": list(execution.argv),
            "started_at": started.isoformat(),
            "finished_at": _utc_now().isoformat(),
        }

    started_perf = time.perf_counter()
    process = subprocess.Popen(
        list(execution.argv),
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    output_lines: list[str] = []

    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
        output_lines.append(line)

    return_code = process.wait()
    finished = _utc_now()
    stdout = "".join(output_lines).strip()

    result: dict[str, Any] = {
        "id": request.command_id,
        "action": request.action,
        "ticker": request.ticker,
        "label": execution.label,
        "status": "ok" if return_code == 0 else "failed",
        "created_at": request.created_at,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round(time.perf_counter() - started_perf, 3),
        "exit_code": return_code,
        "stdout_tail": stdout[-OUTPUT_TAIL_CHARS:],
        "stderr_tail": "",
    }

    if return_code != 0:
        result["error_type"] = "analysis_command_failed"
        result["error_message"] = (
            _last_nonempty_line(stdout)
            or f"exit_code={return_code}"
        )

    return result


def upload_result_json(
    *,
    gcloud_path: str,
    repo_root: Path,
    result: dict[str, Any],
    destination: str,
) -> Path:
    command_id = str(result.get("id") or "unknown")
    now = _utc_now()
    log_dir = (
        repo_root
        / "logs"
        / "command_worker"
        / now.strftime("%Y-%m-%d")
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    local_path = log_dir / f"{command_id}.json"
    local_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _run_gcloud(
        gcloud_path,
        "storage",
        "cp",
        f"--content-type={CONTENT_TYPE_JSON}",
        str(local_path),
        destination,
    )
    return local_path


@contextmanager
def local_worker_lock(lock_path: Path) -> Iterator[bool]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    _remove_stale_lock(lock_path)

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        yield False
        return

    try:
        payload = {
            "pid": os.getpid(),
            "created_at": _utc_now().isoformat(),
        }
        os.write(fd, json.dumps(payload).encode("utf-8"))
        os.close(fd)
        fd = -1
        yield True
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _remove_stale_lock(lock_path: Path) -> None:
    try:
        age = time.time() - lock_path.stat().st_mtime
    except FileNotFoundError:
        return

    lock_pid = _read_lock_pid(lock_path)
    process_alive = _process_exists(lock_pid) if lock_pid is not None else False

    if age > LOCK_STALE_SECONDS or not process_alive:
        reason = "stale" if age > LOCK_STALE_SECONDS else "orphaned"
        print(f"LOCK: eliminando lock {reason}: {lock_path}", flush=True)
        lock_path.unlink(missing_ok=True)


def _read_lock_pid(lock_path: Path) -> int | None:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        pid = int(payload.get("pid"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None

    return pid if pid > 0 else None


def _process_exists(pid: int) -> bool:
    if os.name == "nt":
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _run_gcloud(gcloud_path: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [gcloud_path, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=GCLOUD_TIMEOUT_SECONDS,
    )


def _gcloud_cat(gcloud_path: str, uri: str) -> str:
    return _run_gcloud(gcloud_path, "storage", "cat", uri).stdout


def _gcs_uri(prefix: str, name: str) -> str:
    return f"gs://{BUCKET}/{prefix}/{name}"


def _payload_action(payload: Any) -> str | None:
    if isinstance(payload, dict) and payload.get("action") is not None:
        return str(payload["action"])
    return None


def _last_nonempty_line(value: str) -> str:
    for line in reversed(value.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped[:500]
    return ""


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"command_file_not_found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid_command_json: {path}") from exc


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src").is_dir() and (candidate / "prompts").is_dir():
            return candidate
    raise RuntimeError("repo_root_not_found")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


if __name__ == "__main__":
    raise SystemExit(main())
