@echo off
cd /d "%~dp0.."
".venv\Scripts\python.exe" scripts\start_android_emulator.py --visible --open-app
if errorlevel 1 pause
