"""Upload local report artifacts to a GCS test prefix using gcloud."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


TEST_BUCKET = "stock-analysis-reports-naxo85"
TEST_PREFIX = "_local_test"


@dataclass(frozen=True)
class UploadPlan:
    symbol: str
    markdown_source: Path
    json_source: Path
    markdown_destination: str
    json_destination: str
    dry_run: bool
    gcloud_path: str


def build_test_upload_plan(
    symbol: str,
    markdown_source: Path,
    json_source: Path,
    *,
    dry_run: bool = True,
) -> UploadPlan:
    gcloud_path = require_gcloud()
    normalized_symbol = symbol.strip().upper()

    return UploadPlan(
        symbol=normalized_symbol,
        markdown_source=markdown_source,
        json_source=json_source,
        markdown_destination=(
            f"gs://{TEST_BUCKET}/{TEST_PREFIX}/{normalized_symbol}/latest.md"
        ),
        json_destination=(
            f"gs://{TEST_BUCKET}/{TEST_PREFIX}/{normalized_symbol}/latest.json"
        ),
        dry_run=dry_run,
        gcloud_path=gcloud_path,
    )


def upload_test_artifacts(plan: UploadPlan) -> list[list[str]]:
    commands = [
        [
            plan.gcloud_path,
            "storage",
            "cp",
            str(plan.markdown_source),
            plan.markdown_destination,
        ],
        [
            plan.gcloud_path,
            "storage",
            "cp",
            str(plan.json_source),
            plan.json_destination,
        ],
    ]

    if plan.dry_run:
        return commands

    for command in commands:
        subprocess.run(command, check=True)

    return commands


def require_gcloud() -> str:
    for command in ("gcloud", "gcloud.cmd"):
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
