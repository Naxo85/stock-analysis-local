# Auditoría del primer lote natural de la revisión 40 — 18 de octubre de 2026

## Dictamen

La orden **20261018-090400-731-market-a8dba136** terminó correctamente: **46/46**, con **25 mantenimientos conservados, 21 actualizados y 0 full**. Se usaron 46 llamadas a **gpt-6.1-sol medium mediante el mismo Codex local**, sin reparación, fallback ni reintento de lote. Los cambios tienen efectos operativos y semánticos observables. Esto no acredita una mejora predictiva ni significa que todas las ramas nuevas se hayan ejercitado.

Existe un coste operativo importante: el lote duró **51 min 52,6 s**, frente a **21 min 23,7 s** el 16 de octubre. La cobertura de noticias corregida descarga repetidamente la misma caché para distintas tareas. La auditoría identifica y mide esta duplicación; no la oculta detrás del 46/46 ni cambia la política de cobertura para acortar tiempos.

Esta revisión lee los artefactos originales, reproduce controles locales y contrasta publicaciones mediante consultas de solo lectura. No lanza modelos, lotes, recuperaciones, despliegues ni nuevas publicaciones. Los informes históricos permanecen intactos. Las verificaciones de fuentes públicas realizadas ahora se distinguen de la evidencia que conservó el modelo.

## Resultado y comparación

| Medida | 16 de octubre, revisión 38 | 18 de octubre, revisión 40 |
|---|---:|---:|
| Publicados / solicitados |45/46|46/46|
| Retain / update / full |18 /26 /1|25 /21 /0|
| Llamadas de modelo |55|46|
| Reparaciones |8|0|
| Reintentos de lote |1|0|
| Fallback de modelo/proveedor |0|0|
| Duración del lote |21:23,7|51:52,6|
| Duración del proceso de fuentes |16:45,9|48:49,6|
| Mediana de fase analyze por intento |105,6 s|76,45 s|
| Mediana de publicación por intento |50,5 s|68,35 s|
| Tokens de entrada, total medido |12.606.305|7.805.640|
| Tokens de salida, total medido |177.321|113.502|

La orden nueva corrió de 09:04:48 a las 10:00:48 UTC (**11:04:48–12:00:48 Madrid**): 56 min incluyendo resolución previa y cierre. El directorio de lote empieza a las 09:08:40 UTC. La diferencia temporal no es una espera del modelo por cuota: el techo siguió en 6, el máximo observado fue 4 llamadas solapadas y la espera de admisión acumuló 0,282 s, sin avisos de capacidad.

Hubo **20 operaciones web en 7 tickers**, dentro de Codex; 0 uso de ChatGPT Web como proveedor no significa 0 búsquedas. Las 46 sesiones comenzaron con historia limpiada; 43 reutilizaron una sesión y 3 estrenaron sesión, sin warning. ITV: 43 valores con 2 sesiones de edad, 2 con 1 y 1 con 0; ningún vencimiento de ITV exigió full.

La comparación entre fechas no es un experimento controlado. Hubo otra sesión completada, expiraciones de opciones y diferentes noticias. No se atribuyen las 9 llamadas menos íntegramente a un cambio. Tampoco se presenta la caída de tokens totales como ahorro monetario: entre las 46 llamadas triage de cada lote, la entrada no cacheada pasó de 3.819.171 a 4.291.528 tokens. El uso medido y el tiempo real se conservan separados.

## Efectos comprobados

