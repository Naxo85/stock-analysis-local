# A1 — Puesta en servicio de publicación y lectores (2026-10-18)

Los tres consumidores están activados al 100% con imágenes mínimas construidas sobre sus digests activos originales. El publicador local admite manifest-v1 y autenticación explícita mediante la cuenta CLI existente; su activación de política la coordina raíz. No se ha llamado a modelos, recuperado recibos históricos, ejecutado lotes duplicados ni escrito informes reales o Sheet en esta tarea A1.

## Resultado y alcance

- Web: reports-publication40-20261018, imagen sha256:5e17a93658d320d230779b49e957b468087155ec03477c57163ef2f649d6d140.
- Móvil API: stock-mobile-api-publication40-20261018, imagen sha256:f4c05b8f854308a027c72d573a3ddcd876144ddd63fa87be3f8e786108fb04ca.
- Controller: stock-controller-publication40-20261018, imagen sha256:bc36dc3f00617dcc98e3711507ca13cdc9243906a27dad9fe8a2c5b53eeb3559.
- Región europe-southwest1; proyecto recipe-generator-429817. Runtime (cuenta, CPU, memoria, concurrencia, timeout, variables y referencias a secretos) idéntico al anterior al excluir imagen. IAM invocador de los servicios intacto. Etiqueta anterior strengthtest preservada.
- Rollback de tráfico: reports-00003-g97; stock-mobile-api-00007-g5b; stock-controller-solid65-20261015, cada uno al 100%. Se conservaron esas revisiones y sus imágenes; no se alteraron sus especificaciones.

## Cambios y dependencias

