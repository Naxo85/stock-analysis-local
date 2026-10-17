@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno Python del repositorio.
    pause
    exit /b 1
)

echo Verificacion manual de los tres perfiles ChatGPT Web.
echo No ejecute este archivo durante un lote de analisis.
echo Para cada Firefox: complete usted la verificacion, espere al cuadro de ChatGPT y cierre solo esa ventana.

for %%N in (1 2 3) do (
    echo.
    echo Abriendo perfil %%N de 3...
    ".venv\Scripts\python.exe" -m src.local_runner.chatgpt_browser_generator login --worker-id %%N
    if errorlevel 1 (
        echo No se pudo completar el perfil %%N. No se abriran los siguientes.
        pause
        exit /b 1
    )
)

echo.
echo Los tres perfiles se han abierto. Cierre las tres ventanas de ChatGPT.
echo Despues avise a Codex para comprobar Web antes del lote.
pause
