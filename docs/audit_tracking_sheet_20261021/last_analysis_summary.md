# Restauración del resumen del último análisis — 21/10/2026

El vaciado documentado en README.md también eliminó Mercado!A9 y su nota.
El arreglo inicial recuperó métricas/paneles pero omitió este resumen, cuya
escritura pertenece al reconciliador Apps Script. El recibo de fecha sobrevivió
en ScriptProperties y hacía que el reconciliador ignorase la celda vacía.

`reconcileLatestMarketBatchSummary_` comprueba ahora tanto el recibo como el
valor visible y la nota esperados. Si falta la hoja no registra éxito. Utiliza
el mismo formateador y la misma publicación acotada a A9/A10; no ejecuta análisis.

Fuente original: `batch/status/latest_trading.json`, final21/10/2026
07:33:33UTC:46/46,0fallidos,2completos,0actualizados,44conservados,
2447.01segundos,2reintentos de lote. Copias de los estados originales en
`logs/market_tracking/last_analysis_summary_20261021/`.

Dos pulls verificaron que sólo cambia `analysis_completion_sync.js`; el original
remoto coincidía con HEAD. Publicado mediante el helper seguro; copias en
`.tmp_apps_script_push/20261021-095922/`. El trigger existente repuso A9 sin
ejecución manual. Google Sheets confirmó valor/nota; navegador confirmó la nota
visible. [Captura](last_analysis_restored.png).

Validación: `tests/test_market_summary_reconcile.js` comprueba recuperación de
celda/nota, repetición sin escrituras, reparación de nota ausente o anticuada y
hoja ausente sin marcar éxito. `tests/test_market_analysis_menu.js` también pasa.
Sin lote/modelo nuevo, compras/ventas ni cambio de informes financieros.
