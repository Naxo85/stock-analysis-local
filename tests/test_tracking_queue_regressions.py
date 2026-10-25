from __future__ import annotations
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.local_runner import manage_market_tracking as tracking
from src.local_runner import command_worker as worker

LAYOUT = json.loads(tracking.LAYOUT_PATH.read_text(encoding="utf-8"))

class TrackingQueueRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.layout_path = Path(self.tmp.name) / "layout.json"
        self.portfolio_path = Path(self.tmp.name) / "portfolio.json"
        self.layout_path.write_text(json.dumps(LAYOUT), encoding="utf-8")
        self.portfolio_path.write_text(json.dumps({"positions": {"MRVL": 2, "CLS": 1}}), encoding="utf-8")
        for name, value in (("LAYOUT_PATH", self.layout_path), ("PORTFOLIO_PATH", self.portfolio_path)):
            mock = patch.object(tracking, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        self.snapshot = {ticker: 0 for group in LAYOUT["groups"] for ticker in group["tickers"]}
        self.snapshot.update(MRVL=2, CLS=1)

    def apply(self, action, ticker, command, publish=False, group=None):
        return tracking.apply_tracking_change(
            action=action, ticker=ticker, group_id=group,
            observed_shots=self.snapshot.get(ticker, 0),
            portfolio_snapshot=self.snapshot, command_id=command,
            snapshot_at="2026-10-02T07:34:00Z", publish=publish,
        )

    def positions(self):
        return json.loads(self.portfolio_path.read_text())["positions"]

    def test_mrvl_sale_survives_later_cls_purchase(self):
        self.apply("sell", "MRVL", "sale")
        self.apply("buy", "CLS", "purchase")
        self.assertEqual(self.positions(), {"MRVL": 1, "CLS": 2})

    def test_two_sales_with_same_old_snapshot_reach_zero(self):
        self.apply("sell", "MRVL", "sale-1")
        self.apply("sell", "MRVL", "sale-2")
        self.assertNotIn("MRVL", self.positions())

    def test_two_purchases_with_same_old_snapshot_accumulate(self):
        self.apply("buy", "CLS", "buy-1")
        self.apply("buy", "CLS", "buy-2")
        self.assertEqual(self.positions()["CLS"], 3)

    def test_old_universe_after_remove_or_add_does_not_revert_structure(self):
        self.apply("remove", "MRVL", "remove")
        self.apply("buy", "NEW", "new", group="ai_platforms")
        self.apply("buy", "CLS", "buy")
        self.assertNotIn("MRVL", self.positions())
        self.assertEqual(self.positions()["NEW"], 1)
        self.assertEqual(self.positions()["CLS"], 2)

    def test_retry_after_publication_failure_does_not_repeat_delta(self):
        from src.local_runner import tracking_store
        class Store:
            def read(inner, name):
                path = self.layout_path if name == tracking_store.LAYOUT_OBJECT else self.portfolio_path
                return path.read_text(), 1
            def write(inner, name, body, generation):
                path = self.layout_path if name == tracking_store.LAYOUT_OBJECT else self.portfolio_path
                path.write_text(body)
        with patch.object(tracking_store, 'runtime_store', return_value=Store()), \
             patch.object(tracking, "_upload_runtime_state", side_effect=RuntimeError("offline")):
            with self.assertRaisesRegex(RuntimeError, "offline"):
                self.apply("sell", "MRVL", "sale", publish=True)
        self.assertEqual(self.positions()["MRVL"], 1)
        self.apply("sell", "MRVL", "sale")
        self.assertEqual(self.positions()["MRVL"], 1)

    def test_snapshot_during_publication_preserves_pending_operation(self):
        history = [{"ticker": "MRVL", "applied_at": "2026-10-02T07:33:00Z", "publication_pending": True}]
        self.assertEqual(tracking.snapshot_protected_tickers(history, "2026-10-02T07:34:00Z"), {"MRVL"})
        history[0].update(publication_pending=False, published_at="2026-10-02T07:35:00Z")
        self.assertEqual(tracking.snapshot_protected_tickers(history, "2026-10-02T07:34:00Z"), {"MRVL"})
        self.assertEqual(tracking.snapshot_protected_tickers(history, "2026-10-02T07:36:00Z"), set())

    def test_worker_drains_multiple_commands_under_same_wakeup(self):
        with patch.object(worker, "process_one_gcs_command", side_effect=[0, 0, None]) as process:
            self.assertEqual(worker.drain_gcs_commands(repo_root=Path(self.tmp.name)), 0)
            self.assertEqual(process.call_count, 3)

    def test_worker_stops_after_ambiguous_finalization_failure(self):
        with patch.object(worker, "process_one_gcs_command", return_value=1) as process:
            self.assertEqual(worker.drain_gcs_commands(repo_root=Path(self.tmp.name)), 1)
            self.assertEqual(process.call_count, 1)

    def test_snapshot_timestamp_forwarded_with_legacy_created_at_fallback(self):
        for extra, expected in (({}, "2026-10-02T07:34:00Z"), ({"portfolio_snapshot_at": "2026-10-02T07:33:50Z"}, "2026-10-02T07:33:50Z")):
            request = worker.CommandRequest.from_payload({
                "id": "sale", "action": worker.ACTION_SELL_SHOT,
                "ticker": "MRVL", "created_at": "2026-10-02T07:34:00Z", **extra,
            })
            self.assertEqual(worker._command_environment(request)["PORTFOLIO_SNAPSHOT_AT"], expected)

if __name__ == "__main__":
    unittest.main()
