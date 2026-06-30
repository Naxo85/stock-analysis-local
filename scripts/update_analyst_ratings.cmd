@echo off
setlocal

cd /d "%~dp0.."

python -m src.local_runner.update_analyst_ratings_batch %*

endlocal
