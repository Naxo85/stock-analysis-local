from __future__ import annotations

import json
import concurrent.futures
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.local_runner.analysis_policy import RouteDecision
from src.local_runner.run_batch import (
    BatchConfig,
    PipelineTask,
    _PipelineTracker,
    _SourceProgressGate,
    _analysis_worker_count,
    _replace_pipeline_state_with_retry,
    _reconcile_pipeline_checkpoint_from_artifacts,
    _reconcile_resumed_web_escalations,
    _resume_pipeline_requires_prepare,
    _run_deferred_chat_cleanup,
    _run_ticker_pass,
)


def _route(ticker: str) -> RouteDecision:
    return RouteDecision(
        ticker=ticker,
        action="run",
        analysis_kind="reference",
        tier="priority",
        model="gpt-5.6-sol",
        reasoning_effort="medium",
        reviewer_model=None,
        reason="test",
        owned=False,
    )


def _config(root: Path, tickers: tuple[str, ...]) -> BatchConfig:
    return BatchConfig(
        repo_root=root,
        tickers=tickers,
        source="test",
        max_parallel=2,
        retry_failed=0,
        upload_real=True,
        log_dir=root / "batch",
        update_analysts=False,
        update_ibkr_news=False,
        analysis_profile="trading",
        routes=tuple(_route(ticker) for ticker in tickers),
        model=None,
        reasoning_effort="medium",
    )


def _ok_stage(task: PipelineTask, stage: str) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "ticker": task.ticker,
        "attempt": task.attempt,
        "stage": stage,
        "status": "ok",
        "exit_code": 0,
        "started_at": now,
        "finished_at": now,
        "duration_seconds": 0.01,
    }


