"""Process-safe, contract-isolated Codex sessions without ticker history growth.

Only our dedicated automation sessions are reset. Rollouts and per-call artifacts
remain available for audit. No paid compaction or extra model warm-up is used.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import uuid

from src.local_runner.analysis_state import _remove_stale_lock, _release_lock
from src.local_runner.codex_rate_limits import _send_message, _read_until_response, _stop_app_server


def reset_session(thread_id: str, *, workspace: Path, cli: str, env: dict,
                  config_args: list[str]) -> None:
    """Drop completed ticker turns, preserving session ID and stable policy.

    The installed protocol supports thread/revert; older rollback is removed.
    Unsupported/ambiguous resets retire the slot, never trigger another model call.
    """
    uuid.UUID(thread_id)
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errors:
        process = subprocess.Popen([cli, "app-server", "--stdio", *config_args], cwd=str(workspace),
            env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
            text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        messages = queue.Queue()
        def collect():
            for line in process.stdout:
                messages.put(line)
            messages.put(None)
        threading.Thread(target=collect, daemon=True).start()
        lines = []
        def request(id, method, params):
            _send_message(process, {"id": id, "method": method, "params": params})
            _read_until_response(messages, lines, response_id=id, timeout=30)
            response = next(json.loads(line) for line in reversed(lines) if json.loads(line).get("id") == id)
            if "error" in response:
                raise RuntimeError("session_reset_rpc_failed: " + str(response["error"]))
            return response["result"]
        try:
            request(1, "initialize", {"clientInfo": {"name": "stock_analysis_session_reset", "version": "1.0"},
                                      "capabilities": {"experimentalApi": True}})
            _send_message(process, {"method": "initialized", "params": {}})
            resumed = request(2, "thread/resume", {"threadId": thread_id, "excludeTurns": True})["thread"]
            if resumed.get("status", {}).get("type") == "active":
                raise RuntimeError("session_still_active_no_reuse")
            # Hydrated thread.turns can be empty for paginated history. Query
            # durable turns explicitly; never interpret an omitted view as clean.
            page = request(3, "thread/turns/list", {"threadId": thread_id, "limit": 1, "sortDirection": "asc"})
            turns = page.get("data")
            if not isinstance(turns, list):
                raise RuntimeError("session_history_unknown_no_reuse")
            if turns:
                cleared = request(4, "thread/revert", {"threadId": thread_id, "beforeTurnId": turns[0]["id"]})["thread"]
                if cleared.get("turns") != []:
                    raise RuntimeError("session_history_not_cleared_no_reuse")
                page = request(5, "thread/turns/list", {"threadId": thread_id, "limit": 1})
                if page.get("data") != []:
                    raise RuntimeError("session_durable_history_not_cleared_no_reuse")
        finally:
            _stop_app_server(process)


def contract_key(*, workspace: Path, cli: str, kind: str, model: str, effort: str,
                 instructions: str, schema: dict | None, research: bool, config_args: list[str]) -> str:
    value = {"version": 1, "cwd": str(workspace.resolve()), "cli": cli, "kind": kind,
             "model": model, "effort": effort, "instructions": instructions,
             "schema": schema, "research": research, "config": config_args}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class SessionLease:
    def __init__(self, path: Path, key: str):
        self.path, self.key = path, key
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            id = state.get("thread_id")
            self.thread_id = str(uuid.UUID(id)) if state.get("clean") and state.get("contract") == key else None
        except (OSError, ValueError, TypeError, AttributeError):
            self.thread_id = None
        self.reused = self.thread_id is not None
        self.reset_ok = False
        self.warning = None
        # Retire before starting a call. A crash must never reintroduce history.
        self.save(False)

    def save(self, clean: bool):
        state = {"contract": self.key, "thread_id": self.thread_id, "clean": clean,
                 "pid": os.getpid(), "warning": self.warning}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        tmp.replace(self.path)

    def completed(self, events: str, *, workspace: Path, cli: str, env: dict, config_args: list[str]):
        ids = []
        for line in events.splitlines():
            try:
                event = json.loads(line)
                if event.get("type") == "thread.started":
                    ids.append(str(uuid.UUID(event["thread_id"])))
            except (ValueError, KeyError, TypeError):
                continue
        if len(ids) != 1 or (self.reused and ids[0] != self.thread_id):
            self.warning = "session_id_unconfirmed_no_reuse"
            self.save(False)
            return
        self.thread_id = ids[0]
        try:
            reset_session(self.thread_id, workspace=workspace, cli=cli, env=env, config_args=config_args)
            self.reset_ok = True
        except Exception as exc:
            # A valid completed response remains valid; only the cache slot is
            # retired. No duplicate generation, fallback or batch-wide circuit.
            self.warning = str(exc)
        self.save(self.reset_ok)

    def receipt(self):
        return {"session_id": self.thread_id, "session_reused": self.reused,
                "session_history_cleared": self.reset_ok, "session_warning": self.warning}


@contextmanager
def session_lease(workspace: Path, key: str, *, parallel: int, wait_seconds: int):
    if not 1 <= parallel <= 8:
        raise ValueError("invalid_session_parallelism")
    folder = workspace / "sessions" / key
    folder.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait_seconds
    while True:
        for slot in range(parallel):
            path = folder / f"slot-{slot}.json"
            lock = path.with_suffix(".lock")
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump({"pid": os.getpid()}, handle)
            except (FileExistsError, PermissionError):
                _remove_stale_lock(lock)
                continue
            try:
                yield SessionLease(path, key)
            finally:
                _release_lock(lock)
            return
        if time.monotonic() >= deadline:
            raise RuntimeError("session_pool_wait_timeout_no_model_call")
        time.sleep(.2)
