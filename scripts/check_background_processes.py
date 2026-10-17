"""Read-only Windows process inventory, without PowerShell/CIM dependencies."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import re


class ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
    ]


class UnicodeString(ctypes.Structure):
    _fields_ = [("Length", wintypes.WORD), ("MaximumLength", wintypes.WORD),
                ("Buffer", ctypes.c_void_p)]


def process_inventory(*, extra_names=()):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    native = ctypes.WinDLL("ntdll")
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    native.NtQueryInformationProcess.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)]
    native.NtQueryInformationProcess.restype = wintypes.LONG
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    rows = []
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        available = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while available:
            name = entry.szExeFile.lower()
            if name in {"python.exe", "pythonw.exe", "firefox.exe", "geckodriver.exe", "java.exe", *extra_names}:
                handle = kernel.OpenProcess(0x1000, False, entry.th32ProcessID)
                row = {"pid": entry.th32ProcessID, "parent": entry.th32ParentProcessID,
                       "name": name, "executable": "", "command": ""}
                if handle:
                    try:
                        path = ctypes.create_unicode_buffer(32768)
                        size = wintypes.DWORD(len(path))
                        if kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
                            row["executable"] = path.value
                        needed = wintypes.DWORD()
                        native.NtQueryInformationProcess(handle, 60, None, 0, ctypes.byref(needed))
                        if needed.value:
                            buffer = ctypes.create_string_buffer(needed.value)
                            if native.NtQueryInformationProcess(handle, 60, buffer, len(buffer), ctypes.byref(needed)) >= 0:
                                value = UnicodeString.from_buffer(buffer)
                                row["command"] = ctypes.wstring_at(value.Buffer, value.Length // 2)
                    finally:
                        kernel.CloseHandle(handle)
                rows.append(row)
            available = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    return rows


def main():
    root = Path(__file__).resolve().parents[1]
    # Never print raw command lines: they may contain credentials or user data.
    rows = process_inventory()
    repository_pids = {row["pid"] for row in rows if
                       str(root).lower() in (row["command"] + row["executable"]).lower()
                       or "src.local_runner." in row["command"]}
    while True:
        descendants = {row["pid"] for row in rows if row["parent"] in repository_pids}
        expanded = repository_pids | descendants
        if expanded == repository_pids:
            break
        repository_pids = expanded
    for row in rows:
        if row["pid"] not in repository_pids:
            continue
        match = re.search(r"src\.local_runner\.([\w]+)", row["command"])
        print(json.dumps({key: value for key, value in row.items() if key != "command"}
                         | {"role": match.group(1) if match else row["name"],
                            "repository_process": True}))
    latest = sorted((root / "logs/batch").rglob("sheet_progress.json"),
                    key=lambda path: path.stat().st_mtime, reverse=True)[:3]
    for path in latest:
        progress = json.loads(path.read_text(encoding="utf-8"))
        print(json.dumps({"path": str(path)} | {key: progress.get(key) for key in
                         ("status", "heartbeat_at", "completed", "total")}))


if __name__ == "__main__":
    main()
