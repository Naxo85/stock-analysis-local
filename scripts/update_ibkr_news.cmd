@echo off
setlocal

cd /d "%~dp0.."

python -m src.local_runner.update_ibkr_news_batch %*

endlocal
