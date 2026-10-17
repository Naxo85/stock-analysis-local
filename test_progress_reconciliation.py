from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.local_runner.progress_reconciliation import reconciled_progress


class ProgressReconciliationTest(unittest.TestCase):
    def test_failed_command_closes_matching_partial_progress(self) -> None:
        original = {
            "command_id": "batch-1", "status": "running", "total": 46,
            "completed": 27, "counts": {"published": 27},
            "heartbeat_at": "2026-09-29T17:50:44Z",
            "current": {"phase": "analyze", "ticker": "RKLB"},
        }
        result = reconciled_progress(
            original,
            {"id": "batch-1", "status": "failed", "finished_at": "2026-09-29T17:51:06Z"},
            now=datetime(2026, 9, 29, 18, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["completed"], 27)
        self.assertEqual(result["counts"], {"published": 27})
        self.assertEqual(result["reconciliation"]["unpublished"], 19)
        self.assertEqual(original["status"], "running")
        self.assertRaises(
            ValueError, reconciled_progress, original,
            {"id": "another", "status": "failed"},
        )
        resumed = dict(original, heartbeat_at="2026-09-29T18:42:49Z")
        self.assertRaises(
            ValueError, reconciled_progress, resumed,
            {"id": "batch-1", "status": "failed", "finished_at": "2026-09-29T17:51:06Z"},
        )


if __name__ == "__main__":
    unittest.main()
