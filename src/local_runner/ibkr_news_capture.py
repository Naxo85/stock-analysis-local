"""Execution-scoped reuse of an immutable, verified IBKR cached-news capture.

The backward adapter exhausts the provider's *available cache*, not all history.
A view may widen its lower date only because raw rows and the exact EOF proof
are retained. The acquisition cutoff and observation date never move forward.
SHA-256 binds local artifacts; it is not a provider signature or a freshness
claim beyond the caller's existing snapshot-age policy.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Callable

from src.local_runner.analysis_state import _exclusive_read_lock


SCHEMA_VERSION = 1
METHOD = "historicalNewsEnd_backward_cache_v1"
COVERAGE_SCOPE = "available_provider_cache_before_rounded_end_cursor"


class CaptureError(RuntimeError):
    """A capture cannot safely serve this preparation."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CaptureError(f"ibkr_news_capture_{reason}")


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CaptureError("ibkr_news_capture_invalid_json") from exc


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _dt(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
        _require(isinstance(parsed, datetime) and parsed.utcoffset() is not None, "invalid_timestamp")
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CaptureError("ibkr_news_capture_invalid_timestamp") from exc


def _check_clock(now: datetime, generated_at: object, max_age_seconds: float) -> None:
    _require(type(max_age_seconds) in (int, float) and math.isfinite(max_age_seconds)
             and max_age_seconds > 0, "invalid_max_age")
    age = (_dt(now) - _dt(generated_at)).total_seconds()
    _require(age >= 0, "future_capture")
    _require(age <= max_age_seconds, "stale")


def _identity(symbol: str, provider: str, contract: dict, connection: dict) -> dict:
    _require(isinstance(symbol, str) and bool(symbol.strip()), "invalid_identity")
    _require(isinstance(provider, str) and bool(provider.strip()), "invalid_identity")
    _require(isinstance(contract, dict) and set(contract) == {
        "conId", "symbol", "exchange", "currency", "secType"}, "invalid_contract")
    _require(type(contract["conId"]) is int and contract["conId"] > 0 and all(
        isinstance(contract[k], str) and contract[k] for k in contract if k != "conId"), "invalid_contract")
    _require(isinstance(connection, dict) and set(connection) == {"host", "port"}
             and isinstance(connection["host"], str) and bool(connection["host"])
             and type(connection["port"]) is int and 0 < connection["port"] < 65536,
             "invalid_connection")
    return deepcopy({"symbol": symbol.strip().upper(), "provider": provider,
                     "contract": contract, "connection": connection})


def _filtered(raw: list[dict], start: datetime, end: datetime) -> tuple[list[dict], int, int]:
    times = [_dt(row.get("published_at_raw")) for row in raw]
    return ([row for row, stamp in zip(raw, times) if start <= stamp <= end],
            sum(stamp < start for stamp in times), sum(stamp > end for stamp in times))


def _validate_payload(payload: dict, identity: dict) -> None:
    _require(isinstance(payload, dict) and payload.get("source") == "IBKR_TWS_API", "invalid_source")
    _require(payload.get("ticker") == identity["symbol"]
             and payload.get("providerCode") == identity["provider"]
             and payload.get("contract") == identity["contract"]
             and payload.get("connection") == identity["connection"], "identity_mismatch")
    _require(not any(payload.get(key) for key in ("error", "errors", "truncated")), "source_error")
    cutoff = _dt(payload.get("generated_at"))
    window = payload.get("window", {})
    _require(isinstance(window, dict), "invalid_window")
    start = _dt(window.get("start"))
    _require(start <= cutoff and _dt(window.get("end")) == cutoff, "invalid_window")
    if "provider_fetched_at" in payload:
        _require(_dt(payload["provider_fetched_at"]) == cutoff, "timestamp_mismatch")
    coverage = payload.get("coverage", {})
    _require(isinstance(coverage, dict) and coverage.get("status") == "complete"
             and coverage.get("terminal_received") is True and coverage.get("has_more") is False
             and coverage.get("pagination_complete") is True
             and coverage.get("method") == METHOD and coverage.get("scope") == COVERAGE_SCOPE
             and coverage.get("lower_bound_applied") == "local_filter_after_cache_exhaustion"
             and coverage.get("upper_bound_applied") == "local_filter_exact_end_after_second_overlap"
             and coverage.get("timestamp_basis") == "provider_naive_interpreted_as_utc_existing_contract"
             and not any(coverage.get(key) for key in ("error", "errors", "truncated")), "coverage_not_verified")
    requested = coverage.get("requested_window", {})
    _require(isinstance(requested, dict) and _dt(requested.get("start")) == start
             and _dt(requested.get("end")) == cutoff, "coverage_window_mismatch")
    raw = payload.get("raw_headlines")
    _require(isinstance(raw, list) and payload.get("raw_headline_count") == len(raw)
             and coverage.get("returned_count") == len(raw), "raw_count_mismatch")
    initial = cutoff.replace(microsecond=0) + timedelta(seconds=1)
    _require(_dt(coverage.get("initial_cursor_exclusive")) == initial, "invalid_initial_cursor")
    keys = []
    for row in raw:
        _require(isinstance(row, dict) and row.get("source") == "IBKR_TWS_API"
                 and row.get("ticker") == identity["symbol"]
                 and row.get("providerCode") == identity["provider"]
                 and row.get("conId") == identity["contract"]["conId"]
                 and isinstance(row.get("articleId"), str) and bool(row["articleId"].strip())
                 and isinstance(row.get("headline_raw"), str), "invalid_raw_identity")
        stamp = _dt(row.get("published_at_raw"))
        _require(stamp < initial, "raw_after_cursor")
        keys.append((stamp, row["providerCode"], row["articleId"]))
    _require(len({key[1:] for key in keys}) == len(keys), "duplicate_raw_identity")
    _require(keys == sorted(keys, reverse=True), "raw_not_descending")
    selected, before, after = _filtered(raw, start, cutoff)
    _require(payload.get("headlines") == selected and payload.get("headline_count") == len(selected)
             and payload.get("filtered_before_start_count") == before
             and payload.get("filtered_after_end_count") == after
             and payload.get("unparseable_timestamp_count") == 0, "original_view_mismatch")
    _validate_pages(coverage, initial, len(raw))


def _validate_pages(coverage: dict, initial: datetime, raw_count: int) -> None:
    pages, limit, maximum = coverage.get("pages"), coverage.get("requested_limit"), coverage.get("max_pages")
    _require(isinstance(pages, list) and bool(pages) and coverage.get("page_count") == len(pages)
             and type(limit) is int and 1 <= limit <= 300 and type(maximum) is int
             and 1 <= len(pages) <= maximum, "invalid_pages")
    expected_cursor, received, duplicates = initial, 0, 0
    for number, page in enumerate(pages, 1):
        _require(isinstance(page, dict) and page.get("page") == number
                 and page.get("terminal_received") is True
                 and page.get("has_more") is (number < len(pages)), "invalid_page_terminal")
        cursor = _dt(page.get("cursor_exclusive"))
        _require(cursor == expected_cursor and page.get("wire_end") == ""
                 and page.get("wire_start") == cursor.strftime("%Y-%m-%d %H:%M:%S.0"), "invalid_page_cursor")
        count, duplicate = page.get("returned_count"), page.get("duplicate_count")
        _require(type(count) is int and 0 <= count <= limit and type(duplicate) is int
                 and 0 <= duplicate <= count, "invalid_page_counts")
        if count:
            earliest, latest = _dt(page.get("earliest")), _dt(page.get("latest"))
            _require(earliest <= latest < cursor, "invalid_page_times")
            expected_cursor = earliest.replace(microsecond=0) + timedelta(seconds=1)
            _require(number == len(pages) or expected_cursor < cursor, "page_no_progress")
        else:
            _require(number == len(pages) and page.get("earliest") is None
                     and page.get("latest") is None, "invalid_empty_page")
        received += count
        duplicates += duplicate
    _require(received - duplicates == raw_count and coverage.get("duplicate_count") == duplicates,
             "page_raw_count_mismatch")


def _validate_capture(capture: dict, *, now: datetime, max_age_seconds: float,
                      identity: dict | None = None, scope_sha256: str | None = None) -> None:
    _require(isinstance(capture, dict) and capture.get("schema_version") == SCHEMA_VERSION, "invalid_schema")
    body = {key: value for key, value in capture.items() if key != "capture_sha256"}
    _require(capture.get("capture_sha256") == _hash(body), "digest_mismatch")
    actual = capture.get("identity", {})
    _require(isinstance(actual, dict) and actual == _identity(
        actual.get("symbol"), actual.get("provider"), actual.get("contract"), actual.get("connection")), "invalid_identity")
    _require(capture.get("identity_sha256") == _hash(actual)
             and capture.get("payload_sha256") == _hash(capture.get("payload")), "digest_mismatch")
    if identity is not None:
        _require(actual == identity, "identity_mismatch")
    if scope_sha256 is not None:
        _require(capture.get("scope_sha256") == scope_sha256, "scope_mismatch")
    _validate_payload(capture.get("payload"), actual)
    _check_clock(now, capture["payload"]["generated_at"], max_age_seconds)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CaptureError("ibkr_news_capture_unreadable") from exc


def _write_immutable(path: Path, payload: dict) -> None:
    """Publish fully flushed bytes atomically, never replace an existing object."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _canonical(payload) + b"\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".capture-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            _require(path.read_bytes() == data, "immutable_conflict")
    finally:
        Path(temporary).unlink(missing_ok=True)


def get_or_create_capture(scope_dir: Path, *, symbol: str, provider: str, contract: dict,
                          connection: dict, fetch: Callable[[], dict], now: datetime,
                          max_age_seconds: float) -> dict:
    """Acquire once per exact execution/provider/contract identity, or fail closed.

    Stale/corrupt existing captures cannot be refreshed under the same identity.
    A failed acquisition writes no usable index, so an explicit existing retry
    can try again. Scope creation is local; ``fetch`` is the caller's adapter.
    """
    _check_clock(now, now, max_age_seconds)
    scope_dir = Path(scope_dir).resolve()
    scope_hash = _hash(os.path.normcase(str(scope_dir)))
    identity = _identity(symbol, provider, contract, connection)
    identity_hash = _hash(identity)
    index_path = scope_dir / "keys" / f"{identity_hash}.json"
    lock_path = scope_dir / "locks" / f"{identity_hash}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_read_lock(lock_path):
        if index_path.exists():
            index = _read_json(index_path)
            _require(isinstance(index, dict) and index.get("schema_version") == SCHEMA_VERSION
                     and index.get("scope_sha256") == scope_hash
                     and index.get("identity_sha256") == identity_hash, "index_mismatch")
            capture_hash = index.get("capture_sha256")
            _require(isinstance(capture_hash, str) and len(capture_hash) == 64
                     and all(c in "0123456789abcdef" for c in capture_hash), "invalid_object_reference")
            capture = _read_json(scope_dir / "objects" / f"{capture_hash}.json")
            _require(isinstance(capture, dict) and capture.get("capture_sha256") == capture_hash, "digest_mismatch")
        else:
            payload = deepcopy(fetch())
            _validate_payload(payload, identity)
            _check_clock(now, payload["generated_at"], max_age_seconds)
            capture = {"schema_version": SCHEMA_VERSION, "scope_sha256": scope_hash,
                       "identity": identity, "identity_sha256": identity_hash,
                       "payload_sha256": _hash(payload), "payload": payload}
            capture["capture_sha256"] = _hash(capture)
            _write_immutable(scope_dir / "objects" / f"{capture['capture_sha256']}.json", capture)
            _write_immutable(index_path, {key: capture[key] for key in (
                "schema_version", "scope_sha256", "identity_sha256", "capture_sha256")})
        _validate_capture(capture, now=now, max_age_seconds=max_age_seconds,
                          identity=identity, scope_sha256=scope_hash)
        return deepcopy(capture)


def derive_probe_payload(capture: dict, *, start: datetime, window_basis: str,
                         earnings_context: dict | None = None, now: datetime,
                         max_age_seconds: float) -> dict:
    """Make an independent locally filtered view, retaining original EOF evidence."""
    _validate_capture(capture, now=now, max_age_seconds=max_age_seconds)
    payload = deepcopy(capture["payload"])
    start, cutoff = _dt(start), _dt(payload["generated_at"])
    _require(start <= cutoff and isinstance(window_basis, str) and bool(window_basis), "invalid_view_window")
    selected, before, after = _filtered(payload["raw_headlines"], start, cutoff)
    view = {"basis": window_basis, "start": start.isoformat(), "end": payload["window"]["end"]}
    payload.update(window=deepcopy(view), view_window=view, earnings_context=deepcopy(earnings_context),
                   headlines=deepcopy(selected), headline_count=len(selected),
                   filtered_before_start_count=before, filtered_after_end_count=after,
                   unparseable_timestamp_count=0, derived_at=_dt(now).isoformat(),
                   provider_fetched_at=payload["generated_at"])
    payload["capture_ref"] = {key: capture[key] for key in (
        "schema_version", "capture_sha256", "scope_sha256", "identity_sha256")}
    payload["capture_ref"].update(provider_fetched_at=payload["generated_at"],
                                  cutoff_at=payload["window"]["end"], coverage_scope=COVERAGE_SCOPE,
                                  timestamp_basis="original_probe_generated_at")
    return payload
