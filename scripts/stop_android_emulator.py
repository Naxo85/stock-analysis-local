"""Stop the verified private emulator, without touching physical devices."""
import json
from pathlib import Path
import subprocess
import ctypes
from android_toolchain import TOOLS
sdk=Path(json.loads((TOOLS/'environment.json').read_text())['sdk'])
adb=str(sdk/'platform-tools/adb.exe')
name=subprocess.run([adb,'-s','emulator-5580','shell','getprop','ro.boot.qemu.avd_name'],capture_output=True,text=True,timeout=15)
if name.stdout.strip()!='growth-test':raise RuntimeError('Private emulator identity not verified')
result=subprocess.run([adb,'-s','emulator-5580','emu','kill'],capture_output=True,text=True,timeout=20)
if 'killing emulator' not in result.stdout:
    pid=int((TOOLS/'emulator.pid').read_text())
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:raise RuntimeError('Recorded emulator process is no longer available')
    try:
        buffer=ctypes.create_unicode_buffer(32768);size=ctypes.c_ulong(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(size)):raise RuntimeError('Cannot verify process image')
        if Path(buffer.value).resolve()!= (sdk/'emulator/emulator.exe').resolve():raise RuntimeError('Recorded process is not the task emulator')
    finally:kernel.CloseHandle(handle)
    subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],check=True,capture_output=True)
print('Stopped verified private Growth emulator')
