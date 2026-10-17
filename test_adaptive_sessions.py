import json
import subprocess
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from src.local_runner import adaptive_codex as codex, adaptive_sessions as sessions


class SessionTests(unittest.TestCase):
    def test_contracts_separate_kind_model_schema_effort_tools_and_policy(self):
        base = dict(workspace=Path.cwd(), cli="codex-v1", kind="triage", model="gpt-6-luna",
                    effort="medium", instructions="triage policy", schema={"type": "object"},
                    research=False, config_args=["-c", "web_search=disabled"])
        first = sessions.contract_key(**base)
        self.assertEqual(first, sessions.contract_key(**base))
        for key, value in dict(cli="codex-v2", kind="report", model="gpt-6.1-sol", effort="high",
                              instructions="full report policy", schema=None, research=True,
                              config_args=["-c", "web_search=live"]).items():
            self.assertNotEqual(first, sessions.contract_key(**{**base, key: value}))

    def test_six_concurrent_leases_have_distinct_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            barrier = threading.Barrier(6)
            paths, errors = [], []
            def task():
                try:
                    with sessions.session_lease(root, "contract", parallel=6, wait_seconds=5) as lease:
                        paths.append(lease.path)
                        barrier.wait(timeout=5)
                except Exception as exc: errors.append(exc)
            threads = [threading.Thread(target=task) for _ in range(6)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(timeout=10)
            self.assertEqual(errors, [])
            self.assertEqual(len(set(paths)), 6)
            self.assertFalse(list(root.rglob("*.lock")))

    def test_dirty_corrupt_and_wrong_contract_never_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            id = str(uuid.uuid4())
            for state in ([], {"clean": True, "thread_id": "bad", "contract": "key"},
                          {"clean": False, "thread_id": id, "contract": "key"},
                          {"clean": True, "thread_id": id, "contract": "other"}):
                path.write_text(json.dumps(state), encoding="utf-8")
                self.assertIsNone(sessions.SessionLease(path, "key").thread_id)
            path.write_text(json.dumps({"clean": True, "thread_id": id, "contract": "key"}))
            lease = sessions.SessionLease(path, "key")
            self.assertEqual(lease.thread_id, id)
            self.assertTrue(lease.reused)
            self.assertFalse(json.loads(path.read_text())["clean"])

    def calls(self, failure=None, reset_error=None):
        root = Path(self.tmp.name)
        calls = []
        id = str(uuid.uuid4())
        def execute(command, **kwargs):
            calls.append((command[:], kwargs))
            if failure == "timeout": raise subprocess.TimeoutExpired(command, 1)
            events = [{"type": "thread.started", "thread_id": id},
                      {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 40,
                                                            "output_tokens": 10}}]
            Path(command[command.index("--output-last-message")+1]).write_text("response", encoding="utf-8")
            return subprocess.CompletedProcess(command, 1 if failure else 0,
                                               "\n".join(json.dumps(e) for e in events), "")
        results = []
        with patch.object(codex, "require_codex", return_value="codex"), patch.object(codex, "run_bounded", side_effect=execute), patch.object(sessions, "reset_session", side_effect=reset_error) as reset:
            for symbol in ("FIRST", "SECOND"):
                try:
                    results.append(codex.call_codex(workspace=root / "work", artifacts=root / symbol,
                        kind="triage", model="gpt-6-luna", effort="medium", instructions="stable",
                        data={"symbol": symbol}, timeout=5, schema={"type": "object"}))
                except RuntimeError as exc: results.append(exc)
        return calls, results, reset.call_count

    def setUp(self): self.tmp = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmp.cleanup()

    def test_resume_preserves_schema_auth_policy_and_only_current_input(self):
        calls, results, resets = self.calls()
        self.assertEqual(resets, 2)
        self.assertFalse(results[0]["session_reused"])
        self.assertTrue(results[1]["session_reused"])
        self.assertTrue(results[1]["session_history_cleared"])
        self.assertEqual(results[0]["session_id"], results[1]["session_id"])
        self.assertNotIn("resume", calls[0][0])
        self.assertIn("resume", calls[1][0])
        self.assertIn("--output-schema", calls[1][0])
        self.assertIn('forced_login_method="chatgpt"', calls[1][0])
        self.assertIn('web_search="disabled"', calls[1][0])
        self.assertNotIn("FIRST", calls[1][1]["input"])
        self.assertIn("SECOND", calls[1][1]["input"])
        self.assertEqual(results[1]["usage"]["cached_input_tokens"], 40)

    def test_reset_failure_retires_slot_but_does_not_repeat_or_discard_response(self):
        calls, results, resets = self.calls(reset_error=RuntimeError("unsupported protocol"))
        self.assertEqual(len(calls), 2)
        self.assertEqual(resets, 2)
        for result in results:
            self.assertEqual(result["text"], "response")
            self.assertFalse(result["session_reused"])
            self.assertFalse(result["session_history_cleared"])
            self.assertEqual(result["session_warning"], "unsupported protocol")
        self.assertFalse(any("resume" in c[0] for c in calls))

    def test_failed_and_ambiguous_calls_are_not_reused_or_repeated(self):
        for failure in ("exit", "timeout"):
            with self.subTest(failure=failure):
                self.tmp.cleanup(); self.tmp = tempfile.TemporaryDirectory()
                calls, results, resets = self.calls(failure=failure)
                self.assertEqual(len(calls), 2)
                self.assertEqual(resets, 0)
                self.assertTrue(all(isinstance(r, RuntimeError) for r in results))
                self.assertFalse(any("resume" in c[0] for c in calls))


if __name__ == "__main__": unittest.main()
