"""Update IBKR analyst ratings for a ticker list, then optionally backfill reports."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.local_runner.backfill_analyst_summaries import (
    CORE_TICKERS_GCS_URI,
    _clean_tickers,
    _read_gcs_text,
)
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
        / "analyst_updates"
        / run_started.strftime("%Y-%m-%d")
        / run_started.strftime("%H-%M-%S")
    )
    log_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []

    for index, ticker in enumerate(tickers):
        client_id = args.client_id_base + index * 3
        result = _run_one(
            repo_root=repo_root,
            ticker=ticker,
            client_id=client_id,
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

    summary_path = log_dir / "summary.json"
    summary = {
        "started_at": run_started.isoformat(),
        "source": source,
        "ticker_count": len(tickers),
        "ok_count": sum(1 for item in results if item["status"] == "ok"),
        "failed_count": sum(1 for item in results if item["status"] != "ok"),
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
) -> dict[str, Any]:
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
    }


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
