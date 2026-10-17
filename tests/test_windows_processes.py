"""Cleanup safety checks: all terminating operations are mocked."""
import ctypes
import os
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from src.local_runner import windows_processes as proc


class ExactProcessCleanupTests(unittest.TestCase):
    def test_denied_open_only_skipped_with_confirmed_wait_only_exit(self):
        kernel = Mock()
        kernel.OpenProcess.side_effect = [None, 42]
        kernel.WaitForSingleObject.return_value = 0
        with patch.object(ctypes, 'get_last_error', return_value=5):
            self.assertIsNone(proc._open_process(kernel, 0x1001, 123, proc.time.monotonic() + 1))
        self.assertEqual(kernel.OpenProcess.call_args.args, (0x100000, False, 123))
        kernel.CloseHandle.assert_called_once_with(42)
        kernel.TerminateProcess.assert_not_called()

    def test_denied_open_with_still_live_waiter_is_not_hidden(self):
        kernel = Mock()
        kernel.OpenProcess.side_effect = [None, 42]
        kernel.WaitForSingleObject.return_value = 258
        with patch.object(ctypes, 'get_last_error', return_value=5):
            with self.assertRaises(PermissionError):
                proc._open_process(kernel, 0x1001, 123, proc.time.monotonic())
        kernel.CloseHandle.assert_called_once_with(42)
        kernel.TerminateProcess.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows process handles')
    def test_real_exited_child_handle_is_safe_without_image_metadata(self):
        # Our own harmless child exits naturally. No external process is killed.
        with subprocess.Popen([sys.executable, '-c', 'pass'], creationflags=subprocess.CREATE_NO_WINDOW) as child:
            child.wait(timeout=15)
            kernel = proc._kernel()
            try:
                proc._image(kernel, int(child._handle))
            except OSError as exc:
                print('Exited child image query: winerror=' + str(exc.winerror))
            self.assertIsNone(proc._live_image(kernel, int(child._handle), proc.time.monotonic()))

    def test_exact_image_rechecked_on_same_handle_then_bounded_wait(self):
        kernel = Mock()
        kernel.OpenProcess.return_value = 42
        kernel.WaitForSingleObject.side_effect = [258, 258, 0]
        expected = os.path.normcase(os.path.realpath('E:/isolated/jre/bin/java.exe'))
        with patch.object(proc, '_kernel', return_value=kernel), patch.object(proc, '_matching_pids', return_value=[123]), patch.object(proc, '_image', return_value=expected) as image:
            self.assertEqual(proc.stop_processes_by_executable(expected), [123])
        image.assert_called_once_with(kernel, 42)
        kernel.TerminateProcess.assert_called_once_with(42, 1)
        self.assertLessEqual(kernel.WaitForSingleObject.call_args.args[1], 15000)
        kernel.CloseHandle.assert_called_once_with(42)

    def test_reused_pid_other_java_never_killed(self):
        kernel = Mock()
        kernel.WaitForSingleObject.return_value = 258
        with patch.object(proc, '_kernel', return_value=kernel), patch.object(proc, '_matching_pids', return_value=[123]), patch.object(proc, '_image', return_value='C:/personal/java.exe'):
            self.assertEqual(proc.stop_processes_by_executable('E:/isolated/java.exe'), [])
        kernel.TerminateProcess.assert_not_called()
        kernel.CloseHandle.assert_called_once()

    def test_timeout_is_visible_and_handle_closed(self):
        kernel = Mock()
        kernel.WaitForSingleObject.return_value = 258
        expected = os.path.normcase(os.path.realpath('E:/isolated/java.exe'))
        with patch.object(proc, '_kernel', return_value=kernel), patch.object(proc, '_matching_pids', return_value=[123]), patch.object(proc, '_image', return_value=expected):
            with self.assertRaisesRegex(RuntimeError, 'cleanup_timeout'):
                proc.stop_processes_by_executable(expected, timeout_seconds=0.01)
        kernel.CloseHandle.assert_called_once()

    def test_wait_failure_never_authorizes_termination(self):
        kernel = Mock()
        kernel.WaitForSingleObject.return_value = 0xFFFFFFFF
        expected = os.path.normcase(os.path.realpath('E:/isolated/java.exe'))
        with patch.object(proc, '_kernel', return_value=kernel), patch.object(proc, '_matching_pids', return_value=[123]), patch.object(proc, '_image', return_value=expected):
            with self.assertRaises(OSError):
                proc.stop_processes_by_executable(expected)
        kernel.TerminateProcess.assert_not_called()
        kernel.CloseHandle.assert_called_once()

    def test_denied_termination_is_not_hidden(self):
        kernel = Mock()
        kernel.WaitForSingleObject.return_value = 258
        kernel.TerminateProcess.return_value = False
        expected = os.path.normcase(os.path.realpath('E:/isolated/java.exe'))
        with patch.object(proc, '_kernel', return_value=kernel), patch.object(proc, '_matching_pids', return_value=[123]), patch.object(proc, '_image', return_value=expected):
            with self.assertRaises(OSError):
                proc.stop_processes_by_executable(expected)
        kernel.CloseHandle.assert_called_once()

    def test_already_terminating_process_is_awaited_not_reported_as_denied(self):
        kernel = Mock()
        kernel.OpenProcess.return_value = 42
        kernel.WaitForSingleObject.side_effect = [258, 258, 0]
        kernel.TerminateProcess.return_value = False
        expected = os.path.normcase(os.path.realpath('E:/isolated/java.exe'))
        with patch.object(proc, '_kernel', return_value=kernel), patch.object(proc, '_matching_pids', return_value=[123]), patch.object(proc, '_image', return_value=expected), patch.object(ctypes, 'get_last_error', return_value=5):
            self.assertEqual(proc.stop_processes_by_executable(expected), [])
        self.assertGreater(kernel.WaitForSingleObject.call_args.args[1], 0)
        self.assertLessEqual(kernel.WaitForSingleObject.call_args.args[1], 15000)
        kernel.CloseHandle.assert_called_once_with(42)

    def test_exited_or_denied_open_never_terminates_a_pid_blindly(self):
        for error in (87, 5):
            kernel = Mock()
            kernel.OpenProcess.return_value = None
            with self.subTest(error=error), patch.object(proc, '_kernel', return_value=kernel), patch.object(proc, '_matching_pids', return_value=[123]), patch.object(ctypes, 'get_last_error', return_value=error):
                if error == 87:
                    self.assertEqual(proc.stop_processes_by_executable('E:/isolated/java.exe'), [])
                else:
                    with self.assertRaises(OSError):
                        proc.stop_processes_by_executable('E:/isolated/java.exe')
            kernel.TerminateProcess.assert_not_called()

    def test_relative_path_and_invalid_timeout_rejected_before_enumerating(self):
        for path, timeout in (('java.exe',15), ('E:/isolated/java.exe',0)):
            with patch.object(proc, '_kernel') as kernel:
                with self.assertRaises(ValueError):
                    proc.stop_processes_by_executable(path, timeout_seconds=timeout)
                kernel.assert_not_called()

    def test_enumerator_checks_exact_path_and_closes_all_handles(self):
        kernel = Mock()
        kernel.WaitForSingleObject.return_value = 258
        kernel.CreateToolhelp32Snapshot.return_value = 99
        def first(snapshot, ptr):
            ptr._obj.szExeFile, ptr._obj.th32ProcessID = 'java.exe', 11
            return True
        def next_entry(snapshot, ptr):
            if ptr._obj.th32ProcessID == 11:
                ptr._obj.szExeFile, ptr._obj.th32ProcessID = 'java.exe', 22
                return True
            return False
        kernel.Process32FirstW.side_effect = first
        kernel.Process32NextW.side_effect = next_entry
        kernel.OpenProcess.side_effect = [101,102]
        with patch.object(proc, '_image', side_effect=['E:/isolated/java.exe','C:/personal/java.exe']), patch.object(ctypes, 'get_last_error', return_value=18):
            self.assertEqual(proc._matching_pids(kernel,'E:/isolated/java.exe'), [11])
        self.assertEqual([call.args[0] for call in kernel.CloseHandle.call_args_list], [101,102,99])
        kernel.TerminateProcess.assert_not_called()

    def test_partial_enumeration_blocks_cleanup(self):
        kernel = Mock()
        kernel.Process32FirstW.return_value = False
        with patch.object(ctypes, 'get_last_error', return_value=5):
            with self.assertRaises(OSError):
                proc._matching_pids(kernel,'E:/isolated/java.exe')
        kernel.CloseHandle.assert_called_once()

    def test_dead_handle_does_not_query_removed_image(self):
        kernel = Mock()
        kernel.WaitForSingleObject.return_value = 0
        with patch.object(proc, '_image') as image:
            self.assertIsNone(proc._live_image(kernel, 42, proc.time.monotonic() + 1))
        image.assert_not_called()

    def test_exit_during_image_query_is_confirmed_on_same_handle(self):
        kernel = Mock()
        kernel.WaitForSingleObject.side_effect = [258, 0]
        with patch.object(proc, '_image', side_effect=PermissionError('image removed')):
            self.assertIsNone(proc._live_image(kernel, 42, proc.time.monotonic() + 1))
        self.assertEqual([c.args[0] for c in kernel.WaitForSingleObject.call_args_list], [42, 42])
        self.assertLessEqual(kernel.WaitForSingleObject.call_args.args[1], 1000)

    def test_live_access_denial_and_failed_wait_remain_errors(self):
        for state in (258, 0xFFFFFFFF):
            kernel = Mock()
            kernel.WaitForSingleObject.side_effect = [258, state]
            denied = PermissionError('real denial')
            with self.subTest(state=state), patch.object(proc, '_image', side_effect=denied):
                with self.assertRaises(PermissionError) as caught:
                    proc._live_image(kernel, 42, proc.time.monotonic())
                self.assertIs(caught.exception, denied)
            kernel.TerminateProcess.assert_not_called()

    def test_exit_during_killing_handle_identity_check_never_terminates(self):
        kernel = Mock()
        kernel.OpenProcess.return_value = 42
        kernel.WaitForSingleObject.side_effect = [258, 0]
        with patch.object(proc, '_kernel', return_value=kernel), patch.object(proc, '_matching_pids', return_value=[123]), patch.object(proc, '_image', side_effect=PermissionError('exited')):
            self.assertEqual(proc.stop_processes_by_executable('E:/isolated/java.exe'), [])
        kernel.TerminateProcess.assert_not_called()
        kernel.CloseHandle.assert_called_once_with(42)

    def test_enumeration_exit_race_skips_dead_process_and_keeps_live_match(self):
        kernel = Mock()
        kernel.CreateToolhelp32Snapshot.return_value = 99
        def first(snapshot, ptr):
            ptr._obj.szExeFile, ptr._obj.th32ProcessID = 'java.exe', 11
            return True
        def next_entry(snapshot, ptr):
            if ptr._obj.th32ProcessID == 11:
                ptr._obj.th32ProcessID = 22
                return True
            return False
        kernel.Process32FirstW.side_effect = first
        kernel.Process32NextW.side_effect = next_entry
        kernel.OpenProcess.side_effect = [101, 102]
        kernel.WaitForSingleObject.side_effect = [258, 0, 258]
        with patch.object(proc, '_image', side_effect=[PermissionError('exited'), 'E:/isolated/java.exe']), patch.object(ctypes, 'get_last_error', return_value=18):
            self.assertEqual(proc._matching_pids(kernel, 'E:/isolated/java.exe'), [22])
        self.assertEqual([c.args[0] for c in kernel.CloseHandle.call_args_list], [101,102,99])
        for call in kernel.OpenProcess.call_args_list:
            self.assertTrue(call.args[0] & 0x100000)
        kernel.TerminateProcess.assert_not_called()


if __name__ == '__main__':
    unittest.main()
