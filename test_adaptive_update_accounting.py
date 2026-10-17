from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from src.local_runner.run_batch import (
    _adaptive_report_counts,
    _batch_model_usage,
    _pipeline_progress_payload,
)


class AdaptiveUpdateAccountingTests(unittest.TestCase):
    def state(self, outcomes):
        return {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ticker_order": list(outcomes),
            "tickers": {
                ticker: {"status": "ok" if published else "publish", "current_attempt": 1,
                         "attempts": {"1": {"stages": {
                             "analyze": {"status": "ok", "adaptive_review": {
                                 "status": outcome, "generation_provider": "codex"}},
                             "publish": {"status": "ok" if published else "running"},
                         }}}}
                for ticker, (outcome, published) in outcomes.items()
            },
        }

    def progress(self, state, **kwargs):
        return _pipeline_progress_payload(state, command_id="cmd",
                                          command_action="analyze_market",
                                          generation_provider="codex", **kwargs)

    def test_published_outcomes_are_distinct_from_validated_candidates(self):
        state = self.state({"KEEP": ("retained", True), "EDIT": ("updated", True),
                            "FULL": ("regenerated", True), "PENDING": ("updated", False)})
        payload = self.progress(state)
        self.assertEqual(payload["counts"]["published"], 3)
        self.assertEqual(payload["counts"]["retained_reports"], 1)
        self.assertEqual(payload["counts"]["updated_reports"], 1)
        self.assertEqual(payload["counts"]["regenerated_reports"], 1)
        self.assertEqual(payload["analysis_outcomes"]["updated"],
                         {"count": 2, "tickers": ["EDIT", "PENDING"]})
        self.assertEqual(payload["generation_providers"]["codex"], 4)
        self.assertEqual(payload["fallback_tickers"], [])

    def test_prior_attempt_and_failed_publish_are_not_reported_as_published_update(self):
        state = self.state({"EDIT": ("updated", False)})
        item = state["tickers"]["EDIT"]
        item["attempts"]["1"]["stages"]["publish"]["status"] = "failed"
        item["status"] = "failed"
        payload = self.progress(state)
        self.assertEqual(payload["counts"]["updated_reports"], 0)
        self.assertEqual(payload["counts"]["failed"], 1)
        item["status"] = "prepare"
        item["current_attempt"] = 2
        item["attempts"]["2"] = {"stages": {"prepare": {"status": "ok"}}}
        payload = self.progress(state)
        self.assertEqual(payload["counts"]["updated_reports"], 0)
        self.assertEqual(payload["analysis_outcomes"]["updated"]["count"], 0)

    def test_missing_old_stage_review_can_use_terminal_workflow(self):
        state = self.state({"EDIT": ("updated", True)})
        state["tickers"]["EDIT"]["attempts"]["1"]["stages"]["analyze"].pop("adaptive_review")
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "EDIT.json").write_text(json.dumps({"analysis_workflow": {
                "status": "updated", "effective_model": "gpt-6-luna",
                "generation_provider": "codex"}}), encoding="utf-8")
            payload = self.progress(state, result_dir=root)
        self.assertEqual(payload["counts"]["updated_reports"], 1)
        self.assertEqual(payload["analysis_outcomes"]["updated"]["tickers"], ["EDIT"])

    def test_final_counts_exclude_failed_candidates_and_preserve_legacy_outcomes(self):
        results = [
            {"ticker": ticker, "status": status, "analysis_workflow": {"status": outcome}}
            for ticker, status, outcome in (("KEEP", "ok", "retained"),
                ("EDIT", "ok", "updated"), ("FULL", "ok", "regenerated"),
                ("FAIL", "failed", "updated"), ("OLD", "ok", "unknown"))
        ]
        self.assertEqual(_adaptive_report_counts(results), {
            "retained_reports": 1, "updated_reports": 1, "regenerated_reports": 1})
        self.assertEqual(_adaptive_report_counts([]), {
            "retained_reports": 0, "updated_reports": 0, "regenerated_reports": 0})

    def test_update_model_usage_uses_real_luna_receipts_not_planned_sol(self):
        result = {"ticker": "EDIT", "status": "ok", "route": {
            "reason": "adaptive_luna_sol_itv", "model": "gpt-6.1-sol"},
            "analysis_workflow": {"status": "updated", "effective_model": "gpt-6-luna",
                "receipts": [{"model": "gpt-6-luna", "kind": "triage"},
                             {"model": "gpt-6-luna", "kind": "update"}]}}
        usage = _batch_model_usage([result])
        self.assertEqual(usage["base"], {"Luna": ["EDIT"]})
        self.assertEqual(usage["reviews"], {"Luna": ["EDIT"]})
        result["analysis_workflow"]["receipts"] = []
        self.assertEqual(_batch_model_usage([result])["base"], {"Luna": ["EDIT"]})


if __name__ == "__main__":
    unittest.main()
