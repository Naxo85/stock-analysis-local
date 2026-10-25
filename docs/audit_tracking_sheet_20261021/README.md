# Vaciado de Mercado al sincronizar shots — 21-10-2026

Estado: hoja restaurada y ruta local corregida. El cambio anterior del worker
llamaba incondicionalmente a `_reconcile_structure`. El inicializador utilizado
interpretaba el merge del panel QQQ `C2:E2` como ajeno a la estructura esperada y
emitía un borrado de valores/notas/formatos de `A2:AM27` antes de reconstruir.
Después se recuperaban los informes y los shots, pero las cotizaciones y el
panel podían quedar vacíos hasta el siguiente refresco. Fue un fallo del cambio
de shots, no una pérdida de la cartera persistida.

La reproducción sobre la captura real restaurada genera exactamente el plan
`unmerge` del recuadro QQQ y el borrado general. La captura previa de la hoja
dañada ya no contiene ese merge. No se conserva el request HTTP original; la
causa se apoya en el código ejecutado, los recibos de las compras posteriores y
la reproducción con metadatos reales.

La recuperación usó `run_refresh(publish=True, force=True)` con las fuentes y
cachés normales y `run_sync(..., force=True)` para proyectar los informes ya
publicados.46tickers,15benchmarks, panel general y QQQ restituidos; cero modelos
o lotes nuevos. Se verificó cartera remota exacta al acabar la restauración.
Los nuevos clicks del usuario se conservaron durante la verificación posterior.

La sincronización local usa ahora `tracking_sheet.preserving_structure_requests`.
Con el mismo universo y geometría emite cero escrituras estructurales, aunque
haya cambios en estilos, named ranges o el merge QQQ. Para altas/bajas copia sólo
las filas de ticker por identidad, conserva valores/notas/enlaces/formatos y
bordes, cambia rangos de tablas sin reconstruirlas y vacía únicamente una fila
vacante por una baja autorizada. El panel y resumen quedan fuera de esas máscaras.
El menú inmediato y el CAS de cartera permanecen activos.

Verificación:46tests Python; regresión del merge QQQ, hoja poblada, alta y baja,
conservación de cotizaciones, notas, enlaces normalizados y bordes. Comprobación
real posterior:322celdas de métricas presentes, panel y QQQ presentes y cero
llamadas estructurales de escritura en el reconciliador. Sin compras de prueba.

Evidencia privada local: `logs/market_tracking/blank_sheet_20261021/`, incluidas
capturas antes/después, snapshot/requests de refresco, recibo de proyección,
reproducción del borrado y `verification.json`.
