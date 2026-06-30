"""Update recent IBKR news headlines for a ticker list."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.local_runner.backfill_analyst_summaries import _clean_tickers, _read_gcs_text
from src.local_runner.run_batch import TICKERS_GCS_URI


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    tickers, source = _load_tickers(args)

    if args.limit is not None:
        tickers = tickers[: args.limit]

    if not tickers:
        raise RuntimeError("no_tickers_to_update")

    run_started = datetime.now(timezone.utc)
    log_dir = (
        repo_root
        / "logs"
        / "ibkr_news_updates"
        / run_started.strftime("%Y-%m-%d")
        / run_started.strftime("%H-%M-%S")
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for index, ticker in enumerate(tickers):
        result = _run_one(
            repo_root=repo_root,
            ticker=ticker,
            client_id=args.client_id_base + index * 3,
            args=args,
            log_dir=log_dir,
        )
        results.append(result)
        print(
            f"{result['status'].upper()} {ticker}: "
            f"{result.get('summary', result.get('error', ''))}"
        )

        if args.sleep_seconds > 0 and index < len(tickers) - 1:
            time.sleep(args.sleep_seconds)

    summary = {
        "started_at": run_started.isoformat(),
        "source": source,
        "ticker_count": len(tickers),
        "ok_count": sum(1 for item in results if item["status"] == "ok"),
        "failed_count": sum(1 for item in results if item["status"] != "ok"),
        "results": results,
    }
    summary_path = log_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Summary: {summary_path}")

    return 1 if summary["failed_count"] else 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update recent IBKR news headlines for a ticker list."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--from-gcs", action="store_true")
    source.add_argument("--tickers", help="Comma-separated ticker list.")
    source.add_argument("--config-gcs", help="Read tickers from a custom GCS JSON URI.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--client-id-base", type=int, default=7201)
    parser.add_argument("--sleep-seconds", type=float, default=0.25)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--process-timeout", type=float, default=900.0)
    parser.add_argument("--provider", default="DJ-N")
    parser.add_argument("--total", type=int, default=300)
    parser.add_argument("--fallback-days", type=int, default=90)
    parser.add_argument("--overlap-hours", type=int, default=24)
    parser.add_argument("--since", help="Explicit UTC start datetime for every ticker.")
    parser.add_argument("--no-gemini-aggregation", action="store_true")
    parser.add_argument("--gemini-dry-run", action="store_true")
    parser.add_argument("--aggregate-news", action="store_true")
    parser.add_argument(
        "--news-aggregator",
        choices=("codex", "gemini"),
        default="codex",
    )
    parser.add_argument("--max-unresolved-bodies", type=int, default=8)
    parser.add_argument("--article-body-chars", type=int, default=2500)

    args = parser.parse_args(argv)

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be >= 1")
    if args.total < 1:
        parser.error("--total must be >= 1")
    if args.fallback_days < 1:
        parser.error("--fallback-days must be >= 1")
    if args.overlap_hours < 0:
        parser.error("--overlap-hours must be >= 0")
    if args.process_timeout < 60:
        parser.error("--process-timeout must be >= 60")
    if args.max_unresolved_bodies < 0:
        parser.error("--max-unresolved-bodies must be >= 0")
    if args.article_body_chars < 200:
        parser.error("--article-body-chars must be >= 200")

    return args


def _load_tickers(args: argparse.Namespace) -> tuple[list[str], str]:
    if args.tickers:
        return _clean_tickers(args.tickers.split(",")), "--tickers"

    source = args.config_gcs or TICKERS_GCS_URI
    payload = json.loads(_read_gcs_text(source))
    tickers = payload.get("tickers") if isinstance(payload, dict) else None
    if not isinstance(tickers, list):
        raise RuntimeError(f"invalid_tickers_json: {source}")

    return _clean_tickers(tickers), source


def _run_one(
    *,
    repo_root: Path,
    ticker: str,
    client_id: int,
    args: argparse.Namespace,
    log_dir: Path,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    command = [
        sys.executable,
        "-m",
        "src.local_runner.ibkr_news_update",
        ticker,
        "--client-id",
        str(client_id),
        "--timeout",
        str(args.timeout),
        "--provider",
        str(args.provider),
        "--total",
        str(args.total),
        "--fallback-days",
        str(args.fallback_days),
        "--overlap-hours",
        str(args.overlap_hours),
    ]
    if args.since:
        command.extend(["--since", str(args.since)])
    if args.no_gemini_aggregation:
        command.append("--no-gemini-aggregation")
    if args.gemini_dry_run:
        command.append("--gemini-dry-run")
    if args.aggregate_news:
        command.append("--aggregate-news")
    command.extend(["--news-aggregator", str(args.news_aggregator)])
    command.extend(["--max-unresolved-bodies", str(args.max_unresolved_bodies)])
    command.extend(["--article-body-chars", str(args.article_body_chars)])
    try:
        completed = subprocess.run(
            command,
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=args.process_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        finished = datetime.now(timezone.utc)
        log_path = log_dir / f"{ticker}.log"
        log_path.write_text(
            (exc.stdout or "") + (exc.stderr or "") + "\nPROCESS_TIMEOUT\n",
            encoding="utf-8",
        )
        return {
            "ticker": ticker,
            "status": "failed",
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "elapsed_seconds": round((finished - started).total_seconds(), 3),
            "log": str(log_path),
            "error": f"process_timeout_after_{args.process_timeout:g}s",
        }
    finished = datetime.now(timezone.utc)
    log_path = log_dir / f"{ticker}.log"
    log_path.write_text(
        (completed.stdout or "") + (completed.stderr or ""),
        encoding="utf-8",
    )

    payload: dict[str, Any] = {
        "ticker": ticker,
        "status": "ok" if completed.returncode == 0 else "failed",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "elapsed_seconds": round((finished - started).total_seconds(), 3),
        "log": str(log_path),
    }

    if completed.returncode == 0:
        payload["summary"] = _last_non_empty_line(completed.stdout)
    else:
        payload["error"] = _last_non_empty_line(completed.stderr or completed.stdout)

    return payload


def _last_non_empty_line(value: str) -> str:
    lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


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
        print(f"FAILED update_ibkr_news_batch: {exc}", file=sys.stderr)
        raise SystemExit(1)
