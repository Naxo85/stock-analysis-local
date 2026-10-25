# Correcciones de soporte — revisión41

Autorizadas por el usuario el19-10-2026: implementar los puntos2,3 y4 de la investigación, conservando el peso de Opciones. Esta ejecución no reabre el cambio de pesos ni el rediseño general de candidatos.

**Estado: implementado y activo.** RAW/SLIM41 al100%; política local41 activada19-10-2026 a las10:49:08UTC (12:49:08 Europe/Madrid). [Recibo de activación](activation/policy_activation.json). Único cambio de configuración: routing_revision40→41; SHA256 final10745943fc7b3e7043071b01d283ac68661dbe6a1c7409c76466e4760d4718c4.

## Cambios

1. **Observación dirigida de los orígenes activos.** Se extraen exclusivamente identidades tipadas de zonas Entry/Washout activas en CURRENT autenticado. El productor vuelve a observar suelo/gap sobre las mismas barras descargadas, independientemente de ranking y distancia. No se cambia5% ni el ganador de cada familia, TOP, adquisiciones o puntuaciones.
2. **Mejora material del conocimiento.** Full, mantenimiento y reparación41 pueden justificar `material_improvement` para el mismo soporte cuando una observación aplicable resuelve una limitación material anterior. Deben explicar premisa, novedad respecto a lo incorporado y consecuencia sobre cada componente afectado. No exige inventar apertura de contratos, cambio del mercado ni error pasado; tampoco concede puntos automáticamente o repetidamente.
3. **Significado de los componentes.** El contrato41 distingue estructura, reacción/volumen, opciones, confluencia independiente y durabilidad del soporte completo. Desconocido no equivale a deterioro; un vencimiento sólo compromete la supervivencia global si el respaldo depende de él. Las inferencias no identificadas sobre signo dealer no sirven como riesgo actual demostrado. Se revisa su fundamento dentro de la llamada ordinaria, sin repuntuar por cambiar instrucciones.

Opciones conserva25 puntos; rúbrica25+20+25+15+15, visibilidad65 y sólido70, modelos medium/high, ITV5, techo6, fuente de tenencia, publicación manifest-v1, archivo técnico y noticias por ejecución permanecen iguales. No se añaden schemas de salida, llamadas, reparaciones, rutas de escalado o validadores de prosa.

## Identidad, cobertura y límites

`support_origins` es una petición explícita nueva; `[]` permite identificar futuras formaciones sin solicitar antecedentes. Sin petición se conserva el payload legacy, salvo revisión de fuente. La respuesta llega en `levels.support_origins`, junto al shortlist habitual.

Los orígenes nuevos retienen fechas de formación y confirmación: un pivote k2 no está disponible antes de sus dos sesiones posteriores; un gap exige sesiones contiguas. La reconciliación legacy exige igualdad exacta y única de tipo, nivel redondeado del productor, fecha y toques cuando correspondan. No busca el vecino más cercano. Las identidades ricas sobreviven a un cambio del agrupamiento actual, pero nunca a una modificación no verificada de sus valores/fechas.

`available` identifica la formación, no su vigencia compradora. `not_observed` sólo describe el pool reconstruido; `unavailable` conserva ambigüedad, insuficiencia o historia incompatible. Ningún estado fuerza retención, retirada o nota. El catálogo vincula el objeto completo y las futuras revisiones conservan su identidad mediante `support_record`/fuentes de extensión. Una observación negativa no pasa por origen positivo ni por respaldo válido de una extensión inferior.

La revisión independiente encontró un borde adicional y se corrigió: si faltan sesiones de historia posteriores a una formación válida, ésta puede seguir `available`, mientras reacción histórica y estado `filled`/toques del gap quedan no disponibles. No se inventa una defensa o `filled=false` desde una secuencia incompleta.

## Verificación

- Las20 referencias tipadas históricas —19 identidades distintas— se reconstruyen; se recuperan las9 omisiones. CLS/WDC/LRCX y negativos de identidad, formación, ventana incompleta y sesión futura tienen pruebas específicas.
- Igualdad RAW y SLIM legacy frente a opt-in después de retirar únicamente los campos aditivos; mismas descargas y TOP. El ranking ordinario no se amplía ni sustituye.
- Admisión productor→SLIM→runner, catálogo/origen positivo, preparación41, reparación única, schemas iguales40/41, reutilización exacta de congelados40 y cobertura de `material_improvement` MP/NVDA/TSLA sin decidir sus notas.
- Replay de13 originales:8updates y5retains conservan finanzas en comparación40/41. El recibo40 es original; el41 es sintético en memoria para comprobar compatibilidad, no una llamada ni decisión nueva del modelo.
- [Alcance exacto](scope_verification.json):68 prompts anteriores byteidénticos;275 hashes de informes/referencias originales intactos.94 funciones RAW y20 SLIM sin cambios; la lista de funciones modificadas es explícita. La política sólo cambia su número de revisión al activarse.
- [Pruebas integrales](tests.xml): **304 pruebas y6 subcasos aprobados**,345,34s, sin fallos ni skips;47 avisos. El XML/recibo cuenta310 casos porque incluye los subcasos. Se corrigieron dos fixtures antiguos que confundían configuración activa con valores por defecto/versiones soportadas; no se debilitó la guarda del archivo técnico.
- [Revisión independiente](../overlap/implementation_review.md), con la corrección de sesiones ausentes y límites de la evidencia.

## Despliegue e integración real

Las dos imágenes se construyeron sobre los digests activos40 comprobados, con verificación offline dentro de cada imagen. Se desplegaron sin tráfico, se probaron sin símbolo y se activaron secuencialmente RAW→SLIM. Runtime, variables/secretos, URLs y tags anteriores se conservaron por hash; sólo cambió la imagen y se añadió el tag propio `origins41`. Las revisiones40 permanecen disponibles como rollback.

- RAW: `support-resistances-raw-origins41-20261019`,100%, [recibo](activation/raw-active.json).
- SLIM: `support-resistances-slim-origins41-20261019`,100%, [recibo](activation/slim-active.json).
- [Comprobación real](activation/live_verification.json): una captura técnica CLS,19Oct10:46:30UTC, observó el suelo exacto290,88 y pasó admisión de opciones, cotización, sesiones e identidad41. Puede refrescar el mirror técnico habitual; no publicó un informe financiero.

No se ejecutó un lote, canario de modelo, recuperación ni republicación. No se cambiaron las notas de los informes actuales. La corrección del juicio se aplicará en nuevas llamadas ordinarias; la calidad de esas decisiones y su efecto sobre soportes visibles deben observarse en el siguiente uso natural. Las pruebas de código/cobertura no validan alpha ni garantizan más zonas≥65.

Scripts: [despliegue](../../../scripts/deploy_support_origins_v41.py), [integración/activación](../../../scripts/activate_support_policy_v41.py), [verificación de alcance](verify_scope.py). La baseline comprimida y los recibos conservan el estado anterior y las imágenes para revisión, sin valores de secretos.
