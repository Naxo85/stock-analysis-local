from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import stock_analysis.controller.sheet_layout as sheet_layout


class PackagedLayoutTest(unittest.TestCase):
    def test_explicit_runtime_root_points_to_container_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            expected = Path(directory) / "config" / "market_sheet_layout.json"
            with patch.dict(os.environ, {"STOCK_ANALYSIS_ROOT": directory}):
                reloaded = importlib.reload(sheet_layout)
                self.assertEqual(reloaded.DEFAULT_LAYOUT_PATH, expected)
        importlib.reload(sheet_layout)


if __name__ == "__main__":
    unittest.main()
