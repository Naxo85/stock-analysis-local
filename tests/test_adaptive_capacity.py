"""No provider calls: deterministic capacity, crash, admission and process tests."""
from contextlib import ExitStack
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from src.local_runner import adaptive_capacity as capacity, adaptive_codex as codex
from src.local_runner import adaptive_stage as stage, adaptive_budget as budget
from src.local_runner import run_batch as batch
from src.local_runner.adaptive_context import model_context, serialize_model_input
from test_adaptive_analysis import POLICY, StageTests


def failure(message="Selected model is at capacity", **extra):
    return json.dumps({"type": "turn.failed", "error": {"message": message, **extra}})


class FakeClock:
    def __init__(self): self.now = 1000.0
    def time(self): return self.now
    def monotonic(self): return self.now
    def sleep(self, seconds): self.now += seconds
    def module(self): return SimpleNamespace(time=self.time, monotonic=self.monotonic, sleep=self.sleep)


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.clock = FakeClock()
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(capacity, "time", self.clock.module()))
        self.stack.enter_context(patch.object(capacity.random, "uniform", return_value=0))
    def tearDown(self):
        self.stack.close()
        self.temp.cleanup()
    def state(self): return json.loads((self.root / "capacity/state.json").read_text())
    def lease(self, parallel=6, wait=5):
        return capacity.capacity_lease(self.root, parallel=parallel, wait_seconds=wait)
    def overload(self):
        with self.lease() as lease:
            lease.feedback(failure={"code": "model_at_capacity", "retry_after_seconds": None}, success=False)
    def success(self):
        with self.lease() as lease: lease.feedback(failure=None, success=True)

    def test_error_classification_never_retries_ambiguous_or_completed(self):
        self.assertIsNotNone(capacity.capacity_failure(1, failure(), ""))
        for code in ("server_is_overloaded", "server_overloaded", "slow_down", "model_at_capacity"):
            with self.subTest(code=code):
                events = failure("transient", code=code)
                self.assertIsNotNone(capacity.capacity_failure(1, events, ""))
                self.assertTrue(codex.retryable_failure(1, events, ""))
        for exit_code, events, response in (
                (None, failure(), ""), (0, failure(), ""), (1, failure(), "report"),
                (1, failure() + '\n{"type":"turn.completed"}', ""),
                (1, failure() + '\nnot-json', ""), (1, '["turn.failed"]', ""),
                (1, '{"type":"turn.failed","error":"at capacity"}', ""),
                (1, '{"type":"turn.started"}', ""),
                (1, failure("usage limit", code="insufficient_quota"), ""),
                (1, failure("Selected model is at capacity; quota exhausted"), ""),
                (1, failure("authentication failed", code="server_overloaded"), ""),
                (1, failure("connection reset"), "")):
            with self.subTest(events=events, exit_code=exit_code):
                self.assertIsNone(capacity.capacity_failure(exit_code, events, response))
        self.assertTrue(codex.retryable_failure(1, failure("connection reset"), ""))
        self.assertFalse(codex.retryable_failure(1, failure("Selected model is at capacity; quota exhausted"), ""))

    def test_hints_numeric_date_invalid_and_no_cap_on_provider_minimum(self):
        self.assertEqual(capacity.retry_after_seconds({"retry_after_seconds": 250}), 250)
        self.assertEqual(capacity.retry_after_seconds({"retry_after": "31"}), 31)
        self.assertEqual(capacity.retry_after_seconds({"headers": {"Retry-After": "Thu, 01 Jan 1970 00:17:40 GMT"}}, now=1000), 60)
        self.assertEqual(capacity.retry_after_seconds({"retry_after": 10, "headers": {"retry-after": "90"}}), 90)
        for value in (True, None, -1, "NaN", "inf", "not-a-date", {}):
            with self.subTest(value=value):
                self.assertIsNone(capacity.retry_after_seconds({"retry_after": value}))
        with self.lease() as lease:
            lease.feedback(failure={"code": "server_overloaded", "retry_after_seconds": 250}, success=False)
        self.assertEqual(self.state()["cooldown_until"], 1250)
        with self.assertRaises(capacity.CapacityWaitTimeout):
            with self.lease(wait=2): self.fail("no CLI allowed")
        self.assertEqual(self.state()["active"], {})

    def test_wave_deduplicates_late_failures_and_ignores_old_success(self):
        with ExitStack() as stack:
            leases = [stack.enter_context(self.lease()) for _ in range(6)]
            leases[0].feedback(failure={"code":"model_at_capacity", "retry_after_seconds":None}, success=False)
            self.assertEqual(self.state()["limit"], 3)
            leases[1].feedback(failure=None, success=True)
            self.assertEqual(self.state()["successes"], 0)
            for lease in leases[2:]:
                lease.feedback(failure={"code":"model_at_capacity", "retry_after_seconds":None}, success=False)
            self.assertEqual(self.state()["limit"], 3)
            self.assertEqual(self.state()["capacity_streak"], 1)
            with self.assertRaises(capacity.CapacityWaitTimeout):
                with self.lease(wait=1): pass
            self.assertEqual(len(self.state()["active"]), 6)  # Never cancel the old wave.
        self.assertEqual(self.state()["active"], {})
        self.clock.now = 1011
        self.overload()
        self.assertEqual(self.state()["limit"], 1)
        self.assertEqual(self.state()["cooldown_until"], 1031)

    def test_backoff_grows_is_bounded_and_jitter_applies(self):
        for index, delay in enumerate((10, 20, 40, 80, 120, 120)):
            with self.subTest(index=index):
                with patch.object(capacity.random, "uniform", return_value=1.5): self.overload()
                state = self.state()
                self.assertAlmostEqual(state["cooldown_until"] - self.clock.now, delay + 1.5)
                self.clock.now = state["cooldown_until"] + 1
        self.assertEqual(self.state()["limit"], 1)

    def test_recovery_requires_both_good_calls_and_time_one_slot_at_a_time(self):
        self.overload()
        self.clock.now = 1011
        for _ in range(3): self.success()
        self.assertEqual(self.state()["limit"], 3)
        self.clock.now = 1031
        self.success()
        self.assertEqual(self.state()["limit"], 4)
        for expected in (5, 6):
            for _ in range(3): self.success()
            self.assertEqual(self.state()["limit"], expected - 1)
            self.clock.now += 31
            self.success()
            self.assertEqual(self.state()["limit"], expected)
        self.success()
        self.assertEqual(self.state()["limit"], 6)

    def test_failure_from_request_admitted_before_recovery_still_reduces(self):
        self.overload()
        self.clock.now = 1031
        with self.lease() as late:
            for _ in range(3): self.success()
            self.assertEqual(self.state()["limit"], 4)
            late.feedback(failure={"code":"model_at_capacity", "retry_after_seconds":None}, success=False)
            self.assertEqual(self.state()["limit"], 2)

    def test_cap_shared_for_all_contracts_and_waiting_permit_releases(self):
        with ExitStack() as stack:
            for _ in range(6): stack.enter_context(self.lease())
            with self.assertRaises(capacity.CapacityWaitTimeout):
                with self.lease(wait=1): self.fail("seventh request admitted")
        with self.lease() as lease: self.assertEqual(lease.admission["limit_at_admission"], 6)
        self.assertFalse((self.root / "capacity/state.lock").exists())

    def test_timeout_crash_cleanup_dead_pids_and_corrupt_state_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "simulated crash"):
            with self.lease(): raise RuntimeError("simulated crash")
        self.assertEqual(self.state()["active"], {})
        state = self.state()
        state["active"]["dead"] = {"pid": 2147483647, "epoch": 0}
        (self.root / "capacity/state.json").write_text(json.dumps(state))
        with self.lease(): self.assertNotIn("dead", self.state()["active"])
        (self.root / "capacity/state.json").write_text("not-json")
        with self.assertRaisesRegex(RuntimeError, "capacity_state_invalid"):
            with self.lease(): self.fail("must not start")

    def test_restarted_controller_does_not_reset_reduced_limit(self):
        self.overload()
        self.clock.now = 1011
        with capacity.capacity_lease(self.root, parallel=6, wait_seconds=1) as lease:
            self.assertEqual(lease.admission["limit_at_admission"], 3)
        with self.lease(parallel=2) as lease:
            self.assertEqual(lease.admission["limit_at_admission"], 2)
        with self.lease(parallel=6) as lease:
            self.assertEqual(lease.admission["limit_at_admission"], 2)

    def test_cli_records_capacity_reduction_without_switch_or_automatic_call(self):
        calls = []
        def execute(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 1, failure(), "")
        with patch.object(codex, "require_codex", return_value="codex"), patch.object(codex, "run_bounded", side_effect=execute):
            with self.assertRaisesRegex(RuntimeError, "codex_call_failed_no_fallback"):
                codex.call_codex(workspace=self.root, artifacts=self.root / "CAT", kind="report",
                    instructions="stable", data={"symbol":"CAT"}, model="gpt-6.1-sol", effort="high", timeout=5)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][calls[0].index("-m") + 1], "gpt-6.1-sol")
        receipt = json.loads((self.root / "CAT/report.receipt.json").read_text())
        self.assertTrue(receipt["retryable_failure"])
        self.assertEqual(receipt["capacity_control"]["outcome"], "capacity_failure")
        self.assertEqual(self.state()["limit"], 3)
        self.assertEqual(self.state()["active"], {})

    def test_cleanup_failure_keeps_completed_receipt_but_next_admission_blocks(self):
        with self.lease() as lease:
            (self.root / "capacity/state.json").write_text("corrupt")
            lease.feedback(failure=None, success=True)
        self.assertEqual(lease.receipt()["outcome"], "success")
        self.assertIn("capacity_state_invalid", lease.receipt()["warning"])
        with self.assertRaisesRegex(RuntimeError, "capacity_state_invalid"):
            with self.lease(): self.fail("cannot admit")

    def test_no_started_admission_is_not_paid_or_unknown_usage(self):
        calls = [
            {"model":"gpt-6.1-sol", "usage":{"input_tokens":100,"cached_input_tokens":50,"output_tokens":20}},
            {"model":"gpt-6.1-sol", "usage":None, "no_model_started":False},
            {"model":"gpt-6-luna", "usage":None, "no_model_started":True},
            {"usage":None},
        ]
        measured = batch._measured_adaptive_usage(calls)
        self.assertNotIn("gpt-6-luna", measured)
        self.assertEqual(measured["gpt-6.1-sol"]["calls"], 2)
        self.assertEqual(measured["gpt-6.1-sol"]["unknown_usage_calls"], 1)
        self.assertEqual(measured["gpt-6.1-sol"]["input_tokens"], 100)
        self.assertEqual(measured["unconfirmed"]["unknown_usage_calls"], 1)

    def test_next_submission_waits_and_repeated_capacity_backs_off(self):
        self.overload()
        calls = []
        def execute(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 1, failure(), "")
        with patch.object(codex, "require_codex", return_value="codex"), patch.object(codex, "run_bounded", side_effect=execute):
            with self.assertRaisesRegex(RuntimeError, "codex_call_failed_no_fallback"):
                codex.call_codex(workspace=self.root, artifacts=self.root / "CAT", kind="report",
                    instructions="stable", data={"symbol":"CAT"}, model="gpt-6.1-sol", effort="high", timeout=15)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][calls[0].index("-m") + 1], "gpt-6.1-sol")
        receipt = json.loads((self.root / "CAT/report.receipt.json").read_text())
        self.assertTrue(receipt["retryable_failure"])
        self.assertEqual(receipt["capacity_control"]["outcome"], "capacity_failure")
        self.assertEqual(receipt["capacity_control"]["limit_at_admission"], 3)
        self.assertGreaterEqual(receipt["capacity_control"]["waited_seconds"], 10)
        self.assertEqual(self.state()["limit"], 1)
        self.assertAlmostEqual(self.state()["cooldown_until"] - self.clock.now, 20)
        self.assertEqual(self.state()["active"], {})


