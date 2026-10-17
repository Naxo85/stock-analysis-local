@echo off
setlocal
cd /d "%~dp0"
echo Se abrira Chrome con el perfil dedicado del analisis, no su perfil personal.
echo En esta ventana las extensiones y la sincronizacion del navegador estaran desactivadas.
echo Inicie sesion en ChatGPT con su cuenta habitual.
echo Abra el proyecto Analisis y espere a que cargue.
echo Despues cierre SOLO esta ventana de Chrome y avise a Codex.
".venv\Scripts\python.exe" -m src.local_runner.chatgpt_browser_generator login --browser chromium --worker-id 1
if errorlevel 1 pause
