"""Fetch raw IBKR analyst-action headlines from TWS API."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.local_runner.analyst_actions import parse_analyst_headline
from src.local_runner.finnhub_earnings import (
    DEFAULT_DAYS_FORWARD as FINNHUB_DAYS_FORWARD,
    build_earnings_payload,
    fetch_earnings_calendar,
)
from src.local_runner.local_env import get_local_env_value


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7497
DEFAULT_CLIENT_ID = 71
DEFAULT_PROVIDER = "BRFUPDN"
DEFAULT_DAYS = 14
DEFAULT_TOTAL_RESULTS = 100

_HEADLINE_PREFIX_RE = re.compile(r"^\{.*?\}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    symbol = args.ticker.strip().upper()
    now = datetime.now(timezone.utc)
    start_context = _resolve_start_context(
        symbol=symbol,
        repo_root=repo_root,
        explicit_start=args.start,
        days=args.days,
        now=now,
        earnings_window=not args.no_earnings_window,
        finnhub_api_key=args.finnhub_api_key,
    )
    start = start_context["start"]
    timestamp = _timestamp_for_file(now)

    try:
        payload = fetch_ibkr_analyst_headlines(
            symbol=symbol,
            host=args.host,
            port=args.port,
            client_id=args.client_id,
            provider=args.provider,
            start=start,
            total_results=args.total_results,
            readonly=not args.read_write,
            timeout=args.timeout,
            generated_at=now,
            window_basis=start_context["basis"],
            earnings_context=start_context.get("earnings_context"),
        )
    except RuntimeError as exc:
        print(f"FAILED {symbol}: {exc}")
        return 1

    output_path = _output_path(
        repo_root=repo_root,
        symbol=symbol,
        timestamp=timestamp,
        provider=args.provider,
        out_dir=args.out_dir,
    )
    _write_json(output_path, payload)

    print(f"IBKR analyst probe OK for {symbol}.")
    print(f"Provider: {payload['providerCode']}")
    print(f"Window basis: {payload['window']['basis']}")
    print(f"Window start: {payload['window']['start']}")
    print(f"Headlines: {payload['headline_count']}")
    print(f"Output: {output_path}")

    for item in payload["headlines"][: args.print_examples]:
        print(f"- {item['published_at_raw']} | {item['headline_clean']}")

    return 0


def fetch_ibkr_analyst_headlines(
    *,
    symbol: str,
    host: str,
    port: int,
    client_id: int,
    provider: str,
    start: datetime,
    total_results: int,
    readonly: bool,
    timeout: float,
    generated_at: datetime | None = None,
    window_basis: str = "manual_days",
    earnings_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Connect to TWS and return raw historical analyst-action headlines."""

    try:
        from ib_insync import IB, Stock
    except ImportError as exc:
        raise RuntimeError(
            "ib_insync_not_installed: install ib_insync in this Python environment"
        ) from exc

    generated_at = generated_at or datetime.now(timezone.utc)
    ib = IB()

    try:
        try:
            ib.connect(
                host,
                port,
                clientId=client_id,
                readonly=readonly,
                timeout=timeout,
            )
        except OSError as exc:
            raise RuntimeError(
                f"ibkr_connection_failed: {host}:{port} - {exc}"
            ) from exc
        providers = ib.reqNewsProviders()
        contract = Stock(symbol, "SMART", "USD")
        qualified = ib.qualifyContracts(contract)

        if not qualified:
            raise RuntimeError(f"ibkr_contract_not_found: {symbol}")

        contract = qualified[0]
        raw_items = ib.reqHistoricalNews(
            contract.conId,
            provider,
            _ibkr_datetime(start),
            _ibkr_datetime(generated_at),
            total_results,
        ) or []

        return build_probe_payload(
            symbol=symbol,
            contract=contract,
            provider=provider,
            providers=providers,
            headlines=raw_items,
            start=start,
            generated_at=generated_at,
            host=host,
            port=port,
            window_basis=window_basis,
            earnings_context=earnings_context,
        )
    finally:
        if ib.isConnected():
            ib.disconnect()


