# Punto 4 — Descubrimiento y observación de orígenes

Investigación local del 19-10-2026 sobre los 46 contratos congelados del lote natural `2026-10-18/09-08-40`. No se han ejecutado modelos, nuevas adquisiciones, lotes, publicaciones ni cambios de producción. El replay y este informe son los únicos productos de esta investigación.

## Conclusión y prioridad

**Sí corregiría primero una carencia concreta de observación: los suelos y gaps citados por las zonas CURRENT activas deben volver a observarse independientemente del ranking y del filtro del 5%.** Es el mismo principio que ya se aplica a AVWAP y opciones dirigidas. Hay un caso, CLS, donde la información existe en la captura actual y su omisión interviene explícitamente en la comparación financiera.

**No activaría simplemente `5% → 0%` en los tres selectores.** Eso cambia 37 ganadores, sustituye 27 referencias existentes y ni siquiera garantiza recuperar todos los orígenes activos. La selección global de candidatos cercanos/diversos merece una segunda mejora acotada, con evaluación de cobertura útil y ruido. Este archivo no demuestra que esa alternativa produzca mejores compras ni cuántas casillas superarían 65.

## Qué hace realmente el productor

`gcp_functions/support_resistances_raw/main.py:65` fija 5% para rango, gap y AVWAP. Los selectores aplican esa distancia antes de elegir un único ganador: rango `3415`, gap `3469`, AVWAP `3530`. Rango exige al menos dos pivotes locales confirmados con dos barras posteriores; gap detecta una discontinuidad estricta entre máximo previo y mínimo posterior. AVWAP conserva una prioridad por ancla, no una lista exhaustiva de eventos.

La especificación de runtime guardada en `docs/audit_work_20261017/execution/activation/data/raw-active-redacted.json` declara únicamente TRADIER_TOKEN, GH_TOKEN y EVALUATION_ARCHIVE_ENABLED: no contiene overrides de estos parámetros. La reproducción exacta del resultado original confirma su comportamiento en el corpus. No se ha realizado una nueva consulta cloud.

El 5% ya existía en `incoming_from_gcp/support-resistances-raw/main.py` y en el checkpoint previo a40; no es un filtro recién introducido. Su efecto sí puede crecer durante una caída: una referencia antes situada a8% queda a3% cuando el precio se acerca y sale del listado precisamente al hacerse más alcanzable.

Los caminos alternativos importan. `observed_origins` recalcula AVWAP por fecha solicitada sin ranking (`raw:1724`). `technical_preparation.py:81` solicita fechas desde referencias autenticadas. Opciones CURRENT se observan por identidad tipada (`technical_preparation.py:137`). TOP puts, mínimo anual, medias, Donchian, Keltner y veinte barras recientes suministran otras coordenadas. No hay ceguera universal a soportes cercanos.

## Replay reproducible de las mismas capturas

Comando:

```text
.venv\Scripts\python.exe -X utf8 -B docs\audit_support_constraints_20261019\discovery\replay_discovery.py
```

El script carga exclusivamente catorce definiciones de funciones puras del productor mediante AST; evita su inicialización de clientes. Usa los archivos técnicos con símbolo y `snapshot_at` idénticos al `slim.as_of` de cada input, fija el reloj del ranking a ese instante y reproduce sus ventanas126/252, ATR y desempates. Conserva hashes de46inputs,46archivos técnicos y el código; verifica que no cambian durante la ejecución. Se excluyen expresamente las capturas del19Oct.

El `today_low` no está disponible en el input: se deja en null, lo que sólo cambia `testing_now`, no las coordenadas seleccionadas por estas tres funciones. Se comparan las coordenadas redondeadas como el productor, no la nota descriptiva.

| Medida | Resultado |
|---|---:|
| Correspondencia exacta de captura |46/46|
| Selecciones/nulos originales reproducidos |138/138|
| Candidatos de las tres familias con5% |61|
| Candidatos con0%, mismo ranking/capacidad por familia |71|
| Selecciones que cambian |37 en25tickers|
| Sustituciones / casillas de familia antes vacías |27 /10|
| Cambios por familia: rango / gap / AVWAP |16 /10 /11|
| Cambios cuyo nuevo nivel ya llegaba idéntico por otra vía |9|
| Otros nuevos niveles sin copia exacta en las vías comprobadas |28|
| Cambios con otra referencia a≤0,2ATR |33|
| Nuevos ganadores dentro de1ATR o1EM semanal |35|
| Tickers que ya recibían alguna referencia a<5% por cualquier vía comprobada |46/46|

