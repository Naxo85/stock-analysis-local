"""Run local Codex ticker analyses in a limited parallel batch."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.local_runner.gcs_uploader import require_gcloud


TICKERS_GCS_URI = "gs://stock-analysis-reports-naxo85/config/tickers.json"
DEFAULT_MAX_PARALLEL = 2
MAX_PARALLEL_LIMIT = 8


@dataclass(frozen=True)
class BatchConfig:
    repo_root: Path
    tickers: tuple[str, ...]
    source: str
    max_parallel: int
    retry_failed: int
    upload_real: bool
    log_dir: Path


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    max_parallel = _normalize_max_parallel(args.max_parallel)
    tickers, source = _load_tickers(args)

    if args.limit is not None:
        tickers = tickers[: args.limit]

    if args.resume:
        tickers = _filter_resume_tickers(tickers, args.resume_from)

    if not tickers:
        raise RuntimeError("no_tickers_to_run")

    if not args.upload_real:
        raise RuntimeError("upload_real_required: batch currently supports real runs only")

    run_started = _utc_now()
    log_dir = (
        repo_root
        / "logs"
        / "batch"
        / run_started.strftime("%Y-%m-%d")
        / run_started.strftime("%H-%M-%S")
    )
    (log_dir / "tickers").mkdir(parents=True, exist_ok=True)

    config = BatchConfig(
        repo_root=repo_root,
        tickers=tuple(tickers),
        source=source,
        max_parallel=max_parallel,
        retry_failed=args.retry_failed,
        upload_real=args.upload_real,
        log_dir=log_dir,
    )

    return _run_batch(config, run_started)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local Codex analyses for multiple tickers."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--from-gcs",
        action="store_true",
        help=f"Read ticker list from {TICKERS_GCS_URI}.",
    )
    source.add_argument(
        "--config-gcs",
        help="Read ticker list from a custom GCS JSON URI.",
    )
    source.add_argument(
        "--tickers",
        help="Comma-separated ticker list, for example RKLB,GOOG,IBKR.",
    )
    parser.add_argument(
        "--upload-real",
        action="store_true",
        help="Run each ticker with the full real upload flow.",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=DEFAULT_MAX_PARALLEL,
        help="Maximum concurrent tickers. Values above 8 are capped to 8.",
    )
    parser.add_argument(
        "--retry-failed",
        type=int,
        default=1,
        help="Retry failed tickers up to N additional times. Defaults to 1.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Only run the first N tickers after cleaning and resume filtering.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip tickers already marked ok in --resume-from summary.",
    )
    parser.add_argument(
        "--resume-from",
        type=Path,
        help="Path to a previous logs/batch/.../summary.json.",
    )

    args = parser.parse_args(argv)

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than 0")

    if args.max_parallel < 1:
        parser.error("--max-parallel must be greater than 0")

    if args.retry_failed < 0:
        parser.error("--retry-failed must be 0 or greater")

    if args.resume and not args.resume_from:
        parser.error("--resume requires --resume-from")

    if args.resume_from and not args.resume:
        parser.error("--resume-from can only be used with --resume")

    return args


def _load_tickers(args: argparse.Namespace) -> tuple[list[str], str]:
    if args.from_gcs or args.config_gcs:
        source = args.config_gcs or TICKERS_GCS_URI
        raw = _read_gcs_text(source)
        payload = json.loads(raw)

        if not isinstance(payload, dict):
            raise RuntimeError("invalid_tickers_json: expected object")

        tickers = payload.get("tickers")

        if not isinstance(tickers, list):
            raise RuntimeError("invalid_tickers_json: tickers must be a list")

        return _clean_tickers(tickers), source

    return _clean_tickers(str(args.tickers).split(",")), "--tickers"


def _read_gcs_text(uri: str) -> str:
    gcloud_path = require_gcloud()
    completed = subprocess.run(
        [gcloud_path, "storage", "cat", uri],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout


def _clean_tickers(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    tickers: list[str] = []

    for value in values:
        ticker = str(value).strip().upper()

        if not ticker or ticker in seen:
            continue

        seen.add(ticker)
        tickers.append(ticker)

    return tickers


def _normalize_max_parallel(value: int) -> int:
    if value > MAX_PARALLEL_LIMIT:
        print(
            "WARNING: --max-parallel greater than "
            f"{MAX_PARALLEL_LIMIT}; capping to {MAX_PARALLEL_LIMIT}."
        )
        return MAX_PARALLEL_LIMIT

    return value


def _filter_resume_tickers(tickers: list[str], summary_path: Path | None) -> list[str]:
    if summary_path is None:
        return tickers

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid_resume_summary: {summary_path}") from exc

    results = payload.get("results", [])

    if not isinstance(results, list):
        raise RuntimeError("invalid_resume_summary: results must be a list")

    completed_ok = {
        str(item.get("ticker", "")).strip().upper()
        for item in results
        if isinstance(item, dict) and item.get("status") == "ok"
    }

    return [ticker for ticker in tickers if ticker not in completed_ok]


def _run_batch(config: BatchConfig, run_started: datetime) -> int:
    results = _run_ticker_pass(config, config.tickers, attempt=1)

    for retry_index in range(1, config.retry_failed + 1):
        failed_tickers = tuple(
            str(result["ticker"])
            for result in results
            if result.get("status") != "ok"
        )

        if not failed_tickers:
            break

        _print_retry(retry_index, config.retry_failed, failed_tickers)
        retry_results = _run_ticker_pass(
            config,
            failed_tickers,
            attempt=retry_index + 1,
        )
        results = _merge_retry_results(results, retry_results)

    summary = _build_summary(config, run_started, results)
    _write_json(config.log_dir / "summary.json", summary)
    _print_summary(summary)

    return 0 if summary["failed"] == 0 else 1


def _run_ticker_pass(
    config: BatchConfig,
    tickers: tuple[str, ...],
    attempt: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(config.max_parallel, len(tickers))
    ) as executor:
        futures = {
            executor.submit(_run_one_ticker, config.repo_root, ticker, attempt): ticker
            for ticker in tickers
        }

        for future in concurrent.futures.as_completed(futures):
            ticker = futures[future]

            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "ticker": ticker,
                    "attempt": attempt,
                    "status": "failed",
                    "error_type": "runtime_error",
                    "error_message": str(exc),
                }

            results.append(result)
            _write_json(config.log_dir / "tickers" / f"{ticker}.json", result)
            _print_ticker_result(result)

    return results


def _merge_retry_results(
    results: list[dict[str, Any]],
    retry_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    retry_by_ticker = {
        str(result["ticker"]): result
        for result in retry_results
    }

    return [
        retry_by_ticker.get(str(result["ticker"]), result)
        for result in results
    ]


def _run_one_ticker(repo_root: Path, ticker: str, attempt: int) -> dict[str, Any]:
    started = _utc_now()
    started_perf = time.perf_counter()
    command = [
        sys.executable,
        "-m",
        "src.local_runner.run_one",
        ticker,
        "--run-full",
    ]

    completed = subprocess.run(
        command,
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    finished = _utc_now()
    duration_seconds = round(time.perf_counter() - started_perf, 3)
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()

    result: dict[str, Any] = {
        "ticker": ticker,
        "attempt": attempt,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": duration_seconds,
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }

    if completed.returncode == 0:
        result["status"] = "ok"
        return result

    latest_json = _load_latest_json(repo_root, ticker)
    result.update(
        {
            "status": "failed",
            "error_type": latest_json.get("error_type") or "run_one_failed",
            "error_message": (
                latest_json.get("error_message")
                or _short_failure_from_output(stdout)
                or stderr
                or f"exit_code={completed.returncode}"
            ),
        }
    )

    return result


def _build_summary(
    config: BatchConfig,
    run_started: datetime,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    finished = _utc_now()
    ordered_results = sorted(
        results,
        key=lambda item: config.tickers.index(str(item["ticker"])),
    )
    success = sum(1 for item in ordered_results if item.get("status") == "ok")
    failed = len(ordered_results) - success

    return {
        "started_at": run_started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round((finished - run_started).total_seconds(), 3),
        "source": config.source,
        "max_parallel": config.max_parallel,
        "retry_failed": config.retry_failed,
        "total": len(ordered_results),
        "success": success,
        "failed": failed,
        "results": [
            _summary_result(item)
            for item in ordered_results
        ],
    }


def _summary_result(result: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ticker": result["ticker"],
        "status": result["status"],
        "attempt": result.get("attempt"),
        "duration_seconds": result.get("duration_seconds"),
    }

    if result.get("status") != "ok":
        payload["error_type"] = result.get("error_type", "failed")
        payload["error_message"] = result.get("error_message", "")

    return payload


def _print_ticker_result(result: dict[str, Any]) -> None:
    ticker = result["ticker"]
    attempt = int(result.get("attempt") or 1)
    attempt_suffix = f" retry#{attempt - 1}" if attempt > 1 else ""

    if result.get("status") == "ok":
        print(f"OK {ticker}{attempt_suffix}")
        return

    reason = result.get("error_message") or result.get("error_type") or "failed"
    print(f"FAILED {ticker}{attempt_suffix}: {str(reason)[:160]}")


def _print_retry(
    retry_index: int,
    retry_total: int,
    tickers: tuple[str, ...],
) -> None:
    print(
        f"RETRY {retry_index}/{retry_total}: "
        f"{', '.join(tickers)}."
    )


def _print_summary(summary: dict[str, Any]) -> None:
    total = summary["total"]
    success = summary["success"]
    failed = summary["failed"]

    if failed == 0:
        print(f"OK: {success}/{total} análisis generados y subidos.")
        return

    failed_tickers = [
        item["ticker"]
        for item in summary["results"]
        if item.get("status") != "ok"
    ]
    print(
        f"OK: {success}/{total} análisis generados y subidos. "
        f"Fallidos: {', '.join(failed_tickers)}."
    )


def _short_failure_from_output(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("FAILED "):
            return line.split(": ", 1)[1] if ": " in line else line

    return ""


def _load_latest_json(repo_root: Path, ticker: str) -> dict[str, Any]:
    latest_json_path = repo_root / "output" / ticker / "latest.json"

    if not latest_json_path.exists():
        return {}

    try:
        payload = json.loads(latest_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    return payload if isinstance(payload, dict) else {}


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()

    for candidate in (current, *current.parents):
        if (candidate / "src" / "local_runner" / "run_one.py").exists():
            return candidate

    raise RuntimeError("Could not find repo root from current directory")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


if __name__ == "__main__":
    sys.exit(main())
