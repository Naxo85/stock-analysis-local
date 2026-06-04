"""Prepare and validate one local Codex stock analysis."""

from __future__ import annotations

import argparse
import ast
import contextlib
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.common.analysis_validator import validate_markdown
from src.local_runner.codex_generator import generate_markdown_with_codex
from src.local_runner.gcs_uploader import (
    build_real_upload_plan,
    build_test_upload_plan,
    format_command,
    upload_artifacts,
)


SLIM_BASE_URL = "https://support-resistances-slim-714254943648.europe-southwest1.run.app"
MODEL_NAME = "codex-local"
REQUEST_TIMEOUT_SECONDS = 60
LOCAL_SYSTEM_PROMPT_PATH = Path("prompts") / "stock_analysis_system_prompt.md"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    symbol = args.ticker.strip().upper()

    if args.prepare:
        return _prepare(repo_root, symbol)

    if args.validate:
        return _validate(repo_root, symbol)

    if args.generate:
        return _generate(repo_root, symbol)

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
        return _run_full(repo_root, symbol)

    raise RuntimeError(
        "Either --prepare, --generate, --validate, --upload-test, "
        "--upload-real, or --run-full is required."
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare or validate one local Codex stock analysis."
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
        help="Generate output/{TICKER}/latest.md via non-interactive Codex.",
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
        "--execute-upload-real",
        action="store_true",
        help=(
            "Actually run gcloud storage cp for --upload-real. Without this flag, "
            "--upload-real only prints the commands."
        ),
    )

    args = parser.parse_args(argv)

    if args.execute_upload_test and not args.upload_test:
        parser.error("--execute-upload-test can only be used with --upload-test")

    if args.execute_upload_real and not args.upload_real:
        parser.error("--execute-upload-real can only be used with --upload-real")

    return args


def _prepare(repo_root: Path, symbol: str) -> int:
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

    instructions = _load_system_prompt(repo_root)
    codex_input = _build_codex_input(
        symbol=symbol,
        instructions=instructions,
        slim=slim,
        slim_path=slim_path,
        latest_md_path=output_dir / "latest.md",
    )

    codex_input_path = output_dir / "codex_input.md"
    codex_input_path.write_text(codex_input, encoding="utf-8")

    _write_json(
        logs_dir / f"{timestamp}.prepare.json",
        {
            "symbol": symbol,
            "generated_at": now.isoformat(),
            "slim_path": str(slim_path),
            "codex_input_path": str(codex_input_path),
            "slim_as_of": slim.get("as_of"),
            "latest_price": slim.get("latest_price"),
        },
    )

    print(f"Prepared local Codex input for {symbol}.")
    print(f"Slim JSON: {slim_path}")
    print(f"Codex input: {codex_input_path}")
    print(f"Next: generate markdown into {output_dir / 'latest.md'}")

    return 0


