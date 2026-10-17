from __future__ import annotations

import os
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from src.local_runner.command_worker import (
    ACTION_MARKET,
    CommandRequest,
    _command_environment,
)
from src.local_runner.run_batch import (
    _BatchProgressPublisher,
    _latest_progress_destination,
    _pipeline_progress_payload,
)


def _stage(status: str) -> dict[str, str]:
    return {"status": status}


class LiveBatchProgressTests(unittest.TestCase):
    def test_latest_heartbeat_upload_is_first_and_bounded(self) -> None:
        with TemporaryDirectory() as folder, patch.dict(os.environ, {
            "ANALYSIS_PROGRESS_GCS_URI": "gs://bucket/commands/progress/cmd-1.json",
            "ANALYSIS_COMMAND_ID": "cmd-1",
        }):
            root = Path(folder)
            state = root / "pipeline_state.json"
            state.write_text('{"ticker_order": [], "tickers": {}}', encoding="utf-8")
            config = SimpleNamespace(
                log_dir=root, repo_root=root, generation_provider="chatgpt-browser"
            )
            publisher = _BatchProgressPublisher(config, state)
            with patch("src.local_runner.run_batch.require_gcloud", return_value="gcloud.cmd"), patch(
                "src.local_runner.run_batch.run_bounded",
                return_value=SimpleNamespace(returncode=0),
            ) as upload:
                publisher._publish_once()
            self.assertEqual(upload.call_count, 2)
            self.assertEqual(upload.call_args_list[0].args[0][-1],
                             "gs://bucket/commands/progress/latest.json")
            self.assertEqual(upload.call_args_list[1].args[0][-1],
                             "gs://bucket/commands/progress/cmd-1.json")
            self.assertTrue(all(call.kwargs["timeout"] == 25
                                for call in upload.call_args_list))

    def test_failed_latest_heartbeat_skips_archive_upload(self) -> None:
        with TemporaryDirectory() as folder, patch.dict(os.environ, {
            "ANALYSIS_PROGRESS_GCS_URI": "gs://bucket/commands/progress/cmd-1.json",
        }):
            root = Path(folder)
            state = root / "pipeline_state.json"
            state.write_text('{"ticker_order": [], "tickers": {}}', encoding="utf-8")
            config = SimpleNamespace(
                log_dir=root, repo_root=root, generation_provider="chatgpt-browser"
            )
            publisher = _BatchProgressPublisher(config, state)
            with patch("src.local_runner.run_batch.require_gcloud", return_value="gcloud.cmd"), patch(
                "src.local_runner.run_batch.run_bounded",
                side_effect=subprocess.TimeoutExpired("gcloud.cmd", 25),
            ) as upload:
                publisher._publish_once()
            upload.assert_called_once()
            self.assertEqual(upload.call_args.args[0][-1],
                             "gs://bucket/commands/progress/latest.json")

    def test_latest_progress_destination_uses_stable_alias(self) -> None:
        self.assertEqual(
            _latest_progress_destination(
                "gs://bucket/commands/progress/cmd-market-1.json"
            ),
            "gs://bucket/commands/progress/latest.json",
        )
        self.assertEqual(_latest_progress_destination(""), "")

    def test_worker_exposes_command_progress_destination(self) -> None:
        request = CommandRequest.from_payload(
            {"id": "cmd-market-1", "action": ACTION_MARKET}
        )
        with patch.dict(os.environ, {}, clear=True):
            env = _command_environment(request)

        self.assertEqual(env["ANALYSIS_COMMAND_ID"], "cmd-market-1")
        self.assertEqual(env["ANALYSIS_COMMAND_ACTION"], ACTION_MARKET)
        self.assertEqual(
            env["ANALYSIS_PROGRESS_GCS_URI"],
            "gs://stock-analysis-reports-naxo85/commands/progress/cmd-market-1.json",
        )

    def test_payload_counts_stages_retries_and_eta(self) -> None:
        started = datetime.now(timezone.utc) - timedelta(minutes=10)
        state = {
            "started_at": started.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "ticker_order": ["AAA", "BBB", "CCC"],
            "tickers": {
                "AAA": {
                    "status": "ok",
                    "current_attempt": 1,
                    "attempts": {
                        "1": {
                            "stages": {
                                "prepare": _stage("ok"),
                                "analyze": _stage("ok"),
                                "publish": _stage("ok"),
                            }
                        }
                    },
                },
                "BBB": {
                    "status": "analyze",
                    "current_attempt": 2,
                    "attempts": {
                        "1": {"stages": {"prepare": _stage("failed")}},
                        "2": {
                            "stages": {
                                "prepare": _stage("ok"),
                                "analyze": _stage("running"),
                            }
                        },
                    },
                },
                "CCC": {"status": "queued", "attempts": {}},
            },
        }

        payload = _pipeline_progress_payload(
            state,
            command_id="cmd-market-1",
            command_action=ACTION_MARKET,
            generation_provider="chatgpt-browser",
            browser_status={
                "chat_group_size": 8,
                "chat_group_tickers": 3,
                "rate_limit_count": 2,
                "rate_limit_waiting": True,
                "rate_limit_resume_at": "2026-09-10T16:00:00+00:00",
            },
        )

        self.assertEqual(payload["completed"], 1)
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["counts"]["prepared"], 2)
        self.assertEqual(payload["counts"]["validated"], 1)
        self.assertEqual(payload["counts"]["published"], 1)
        self.assertEqual(payload["counts"]["retries"], 1)
        self.assertEqual(payload["current"]["phase"], "analyze")
        self.assertEqual(payload["current"]["ticker"], "BBB")
        self.assertGreater(payload["eta_seconds"], 0)
        self.assertTrue(payload["chatgpt_web"]["rate_limit_waiting"])
        self.assertEqual(payload["chatgpt_web"]["rate_limit_count"], 2)

    def test_payload_only_counts_the_current_attempt(self) -> None:
        state = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ticker_order": ["RETRY"],
            "tickers": {
                "RETRY": {
                    "status": "prepare",
                    "current_attempt": 2,
                    "attempts": {
                        "1": {
                            "stages": {
                                "prepare": _stage("ok"),
                                "analyze": _stage("ok"),
                                "publish": _stage("failed"),
                            }
                        },
                        "2": {"stages": {"prepare": _stage("ok")}},
                    },
                }
            },
        }

        payload = _pipeline_progress_payload(
            state,
            command_id="cmd-market-1",
            command_action=ACTION_MARKET,
            generation_provider="chatgpt-browser",
        )

        self.assertEqual(payload["counts"]["prepared"], 1)
        self.assertEqual(payload["counts"]["generated"], 0)
        self.assertEqual(payload["counts"]["validated"], 0)
        self.assertEqual(payload["counts"]["published"], 0)
        self.assertEqual(payload["counts"]["retries"], 1)
        self.assertEqual(payload["current"]["phase"], "queued")
        self.assertEqual(payload["current"]["ticker"], "")

    def test_payload_separates_pipeline_and_internal_web_retries(self) -> None:
        state = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ticker_order": ["DONE", "ACTIVE"],
            "tickers": {
                "DONE": {
                    "status": "ok",
                    "current_attempt": 2,
                    "attempts": {
                        "1": {
                            "stages": {
                                "analyze": {
                                    "status": "failed",
                                    "web_retry_count": 1,
                                }
                            }
                        },
                        "2": {
                            "stages": {
                                "analyze": {
                                    "status": "ok",
                                    "web_retry_count": 0,
                                },
                                "publish": _stage("ok"),
                            }
                        },
                    },
                },
                "ACTIVE": {
                    "status": "analyze",
                    "current_attempt": 1,
                    "attempts": {
                        "1": {"stages": {"analyze": _stage("running")}}
                    },
                },
            },
        }

        payload = _pipeline_progress_payload(
            state,
            command_id="cmd-market-1",
            command_action=ACTION_MARKET,
            generation_provider="chatgpt-browser",
            browser_status={
                "workers": [
                    {
                        "worker_id": 1,
                        "active_ticker": "ACTIVE",
                        "active_attempt": 3,
                    }
                ]
            },
        )

        self.assertEqual(payload["counts"]["pipeline_retries"], 1)
        self.assertEqual(payload["counts"]["chatgpt_web_retries"], 3)
        self.assertEqual(payload["counts"]["retries"], 4)

    def test_payload_reports_actual_generation_providers(self) -> None:
        state = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ticker_order": ["WEB", "FALLBACK", "OLD"],
            "tickers": {
                ticker: {
                    "status": "ok",
                    "attempts": {
                        "1": {
                            "stages": {
                                "analyze": _stage("ok"),
                                "publish": _stage("ok"),
                            }
                        }
                    },
                }
                for ticker in ("WEB", "FALLBACK", "OLD")
            },
        }
        with TemporaryDirectory() as temporary:
            result_dir = Path(temporary)
            (result_dir / "WEB.json").write_text(
                '{"analysis_workflow":{"generation_provider":"chatgpt-browser"}}',
                encoding="utf-8",
            )
            (result_dir / "FALLBACK.json").write_text(
                '{"analysis_workflow":{"generation_provider":"codex"}}',
                encoding="utf-8",
            )
            payload = _pipeline_progress_payload(
                state,
                command_id="cmd-market-1",
                command_action=ACTION_MARKET,
                generation_provider="chatgpt-browser",
                result_dir=result_dir,
            )

        self.assertEqual(
            payload["generation_providers"],
            {"chatgpt-browser": 1, "codex": 1, "unknown": 1},
        )
        self.assertEqual(payload["fallback_tickers"], ["FALLBACK"])

    def test_payload_marks_a_fully_published_batch_completed(self) -> None:
        state = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ticker_order": ["AAA", "BBB"],
            "tickers": {
                ticker: {
                    "status": "ok",
                    "attempts": {
                        "1": {
                            "stages": {
                                "prepare": _stage("ok"),
                                "analyze": _stage("ok"),
                                "publish": _stage("ok"),
                            }
                        }
                    },
                }
                for ticker in ("AAA", "BBB")
            },
        }

        payload = _pipeline_progress_payload(
            state,
            command_id="cmd-market-1",
            command_action=ACTION_MARKET,
            generation_provider="chatgpt-browser",
        )

        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["completed"], 2)

    def test_payload_marks_a_terminal_batch_with_failures_failed(self) -> None:
        state = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ticker_order": ["AAA", "BBB"],
            "tickers": {
                "AAA": {
                    "status": "ok",
                    "attempts": {
                        "1": {"stages": {"publish": _stage("ok")}}
                    },
                },
                "BBB": {
                    "status": "failed",
                    "attempts": {
                        "1": {"stages": {"analyze": _stage("failed")}}
                    },
                },
            },
        }

        payload = _pipeline_progress_payload(
            state,
            command_id="cmd-market-1",
            command_action=ACTION_MARKET,
            generation_provider="chatgpt-browser",
        )

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["completed"], 2)

    def test_payload_records_per_ticker_stage_and_retry_durations(self) -> None:
        now = datetime.now(timezone.utc)
        state = {
            "started_at": (now - timedelta(minutes=5)).isoformat(),
            "ticker_order": ["AAA"],
            "tickers": {
                "AAA": {
                    "status": "analyze",
                    "current_attempt": 2,
                    "attempts": {
                        "1": {
                            "stages": {
                                "prepare": {"status": "ok", "duration_seconds": 12},
                                "analyze": {"status": "failed", "duration_seconds": 80},
                            }
                        },
                        "2": {
                            "stages": {
                                "prepare": {"status": "ok", "duration_seconds": 10},
                                "analyze": {
                                    "status": "running",
                                    "started_at": (now - timedelta(seconds=30)).isoformat(),
                                },
                            }
                        },
                    },
                }
            },
        }

        payload = _pipeline_progress_payload(
            state,
            command_id="cmd-market-1",
            command_action=ACTION_MARKET,
            generation_provider="chatgpt-browser",
        )

        timing = payload["ticker_timings"]["AAA"]
        self.assertEqual(timing["attempt_count"], 2)
        self.assertEqual(timing["attempts"]["1"]["total_seconds"], 92.0)
        self.assertGreaterEqual(
            timing["attempts"]["2"]["stages_seconds"]["analyze"],
            29.0,
        )

    def test_payload_separates_web_queue_and_execution_timings(self) -> None:
        now = datetime.now(timezone.utc)
        state = {
            "started_at": (now - timedelta(minutes=5)).isoformat(),
            "ticker_order": ["AAA"],
            "tickers": {
                "AAA": {
                    "status": "ok",
                    "current_attempt": 1,
                    "attempts": {
                        "1": {
                            "stages": {
                                "analyze": {
                                    "status": "ok",
                                    "duration_seconds": 390,
                                    "web_worker_id": 2,
                                    "web_timing_seconds": {
                                        "queue_wait_seconds": 190,
                                        "execution_seconds": 180,
                                        "non_web_seconds": 20,
                                    },
                                },
                                "publish": {"status": "ok", "duration_seconds": 60},
                            }
                        }
                    },
                }
            },
        }

        payload = _pipeline_progress_payload(
            state,
            command_id="cmd-market-1",
            command_action=ACTION_MARKET,
            generation_provider="chatgpt-browser",
        )

        attempt = payload["ticker_timings"]["AAA"]["attempts"]["1"]
        self.assertEqual(attempt["web_worker_id"], 2)
        self.assertEqual(attempt["web_timing_seconds"]["queue_wait_seconds"], 190.0)
        self.assertEqual(attempt["web_timing_seconds"]["execution_seconds"], 180.0)
        self.assertEqual(payload["web_timing"]["average_queue_wait_seconds"], 190.0)
        self.assertEqual(payload["web_timing"]["average_execution_seconds"], 180.0)


if __name__ == "__main__":
    unittest.main()
