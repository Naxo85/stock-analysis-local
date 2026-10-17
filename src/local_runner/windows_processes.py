"""Exact-image Windows cleanup without shell/CIM startup or PID-only killing."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import time


class _ProcessEntry(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]


def _kernel():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
    kernel.Process32FirstW.restype = kernel.Process32NextW.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateProcess.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    return kernel


def _image(kernel, handle):
    buffer = ctypes.create_unicode_buffer(32768)
    size = wintypes.DWORD(len(buffer))
    if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    return os.path.normcase(os.path.realpath(buffer.value))


def _open_process(kernel, access, pid, deadline):
    """Keep access denials unless a wait-only handle proves the PID exited."""
    handle = kernel.OpenProcess(access, False, pid)
    if handle:
        return handle
    error = ctypes.get_last_error()
    if error == 87:
        return None
    if error == 5:
        # Exit can race even with opening the query/termination handle. This
        # fallback grants no query/kill authority: it can only observe exit.
        waiter = kernel.OpenProcess(0x100000, False, pid)
        if waiter:
            try:
                remaining = max(0, int((deadline - time.monotonic()) * 1000))
                if kernel.WaitForSingleObject(waiter, remaining) == 0:
                    return None
            finally:
                kernel.CloseHandle(waiter)
    raise ctypes.WinError(error)


def _live_image(kernel, handle, deadline):
    """Skip only confirmed exits, including exit during an image query."""
    state = kernel.WaitForSingleObject(handle, 0)
    if state == 0:
        return None
    if state != 258:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return _image(kernel, handle)
    except OSError:
        # Image metadata can disappear before process rundown is complete.
        # A signalled SAME handle proves exit; real access denial stays visible.
        remaining = max(0, int((deadline - time.monotonic()) * 1000))
        if kernel.WaitForSingleObject(handle, remaining) == 0:
            return None
        raise


def _matching_pids(kernel, expected, *, deadline=None):
    if deadline is None:
        deadline = time.monotonic() + 15
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    matches = []
    try:
        entry = _ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        available = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while available:
            if entry.szExeFile.casefold() == Path(expected).name.casefold():
                handle = _open_process(kernel, 0x1000 | 0x100000, entry.th32ProcessID, deadline)
                if handle:
                    try:
                        if _live_image(kernel, handle, deadline) == expected:
                            matches.append(entry.th32ProcessID)
                    finally:
                        kernel.CloseHandle(handle)
            available = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        error = ctypes.get_last_error()
        if error != 18:  # ERROR_NO_MORE_FILES; enumeration must be complete.
            raise ctypes.WinError(error)
        return matches
    finally:
        kernel.CloseHandle(snapshot)


def stop_processes_by_executable(executable: str, *, timeout_seconds: float = 15) -> list[int]:
    """Stop only the exact local executable; verify again on the killing handle.

    Never falls back to image-name/taskkill-wide termination. A reused PID with
    another image is skipped, and access/cleanup errors block a duplicate launch.
    """
    if os.name != "nt":
        raise RuntimeError("windows_process_cleanup_windows_only")
    if not Path(executable).is_absolute() or timeout_seconds <= 0:
        raise ValueError("windows_process_cleanup_requires_absolute_path_and_timeout")
    expected = os.path.normcase(os.path.realpath(executable))
    kernel = _kernel()
    stopped = []
    deadline = time.monotonic() + timeout_seconds
    for pid in _matching_pids(kernel, expected, deadline=deadline):
        # Query + terminate + synchronize; re-query this SAME handle before kill.
        handle = _open_process(kernel, 0x1000 | 0x0001 | 0x100000, pid, deadline)
        if not handle:
            continue
        try:
            if _live_image(kernel, handle, deadline) != expected:
                continue
            state = kernel.WaitForSingleObject(handle, 0)
            if state == 0:
                continue
            if state != 258:
                raise ctypes.WinError(ctypes.get_last_error())
            if not kernel.TerminateProcess(handle, 1):
                error = ctypes.get_last_error()
                # Another owner (e.g. our taskkill tree) may already have
                # requested termination. Windows returns ACCESS_DENIED while
                # that asynchronous rundown is still pending. Wait for proof
                # of exit on this handle, within the SAME cleanup deadline.
                remaining = max(0, int((deadline - time.monotonic()) * 1000))
                if kernel.WaitForSingleObject(handle, remaining) == 0:
                    continue
                raise ctypes.WinError(error)
            remaining = max(0, int((deadline - time.monotonic()) * 1000))
            result = kernel.WaitForSingleObject(handle, remaining)
            if result == 258:
                raise RuntimeError("windows_process_cleanup_timeout")
            if result != 0:
                raise ctypes.WinError(ctypes.get_last_error())
            stopped.append(pid)
        finally:
            kernel.CloseHandle(handle)
    return stopped
