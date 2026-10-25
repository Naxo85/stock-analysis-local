# Trabajo pendiente vigente

## Esquema compartido23Oct — aplicado por autorización del usuario

- [x] Activar shared-defs-v1 sólo en nuevas revisiones/reparación41;full y
  congelados sin opción exactos. Solmedium/fullhigh conservados.
- [x]94pruebas+7subtests,92replays/13.606mutantes y92schemas repair exactos;
  552originales+13prompts intactos. [Detalle](audit_sol_input_cost_20261023/implementation/README.md).
- [ ] Observar admisión/uso/caché en siguiente ejecución natural;49%menos texto
  del schema equivale a~1,5%entrada visible,NOahorro semanal demostrado.
  No lote duplicado,pruebas pagadas ni fallback de schema por estas notas.
- [ ] Compresión histórica/cache/otros formatos siguen sin activación;no sumar
  porcentajes de caché hipotética al codec de snapshots.

## Sol medium e investigación de ahorro23Oct — completado

- [x] Por orden expresa,restaurar revisiones Sol6.1medium;fullhigh y demás
  política intactos. load_policy comprobado y460originales preservados.
- [x] Investigar schema,snapshots,cache,instrucciones y fuentes bajo demanda.
  13.606mutantes schema,92roundtrips por variante,7.576registros exactos.
  [Conclusiones](audit_sol_input_cost_20261023/followup/README.md).
- [x] Schema $defs aplicado por orden posterior;beneficio efectivo pendiente.
  Mayor recorte:snapshots dentro de listas (8,61–13,34%caracteres),pero evaluación
  de interpretación financiera pendiente;versión simple sólo0,66–0,85%.
- [ ] Cache:no sumar a snapshots;comprimir ancla destruye gran parte del prefijo
  estable. Inject_items permite estudiar mensajes separados,pero no prueba
  escritura/retención del ancla. Sin control público cache/TTL verificado.
  No migrar cliente ni activar optimizaciones/llamadas por estas notas.
- [x] Recorte general de instrucciones y fuentes bajo demanda estudiados,
  sin ahorro grande seguro demostrado;no habilitados.

## Auditoría corregida Sol21/22Oct — sin activación

- [x]92revisiones reales Sol6.1 medium,ambos46/46 sin repairs;13updates22Oct.
  Revisiones85–88%del crédito calculado;entrada92,7%del coste de revisión22Oct.
  Prioridad Luna sustituida. [Informe](audit_sol_input_cost_20261023/README.md).
- [x]92roundtrips,368checks schema,460originales intactos. Sobre copias con
  pointer-diff ya activo, ahorro adicional combinado12,31%/17,23%de caracteres;
  snapshots8,61%/13,34%,schema~1,4%. No confundir con tokens/créditos/cuota.
- [ ] Primera mejora acotada:schema equivalente;principal recorte medido:codec
  exacto snapshots. Validar admisión/interpretación antes de activar;no modelos
  nuevos ni lotes duplicados autorizados por esta auditoría.
- [ ] Investigar frontera de caché Codex para ancla estable de primera revisión.
  43/46anclas iguales Sol→Sol;reordenar JSON no demuestra caché. Repair secundario.
- [x] Discrepancia resuelta por orden posterior:Sol6.1medium restaurado;ver
  seguimiento superior. La auditoría original no alteró la configuración.

## Auditoría Luna coste de entrada23Oct — antecedente histórico

- [x] Medir46inputs reales y prototipos exactos: hasta10,97%menos caracteres
  normalizados combinados, no ahorro demostrado de tokens/cuota.184checks de
  schema y46roundtrips+8bordes. [Informe](audit_input_cost_20261023/README.md).
- [ ] Defecto contractual/routing de Luna como asunto separado;su84,8%full NO
  prioriza el coste con Sol. No suprimir pipeline retries ni ocultar fallos.
- [ ] Schema $defs equivalente; investigar schema/historial estable para repair
  y fronteras de caché soportadas por Codex antes de activar otro transporte.
  No llamar modelos, modificar congelados ni desplegar por estas notas.

## Comparación Sol medium/low23Oct — completada con alcance limitado

