# Motor Codex adaptativo: contrato vigente

Estado documental: 19-10-2026. La revisión41 está activa para nuevas preparaciones, con fuentes raw/slim41 al100% en sus URLs habituales y el mismo Codex local/modelos configurados. El usuario autorizó las correcciones de continuidad, significado de los componentes y observación dirigida, y confirmó mantener Opciones25. La activación41 incluye verificación técnica real,304 pruebas y6 subcasos, sin llamadas de modelo ni publicaciones financieras. El juicio financiero41 y su efecto sobre las zonas visibles quedan pendientes del siguiente uso natural autorizado; no se fuerza un lote para medirlos. Los canarios LEU/MRNA40 y su revisión financiera independiente se conservan como evidencia histórica40.

**Activación global comprobada:**

Revisión41 activada el19-10-2026 a las10:49:08.390846 UTC (12:49:08.390846 Europe/Madrid). Configuración SHA256 `10745943fc7b3e7043071b01d283ac68661dbe6a1c7409c76466e4760d4718c4`. RAW/SLIM `origins41-20261019` sirven el100% del tráfico; runtime, variables/secretos y URLs previos se conservan. La política local sólo cambia su número de revisión. Permanecen modelos medium/high, ITV5, techo6, rúbrica25+20+25+15+15, visibilidad65/sólido70, publicación manifest-v1, último intento y archivo técnico. Congelados<=40 mantienen exactamente instrucciones, schemas, recibos y autoridad. [Implementación, pruebas y recibos de activación41](audit_support_constraints_20261019/implementation/README.md).

Antecedente40: activado para nuevas preparaciones el18-10-2026 a las08:17:18 UTC (10:17:18 Europe/Madrid), con lectura de comprobación y sustitución atómica. Publicación manifest-v1, último intento y archivo técnico habilitados; fuentes y tres consumidores compatibles al100%. Configuración histórica SHA25664e54ed9d2e40a47a86538b5af82747ca9f573c00fba0784ee7ca2a28d6ec53e. Mismo Codex local, modelos medium/high, ITV5 y techo6; congelados<=39 intactos en aquella activación.

El full MRNA usó una nueva preparación canónica40 con noticias completas de tres páginas y propiedad registrada desde Mercado. Los intentos anteriores fallidos se conservan y no se cuentan como análisis completados. La comprobación previa a la activación incluyó la capacidad/tiempo de adquisición de noticias de NVDA: el control fresco con16 páginas máximas agotó75s y no admitió un payload. Se aplicó después un ajuste acotado a180s de colección,210s de proceso y600s de backfill, y la nueva captura NVDA llegó a evento terminal recibido y hasMore=False en14 páginas,4.065 identidades/19duplicados/95titulares de ventana:115,797s de colección y116,5s de proceso, sin modelo ni publicación. Esta prueba de capacidad no repite los modelos de LEU/MRNA ni garantiza que todos los futuros tickers quepan en esos límites.

Fuente local de configuración: config/codex_analysis.json. Implementación y evaluaciones: [matriz completa](execution_audit_20261017.md). Arquitectura: [punto de entrada](architecture.md). La cronología previa se conserva [aquí](history/codex_adaptive_analysis_before_audit_20261017.md); sus estados temporales no describen el despliegue de hoy. Checkpoint previo8034b7a y originales preservados. La [evidencia durable de puesta en servicio](audit_work_20261017/execution/activation/README.md) contiene índices, resultados y hashes; los originales de trabajo permanecen en .tmp/activation40_20261018/.

## Configuración actual y significado de los roles

| Elemento | Valor local |
|---|---|
| routing_revision | 41, activa desde19-10-2026 10:49:08.390846UTC; congelados<=40 conservados |
| production_enabled | true |
| Mantenimiento (alias interno Luna/triage) | gpt-6.1-sol, medium; restaurado por orden expresa23-10-2026 para nuevas preparaciones |
| Full (alias Sol/report) | gpt-6.1-sol, high |
| Investigación web | Habilitada para ambos roles dentro de su llamada |
| ITV prioridad / seguimiento | 5 / 5 sesiones de mercado |
| Concurrencia de modelos | Máximo 6, admisión compartida adaptable |
| Relojes mantenimiento / full | 240 / 1200 segundos para arranque y ejecución por separado |
| Frescura máxima configurada | 24 horas;40 añade fechas/calidad por dato, sesiones completas y cobertura terminal de feeds; ver límites más abajo |
| Reparación de mantenimiento | Una corrección dirigida; luna_repair_version=1 |
| Schema de salida mantenimiento | shared-defs-v1; nuevas preparaciones41 desde23Oct, full/congelados anteriores intactos |

