from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.local_runner.manage_market_tracking import (
    ACTION_BUY,
    ACTION_REMOVE,
    ACTION_SELL,
    mutate_tracking_state,
    reconcile_portfolio_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = json.loads(
    (
        ROOT
        / "gcp_services"
        / "stock_controller"
        / "config"
        / "market_sheet_layout.json"
    ).read_text(encoding="utf-8")
)


class MarketTrackingMutationTests(unittest.TestCase):
    def test_live_colors_reconcile_stale_local_positions(self) -> None:
        universe = {
            ticker
            for group in LAYOUT["groups"]
            for ticker in group["tickers"]
        }
        snapshot = {ticker: 0 for ticker in universe}
        snapshot["QCOM"] = 1
        snapshot["RKLB"] = 2

        updated = reconcile_portfolio_snapshot(
            LAYOUT,
            {"positions": {"AMD": 1, "RKLB": 3}},
            snapshot,
        )

        self.assertEqual(updated["positions"], {"QCOM": 1, "RKLB": 3})

    def test_buy_existing_increments_from_live_observation(self) -> None:
        portfolio = {"positions": {"AMD": 1}}

        _, updated, result = mutate_tracking_state(
            LAYOUT,
            portfolio,
            action=ACTION_BUY,
            ticker="AMD",
            group_id=None,
            observed_shots=2,
        )

        self.assertEqual(updated["positions"]["AMD"], 3)
        self.assertFalse(result["structure_changed"])

    def test_buy_new_adds_group_and_first_shot(self) -> None:
        portfolio = {"positions": {}}

        layout, updated, result = mutate_tracking_state(
            LAYOUT,
            portfolio,
            action=ACTION_BUY,
            ticker="NEW",
            group_id="ai_platforms",
            observed_shots=0,
        )

        group = next(
            item for item in layout["groups"] if item["id"] == "ai_platforms"
        )
        self.assertIn("NEW", group["tickers"])
        self.assertEqual(updated["positions"]["NEW"], 1)
        self.assertTrue(result["structure_changed"])

    def test_sell_last_shot_keeps_ticker_tracked(self) -> None:
        portfolio = {"positions": {"RKLB": 1}}

        layout, updated, result = mutate_tracking_state(
            LAYOUT,
            portfolio,
            action=ACTION_SELL,
            ticker="RKLB",
            group_id=None,
            observed_shots=1,
        )

        self.assertNotIn("RKLB", updated["positions"])
        self.assertTrue(result["tracked"])
        self.assertFalse(result["structure_changed"])
        self.assertTrue(
            any("RKLB" in group["tickers"] for group in layout["groups"])
        )

    def test_remove_drops_ticker_and_position(self) -> None:
        portfolio = {"positions": {"RKLB": 2}}

        layout, updated, result = mutate_tracking_state(
            LAYOUT,
            portfolio,
            action=ACTION_REMOVE,
            ticker="RKLB",
            group_id=None,
            observed_shots=2,
        )

        self.assertNotIn("RKLB", updated["positions"])
        self.assertFalse(result["tracked"])
        self.assertTrue(result["structure_changed"])
        self.assertFalse(
            any("RKLB" in group["tickers"] for group in layout["groups"])
        )

    def test_new_ticker_requires_a_valid_group(self) -> None:
        with self.assertRaisesRegex(ValueError, "group_required"):
            mutate_tracking_state(
                LAYOUT,
                {"positions": {}},
                action=ACTION_BUY,
                ticker="NEW",
                group_id=None,
                observed_shots=0,
            )


if __name__ == "__main__":
    unittest.main()