def _validate(repo_root: Path, symbol: str) -> int:
    now = _utc_now()
    timestamp = _timestamp_for_file(now)

    output_dir = repo_root / "output" / symbol
    logs_dir = repo_root / "logs" / symbol
    latest_md_path = output_dir / "latest.md"

    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    slim = _load_latest_slim(repo_root, symbol)

    if latest_md_path.exists():
        analysis_md = latest_md_path.read_text(encoding="utf-8")
        validation = validate_markdown(analysis_md)
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
            validation=validation.to_dict(),
        )
        latest_json_path = output_dir / "latest.json"
        _write_json(latest_json_path, payload)

        _write_json(
            logs_dir / f"{timestamp}.validate.json",
            {
                "symbol": symbol,
                "generated_at": now.isoformat(),
                "analysis_status": "ok",
                "latest_json_path": str(latest_json_path),
                "validation": validation.to_dict(),
            },
        )

        print(f"Validation OK for {symbol}.")
        print(f"Latest JSON: {latest_json_path}")

        return 0

    error_message = "; ".join(validation.errors)
    payload = _build_failed_payload(
        symbol=symbol,
        now=now,
        error_type="validation_failed",
        error_message=error_message,
        slim=slim,
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


def _generate(repo_root: Path, symbol: str) -> int:
    output_dir = repo_root / "output" / symbol
    codex_input_path = output_dir / "codex_input.md"
    latest_md_path = output_dir / "latest.md"

    result = generate_markdown_with_codex(
        input_path=codex_input_path,
        output_path=latest_md_path,
        cwd=repo_root,
    )

    print(f"Generated markdown for {symbol}: {result.output_path}")

    return 0


def _run_full(repo_root: Path, symbol: str) -> int:
    run_started = _utc_now()
    run_log: dict[str, Any] = {
        "symbol": symbol,
        "started_at": run_started.isoformat(),
        "phases": [],
    }

    try:
        _run_full_phase(run_log, "prepare", lambda: _prepare(repo_root, symbol))
        _run_full_phase(run_log, "generate", lambda: _generate(repo_root, symbol))
        validate_status = _run_full_phase(
            run_log,
            "validate",
            lambda: _validate(repo_root, symbol),
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

        _finish_run_full_log(repo_root, symbol, run_log, "ok")
        print(f"OK {symbol}: análisis generado y subido.")
        return upload_status
    except Exception as exc:
        run_log["error_type"] = "runtime_error"
        run_log["error_message"] = str(exc)
        _finish_run_full_log(repo_root, symbol, run_log, "failed")
        print(f"FAILED {symbol}: runtime_error - {exc}")
        return 1


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

    if upload_kind == "test":
        if analysis_status != "ok":
            raise RuntimeError(
                "test_upload_rejected: _local_test uploads require "
                f"analysis_status='ok'; found {analysis_status!r}"
            )

        plan = build_test_upload_plan(
            symbol=symbol,
            markdown_source=latest_md_path,
            json_source=latest_json_path,
            dry_run=dry_run,
        )
    elif upload_kind == "real":
        date_part, time_part = _snapshot_parts(latest_json)
        plan = build_real_upload_plan(
            symbol=symbol,
            markdown_source=latest_md_path if analysis_status == "ok" else None,
            json_source=latest_json_path,
            analysis_status=analysis_status,
            timestamp_date=date_part,
            timestamp_time=time_part,
            dry_run=dry_run,
        )
    else:
        raise RuntimeError(f"unknown_upload_kind: {upload_kind}")

    commands = upload_artifacts(plan)

    mode = "DRY-RUN" if dry_run else "EXECUTED"
    label = "test" if upload_kind == "test" else "real"
    print(f"GCS {label} upload {mode} for {symbol}.")
    print(f"analysis_status={analysis_status}")

    for destination in plan.destinations:
        print(f"Destination: {destination}")

    for command in commands:
        print(format_command(command))

    return 0


def _fetch_slim(symbol: str) -> dict[str, Any]:
    url = f"{SLIM_BASE_URL}?{urlencode({'symbol': symbol})}"
    request = Request(url, headers={"User-Agent": "stock-analysis-local/0.1"})

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"slim_endpoint_http_error: HTTP {exc.code}: {detail[:1000]}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"slim_endpoint_url_error: {exc}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("slim_endpoint_invalid_json") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("slim_endpoint_unexpected_payload: expected JSON object")

    return payload


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


def _build_codex_input(
    symbol: str,
    instructions: str,
    slim: dict[str, Any],
    slim_path: Path,
    latest_md_path: Path,
) -> str:
    slim_json = json.dumps(slim, ensure_ascii=False, indent=2)

    return f"""# Local Codex Analysis Input

Ticker: {symbol}

Slim JSON source: {slim_path}

Output file to create: {latest_md_path}

System prompt source: {LOCAL_SYSTEM_PROMPT_PATH}

## Operating Rules

- Generate only the final analysis markdown.
- Do not call Gemini, Vertex AI, gemini-stock-analyze, or stock-analyze-batch.
- Do not upload anything to GCS.
- Follow the current analysis instructions exactly.
- Use the slim JSON below as the main source of truth for technical/options data.

## Current Analysis Instructions

```text
{instructions}
```

## User Task

Analiza el ticker {symbol} usando este JSON técnico slim como fuente de verdad principal para técnico/opciones.

Busca información reciente necesaria para narrativa vigente, earnings, catalizadores, noticias, analistas, riesgos, sentimiento reciente y próximo evento clave.

Devuelve solo el markdown final con el formato exigido por las instrucciones actuales.

## JSON Técnico Slim

```json
{slim_json}
```
"""


def _build_ok_payload(
    symbol: str,
    now: datetime,
    analysis_md: str,
    slim: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "generated_at": now.isoformat(),
        "model": MODEL_NAME,
        "analysis_status": "ok",
        "slim_as_of": slim.get("as_of"),
        "latest_price": slim.get("latest_price"),
        "analysis_markdown": analysis_md,
        "grounding": {},
        "slim_snapshot": slim,
        "validation": validation,
    }


def _build_failed_payload(
    symbol: str,
    now: datetime,
    error_type: str,
    error_message: str,
    slim: dict[str, Any],
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
    sys.exit(main())
