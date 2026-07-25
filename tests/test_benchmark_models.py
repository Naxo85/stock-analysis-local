from __future__ import annotations

import unittest

from src.local_runner.benchmark_models import (
    Candidate,
    _build_price_invariance_input,
    _pairwise_summary,
    _parse_candidates,
)


class BenchmarkModelsTests(unittest.TestCase):
    def test_price_invariance_override_changes_only_scenario_context(self) -> None:
        source = "Ticker: RKLB\nlatest_price: 80.665\nsupport: 75\n"

        result = _build_price_invariance_input(source, price=75.0)

        self.assertIn("current/reference price as $75.00", result)
        self.assertIn("must not be moved lower", result)
        self.assertTrue(result.endswith(source))

    def test_parses_candidate(self) -> None:
        candidate = Candidate.parse("gpt-5.6-terra:xhigh")

        self.assertEqual(candidate.model, "gpt-5.6-terra")
        self.assertEqual(candidate.effort, "xhigh")

    def test_rejects_duplicate_candidates(self) -> None:
        with self.assertRaisesRegex(ValueError, "must_be_unique"):
            _parse_candidates(
                ["gpt-5.6-terra:xhigh", "gpt-5.6-terra:xhigh"]
            )

    def test_accepts_one_candidate_for_historical_baseline(self) -> None:
        parsed = _parse_candidates(["gpt-5.5:medium"])

        self.assertEqual(parsed, (Candidate("gpt-5.5", "medium"),))

    def test_pairwise_summary_includes_quota_and_tokens(self) -> None:
        summary = _pairwise_summary(
            [
                {
                    "label": "A",
                    "usage": {"total_tokens": 100, "output_tokens": 20},
                    "duration_seconds": 8,
                    "quota_delta": {
                        "primary": {"used_percent_delta": 2},
                        "secondary": {"used_percent_delta": 1},
                    },
                },
                {
                    "label": "B",
                    "usage": {"total_tokens": 75, "output_tokens": 15},
                    "duration_seconds": 5,
                    "quota_delta": {
                        "primary": {"used_percent_delta": 1},
                        "secondary": {"used_percent_delta": 0},
                    },
                },
            ]
        )

        self.assertEqual(summary["total_tokens_delta_a_minus_b"], 25)
        self.assertNotIn("five_hour_used_percent_delta_a_minus_b", summary)


if __name__ == "__main__":
    unittest.main()
