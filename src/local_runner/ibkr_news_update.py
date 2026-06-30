"""Fetch recent general IBKR news headlines for one ticker."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.local_runner.finnhub_earnings import (
    DEFAULT_DAYS_FORWARD as FINNHUB_DAYS_FORWARD,
    build_earnings_payload,
    fetch_earnings_calendar,
)
from src.local_runner.ibkr_analyst_probe import fetch_ibkr_analyst_headlines
from src.local_runner.ibkr_news_articles import fetch_ibkr_news_articles
from src.local_runner.ibkr_news_events import (
    resolve_unresolved_with_article_bodies,
    write_recent_news_events,
)
from src.local_runner.local_env import get_local_env_value
from src.local_runner.previous_analysis import load_previous_analysis_context


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7497
DEFAULT_CLIENT_ID = 7001
DEFAULT_PROVIDER = "DJ-N"
DEFAULT_FALLBACK_DAYS = 90
DEFAULT_OVERLAP_HOURS = 24
DEFAULT_TOTAL = 300


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    symbol = args.ticker.strip().upper()
    now = datetime.now(timezone.utc)
    start, basis = _window_start(
        symbol=symbol,
        repo_root=repo_root,
        now=now,
        since=args.since,
        finnhub_api_key=args.finnhub_api_key,
        fallback_days=args.fallback_days,
        overlap_hours=args.overlap_hours,
    )

    payload = fetch_ibkr_analyst_headlines(
        symbol=symbol,
        provider=args.provider,
        start=start,
        total_results=args.total,
        host=args.host,
        port=args.port,
        client_id=args.client_id,
        timeout=args.timeout,
        generated_at=now,
        window_basis=basis,
        readonly=not args.no_readonly,
        earnings_context=None,
    )

    raw_path = _raw_path(repo_root, symbol, args.provider, now)
    _write_json(raw_path, payload)

    compact = _compact_payload(payload)
    latest_path = repo_root / "data" / "ibkr_news_recent" / symbol / "latest.json"
    _write_json(latest_path, compact)
    events_payload: dict[str, Any] = {"event_count": 0, "unresolved_count": 0}
    if args.aggregate_news:
        events_payload = write_recent_news_events(
            repo_root,
            symbol,
            use_gemini=not args.no_gemini_aggregation,
            gemini_dry_run=args.gemini_dry_run,
            aggregator_provider=args.news_aggregator,
        )
    if (
        args.aggregate_news
        and not args.gemini_dry_run
        and not args.no_gemini_aggregation
        and events_payload.get("unresolved_count", 0) > 0
        and args.max_unresolved_bodies > 0
    ):
        article_payload = fetch_ibkr_news_articles(
            articles=events_payload.get("unresolved_headlines") or [],
            host=args.host,
            port=args.port,
            client_id=args.client_id + 1,
            timeout=args.timeout,
            readonly=not args.no_readonly,
            max_articles=args.max_unresolved_bodies,
            max_chars=args.article_body_chars,
        )
        events_payload = resolve_unresolved_with_article_bodies(
            repo_root=repo_root,
            symbol=symbol,
            payload=events_payload,
            article_payload=article_payload,
            aggregator_provider=args.news_aggregator,
        )

    print(
        f"IBKR news updated for {symbol}: "
        f"headlines={compact['count']} events={events_payload.get('event_count')} "
        f"unresolved={events_payload.get('unresolved_count')} "
        f"basis={basis} start={start.isoformat()}",
        flush=True,
    )
    print(f"Latest: {latest_path}", flush=True)

    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch recent general IBKR news headlines for one ticker."
    )
    parser.add_argument("ticker", help="Ticker symbol, for example HOOD")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--client-id", type=int, default=DEFAULT_CLIENT_ID)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument("--total", type=int, default=DEFAULT_TOTAL)
    parser.add_argument("--fallback-days", type=int, default=DEFAULT_FALLBACK_DAYS)
    parser.add_argument("--overlap-hours", type=int, default=DEFAULT_OVERLAP_HOURS)
    parser.add_argument("--finnhub-api-key")
    parser.add_argument("--since", help="Explicit UTC start datetime.")
    parser.add_argument("--no-readonly", action="store_true")
    parser.add_argument(
        "--no-gemini-aggregation",
        action="store_true",
        help="Do not use Gemini Flash to aggregate unresolved headlines.",
    )
    parser.add_argument(
        "--gemini-dry-run",
        action="store_true",
        help="Estimate aggregator tokens/cost without calling the AI provider.",
    )
    parser.add_argument(
        "--news-aggregator",
        choices=("codex", "gemini"),
        default="codex",
        help="AI provider for unresolved headline aggregation.",
    )
    parser.add_argument(
        "--aggregate-news",
        action="store_true",
        help="Run optional AI aggregation of IBKR headlines. Disabled by default.",
    )
    parser.add_argument("--max-unresolved-bodies", type=int, default=8)
    parser.add_argument("--article-body-chars", type=int, default=2500)

    args = parser.parse_args(argv)

    if args.total < 1:
        parser.error("--total must be >= 1")
    if args.fallback_days < 1:
        parser.error("--fallback-days must be >= 1")
    if args.overlap_hours < 0:
        parser.error("--overlap-hours must be >= 0")
    if args.max_unresolved_bodies < 0:
        parser.error("--max-unresolved-bodies must be >= 0")
    if args.article_body_chars < 200:
        parser.error("--article-body-chars must be >= 200")

    return args


def _window_start(
    *,
    symbol: str,
    repo_root: Path,
    now: datetime,
    since: str | None,
    finnhub_api_key: str | None,
    fallback_days: int,
    overlap_hours: int,
) -> tuple[datetime, str]:
    explicit = _parse_datetime(since)
    if explicit is not None:
        return explicit, "explicit_since"

    previous = load_previous_analysis_context(symbol)
    previous_dt = _parse_datetime(previous.generated_at)

    if previous_dt is not None:
        return previous_dt - timedelta(hours=overlap_hours), "previous_analysis"

    previous_earnings = _previous_earnings_date(
        symbol=symbol,
        repo_root=repo_root,
        now=now,
        api_key=finnhub_api_key,
    )

    if previous_earnings is not None:
        return (
            datetime(
                previous_earnings.year,
                previous_earnings.month,
                previous_earnings.day,
                tzinfo=timezone.utc,
            ),
            "finnhub_previous_earnings_no_previous_analysis",
        )

    return now - timedelta(days=fallback_days), "fallback_days_no_previous_analysis"


def _previous_earnings_date(
    *,
    symbol: str,
    repo_root: Path,
    now: datetime,
    api_key: str | None,
) -> date | None:
    key = (
        api_key
        or get_local_env_value("FINN_KEY", repo_root=repo_root)
        or get_local_env_value("FINNHUB_API_KEY", repo_root=repo_root)
    )
    if not key:
        return None

    today = now.date()
    try:
        payload = build_earnings_payload(
            symbol=symbol,
            events=fetch_earnings_calendar(
                symbol=symbol,
                start=today - timedelta(days=730),
                end=today + timedelta(days=FINNHUB_DAYS_FORWARD),
                api_key=key,
            ),
            start=today - timedelta(days=730),
            end=today + timedelta(days=FINNHUB_DAYS_FORWARD),
            today=today,
            generated_at=now,
        )
    except Exception:
        return None

    previous = payload.get("previous_earnings_date")
    if not previous:
        return None

    try:
        return date.fromisoformat(str(previous)[:10])
    except ValueError:
        return None


def _compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    headlines = payload.get("headlines")
    if not isinstance(headlines, list):
        headlines = []

    items = []
    for item in headlines:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "published_at": item.get("published_at_raw"),
                "providerCode": item.get("providerCode"),
                "articleId": item.get("articleId"),
                "headline": item.get("headline_clean"),
            }
        )

    return {
        "status": "ok",
        "source": payload.get("source") or "IBKR_TWS_API",
        "kind": "recent_ibkr_news",
        "ticker": payload.get("ticker"),
        "generated_at": payload.get("generated_at"),
        "providerCode": payload.get("providerCode"),
        "window": payload.get("window"),
        "count": len(items),
        "items": items,
        "truncated": False,
    }


def _raw_path(repo_root: Path, symbol: str, provider: str, now: datetime) -> Path:
    timestamp = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return (
        repo_root
        / "data"
        / "ibkr_news_raw"
        / symbol
        / f"{timestamp}.{provider}.general.json"
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()

    for candidate in (current, *current.parents):
        if (candidate / "AGENTS.md").exists() and (candidate / "src").exists():
            return candidate

    return current


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI should print concise failures.
        print(f"FAILED ibkr_news_update: {exc}", file=sys.stderr)
        raise SystemExit(1)
