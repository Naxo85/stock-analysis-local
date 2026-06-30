"""Update current analyst ratings for one ticker from IBKR news."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.local_runner.analyst_ratings import (
    apply_probe_payload,
    build_empty_ratings_state,
)
from src.local_runner.finnhub_earnings import (
    DEFAULT_DAYS_FORWARD as FINNHUB_DAYS_FORWARD,
    build_earnings_payload,
    fetch_earnings_calendar,
)
from src.local_runner.ibkr_analyst_probe import fetch_ibkr_analyst_headlines
from src.local_runner.local_env import get_local_env_value


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7497
DEFAULT_CLIENT_ID = 81
DEFAULT_SEED_DAYS = 365
DEFAULT_SEED_TOTAL = 300
DEFAULT_UPDATE_TOTAL = 300
DEFAULT_INCREMENTAL_OVERLAP_HOURS = 24


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    symbol = args.ticker.strip().upper()
    now = datetime.now(timezone.utc)
    output_path = _current_path(repo_root, symbol)
    earnings_context = _load_earnings_context(
        symbol=symbol,
        repo_root=repo_root,
        now=now,
        api_key=args.finnhub_api_key,
    )
    state = _load_state(output_path)

    if state is None:
        state = build_empty_ratings_state(
            symbol=symbol,
            now=now,
            previous_earnings_date=earnings_context.get("previous_earnings_date"),
            next_earnings_date=earnings_context.get("next_earnings_date"),
        )
        if not args.no_seed:
            seed_payload = _fetch_provider(
                symbol=symbol,
                provider="BRFUPDN",
                start=now - timedelta(days=args.seed_days),
                total_results=args.seed_total,
                host=args.host,
                port=args.port,
                client_id=args.client_id,
                timeout=args.timeout,
                generated_at=now,
                window_basis="seed_brfupdn",
                earnings_context=earnings_context,
            )
            _write_raw_probe(repo_root, symbol, seed_payload, now)
            state = apply_probe_payload(state, seed_payload, now=now)
    else:
        state.setdefault("earnings", {})
        _merge_earnings_context(state, earnings_context)

    update_start = _update_start(
        now=now,
        state=state,
        earnings_context=earnings_context,
        fallback_days=args.update_days,
        overlap_hours=args.incremental_overlap_hours,
    )
    update_payload = _fetch_provider(
        symbol=symbol,
        provider=args.update_provider,
        start=update_start,
        total_results=args.update_total,
        host=args.host,
        port=args.port,
        client_id=args.client_id + 1,
        timeout=args.timeout,
        generated_at=now,
        window_basis=_update_window_basis(
            state=state,
            earnings_context=earnings_context,
        ),
        earnings_context=earnings_context,
    )
    _write_raw_probe(repo_root, symbol, update_payload, now)
    state = apply_probe_payload(state, update_payload, now=now)
    state["as_of"] = now.isoformat()
    state["last_update"] = {
        "provider": args.update_provider,
        "window_start": update_start.isoformat(),
        "window_basis": _update_window_basis(
            state=state,
            earnings_context=earnings_context,
        ),
        "completed_at": now.isoformat(),
        "headline_count": update_payload.get("headline_count"),
    }

    _write_json(output_path, state)

    summary = state["summary_active"]
    print(f"Analyst ratings updated for {symbol}.")
    print(f"Output: {output_path}")
    print(f"Basis: {summary['basis']} | quality={summary['quality']}")
    print(
        "Ratings: "
        f"{summary['rating_counts'].get('buy', 0)}B "
        f"{summary['rating_counts'].get('hold', 0)}H "
        f"{summary['rating_counts'].get('sell', 0)}S"
    )
    print(
        "Targets: "
        f"median={summary['target_median']} "
        f"low={summary['target_low']} "
        f"high={summary['target_high']} "
        f"count={summary['target_count']}"
    )

    return 0


def _fetch_provider(
    *,
    symbol: str,
    provider: str,
    start: datetime,
    total_results: int,
    host: str,
    port: int,
    client_id: int,
    timeout: float,
    generated_at: datetime,
    window_basis: str,
    earnings_context: dict[str, Any],
) -> dict[str, Any]:
    return fetch_ibkr_analyst_headlines(
        symbol=symbol,
        host=host,
        port=port,
        client_id=client_id,
        provider=provider,
        start=start,
        total_results=total_results,
        readonly=True,
        timeout=timeout,
        generated_at=generated_at,
        window_basis=window_basis,
        earnings_context=earnings_context,
    )


def _load_earnings_context(
    *,
    symbol: str,
    repo_root: Path,
    now: datetime,
    api_key: str | None,
) -> dict[str, Any]:
    key = (
        api_key
        or get_local_env_value("FINN_KEY", repo_root=repo_root)
        or get_local_env_value("FINNHUB_API_KEY", repo_root=repo_root)
    )

    if not key:
        return {"status": "missing_finnhub_api_key"}

    today = now.date()
    start = today - timedelta(days=1460)
    end = today + timedelta(days=FINNHUB_DAYS_FORWARD)

    try:
        payload = build_earnings_payload(
            symbol=symbol,
            events=fetch_earnings_calendar(
                symbol=symbol,
                start=start,
                end=end,
                api_key=key,
            ),
            start=start,
            end=end,
            today=today,
            generated_at=now,
        )
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}

    return {
        "status": "ok",
        "source": payload["source"],
        "previous_earnings_date": payload["previous_earnings_date"],
        "next_earnings_date": payload["next_earnings_date"],
        "event_count": payload["event_count"],
    }


def _update_start(
    *,
    now: datetime,
    state: dict[str, Any],
    earnings_context: dict[str, Any],
    fallback_days: int,
    overlap_hours: int,
) -> datetime:
    last_ingested = _last_ingested_at(state)

    if last_ingested is not None:
        return max(
            last_ingested - timedelta(hours=overlap_hours),
            now - timedelta(days=fallback_days),
        )

    previous = earnings_context.get("previous_earnings_date")

    if previous:
        value = date.fromisoformat(str(previous))
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)

    return now - timedelta(days=fallback_days)


def _merge_earnings_context(
    state: dict[str, Any],
    earnings_context: dict[str, Any],
) -> None:
    earnings = state.setdefault("earnings", {})

    for key in ("previous_earnings_date", "next_earnings_date"):
        value = earnings_context.get(key)
        if value:
            earnings[key] = value


def _update_window_basis(
    *,
    state: dict[str, Any],
    earnings_context: dict[str, Any],
) -> str:
    if _last_ingested_at(state) is not None:
        return "incremental_last_ingested"
    if earnings_context.get("previous_earnings_date"):
        return "finnhub_previous_earnings"
    return "update_days_fallback"


def _last_ingested_at(state: dict[str, Any]) -> datetime | None:
    for value in (
        state.get("as_of"),
        (state.get("last_update") or {}).get("completed_at"),
    ):
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed

    return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _load_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def _write_raw_probe(
    repo_root: Path,
    symbol: str,
    payload: dict[str, Any],
    now: datetime,
) -> None:
    provider = str(payload.get("providerCode") or "UNKNOWN")
    path = (
        repo_root
        / "data"
        / "ibkr_news_raw"
        / symbol
        / f"{_timestamp_for_file(now)}.{provider}.json"
    )
    _write_json(path, payload)


def _current_path(repo_root: Path, symbol: str) -> Path:
    return repo_root / "data" / "analyst_ratings" / symbol / "current.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update current analyst ratings for one ticker from IBKR news."
    )
    parser.add_argument("ticker", help="Ticker symbol, for example RKLB")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--client-id", type=int, default=DEFAULT_CLIENT_ID)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--finnhub-api-key")
    parser.add_argument("--no-seed", action="store_true")
    parser.add_argument("--seed-days", type=int, default=DEFAULT_SEED_DAYS)
    parser.add_argument("--seed-total", type=int, default=DEFAULT_SEED_TOTAL)
    parser.add_argument("--update-provider", default="DJ-N")
    parser.add_argument("--update-days", type=int, default=30)
    parser.add_argument("--update-total", type=int, default=DEFAULT_UPDATE_TOTAL)
    parser.add_argument(
        "--incremental-overlap-hours",
        type=int,
        default=DEFAULT_INCREMENTAL_OVERLAP_HOURS,
        help=(
            "When current.json already exists, fetch new headlines from the "
            "last analyst ingestion minus this overlap. Default: 24."
        ),
    )

    args = parser.parse_args(argv)

    if args.seed_days < 1:
        parser.error("--seed-days must be >= 1")
    if args.seed_total < 1:
        parser.error("--seed-total must be >= 1")
    if args.update_days < 1:
        parser.error("--update-days must be >= 1")
    if args.update_total < 1:
        parser.error("--update-total must be >= 1")
    if args.incremental_overlap_hours < 0:
        parser.error("--incremental-overlap-hours must be >= 0")

    return args


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()

    for candidate in (current, *current.parents):
        if (candidate / "AGENTS.md").exists() and (candidate / "src").exists():
            return candidate

    return current


def _timestamp_for_file(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


if __name__ == "__main__":
    sys.exit(main())
