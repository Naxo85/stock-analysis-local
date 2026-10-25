"""Persistence helpers for authoritative analysis references."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import time
import uuid
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
    from src.local_runner.publication_authority import committed_payload
    committed, manifest = committed_payload(normalized, 'anchor')
    if manifest:
        return committed
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
    staged_path = state_dir / "reference.pending.json"
    staged_path.write_text(
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
            str(staged_path),
            destination,
        ],
        check=True,
    )
    os.replace(staged_path, local_path)
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
    token = uuid.uuid4().hex
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"pid": os.getpid(), "token": token,
                           "owner_started_ns": _process_observation(os.getpid())[1]}, handle)
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
        _release_lock(lock_path, expected_token=token)


def _release_lock(lock_path: Path, *, expected_token: str | None = None) -> None:
    """Best-effort release; never remove another GCS acquisition's token.

    The optional argument preserves the legacy session-pool caller contract.
    """
    for attempt in range(10):
        try:
            if expected_token is None:
                lock_path.unlink()
                return
            snapshot = _lock_snapshot(lock_path)
            payload = json.loads(snapshot[0])
            if not isinstance(payload, dict) or payload.get("token") != expected_token:
                return
            if _unlink_unchanged_lock(lock_path, snapshot):
                return
        except FileNotFoundError:
            return
        except (ValueError, TypeError):
            return
        except OSError:
            pass
        if attempt < 9:
            time.sleep(0.1)


def _lock_snapshot(lock_path: Path) -> tuple[bytes, tuple[int, ...]]:
    """Bind parsed contents to the same open file and its observed identity."""
    with lock_path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        raw = handle.read()
        after = os.fstat(handle.fileno())
    identity = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    if identity(before) != identity(after):
        raise OSError("lock_changed_during_read")
    return raw, identity(after)


def _unlink_unchanged_lock(lock_path: Path, snapshot: tuple[bytes, tuple[int, ...]]) -> bool:
    # Reject a replacement observed before unlink. Like the previous file-based
    # mutex, this is not an atomic compare-and-delete primitive.
    try:
        if _lock_snapshot(lock_path) != snapshot:
            return False
        lock_path.unlink()
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def _remove_stale_lock(lock_path: Path) -> bool:
    try:
        snapshot = _lock_snapshot(lock_path)
    except FileNotFoundError:
        return True
    except OSError:
        return False  # Unreadable is unknown, not proof of an abandoned owner.
    try:
        payload = json.loads(snapshot[0])
        pid = payload.get("pid") if isinstance(payload, dict) else None
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            raise ValueError("invalid_lock_pid")
    except (ValueError, TypeError):
        age = time.time() - snapshot[1][3] / 1_000_000_000
        if age < GCS_READ_LOCK_INITIALIZATION_GRACE_SECONDS:
            return False
    else:
        alive, started_ns = _process_observation(pid)
        if alive is None:
            return False
        if alive:
            if started_ns is None:
                return False
            owner_started_ns = payload.get("owner_started_ns")
            if owner_started_ns is not None:
                if (not isinstance(owner_started_ns, int) or isinstance(owner_started_ns, bool)
                        or owner_started_ns <= 0 or started_ns <= owner_started_ns):
                    return False
            elif started_ns <= snapshot[1][3]:
                # Legacy {pid}: a process born after this file's last write
                # cannot own it, even when Windows has reused the numeric PID.
                return False
    return _unlink_unchanged_lock(lock_path, snapshot)


def _process_observation(pid: int) -> tuple[bool | None, int | None]:
    """Return alive/dead/unknown and the process instance's UTC birth time."""
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            # ERROR_INVALID_PARAMETER denotes a nonexistent PID. Permission or
            # any other failure does not prove death; never steal that lock.
            return (False, None) if kernel32.GetLastError() == 87 else (None, None)
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return None, None
            if exit_code.value != 259:  # STILL_ACTIVE
                return False, None
            creation, exit_time, kernel, user = (wintypes.FILETIME() for _ in range(4))
            if not kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                           ctypes.byref(kernel), ctypes.byref(user)):
                return True, None
            ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            return True, (ticks - 116444736000000000) * 100
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False, None
    except (PermissionError, OSError):
        return None, None
    return True, None


def _process_exists(pid: int) -> bool:
    # Existing callers need a bool: unknown is conservatively still alive.
    return _process_observation(pid)[0] is not False


def _score_from_payload(payload: dict[str, Any]) -> float | None:
    decision = payload.get("decision")
    if isinstance(decision, dict) and isinstance(decision.get("score"), (int, float)):
        return float(decision["score"])
    validation = payload.get("validation")
    if isinstance(validation, dict) and isinstance(validation.get("score"), (int, float)):
        return float(validation["score"])
    return None
