# stock-analysis-local

Centro de control local del sistema de analisis de acciones. El flujo diario usa
Python para preparar, validar y subir los informes, y Codex para generar el
Markdown final.

## Antes de modificar el sistema

La vista completa de componentes, relaciones, flujos, almacenamiento y
despliegues esta en:

[`docs/architecture.md`](docs/architecture.md)

Empieza por ese documento para saber que parte vive en local, cual se ejecuta
en Google Apps Script o Cloud Run, como se comunican mediante GCS y que codigo
es solo una referencia historica.

## Uso habitual

Desde la raiz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.run_one RKLB --run-full
```

Batch Trading:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.run_batch `
  --from-gcs --upload-real --max-parallel 6
```

Batch Core:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.run_batch `
  --config-gcs gs://stock-analysis-reports-naxo85/config/tickers_core.json `
  --upload-real --max-parallel 6
```

## Instalacion en un ordenador nuevo

Requisitos del sistema:

- Windows y PowerShell 5.1 o posterior;
- Git;
- Python 3.12 recomendado (3.11 o posterior);
- Codex Desktop o Codex CLI autenticado;
- Google Cloud SDK autenticado.

Despues de clonar:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\setup_new_pc.ps1
```

Completa `FINN_KEY` en `.env.local` y verifica el equipo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\check_new_pc.ps1 -Online
```

Para comprobar tambien IBKR, abre TWS/Gateway con la API activa en el puerto
paper `7497` y ejecuta:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\check_new_pc.ps1 -Online -CheckIbkr
```

La guia completa, incluida la autenticacion y los elementos que no deben
guardarse en Git, esta en
[`docs/new_computer_setup.md`](docs/new_computer_setup.md).

## Dependencias opcionales

- IBKR TWS/Gateway: titulares, analistas y eventos. Si no esta disponible, el
  flujo principal continua usando el ultimo estado local disponible.
- Node.js y `@google/clasp`: solo para administrar Apps Script.
- Clave Gemini/Google: agregacion secundaria opcional de noticias.

## Documentacion operativa

- `docs/architecture.md`: mapa completo del sistema y guia para localizar cambios.
- `docs/standard_analyze_workflow.md`: contrato del analisis individual.
- `docs/batch_workflow.md`: ejecuciones por lotes.
- `docs/command_queue.md`: ordenes desde Google Sheets hasta el worker local.
- `docs/apps_script_ticker_export.md`: listas Trading/Core y columnas de la Sheet.
- `docs/operations.md`: mapa de operaciones y despliegues.
- `docs/troubleshooting.md`: problemas conocidos.
- `docs/new_computer_setup.md`: instalacion y autenticacion en otro ordenador.