El timeout de ejecución comienza con el primer `turn.started`; arranque no consume ese reloj, pero también tiene límite. El pipeline externo tiene sus propios tiempos. Un timeout ambiguo no autoriza otra llamada; evidencia de finalización permite reutilización, fallo transitorio confirmado permite el reintento existente. No hay fallback automático de proveedor/modelo.

No se deduce el modelo a partir de «Luna», `model_usage.base` o la columna de progreso: se comprueban política congelada, recibo y metadatos de ejecución. `--model` y `--reasoning-effort` no son overrides admitidos para el batch adaptativo.

## Contexto final y prompts ensamblados

Desde23Oct, nuevas políticas congelan `maintenance_output_schema=shared-defs-v1`:
el schema de mantenimiento/reparación comparte definiciones sin cambiar su
contrato expandido ni restricciones de fuentes. Se aplica antes de claves de
caché/recibos y reserva, sólo en esos dos roles. Full y políticas sin opción
conservan schema exacto; no hay otro prompt ni cambio de datos financieros.
[Implementación y verificación](audit_sol_input_cost_20261023/implementation/README.md).

Desde22Oct, nuevas políticas congelan `maintenance_context_transport=pointer-diff-v1`:
sólo mantenimiento/reparación serializan los valores de diff por rutas exactas,
con presencia y contexto lógico completo verificados. Los congelados sin opción
conservan sus bytes/instrucciones; full no cambia. [Pruebas y alcance](audit_context_cost_20261022/implementation.md).

adaptive_stage.prepare congela input/policy/instructions. Para una **nueva preparación 41**, el orden real es:

1. Full: stock_analysis_semantic_v14.md. Mantenimiento: daily_maintenance_semantic_v41.md seguido de esa misma política financiera v14.
2. adaptive_revision41.md.
3. volume_arithmetic_v25.md.
4. evidence_direction_v27.md.
5. report_reader_style_v35.md.
6. strength_evidence_v41.md.
7. reader_report_v35.md.
8. catalyst_editorial_v33.md.
9. volume_rubric_v34.md.
10. support_validity_v37.md.
11. option_origins_v39.md.
12. support_origins_v41.md.

El orden proviene de adaptive_stage.prepare; no se añaden los overlays sustituidos además del contrato41. Los schemas de salida41 son iguales a40. Los congelados40 conservan financial_v13, daily/adaptive40 y strength_evidence_v31; no reciben support_origins_v41 ni se reconstruyen con la composición vigente. model_call añade instrucciones de rol/investigación y el schema. adaptive_context.model_context construye el input realmente enviado con CURRENT, ancla full, slim, noticias, acciones de analistas, diferencias, agenda y catálogo. Full puede recibir memoria de investigación; triage elimina esa memoria de investigación full como entrada de relevancia. La memoria autenticada de revisiones y antecedentes sigue disponible según su contrato. El archivo técnico extenso queda fuera del contexto y los mirrors del modelo.

Una reparación recibe el error tipado y el mismo contexto/autoridad; no es una nueva investigación financiera completa. Leer un prompt suelto no basta. El contrato40 retiró la contradicción antigua del techo de volumen por distancia de nodo y la certificación redundante de párrafos no editados;41 conserva esa corrección, revisión de cambios, campos protegidos, origen actual, riesgo y aritmética. La contradicción permanece documentada como historia de los contratos antiguos.41 mantiene la única reparación y las mismas rutas de escalado; su aclaración financiera se aplica también a esa reparación existente.

`stock_analysis_system_prompt.md` sigue existiendo para rutas legacy y se lee inicialmente en prepare; desde 9 las instrucciones full adaptativas se reemplazan por el contrato semántico correspondiente. No es el único prompt activo del sistema actual.

## Reutilización local de noticias por ejecución

Desde18-10, las nuevas órdenes individuales y de lote comparten una captura IBKR completa entre noticias generales, actualización de analistas y backfill hasta el ancla. El directorio propio de la orden impide reutilizar otra ejecución; DJ-N y BRFUPDN conservan identidades separadas. Se valida el contrato cualificado, digest, EOF y el límite de edad de la política vigente. Refiltrar a una fecha inicial anterior usa filas brutas verificadas, conserva la consulta original y nunca extiende el corte ni renueva la fecha de fuente. Un estado más reciente se conserva; una captura caducada o corrupta falla explícitamente. Las preparaciones ya admitidas permanecen congeladas.