class ProcessTests(unittest.TestCase):
    def test_actual_cli_timeout_is_not_admission_failure_or_capacity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(codex, "require_codex", return_value="codex"), patch.object(codex, "run_bounded",
                    side_effect=subprocess.TimeoutExpired("codex", 1)) as model:
                with self.assertRaisesRegex(RuntimeError, "model_timeout_no_automatic_fallback"):
                    codex.call_codex(workspace=root / "work", artifacts=root / "CAT", kind="report",
                        instructions="stable", data={"symbol":"CAT"}, model="gpt-6.1-sol", effort="high", timeout=1)
            self.assertEqual(model.call_count, 1)
            receipt = json.loads((root / "CAT/report.receipt.json").read_text())
            self.assertFalse(receipt['retryable_failure'])
            self.assertFalse(receipt['no_model_started'])
            self.assertEqual(receipt['timeout_reconciliation']['state'], 'unknown')
            state = json.loads((root / "work/capacity/state.json").read_text())
            self.assertEqual(state["limit"], 6)
            self.assertEqual(state["active"], {})

    def test_wait_failure_without_model_gets_bound_receipt_and_safe_re_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "CAT"
            work.mkdir()
            (work / "instructions.md").write_text("stable")
            context = StageTests().context()
            policy = {**POLICY, "report_timeout_seconds": 1}
            ledger = root / "budget.json"
            with patch.object(budget, "read_codex_rate_limits", return_value={"primary":{"used_percent":20}}), \
                    patch.object(codex, "require_codex", return_value="codex"), \
                    patch.object(codex, "capacity_lease", side_effect=capacity.CapacityWaitTimeout("capacity_wait_timeout_no_model_call")), \
                    patch.object(codex, "run_bounded", side_effect=AssertionError("NO CLI ALLOWED")) as cli:
                with self.assertRaises(capacity.CapacityWaitTimeout):
                    stage.model_call(root, work, "CAT", ledger, policy, "report", context)
                cli.assert_not_called()
            receipt = json.loads((work / "report.receipt.json").read_text())
            self.assertTrue(receipt["no_model_started"])
            self.assertTrue(budget.read_json(ledger)["calls"]["CAT:report"]["no_model_started"])
            self.assertEqual(receipt["input_sha256"], hashlib.sha256(serialize_model_input(model_context(context)).encode()).hexdigest())
            def execute(command, **kwargs):
                response = Path(command[command.index("--output-last-message") + 1])
                response.write_text("valid completed report")
                events = [{"type":"thread.started", "thread_id":str(uuid.uuid4())},
                          {"type":"turn.completed", "usage":{"input_tokens":100,"cached_input_tokens":40,"output_tokens":10}}]
                return subprocess.CompletedProcess(command, 0, "\n".join(json.dumps(e) for e in events), "")
            with patch.object(budget, "read_codex_rate_limits", return_value={"primary":{"used_percent":20}}) as quota, \
                    patch.object(codex, "require_codex", return_value="codex"), \
                    patch.object(codex, "run_bounded", side_effect=execute) as cli, \
                    patch("src.local_runner.adaptive_sessions.reset_session"):
                result = stage.model_call(root, work, "CAT", ledger, policy, "report", context)
                repeated = stage.model_call(root, work, "CAT", ledger, policy, "report", context)
            self.assertEqual(cli.call_count, 1)
            self.assertEqual(quota.call_count, 1)
            self.assertEqual(result["text"], repeated["text"])
            self.assertFalse(budget.read_json(ledger)["calls"]["CAT:report"]["no_model_started"])
            history = budget.read_json(ledger)["failed_call_history"]["CAT:report"]
            self.assertEqual(len(history), 1)
            self.assertTrue(history[0]["no_model_started"])

    def test_no_start_marker_does_not_override_hashes_or_evidence_of_execution(self):
        for tamper in ("input_sha256", "model", "events", "response"):
            with self.subTest(tamper=tamper), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                work = root / "CAT"
                work.mkdir()
                (work / "instructions.md").write_text("stable")
                context = StageTests().context()
                ledger = root / "budget.json"
                instructions = codex.report_instructions("stable", research=POLICY["report_web_research_enabled"])
                receipt = {"no_model_started":True, "retryable_failure":True, "exit_code":124,
                    "failure_type":"capacity_admission_timeout", "model":POLICY["report_model"],
                    "reasoning_effort":POLICY["report_effort"], "research_enabled":POLICY["report_web_research_enabled"],
                    "input_sha256":hashlib.sha256(serialize_model_input(model_context(context)).encode()).hexdigest(),
                    "instructions_sha256":hashlib.sha256(instructions.encode()).hexdigest(),
                    "schema_sha256":hashlib.sha256(json.dumps(None,sort_keys=True).encode()).hexdigest()}
                if tamper in ("input_sha256", "model"): receipt[tamper] = "wrong"
                elif tamper == "events": (work / "report.events.jsonl").write_text('{"type":"turn.started"}')
                else: (work / "report.response").write_text("completed response")
                budget.write_json(work / "report.receipt.json", receipt)
                budget.write_json(ledger, {"policy":POLICY, "calls":{"CAT:report":{"status":"failed"}}})
                with patch.object(stage,"call_codex", side_effect=AssertionError("NO MODEL ALLOWED")) as cli:
                    with self.assertRaisesRegex(RuntimeError, "already_reserved"):
                        stage.model_call(root,work,"CAT",ledger,POLICY,"report",context)
                    cli.assert_not_called()

    def test_distinct_processes_share_one_global_limit(self):
        # Real child processes, but no CLI/model/network: each holds only a lease.
        script = '''import json, sys, time
from pathlib import Path
from src.local_runner.adaptive_capacity import capacity_lease
root = Path(sys.argv[1])
with capacity_lease(root, parallel=3, wait_seconds=15):
    print("admitted", flush=True)
    time.sleep(.2)
'''
        with tempfile.TemporaryDirectory() as tmp:
            children = [subprocess.Popen([sys.executable, "-B", "-c", script, tmp], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0) for _ in range(6)]
            maximum = 0
            path = Path(tmp) / "capacity/state.json"
            deadline = time.monotonic() + 20
            while any(child.poll() is None for child in children) and time.monotonic() < deadline:
                if path.exists():
                    try: maximum = max(maximum, len(json.loads(path.read_text())["active"]))
                    except (OSError, ValueError): pass
                time.sleep(.01)
            for child in children:
                stdout, stderr = child.communicate(timeout=5)
                self.assertEqual(child.returncode, 0, stderr)
                self.assertEqual(stdout.strip(), "admitted")
            self.assertGreaterEqual(maximum, 2)
            self.assertLessEqual(maximum, 3)
            self.assertEqual(json.loads(path.read_text())["active"], {})

    def test_healthy_six_threads_can_still_run_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            barrier = threading.Barrier(6)
            errors = []
            def worker():
                try:
                    with capacity.capacity_lease(root, parallel=6, wait_seconds=10): barrier.wait(timeout=10)
                except Exception as exc: errors.append(str(exc))
            threads = [threading.Thread(target=worker) for _ in range(6)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(timeout=15)
            self.assertEqual(errors, [])
            self.assertFalse(any(thread.is_alive() for thread in threads))


if __name__ == "__main__": unittest.main()
