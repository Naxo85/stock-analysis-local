"""Non-interactive Codex markdown generation helper."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


WINDOWS_CODEX_CMD = Path(
    os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
) / "npm" / "codex.cmd"
WINDOWS_CODEX_APP_BIN_ROOT = Path(
    os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
) / "OpenAI" / "Codex" / "bin"
DEFAULT_REASONING_EFFORT = "medium"


@dataclass(frozen=True)
class CodexGenerationResult:
    command: tuple[str, ...]
    input_path: Path
    output_path: Path
    usage: dict[str, int] | None = None


def generate_markdown_with_codex(
    input_path: Path,
    output_path: Path,
    *,
    cwd: Path,
    model: str | None = None,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    event_log_path: Path | None = None,
    benchmark_isolation: bool = False,
) -> CodexGenerationResult:
    """Generate final markdown via `codex exec`.

    Python reads the full prepared prompt and sends it through stdin. Codex only
    writes the markdown. The runner handles orchestration, validation, JSON, and
    uploads.
    """

    if not input_path.exists():
        raise RuntimeError(f"missing_codex_input: {input_path}")

    codex_path = require_codex()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    codex_input = input_path.read_text(encoding="utf-8")
    isolation = ""
    if benchmark_isolation:
        isolation = (
            "MODO BENCHMARK AISLADO: usa el input congelado incluido abajo como "
            "unica base previa. No leas output/latest.md ni ningun informe generado "
            "por otro candidato del benchmark. Cada candidato debe partir exactamente "
            "del mismo contexto.\n\n"
        )

    prompt = (
        isolation
        + "Genera SOLO el markdown final. No anadas explicaciones, prefacios, "
        "comentarios ni pasos internos. Aqui esta el input completo:\n\n"
        f"{codex_input}"
    )

    command_parts = [
        codex_path,
        "exec",
        "--json",
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
    ]
    if model:
        command_parts.extend(("-m", model))
    command_parts.extend(
        (
            "--output-last-message",
            str(output_path),
            "-",
        )
    )
    command = tuple(command_parts)

    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd),
            check=True,
            input=prompt,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
    except PermissionError as exc:
        raise RuntimeError(
            "codex_exec_permission_error: Codex CLI exists but cannot be "
            "executed from this environment"
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        detail = f": {stderr[:1000]}" if stderr else ""
        raise RuntimeError(
            f"codex_exec_failed: exit_code={exc.returncode}{detail}"
        ) from exc

    stdout = completed.stdout or ""
    if event_log_path is not None:
        event_log_path.parent.mkdir(parents=True, exist_ok=True)
        event_log_path.write_text(stdout, encoding="utf-8")

    usage = parse_codex_jsonl_usage(stdout)

    if not output_path.exists():
        raise RuntimeError(f"codex_exec_no_output: {output_path}")

    return CodexGenerationResult(
        command=command,
        input_path=input_path,
        output_path=output_path,
        usage=usage,
    )


def parse_codex_jsonl_usage(raw_output: str) -> dict[str, int] | None:
    """Return the last token-usage payload emitted by ``codex exec --json``."""

    usage: dict[str, int] | None = None

    for raw_line in str(raw_output or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") != "turn.completed":
            continue

        candidate = event.get("usage")
        if not isinstance(candidate, dict):
            continue

        normalized: dict[str, int] = {}
        for key, value in candidate.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            normalized[str(key)] = int(value)

        if normalized:
            input_tokens = normalized.get("input_tokens")
            cached_tokens = normalized.get("cached_input_tokens", 0)
            output_tokens = normalized.get("output_tokens")
            if input_tokens is not None:
                normalized.setdefault(
                    "uncached_input_tokens",
                    max(input_tokens - cached_tokens, 0),
                )
            if input_tokens is not None and output_tokens is not None:
                normalized.setdefault("total_tokens", input_tokens + output_tokens)
            usage = normalized

    return usage


def require_codex() -> str:
    env_path = os.environ.get("CODEX_CLI_PATH")

    if env_path:
        path = Path(env_path)

        if path.exists():
            return str(path)

        raise RuntimeError(f"codex_cli_path_not_found: {path}")

    if os.name == "nt":
        app_codex = _latest_windows_app_codex()
        if app_codex is not None:
            return str(app_codex)
        if WINDOWS_CODEX_CMD.exists():
            return str(WINDOWS_CODEX_CMD)

    path = shutil.which("codex.cmd") or shutil.which("codex")

    if not path:
        raise RuntimeError("codex_cli_not_found: codex is not on PATH")

    if path.lower().endswith(".ps1"):
        raise RuntimeError(f"codex_cli_ps1_not_supported: {path}")

    return path


def _latest_windows_app_codex() -> Path | None:
    """Find the versioned CLI bundled with the current Codex desktop app."""

    if not WINDOWS_CODEX_APP_BIN_ROOT.exists():
        return None

    candidates = tuple(WINDOWS_CODEX_APP_BIN_ROOT.glob("*/codex.exe"))
    if not candidates:
        return None

    return max(candidates, key=lambda candidate: candidate.stat().st_mtime_ns)