[Implementación y evidencia](audit_work_20261017/execution/activation/news_capture_reuse_20261018/README.md):125tests+125subcasos,118vistas con46adquisiciones y236comparaciones downstream;46admisiones y138rechazos negativos. La equivalencia del corpus dominical no garantiza igualdad cuando llegan noticias entre etapas; la nueva metodología usa un corte explícito por orden y ticker. La siguiente orden adquiere datos nuevos. Duración real pendiente del siguiente uso natural; la reutilización no cambió modelos, ITV ni la política financiera40 de su activación y se mantiene en41.

## Qué decide el modelo y qué comprueba el código

| Tema | Juicio del modelo | Responsabilidad determinista |
|---|---|---|
| Soporte | Origen, vigencia compradora, selección y motivos de ausencia | Identidad/resolución de fuentes, forma, valores y cálculos aplicables |
| Continuidad | Por qué cambiar CURRENT, retirar/promover o mantener | Evidencia del cambio separada del origen alternativo; autoridad por campo |
| Fortaleza | Componentes y evaluación de evidencia | Pesos/límites/suma/categoría y Volumen explícito verificable |
| Noticias | Relevancia causal, cobertura de temas, consecuencias y riesgo | Agenda/IDs, conservación de hechos y procedencia |
| Mantenimiento/full | Rutina frente a riesgo, incertidumbre esencial o cambio protegido | ITV, guardas, schema, límites de autorización y reparación |
| Texto público | Redacción, síntesis y selección editorial | Render tipado; no clasificador de verdad/prosa ni gate por puntuación |
| Extensión inferior | Estimación prospectiva defendible o null razonado | Rango/fecha/fuentes; invalidación visual segura sin repair/full adicional |
| Publicación | Ninguna autoridad para elegir hashes o reescribir ancla | Runner vincula respuesta, candidato, bases y ancla; manifest confirma una versión multiformato por ticker y los lectores verifican sus hashes |

El plan nuevo contiene Entry y Washout, opcionales y distintos. Washout representa otro bloque inferior, no una casilla obligatoria. En40 el límite superior de Washout debe ser estrictamente inferior al límite inferior de Entry: no se admiten rangos duplicados, solapados o que se toquen. No se añade un mínimo determinista de separación por ATR; la guía financiera aproximada de0,35 ATR conserva la excepción de estructuras claramente independientes. Poca confluencia, una reacción antigua o ausencia de rebote fresco no convierten automáticamente un origen inferior en inexistente. Una zona por encima de la cotización necesita respaldo positivo de vigencia actual. No se rescata una compra perdida mediante «esperar recuperación».

La rúbrica conserva pesos **25 estructura +20 volumen/reacción +25 opciones +15 confluencia +15 durabilidad** y categorías 70/85/95 con requisitos adicionales. El filtro numérico 50 de Mercado (autorizado22Oct, antes65) es presentación, no categoría ni umbral financiero de selección. Pesos, ventanas y umbrales son convenciones metodológicas; no se encontró calibración predictiva que los valide.

41 aclara el significado de cada componente: confluencia exige información realmente adicional, no contar transformaciones del mismo precio como familias independientes por su nombre; desconocido o pendiente no equivale a deterioro; y el vencimiento de contratos no determina por sí solo la durabilidad del soporte completo. Las inferencias no identificadas sobre signo dealer se revisan por su fundamento actual. Ninguna aclaración concede puntos, impone un mínimo de zonas o autoriza repuntuar por el mero cambio de instrucciones. Opciones conserva25 por preferencia confirmada del usuario.

Reacciones usan ventanas futuras de cinco sesiones completas para medir historia, no un periodo de gracia para conservar soportes. Distancia del nodo aporta proximidad; desde 34 no debe volver a limitar toda la reacción histórica. Datos nuevos o bases de medición distintas no prueban deterioro ni mejora.

## Retain, update, full y memoria

- **Retain:** mantiene juicio financiero y fechas; puede guardar revisión/memoria y migrar presentación/estimar extensión conforme al contrato, sin reset ITV.
- **Update:** cambia campos rutinarios autorizados, con justificación independiente frente a CURRENT. No toma el ancla vieja como si fuera el plan actual.
- **Full:** investigación completa high por petición expresa, ITV o causa protegida/crítica. Crea nueva referencia full y reinicia ITV.
- **Blocked/failure:** conserva el fallo del intento separado del último informe válido. El aviso remoto depende del protocolo/switch activado; no cambia la fecha financiera ni fuerza una retención o un full para superar un rechazo mecánico.

