import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class BaselineArtifactTest(unittest.TestCase):
    def test_legacy_manifest_has_unique_valid_files(self) -> None:
        manifest = json.loads(
            (ROOT / "baseline" / "legacy_source_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        paths = [item["path"] for item in manifest["files"]]

        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(paths)
        for item in manifest["files"]:
            self.assertRegex(item["sha256"], SHA256_PATTERN)

    def test_deployed_service_snapshot_has_unique_revisions(self) -> None:
        snapshot = json.loads(
            (
                ROOT
                / "baseline"
                / "deployed_services_2026-09-05.json"
            ).read_text(encoding="utf-8")
        )
        names = [service["name"] for service in snapshot["services"]]
        revisions = [service["revision"] for service in snapshot["services"]]

        self.assertEqual(len(names), 7)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertFalse(snapshot["cloud_scheduler_api_enabled"])

    def test_universe_counts_match_unique_tickers(self) -> None:
        snapshot = json.loads(
            (ROOT / "baseline" / "universe_2026-09-05.json").read_text(
                encoding="utf-8"
            )
        )
        profiles = {profile["name"]: profile for profile in snapshot["profiles"]}

        self.assertEqual(len(profiles["trading"]["tickers"]), 38)
        self.assertEqual(len(profiles["core"]["tickers"]), 30)
        for profile in profiles.values():
            self.assertEqual(len(profile["tickers"]), len(set(profile["tickers"])))

    def test_market_metric_fixture_has_named_cases(self) -> None:
        fixture = json.loads(
            (
                ROOT
                / "tests"
                / "characterization"
                / "fixtures"
                / "market_metrics.json"
            ).read_text(encoding="utf-8")
        )
        day_names = [case["name"] for case in fixture["day_change_cases"]]
        drawdown_names = [case["name"] for case in fixture["drawdown_cases"]]

        self.assertEqual(len(day_names), len(set(day_names)))
        self.assertEqual(len(drawdown_names), len(set(drawdown_names)))
        self.assertGreaterEqual(len(day_names), 3)
        self.assertGreaterEqual(len(drawdown_names), 4)

    def test_sheet_metric_fixture_preserves_live_formula_contract(self) -> None:
        fixture = json.loads(
            (
                ROOT
                / "tests"
                / "characterization"
                / "fixtures"
                / "sheet_metrics.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(fixture["cells"]["return_5d"]["formula"], "=DELTA5(D2;F2)")
        self.assertEqual(fixture["cells"]["return_20d"]["formula"], "=DELTA20(D2;F2)")
        self.assertEqual(fixture["cells"]["volatility"]["formula"], "=ATR20P(D2)")
        self.assertEqual(
            fixture["cells"]["strength"]["comparison_universe"],
            "all non-empty Trading rows in S:T:U",
        )
        self.assertAlmostEqual(fixture["cases"]["return_5d"]["expected"], 0.1)
        self.assertAlmostEqual(fixture["cases"]["return_20d"]["expected"], 0.2)

    def test_analysis_fixture_is_synthetic_and_structured(self) -> None:
        fixture = json.loads(
            (
                ROOT
                / "tests"
                / "characterization"
                / "fixtures"
                / "analysis_report.json"
            ).read_text(encoding="utf-8")
        )

        self.assertTrue(fixture["source"]["synthetic"])
        self.assertEqual(fixture["expected"]["schema_version"], 2)
        self.assertEqual(fixture["expected"]["decision"]["score"], 7.0)
        self.assertEqual(
            set(fixture["expected"]["plan"]),
            {
                "entry",
                "entry_reason",
                "ambitious_entry",
                "ambitious_entry_reason",
                "management_stop",
                "management_stop_reason",
                "structural_stop",
                "structural_stop_reason",
                "target",
                "target_reason",
            },
        )


if __name__ == "__main__":
    unittest.main()