- [x]3llamadas medium autorizadas con inputs idénticos a low: mismas decisiones
  AMD/CLS escalate e IREN retain, mismos riesgos, sin errores en guardas ejercitadas.
  [Informe](audit_context_cost_20261022/sol_medium_comparison_20261023.md).
- [ ] Actualizaciones financieras y reparación siguen sin contraste low/medium;
  no activar modelos, duplicar lotes ni ampliar pruebas automáticamente.

## Sol6.1 low23Oct — piloto limitado

- [x]3llamadas autorizadas sin web/full/repair/publicación:AMD/CLS piden Sol;
  IREN conserva. Recibos/rutas y cobertura ejercitada pasan. [Detalle](audit_context_cost_20261022/sol_low_test_20261023.md).
- [ ] Low/medium siguen sin validar updates; comparación de rutas completada
  en la sección superior. No activar ni repetir pruebas automáticamente.
  Configuración diaria intacta.

## Cobertura pública de noticias23Oct

- Propuesta REVERTIDA por orden expresa del usuario por coste potencial. Se
  retiraron opción, integración y prompt; sigue el alcance web previo. La
  carencia de cobertura CRDO continúa abierta. No reactivar ni lanzar pruebas
  de modelo sin autorización. [Antecedente](audit_news_discovery_20261023/README.md).

## Lote23Oct — fiabilidad y reintentos

- [x] Comprobar AMD/AMAT/SNDK/ASTS: mezcla Volumen+justificación abre fallback
  aunque cada incidencia aislada bloquea Sol. Sin ITV/risk/guardas que lo exijan;
  recibos12llamadas y48archivos originales verificados. [Auditoría](audit_context_cost_20261022/escalations_20261023.md).
- [ ] Corregir composición de guardas para conjuntos de errores ya excluidos de
  Sol, conservando riesgo real/incertidumbre/ITV y fallos visibles. Diagnóstico
  completado; cambio de motor todavía no aplicado ni recuperación autorizada.
- [x] Auditar34/46 y12fallos:9Volumen,2justificación y1timeout. Los12reintentos
  de pipeline no consumieron llamadas nuevas; sí hubo19reparaciones previas.
- [x] Revertir el filtro de reintentos añadido sin petición del usuario. Se
  restaura el comportamiento anterior; diagnóstico conservado, sin modelo/lote.
  [Evidencia](audit_batch_retries_20261023/README.md).
- [ ] Observar calidad/reparaciones en el siguiente uso natural con las mejoras;
 12fallos originales sin recuperación. No repetir lote ni cambiar modelo por ello.

## Citas/aritmética de Volumen23Oct

- [x] Aclaración y diagnóstico dirigido en nuevas políticas mediante
  `volume_calculation_guidance=selected-sources-v1`; fórmula y guardas intactas.
  Reproducción offline de CLS/GEV/ASML, sin modelos ni publicaciones.
  [Detalle](audit_volume_feedback_20261023/README.md).
- [ ] Observar una reparación natural con la nueva opción, sin provocar un lote.
  Los fallos originales23Oct no se han recuperado ni se autorizan por este apunte.

## Prueba de tablas22Oct — completada, sin activación

- [x]8lecturas reales Luna6high:154comprobaciones exactas;4contrastes de
  mantenimiento LEU/TSLA: decisiones/flags coinciden,5,43%menos entrada. Sin web,
  repair/full/fallback/publicación ni alteración de originales. [Informe](audit_context_cost_20261022/table_test_report.md).
- [ ] No hay equivalencia general demostrada: asociación excesiva de titulares
  TSLA en variante tabular; no se ejercitaron updates/repairs. Tablas no activadas;
  no repetir llamadas automáticamente para resolver esa incertidumbre.

## Consumo22Oct — transporte por referencias activo

- [x] Activar `pointer-diff-v1` sólo para nuevas revisiones/reparaciones mediante
  política congelada.63tests+159subcasos,46roundtrips; full y congelados sin opción
  exactos. No modelo/lote/publicación. [Evidencia](audit_context_cost_20261022/implementation.md).
