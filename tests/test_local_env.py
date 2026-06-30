from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.local_runner.local_env import get_local_env_value


class LocalEnvTests(unittest.TestCase):
    def test_reads_env_local_when_process_env_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env.local").write_text(
                "FINN_KEY='abc123'\nOTHER=value\n",
                encoding="utf-8",
            )

            with patch.dict("os.environ", {}, clear=True):
                self.assertEqual(
                    get_local_env_value("FINN_KEY", repo_root=root),
                    "abc123",
                )

    def test_process_env_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env.local").write_text("FINN_KEY=file\n", encoding="utf-8")

            with patch.dict("os.environ", {"FINN_KEY": "process"}):
                self.assertEqual(
                    get_local_env_value("FINN_KEY", repo_root=root),
                    "process",
                )


if __name__ == "__main__":
    unittest.main()
