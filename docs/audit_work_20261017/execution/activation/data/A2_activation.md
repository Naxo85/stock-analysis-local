# A2 — fuentes40 activadas y verificadas

18-Oct-2026: raíz autorizó la activación tras A1 consumidores100%. Raw support-resistances-raw-source40-audit-20261018 quedó100% a07:23:01UTC; slim support-resistances-slim-source40-active-20261018 a07:23:55UTC. Ambos utilizan los mismos digests verificados en staging. Slim nuevo apunta explícitamente al raw canónico; audit40 y timeout60-test previos permanecen.

Se verificaron identidad de revisión, runtime, cuentas, recursos, referencias de secretos, timeout120s, concurrencia80, anotaciones y tags. MaxScale sigue raw1/slim20. No se cambió configuración local por este agente. No modelos, informes financieros, cartera ni recuperación histórica. El flujo de captura conserva su efecto normal en espejos técnicos.

## Verificación canónica

Tras coordinar ventana exclusiva con financial, una sola captura APP por https://support-resistances-slim-714254943648.europe-southwest1.run.app respondió200 en7.437s, sin redirects, as_of2026-10-18T07:24:13.152084Z. No hubo captura raw adicional. Las comprobaciones de contrato40, quote, historia20, orígenes put250/255 y archivo pasaron. Quote conserva fecha16-Oct23:55UTC y antigüedad113353s: última sesión del domingo, no cotización ejecutable al segundo.

APP conserva275 filas y252 sesiones esperadas completas. Opciones:7 respuestas cacheadas,6 expiraciones descargadas,790 contratos; muestreo completo en su alcance, market_complete=false, OI effective_at desconocido. SPY adicional queda parcial: close<low en18-Dec2025 y17-Jun2026, exactamente preservados; no se inventan ajustes. Archivo extraído fuera del contexto del modelo y auxiliares retirados ausentes. Esto prueba integración, no validez financiera ni poder predictivo.

Recibo nuevo canonical_capture/verified_sources.json, status verified_active, verified_at07:24:26.210527Z; evidencia SHA2565fd1e4393dddf60633ace151a0c0434c933642e07effcd457a183090d541696f. El recibo staging original permanece intacto. Runtime/tráfico antes/después y hashes en activation_results.json.

## Comandos y rollback

Se ejecutaron activate_sources.py preflight, activate-raw --execute, stage-canonical-slim --execute, activate-slim --execute y capture_active_sources.py, usando .venv\Scripts\python.exe -B desde el repositorio y gcloud.cmd con acceso elevado acotado a la configuración GCloud. El manifiesto conserva los argumentos exactos y los hashes previos. Seis tests offline más seis subtests verificaron drift, tags/runtime y rechazo de redirects antes de la activación.

Rollback preparado: activate_sources.py rollback --execute. Requiere coordinación de raíz para pausar nuevas preparaciones40 y restaurar política local; mueve tráfico primero slim39 y después raw39, mantiene tags y evidencia. No se ha ejecutado rollback. El template del servicio conserva última40 aunque un rollback sirva la revisión39 inmutable.

## Configuración local pendiente de raíz

La candidata40 cambia routing_revision a40, publication_protocol a manifest-v1, latest_attempt_publication_enabled y technical_archive_enabled atrue, y publication_auth a CLI con cuenta validada/proyecto existente. Production_enabled ya era true. Se mantienen modelos/efforts, ITV5, investigación, límites, timeouts, concurrencia y extra_market_closures. El runner ya usa la URL slim canónica numérica; no requiere cambiar código/URL. Activación de estos flags y A3 es propiedad de raíz.

## Incidencia de preparación LEUv3

Cloud Logging demostró429 de admisión raw por falta de instancia disponible, propagado como502 por slim; no prueba throttling de Tradier. Original conservado, ningún modelo usó esa captura. Véanse rate_limit_diagnosis.md y rate_limit_log_evidence.json. No se cambió capacidad para el incidente.
