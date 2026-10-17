import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
from src.local_runner.update_analysis_sources_pipeline import _run_ticker_source_update

class NewsGatewayRecoveryTests(unittest.TestCase):
    def check_recovery(self, healthy):
        with tempfile.TemporaryDirectory() as tmp, patch("src.local_runner.update_analysis_sources_pipeline.run_news_update") as news, patch("src.local_runner.update_analysis_sources_pipeline.is_gateway_available", return_value=healthy), patch("src.local_runner.update_analysis_sources_pipeline.restart_gateway") as restart:
            news.side_effect = [{"status": "failed", "error": "process_timeout_after_90s"}, {"status": "ok"}]
            result = _run_ticker_source_update(
                repo_root=Path(tmp), ticker="IONQ", ticker_index=0, earnings_context={},
                args=Namespace(update_news=True, news_client_id_base=7201, update_analysts=False, host="127.0.0.1", port=7497),
                news_log_dir=Path(tmp), analyst_log_dir=Path(tmp))
            self.assertEqual(news.call_count, 2)
            self.assertEqual(restart.call_count, 0 if healthy else 1)
            self.assertEqual(result["news"]["retried_after_gateway_restart"], not healthy)

    def test_healthy_gateway_is_not_restarted_on_news_timeout(self):
        self.check_recovery(True)

    def test_unavailable_gateway_is_restarted(self):
        self.check_recovery(False)
