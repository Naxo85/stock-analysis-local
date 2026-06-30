from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.local_runner.analyst_ratings import (
    apply_probe_payload,
    build_empty_ratings_state,
)


NOW = datetime(2026, 6, 26, 22, tzinfo=timezone.utc)


def _headline(
    *,
    time: str,
    article_id: str,
    firm: str,
    event_type: str,
    rating: str | None = None,
    rating_bucket: str = "unknown",
    target: float | None = None,
    previous_target: float | None = None,
    headline: str = "headline",
) -> dict:
    return {
        "published_at_raw": time,
        "providerCode": "DJ-N",
        "articleId": article_id,
        "headline_clean": headline,
        "analyst_action": {
            "parse_status": "parsed",
            "event_type": event_type,
            "firm": firm,
            "rating": rating,
            "rating_bucket": rating_bucket,
            "target": target,
            "previous_target": previous_target,
        },
    }


class AnalystRatingsTests(unittest.TestCase):
    def test_rating_update_preserves_existing_target(self):
        state = build_empty_ratings_state(
            symbol="MU",
            now=NOW,
            previous_earnings_date="2026-06-24",
        )
        state = apply_probe_payload(
            state,
            {
                "headlines": [
                    _headline(
                        time="2026-06-25T20:47:00+00:00",
                        article_id="target",
                        firm="Barclays",
                        event_type="price_target_raised",
                        target=2000,
                        previous_target=1175,
                    )
                ]
            },
            now=NOW,
        )
        state = apply_probe_payload(
            state,
            {
                "headlines": [
                    _headline(
                        time="2026-06-25T20:48:00+00:00",
                        article_id="rating",
                        firm="Barclays",
                        event_type="rating_maintained",
                        rating="Overweight",
                        rating_bucket="buy",
                    )
                ]
            },
            now=NOW,
        )

        barclays = state["firms"]["Barclays"]
        self.assertEqual(barclays["target"], 2000)
        self.assertEqual(barclays["previous_target"], 1175)
        self.assertEqual(barclays["target_prior_to_last_change"], 1175)
        self.assertEqual(
            barclays["target_last_event"]["event_type"],
            "price_target_raised",
        )
        self.assertEqual(barclays["rating"], "Overweight")
        self.assertEqual(barclays["rating_bucket"], "buy")
        self.assertEqual(barclays["last_updated"], "2026-06-25T20:48:00+00:00")

    def test_summary_uses_post_earnings_only_when_coverage_is_broad(self):
        state = build_empty_ratings_state(
            symbol="MU",
            now=NOW,
            previous_earnings_date="2026-06-24",
        )
        headlines = [
            _headline(
                time=f"2026-06-25T1{i}:00:00+00:00",
                article_id=f"id{i}",
                firm=f"Firm {i}",
                event_type="rating_maintained",
                rating="Buy",
                rating_bucket="buy",
                target=100 + i,
            )
            for i in range(8)
        ]

        state = apply_probe_payload(state, {"headlines": headlines}, now=NOW)

        self.assertEqual(state["summary_active"]["basis"], "post_earnings_only")
        self.assertEqual(state["summary_active"]["quality"], "high")
        self.assertEqual(state["summary_active"]["active_firm_count"], 8)

    def test_summary_extends_to_180_days_when_post_earnings_coverage_is_thin(self):
        state = build_empty_ratings_state(
            symbol="RKLB",
            now=NOW,
            previous_earnings_date="2026-06-24",
        )
        state = apply_probe_payload(
            state,
            {
                "headlines": [
                    _headline(
                        time="2026-06-25T10:00:00+00:00",
                        article_id="post",
                        firm="Fresh Firm",
                        event_type="rating_maintained",
                        rating="Buy",
                        rating_bucket="buy",
                        target=100,
                    ),
                    _headline(
                        time="2026-04-01T10:00:00+00:00",
                        article_id="old",
                        firm="Older Firm",
                        event_type="rating_maintained",
                        rating="Hold",
                        rating_bucket="hold",
                        target=80,
                    ),
                ]
            },
            now=NOW,
        )

        self.assertEqual(state["summary_active"]["basis"], "post_earnings_plus_180d")
        self.assertEqual(state["summary_active"]["active_firm_count"], 2)


if __name__ == "__main__":
    unittest.main()
