@echo off
setlocal

cd /d "%~dp0.."

python -m src.local_runner.audit_analyst_firm_aliases %*

endlocal
