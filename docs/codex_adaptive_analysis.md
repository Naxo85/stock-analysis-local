# Motor Codex adaptativo: contrato vigente

Estado documental: 17-10-2026. Fuente local de configuración: `config/codex_analysis.json`. Esta descripción sustituye las antiguas secciones que se titulaban simultáneamente «Current deployment». La cronología completa se conserva [aquí](history/codex_adaptive_analysis_before_audit_20261017.md). Arquitectura: [punto de entrada](architecture.md).

## Configuración actual y significado de los roles

| Elemento | Valor local |
|---|---|
| routing_revision | 39, para nuevas preparaciones |
| production_enabled | true |
| Mantenimiento (alias interno Luna/triage) | gpt-6.1-sol, medium |
| Full (alias Sol/report) | gpt-6.1-sol, high |
| Investigación web | Habilitada para ambos roles dentro de su llamada |
| ITV prioridad / seguimiento | 5 / 5 sesiones de mercado |
| Concurrencia de modelos | Máximo 6, admisión compartida adaptable |
| Relojes medium / high | 240 / 1200 segundos para arranque y ejecución por separado |
| Frescura máxima configurada | 24 horas; validación actual de envoltorios, con limitaciones por dato |
| Reparación de mantenimiento | Una corrección dirigida; luna_repair_version=1 |

El timeout de ejecución comienza con el primer `turn.started`; arranque no consume ese reloj, pero también tiene límite. El pipeline externo tiene sus propios tiempos. Un timeout ambiguo no autoriza otra llamada; evidencia de finalización permite reutilización, fallo transitorio confirmado permite el reintento existente. No hay fallback automático de proveedor/modelo.

No se deduce el modelo a partir de «Luna», `model_usage.base` o la columna de progreso: se comprueban política congelada, recibo y metadatos de ejecución. `--model` y `--reasoning-effort` no son overrides admitidos para el batch adaptativo.

## Contexto final y prompts ensamblados

`adaptive_stage.prepare` congela input/policy/instructions. La revisión 39 usa el siguiente orden real (líneas 179–202 del código inspeccionado):

1. Full: `stock_analysis_semantic_v12.md`. Mantenimiento: `daily_maintenance_semantic_v35.md` seguido de la misma política financiera v12.
2. `adaptive_revision35.md`.
3. `volume_arithmetic_v25.md`.
4. `evidence_direction_v27.md`.
5. `report_reader_style_v35.md`.
6. `strength_evidence_v31.md`.
7. `reader_report_v35.md`.
8. `catalyst_editorial_v33.md`.
9. `volume_rubric_v34.md`.
10. `support_validity_v37.md`.
11. `option_origins_v39.md`.

`model_call` añade instrucciones de investigación web/rol y el schema. `adaptive_context.model_context` construye el input realmente enviado con CURRENT, ancla, slim, noticias, acciones de analistas, diferencias, agenda y catálogo. Full puede recibir memoria de investigación; triage elimina esa memoria de investigación full como entrada de relevancia. La memoria autenticada de revisiones y antecedentes sigue disponible según su contrato.

La reparación recibe el error tipado y el mismo contexto/autoridad; no es una nueva investigación financiera completa. **Leer un prompt suelto no basta**. En la composición vigente persiste texto antiguo de distancia del nodo en adaptive 35, incompatible con el criterio 34; está documentado como defecto abierto, no resuelto en esta actualización documental.

`stock_analysis_system_prompt.md` sigue existiendo para rutas legacy y se lee inicialmente en prepare; desde 9 las instrucciones full adaptativas se reemplazan por el contrato semántico correspondiente. No es el único prompt activo del sistema actual.

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
| Publicación | Ninguna autoridad para elegir hashes o reescribir ancla | Runner vincula bases/autoridad y persiste; huecos duraderos abiertos en auditoría |

El plan nuevo contiene Entry y Washout, opcionales y distintos. Washout representa otro bloque inferior, no una casilla obligatoria. Poca confluencia, una reacción antigua o ausencia de rebote fresco no convierten automáticamente un origen inferior en inexistente. Una zona por encima de la cotización necesita respaldo positivo de vigencia actual. No se rescata una compra perdida mediante «esperar recuperación».

La rúbrica conserva pesos **25 estructura +20 volumen/reacción +25 opciones +15 confluencia +15 durabilidad** y categorías 70/85/95 con requisitos adicionales. El filtro numérico 65 de Mercado es presentación, no categoría ni umbral financiero de selección. Pesos, ventanas y umbrales son convenciones metodológicas; no se encontró calibración predictiva que los valide.

Reacciones usan ventanas futuras de cinco sesiones completas para medir historia, no un periodo de gracia para conservar soportes. Distancia del nodo aporta proximidad; desde 34 no debe volver a limitar toda la reacción histórica. Datos nuevos o bases de medición distintas no prueban deterioro ni mejora.

## Retain, update, full y memoria

