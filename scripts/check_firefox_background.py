"""Local-only Firefox isolation smoke. No ChatGPT requests or saved profile use."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.local_runner.chatgpt_browser_generator import _launch_firefox


def windows_for_pid(api, process_id, desktop=None):
    windows = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def visit(hwnd, _):
        owner = wintypes.DWORD()
        api.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == process_id:
            windows.append(int(hwnd))
        return True

    if desktop is None:
        api.EnumWindows(visit, 0)
    else:
        api.EnumDesktopWindows(desktop, visit, 0)
    return windows


def main():
    os.environ.setdefault("SE_CACHE_PATH", str(Path(__file__).resolve().parents[1] / ".local" / "selenium-cache"))
    os.environ["SE_OFFLINE"] = "true"
    os.environ["ANALYSIS_PRIVATE_DESKTOP"] = "1"
    api = ctypes.WinDLL("user32", use_last_error=True)
    api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    api.EnumDesktopWindows.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.LPARAM]
    api.GetForegroundWindow.restype = wintypes.HWND
    log_dir = Path(__file__).resolve().parents[1] / "logs" / "firefox_background"
    log_dir.mkdir(parents=True, exist_ok=True)
    for cycle in range(1, 3):
        with TemporaryDirectory(prefix="firefox-isolation-") as temporary:
            os.environ["ANALYSIS_FIREFOX_SERVICE_LOG"] = str(log_dir / f"geckodriver-{cycle}.log")
            print(json.dumps({"cycle": cycle, "status": "launching"}), flush=True)
            foreground = api.GetForegroundWindow()
            driver = _launch_firefox(Path(temporary), headed=False)
            try:
                driver.get("data:text/html,<title>Background smoke</title><input id='test'>")
                field = driver.find_element("id", "test")
                field.send_keys("background works")
                assert field.get_attribute("value") == "background works"
                driver.switch_to.new_window("window")
                driver.get("data:text/html,<title>Second window</title>")
                driver.set_window_size(1200, 800)
                process_id = driver.capabilities["moz:processID"]
                interactive = windows_for_pid(api, process_id)
                private = windows_for_pid(api, process_id, driver.service.desktop.handle)
                assert not interactive, f"Firefox appeared on user desktop: {interactive}"
                assert private, "No Firefox window found on private desktop"
                print(json.dumps({
                    "cycle": cycle, "status": "ok", "firefox_pid": process_id,
                    "interactive_windows": len(interactive), "private_windows": len(private),
                    "foreground_unchanged": api.GetForegroundWindow() == foreground,
                    "typing": "ok", "new_window": "ok",
                }), flush=True)
            finally:
                driver.quit()
                assert driver.service.desktop is None, "Desktop handle not released"


if __name__ == "__main__":
    main()