El ancla full inmutable y CURRENT mantenido son objetos distintos. Textos heredados protegidos conservan su fecha/observación; idéntico texto copiado no es una revisión nueva. Una actualización editorial no debe aparecer como renovación financiera. Una referencia autenticada puede demostrar un error previo, pero no sustentar por sí sola un origen actual.

Desde41, `material_improvement` admite actualizar el conocimiento del mismo soporte cuando evidencia actual aplicable resuelve una limitación material del juicio anterior. El modelo debe identificar la premisa, la novedad frente a lo ya incorporado, la consecuencia concreta y los componentes afectados; la memoria evita conceder repetidamente el mismo respaldo. No necesita inventar un cambio del mercado, una apertura de contratos o un `prior_error`. La nueva cobertura por sí sola tampoco obliga a cambiar: se conservan rango y componentes no afectados, y siguen vigentes viabilidad, origen y riesgo. Se decide dentro de la llamada ordinaria de full, mantenimiento o reparación existente.

El historial de recuperaciones no se reescribe como éxito. Recibir una nueva publicación de un ticker tampoco convierte un intento anterior fallido en recuperado.

## Fuentes técnicas41 y cobertura informativa

Las fuentes raw/slim41 están activas al100% en sus endpoints canónicos como `support-resistances-raw-origins41-20261019` y `support-resistances-slim-origins41-20261019`. La captura técnica real CLS del19-10 a las10:46:30UTC observó el suelo exacto290,88 y pasó admisión41; no fue una llamada de modelo ni una publicación financiera. Las capturas APP/archivo40 conservan su alcance histórico. La política de análisis y la revisión de fuente son identidades separadas: un recibo antiguo no se convierte en41 porque el servicio actual se haya desplegado. Las capturas/tag de staging conservan recibos distintos y no se presentan como prueba de la URL canónica.

41 añade `levels.support_origins` para volver a observar suelos de rango y bordes inferiores de gaps con identidad tipada exacta de Entry/Washout activos en CURRENT autenticado, sobre las mismas barras descargadas. La identidad conserva fechas de formación/confirmación y disponibilidad; el legado sólo se reconcilia con una coincidencia exacta y única. No se infieren identidades desde prosa, vecinos o el ancla antigua. La admisión comprueba cobertura de cada petición antes de congelar el contexto. Se conservan shortlist, filtro5%, ganador de cada familia y adquisiciones.

`available` significa formación observada, no vigencia compradora ni fortaleza. `not_observed` describe el pool/identidad observados, nunca demuestra ruptura; `unavailable` conserva historia insuficiente o identidad ambigua. Una formación válida puede seguir observada si faltan sesiones posteriores, pero entonces reacción y estado de relleno/toques quedan explícitamente no disponibles. No se inventa una defensa ni `filled=false`. Ningún estado obliga a retener, retirar o puntuar, y una observación negativa no sirve como origen positivo.

Las identidades de opciones siguen procediendo de fuentes tipadas de Entry/Washout activos en CURRENT, incluidas comparaciones citadas. Se consultan dentro de las mismas cadenas/vencimientos descargados: no se aumenta TOP ni se infiere desaparición por ausencia del ranking. available significa observado, no comprable; not_observed queda acotado al muestreo. Cero, desconocido y descarga fallida son estados distintos. El OI dirigido suma todos los contratos observados y no comparte necesariamente la base gamma-elegible de TOP.40 conserva identidad/OI/quotes aunque no haya gamma suficiente para TOP; no inventa gamma ni liquidez.

La captura40 separa la última sesión de mercado completada del intradía, comprueba integridad de la ventana OHLCV y conserva fechas/selección de quote. La hora de captura no rejuvenece una quote o historia antigua. Se rechazan identidades explícitamente contradictorias; que falte un campo no inventa contradicción. Las observaciones de opciones siguen limitadas a cadenas/vencimientos muestreados, con sus fechas y supuestos.

