@echo off
setlocal
cd /d "%~dp0"
echo Se abriran solo los perfiles 2 y 3. El perfil 1 ya esta verificado.
echo No ejecute este archivo durante un lote de analisis.
echo Si aparece el error de cuenta, pulse Volver a cargar.
echo Compruebe que puede abrir Analisis en ambos y cierre las dos ventanas.
for %%N in (2 3) do (
    echo Abriendo perfil %%N...
    ".venv\Scripts\python.exe" -m src.local_runner.chatgpt_browser_generator login --worker-id %%N
    if errorlevel 1 (
        pause
        exit /b 1
    )
)
echo Ambos perfiles se han abierto. Avise a Codex tras comprobarlos y cerrarlos.
pause
