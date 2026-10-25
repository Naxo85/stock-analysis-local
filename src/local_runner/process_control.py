"""Bound subprocess lifetimes, including Windows launcher grandchildren."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any


def configure_utf8_output() -> None:
    """Keep CLI diagnostics and inherited Python subprocess pipes UTF-8.

    Decoding a child as UTF-8 is insufficient when its redirected Windows
    stdout still uses CP1252. Diagnostics must never abort source retry logic.
    """
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")


def run_bounded(command: Any, *, timeout: float, check: bool = False,
                input: Any = None, start_signal=None, startup_timeout: float | None = None,
                **kwargs: Any) -> subprocess.CompletedProcess:
    """Like run(), but terminate a Windows tree before reaping its root."""
    if input is not None:
        kwargs["stdin"] = subprocess.PIPE
    if kwargs.pop("capture_output", False):
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    with subprocess.Popen(command, **kwargs) as process:
        try:
            if start_signal is None:
                stdout, stderr = process.communicate(input, timeout=timeout)
            else:
                # A slow CLI boot must not consume the model's execution time.
                # Only the FIRST verified start can reset the deadline; streaming
                # tokens/tools and repeated start events never extend it further.
                deadline = time.monotonic() + (timeout if startup_timeout is None else startup_timeout)
                started, first = False, True
                while True:
                    remaining = deadline - time.monotonic()
                    try:
                        stdout, stderr = process.communicate(input if first else None,
                            timeout=max(.001, min(.25, remaining)))
                        break
                    except subprocess.TimeoutExpired as pending:
                        first = False
                        if not started and start_signal():
                            started = True
                            deadline = time.monotonic() + timeout
                        elif time.monotonic() >= deadline:
                            pending.phase = 'execution' if started else 'startup'
                            raise
        except subprocess.TimeoutExpired as exc:
            if os.name == "nt":
                try:
                    stopped = subprocess.run(
                        ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW, timeout=15,
                        check=False,
                    )
                    if stopped.returncode:
                        process.kill()
                except (OSError, subprocess.SubprocessError):
                    process.kill()
            else:
                process.kill()
            try:
                stdout, stderr = process.communicate(timeout=5)
                exc.output, exc.stderr = stdout, stderr
            except subprocess.TimeoutExpired:
                # Do not hang on inherited pipes if Windows denied tree cleanup.
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
            raise
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result
