import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from src.local_runner.process_control import run_bounded

class ProcessControlTests(unittest.TestCase):
    def test_output_and_exit_status(self):
        result = run_bounded([sys.executable, "-c", "print('done')"], timeout=10,
                             capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "done")
        with self.assertRaises(subprocess.CalledProcessError):
            run_bounded([sys.executable, "-c", "raise SystemExit(7)"], timeout=10, check=True)

    @unittest.skipUnless(os.name == "nt", "Windows launcher regression")
    def test_timeout_kills_grandchild(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "orphan.txt"
            child = "import time,pathlib;time.sleep(4);pathlib.Path(" + repr(str(marker)) + ").touch()"
            parent = "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c'," + repr(child) + "]);print('started',flush=True);time.sleep(60)"
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                run_bounded([sys.executable, "-c", parent], timeout=1, capture_output=True, text=True)
            self.assertIn("started", caught.exception.stdout)
            time.sleep(4)
            self.assertFalse(marker.exists())
