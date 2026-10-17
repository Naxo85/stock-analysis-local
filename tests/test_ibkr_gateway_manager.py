from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.local_runner.ibkr_gateway_manager import (
    _archive_rejected_profile,
    _recover_rejected_profile,
    _repair_gateway_settings,
    ensure_gateway,
    is_gateway_available,
    restart_gateway,
)


class EnsureGatewayTests(unittest.TestCase):
    def test_recovery_waits_for_own_launcher_before_orphan_cleanup(self):
        from src.local_runner import ibkr_gateway_manager as manager
        events = []
        process = Mock()
        process.wait.side_effect = lambda **kwargs: events.append('wait')
        with patch.object(manager, '_terminate_process_tree', side_effect=lambda p: events.append('terminate')), patch.object(manager, '_stop_stale_ibkr_processes', side_effect=lambda p: events.append('orphans')):
            with self.assertRaisesRegex(RuntimeError, 'settings_recovery_repeated'):
                _recover_rejected_profile(Path('.'), process, Path('startup.log'),
                    host='127.0.0.1', port=7497, timeout_seconds=180,
                    poll_interval_seconds=2, already_attempted=True)
        self.assertEqual(events, ['terminate', 'wait', 'orphans'])

    def test_rejected_profile_is_archived_without_touching_root_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = root / ".local" / "ibgateway-settings"
            account = settings / "account-id"
            account.mkdir(parents=True)
            (settings / "jts.ini").write_text("keep")
            (account / "ibg.Mon.xml").write_text("backup")
            log = root / "startup.log"
            log.write_text(f"File does not exist {account / 'ibg.xml'}\n")
            archive = _archive_rejected_profile(root, log)
            self.assertFalse(account.exists())
            self.assertEqual((archive / "ibg.Mon.xml").read_text(), "backup")
            self.assertEqual((settings / "jts.ini").read_text(), "keep")

    def test_recovery_refuses_profile_outside_settings_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "startup.log"
            log.write_text(f"File does not exist {root / 'ibg.xml'}\n")
            with self.assertRaisesRegex(RuntimeError, "outside_settings"):
                _archive_rejected_profile(root, log)
            self.assertTrue(log.exists())

    @patch("src.local_runner.ibkr_gateway_manager._stop_stale_ibkr_processes")
    @patch("src.local_runner.ibkr_gateway_manager._terminate_process_tree")
    @patch("src.local_runner.ibkr_gateway_manager.ensure_gateway")
    def test_recovery_stops_after_one_profile_recreation(self, ensure, terminate, _stop):
        process = Mock()
        with self.assertRaisesRegex(RuntimeError, "settings_recovery_repeated"):
            _recover_rejected_profile(Path("."), process, Path("startup.log"),
                host="127.0.0.1", port=7497, timeout_seconds=180,
                poll_interval_seconds=2, already_attempted=True)
        terminate.assert_called_once_with(process)
        ensure.assert_not_called()

    def test_restores_missing_encrypted_settings_from_daily_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Path(temp_dir)
            account = settings / "account-id"
            account.mkdir()
            backup = account / "ibg.Fri.xml"
            backup.write_bytes(b"IBGZENC" + b"x" * 256)

            restored = _repair_gateway_settings(settings)

            current = account / "ibg.xml"
            self.assertEqual(restored, [current])
            self.assertEqual(current.read_bytes(), backup.read_bytes())

    def test_promotes_newer_temporary_settings_over_stale_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Path(temp_dir)
            account = settings / "account-id"
            account.mkdir()
            current = account / "ibg.xml"
            temporary = account / "ibg.tmp.xml"
            current.write_bytes(b"IBGZENC" + b"old" * 100)
            temporary.write_bytes(b"IBGZENC" + b"new" * 100)
            temporary_mtime = current.stat().st_mtime + 10
            os.utime(temporary, (temporary_mtime, temporary_mtime))
            expected = temporary.read_bytes()

            restored = _repair_gateway_settings(settings)

            self.assertEqual(restored, [current])
            self.assertEqual(current.read_bytes(), expected)
            self.assertFalse(temporary.exists())

    def test_keeps_current_when_temporary_settings_are_older(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Path(temp_dir)
            account = settings / "account-id"
            account.mkdir()
            current = account / "ibg.xml"
            temporary = account / "ibg.tmp.xml"
            temporary.write_bytes(b"IBGZENC" + b"old" * 100)
            current.write_bytes(b"IBGZENC" + b"new" * 100)
            temporary_mtime = current.stat().st_mtime - 10
            os.utime(temporary, (temporary_mtime, temporary_mtime))
            stale = temporary.read_bytes()

            restored = _repair_gateway_settings(settings)

            self.assertEqual(restored, [])
            self.assertNotEqual(current.read_bytes(), stale)
            self.assertFalse(temporary.exists())

    def test_removes_stale_temporary_file_after_backup_restore(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Path(temp_dir)
            account = settings / "account-id"
            account.mkdir()
            temporary = account / "ibg.tmp.xml"
            temporary.write_bytes(b"not-a-valid-settings-file")
            backup = account / "ibg.Mon.xml"
            backup.write_bytes(b"IBGZENC" + b"backup" * 50)

            restored = _repair_gateway_settings(settings)

            current = account / "ibg.xml"
            self.assertEqual(restored, [current])
            self.assertEqual(current.read_bytes(), backup.read_bytes())
            self.assertFalse(temporary.exists())

    @patch("src.local_runner.ibkr_gateway_manager.is_gateway_available", return_value=True)
    @patch("src.local_runner.ibkr_gateway_manager.subprocess.Popen")
    def test_does_not_launch_when_port_is_available(self, popen: Mock, _check: Mock) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = ensure_gateway(Path(temp_dir))

        self.assertEqual(result, "already_running")
        popen.assert_not_called()

    @patch("src.local_runner.ibkr_gateway_manager.is_gateway_available", return_value=False)
    def test_requires_local_config_before_launch(self, _check: Mock) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(RuntimeError, "ibkr_gateway_autostart_not_configured"):
                ensure_gateway(Path(temp_dir), timeout_seconds=1)

    @patch(
        "src.local_runner.ibkr_gateway_manager.is_gateway_available",
        side_effect=(False, False, True),
    )
    @patch("src.local_runner.ibkr_gateway_manager.time.sleep")
    @patch("src.local_runner.ibkr_gateway_manager._stop_stale_ibkr_processes")
    @patch("src.local_runner.ibkr_gateway_manager.subprocess.run")
    @patch("src.local_runner.ibkr_gateway_manager.subprocess.Popen")
    def test_launches_ibc_and_waits_for_port(
        self,
        popen: Mock,
        _run: Mock,
        _stop: Mock,
        _sleep: Mock,
        _check: Mock,
    ) -> None:
        process = popen.return_value
        process.poll.return_value = None

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for path in (
                root / ".local" / "ibc" / "scripts" / "StartIBC.bat",
                root / ".local" / "ibc" / "IBC.jar",
                root
                / ".local"
                / "ibgateway"
                / "ibgateway-offline"
                / "ibgateway.vmoptions",
                root / "secrets" / "ibc" / "config.ini",
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()

            result = ensure_gateway(root, timeout_seconds=5, poll_interval_seconds=0)

        self.assertEqual(result, "started")
        popen.assert_called_once()
        command = popen.call_args.args[0]
        self.assertIn("/Gateway", command)
        self.assertIn("/Mode:paper", command)
        self.assertTrue(any(item.startswith("/Config:") for item in command))
        self.assertTrue(any(item.startswith("/JavaPath:") for item in command))
        creationflags = popen.call_args.kwargs["creationflags"]
        self.assertTrue(creationflags & subprocess.CREATE_NO_WINDOW)

    @patch("src.local_runner.ibkr_gateway_manager.socket.create_connection", side_effect=ConnectionRefusedError())
    def test_closed_port_does_not_start_noisy_ib_handshake(self, _tcp):
        import ib_insync
        with patch.object(ib_insync, 'IB') as factory:
            self.assertFalse(is_gateway_available())
        factory.assert_not_called()

    @patch("src.local_runner.ibkr_gateway_manager.socket.create_connection")
    def test_open_tcp_still_requires_real_readonly_handshake(self, tcp):
        import ib_insync
        with patch.object(ib_insync, 'IB') as factory:
            factory.return_value.isConnected.return_value = True
            self.assertTrue(is_gateway_available())
            factory.return_value.connect.assert_called_once()
            self.assertTrue(factory.return_value.connect.call_args.kwargs['readonly'])
            factory.return_value.disconnect.assert_called_once()
        tcp.return_value.__exit__.assert_called_once()

    @patch("src.local_runner.ibkr_gateway_manager.socket.create_connection")
    def test_open_port_with_wrong_service_never_reports_healthy(self, _tcp):
        import ib_insync
        with patch.object(ib_insync, 'IB') as factory:
            factory.return_value.connect.side_effect = TimeoutError()
            factory.return_value.isConnected.return_value = False
            self.assertFalse(is_gateway_available())

    def test_cleanup_delegates_only_exact_isolated_java_path(self):
        from src.local_runner.ibkr_gateway_manager import _stop_stale_ibkr_processes
        with patch('src.local_runner.windows_processes.stop_processes_by_executable') as stop:
            root = Path('E:/isolated/gateway')
            _stop_stale_ibkr_processes(root)
        stop.assert_called_once_with(str((root/'jre/bin/java.exe').resolve()), timeout_seconds=15)

    @patch("src.local_runner.ibkr_gateway_manager.time.sleep")
    @patch("src.local_runner.ibkr_gateway_manager._stop_stale_ibkr_processes")
    @patch("src.local_runner.ibkr_gateway_manager.is_gateway_available", return_value=False)
    @patch("src.local_runner.ibkr_gateway_manager.ensure_gateway")
    def test_restart_retries_one_autostart_timeout(
        self,
        ensure: Mock,
        _available: Mock,
        stop: Mock,
        _sleep: Mock,
    ) -> None:
        ensure.side_effect = (
            RuntimeError("ibkr_gateway_autostart_timeout: unavailable after 120s"),
            "started",
        )

        result = restart_gateway(Path("E:/repo"), timeout_seconds=120)

        self.assertEqual(result, "restarted:started")
        self.assertEqual(ensure.call_count, 2)
        self.assertEqual(stop.call_count, 2)


if __name__ == "__main__":
    unittest.main()
