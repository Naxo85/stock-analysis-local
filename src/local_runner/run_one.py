"""Prepare and validate one local Codex stock analysis."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.common.analysis_validator import validate_markdown


SLIM_BASE_URL = "https://support-resistances-slim-714254943648.europe-southwest1.run.app"
MODEL_NAME = "codex-local"
REQUEST_TIMEOUT_SECONDS = 60


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = _find_repo_root(Path.cwd())
    symbol = args.ticker.strip().upper()

    if args.prepare:
        return _prepare(repo_root, symbol)

    if args.validate:
        return _validate(repo_root, symbol)

    raise RuntimeError("Either --prepare or --validate is required.")


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

    return parser.parse_args(argv)


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
    _write_json(failed_json_path, payload)

    _write_json(
        logs_dir / f"{timestamp}.validate.json",
        {
            "symbol": symbol,
            "generated_at": now.isoformat(),
            "analysis_status": "failed",
            "latest_failed_json_path": str(failed_json_path),
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