- **Bloqueo GCS:** el lote posterior arrancó y terminó sin reincidir en gcs_read_lock_timeout. La reproducción anterior demostró reutilización de PID y la corrección de identidad de instancia. Este lote confirma funcionamiento normal posterior; no demuestra una nueva recuperación espontánea del mismo tipo de lock. El fallo08:29 permanece como antecedente.
- **Datos:**46/46 inputs recibieron contrato40 y superan de nuevo la admisión offline. Cada uno contiene20 sesiones cerradas hasta16 Oct; 0 barras inválidas en la ventana de 20 sesiones. Las quotes tienen fecha y estado disponible. No había sesión intradía abierta en este lote dominical: ese control negativo se sostiene en las pruebas anteriores.
- **Opciones y archivo:**180 registros dirigidos por vencimiento (60 identidades strike/tipo) conservan OI coherente; 0 auxiliares retirados reaparecen. Siete identidades fuera del TOP se observan positivamente en 6 tickers; APP 250/255 en esta captura sí pertenecen al TOP, por lo que no se atribuye a APP ese caso natural. Los 46 archivos técnicos pasan sus hashes/cobertura y no entraron al contexto del modelo. Su volumen es54.824.820 bytes;34 tienen ventana anual completa y12 declaran historia corta/barras inválidas. Ninguno de los 180 registros dirigidos ejercita OIpositivo con gamma ausente; no se atribuye ese negativo a esta corrida.
- **Medición de trayectoria:** los 503 objetos se reproducen exactamente desde el archivo y la limpieza real de slim. También se verifican volumen de última sesión, ratio y unidades de straddle46/46.503 objetos describen adversidad, cierre y fechas manteniendo desconocido el orden intradía.45 tickers tienen al menos un caso de excursión favorable con cierre final adverso. No son503 ensayos independientes ni retornos ejecutados.
- **Corrección de explicaciones:**9 updates con rango modificado y plan_explanation=null ya no activan el certificado redundante. El replay de esa guarda aislada devuelve error plan_coherence bajo la rama antigua y ninguno bajo40. No se ejecutó un análisis39 completo ni se demuestra que cada caso hubiera comprado una reparación.
- **Continuidad:**46/46 anclas y last_full exactos. Los 25 retain conservan fecha financiera, decisión, catalizadores y evento. ASML, PLTR yTLN sí revisan la extensión inferior Entry, conforme al contrato36/37:1610→1590,184,5→182 y349,15→348. Sus rangos y puntuaciones permanecen exactos. Por tanto,25 retain no significa25 documentos idénticos.
- **Cambios financieros reales:**10 tickers cambian algún rango,4 cambian Setup y ninguno cambia la nota de tesis. Las zonas activas pasan de 72 a70. Cinco promociones de Washout conservan exactamente sus cinco componentes, sin repuntuar para visibilidad. Diez motivos internos de Setup corrigen atribuciones dealer no identificadas; seis updates se concentran en esa corrección y cuatro la combinan con cambios de plan. Detalle, razonamiento y contraejemplos en financial/financial_audit.md.

El replay financiero reproduce46/46 decisiones y su render sin discrepancias: binding, cobertura y geometría en todos; mantenimiento y validación en los 21 updates. Las guardas automáticas se complementan con revisión semántica de los cambios; no sustituyen su mérito financiero.

## Publicación y consumidores

Se confirmaron **46/46 commits contra GCS**:276 objetos inmutables con hash correcto, manifest actual e histórico e intento succeeded exactos. Las respuestas JSON web/móvil y los enlaces versionados coinciden46/46; se verifican los bytes MD/HTML almacenados, no una inspección visual de 46 páginas. Los 46 espejos de Sheet y2 resúmenes remotos coinciden exactamente.

El controller registró sincronización a las10:00:47UTC con las46versiones nuevas. El dashboard devuelve70zonas con rangos, puntuaciones, fechas y versiones exactas, sin warnings ni stale.

La primera lectura directa a Google Sheets con GCloud devolvió403 PERMISSION_DENIED. Se conservó ese resultado y se utilizó el conector Google Drive ya disponible, sin cambiar permisos: **46/46 filas y230valores financieros exactos** (Entry, Washout, Res vacía, Tesis y Setup), notas de Entry/Washout/Setup exactas y46enlaces de Tesis fijados a las versiones comprometidas. Se leyeron322celdas en total, incluyendo92de ticker/precio para identificar filas y contexto. No se afirma haber revisado todas las celdas del libro ni colores/bordes, notas de delta de tesis o un teléfono físico. La lectura independiente queda comprobada por esta segunda vía; el403inicial no permanece como bloqueo.