def build_probe_payload(
    *,
    symbol: str,
    contract: Any,
    provider: str,
    providers: list[Any],
    headlines: list[Any],
    start: datetime,
    generated_at: datetime,
    host: str,
    port: int,
    window_basis: str = "manual_days",
    earnings_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    serialized_headlines = [
        serialize_news_headline(symbol=symbol, con_id=contract.conId, item=item)
        for item in _filter_headlines_by_window(
            headlines,
            start=start,
            end=generated_at,
        )
    ]

    return {
        "source": "IBKR_TWS_API",
        "kind": "analyst_actions_probe",
        "ticker": symbol,
        "generated_at": generated_at.isoformat(),
        "connection": {
            "host": host,
            "port": port,
        },
        "contract": {
            "conId": contract.conId,
            "symbol": getattr(contract, "symbol", symbol),
            "exchange": getattr(contract, "exchange", None),
            "currency": getattr(contract, "currency", None),
            "secType": getattr(contract, "secType", None),
        },
        "providerCode": provider,
        "available_providers": [
            {
                "code": getattr(item, "code", None),
                "name": getattr(item, "name", None),
            }
            for item in providers
        ],
        "window": {
            "basis": window_basis,
            "start": start.isoformat(),
            "end": generated_at.isoformat(),
        },
        "earnings_context": earnings_context,
        "raw_headline_count": len(headlines),
        "headline_count": len(serialized_headlines),
        "filtered_before_start_count": len(headlines) - len(serialized_headlines),
        "headlines": serialized_headlines,
    }


def serialize_news_headline(*, symbol: str, con_id: int, item: Any) -> dict[str, Any]:
    headline_raw = str(getattr(item, "headline", "") or "")
    headline_clean = clean_ibkr_headline(headline_raw)

    return {
        "source": "IBKR_TWS_API",
        "ticker": symbol,
        "conId": con_id,
        "providerCode": getattr(item, "providerCode", None),
        "articleId": getattr(item, "articleId", None),
        "published_at_raw": _stringify_time(getattr(item, "time", None)),
        "headline_raw": headline_raw,
        "headline_clean": headline_clean,
        "analyst_action": parse_analyst_headline(headline_clean),
        "article": {
            "fetched": False,
            "articleType": None,
            "articleText": None,
        },
        "triage": {
            "status": "not_applicable_analyst_action",
        },
    }


def clean_ibkr_headline(headline: str) -> str:
    cleaned = _HEADLINE_PREFIX_RE.sub("", str(headline or "")).strip()
    return cleaned.lstrip("!").strip()


def _filter_headlines_by_window(
    headlines: list[Any],
    *,
    start: datetime,
    end: datetime,
) -> list[Any]:
    filtered = []

    for item in headlines:
        published_at = _time_as_datetime(getattr(item, "time", None))

        if published_at is None:
            filtered.append(item)
            continue

        if start <= published_at <= end:
            filtered.append(item)

    return filtered


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch raw IBKR BRFUPDN analyst-action headlines for one ticker."
    )
    parser.add_argument("ticker", help="Ticker symbol, for example RKLB")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument(
        "--start",
        help="Optional explicit UTC start datetime, ISO format or YYYYMMDD HH:MM:SS.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--client-id", type=int, default=DEFAULT_CLIENT_ID)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument("--total-results", type=int, default=DEFAULT_TOTAL_RESULTS)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--no-earnings-window",
        action="store_true",
        help="Do not use Finnhub previous earnings as the default start date.",
    )
    parser.add_argument(
        "--finnhub-api-key",
        help="Finnhub API key. Defaults to FINN_KEY/FINNHUB_API_KEY or .env.local.",
    )
    parser.add_argument(
        "--read-write",
        action="store_true",
        help="Connect without TWS readonly mode. Not needed for news probing.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Optional output directory. Defaults to data/ibkr_news_raw/{TICKER}.",
    )
    parser.add_argument("--print-examples", type=int, default=5)

    args = parser.parse_args(argv)

    if args.days < 1:
        parser.error("--days must be >= 1")
    if args.total_results < 1:
        parser.error("--total-results must be >= 1")
    if args.print_examples < 0:
        parser.error("--print-examples must be >= 0")

    return args


def _resolve_start_context(
    *,
    symbol: str,
    repo_root: Path,
    explicit_start: str | None,
    days: int,
    now: datetime,
    earnings_window: bool,
    finnhub_api_key: str | None,
) -> dict[str, Any]:
    if explicit_start:
        parsed = _parse_start(explicit_start)
        if parsed is None:
            raise RuntimeError(
                "--start must be ISO format or IBKR format YYYYMMDD HH:MM:SS"
            )
        return {"start": parsed, "basis": "manual_start"}

    if earnings_window:
        context = _load_previous_earnings_context(
            symbol=symbol,
            repo_root=repo_root,
            now=now,
            api_key=finnhub_api_key,
        )
        previous = context.get("previous_earnings_date")

        if previous:
            return {
                "start": _start_of_utc_date(date.fromisoformat(str(previous))),
                "basis": "finnhub_previous_earnings",
                "earnings_context": context,
            }

        return {
            "start": now - timedelta(days=days),
            "basis": "days_fallback_no_previous_earnings",
            "earnings_context": context,
        }

    return {
        "start": now - timedelta(days=days),
        "basis": "manual_days",
    }


def _load_previous_earnings_context(
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


def _start_of_utc_date(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _resolve_start(
    start: str | None,
    *,
    days: int,
    now: datetime,
) -> datetime:
    if start:
        parsed = _parse_start(start)
        if parsed is None:
            raise RuntimeError(
                "--start must be ISO format or IBKR format YYYYMMDD HH:MM:SS"
            )
        return parsed

    return now - timedelta(days=days)


def _parse_start(value: str) -> datetime | None:
    text = value.strip()

    if not text:
        return None

    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y%m%d %H:%M:%S")
        except ValueError:
            return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _ibkr_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%d %H:%M:%S")


def _stringify_time(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()

    return str(value)


def _time_as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    text = str(value).strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _output_path(
    *,
    repo_root: Path,
    symbol: str,
    timestamp: str,
    provider: str,
    out_dir: Path | None,
) -> Path:
    base_dir = out_dir or repo_root / "data" / "ibkr_news_raw" / symbol
    return base_dir / f"{timestamp}.{provider}.json"


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
