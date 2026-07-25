from __future__ import annotations

import json
import unittest

from src.local_runner.codex_rate_limits import (
    calculate_rate_limit_delta,
    parse_rate_limits_response,
)


class CodexRateLimitTests(unittest.TestCase):
    def test_parses_app_server_snapshot(self) -> None:
        raw = "\n".join(
            (
                json.dumps({"id": 1, "result": {"userAgent": "codex"}}),
                json.dumps(
                    {
                        "id": 2,
                        "result": {
                            "rateLimits": {
                                "limitId": "codex",
                                "planType": "pro",
                                "primary": {
                                    "usedPercent": 25,
                                    "windowDurationMins": 300,
                                    "resetsAt": 1000,
                                },
                                "secondary": {
                                    "usedPercent": 18,
                                    "windowDurationMins": 10080,
                                    "resetsAt": 2000,
                                },
                            },
                            "rateLimitsByLimitId": {
                                "codex": {
                                    "limitId": "codex",
                                    "primary": {
                                        "usedPercent": 25,
                                        "windowDurationMins": 300,
                                        "resetsAt": 1000,
                                    },
                                }
                            },
                        },
                    }
                ),
            )
        )

        snapshot = parse_rate_limits_response(raw)

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot["primary"]["used_percent"], 25)
        self.assertEqual(snapshot["primary"]["window_minutes"], 300)
        self.assertEqual(snapshot["secondary"]["used_percent"], 18)
        self.assertEqual(
            snapshot["by_limit_id"]["codex"]["primary"]["used_percent"],
            25,
        )

    def test_calculates_both_window_deltas(self) -> None:
        before = {
            "primary": {"used_percent": 10, "resets_at": 1000},
            "secondary": {"used_percent": 20, "resets_at": 2000},
        }
        after = {
            "primary": {"used_percent": 13, "resets_at": 1000},
            "secondary": {"used_percent": 21, "resets_at": 2000},
        }

        delta = calculate_rate_limit_delta(before, after)

        self.assertEqual(delta["primary"]["used_percent_delta"], 3)
        self.assertEqual(delta["secondary"]["used_percent_delta"], 1)

    def test_does_not_compare_across_reset_boundary(self) -> None:
        before = {"primary": {"used_percent": 99, "resets_at": 1000}}
        after = {"primary": {"used_percent": 1, "resets_at": 3000}}

        delta = calculate_rate_limit_delta(before, after)

        self.assertIsNone(delta["primary"]["used_percent_delta"])
        self.assertTrue(delta["primary"]["reset_boundary_crossed"])

    def test_marks_counter_reconciliation_without_claiming_reset(self) -> None:
        before = {"primary": {"used_percent": 53, "resets_at": 2000}}
        after = {"primary": {"used_percent": 4, "resets_at": 1968}}

        delta = calculate_rate_limit_delta(before, after)

        self.assertIsNone(delta["primary"]["used_percent_delta"])
        self.assertFalse(delta["primary"]["reset_boundary_crossed"])
        self.assertTrue(delta["primary"]["counter_decreased_or_reconciled"])


if __name__ == "__main__":
    unittest.main()
