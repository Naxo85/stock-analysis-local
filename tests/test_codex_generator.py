from __future__ import annotations

import subprocess
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from src.local_runner.codex_generator import (
    _latest_windows_app_codex,
    generate_markdown_with_codex,
    parse_codex_jsonl_usage,
)


class CodexGeneratorTests(unittest.TestCase):
    def test_finds_newest_bundled_windows_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older = root / "old" / "codex.exe"
            newer = root / "new" / "codex.exe"
            older.parent.mkdir()
            newer.parent.mkdir()
            older.write_bytes(b"old")
            newer.write_bytes(b"new")
            os.utime(older, ns=(1, 1))
            os.utime(newer, ns=(2, 2))

            with patch(
                "src.local_runner.codex_generator.WINDOWS_CODEX_APP_BIN_ROOT",
                root,
            ):
                self.assertEqual(_latest_windows_app_codex(), newer)

    def test_parses_last_completed_turn_usage(self) -> None:
        raw = "\n".join(
            (
                '{"type":"turn.completed","usage":{"input_tokens":10}}',
                "not-json",
                (
                    '{"type":"turn.completed","usage":{"input_tokens":20,'
                    '"cached_input_tokens":5,"output_tokens":7,'
                    '"reasoning_output_tokens":3}}'
                ),
            )
        )

        self.assertEqual(
            parse_codex_jsonl_usage(raw),
            {
                "input_tokens": 20,
                "cached_input_tokens": 5,
                "output_tokens": 7,
                "reasoning_output_tokens": 3,
                "uncached_input_tokens": 15,
                "total_tokens": 27,
            },
        )

    def test_generation_accepts_explicit_model_and_effort(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input.md"
            output_path = root / "report.md"
            events_path = root / "events.jsonl"
            input_path.write_text("frozen input", encoding="utf-8")

            def fake_run(command, **kwargs):
                output_path.write_text("report", encoding="utf-8")
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=(
                        '{"type":"turn.completed","usage":'
                        '{"input_tokens":100,"output_tokens":9}}\n'
                    ),
                    stderr="",
                )

            with (
                patch(
                    "src.local_runner.codex_generator.require_codex",
                    return_value="codex",
                ),
                patch(
                    "src.local_runner.codex_generator.subprocess.run",
                    side_effect=fake_run,
                ) as run,
            ):
                result = generate_markdown_with_codex(
                    input_path,
                    output_path,
                    cwd=root,
                    model="gpt-5.6-sol",
                    reasoning_effort="medium",
                    event_log_path=events_path,
                    benchmark_isolation=True,
                )

            command = run.call_args.args[0]
            self.assertIn("--json", command)
            self.assertIn("gpt-5.6-sol", command)
            self.assertIn('model_reasoning_effort="medium"', command)
            self.assertEqual(
                result.usage,
                {
                    "input_tokens": 100,
                    "output_tokens": 9,
                    "uncached_input_tokens": 100,
                    "total_tokens": 109,
                },
            )
            self.assertTrue(events_path.exists())


if __name__ == "__main__":
    unittest.main()
