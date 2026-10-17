"""Process-safe admission ledger; confirmed failed calls can be retried."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from src.local_runner.analysis_state import _exclusive_read_lock
from src.local_runner.codex_rate_limits import parse_rate_limits_response
from src.local_runner.adaptive_preflight import rpc


RETIRED_LIMITS = frozenset({"max_used_percent", "max_calls_per_batch",
                          "max_reports_per_batch", "max_itv_per_batch",
                          "max_output_tokens_per_batch", "max_uncached_input_tokens_per_batch",
                          "max_input_chars"})


def _effective_policy(policy: dict) -> dict:
    # Frozen old checkpoints may record these removed limits. They have no
    # effect and must not prevent reuse of completed calls after this change.
    return {key: value for key, value in policy.items() if key not in RETIRED_LIMITS}


def read_codex_rate_limits(*, cwd: Path) -> dict:
    result = rpc("account/rateLimits/read", {}, cwd)
    return parse_rate_limits_response(json.dumps({"id": 2, "result": result})) or {}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def check_quota(snapshot: dict) -> None:
    # Inspect all advertised buckets conservatively; never substitute credits
    # for exhausted included quota. Unknown quota is not unlimited quota.
    windows = [snapshot.get("primary"), snapshot.get("secondary")]
    for bucket in snapshot.get("by_limit_id", {}).values():
        windows.extend([bucket.get("primary"), bucket.get("secondary")])
    known = [w for w in windows if isinstance(w, dict) and isinstance(w.get("used_percent"), (int, float))]
    if not known or snapshot.get("rate_limit_reached_type"):
        raise RuntimeError("quota_unavailable_or_exhausted")
    if any(w["used_percent"] >= 100 for w in known):
        raise RuntimeError("quota_unavailable_or_exhausted")


def reserve(path: Path, *, ticker: str, kind: str, itv: bool, policy: dict, root: Path,
            retry_failed: bool = False) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_read_lock(path.with_suffix(".lock")):
        ledger = read_json(path) or {"calls": {}, "policy": policy}
        if _effective_policy(ledger["policy"]) != _effective_policy(policy):
            raise RuntimeError("budget_policy_changed_start_new_batch")
        key = f"{ticker}:{kind}"
        previous = ledger["calls"].get(key)
        if previous and not (retry_failed and previous.get("status") == "failed"):
            raise RuntimeError(f"call_already_reserved_no_duplicate: {key}")
        snapshot = read_codex_rate_limits(cwd=root)
        check_quota(snapshot)
        ledger["last_quota"] = snapshot
        if previous:
            ledger.setdefault("failed_call_history", {}).setdefault(key, []).append(previous)
        ledger["calls"][key] = {"ticker": ticker, "kind": kind, "itv": itv,
                                "status": "reserved", "at": datetime.now(timezone.utc).isoformat()}
        write_json(path, ledger)
        return key


def finish(path: Path, key: str, *, receipt: dict | None = None, error: str | None = None) -> None:
    with _exclusive_read_lock(path.with_suffix(".lock")):
        ledger = read_json(path)
        ledger["calls"][key].update({"status": "failed" if error else "completed",
                                     "finished_at": datetime.now(timezone.utc).isoformat(),
                                     "retryable_failure": bool((receipt or {}).get("retryable_failure")),
                                     "no_model_started": (receipt or {}).get("no_model_started") is True,
                                     "capacity_control": (receipt or {}).get("capacity_control"),
                                     "usage": (receipt or {}).get("usage"),
                                     "model": (receipt or {}).get("model"), "error": error})
        # The failed reservation remains visible and cannot be repeated blindly.
        # It does not block other tickers; each admission checks real quota.
        write_json(path, ledger)