## Coste detectado: capturas repetidas de noticias

Las 118 capturas se distribuyen en 46 de noticias generales,46 de analistas y26 backfills desde el ancla. Todas terminaron con EOF recibido y hasMore=False; no hubo timeout ni retry de fuentes. Acumulan341 páginas;239 son enteramente anteriores a la ventana pedida y consumieron1.652,875 s de adquisición sumada. Esas páginas certifican final de la caché; no son noticias nuevas útiles para esa ventana.

Los datos brutos descargados dos o tres veces para cada ticker tienen **el mismo fingerprint de identidad, texto y hora en los 46**. NVDA ilustra el extremo: tres capturas de 14 páginas y4.065 identidades cada una,337,156 s de adquisición agregada. La serialización del pipeline convierte buena parte de ese trabajo en latencia del lote; los backfills de prepare se solapan, por lo que sus tiempos no se suman directamente a la duración de pared.

El proceso de fuentes emplea1.567,9 s en noticias,1.055,59 s en analistas y306,127 s en otras tareas. Los 26 backfills suman470,465 s adicionales en sus procesos, parcialmente concurrentes. Es una ineficiencia de integración: certificar cobertura completa es correcto, pero reutilizar dentro de la misma preparación una captura autenticada suficientemente amplia evitaría descargar de nuevo el mismo contenido.

El replay local reconstruye exactamente los 118 conjuntos de titulares filtrados a partir de la primera captura de cada ticker, incluidos identidad, texto, hora y orden. En este archivo,46 capturas habrían necesitado134 páginas: hay 207 páginas repetidas y1.455,060 s de adquisición duplicada observada. La comparación cubre la materia prima y sus vistas temporales; no verifica todavía equivalencia del parser de analistas, consenso ni eventos downstream. Es una demostración de equivalencia sobre este corpus, no una promesa de reducir el lote en 24 min: hay solapamientos y en otra sesión las fuentes pueden cambiar.

La alternativa concreta es una captura por ticker/proveedor con cobertura suficiente para news, analistas y ancla, enlazada por hash/fecha a sus vistas filtradas. Debe conservar terminal real, errores, identidad, orden, procedencia y frescura; no se propone volver a detenerse sin EOF ni reutilizar indefinidamente una caché vieja. La igualdad observada el domingo no garantiza igualdad de capturas separadas en un día con noticias. El replay local de derivación se documenta en data/README.md; no es una implementación ni un benchmark de latencia desplegada.

## Límites y observaciones residuales

1. No hubo full ni repair; la nueva geometría full y el nuevo estado de tesis no se ejercitaron naturalmente. Los 46 informes carecen de un estado nuevo de tesis, de forma compatible con herencia exacta. El canario full anterior prueba integración de ese camino, no calidad general.
2. No hubo fallos de ticker, carreras CAS, publicaciones envejecidas o mutaciones de recibos. No se convierte un camino exitoso en validación natural de esos negativos ya ensayados.
3. MU conserva una explicación de ausencia fechada15 Oct menos representativa de su razonamiento actual: el modelo considera un gap marginalmente alcanzable y lo descarta por adversidad/escasa mejora, mientras el texto heredado lo sitúa fuera del horizonte ordinario. La fecha es fiel y no se demuestra una selección errónea; queda una limitación editorial. No se reescribe el informe durante esta auditoría.
4. La evidencia del modelo conserva operaciones y snippets, pero no todos los cuerpos web. Una comprobación retrospectiva de las URLs citadas confirmó las 3 novedades examinadas deCIFR/IONQ/QBTS, con documentos anteriores al run. Esto confirma sus afirmaciones con las fuentes consultadas ahora; no demuestra qué cuerpo exacto vio entonces el modelo. No se modificaron inputs ni se rellenaron retrospectivamente los recibos. 
5. Las propuestas de ranking, pesos, contexto sectorial homogéneo, expectativas, comprensión y cadencia siguen con las carencias concretas ya documentadas. Este lote no proporciona un holdout ni desenlaces posteriores suficientes. No se afirma rentabilidad mejorada.
6. APP tuvo éxito en una preparación nueva. Su intento fallido del16 Oct no se recupera ni cambia retroactivamente.

