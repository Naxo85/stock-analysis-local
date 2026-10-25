# Integridad y publicación del lote natural 18-10-2026

Alcance: logs/batch/2026-10-18/09-08-40, orden 20261018-090400-731-market-a8dba136. Auditoría posterior de solo lectura: ningún modelo, publicación, lote, recuperación o mutación remota. Los informes y artefactos originales se leyeron sin cambiarlos.

## Resultado

- 46/46 bundles verifican archivos, evidencia, review y snapshots. Los 46 recibos autentican respuesta/eventos/contrato y finalización; los inputs crudos y schemas coinciden con sus hashes. Esta es integridad local, no una firma del proveedor.
- 46/46 publicaciones confirmadas en GCS: manifest actual idéntico al commit local; manifest histórico idéntico; seis objetos inmutables por símbolo (276), todos con su hash correcto. El puntero conserva generación y contenido durante cada comprobación.
- 46/46 intentos remotos succeeded, con versión exacta del commit y mismo contenido que el intento local. Esto confirma autoridad publicada, más allá de exit_code=0.
- 46/46 respuestas JSON web y móvil coinciden en Markdown, fecha financiera, estado, versión e intento. La consulta web con versión explícita resuelve el mismo informe. Los md/html inmutables se comprobaron por hash; no se volvió a probar visualmente cada formato o cada pantalla.
- Los 46 espejos GCS de entrada a Sheet y los dos objetos de resumen remoto coinciden exactamente con los archivos locales.
- Marcador real de sincronización controller a las10:00:47.007764UTC: las46 versiones registradas coinciden con los commits naturales. El dashboard móvil tiene70 zonas, y rangos/notas/fechas/versiones coinciden en46/46, sin warnings ni stale.

## Retención y fechas

25retained,21updated,0regenerated. Los46 anclajes completos permanecen exactamente iguales al sol_reference congelado, y mantienen su fecha completa e ITV. Los25 retained conservan la fecha financiera, decisión, catalizadores, próximo evento, rangos de compra, puntuaciones, componentes y razones del plan.22 conservan también el Markdown exacto. TLN,PLTR yASML actualizan únicamente la extensión estimada de Entry y su explicación/fecha/fuentes correspondientes dentro del plan, con Markdown coherente:349.15→348;184.5→182;1610→1590. Esta facultad de presentación/estimación36–37 está permitida en retain; su conveniencia financiera se revisa por separado. No se debe describir estos tres como un plan idéntico byte a byte ni convertir el commit nuevo en una renovación de la fecha financiera. Los21updated sí tienen una nueva fecha financiera.

## Celdas reales de Sheet y límites

El primer GET con la credencial GCloud devolvió403 PERMISSION_DENIED y queda registrado. El conector Google Drive ya conectado sí permitió leer el documento exacto y la pestaña visible Mercado, sin ampliar permisos ni crear Job. Metadata confirmó27filas y38columnas. Se leyeron solo322celdas acotadas:92de ticker/precio y230financieras en46filas.

Comparación independiente con el proyector local del controller:230/230valores exactos (Entry,Washout,Res vacía,Tesis,Setup); notas de Entry/Washout/Setup exactas en46/46;46enlaces de Tesis exactos a las versiones comprometidas. Cero discrepancias. Las70zonas internas no implican70celdas visibles: se mantiene el umbral65 y la lógica vigente de presentación. El móvil por sí solo no probaría esta coherencia de celdas; la comprobación se hizo con la lectura real del conector.

No se compararon colores/bordes ni la nota de delta/historial de Tesis. No se verificó un teléfono físico. La hora de cada lectura figura en su evidencia; no demuestra un estado futuro.

## Evidencia

- local_integrity.json: verificación local completa y diferencias por símbolo.
- supplemental_local_bindings.json:46 hashes de input crudo y25 planes retenidos sin cambios salvo los campos de extensión.
- remote_integrity.json:276 hashes/generaciones,46manifests/intentos/lectores/enlaces versionados y dashboard.
- compatibility_mirrors.json:46 espejos y dos resúmenes remotos.
- projection_and_sheet_read.json: sincronización controller,70zonas móviles y antecedente403 delGETGCloud.
- sheet_connector_metadata.json, sheet_connector_cells.json y sheet_connector_verification.json: metadata del destino exacto,322celdas reales y comparación de230valores/46enlaces/notas.
- sheet_projection_layout.json y verify_sheet_connector.py: configuración vigente sin identidad del documento y comparación local pura.
- audit_integrity.py, audit_mirrors.py, audit_projection.py: procedimientos usados, solo GET/descargas remotas.

Este resultado demuestra funcionamiento e integridad del recorrido de publicación observado. No demuestra rentabilidad, calidad predictiva, ejecución de la ruta full o ausencia de fallos futuros.
