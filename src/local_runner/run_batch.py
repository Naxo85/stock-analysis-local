"""Run local ticker analyses in a limited parallel batch."""

from __future__ import annotations

import argparse
import atexit
import concurrent.futures
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.local_runner.ibkr_news_pagination import DEFAULT_NEWS_PROCESS_TIMEOUT
from src.local_runner.gcs_uploader import require_gcloud
from src.local_runner.process_control import run_bounded, configure_utf8_output
from src.local_runner.ibkr_gateway_manager import ensure_gateway
from src.local_runner.chatgpt_browser_generator import (
    ChatGPTBrowserSession,
    ChatGPTBrowserSessionPool,
)
from src.local_runner.run_one import (
    _finalize_real as _finalize_one,
    _generate as _generate_one,
    _run_full as _run_one_full,
    _validate as _validate_one,
)
from src.local_runner.analysis_policy import (
    MADRID_TZ,
    RouteDecision,
    TickerRecord,
    batch_day_mode,
    parse_reference_summary,
    route_ticker,
)
from src.local_runner.analysis_state import load_reference_payload


TICKERS_GCS_URI = "gs://stock-analysis-reports-naxo85/config/tickers.json"
CORE_TICKERS_GCS_URI = "gs://stock-analysis-reports-naxo85/config/tickers_core.json"
BATCH_STATUS_GCS_PREFIX = "gs://stock-analysis-reports-naxo85/batch/status"
SHEET_STATUS_MIRROR_GCS_PREFIX = (
    "gs://stock-analysis-system-naxo85/runtime/analysis-status"
)
PROFILE_REASONING_EFFORT = {"trading": "medium", "core": "medium"}
DEFAULT_MAX_PARALLEL = 3
MAX_PARALLEL_LIMIT = 8
MAX_REVIEW_PARALLEL = 2
TRANSIENT_REVIEW_RETRIES = 2
TRANSIENT_REVIEW_BACKOFF_SECONDS = 5.0
PIPELINE_STATE_VERSION = 1
PIPELINE_STATE_REPLACE_TIMEOUT_SECONDS = 10.0
PIPELINE_STATE_REPLACE_RETRY_INTERVAL_SECONDS = 0.1
MAX_FINALIZE_PARALLEL = 4
PROGRESS_HEARTBEAT_SECONDS = 15.0
PIPELINE_STAGE_TIMEOUT_SECONDS = {
    "prepare": 15 * 60,
    "analyze": 35 * 60,
    "publish": 10 * 60,
}
DEFAULT_CHATGPT_WEB_WORKERS = 3
MAX_CHATGPT_WEB_WORKERS = 3

BrowserSession = ChatGPTBrowserSession | ChatGPTBrowserSessionPool


@dataclass(frozen=True)
class BatchConfig:
    repo_root: Path
    tickers: tuple[str, ...]
    source: str
    max_parallel: int
    retry_failed: int
    upload_real: bool
    log_dir: Path
    update_analysts: bool
    update_ibkr_news: bool
    analysis_profile: str
    routes: tuple[RouteDecision, ...]
    model: str | None
    reasoning_effort: str
    generation_provider: str = "chatgpt-browser"
    chatgpt_browser_headed: bool = False
    chatgpt_browser_max_attempts: int = 2
    chatgpt_chat_group_size: int = 5
    chatgpt_web_workers: int = DEFAULT_CHATGPT_WEB_WORKERS
    generator_fallback: bool = True
    resume_pipeline_from: Path | None = None
    adaptive_codex: bool = False
    ownership_context: dict[str, dict[str, Any]] | None = None


@dataclass(frozen=True)
class PipelineTask:
    ticker: str
    attempt: int


def main(argv: list[str] | None = None) -> int:
    configure_utf8_output()
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    max_parallel = _normalize_max_parallel(args.max_parallel)
    records, source = _load_ticker_records(args)
    if args.resume_pipeline_from is not None:
        records = _order_records_for_pipeline_resume(records, args.resume_pipeline_from)
    tickers = [record.ticker for record in records]
    analysis_profile = _resolve_analysis_profile(args)

    if args.limit is not None:
        tickers = tickers[: args.limit]

    if args.resume:
        tickers = _filter_resume_tickers(tickers, args.resume_from)

    selected = set(tickers)
    records = [record for record in records if record.ticker in selected]

    if not tickers:
        raise RuntimeError("no_tickers_to_run")

    if not args.upload_real and not args.routing_plan:
        raise RuntimeError("upload_real_required: batch currently supports real runs only")

    on_date = _resolve_on_date(args.as_of_date)
    adaptive = args.generation_provider == "codex" and not args.legacy_codex
    if adaptive and (args.model or args.reasoning_effort):
        raise RuntimeError("adaptive_models_configured_in_config/codex_analysis.json")
    requested_mode = args.analysis_mode
    if requested_mode == "auto" and not args.routing_plan and not adaptive:
        requested_mode = (
            _consume_one_shot_analysis_mode(
                repo_root,
                on_date=on_date,
                analysis_profile=analysis_profile,
            )
            or "auto"
        )
    if not adaptive and requested_mode == "auto" and batch_day_mode(on_date) == "skip":
        routes = tuple(
            route_ticker(
                record,
                parse_reference_summary(None),
                on_date=on_date,
                requested_mode="auto",
            )
            for record in records
        )
        if args.routing_plan:
            print(json.dumps(_routing_plan_payload(routes, on_date), ensure_ascii=False, indent=2))
        else:
            print(f"SKIPPED batch: {on_date.isoformat()} is Friday/Saturday.")
        return 0
    if adaptive and not args.routing_plan:
        from src.local_runner.adaptive_preflight import check
        from src.local_runner.adaptive_policy import load_policy, require_activation
        policy = load_policy(repo_root)
        require_activation(policy)
        check(repo_root, policy)
    if not args.routing_plan and (
        args.resume_pipeline_from is None
        or _resume_pipeline_requires_prepare(
            args.resume_pipeline_from.expanduser().resolve(),
            tuple(tickers),
        )
    ):
        ensure_gateway(repo_root)
    routes = tuple(
        route_ticker(
            record,
            parse_reference_summary(load_reference_payload(record.ticker)),
            on_date=on_date,
            requested_mode=requested_mode,
            model_override=args.model,
        )
        for record in records
    ) if not adaptive else ()
    if adaptive:
        from src.local_runner.adaptive_policy import routes_for
        routes = routes_for(records, repo_root, requested_mode == "reference",
                            resume_dir=args.resume_pipeline_from.parent if args.resume_pipeline_from else None)
        if args.resume_pipeline_from is not None:
            # Completed ITVs change priority/age. Ranking again would make
            # the same ticker set incompatible with its own checkpoint.
            routes = _order_adaptive_resume_routes(routes, records)

    if args.routing_plan:
        print(json.dumps(_routing_plan_payload(routes, on_date), ensure_ascii=False, indent=2))
        return 0

    runnable_routes = tuple(route for route in routes if route.action == "run")
    if not runnable_routes:
        print(f"SKIPPED batch: {on_date.isoformat()} is Friday/Saturday.")
        return 0

    run_started = _utc_now()
    log_dir = (
        repo_root
        / "logs"
        / "batch"
        / run_started.strftime("%Y-%m-%d")
        / run_started.strftime("%H-%M-%S")
    )
    if args.resume_pipeline_from is not None:
        resume_path = args.resume_pipeline_from.expanduser().resolve()
        if resume_path.name != "pipeline_state.json" or not resume_path.exists():
            raise RuntimeError(f"invalid_pipeline_resume_state: {resume_path}")
        log_dir = resume_path.parent
    (log_dir / "tickers").mkdir(parents=True, exist_ok=True)
    strategy_path = log_dir / "strategy.json"
    strategy = "adaptive-codex-v1" if adaptive else "legacy"
    if args.resume_pipeline_from is not None:
        saved_strategy = _load_json_file(strategy_path).get("strategy", "legacy")
        if saved_strategy != strategy:
            raise RuntimeError("resume_strategy_mismatch_start_new_batch")
    else:
        _write_json(strategy_path, {"strategy": strategy})

    config = BatchConfig(
        repo_root=repo_root,
        tickers=tuple(route.ticker for route in runnable_routes),
        source=source,
        max_parallel=max_parallel,
        retry_failed=args.retry_failed,
        upload_real=args.upload_real,
        log_dir=log_dir,
        update_analysts=_should_update_analysts(args),
        update_ibkr_news=_should_update_ibkr_news(args),
        analysis_profile=analysis_profile,
        routes=runnable_routes,
        model=args.model,
        reasoning_effort=(
            args.reasoning_effort or PROFILE_REASONING_EFFORT[analysis_profile]
        ),
        generation_provider=args.generation_provider,
        chatgpt_browser_headed=args.chatgpt_browser_headed,
        chatgpt_browser_max_attempts=args.chatgpt_browser_max_attempts,
        chatgpt_chat_group_size=args.chatgpt_chat_group_size,
        chatgpt_web_workers=args.chatgpt_web_workers,
        generator_fallback=not args.no_generator_fallback,
        resume_pipeline_from=(
            args.resume_pipeline_from.expanduser().resolve()
            if args.resume_pipeline_from is not None
            else None
        ),
        adaptive_codex=adaptive,
        ownership_context=_batch_ownership_context(records, source) if adaptive else None,
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
    parser.add_argument(
        "--resume-pipeline-from",
        type=Path,
        help=(
            "Resume unfinished ticker stages from a previous "
            "logs/batch/.../pipeline_state.json checkpoint."
        ),
    )
    parser.add_argument(
        "--update-analysts",
        action="store_true",
        help=(
            "Run the non-blocking IBKR analyst update/backfill step before "
            "the ticker analyses."
        ),
    )
    parser.add_argument(
        "--skip-analyst-update",
        action="store_true",
        help=(
            "Skip the automatic analyst update step. For --from-gcs trading "
            "batches the step is enabled by default."
        ),
    )
    parser.add_argument(
        "--update-ibkr-news",
        action="store_true",
        help=(
            "Run the non-blocking IBKR recent-news update step before the "
            "ticker analyses."
        ),
    )
    parser.add_argument(
        "--skip-ibkr-news-update",
        action="store_true",
        help=(
            "Skip the automatic IBKR recent-news update step. For --from-gcs "
            "trading batches the step is enabled by default."
        ),
    )
    parser.add_argument(
        "--analysis-profile",
        choices=("trading", "core"),
        help=(
            "Select the analysis profile. Inferred as core for tickers_core.json; "
            "otherwise trading."
        ),
    )
    parser.add_argument(
        "--model",
        help="Override the automatic model for every ticker (diagnostics only).",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high", "xhigh"),
        help="Override the profile reasoning effort.",
    )
    parser.add_argument(
        "--analysis-mode",
        choices=("auto", "reference", "daily"),
        default="auto",
        help="Automatic calendar routing, or explicitly force reference/daily.",
    )
    parser.add_argument(
        "--as-of-date",
        type=date.fromisoformat,
        help="Override Europe/Madrid date (YYYY-MM-DD), mainly for tests.",
    )
    parser.add_argument(
        "--routing-plan",
        action="store_true",
        help="Print routing decisions without Gateway, model calls, or uploads.",
    )
    parser.add_argument(
        "--generation-provider",
        choices=("codex", "chatgpt-browser"),
        default="codex",
        help="Markdown generator used by every ticker in the batch.",
    )
    parser.add_argument(
        "--chatgpt-browser-headed",
        action="store_true",
        help="Show the dedicated ChatGPT browser during generation.",
    )
    parser.add_argument(
        "--chatgpt-browser-max-attempts",
        type=int,
        default=2,
        help="Fresh ChatGPT requests allowed per ticker.",
    )
    parser.add_argument(
        "--chatgpt-chat-group-size",
        type=int,
        default=5,
        help="Tickers kept in one ChatGPT conversation before rotating it.",
    )
    parser.add_argument(
        "--chatgpt-web-workers",
        type=int,
        default=DEFAULT_CHATGPT_WEB_WORKERS,
        help="Independent ChatGPT Web/Firefox workers. Currently capped at 3.",
    )
    parser.add_argument(
        "--no-generator-fallback",
        action="store_true",
        help="Do not fall back to Codex after ChatGPT browser failure.",
    )
    parser.add_argument("--legacy-codex", action="store_true",
                        help="Explicitly use the former full-report-per-ticker Codex workflow.")

    args = parser.parse_args(argv)

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than 0")

    if args.max_parallel < 1:
        parser.error("--max-parallel must be greater than 0")

    if args.retry_failed < 0:
        parser.error("--retry-failed must be 0 or greater")

    if args.chatgpt_browser_max_attempts < 1:
        parser.error("--chatgpt-browser-max-attempts must be greater than 0")

    if args.chatgpt_chat_group_size < 1:
        parser.error("--chatgpt-chat-group-size must be greater than 0")

    if not 1 <= args.chatgpt_web_workers <= MAX_CHATGPT_WEB_WORKERS:
        parser.error(
            "--chatgpt-web-workers must be between 1 and "
            f"{MAX_CHATGPT_WEB_WORKERS}"
        )

    if args.resume and not args.resume_from:
        parser.error("--resume requires --resume-from")

    if args.resume_from and not args.resume:
        parser.error("--resume-from can only be used with --resume")
    if args.resume_pipeline_from and (args.resume or args.resume_from):
        parser.error(
            "--resume-pipeline-from cannot be combined with --resume/--resume-from"
        )

    if args.update_analysts and args.skip_analyst_update:
        parser.error("--update-analysts and --skip-analyst-update are mutually exclusive")
    if args.update_ibkr_news and args.skip_ibkr_news_update:
        parser.error(
            "--update-ibkr-news and --skip-ibkr-news-update are mutually exclusive"
        )

    return args


def _resolve_analysis_profile(args: argparse.Namespace) -> str:
    if args.analysis_profile:
        return str(args.analysis_profile)
    if args.config_gcs == CORE_TICKERS_GCS_URI:
        return "core"
    return "trading"


def _load_ticker_records(args: argparse.Namespace) -> tuple[list[TickerRecord], str]:
    if args.from_gcs or args.config_gcs:
        source = args.config_gcs or TICKERS_GCS_URI
        raw = _read_gcs_text(source)
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RuntimeError("invalid_tickers_json: expected object")
        from src.local_runner.ownership import recorded_ownership, MARKET_OWNERSHIP_GCS_URI
        market_raw = raw if source == MARKET_OWNERSHIP_GCS_URI else None
        def resolve_unknown(ticker):
            nonlocal market_raw
            if market_raw is None:
                market_raw = _read_gcs_text(MARKET_OWNERSHIP_GCS_URI)
            return recorded_ownership(ticker, lambda uri: market_raw)
        if 'ticker_records' in payload:
            ticker_records = payload['ticker_records']
            if not isinstance(ticker_records, list):
                raise RuntimeError("invalid_tickers_json: ticker_records must be a list")
            return _clean_ticker_records(ticker_records, ownership_resolver=resolve_unknown), source
        tickers = payload.get("tickers")
        if not isinstance(tickers, list):
            raise RuntimeError("invalid_tickers_json: tickers must be a list")
        # A universe selects symbols; list membership does not declare ownership.
        values = [{'ticker': value} for value in _clean_tickers(tickers)]
        return _clean_ticker_records(values, ownership_resolver=resolve_unknown), source

    if getattr(args, 'generation_provider', None) == 'codex' and not getattr(args, 'legacy_codex', False):
        from src.local_runner.ownership import recorded_ownership, MARKET_OWNERSHIP_GCS_URI
        raw = _read_gcs_text(MARKET_OWNERSHIP_GCS_URI)
        records = []
        for ticker in _clean_tickers(str(args.tickers).split(',')):
            owned, evidence = recorded_ownership(ticker, lambda uri: raw)
            records.append(TickerRecord(ticker=ticker, owned=owned,
                                        ownership_source=evidence['source']))
        return records, '--tickers (ownership from market config)'
    return [
        TickerRecord(ticker=value)
        for value in _clean_tickers(str(args.tickers).split(","))
    ], "--tickers"


def _order_records_for_pipeline_resume(
    records: list[TickerRecord], state_path: Path,
) -> list[TickerRecord]:
    stored = _load_json_file(state_path).get("ticker_order", [])
    by_ticker = {record.ticker: record for record in records}
    if not stored or len(stored) != len(set(stored)) or set(stored) != set(by_ticker):
        raise RuntimeError("pipeline_resume_ticker_mismatch: checkpoint ticker set differs")
    return [by_ticker[ticker] for ticker in stored]


def _load_tickers(args: argparse.Namespace) -> tuple[list[str], str]:
    records, source = _load_ticker_records(args)
    return [record.ticker for record in records], source


def _clean_ticker_records(values: list[Any], *, ownership_resolver=None) -> list[TickerRecord]:
    records: list[TickerRecord] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, dict):
            raise RuntimeError('ownership_unavailable: ticker record must be an object')
        ticker = str(value.get("ticker") or "").strip().upper()
        if not ticker or ticker in seen:
            raise RuntimeError('ownership_unavailable: explicit unique ticker record required: ' + ticker)
        seen.add(ticker)
        ownership_source = str(value.get('ownership_source') or '').strip() or None
        owned = value.get('owned')
        if type(owned) is not bool:
            if ownership_resolver is None:
                raise RuntimeError('ownership_unavailable: explicit boolean or Mercado authority required for ' + ticker)
            owned, evidence = ownership_resolver(ticker)
            if type(owned) is not bool or not isinstance(evidence, dict) or not evidence.get('source'):
                raise RuntimeError('ownership_unavailable: invalid Mercado authority for ' + ticker)
            # Do not retain an unverified source label from the incomplete row.
            ownership_source = evidence['source']
        records.append(TickerRecord(ticker=ticker, owned=owned, ownership_source=ownership_source))
    return records