- **Retain:** mantiene juicio financiero y fechas; puede guardar revisión/memoria y migrar presentación/estimar extensión conforme al contrato, sin reset ITV.
- **Update:** cambia campos rutinarios autorizados, con justificación independiente frente a CURRENT. No toma el ancla vieja como si fuera el plan actual.
- **Full:** investigación completa high por petición expresa, ITV o causa protegida/crítica. Crea nueva referencia full y reinicia ITV.
- **Blocked/failure:** deja evidencia local y estado de lote; no fuerza una retención ni compra full solo para superar un rechazo mecánico.

El ancla full inmutable y CURRENT mantenido son objetos distintos. Textos heredados protegidos conservan su fecha/observación; idéntico texto copiado no es una revisión nueva. Una actualización editorial no debe aparecer como renovación financiera. Una referencia autenticada puede demostrar un error previo, pero no sustentar por sí sola un origen actual.

El historial de recuperaciones no se reescribe como éxito. Recibir una nueva publicación de un ticker tampoco convierte un intento anterior fallido en recuperado.

## Datos técnicos 39

Las identidades de opciones proceden de fuentes tipadas de Entry/Washout activos en CURRENT, incluidas comparaciones citadas. Se consultan dentro de las mismas cadenas/vencimientos descargados: no se aumenta TOP ni se infiere desaparición por ausencia del ranking.

`available` significa observado, no comprable; `not_observed` queda acotado al muestreo; cero, desconocido y descarga fallida son estados distintos. El OI dirigido suma contratos observados y no comparte necesariamente la base gamma-elegible de TOP. Un origen positivo sigue necesitando put observado no expirado con apoyo positivo. Las limitaciones de agregados generales y de frescura se detallan en la auditoría.


## Metodología financiera vigente y límites de interpretación

