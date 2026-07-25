"""Load and summarize the previous uploaded analysis for a ticker."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any

from src.common.analysis_validator import extract_range, extract_score
from src.local_runner.gcs_uploader import TEST_BUCKET, require_gcloud


MAX_CATALYST_LINES = 10


@dataclass(frozen=True)
class PreviousAnalysisContext:
    found: bool
    source_uri: str
    generated_at: str | None = None
    markdown: str = ""
    analysis_markdown: str = ""
    reason: str | None = None

    def to_prompt_block(self, symbol: str) -> str:
        if not self.found:
            reason = f" Motivo: {self.reason}." if self.reason else ""
            return (
                f"No hay informe anterior disponible para {symbol}.{reason}\n"
                "Analiza desde cero. No inventes continuidad ni contexto previo."
            )

        return self.markdown

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "source_uri": self.source_uri,
            "generated_at": self.generated_at,
            "reason": self.reason,
        }


def load_previous_analysis_context(symbol: str) -> PreviousAnalysisContext:
    normalized_symbol = symbol.strip().upper()
    source_uri = f"gs://{TEST_BUCKET}/{normalized_symbol}/latest.json"

    try:
        raw = _read_gcs_text(source_uri)
    except RuntimeError as exc:
        return PreviousAnalysisContext(
            found=False,
            source_uri=source_uri,
            reason=str(exc),
        )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return PreviousAnalysisContext(
            found=False,
            source_uri=source_uri,
            reason="previous_latest_json_invalid",
        )

    if not isinstance(payload, dict):
        return PreviousAnalysisContext(
            found=False,
            source_uri=source_uri,
            reason="previous_latest_json_not_object",
        )

    if payload.get("analysis_status") != "ok":
        return PreviousAnalysisContext(
            found=False,
            source_uri=source_uri,
            generated_at=_string_or_none(payload.get("generated_at")),
            reason=f"previous_analysis_status={payload.get('analysis_status')!r}",
        )

    analysis_markdown = _string_or_none(payload.get("analysis_markdown")) or ""

    if not analysis_markdown.strip():
        return PreviousAnalysisContext(
            found=False,
            source_uri=source_uri,
            generated_at=_string_or_none(payload.get("generated_at")),
            reason="previous_analysis_markdown_empty",
        )

    generated_at = _string_or_none(payload.get("generated_at"))
    markdown = _build_previous_prompt_markdown(
        symbol=normalized_symbol,
        source_uri=source_uri,
        generated_at=generated_at,
        payload=payload,
        analysis_markdown=analysis_markdown,
    )

    return PreviousAnalysisContext(
        found=True,
        source_uri=source_uri,
        generated_at=generated_at,
        markdown=markdown,
        analysis_markdown=analysis_markdown,
    )


def _read_gcs_text(uri: str) -> str:
    try:
        gcloud_path = require_gcloud()
    except RuntimeError as exc:
        raise RuntimeError(f"previous_analysis_gcloud_unavailable: {exc}") from exc

    completed = subprocess.run(
        [gcloud_path, "storage", "cat", uri],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        detail = f": {stderr[:500]}" if stderr else ""
        raise RuntimeError(f"previous_analysis_not_loaded{detail}")

    return completed.stdout


def _build_previous_prompt_markdown(
    symbol: str,
    source_uri: str,
    generated_at: str | None,
    payload: dict[str, Any],
    analysis_markdown: str,
) -> str:
    score = _score_from_payload(payload)
    if score is None:
        score = extract_score(analysis_markdown)

    entry_range = _range_from_payload(payload, "entry_range")
    if entry_range is None:
        entry_range = extract_range(analysis_markdown, "Entrada")

    ambitious_range = _range_from_payload(payload, "ambitious_entry_range")
    if ambitious_range is None:
        ambitious_range = extract_range(analysis_markdown, "Entrada ambiciosa")
    narrative = _extract_prefixed_line(analysis_markdown, "Narrativa actual")
    catalysts = _extract_section(
        analysis_markdown,
        start_pattern=r"^1\)\s*Narrativa",
        end_pattern=r"^2\)\s*Pr[oó]ximo",
        max_lines=MAX_CATALYST_LINES,
    )
    next_event = _extract_section(
        analysis_markdown,
        start_pattern=r"^2\)\s*Pr[oó]ximo",
        end_pattern=r"^3\)\s*Plan",
        max_lines=5,
    )
    exit_target = _extract_prefixed_line(
        analysis_markdown,
        "Salida / objetivo principal",
    )

    lines = [
        "Informe anterior disponible.",
        f"source: {source_uri}",
        f"generated_at: {generated_at or 'unknown'}",
        f"nota_anterior: {_format_optional_number(score)}",
        f"narrativa_anterior: {narrative or 'no extraída'}",
        f"entrada_anterior: {_format_range(entry_range)}",
        f"entrada_ambiciosa_anterior: {_format_range(ambitious_range)}",
        f"salida_anterior: {exit_target or 'no extraída'}",
        "",
        "catalizadores_anteriores:",
        catalysts or "no extraídos",
        "",
        "uso_de_catalizadores_anteriores:",
        "- No los presentes como nuevos salvo que haya una noticia/evento reciente que los actualice.",
        "- Mantén solo los que sigan activos para la tesis actual.",
        "- Si un catalizador anterior ya está descontado, expirado o invalidado, dilo o sustitúyelo por el evento nuevo relevante.",
        "- Si una noticia reciente se refiere al mismo tema, trátala como evolución del catalizador anterior, no como duplicado.",
        "",
        "proximo_evento_anterior:",
        next_event or "no extraído",
    ]

    return "\n".join(lines)


def _extract_prefixed_line(markdown: str, label: str) -> str:
    normalized_label = label.lower()

    for raw_line in markdown.splitlines():
        line = _clean_line(raw_line)

        if line.lower().startswith(f"{normalized_label}:"):
            return line.split(":", 1)[1].strip()

    return ""


def _extract_section(
    markdown: str,
    *,
    start_pattern: str,
    end_pattern: str,
    max_lines: int,
) -> str:
    start_re = re.compile(start_pattern, re.IGNORECASE)
    end_re = re.compile(end_pattern, re.IGNORECASE)
    in_section = False
    lines: list[str] = []

    for raw_line in markdown.splitlines():
        line = _clean_line(raw_line)

        if not line:
            continue

        if start_re.search(line):
            in_section = True
            continue

        if in_section and end_re.search(line):
            break

        if in_section:
            lines.append(line)

            if len(lines) >= max_lines:
                break

    return "\n".join(lines)


def _clean_line(line: str) -> str:
    return str(line or "").replace("**", "").replace("*", "").strip()


def _format_optional_number(value: float | None) -> str:
    if value is None:
        return "no extraída"

    return f"{value:.1f}"


def _format_range(value: Any) -> str:
    if value is None:
        return "no extraída"

    return f"{value.lower:g}-{value.upper:g}"


def _score_from_payload(payload: dict[str, Any]) -> float | None:
    validation = payload.get("validation")

    if not isinstance(validation, dict):
        return None

    value = validation.get("score")

    if isinstance(value, (int, float)):
        return float(value)

    return None


def _range_from_payload(payload: dict[str, Any], key: str) -> Any:
    validation = payload.get("validation")

    if not isinstance(validation, dict):
        return None

    value = validation.get(key)

    if not isinstance(value, dict):
        return None

    lower = value.get("lower")
    upper = value.get("upper")

    if not isinstance(lower, (int, float)) or not isinstance(upper, (int, float)):
        return None

    return _StructuredRange(lower=float(lower), upper=float(upper))


@dataclass(frozen=True)
class _StructuredRange:
    lower: float
    upper: float


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()

    return None
