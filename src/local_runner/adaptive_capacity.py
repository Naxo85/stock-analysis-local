"""Cross-process admission/backoff for confirmed Codex capacity failures.

This is transport pacing, not a spending/report quota. It never calls a model,
retries an execution, cancels an active request or changes frozen model policy.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
import os
from pathlib import Path
import random
import time
import uuid

from src.local_runner.analysis_state import _exclusive_read_lock, _process_exists

BASE_DELAY_SECONDS = 10
MAX_BACKOFF_SECONDS = 120
RECOVERY_INTERVAL_SECONDS = 30
RECOVERY_SUCCESSES = 3
POLL_SECONDS = 0.2


class CapacityWaitTimeout(RuntimeError):
    """Admission ended before any CLI/model execution started."""


def terminal_failure(exit_code: int | None, events: str, response: str) -> dict | None:
    """Only a failed, terminated execution with no completed report is retryable.

Do not interpret stderr substrings, HTTP statuses alone, missing receipts or
timeouts as confirmation. Malformed evidence and successful turns quarantine.
"""
    if exit_code in (None, 0) or response.strip():
        return None
    terminal = None
    for line in events.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            return None
        if not isinstance(event, dict):
            return None
        if event.get("type") == "turn.completed":
            return None
        if event.get("type") == "turn.failed":
            error = event.get("error")
            if not isinstance(error, dict):
                return None
            terminal = error
    return terminal


def retry_after_seconds(error: dict, *, now: float | None = None) -> float | None:
    """Honor an explicit server minimum, including numeric or HTTP-date hints."""
    values = [error.get("retry_after_seconds"), error.get("retry_after")]
    headers = error.get("headers")
    if isinstance(headers, dict):
        values.extend(value for key, value in headers.items() if str(key).casefold() == "retry-after")
    delays = []
    for value in values:
        if isinstance(value, bool) or value is None:
            continue
        try:
            delay = float(value)
        except (ValueError, TypeError):
            try:
                date = parsedate_to_datetime(str(value))
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                delay = date.timestamp() - (time.time() if now is None else now)
            except (ValueError, TypeError, OverflowError):
                continue
        if math.isfinite(delay) and delay >= 0:
            delays.append(delay)
    return max(delays) if delays else None


def capacity_failure(exit_code: int | None, events: str, response: str) -> dict | None:
    error = terminal_failure(exit_code, events, response)
    if error is None:
        return None
    message = str(error.get("message") or "").casefold()
    code = str(error.get("code") or "").casefold()
    # Quota/auth/model/context faults require different action, not traffic pacing.
    if any(marker in code + " " + message for marker in (
            "usage limit", "quota", "billing", "credit_balance", "unauthorized",
            "authentication", "context_length", "model_not_found", "spend_limit")):
        return None
    if code not in {"server_is_overloaded", "server_overloaded", "slow_down", "model_at_capacity"} and not any(
            marker in message for marker in ("selected model is at capacity", "model is temporarily overloaded")):
        return None
    return {"code": code or "model_at_capacity", "retry_after_seconds": retry_after_seconds(error)}


class CapacityLease:
    def __init__(self, folder: Path, token: str, admission: dict):
        self.folder, self.token, self.admission = folder, token, admission
        self.outcome = None
        self.warning = None

    def feedback(self, *, failure: dict | None, success: bool) -> None:
        """A late success from the pre-failure wave cannot raise the new limit."""
        if self.outcome is not None:
            raise RuntimeError("capacity_feedback_already_recorded")
        self.outcome = "capacity_failure" if failure else "success" if success else "unconfirmed_failure"
        try:
            with _exclusive_read_lock(self.folder / "state.lock"):
                state = _load(self.folder, self.admission["ceiling"])
                ticket = state["active"].get(self.token)
                if ticket is None:
                    raise RuntimeError("capacity_lease_missing")
                now = time.time()
                if failure:
                    hint = failure.get("retry_after_seconds")
                    current_wave = ticket["epoch"] == state["epoch"]
                    if current_wave:
                        state["epoch"] += 1
                        state["capacity_streak"] += 1
                        previous = state["limit"]
                        state["limit"] = max(1, previous // 2)
                        state["successes"] = 0
                        state["recovery_after"] = now + RECOVERY_INTERVAL_SECONDS
                        delay = min(MAX_BACKOFF_SECONDS, BASE_DELAY_SECONDS * (2 ** min(state["capacity_streak"] - 1, 20)))
                        delay = max(delay, hint or 0) + random.uniform(0, 2)
                        state["cooldown_until"] = max(state["cooldown_until"], now + delay)
                        _event(self.folder, "capacity_reduced", state, previous_limit=previous,
                               delay_seconds=delay, code=failure["code"])
                    elif hint is not None:
                        # Same-wave errors do not halve again, but server minimums apply.
                        state["cooldown_until"] = max(state["cooldown_until"], now + hint)
                    _event(self.folder, "capacity_failure", state, same_wave=not current_wave,
                           code=failure["code"])
                elif success and ticket["epoch"] == state["epoch"] and now >= state["cooldown_until"]:
                    state["successes"] += 1
                    if (state["limit"] < state["ceiling"]
                            and state["successes"] >= RECOVERY_SUCCESSES
                            and now >= state["recovery_after"]):
                        previous = state["limit"]
                        state["limit"] += 1
                        state["successes"] = 0
                        state["capacity_streak"] = 0
                        state["recovery_after"] = now + RECOVERY_INTERVAL_SECONDS
                        _event(self.folder, "capacity_recovered", state, previous_limit=previous)
                    elif state["limit"] == state["ceiling"]:
                        state["successes"] = 0
                        state["capacity_streak"] = 0
                elif not success:
                    state["successes"] = 0
                _save(self.folder, state)
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
            # Completed evidence remains usable; never repeat it for telemetry.
            self.warning = str(exc)

    def receipt(self) -> dict:
        return {**self.admission, "outcome": self.outcome, "warning": self.warning,
                "state_path": str(self.folder / "state.json")}


def _event(folder: Path, event: str, state: dict, **details) -> None:
    with (folder / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "event": event,
                                "limit": state["limit"], "epoch": state["epoch"], **details}) + "\n")


def _save(folder: Path, state: dict) -> None:
    path = folder / "state.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    # Windows readers (including progress diagnostics/AV) can briefly deny
    # DELETE sharing despite our writer lock. Retry ONLY atomic replacement,
    # still holding that lock; never truncate the old state or repeat a model.
    deadline = time.monotonic() + 2.0
    while True:
        try:
            temporary.replace(path)
            break
        except PermissionError as exc:
            if os.name != 'nt' or getattr(exc, 'winerror', None) not in (5, 32, 33) or time.monotonic() >= deadline:
                raise
            time.sleep(.05)


def _load(folder: Path, ceiling: int) -> dict:
    path = folder / "state.json"
    if not path.exists():
        return {"version": 1, "ceiling": ceiling, "limit": ceiling, "epoch": 0,
                "capacity_streak": 0, "successes": 0, "cooldown_until": 0,
                "recovery_after": 0, "active": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        def require(condition):
            if not condition:
                raise ValueError("invalid capacity state")
        require(state["version"] == 1)
        for key in ("ceiling", "limit", "epoch", "capacity_streak", "successes"):
            require(type(state[key]) is int and state[key] >= 0)
        require(1 <= state["limit"] <= state["ceiling"] <= 8)
        for key in ("cooldown_until", "recovery_after"):
            require(not isinstance(state[key], bool) and math.isfinite(state[key]) and state[key] >= 0)
        require(isinstance(state["active"], dict))
        for ticket in state["active"].values():
            require(isinstance(ticket, dict) and type(ticket["pid"]) is int and ticket["pid"] > 0)
            require(type(ticket["epoch"]) is int and 0 <= ticket["epoch"] <= state["epoch"])
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        raise RuntimeError("capacity_state_invalid_no_model_call") from exc
    # A policy reduction applies immediately; raising the ceiling never resets backoff.
    state["ceiling"] = ceiling
    state["limit"] = min(state["limit"], ceiling)
    return state


@contextmanager
def capacity_lease(workspace: Path, *, parallel: int, wait_seconds: float):
    """Shared by Luna/Sol contracts and subprocesses, not just Python threads."""
    if type(parallel) is not int or not 1 <= parallel <= 8:
        raise ValueError("invalid_capacity_parallelism")
    folder = workspace / "capacity"
    folder.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    deadline = started + wait_seconds
    token = uuid.uuid4().hex
    waiting_logged = False
    while True:
        with _exclusive_read_lock(folder / "state.lock"):
            state = _load(folder, parallel)
            state["active"] = {key: value for key, value in state["active"].items()
                               if _process_exists(value["pid"])}
            now = time.time()
            if now >= state["cooldown_until"] and len(state["active"]) < state["limit"]:
                state["active"][token] = {"pid": os.getpid(), "epoch": state["epoch"]}
                _save(folder, state)
                admission = {"limit_at_admission": state["limit"], "ceiling": parallel,
                             "epoch": state["epoch"], "waited_seconds": round(time.monotonic() - started, 3)}
                break
            if not waiting_logged:
                _event(folder, "capacity_wait", state, active=len(state["active"]),
                       cooldown_remaining_seconds=max(0, state["cooldown_until"] - now))
                waiting_logged = True
            _save(folder, state)
        if time.monotonic() >= deadline:
            raise CapacityWaitTimeout("capacity_wait_timeout_no_model_call")
        time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
    lease = CapacityLease(folder, token, admission)
    try:
        yield lease
    finally:
        # No normal/success feedback is inferred from a crash, timeout or exception.
        try:
            with _exclusive_read_lock(folder / "state.lock"):
                state = _load(folder, parallel)
                state["active"].pop(token, None)
                _save(folder, state)
        except (OSError, RuntimeError) as exc:
            # Preserve a completed report. Broken state blocks the NEXT admission.
            lease.warning = lease.warning or str(exc)
