"""Non-interactive Codex markdown generation helper."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


WINDOWS_CODEX_CMD = Path(r"C:\Users\ignac\AppData\Roaming\npm\codex.cmd")
DEFAULT_REASONING_EFFORT = "medium"


@dataclass(frozen=True)
class CodexGenerationResult:
    command: tuple[str, ...]
    input_path: Path
    output_path: Path


def generate_markdown_with_codex(
    input_path: Path,
    output_path: Path,
    *,
    cwd: Path,
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
    prompt = (
        "Genera SOLO el markdown final. No anadas explicaciones, prefacios, "
        "comentarios ni pasos internos. Aqui esta el input completo:\n\n"
        f"{codex_input}"
    )

    command = (
        codex_path,
        "exec",
        "-c",
        f'model_reasoning_effort="{DEFAULT_REASONING_EFFORT}"',
        "--output-last-message",
        str(output_path),
        "-",
    )

    try:
        subprocess.run(
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

    if not output_path.exists():
        raise RuntimeError(f"codex_exec_no_output: {output_path}")

    return CodexGenerationResult(
        command=command,
        input_path=input_path,
        output_path=output_path,
    )


def require_codex() -> str:
    env_path = os.environ.get("CODEX_CLI_PATH")

    if env_path:
        path = Path(env_path)

        if path.exists():
            return str(path)

        raise RuntimeError(f"codex_cli_path_not_found: {path}")

    if os.name == "nt" and WINDOWS_CODEX_CMD.exists():
        return str(WINDOWS_CODEX_CMD)

    path = shutil.which("codex.cmd") or shutil.which("codex")

    if not path:
        raise RuntimeError("codex_cli_not_found: codex is not on PATH")

    if path.lower().endswith(".ps1"):
        raise RuntimeError(f"codex_cli_ps1_not_supported: {path}")

    return path
