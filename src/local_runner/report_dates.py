"""Normalize user-visible report dates and catalyst ordering."""

from __future__ import annotations

import re
from datetime import date, datetime


_DATE_TOKEN = r"(?:\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})"
_DATE_AT_START_RE = re.compile(
    rf"^(?P<prefix>\s*(?:[-*]\s*)?(?:\*\*)?)(?P<date>{_DATE_TOKEN})"
)
_ANALYSIS_DATE_RE = re.compile(
    rf"(?im)^(?P<prefix>\s*(?:\*\*)?Fecha del an[aá]lisis\s*:\s*(?:\*\*)?\s*)"
    rf"(?P<date>{_DATE_TOKEN})"
)
_CATALYST_HEADER_RE = re.compile(
    rf"^\s*(?:[-*]\s*)?(?:\*\*)?{_DATE_TOKEN}(?:\*\*)?\s*[·|]"
    r".+?\s*[·|]\s*\([+-]?\d+\)\s*$"
)


def parse_report_date(value: str) -> date | None:
    """Parse current Spanish dates and legacy ISO report dates."""

    text = str(value or "").strip()
    for pattern in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def format_report_date(value: str | date | datetime) -> str:
    """Return a report date as DD-MM-YYYY, preserving unparseable text."""

    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        parsed = parse_report_date(str(value or ""))
        if parsed is None:
            return str(value or "")
    return parsed.strftime("%d-%m-%Y")


def canonical_report_date(value: str) -> str:
    """Return YYYY-MM-DD for structured data, preserving invalid text."""

    parsed = parse_report_date(value)
    return parsed.isoformat() if parsed is not None else str(value or "")


def normalize_report_dates(markdown: str) -> str:
    """Use Spanish dates and sort catalyst blocks newest first."""

    text = _ANALYSIS_DATE_RE.sub(_replace_named_date, str(markdown or ""))
    lines = text.splitlines(keepends=True)
    catalyst_start = _section_index(lines, "1)")
    catalyst_end = _section_index(lines, "2)", start=catalyst_start + 1)
    if catalyst_start >= 0 and catalyst_end > catalyst_start:
        body = lines[catalyst_start + 1 : catalyst_end]
        lines[catalyst_start + 1 : catalyst_end] = _sort_catalyst_body(body)

    event_start = _section_index(lines, "2)")
    event_end = _section_index(lines, "3)", start=event_start + 1)
    if event_start >= 0:
        limit = event_end if event_end > event_start else len(lines)
        for index in range(event_start + 1, limit):
            if not lines[index].strip():
                continue
            lines[index] = _normalize_leading_date(lines[index])
            break
    return "".join(lines)


def _replace_named_date(match: re.Match[str]) -> str:
    return f"{match.group('prefix')}{format_report_date(match.group('date'))}"


def _normalize_leading_date(line: str) -> str:
    match = _DATE_AT_START_RE.match(line)
    if not match:
        return line
    formatted = format_report_date(match.group("date"))
    return line[: match.start("date")] + formatted + line[match.end("date") :]


def _sort_catalyst_body(lines: list[str]) -> list[str]:
    preamble: list[str] = []
    blocks: list[tuple[date | None, int, list[str]]] = []
    current: list[str] | None = None
    current_date: date | None = None

    for line in lines:
        clean = _clean_markdown_line(line)
        if _CATALYST_HEADER_RE.match(clean):
            if current is not None:
                blocks.append((current_date, len(blocks), current))
            normalized = _normalize_leading_date(line)
            token = _DATE_AT_START_RE.match(line)
            current_date = parse_report_date(token.group("date")) if token else None
            current = [normalized]
        elif current is None:
            preamble.append(line)
        else:
            current.append(line)

    if current is not None:
        blocks.append((current_date, len(blocks), current))
    if not blocks:
        return lines

    blocks.sort(
        key=lambda item: (
            item[0] is None,
            -(item[0].toordinal()) if item[0] is not None else 0,
            item[1],
        )
    )
    return preamble + [line for _, _, block in blocks for line in block]


def _section_index(lines: list[str], prefix: str, *, start: int = 0) -> int:
    for index in range(max(start, 0), len(lines)):
        if _clean_markdown_line(lines[index]).startswith(prefix):
            return index
    return -1


def _clean_markdown_line(value: str) -> str:
    return str(value or "").strip().lstrip("-*# ").replace("**", "").strip()
