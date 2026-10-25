"""Prepare and validate one local Codex stock analysis."""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from src.local_runner.ibkr_news_pagination import DEFAULT_NEWS_PROCESS_TIMEOUT
from src.local_runner.process_control import configure_utf8_output

from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.common.analysis_validator import extract_score, extract_dimension_score, validate_markdown
from src.local_runner.analyst_quality import load_analyst_quality_context
from src.local_runner.analyst_recent_actions import (
    format_recent_analyst_actions_for_prompt,
    load_recent_analyst_actions,
)
from src.local_runner.analyst_summary import load_compact_analyst_summary
from src.local_runner.codex_generator import generate_markdown_with_codex
from src.local_runner.chatgpt_browser_generator import (
    DEFAULT_MAX_ATTEMPTS as DEFAULT_CHATGPT_BROWSER_MAX_ATTEMPTS,
    ChatGPTBrowserSession,
    build_chatgpt_web_input,
    generate_markdown_with_chatgpt_browser,
)
from src.local_runner.gcs_uploader import (
    build_real_upload_plan,
    build_test_upload_plan,
    format_command,
    upload_artifacts,
)
from src.local_runner.html_report import write_analysis_html
from src.local_runner.ibkr_recent_news import (
    format_recent_news_for_prompt,
    load_recent_news,
)
from src.local_runner.level_continuity import build_level_continuity_precheck
from src.local_runner.previous_analysis import (
    load_authoritative_reference_context,
    load_previous_analysis_context,
)
from src.local_runner.analysis_policy import LUNA_MODEL, MADRID_TZ, SOL_MODEL
from src.local_runner.analysis_state import load_reference_payload, save_reference_payload
from src.local_runner.report_archive import maintain_report_archive
from src.local_runner.report_dates import format_report_date, normalize_report_dates
from src.local_runner.report_schema import build_structured_report
from src.local_runner.ibkr_gateway_manager import ensure_gateway


SLIM_BASE_URL = "https://support-resistances-slim-714254943648.europe-southwest1.run.app"
MODEL_NAME = "codex-local"
DEFAULT_CODEX_MODEL = "gpt-6.1-sol"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_GENERATION_PROVIDER = "codex"
REQUEST_TIMEOUT_SECONDS = 120
LOCAL_SYSTEM_PROMPT_PATH = Path("prompts") / "stock_analysis_system_prompt.md"


def main(argv: list[str] | None = None) -> int:
    configure_utf8_output()
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    symbol = args.ticker.strip().upper()
    if args.run_full and args.execution_context == "individual" and args.generation_provider == "codex":
        from src.local_runner.adaptive_stage import run_individual
        return run_individual(repo_root, symbol, args)

    args.owned = bool(args.owned)  # Legacy paths retain their historical boolean contract.

    if args.prepare:
        if not args.skip_ibkr_gateway_ensure:
            ensure_gateway(repo_root)
        if not args.skip_preflight_updates:
            _run_preflight_updates(repo_root, symbol)
        return _prepare(
            repo_root,
            symbol,
            execution_context=args.execution_context,
            analysis_kind=args.analysis_kind,
            reference_tier=args.reference_tier,
            owned=args.owned,
            generation_model=args.model,
            generation_provider=args.generation_provider,
        )

    if args.validate:
        return _validate(
            repo_root,
            symbol,
            execution_context=args.execution_context,
            analysis_kind=args.analysis_kind,
            reference_tier=args.reference_tier,
            owned=args.owned,
            generation_model=args.model,
            reasoning_effort=args.reasoning_effort,
            generation_provider=args.generation_provider,
        )

    if args.generate:
        return _generate(
            repo_root,
            symbol,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            execution_context=args.execution_context,
            analysis_kind=args.analysis_kind,
            reference_tier=args.reference_tier,
            owned=args.owned,
            generation_provider=args.generation_provider,
            chatgpt_browser_headed=args.chatgpt_browser_headed,
            chatgpt_browser_max_attempts=args.chatgpt_browser_max_attempts,
            generator_fallback=not args.no_generator_fallback,
        )

    if args.finalize_real:
        return _finalize_real(
            repo_root,
            symbol,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            execution_context=args.execution_context,
            analysis_kind=args.analysis_kind,
            reference_tier=args.reference_tier,
            owned=args.owned,
            generation_provider=args.generation_provider,
        )

    if args.publish_real:
        return _finalize_real(
            repo_root,
            symbol,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            execution_context=args.execution_context,
            analysis_kind=args.analysis_kind,
            reference_tier=args.reference_tier,
            owned=args.owned,
            generation_provider=args.generation_provider,
            validate_first=False,
        )

    if args.upload_test:
        return _upload(
            repo_root=repo_root,
            symbol=symbol,
            upload_kind="test",
            dry_run=not args.execute_upload_test,
        )

    if args.upload_real:
        return _upload(
            repo_root=repo_root,
            symbol=symbol,
            upload_kind="real",
            dry_run=not args.execute_upload_real,
        )

    if args.run_full:
        return _run_full(
            repo_root,
            symbol,
            skip_preflight_updates=args.skip_preflight_updates,
            skip_ibkr_gateway_ensure=args.skip_ibkr_gateway_ensure,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            execution_context=args.execution_context,
            analysis_kind=args.analysis_kind,
            reference_tier=args.reference_tier,
            owned=args.owned,
            generation_provider=args.generation_provider,
            chatgpt_browser_headed=args.chatgpt_browser_headed,
            chatgpt_browser_max_attempts=args.chatgpt_browser_max_attempts,
            generator_fallback=not args.no_generator_fallback,
        )

    raise RuntimeError(
        "Either --prepare, --generate, --finalize-real, --publish-real, "
        "--validate, --upload-test, --upload-real, or --run-full is required."
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare, generate, or validate one local stock analysis."
    )
    parser.add_argument("ticker", help="Ticker symbol, for example RKLB")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--prepare",
        action="store_true",
        help="Fetch slim JSON and create output/{TICKER}/codex_input.md.",
    )
    mode.add_argument(
        "--validate",
        action="store_true",
        help="Validate output/{TICKER}/latest.md and build latest JSON.",
    )
    mode.add_argument(
        "--generate",
        action="store_true",
        help="Generate output/{TICKER}/latest.md with the selected provider.",
    )
    mode.add_argument(
        "--finalize-real",
        action="store_true",
        help=(
            "Validate an already generated report, apply batch policy, upload it "
            "to the real paths, and save its authoritative reference."
        ),
    )
    mode.add_argument(
        "--publish-real",
        action="store_true",
        help=(
            "Apply batch policy and publish an already validated latest.json. "
            "This is the final stage used by the batch pipeline."
        ),
    )
    mode.add_argument(
        "--upload-test",
        action="store_true",
        help="Upload latest artifacts to the _local_test GCS prefix. Dry-run by default.",
    )
    mode.add_argument(
        "--upload-real",
        action="store_true",
        help="Upload latest artifacts to real ticker GCS paths. Dry-run by default.",
    )
    mode.add_argument(
        "--run-full",
        action="store_true",
        help="Run prepare, generate, validate, and execute real upload.",
    )
    parser.add_argument(
        "--execute-upload-test",
        action="store_true",
        help=(
            "Actually run gcloud storage cp for --upload-test. Without this flag, "
            "--upload-test only prints the commands."
        ),
    )
    parser.add_argument(
        "--execution-context",
        choices=("individual", "batch"),
        default="individual",
        help="Individual analyses are always authoritative Sol runs.",
    )
    parser.add_argument(
        "--analysis-kind",
        choices=("reference", "daily", "review"),
        default="reference",
        help="Batch role selected by the routing policy.",
    )
    parser.add_argument(
        "--reference-tier",
        choices=("priority", "tracking"),
        default="priority",
    )
    parser.add_argument("--owned", action=argparse.BooleanOptionalAction, default=None,
                        help="Explicit holding override; individual Codex defaults to recorded market holdings.")
    parser.add_argument(
        "--execute-upload-real",
        action="store_true",
        help=(
            "Actually run gcloud storage cp for --upload-real. Without this flag, "
            "--upload-real only prints the commands."
        ),
    )
    parser.add_argument(
        "--skip-preflight-updates",
        action="store_true",
        help=(
            "Skip non-blocking IBKR analyst/news refresh before --prepare or "
            "--run-full. Used by batch runs that already did the refresh."
        ),
    )
    parser.add_argument(
        "--skip-ibkr-gateway-ensure",
        action="store_true",
        help="Skip the strict IBKR API check. Used by a batch after its shared check.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_CODEX_MODEL,
        help=f"Codex model used for generation. Defaults to {DEFAULT_CODEX_MODEL}.",
    )
    parser.add_argument(
        "--reasoning-effort",
        default=DEFAULT_REASONING_EFFORT,
        choices=("low", "medium", "high", "xhigh"),
        help=(
            "Reasoning effort used for generation. "
            f"Defaults to {DEFAULT_REASONING_EFFORT}."
        ),
    )
    parser.add_argument(
        "--generation-provider",
        choices=("codex", "chatgpt-browser"),
        default=DEFAULT_GENERATION_PROVIDER,
        help="Markdown generator. Codex is the default; individual full runs use the adaptive policy's Sol model.",
    )
    parser.add_argument(
        "--chatgpt-browser-headed",
        action="store_true",
        help="Show the dedicated ChatGPT browser window during generation.",
    )
    parser.add_argument(
        "--chatgpt-browser-max-attempts",
        type=int,
        default=DEFAULT_CHATGPT_BROWSER_MAX_ATTEMPTS,
        help="Fresh ChatGPT requests allowed before the generator fails.",
    )
    parser.add_argument(
        "--no-generator-fallback",
        action="store_true",
        help="Do not fall back to Codex if ChatGPT browser generation fails.",
    )

    args = parser.parse_args(argv)

    if args.execute_upload_test and not args.upload_test:
        parser.error("--execute-upload-test can only be used with --upload-test")

    if args.execute_upload_real and not args.upload_real:
        parser.error("--execute-upload-real can only be used with --upload-real")

    if args.chatgpt_browser_max_attempts < 1:
        parser.error("--chatgpt-browser-max-attempts must be greater than 0")

    if args.execution_context == "individual":
        args.model = DEFAULT_CODEX_MODEL
        args.analysis_kind = "reference"

    return args