class BatchPipelineTests(unittest.TestCase):
    def test_checkpoint_replace_retries_transient_windows_lock(self) -> None:
        class TemporaryPath:
            def __init__(self) -> None:
                self.calls = 0

            def replace(self, destination: Path) -> None:
                self.calls += 1
                if self.calls == 1:
                    raise PermissionError(5, "locked", str(destination))

        temporary = TemporaryPath()
        with patch("src.local_runner.run_batch.time.sleep"):
            _replace_pipeline_state_with_retry(
                temporary,  # type: ignore[arg-type]
                Path("pipeline_state.json"),
                timeout_seconds=1,
                retry_interval_seconds=0,
            )

        self.assertEqual(temporary.calls, 2)

    def test_resume_recovers_completed_analyze_and_publish_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _config(root, ("AAA", "BBB"))
            state_path = config.log_dir / "pipeline_state.json"
            state_path.parent.mkdir(parents=True)
            started = "2026-09-17T10:00:00+00:00"
            state_path.write_text(
                json.dumps(
                    {
                        "ticker_order": ["AAA", "BBB"],
                        "tickers": {
                            ticker: {
                                "status": "analyze" if ticker == "AAA" else "publish",
                                "current_attempt": 1,
                                "attempts": {
                                    "1": {
                                        "stages": {
                                            "prepare": {"status": "ok"},
                                            "analyze": {
                                                "status": "running",
                                                "started_at": started,
                                            },
                                            **(
                                                {
                                                    "publish": {
                                                        "status": "running",
                                                        "started_at": started,
                                                    }
                                                }
                                                if ticker == "BBB"
                                                else {}
                                            ),
                                        }
                                    }
                                },
                            }
                            for ticker in ("AAA", "BBB")
                        },
                    }
                ),
                encoding="utf-8",
            )
            for ticker in ("AAA", "BBB"):
                output = root / "output" / ticker
                output.mkdir(parents=True)
                (output / "generation_metadata.json").write_text(
                    json.dumps(
                        {
                            "symbol": ticker,
                            "status": "ok",
                            "provider_used": "chatgpt-browser",
                            "started_at": "2026-09-17T10:01:00+00:00",
                            "finished_at": "2026-09-17T10:04:00+00:00",
                        }
                    ),
                    encoding="utf-8",
                )
                (output / "latest.json").write_text(
                    json.dumps(
                        {
                            "symbol": ticker,
                            "analysis_status": "ok",
                            "generated_at": "2026-09-17T10:04:01+00:00",
                        }
                    ),
                    encoding="utf-8",
                )
            publish_logs = root / "logs" / "BBB"
            publish_logs.mkdir(parents=True)
            (publish_logs / "2026-09-17T10-05-00Z.run_full.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "started_at": "2026-09-17T10:05:00+00:00",
                        "finished_at": "2026-09-17T10:06:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            config = BatchConfig(
                **{
                    **config.__dict__,
                    "resume_pipeline_from": state_path,
                }
            )

            _reconcile_pipeline_checkpoint_from_artifacts(config)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(
                state["tickers"]["AAA"]["attempts"]["1"]["stages"]["analyze"]["status"],
                "ok",
            )
            self.assertEqual(state["tickers"]["AAA"]["status"], "analyze")
            self.assertEqual(
                state["tickers"]["BBB"]["attempts"]["1"]["stages"]["publish"]["status"],
                "ok",
            )
            self.assertEqual(state["tickers"]["BBB"]["status"], "ok")

    def test_batch_never_schedules_chat_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queue_path = root / ".local" / "chatgpt-chat-cleanup-queue.json"
            queue_path.parent.mkdir(parents=True)
            queue_path.write_text('[{"chat_id":"one"}]', encoding="utf-8")

            with patch.dict("os.environ", {"CHATGPT_DEFERRED_CHAT_CLEANUP_ENABLED": "1"}, clear=True), patch(
                "src.local_runner.run_batch.subprocess.Popen"
            ) as popen:
                _run_deferred_chat_cleanup(_config(root, ("AAA",)))

            popen.assert_not_called()

    def test_three_web_workers_run_concurrently_within_global_cap(self) -> None:
        pool = type("Pool", (), {"worker_count": 3})()

        self.assertEqual(
            _analysis_worker_count(
                ticker_count=47,
                browser_session=pool,
                generator_fallback=False,
                max_parallel=6,
            ),
            3,
        )
        self.assertEqual(
            _analysis_worker_count(
                ticker_count=47,
                browser_session=pool,
                generator_fallback=True,
                max_parallel=6,
            ),
            6,
        )
        self.assertEqual(
            _analysis_worker_count(
                ticker_count=47,
                browser_session=pool,
                generator_fallback=True,
                max_parallel=2,
            ),
            2,
        )

    def test_resume_retries_terminal_failure_as_new_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "pipeline_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "ticker_order": ["AAA"],
                        "tickers": {
                            "AAA": {
                                "status": "failed",
                                "current_attempt": 1,
                                "attempts": {
                                    "1": {
                                        "stages": {
                                            "prepare": {"status": "ok"},
                                            "analyze": {"status": "ok"},
                                            "publish": {"status": "failed"},
                                        }
                                    }
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            tracker = _PipelineTracker(
                state_path,
                tickers=("AAA",),
                source="test",
                started_at=datetime.now(timezone.utc),
                resume=True,
            )

            attempt = tracker.attempt_for("AAA", None)

            self.assertEqual(attempt, 2)
            self.assertEqual(tracker.next_stage("AAA", attempt), "prepare")
            self.assertFalse(
                _resume_pipeline_requires_prepare(state_path, ("AAA",))
            )

    def test_resume_skips_gateway_when_current_attempt_is_prepared(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "pipeline_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "tickers": {
                            "AAA": {
                                "current_attempt": 2,
                                "attempts": {
                                    "2": {
                                        "stages": {
                                            "prepare": {"status": "ok"},
                                        }
                                    }
                                },
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            self.assertFalse(
                _resume_pipeline_requires_prepare(state_path, ("AAA",))
            )

    def test_resume_requires_gateway_when_prepare_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "pipeline_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "tickers": {
                            "AAA": {
                                "current_attempt": 1,
                                "attempts": {"1": {"stages": {}}},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(
                _resume_pipeline_requires_prepare(state_path, ("AAA",))
            )

    def test_source_gate_fails_closed_for_missing_news(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            progress_dir = Path(temp_dir)
            (progress_dir / "AAA.json").write_text(
                json.dumps(
                    {
                        "ticker": "AAA",
                        "status": "failed",
                        "error": "ibkr_news_update_failed: no current news",
                    }
                ),
                encoding="utf-8",
            )
            future: concurrent.futures.Future[dict[str, object]] = (
                concurrent.futures.Future()
            )
            gate = _SourceProgressGate(progress_dir, future)

            with self.assertRaisesRegex(RuntimeError, "ibkr_news_update_failed"):
                gate.wait("AAA")

    def test_generation_starts_before_all_preparation_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tickers = ("AAA", "BBB")
            config = _config(root, tickers)
            tracker = _PipelineTracker(
                config.log_dir / "pipeline_state.json",
                tickers=tickers,
                source="test",
                started_at=datetime.now(timezone.utc),
                resume=False,
            )
            generation_started = threading.Event()
            generation_active = 0
            maximum_generation_active = 0
            guard = threading.Lock()

            def fake_stage(unused_config, task, stage):
                nonlocal generation_active, maximum_generation_active
                if stage == "prepare" and task.ticker == "BBB":
                    self.assertTrue(generation_started.wait(timeout=2))
                if stage == "analyze":
                    with guard:
                        generation_active += 1
                        maximum_generation_active = max(
                            maximum_generation_active, generation_active
                        )
                    generation_started.set()
                    time.sleep(0.02)
                    with guard:
                        generation_active -= 1
                return _ok_stage(task, stage)

            with patch(
                "src.local_runner.run_batch._run_pipeline_stage",
                side_effect=fake_stage,
            ):
                results = _run_ticker_pass(
                    config, tickers, attempt=1, tracker=tracker
                )

            self.assertEqual([item["status"] for item in results], ["ok", "ok"])
            self.assertEqual(maximum_generation_active, 1)
            state = json.loads(
                (config.log_dir / "pipeline_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["tickers"]["AAA"]["status"], "ok")
            self.assertEqual(state["tickers"]["BBB"]["status"], "ok")

    def test_resume_skips_completed_preparation_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tickers = ("AAA",)
            config = _config(root, tickers)
            state_path = config.log_dir / "pipeline_state.json"
            tracker = _PipelineTracker(
                state_path,
                tickers=tickers,
                source="test",
                started_at=datetime.now(timezone.utc),
                resume=False,
            )
            task = PipelineTask("AAA", 1)
            tracker.stage_started(task, "prepare")
            tracker.stage_finished(task, "prepare", _ok_stage(task, "prepare"))
            resumed = _PipelineTracker(
                state_path,
                tickers=tickers,
                source="test",
                started_at=datetime.now(timezone.utc),
                resume=True,
            )
            invoked: list[str] = []

            def fake_stage(unused_config, current_task, stage):
                invoked.append(stage)
                return _ok_stage(current_task, stage)

            with patch(
                "src.local_runner.run_batch._run_pipeline_stage",
                side_effect=fake_stage,
            ):
                results = _run_ticker_pass(
                    config, tickers, attempt=None, tracker=resumed
                )

            self.assertEqual(invoked, ["analyze", "publish"])
            self.assertEqual(results[0]["status"], "ok")

    def test_browser_analysis_uses_shared_in_process_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tickers = ("AAA", "BBB")
            config = _config(root, tickers)
            tracker = _PipelineTracker(
                config.log_dir / "pipeline_state.json",
                tickers=tickers,
                source="test",
                started_at=datetime.now(timezone.utc),
                resume=False,
            )
            session = object()
            browser_calls: list[tuple[str, object]] = []

            def fake_stage(unused_config, task, stage):
                self.assertNotEqual(stage, "analyze")
                return _ok_stage(task, stage)

            def fake_browser_stage(unused_config, task, current_session):
                browser_calls.append((task.ticker, current_session))
                return _ok_stage(task, "analyze")

            with patch(
                "src.local_runner.run_batch._run_pipeline_stage",
                side_effect=fake_stage,
            ), patch(
                "src.local_runner.run_batch._run_persistent_browser_analyze_stage",
                side_effect=fake_browser_stage,
            ):
                results = _run_ticker_pass(
                    config,
                    tickers,
                    attempt=1,
                    tracker=tracker,
                    browser_session=session,
                )

            self.assertEqual([item["status"] for item in results], ["ok", "ok"])
            self.assertEqual(browser_calls, [("AAA", session), ("BBB", session)])

    def test_shared_browser_can_advance_while_another_worker_is_in_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tickers = ("AAA", "BBB")
            config = _config(root, tickers)
            tracker = _PipelineTracker(
                config.log_dir / "pipeline_state.json",
                tickers=tickers,
                source="test",
                started_at=datetime.now(timezone.utc),
                resume=False,
            )
            first_active = threading.Event()
            second_active = threading.Event()

            def fake_stage(unused_config, task, stage):
                return _ok_stage(task, stage)

            def fake_browser_stage(unused_config, task, current_session):
                if task.ticker == "AAA":
                    first_active.set()
                    self.assertTrue(second_active.wait(timeout=2))
                else:
                    self.assertTrue(first_active.wait(timeout=2))
                    second_active.set()
                return _ok_stage(task, "analyze")

            with patch(
                "src.local_runner.run_batch._run_pipeline_stage",
                side_effect=fake_stage,
            ), patch(
                "src.local_runner.run_batch._run_persistent_browser_analyze_stage",
                side_effect=fake_browser_stage,
            ):
                results = _run_ticker_pass(
                    config,
                    tickers,
                    attempt=1,
                    tracker=tracker,
                    browser_session=object(),
                )

            self.assertEqual([item["status"] for item in results], ["ok", "ok"])

    def test_resume_promotes_valid_web_escalation_without_model_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _config(root, ("AAA",))
            result_path = config.log_dir / "tickers" / "AAA.json"
            result_path.parent.mkdir(parents=True)
            result_path.write_text(
                json.dumps(
                    {
                        "ticker": "AAA",
                        "status": "ok",
                        "analysis_workflow": {
                            "status": "escalation_required",
                        },
                    }
                ),
                encoding="utf-8",
            )
            output = root / "output" / "AAA"
            output.mkdir(parents=True)
            latest_path = output / "latest.json"
            latest_path.write_text(
                json.dumps(
                    {
                        "generation_provider": "chatgpt-browser",
                        "analysis_workflow": {
                            "status": "escalation_required",
                        },
                    }
                ),
                encoding="utf-8",
            )

            def fake_finalize(*_args, **_kwargs):
                latest_path.write_text(
                    json.dumps(
                        {
                            "generation_provider": "chatgpt-browser",
                            "analysis_workflow": {
                                "status": "published_high_confidence_score_locked",
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                return 0

            with patch(
                "src.local_runner.run_batch._finalize_one",
                side_effect=fake_finalize,
            ) as finalize:
                _reconcile_resumed_web_escalations(config)

            finalize.assert_called_once()
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(
                result["analysis_workflow"]["status"],
                "published_high_confidence_score_locked",
            )
            self.assertEqual(
                result["resume_reconciliation"]["status"],
                "promoted_without_model_retry",
            )


if __name__ == "__main__":
    unittest.main()