Las9copias exactas son AVWAP ya observados. La proximidad de33/37 no convierte las referencias en equivalentes: una media, un gap y un suelo pueden aportar descripciones distintas, aunque compartan OHLCV y no merezcan puntos como familias independientes. Los28niveles adicionales son omisiones identificables del conjunto actual, no28compras aptas demostradas. Existen19clusters de al menos dos pivotes y54gaps en la banda0–5%; no se propone enviar ese pool entero al modelo.

En12tickers ATR10 es inferior al5%del precio, por lo que el filtro excluye por construcción esa escala próxima en las tres familias; el movimiento semanal puede ampliar el alcance financiero. Esto no demuestra que hubiera una buena zona en cada uno.

## Observación dirigida: una corrección más estrecha

Se revisaron únicamente registros tipados de rango/gap contenidos en `resolved_facts` o `support_validity.sources` de zonas CURRENT activas. Se encontraron20referencias asociadas a zonas, correspondientes a19identidades únicas: GEV cita el mismo origen en dos zonas. **Las20referencias se reconstruyen de forma exacta y única con los datos actuales;9no figuran en el shortlist actual**:

| Ticker | Origen vigente citado pero omitido |
|---|---|
| CLS | Suelo290,88, último pivote19Ago,2toques |
| HIMS | Suelo27,345,8Oct,4toques |
| INTC | Suelo85,62,1Sep,3toques |
| LRCX | Suelo251,89,29Jul,2toques |
| MRVL | Suelo221,68,24Ago,2toques; gap225,14,2Jun |
| SNDK | Gap1287,04,12Ago |
| TLN | Gap337,22,6Oct |
| WDC | Gap312,20,8Abr |

Son fuentes citadas para evaluar zonas, no una inferencia de que cada una sea el origen definitorio exclusivo. El inventario no extrae niveles de prosa.

LRCX demuestra que eliminar el5%no basta: el suelo activo251,89 se reconstruye, pero con0%el único ganador sería264,54 y seguiría faltando251,89. La continuidad necesita un canal que sobreviva tanto al filtro como al ranking.

## Casos y contraejemplos

**CLS: omisión que entra en el argumento de selección.** El antiguo Washout289,5–292 citaba el suelo290,88. La captura18Oct permite reconstruirlo con2pivotes,27Jul y19Ago, volumen medio1,805×la mediana. Está3,722%por debajo de302,125; antes estaba8,11%por debajo del precio de su registro autenticado. Por el5%se entrega en su lugar el suelo283,38. No hay otra coordenada actual a≤0,2ATR de290,88 en las vías comprobadas. `logs/batch/2026-10-18/09-08-40/adaptive/CLS/triage.json:111` compara favorablemente283–285 con el «antiguo suelo de290,88 sin origen actual observado». El suelo sí existe en los datos actuales descargados. Esto muestra una desventaja informativa concreta para el candidato anterior; no establece que deba conservarse ni que sus componentes superen65. La misma respuesta menciona otras razones financieras para escoger283–285 y retirar el antiguo principal312–314.

**WDC: omisión real, continuidad correctamente protegida.** El gap312,20 del8Abr sigue presente y abierto en el replay. A4,584%de327,20 queda omitido; su referencia anterior estaba8,89%debajo. Tiene0toques posteriores según el detector del gap, por lo que su disponibilidad no acredita defensa completada. No hay otra coordenada actual a≤0,2ATR. La respuesta original conserva311–313 y explica que su desaparición del listado no demuestra cierre ni pérdida (`WDC/triage.json:4`). La corrección de datos evita obligar al modelo a reconstruir esa distinción desde antecedentes, pero no debe elevar su fortaleza automáticamente.

**AMD: contraejemplo a una acusación general de ceguera.** Sin5%el AVWAP ganador pasa418,2098→508,2703, anclado6May. El segundo ya estaba disponible exactamente en `observed_origins` y corresponde al entorno de Washout506–509. Ampliar este shortlist por sí solo no aporta información nueva al juicio de AMD.

**HOOD/AUR: quitar el filtro tampoco garantiza calidad.** HOOD pasaría del gap79,28 al96,10, pero el segundo ya figura como `filled=true` y su última visita registrada es14Ago. AUR gana un gap4,70 de sólo0,02dólares de tamaño, antiguo y sin toques posteriores. Son hechos que permiten estudiar un soporte; no son prueba de viabilidad actual. No se propone convertir `filled` o pocos toques en veto automático: se propone conservar su significado y dejar el juicio financiero explícito.

