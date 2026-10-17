"""Revalidate and publish already-generated non-escalated daily candidates."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from src.local_runner.run_one import (
    DEFAULT_CODEX_MODEL,
    DEFAULT_REASONING_EFFORT,
    _apply_daily_candidate_policy,
    _find_repo_root,
    _upload,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Recover daily candidates without another model call."
    )
    parser.add_argument("--tickers", required=True, help="Comma-separated tickers")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    tickers = _clean_tickers(args.tickers)
    failures = 0
    for ticker in tickers:
        try:
            _recover_one(repo_root, ticker, execute=args.execute)
            print(f"OK {ticker}: candidate recovered{' and uploaded' if args.execute else ''}.")
        except Exception as exc:
            failures += 1
            print(f"FAILED {ticker}: {type(exc).__name__} - {exc}")
    return 0 if failures == 0 else 1


def _recover_one(repo_root: Path, ticker: str, *, execute: bool) -> None:
    output_dir = repo_root / "output" / ticker
    candidate_md = output_dir / "candidate.md"
    candidate_json = output_dir / "candidate.json"
    candidate_html = output_dir / "candidate.html"
    if not candidate_md.is_file() or not candidate_json.is_file():
        raise RuntimeError("candidate_artifacts_missing")
    payload = _read_json(candidate_json)
    shutil.copy2(candidate_md, output_dir / "latest.md")
    shutil.copy2(candidate_json, output_dir / "latest.json")
    if candidate_html.is_file():
        shutil.copy2(candidate_html, output_dir / "latest.html")
    status = _apply_daily_candidate_policy(
        repo_root=repo_root,
        symbol=ticker,
        generation_model=str(payload.get("generation_model") or DEFAULT_CODEX_MODEL),
        reasoning_effort=str(
            payload.get("reasoning_effort") or DEFAULT_REASONING_EFFORT
        ),
        reference_tier=str(payload.get("reference_tier") or "tracking"),
        owned=payload.get("owned") is True,
    )
    if status != 0:
        raise RuntimeError(f"candidate_policy_failed: exit_code={status}")
    latest = _read_json(output_dir / "latest.json")
    workflow = latest.get("analysis_workflow")
    if not isinstance(workflow, dict) or workflow.get("status") != "published_score_locked":
        raise RuntimeError("candidate_now_requires_review")
    _upload(
        repo_root=repo_root,
        symbol=ticker,
        upload_kind="real",
        dry_run=not execute,
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid_json: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object: {path}")
    return payload


def _clean_tickers(raw: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in raw.split(","):
        ticker = value.strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            result.append(ticker)
    if not result:
        raise RuntimeError("no_tickers")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
