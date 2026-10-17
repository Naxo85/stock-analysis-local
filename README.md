# stock-analysis-local

Centro de control local del sistema de analisis de acciones. El flujo diario usa
Python para preparar, validar, renderizar y publicar informes, y Codex para
devolver datos financieros estructurados y juicios de mantenimiento o revisión completa.

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

Lista «todos» de AGENTS (`tickers.json`; distinta del menú Mercado):

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.run_batch `
  --from-gcs --upload-real --max-parallel 6
```

El menú Mercado usa `tickers_market.json`. Alcance, efectos y comandos actuales en
[docs/batch_workflow.md](docs/batch_workflow.md). ChatGPT Web es una ruta legacy explícita.

Batch Core:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.run_batch `
  --config-gcs gs://stock-analysis-reports-naxo85/config/tickers_core.json `
  --upload-real --max-parallel 6
```

`run_one TICKER --run-full` usa el full high configurado y crea una referencia
autoritativa. Nuevos batches usan revisión 39: Sol 6.1 medium mantiene, high trata
full/causas críticas e ITV5. No hay fallback automático ni skip semanal heredado.
El comando Core anterior no refresca fuentes por sí solo; véase la guía de lotes.
Para ver rutas sin modelo/Gateway/publicación (puede leer GCS):

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.run_batch `
  --from-gcs --routing-plan
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

IB Gateway se comprueba y arranca automáticamente en segundo plano antes de un
análisis. Para comprobar además su API paper en el puerto `7497`, ejecuta:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\check_new_pc.ps1 -Online -CheckIbkr
```

La guia completa, incluida la autenticacion y los elementos que no deben
guardarse en Git, esta en
[`docs/new_computer_setup.md`](docs/new_computer_setup.md).

## Integraciones

- IBKR Gateway + IBC: titulares, analistas y eventos. El runner exige que la API
  esté disponible antes de preparar o ejecutar un análisis.
- Node.js y `@google/clasp`: solo para administrar Apps Script.
- Clave Gemini/Google: agregacion secundaria opcional de noticias.

## Documentacion operativa

- [docs/architecture.md](docs/architecture.md): mapa completo del sistema y guia para localizar cambios.
- [docs/standard_analyze_workflow.md](docs/standard_analyze_workflow.md): contrato del analisis individual.
- [docs/batch_workflow.md](docs/batch_workflow.md): ejecuciones por lotes.
- [docs/command_queue.md](docs/command_queue.md): ordenes desde Google Sheets hasta el worker local.
- [docs/apps_script_ticker_export.md](docs/apps_script_ticker_export.md): listas Trading/Core y columnas de la Sheet.
- [docs/operations.md](docs/operations.md): mapa de operaciones y despliegues.
- [docs/troubleshooting.md](docs/troubleshooting.md): problemas conocidos.
- [docs/new_computer_setup.md](docs/new_computer_setup.md): instalacion y autenticacion en otro ordenador.
- [docs/ibkr_gateway_automation.md](docs/ibkr_gateway_automation.md): Gateway automático, Secret Manager y migración.
- [docs/estrategia_compra_bolsa.md](docs/estrategia_compra_bolsa.md): cuaderno vivo para definir la estrategia de compra.
- [Auditoría independiente 17-10](docs/audit_analysis_system_20261017.md): evidencia, defectos y ampliación crítica de metodología con fuentes primarias y plan de evaluación; propuestas sin implementar.
- [Relevo](docs/handoff_current.md) y [backlog](docs/pending_work_current.md): estado y pendientes canónicos.
- [docs/system_audit_2026-09-04.md](docs/system_audit_2026-09-04.md): auditoría histórica, no descripción vigente.
- [docs/component_map.md](docs/component_map.md): mapa visual de componentes y secuencia operativa.
- [docs/plan_reconstruccion_sistema.md](docs/plan_reconstruccion_sistema.md): plan histórico de reconstrucción; no fija el destino normativo del diseño actual.

En un ordenador nuevo, después de autenticar Google Cloud, Gateway, IBC y sus
credenciales paper se reconstruyen con:

```powershell
.\scripts\bootstrap_ibkr_gateway.ps1
```
