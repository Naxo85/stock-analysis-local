"""Verify cold Gateway starts; optionally require private-desktop isolation."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.local_runner.ibkr_gateway_manager import restart_gateway, is_gateway_available
from src.local_runner.command_worker import local_worker_lock
from check_background_processes import process_inventory
from check_firefox_background import windows_for_pid


def assert_gateway_isolated(root):
    api = ctypes.WinDLL("user32", use_last_error=True)
    api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    api.GetProcessWindowStation.restype = wintypes.HANDLE
    api.EnumDesktopWindows.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.LPARAM]
    api.EnumDesktopsW.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.LPARAM]
    api.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenDesktopW.restype = wintypes.HANDLE
    api.CloseDesktop.argtypes = [wintypes.HANDLE]
    java_path = str(root / ".local/ibgateway/ibgateway-offline/jre/bin/java.exe").lower()
    processes = [row for row in process_inventory() if row["executable"].lower() == java_path]
    assert processes, "Isolated Gateway Java process not found"
    names = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.LPWSTR, wintypes.LPARAM)

    @callback_type
    def visit(name, _):
        if name.startswith("stock-analysis-ibkr-"):
            names.append(name)
        return True

    assert api.EnumDesktopsW(api.GetProcessWindowStation(), visit, 0)
    interactive = sum(len(windows_for_pid(api, row["pid"])) for row in processes)
    private = 0
    for name in names:
        desktop = api.OpenDesktopW(name, 0, False, 0x0041)
        assert desktop, f"Unable to inspect private desktop {name}"
        try:
            private += sum(len(windows_for_pid(api, row["pid"], desktop)) for row in processes)
        finally:
            api.CloseDesktop(desktop)
    assert not interactive, f"Gateway windows appeared on interactive desktop: {interactive}"
    assert private, "No Gateway windows found on private desktop"
    return {"interactive_windows": interactive, "private_windows": private}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-desktop", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.private_desktop:
        os.environ["ANALYSIS_PRIVATE_DESKTOP"] = "1"
    for row in process_inventory():
        if "src.local_runner.run_batch" in row["command"] or "src.local_runner.run_one" in row["command"]:
            raise RuntimeError("Stop the active analysis before testing cold starts")
    with local_worker_lock(root / "logs/command_worker.lock") as acquired:
        if not acquired:
            raise RuntimeError("Stop the active command worker before testing cold starts")
        for index in range(1, 3):
            print(f"COLD_START {index}: restarting", flush=True)
            print(restart_gateway(root, timeout_seconds=240), flush=True)
            log = max((root / "logs/tws").glob("ibc-*.log"), key=lambda p: p.stat().st_mtime)
            text = log.read_text(encoding="utf-8", errors="replace")
            if "trouble loading your settings" in text:
                raise RuntimeError(f"Settings recovery recurred: {log}")
            if "Configuration tasks completed" not in text:
                raise RuntimeError(f"Configuration incomplete: {log}")
            time.sleep(5)
            if not is_gateway_available(timeout_seconds=5):
                raise RuntimeError(f"API did not remain available: {log}")
            isolation = assert_gateway_isolated(root) if args.private_desktop else {}
            print(json.dumps({"cycle": index, "status": "ok", "api": "healthy",
                              "recovery_dialog": False, "log": log.name, **isolation}), flush=True)


if __name__ == "__main__":
    main()
