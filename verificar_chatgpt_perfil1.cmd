@echo off
setlocal
cd /d "%~dp0"
echo Abriendo solo el perfil 1 de ChatGPT.
echo Abra Analisis y despliegue el selector de modelo para comprobar que carga.
echo Despues cierre esta ventana de Firefox y comunique el resultado a Codex.
".venv\Scripts\python.exe" -m src.local_runner.chatgpt_browser_generator login --worker-id 1
if errorlevel 1 pause
