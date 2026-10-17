> Archivo histórico preservado el 17-10-2026. Sus referencias a «actual», «vigente» o «siguiente» corresponden a la fecha de cada entrada. No es una guía de ejecución vigente. Consulte [arquitectura actual](../architecture.md), [relevo](../handoff_current.md) y [backlog](../pending_work_current.md). Se ajustaron únicamente rutas relativas de enlaces al archivar.

# Lotes de análisis: flujo vigente

Antes de diagnosticar, lanzar o reanudar un lote, leer
[`handoff_current.md`](../handoff_current.md). El backlog vigente está en
[`pending_work_current.md`](../pending_work_current.md). El lote del 29-09-2026,
orden `20260929-160621-market-d41c8302`, se detuvo en 27/46 y luego se
reanudó desde el checkpoint original con autorización expresa. A las 18:43
UTC seguía activo en 35/46. Consultar el relevo y el progreso vivo antes de
cualquier acción; no lanzar una segunda orden ni reconciliar un RUNNING vivo.

## Comandos normales

Usar el Python del repositorio. La lista «todos» procede de
`gs://stock-analysis-reports-naxo85/config/tickers.json`:

```powershell
& '.\.venv\Scripts\python.exe' -m src.local_runner.run_batch --from-gcs --upload-real --max-parallel 6
```

Para «core»:

```powershell
& '.\.venv\Scripts\python.exe' -m src.local_runner.run_batch --config-gcs gs://stock-analysis-reports-naxo85/config/tickers_core.json --upload-real --max-parallel 6
```

`--upload-real` activa la publicación real del batch. Un ticker individual usa
`python -m src.local_runner.run_one RKLB --run-full`. Si el usuario pide una
prueba sin publicación, usar el modo dry-run indicado en `AGENTS.md`.

ChatGPT Web con Sol/Alta es el generador principal y Codex es fallback
automático. Hay tres trabajadores Web persistentes, cada uno con su perfil
Firefox y grupos de hasta cinco tickers por chat dentro de `Analisis`.
`--max-parallel 6` solapa preparación, generación y publicación; no crea
seis sesiones Web. El límite del runner es 8. Los chats se conservan; el
batch no programa su eliminación.

## Fases y artefactos

```text
fuentes/prepare -> ChatGPT Web generate/validate -> publish
                                   \-> Codex fallback si falla Web
```

La actualización de noticias, analistas y earnings libera cada ticker al
completar su preparación. Un fallo de un ticker no debe detener los demás.
El checkpoint durable se guarda en
`logs/batch/YYYY-MM-DD/HH-MM-SS/pipeline_state.json`; el resumen en
`summary.json`, el progreso en `sheet_progress.json` y los eventos de espera
anómala en `stall_events.jsonl`. Los intentos Web conservan diagnósticos por
ticker en `output/<TICKER>/browser_diagnostics/`.

El estado visible en `C4` es un espejo. Para saber qué ocurrió, comparar el
resultado de la orden, el checkpoint, el progreso local y remoto, las salidas
por ticker y los diagnósticos del intento. `47/47` publicado no implica que
Web funcionase bien: revisar proveedores efectivos, lista de fallback,
reintentos Web y de pipeline, stalls y trabajadores desactivados. Para
reproducir un fallo Web, usar un solo ticker con
`--no-generator-fallback`.

## Interrupción y recuperación

No iniciar una orden nueva para completar un lote interrumpido. Comprobar
primero que no hay otro worker con el lock, preservar artefactos y usar el
checkpoint exacto con `--resume-pipeline-from` solo tras autorización del
usuario. La herramienta `scripts/resume_batch_command.py` conserva la
identidad de la orden del 29-09; su uso concreto está en el relevo.

Si la orden ya es terminal pero `commands/progress/latest.json` permanece
`running`, reconciliar únicamente cuando coincidan los IDs de estado,
progreso remoto y progreso local **y el heartbeat sea anterior al cierre de
la orden**. Un heartbeat posterior indica una posible reanudación; la
herramienta la rechaza. Conserva los contadores publicados:

```powershell
& '.\.venv\Scripts\python.exe' -m src.local_runner.progress_reconciliation --command-id ID --progress-path logs\batch\FECHA\HORA\sheet_progress.json
& '.\.venv\Scripts\python.exe' -m src.local_runner.progress_reconciliation --command-id ID --progress-path logs\batch\FECHA\HORA\sheet_progress.json --execute
& '.\.venv\Scripts\python.exe' -m src.local_runner.progress_reconciliation --command-id ID --progress-path logs\batch\FECHA\HORA\sheet_progress.json --verify
```

Esto cierra el indicador, sin analizar tickers ni convertir los no
publicados en fallos individuales. El procedimiento de diagnóstico completo
está en `handoff_current.md`.

## Compatibilidad histórica

Las rutas antiguas Trading/Core, referencias semanales Sol/Tierra/Luna y
`model_usage.base` permanecen en algunos artefactos y módulos por
compatibilidad. No representan la política operativa Web actual.
`model_usage.base` describe la ruta planificada; para diagnosticar un lote
usar el proveedor/modelo efectivo de cada salida y los contadores Web/fallback.
El usuario retiró del backlog la propuesta de fallback según antigüedad del
análisis Sol y el recuento nuevo por modelo. Véase
[`pending_work_current.md`](../pending_work_current.md).
