"""Backfill analyst summaries into existing latest.json reports."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.local_runner.analyst_summary import load_compact_analyst_summary
from src.local_runner.gcs_uploader import CONTENT_TYPE_JSON, TEST_BUCKET, require_gcloud
from src.local_runner.run_batch import TICKERS_GCS_URI


CORE_TICKERS_GCS_URI = f"gs://{TEST_BUCKET}/config/tickers_core.json"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    tickers = _load_tickers(args)

    if args.limit is not None:
        tickers = tickers[: args.limit]

    if not tickers:
        raise RuntimeError("no_tickers_to_backfill")

    gcloud_path = require_gcloud()
    results = []

    for ticker in tickers:
        results.append(
            _backfill_one(
                repo_root=repo_root,
                gcloud_path=gcloud_path,
                ticker=ticker,
                execute_upload=args.execute_upload_real,
                write_unavailable=args.write_unavailable,
            )
        )

    ok_count = sum(1 for item in results if item["status"] == "ok")
    skipped_count = sum(1 for item in results if item["status"] == "skipped")
    failed_count = sum(1 for item in results if item["status"] == "failed")

    print(
        "Backfill analyst summaries: "
        f"ok={ok_count} skipped={skipped_count} failed={failed_count} "
        f"upload={'executed' if args.execute_upload_real else 'dry-run'}"
    )

    for item in results:
        if item["status"] != "ok":
            print(f"{item['status'].upper()} {item['ticker']}: {item['reason']}")

    return 1 if failed_count else 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Patch existing latest.json reports with local analyst summaries "
            "without rerunning analyses."
        )
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
    source.add_argument(
        "--config-gcs",
        help="Read tickers from a custom GCS JSON URI.",
    )
    source.add_argument(
        "--tickers",
        help="Comma-separated ticker list, for example MU,RKLB,GOOG.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Only process the first N tickers after cleaning.",
    )
    parser.add_argument(
        "--write-unavailable",
        action="store_true",
        help=(
            "Write an unavailable analyst_ratings_summary when no local "
            "current.json exists. By default such tickers are skipped."
        ),
    )
    parser.add_argument(
        "--execute-upload-real",
        action="store_true",
        help=(
            "Actually upload patched latest.json files to GCS. Without this, "
            "the command only writes local output/<ticker>/latest.json files."
        ),
    )

    args = parser.parse_args(argv)

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than 0")

    return args


def _load_tickers(args: argparse.Namespace) -> list[str]:
    if args.tickers:
        return _clean_tickers(args.tickers.split(","))

    source = TICKERS_GCS_URI
    if args.core:
        source = CORE_TICKERS_GCS_URI
    elif args.config_gcs:
        source = args.config_gcs

    payload = json.loads(_read_gcs_text(source))
    tickers = payload.get("tickers") if isinstance(payload, dict) else None

    if not isinstance(tickers, list):
        raise RuntimeError(f"invalid_tickers_json: {source}")

    return _clean_tickers(tickers)


def _backfill_one(
    *,
    repo_root: Path,
    gcloud_path: str,
    ticker: str,
    execute_upload: bool,
    write_unavailable: bool,
) -> dict[str, str]:
    summary = load_compact_analyst_summary(repo_root, ticker)

    if summary.get("status") != "ok" and not write_unavailable:
        return {
            "ticker": ticker,
            "status": "skipped",
            "reason": str(summary.get("reason") or "analyst_summary_unavailable"),
        }

    try:
        payload = _read_latest_json(gcloud_path, ticker)
    except Exception as exc:  # noqa: BLE001 - CLI should continue per ticker.
        return {
            "ticker": ticker,
            "status": "failed",
            "reason": f"read_latest_json_failed: {exc}",
        }

    payload["analyst_ratings_summary"] = summary

    output_path = repo_root / "output" / ticker / "latest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if execute_upload:
        try:
            _upload_latest_json(gcloud_path, ticker, output_path)
        except Exception as exc:  # noqa: BLE001 - CLI should continue per ticker.
            return {
                "ticker": ticker,
                "status": "failed",
                "reason": f"upload_latest_json_failed: {exc}",
            }

    return {
        "ticker": ticker,
        "status": "ok",
        "reason": "",
    }


def _read_latest_json(gcloud_path: str, ticker: str) -> dict[str, Any]:
    uri = f"gs://{TEST_BUCKET}/{ticker}/latest.json"
    raw = _run_gcloud(gcloud_path, "storage", "cat", uri).stdout
    payload = json.loads(raw)

    if not isinstance(payload, dict):
        raise RuntimeError("latest_json_not_object")

    return payload


def _upload_latest_json(gcloud_path: str, ticker: str, source: Path) -> None:
    uri = f"gs://{TEST_BUCKET}/{ticker}/latest.json"
    _run_gcloud(
        gcloud_path,
        "storage",
        "cp",
        f"--content-type={CONTENT_TYPE_JSON}",
        str(source),
        uri,
    )


def _read_gcs_text(uri: str) -> str:
    gcloud_path = require_gcloud()
    return _run_gcloud(gcloud_path, "storage", "cat", uri).stdout


def _run_gcloud(gcloud_path: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [gcloud_path, *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


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


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()

    for candidate in (current, *current.parents):
        if (candidate / "src" / "local_runner").exists():
            return candidate

    raise RuntimeError(f"repo_root_not_found: {start}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED backfill_analyst_summaries: {exc}", file=sys.stderr)
        raise SystemExit(1)