Los overlays contienen 2 archivos web, 3 móvil y 5 controller. El quinto archivo del controller, analysis_worker/run_sync.py, es necesario: la identidad de la proyección usa publication_version cuando existe manifest, en lugar de la generación del espejo legacy. El runtime activo real carga el paquete instalado bajo /usr/local/lib/python3.12/site-packages, no un árbol fuente genérico. overlay-plan.json y build/*/files.json contienen destinos y hashes previos/posteriores; se comprobó equivalencia AST con la base caracterizada y se preservaron funciones ajenas, incluyendo visibilidad65/solidez70 y extensión36.

El controller carecía de permiso efectivo de lectura de CAT/latest.json (403). Se añadió únicamente roles/storage.objectViewer a serviceAccount:stock-analysis-sheets@recipe-generator-429817.iam.gserviceaccount.com en gs://stock-analysis-reports-naxo85. GET efectivo posterior200. No se añadieron permisos públicos, roles de proyecto ni claves. La identidad CLI existente [cuenta personal omitida] sí podía hacer GET real200; no se le amplió IAM aunque testIamPermissions de bucket no anunciaba storage.objects.get.

ADC local estaba ausente. publication_auth.py introduce un modo optativo explícito gcloud-cli con cuenta/proyecto fijados, token exclusivamente en memoria, refresco mediante CLI existente y errores redactados. ADC sigue siendo el default y lo usan los servicios. No hay fallback, login nuevo ni credenciales guardadas. GcsStore acepta auth; stage/attempt y validación de política transmiten esta configuración. candidate_publication_auth.json contiene solo modo/cuenta/proyecto. Dependencias instaladas verificadas por raíz: google-cloud-storage3.13.0 y google-auth2.56.2.

Se añadió además rechazo explícito de publication.json sin committed_at al índice del controller, consistente con web/móvil. No altera contratos financieros o modelos.

## Evidencia de pruebas

1. 80 pruebas offline de auth/integridad/consumidores pasan (71.98s); harness bloquea red/procesos externos. bridge_tests.log.
2. Cada build ejecutó pruebas sobre sus archivos instalados exactos con hashes, coherencia manifest, alias no confirmado, fechas/fallo, pinning de versión, corrupción y puntero no confirmado, sin conexiones externas durante esos tests. Los tres builds finales SUCCESS. Primer intento de los tres builds falló en la comprobación exacta de hash por conversión CRLF al escribir el overlay en Windows; se corrigió el escritor a bytes UTF-8, se regeneraron todos y se repitieron las mismas guardas, sin debilitarlas. Registros attempt1 preservados.
3. CAS real en prefijos sintéticos nuevos ZZZAUDIT40/ZZZAUDIT40F del bucket reports: ack perdido tras escritura, reintento idempotente, CAS obsoleto rechazado, lectura histórica A y actual B; alias latest no confirmado deliberado; intento fallido separado. live-cas-result.json. Ningún símbolo real escrito.
4. Bucket privado temporal stock-analysis-audit40-20261018-714254943648, acceso público impedido y permisos viewer a las tres SA lectoras. CAT puramente sintético con fecha2000 y score8 ficticio. Revisiones web/móvil0% con ese bucket, mismas imágenes finales; lectura de system y Sheet únicamente. HTTP real: JSON/MD/HTML B actual y A histórica, fallo visible sin cambiar fecha, alias ignorado, versión inválida400/inexistente404 y fallo sin informe404. Móvil autenticado report/dashboard mostraron versiónB, fecha2000 y aviso failed. isolated-http-results.json.
5. Controller no tiene ruta financiera de lectura: /analysis/refresh escribe Sheet y no fue invocada. Un Job temporal autorizado ejecutó MISMA imagen y MISMA SA, leyó fixture GCS real mediante GcsAnalysisReportStore, verificó5hashes de archivos y proyectó score/aviso/link fijado en memoria. Caso sin informe conservó fecha desconocida. Exit0, cero escrituras Sheet. controller-job-status.json y controller-job-logs.json. Esta prueba valida integración de lectura/proyección, no una escritura productiva de Sheet.
6. Revisiones finales con buckets originales a0%: Ready, runtime exacto, CAT legacy web3formatos íntegro; móvil CAT conserva fecha/texto, dashboard46sinwarnings; /health controller autenticado200. production-http-results.json. Tras100%, mismas comprobaciones sobre URLs habituales: active-http-results.json.
7. Comprobación ampliada46/46: web y móvil coinciden con cada latest.json original GCS en generated_at, analysis_status y analysis_markdown. Generación de cada objeto igual antes/después, sin mutaciones. legacy46-readback.json guarda fechas/hashes/generaciones, no copia cuerpos financieros.

## Límites y operación

La atomicidad es por ticker y manifest. Sheet es proyección asíncrona: la fila apunta a una versión verificable, pero no se promete una transacción global de todo el universo. El intento más reciente sigue separado de la fecha financiera, incluso al consultar una versión histórica. La prueba no convierte los reportes legacy en manifest ni los redatada; su primera publicación natural confirmada adoptará el protocolo según la política que active raíz. El historial protegido de modelos/recibos congelados no se reescribe.

Para rollback global del protocolo, desactivar primero nuevos commits manifest y evaluar consumidores: devolver un lector legacy después de publicar manifests podría reabrir dependencia de aliases. Las revisiones anteriores se conservan como rollback técnico; no ejecutar rollback ciego de lectores con publicador aún activo. Cada consumidor soporta legacy y manifest.

## Artefactos y limpieza

Inspección previa: *-before-redacted.json, *-active-source.json, iam-before.json, runner-adc-before.json. Estado posterior: *-activated.json y *-final.json; IAM antes/después y diferencia exacta en iam-final.json. No se guardaron tokens ni valores de secretos. Limpieza condicionada por identidad/generación y tráfico100% activo: cleanup-results.json confirma limpieza completa: 36 objetos propios eliminados con precondición de generación, bucket temporal eliminado, dos revisiones de ensayo y el Job eliminados, tags propios retirados. El bucket temporal tenía soft-delete de604800segundos por defecto del proveedor: eliminado del servicio activo, con retención recuperable7días de GCS; no se afirma borrado físico inmediato. Solo se retiran tags/revisiones de ensayo propias, Job temporal, bucket privado y objetos sintéticos inventariados; se conservan imágenes finales, revisiones de rollback y evidencia de builds.
