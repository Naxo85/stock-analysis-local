@echo off
setlocal

cd /d "%~dp0.."

python -m src.local_runner.push_apps_script_file %*

endlocal
