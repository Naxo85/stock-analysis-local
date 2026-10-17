from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.local_runner.run_one import _generate


class GenerationRetryMetadataTests(unittest.TestCase):
    def test_codex_fallback_preserves_failed_web_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "output" / "AAA"
            output_dir.mkdir(parents=True)
            (output_dir / "codex_input.md").write_text("input", encoding="utf-8")

            def fail_web(**kwargs: object) -> object:
                metadata_path = output_dir / "generation_metadata.json"
                metadata_path.write_text(
                    json.dumps(
                        {
                            "provider_requested": "chatgpt-browser",
                            "provider_used": None,
                            "web_worker_id": 2,
                            "attempts": [{"attempt": 1}, {"attempt": 2}],
                            "web_attempt_count": 2,
                            "web_retry_count": 1,
                            "status": "failed",
                        }
                    ),
                    encoding="utf-8",
                )
                raise RuntimeError("browser failed after 2 attempts")

            with (
                patch(
                    "src.local_runner.run_one.generate_markdown_with_chatgpt_browser",
                    side_effect=fail_web,
                ),
                patch(
                    "src.local_runner.run_one.generate_markdown_with_codex",
                    return_value=SimpleNamespace(output_path=output_dir / "latest.md"),
                ),
            ):
                exit_code = _generate(
                    root,
                    "AAA",
                    generation_provider="chatgpt-browser",
                )

            metadata = json.loads(
                (output_dir / "generation_metadata.json").read_text(encoding="utf-8")
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(metadata["provider_used"], "codex")
        self.assertEqual(metadata["status"], "ok_fallback")
        self.assertEqual(metadata["web_worker_id"], 2)
        self.assertEqual(metadata["web_attempt_count"], 2)
        self.assertEqual(metadata["web_retry_count"], 1)
        self.assertEqual(len(metadata["attempts"]), 2)


if __name__ == "__main__":
    unittest.main()
