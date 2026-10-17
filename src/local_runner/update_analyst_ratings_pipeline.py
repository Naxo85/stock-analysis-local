"""Stream analyst refresh completion so the batch can prepare tickers early."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from src.local_runner.finnhub_earnings import (
    DEFAULT_DAYS_BACK,
    DEFAULT_DAYS_FORWARD,
    build_earnings_payload,
    fetch_earnings_calendar,
)
from src.local_runner.local_env import get_local_env_value
from src.local_runner.update_analyst_ratings_batch import (
    _cached_earnings_context,
    _clean_tickers,
    _run_backfill,
    _run_one,
)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    tickers = _clean_tickers(args.tickers.split(","))
    if not tickers:
        raise RuntimeError("no_tickers_to_update")

    started_at = datetime.now(timezone.utc)
    log_dir = (
        repo_root
        / "logs"
        / "analyst_updates"
        / started_at.strftime("%Y-%m-%d")
        / started_at.strftime("%H-%M-%S")
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    args.progress_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    earnings_contexts: dict[str, dict[str, Any]] = {}

    for ticker, earnings_context in _iter_earnings_contexts(
        repo_root=repo_root,
        tickers=tickers,
        args=args,
        now=started_at,
    ):
        earnings_contexts[ticker] = earnings_context
        index = tickers.index(ticker)
        result = _run_one(
            repo_root=repo_root,
            ticker=ticker,
            client_id=args.client_id_base + index * 3,
            args=args,
            log_dir=log_dir,
            earnings_context=earnings_context,
        )
        if result.get("status") == "ok" and args.backfill:
            try:
                _run_backfill(
                    repo_root=repo_root,
                    tickers=[ticker],
                    execute_upload_real=args.execute_upload_real,
                )
            except Exception as exc:
                result["backfill_warning"] = str(exc)
        results.append(result)
        _write_progress(args.progress_dir / f"{ticker}.json", result)
        print(
            f"{str(result.get('status') or 'failed').upper()} {ticker}: "
            f"{result.get('summary', result.get('error', ''))}",
            flush=True,
        )
        if args.sleep_seconds > 0 and len(results) < len(tickers):
            time.sleep(args.sleep_seconds)

    results.sort(key=lambda item: tickers.index(str(item["ticker"])))
    contexts = {ticker: earnings_contexts[ticker] for ticker in tickers}
    counts: dict[str, int] = {}
    for context in contexts.values():
        status = str(context.get("source_status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    summary = {
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "ticker_count": len(tickers),
        "ok_count": sum(1 for item in results if item.get("status") == "ok"),
        "failed_count": sum(1 for item in results if item.get("status") != "ok"),
        "earnings_refresh": {
            "status": "ok" if counts.get("unavailable", 0) == 0 else "partial",
            "max_parallel": min(args.finnhub_max_parallel, len(tickers)),
            "retries": args.finnhub_retries,
            "counts": counts,
            "tickers": contexts,
        },
        "results": results,
    }
    _write_progress(log_dir / "summary.json", summary)
    print(f"Summary: {log_dir / 'summary.json'}")
    return 1 if summary["failed_count"] else 0


def _iter_earnings_contexts(
    *,
    repo_root: Path,
    tickers: list[str],
    args: argparse.Namespace,
    now: datetime,
) -> Iterator[tuple[str, dict[str, Any]]]:
    api_key = (
        get_local_env_value("FINN_KEY", repo_root=repo_root)
        or get_local_env_value("FINNHUB_API_KEY", repo_root=repo_root)
    )
    if not api_key:
        for ticker in tickers:
            yield ticker, _cached_earnings_context(
                repo_root=repo_root,
                ticker=ticker,
                now=now,
                error="missing_finnhub_api_key",
                attempts=0,
            )
        return

    workers = min(args.finnhub_max_parallel, len(tickers))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            ticker: executor.submit(
                _fetch_earnings_context,
                repo_root=repo_root,
                ticker=ticker,
                api_key=api_key,
                now=now,
                retries=args.finnhub_retries,
            )
            for ticker in tickers
        }
        for ticker in tickers:
            try:
                context = futures[ticker].result()
            except Exception as exc:
                context = _cached_earnings_context(
                    repo_root=repo_root,
                    ticker=ticker,
                    now=now,
                    error=f"prefetch_runtime_error: {exc}",
                    attempts=args.finnhub_retries + 1,
                )
            yield ticker, context


def _fetch_earnings_context(
    *,
    repo_root: Path,
    ticker: str,
    api_key: str,
    now: datetime,
    retries: int,
) -> dict[str, Any]:
    start = now.date() - timedelta(days=DEFAULT_DAYS_BACK)
    end = now.date() + timedelta(days=DEFAULT_DAYS_FORWARD)
    last_error = "unknown_finnhub_error"
    for attempt in range(1, retries + 2):
        try:
            payload = build_earnings_payload(
                symbol=ticker,
                events=fetch_earnings_calendar(
                    symbol=ticker,
                    start=start,
                    end=end,
                    api_key=api_key,
                ),
                start=start,
                end=end,
                today=now.date(),
                generated_at=now,
            )
            return {
                "status": "ok",
                "source_status": "live",
                "source": payload["source"],
                "previous_earnings_date": payload["previous_earnings_date"],
                "next_earnings_date": payload["next_earnings_date"],
                "event_count": payload["event_count"],
                "data_as_of": now.isoformat(),
                "attempts": attempt,
            }
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt <= retries:
                time.sleep(min(2.0 * attempt, 5.0))
    return _cached_earnings_context(
        repo_root=repo_root,
        ticker=ticker,
        now=now,
        error=last_error,
        attempts=retries + 1,
    )


def _write_progress(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--progress-dir", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id-base", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--seed-days", type=int, default=365)
    parser.add_argument("--seed-total", type=int, default=300)
    parser.add_argument("--update-total", type=int, default=300)
    parser.add_argument("--update-days", type=int, default=30)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--finnhub-max-parallel", type=int, default=4)
    parser.add_argument("--finnhub-retries", type=int, default=1)
    parser.add_argument("--no-seed", action="store_true")
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--execute-upload-real", action="store_true")
    args = parser.parse_args(argv)
    if args.execute_upload_real and not args.backfill:
        parser.error("--execute-upload-real requires --backfill")
    return args


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "src" / "local_runner" / "run_one.py").exists():
            return candidate
    raise RuntimeError("Could not find repo root")


if __name__ == "__main__":
    raise SystemExit(main())
