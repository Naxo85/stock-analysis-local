# Puesta en servicio de la revisión 40 — 18-10-2026

**Activada y comprobada a las 08:17:18 UTC (10:17:18 Europe/Madrid).** Los nuevos análisis preparados en este repositorio usan revisión40, publicación manifest-v1, aviso del último intento y archivo técnico. Se conserva el ejecutor Codex local con autenticación ChatGPT, gpt-6.1-sol medium/high, ITV5 y concurrencia máxima6. No se introdujo otra API ni CLI de modelos. Una orden reanudada conserva su contrato congelado; el worker carga la política en cada nueva orden y no necesita reinicio.

La [matriz completa](../../../execution_audit_20261017.md) resuelve29 filas:18 desgloses originales de H01–H15, H16 de tenencia descubierto durante integración, H17 del arranque posterior, M01–M08 y C01. Distingue correcciones activadas, evaluaciones descartadas e incertidumbres concretas. La [auditoría original](../../../audit_analysis_system_20261017.md) conserva su historia y fuentes. No todas las propuestas son funciones que debían añadirse.

**Incidente posterior18-10/08:29:** el primer intento de Mercado falló antes del modelo por un lock GCS residual y un PID reutilizado. El arreglo local y la verificación de arranque están en [H17](gcs_lock_incident/README.md). El snapshot56archivos y los recibos anteriores describen la puesta en servicio inicial; H17 añade el cambio posterior de analysis_state.py y sus regresiones, sin modificar modelos ni servicios.

## Evidencia por ámbito

| Ámbito | Resultado comprobado | Índice |
|---|---|---|
| Fuentes y noticias | Raw/slim40 al100%; captura canónica con sesiones completas y opciones dirigidas; NVDA fresco completó14páginas/4.065identidades/19duplicados/95en ventana en116,5s, con evento terminal recibido y hasMore=False | [Datos](data/README.md) |
| Publicación y consumidores | Reports/móvil/controller al100%; CAS real, pérdida de ack, versiones fijadas y fallo sin informe en datos sintéticos.46informes productivos mantienen texto/fechas/generaciones | [Integridad](integrity/README.md) |
| Finanzas | LEU retained con1medium,0repair/0web; MRNA regenerated con1high,0repair/10operaciones web. Revisión financiera independiente de ambos, sin publicación | [Finanzas](financial/README.md) |
| Android | Release firmada, build/unit/lint offline,9tests de instrumentación, verificación visual y servicio real en emulador. Teléfono físico no verificado | [Android](android/README.md) |
| Activación local | Sustitución atómica, backup39 y lectura de SHA256; exactamente5claves cambiadas | [Recibo](policy_activation_receipt.json), [política sin identidades](active_policy_metadata.json) |
| Conservación | 2.152artefactos originales,65prompts antiguos, generador y sesiones intactos;98Python modificados/nuevos parseados; git diff --check limpio | [Invariantes](activation_invariants.json) |
| Historial documental |92archivos del paquete de evidencia anterior sin cambios; cierre local anterior guardado con fecha | [Verificación](historical_evidence_integrity.json), [historia](history/README.md) |

Los controles de datos88+16subcasos, integración/tenencia76+45 y cierre UTF8/procedencia/plazos18+16 se solapan; no se suman como casos únicos. Las suites y los negativos originales quedan en sus índices. La geometría, integridad y mediciones deterministas se verifican por tests/replays; las capturas y canarios comprueban integración real, no eficacia predictiva. Los componentes heredados del full MRNA siguen fechados y no se convierten en mediciones nuevas. No se afirma optimalidad, rentabilidad ni ahorro general de llamadas.

## Estado y límites de operación

