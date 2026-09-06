"""Upload local report artifacts to GCS using gcloud."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


TEST_BUCKET = "stock-analysis-reports-naxo85"
TEST_PREFIX = "_local_test"
SHEET_REPORT_MIRROR_BUCKET = "stock-analysis-system-naxo85"
SHEET_REPORT_MIRROR_PREFIX = "runtime/analysis-reports"
CONTENT_TYPE_JSON = "application/json; charset=utf-8"
CONTENT_TYPE_MARKDOWN = "text/markdown; charset=utf-8"
CONTENT_TYPE_HTML = "text/html; charset=utf-8"


@dataclass(frozen=True)
class UploadPlan:
    symbol: str
    commands: tuple[tuple[str, ...], ...]
    destinations: tuple[str, ...]
    dry_run: bool
    gcloud_path: str


def build_test_upload_plan(
    symbol: str,
    markdown_source: Path,
    html_source: Path,
    json_source: Path,
    *,
    dry_run: bool = True,
) -> UploadPlan:
    gcloud_path = require_gcloud()
    normalized_symbol = symbol.strip().upper()
    markdown_destination = (
        f"gs://{TEST_BUCKET}/{TEST_PREFIX}/{normalized_symbol}/latest.md"
    )
    json_destination = (
        f"gs://{TEST_BUCKET}/{TEST_PREFIX}/{normalized_symbol}/latest.json"
    )
    html_destination = (
        f"gs://{TEST_BUCKET}/{TEST_PREFIX}/{normalized_symbol}/latest.html"
    )
    commands = (
        _cp_command(
            gcloud_path,
            markdown_source,
            markdown_destination,
            CONTENT_TYPE_MARKDOWN,
        ),
        _cp_command(
            gcloud_path,
            html_source,
            html_destination,
            CONTENT_TYPE_HTML,
        ),
        _cp_command(
            gcloud_path,
            json_source,
            json_destination,
            CONTENT_TYPE_JSON,
        ),
    )

    return UploadPlan(
        symbol=normalized_symbol,
        commands=commands,
        destinations=(markdown_destination, html_destination, json_destination),
        dry_run=dry_run,
        gcloud_path=gcloud_path,
    )


def build_real_upload_plan(
    symbol: str,
    json_source: Path,
    *,
    analysis_status: str,
    timestamp_date: str,
    timestamp_time: str,
    markdown_source: Path | None = None,
    html_source: Path | None = None,
    dry_run: bool = True,
) -> UploadPlan:
    gcloud_path = require_gcloud()
    normalized_symbol = symbol.strip().upper()

    latest_json_destination = (
        f"gs://{TEST_BUCKET}/{normalized_symbol}/latest.json"
    )

    commands: list[tuple[str, ...]] = [
        _cp_command(
            gcloud_path,
            json_source,
            latest_json_destination,
            CONTENT_TYPE_JSON,
        )
    ]
    destinations = [latest_json_destination]

    if analysis_status == "ok":
        if markdown_source is None:
            raise RuntimeError("markdown_source is required for ok uploads")
        if html_source is None:
            raise RuntimeError("html_source is required for ok uploads")

        latest_markdown_destination = (
            f"gs://{TEST_BUCKET}/{normalized_symbol}/latest.md"
        )
        latest_html_destination = (
            f"gs://{TEST_BUCKET}/{normalized_symbol}/latest.html"
        )
        snapshot_markdown_destination = (
            f"gs://{TEST_BUCKET}/{normalized_symbol}/"
            f"{timestamp_date}/{timestamp_time}.md"
        )
        snapshot_json_destination = (
            f"gs://{TEST_BUCKET}/{normalized_symbol}/"
            f"{timestamp_date}/{timestamp_time}.json"
        )
        snapshot_html_destination = (
            f"gs://{TEST_BUCKET}/{normalized_symbol}/"
            f"{timestamp_date}/{timestamp_time}.html"
        )
        sheet_report_destination = (
            f"gs://{SHEET_REPORT_MIRROR_BUCKET}/{SHEET_REPORT_MIRROR_PREFIX}/"
            f"{normalized_symbol}.json"
        )

        commands = [
            _cp_command(
                gcloud_path,
                markdown_source,
                latest_markdown_destination,
                CONTENT_TYPE_MARKDOWN,
            ),
            _cp_command(
                gcloud_path,
                html_source,
                latest_html_destination,
                CONTENT_TYPE_HTML,
            ),
            *commands,
            _cp_command(
                gcloud_path,
                markdown_source,
                snapshot_markdown_destination,
                CONTENT_TYPE_MARKDOWN,
            ),
            _cp_command(
                gcloud_path,
                json_source,
                snapshot_json_destination,
                CONTENT_TYPE_JSON,
            ),
            _cp_command(
                gcloud_path,
                html_source,
                snapshot_html_destination,
                CONTENT_TYPE_HTML,
            ),
            _cp_command(
                gcloud_path,
                json_source,
                sheet_report_destination,
                CONTENT_TYPE_JSON,
            ),
        ]
        destinations = [
            latest_markdown_destination,
            latest_html_destination,
            latest_json_destination,
            snapshot_markdown_destination,
            snapshot_json_destination,
            snapshot_html_destination,
            sheet_report_destination,
        ]

    elif analysis_status == "failed":
        error_json_destination = (
            f"gs://{TEST_BUCKET}/{normalized_symbol}/"
            f"{timestamp_date}/{timestamp_time}.error.json"
        )
        commands.append(
            _cp_command(
                gcloud_path,
                json_source,
                error_json_destination,
                CONTENT_TYPE_JSON,
            )
        )
        destinations.append(error_json_destination)

    else:
        raise RuntimeError(
            "unsupported_analysis_status_for_upload: "
            f"expected 'ok' or 'failed', got {analysis_status!r}"
        )

    return UploadPlan(
        symbol=normalized_symbol,
        commands=tuple(commands),
        destinations=tuple(destinations),
        dry_run=dry_run,
        gcloud_path=gcloud_path,
    )


def upload_artifacts(plan: UploadPlan) -> list[list[str]]:
    commands = [list(command) for command in plan.commands]

    if plan.dry_run:
        return commands

    for command in commands:
        subprocess.run(command, check=True)

    return commands


def require_gcloud() -> str:
    for command in ("gcloud.cmd", "gcloud"):
        path = shutil.which(command)

        if path:
            return path

    raise RuntimeError(
        "gcloud_not_found: install Google Cloud SDK or add gcloud to PATH"
    )


def format_command(command: list[str]) -> str:
    return " ".join(_quote_part(part) for part in command)


def _quote_part(part: str) -> str:
    if not part:
        return "''"

    if any(ch.isspace() for ch in part):
        return f"'{part}'"

    return part


def _cp_command(
    gcloud_path: str,
    source: Path,
    destination: str,
    content_type: str,
) -> tuple[str, ...]:
    return (
        gcloud_path,
        "storage",
        "cp",
        f"--content-type={content_type}",
        str(source),
        destination,
    )
