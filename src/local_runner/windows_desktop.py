"""Start background GUI processes on a private Windows desktop.

Hiding a window after WebDriver connects is too late: Firefox has already
displayed its first window. Set lpDesktop at process creation instead. Never
switch the user's desktop or silently fall back to the interactive desktop.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import json
from pathlib import Path
import subprocess
import uuid


def configure_background_launch(settings_dir=None):
    """Validate settings at CLI startup without changing process-wide overrides.

    run_one/run_batch retain this bootstrap hook. Each actual process launch
    still re-reads the persistent per-component setting.
    """
    directory = (Path(__file__).resolve().parents[2] / ".local"
                 if settings_dir is None else Path(settings_dir))
    return {component: private_desktop_enabled(component, directory)
            for component in ("firefox", "ibkr")}


def private_desktop_enabled(component, settings_dir):
    """Per-installation setting, re-read even by an existing command worker."""
    if os.name != "nt":
        return False
    override = os.environ.get("ANALYSIS_PRIVATE_DESKTOP")
    if override is not None:
        return override == "1"
    directory = Path(settings_dir).resolve()
    local_dir = next((parent for parent in (directory, *directory.parents)
                      if parent.name == ".local"), None)
    if local_dir is None:
        return False
    path = local_dir / "background_windows.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"background_windows_config_invalid: {path}") from exc
    if not isinstance(config, dict) or not isinstance(config.get(component, False), bool):
        raise RuntimeError(f"background_windows_config_invalid: {path}; component={component}")
    return config.get(component, False)


class _StartupInfo(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
    ]


class _StartupInfoEx(ctypes.Structure):
    _fields_ = [("StartupInfo", _StartupInfo), ("lpAttributeList", ctypes.c_void_p)]


class PrivateDesktop:
    def __init__(self, label="firefox"):
        self.name = f"stock-analysis-{label}-{os.getpid()}-{uuid.uuid4().hex}"
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        self.api.CreateDesktopW.argtypes = [
            wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        ]
        self.api.CreateDesktopW.restype = wintypes.HANDLE
        self.api.CloseDesktop.argtypes = [wintypes.HANDLE]
        self.api.CloseDesktop.restype = wintypes.BOOL
        # DESKTOP_ALL_ACCESS. Default security descriptor; non-inheritable.
        self.handle = self.api.CreateDesktopW(self.name, None, None, 0, 0x01FF, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            if not self.api.CloseDesktop(self.handle):
                raise ctypes.WinError(ctypes.get_last_error())
            self.handle = None


class DesktopProcess:
    """Small Popen-compatible lifecycle used by Selenium's Service."""

    stdin = stdout = stderr = None

    def __init__(self, command, *, desktop, env, cwd=None, stdout=None):
        import _winapi

        self._api = _winapi
        self._handle = None
        self._owned_desktop = None
        self.args = command
        self.returncode = None
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateProcessW.argtypes = [
            wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
            ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p,
            wintypes.LPCWSTR, ctypes.c_void_p,
            ctypes.POINTER(_ProcessInfo),
        ]
        kernel.CreateProcessW.restype = wintypes.BOOL
        startup = _StartupInfo()
        startup.cb = ctypes.sizeof(startup)
        startup.lpDesktop = desktop.name
        startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        info = _ProcessInfo()
        command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
        environment = ctypes.create_unicode_buffer(
            "\0".join(f"{key}={value}" for key, value in sorted(env.items())) + "\0\0"
        )
        flags = subprocess.CREATE_NO_WINDOW | 0x00000400  # CREATE_UNICODE_ENVIRONMENT
        # Inherit only the log and null input, never other workers' handles.
        inherited = []
        attributes = None
        try:
            if stdout is not None:
                import msvcrt

                current = _winapi.GetCurrentProcess()
                with open(os.devnull, "rb") as null_input:
                    for fd in (null_input.fileno(), stdout.fileno()):
                        inherited.append(_winapi.DuplicateHandle(
                            current, msvcrt.get_osfhandle(fd), current, 0, True,
                            _winapi.DUPLICATE_SAME_ACCESS,
                        ))
                startup.dwFlags |= subprocess.STARTF_USESTDHANDLES
                startup.hStdInput = inherited[0]
                startup.hStdOutput = startup.hStdError = inherited[1]
                size = ctypes.c_size_t()
                kernel.InitializeProcThreadAttributeList.argtypes = [
                    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                    ctypes.POINTER(ctypes.c_size_t),
                ]
                kernel.UpdateProcThreadAttribute.argtypes = [
                    ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t,
                    ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p,
                ]
                kernel.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
                kernel.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
                buffer = ctypes.create_string_buffer(size.value)
                if not kernel.InitializeProcThreadAttributeList(buffer, 1, 0, ctypes.byref(size)):
                    raise ctypes.WinError(ctypes.get_last_error())
                attributes = buffer
                handles = (wintypes.HANDLE * len(inherited))(*inherited)
                if not kernel.UpdateProcThreadAttribute(
                    buffer, 0, 0x00020002, handles, ctypes.sizeof(handles), None, None,
                ):
                    raise ctypes.WinError(ctypes.get_last_error())
                extended = _StartupInfoEx(startup, ctypes.cast(buffer, ctypes.c_void_p))
                extended.StartupInfo.cb = ctypes.sizeof(extended)
                startup_pointer = ctypes.byref(extended)
                flags |= 0x00080000  # EXTENDED_STARTUPINFO_PRESENT
            else:
                startup_pointer = ctypes.byref(startup)
            if not kernel.CreateProcessW(
                command[0], command_line, None, None, bool(inherited), flags,
                environment, cwd, startup_pointer, ctypes.byref(info),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            if attributes is not None:
                kernel.DeleteProcThreadAttributeList(attributes)
            for handle in inherited:
                _winapi.CloseHandle(handle)
        self._handle = info.hProcess
        self.pid = info.dwProcessId
        _winapi.CloseHandle(info.hThread)

    def poll(self):
        if self.returncode is None and self._api.WaitForSingleObject(self._handle, 0) == 0:
            self.returncode = self._api.GetExitCodeProcess(self._handle)
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            milliseconds = 0xFFFFFFFF if timeout is None else max(0, int(timeout * 1000))
            result = self._api.WaitForSingleObject(self._handle, milliseconds)
            if result == 258:
                raise subprocess.TimeoutExpired(self.args, timeout)
            self.returncode = self._api.GetExitCodeProcess(self._handle)
        return self.returncode

    def terminate(self):
        if self.poll() is None:
            try:
                self._api.TerminateProcess(self._handle, 1)
            except PermissionError:
                if self.poll() is None:
                    raise

    kill = terminate

    def close(self):
        if self._handle is not None:
            self._api.CloseHandle(self._handle)
            self._handle = None
        if self._owned_desktop is not None:
            self._owned_desktop.close()
            self._owned_desktop = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def start_private_desktop_process(command, *, cwd, stdout, label):
    desktop = PrivateDesktop(label)
    try:
        process = DesktopProcess(command, desktop=desktop, env=os.environ, cwd=cwd, stdout=stdout)
    except BaseException:
        desktop.close()
        raise
    process._owned_desktop = desktop
    return process