- [ ] Medir tokens/interpretación en próximo uso natural;3,561% de reducción en
  caracteres descontando nueva instrucción no es un porcentaje de cuota Plus.
- [ ] Tablas: protocolo de8llamadas cortas y posterior contraste de mantenimiento
  descrito, no ejecutado ni activado; no asumir equivalencia financiera por roundtrip.
- [ ] Caché: sin TTL público encontrado en CLI0.163.0-alpha.11.1/452schemas; aciertos
  nocturnos mezclan posible retención y prefijos compartidos. No activar parámetros
  desconocidos ni warmups ni automatizaciones para mantener caché.

## Avisos earnings21Oct — activados y comprobados

- [x] Borde naranja fino2–7días y rojo grueso hoy/mañana, nota fechada y retirada por calendario Europe/Madrid; identidad/enlace/fondo de cartera conservados. API y etiqueta Android equivalentes.
- [x] Verificar75tests controller/21API,8unitarias Android, compilación/lint y ejemplos publicados SPCX20Oct/LRCX21Oct sin regenerar informes. Interfaz instrumentada sin ejecutar por falta de aceleración del emulador.
- [x] Autorización explícita posterior recibida; controlador/API `earnings-20261021` al100% con runtime conservado. Refresh46/46, visual/lectura independiente LRCXK8rojo y SPCXsinmarca,10avisos concordantes API/Sheet y46fondos concordantes con cartera vigente. La comparación original coincide con lote/órdenes ajenos activos; no declarar finanzas/cartera idénticas ni atribuirlas a esta tarea. [Evidencia](audit_earnings_20261021/README.md).


Actualizado19-10-2026. Este es el backlog canónico. Revisión41 activada para nuevas preparaciones el19-10-2026 a las10:49:08 UTC (12:49:08 Europe/Madrid). RAW y SLIM `origins41-20261019` están al100%; los tres consumidores compatibles publication40 permanecen activos. La política cambió únicamente routing_revision40→41, con SHA25610745943fc7b3e7043071b01d283ac68661dbe6a1c7409c76466e4760d4718c4. Publicación manifest-v1, último intento y archivo técnico siguen habilitados. Mismo Codex local, modelos medium/high, ITV5 y techo6; congelados<=40 intactos. [Implementación, pruebas y activación41](audit_support_constraints_20261019/implementation/README.md).

La activación40 del18-10-2026 a las08:17:18 UTC y su configuración SHA25664e54ed9d2e40a47a86538b5af82747ca9f573c00fba0784ee7ca2a28d6ec53e quedan como antecedente fechado; no son la política de nuevas preparaciones.

Formato Tesis INTC19Oct: **corregido y activo**. Retirada negrita residual de AK13 con contenido/enlace exactos; actualizador fija peso normal en el fragmento de Tesis. Controller `stock-controller-thesis-plain-20261019`, runtime/presentation15 conservados,23tests+3subcasos locales y7tests en imagen. [Evidencia](audit_thesis_plain_20261019/README.md). Es presentación; no representa cambio de juicio financiero.

Enlaces Tesis19Oct: **corregido y restaurado46/46**. Controller `stock-controller-report-links-sort-20261019` conserva compatibilidad publication40; sólo cambian serialización de enlaces normalizados al ordenar y presentation_version15. Reproducción real antes/después,55tests+3subcasos, refresh normal con ordenación y comparación de46versiones/valores/notas exactos. [Evidencia](audit_thesis_links_20261019/README.md). No se generó otro lote ni informe financiero.

LRCX19Oct: **corregido y recuperado**. Raw máximo1→3 en servicio/revisión, imagen41 exacta, resto del runtime equivalente; cliente reintenta de forma acotada los rechazos temporales429/503 antes de admitir el input.108tests+17subcasos y reproducción de ambos errores originales. [Evidencia](audit_lrcx_capacity_20261019/README.md). Full individual nuevo publicado14:39:07UTC; una high/6web/0repair/0fallback, seis artefactos e intento succeeded verificados, JSON/HTML y enlace Sheet correctos. No se vuelve a ejecutar el lote45/46 ni se alteran sus estados originales. No es validación de calidad predictiva ni garantía contra caídas persistentes.

