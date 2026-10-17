from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from src.local_runner import analysis_state


class AnalysisStateGcsReadTests(unittest.TestCase):
    def test_lock_treats_windows_permission_error_as_contention(self) -> None:
        with TemporaryDirectory() as temporary:
            lock_path = Path(temporary) / "read.lock"
            real_open = analysis_state.os.open
            calls = 0

            def open_after_contention(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise PermissionError(13, "busy")
                return real_open(*args, **kwargs)

            with patch.object(
                analysis_state.os,
                "open",
                side_effect=open_after_contention,
            ):
                with analysis_state._exclusive_read_lock(lock_path):
                    self.assertTrue(lock_path.exists())

            self.assertEqual(calls, 2)
            self.assertFalse(lock_path.exists())

    def test_release_retries_windows_sharing_violation(self) -> None:
        lock_path = Mock()
        lock_path.unlink.side_effect = [PermissionError(32, "busy"), None]
        with patch.object(analysis_state.time, "sleep") as sleep:
            analysis_state._release_lock(lock_path)

        self.assertEqual(lock_path.unlink.call_count, 2)
        sleep.assert_called_once_with(0.1)

    def test_fresh_incomplete_lock_is_not_removed(self) -> None:
        with TemporaryDirectory() as temporary:
            lock_path = Path(temporary) / "read.lock"
            lock_path.write_text("", encoding="utf-8")

            self.assertFalse(analysis_state._remove_stale_lock(lock_path))
            self.assertTrue(lock_path.exists())

    def test_old_incomplete_lock_is_removed(self) -> None:
        with TemporaryDirectory() as temporary, patch.object(
            analysis_state,
            "GCS_READ_LOCK_INITIALIZATION_GRACE_SECONDS",
            0,
        ):
            lock_path = Path(temporary) / "read.lock"
            lock_path.write_text("", encoding="utf-8")

            self.assertTrue(analysis_state._remove_stale_lock(lock_path))
            self.assertFalse(lock_path.exists())

    def test_windows_process_probe_does_not_send_a_signal(self) -> None:
        with patch.object(
            analysis_state.ctypes.windll.kernel32,
            "OpenProcess",
            return_value=123,
        ) as open_process, patch.object(
            analysis_state.ctypes.windll.kernel32,
            "GetExitCodeProcess",
            side_effect=lambda handle, code: setattr(code._obj, "value", 259) or 1,
        ), patch.object(
            analysis_state.ctypes.windll.kernel32,
            "CloseHandle",
        ) as close_handle, patch.object(
            analysis_state.os,
            "kill",
        ) as kill:
            self.assertTrue(analysis_state._process_exists(456))

        open_process.assert_called_once_with(0x1000, False, 456)
        close_handle.assert_called_once_with(123)
        kill.assert_not_called()

    def test_retries_timed_out_gcs_read_then_returns_content(self) -> None:
        self._assert_exited_process_is_not_alive()
        success = subprocess.CompletedProcess([], 0, stdout='{"ok": true}', stderr="")
        with TemporaryDirectory() as temporary, patch.object(
            analysis_state, "GCS_READ_LOCK_PATH", Path(temporary) / "read.lock"
        ), patch.object(
            analysis_state, "GCS_READ_TIMEOUT_SECONDS", 1
        ), patch.object(
            analysis_state, "require_gcloud", return_value="gcloud.cmd"
        ), patch.object(
            analysis_state,
            "run_bounded",
            side_effect=[subprocess.TimeoutExpired([], 1), success],
        ) as run:
            self.assertEqual(analysis_state.read_text_gcs("gs://bucket/item"), '{"ok": true}')
        self.assertEqual(run.call_count, 2)

    def _assert_exited_process_is_not_alive(self) -> None:
        with patch.object(analysis_state.ctypes.windll.kernel32, "OpenProcess", return_value=123), patch.object(analysis_state.ctypes.windll.kernel32, "CloseHandle"), patch.object(analysis_state.ctypes.windll.kernel32, "GetExitCodeProcess", side_effect=lambda handle, code: setattr(code._obj, "value", 0) or 1):
            self.assertFalse(analysis_state._process_exists(456))

    def test_fails_closed_after_repeated_gcs_timeouts(self) -> None:
        with TemporaryDirectory() as temporary, patch.object(
            analysis_state, "GCS_READ_LOCK_PATH", Path(temporary) / "read.lock"
        ), patch.object(
            analysis_state, "GCS_READ_TIMEOUT_SECONDS", 1
        ), patch.object(
            analysis_state, "require_gcloud", return_value="gcloud.cmd"
        ), patch.object(
            analysis_state,
            "run_bounded",
            side_effect=[
                subprocess.TimeoutExpired([], 1),
                subprocess.TimeoutExpired([], 1),
            ],
        ):
            with self.assertRaisesRegex(RuntimeError, "gcs_read_failed"):
                analysis_state.read_text_gcs("gs://bucket/item")

    def test_missing_gcs_object_is_not_a_transport_failure(self) -> None:
        missing = subprocess.CompletedProcess(
            [], 1, stdout="", stderr="ERROR: gs://bucket/item not found"
        )
        with TemporaryDirectory() as temporary, patch.object(
            analysis_state, "GCS_READ_LOCK_PATH", Path(temporary) / "read.lock"
        ), patch.object(
            analysis_state, "require_gcloud", return_value="gcloud.cmd"
        ), patch.object(analysis_state, "run_bounded", return_value=missing):
            self.assertIsNone(analysis_state.read_text_gcs("gs://bucket/item"))


if __name__ == "__main__":
    unittest.main()
