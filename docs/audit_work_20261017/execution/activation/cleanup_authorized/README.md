# Limpieza A2 autorizada — 18-10-2026

Tras el rechazo inicial, el usuario autorizó expresamente borrar los auxiliares pendientes. La limpieza terminó a las08:25:41UTC; la comprobación posterior confirmó su ausencia y producción conservada.

- Retirados únicamente los tags raw/audit40, slim/audit40 y slim/active40.
- Eliminada únicamente la revisión support-resistances-slim-source40-audit-20261018, sin tráfico canónico.
- Conservadas las revisiones raw-source40-audit y slim-source40-active al100%, Ready, con las mismas imágenes y runtime. Raw mantiene su tag original timeout60-test; las revisiones39 de respaldo siguen Ready con las imágenes verificadas.
- Slim sigue usando la URL raw canónica; ambas URLs canónicas devuelven el400 esperado al omitir símbolo, sin consultas a proveedores, modelos, informes ni operaciones de cartera.

La primera comprobación HTTP de raw agotó40s y quedó registrada en verification_first_attempt.json. La segunda comprobación de lectura pasó; no se repitió ninguna mutación ni se atribuye una causa no demostrada al timeout.

Evidencia: authorization.json, cleanup_results.json y verification.json. docs_receipt.json liga por hashes la actualización del relevo, matriz y operaciones. Los registros históricos cleanup_not_executed.json y A2_final_state.json se preservan: describen el estado anterior a esta autorización.

Script ejecutado: .tmp/activation40_20261018/data/cleanup_source_staging.py --execute, después de preflight de lectura y revisión independiente del alcance. Verificador: .tmp/activation40_20261018/cleanup_authorized/verify_cleanup.py. No borrar la revisión raw activa por contener audit en el nombre.
