import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.local_runner import command_worker as worker


class TrackingDuringAnalysisTests(unittest.TestCase):
    def test_quiet_analysis_services_tracking_before_output_closes(self):
        called = []

        def child_output():
            yield 'starting\n'
            self.assertTrue(event.wait(3), 'tracking was blocked by child stdout')
            yield 'finished\n'

        import threading
        event = threading.Event()
        child = SimpleNamespace(stdout=child_output(), poll=lambda: None)
        def tick():
            called.append(True)
            event.set()
        self.assertEqual(worker._collect_output(child, on_wait=tick), ['starting\n', 'finished\n'])
        self.assertEqual(called, [True])

    def test_tracking_poll_failure_preserves_analysis_output(self):
        child = SimpleNamespace(stdout=io.StringIO('OK: 46/46\n'), poll=lambda: None)
        callback = Mock(side_effect=RuntimeError('GCS offline'))
        self.assertEqual(worker._collect_output(child, on_wait=callback), ['OK: 46/46\n'])
        callback.assert_called_once()

    def test_filtered_queue_does_not_claim_analysis_or_trust_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(worker, 'require_gcloud', return_value='gcloud'), \
                 patch.object(worker, 'list_pending_commands', return_value=['looks_like_buy.json']), \
                 patch.object(worker, '_gcloud_cat', return_value='{"action":"analyze_market"}'), \
                 patch.object(worker, '_run_gcloud') as mutate:
                self.assertIsNone(worker.process_one_gcs_command(
                    repo_root=Path(directory), empty_result=None,
                    allowed_actions=worker.TRACKING_ACTIONS,
                ))
                mutate.assert_not_called()

    def test_tracking_drains_in_order_and_stops_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(worker, 'process_one_gcs_command', side_effect=[0, 0, None]) as process:
                worker.service_pending_tracking(repo_root=Path(directory))
                self.assertEqual(process.call_count, 3)
                self.assertEqual(process.call_args.kwargs['allowed_actions'], worker.TRACKING_ACTIONS)
            with patch.object(worker, 'process_one_gcs_command', return_value=1) as process:
                worker.service_pending_tracking(repo_root=Path(directory))
                process.assert_called_once()

    def test_tracking_work_does_not_recursively_poll(self):
        request = worker.CommandRequest.from_payload({
            'id': 'buy', 'action': worker.ACTION_BUY_SHOT, 'ticker': 'SNDK',
        })
        child = SimpleNamespace(stdout=io.StringIO('OK market_tracking\n'), wait=lambda: 0)
        with patch.object(worker.subprocess, 'Popen', return_value=child), \
             patch.object(worker, 'service_pending_tracking') as service:
            result = worker.execute_command(request, worker.build_execution(request), repo_root=Path('.'), dry_run=False)
            self.assertEqual(result['status'], 'ok')
            service.assert_not_called()


if __name__ == '__main__':
    unittest.main()
