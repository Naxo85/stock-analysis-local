from __future__ import annotations

import copy
import unittest

from stock_analysis.analysis_worker.run_sync import effective_sync_version
from stock_analysis.controller.sheet_layout import load_market_sheet_layout


class AnalysisSyncVersionTest(unittest.TestCase):
    def test_projection_change_invalidates_unchanged_reports(self) -> None:
        layout = load_market_sheet_layout()
        changed = copy.deepcopy(layout)
        changed["links"]["report"] += "&preview=1"

        self.assertNotEqual(
            effective_sync_version("same-reports", layout),
            effective_sync_version("same-reports", changed),
        )

    def test_table_move_invalidates_unchanged_reports(self) -> None:
        layout = load_market_sheet_layout()
        changed = copy.deepcopy(layout)
        changed["blocks"][1]["start_column"] = "N"
        changed["blocks"][1]["end_column"] = "Y"

        self.assertNotEqual(
            effective_sync_version("same-reports", layout),
            effective_sync_version("same-reports", changed),
        )


if __name__ == "__main__":
    unittest.main()