Noticias y analistas necesitan confirmación terminal del proveedor; timeout/error y has_more no se convierten en un vacío completo. El vacío con terminación real sí puede ser válido. Los relojes de conexión y respuesta histórica se distinguen: el helper local honra el plazo configurado frente a los cuatro segundos fijos de ib_insync, mantiene identidad de petición, errores, terminal y limpieza. run_one, run_batch y las entradas IBKR news/analyst corregidas preservan UTF8 para que un diagnóstico CP1252 no impida el reintento ni oculte el error original. La unión aplicada de UTF8 batch, procedencia, plazos y resumen de reintentos pasa18 pruebas y16 subcasos locales; incluye la ruta real de impresión con subprocess simulado. El pipeline de fuentes se contrastó sin fallo de impresión y no necesitó ese cambio. La integración resolvió la cobertura incompleta de MRNA mediante cursor inverso observado, superposición de un segundo, deduplicación por identidad y rechazo de conflictos/fronteras perdidas. Se agotaron tres páginas reales:652 identidades únicas,2 duplicados y14 titulares en ventana. Solo un evento terminal recibido y hasMore=False completa; cruzar la fecha inicial no basta. La primera capacidad8 falló para NVDA y se amplió a16 sin cambiar30s por respuesta/75s total; la prueba fresca de NVDA agotó75s. El ajuste posterior eleva colección a180s, proceso a210s y backfill a600s, mantiene30s por respuesta/16 páginas y no cambia relojes ni modelos de análisis. El control fresco posterior cerró la adquisición en115,797s/14páginas con EOF real, dentro de los relojes180/210. Límites o fallos futuros siguen rechazando cobertura parcial; no se garantiza capacidad ilimitada. Se conserva el histórico bruto antes del filtro local y su alcance de caché disponible. La metodología financiera no presupone cobertura universal de todas las noticias por disponer de un feed completo.

## Metodología financiera vigente y límites de interpretación

Esta sección describe el contrato financiero41 y las fuentes41 vigentes, conservando los cambios y límites heredados de40. La activación global se identifica al inicio; la compatibilidad de preparaciones anteriores se conserva. Las propuestas M01–M08 tienen resolución en la [matriz de ejecución](execution_audit_20261017.md); las correcciones autorizadas2/3/4 constan en la [implementación41](audit_support_constraints_20261019/implementation/README.md). Las mejoras de fidelidad no rediseñan pesos, selección o ITV.

El propósito es seguimiento empresarial y selección opcional de compras en retrocesos para swing. No hay un horizonte único formalizado para todas las evidencias ni una estrategia completa de ejecución/tamaño/salida. Tesis y Setup internos son juicios distintos; Entry y Washout deben corresponder a bloques compradores defendibles, con Washout inferior y distinto. Origen verificable, viabilidad presente, fortaleza y selección no son sinónimos. El contrato permite ausencia; una referencia disponible no obliga a comprarla.

### Datos y descubrimiento de estructura

| Elemento vigente | Alcance real y límite |
|---|---|
| Historia/precio | Indicadores diarios y20 sesiones recientes completadas en slim. Recorridos descriptivos añadidos en 40; la historia extensa archivada no llega íntegra al modelo |
| Familias | Mínimo252 sesiones, pivotes de rango126, gaps estrictos entre barras, AVWAP diario, medias, canales/estructura, y contratos de opciones observados. No es un catálogo de todos los soportes posibles |
| Selección resumida | Raw tiene mínimos de distancia por defecto del5% para gap/rango/AVWAP y reduce a un ganador de cada familia. No aplica igual a mínimo anual, medias u orígenes dirigidos. Es selección upstream, no una regla financiera de ruptura |
| AVWAP | Promedio acumulado del precio típico diario ponderado por volumen. Jerarquía de anclas y observación independiente de fechas anteriores solicitadas. No es VWAP intradía exacto ni coste observado de los actuales propietarios |
| Gaps | Se observa el gap estricto entre high/low de barras contiguas; no todo gap apertura/cierre.41 conserva identidad y metadatos reconstructibles en la vía dirigida; el shortlist habitual mantiene su alcance |
| Mercado/sector | Fuerza relativa frente a SPY20/60 como diferencia de retornos, tendencia e investigación macro/sector. No es alpha ajustada por beta. El contexto QQQ/VXN/sentimiento y benchmarks que genera el controller no se congela como paquete equivalente en cada input financiero |

La amplitud de familias del prompt no garantiza igual acceso a cada origen en full/mantenimiento. Un origen existente puede perderse por ranking/transmisión. La observación dirigida de opciones CURRENT introducida en39 se mantiene, y41 añade los suelos/gaps activos con identidad tipada. Este alcance permite observar antecedentes concretos fuera del ranking; no crea un catálogo universal ni modifica el descubrimiento general de alternativas. Los detalles previos están en el [anexo de estructura](audit_work_20261017/methodology_structure.md) y la ampliación en la [implementación41](audit_support_constraints_20261019/implementation/README.md).