A1 preservó runtime salvo las imágenes. A2 habilitó explícitamente EVALUATION_ARCHIVE_ENABLED en raw y fijó RAW_BASE_URL canónico en slim; conservó el resto. Se añadió únicamente objectViewer al controller sobre el bucket de informes, tras reproducir403. El puente de autenticación GCloud existente fija cuenta/proyecto para CAS/intentos; lecturas y aliases CLI requieren identidad activa concordante. Tokens en memoria, sin claves nuevas; este mecanismo no toca el modelo. Sheet sigue siendo una proyección asíncrona: se probó con la imagen/cuenta real en memoria, sin escritura productiva. La publicación es coherente por ticker, no una transacción del universo entero.

Se conservan fallos previos de capacidad8 y75s. Límites actuales: conexión10s, página30s, adquisición180s/máximo16, proceso210s y backfill600s; prepare900s y relojes/modelos intactos. Un límite vuelve a fallar explícitamente, sin convertir cobertura parcial en un vacío reciente. La terminación cubre el caché disponible del proveedor, no todas las noticias del mercado.

El archivo técnico conserva observaciones ya descargadas, separado del contexto/modelo. Su cobertura parcial sigue explícita; no reconstruye historia descartada ni justifica nuevas señales. Las incógnitas metodológicas concretas permanecen en la matriz: series y expectativas ex ante insuficientes, pocos horizontes/fechas independientes, ausencia de etiquetas de materialidad y participantes humanos. No se cambiaron pesos ni ITV para mejorar resultados del corpus.

**Observación natural18-10 completada:**46/46,46medium,0repair/full/fallback/retry. [Auditoría con matriz29puntos](natural_run_20261018/README.md): replays46/46,276objetos remotos íntegros,lectores46/46 y70zonas; controller46versiones y mirrors exactos. Tras403de GCloud, lectura directa por conector existente:46filas/230valores financieros,notas Entry/Washout/Setup y46enlaces versionados exactos,sin permisos nuevos. No se validó predicción;118capturas repetidas para46tickers explican un coste operativo medido. La [optimización local posterior](news_capture_reuse_20261018/README.md) ya comparte capturas dentro de cada nueva orden, con125tests+125subcasos y replay118/118; la duración real posterior todavía no se ha observado. El estado nuevo de tesis full no fue ejercitado. No se lanzó un lote duplicado ni se recuperó APP histórico. El APK firmado está en releases/android/Growth-0.1.0.apk con SHA256736802a719a50fcb7f167653a55c6949577e403a646bdaa33ce5f7b1d9db43d4; instalación física pendiente de dispositivo accesible.

**Limpieza auxiliar A2 completada el18-10 a las08:25:41UTC:** después del rechazo inicial el usuario concedió permiso específico. Se retiraron tags raw/audit40, slim/audit40 y slim/active40 y se eliminó únicamente support-resistances-slim-source40-audit-20261018. Producción40 permanece Ready al100%, con runtime, endpoints canónicos, tag original raw/timeout60-test y rollback preservados. [Autorización, recibo y comprobación final](cleanup_authorized/README.md). A1 ya había retirado sus objetos/bucket/Job/revisiones sintéticos, con retención soft-delete7d del proveedor. La revisión raw activa se conserva aunque su nombre contenga audit.

## Revisión y reproducibilidad

Checkpoint previo8034b7afb20c5a3fbe151d36429fe608160b3c16; implementación posterior sin commit ni push. [Documentación aplicada](canonical_docs_receipt.json) y [manifiesto de snapshot56archivos](review_package_manifest.json). El snapshot está en .tmp/activation40_20261018/review_package40_activated_snapshot; su etiqueta prepared_not_deployed y switches apagados describen únicamente ese paquete de revisión, nunca el estado activo. Sus bases16-Oct requieren revalidación antes de cualquier nuevo despliegue. Consultar los recibos activos y no ejecutar un Dockerfile antiguo.

INDEX.json enumera los archivos durables por ruta/tamaño/SHA256, excepto sí mismo. Las subcarpetas conservan evidencia fechada; estados preparados antiguos no sustituyen este cierre. Se excluyen payloads completos, credenciales, valores privados de tenencia y capturas de cartera. Los originales locales de trabajo permanecen bajo .tmp/activation40_20261018 y los de la fase inicial no se reescribieron.
