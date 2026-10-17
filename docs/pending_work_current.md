# Trabajo pendiente vigente

Actualizado 17-10-2026. Este es el backlog canónico.

 Las mejoras de sistema siguientes están **propuestas, no implementadas**; la auditoría autorizó documentación y pruebas locales, no cambios de comportamiento. Evidencia y criterios detallados: [auditoría](audit_analysis_system_20261017.md). Estado operativo: [relevo](handoff_current.md).

## Prioridades de corrección propuestas

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

Estos puntos no autorizan publicar correcciones retrospectivas ni repetir lotes. Los cambios de datos/código deberán proponerse de forma acotada y conservar las protecciones de origen, riesgo, autoridad, fechas y memoria.


## Investigación metodológica pendiente, sin implementación

La [ampliación de la auditoría, §§14–20](audit_analysis_system_20261017.md#14-ampliación-qué-conservaríamos-y-qué-rediseñaríamos) evalúa alternativas al propio método, con evidencia primaria favorable/contraria y casos ex ante. No cambia la política actual. Esta tabla es el backlog; los anexos desarrollan evidencia y diseño, no son otra lista de órdenes.

| Prioridad / ID | Propuesta pendiente | Comparación y condición para avanzar |
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

Los primeros pasos de cálculo, etiquetas y comprensión pueden ser deterministas o humanos. Comparar nuevas respuestas financieras del modelo requeriría un encargo y presupuesto posteriores. No se autorizan llamadas adicionales, experimentos externos, batches de prueba o sustitución de modelos por esta tabla.

El [protocolo](audit_work_20261017/methodology_evaluation.md) propone B0 original, B1 con correcciones deterministas aprobadas, B2 sencilla y una alternativa por vez; muestra cronológica, unidad episodio, universos de época, controles de múltiples pruebas y criterios de adoptar/descartar/inconcluso. B1 todavía no está implementada. Los descriptivos46 inputs/45 publicaciones/71 zonas no son validación predictiva.

Separar como decisiones de producto: horizonte principal/tarea de utilidad y estado de tesis; estrategia de rupturas, ejecución, tamaño, stops, objetivos o gestión automática de cartera no se incorporan como supuestas carencias del soporte actual. Las retiradas históricas siguen vigentes.

## Observación natural pendiente

- [ ] Revisión 39: observar llegada de orígenes dirigidos y juicio financiero con bases OI/vencimientos correctos; captura técnica APP no sustituye modelo real.
- [ ] APP original 38 sigue fallido; una preparación futura 39 no lo recupera retrospectivamente.
- [ ] Criterios 37/38: ya hay natural 38 del 16-10 con decisiones reales; revisar selectivamente nulls, extensiones, selección y retiradas sin suponer que todos cumplen ni exigir más casillas.
- [ ] Editorial 32/33/35 y rúbrica 34: hubo full y mantenimiento posteriores; queda evaluación cualitativa/financiera, no esperar literalmente un lote con cada número de revisión retirado.
- [ ] Capacidad, tiempos, reparaciones y consumo: registrar por llamadas/contratos e intentos; no deducir ahorro de quota ni rentabilidad de porcentajes de retain.
- [ ] Consumidores/despliegue: comprobar coherencia remota y runtime cuando se autorice una operación que lo requiera; no se revalidaron 17-10.

## Evaluación, producto y mantenibilidad

- [ ] Diseñar evaluación prospectiva con decisiones y universos fechados, comparadores y sesgos controlados; separar precisión factual, vigencia de soporte, calibración y utilidad económica.
- [ ] Evaluar pesos/ventanas/ITV5; no están demostrados incorrectos ni validados empíricamente. No cambiar Opciones 25 por intuición o cuota visible.
- [ ] Resolver el eje de estado de tesis separado de nota acordado en el [cuaderno](estrategia_compra_bolsa.md), cuyo disparador operativo sigue sin definir. No introducir stops/ventas automáticas retirados.
- [ ] Resolver intención del universo «todos» (AGENTS/tickers.json) frente a menú Mercado/tickers_market.json. La auditoría describe ambas rutas sin cambiar instrucciones.
- [ ] Conservar recibos de adquisición suficientes para revisar splits/unidades, timestamps y contratos originales sin nuevas consultas futuras.
- [ ] Preparar commits lógicos del árbol previo acumulado. La auditoría no hizo commit ni mezcló sus cambios con código anterior.
- [ ] Mantener una sola descripción vigente y archivar cronología; revisiones documentales no deben convertirse en política nueva.

## Pendientes anteriores conservados, sin cierre implícito

El [backlog anterior completo](history/pending_work_current_before_audit_20261017.md) conserva cada checkbox y su evidencia. Se mantienen abiertos o como incidentes históricos sin recuperación, según allí consta:

- CRWV/MU full 31, SOFI natural 28, AMAT, SPCX/AUR y otros fallos antiguos; una publicación posterior no modifica el intento original.
- Restauración puntual de motivos MU y discrepancias derivadas MRNA/Sheet CRDO-LRCX: no se ejecutó reparación remota ni se confirmó vigencia actual del defecto.
- Rechazo intermitente del perfil cifrado Gateway: causa interna no demostrada.
- Web/Firefox/Chromium, Cloudflare y GPU: compatibilidad legacy, no dependencia de salud del motor adaptativo diario; pruebas vivas no repetidas.
- Heartbeats/reconciliación de progreso y timeouts GCS; estado remoto no revalidado.
- Verificación visual de operaciones reales de cartera/cotizaciones sin bid-ask; no repetir compras/ventas para probar.
- Taxonomía, exposiciones solapadas, benchmarks de cartera y noticias generales Growth: propuestas y acuerdos de sus documentos, sin implementación en esta auditoría.
- Instalación y app Android: conservar pendientes específicos de sus guías; no afirmar que la auditoría local verifica servicios/APK hoy.

La evidencia de lotes posteriores permite corregir frases temporales como «aún no hubo ejecución», pero no cerrar calidad, incidencias originales ni propuestas de producto. El historial no es una lista de órdenes para ejecutar automáticamente.
