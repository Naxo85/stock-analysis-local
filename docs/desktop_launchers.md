# Lanzadores de escritorio

> En instalaciones nuevas, los lanzadores usan primero
> `.venv\Scripts\python.exe`. Créalo con `scripts\setup_new_pc.ps1`.

Los lanzadores permiten iniciar análisis sin escribir comandos manualmente.

## Accesos disponibles

- `Analizar Trading`: ejecuta el batch real desde `config/tickers.json` con paralelismo 6.
- `Analizar Core`: ejecuta el batch real desde `gs://stock-analysis-reports-naxo85/config/tickers_core.json` con paralelismo 6.
- `Analizar Ticker`: abre una ventana, pide un ticker y ejecuta su flujo `--run-full`.

Los análisis iniciados por estos accesos generan y suben resultados reales. La ventana permanece abierta al terminar para mostrar `OK` o `FAILED`.

## Instalar accesos

Ejecutar una vez:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_desktop_shortcuts.ps1
```

Alternativamente, puede abrirse con doble clic:

```text
scripts\install_desktop_shortcuts.vbs
```

Esto no cambia permanentemente la `ExecutionPolicy`; el bypass solo se aplica al proceso que instala o abre el acceso directo.

## Eliminar accesos

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\remove_desktop_shortcuts.ps1
```

## Ejecutar scripts directamente

```powershell
.\scripts\analyze_trading.ps1
.\scripts\analyze_core.ps1
.\scripts\analyze_ticker.ps1
```

Para pruebas sin pausa final:

```powershell
.\scripts\analyze_ticker.ps1 -Ticker HOOD -NoPause
```

## Python

Se usa, por orden:

1. La variable `STOCK_ANALYSIS_PYTHON`, si apunta a un fichero válido.
2. `C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe`.
3. El comando `python` disponible en `PATH`.

## Siguiente fase

Estos mismos flujos serán invocados por el futuro `command_worker.py`, que recibirá órdenes desde Google Sheets mediante una cola en GCS.