### Reacciones, volumen y opciones

La reacción histórica usa hasta252 sesiones, agrupa contactos, exige ventanas maduras y comprueba el cierre respecto al nivel/tolerancia y el rebote desde el nivel hasta el máximo de las cinco sesiones siguientes respecto al umbral. Distingue rechazo y rebote y mantiene la base de medición. El agregado original no mide por sí solo el descenso anterior al rebote, su orden intradía, una operación ganadora o episodios estadísticamente independientes.40 añade observaciones descriptivas del recorrido tras el cierre de contacto: excursión favorable/adversa, cierre terminal, tiempo y ventanas solapadas. Declara la ambigüedad de extremos de una misma sesión; OHLC no reconstruye orden intradía. Se calcula sobre una coordenada horizontal actual; no reconstruye automáticamente la curva histórica del AVWAP ni el OI histórico de esa coordenada. Seleccionar hoy una coordenada y resumir sus reacciones pasadas es descripción retrospectiva, no validación ex ante de que se habría elegido antes.

El perfil de volumen usa126 sesiones y48 bins, repartiendo uniformemente el volumen de cada barra entre precios tocados. Está marcado approximate. Es mapa aproximado de actividad, no volumen real a cada precio, libro de órdenes ni flujo comprador/vendedor. La rúbrica limita a3 sus puntos de perfil diario; hasta16 puntos del componente Volumen/reacción derivan de episodios del precio.

Opciones usa tres vencimientos muestreados, TOP por concentración de gamma y detalle por expiración/quotes;39 añade identidades CURRENT fuera de TOP con las mismas descargas. La muestra no es el mercado completo ni siempre el mismo horizonte: puede incluir vencimiento del día. Presencia en varias expiraciones no prueba persistencia de posiciones entre capturas.

En40 se retiran las etiquetas que confundían hipótesis con observaciones: gamma neta de calls menos puts no se presenta como inventario dealer; la prima straddle ATM con su vencimiento/precios no se convierte en sigma semanal calibrada; desaparecen la supuesta probabilidad de toque derivada de una cola terminal y el prior técnico agregado. La concentración/nocional gamma conservados declaran supuestos y cobertura. Max pain puede permanecer como observación de la muestra, sin significado causal automático. Las capturas históricas39 mantienen sus campos y limitaciones originales; no se reescriben. [Opciones y volumen: fórmulas, evidencia y límites](audit_work_20261017/methodology_volume_options.md).


### Rúbrica, empresa y lectura

La fortaleza suma Estructura25 + Volumen/reacción20 + Opciones25 + Confluencia15 + Durabilidad15. Categorías: débil0–39, moderado40–69, sólido70–84, fuerte85–94 y excepcional95–100, con condiciones adicionales de pilares y sumas. Visibilidad de Mercado desde50 (autorizado22Oct) no cambia esos umbrales. Con Opciones0 el máximo es75; aun así se pueden seleccionar compras sin opciones positivas. La escala es convencional y no tiene validación predictiva fuera de muestra demostrada. Notas auxiliares raw y confianza técnica son escalas distintas; ninguna es una probabilidad por compartir números de0 a100.

El contexto permite investigación primaria de noticias, resultados, guía, riesgo y situación empresarial dentro de la llamada vigente. Agenda, memoria fechada y agrupación causal no equivalen a una ficha uniforme de expectativas conocidas antes del evento, realizado y premisas afectadas. Los targets de analistas no son objetivos swing por defecto. Los riesgos antiguos siguen pudiendo ser relevantes aunque no haya un titular nuevo. El full 40 incorpora thesis_state nullable: vigente, deteriorada, rota o no_determinable, con premisa central, evaluación y evidencia. La fecha la fija el runner; las URLs referidas no prueban por sí solas que se recuperaron sus cuerpos. Maintenance conserva exactamente el estado y fecha previos; ausencia/null nunca significa tesis sana. El diagnóstico se separa de score, quote y fortaleza y no crea ventas, stops ni ejecución automática.

El informe público sintetiza resumen, drivers, evento y plan. La extensión inferior es una estimación fechada o null, no stop/garantía/cuantil. ITV5 controla cuándo se exige full, no la vida económica uniforme de una señal. Fecha de revisión, antigüedad de la fuente y horizonte de la conclusión son conceptos distintos.

