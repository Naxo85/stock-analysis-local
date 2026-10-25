# Cobertura pública de noticias en mantenimiento · 23-10-2026

**REVERTIDO por orden expresa del usuario por coste potencial.** Se retiraron
opción de configuración, integración, prompt, prueba nueva y cambios de fixtures.
El mantenimiento vuelve al alcance de investigación anterior. No se ejecutó
un análisis con esta opción en esta tarea. La carencia CRDO sigue abierta;
no reactivar sin autorización. Lo siguiente documenta el cambio retirado y sus
comprobaciones históricas; sus archivos de implementación ya no están activos.

CRDO23Oct recibió siete titulares IBKR/DJ-N, todos de ventas de directivos o
resúmenes. El proveedor agotó su caché correctamente; eso no acredita cobertura
de todas las noticias públicas. Las dos operaciones web de Luna aclararon la
venta de Cheng. No evaluó MaxLinear/Edgewater; no fue un descarte financiero
documentado ni una omisión de presentación. La conferencia de MaxLinear22Oct
precedía al corte; no se confirmó la hora original del informe Edgewater.

Originales: `logs/batch/2026-10-23/14-18-22/adaptive/CRDO/`, con captura
14:37:45UTC, revisión14:47 y publicación14:49:51UTC. No se modifican.

## Cambio aplicado a nuevas preparaciones

`maintenance_news_discovery=public-material-v1` en la política local41 activa
una comprobación pública focalizada en la MISMA llamada de mantenimiento.
Prompt fuente: `prompts/maintenance_news_discovery_v1.md`. Comprueba novedades
desde el ancla full Sol, priorizando la última sesión y hechos no incorporados
en CURRENT, para poder encontrar omisiones anteriores. Incluye noticias de
competidores/clientes, comentarios de resultados y análisis de terceros con
relación demostrada, tanto favorables como adversos. No depende de un titular
IBKR, feed vacío, porcentaje de caída ni causa conocida de antemano.

La apertura restrictiva antigua del permiso web se sustituye sólo con esta
opción; las políticas congeladas sin ella conservan el prefijo exacto. El
descubrimiento se informa en los assessments existentes, con fechas, URLs y
límites; no inventa IDs de la agenda ni modifica titulares o técnicos congelados.
Un snippet no verifica un hecho; ambiciones de un rival no equivalen a contratos
ganados. Las fuentes inaccesibles y búsquedas sin resultado no prueban inocuidad.
Reparación reutiliza la investigación inicial salvo cuestiones concretas abiertas.

Mismos modelos/esfuerzos, ITV5, rúbrica, pesos, guardas, autoridad y publicación.
Hallazgos rutinarios pueden usar la nota pública existente; evidencia crítica,
corrección fundamental o incertidumbre esencial siguen a Sol. No hay cuota de
búsquedas, clasificador de prosa, nueva puerta de validación financiera,
reparación extra ni escalada automática. Se mantienen los plazos actuales.
Puede aumentar el trabajo web y el tiempo dentro de la misma llamada; no se
afirma coste constante ni cobertura exhaustiva. Full conserva su contrato.

## Verificación y límites

`scripts/verify_news_discovery_frozen.py` reconstruye exactamente los prefijos
de65recibos originales (46tickers, triage y reparación) y comprueba sus hashes
registrados. No llama modelos, descarga fuentes ni publica. Incluye CRDO.
Resultado guardado en [frozen_receipts.json](frozen_receipts.json).

Las pruebas offline comprueban opt-in, política inválida, integración en triage
y reparación, aislamiento de full, procedencia de fuentes, autoridad de edición
y escalado ya existente. Se actualizan dos fixtures históricos de noticias:
el recibo de caché incluye su hash exigido por integridad y el ensayo legacy
desactiva opciones modernas heredadas de la configuración viva. El fixture
compartido de revisión3 fija además publicación legacy y desactiva avisos remotos:
el primer pase ampliado había intentado autenticarse en GCloud antes de las
comprobaciones simuladas y falló; no se publicó ningún dato.

Resultado final: **53 tests y66subcasos aprobados** con:

```text
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_maintenance_news_discovery.py tests/test_adaptive_news_research.py tests/test_adaptive_maintenance_stage.py tests/test_volume_feedback.py tests/test_diff_transport_binding.py -q -p no:cacheprovider
```

La comprobación adicional de igualdad exacta del contrato full con/sin opción
también pasa (3tests/9subcasos del archivo nuevo). `git diff --check` sin errores.

Pendiente: observar cobertura, selección de noticias, tiempos/coste y límites de
acceso en el siguiente uso natural. Las pruebas de instrucciones/transporte no
demuestran que el modelo encuentre MaxLinear/Edgewater ni todas las novedades.
No se lanzó modelo/canario/lote, no se regeneró CRDO ni se publicó un informe.