La [matriz completa](execution_audit_20261017.md) contiene29 resoluciones: los27 puntos originales, H16 encontrado durante la puesta en servicio y H17 tras el primer arranque posterior. La [evidencia18-10](audit_work_20261017/execution/activation/README.md) cierra A1–A3. No todos los puntos son funciones que debían incorporarse: algunas hipótesis quedan descartadas o inconclusas por evidencia concreta.

Las tablas siguientes son el **inventario original**. El estado actual (activado/verificado, descartado o inconcluso) está en la matriz de ejecución; no deben leerse como una lista de todo todavía sin implementar. Evidencia y criterios detallados: [auditoría](audit_analysis_system_20261017.md). Estado operativo: [relevo](handoff_current.md).

## Inventario original de correcciones — estado actualizado en la matriz

| Prioridad | Trabajo | Criterio mínimo de aceptación / dependencia |
|---|---|---|
| Alta | Conservar terminación/error del feed IBKR; no redatar timeout como vacío | Timeout/error no llega como fuente completa; vacío terminado sí. Replay MU/CRWV/IBKR 15-10 y analistas OKLO 14-10. Preservar last_good fechado |
| Alta | Cerrar integridad durable respuesta → candidato → bundle | Mutar response, espejos, MD o HTML se rechaza antes de escribir; originales válidos y recibos congelados siguen utilizables sin reescribirlos |
| Alta | Revisar frescura antes del primer compromiso de publicación tardío | Candidato validado>24 h no inicia publicación; reintento parcial legítimo tiene contrato explícito, fechas e ITV originales |
| Alta | Separar volumen completado de intradía | Variar barra abierta no cambia last_complete_day ni indicador last_close; 46 inputs 16-10 coherentes sin repuntuar informes |
| Media | Evitar Entry/Washout idénticas y reconciliar herencia tipada TLN | Mantener dos bloques distintos/inferiores y ausencia válida; la misma cita autenticada no exige duplicación de ubicación para heredar cifra exacta |
| Media | Corregir unidades expected move y lado de pared próxima |0.75% no se vuelve 75%; pared superior no se convierte en distancia inferior 0 |
| Media | Separar parser contractual de elegibilidad gamma | OI/quotes válidos sin gamma permanecen en métricas que no necesitan gamma; TOP completo conserva resultados |
| Media | Frescura por dato y calidad de quote | captured_at no rejuvenece quote/history; midpoint inválido usa alternativa válida/fechada o falla explícitamente |
| Media | Cobertura IBKR con señal hasMore/límite | No declarar complete/truncated=false cuando faltan páginas; error intermedio conserva incertidumbre |
| Media | Estado de intento separado del último informe válido | APP-like visible en API/Sheet/lector sin borrar, redatar ni invalidar el informe anterior |
| Media | Definir commit multiformato y ancla/CURRENT | Fallos inyectados por escritura dejan versión completa o estado pendiente visible; considerar manifest/CAS según alcance de varios escritores |
| Media | Consolidar instrucciones actuales y contrato de explicación | Retirar contradicción volumen<=3% solo en nueva versión autorizada; preservar congelados. Evaluar wrappers redundantes sin eliminar reconciliación financiera |
| Media | Baseline reproducible del árbol y tests por revisión | Registrar archivos/digests/runtime y separar tests de versión fija de configuración vigente; no cambiar modelo para satisfacer expectativa antigua |

Estos puntos no autorizan publicar correcciones retrospectivas ni repetir lotes. Las correcciones locales ya verificadas conservan las protecciones de origen, riesgo, autoridad, fechas y memoria; su activación e integración A1–A3 ya están documentadas en la matriz. H16 añade la corrección de autoridad de tenencia individual/manual y procedencia de lote, sin alterar universos ni cartera.


## Inventario metodológico original y resolución posterior