No se ha demostrado que los pesos, ventanas, distancias, colores o continuidad produzcan mejor resultado económico. Tampoco se ha demostrado lo contrario. La evaluación propuesta separa corrección factual, utilidad de zonas, comprensión del lector y P&L ejecutable, con comparadores, muestra temporal y control de sesgos. [Protocolo de referencia](audit_work_20261017/methodology_evaluation.md) y [resultados locales](execution_audit_20261017.md). Los estudios ejecutados no disponen de holdout suficiente y no justifican reescribir informes históricos.

## Compatibilidades que siguen siendo necesarias

Los recibos históricos conservan su propia política/instrucciones/schema. La selección financiera de versiones es: <=28 v6 en los contratos recientes de esa familia; 29 v7; 30–32 v8; 33 v9; 34 v10; 35–37 v11; 38–39 v12; 40 v13 (usado en los canarios de puesta en servicio); >=41 v14. Los congelados<=40 siguen exactos;41 no añade campos de salida ni modifica sus schemas. Revisiones semánticas más antiguas conservan sus versiones específicas: no reconstruirlas con esta tabla abreviada.

Desde 40, citar exactamente el bloque comprador opuesto de CURRENT en change_review.previous_evidence basta para reconocer la herencia de su rango/Volumen sin exigir duplicar esa misma cita en otro campo. No autoriza la promoción financiera por sí sola ni sustituye el origen actual, la justificación del cambio o los controles de riesgo.

La retirada de stops 29 y resistencia 35 no autoriza eliminar guardas usadas por recibos anteriores. La herencia exacta de rango/Volumen entre compras desde 28 evita tratar una promoción de casilla como cálculo nuevo; no autoriza promover financieramente una zona por sí sola. Los labels legacy permanecen por compatibilidad y observabilidad.

## Qué se ha demostrado

Lote natural seleccionado en la auditoría del17-10:16-10, revisión38,45/46 publicados:18 retain,26 update,1 full IBKR; APP bloqueado.55 llamadas registradas:46 revisiones,8 reparaciones y1 full; un reintento de lote no equivale a otra llamada. Full36 del14-10:46/46 por renovación expresamente solicitada. Estos datos identifican la muestra histórica, no el último uso posterior del sistema.

Revisión 39 tiene captura técnica real APP y pruebas offline; no se encontró en la muestra una ejecución financiera natural 39. Los resultados 32–38 sí tuvieron ejecuciones posteriores guardadas; eso sustituye la afirmación temporal «aún no hubo un siguiente lote», pero no cierra su calidad financiera ni demuestra efectos causales de cada revisión.

La [auditoría](audit_analysis_system_20261017.md) separa contrato sintético, replay original, captura técnica real, modelo real y resultado financiero. Hay controles sólidos y defectos reproducidos; ningún test offline es una validación de rentabilidad.

La activación41 pasó304 pruebas y6 subcasos, incluyendo productor→slim→admisión, preparación41, congelados40, schemas iguales, reparación única y `material_improvement` con MP/NVDA/TSLA sin decidir sus notas. El replay de13 originales conserva sus finanzas; la variante41 en memoria comprueba compatibilidad, no representa nuevas decisiones del modelo. Se verificaron68 prompts anteriores byteidénticos y275 hashes de informes/referencias intactos. La captura CLS añade evidencia técnica real de observación dirigida. Esta ejecución tuvo0 llamadas de modelo y0 publicaciones financieras: sigue pendiente observar el juicio41 y sus consecuencias en llamadas ordinarias. [Alcance y recibos](audit_support_constraints_20261019/implementation/README.md).

## Publicación, archivo y estado de puesta en servicio

Los lectores web, móvil y controller compatibles con legacy y manifest-v1 están activos al 100%. Se verificaron CAS e idempotencia en prefijos sintéticos, versiones históricas/actuales, rechazo de corrupción y puntero no confirmado, y aviso de intento fallido sin redatar el último informe. 46/46 informes legacy mantuvieron generated_at, analysis_status, analysis_markdown y generación GCS. Las pruebas de controller verificaron lectura/proyección con su imagen e identidad reales, sin escritura productiva de Sheet. La ruta manifest confirma el bundle por ticker; Sheet sigue siendo una proyección asíncrona, no una transacción global del universo.

