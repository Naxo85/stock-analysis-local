"""Ensure the local IBKR Gateway paper API is available before analysis."""

from __future__ import annotations

import argparse
import ctypes
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7497
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_RESTART_ATTEMPTS = 2
POLL_INTERVAL_SECONDS = 2.0
PROFILE_ARCHIVE_TIMEOUT_SECONDS = 30.0
PROFILE_ARCHIVE_RETRY_INTERVAL_SECONDS = 0.5


def is_gateway_available(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    timeout_seconds: float = 5.0,
) -> bool:
    """Return whether a real read-only IBKR API handshake succeeds."""
    # A closed startup port is expected, not an ib_insync connection failure.
    # TCP readiness alone NEVER certifies a healthy API: the handshake below
    # is still mandatory whenever the listener is open.
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            pass
    except OSError:
        return False
    try:
        from ib_insync import IB
    except ImportError:
        return False

    ib = IB()
    try:
        ib.connect(
            host,
            port,
            clientId=28_000 + (os.getpid() % 1_000),
            readonly=True,
            timeout=timeout_seconds,
        )
        return ib.isConnected()
    except (OSError, TimeoutError):
        return False
    finally:
        if ib.isConnected():
            ib.disconnect()


def ensure_gateway(
    repo_root: Path,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = POLL_INTERVAL_SECONDS,
    _profile_recovery_attempted: bool = False,
) -> str:
    """Start IB Gateway through IBC when needed and wait for its API port."""
    if is_gateway_available(host, port):
        return "already_running"

    if os.name != "nt":
        raise RuntimeError("ibkr_gateway_autostart_windows_only")

    ibc_dir = repo_root / ".local" / "ibc"
    start_ibc = ibc_dir / "scripts" / "StartIBC.bat"
    gateway_dir = repo_root / ".local" / "ibgateway" / "ibgateway-offline"
    gateway_settings_dir = repo_root / ".local" / "ibgateway-settings"
    config_path = repo_root / "secrets" / "ibc" / "config.ini"

    required = {
        "ibc_launcher": start_ibc,
        "ibc_jar": ibc_dir / "IBC.jar",
        "offline_gateway": gateway_dir / "ibgateway.vmoptions",
        "ibc_config": config_path,
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        detail = ",".join(missing)
        raise RuntimeError(
            f"ibkr_gateway_autostart_not_configured: {detail}; "
            "run scripts\\setup_ibkr_gateway_autostart.ps1"
        )

    _stop_stale_ibkr_processes(gateway_dir)
    gateway_settings_dir.mkdir(parents=True, exist_ok=True)
    repaired_settings = _repair_gateway_settings(gateway_settings_dir)
    log_dir = repo_root / "logs" / "tws"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"ibc-{datetime.now():%Y%m%d-%H%M%S-%f}.log"

    command = [
        os.environ.get("COMSPEC", "cmd.exe"),
        "/c",
        str(start_ibc),
        gateway_dir.name,
        "/Gateway",
        f"/TwsPath:{gateway_dir.parent.parent}",
        f"/TwsSettingsPath:{gateway_settings_dir}",
        f"/IbcPath:{ibc_dir}",
        f"/Config:{config_path}",
        f"/JavaPath:{gateway_dir / 'jre' / 'bin'}",
        "/Mode:paper",
    ]

    # IBC is a batch launcher. CREATE_NO_WINDOW keeps its cmd/java console hidden
    # while IB Gateway remains an independent GUI process (normally minimized).
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    with log_path.open("a", encoding="utf-8") as log_handle:
        for repaired_path in repaired_settings:
            log_handle.write(f"gateway_settings_repaired: {repaired_path}\n")
        log_handle.flush()
        from .windows_desktop import private_desktop_enabled

        if private_desktop_enabled("ibkr", repo_root / ".local"):
            from .windows_desktop import start_private_desktop_process

            try:
                process = start_private_desktop_process(
                    command, cwd=str(repo_root), stdout=log_handle, label="ibkr",
                )
            except OSError as exc:
                raise RuntimeError(f"ibkr_gateway_private_desktop_launch_failed: {exc}") from exc
        else:
            process = subprocess.Popen(
                command,
                cwd=str(repo_root),
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _log_reports_settings_recovery(log_path):
            return _recover_rejected_profile(
                repo_root, process, log_path, host=host, port=port,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                already_attempted=_profile_recovery_attempted,
            )
        if is_gateway_available(host, port):
            # An API handshake can succeed even while recovery is required.
            # Never report that damaged profile as a healthy startup.
            time.sleep(1.0)
            if _log_reports_settings_recovery(log_path):
                return _recover_rejected_profile(
                    repo_root, process, log_path, host=host, port=port,
                    timeout_seconds=timeout_seconds,
                    poll_interval_seconds=poll_interval_seconds,
                    already_attempted=_profile_recovery_attempted,
                )
            return "started"
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(
                f"ibkr_gateway_autostart_failed: exit_code={exit_code}; log={log_path}"
            )
        time.sleep(poll_interval_seconds)

    _terminate_process_tree(process)
    raise RuntimeError(
        f"ibkr_gateway_autostart_timeout: {host}:{port} unavailable after "
        f"{timeout_seconds}s; log={log_path}"
    )


def restart_gateway(
    repo_root: Path,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_attempts: int = DEFAULT_RESTART_ATTEMPTS,
) -> str:
    """Restart the isolated Gateway process and wait for a fresh API session."""
    if os.name != "nt":
        raise RuntimeError("ibkr_gateway_restart_windows_only")

    if max_attempts < 1:
        raise ValueError("ibkr_gateway_restart_attempts_must_be_positive")

    gateway_dir = repo_root / ".local" / "ibgateway" / "ibgateway-offline"
    last_error: RuntimeError | None = None
    for attempt in range(1, max_attempts + 1):
        _stop_stale_ibkr_processes(gateway_dir)

        stop_deadline = time.monotonic() + 15
        while is_gateway_available(host, port):
            if time.monotonic() >= stop_deadline:
                raise RuntimeError("ibkr_gateway_restart_stop_timeout")
            time.sleep(0.5)

        try:
            result = ensure_gateway(
                repo_root,
                host=host,
                port=port,
                timeout_seconds=timeout_seconds,
            )
            return f"restarted:{result}"
        except RuntimeError as exc:
            last_error = exc
            if (
                "ibkr_gateway_autostart_timeout" not in str(exc)
                or attempt >= max_attempts
            ):
                raise
            time.sleep(2)

    raise last_error or RuntimeError("ibkr_gateway_restart_failed")


def _recover_rejected_profile(
    repo_root: Path, process: subprocess.Popen, log_path: Path, *,
    host: str, port: int, timeout_seconds: int, poll_interval_seconds: float,
    already_attempted: bool,
) -> str:
    _terminate_process_tree(process)
    gateway_dir = repo_root / ".local" / "ibgateway" / "ibgateway-offline"
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    # Reap our launcher before inspecting remaining children. Process rundown
    # is asynchronous; the exact-image cleaner also handles exiting children.
    _stop_stale_ibkr_processes(gateway_dir)
    if already_attempted:
        raise RuntimeError(f"ibkr_gateway_settings_recovery_repeated: log={log_path}")
    archive = _archive_rejected_profile_after_shutdown(
        repo_root,
        log_path,
        gateway_dir,
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"gateway_profile_archived: {archive}\n")
    result = ensure_gateway(
        repo_root, host=host, port=port, timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        _profile_recovery_attempted=True,
    )
    return f"profile_recreated:{result}"


def _archive_rejected_profile_after_shutdown(
    repo_root: Path,
    log_path: Path,
    gateway_dir: Path,
    *,
    timeout_seconds: float = PROFILE_ARCHIVE_TIMEOUT_SECONDS,
    retry_interval_seconds: float = PROFILE_ARCHIVE_RETRY_INTERVAL_SECONDS,
) -> Path:
    """Archive a rejected profile once Gateway releases its Windows handles."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        _stop_stale_ibkr_processes(gateway_dir)
        try:
            return _archive_rejected_profile(repo_root, log_path)
        except PermissionError as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"ibkr_gateway_recovery_profile_locked: log={log_path}"
                ) from exc
            time.sleep(retry_interval_seconds)


def _archive_rejected_profile(repo_root: Path, log_path: Path) -> Path:
    """Preserve only the account directory named by the exact recovery error."""
    settings_root = (repo_root / ".local" / "ibgateway-settings").resolve()
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"File does not exist ([^\r\n]+[\\/]ibg\.xml)", log_text)
    if not match:
        raise RuntimeError("ibkr_gateway_recovery_profile_not_identified")
    account_dir = Path(match.group(1)).parent.resolve()
    if account_dir.parent != settings_root or not account_dir.is_dir():
        raise RuntimeError("ibkr_gateway_recovery_profile_outside_settings")
    archive_root = repo_root / ".local" / "ibgateway-settings-archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    archive = archive_root / f"{account_dir.name}-rejected-{datetime.now():%Y%m%d-%H%M%S-%f}"
    account_dir.rename(archive)
    return archive


def _log_reports_settings_recovery(log_path: Path) -> bool:
    try:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-8_000:]
    except OSError:
        return False
    lowered = tail.lower()
    return (
        "trouble loading your settings" in lowered
        and "file does not exist" in lowered
        and "would you like to try recovering" in lowered
    )


def _dismiss_gateway_settings_recovery_dialog(
    *, confirmed_by_log: bool = False
) -> bool:
    """Accept only Gateway's missing/corrupt local-settings recovery dialog."""
    if os.name != "nt":
        return False

    from ctypes import wintypes

    user32 = ctypes.windll.user32
    windows: list[int] = []
    enum_proc_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
    )
    user32.EnumWindows.argtypes = [enum_proc_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.EnumChildWindows.argtypes = [
        wintypes.HWND,
        enum_proc_type,
        wintypes.LPARAM,
    ]
    user32.EnumChildWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.PostMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.PostMessageW.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.mouse_event.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]

    def window_text(handle: int) -> str:
        length = user32.GetWindowTextLengthW(handle)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(handle, buffer, len(buffer))
        return buffer.value

    def class_name(handle: int) -> str:
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(handle, buffer, len(buffer))
        return buffer.value

    @enum_proc_type
    def collect_window(handle: int, _param: int) -> bool:
        if user32.IsWindowVisible(handle):
            windows.append(handle)
        return True

    user32.EnumWindows(collect_window, 0)
    for handle in windows:
        if window_text(handle) != "IBKR Gateway":
            continue
        if "dialog" not in class_name(handle).lower():
            continue
        child_handles: list[int] = []

        @enum_proc_type
        def collect_child(child: int, _param: int) -> bool:
            child_handles.append(child)
            return True

        user32.EnumChildWindows(handle, collect_child, 0)
        texts = {window_text(child).strip() for child in child_handles}
        is_recovery = confirmed_by_log or any(
            "trouble loading your settings" in text.lower()
            and "may be corrupted" in text.lower()
            for text in texts
        )
        if not is_recovery:
            continue
        for child in child_handles:
            if window_text(child).strip().lower() in {"yes", "sí", "si"}:
                user32.PostMessageW(child, 0x00F5, 0, 0)  # BM_CLICK
                return True
        # Swing buttons are not native child HWNDs and ignore posted keyboard
        # messages. Click the stable relative centre of "Yes" only after the
        # log and the SunAwtDialog class both confirm this exact recovery UI.
        rect = wintypes.RECT()
        if not user32.GetWindowRect(handle, ctypes.byref(rect)):
            return False
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if not (500 <= width <= 1_400 and 160 <= height <= 500):
            return False
        original_cursor = wintypes.POINT()
        cursor_saved = bool(user32.GetCursorPos(ctypes.byref(original_cursor)))
        yes_x = rect.left + round(width * 0.462)
        yes_y = rect.top + round(height * 0.91)
        user32.ShowWindow(handle, 5)  # SW_SHOW
        user32.SetForegroundWindow(handle)
        time.sleep(0.15)
        user32.SetCursorPos(yes_x, yes_y)
        user32.mouse_event(0x0002, 0, 0, 0, None)  # MOUSEEVENTF_LEFTDOWN
        user32.mouse_event(0x0004, 0, 0, 0, None)  # MOUSEEVENTF_LEFTUP
        if cursor_saved:
            time.sleep(0.05)
            user32.SetCursorPos(original_cursor.x, original_cursor.y)
        return True
    return False


def _repair_gateway_settings(settings_dir: Path) -> list[Path]:
    """Restore ibg.xml and remove stale transaction files before Gateway starts.

    Gateway uses ``ibg.tmp.xml`` as an in-place transaction file.  Leaving both
    files behind can make the next startup fail while rotating ``ibg.xml`` and
    display the settings-recovery dialog again.  A usable temporary file must
    therefore be *moved* into place, not copied.
    """
    restored: list[Path] = []
    for account_dir in settings_dir.iterdir():
        if not account_dir.is_dir():
            continue
        current = account_dir / "ibg.xml"
        temporary = account_dir / "ibg.tmp.xml"
        current_is_usable = _looks_like_gateway_settings(current)
        if (
            _looks_like_gateway_settings(temporary)
            and (
                not current_is_usable
                or temporary.stat().st_mtime > current.stat().st_mtime
            )
        ):
            temporary.replace(current)
            restored.append(current)
            continue
        if current_is_usable:
            # A leftover transaction file can collide with Gateway's next
            # attempt to rotate ibg.xml, even when the current file is valid.
            temporary.unlink(missing_ok=True)
            continue
        backups = sorted(
            (
                path
                for path in account_dir.glob("ibg.*.xml")
                if path.name not in {"ibg.tmp.xml", "ibg.xml"}
                and _looks_like_gateway_settings(path)
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not backups:
            continue
        shutil.copy2(backups[0], current)
        temporary.unlink(missing_ok=True)
        restored.append(current)
    return restored


def _looks_like_gateway_settings(path: Path) -> bool:
    try:
        if path.stat().st_size < 128:
            return False
        with path.open("rb") as handle:
            return handle.read(7) == b"IBGZENC"
    except OSError:
        return False


def _stop_stale_ibkr_processes(program_dir: Path) -> None:
    """Remove only orphaned Java processes belonging to our isolated Gateway."""
    java_path = str((program_dir / "jre" / "bin" / "java.exe").resolve())
    from .windows_processes import stop_processes_by_executable
    stop_processes_by_executable(java_path, timeout_seconds=15)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    subprocess.run(
        ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check or start the IB Gateway paper API.")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)

    repo_root = _find_repo_root(Path.cwd())
    if args.check_only:
        if is_gateway_available():
            print(f"OK IBKR: API disponible en {DEFAULT_HOST}:{DEFAULT_PORT}.")
            return 0
        print(f"FAILED IBKR: API no disponible en {DEFAULT_HOST}:{DEFAULT_PORT}.")
        return 1

    try:
        result = ensure_gateway(repo_root, timeout_seconds=args.timeout_seconds)
    except RuntimeError as exc:
        print(f"FAILED IBKR: {exc}", file=sys.stderr)
        return 1

    print(f"OK IBKR: {result} en {DEFAULT_HOST}:{DEFAULT_PORT}.")
    return 0


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "src" / "local_runner").is_dir():
            return candidate
    raise RuntimeError(f"repo_root_not_found_from: {start}")


if __name__ == "__main__":
    raise SystemExit(main())
