"""Fetch corporate event / earnings data from IBKR WSH via TWS API."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7497
DEFAULT_CLIENT_ID = 72
DEFAULT_DAYS_BACK = 180
DEFAULT_DAYS_FORWARD = 120
DEFAULT_TOTAL_LIMIT = 100


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    symbol = args.ticker.strip().upper()
    now = datetime.now(timezone.utc)
    start_date = _resolve_date(args.start, default=now.date() - timedelta(days=args.days_back))
    end_date = _resolve_date(args.end, default=now.date() + timedelta(days=args.days_forward))

    payload = fetch_ibkr_wsh_events(
        symbol=symbol,
        host=args.host,
        port=args.port,
        client_id=args.client_id,
        start_date=start_date,
        end_date=end_date,
        total_limit=args.total_limit,
        readonly=not args.read_write,
        timeout=args.timeout,
        include_metadata=args.include_metadata,
        generated_at=now,
    )

    output_path = _output_path(
        repo_root=repo_root,
        symbol=symbol,
        timestamp=_timestamp_for_file(now),
        out_dir=args.out_dir,
    )
    _write_json(output_path, payload)

    print(f"IBKR WSH earnings probe OK for {symbol}.")
    print(f"Status: {payload['status']}")
    print(f"Window: {payload['window']['start']} -> {payload['window']['end']}")
    print(f"Raw events: {payload['raw_event_count']}")
    print(f"Earnings-like events: {payload['earnings_event_count']}")
    print(f"Output: {output_path}")

    for event in payload["earnings_events"][: args.print_examples]:
        print(f"- {_event_display_date(event)} | {_event_display_name(event)}")

    return 0


def fetch_ibkr_wsh_events(
    *,
    symbol: str,
    host: str,
    port: int,
    client_id: int,
    start_date: date,
    end_date: date,
    total_limit: int,
    readonly: bool,
    timeout: float,
    include_metadata: bool,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Connect to TWS and return WSH events for one ticker."""

    try:
        from ib_insync import IB, Stock, WshEventData
    except ImportError as exc:
        raise RuntimeError(
            "ib_insync_not_installed: install ib_insync in this Python environment"
        ) from exc

    generated_at = generated_at or datetime.now(timezone.utc)
    ib = IB()

    try:
        ib.connect(
            host,
            port,
            clientId=client_id,
            readonly=readonly,
            timeout=timeout,
        )
        contract = Stock(symbol, "SMART", "USD")
        qualified = ib.qualifyContracts(contract)

        if not qualified:
            raise RuntimeError(f"ibkr_contract_not_found: {symbol}")

        contract = qualified[0]
        metadata = _load_wsh_metadata(ib) if include_metadata else None
        raw_json = ib.getWshEventData(
            WshEventData(
                conId=contract.conId,
                startDate=_wsh_date(start_date),
                endDate=_wsh_date(end_date),
                totalLimit=total_limit,
            )
        )
    finally:
        if ib.isConnected():
            ib.disconnect()

    raw_events = _parse_wsh_events(raw_json)
    earnings_events = [event for event in raw_events if is_earnings_like_event(event)]
    status = "ok" if raw_events else "unavailable"
    warning = None if raw_events else "wsh_returned_no_events_or_permission_error"

    return {
        "source": "IBKR_TWS_API_WSH",
        "kind": "earnings_events_probe",
        "status": status,
        "warning": warning,
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
        "window": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "raw_event_count": len(raw_events),
        "earnings_event_count": len(earnings_events),
        "earnings_events": earnings_events,
        "raw_events": raw_events,
        "metadata": metadata,
    }


def is_earnings_like_event(event: Any) -> bool:
    """Return True when a WSH event appears to be earnings-related."""

    text = json.dumps(event, ensure_ascii=False).lower()
    needles = (
        "earnings",
        "eps",
        "results",
        "quarter",
        "q1",
        "q2",
        "q3",
        "q4",
        "fiscal",
    )
    return any(needle in text for needle in needles)


def _load_wsh_metadata(ib: Any) -> Any:
    try:
        raw = ib.getWshMetaData()
    except Exception as exc:  # pragma: no cover - depends on IBKR permissions.
        return {"status": "failed", "error": str(exc)}

    return _loads_json_or_raw(raw)


def _parse_wsh_events(raw_json: str) -> list[Any]:
    if not str(raw_json or "").strip():
        return []

    payload = _loads_json_or_raw(raw_json)

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("events", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return [payload]

    return []


def _loads_json_or_raw(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def _event_display_date(event: Any) -> str:
    if not isinstance(event, dict):
        return "unknown"

    for key in ("date", "eventDate", "startDate", "startDateTime", "time", "timestamp"):
        value = event.get(key)
        if value:
            return str(value)

    return "unknown"


def _event_display_name(event: Any) -> str:
    if not isinstance(event, dict):
        return str(event)[:160]

    for key in ("eventName", "eventType", "type", "title", "name", "description"):
        value = event.get(key)
        if value:
            return str(value)[:160]

    return json.dumps(event, ensure_ascii=False)[:160]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch raw IBKR Wall Street Horizon events for one ticker."
    )
    parser.add_argument("ticker", help="Ticker symbol, for example RKLB")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--client-id", type=int, default=DEFAULT_CLIENT_ID)
    parser.add_argument("--days-back", type=int, default=DEFAULT_DAYS_BACK)
    parser.add_argument("--days-forward", type=int, default=DEFAULT_DAYS_FORWARD)
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--total-limit", type=int, default=DEFAULT_TOTAL_LIMIT)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--include-metadata", action="store_true")
    parser.add_argument(
        "--read-write",
        action="store_true",
        help="Connect without TWS readonly mode. Not needed for event probing.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Optional output directory. Defaults to data/ibkr_events/{TICKER}.",
    )
    parser.add_argument("--print-examples", type=int, default=10)

    args = parser.parse_args(argv)

    if args.days_back < 0:
        parser.error("--days-back must be >= 0")
    if args.days_forward < 0:
        parser.error("--days-forward must be >= 0")
    if args.total_limit < 1:
        parser.error("--total-limit must be >= 1")
    if args.print_examples < 0:
        parser.error("--print-examples must be >= 0")

    return args


def _resolve_date(value: str | None, *, default: date) -> date:
    if not value:
        return default

    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise RuntimeError("date arguments must use YYYY-MM-DD") from exc


def _wsh_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def _output_path(
    *,
    repo_root: Path,
    symbol: str,
    timestamp: str,
    out_dir: Path | None,
) -> Path:
    base_dir = out_dir or repo_root / "data" / "ibkr_events" / symbol
    return base_dir / f"{timestamp}.WSH.json"


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