def _prepare(
    repo_root: Path,
    symbol: str,
    *,
    execution_context: str = "individual",
    analysis_kind: str = "reference",
    reference_tier: str = "priority",
    owned: bool = False,
    generation_model: str = DEFAULT_CODEX_MODEL,
    generation_provider: str = DEFAULT_GENERATION_PROVIDER,
) -> int:
    now = _utc_now()
    timestamp = _timestamp_for_file(now)

    slim = _fetch_slim(symbol)

    slim_dir = repo_root / "data" / "slim" / symbol
    output_dir = repo_root / "output" / symbol
    logs_dir = repo_root / "logs" / symbol

    slim_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    slim_path = slim_dir / f"{timestamp}.json"
    _write_json(slim_path, slim)

    previous_analysis = (
        load_authoritative_reference_context(symbol)
        if execution_context == "batch"
        else load_previous_analysis_context(symbol)
    )
    previous_analysis_block = previous_analysis.to_prompt_block(symbol)
    if analysis_kind == "review":
        candidate_path = output_dir / "candidate.md"
        if not candidate_path.exists():
            raise RuntimeError(f"review_candidate_not_found: {candidate_path}")
        previous_analysis_block += (
            "\n\nCANDIDATO QUE SOLICITA REVISIÓN SUPERIOR:\n\n"
            + candidate_path.read_text(encoding="utf-8")
        )
    analyst_quality = _load_analyst_quality(repo_root, symbol, slim, now=now)
    recent_analyst_actions = load_recent_analyst_actions(
        repo_root,
        symbol,
        since=previous_analysis.generated_at,
    )
    recent_ibkr_news = load_recent_news(repo_root, symbol)
    recent_ibkr_news_events = _news_events_not_used()
    instructions = _load_system_prompt(repo_root)
    analysis_authority_model = (
        SOL_MODEL
        if generation_provider == "chatgpt-browser"
        else generation_model
    )
    codex_input = _build_codex_input(
        symbol=symbol,
        analysis_date=datetime.now().astimezone().date().isoformat(),
        instructions=instructions,
        slim=slim,
        analyst_quality=analyst_quality,
        recent_analyst_actions_block=format_recent_analyst_actions_for_prompt(
            recent_analyst_actions
        ),
        recent_ibkr_news_block=format_recent_news_for_prompt(recent_ibkr_news),
        slim_path=slim_path,
        latest_md_path=output_dir / "latest.md",
        previous_analysis_block=previous_analysis_block,
        level_continuity_block=build_level_continuity_precheck(
            previous_analysis.analysis_markdown,
            slim,
        ),
        analysis_policy_block=_analysis_policy_prompt(
            execution_context=execution_context,
            analysis_kind=analysis_kind,
            reference_tier=reference_tier,
            owned=owned,
            reference_found=previous_analysis.found,
            generation_model=analysis_authority_model,
            web_sol_authoritative=generation_provider == "chatgpt-browser",
        ),
    )

    codex_input_path = output_dir / "codex_input.md"
    codex_input_path.write_text(codex_input, encoding="utf-8")
    previous_analysis_path = output_dir / "previous_analysis.md"
    if previous_analysis.found and previous_analysis.analysis_markdown.strip():
        previous_analysis_path.write_text(
            _build_previous_analysis_attachment(symbol, previous_analysis),
            encoding="utf-8",
        )
    else:
        previous_analysis_path.unlink(missing_ok=True)

    _write_json(
        logs_dir / f"{timestamp}.prepare.json",
        {
            "symbol": symbol,
            "generated_at": now.isoformat(),
            "slim_path": str(slim_path),
            "codex_input_path": str(codex_input_path),
            "previous_analysis_path": (
                str(previous_analysis_path) if previous_analysis_path.exists() else None
            ),
            "slim_as_of": slim.get("as_of"),
            "latest_price": slim.get("latest_price"),
            "analyst_consensus_quality": analyst_quality,
            "analyst_recent_actions": recent_analyst_actions,
            "ibkr_recent_news": recent_ibkr_news,
            "ibkr_recent_news_events": recent_ibkr_news_events,
            "previous_analysis": previous_analysis.to_log_dict(),
            "execution_context": execution_context,
            "analysis_kind": analysis_kind,
            "generation_model": generation_model,
            "analysis_authority_model": analysis_authority_model,
            "generation_provider": generation_provider,
            "reference_tier": reference_tier,
            "owned": owned,
        },
    )

    print(f"Prepared local Codex input for {symbol}.")
    print(f"Slim JSON: {slim_path}")
    print(f"Codex input: {codex_input_path}")
    print(f"Next: generate markdown into {output_dir / 'latest.md'}")

    return 0


def _validate(
    repo_root: Path,
    symbol: str,
    *,
    execution_context: str = "individual",
    analysis_kind: str = "reference",
    reference_tier: str = "priority",
    owned: bool = False,
    generation_model: str = DEFAULT_CODEX_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    generation_provider: str = DEFAULT_GENERATION_PROVIDER,
) -> int:
    now = _utc_now()
    timestamp = _timestamp_for_file(now)

    output_dir = repo_root / "output" / symbol
    logs_dir = repo_root / "logs" / symbol
    latest_md_path = output_dir / "latest.md"

    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    slim = _load_latest_slim(repo_root, symbol)
    analyst_quality = _load_analyst_quality(repo_root, symbol, slim, now=now)
    analyst_ratings_summary = load_compact_analyst_summary(repo_root, symbol)
    previous_analysis = (
        load_authoritative_reference_context(symbol)
        if execution_context == "batch"
        else load_previous_analysis_context(symbol)
    )
    recent_analyst_actions = load_recent_analyst_actions(
        repo_root,
        symbol,
        since=previous_analysis.generated_at,
    )
    recent_ibkr_news = load_recent_news(repo_root, symbol)
    recent_ibkr_news_events = _news_events_not_used()
    generation_metadata = _load_generation_metadata(output_dir)
    provider_used = str(
        generation_metadata.get("provider_used") or generation_provider
    )
    web_sol_used = provider_used == "chatgpt-browser"
    effective_generation_model = SOL_MODEL if web_sol_used else generation_model
    effective_reasoning_effort = "high" if web_sol_used else reasoning_effort

    if latest_md_path.exists():
        analysis_md = latest_md_path.read_text(encoding="utf-8")
        normalized_md = normalize_report_dates(analysis_md)
        if normalized_md != analysis_md:
            latest_md_path.write_text(normalized_md, encoding="utf-8")
            analysis_md = normalized_md
        context_path = output_dir / "codex_input.md"
        authoritative_context = (
            context_path.read_text(encoding="utf-8")
            if context_path.exists()
            else None
        )
        validation = validate_markdown(
            analysis_md,
            authoritative_context=authoritative_context,
            require_support_strengths=True,
            require_resistance=True,
            require_separate_scores=True,
        )
    else:
        analysis_md = ""
        validation = validate_markdown("")
        validation = validation.__class__(
            ok=False,
            status="failed",
            errors=(f"missing_markdown_file: output/{symbol}/latest.md not found",),
        )

    if validation.ok:
        payload = _build_ok_payload(
            symbol=symbol,
            now=now,
            analysis_md=analysis_md,
            slim=slim,
            analyst_quality=analyst_quality,
            analyst_ratings_summary=analyst_ratings_summary,
            recent_analyst_actions=recent_analyst_actions,
            recent_ibkr_news=recent_ibkr_news,
            recent_ibkr_news_events=recent_ibkr_news_events,
            validation=validation.to_dict(),
            previous_analysis_markdown=previous_analysis.analysis_markdown,
            generation_model=effective_generation_model,
            reasoning_effort=effective_reasoning_effort,
            execution_context=execution_context,
            analysis_kind=analysis_kind,
            reference_tier=reference_tier,
            owned=owned,
            generation_provider=provider_used,
        )
        latest_json_path = output_dir / "latest.json"
        latest_html_path = output_dir / "latest.html"
        _write_json(latest_json_path, payload)
        write_analysis_html(
            analysis_md,
            latest_html_path,
            symbol=symbol,
        )

        _write_json(
            logs_dir / f"{timestamp}.validate.json",
            {
                "symbol": symbol,
                "generated_at": now.isoformat(),
                "analysis_status": "ok",
                "latest_json_path": str(latest_json_path),
                "latest_html_path": str(latest_html_path),
                "analyst_consensus_quality": analyst_quality,
                "analyst_ratings_summary": analyst_ratings_summary,
                "analyst_recent_actions": recent_analyst_actions,
                "ibkr_recent_news": recent_ibkr_news,
                "ibkr_recent_news_events": recent_ibkr_news_events,
                "validation": validation.to_dict(),
                "generation_provider": provider_used,
                "generation_metadata": generation_metadata,
            },
        )

        print(f"Validation OK for {symbol}.")
        print(f"Latest JSON: {latest_json_path}")

        return 0

    error_message = "; ".join(validation.errors)
    (output_dir / "latest.html").unlink(missing_ok=True)
    payload = _build_failed_payload(
        symbol=symbol,
        now=now,
        error_type="validation_failed",
        error_message=error_message,
        slim=slim,
        analyst_quality=analyst_quality,
        analyst_ratings_summary=analyst_ratings_summary,
        recent_analyst_actions=recent_analyst_actions,
        recent_ibkr_news=recent_ibkr_news,
        recent_ibkr_news_events=recent_ibkr_news_events,
    )
    failed_json_path = output_dir / "latest.failed.json"
    latest_json_path = output_dir / "latest.json"
    _write_json(failed_json_path, payload)
    _write_json(latest_json_path, payload)

    _write_json(
        logs_dir / f"{timestamp}.validate.json",
        {
            "symbol": symbol,
            "generated_at": now.isoformat(),
            "analysis_status": "failed",
            "latest_failed_json_path": str(failed_json_path),
            "latest_json_path": str(latest_json_path),
            "analyst_consensus_quality": analyst_quality,
            "analyst_ratings_summary": analyst_ratings_summary,
            "validation": validation.to_dict(),
        },
    )

    print(f"Validation FAILED for {symbol}.")
    print(f"Errors: {error_message}")
    print(f"Failed JSON: {failed_json_path}")

    stale_latest_json = output_dir / "latest.json"
    if stale_latest_json.exists():
        print(
            "Warning: output latest.json already exists from a previous run; "
            f"review it before using it: {stale_latest_json}"
        )

    return 1