La activación del publicador local usa switches explícitos y la misma validación de política que la ruta habitual. publication_auth selecciona expresamente el CLI GCloud existente con cuenta/proyecto fijados para la ruta SDK de CAS/intentos; ADC sigue siendo el default si no se configura ese modo. Las lecturas y aliases que ya usan el CLI mantienen su identidad activa y requieren que sea concordante. No hay fallback silencioso, proveedor de modelo nuevo, login adicional ni credenciales copiadas. El aviso de latest_attempt está separado del estado y fecha financiera. Un reintento tardío vuelve a comprobar la frescura/autoridad exigida por su contrato; un recibo no autentica por sí solo un artefacto cambiado.

El archivo técnico opcional requiere habilitación del productor y solicitud del runner. El productor40 incorporó el archivo y fue comprobado en la captura canónica;41 lo conserva: historia y respuestas de opciones ya descargadas, con cobertura/hashes y limitaciones explícitas. El switch del runner está habilitado desde la activación global40 comprobada. No añade consultas, no entra en prompts/mirrors del modelo y un fallo exclusivo de archivo queda registrado sin bloquear el análisis. Una serie parcial del benchmark se declara parcial; no se inventan252 sesiones ni cadenas completas para rellenarla.

LEU 40 fue preparado de nuevo contra la fuente canónica40, propiedad registrada y terminales IBKR completos. Una llamada real gpt-6.1-sol medium terminó retained, sin reparación ni búsqueda web ejecutada, usando el mismo Codex local/ChatGPT. La revisión independiente confirmó rangos, componentes, extensión/fecha, ancla y datos financieros exactos; solo migró la revisión de presentación. Se contabilizaron96.364 tokens de entrada y 1.315 de salida, sin convertirlos en un coste monetario no verificado. El retain por sí solo no demuestra el campo de tesis del full ni cubre todas las decisiones update/repair. Sus artefactos siguen separados de publicación; un análisis correcto no prueba automáticamente lectura remota de un informe nuevo.

MRNA40 completó una llamada real gpt-6.1-sol high, sin reparación, con10 operaciones web, mediante el mismo Codex local. El resultado regenerated mantiene los rangos184,5–185,5 y169,5–170,5 y los componentes exactos de CURRENT,55 ambos, tras reevaluar su vigencia y alternativas. Las extensiones182,5/168,3 se vinculan a mínimos observados y fuentes actuales. El nuevo estado de tesis vigente declara premisa, evidencia y límites clínicos/financieros; su fecha la fija el runner. La revisión independiente contrastó siete cuerpos centrales de fuentes realmente devueltos al modelo, no solo URLs. Los componentes heredados de opciones y volumen siguen siendo juicios fechados, no nuevas mediciones; el caso no prueba optimalidad ni calibración. Se registraron1.714.172 tokens de entrada (1.519.104 en caché) y10.548 de salida, sin coste monetario inferido. Ambos canarios siguen sin publicación. Evidencia financiera resumida y hashes: [índice de activación](audit_work_20261017/execution/activation/financial/README.md).

Los incidentes de adquisición y checker de esta integración se preservan con sus soluciones: CP1252, reloj histórico fijo 4 s,429 por instancia Cloud Run no disponible y fallo local del bloqueador de subprocess al importar asyncio. Ninguno se reinterpreta como fallo financiero del modelo. Los intentos MRNA incompletos siguen visibles como adquisición fallida, separados del nuevo full exitoso; no se mezclan con el AMD histórico ambiguo ni autorizan repetirlo.

La observación posterior41 debe hacerse en el próximo flujo natural autorizado, sin forzar un lote o canario de modelo. Registrar decisiones, fuentes, razones de ausencia/retiro, límites de extensión, reparaciones, tiempos y consumo por contrato; comprobar que retain mantiene fecha/ITV y que full registra estado/premisa sin equipararlo a score. Revisar también que la cobertura nueva se juzgue por aplicabilidad y materialidad, sin premio repetido, y que observación dirigida no se confunda con viabilidad. Las mejoras32–38 ya tuvieron ejecuciones posteriores: no esperar literalmente un lote para cada revisión retirada. Las transiciones40/41 no recuperan APP original38 ni otros incidentes históricos, y41 no garantiza más zonas>=65.

Pesos, distancias, ventanas e ITV5 siguen sin validación predictiva suficiente. Los controles sintéticos, replays, capturas reales, llamadas de modelo e integración remota prueban cosas distintas. Ni LEU ni el full MRNA completado constituyen una comparación fuera de muestra o una demostración de rentabilidad.
