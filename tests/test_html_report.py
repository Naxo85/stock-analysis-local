from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.local_runner.gcs_uploader import (
    CONTENT_TYPE_HTML,
    build_real_upload_plan,
    build_test_upload_plan,
)
from src.local_runner.html_report import render_analysis_html


SAMPLE_MARKDOWN = """NBIS

Fecha del análisis: 2026-06-22

**0) Resumen ejecutivo**

Valoración: **8.2 / 10**

- [Fuente](https://example.com/report)

<script>alert('no')</script>
"""


class HtmlReportTests(unittest.TestCase):
    def test_renders_standalone_readable_html(self):
        result = render_analysis_html(SAMPLE_MARKDOWN, symbol="NBIS")

        self.assertIn("<!doctype html>", result)
        self.assertIn("<h1>NBIS</h1>", result)
        self.assertIn("<h2>0) Resumen ejecutivo</h2>", result)
        self.assertIn('<a href="https://example.com/report">Fuente</a>', result)
        self.assertIn("width: min(920px", result)

    def test_escapes_raw_html_from_markdown(self):
        result = render_analysis_html(SAMPLE_MARKDOWN, symbol="NBIS")

        self.assertNotIn("<script>alert", result)
        self.assertIn("&lt;script&gt;", result)

    @patch("src.local_runner.gcs_uploader.require_gcloud", return_value="gcloud")
    def test_real_upload_contains_latest_and_snapshot_html(self, _require_gcloud):
        plan = build_real_upload_plan(
            symbol="NBIS",
            markdown_source=Path("latest.md"),
            html_source=Path("latest.html"),
            json_source=Path("latest.json"),
            analysis_status="ok",
            timestamp_date="2026-06-22",
            timestamp_time="10-00-00",
        )

        self.assertIn(
            "gs://stock-analysis-reports-naxo85/NBIS/latest.html",
            plan.destinations,
        )
        self.assertIn(
            "gs://stock-analysis-reports-naxo85/NBIS/2026-06-22/10-00-00.html",
            plan.destinations,
        )
        self.assertIn(
            "gs://stock-analysis-system-naxo85/runtime/analysis-reports/NBIS.json",
            plan.destinations,
        )
        html_commands = [command for command in plan.commands if "latest.html" in command]
        self.assertTrue(any(f"--content-type={CONTENT_TYPE_HTML}" in command for command in html_commands))

    @patch("src.local_runner.gcs_uploader.require_gcloud", return_value="gcloud")
    def test_test_upload_contains_html(self, _require_gcloud):
        plan = build_test_upload_plan(
            symbol="NBIS",
            markdown_source=Path("latest.md"),
            html_source=Path("latest.html"),
            json_source=Path("latest.json"),
        )

        self.assertIn(
            "gs://stock-analysis-reports-naxo85/_local_test/NBIS/latest.html",
            plan.destinations,
        )


if __name__ == "__main__":
    unittest.main()