def _batch_ownership_context(records: list[TickerRecord], source: str) -> dict[str, dict[str, Any]]:
    # Preserve selection and recorded/resolved provenance separately. A row label
    # is not proof that an external holdings source was independently verified.
    return {record.ticker: {
        'symbol': record.ticker, 'owned': record.owned, 'selection_source': source,
        'ownership_source': record.ownership_source,
    } for record in records}


def _should_update_analysts(args: argparse.Namespace) -> bool:
    if args.skip_analyst_update:
        return False
    if args.update_analysts:
        return True
    return bool(args.from_gcs)


def _should_update_ibkr_news(args: argparse.Namespace) -> bool:
    if args.skip_ibkr_news_update:
        return False
    if args.update_ibkr_news:
        return True
    return bool(args.from_gcs)


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


def _order_adaptive_resume_routes(routes, records):
    by_ticker = {route.ticker: route for route in routes}
    if len(by_ticker) != len(routes) or set(by_ticker) != {record.ticker for record in records}:
        raise RuntimeError("pipeline_resume_ticker_mismatch: adaptive route set differs")
    # records has already passed _order_records_for_pipeline_resume.
    return tuple(by_ticker[record.ticker] for record in records)


def _resolve_on_date(value: date | None) -> date:
    return value or datetime.now(MADRID_TZ).date()


def _resume_pipeline_requires_prepare(
    state_path: Path,
    tickers: tuple[str, ...],
) -> bool:
    """Only require live source services when a resumed ticker needs preparation."""

    state = _load_json_file(state_path)
    ticker_states = state.get("tickers")
    if not isinstance(ticker_states, dict):
        return True
    for ticker in tickers:
        item = ticker_states.get(ticker)
        if not isinstance(item, dict):
            return True
        attempt = str(max(1, int(item.get("current_attempt") or 1)))
        attempts = item.get("attempts")
        if not isinstance(attempts, dict):
            return True
        attempt_state = attempts.get(attempt)
        stages = attempt_state.get("stages") if isinstance(attempt_state, dict) else None
        if not isinstance(stages, dict):
            return True
        if stages.get("prepare", {}).get("status") != "ok":
            return True
    return False


