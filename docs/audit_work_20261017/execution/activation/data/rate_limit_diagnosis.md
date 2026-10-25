# LEU v3: rechazo en admisión de Cloud Run

El 18-Oct a07:17:55.422566Z la revisión raw source40-audit devolvió429, responseSize14, latency0s. El log requests declara literalmente: "The request was aborted because there was no available instance." El mensaje de respuesta observado por slim fue "Rate exceeded."; slim devolvió502 después89.526s. No es evidencia de throttling Tradier: el rechazo identificado corresponde a Cloud Run antes de ejecutar esa solicitud raw. No se afirma un conteo de llamadas del proveedor por ausencia de logs.

La consulta read-only realizada07:21:20UTC devolvió10 entradas de raw/slim, ventana07:14→07:23 (solo lo disponible al consultar), con una petición slim y una raw, arranques y el error propagado. Raw comenzó nueva instancia07:17:59.824357 y startup TCP tuvo éxito07:18:04.991490. Esto es compatible con capacidad no disponible durante arranque; no demuestra por sí solo la causa interna exacta ni requiere cambiar capacidad. Servicio y revisión raw conservan maxScale1, concurrencia80, timeout120s; slim maxScale20.

Se comunicó a raíz/financial: preservar LEUv3; preparar nuevamente de forma serial y bajo las guardas existentes; no reutilizar captura fallida ni iniciar modelo. No se hicieron nuevas capturas durante diagnóstico ni se cambió maxScale. La activación posterior fue autorizada por raíz independientemente.

Evidencia: rate_limit_log_evidence.json y financial/canary_batch_v3/adaptive/LEU/activation_prepare_failure.json. Script reproducible read-only inspect_rate_limit.py.
