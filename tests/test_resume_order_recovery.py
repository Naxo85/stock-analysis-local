import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
from src.local_runner.analysis_policy import TickerRecord
from src.local_runner.run_batch import _order_records_for_pipeline_resume, _PipelineTracker

class ResumeOrderTests(unittest.TestCase):
    def test_failed_preflight_is_archived_on_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pipeline_state.json'
            path.write_text(json.dumps({'ticker_order': ['A'], 'status': 'failed', 'fatal_error': {'message': 'prompt_not_available'}, 'finished_at': '2026-09-24T13:16:00Z', 'tickers': {'A': {'status': 'queued', 'current_attempt': 1, 'attempts': {}}}}))
            _PipelineTracker(path, tickers=('A',), source='test', started_at=datetime.now(timezone.utc), resume=True)
            saved = json.loads(path.read_text())
            self.assertEqual(saved['status'], 'running')
            self.assertNotIn('fatal_error', saved)
            self.assertNotIn('finished_at', saved)
            self.assertEqual(saved['failure_history'][0]['fatal_error']['message'], 'prompt_not_available')
            self.assertEqual(saved['tickers']['A']['status'], 'queued')

    def test_preserves_checkpoint_order_and_ownership(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pipeline_state.json'
            path.write_text(json.dumps({'ticker_order': ['B', 'A']}))
            records = [TickerRecord(ticker='A', owned=True), TickerRecord(ticker='B')]
            ordered = _order_records_for_pipeline_resume(records, path)
            self.assertEqual([r.ticker for r in ordered], ['B', 'A'])
            self.assertIs(ordered[1], records[0])
            self.assertTrue(ordered[1].owned)

    def test_rejects_changed_or_duplicate_tickers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pipeline_state.json'
            for stored in (['B'], ['A', 'B', 'C'], ['A', 'B', 'B'], []):
                path.write_text(json.dumps({'ticker_order': stored}))
                with self.assertRaisesRegex(RuntimeError, 'ticker_mismatch'):
                    _order_records_for_pipeline_resume([TickerRecord(ticker='A'), TickerRecord(ticker='B')], path)

if __name__ == '__main__':
    unittest.main()
