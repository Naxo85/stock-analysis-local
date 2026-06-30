# Cola de órdenes local

El worker permite que Google Sheets solicite análisis sin acceder directamente al ordenador local.

## Arquitectura

```text
Google Sheets / Apps Script
  -> GCS commands/pending
  -> command_worker.py --once
  -> runner local + Codex CLI
  -> GCS commands/completed o commands/failed
```

El worker solo reconoce tres acciones:

- `analyze_ticker`
- `analyze_trading`
- `analyze_core`

No acepta comandos de shell ni rutas arbitrarias.

## Permisos Apps Script

El manifest debe incluir estos scopes:

```text
https://www.googleapis.com/auth/spreadsheets.currentonly
https://www.googleapis.com/auth/script.external_request
https://www.googleapis.com/auth/devstorage.read_write
https://www.googleapis.com/auth/script.scriptapp
```

`script.scriptapp` permite crear y eliminar el trigger temporal. Después de
añadirlo, Google solicitará una nueva autorización la próxima vez que se
ejecute una función que gestione la cola.

Al solicitar `analyze_trading` o `analyze_core` desde Google Sheets, Apps Script
exporta primero la lista actual de tickers a su JSON de configuración y solo
después crea la orden. Si la exportación falla, la orden no se encola.

## Rutas GCS

```text
gs://stock-analysis-reports-naxo85/commands/pending/
gs://stock-analysis-reports-naxo85/commands/running/
gs://stock-analysis-reports-naxo85/commands/completed/
gs://stock-analysis-reports-naxo85/commands/failed/
```

Una ejecución `--once` toma como máximo una orden. Primero mueve la orden a `running`, ejecuta el flujo y finalmente escribe un JSON de resultado en `completed` o `failed`.

## Contrato

Ticker individual:

```json
{
  "id": "20260621-120000-hood",
  "action": "analyze_ticker",
  "ticker": "HOOD",
  "created_at": "2026-06-21T12:00:00Z"
}
```

Batch:

```json
{
  "id": "20260621-120000-trading",
  "action": "analyze_trading",
  "max_parallel": 6,
  "created_at": "2026-06-21T12:00:00Z"
}
```

`max_parallel` debe estar entre 1 y 8.

## Prueba local sin análisis

```powershell
python -m src.local_runner.command_worker --command-file examples/commands/analyze_ticker.json --dry-run
```

Este modo valida la orden y muestra el comando resultante. No consulta GCS, no ejecuta Codex y no sube resultados.

## Worker GCS

```powershell
python -m src.local_runner.command_worker --once
```

Si no hay órdenes, termina inmediatamente con `NO_COMMANDS`.

## Bloqueo local

`logs/command_worker.lock` evita que dos workers locales procesen órdenes a la vez. Un lock de más de cuatro horas se considera obsoleto.

## Siguiente fase

El archivo `apps_script/analysis_command_queue.gs` añade las funciones para
crear órdenes desde Google Sheets. El menú se conecta desde
`apps_script/export_tickers_to_gcs.gs`.

Prueba manual inicial:

1. Copiar/actualizar ambos Apps Scripts en el proyecto de la Sheet.
2. Recargar la Sheet.
3. Elegir `Análisis IA -> Analizar ticker en local...`.
4. Ejecutar el acceso de escritorio `Procesar Cola Una Vez`.
5. Verificar el resultado en `commands/completed` o `commands/failed`.

Una vez instalada la tarea programada de Windows, no es necesario pulsar el
acceso manual del worker. `process_command_queue_once.ps1` se conserva para
diagnóstico.

## Tarea programada

Para instalarla sin escribir comandos, abrir con doble clic:

```text
scripts\install_command_worker_task.vbs
```

La tarea `Stock Analysis Command Worker` comprueba una orden cada minuto. Usa
`wscript.exe` y un wrapper VBS con ventana completamente oculta para no robar el
foco. No inicia otra instancia si una sigue activa y permite hasta tres horas
para un batch.

Para eliminarla:

```text
scripts\remove_command_worker_task.vbs
```

La tarea usa un inicio de sesión interactivo: funciona cuando el usuario tiene
sesión iniciada en Windows. No guarda contraseñas.

La prueba real con `INOD` confirmó el flujo completo automático desde Google
Sheets hasta la generación local y actualización del informe.

## Sincronización automática de la Sheet

El worker publica el último resultado en:

```text
gs://stock-analysis-reports-naxo85/commands/status/latest.json
```

Al encolar una orden, `apps_script/analysis_completion_sync.gs` registra su ID
y crea un trigger temporal que consulta cada minuto únicamente las órdenes
pendientes. Cuando encuentra un resultado con estado `ok`:

- `analyze_ticker`: actualiza solo las filas donde aparece el ticker;
- `analyze_trading`: actualiza target/nota de trading;
- `analyze_core`: actualiza target/nota de core.

Después de una actualización completa, el updater registra la hora en la
Sheet:

- `AD5`: `Trading: dd/MM/yyyy`;
- `AD6`: `Core: dd/MM/yyyy`.

Las actualizaciones de un único ticker no cambian estas celdas.

Los resultados fallidos no modifican la Sheet. Cada orden se elimina de la
lista local después de procesarla. Cuando no quedan órdenes, el trigger se
borra automáticamente y deja de consultar GCS. Una orden que no termina en
cuatro horas se marca como expirada para evitar un trigger permanente.

No hace falta instalar un trigger permanente: `enqueueAnalysisCommand_` lo
crea automáticamente cuando envía una orden. La función siguiente queda como
herramienta manual de reparación:

```text
installAnalysisCompletionTrigger
```

El menú `Análisis IA -> Ver última ejecución` permite consultar el último
resultado publicado.