def _generate(
    repo_root: Path,
    symbol: str,
    *,
    model: str = DEFAULT_CODEX_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    execution_context: str = "individual",
    analysis_kind: str = "reference",
    reference_tier: str = "priority",
    owned: bool = False,
    generation_provider: str = DEFAULT_GENERATION_PROVIDER,
    chatgpt_browser_headed: bool = False,
    chatgpt_browser_max_attempts: int = DEFAULT_CHATGPT_BROWSER_MAX_ATTEMPTS,
    generator_fallback: bool = True,
    chatgpt_browser_session: ChatGPTBrowserSession | None = None,
) -> int:
    output_dir = repo_root / "output" / symbol
    codex_input_path = output_dir / "codex_input.md"
    previous_analysis_path = output_dir / "previous_analysis.md"
    latest_md_path = output_dir / "latest.md"

    if generation_provider == "chatgpt-browser":
        chatgpt_input_path = output_dir / "chatgpt_input.md"
        chatgpt_input_path.write_text(
            build_chatgpt_web_input(codex_input_path.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        try:
            result = generate_markdown_with_chatgpt_browser(
                input_path=chatgpt_input_path,
                previous_analysis_path=(
                    previous_analysis_path if previous_analysis_path.exists() else None
                ),
                output_path=latest_md_path,
                cwd=repo_root,
                symbol=symbol,
                headed=chatgpt_browser_headed,
                max_attempts=chatgpt_browser_max_attempts,
                session=chatgpt_browser_session,
            )
        except RuntimeError as exc:
            if not generator_fallback:
                raise
            if execution_context == "batch" and (
                "chatgpt_human_verification_required" in str(exc)
                or "chatgpt_account_load_failed" in str(exc)
                or "chatgpt_no_healthy_browser_workers" in str(exc)
                or "chatgpt_project_not_open" in str(exc)
                or "chatgpt_project_context_not_confirmed" in str(exc)
                or getattr(chatgpt_browser_session, "worker_count", 1) == 0
            ):
                # Browser authentication or project navigation failures can
                # affect the whole worker pool. Do not hide them behind a
                # fallback for every queued ticker.
                raise
            fallback_error = str(exc)
            failed_web_metadata = _load_generation_metadata(output_dir)
            fallback_input_path = output_dir / "codex_fallback_input.md"
            fallback_policy = ""
            if execution_context == "batch" and analysis_kind == "daily":
                fallback_policy = _analysis_policy_prompt(
                    execution_context=execution_context,
                    analysis_kind=analysis_kind,
                    reference_tier=reference_tier,
                    owned=owned,
                    reference_found=True,
                    generation_model=model,
                    web_sol_authoritative=False,
                )
            fallback_input_path.write_text(
                _build_codex_fallback_input(
                    codex_input_path.read_text(encoding="utf-8"),
                    fallback_error,
                    analysis_policy_override=fallback_policy,
                ),
                encoding="utf-8",
            )
            result = generate_markdown_with_codex(
                input_path=fallback_input_path,
                output_path=latest_md_path,
                cwd=repo_root,
                model=model,
                reasoning_effort=reasoning_effort,
            )
            _write_json(
                output_dir / "generation_metadata.json",
                {
                    **failed_web_metadata,
                    "provider_requested": "chatgpt-browser",
                    "provider_used": "codex",
                    "fallback_error": fallback_error,
                    "web_timing_seconds": failed_web_metadata.get(
                        "web_timing_seconds", {}
                    ),
                    "symbol": symbol,
                    "generated_at": _utc_now().isoformat(),
                    "output_path": str(latest_md_path),
                    "status": "ok_fallback",
                },
            )
            print(f"ChatGPT browser failed; Codex fallback used: {fallback_error}")
    else:
        result = generate_markdown_with_codex(
            input_path=codex_input_path,
            output_path=latest_md_path,
            cwd=repo_root,
            model=model,
            reasoning_effort=reasoning_effort,
        )
        _write_json(
            output_dir / "generation_metadata.json",
            {
                "provider_requested": "codex",
                "provider_used": "codex",
                "symbol": symbol,
                "generated_at": _utc_now().isoformat(),
                "output_path": str(latest_md_path),
                "status": "ok",
            },
        )

    print(f"Generated markdown for {symbol}: {result.output_path}")

    return 0


def _build_codex_fallback_input(
    source_text: str,
    browser_error: str,
    *,
    analysis_policy_override: str = "",
) -> str:
    policy = ""
    if analysis_policy_override.strip():
        policy = (
            "\n\n# Mandatory Codex fallback analysis policy\n\n"
            "The provider is now Codex. The Web-authoritative policy in the "
            "original input no longer applies. Follow this replacement policy; "
            "it takes precedence over the original provider policy.\n\n"
            f"{analysis_policy_override.strip()}\n"
        )
    return (
        f"{source_text.rstrip()}\n\n"
        "# Mandatory fallback correction\n\n"
        "ChatGPT Web did not produce a valid report. The exact failure is included "
        "below. Generate the complete report again from the beginning and ensure "
        "the final markdown fixes every listed error. Do not describe the correction; "
        "return only the complete final report.\n\n"
        f"- {browser_error.strip()}\n"
        f"{policy}"
    )


def _ensure_ibkr_gateway_phase(repo_root: Path) -> int:
    ensure_gateway(repo_root)
    return 0


def _run_preflight_updates(repo_root: Path, symbol: str, *, capture_dir: Path | None = None,
                           capture_max_age_seconds: float | None = None) -> int:
    if capture_dir is not None and capture_max_age_seconds is None:
        raise ValueError("news_capture_max_age_required")
    steps = (
        (
            "analyst_update",
            [
                sys.executable,
                "-m",
                "src.local_runner.update_analyst_ratings_batch",
                "--tickers",
                symbol,
            ],
        ),
        (
            "ibkr_news_update",
            [
                sys.executable,
                "-m",
                "src.local_runner.update_ibkr_news_batch",
                "--tickers",
                symbol,
                "--process-timeout",
                str(DEFAULT_NEWS_PROCESS_TIMEOUT),
            ],
        ),
    )

    for name, command in steps:
        if capture_dir is not None:
            command += ["--capture-dir", str(capture_dir.resolve()),
                        "--capture-max-age-seconds", str(capture_max_age_seconds)]
        completed = subprocess.run(
            command,
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode == 0:
            print(f"{name}: ok")
        else:
            detail = (
                (completed.stderr or "").strip()
                or (completed.stdout or "").strip()
                or f"exit_code={completed.returncode}"
            )
            if name == "ibkr_news_update":
                raise RuntimeError(
                    "ibkr_news_update_failed_after_gateway_restart: "
                    f"{detail[:500]}"
                )
            print(f"{name}: failed_non_blocking: {detail[:240]}")

    return 0


def _finalize_real(
    repo_root: Path,
    symbol: str,
    *,
    model: str = DEFAULT_CODEX_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    execution_context: str = "individual",
    analysis_kind: str = "reference",
    reference_tier: str = "priority",
    owned: bool = False,
    generation_provider: str = DEFAULT_GENERATION_PROVIDER,
    validate_first: bool = True,
) -> int:
    """Finalize an already prepared and generated report without regenerating it."""
    run_started = _utc_now()
    run_log: dict[str, Any] = {
        "symbol": symbol,
        "started_at": run_started.isoformat(),
        "model": model,
        "reasoning_effort": reasoning_effort,
        "execution_context": execution_context,
        "analysis_kind": analysis_kind,
        "reference_tier": reference_tier,
        "owned": owned,
        "generation_provider_requested": generation_provider,
        "pipeline_stage": "finalize_real",
        "phases": [],
    }

    try:
        validate_status = 0
        if validate_first:
            validate_status = _run_full_phase(
                run_log,
                "validate",
                lambda: _validate(
                    repo_root,
                    symbol,
                    execution_context=execution_context,
                    analysis_kind=analysis_kind,
                    reference_tier=reference_tier,
                    owned=owned,
                    generation_model=model,
                    reasoning_effort=reasoning_effort,
                    generation_provider=generation_provider,
                ),
            )
        latest_json = _load_latest_json(repo_root, symbol)
        if validate_status != 0 or latest_json.get("analysis_status") != "ok":
            if not validate_first:
                raise RuntimeError(
                    "publish_requires_validated_analysis: "
                    "latest.json must have analysis_status='ok'"
                )
            _run_full_phase(
                run_log,
                "upload_failed_validation",
                lambda: _upload(
                    repo_root=repo_root,
                    symbol=symbol,
                    upload_kind="real",
                    dry_run=False,
                ),
            )
            error_type, error_message = _failed_summary(latest_json)
            _finish_run_full_log(repo_root, symbol, run_log, "failed")
            print(f"FAILED {symbol}: {error_type} - {error_message}")
            return validate_status or 1

        if execution_context == "batch" and analysis_kind == "daily":
            _run_full_phase(
                run_log,
                "daily_authority_policy",
                lambda: _apply_daily_candidate_policy(
                    repo_root=repo_root,
                    symbol=symbol,
                    generation_model=model,
                    reasoning_effort=reasoning_effort,
                    reference_tier=reference_tier,
                    owned=owned,
                ),
            )
            daily_payload = _load_latest_json(repo_root, symbol)
            daily_workflow = daily_payload.get("analysis_workflow")
            if isinstance(daily_workflow, dict):
                daily_status = daily_workflow.get("status")
                if daily_status == "escalation_required":
                    _finish_run_full_log(
                        repo_root, symbol, run_log, "escalation_required"
                    )
                    print(f"ESCALATE {symbol}: revision superior requerida.")
                    return 0
                if daily_status == "reference_retained_low_confidence":
                    print(
                        f"RETAIN {symbol}: seguimiento actualizado; "
                        "se conserva la referencia vigente."
                    )

        upload_status = _run_full_phase(
            run_log,
            "upload_real",
            lambda: _upload(
                repo_root=repo_root,
                symbol=symbol,
                upload_kind="real",
                dry_run=False,
            ),
        )

        authority_payload = _load_latest_json(repo_root, symbol)
        if _should_save_authoritative_reference(
            execution_context=execution_context,
            analysis_kind=analysis_kind,
            payload=authority_payload,
        ):
            workflow = authority_payload.get("analysis_workflow")
            web_authoritative = (
                isinstance(workflow, dict)
                and workflow.get("web_sol_authoritative") is True
            )
            _run_full_phase(
                run_log,
                "save_authoritative_reference",
                lambda: _save_authoritative_reference(
                    repo_root=repo_root,
                    symbol=symbol,
                    generation_model=SOL_MODEL if web_authoritative else model,
                    reasoning_effort="high" if web_authoritative else reasoning_effort,
                    reference_tier=reference_tier,
                    owned=owned,
                ),
            )

        _finish_run_full_log(repo_root, symbol, run_log, "ok")
        print(f"OK {symbol}: analisis validado y subido.")
        return upload_status
    except Exception as exc:
        run_log["error_type"] = "runtime_error"
        run_log["error_message"] = str(exc)
        _finish_run_full_log(repo_root, symbol, run_log, "failed")
        print(f"FAILED {symbol}: runtime_error - {exc}")
        return 1


def _run_full(
    repo_root: Path,
    symbol: str,
    *,
    skip_preflight_updates: bool = False,
    skip_ibkr_gateway_ensure: bool = False,
    model: str = DEFAULT_CODEX_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    execution_context: str = "individual",
    analysis_kind: str = "reference",
    reference_tier: str = "priority",
    owned: bool = False,
    generation_provider: str = DEFAULT_GENERATION_PROVIDER,
    chatgpt_browser_headed: bool = False,
    chatgpt_browser_max_attempts: int = DEFAULT_CHATGPT_BROWSER_MAX_ATTEMPTS,
    generator_fallback: bool = True,
    chatgpt_browser_session: ChatGPTBrowserSession | None = None,
) -> int:
    run_started = _utc_now()
    run_log: dict[str, Any] = {
        "symbol": symbol,
        "started_at": run_started.isoformat(),
        "model": model,
        "reasoning_effort": reasoning_effort,
        "execution_context": execution_context,
        "analysis_kind": analysis_kind,
        "reference_tier": reference_tier,
        "owned": owned,
        "generation_provider_requested": generation_provider,
        "phases": [],
    }

    try:
        if not skip_ibkr_gateway_ensure:
            _run_full_phase(
                run_log,
                "ensure_ibkr_gateway",
                lambda: _ensure_ibkr_gateway_phase(repo_root),
            )
        if not skip_preflight_updates:
            _run_full_phase(
                run_log,
                "preflight_updates",
                lambda: _run_preflight_updates(repo_root, symbol),
            )
        _run_full_phase(
            run_log,
            "prepare",
            lambda: _prepare(
                repo_root,
                symbol,
                execution_context=execution_context,
                analysis_kind=analysis_kind,
                reference_tier=reference_tier,
                owned=owned,
                generation_model=model,
                generation_provider=generation_provider,
            ),
        )
        _run_full_phase(
            run_log,
            "generate",
            lambda: _generate(
                repo_root,
                symbol,
                model=model,
                reasoning_effort=reasoning_effort,
                execution_context=execution_context,
                analysis_kind=analysis_kind,
                reference_tier=reference_tier,
                owned=owned,
                generation_provider=generation_provider,
                chatgpt_browser_headed=chatgpt_browser_headed,
                chatgpt_browser_max_attempts=chatgpt_browser_max_attempts,
                generator_fallback=generator_fallback,
                chatgpt_browser_session=chatgpt_browser_session,
            ),
        )
        validate_status = _run_full_phase(
            run_log,
            "validate",
            lambda: _validate(
                repo_root,
                symbol,
                execution_context=execution_context,
                analysis_kind=analysis_kind,
                reference_tier=reference_tier,
                owned=owned,
                generation_model=model,
                reasoning_effort=reasoning_effort,
                generation_provider=generation_provider,
            ),
        )
        latest_json = _load_latest_json(repo_root, symbol)
        if validate_status != 0 or latest_json.get("analysis_status") != "ok":
            _run_full_phase(
                run_log,
                "upload_failed_validation",
                lambda: _upload(
                    repo_root=repo_root,
                    symbol=symbol,
                    upload_kind="real",
                    dry_run=False,
                ),
            )
            error_type, error_message = _failed_summary(latest_json)
            _finish_run_full_log(repo_root, symbol, run_log, "failed")
            print(f"FAILED {symbol}: {error_type} - {error_message}")
            return validate_status or 1

        if execution_context == "batch" and analysis_kind == "daily":
            _run_full_phase(
                run_log,
                "daily_authority_policy",
                lambda: _apply_daily_candidate_policy(
                    repo_root=repo_root,
                    symbol=symbol,
                    generation_model=model,
                    reasoning_effort=reasoning_effort,
                    reference_tier=reference_tier,
                    owned=owned,
                ),
            )
            daily_payload = _load_latest_json(repo_root, symbol)
            daily_workflow = daily_payload.get("analysis_workflow")
            if isinstance(daily_workflow, dict):
                daily_status = daily_workflow.get("status")
                if daily_status == "escalation_required":
                    _finish_run_full_log(repo_root, symbol, run_log, "escalation_required")
                    print(f"ESCALATE {symbol}: revisión superior requerida.")
                    return 0
                if daily_status == "reference_retained_low_confidence":
                    print(
                        f"RETAIN {symbol}: seguimiento actualizado; "
                        "se conserva la referencia vigente."
                    )

        upload_status = _run_full_phase(
            run_log,
            "upload_real",
            lambda: _upload(
                repo_root=repo_root,
                symbol=symbol,
                upload_kind="real",
                dry_run=False,
            ),
        )

        latest_json = _load_latest_json(repo_root, symbol)
        analysis_status = latest_json.get("analysis_status")

        if validate_status != 0 or analysis_status != "ok":
            error_type, error_message = _failed_summary(latest_json)
            _finish_run_full_log(repo_root, symbol, run_log, "failed")
            print(f"FAILED {symbol}: {error_type} - {error_message}")
            return validate_status or 1

        authority_payload = _load_latest_json(repo_root, symbol)
        if _should_save_authoritative_reference(
            execution_context=execution_context,
            analysis_kind=analysis_kind,
            payload=authority_payload,
        ):
            workflow = authority_payload.get("analysis_workflow")
            web_authoritative = (
                isinstance(workflow, dict)
                and workflow.get("web_sol_authoritative") is True
            )
            _run_full_phase(
                run_log,
                "save_authoritative_reference",
                lambda: _save_authoritative_reference(
                    repo_root=repo_root,
                    symbol=symbol,
                    generation_model=SOL_MODEL if web_authoritative else model,
                    reasoning_effort="high" if web_authoritative else reasoning_effort,
                    reference_tier=reference_tier,
                    owned=owned,
                ),
            )

        _finish_run_full_log(repo_root, symbol, run_log, "ok")
        print(f"OK {symbol}: análisis generado y subido.")
        return upload_status
    except Exception as exc:
        run_log["error_type"] = "runtime_error"
        run_log["error_message"] = str(exc)
        _finish_run_full_log(repo_root, symbol, run_log, "failed")
        print(f"FAILED {symbol}: runtime_error - {exc}")
        return 1


_ESCALATION_COMMENT_RE = re.compile(
    r"<!--\s*ANALYSIS_ESCALATION\s+(\{.*?\})\s*-->",
    re.IGNORECASE | re.DOTALL,
)
_ALLOWED_ESCALATION_REASONS = {
    "score_change",
    "high_impact_catalyst",
    "thesis_narrative",
    "structural_technical",
}
_CONFIDENCE_REVIEW_MIN = 65.0
_STRUCTURAL_CONFIDENCE_REVIEW_MIN = 60.0
_CONFIDENCE_DIRECT_MIN = 85.0
_CONFIDENCE_AUDIT_RATE = 0.10
_EVIDENCE_CONFIDENCE_CAPS = {
    "none": 64.0,
    "weak": 74.0,
}


def _apply_daily_candidate_policy(
    *,
    repo_root: Path,
    symbol: str,
    generation_model: str,
    reasoning_effort: str,
    reference_tier: str,
    owned: bool,
) -> int:
    output_dir = repo_root / "output" / symbol
    latest_md_path = output_dir / "latest.md"
    latest_json_path = output_dir / "latest.json"
    latest_html_path = output_dir / "latest.html"
    candidate_md_path = output_dir / "candidate.md"
    candidate_json_path = output_dir / "candidate.json"
    candidate_html_path = output_dir / "candidate.html"
    shutil.copy2(latest_md_path, candidate_md_path)
    shutil.copy2(latest_json_path, candidate_json_path)
    if latest_html_path.exists():
        shutil.copy2(latest_html_path, candidate_html_path)

    payload = _load_latest_json(repo_root, symbol)
    web_sol_authoritative = payload.get("generation_provider") == "chatgpt-browser"
    reference = load_authoritative_reference_context(symbol)
    if not reference.found:
        raise RuntimeError("daily_analysis_requires_authoritative_reference")
    proposed_score = extract_score(candidate_md_path.read_text(encoding="utf-8"))
    reference_score = extract_score(reference.analysis_markdown)
    score_migration = (
        extract_dimension_score(candidate_md_path.read_text(encoding="utf-8"), "Tesis") is not None
        and extract_dimension_score(reference.analysis_markdown, "Tesis") is None
    )
    if web_sol_authoritative:
        confidence = {
            "decision": "direct_publish",
            "material_change": None,
            "candidate_applies_material_change": None,
            "reasons": [],
            "urgent_risk": False,
            "reference_invalidation_confidence": None,
            "replacement_confidence": None,
            "raw_effective_confidence": None,
            "effective_confidence": None,
            "evidence_quality": "not_required",
            "independent_support": None,
            "confidence_cap_applied": False,
            "previous_conclusion": "",
            "invalidation_evidence": "",
            "proposed_replacement": "",
            "strongest_counterargument": "",
            "evidence_to_keep_reference": "",
        }
    else:
        confidence = _daily_confidence_decision(candidate_md_path)
        if score_migration:
            # An old mixed score cannot be locked into the new thesis field.
            confidence["decision"] = "review"
            confidence["material_change"] = True
            confidence["reasons"] = list(dict.fromkeys([*confidence["reasons"], "score_change"]))
    reasons = confidence["reasons"]
    gate_decision = confidence["decision"]
    if (
        not web_sol_authoritative
        and generation_model == LUNA_MODEL
        and not score_migration
        and confidence["material_change"]
    ):
        if (
            confidence["urgent_risk"]
            or confidence["effective_confidence"] >= _CONFIDENCE_REVIEW_MIN
        ):
            if not confidence["candidate_applies_material_change"]:
                raise RuntimeError("luna_review_candidate_missing_material_change")
            gate_decision = "review"
        else:
            if confidence["candidate_applies_material_change"]:
                raise RuntimeError("luna_low_confidence_change_must_not_be_applied")
            gate_decision = "publish_reference_aligned"
    confidence_audit_selected = (
        not web_sol_authoritative
        and gate_decision == "direct_publish"
        and _confidence_audit_selected(symbol)
    )
    decision = "confidence_audit" if confidence_audit_selected else gate_decision
    status_by_decision = {
        "no_material_change": "published_score_locked",
        "publish_reference_aligned": "published_reference_aligned_low_confidence",
        "direct_publish": "published_high_confidence_score_locked",
        "review": "escalation_required",
        "confidence_audit": "escalation_required",
        "retain_reference": "reference_retained_low_confidence",
    }
    workflow_status = (
        "published_web_sol_authoritative"
        if web_sol_authoritative and decision == "direct_publish"
        else status_by_decision[decision]
    )
    workflow = {
        "policy_version": 3,
        "candidate_model": SOL_MODEL if web_sol_authoritative else generation_model,
        "generation_provider": payload.get("generation_provider"),
        "web_sol_authoritative": web_sol_authoritative,
        "model_policy": (
            "web_sol_authoritative"
            if web_sol_authoritative
            else "luna_guarded"
            if generation_model == LUNA_MODEL
            else "standard_confidence"
        ),
        "status": workflow_status,
        "decision": decision,
        "confidence_gate_decision": gate_decision,
        "confidence_audit_selected": confidence_audit_selected,
        "confidence_audit_rate": _CONFIDENCE_AUDIT_RATE,
        "reference_score": reference_score,
        "proposed_score": proposed_score,
        "published_score": (
            proposed_score
            if web_sol_authoritative or reference_score is None
            else reference_score
        ),
        "official_score_locked": not web_sol_authoritative,
        "score_review_requested": (
            decision in {"review", "confidence_audit"}
            and "score_change" in reasons
        ),
        "material_change": confidence["material_change"],
        "candidate_applies_material_change": confidence[
            "candidate_applies_material_change"
        ],
        "material_change_reasons": reasons,
        "escalation_reasons": (
            reasons if decision in {"review", "confidence_audit"} else []
        ),
        "urgent_risk": confidence["urgent_risk"],
        "reference_invalidation_confidence": confidence[
            "reference_invalidation_confidence"
        ],
        "replacement_confidence": confidence["replacement_confidence"],
        "raw_effective_confidence": confidence["raw_effective_confidence"],
        "effective_confidence": confidence["effective_confidence"],
        "evidence_quality": confidence["evidence_quality"],
        "independent_support": confidence["independent_support"],
        "confidence_cap_applied": confidence["confidence_cap_applied"],
        "previous_conclusion": confidence["previous_conclusion"],
        "invalidation_evidence": confidence["invalidation_evidence"],
        "proposed_replacement": confidence["proposed_replacement"],
        "strongest_counterargument": confidence["strongest_counterargument"],
        "evidence_to_keep_reference": confidence["evidence_to_keep_reference"],
        "candidate_markdown_path": str(candidate_md_path),
        "reference_generated_at": reference.generated_at,
    }
    candidate_payload = dict(payload)
    candidate_payload["analysis_workflow"] = workflow
    _write_json(candidate_json_path, candidate_payload)

    if decision in {"review", "confidence_audit"}:
        payload["analysis_workflow"] = workflow
        _write_json(latest_json_path, payload)
        return 0

    if decision == "retain_reference":
        _publish_reference_retained_followup(
            repo_root=repo_root,
            symbol=symbol,
            reference=reference,
            workflow=workflow,
            candidate_payload=candidate_payload,
            generation_model=generation_model,
            reasoning_effort=reasoning_effort,
            reference_tier=reference_tier,
            owned=owned,
        )
        return 0

    if reference_score is None:
        raise RuntimeError("authoritative_reference_score_missing")
    candidate_markdown = candidate_md_path.read_text(encoding="utf-8")
    publishable_markdown = _ESCALATION_COMMENT_RE.sub("", candidate_markdown).rstrip() + "\n"
    final_markdown = (
        publishable_markdown
        if web_sol_authoritative
        else _replace_report_score(publishable_markdown, reference_score)
    )
    latest_md_path.write_text(final_markdown, encoding="utf-8")
    status = _validate(
        repo_root,
        symbol,
        execution_context="batch",
        analysis_kind="daily",
        reference_tier=reference_tier,
        owned=owned,
        generation_model=generation_model,
        reasoning_effort=reasoning_effort,
    )
    if status != 0:
        _upload(
            repo_root=repo_root,
            symbol=symbol,
            upload_kind="real",
            dry_run=False,
        )
        raise RuntimeError("score_locked_candidate_validation_failed")
    payload = _load_latest_json(repo_root, symbol)
    payload["analysis_workflow"] = workflow
    _write_json(latest_json_path, payload)
    return 0


def _daily_escalation_reasons(payload: dict[str, Any], candidate_path: Path) -> list[str]:
    del payload  # The reviewing model is authoritative about material changes.
    decision = _daily_confidence_decision(candidate_path)
    return decision["reasons"] if decision["decision"] == "review" else []


def _daily_confidence_decision(candidate_path: Path) -> dict[str, Any]:
    marker = _parse_escalation_marker(candidate_path.read_text(encoding="utf-8"))
    if not marker or not isinstance(marker.get("material_change"), bool):
        raise RuntimeError("daily_confidence_marker_missing_or_invalid")

    material_change = marker["material_change"]
    candidate_applies_material_change = marker.get(
        "candidate_applies_material_change"
    )
    urgent_risk = marker.get("urgent_risk")
    independent_support = marker.get("independent_support")
    if (
        not isinstance(candidate_applies_material_change, bool)
        or not isinstance(urgent_risk, bool)
        or not isinstance(independent_support, bool)
    ):
        raise RuntimeError("daily_confidence_marker_missing_or_invalid")

    raw_reasons = marker.get("reasons")
    if not isinstance(raw_reasons, list):
        raise RuntimeError("daily_confidence_marker_missing_or_invalid")
    reasons = sorted({str(reason) for reason in raw_reasons})
    if any(reason not in _ALLOWED_ESCALATION_REASONS for reason in reasons):
        raise RuntimeError("daily_confidence_marker_unknown_reason")
    if material_change != bool(reasons):
        raise RuntimeError("daily_confidence_marker_reason_mismatch")
    if urgent_risk and not material_change:
        raise RuntimeError("daily_confidence_marker_urgent_without_change")
    if candidate_applies_material_change and not material_change:
        raise RuntimeError("daily_confidence_marker_applied_without_change")

    invalidation_confidence = _confidence_value(
        marker.get("reference_invalidation_confidence"),
        "reference_invalidation_confidence",
    )
    replacement_confidence = _confidence_value(
        marker.get("replacement_confidence"),
        "replacement_confidence",
    )
    evidence_quality = marker.get("evidence_quality")
    if evidence_quality not in {"none", "weak", "strong"}:
        raise RuntimeError("daily_confidence_marker_invalid_evidence_quality")

    text_fields = {
        key: str(marker.get(key) or "").strip()
        for key in (
            "previous_conclusion",
            "invalidation_evidence",
            "proposed_replacement",
            "strongest_counterargument",
            "evidence_to_keep_reference",
        )
    }
    if material_change and any(not value for value in text_fields.values()):
        raise RuntimeError("daily_confidence_marker_missing_material_evidence")

    if not material_change:
        return {
            "decision": "no_material_change",
            "material_change": False,
            "candidate_applies_material_change": False,
            "reasons": [],
            "urgent_risk": False,
            "reference_invalidation_confidence": invalidation_confidence,
            "replacement_confidence": replacement_confidence,
            "raw_effective_confidence": 0.0,
            "effective_confidence": 0.0,
            "evidence_quality": evidence_quality,
            "independent_support": independent_support,
            "confidence_cap_applied": None,
            **text_fields,
        }

    raw_effective = min(invalidation_confidence, replacement_confidence)
    confidence_cap = _EVIDENCE_CONFIDENCE_CAPS.get(str(evidence_quality))
    if evidence_quality == "strong" and not independent_support:
        confidence_cap = 84.0
    effective = min(raw_effective, confidence_cap) if confidence_cap else raw_effective

    structural_review = (
        "structural_technical" in reasons
        and evidence_quality == "strong"
        and effective >= _STRUCTURAL_CONFIDENCE_REVIEW_MIN
    )

    if urgent_risk:
        decision = "review"
    elif effective >= _CONFIDENCE_DIRECT_MIN:
        decision = "direct_publish"
    elif structural_review:
        decision = "review"
    elif effective >= _CONFIDENCE_REVIEW_MIN:
        decision = "review"
    else:
        decision = "retain_reference"

    return {
        "decision": decision,
        "material_change": True,
        "candidate_applies_material_change": candidate_applies_material_change,
        "reasons": reasons,
        "urgent_risk": urgent_risk,
        "reference_invalidation_confidence": invalidation_confidence,
        "replacement_confidence": replacement_confidence,
        "raw_effective_confidence": raw_effective,
        "effective_confidence": effective,
        "evidence_quality": evidence_quality,
        "independent_support": independent_support,
        "confidence_cap_applied": confidence_cap if effective < raw_effective else None,
        "structural_review_threshold_applied": structural_review,
        **text_fields,
    }


def _publish_reference_retained_followup(
    *,
    repo_root: Path,
    symbol: str,
    reference: Any,
    workflow: dict[str, Any],
    candidate_payload: dict[str, Any],
    generation_model: str,
    reasoning_effort: str,
    reference_tier: str,
    owned: bool,
) -> None:
    output_dir = repo_root / "output" / symbol
    candidate_md_path = output_dir / "candidate.md"
    candidate_json_path = output_dir / "candidate.json"
    candidate_html_path = output_dir / "candidate.html"
    generated_at = str(candidate_payload.get("generated_at") or _utc_now().isoformat())
    archive_stamp = re.sub(r"[^0-9A-Za-z_-]", "-", generated_at)
    archive_dir = output_dir / "retained_candidates" / archive_stamp
    archive_dir.mkdir(parents=True, exist_ok=True)
    for source in (candidate_md_path, candidate_json_path, candidate_html_path):
        if source.exists():
            shutil.copy2(source, archive_dir / source.name)

    reference_date = _display_analysis_date(reference.generated_at)
    followup_date = _display_analysis_date(generated_at)
    decision = candidate_payload.get("decision")
    price = decision.get("reference_price") if isinstance(decision, dict) else None
    price_text = f"${float(price):.2f}" if isinstance(price, (int, float)) else "no disponible"
    reasons = ", ".join(workflow.get("material_change_reasons") or []) or "sin cambio material confirmado"
    effective = workflow.get("effective_confidence")
    confidence_text = f"{float(effective):.0f}%" if isinstance(effective, (int, float)) else "no disponible"

    followup = (
        f"# {symbol}\n\n"
        f"Fecha del análisis: {followup_date}\n\n"
        f"Precio de referencia actual: **{price_text}**\n\n"
        "> ⚠ **Seguimiento actualizado — no sustituye la referencia oficial.** "
        f"La nota y los niveles oficiales siguen correspondiendo al informe del {reference_date}.\n\n"
        "## Seguimiento actual\n\n"
        f"- **Decisión:** conservar la referencia oficial.\n"
        f"- **Confianza efectiva del cambio propuesto:** {confidence_text}.\n"
        f"- **Motivos examinados:** {reasons}.\n"
        f"- **Evidencia para invalidar lo anterior:** {workflow.get('invalidation_evidence') or 'No concluyente.'}\n"
        f"- **Principal argumento para conservarlo:** {workflow.get('evidence_to_keep_reference') or workflow.get('strongest_counterargument') or 'No se confirmó una sustitución superior.'}\n\n"
        "---\n\n"
        f"## Referencia oficial vigente · {reference_date}\n\n"
        f"{reference.analysis_markdown.strip()}\n"
    )
    latest_md_path = output_dir / "latest.md"
    latest_md_path.write_text(followup, encoding="utf-8")
    status = _validate(
        repo_root,
        symbol,
        execution_context="batch",
        analysis_kind="daily",
        reference_tier=reference_tier,
        owned=owned,
        generation_model=generation_model,
        reasoning_effort=reasoning_effort,
    )
    if status != 0:
        raise RuntimeError("reference_retained_followup_validation_failed")
    latest_payload = _load_latest_json(repo_root, symbol)
    workflow["followup_generated_at"] = latest_payload.get("generated_at")
    workflow["sheet_warning"] = "reference_retained"
    latest_payload["analysis_workflow"] = workflow
    _write_json(output_dir / "latest.json", latest_payload)


def _display_analysis_date(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "fecha desconocida"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value[:10]
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(MADRID_TZ).strftime("%d-%m-%Y")


def _confidence_value(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"daily_confidence_marker_invalid_{field}")
    normalized = float(value)
    if not 0.0 <= normalized <= 100.0:
        raise RuntimeError(f"daily_confidence_marker_invalid_{field}")
    return normalized


def _confidence_audit_selected(
    symbol: str,
    *,
    on_date: str | None = None,
    rate: float = _CONFIDENCE_AUDIT_RATE,
) -> bool:
    if rate <= 0:
        return False
    if rate >= 1:
        return True
    audit_date = on_date or datetime.now().astimezone().date().isoformat()
    digest = hashlib.sha256(
        f"confidence-v2:{audit_date}:{symbol.strip().upper()}".encode("utf-8")
    ).digest()
    sample = int.from_bytes(digest[:8], "big") / float(2**64)
    return sample < rate


def _parse_escalation_marker(markdown: str) -> dict[str, Any]:
    match = _ESCALATION_COMMENT_RE.search(markdown)
    if not match:
        return {}
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _replace_report_score(markdown: str, score: float) -> str:
    pattern = re.compile(
        r"(?im)^(\s*.*?(?:Tesis|Valoraci[oó]n)(?:\*\*)?\s*:\s*(?:\*\*)?)"
        r"[0-9]+(?:[.,][0-9]+)?(\s*/\s*10.*)$"
    )
    replacement = rf"\g<1>{score:.1f}\g<2>"
    updated, count = pattern.subn(replacement, markdown, count=1)
    if count != 1:
        raise RuntimeError("official_score_lock_failed: valuation_line_not_found")
    return updated


def _should_save_authoritative_reference(
    *,
    execution_context: str,
    analysis_kind: str,
    payload: dict[str, Any],
) -> bool:
    if execution_context == "individual" or analysis_kind in {"reference", "review"}:
        return True
    workflow = payload.get("analysis_workflow")
    return bool(
        execution_context == "batch"
        and analysis_kind == "daily"
        and isinstance(workflow, dict)
        and workflow.get("web_sol_authoritative") is True
        and workflow.get("status") == "published_web_sol_authoritative"
    )


def _save_authoritative_reference(
    *,
    repo_root: Path,
    symbol: str,
    generation_model: str,
    reasoning_effort: str,
    reference_tier: str,
    owned: bool,
) -> int:
    payload = _load_latest_json(repo_root, symbol)
    if payload.get("analysis_status") != "ok":
        raise RuntimeError("cannot_save_failed_reference")
    score = extract_score(str(payload.get("analysis_markdown") or ""))
    previous_reference = load_reference_payload(symbol) or {}
    previous_tier = previous_reference.get("reference_tier")
    effective_tier = reference_tier
    if owned:
        effective_tier = "priority"
    elif isinstance(score, (int, float)):
        if score < 6.5:
            effective_tier = "tracking"
        elif score >= 7.0 and generation_model == SOL_MODEL:
            effective_tier = "priority"
        elif 6.5 <= score < 7.0 and previous_tier in {"priority", "tracking"}:
            effective_tier = str(previous_tier)
    payload.update(
        {
            "reference_model": generation_model,
            "reference_reasoning_effort": reasoning_effort,
            "reference_generated_at": payload.get("generated_at"),
            "reference_score": score,
            "reference_tier": effective_tier,
            "owned": owned,
        }
    )
    destination = save_reference_payload(repo_root, symbol, payload)
    print(f"Authoritative reference: {destination}")
    return 0


def _run_full_phase(
    run_log: dict[str, Any],
    phase_name: str,
    callback: Any,
) -> int:
    started = _utc_now()
    started_perf = time.perf_counter()
    stdout = io.StringIO()

    phase_log: dict[str, Any] = {
        "name": phase_name,
        "started_at": started.isoformat(),
    }

    try:
        with contextlib.redirect_stdout(stdout):
            exit_code = callback()
    except Exception as exc:
        finished = _utc_now()
        phase_log.update(
            {
                "finished_at": finished.isoformat(),
                "duration_seconds": round(time.perf_counter() - started_perf, 3),
                "status": "failed",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "stdout": stdout.getvalue(),
            }
        )
        run_log["phases"].append(phase_log)
        raise

    finished = _utc_now()
    phase_log.update(
        {
            "finished_at": finished.isoformat(),
            "duration_seconds": round(time.perf_counter() - started_perf, 3),
            "status": "ok" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "stdout": stdout.getvalue(),
        }
    )
    run_log["phases"].append(phase_log)

    return exit_code


def _finish_run_full_log(
    repo_root: Path,
    symbol: str,
    run_log: dict[str, Any],
    status: str,
) -> None:
    finished = _utc_now()
    started_raw = run_log.get("started_at")

    try:
        started = datetime.fromisoformat(str(started_raw))
        duration_seconds = round((finished - started).total_seconds(), 3)
    except ValueError:
        duration_seconds = None

    run_log.update(
        {
            "finished_at": finished.isoformat(),
            "duration_seconds": duration_seconds,
            "status": status,
        }
    )

    logs_dir = repo_root / "logs" / symbol
    logs_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        logs_dir / f"{_timestamp_for_file(finished)}.run_full.json",
        run_log,
    )


def _load_latest_json(repo_root: Path, symbol: str) -> dict[str, Any]:
    latest_json_path = repo_root / "output" / symbol / "latest.json"

    if not latest_json_path.exists():
        return {}

    try:
        payload = json.loads(latest_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    return payload if isinstance(payload, dict) else {}


def _failed_summary(latest_json: dict[str, Any]) -> tuple[str, str]:
    error_type = latest_json.get("error_type") or "analysis_failed"
    error_message = latest_json.get("error_message") or "analysis_status is not ok"

    return str(error_type), str(error_message)


def _upload(repo_root: Path, symbol: str, *, upload_kind: str, dry_run: bool) -> int:
    output_dir = repo_root / "output" / symbol
    latest_md_path = output_dir / "latest.md"
    latest_json_path = output_dir / "latest.json"
    latest_html_path = output_dir / "latest.html"

    if not latest_json_path.exists():
        raise RuntimeError(f"missing_latest_json: {latest_json_path}")

    try:
        latest_json = json.loads(latest_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid_latest_json: {latest_json_path}") from exc

    analysis_status = latest_json.get("analysis_status")

    if analysis_status not in ("ok", "failed"):
        raise RuntimeError(
            "upload_rejected: latest.json must have analysis_status='ok' or 'failed'; "
            f"found {analysis_status!r}"
        )

    if analysis_status == "ok" and not latest_md_path.exists():
        raise RuntimeError(f"missing_latest_md: {latest_md_path}")

    if analysis_status == "ok" and not latest_html_path.exists():
        raise RuntimeError(
            f"missing_latest_html: {latest_html_path}; run --validate first"
        )

    if upload_kind == "test":
        if analysis_status != "ok":
            raise RuntimeError(
                "test_upload_rejected: _local_test uploads require "
                f"analysis_status='ok'; found {analysis_status!r}"
            )

        plan = build_test_upload_plan(
            symbol=symbol,
            markdown_source=latest_md_path,
            html_source=latest_html_path,
            json_source=latest_json_path,
            dry_run=dry_run,
        )
    elif upload_kind == "real":
        date_part, time_part = _snapshot_parts(latest_json)
        plan = build_real_upload_plan(
            symbol=symbol,
            markdown_source=latest_md_path if analysis_status == "ok" else None,
            html_source=latest_html_path if analysis_status == "ok" else None,
            json_source=latest_json_path,
            analysis_status=analysis_status,
            timestamp_date=date_part,
            timestamp_time=time_part,
            dry_run=dry_run,
        )
    else:
        raise RuntimeError(f"unknown_upload_kind: {upload_kind}")

    commands = upload_artifacts(plan)

    if upload_kind == "real" and not dry_run:
        try:
            archive_result = maintain_report_archive(
                symbol=symbol,
                latest_json_path=latest_json_path,
                output_dir=output_dir,
                gcloud_path=plan.gcloud_path,
            )
            print(
                "Report archive maintained: "
                f"history_entries={archive_result['history_entries']}, "
                f"deleted_objects={archive_result['deleted_objects']}"
            )
        except Exception as exc:
            print(f"report_archive: failed_non_blocking: {exc}")

    mode = "DRY-RUN" if dry_run else "EXECUTED"
    label = "test" if upload_kind == "test" else "real"
    print(f"GCS {label} upload {mode} for {symbol}.")
    print(f"analysis_status={analysis_status}")

    for destination in plan.destinations:
        print(f"Destination: {destination}")

    for command in commands:
        print(format_command(command))

    return 0


def _fetch_slim(symbol: str, *, avwap_anchors=(), option_origins=(), support_origins=None, archive_root=None, archive_failure_path=None) -> dict[str, Any]:
    params = {'symbol': symbol}
    if avwap_anchors:
        params['avwap_anchors'] = ','.join(avwap_anchors)
    if option_origins:
        from src.local_runner.technical_preparation import encode_option_origins
        params['option_origins'] = encode_option_origins(option_origins)
    if support_origins is not None:
        from src.local_runner.support_origins import encode_support_origins
        params['support_origins'] = encode_support_origins(support_origins)
    if archive_root is not None:
        params['evaluation_archive'] = '1'
    url = f"{SLIM_BASE_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "stock-analysis-local/0.1"})

    from src.local_runner.technical_http import read_slim_response
    body = read_slim_response(request, opener=urlopen, request_timeout=REQUEST_TIMEOUT_SECONDS)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("slim_endpoint_invalid_json") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("slim_endpoint_unexpected_payload: expected JSON object")

    from src.local_runner.archive_technical_observations import extract_for_model
    import hashlib
    return extract_for_model(payload, archive_root=archive_root, symbol=symbol,
                             source_sha256=hashlib.sha256(body.encode('utf-8')).hexdigest(),
                             failure_path=archive_failure_path)


def _load_analyst_quality(
    repo_root: Path,
    symbol: str,
    slim: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    return load_analyst_quality_context(
        repo_root,
        symbol,
        current_price=slim.get("latest_price"),
        now=now,
    )


def _load_system_prompt(repo_root: Path) -> str:
    local_prompt_path = repo_root / LOCAL_SYSTEM_PROMPT_PATH

    if local_prompt_path.exists():
        prompt = local_prompt_path.read_text(encoding="utf-8").strip()

        if not prompt:
            raise RuntimeError(f"Local system prompt is empty: {local_prompt_path}")

        return prompt

    source_path = repo_root / "incoming_from_gcp" / "gemini_stock_analyze" / "main.py"

    if not source_path.exists():
        raise FileNotFoundError(f"Missing analysis source of truth: {source_path}")

    source = source_path.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(source_path))

    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue

        target_names = [
            target.id for target in node.targets if isinstance(target, ast.Name)
        ]

        if "SYSTEM_PROMPT" not in target_names:
            continue

        value = _literal_string_with_optional_strip(node.value)

        if not isinstance(value, str) or not value.strip():
            raise RuntimeError("SYSTEM_PROMPT is empty or not a string")

        return value.strip()

    raise RuntimeError(f"SYSTEM_PROMPT not found in {source_path}")


def _literal_string_with_optional_strip(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value

    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "strip"
        and not node.args
        and not node.keywords
        and isinstance(node.func.value, ast.Constant)
        and isinstance(node.func.value.value, str)
    ):
        return node.func.value.value.strip()

    raise RuntimeError("SYSTEM_PROMPT must be a string literal or literal.strip()")


def _analysis_policy_prompt(
    *,
    execution_context: str,
    analysis_kind: str,
    reference_tier: str,
    owned: bool,
    reference_found: bool,
    generation_model: str = DEFAULT_CODEX_MODEL,
    web_sol_authoritative: bool = False,
) -> str:
    if execution_context == "individual":
        return (
            "ANÁLISIS INDIVIDUAL AUTORITATIVO. Este informe se ejecuta con Sol y, "
            "si valida, sustituye la referencia vigente."
        )
    if analysis_kind == "review":
        return (
            "REVISIÓN SUPERIOR. Contrasta el candidato incluido con el informe "
            "autoritativo y con los datos vigentes. Conserva la referencia cuando la "
            "evidencia nueva no sea suficiente; cambia tesis, nota o estructura solo si "
            "puedes justificarlo de forma concreta. Tu informe validado será la nueva "
            "referencia autoritativa."
        )
    if analysis_kind == "reference":
        return (
            "NUEVA REFERENCIA AUTORITATIVA SEMANAL. Recalibra el informe completo "
            f"con evidencia vigente. Nivel={reference_tier}; owned={str(owned).lower()}."
        )
    if not reference_found:
        raise RuntimeError("daily_analysis_requires_authoritative_reference")
    if web_sol_authoritative:
        return """SEGUIMIENTO DIARIO AUTORITATIVO CON CHATGPT WEB SOL ALTO.
El informe completo anterior incluido arriba es la referencia oficial. Actualiza el informe
completo con los datos vigentes y cambia tesis, niveles o narrativa cuando la evidencia lo
justifique, respetando las reglas de continuidad. Tu respuesta validada se publica sin
revisión de otro modelo."""
    luna_policy = ""
    if generation_model == LUNA_MODEL:
        luna_policy = """

POLÍTICA ESPECÍFICA PARA LUNA.
Luna puede publicar por sí sola el seguimiento normal y los ajustes operativos bien
razonados que no sean cambios materiales. Luna nunca confirma por sí sola un cambio
material, aunque su confianza sea 85-100.
- Si la confianza efectiva del cambio material es menor de 65 y no hay urgencia, conserva
  en el cuerpo del informe la conclusión, tesis o nivel discutido de la referencia; actualiza
  normalmente el resto del informe y pon candidate_applies_material_change=false. Documenta
  la alternativa rechazada solo en el marcador o como señal pendiente, sin convertirla en
  la conclusión vigente.
- Si la confianza efectiva es 65 o más, o existe riesgo urgente, desarrolla el candidato,
  pon candidate_applies_material_change=true y solicita implícitamente revisión de Tierra;
  el sistema impedirá que ese candidato se publique antes de la revisión.
"""
    return f"""SEGUIMIENTO DIARIO CONTRA REFERENCIA AUTORITATIVA.
El informe completo anterior incluido arriba es la referencia oficial, no una sugerencia.
Razona expresamente contra ella antes de proponer cualquier cambio material. No cambies la
nota por estilo, humor del día, movimiento rutinario del precio ni cambio de categoría.
Puedes proponer otra nota en el formato normal del informe, pero el sistema conservará la
nota oficial hasta que la confirme un modelo superior. Estás autorizado a cambiar entrada,
entrada ambiciosa, objetivo y stops sin revisión superior cuando lo tengas claro. Para cada
nivel modificado, compara expresamente con el nivel anterior, explica la evidencia concreta
que lo invalida y justifica el nivel nuevo. Una recalibración operativa de niveles bien
razonada no requiere escalada por sí sola.

Al final del markdown añade exactamente un comentario HTML de una sola línea:
<!-- ANALYSIS_ESCALATION {{"material_change":false,"candidate_applies_material_change":false,"reasons":[],"urgent_risk":false,"reference_invalidation_confidence":0,"replacement_confidence":0,"evidence_quality":"none","independent_support":false,"previous_conclusion":"","invalidation_evidence":"","proposed_replacement":"","strongest_counterargument":"","evidence_to_keep_reference":""}} -->

material_change=true solo para: cambio de nota propuesto >=1.0; catalizador NUEVO de
impacto alto; cambio material de tesis/narrativa; o cambio estructural/técnico que transforma
el escenario o la tesis. reasons solo puede contener score_change, high_impact_catalyst,
thesis_narrative o structural_technical. Un cambio de categoría, una entrada/stop rutinarios
o el vencimiento normal de opciones no bastan.

Si material_change=true, rellena todos los campos explicativos. Da dos porcentajes distintos:
confianza en que la referencia ha quedado invalidada y confianza en que el reemplazo es
mejor. Si hay varios cambios materiales, usa en cada porcentaje el menor valor defendible.
evidence_quality solo puede ser none, weak o strong; independent_support=true exige una
segunda evidencia verificable e independiente. Sin evidencia nueva verificable no superes
64; con una señal débil o ambigua no superes 74; para llegar a 85 necesitas invalidación
explícita, evidencia strong y apoyo independiente. 95-100 es excepcional. urgent_risk=true
solo si esperar a la siguiente referencia puede causar un error material. El sistema usará
el menor de ambos porcentajes: <65 conserva la referencia; 65-84 pide revisión superior;
>=85 permite aplicar el cambio sin revisión, manteniendo bloqueada la nota oficial.
candidate_applies_material_change=true solo cuando el cuerpo del informe incorpora realmente
el reemplazo material propuesto; false significa que mantiene la conclusión afectada de la
referencia. Si material_change=false, debe ser false.{luna_policy}"""


def _build_codex_input(
    symbol: str,
    analysis_date: str,
    instructions: str,
    slim: dict[str, Any],
    analyst_quality: dict[str, Any],
    recent_analyst_actions_block: str,
    recent_ibkr_news_block: str,
    slim_path: Path,
    latest_md_path: Path,
    previous_analysis_block: str,
    level_continuity_block: str = "",
    analysis_policy_block: str = "",
) -> str:
    display_analysis_date = format_report_date(analysis_date)
    slim_json = json.dumps(slim, ensure_ascii=False, indent=2)
    analyst_quality_json = json.dumps(analyst_quality, ensure_ascii=False, indent=2)

    return f"""# Local Codex Analysis Input

Ticker: {symbol}

Analysis date (Europe/Madrid): {display_analysis_date}

Slim JSON source: {slim_path}

Output file to create: {latest_md_path}

System prompt source: {LOCAL_SYSTEM_PROMPT_PATH}

## Operating Rules

- Generate only the final analysis markdown.
- Do not call Gemini, Vertex AI, gemini-stock-analyze, or stock-analyze-batch.
- Do not upload anything to GCS.
- Follow the current analysis instructions exactly.
- Use the slim JSON below as the main source of truth for technical/options data.
- Use the analyst consensus quality layer below only according to its usage guidance.
- Use the recent analyst actions block only as fresh event context, not as a standing consensus valuation.
- Use the recent IBKR events block as fresh event context only. Decide impact yourself; ignore noise and do not force low-impact events into catalysts.
- Use previous catalysts as continuity memory: do not duplicate them as new catalysts; keep, drop, or update them depending on whether they remain active and whether recent news changes them.
- The complete previous report is supplied separately as `previous_analysis.md` when one exists. Read it in full; its narrative, catalysts, event, plan and cited sources are the only authoritative report memory.

## Analysis Authority Policy

```text
{analysis_policy_block}
```

## Previous Analysis Context

```text
{previous_analysis_block}
```

## Deterministic Level Continuity Precheck

```text
{level_continuity_block}
```

## Current Analysis Instructions

```text
{instructions}
```

## User Task

Analiza el ticker {symbol} usando este JSON técnico slim como fuente de verdad principal para técnico/opciones.

La fecha del análisis que debe aparecer en el markdown es {display_analysis_date}.

Busca información reciente necesaria para narrativa vigente, earnings, catalizadores, noticias, analistas recientes, riesgos, sentimiento reciente y próximo evento clave.

No uses el consenso agregado de analistas como motor de la nota diaria salvo que las instrucciones actuales lo pidan expresamente. Un cambio reciente de analista puede ser catalizador solo si es nuevo y cambia de verdad la tesis o el precio.

Usa los eventos/titulares recientes de IBKR para detectar catalizadores que quizá eviten una búsqueda web innecesaria. No todos son catalizadores: solo incluyas los que realmente tengan impacto neto alto o cambien el contexto.

Usa los catalizadores del informe anterior como lista de continuidad. Evita repetirlos por inercia: conserva solo los vigentes, elimina los que ya no importen y fusiona noticias nuevas con catalizadores anteriores cuando sean la misma tesis evolucionando.

Devuelve solo el markdown final con el formato exigido por las instrucciones actuales.

## Analyst Consensus Quality Layer

```json
{analyst_quality_json}
```

## Recent Analyst Actions Since Previous Analysis

```text
{recent_analyst_actions_block}
```

## Recent IBKR News Events Since Previous Analysis

```text
{recent_ibkr_news_block}
```

## JSON Técnico Slim

```json
{slim_json}
```
"""


def _build_previous_analysis_attachment(
    symbol: str,
    previous_analysis: Any,
) -> str:
    generated_at = previous_analysis.generated_at or "unknown"
    return (
        f"# Authoritative previous analysis: {symbol}\n\n"
        f"Source: {previous_analysis.source_uri}\n\n"
        f"Generated at: {generated_at}\n\n"
        "The complete previous report follows verbatim. Use every section for "
        "continuity, including narrative, catalysts, next event, levels and sources.\n\n"
        "---\n\n"
        f"{previous_analysis.analysis_markdown.rstrip()}\n"
    )


def _build_ok_payload(
    symbol: str,
    now: datetime,
    analysis_md: str,
    slim: dict[str, Any],
    analyst_quality: dict[str, Any],
    analyst_ratings_summary: dict[str, Any],
    recent_analyst_actions: dict[str, Any],
    recent_ibkr_news: dict[str, Any],
    recent_ibkr_news_events: dict[str, Any],
    validation: dict[str, Any],
    previous_analysis_markdown: str = "",
    generation_model: str = DEFAULT_CODEX_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    execution_context: str = "individual",
    analysis_kind: str = "reference",
    reference_tier: str = "priority",
    owned: bool = False,
    generation_provider: str = DEFAULT_GENERATION_PROVIDER,
    structured_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if structured_report is None:
        structured_report = build_structured_report(
            markdown=analysis_md,
            generated_at=now,
            latest_price=slim.get("latest_price"),
            previous_markdown=previous_analysis_markdown,
        )
    return {
        "symbol": symbol,
        "generated_at": now.isoformat(),
        "model": MODEL_NAME,
        "generation_model": generation_model,
        "generation_provider": generation_provider,
        "reasoning_effort": reasoning_effort,
        "execution_context": execution_context,
        "analysis_kind": analysis_kind,
        "reference_tier": reference_tier,
        "owned": owned,
        "analysis_status": "ok",
        "slim_as_of": slim.get("as_of"),
        "latest_price": slim.get("latest_price"),
        "analysis_markdown": analysis_md,
        "grounding": {},
        "analyst_consensus_quality": analyst_quality,
        "analyst_ratings_summary": analyst_ratings_summary,
        "analyst_recent_actions": recent_analyst_actions,
        "ibkr_recent_news": recent_ibkr_news,
        "ibkr_recent_news_events": recent_ibkr_news_events,
        "slim_snapshot": slim,
        "validation": validation,
        "report_schema_version": structured_report["schema_version"],
        "decision": structured_report["decision"],
        "plan": structured_report["plan"],
        "catalysts": structured_report["catalysts"],
        "next_event": structured_report["next_event"],
        "changes": structured_report["changes"],
        "alerts": structured_report["alerts"],
    }


def _load_generation_metadata(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "generation_metadata.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _build_failed_payload(
    symbol: str,
    now: datetime,
    error_type: str,
    error_message: str,
    slim: dict[str, Any],
    analyst_quality: dict[str, Any],
    analyst_ratings_summary: dict[str, Any],
    recent_analyst_actions: dict[str, Any],
    recent_ibkr_news: dict[str, Any],
    recent_ibkr_news_events: dict[str, Any],
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "generated_at": now.isoformat(),
        "model": MODEL_NAME,
        "analysis_status": "failed",
        "error_type": error_type,
        "error_message": error_message,
        "analysis_markdown": "",
        "slim_as_of": slim.get("as_of"),
        "latest_price": slim.get("latest_price"),
        "analyst_consensus_quality": analyst_quality,
        "analyst_ratings_summary": analyst_ratings_summary,
        "analyst_recent_actions": recent_analyst_actions,
        "ibkr_recent_news": recent_ibkr_news,
        "ibkr_recent_news_events": recent_ibkr_news_events,
        "slim_snapshot": slim,
    }


def _load_latest_slim(repo_root: Path, symbol: str) -> dict[str, Any]:
    slim_dir = repo_root / "data" / "slim" / symbol

    if not slim_dir.exists():
        return {}

    slim_files = sorted(slim_dir.glob("*.json"))

    if not slim_files:
        return {}

    latest = slim_files[-1]

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    return payload if isinstance(payload, dict) else {}


def _news_events_not_used() -> dict[str, Any]:
    return {
        "status": "not_used",
        "reason": "normal_flow_uses_ibkr_recent_headlines_without_ai_preaggregation",
    }


def _snapshot_parts(latest_json: dict[str, Any]) -> tuple[str, str]:
    generated_at = latest_json.get("generated_at")

    if isinstance(generated_at, str) and generated_at.strip():
        try:
            value = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError:
            value = _utc_now()
    else:
        value = _utc_now()

    value = value.astimezone(timezone.utc)

    return value.strftime("%Y-%m-%d"), value.strftime("%H-%M-%S")


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()

    for candidate in (current, *current.parents):
        source_file = (
            candidate
            / "incoming_from_gcp"
            / "gemini_stock_analyze"
            / "main.py"
        )

        if source_file.exists():
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


def _timestamp_for_file(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H-%M-%SZ")


if __name__ == "__main__":
    from src.local_runner.windows_desktop import configure_background_launch

    configure_background_launch()
    sys.exit(main())