Esta sección es **descriptiva**: documenta cálculos y límites encontrados el17-10-2026. No modifica prompts, pesos, selección, routing ni contratos. Las alternativas M01–M08 de la [ampliación metodológica](audit_analysis_system_20261017.md#14-ampliación-qué-conservaríamos-y-qué-rediseñaríamos) están pendientes, no incorporadas.

El propósito es seguimiento empresarial y selección opcional de compras en retrocesos para swing. No hay un horizonte único formalizado para todas las evidencias ni una estrategia completa de ejecución/tamaño/salida. Tesis y Setup internos son juicios distintos; Entry y Washout deben corresponder a bloques compradores defendibles, con Washout inferior y distinto. Origen verificable, viabilidad presente, fortaleza y selección no son sinónimos. El contrato permite ausencia; una referencia disponible no obliga a comprarla.

### Datos y descubrimiento de estructura

| Elemento vigente | Alcance real y límite |
|---|---|
| Historia/precio | Indicadores diarios y20 sesiones recientes en slim. La historia extensa usada por raw para cálculos no llega íntegra al modelo |
| Familias | Mínimo252 sesiones, pivotes de rango126, gaps estrictos entre barras, AVWAP diario, medias, canales/estructura, y contratos de opciones observados. No es un catálogo de todos los soportes posibles |
| Selección resumida | Raw tiene mínimos de distancia por defecto del5% para gap/rango/AVWAP y reduce a un ganador de cada familia. No aplica igual a mínimo anual, medias u orígenes dirigidos. Es selección upstream, no una regla financiera de ruptura |
| AVWAP | Promedio acumulado del precio típico diario ponderado por volumen. Jerarquía de anclas y observación independiente de fechas anteriores solicitadas. No es VWAP intradía exacto ni coste observado de los actuales propietarios |
| Gaps | Se observa el gap estricto entre high/low de barras contiguas; no todo gap apertura/cierre. Raw contiene bordes/estado que no se preservan íntegros como campos tipados de slim |
| Mercado/sector | Fuerza relativa frente a SPY20/60 como diferencia de retornos, tendencia e investigación macro/sector. No es alpha ajustada por beta. El contexto QQQ/VXN/sentimiento y benchmarks que genera el controller no se congela como paquete equivalente en cada input financiero |

La amplitud de familias del prompt no garantiza igual acceso a cada origen en full/mantenimiento. Un origen existente puede perderse por ranking/transmisión;39 corrige un caso concreto de opciones CURRENT, no la selección universal de candidatos. Los detalles y referencias de código están en el [anexo de estructura](audit_work_20261017/methodology_structure.md).

### Reacciones, volumen y opciones

La reacción histórica usa hasta252 sesiones, agrupa contactos, exige ventanas maduras y comprueba el cierre respecto al nivel/tolerancia y el rebote desde el nivel hasta el máximo de las cinco sesiones siguientes respecto al umbral. Distingue rechazo y rebote y mantiene la base de medición. Ese agregado no mide por sí solo el descenso anterior al rebote, su orden intradía, una operación ganadora o episodios estadísticamente independientes. Se calcula sobre una coordenada horizontal actual; no reconstruye automáticamente la curva histórica del AVWAP ni el OI histórico de esa coordenada.

El perfil de volumen usa126 sesiones y48 bins, repartiendo uniformemente el volumen de cada barra entre precios tocados. Está marcado approximate. Es mapa aproximado de actividad, no volumen real a cada precio, libro de órdenes ni flujo comprador/vendedor. La rúbrica limita a3 sus puntos de perfil diario; hasta16 puntos del componente Volumen/reacción derivan de episodios del precio.

Opciones usa tres vencimientos muestreados, TOP por concentración de gamma y detalle por expiración/quotes;39 añade identidades CURRENT fuera de TOP con las mismas descargas. La muestra no es el mercado completo ni siempre el mismo horizonte: puede incluir vencimiento del día. Presencia en varias expiraciones no prueba persistencia de posiciones entre capturas.

El campo gamma_regime se construye con calls menos puts ponderados por gamma/OI; el input no observa inventario neto dealer. El expected move procede de una prima straddle ATM y escalado temporal según vencimiento; IV/RV compara esa escala con volatilidad realizada y prob_touch usa una cola normal terminal. **Estos nombres no acreditan signo dealer, volatilidad barata, distribución física o probabilidad calibrada de primer toque.** El anexo distingue errores de objeto, aproximaciones y datos que faltan; las propuestas de retirada/corrección no están aplicadas. [Opciones y volumen: fórmulas, evidencia y límites](audit_work_20261017/methodology_volume_options.md).

### Rúbrica, empresa y lectura

La fortaleza suma Estructura25 + Volumen/reacción20 + Opciones25 + Confluencia15 + Durabilidad15. Categorías: débil0–39, moderado40–69, sólido70–84, fuerte85–94 y excepcional95–100, con condiciones adicionales de pilares y sumas. Visibilidad del consumidor desde65 no cambia esos umbrales. Con Opciones0 el máximo es75; aun así se pueden seleccionar compras sin opciones positivas. La escala es convencional y no tiene validación predictiva fuera de muestra demostrada. Notas auxiliares raw y confianza técnica son escalas distintas; ninguna es una probabilidad por compartir números de0 a100.

El contexto permite investigación primaria de noticias, resultados, guía, riesgo y situación empresarial dentro de la llamada vigente. Agenda, memoria fechada y agrupación causal no equivalen a una ficha uniforme de expectativas conocidas antes del evento, realizado y premisas afectadas. Los targets de analistas no son objetivos swing por defecto. Los riesgos antiguos siguen pudiendo ser relevantes aunque no haya un titular nuevo.

El informe público sintetiza resumen, drivers, evento y plan. La extensión inferior es una estimación fechada o null, no stop/garantía/cuantil. ITV5 controla cuándo se exige full, no la vida económica uniforme de una señal. Fecha de revisión, antigüedad de la fuente y horizonte de la conclusión son conceptos distintos.

No se ha demostrado que los pesos, ventanas, distancias, colores o continuidad produzcan mejor resultado económico. Tampoco se ha demostrado lo contrario. La evaluación propuesta separa corrección factual, utilidad de zonas, comprensión del lector y P&L ejecutable, con comparadores, muestra temporal y control de sesgos. [Protocolo pendiente](audit_work_20261017/methodology_evaluation.md). Nada de esta sección autoriza cambiar el comportamiento o reescribir informes históricos.

## Compatibilidades que siguen siendo necesarias

Los recibos históricos conservan su propia política/instrucciones/schema. La selección financiera de versiones es: <=28 v6 en los contratos recientes de esa familia; 29 v7; 30–32 v8; 33 v9; 34 v10; 35–37 v11; >=38 v12. Revisiones semánticas más antiguas conservan sus versiones específicas: no reconstruirlas con esta tabla abreviada.

La retirada de stops 29 y resistencia 35 no autoriza eliminar guardas usadas por recibos anteriores. La herencia exacta de rango/Volumen entre compras desde 28 evita tratar una promoción de casilla como cálculo nuevo; no autoriza promover financieramente una zona por sí sola. Los labels legacy permanecen por compatibilidad y observabilidad.

## Qué se ha demostrado

Último lote natural seleccionado:16-10, revisión 38,45/46 publicados:18 retain,26 update,1 full IBKR; APP bloqueado. 55 llamadas registradas:46 revisiones,8 reparaciones y 1 full; un reintento de lote no equivale a otra llamada. Full 36 del 14-10:46/46 por renovación expresamente solicitada.

Revisión 39 tiene captura técnica real APP y pruebas offline; no se encontró en la muestra una ejecución financiera natural 39. Los resultados 32–38 sí tuvieron ejecuciones posteriores guardadas; eso sustituye la afirmación temporal «aún no hubo un siguiente lote», pero no cierra su calidad financiera ni demuestra efectos causales de cada revisión.

La [auditoría](audit_analysis_system_20261017.md) separa contrato sintético, replay original, captura técnica real, modelo real y resultado financiero. Hay controles sólidos y defectos reproducidos; ningún test offline es una validación de rentabilidad.
