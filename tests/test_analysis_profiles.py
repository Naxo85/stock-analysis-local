from __future__ import annotations

import argparse
import unittest

from src.local_runner.run_batch import (
    CORE_TICKERS_GCS_URI,
    PROFILE_REASONING_EFFORT,
    _resolve_analysis_profile,
)
from src.local_runner.run_one import DEFAULT_CODEX_MODEL, DEFAULT_REASONING_EFFORT


class AnalysisProfileTests(unittest.TestCase):
    def test_trading_is_the_default_profile(self) -> None:
        args = argparse.Namespace(analysis_profile=None, config_gcs=None)

        profile = _resolve_analysis_profile(args)

        self.assertEqual(profile, "trading")
        self.assertEqual(PROFILE_REASONING_EFFORT[profile], "medium")

    def test_core_config_automatically_selects_medium_effort(self) -> None:
        args = argparse.Namespace(
            analysis_profile=None,
            config_gcs=CORE_TICKERS_GCS_URI,
        )

        profile = _resolve_analysis_profile(args)

        self.assertEqual(profile, "core")
        self.assertEqual(PROFILE_REASONING_EFFORT[profile], "medium")

    def test_single_ticker_defaults_to_sol_medium(self) -> None:
        self.assertEqual(DEFAULT_CODEX_MODEL, "gpt-5.6-sol")
        self.assertEqual(DEFAULT_REASONING_EFFORT, "medium")


if __name__ == "__main__":
    unittest.main()
