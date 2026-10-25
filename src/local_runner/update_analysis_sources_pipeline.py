"""Refresh strict news and analyst inputs, releasing one ticker at a time."""

from __future__ import annotations


import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.local_runner.ibkr_news_pagination import DEFAULT_NEWS_PROCESS_TIMEOUT
from src.local_runner.adaptive_policy import load_policy
from src.local_runner.ibkr_gateway_manager import is_gateway_available, restart_gateway
from src.local_runner.update_analyst_ratings_batch import (
    _run_backfill,
    _run_one as run_analyst_update,
)
from src.local_runner.update_analyst_ratings_pipeline import (
    _iter_earnings_contexts,
    _write_progress,
)
from src.local_runner.update_ibkr_news_batch import _run_one as run_news_update


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    # One immutable provider capture per order, shared by the news, analyst
    # and full-anchor views. A later order always has its own directory.
    args.capture_dir = (args.capture_dir or args.progress_dir.resolve().parent / "news_captures").resolve()
    args.capture_max_age_seconds = load_policy(repo_root)["max_snapshot_age_hours"] * 3600
    tickers = _clean_tickers(args.tickers)
    if not tickers:
        raise RuntimeError("no_tickers_to_update")

    started_at = datetime.now(timezone.utc)
    log_dir = (
        repo_root
        / "logs"
        / "source_updates"
        / started_at.strftime("%Y-%m-%d")
        / started_at.strftime("%H-%M-%S")
    )
    news_log_dir = log_dir / "news"
    analyst_log_dir = log_dir / "analysts"
    news_log_dir.mkdir(parents=True, exist_ok=True)
    analyst_log_dir.mkdir(parents=True, exist_ok=True)
    args.progress_dir.mkdir(parents=True, exist_ok=True)
    results = _completed_progress_results(args.progress_dir, tickers)
    completed = {str(item["ticker"]) for item in results}
    pending_tickers = [ticker for ticker in tickers if ticker not in completed]

    earnings = () if not pending_tickers else (
        _iter_earnings_contexts(
            repo_root=repo_root,
            tickers=pending_tickers,
            args=args,
            now=started_at,
        )
        if args.update_analysts
        else ((ticker, {}) for ticker in pending_tickers)
    )

    deferred: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for ticker, earnings_context in earnings:
        ticker_result = _run_ticker_source_update(
            repo_root=repo_root,
            ticker=ticker,
            ticker_index=tickers.index(ticker),
            earnings_context=earnings_context,
            args=args,
            news_log_dir=news_log_dir,
            analyst_log_dir=analyst_log_dir,
        )
        if ticker_result["status"] == "ok":
            _record_source_result(args.progress_dir, results, ticker_result)
        else:
            deferred.append((ticker, earnings_context, ticker_result))
            _print_source_result(ticker_result, suffix="; deferred")
        if args.sleep_seconds > 0 and len(results) < len(tickers):
            time.sleep(args.sleep_seconds)

    for retry_round in range(1, args.deferred_retries + 1):
        if not deferred:
            break
        if args.deferred_retry_delay > 0:
            time.sleep(args.deferred_retry_delay * retry_round)
        retry_log_dir = news_log_dir / f"deferred-{retry_round}"
        retry_log_dir.mkdir(parents=True, exist_ok=True)
        next_deferred: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for ticker, earnings_context, previous_result in deferred:
            ticker_result = _run_ticker_source_update(
                repo_root=repo_root,
                ticker=ticker,
                ticker_index=tickers.index(ticker),
                earnings_context=earnings_context,
                args=args,
                news_log_dir=retry_log_dir,
                analyst_log_dir=analyst_log_dir,
                client_id_offset=10 * retry_round,
            )
            ticker_result["deferred_retry_round"] = retry_round
            ticker_result["previous_error"] = previous_result.get("error")
            if ticker_result["status"] == "ok":
                _record_source_result(args.progress_dir, results, ticker_result)
            else:
                next_deferred.append((ticker, earnings_context, ticker_result))
                _print_source_result(ticker_result, suffix="; deferred again")
        deferred = next_deferred

    for _, _, ticker_result in deferred:
        _record_source_result(args.progress_dir, results, ticker_result)

    order = {ticker: index for index, ticker in enumerate(tickers)}
    results.sort(key=lambda item: order.get(str(item.get("ticker")), len(order)))

    summary = {
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "ticker_count": len(tickers),
        "ok_count": sum(1 for item in results if item["status"] == "ok"),
        "failed_count": sum(1 for item in results if item["status"] != "ok"),
        "capture_dir": str(args.capture_dir),
        "results": results,
    }
    _write_progress(log_dir / "summary.json", summary)
    earnings_counts: dict[str, int] = {}
    for item in results:
        analyst = item.get("analysts")
        context = analyst.get("earnings_context") if isinstance(analyst, dict) else None
        if isinstance(context, dict):
            status = str(context.get("source_status") or "unknown")
            earnings_counts[status] = earnings_counts.get(status, 0) + 1
    print(
        "EARNINGS_REFRESH:"
        + json.dumps(
            {
                "status": (
                    "ok" if earnings_counts.get("unavailable", 0) == 0 else "partial"
                ),
                "max_parallel": min(args.finnhub_max_parallel, len(tickers)),
                "retries": args.finnhub_retries,
                "counts": earnings_counts,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    print(f"Summary: {log_dir / 'summary.json'}")
    return 1 if summary["failed_count"] else 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--progress-dir", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--update-news", action="store_true")
    parser.add_argument("--update-analysts", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--analyst-client-id-base", type=int, default=500)
    parser.add_argument("--news-client-id-base", type=int, default=7201)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--process-timeout", type=float, default=DEFAULT_NEWS_PROCESS_TIMEOUT)
    parser.add_argument("--provider", default="DJ-N")
    parser.add_argument("--total", type=int, default=300)
    parser.add_argument("--fallback-days", type=int, default=90)
    parser.add_argument("--overlap-hours", type=int, default=24)
    parser.add_argument("--since")
    parser.add_argument("--no-gemini-aggregation", action="store_true")
    parser.add_argument("--gemini-dry-run", action="store_true")
    parser.add_argument("--aggregate-news", action="store_true")
    parser.add_argument("--news-aggregator", choices=("codex", "gemini"), default="codex")
    parser.add_argument("--max-unresolved-bodies", type=int, default=8)
    parser.add_argument("--article-body-chars", type=int, default=2500)
    parser.add_argument("--seed-days", type=int, default=365)
    parser.add_argument("--seed-total", type=int, default=300)
    parser.add_argument("--update-total", type=int, default=300)
    parser.add_argument("--update-days", type=int, default=30)
    parser.add_argument("--sleep-seconds", type=float, default=0.25)
    parser.add_argument("--deferred-retries", type=int, default=2)
    parser.add_argument("--deferred-retry-delay", type=float, default=5.0)
    parser.add_argument("--finnhub-max-parallel", type=int, default=4)
    parser.add_argument("--finnhub-retries", type=int, default=1)
    parser.add_argument("--no-seed", action="store_true")
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--execute-upload-real", action="store_true")
    return parser.parse_args(argv)


def _run_ticker_source_update(
    *,
    repo_root: Path,
    ticker: str,
    ticker_index: int,
    earnings_context: dict[str, Any],
    args: argparse.Namespace,
    news_log_dir: Path,
    analyst_log_dir: Path,
    client_id_offset: int = 0,
) -> dict[str, Any]:
    ticker_result: dict[str, Any] = {
        "ticker": ticker,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "news": {"status": "skipped"},
        "analysts": {"status": "skipped"},
    }
    if args.update_news:
        client_id = args.news_client_id_base + ticker_index * 3 + client_id_offset
        news = run_news_update(
            repo_root=repo_root,
            ticker=ticker,
            client_id=client_id,
            args=args,
            log_dir=news_log_dir,
        )
        if news.get("status") != "ok":
            first_error = str(news.get("error") or "unknown_error")
            try:
                restarted = not is_gateway_available(args.host, args.port, timeout_seconds=5)
                if restarted:
                    restart_gateway(repo_root, host=args.host, port=args.port, timeout_seconds=120)
                news = run_news_update(
                    repo_root=repo_root,
                    ticker=ticker,
                    client_id=client_id + 1,
                    args=args,
                    log_dir=news_log_dir,
                )
                news["retried_after_gateway_restart"] = restarted
                news["first_error"] = first_error
            except Exception as exc:
                news = {
                    "ticker": ticker,
                    "status": "failed",
                    "error": f"news_recovery_failed: {exc}",
                    "first_error": first_error,
                }
        ticker_result["news"] = news

    if ticker_result["news"].get("status") == "ok" or not args.update_news:
        if args.update_analysts:
            analyst = run_analyst_update(
                repo_root=repo_root,
                ticker=ticker,
                client_id=(
                    args.analyst_client_id_base + ticker_index * 3 + client_id_offset
                ),
                args=args,
                log_dir=analyst_log_dir,
                earnings_context=earnings_context,
            )
            if analyst.get("status") == "ok" and args.backfill:
                try:
                    _run_backfill(
                        repo_root=repo_root,
                        tickers=[ticker],
                        execute_upload_real=args.execute_upload_real,
                    )
                except Exception as exc:
                    analyst["backfill_warning"] = str(exc)
            ticker_result["analysts"] = analyst

    news_ok = not args.update_news or ticker_result["news"].get("status") == "ok"
    ticker_result["status"] = "ok" if news_ok else "failed"
    if not news_ok:
        ticker_result["error"] = (
            "ibkr_news_update_failed: "
            + str(ticker_result["news"].get("error") or "unknown_error")
        )
    ticker_result["finished_at"] = datetime.now(timezone.utc).isoformat()
    return ticker_result


def _record_source_result(
    progress_dir: Path,
    results: list[dict[str, Any]],
    ticker_result: dict[str, Any],
) -> None:
    ticker = str(ticker_result["ticker"])
    results[:] = [item for item in results if str(item.get("ticker")) != ticker]
    results.append(ticker_result)
    _write_progress(progress_dir / f"{ticker}.json", ticker_result)
    _print_source_result(ticker_result)


def _print_source_result(
    ticker_result: dict[str, Any],
    *,
    suffix: str = "",
) -> None:
    print(
        f"SOURCE {ticker_result['ticker']}: {ticker_result['status']} "
        f"news={ticker_result['news'].get('status')} "
        f"analysts={ticker_result['analysts'].get('status')}{suffix}",
        flush=True,
    )


def _clean_tickers(raw: str) -> list[str]:
    result: list[str] = []
    for value in raw.split(","):
        ticker = value.strip().upper()
        if ticker and ticker not in result:
            result.append(ticker)
    return result


def _completed_progress_results(
    progress_dir: Path,
    tickers: list[str],
) -> list[dict[str, Any]]:
    completed: list[dict[str, Any]] = []
    for ticker in tickers:
        path = progress_dir / f"{ticker}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("status") == "ok":
            completed.append(payload)
    return completed


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "src" / "local_runner" / "run_one.py").exists():
            return candidate
    raise RuntimeError("Could not find repo root")


if __name__ == "__main__":
    raise SystemExit(main())