def _consume_one_shot_analysis_mode(
    repo_root: Path,
    *,
    on_date: date,
    analysis_profile: str,
) -> str | None:
    marker_path = repo_root / ".local" / "analysis_mode_once.json"
    if not marker_path.exists():
        return None
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid_one_shot_analysis_mode: {marker_path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("invalid_one_shot_analysis_mode: expected object")
    mode = str(payload.get("analysis_mode") or "")
    expires_on = str(payload.get("expires_on") or "")
    profile = str(payload.get("profile") or "")
    if mode not in {"reference", "daily"}:
        raise RuntimeError(f"invalid_one_shot_analysis_mode: mode={mode!r}")
    if expires_on != on_date.isoformat():
        raise RuntimeError(
            "one_shot_analysis_mode_wrong_date: "
            f"expected={on_date.isoformat()} found={expires_on!r}"
        )
    if profile != analysis_profile:
        return None
    marker_path.unlink()
    print(
        "ONE-SHOT override consumed: "
        f"profile={analysis_profile}, mode={mode}, date={on_date.isoformat()}."
    )
    return mode


def _routing_plan_payload(
    routes: tuple[RouteDecision, ...], on_date: date
) -> dict[str, Any]:
    return {
        "as_of_date": on_date.isoformat(),
        "routes": [
            {
                "ticker": route.ticker,
                "owned": route.owned,
                "tier": route.tier,
                "action": route.action,
                "analysis_kind": route.analysis_kind,
                "model": route.model,
                "reviewer_model": route.reviewer_model,
                "reason": route.reason,
            }
            for route in routes
        ],
    }


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


class _PipelineTracker:
    """Thread-safe durable checkpoints for a staged batch."""

    def __init__(
        self,
        path: Path,
        *,
        tickers: tuple[str, ...],
        source: str,
        started_at: datetime,
        resume: bool,
    ) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._resume = resume
        loaded = _load_json_file(path) if resume else {}
        if loaded:
            stored = tuple(str(item) for item in loaded.get("ticker_order", []))
            if stored and stored != tickers:
                raise RuntimeError(
                    "pipeline_resume_ticker_mismatch: checkpoint ticker order differs"
                )
            self._state = loaded
            if loaded.get("status") == "failed" or loaded.get("fatal_error"):
                loaded.setdefault("failure_history", []).append({
                    "finished_at": loaded.get("finished_at"),
                    "fatal_error": loaded.get("fatal_error"),
                    "resumed_at": started_at.isoformat(),
                })
                loaded["status"] = "running"
                loaded.pop("fatal_error", None)
                loaded.pop("finished_at", None)
                loaded["updated_at"] = started_at.isoformat()
        else:
            self._state = {
                "version": PIPELINE_STATE_VERSION,
                "started_at": started_at.isoformat(),
                "updated_at": started_at.isoformat(),
                "source": source,
                "ticker_order": list(tickers),
                "tickers": {},
            }
        for ticker in tickers:
            self._state.setdefault("tickers", {}).setdefault(
                ticker,
                {"status": "queued", "current_attempt": 1, "attempts": {}},
            )
        self._write_locked()

    def attempt_for(self, ticker: str, requested: int | None) -> int:
        if requested is not None:
            return requested
        with self._lock:
            item = self._state["tickers"].get(ticker, {})
            current_attempt = max(1, int(item.get("current_attempt") or 1))
            if self._resume and item.get("status") == "failed":
                return current_attempt + 1
            return current_attempt

    def next_stage(self, ticker: str, attempt: int) -> str | None:
        with self._lock:
            item = self._state["tickers"].get(ticker, {})
            attempt_state = item.get("attempts", {}).get(str(attempt), {})
            stages = attempt_state.get("stages", {})
            if stages.get("publish", {}).get("status") == "ok":
                return None
            if stages.get("analyze", {}).get("status") == "ok":
                return "publish"
            if stages.get("prepare", {}).get("status") == "ok":
                return "analyze"
            return "prepare"

    def stage_started(self, task: PipelineTask, stage: str) -> None:
        self._update_stage(
            task,
            stage,
            {"status": "running", "started_at": _utc_now().isoformat()},
            ticker_status=stage,
        )

    def stage_finished(
        self,
        task: PipelineTask,
        stage: str,
        result: dict[str, Any],
    ) -> None:
        payload = {
            "status": result.get("status", "failed"),
            "started_at": result.get("started_at"),
            "finished_at": result.get("finished_at"),
            "duration_seconds": result.get("duration_seconds"),
            "exit_code": result.get("exit_code"),
            "error_type": result.get("error_type"),
            "error_message": result.get("error_message"),
            "generation_provider": result.get("generation_provider"),
            "web_worker_id": result.get("web_worker_id"),
            "web_attempt_count": result.get("web_attempt_count"),
            "web_retry_count": result.get("web_retry_count"),
            "web_timing_seconds": result.get("web_timing_seconds"),
            "adaptive_review": result.get("adaptive_review"),
        }
        ticker_status = stage if result.get("status") == "ok" else "failed"
        if stage == "publish" and result.get("status") == "ok":
            ticker_status = "ok"
        self._update_stage(task, stage, payload, ticker_status=ticker_status)

    def mark_terminal(self, task: PipelineTask, status: str) -> None:
        with self._lock:
            item = self._state["tickers"][task.ticker]
            item["status"] = status
            item["current_attempt"] = task.attempt
            item["finished_at"] = _utc_now().isoformat()
            self._touch_and_write_locked()

    def mark_batch_failed(self, error: BaseException) -> None:
        with self._lock:
            self._state["status"] = "failed"
            self._state["finished_at"] = _utc_now().isoformat()
            self._state["fatal_error"] = {
                "type": type(error).__name__,
                "message": str(error),
            }
            self._touch_and_write_locked()

    def _update_stage(
        self,
        task: PipelineTask,
        stage: str,
        payload: dict[str, Any],
        *,
        ticker_status: str,
    ) -> None:
        with self._lock:
            item = self._state["tickers"][task.ticker]
            item["status"] = ticker_status
            item["current_attempt"] = task.attempt
            attempt_state = item.setdefault("attempts", {}).setdefault(
                str(task.attempt), {"stages": {}}
            )
            attempt_state.setdefault("stages", {})[stage] = payload
            self._touch_and_write_locked()

    def _touch_and_write_locked(self) -> None:
        self._state["updated_at"] = _utc_now().isoformat()
        self._write_locked()

    def _write_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _replace_pipeline_state_with_retry(temporary, self.path)


def _replace_pipeline_state_with_retry(
    temporary: Path,
    destination: Path,
    *,
    timeout_seconds: float = PIPELINE_STATE_REPLACE_TIMEOUT_SECONDS,
    retry_interval_seconds: float = PIPELINE_STATE_REPLACE_RETRY_INTERVAL_SECONDS,
) -> None:
    """Replace a checkpoint after transient Windows readers release it."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            temporary.replace(destination)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(retry_interval_seconds)


class _BatchProgressPublisher:
    """Publish a throttled live view of pipeline_state.json for Google Sheets."""

    def __init__(
        self,
        config: BatchConfig,
        state_path: Path,
        browser_session: BrowserSession | None = None,
    ) -> None:
        self.config = config
        self.state_path = state_path
        self.local_path = config.log_dir / "sheet_progress.json"
        self.destination = os.environ.get("ANALYSIS_PROGRESS_GCS_URI", "").strip()
        self.latest_destination = _latest_progress_destination(self.destination)
        self.command_id = os.environ.get("ANALYSIS_COMMAND_ID", "").strip()
        self.command_action = os.environ.get("ANALYSIS_COMMAND_ACTION", "").strip()
        self.browser_session = browser_session
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._reported_stalls: set[tuple[int, str, int, str]] = set()

    def start(self) -> None:
        self._publish_once()
        if not self.destination:
            return
        self._thread = threading.Thread(
            target=self._run,
            name="batch-progress-publisher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=PROGRESS_HEARTBEAT_SECONDS + 65)
        self._publish_once()

    def _run(self) -> None:
        while not self._stop.wait(PROGRESS_HEARTBEAT_SECONDS):
            self._publish_once()

    def _publish_once(self) -> None:
        state = _load_json_file(self.state_path)
        if not state:
            return
        payload = _pipeline_progress_payload(
            state,
            command_id=self.command_id,
            command_action=self.command_action,
            generation_provider=self.config.generation_provider,
            result_dir=self.config.log_dir / "tickers",
            browser_status=(
                self.browser_session.progress_status()
                if self.browser_session is not None
                else None
            ),
        )
        _write_json(self.local_path, payload)
        _write_json(
            self.config.log_dir / "ticker_timings.json",
            {
                "generated_at": payload["heartbeat_at"],
                "command_id": self.command_id,
                "tickers": payload.get("ticker_timings", {}),
            },
        )
        self._record_stall_if_needed(payload)
        if not self.destination:
            return
        # C4 reads latest.json. Publish that heartbeat first, so a slow
        # per-command archive cannot make a healthy batch look disconnected.
        destinations = [self.latest_destination or self.destination]
        if self.latest_destination and self.latest_destination != self.destination:
            destinations.append(self.destination)
        for destination in destinations:
            try:
                completed = run_bounded(
                    [
                        require_gcloud(),
                        "storage",
                        "cp",
                        "--content-type=application/json",
                        str(self.local_path),
                        destination,
                    ],
                    cwd=str(self.config.repo_root),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=25,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                    ),
                )
                if completed.returncode != 0:
                    print(
                        "WARNING: live batch progress upload failed: "
                        f"exit_code={completed.returncode}",
                        flush=True,
                    )
                    if destination == self.latest_destination:
                        break
            except (OSError, subprocess.SubprocessError) as exc:
                print(f"WARNING: live batch progress upload failed: {exc}", flush=True)
                if destination == self.latest_destination:
                    break

    def _record_stall_if_needed(self, payload: dict[str, Any]) -> None:
        web = payload.get("chatgpt_web", {})
        if not isinstance(web, dict):
            return
        workers = web.get("workers")
        worker_states = (
            [item for item in workers if isinstance(item, dict)]
            if isinstance(workers, list)
            else [web]
        )
        for worker in worker_states:
            if not worker.get("active_stage_stalled"):
                continue
            worker_id = int(worker.get("worker_id") or 1)
            ticker = str(worker.get("active_ticker") or "")
            attempt = int(worker.get("active_attempt") or 0)
            stage = str(worker.get("active_stage") or "")
            key = (worker_id, ticker, attempt, stage)
            if not ticker or not stage or key in self._reported_stalls:
                continue
            self._reported_stalls.add(key)
            event = {
                "detected_at": payload.get("heartbeat_at"),
                "web_worker_id": worker_id,
                "ticker": ticker,
                "attempt": attempt,
                "stage": stage,
                "elapsed_seconds": worker.get("active_stage_elapsed_seconds"),
                "threshold_seconds": worker.get(
                    "active_stage_stall_threshold_seconds"
                ),
                "waiting_tickers": web.get("waiting_tickers", []),
            }
            path = self.config.log_dir / "stall_events.jsonl"
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=True) + "\n")
            print(
                "WARNING: possible Web stall: "
                f"worker={worker_id} ticker={ticker} attempt={attempt} "
                f"stage={stage} elapsed={event['elapsed_seconds']}s",
                flush=True,
            )


def _latest_progress_destination(destination: str) -> str:
    marker = "/commands/progress/"
    if marker not in destination or not destination.endswith(".json"):
        return ""
    prefix, _ = destination.rsplit(marker, 1)
    return f"{prefix}{marker}latest.json"


def _pipeline_progress_payload(
    state: dict[str, Any],
    *,
    command_id: str,
    command_action: str,
    generation_provider: str,
    browser_status: dict[str, Any] | None = None,
    result_dir: Path | None = None,
) -> dict[str, Any]:
    ticker_order = [str(item) for item in state.get("ticker_order", [])]
    ticker_states = state.get("tickers", {})
    if not isinstance(ticker_states, dict):
        ticker_states = {}

    counts = {
        "prepared": 0,
        "generated": 0,
        "validated": 0,
        "published": 0,
        "failed": 0,
        "pipeline_retries": 0,
        "chatgpt_web_retries": 0,
        "retries": 0,
        "retained_reports": 0,
        "updated_reports": 0,
        "regenerated_reports": 0,
    }
    active: dict[str, list[str]] = {"prepare": [], "analyze": [], "publish": []}
    failed_tickers: list[str] = []
    generation_providers = {
        "chatgpt-browser": 0,
        "codex": 0,
        "unknown": 0,
    }
    fallback_tickers: list[str] = []
    analysis_outcomes: dict[str, list[str]] = {
        "retained": [], "updated": [], "regenerated": [],
    }

    for ticker in ticker_order:
        item = ticker_states.get(ticker, {})
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "queued")
        if status == "failed":
            counts["failed"] += 1
            failed_tickers.append(ticker)
        attempts = item.get("attempts", {})
        if not isinstance(attempts, dict):
            attempts = {}
        counts["pipeline_retries"] += max(0, len(attempts) - 1)
        for pipeline_attempt in attempts.values():
            if not isinstance(pipeline_attempt, dict):
                continue
            pipeline_stages = pipeline_attempt.get("stages", {})
            if not isinstance(pipeline_stages, dict):
                continue
            analyze_stage = pipeline_stages.get("analyze", {})
            if isinstance(analyze_stage, dict):
                counts["chatgpt_web_retries"] += max(
                    0, int(analyze_stage.get("web_retry_count") or 0)
                )
        current_attempt = str(max(1, int(item.get("current_attempt") or 1)))
        attempt = attempts.get(current_attempt, {})
        stages = attempt.get("stages", {}) if isinstance(attempt, dict) else {}
        if not isinstance(stages, dict):
            stages = {}
        for phase in active:
            if stages.get(phase, {}).get("status") == "running":
                active[phase].append(ticker)
        prepare_ok = stages.get("prepare", {}).get("status") == "ok"
        analyze_ok = stages.get("analyze", {}).get("status") == "ok"
        publish_ok = stages.get("publish", {}).get("status") == "ok"
        counts["prepared"] += int(prepare_ok)
        counts["generated"] += int(analyze_ok)
        counts["validated"] += int(analyze_ok)
        counts["published"] += int(publish_ok)
        if analyze_ok:
            adaptive_review = stages.get("analyze", {}).get("adaptive_review") or {}
            provider_used = str(adaptive_review.get("generation_provider") or "")
            if result_dir is not None:
                result = _load_json_file(result_dir / f"{ticker}.json")
                workflow = result.get("analysis_workflow")
                if isinstance(workflow, dict):
                    provider_used = str(workflow.get("generation_provider") or "")
                    if not adaptive_review:
                        adaptive_review = workflow
            counts["retained_reports"] += int(publish_ok and adaptive_review.get("status") == "retained")
            counts["updated_reports"] += int(publish_ok and adaptive_review.get("status") == "updated")
            counts["regenerated_reports"] += int(publish_ok and adaptive_review.get("status") == "regenerated")
            outcome = adaptive_review.get("status")
            if outcome in analysis_outcomes:
                analysis_outcomes[outcome].append(ticker)
            provider_key = (
                provider_used
                if provider_used in {"chatgpt-browser", "codex"}
                else "unknown"
            )
            generation_providers[provider_key] += 1
            if provider_key == "codex" and generation_provider == "chatgpt-browser":
                fallback_tickers.append(ticker)

    web_status = browser_status if isinstance(browser_status, dict) else {}
    web_workers = web_status.get("workers")
    if not isinstance(web_workers, list) or not web_workers:
        web_workers = [web_status]
    counts["chatgpt_web_retries"] += sum(
        max(0, int(worker.get("active_attempt") or 1) - 1)
        for worker in web_workers
        if isinstance(worker, dict) and worker.get("active_ticker")
    )
    counts["retries"] = (
        counts["pipeline_retries"] + counts["chatgpt_web_retries"]
    )

    total = len(ticker_order)
    completed = counts["published"] + counts["failed"]
    progress_status = str(state.get("status") or "running")
    if progress_status != "failed" and total > 0 and completed >= total:
        progress_status = "failed" if counts["failed"] else "completed"
    now = _utc_now()
    started_at = _parse_iso_datetime(state.get("started_at")) or now
    elapsed_seconds = max(0.0, (now - started_at).total_seconds())
    eta_seconds: float | None = None
    if completed > 0 and completed < total:
        eta_seconds = elapsed_seconds * (total - completed) / completed
    current_phase = next(
        (phase for phase in ("analyze", "publish", "prepare") if active[phase]),
        "queued",
    )
    current_ticker = (
        active[current_phase][0] if current_phase in active and active[current_phase] else ""
    )

    ticker_timings = _ticker_timing_summary(
        ticker_order,
        ticker_states,
        now=now,
    )
    return {
        "schema_version": 1,
        "command_id": command_id,
        "action": command_action,
        "status": progress_status,
        "heartbeat_at": now.isoformat(),
        "started_at": started_at.isoformat(),
        "updated_at": state.get("updated_at"),
        "total": total,
        "completed": completed,
        "percent_complete": round((completed / total * 100) if total else 0, 1),
        "counts": counts,
        "analysis_outcomes": {
            outcome: {"count": len(tickers), "tickers": tickers}
            for outcome, tickers in analysis_outcomes.items()
        },
        "current": {
            "phase": current_phase,
            "ticker": current_ticker,
            "preparing": active["prepare"],
            "analyzing": active["analyze"],
            "publishing": active["publish"],
        },
        "provider": generation_provider,
        "generation_providers": generation_providers,
        "fallback_tickers": fallback_tickers,
        "chatgpt_web": dict(browser_status or {}),
        "ticker_timings": ticker_timings,
        "web_timing": _web_timing_rollup(ticker_timings),
        "failed_tickers": failed_tickers,
        "fatal_error": state.get("fatal_error"),
        "elapsed_seconds": round(elapsed_seconds, 1),
        "eta_seconds": round(eta_seconds, 1) if eta_seconds is not None else None,
    }


def _ticker_timing_summary(
    ticker_order: list[str],
    ticker_states: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for ticker in ticker_order:
        item = ticker_states.get(ticker, {})
        if not isinstance(item, dict):
            continue
        attempts = item.get("attempts", {})
        if not isinstance(attempts, dict):
            attempts = {}
        attempt_summaries: dict[str, Any] = {}
        ticker_total = 0.0
        for attempt_number, attempt in attempts.items():
            stages = attempt.get("stages", {}) if isinstance(attempt, dict) else {}
            if not isinstance(stages, dict):
                stages = {}
            stage_durations: dict[str, float] = {}
            for stage_name in ("prepare", "analyze", "publish"):
                stage = stages.get(stage_name, {})
                if not isinstance(stage, dict):
                    continue
                duration = stage.get("duration_seconds")
                if duration is None and stage.get("status") == "running":
                    started = _parse_iso_datetime(stage.get("started_at"))
                    if started is not None:
                        duration = max(0.0, (now - started).total_seconds())
                if duration is not None:
                    stage_durations[stage_name] = round(float(duration), 1)
            attempt_total = round(sum(stage_durations.values()), 1)
            ticker_total += attempt_total
            attempt_summary = {
                "stages_seconds": stage_durations,
                "total_seconds": attempt_total,
            }
            analyze_stage = stages.get("analyze", {})
            if isinstance(analyze_stage, dict):
                web_worker_id = analyze_stage.get("web_worker_id")
                if web_worker_id is not None:
                    attempt_summary["web_worker_id"] = int(web_worker_id)
                raw_web_timing = analyze_stage.get("web_timing_seconds")
                if isinstance(raw_web_timing, dict):
                    attempt_summary["web_timing_seconds"] = {
                        key: round(float(raw_web_timing.get(key) or 0.0), 1)
                        for key in (
                            "queue_wait_seconds",
                            "execution_seconds",
                            "non_web_seconds",
                        )
                    }
            attempt_summaries[str(attempt_number)] = attempt_summary
        summary[ticker] = {
            "status": str(item.get("status") or "queued"),
            "current_attempt": max(1, int(item.get("current_attempt") or 1)),
            "attempt_count": len(attempts),
            "total_seconds": round(ticker_total, 1),
            "attempts": attempt_summaries,
        }
    return summary


def _web_timing_rollup(
    ticker_timings: dict[str, dict[str, Any]],
) -> dict[str, float | int]:
    samples: list[dict[str, Any]] = []
    for ticker in ticker_timings.values():
        for attempt in ticker.get("attempts", {}).values():
            timing = attempt.get("web_timing_seconds")
            if isinstance(timing, dict):
                samples.append(timing)
    totals = {
        key: round(sum(float(sample.get(key) or 0.0) for sample in samples), 1)
        for key in ("queue_wait_seconds", "execution_seconds", "non_web_seconds")
    }
    count = len(samples)
    return {
        "completed_attempts": count,
        **{f"total_{key}": value for key, value in totals.items()},
        **{
            f"average_{key}": round(value / count, 1) if count else 0.0
            for key, value in totals.items()
        },
    }


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class _SourceProgressGate:
    def __init__(
        self,
        progress_dir: Path,
        future: concurrent.futures.Future[dict[str, Any]],
    ) -> None:
        self.progress_dir = progress_dir
        self.future = future

    def wait(self, ticker: str) -> None:
        marker = self.progress_dir / f"{ticker}.json"
        while not marker.exists():
            if self.future.done():
                raise RuntimeError(f"source_update_missing_marker: {ticker}")
            time.sleep(0.2)
        payload = _load_json_file(marker)
        if payload.get("status") != "ok":
            raise RuntimeError(
                str(payload.get("error") or f"source_update_failed: {ticker}")
            )


def _run_batch(config: BatchConfig, run_started: datetime) -> int:
    browser_session: BrowserSession | None = None
    if config.generation_provider == "chatgpt-browser":
        web_workers = min(
            config.chatgpt_web_workers,
            config.max_parallel,
            len(config.tickers),
        )
        if web_workers > 1:
            browser_session = ChatGPTBrowserSessionPool(
                config.repo_root,
                worker_count=web_workers,
                headed=config.chatgpt_browser_headed,
                chat_group_size=config.chatgpt_chat_group_size,
            )
        else:
            browser_session = ChatGPTBrowserSession(
                config.repo_root,
                headed=config.chatgpt_browser_headed,
                chat_group_size=config.chatgpt_chat_group_size,
            )
    if browser_session is not None:
        atexit.register(browser_session.close)
    if config.resume_pipeline_from is not None and not config.adaptive_codex:
        _reconcile_pipeline_checkpoint_from_artifacts(config)
    tracker = _PipelineTracker(
        config.log_dir / "pipeline_state.json",
        tickers=config.tickers,
        source=config.source,
        started_at=run_started,
        resume=config.resume_pipeline_from is not None,
    )
    progress_publisher = _BatchProgressPublisher(
        config,
        tracker.path,
        browser_session,
    )
    progress_publisher.start()
    preflight = getattr(browser_session, "preflight", None)
    if callable(preflight):
        try:
            preflight()
        except BaseException as exc:
            tracker.mark_batch_failed(exc)
            progress_publisher.stop()
            if browser_session is not None:
                browser_session.close()
                atexit.unregister(browser_session.close)
            raise
    source_executor: concurrent.futures.ThreadPoolExecutor | None = None
    source_future: concurrent.futures.Future[dict[str, Any]] | None = None
    preparation_gate: _SourceProgressGate | None = None
    if config.resume_pipeline_from is not None:
        source_update = _load_json_file(config.log_dir / "source_update.json")
    else:
        source_update = {}
    if (config.update_analysts or config.update_ibkr_news) and source_update.get(
        "status"
    ) != "ok":
        progress_dir = config.log_dir / "source_progress"
        progress_dir.mkdir(parents=True, exist_ok=True)
        _discard_failed_source_markers(progress_dir, config.tickers)
        source_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="source-refresh",
        )
        source_future = source_executor.submit(
            _run_source_update,
            config,
            progress_dir,
        )
        preparation_gate = _SourceProgressGate(progress_dir, source_future)
        source_update = {"status": "running"}
    analyst_update = dict(source_update)
    ibkr_news_update = dict(source_update)
    if not config.update_analysts:
        analyst_update = {"status": "skipped", "reason": "disabled"}
    if not config.update_ibkr_news:
        ibkr_news_update = {"status": "skipped", "reason": "disabled"}
    if config.resume_pipeline_from is not None and not config.adaptive_codex:
        _reconcile_resumed_web_escalations(config)
    try:
        results = _run_ticker_pass(
            config,
            config.tickers,
            attempt=None if config.resume_pipeline_from is not None else 1,
            tracker=tracker,
            preparation_gate=preparation_gate,
            browser_session=browser_session,
        )
    finally:
        if source_future is not None:
            source_update = source_future.result()
            if config.update_analysts:
                analyst_update = dict(source_update)
            if config.update_ibkr_news:
                ibkr_news_update = dict(source_update)
        if source_executor is not None:
            source_executor.shutdown(wait=True, cancel_futures=False)

    for retry_index in range(1, config.retry_failed + 1):
        failed_tickers = tuple(
            str(result["ticker"])
            for result in results
            if result.get("status") != "ok"
        )

        if not failed_tickers:
            break

        _print_retry(retry_index, config.retry_failed, failed_tickers)
        next_attempts = {
            str(result["ticker"]): int(result.get("attempt") or 1) + 1
            for result in results
            if str(result["ticker"]) in failed_tickers
        }
        retry_results = _run_ticker_pass(
            config,
            failed_tickers,
            attempt=next_attempts,
            tracker=tracker,
            preparation_gate=preparation_gate,
            browser_session=browser_session,
        )
        results = _merge_retry_results(results, retry_results)

    if not config.adaptive_codex:
        results = _run_escalation_reviews(
            config, results, browser_session=browser_session,
        )
    if browser_session is not None:
        browser_session.close()
        atexit.unregister(browser_session.close)

    summary = _build_summary(
        config,
        run_started,
        results,
        analyst_update,
        ibkr_news_update,
    )
    if config.adaptive_codex:
        workflows = [r.get("analysis_workflow", {}) for r in results]
        summary["strategy"] = "adaptive-codex-v1"
        summary.update(_adaptive_report_counts(results))
        summary["codex_budget"] = _load_json_file(config.log_dir / "codex_budget.json")
        calls = list(summary["codex_budget"].get("calls", {}).values())
        calls.extend(call for history in summary["codex_budget"].get("failed_call_history", {}).values() for call in history)
        summary["measured_model_usage"] = _measured_adaptive_usage(calls)
        summary["model_admissions_not_started"] = sum(call.get("no_model_started") is True for call in calls)
        summary["reused_luna_verdicts"] = sum(
            bool(receipt.get("cache_reused")) for workflow in workflows
            for receipt in workflow.get("receipts", []))
        summary["codex_fallback_tickers"] = []
        summary["generation_fallback"] = {"used": False, "count": 0, "tickers": []}
        successful = [r["ticker"] for r in results if r.get("status") == "ok"]
        summary["generation_providers"] = {
            "codex": {"count": len(successful), "tickers": successful},
            "chatgpt-browser": {"count": 0, "tickers": []},
            "unknown": {"count": 0, "tickers": []},
        }
    summary_path = config.log_dir / "summary.json"
    _write_json(summary_path, summary)
    _publish_latest_batch_summary(config, summary_path)
    _print_summary(summary)
    progress_publisher.stop()

    return 0 if summary["failed"] == 0 else 1


def _reconcile_resumed_web_escalations(config: BatchConfig) -> None:
    """Publish valid Web candidates left pending by the former review policy."""

    for ticker in config.tickers:
        result_path = config.log_dir / "tickers" / f"{ticker}.json"
        result = _load_json_file(result_path)
        workflow = result.get("analysis_workflow")
        if (
            result.get("status") != "ok"
            or not isinstance(workflow, dict)
            or workflow.get("status") != "escalation_required"
            or _latest_generation_provider(config.repo_root, ticker)
            != "chatgpt-browser"
        ):
            continue

        route = _route_for(config, ticker)
        print(
            f"RESUME PROMOTE {ticker}: valid Web Sol candidate; "
            "no equivalent model review required.",
            flush=True,
        )
        status = _finalize_one(
            config.repo_root,
            ticker,
            model=str(route.model),
            reasoning_effort=config.reasoning_effort,
            execution_context="batch",
            analysis_kind=str(route.analysis_kind),
            reference_tier=route.tier,
            owned=route.owned,
            generation_provider=config.generation_provider,
            validate_first=False,
        )
        if status != 0:
            print(
                f"WARNING: resume promotion failed for {ticker}; "
                "the pending review remains visible.",
                flush=True,
            )
            continue

        result["analysis_workflow"] = _analysis_workflow(
            config.repo_root,
            ticker,
        )
        result["resume_reconciliation"] = {
            "status": "promoted_without_model_retry",
            "provider": "chatgpt-browser",
            "finished_at": _utc_now().isoformat(),
        }
        _write_json(result_path, result)


def _reconcile_pipeline_checkpoint_from_artifacts(config: BatchConfig) -> None:
    """Promote stages that finished after their checkpoint stopped advancing."""

    state_path = config.resume_pipeline_from
    if state_path is None:
        return
    state = _load_json_file(state_path)
    ticker_states = state.get("tickers")
    if not isinstance(ticker_states, dict):
        return

    recovered: list[str] = []
    for ticker in config.tickers:
        item = ticker_states.get(ticker)
        if not isinstance(item, dict):
            continue
        attempt_number = max(1, int(item.get("current_attempt") or 1))
        attempts = item.get("attempts")
        attempt_state = (
            attempts.get(str(attempt_number))
            if isinstance(attempts, dict)
            else None
        )
        stages = (
            attempt_state.get("stages")
            if isinstance(attempt_state, dict)
            else None
        )
        if not isinstance(stages, dict):
            continue

        analyze = stages.get("analyze")
        if isinstance(analyze, dict) and analyze.get("status") != "ok":
            result = _recover_analyze_stage_from_artifacts(
                config,
                ticker,
                attempt_number,
                analyze,
            )
            if result is not None:
                stages["analyze"] = result
                item["status"] = "analyze"
                recovered.append(f"{ticker}:analyze")

        publish = stages.get("publish")
        if isinstance(publish, dict) and publish.get("status") != "ok":
            result = _recover_publish_stage_from_artifacts(
                config,
                ticker,
                attempt_number,
                publish,
            )
            if result is not None:
                stages["publish"] = result
                item["status"] = "ok"
                item["finished_at"] = result["finished_at"]
                recovered.append(f"{ticker}:publish")

    if not recovered:
        return
    state["updated_at"] = _utc_now().isoformat()
    _write_json(state_path, state)
    print(
        "RESUME RECOVERY: promoted completed artifacts: "
        + ", ".join(recovered),
        flush=True,
    )


def _recover_analyze_stage_from_artifacts(
    config: BatchConfig,
    ticker: str,
    attempt: int,
    checkpoint: dict[str, Any],
) -> dict[str, Any] | None:
    stage_started = _parse_iso_datetime(checkpoint.get("started_at"))
    metadata = _load_generation_metadata(config.repo_root, ticker)
    latest = _load_latest_json(config.repo_root, ticker)
    metadata_finished = _parse_iso_datetime(metadata.get("finished_at"))
    latest_generated = _parse_iso_datetime(latest.get("generated_at"))
    if (
        stage_started is None
        or metadata_finished is None
        or metadata_finished < stage_started
        or latest_generated is None
        or latest_generated < stage_started
        or str(metadata.get("status") or "").casefold()
        not in {"ok", "ok_fallback"}
        or latest.get("analysis_status") != "ok"
    ):
        return None

    result: dict[str, Any] = {
        "ticker": ticker,
        "attempt": attempt,
        "stage": "analyze",
        "status": "ok",
        "exit_code": 0,
        "started_at": checkpoint.get("started_at"),
        "finished_at": metadata_finished.isoformat(),
        "duration_seconds": round(
            (metadata_finished - stage_started).total_seconds(), 3
        ),
        "recovered_from_artifacts": True,
    }
    _add_generation_details_to_stage_result(result, metadata)
    return result


def _recover_publish_stage_from_artifacts(
    config: BatchConfig,
    ticker: str,
    attempt: int,
    checkpoint: dict[str, Any],
) -> dict[str, Any] | None:
    stage_started = _parse_iso_datetime(checkpoint.get("started_at"))
    if stage_started is None:
        return None
    log_dir = config.repo_root / "logs" / ticker
    for path in sorted(
        log_dir.glob("*.run_full.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        payload = _load_json_file(path)
        run_started = _parse_iso_datetime(payload.get("started_at"))
        run_finished = _parse_iso_datetime(payload.get("finished_at"))
        if run_started is None or run_finished is None:
            continue
        if run_started < stage_started or payload.get("status") != "ok":
            continue
        return {
            "ticker": ticker,
            "attempt": attempt,
            "stage": "publish",
            "status": "ok",
            "exit_code": 0,
            "started_at": checkpoint.get("started_at"),
            "finished_at": run_finished.isoformat(),
            "duration_seconds": round(
                (run_finished - stage_started).total_seconds(), 3
            ),
            "recovered_from_artifacts": True,
            "run_log": str(path),
        }
    return None


def _discard_failed_source_markers(
    progress_dir: Path,
    tickers: tuple[str, ...],
) -> None:
    for ticker in tickers:
        marker = progress_dir / f"{ticker}.json"
        if marker.exists() and _load_json_file(marker).get("status") != "ok":
            marker.unlink()


def _run_deferred_chat_cleanup(config: BatchConfig) -> None:
    """Compatibility hook: analysis chats are retained in the Analisis project."""
    return


def _publish_latest_batch_summary(config: BatchConfig, summary_path: Path) -> None:
    """Publish compact batch metadata for the Sheet update note."""
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    mirror_path = summary_path.with_name("sheet_status.json")
    _write_json(
        mirror_path,
        {
            "schema_version": 1,
            "analysis_profile": config.analysis_profile,
            "finished_at": summary["finished_at"],
            "success": summary["success"],
            "failed": summary["failed"],
            "model_usage": summary.get("model_usage", {}),
            "generation_fallback": summary.get(
                "generation_fallback",
                {"used": False, "count": 0, "tickers": []},
            ),
        },
    )
    destinations = (
        (
            summary_path,
            f"{BATCH_STATUS_GCS_PREFIX}/latest_{config.analysis_profile}.json",
        ),
        (
            mirror_path,
            f"{SHEET_STATUS_MIRROR_GCS_PREFIX}/latest_{config.analysis_profile}.json",
        ),
    )
    for source, destination in destinations:
        try:
            completed = subprocess.run(
                [
                    require_gcloud(),
                    "storage",
                    "cp",
                    "--content-type=application/json",
                    str(source),
                    destination,
                ],
                cwd=str(config.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"WARNING: batch metadata upload failed for {destination}: {exc}")
            continue
        if completed.returncode != 0:
            reason = completed.stderr.strip() or completed.stdout.strip()
            print(
                f"WARNING: batch metadata upload failed for {destination}: "
                f"{reason[:240]}"
            )


def _run_escalation_reviews(
    config: BatchConfig,
    results: list[dict[str, Any]],
    *,
    browser_session: BrowserSession | None = None,
) -> list[dict[str, Any]]:
    review_routes: dict[str, RouteDecision] = {}
    escalated: list[dict[str, Any]] = []
    for result in results:
        if result.get("status") != "ok":
            continue
        ticker = str(result["ticker"])
        route = _route_for(config, ticker)
        workflow = result.get("analysis_workflow")
        if not isinstance(workflow, dict):
            workflow = _analysis_workflow(config.repo_root, ticker)
        if workflow.get("status") == "escalation_required":
            review_routes[ticker] = route
            escalated.append(result)
            continue
        if (
            route.analysis_kind == "reference"
            and route.tier == "tracking"
            and _latest_generation_provider(config.repo_root, ticker)
            != "chatgpt-browser"
            and _latest_score(config.repo_root, ticker) >= 7.0
        ):
            latest_path = config.repo_root / "output" / ticker / "latest.md"
            candidate_path = config.repo_root / "output" / ticker / "candidate.md"
            candidate_path.write_text(
                latest_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
            review_routes[ticker] = RouteDecision(
                ticker=ticker,
                action="run",
                analysis_kind="review",
                tier="tracking",
                model=route.model,
                reasoning_effort=route.reasoning_effort,
                reviewer_model="gpt-5.6-sol",
                reason="terra_reference_requests_promotion",
                owned=route.owned,
            )
            escalated.append(result)
    if not escalated:
        return results

    print(
        "REVIEWS: starting after candidate pass: "
        + ", ".join(str(item["ticker"]) for item in escalated)
    )
    reviewed_by_ticker: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=(
            min(_browser_worker_count(browser_session), len(escalated))
            if browser_session is not None
            else _review_worker_count(config.max_parallel, len(escalated))
        )
    ) as executor:
        futures = {
            executor.submit(
                _run_review_with_retries,
                config,
                str(result["ticker"]),
                review_routes[str(result["ticker"])],
                browser_session,
            ): str(result["ticker"])
            for result in escalated
        }
        for future in concurrent.futures.as_completed(futures):
            ticker = futures[future]
            try:
                review = future.result()
            except Exception as exc:
                review = {
                    "ticker": ticker,
                    "status": "failed",
                    "error_type": "review_runtime_error",
                    "error_message": str(exc),
                }
            reviewed_by_ticker[ticker] = review
            _print_ticker_result(review)

    merged: list[dict[str, Any]] = []
    for result in results:
        ticker = str(result["ticker"])
        review = reviewed_by_ticker.get(ticker)
        if review is None:
            merged.append(result)
            continue
        updated = dict(result)
        updated["review"] = review
        if review.get("status") != "ok":
            updated["status"] = "failed"
            updated["error_type"] = review.get("error_type", "review_failed")
            updated["error_message"] = review.get("error_message", "review failed")
        merged.append(updated)
    return merged


def _review_worker_count(batch_max_parallel: int, review_count: int) -> int:
    """Keep expensive review runs below the technical endpoint's safe fan-out."""
    return min(MAX_REVIEW_PARALLEL, batch_max_parallel, review_count)


def _run_review_with_retries(
    config: BatchConfig,
    ticker: str,
    route: RouteDecision,
    browser_session: BrowserSession | None = None,
) -> dict[str, Any]:
    """Retry a review only when its failure is clearly transient."""
    for attempt in range(1, TRANSIENT_REVIEW_RETRIES + 2):
        result = _run_one_review(
            config,
            ticker,
            route,
            browser_session=browser_session,
        )
        result["attempt"] = attempt
        if result.get("status") == "ok" or not _is_transient_review_failure(result):
            return result
        if attempt > TRANSIENT_REVIEW_RETRIES:
            return result
        delay = TRANSIENT_REVIEW_BACKOFF_SECONDS * (2 ** (attempt - 1))
        print(
            f"RETRY REVIEW {attempt}/{TRANSIENT_REVIEW_RETRIES}: "
            f"{ticker} after {delay:g}s.",
            flush=True,
        )
        time.sleep(delay)

    raise AssertionError("unreachable")


def _is_transient_review_failure(result: dict[str, Any]) -> bool:
    if result.get("status") == "ok":
        return False
    detail = " ".join(
        str(result.get(key) or "")
        for key in ("error_type", "error_message", "stdout", "stderr")
    ).lower()
    markers = (
        "http 502",
        "http 503",
        "502 server error",
        "503 server error",
        "service unavailable",
        "connection reset",
        "connection aborted",
        "timed out",
        "timeout",
    )
    return any(marker in detail for marker in markers)


def _latest_score(repo_root: Path, ticker: str) -> float:
    payload = _load_latest_json(repo_root, ticker)
    decision = payload.get("decision")
    score = decision.get("score") if isinstance(decision, dict) else None
    return float(score) if isinstance(score, (int, float)) else float("-inf")


def _latest_generation_provider(repo_root: Path, ticker: str) -> str:
    payload = _load_latest_json(repo_root, ticker)
    return str(payload.get("generation_provider") or "")


def _analysis_workflow(repo_root: Path, ticker: str) -> dict[str, Any]:
    payload = _load_latest_json(repo_root, ticker)
    workflow = payload.get("analysis_workflow")
    return dict(workflow) if isinstance(workflow, dict) else {}


def _route_for(config: BatchConfig, ticker: str) -> RouteDecision:
    return next(route for route in config.routes if route.ticker == ticker)


def _run_one_review(
    config: BatchConfig,
    ticker: str,
    route: RouteDecision,
    *,
    browser_session: BrowserSession | None = None,
) -> dict[str, Any]:
    reviewer = route.reviewer_model
    if not reviewer:
        raise RuntimeError(f"reviewer_model_missing: {ticker}")
    started = _utc_now()
    started_perf = time.perf_counter()
    command = [
        sys.executable,
        "-m",
        "src.local_runner.run_one",
        ticker,
        "--run-full",
        "--skip-preflight-updates",
        "--skip-ibkr-gateway-ensure",
        "--execution-context",
        "batch",
        "--analysis-kind",
        "review",
        "--reference-tier",
        route.tier,
        "--model",
        reviewer,
        "--reasoning-effort",
        config.reasoning_effort,
    ]
    command.extend(_generation_provider_args(config))
    if route.owned:
        command.append("--owned")
    if browser_session is None:
        completed = subprocess.run(
            command,
            cwd=str(config.repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    else:
        exit_code = _run_one_full(
            config.repo_root,
            ticker,
            skip_preflight_updates=True,
            skip_ibkr_gateway_ensure=True,
            model=reviewer,
            reasoning_effort=config.reasoning_effort,
            execution_context="batch",
            analysis_kind="review",
            reference_tier=route.tier,
            owned=route.owned,
            generation_provider=config.generation_provider,
            chatgpt_browser_headed=config.chatgpt_browser_headed,
            chatgpt_browser_max_attempts=config.chatgpt_browser_max_attempts,
            generator_fallback=config.generator_fallback,
            chatgpt_browser_session=browser_session,
        )
        completed = subprocess.CompletedProcess(
            args=command,
            returncode=exit_code,
            stdout="",
            stderr="",
        )
    result: dict[str, Any] = {
        "ticker": ticker,
        "status": "ok" if completed.returncode == 0 else "failed",
        "model": reviewer,
        "started_at": started.isoformat(),
        "finished_at": _utc_now().isoformat(),
        "duration_seconds": round(time.perf_counter() - started_perf, 3),
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
    if completed.returncode != 0:
        latest = _load_latest_json(config.repo_root, ticker)
        result["error_type"] = latest.get("error_type") or "review_failed"
        result["error_message"] = (
            latest.get("error_message")
            or _short_failure_from_output(completed.stdout)
            or completed.stderr
            or f"exit_code={completed.returncode}"
        )
        return result

    if route.tier == "tracking" and reviewer != "gpt-5.6-sol":
        latest = _load_latest_json(config.repo_root, ticker)
        decision = latest.get("decision")
        score = decision.get("score") if isinstance(decision, dict) else None
        if isinstance(score, (int, float)) and float(score) >= 7.0:
            candidate_path = config.repo_root / "output" / ticker / "candidate.md"
            latest_path = config.repo_root / "output" / ticker / "latest.md"
            candidate_path.write_text(latest_path.read_text(encoding="utf-8"), encoding="utf-8")
            promoted_route = RouteDecision(
                ticker=ticker,
                action="run",
                analysis_kind="review",
                tier="priority",
                model=route.model,
                reasoning_effort=route.reasoning_effort,
                reviewer_model="gpt-5.6-sol",
                reason="terra_confirmed_promotion",
                owned=route.owned,
            )
            sol_result = _run_one_review(
                config,
                ticker,
                promoted_route,
                browser_session=browser_session,
            )
            result["promotion_review"] = sol_result
            if sol_result.get("status") != "ok":
                result["status"] = "failed"
                result["error_type"] = sol_result.get("error_type")
                result["error_message"] = sol_result.get("error_message")
    return result


def _run_analyst_update(
    config: BatchConfig,
    progress_dir: Path | None = None,
) -> dict[str, Any]:
    if not config.update_analysts:
        return {
            "status": "skipped",
            "reason": "disabled",
        }

    command = [
        sys.executable,
        "-m",
        (
            "src.local_runner.update_analyst_ratings_pipeline"
            if progress_dir is not None
            else "src.local_runner.update_analyst_ratings_batch"
        ),
        "--tickers",
        ",".join(config.tickers),
        "--backfill",
        "--execute-upload-real",
    ]
    if progress_dir is not None:
        command.extend(["--progress-dir", str(progress_dir)])
    return _run_non_blocking_prestep(
        config=config,
        name="Analyst update",
        log_name="analyst_update.json",
        command=command,
    )


def _run_source_update(
    config: BatchConfig,
    progress_dir: Path,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "src.local_runner.update_analysis_sources_pipeline",
        "--tickers",
        ",".join(config.tickers),
        "--progress-dir",
        str(progress_dir),
    ]
    if config.update_analysts:
        command.extend(["--update-analysts", "--backfill", "--execute-upload-real"])
    if config.update_ibkr_news:
        command.append("--update-news")
    return _run_non_blocking_prestep(
        config=config,
        name="Progressive source update",
        log_name="source_update.json",
        command=command,
    )


def _run_ibkr_news_update(config: BatchConfig) -> dict[str, Any]:
    if not config.update_ibkr_news:
        return {
            "status": "skipped",
            "reason": "disabled",
        }

    result = _run_non_blocking_prestep(
        config=config,
        name="IBKR news update",
        log_name="ibkr_news_update.json",
        command=[
            sys.executable,
            "-m",
            "src.local_runner.update_ibkr_news_batch",
            "--tickers",
            ",".join(config.tickers),
            "--process-timeout",
            str(DEFAULT_NEWS_PROCESS_TIMEOUT),
        ],
    )
    if result.get("status") != "ok":
        detail = result.get("stderr") or result.get("stdout") or "unknown_error"
        raise RuntimeError(f"ibkr_news_update_failed: {str(detail)[:500]}")
    return result


def _run_non_blocking_prestep(
    *,
    config: BatchConfig,
    name: str,
    log_name: str,
    command: list[str],
) -> dict[str, Any]:
    started = _utc_now()
    started_perf = time.perf_counter()

    print(f"{name}: starting")
    completed = subprocess.run(
        command,
        cwd=str(config.repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    finished = _utc_now()
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    result = {
        "status": "ok" if completed.returncode == 0 else "failed_non_blocking",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round(time.perf_counter() - started_perf, 3),
        "exit_code": completed.returncode,
        "command": command,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
    }

    _write_json(config.log_dir / log_name, result)

    if completed.returncode == 0:
        print(f"{name}: ok")
    else:
        reason = stderr or stdout or f"exit_code={completed.returncode}"
        print(f"{name}: failed_non_blocking: {reason[:240]}")

    return result


def _analysis_worker_count(
    *,
    ticker_count: int,
    browser_session: BrowserSession | None,
    generator_fallback: bool,
    max_parallel: int,
    model_parallel: int | None = None,
) -> int:
    if ticker_count < 1:
        return 1
    if model_parallel is not None:
        return min(ticker_count, max_parallel, model_parallel)
    if browser_session is not None:
        web_workers = _browser_worker_count(browser_session)
        fallback_capacity = web_workers if generator_fallback else 0
        return min(
            ticker_count,
            max_parallel,
            web_workers + fallback_capacity,
        )
    return 1


def _browser_worker_count(browser_session: BrowserSession) -> int:
    return max(1, int(getattr(browser_session, "worker_count", 1)))


def _run_ticker_pass(
    config: BatchConfig,
    tickers: tuple[str, ...],
    attempt: int | dict[str, int] | None,
    *,
    tracker: _PipelineTracker,
    preparation_gate: _SourceProgressGate | None = None,
    browser_session: BrowserSession | None = None,
) -> list[dict[str, Any]]:
    if not tickers:
        return []

    preparation_workers = min(config.max_parallel, len(tickers))
    model_parallel = None
    if config.adaptive_codex:
        from src.local_runner.adaptive_policy import load_policy
        model_parallel = load_policy(config.repo_root)["max_model_parallel"]
    analysis_workers = _analysis_worker_count(
        ticker_count=len(tickers),
        browser_session=browser_session,
        generator_fallback=config.generator_fallback,
        max_parallel=config.max_parallel,
        model_parallel=model_parallel,
    )
    finalize_workers = min(MAX_FINALIZE_PARALLEL, config.max_parallel, len(tickers))
    events: queue.Queue[
        tuple[str, PipelineTask, concurrent.futures.Future[dict[str, Any]]]
    ] = queue.Queue()
    results: list[dict[str, Any]] = []
    stage_results: dict[str, dict[str, dict[str, Any]]] = {}
    terminal_count = 0

    executors = {
        "prepare": concurrent.futures.ThreadPoolExecutor(
            max_workers=preparation_workers,
            thread_name_prefix="analysis-prepare",
        ),
        "analyze": concurrent.futures.ThreadPoolExecutor(
            max_workers=analysis_workers,
            thread_name_prefix="analysis-model",
        ),
        "publish": concurrent.futures.ThreadPoolExecutor(
            max_workers=finalize_workers,
            thread_name_prefix="analysis-publish",
        ),
    }

    def submit(stage: str, task: PipelineTask) -> None:
        future = executors[stage].submit(
            _run_pipeline_stage_after_gate,
            config,
            task,
            stage,
            preparation_gate,
            browser_session,
            tracker,
        )
        future.add_done_callback(
            lambda completed, current_stage=stage, current_task=task: events.put(
                (current_stage, current_task, completed)
            )
        )

    try:
        for ticker in tickers:
            requested_attempt = (
                attempt.get(ticker)
                if isinstance(attempt, dict)
                else attempt
            )
            task = PipelineTask(
                ticker=ticker,
                attempt=tracker.attempt_for(ticker, requested_attempt),
            )
            next_stage = tracker.next_stage(task.ticker, task.attempt)
            if next_stage is None:
                result = _load_json_file(
                    config.log_dir / "tickers" / f"{ticker}.json"
                ) or _pipeline_terminal_result(config, task, {}, status="ok")
                results.append(result)
                terminal_count += 1
                continue
            submit(next_stage, task)

        while terminal_count < len(tickers):
            stage, task, future = events.get()
            try:
                stage_result = future.result()
            except Exception as exc:
                stage_result = {
                    "ticker": task.ticker,
                    "attempt": task.attempt,
                    "stage": stage,
                    "status": "failed",
                    "error_type": "runtime_error",
                    "error_message": str(exc),
                }
            stage_results.setdefault(task.ticker, {})[stage] = stage_result
            tracker.stage_finished(task, stage, stage_result)

            if stage_result.get("status") != "ok":
                result = _pipeline_terminal_result(
                    config,
                    task,
                    stage_results[task.ticker],
                    status="failed",
                )
                if config.adaptive_codex:
                    from src.local_runner.analysis_attempt import record_failure
                    record_failure(config.repo_root, config.log_dir / "adaptive" / task.ticker,
                                   task.ticker, stage, RuntimeError(str(stage_result.get("error_message") or "stage_failed")),
                                   started_at=datetime.fromtimestamp(config.log_dir.stat().st_ctime, timezone.utc).isoformat())
                tracker.mark_terminal(task, "failed")
                _write_json(
                    config.log_dir / "tickers" / f"{task.ticker}.json",
                    result,
                )
                _print_ticker_result(result)
                results.append(result)
                terminal_count += 1
                continue

            if stage == "prepare":
                submit("analyze", task)
            elif stage == "analyze":
                submit("publish", task)
            else:
                result = _pipeline_terminal_result(
                    config,
                    task,
                    stage_results[task.ticker],
                    status="ok",
                )
                tracker.mark_terminal(task, "ok")
                _write_json(
                    config.log_dir / "tickers" / f"{task.ticker}.json",
                    result,
                )
                _print_ticker_result(result)
                results.append(result)
                terminal_count += 1
    finally:
        for executor in executors.values():
            executor.shutdown(wait=True, cancel_futures=False)

    return sorted(results, key=lambda item: tickers.index(str(item["ticker"])))


def _run_pipeline_stage_after_gate(
    config: BatchConfig,
    task: PipelineTask,
    stage: str,
    preparation_gate: _SourceProgressGate | None,
    browser_session: BrowserSession | None = None,
    tracker: _PipelineTracker | None = None,
) -> dict[str, Any]:
    if stage == "prepare" and preparation_gate is not None:
        preparation_gate.wait(task.ticker)
    if tracker is not None:
        tracker.stage_started(task, stage)
    print(
        f"PIPELINE {stage.upper()} {task.ticker} attempt={task.attempt}",
        flush=True,
    )
    if stage == "analyze" and browser_session is not None:
        return _run_persistent_browser_analyze_stage(
            config,
            task,
            browser_session,
        )
    return _run_pipeline_stage(config, task, stage)


def _run_persistent_browser_analyze_stage(
    config: BatchConfig,
    task: PipelineTask,
    browser_session: BrowserSession,
) -> dict[str, Any]:
    started = _utc_now()
    started_perf = time.perf_counter()
    ticker = task.ticker
    route = _route_for(config, ticker)
    exit_code = 1
    stderr = ""
    try:
        exit_code = _generate_one(
            config.repo_root,
            ticker,
            model=str(route.model),
            reasoning_effort=config.reasoning_effort,
            execution_context="batch",
            analysis_kind=str(route.analysis_kind),
            reference_tier=route.tier,
            owned=route.owned,
            generation_provider=config.generation_provider,
            chatgpt_browser_headed=config.chatgpt_browser_headed,
            chatgpt_browser_max_attempts=config.chatgpt_browser_max_attempts,
            generator_fallback=config.generator_fallback,
            chatgpt_browser_session=browser_session,
        )
        if exit_code == 0:
            exit_code = _validate_one(
                config.repo_root,
                ticker,
                execution_context="batch",
                analysis_kind=str(route.analysis_kind),
                reference_tier=route.tier,
                owned=route.owned,
                generation_model=str(route.model),
                reasoning_effort=config.reasoning_effort,
                generation_provider=config.generation_provider,
            )
    except Exception as exc:
        stderr = f"{type(exc).__name__}: {exc}"
        exit_code = 1

    stdout = ""
    result: dict[str, Any] = {
        "ticker": ticker,
        "attempt": task.attempt,
        "stage": "analyze",
        "started_at": started.isoformat(),
        "finished_at": _utc_now().isoformat(),
        "duration_seconds": round(time.perf_counter() - started_perf, 3),
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
    }
    generation_metadata = _load_generation_metadata(config.repo_root, ticker)
    metadata_started_at = _parse_iso_datetime(generation_metadata.get("started_at"))
    if exit_code != 0 and (
        metadata_started_at is None or metadata_started_at < started
    ):
        # Generation can fail before writing metadata. Do not attribute that
        # attempt to a provider left behind by an older successful run.
        generation_metadata = {"provider_used": config.generation_provider}
    _add_generation_details_to_stage_result(result, generation_metadata)
    if exit_code == 0:
        result["status"] = "ok"
        return result

    latest_json = _load_latest_json(config.repo_root, ticker)
    result.update(
        {
            "status": "failed",
            "error_type": latest_json.get("error_type") or "run_one_failed",
            "error_message": (
                latest_json.get("error_message")
                or _short_failure_from_output(stdout)
                or stderr
                or f"exit_code={exit_code}"
            ),
        }
    )
    return result


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


def _run_pipeline_stage(
    config: BatchConfig,
    task: PipelineTask,
    stage: str,
) -> dict[str, Any]:
    started = _utc_now()
    started_perf = time.perf_counter()
    ticker = task.ticker
    route = next(route for route in config.routes if route.ticker == ticker)
    if route.model is None or route.analysis_kind is None:
        raise RuntimeError(f"invalid_runnable_route: {ticker}")

    if stage not in {"prepare", "analyze", "publish"}:
        raise RuntimeError(f"unknown_pipeline_stage: {stage}")

    common = [
        "--execution-context",
        "batch",
        "--analysis-kind",
        route.analysis_kind,
        "--reference-tier",
        route.tier,
        "--model",
        route.model,
        "--reasoning-effort",
        config.reasoning_effort,
    ]
    if route.owned:
        common.append("--owned")

    modes = {
        "prepare": ("--prepare",),
        "analyze": ("--generate", "--validate"),
        "publish": ("--publish-real",),
    }[stage]
    if config.adaptive_codex:
        modes = (stage,)
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    completed: subprocess.CompletedProcess[str] | None = None
    for mode in modes:
        command = [
            sys.executable,
            "-m",
            "src.local_runner.run_one",
            ticker,
            mode,
            *common,
        ]
        if config.adaptive_codex:
            command = [sys.executable, "-m", "src.local_runner.adaptive_stage", ticker,
                       "--stage", stage, "--batch-dir", str(config.log_dir), "--tier", route.tier]
            if route.owned:
                command.append("--owned")
            if route.analysis_kind == "reference":
                command.append("--force-full")
            if stage == "prepare" and config.ownership_context is not None:
                command.extend(["--ownership-json", json.dumps(
                    config.ownership_context[ticker], ensure_ascii=True, separators=(",", ":"))])
        if stage == "prepare" and not config.adaptive_codex:
            command.extend(
                ["--skip-preflight-updates", "--skip-ibkr-gateway-ensure"]
            )
        if stage in {"prepare", "analyze", "publish"} and not config.adaptive_codex:
            command.extend(_generation_provider_args(config))
        with tempfile.TemporaryFile(
            mode="w+", encoding="utf-8", errors="replace"
        ) as stdout_file, tempfile.TemporaryFile(
            mode="w+", encoding="utf-8", errors="replace"
        ) as stderr_file:
            try:
                completed = run_bounded(
                    command,
                    cwd=str(config.repo_root),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=PIPELINE_STAGE_TIMEOUT_SECONDS[stage],
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                    ),
                )
            except subprocess.TimeoutExpired:
                completed = subprocess.CompletedProcess(command, 124)
                stderr_file.write(
                    f"pipeline_{stage}_timeout_after_"
                    f"{PIPELINE_STAGE_TIMEOUT_SECONDS[stage]}s"
                )
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout_parts.append(stdout_file.read().strip())
            stderr_parts.append(stderr_file.read().strip())
        if completed.returncode != 0:
            break
    if completed is None:
        raise AssertionError("pipeline stage has no commands")
    finished = _utc_now()
    duration_seconds = round(time.perf_counter() - started_perf, 3)
    stdout = "\n".join(part for part in stdout_parts if part)
    stderr = "\n".join(part for part in stderr_parts if part)

    result: dict[str, Any] = {
        "ticker": ticker,
        "attempt": task.attempt,
        "stage": stage,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": duration_seconds,
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }

    if stage == "analyze" and not config.adaptive_codex:
        _add_generation_details_to_stage_result(
            result,
            _load_generation_metadata(config.repo_root, ticker),
        )
    if config.adaptive_codex:
        review = _load_json_file(config.log_dir / "adaptive" / ticker / "review.json")
        result["adaptive_review"] = review
        result["generation_provider_used"] = "codex"

    if completed.returncode == 0:
        result["status"] = "ok"
        return result

    latest_json = (
        _load_latest_json(config.repo_root, ticker) if stage == "analyze" else {}
    )
    if config.adaptive_codex:
        latest_json = _load_json_file(config.log_dir / "adaptive" / ticker / "failure.json")
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


def _pipeline_terminal_result(
    config: BatchConfig,
    task: PipelineTask,
    stages: dict[str, dict[str, Any]],
    *,
    status: str,
) -> dict[str, Any]:
    route = _route_for(config, task.ticker)
    failed_stage = next(
        (
            stage_result
            for stage_result in stages.values()
            if stage_result.get("status") != "ok"
        ),
        {},
    )
    started_values = [
        str(item.get("started_at"))
        for item in stages.values()
        if item.get("started_at")
    ]
    finished_values = [
        str(item.get("finished_at"))
        for item in stages.values()
        if item.get("finished_at")
    ]
    result: dict[str, Any] = {
        "ticker": task.ticker,
        "attempt": task.attempt,
        "status": status,
        "started_at": min(started_values) if started_values else _utc_now().isoformat(),
        "finished_at": max(finished_values) if finished_values else _utc_now().isoformat(),
        "duration_seconds": round(
            sum(float(item.get("duration_seconds") or 0) for item in stages.values()),
            3,
        ),
        "pipeline_stages": stages,
        "route": {
            "analysis_kind": route.analysis_kind,
            "tier": route.tier,
            "model": route.model,
            "reviewer_model": route.reviewer_model,
            "reason": route.reason,
            "owned": route.owned,
        },
    }
    if status != "ok":
        result["error_type"] = failed_stage.get("error_type") or "run_one_failed"
        result["error_message"] = (
            failed_stage.get("error_message") or "pipeline stage failed"
        )
        return result

    workflow = (_load_json_file(config.log_dir / "adaptive" / task.ticker / "review.json")
                if config.adaptive_codex else _analysis_workflow(config.repo_root, task.ticker))
    if workflow:
        result["analysis_workflow"] = workflow
    return result


def _build_summary(
    config: BatchConfig,
    run_started: datetime,
    results: list[dict[str, Any]],
    analyst_update: dict[str, Any],
    ibkr_news_update: dict[str, Any],
) -> dict[str, Any]:
    finished = _utc_now()
    ordered_results = sorted(
        results,
        key=lambda item: config.tickers.index(str(item["ticker"])),
    )
    success = sum(1 for item in ordered_results if item.get("status") == "ok")
    failed = len(ordered_results) - success
    fallback_tickers = [
        str(item["ticker"])
        for item in ordered_results
        if item.get("status") == "ok" and _used_codex_fallback(
            _load_generation_metadata(config.repo_root, str(item["ticker"]))
        )
    ]

    summary = {
        "started_at": run_started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round((finished - run_started).total_seconds(), 3),
        "source": config.source,
        "analysis_profile": config.analysis_profile,
        "model": config.model or "automatic",
        "routes": _routing_plan_payload(config.routes, run_started.astimezone(MADRID_TZ).date())["routes"],
        "reasoning_effort": config.reasoning_effort,
        "generation_provider": config.generation_provider,
        "pipeline_state_path": str(config.log_dir / "pipeline_state.json"),
        "generation_fallback": {
            "used": bool(fallback_tickers),
            "count": len(fallback_tickers),
            "tickers": fallback_tickers,
        },
        "generation_providers": _generation_provider_summary(
            config.repo_root, ordered_results
        ),
        "retry_summary": _generation_retry_summary(
            config.repo_root,
            ordered_results,
            pipeline_state_path=config.log_dir / "pipeline_state.json",
        ),
        "max_parallel": config.max_parallel,
        "chatgpt_web_workers": config.chatgpt_web_workers,
        "retry_failed": config.retry_failed,
        "analyst_update": _summary_analyst_update(analyst_update),
        "ibkr_news_update": _summary_prestep(ibkr_news_update),
        "total": len(ordered_results),
        "success": success,
        "failed": failed,
        "confidence_decisions": _confidence_decision_counts(ordered_results),
        "results": [
            _summary_result(item)
            for item in ordered_results
        ],
    }
    summary["model_usage"] = _batch_model_usage(summary["results"])
    return summary


def _measured_adaptive_usage(calls: list[dict[str, Any]]) -> dict[str, Any]:
    measured: dict[str, Any] = {}
    for call in calls:
        if call.get("no_model_started") is True:
            continue  # Admission wait timed out; never count as a paid/unknown call.
        model = call.get("model") or "unconfirmed"
        totals = measured.setdefault(model, {"calls": 0, "input_tokens": 0,
            "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0,
            "unknown_usage_calls": 0})
        totals["calls"] += 1
        totals["unknown_usage_calls"] += int(not isinstance(call.get("usage"), dict))
        for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"):
            totals[key] += int((call.get("usage") or {}).get(key) or 0)
    return measured


def _adaptive_report_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    """Count published outcomes, not model calls or unuploaded candidates."""
    counts = {"retained_reports": 0, "updated_reports": 0, "regenerated_reports": 0}
    for result in results:
        workflow = result.get("analysis_workflow")
        if result.get("status") != "ok" or not isinstance(workflow, dict):
            continue
        key = {"retained": "retained_reports", "updated": "updated_reports",
               "regenerated": "regenerated_reports"}.get(workflow.get("status"))
        if key:
            counts[key] += 1
    return counts


def _generation_provider_summary(
    repo_root: Path, results: list[dict[str, Any]]
) -> dict[str, Any]:
    grouped: dict[str, list[str]] = {}
    for result in results:
        if result.get("status") != "ok":
            continue
        ticker = str(result.get("ticker") or "")
        metadata = _load_generation_metadata(repo_root, ticker)
        provider = str(metadata.get("provider_used") or "unknown")
        grouped.setdefault(provider, []).append(ticker)
    return {
        provider: {"count": len(tickers), "tickers": tickers}
        for provider, tickers in sorted(grouped.items())
    }


def _generation_retry_summary(
    repo_root: Path,
    results: list[dict[str, Any]],
    *,
    pipeline_state_path: Path | None = None,
) -> dict[str, int]:
    state = _load_json_file(pipeline_state_path) if pipeline_state_path else {}
    ticker_states = state.get("tickers")
    if isinstance(ticker_states, dict):
        batch_retries = 0
        web_retries = 0
        for ticker_state in ticker_states.values():
            if not isinstance(ticker_state, dict):
                continue
            attempts = ticker_state.get("attempts")
            if not isinstance(attempts, dict):
                continue
            batch_retries += max(0, len(attempts) - 1)
            for pipeline_attempt in attempts.values():
                if not isinstance(pipeline_attempt, dict):
                    continue
                stages = pipeline_attempt.get("stages")
                if not isinstance(stages, dict):
                    continue
                analyze = stages.get("analyze")
                if isinstance(analyze, dict):
                    web_retries += max(
                        0,
                        int(analyze.get("web_retry_count") or 0),
                    )
        return {
            "batch": batch_retries,
            "chatgpt_web": web_retries,
            "total": batch_retries + web_retries,
        }

    batch_retries = sum(
        max(0, int(result.get("attempt") or 1) - 1) for result in results
    )
    web_retries = 0
    for result in results:
        stages = result.get("pipeline_stages")
        if not isinstance(stages, dict) or "analyze" not in stages:
            continue
        ticker = str(result.get("ticker") or "")
        metadata = _load_generation_metadata(repo_root, ticker)
        attempts = metadata.get("attempts")
        if metadata.get("provider_requested") != "chatgpt-browser":
            continue
        if metadata.get("web_retry_count") is not None:
            web_retries += max(0, int(metadata["web_retry_count"]))
        elif isinstance(attempts, list):
            web_retries += max(0, len(attempts) - 1)
    return {
        "batch": batch_retries,
        "chatgpt_web": web_retries,
        "total": batch_retries + web_retries,
    }


def _generation_provider_args(config: BatchConfig) -> list[str]:
    args = [
        "--generation-provider",
        config.generation_provider,
        "--chatgpt-browser-max-attempts",
        str(config.chatgpt_browser_max_attempts),
    ]
    if config.chatgpt_browser_headed:
        args.append("--chatgpt-browser-headed")
    if not config.generator_fallback:
        args.append("--no-generator-fallback")
    return args


def _batch_model_usage(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize base routes and superior reviews by friendly model name."""
    base: dict[str, list[str]] = {}
    reviews: dict[str, list[str]] = {}
    failed: list[str] = []
    published: list[str] = []
    reference_retained: list[dict[str, Any]] = []
    reviewed_and_published: list[dict[str, Any]] = []

    def add(group: dict[str, list[str]], model: Any, ticker: str) -> None:
        name = _friendly_model_name(model)
        if not name:
            return
        tickers = group.setdefault(name, [])
        if ticker not in tickers:
            tickers.append(ticker)

    for result in results:
        ticker = str(result.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        route = result.get("route")
        workflow = result.get("analysis_workflow")
        adaptive = isinstance(route, dict) and route.get("reason") == "adaptive_luna_sol_itv"
        if adaptive and isinstance(workflow, dict):
            receipts = workflow.get("receipts") or []
            if receipts:
                add(base, receipts[0].get("model"), ticker)
                for receipt in receipts[1:]:
                    add(reviews, receipt.get("model"), ticker)
            else:
                add(base, workflow.get("effective_model"), ticker)
        elif isinstance(route, dict) and not adaptive:
            add(base, route.get("model"), ticker)
        review = result.get("review")
        if isinstance(review, dict):
            add(reviews, review.get("model"), ticker)
            promotion = review.get("promotion_review")
            if isinstance(promotion, dict):
                add(reviews, promotion.get("model"), ticker)
        if result.get("status") != "ok":
            failed.append(ticker)
            continue

        workflow = result.get("analysis_workflow")
        if (
            isinstance(workflow, dict)
            and workflow.get("status") == "reference_retained_low_confidence"
        ):
            reference_retained.append(
                {
                    "ticker": ticker,
                    "confidence": workflow.get("effective_confidence"),
                    "reasons": workflow.get("material_change_reasons") or [],
                    "reference_generated_at": workflow.get("reference_generated_at"),
                }
            )
        elif isinstance(review, dict) and review.get("status") == "ok":
            final_model = review.get("model")
            promotion = review.get("promotion_review")
            if isinstance(promotion, dict) and promotion.get("status") == "ok":
                final_model = promotion.get("model")
            reviewed_and_published.append(
                {
                    "ticker": ticker,
                    "model": _friendly_model_name(final_model),
                }
            )
        else:
            published.append(ticker)

    return {
        "base": base,
        "reviews": reviews,
        "published": published,
        "reference_retained": reference_retained,
        "reviewed_and_published": reviewed_and_published,
        "failed": failed,
    }


def _friendly_model_name(model: Any) -> str:
    value = str(model or "").strip().lower()
    if not value:
        return ""
    if "luna" in value:
        return "Luna"
    if "terra" in value:
        return "Tierra"
    if "sol" in value:
        return "Sol"
    return str(model)


def _summary_analyst_update(result: dict[str, Any]) -> dict[str, Any]:
    payload = _summary_prestep(result)
    stdout = str(result.get("stdout_tail") or "")
    for line in reversed(stdout.splitlines()):
        if not line.startswith("EARNINGS_REFRESH:"):
            continue
        try:
            refresh = json.loads(line.split(":", 1)[1])
        except json.JSONDecodeError:
            break
        if isinstance(refresh, dict):
            payload["earnings_refresh"] = refresh
        break
    return payload


def _summary_prestep(result: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "status": result.get("status"),
        "duration_seconds": result.get("duration_seconds"),
        "exit_code": result.get("exit_code"),
    }

    if result.get("status") == "failed_non_blocking":
        payload["error_message"] = (
            result.get("stderr_tail")
            or result.get("stdout_tail")
            or "analyst_update_failed"
        )[:500]
    elif result.get("reason"):
        payload["reason"] = result.get("reason")

    return payload


def _summary_result(result: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ticker": result["ticker"],
        "status": result["status"],
        "attempt": result.get("attempt"),
        "duration_seconds": result.get("duration_seconds"),
        "route": result.get("route"),
    }

    if result.get("status") != "ok":
        payload["error_type"] = result.get("error_type", "failed")
        payload["error_message"] = result.get("error_message", "")
    if result.get("review") is not None:
        review = result["review"]
        payload["review"] = {
            "status": review.get("status"),
            "model": review.get("model"),
            "duration_seconds": review.get("duration_seconds"),
            "promotion_review": review.get("promotion_review"),
        }
    if isinstance(result.get("analysis_workflow"), dict):
        payload["analysis_workflow"] = result["analysis_workflow"]

    return payload


def _confidence_decision_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        workflow = result.get("analysis_workflow")
        if not isinstance(workflow, dict):
            continue
        decision = str(workflow.get("decision") or "unknown")
        counts[decision] = counts.get(decision, 0) + 1
    return counts


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

    print(
        "BATCH_MODEL_USAGE:"
        + json.dumps(summary.get("model_usage", {}), ensure_ascii=False, separators=(",", ":"))
    )

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


def _load_generation_metadata(repo_root: Path, ticker: str) -> dict[str, Any]:
    path = repo_root / "output" / ticker / "generation_metadata.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _add_generation_details_to_stage_result(
    result: dict[str, Any], metadata: dict[str, Any]
) -> None:
    result["generation_provider"] = metadata.get("provider_used")
    web_worker_id = metadata.get("web_worker_id")
    if web_worker_id is not None:
        result["web_worker_id"] = int(web_worker_id)

    attempts = metadata.get("attempts")
    inferred_attempt_count = len(attempts) if isinstance(attempts, list) else 0
    web_attempt_count = max(
        0, int(metadata.get("web_attempt_count") or inferred_attempt_count)
    )
    web_retry_count = max(
        0,
        int(
            metadata.get("web_retry_count")
            if metadata.get("web_retry_count") is not None
            else max(0, web_attempt_count - 1)
        ),
    )
    result["web_attempt_count"] = web_attempt_count
    result["web_retry_count"] = web_retry_count

    raw_web_timing = metadata.get("web_timing_seconds")
    if isinstance(raw_web_timing, dict) and raw_web_timing:
        queue_wait = float(raw_web_timing.get("queue_wait_seconds") or 0.0)
        execution = float(raw_web_timing.get("execution_seconds") or 0.0)
        result["web_timing_seconds"] = {
            "queue_wait_seconds": round(queue_wait, 3),
            "execution_seconds": round(execution, 3),
            "non_web_seconds": round(
                max(
                    0.0,
                    float(result.get("duration_seconds") or 0.0)
                    - queue_wait
                    - execution,
                ),
                3,
            ),
        }


def _used_codex_fallback(metadata: dict[str, Any]) -> bool:
    return (
        metadata.get("provider_requested") == "chatgpt-browser"
        and metadata.get("provider_used") == "codex"
        and metadata.get("status") == "ok_fallback"
    )


def _load_latest_json(repo_root: Path, ticker: str) -> dict[str, Any]:
    latest_json_path = repo_root / "output" / ticker / "latest.json"

    if not latest_json_path.exists():
        return {}

    try:
        payload = json.loads(latest_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    return payload if isinstance(payload, dict) else {}


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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
    from src.local_runner.windows_desktop import configure_background_launch

    configure_background_launch()
    sys.exit(main())