**TLN: una formación reciente necesita fecha y muestra.** La variante0%elige gap337,22 del6Oct, con un único toque posterior, en lugar de320,07. Mayor proximidad no acredita superioridad ni defensa consolidada. Ese gap ya aparece entre las fuentes tipadas del Washout CURRENT, otro motivo para observarlo sin forzar que gane el ranking.

## Propuesta de implementación posterior

1. Añadir una observación tipada de orígenes de rango/gap citados por CURRENT activo, a partir de los datos que ya se descargan. Conservar shortlist ordinario; un origen observado no se declara viable por código. No hace falta modificar globalmente el5%para cerrar este defecto.
2. La identidad debe conservar tipo, fechas de formación/miembros, método y fecha de disponibilidad. Para gaps, fecha exacta y barras contiguas del evento; para clusters, fechas de pivotes y su confirmación. Slim hoy descarta `first_touch_date` y los clusters ni siquiera guardan todos los miembros: eso debe subsanarse para nuevas observaciones.
3. Compatibilidad legacy conservadora: un registro autenticado con tipo/fecha/nivel/toques puede recibir una observación cuando la reconstrucción actual coincide de manera única y exacta, como en los9casos. Una identidad ambigua, una ventana que ya no cubre su formación o un ajuste corporativo no verificado produce estado explícito con alcance; nunca se elige el vecino ni se reetiqueta el dato histórico como actual.
4. Transportar solicitud y respuesta en campos nuevos y catalogarlos con identidad/scope; preparar una nueva revisión para nuevas órdenes. Los prompts/schemas/inputs congelados<=40 permanecen exactos. Reutilizar adquisición; no nuevas llamadas al modelo ni descargas extra.
5. Después evaluar un inventario compacto de candidatos próximos/diversos. Conservar la observación dirigida aunque el inventario se trunque. Desduplicar misma identidad/familia y evitar desplazar automáticamente un bloque inferior útil por un candidato casi coincidente con la cotización.

## Aceptación mínima

- Replay46/46 con las mismas capturas: recuperar9observaciones omitidas, conservar los ganadores originales y mostrar ausencia/ambigüedad real con alcance. CLS y WDC deben recibir su origen sin repuntuar ni cambiar el informe por código; LRCX251,89 debe llegar aunque264,54 gane el ranking alternativo.
- Negativos de identidad: fecha equivocada, fuente sin autenticación, cluster ambiguo/reagrupado, historia incompleta, barra futura, ajuste corporativo, orden de arrays distinto y duplicación entre slots. Un precio parecido no es una identidad.
- Sin fuga temporal: un pivote con2barras posteriores sólo está disponible tras la segunda; la formación de un gap no crea una reacción histórica ya confirmada; métodos de reacción y camino adverso conservan su alcance descriptivo.
- No interpretar `available` como viabilidad, no subir puntos por reencontrar un origen, no duplicar confluencia entre copias ni forzar Entry/Washout. Precio acercándose al soporte no puede borrar su observación.
- Para la mejora global posterior: presupuesto/contexto acotado, cobertura de orígenes defendibles y rechazos revisados ex ante, igualdad de distancia/escala cuando se comparen resultados, conservación de bloques inferiores útiles y abstención. No optimizar parámetros por el número de casillas visibles.

## Relación con M02 y límites

M02 ya detectó el5%y evaluó un inventario alternativo; su control de distancia sólo pudo emparejar1de47candidatos sustituidos. Sus19/45contactos no demuestran calidad y este replay tampoco. La evidencia nueva resuelve una cuestión distinta: con la historia completa capturada para cada input se puede atribuir de forma exacta una omisión de origen al filtro/ranking y mostrar su uso en CLS. Eso justifica una corrección de observación, sin afirmar ventaja predictiva de otro ranking.

34/46archivos tienen ventana252completa;12marcan una barra antigua inválida o historia corta en SPCX. Se preservaron filas originales para reproducir fielmente lo que calculó producción y quedaron sus flags en el resultado.27de37cambios proceden de tickers con ventana completa; CLS, WDC, AMD, AUR, HOOD y TLN pertenecen a ese conjunto. No se usan esosflags para inferir que todos los informes estén mal ni se corrigen originales. No se consultaron precios posteriores a los contratos ni se midieron retornos, ejecuciones, costes o alpha.

Resultado íntegro y hashes: `discovery_replay.json`. Implementación reproducible: `replay_discovery.py`.
