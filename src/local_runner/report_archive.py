"""Maintain a compact report history and bounded GCS snapshot archive."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

from src.common.analysis_validator import extract_range, extract_score
from src.local_runner.gcs_uploader import CONTENT_TYPE_JSON, TEST_BUCKET


KEEP_SUCCESSFUL_SNAPSHOTS = 5
KEEP_FAILED_SNAPSHOTS = 2
SNAPSHOT_RE = re.compile(
    r"^(?P<prefix>gs://[^/]+/(?P<symbol>[^/]+)/)"
    r"(?P<date>\d{4}-\d{2}-\d{2})/(?P<time>\d{2}-\d{2}-\d{2})"
    r"(?P<error>\.error)?\.(?P<extension>md|html|json)$"
)


def maintain_report_archive(
    *,
    symbol: str,
    latest_json_path: Path,
    output_dir: Path,
    gcloud_path: str,
) -> dict[str, Any]:
    """Append compact history, upload it, then prune old report snapshots."""
    normalized_symbol = symbol.strip().upper()
    prefix = f"gs://{TEST_BUCKET}/{normalized_symbol}/"
    snapshot_uris = _list_snapshot_uris(gcloud_path, prefix)
    history_uri = f"{prefix}history.json"
    history = _read_remote_history(gcloud_path, history_uri)
    latest_payload = json.loads(latest_json_path.read_text(encoding="utf-8"))
    history = merge_history(history, compact_history_entry(latest_payload))

    history_path = output_dir / "history.json"
    history_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            gcloud_path,
            "storage",
            "cp",
            f"--content-type={CONTENT_TYPE_JSON}",
            str(history_path),
            history_uri,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    stale_uris = select_stale_snapshot_uris(snapshot_uris)
    for chunk in _chunks(stale_uris, 100):
        subprocess.run(
            [gcloud_path, "storage", "rm", *chunk],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    return {
        "history_entries": len(history["entries"]),
        "deleted_objects": len(stale_uris),
        "kept_successful_snapshots": KEEP_SUCCESSFUL_SNAPSHOTS,
        "kept_failed_snapshots": KEEP_FAILED_SNAPSHOTS,
    }


def compact_history_entry(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("report_schema_version") == 2:
        decision = payload.get("decision") or {}
        plan = payload.get("plan") or {}
        return {
            "generated_at": payload.get("generated_at"),
            "symbol": payload.get("symbol"),
            "analysis_status": payload.get("analysis_status"),
            "price": decision.get("reference_price", payload.get("latest_price")),
            "score": decision.get("score"),
            "entry": plan.get("entry"),
            "ambitious_entry": plan.get("ambitious_entry"),
            "management_stop": plan.get("management_stop"),
            "structural_stop": plan.get("structural_stop"),
            "target": plan.get("target"),
            "catalysts": payload.get("catalysts") or [],
            "next_event": payload.get("next_event"),
        }

    markdown = str(payload.get("analysis_markdown") or "")
    entry = extract_range(markdown, "Entrada")
    ambitious = extract_range(markdown, "Entrada ambiciosa")
    return {
        "generated_at": payload.get("generated_at"),
        "symbol": payload.get("symbol"),
        "analysis_status": payload.get("analysis_status"),
        "price": payload.get("latest_price"),
        "score": extract_score(markdown),
        "entry": entry.to_dict() if entry else None,
        "ambitious_entry": ambitious.to_dict() if ambitious else None,
        "management_stop": _extract_prefixed_value(markdown, "Stop de gestión"),
        "structural_stop": _extract_prefixed_value(markdown, "Stop estructural"),
        "target": _extract_prefixed_value(markdown, "Salida / objetivo principal"),
        "current_state": _extract_prefixed_value(markdown, "Estado actual"),
        "catalysts": _extract_section_lines(markdown, "1)", "2)"),
        "next_event": _extract_section_lines(markdown, "2)", "3)"),
    }


def merge_history(
    history: dict[str, Any] | None,
    entry: dict[str, Any],
) -> dict[str, Any]:
    existing = history.get("entries", []) if isinstance(history, dict) else []
    entries = [item for item in existing if isinstance(item, dict)]
    generated_at = entry.get("generated_at")
    entries = [item for item in entries if item.get("generated_at") != generated_at]
    entries.append(entry)
    entries.sort(key=lambda item: str(item.get("generated_at") or ""))
    return {"schema_version": 1, "entries": entries}


def select_stale_snapshot_uris(uris: Iterable[str]) -> list[str]:
    successful: dict[str, list[str]] = {}
    failed: dict[str, list[str]] = {}

    for uri in uris:
        match = SNAPSHOT_RE.match(uri.strip())
        if not match:
            continue
        key = f"{match.group('date')}/{match.group('time')}"
        target = failed if match.group("error") else successful
        target.setdefault(key, []).append(uri.strip())

    stale: list[str] = []
    for groups, keep in (
        (successful, KEEP_SUCCESSFUL_SNAPSHOTS),
        (failed, KEEP_FAILED_SNAPSHOTS),
    ):
        old_keys = sorted(groups, reverse=True)[keep:]
        for key in old_keys:
            stale.extend(sorted(groups[key]))
    return stale


def _list_snapshot_uris(gcloud_path: str, prefix: str) -> list[str]:
    completed = subprocess.run(
        [gcloud_path, "storage", "ls", "--recursive", prefix],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _read_remote_history(gcloud_path: str, history_uri: str) -> dict[str, Any]:
    completed = subprocess.run(
        [gcloud_path, "storage", "cat", history_uri],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        detail = (completed.stderr or "").casefold()
        if "not found" in detail or "matched no objects" in detail or "404" in detail:
            return {"schema_version": 1, "entries": []}
        raise RuntimeError(
            "report_history_read_failed: "
            + ((completed.stderr or completed.stdout).strip() or "unknown error")
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"schema_version": 1, "entries": []}
    return payload if isinstance(payload, dict) else {"schema_version": 1, "entries": []}


def _extract_prefixed_value(markdown: str, label: str) -> str | None:
    normalized_label = label.casefold()
    for raw_line in markdown.splitlines():
        line = raw_line.strip().lstrip("-*# ").replace("**", "")
        if line.casefold().startswith(normalized_label + ":"):
            value = line.split(":", 1)[1].strip()
            return value or None
    return None


def _extract_section_lines(markdown: str, start: str, end: str) -> list[str]:
    collecting = False
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        clean = raw_line.strip().lstrip("# ").replace("**", "")
        if clean.startswith(end):
            break
        if collecting and clean:
            lines.append(clean)
        if clean.startswith(start):
            collecting = True
    return lines


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]
