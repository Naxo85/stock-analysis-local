"""Exercise actual module entry points without analysis, network or publication."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.local_runner.windows_desktop import configure_background_launch


@pytest.mark.parametrize("module", [
    "src.local_runner.run_batch",
    "src.local_runner.run_one",
    "src.local_runner.command_worker",
    "src.local_runner.chatgpt_browser_generator",
    "src.local_runner.ibkr_gateway_manager",
    "src.local_runner.update_analysis_sources_pipeline",
    "src.local_runner.update_ibkr_news_batch",
])
def test_actual_cli_help_reaches_argument_parser_without_starting_work(module):
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "usage:" in result.stdout.lower()


def test_bootstrap_preserves_per_component_settings_without_global_override(tmp_path, monkeypatch):
    monkeypatch.delenv("ANALYSIS_PRIVATE_DESKTOP", raising=False)
    directory = tmp_path / ".local"
    directory.mkdir()
    (directory / "background_windows.json").write_text('{"firefox":true,"ibkr":false}')
    assert configure_background_launch(directory) == {"firefox": True, "ibkr": False}
    assert "ANALYSIS_PRIVATE_DESKTOP" not in os.environ


def test_bootstrap_validates_settings_before_work_can_start(tmp_path, monkeypatch):
    monkeypatch.delenv("ANALYSIS_PRIVATE_DESKTOP", raising=False)
    directory = tmp_path / ".local"
    directory.mkdir()
    (directory / "background_windows.json").write_text('{"firefox":"yes"}')
    with pytest.raises(RuntimeError, match="background_windows_config_invalid"):
        configure_background_launch(directory)
