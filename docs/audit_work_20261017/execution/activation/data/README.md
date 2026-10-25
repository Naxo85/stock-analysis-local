# A2 — fuentes y noticias verificadas

Estado observado el 18-Oct-2026 a las 08:10 UTC: raw40 y slim40 canónicos sirven el 100% del tráfico. Sus especificaciones siguen exactamente iguales a las verificadas en la captura canónica de APP; runtime, referencias de secretos y rollback39 se conservaron. La política local pertenece a raíz y su activación se documenta por separado.

- Raw: support-resistances-raw-source40-audit-20261018.
- Slim: support-resistances-slim-source40-active-20261018; upstream raw canónico.
- Captura APP: contrato40, historia reciente de 20 sesiones completas y archivo de 252 sesiones verificado. El benchmark adicional conserva cobertura parcial y sus anomalías originales.
- IBKR final: adquisición máxima 180 s, 30 s por respuesta, 16 páginas y máximo300 filas por página; proceso de noticias 210 s; backfill 600 s para el reintento ya existente. Prepare 900 s y relojes de modelo permanecen iguales.
- NVDA nuevo: 14 peticiones, evento terminal recibido y hasMore=False, 4.065 identidades únicas, 19 duplicados y95 noticias en la ventana.115.797 s de adquisición y116.500 s del proceso. Cero latest, modelos, órdenes y publicaciones financieras.
- Regresión final: 88 pruebas y16 subcasos pasan sin red. Los fallos previos con 8 páginas y con 75 s permanecen conservados; no se presentan como éxitos ni se eliminan.

La semántica temporal observada del proveedor difiere del rango documentado; el adaptador recorre hacia atrás y exige el final real del caché antes del filtro local. No declara cobertura mundial de noticias, ni interpreta cruzar la fecha inferior como cobertura completa. La fecha ingenua del proveedor conserva la interpretación UTC previa; esta prueba no establece una garantía de zona horaria o latencia universal. Véase IBKR_pagination.md para fuentes primarias, controles, empates y límites.

## Auxiliares retirados tras autorización específica

El rechazo automático inicial quedó respetado. El usuario autorizó después el borrado y el18-10 a las08:25:41UTC se retiraron raw/audit40, slim/audit40 y slim/active40 y se eliminó únicamente la revisión support-resistances-slim-source40-audit-20261018 sin tráfico. Se verificaron las dos revisiones productivas Ready al100%, runtime y endpoints canónicos intactos, rollback39 disponible y tag original raw/timeout60-test conservado. La revisión raw activa no se borró.

[Autorización, recibo y verificación final](../cleanup_authorized/README.md). A2_final_state.json, cleanup_not_executed.json y final_remote_readonly.json conservan el estado histórico anterior; no describen el estado posterior a esta limpieza. No se reescribieron sus datos.

## Evidencia y conservación

manifest.json enumera copias exactas por lista explícita con SHA256. Contienen metadata, recibos, resultados y logs redactados. Se excluyen corpus completos de noticias, cuerpos raw/slim, sidecars/cadenas, credenciales, entradas de modelos e informes financieros. Los originales permanecen en .tmp/activation40_20261018/data. validation_metadata.json es una proyección declarada del resultado original, cuyo hash conserva.

Las notas y recibos históricos conservan su fecha: los estados previos prepared o tags_preserved no sustituyen el estado final. Las pruebas ejecutables vigentes están en tests/test_ibkr_news_pagination.py y tests/test_ibkr_source_deadlines.py; el comando completo y los resultados están en pagination_deadline_applied_tests.json/.txt. Los canarios financieros originales no se reescribieron ni repitieron por estos ajustes de capacidad.
