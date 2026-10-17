"""Update IBKR analyst ratings for a ticker list, then optionally backfill reports."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.local_runner.backfill_analyst_summaries import (
    CORE_TICKERS_GCS_URI,
    _clean_tickers,
    _read_gcs_text,
)
from src.local_runner.run_batch import TICKERS_GCS_URI
from src.local_runner.finnhub_earnings import (
    DEFAULT_DAYS_BACK as FINNHUB_DAYS_BACK,
    DEFAULT_DAYS_FORWARD as FINNHUB_DAYS_FORWARD,
    build_earnings_payload,
    fetch_earnings_calendar,
)
from src.local_runner.local_env import get_local_env_value


DEFAULT_FINNHUB_MAX_PARALLEL = 4
DEFAULT_FINNHUB_RETRIES = 1


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
        / "analyst_updates"
        / run_started.strftime("%Y-%m-%d")
        / run_started.strftime("%H-%M-%S")
    )
    log_dir.mkdir(parents=True, exist_ok=True)

    earnings_contexts, earnings_refresh = _prefetch_earnings_contexts(
        repo_root=repo_root,
        tickers=tickers,
        args=args,
        now=run_started,
    )
    _write_json(log_dir / "earnings_refresh.json", earnings_refresh)

    results: list[dict[str, Any]] = []

    for index, ticker in enumerate(tickers):
        client_id = args.client_id_base + index * 3
        result = _run_one(
            repo_root=repo_root,
            ticker=ticker,
            client_id=client_id,
            args=args,
            log_dir=log_dir,
            earnings_context=earnings_contexts[ticker],
        )
        results.append(result)
        print(
            f"{result['status'].upper()} {ticker}: "
            f"{result.get('summary', result.get('error', ''))}"
        )

        if args.sleep_seconds > 0 and index < len(tickers) - 1:
            time.sleep(args.sleep_seconds)

    summary_path = log_dir / "summary.json"
    summary = {
        "started_at": run_started.isoformat(),
        "source": source,
        "ticker_count": len(tickers),
        "ok_count": sum(1 for item in results if item["status"] == "ok"),
        "failed_count": sum(1 for item in results if item["status"] != "ok"),
        "earnings_refresh": earnings_refresh,
        "results": results,
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.backfill:
        ok_tickers = [item["ticker"] for item in results if item["status"] == "ok"]
        if ok_tickers:
            _run_backfill(
                repo_root=repo_root,
                tickers=ok_tickers,
                execute_upload_real=args.execute_upload_real,
            )

    print(
        "EARNINGS_REFRESH:"
        + json.dumps(
            {
                "status": earnings_refresh["status"],
                "max_parallel": earnings_refresh["max_parallel"],
                "retries": earnings_refresh["retries"],
                "counts": earnings_refresh["counts"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    print(f"Summary: {summary_path}")
    return 1 if summary["failed_count"] else 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update current analyst ratings from IBKR for a ticker list."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--from-gcs",
        action="store_true",
        help=f"Read trading tickers from {TICKERS_GCS_URI}. This is the default.",
    )
    source.add_argument(
        "--core",
        action="store_true",
        help=f"Read core tickers from {CORE_TICKERS_GCS_URI}.",
    )
    source.add_argument("--config-gcs", help="Read tickers from a custom GCS URI.")
    source.add_argument("--tickers", help="Comma-separated ticker list.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id-base", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--seed-days", type=int, default=365)
    parser.add_argument("--seed-total", type=int, default=300)
    parser.add_argument("--update-total", type=int, default=300)
    parser.add_argument("--update-days", type=int, default=30)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument(
        "--finnhub-max-parallel",
        type=int,
        default=DEFAULT_FINNHUB_MAX_PARALLEL,
    )
    parser.add_argument(
        "--finnhub-retries",
        type=int,
        default=DEFAULT_FINNHUB_RETRIES,
    )
    parser.add_argument("--no-seed", action="store_true")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="After successful analyst updates, patch latest.json for those tickers.",
    )
    parser.add_argument(
        "--execute-upload-real",
        action="store_true",
        help="With --backfill, upload patched latest.json files to GCS.",
    )

    args = parser.parse_args(argv)

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than 0")
    if args.seed_days < 1:
        parser.error("--seed-days must be >= 1")
    if args.seed_total < 1:
        parser.error("--seed-total must be >= 1")
    if args.update_total < 1:
        parser.error("--update-total must be >= 1")
    if args.update_days < 1:
        parser.error("--update-days must be >= 1")
    if args.sleep_seconds < 0:
        parser.error("--sleep-seconds must be >= 0")
    if args.finnhub_max_parallel < 1:
        parser.error("--finnhub-max-parallel must be >= 1")
    if args.finnhub_retries < 0:
        parser.error("--finnhub-retries must be >= 0")
    if args.execute_upload_real and not args.backfill:
        parser.error("--execute-upload-real requires --backfill")

    return args


def _load_tickers(args: argparse.Namespace) -> tuple[list[str], str]:
    if args.tickers:
        return _clean_tickers(args.tickers.split(",")), "--tickers"

    source = TICKERS_GCS_URI
    if args.core:
        source = CORE_TICKERS_GCS_URI
    elif args.config_gcs:
        source = args.config_gcs

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
    earnings_context: dict[str, Any],
) -> dict[str, Any]:
    earnings_dir = log_dir / "earnings"
    earnings_path = earnings_dir / f"{ticker}.json"
    _write_json(earnings_path, earnings_context)
    command = [
        sys.executable,
        "-m",
        "src.local_runner.ibkr_analyst_update",
        ticker,
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--client-id",
        str(client_id),
        "--timeout",
        str(args.timeout),
        "--earnings-context-file",
        str(earnings_path),
        "--seed-days",
        str(args.seed_days),
        "--seed-total",
        str(args.seed_total),
        "--update-total",
        str(args.update_total),
        "--update-days",
        str(args.update_days),
    ]

    if args.no_seed:
        command.append("--no-seed")

    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = round(time.perf_counter() - started, 2)
    output = completed.stdout or ""
    log_path = log_dir / f"{ticker}.log"
    log_path.write_text(output, encoding="utf-8")

    if completed.returncode != 0:
        return {
            "ticker": ticker,
            "status": "failed",
            "elapsed_seconds": elapsed,
            "log": str(log_path),
            "error": _last_non_empty_line(output) or f"exit_{completed.returncode}",
        }

    return {
        "ticker": ticker,
        "status": "ok",
        "elapsed_seconds": elapsed,
        "log": str(log_path),
        "summary": _summarize_output(output),
        "earnings_context": earnings_context,
    }


def _prefetch_earnings_contexts(
    *,
    repo_root: Path,
    tickers: list[str],
    args: argparse.Namespace,
    now: datetime,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    api_key = (
        get_local_env_value("FINN_KEY", repo_root=repo_root)
        or get_local_env_value("FINNHUB_API_KEY", repo_root=repo_root)
    )
    workers = min(args.finnhub_max_parallel, len(tickers))
    contexts: dict[str, dict[str, Any]] = {}

    if not api_key:
        for ticker in tickers:
            contexts[ticker] = _cached_earnings_context(
                repo_root=repo_root,
                ticker=ticker,
                now=now,
                error="missing_finnhub_api_key",
                attempts=0,
            )
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _fetch_earnings_context,
                    repo_root=repo_root,
                    ticker=ticker,
                    api_key=api_key,
                    now=now,
                    retries=args.finnhub_retries,
                ): ticker
                for ticker in tickers
            }
            for future in concurrent.futures.as_completed(futures):
                ticker = futures[future]
                try:
                    contexts[ticker] = future.result()
                except Exception as exc:  # defensive: preserve the batch
                    contexts[ticker] = _cached_earnings_context(
                        repo_root=repo_root,
                        ticker=ticker,
                        now=now,
                        error=f"prefetch_runtime_error: {exc}",
                        attempts=args.finnhub_retries + 1,
                    )

    ordered = {ticker: contexts[ticker] for ticker in tickers}
    counts: dict[str, int] = {}
    for context in ordered.values():
        status = str(context.get("source_status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return ordered, {
        "status": "ok" if counts.get("unavailable", 0) == 0 else "partial",
        "max_parallel": workers,
        "retries": args.finnhub_retries,
        "counts": counts,
        "tickers": ordered,
    }


def _fetch_earnings_context(
    *,
    repo_root: Path,
    ticker: str,
    api_key: str,
    now: datetime,
    retries: int,
) -> dict[str, Any]:
    today = now.date()
    start = today - timedelta(days=FINNHUB_DAYS_BACK)
    end = today + timedelta(days=FINNHUB_DAYS_FORWARD)
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
                today=today,
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
        except Exception as exc:  # network/provider errors are retried
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


def _cached_earnings_context(
    *,
    repo_root: Path,
    ticker: str,
    now: datetime,
    error: str,
    attempts: int,
) -> dict[str, Any]:
    state_path = repo_root / "data" / "analyst_ratings" / ticker / "current.json"
    state: dict[str, Any] = {}
    try:
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            state = loaded
    except (OSError, json.JSONDecodeError):
        pass
    earnings = state.get("earnings") if isinstance(state.get("earnings"), dict) else {}
    previous = earnings.get("previous_earnings_date")
    upcoming = earnings.get("next_earnings_date")
    cached_as_of = earnings.get("data_as_of") or state.get("as_of")
    age_days = None
    if isinstance(cached_as_of, str):
        try:
            cached_at = datetime.fromisoformat(cached_as_of.replace("Z", "+00:00"))
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            age_days = max(0, (now - cached_at).days)
        except ValueError:
            pass
    available = bool(previous or upcoming)
    return {
        "status": "ok" if available else "failed",
        "source_status": "cached_fallback" if available else "unavailable",
        "source": "FINNHUB_EARNINGS_CALENDAR",
        "previous_earnings_date": previous,
        "next_earnings_date": upcoming,
        "data_as_of": cached_as_of,
        "age_days": age_days,
        "attempts": attempts,
        "live_error": error,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _run_backfill(
    *,
    repo_root: Path,
    tickers: list[str],
    execute_upload_real: bool,
) -> None:
    command = [
        sys.executable,
        "-m",
        "src.local_runner.backfill_analyst_summaries",
        "--tickers",
        ",".join(tickers),
    ]

    if execute_upload_real:
        command.append("--execute-upload-real")

    subprocess.run(command, cwd=repo_root, check=True)


def _summarize_output(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    basis = next((line for line in lines if line.startswith("Basis:")), "")
    ratings = next((line for line in lines if line.startswith("Ratings:")), "")
    targets = next((line for line in lines if line.startswith("Targets:")), "")
    return " | ".join(line for line in (basis, ratings, targets) if line)


def _last_non_empty_line(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
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
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED update_analyst_ratings_batch: {exc}", file=sys.stderr)
        raise SystemExit(1)
