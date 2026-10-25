from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.local_runner import analysis_state as state


class GcsLockInstanceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.lock = Path(self.folder.name) / 'gcs-read.lock'

    def write_lock(self, payload, *, seconds_ago=0):
        self.lock.write_text(json.dumps(payload), encoding='utf-8')
        stamp = time.time_ns() - int(seconds_ago * 1_000_000_000)
        os.utime(self.lock, ns=(stamp, stamp))
        return self.lock.stat().st_mtime_ns

    def test_legacy_pid_reused_after_file_write_is_recovered(self):
        written = self.write_lock({'pid': 104024}, seconds_ago=1800)
        with patch.object(state, '_process_observation', return_value=(True, written + 1200_000_000_000)):
            self.assertTrue(state._remove_stale_lock(self.lock))
        self.assertFalse(self.lock.exists())

    def test_legacy_live_owner_is_not_removed_for_age(self):
        written = self.write_lock({'pid': 123}, seconds_ago=86400)
        with patch.object(state, '_process_observation', return_value=(True, written - 1_000_000)):
            self.assertFalse(state._remove_stale_lock(self.lock))
        self.assertTrue(self.lock.exists())

    def test_alive_without_birth_time_is_unknown_not_stale(self):
        self.write_lock({'pid': 123}, seconds_ago=86400)
        with patch.object(state, '_process_observation', return_value=(True, None)):
            self.assertFalse(state._remove_stale_lock(self.lock))

    def test_unknown_process_is_not_stale(self):
        self.write_lock({'pid': 123}, seconds_ago=86400)
        with patch.object(state, '_process_observation', return_value=(None, None)):
            self.assertFalse(state._remove_stale_lock(self.lock))

    def test_new_identity_keeps_same_owner_even_when_mtime_is_older(self):
        started = time.time_ns() - 30_000_000_000
        self.write_lock({'pid': 123, 'owner_started_ns': started, 'token': 'first'}, seconds_ago=86400)
        with patch.object(state, '_process_observation', return_value=(True, started)):
            self.assertFalse(state._remove_stale_lock(self.lock))

    def test_new_identity_recovers_reused_pid_with_recent_mtime(self):
        started = time.time_ns() - 30_000_000_000
        self.write_lock({'pid': 123, 'owner_started_ns': started, 'token': 'first'})
        with patch.object(state, '_process_observation', return_value=(True, started + 1_000_000)):
            self.assertTrue(state._remove_stale_lock(self.lock))

    def test_invalid_or_future_instance_identity_is_not_proof(self):
        for owner in (-1, True, 'invalid', time.time_ns() + 86400_000_000_000):
            with self.subTest(owner=owner):
                self.write_lock({'pid': 123, 'owner_started_ns': owner}, seconds_ago=86400)
                with patch.object(state, '_process_observation', return_value=(True, time.time_ns())):
                    self.assertFalse(state._remove_stale_lock(self.lock))

    def test_dead_owner_can_be_removed(self):
        self.write_lock({'pid': 123})
        with patch.object(state, '_process_observation', return_value=(False, None)):
            self.assertTrue(state._remove_stale_lock(self.lock))

    def test_unreadable_old_lock_is_not_removed(self):
        self.write_lock({'pid': 123}, seconds_ago=86400)
        with patch.object(state, '_lock_snapshot', side_effect=PermissionError('sharing violation')):
            self.assertFalse(state._remove_stale_lock(self.lock))
        self.assertTrue(self.lock.exists())

    def test_fresh_incomplete_file_stays_but_old_incomplete_is_recoverable(self):
        self.lock.write_bytes(b'')
        self.assertFalse(state._remove_stale_lock(self.lock))
        stamp = time.time() - 60
        os.utime(self.lock, (stamp, stamp))
        self.assertTrue(state._remove_stale_lock(self.lock))

    def test_changed_file_is_not_reaped(self):
        self.write_lock({'pid': 123, 'token': 'old'})
        before = state._lock_snapshot(self.lock)
        self.write_lock({'pid': 456, 'token': 'new'})
        self.assertFalse(state._unlink_unchanged_lock(self.lock, before))
        self.assertEqual(json.loads(self.lock.read_text())['token'], 'new')

    def test_replacement_during_owner_probe_is_not_reaped(self):
        self.write_lock({'pid': 123, 'token': 'old'})
        def replaced(pid):
            self.write_lock({'pid': 456, 'token': 'new'})
            return False, None
        with patch.object(state, '_process_observation', side_effect=replaced):
            self.assertFalse(state._remove_stale_lock(self.lock))
        self.assertEqual(json.loads(self.lock.read_text())['token'], 'new')

    def test_release_preserves_another_acquisition_token(self):
        self.write_lock({'pid': os.getpid(), 'token': 'replacement'})
        state._release_lock(self.lock, expected_token='original')
        self.assertTrue(self.lock.exists())

    def test_release_removes_its_own_token(self):
        self.write_lock({'pid': os.getpid(), 'token': 'original'})
        state._release_lock(self.lock, expected_token='original')
        self.assertFalse(self.lock.exists())

    def test_acquisition_records_identity_and_releases_on_exception(self):
        with self.assertRaisesRegex(ValueError, 'body failed'):
            with state._exclusive_read_lock(self.lock):
                payload = json.loads(self.lock.read_text())
                self.assertEqual(payload['pid'], os.getpid())
                self.assertEqual(len(payload['token']), 32)
                if os.name == 'nt':
                    self.assertIsInstance(payload['owner_started_ns'], int)
                raise ValueError('body failed')
        self.assertFalse(self.lock.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows instance identity')
    def test_windows_access_denied_is_unknown_and_preserved(self):
        kernel32 = state.ctypes.windll.kernel32
        with patch.object(kernel32, 'OpenProcess', return_value=0), \
             patch.object(kernel32, 'GetLastError', return_value=5):
            self.assertEqual(state._process_observation(123), (None, None))
            self.assertTrue(state._process_exists(123))

    @unittest.skipUnless(os.name == 'nt', 'Windows instance identity')
    def test_windows_nonexistent_pid_is_confirmed_dead(self):
        kernel32 = state.ctypes.windll.kernel32
        with patch.object(kernel32, 'OpenProcess', return_value=0), \
             patch.object(kernel32, 'GetLastError', return_value=87):
            self.assertEqual(state._process_observation(123), (False, None))
            self.assertFalse(state._process_exists(123))

    @unittest.skipUnless(os.name == 'nt', 'Windows instance identity')
    def test_real_windows_process_birth_is_stable_and_before_new_lock(self):
        first = state._process_observation(os.getpid())
        second = state._process_observation(os.getpid())
        self.assertEqual(first, second)
        self.assertTrue(first[0])
        written = self.write_lock({'pid': os.getpid()})
        self.assertLessEqual(first[1], written)
        self.assertFalse(state._remove_stale_lock(self.lock))

    def test_real_child_holds_lock_then_dead_owner_is_recovered(self):
        # Only a local Python child: no gcloud, model, network or project lock.
        source = Path(state.__file__).resolve()
        child = "import importlib.util,json,pathlib,sys,time; s=importlib.util.spec_from_file_location('lock_fixture',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); p=pathlib.Path(sys.argv[2]); c=m._exclusive_read_lock(p); c.__enter__(); print('ready',flush=True); time.sleep(30)"
        proc = subprocess.Popen([sys.executable, '-B', '-u', '-c', child, str(source), str(self.lock)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            self.assertEqual(proc.stdout.readline().strip(), 'ready')
            with patch.object(state, 'GCS_READ_LOCK_TIMEOUT_SECONDS', 0.05):
                with self.assertRaisesRegex(RuntimeError, 'gcs_read_lock_timeout'):
                    with state._exclusive_read_lock(self.lock):
                        self.fail('must not enter while child owns the lock')
            self.assertTrue(self.lock.exists())
            proc.kill()
            proc.wait(timeout=5)
            with state._exclusive_read_lock(self.lock):
                self.assertEqual(json.loads(self.lock.read_text())['pid'], os.getpid())
            self.assertFalse(self.lock.exists())
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
