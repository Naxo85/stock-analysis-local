@echo off
setlocal

cd /d "%~dp0.."

python -m src.local_runner.backfill_analyst_summaries %*

endlocal
