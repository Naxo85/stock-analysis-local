@echo off
setlocal

cd /d "%~dp0..\apps_script"

clasp login --status
clasp status

endlocal
