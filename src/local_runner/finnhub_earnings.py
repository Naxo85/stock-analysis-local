"""Fetch past and future earnings dates from Finnhub."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from src.local_runner.local_env import get_local_env_value


FINNHUB_EARNINGS_URL = "https://finnhub.io/api/v1/calendar/earnings"
DEFAULT_DAYS_BACK = 1460
DEFAULT_DAYS_FORWARD = 270
REQUEST_TIMEOUT_SECONDS = 30


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    symbol = normalize_finnhub_symbol(args.ticker)
    today = datetime.now(timezone.utc).date()
    start = _resolve_date(args.start, default=today - timedelta(days=args.days_back))
    end = _resolve_date(args.end, default=today + timedelta(days=args.days_forward))
    api_key = (
        args.api_key
        or get_local_env_value("FINN_KEY", repo_root=repo_root)
        or get_local_env_value("FINNHUB_API_KEY", repo_root=repo_root)
        or os.environ.get("FINN_KEY")
        or os.environ.get("FINNHUB_API_KEY")
    )

    if not api_key:
        raise RuntimeError("missing_finnhub_api_key: set FINN_KEY or FINNHUB_API_KEY")

    payload = build_earnings_payload(
        symbol=symbol,
        events=fetch_earnings_calendar(
            symbol=symbol,
            start=start,
            end=end,
            api_key=api_key,
        ),
        start=start,
        end=end,
        today=today,
        generated_at=datetime.now(timezone.utc),
    )

    output_path = _output_path(
        repo_root=repo_root,
        symbol=symbol,
        timestamp=_timestamp_for_file(datetime.now(timezone.utc)),
        out_dir=args.out_dir,
    )
    _write_json(output_path, payload)

    print(f"Finnhub earnings OK for {symbol}.")
    print(f"Window: {start.isoformat()} -> {end.isoformat()}")
    print(f"Events: {payload['event_count']}")
    print(f"Previous earnings: {payload['previous_earnings_date'] or 'none'}")
    print(f"Next earnings: {payload['next_earnings_date'] or 'none'}")
    print(
        "Past earnings dates: "
        + (", ".join(payload["past_earnings_dates"]) or "none")
    )
    print(
        "Future earnings dates: "
        + (", ".join(payload["future_earnings_dates"]) or "none")
    )
    print(f"Output: {output_path}")

    return 0


def fetch_earnings_calendar(
    *,
    symbol: str,
    start: date,
    end: date,
    api_key: str,
) -> list[dict[str, Any]]:
    params = urlencode(
        {
            "symbol": symbol,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "token": api_key,
        }
    )
    url = f"{FINNHUB_EARNINGS_URL}?{params}"

    with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        raw = response.read().decode("utf-8")

    payload = json.loads(raw)
    return extract_earnings_events(payload)


def build_earnings_payload(
    *,
    symbol: str,
    events: list[dict[str, Any]],
    start: date,
    end: date,
    today: date,
    generated_at: datetime,
) -> dict[str, Any]:
    dated_events = sorted(
        (
            {
                **event,
                "normalized_date": normalized,
            }
            for event in events
            if (normalized := normalize_earnings_date(event))
        ),
        key=lambda item: item["normalized_date"],
    )
    dates = [event["normalized_date"] for event in dated_events]
    today = current_date_string(today)
    past_dates = [value for value in dates if value < today]
    future_dates = [value for value in dates if value >= today]

    return {
        "source": "FINNHUB_EARNINGS_CALENDAR",
        "ticker": symbol,
        "generated_at": generated_at.isoformat(),
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "event_count": len(dated_events),
        "past_earnings_dates": past_dates,
        "future_earnings_dates": future_dates,
        "previous_earnings_date": past_dates[-1] if past_dates else None,
        "next_earnings_date": future_dates[0] if future_dates else None,
        "events": dated_events,
    }


def extract_earnings_events(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        raw_events = payload
    elif isinstance(payload, dict):
        raw_events = payload.get("earningsCalendar") or payload.get("data") or []
    else:
        raw_events = []

    return [event for event in raw_events if isinstance(event, dict)]


def normalize_earnings_date(event: dict[str, Any]) -> str | None:
    for key in ("date", "reportDate", "reportedDate", "actualReleaseDate"):
        value = event.get(key)
        normalized = _normalize_ymd(value)
        if normalized:
            return normalized
    return None


def latest_on_or_before(dates: list[str], current_date: date) -> str | None:
    today = current_date.isoformat()
    candidates = [value for value in dates if value <= today]
    return candidates[-1] if candidates else None


def first_on_or_after(dates: list[str], current_date: date) -> str | None:
    today = current_date.isoformat()
    candidates = [value for value in dates if value >= today]
    return candidates[0] if candidates else None


def current_date_string(current_date: date) -> str:
    return current_date.isoformat()


def normalize_finnhub_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch all available Finnhub earnings dates in a window and split "
            "them into past and future dates."
        )
    )
    parser.add_argument("ticker", help="Ticker symbol, for example RKLB")
    parser.add_argument("--api-key", help="Finnhub API key. Defaults to FINN_KEY env.")
    parser.add_argument("--days-back", type=int, default=DEFAULT_DAYS_BACK)
    parser.add_argument("--days-forward", type=int, default=DEFAULT_DAYS_FORWARD)
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Optional output directory. Defaults to data/earnings/{TICKER}.",
    )
    args = parser.parse_args(argv)

    if args.days_back < 0:
        parser.error("--days-back must be >= 0")
    if args.days_forward < 0:
        parser.error("--days-forward must be >= 0")

    return args


def _resolve_date(value: str | None, *, default: date) -> date:
    if not value:
        return default

    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise RuntimeError("date arguments must use YYYY-MM-DD") from exc


def _normalize_ymd(value: Any) -> str | None:
    text = str(value or "")[:10]

    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _output_path(
    *,
    repo_root: Path,
    symbol: str,
    timestamp: str,
    out_dir: Path | None,
) -> Path:
    base_dir = out_dir or repo_root / "data" / "earnings" / symbol
    return base_dir / f"{timestamp}.finnhub.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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