## Matriz de observación de los 29 puntos

Esta tabla añade observación del lote a la matriz de ejecución; no sustituye antecedentes, tests ni decisiones de adopción. «No ejercitado» no equivale a «sin implementar».

| ID | Resultado en este lote | Evidencia | Límite |
|---|---|---|---|
| H01 | Observado | 118 capturas con EOF recibido y hasMore=False; 0 timeouts/retries de fuentes. | La cobertura es de la caché del proveedor. La descarga repetida encarece la garantía. |
| H02 | Observado parcialmente | 46 inputs con20 sesiones completas hasta16Oct;0barras inválidas admitidas. | Domingo: no ejercita una nueva barra intradía abierta; ese negativo procede de los tests previos. |
| H03 | Observado | 46 respuestas/recibos/bundles enlazados y bytes verificados. | No ocurrió una mutación adversarial en producción; su rechazo se probó aparte. |
| H04 | Camino normal observado | 46 snapshots frescos comprometidos con las guardas activas. | No hubo resume envejecido ni ack perdido natural. |
| H05 | Sin full natural | No se generó ningún informe full40; mantenimiento conserva geometría válida. | La nueva guarda full se sostiene en canario y controles previos, no en este lote. |
| H06 | Continuidad observada; rama específica no demostrada | TLN conserva Volumen13 y su rango. | Retain no demuestra por sí mismo la nueva rama de herencia en change_review de un update. |
| H07 | Fuente40 observada | Unidades de straddle verificadas contra el archivo46/46; fuente40 en todos los inputs. | No afirmar que el lote contiene todos los valores frontera ensayados localmente. |
| H08 | Observado parcialmente | 180registros por vencimiento,60identidades strike/tipo,con OI coherente;7identidades fueraTOP en6tickers. | Ninguna observación dirigida con OI positivo y gamma ausente: falta ese caso natural. |
| H09 | Observado | 0 auxiliares retirados detectados en los46 inputs. | Retirarlos evita la inferencia defectuosa; no prueba mejor predicción. |
| H10a | Observado | 46/46 admisiones locales reproducidas; historia corriente completa y fechada. | 12 archivos anuales parciales se declaran como tales y permanecen fuera del contexto. |
| H10b | Camino válido observado | 46 quotes admitidas con estado disponible y fecha. | Los rechazos de quotes inválidas se verificaron previamente; no inventar nuevos rechazos naturales. |
| H11 | Observado | 46 commits remotos,276objetos/hash y JSONweb/móvil/versionado coincidentes. Sheet directo:46filas,230valores y46enlaces exactos. | Sin carreras/fallos parciales naturales. Lectura acotada de celdas;no inspección visual de colores/bordes. |
| H12 | Éxito natural observado | 46 intentos succeeded separados del informe válido. | No hubo fallo de ticker en este lote; fallo sin informe probado en puesta en servicio. APP16Oct sigue fallido. |
| H13a | Maintenance observado | 46 preparaciones/recibos40 medium con instrucciones congeladas. | Full/high y repair no se ejercitaron en este lote. |
| H13b | Efecto específico demostrado localmente | 0 repairs naturales;9 cambios de rango con explicación null ya no activan la guarda redundante. | Replay de una guarda, no9 llamadas ahorradas demostradas ni comparación causal entre fechas. |
| H14a | Inconcluso | No hay desenlaces futuros del lote para validar utilidad predictiva. | Una ejecución sin errores no demuestra rentabilidad ni calibración. |
| H14b | No ejercitado | 0 full;0 estados de tesis nuevos. | Se hereda el estado disponible; no confundir ausencia con tesis sana. |
| H15 | Observado | Política40, mismo Codex local/modelo medium,0 fallback; originales conservados. | Checkpoint previo y puesta en servicio siguen siendo evidencia independiente. |
| H16 | Procedencia de lote observada | 46 tenencias proceden del universo Mercado con autoridad explícita, sin fallback. | No ejercita la ruta individual/manual corregida ni modifica cartera. |
| H17 | Sin reincidencia | La orden posterior terminó46/46; no quedó lock residual. | La reutilización de PID se reprodujo antes/después aparte; aquí no volvió a ocurrir. |
| M01 | Corrección semántica observada | Diez motivos internos Setup corrigen inferencias dealer;seis updates se concentran en ello. Auxiliares retirados ausentes. | Sin sustituto predictivo validado. |
| M02 | Archivo observado; ranking no adoptado | 46 archivos de observaciones conservados fuera del modelo. | No se alteró ranking ni filtro; faltan muestras temporales comparables. |
| M03 | Medición observada | 503/503 trayectorias reproducidas;45tickers con algún caso de excursión favorable/cierre adverso. | Son descriptores; orden intradía desconocido y ausencia de validación de decisiones. |
| M04 | Conservado | Sin cambio de pesos ni umbrales; cinco promociones mantienen componentes anteriores. | El lote no determina pesos óptimos ni independencia de componentes. |
| M05 | Archivo observado; contexto homogéneo inconcluso | Se conserva el archivo de benchmarks descargados. | No se incorporó un nuevo filtro sectorial ni se completaron series ausentes. |
| M06 | Parcial | Tres novedades CIFR/IONQ/QBTS comprobadas ahora en URLs citadas, anteriores al run; tesis full no ejercitada. | No existen expectativas point-in-time nuevas para validar sorpresa. |
| M07 | Fidelidad observada con límite editorial | Fechas de razones heredadas preservadas; tres extensiones revisadas separadamente. | MU conserva una razón antigua fechada menos representativa del razonamiento actual; comprensión humana no evaluada. |
| M08 | Política conservada | 46 medium,ITV sin reset,0 full;0,282s de espera de capacidad y techo6 intacto. | Menos llamadas en otra fecha no demuestra cadencia óptima ni ahorro monetario. |
| C01 | Archivo observado; señales no adoptadas | 46 cadenas archivadas con cobertura/hashes. | No se infiere flujo/dealer ni probabilidad calibrada; intradía/skew siguen sin evidencia suficiente. |

## Evidencia y reproducción

Revisiones independientes: [datos y rendimiento](data/README.md), [finanzas y decisiones](financial/financial_audit.md), [integridad y consumidores](integrity/README.md).

- metrics.py/metrics.json: comparación reproducible de los dos lotes y recibos; runtime_summary.json y triage_comparison.json separan sesiones, capacidad y triage.
- data/: censo46, capturas118, archivos y replay de admisión/medidas. Sus scripts sólo leen corpus local.
- financial/: censo de cambios, revisión semántica y replays de contrato/certificado redundante.
- integrity/: hashes/commits, lecturas remotas y consumidores; el script remoto requiere autenticación vigente y sólo lee.
- resolution_matrix.json e INDEX.sha256.json: observación por punto e integridad de esta evidencia.

Los originales están bajo logs/batch/2026-10-18/09-08-40 y los paths registrados en los manifiestos. No se copian todos los 54,8MB del archivo a documentación. Las lecturas remotas prueban el estado a la hora registrada; un script offline no sustituye esa comprobación. El directorio de evidencia no contiene credenciales ni autoriza nuevos análisis.
