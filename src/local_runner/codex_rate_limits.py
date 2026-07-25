"""Read ChatGPT Codex quota windows through the local Codex app-server."""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from src.local_runner.codex_generator import require_codex


APP_SERVER_TIMEOUT_SECONDS = 30


def read_codex_rate_limits(*, cwd: Path) -> dict[str, Any]:
    """Return the current five-hour and weekly quota snapshot.

    The stable ``account/rateLimits/read`` app-server method reports the same
    quota windows shown by Codex. Reading it does not start a model turn.
    """

    codex_path = require_codex()
    try:
        process = subprocess.Popen(
            [codex_path, "app-server", "--stdio"],
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        raise RuntimeError(f"codex_rate_limits_start_failed: {exc}") from exc

    if process.stdin is None or process.stdout is None:
        process.kill()
        raise RuntimeError("codex_rate_limits_missing_stdio")

    output_queue: queue.Queue[str | None] = queue.Queue()

    def collect_stdout() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            output_queue.put(line)
        output_queue.put(None)

    reader = threading.Thread(target=collect_stdout, daemon=True)
    reader.start()
    output_lines: list[str] = []

    try:
        _send_message(
            process,
            {
                "method": "initialize",
                "id": 1,
                "params": {
                    "clientInfo": {
                        "name": "stock_analysis_model_benchmark",
                        "title": "Stock Analysis Model Benchmark",
                        "version": "1.0.0",
                    }
                },
            },
        )
        _read_until_response(
            output_queue,
            output_lines,
            response_id=1,
            timeout=APP_SERVER_TIMEOUT_SECONDS,
        )
        _send_message(process, {"method": "initialized", "params": {}})
        _send_message(process, {"method": "account/rateLimits/read", "id": 2})
        _read_until_response(
            output_queue,
            output_lines,
            response_id=2,
            timeout=APP_SERVER_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        detail = _stop_app_server(process)
        suffix = f": {detail[:1000]}" if detail else ""
        raise RuntimeError(f"codex_rate_limits_read_failed{suffix}") from exc
    else:
        _stop_app_server(process)

    snapshot = parse_rate_limits_response("".join(output_lines))
    if snapshot is None:
        raise RuntimeError("codex_rate_limits_missing_response")

    return snapshot


def _send_message(process: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    if process.stdin is None:
        raise RuntimeError("codex_app_server_stdin_closed")
    process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    process.stdin.flush()


def _read_until_response(
    output_queue: queue.Queue[str | None],
    output_lines: list[str],
    *,
    response_id: int,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"codex_app_server_response_timeout: id={response_id}")
        try:
            line = output_queue.get(timeout=remaining)
        except queue.Empty as exc:
            raise TimeoutError(
                f"codex_app_server_response_timeout: id={response_id}"
            ) from exc
        if line is None:
            raise RuntimeError(
                f"codex_app_server_closed_before_response: id={response_id}"
            )
        output_lines.append(line)
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("id") != response_id:
            continue
        if "error" in message:
            raise RuntimeError(
                f"codex_app_server_error: id={response_id}: {message['error']}"
            )
        return


def _stop_app_server(process: subprocess.Popen[str]) -> str:
    try:
        if process.stdin is not None:
            process.stdin.close()
    except OSError:
        pass
    try:
        process.terminate()
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()
        process.wait(timeout=5)
    if process.stderr is None:
        return ""
    try:
        return process.stderr.read().strip()
    except OSError:
        return ""


def parse_rate_limits_response(raw_output: str) -> dict[str, Any] | None:
    """Extract and normalize the response to request id 2."""

    for raw_line in str(raw_output or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue

        if message.get("id") != 2:
            continue

        result = message.get("result")
        if not isinstance(result, dict):
            return None

        raw_limits = result.get("rateLimits") or result.get("rate_limits")
        if not isinstance(raw_limits, dict):
            return None

        raw_by_limit_id = (
            result.get("rateLimitsByLimitId")
            or result.get("rate_limits_by_limit_id")
            or {}
        )
        by_limit_id = {
            str(limit_id): _normalize_rate_limits(limit_value)
            for limit_id, limit_value in raw_by_limit_id.items()
            if isinstance(limit_value, dict)
        }

        normalized = _normalize_rate_limits(raw_limits)
        normalized["by_limit_id"] = by_limit_id
        return normalized

    return None


def _normalize_rate_limits(raw_limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary": _normalize_window(
            raw_limits.get("primary") or raw_limits.get("primary_window")
        ),
        "secondary": _normalize_window(
            raw_limits.get("secondary") or raw_limits.get("secondary_window")
        ),
        "plan_type": raw_limits.get("planType") or raw_limits.get("plan_type"),
        "limit_id": raw_limits.get("limitId") or raw_limits.get("limit_id"),
        "rate_limit_reached_type": (
            raw_limits.get("rateLimitReachedType")
            or raw_limits.get("rate_limit_reached_type")
        ),
    }


def calculate_rate_limit_delta(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Calculate used-percentage changes without crossing reset boundaries."""

    return {
        "primary": _window_delta(before.get("primary"), after.get("primary")),
        "secondary": _window_delta(
            before.get("secondary"), after.get("secondary")
        ),
    }


def _normalize_window(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    window_minutes = value.get(
        "windowDurationMins",
        value.get("window_minutes"),
    )
    if window_minutes is None:
        window_seconds = _number(value.get("limit_window_seconds"))
        if window_seconds is not None:
            window_minutes = window_seconds / 60

    return {
        "used_percent": _number(
            value.get("usedPercent", value.get("used_percent"))
        ),
        "window_minutes": _number(window_minutes),
        "resets_at": _number(value.get("resetsAt", value.get("resets_at"))),
    }


def _window_delta(before: Any, after: Any) -> dict[str, Any] | None:
    if not isinstance(before, dict) or not isinstance(after, dict):
        return None

    before_reset = before.get("resets_at")
    after_reset = after.get("resets_at")
    before_used = before.get("used_percent")
    after_used = after.get("used_percent")
    counter_decreased = (
        isinstance(before_used, (int, float))
        and isinstance(after_used, (int, float))
        and after_used < before_used
    )
    reset_changed = (
        counter_decreased
        and isinstance(before_reset, (int, float))
        and isinstance(after_reset, (int, float))
        and after_reset > before_reset + 60
    )
    delta = None

    if not reset_changed and not counter_decreased and isinstance(
        before_used, (int, float)
    ) and isinstance(after_used, (int, float)):
        delta = round(float(after_used) - float(before_used), 6)

    return {
        "used_percent_before": before_used,
        "used_percent_after": after_used,
        "used_percent_delta": delta,
        "reset_boundary_crossed": reset_changed,
        "counter_decreased_or_reconciled": counter_decreased and not reset_changed,
        "resets_at_before": before.get("resets_at"),
        "resets_at_after": after.get("resets_at"),
    }


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value