La [ampliación de la auditoría, §§14–20](audit_analysis_system_20261017.md#14-ampliación-qué-conservaríamos-y-qué-rediseñaríamos) evalúa alternativas al propio método, con evidencia primaria favorable/contraria y casos ex ante. Esta tabla conserva el índice original; la matriz enlazada arriba contiene el resultado de la investigación y ejecución, incluidas adopciones parciales y descartes.

| Prioridad / ID | Propuesta investigada | Comparación y condición para avanzar |
|---|---|---|
| 1 / M01 | Separar concentración observada de signo dealer; sustituir o retirar prob_touch terminal, interpretación IV barata desde EM/RV y max pain como argumento causal | Mismos hechos sin etiquetas ambiguas; fórmulas/tiempos correctos antes de evaluar valor incremental. No duplicar porcentajes ni afirmar que todo mecanismo de opciones es inútil. E4 |
| 1 / M03 | Conservar eventos y fechas de formación; medir adversidad, cierre, tiempo y dependencia además del high5d | Misma selección/visitas, resúmenes alternativos, datos ex ante y orden intradía ambiguo explícito. No introducir stops ni recalificar originales. E3 |
| 1 / M05 | Contexto común/sectorial mínimo fechado, incluyendo comparación sin etiqueta agregada CNN/VXN | Mejor atribución y evaluación de vigencia sin doble penalización, veto contrarian o causalidad inventada. Congelar bases/horas antes de copiar paneles. E1 |
| 1 / M06 | Fichas de premisas/eventos: expectativa disponible, realizado, implicación y cuestión abierta | Menos omisiones/afirmaciones erróneas frente a la investigación actual; no sorpresa inventada ni mezcla GAAP/periodos. Factibilidad antes de comprar consenso histórico. E5 |
| 2 / M02 | Descubrimiento compacto de candidatos cercanos/diversos; después multiescala y anclas de evento | Mismo presupuesto, sin filtro fijo5% en alternativa, origen/availability_date y abstención; ganancia fuera de muestra, no más casillas. E2 |
| 2 / M04 | Ablación de priors raw y confluencia; luego opciones como contexto o rúbrica más simple | Información incremental y ordenamiento mejor, con registro de variantes/pesos. No redistribuir puntos para elevar notas/visibilidad;0 opciones permite selección pero limita total75. E4 |
| 2 / M07 | Explicitar horizonte de evidencia, condición pendiente y fechas en la lectura | Misma decisión financiera, menos confusión entre zona/verde/confirmación/compra y conservación de riesgos. No rediseño automático de rangos. E6 |
| 3 / M08 | Relojes de fuentes, eventos y materialidad; evaluación de cadencia en sombra | Menor retraso y llamadas/cambios evitables sin perder riesgo; ITV actual como referencia hasta evidencia suficiente. E7 |
| Condicional | Datos intradía, flujos clasificados, panel temporal de opciones, skew/estructura temporal o probabilidades calibradas | Pregunta específica no resuelta por versión sencilla; coste/cobertura/horizonte justificados. No son requisitos para completar el producto actual |

Los pasos de cálculo/etiquetas se verificaron localmente y en capturas reales. Los canarios autorizados verifican integración de los dos roles40; no resuelven calidad general o comprensión humana. Este backlog no ordena experimentos, lotes duplicados, operaciones de cartera ni sustituciones de modelo.

El [protocolo](audit_work_20261017/methodology_evaluation.md) propone B0 original, B1 con correcciones deterministas aprobadas, B2 sencilla y una alternativa por vez; muestra cronológica, unidad episodio, universos de época, controles de múltiples pruebas y criterios de adoptar/descartar/inconcluso. Las correcciones deterministas B1 están implementadas, verificadas y activadas; no están validadas predictivamente. Los descriptivos46 inputs/45 publicaciones/71 zonas no son validación predictiva.

Separar como decisiones de producto: horizonte principal/tarea de utilidad y acciones operativas ante estado de tesis; el diagnóstico informativo está implementado para full40, sin automatización; estrategia de rupturas, ejecución, tamaño, stops, objetivos o gestión automática de cartera no se incorporan como supuestas carencias del soporte actual. Las retiradas históricas siguen vigentes.

## Correcciones de soportes41 — completadas19-10

- [x] Actualización material del conocimiento: la nueva evidencia aplicable puede revisar el componente del mismo soporte mediante la autoridad ordinaria, sin inventar cambio de mercado ni error previo; recibir, revisar e incorporar información son hechos distintos.
- [x] Aporte independiente de componentes: distinguir desconocido de evidencia adversa, vencimiento contractual de supervivencia del soporte completo y fundamentos heredados de signo dealer no identificado. Sin repuntuación automática, nuevas puertas de prosa ni cambios de pesos.
- [x] Observación dirigida de orígenes CURRENT: recuperar identidades exactas de suelos/gaps fechados aunque salgan del ranking; estados y cobertura explícitos, sin convertir disponibilidad en viabilidad ni forzar retención. Se mantienen los selectores y el filtro global5%.
- [x] Ratificar Opciones25 y visibilidad65/solid70. La investigación no sustenta cambiar pesos para conseguir más zonas visibles.
- [x] Verificar y activar41:304pruebas+6subcasos, RAW/SLIM al100% con runtime conservado y captura técnica real CLS290,88 disponible y admitida a10:46:30UTC. Cero llamadas de modelo y cero publicaciones financieras en esta activación. [Evidencia](audit_support_constraints_20261019/implementation/README.md).
- [ ] Observar el juicio financiero y el comportamiento operativo41 en el siguiente flujo natural. Las pruebas y la captura CLS verifican integración, no calidad predictiva ni un aumento de soportes. No lanzar un lote duplicado para medirlo.

## Observación natural18-10 y pendientes concretos

La primera orden40 del18-10/08:29 falló por H17 antes de analizar. La orden posterior **20261018-090400-731-market-a8dba136** terminó46/46,25retain/21update/0full,46medium/0repair/0fallback/0retry. Los originales conservan sus estados; APP nuevo no recupera APP16Oct. [Auditoría, evidencia y matriz29puntos](audit_work_20261017/execution/activation/natural_run_20261018/README.md).

- [x] Observar natural40: admisión, orígenes dirigidos, selección, extensiones y bases OI/vencimientos en46casos; replay financiero46/46.46anclas y last_full exactos; tresretain revisan sólo su extensión de compra. Sin defecto financiero material identificado en el alcance revisado.
- [x] Auditar revisiones37/38, editorial y rúbrica en el lote vigente, sin exigir repetir números de revisión antiguos:10tickers cambian rangos, cinco promociones conservan componentes;0cambios de nota de tesis. La razón heredada de ausencia de MU está fechada pero refleja peor el razonamiento actual: límite editorial documentado, no corrección publicada.
- [x] Medir capacidad, tiempos, reparaciones y consumo:46medium,20operaciones web,0repair,techo6 y0,282s de espera de capacidad.51min52,6s de lote frente21min23,7s anterior. No es evidencia causal de ahorro ni de rentabilidad.
- [x] Comprobar publicación real:46commits/276objetos conhash,46lectores web/móvil/versionados exactos,70zonas móviles coherentes.46mirrors y2resúmenes remotos exactos; controller marca46versiones sincronizadas a10:00:47UTC.
- [x] **Duplicación de capturas:** [implementada en nuevas órdenes locales](audit_work_20261017/execution/activation/news_capture_reuse_20261018/README.md). Noticias, analistas y backfill comparten captura inmutable por ejecución con EOF/digest/identidad, corte original y límite de frescura vigente.125tests+125subcasos;118vistas desde46adquisiciones y236comparaciones downstream aprobadas; nueva orden obtiene noticias nuevas. Los118originales y el lote pasado quedan intactos.
- [ ] **Efecto operativo de la reutilización:** medir adquisiciones y duración en el siguiente flujo natural.207páginas/1.455,060s duplicados del corpus son oportunidad observada, no ahorro de pared demostrado. No repetir un lote sólo para medirlo.
- [ ] Estado de tesis full40, repair y negativos de publicación: no ejercitados por este lote sin full/repair/fallos. Canarios y tests previos conservan su evidencia; observarlos cuando corresponda naturalmente, sin forzar otro lote.
- [x] Lectura independiente de Sheet por el conector existente tras403de GCloud:46filas,230valores financieros, notas Entry/Washout/Setup y46enlaces versionados exactos.322celdas leídas, sin cambios ni ampliación de permisos. No implica inspección de todo el libro, colores/bordes o notas de deltaTesis.
- [ ] Teléfono físico: APK firmado y emulador ya comprobados; instalación/verificación física sigue sin dispositivo accesible.

## Evaluación, producto y mantenibilidad

- [x] Retroceso relativo actual QQQ en espacio superior C2:H7 de Mercado y app:
  cierre fechado, máximo relativo, umbral5% y reinicio tras rebote5%, sin historial
  visible ni desplazamiento de tablas. Controller/API activados con runtime
  preservado; APK firmado y unit/lint verificados. No se verificó teléfono físico.
  [Evidencia](audit_qqq_pullback_20261019/README.md).

- [x] Ejecutar la evaluación local posible y especificar la confirmación pendiente: candidatos, recorridos, ablaciones, contexto, eventos, cadencia y opciones. Las carencias de datos/etiquetas/lectores de la matriz no se cierran por simulación.
- [ ] Evaluar ventanas/ITV5 cuando exista evidencia suficiente; no están demostrados incorrectos ni validados empíricamente. Opciones25 quedó ratificado el19-10; este pendiente no abre una modificación de pesos.
- [x] Implementar estado de tesis informativo separado de nota para full40, con evidencia/fecha e herencia exacta. Calidad del juicio y acciones operativas siguen sin validar/definir; no introducir ventas/stops automáticos.
- Universo: se conservan «todos» (AGENTS/tickers.json) y menú Mercado/tickers_market.json tal como están autorizados. Cambiar su intención es decisión de producto; no se unifican silenciosamente en esta ejecución.
- [x] Preparar, probar y activar archivo técnico de observaciones ya descargadas, separado del contexto/modelo. Se exportaron184 inputs locales, todos parciales; conserva cobertura y fechas sin inventar252 sesiones ni cadenas completas. A2/A3 habilitados y comprobados; nuevas capturas reales pueden conservar252 barras/cadenas cuando la fuente las suministra válidas. Las series originales no resuelven por sí solas ajustes corporativos ni fecha efectiva de OI.
- [x] Crear checkpoint previo8034b7a a petición del usuario:681 archivos,479 fuentes y Android verificados por hash; cinco documentos reconstruidos desde ediciones conocidas. Cambios de ejecución fuera del commit.
- [x] Actualizar arquitectura, motor, relevo, auditoría y matriz; antecedentes preservados. Revisión41 y protocolos activos; los snapshots candidatos anteriores quedan como historia, no instrucciones vigentes.

## Pendientes anteriores conservados, sin cierre implícito

El [backlog anterior completo](history/pending_work_current_before_audit_20261017.md) conserva cada checkbox y su evidencia. Se mantienen abiertos o como incidentes históricos sin recuperación, según allí consta:

- CRWV/MU full 31, SOFI natural 28, AMAT, SPCX/AUR y otros fallos antiguos; una publicación posterior no modifica el intento original.
- Restauración puntual de motivos MU y discrepancias derivadas MRNA/Sheet CRDO-LRCX: no se ejecutó reparación remota ni se confirmó vigencia actual del defecto.
- Rechazo intermitente del perfil cifrado Gateway: causa interna no demostrada.
- Web/Firefox/Chromium, Cloudflare y GPU: compatibilidad legacy, no dependencia de salud del motor adaptativo diario; pruebas vivas no repetidas.
- Heartbeats/reconciliación de progreso y timeouts GCS; estado remoto no revalidado.
- Verificación visual de operaciones reales de cartera/cotizaciones sin bid-ask; no repetir compras/ventas para probar.
- Taxonomía, exposiciones solapadas, benchmarks de cartera y noticias generales Growth: propuestas y acuerdos de sus documentos, sin implementación en esta auditoría.
- Instalación y app Android: conservar pendientes específicos ajenos a esta auditoría; la puesta en servicio comprobó servicio/APK en emulador, no instalación en teléfono.

La evidencia de lotes posteriores permite corregir frases temporales como «aún no hubo ejecución», pero no cerrar calidad, incidencias originales ni propuestas de producto. El historial no es una lista de órdenes para ejecutar automáticamente.
