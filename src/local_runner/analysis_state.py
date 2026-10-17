"""Persistence helpers for authoritative analysis references."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from src.local_runner.gcs_uploader import TEST_BUCKET, require_gcloud
from src.local_runner.process_control import run_bounded


STATE_PREFIX = "_analysis_state"
GCS_READ_TIMEOUT_SECONDS = 60
GCS_READ_ATTEMPTS = 2
GCS_READ_LOCK_TIMEOUT_SECONDS = 180
GCS_READ_LOCK_INITIALIZATION_GRACE_SECONDS = 5
GCS_READ_LOCK_PATH = Path(".local") / "gcs-read.lock"


def reference_uri(symbol: str) -> str:
    return f"gs://{TEST_BUCKET}/{STATE_PREFIX}/{symbol.strip().upper()}/reference.json"


def load_reference_payload(symbol: str) -> dict[str, Any] | None:
    """Load explicit reference, bootstrapping from canonical latest when absent."""
    normalized = symbol.strip().upper()
    try:
        explicit = _read_json_gcs(reference_uri(normalized))
    except RuntimeError:
        local = _load_local_reference_payload(normalized)
        if local is None:
            raise
        print(
            f"WARNING: using local authoritative reference for {normalized} "
            "after a transient GCS read failure.",
            flush=True,
        )
        return local
    if explicit is not None:
        return explicit
    canonical_uri = f"gs://{TEST_BUCKET}/{normalized}/latest.json"
    canonical = _read_json_gcs(canonical_uri)
    if not isinstance(canonical, dict) or canonical.get("analysis_status") != "ok":
        return None
    canonical = dict(canonical)
    canonical.setdefault("reference_model", "gpt-5.6-sol")
    canonical.setdefault("reference_generated_at", canonical.get("generated_at"))
    score = _score_from_payload(canonical)
    if score is not None:
        canonical.setdefault("reference_score", score)
    canonical["reference_bootstrapped_from"] = canonical_uri
    return canonical


def save_reference_payload(repo_root: Path, symbol: str, payload: dict[str, Any]) -> str:
    normalized = symbol.strip().upper()
    state_dir = repo_root / "data" / "analysis_state" / normalized
    state_dir.mkdir(parents=True, exist_ok=True)
    local_path = state_dir / "reference.json"
    local_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    destination = reference_uri(normalized)
    subprocess.run(
        [
            require_gcloud(),
            "storage",
            "cp",
            "--content-type=application/json; charset=utf-8",
            str(local_path),
            destination,
        ],
        check=True,
    )
    return destination


def _read_json_gcs(uri: str) -> dict[str, Any] | None:
    raw = read_text_gcs(uri)
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _load_local_reference_payload(symbol: str) -> dict[str, Any] | None:
    local_path = (
        Path.cwd()
        / "data"
        / "analysis_state"
        / symbol.strip().upper()
        / "reference.json"
    )
    try:
        payload = json.loads(local_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def read_text_gcs(uri: str) -> str | None:
    """Read GCS without allowing concurrent gcloud processes to hang forever."""
    try:
        gcloud_path = require_gcloud()
    except RuntimeError as exc:
        raise RuntimeError(f"gcs_read_unavailable: {exc}") from exc

    lock_path = Path.cwd() / GCS_READ_LOCK_PATH
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    last_error = "unknown"
    for attempt in range(1, GCS_READ_ATTEMPTS + 1):
        # Release the cross-process lock between attempts. One stalled object
        # must not monopolize every GCS reader for both timeout windows.
        with _exclusive_read_lock(lock_path):
            try:
                completed = run_bounded(
                    [gcloud_path, "storage", "cat", uri],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=GCS_READ_TIMEOUT_SECONDS,
                    creationflags=_gcloud_creation_flags(),
                )
            except subprocess.TimeoutExpired:
                last_error = (
                    f"timeout after {GCS_READ_TIMEOUT_SECONDS}s "
                    f"(attempt {attempt}/{GCS_READ_ATTEMPTS})"
                )
            else:
                if completed.returncode == 0:
                    return completed.stdout
                detail = (completed.stderr or completed.stdout or "").strip()
                if _is_gcs_not_found(detail):
                    return None
                last_error = (
                    f"exit_code={completed.returncode}: {detail[:500]}"
                )
        if attempt < GCS_READ_ATTEMPTS:
            time.sleep(1)
    raise RuntimeError(f"gcs_read_failed: {uri}: {last_error}")


def _is_gcs_not_found(detail: str) -> bool:
    normalized = detail.casefold()
    return any(
        marker in normalized
        for marker in ("not found", "matched no objects", "status=404", " 404 ")
    )


def _gcloud_creation_flags() -> int:
    """Keep gcloud children out of the worker's shared Windows console."""
    if os.name != "nt":
        return 0
    return subprocess.CREATE_NO_WINDOW


@contextmanager
def _exclusive_read_lock(lock_path: Path) -> Iterator[None]:
    deadline = time.monotonic() + GCS_READ_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"pid": os.getpid()}, handle)
            break
        except (FileExistsError, PermissionError):
            if _remove_stale_lock(lock_path):
                continue
            if time.monotonic() >= deadline:
                raise RuntimeError("gcs_read_lock_timeout")
            time.sleep(0.2)
    try:
        yield
    finally:
        _release_lock(lock_path)


def _release_lock(lock_path: Path) -> None:
    """Best-effort release; Windows readers can briefly deny deletion."""
    for attempt in range(10):
        try:
            lock_path.unlink()
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt < 9:
                time.sleep(0.1)


def _remove_stale_lock(lock_path: Path) -> bool:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        pid = int(payload.get("pid"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        try:
            age = time.time() - lock_path.stat().st_mtime
        except FileNotFoundError:
            return True
        if (
            GCS_READ_LOCK_INITIALIZATION_GRACE_SECONDS > 0
            and age < GCS_READ_LOCK_INITIALIZATION_GRACE_SECONDS
        ):
            return False
        pid = -1
    if pid > 0 and _process_exists(pid):
        return False
    try:
        lock_path.unlink()
        return True
    except OSError:
        return False


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
        try:
            exit_code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True  # Unknown: do not steal a possibly live lock.
            return exit_code.value == 259  # STILL_ACTIVE, not merely an open handle.
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _score_from_payload(payload: dict[str, Any]) -> float | None:
    decision = payload.get("decision")
    if isinstance(decision, dict) and isinstance(decision.get("score"), (int, float)):
        return float(decision["score"])
    validation = payload.get("validation")
    if isinstance(validation, dict) and isinstance(validation.get("score"), (int, float)):
        return float(validation["score"])
    return None
