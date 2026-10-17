from __future__ import annotations

import unittest

from stock_analysis.analysis_worker.run_sync import build_analysis_records


def payload(ticker: str, score: float, previous_score: float) -> dict:
    return {
        "symbol": ticker,
        "generated_at": "2026-09-10T10:00:00Z",
        "analysis_status": "ok",
        "validation": {"ok": True},
        "decision": {"score": score, "reference_price": 100.0},
        "plan": {
            "entry": {"lower": 90.0, "upper": 92.0},
            "ambitious_entry": {"lower": 80.0, "upper": 82.0},
        },
        "changes": {"previous_score": previous_score},
    }


class AnalysisScorePersistenceTest(unittest.TestCase):
    def test_another_ticker_update_keeps_existing_alert(self):
        previous_state = {
            "score_presentation_version": 2,
            "report_generations": {"RKLB": "10", "HOOD": "20"},
            "score_presentations": {
                "RKLB": {
                    "background": "#D9EAD3",
                    "note": "La nota subió: 5,4 → 6,1 (+0,7).",
                },
                "HOOD": {"background": None, "note": ""},
            },
        }

        records, failures, presentations = build_analysis_records(
            ("RKLB", "HOOD"),
            {
                "RKLB": payload("RKLB", 6.1, 5.4),
                "HOOD": payload("HOOD", 8.4, 8.2),
            },
            report_generations={"RKLB": "10", "HOOD": "21"},
            previous_state=previous_state,
            visible_scores={"RKLB": 6.1, "HOOD": 8.2},
            report_url_template="https://reports.example/?symbol={ticker}",
        )

        self.assertEqual(failures, {})
        self.assertEqual(records["RKLB"].score_background, "#D9EAD3")
        self.assertIn("5,4", records["RKLB"].score_note)
        self.assertIsNone(records["HOOD"].score_background)
        self.assertEqual(presentations["RKLB"]["background"], "#D9EAD3")

    def test_same_ticker_update_recalculates_and_clears_old_alert(self):
        previous_state = {
            "report_generations": {"RKLB": "10"},
            "score_presentations": {
                "RKLB": {"background": "#D9EAD3", "note": "old alert"}
            },
        }

        records, failures, _ = build_analysis_records(
            ("RKLB",),
            {"RKLB": payload("RKLB", 6.3, 6.1)},
            report_generations={"RKLB": "11"},
            previous_state=previous_state,
            visible_scores={"RKLB": 6.1},
            report_url_template="https://reports.example/?symbol={ticker}",
        )

        self.assertEqual(failures, {})
        self.assertIsNone(records["RKLB"].score_background)
        self.assertEqual(records["RKLB"].score_note, "")


if __name__ == "__main__":
    unittest.main()
