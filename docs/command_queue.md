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

El worker reconoce las cuatro acciones de análisis y tres acciones acotadas de seguimiento:

- `analyze_ticker`
- `analyze_trading`
- `analyze_core`
- `analyze_market`
- `portfolio_buy_shot`
- `portfolio_sell_shot`
- `market_remove_ticker`

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

Al solicitar `analyze_trading`, `analyze_core` o `analyze_market` desde
Google Sheets, Apps Script exporta primero la lista actual de tickers a su JSON
de configuración y solo después crea la orden. Si la exportación falla, la
orden no se encola.

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

La acción `analyze_market` consume
`config/tickers_market.json`, generado desde las dos tablas de `Mercado`.
Lanza `run_batch` con publicación real, perfil de trading y las mismas
actualizaciones previas de analistas y noticias. No modifica el prompt, el
esquema del informe, la validación ni el upload por ticker.

Las órdenes manuales de Trading/Core recibidas desde Google Sheets no se
bloquean por ser viernes o sábado: el worker añade
`--analysis-mode daily` y aplica el enrutado normal Luna/Terra. El salto de
viernes/sábado queda reservado para futuras ejecuciones automáticas directas
del calendario. El domingo conserva el modo automático de referencia semanal.

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
- `analyze_core`: actualiza target/nota de core;
- `analyze_market`: el sincronizador cloud publica los informes validados y
  Apps Script escribe el resumen final del lote en `Mercado`.

Mientras haya órdenes activas, `Mercado!C4` muestra el estado global de la cola:

- `PENDING`: la orden está enviada y aún no ha sido reclamada por el worker,
  con fondo amarillo claro;
- `RUNNING n/total`: una orden batch está en ejecución, con fondo verde claro.
  Su nota muestra fase y ticker actuales, preparados, validados, publicados,
  fallidos, reintentos, tiempo transcurrido, ETA y heartbeat. El runner publica
  este estado cada 15 segundos en `commands/progress/<command_id>.json` y la
  Sheet lo consulta con su trigger temporal cada minuto.
- `SIN SEÑAL`: la orden continúa en `running`, pero el heartbeat lleva más de
  tres minutos sin actualizarse; se muestra con fondo rojo claro.

Cuando no quedan órdenes pendientes ni en ejecución, `C4` vuelve a quedar
vacía y sin color de fondo. No se muestra un estado `COMPLETED`.

Después de una actualización completa, `Mercado!A9` muestra una única fecha
`Mercado: dd/MM/yyyy`; `A10` se limpia. La nota de `A9` conserva la fotografía
final del progreso: publicados, fallidos, duración, uso real de ChatGPT Web y
Codex fallback, reintentos, errores e inicio/fin. Si intervino Codex, `A9`
queda con fondo amarillo claro.

Las actualizaciones de un único ticker no cambian estas celdas.

Los fallos completos no modifican la Sheet. Si un batch publica correctamente
al menos un ticker pero termina con otros fallidos, el resultado incluye los
contadores `batch_success`, `batch_total` y `batch_failed`: la Sheet aplica los
informes publicados y mantiene las referencias anteriores de los fallidos,
sin ocultar el estado `failed` de la orden. Cada orden se elimina de la lista
local después de procesarla. Cuando no quedan órdenes, el trigger se
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

## Posiciones y seguimiento desde Mercado

El menú `Análisis IA` ofrece `He comprado 1 shot...`, `He vendido 1 shot...` y `Quitar ticker del seguimiento...`. Compra y venta actualizan el número exacto de shots, el color del ticker, la banda lateral del grupo y las columnas `Pos.`/`Shots`. Vender el último shot conserva el ticker sin color; quitarlo elimina tanto el seguimiento como cualquier posición restante.

Si una compra usa un ticker nuevo, Apps Script solicita su grupo y la operación actualiza conjuntamente `market_sheet_layout.json`, `portfolio.json`, `tickers_market.json` y la estructura de la hoja. El controlador cloud lee el universo vivo desde `gs://stock-analysis-system-naxo85/runtime/config/market_sheet_layout.json`, por lo que el siguiente refresco no revierte el alta o la baja.

Estas órdenes no escriben en `commands/status/latest.json`, no crean seguimiento de análisis y no alteran `Mercado!C4`. El historial `applied_tracking_commands` evita aplicar dos veces una misma orden si el worker la reanuda.

## Ordenes acumuladas de shots (02-10-2026)

Cada orden se envia por push como objeto GCS independiente. El worker hace pull
y aplica su delta al estado mas reciente; una fotografia anterior no puede
deshacer operaciones posteriores a su captura. La fecha portfolio_snapshot_at
se toma antes de leer la hoja; las ordenes antiguas usan created_at.
El historial se persiste antes de publicar para que un reintento del mismo ID
no duplique compras ni ventas, incluso si falla la publicacion.

El wrapper programado usa --drain: reclama y finaliza una orden cada vez,
reconsulta la cola y sigue hasta vaciarla. --once conserva su comportamiento
para diagnostico. No cambia el sondeo de un minuto ni el bloqueo mientras
un analisis esta activo. Un fallo no elimina las ordenes posteriores.

Regresiones: tests/test_tracking_queue_regressions.py.

## Operaciones del menú durante un análisis (21-10-2026)

Compra y venta se confirman visualmente en la misma invocación de Apps Script:
el menú encola primero el ID original, actualiza `runtime/config/portfolio.json`
con CAS por generación y pinta color, banda de grupo y Pos./Shots antes de
terminar. El historial registra ese mismo ID, por lo que el worker reconoce el
delta ya aplicado y sólo reconcilia estructura y mirrors. La cartera queda
persistida para los consumidores, y la ordenación conserva sus colores; la
respuesta visual no depende de que termine un lote.
Se conserva el contador exacto incluso con tres o más shots. Las etiquetas del
resumen se resuelven por su orden visible, que puede estar ordenado por Día.

El worker lee cartera/layout remotos antes de mutar, rebasea conflictos CAS y
marca la publicación sin sobrescribir compras posteriores del menú. No publica
copias locales antiguas de esos dos objetos. `refreshMarketPortfolioNow` vuelve
a pintar el estado actual sin crear compras ni ventas; se verificó en el Apps
Script activo el21-10, ejecución09:22:25–09:22:31 Madrid. Sólo se cambió
`market_portfolio_menu.js` del proyecto remoto vinculado en `.clasp.json`.

El worker consulta también las órdenes de cartera/seguimiento cada60s mientras
espera al subproceso de análisis. La lectura de stdout está en un hilo para que
un análisis silencioso no bloquee esta consulta. Sólo se reclaman acciones de
seguimiento verificadas en el JSON; otros análisis permanecen en cola. Las
operaciones mantienen sus IDs originales, deltas acumulativos e historial
idempotente, sin cambiar el estado global del análisis ni sus inputs congelados.

El código se carga en el siguiente arranque del worker; una instancia ya activa
conserva su implementación anterior. El21-10 se diagnosticaron nueve compras
pendientes detrás del lote Mercado y se atendieron mediante el mismo procesador
filtrado, sin reiniciar el lote. Evidencia local: logs/market_tracking/recovery_20261021.
Pruebas:42casos Python en tests/test_tracking_during_analysis.py,
tests/test_command_worker.py, tests/test_tracking_queue_regressions.py,
tests/test_market_tracking.py y tests/test_tracking_runtime_cas.py; pruebas Node
tests/test_market_immediate_shots.js y tests/test_market_analysis_menu.js.
