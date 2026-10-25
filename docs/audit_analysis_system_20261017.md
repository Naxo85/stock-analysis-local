# Auditoría independiente del sistema de análisis de acciones — 17-10-2026

**Ejecución y puesta en servicio posteriores (17–18-10-2026):** correcciones adoptadas implementadas, verificadas y activadas para nuevas preparaciones40. Revisión40 activada para nuevas preparaciones el18-10-2026 a las08:17:18 UTC (10:17:18 Europe/Madrid), con lectura de comprobación y sustitución atómica. Publicación manifest-v1, último intento y archivo técnico habilitados; fuentes y tres consumidores compatibles al100%. Configuración SHA25664e54ed9d2e40a47a86538b5af82747ca9f573c00fba0784ee7ca2a28d6ec53e. Mismo Codex local, modelos medium/high, ITV5 y techo6; congelados<=39 intactos. Resolución por hallazgo/propuesta en la [matriz completa](execution_audit_20261017.md) y [evidencia de activación](audit_work_20261017/execution/activation/README.md). Las propuestas inconclusas no se presentan como capacidades ni beneficios validados. Checkpoint previo8034b7a; originales preservados.

**Registro histórico de la fase de auditoría, anterior a la ejecución:** las restricciones y «No aplicado» de este párrafo corresponden a aquella fase; el resultado posterior está en la matriz enlazada arriba.

**Alcance:** árbol local de `E:\stock-analysis-local`, contratos, configuración, prompts ensamblados, pruebas y artefactos originales disponibles. Fecha Europe/Madrid. **Intervención aplicada:** documentación y reproducciones locales aisladas. **No aplicado:** código, configuración, prompts, schemas, tests existentes, políticas, originales, modelos, lotes, recuperación, publicación, despliegue ni cambios externos.

**Ampliación metodológica:** las [secciones 14–20](#14-ampliación-qué-conservaríamos-y-qué-rediseñaríamos) desarrollan la investigación externa, oportunidades y evaluación solicitadas después de la primera auditoría. En aquella fase sus propuestas no estaban implementadas. La evaluación e implementación posterior se registra por ID en la matriz, sin alterar los hallazgos históricos.

Punto de entrada actualizado: [arquitectura](architecture.md). Estado: [relevo](handoff_current.md). Propuestas: [backlog](pending_work_current.md). Investigación reproducible: [datos](audit_work_20261017/data.md), [finanzas](audit_work_20261017/financial.md), [integridad](audit_work_20261017/integrity.md). Estos anexos contienen código de reproducciones, controles contrarios y referencias detalladas; forman parte del informe, no otro backlog.

## 1. Diagnóstico ejecutivo

El propósito actual es coherente: seguimiento empresarial y selección de compras en soportes, con mantenimiento rutinario separado de investigación completa, dos zonas opcionales y continuidad de juicios fechados. No hay fundamento en esta auditoría para volver al diseño original, restaurar resistencia/stops retirados o forzar más casillas. Las decisiones del usuario, las convenciones de la rúbrica y los resultados empíricos son cosas distintas.

**El sistema puede razonar de forma disciplinada sobre una entrada y, aun así, recibir datos que parecen completos sin serlo.** Hay dos defectos con evidencia original especialmente importantes: timeouts IBKR convertidos en feeds vacíos recientes que alcanzaron publicaciones; y volumen de sesión abierta presentado como último día completo en 46/46 inputs del 16-10. También se reprodujeron errores de unidades, agregados de opciones y lado de paredes.

**La integridad funciona mejor dentro de la validación que entre archivos duraderos y publicación.** Se aceptaron en copias una respuesta alterada después de su recibo y un espejo JSON cambiado después de validar. Una revisión pendiente ya validada puede eludir la frescura actual al reanudarse. No se encontró corrupción de ese tipo en los originales contrastados:101 recibos y 91 publicaciones fueron congruentes en los controles ejecutados. Esta contraevidencia limita el diagnóstico, pero no elimina los huecos.

**La frontera financiera tiene dos defectos concretos y una simplificación pendiente.** Se aceptan dos compras idénticas o Washout superior en pruebas full 39; TLN tuvo una reparación real porque una cita CURRENT debía repetirse en otra ubicación, y esa reparación elevó Volumen 13→16 aunque repetir solo la cita validaba 13. Siete de ocho reparaciones del 16-10 se activaron por un certificado de coherencia de texto cuyo objeto todo-null puede equivaler a conservar todo. No debe confundirse ese coste contractual con nueva investigación financiera necesaria.

Hay protecciones bien justificadas: CURRENT separado del ancla full; conservación de fechas; una reparación acotada; no convertir ausencia del TOP en pérdida; fuentes por identidad y alcance; madurez/dirección de reacciones; autoridad de riesgo; datos financieros estructurados antes de render. Deben conservarse al simplificar.

No se encontró validación predictiva fuera de muestra de los pesos, umbrales, ITV5, ventanas de selección o extensiones inferiores. Eso no demuestra que sean malos; impide presentarlos como calibrados. Tampoco existe todavía una estrategia completa de ejecución, tamaño y salida que permita interpretar un P&L como prueba del producto actual.

La documentación se actualizó de forma efectiva. Se retiraron del recorrido vigente las afirmaciones de Web principal, fallback automático, calendario semanal retirado y Markdown como autoridad financiera. Se archivaron las cronologías sin cerrar incidentes originales. Las recomendaciones técnicas de esta auditoría **siguen sin implementar**.

## 2. Método, autorización y límites

Se trabajó en ocho fases con tres investigaciones paralelas y una integración independiente: reconstrucción, criterio financiero, datos/fuentes, evolución, integridad, pruebas/casos, alternativas y documentación. Se empezó por AGENTS y los cuatro documentos canónicos pedidos. Se registró el estado inicial del árbol y huellas de 479 archivos protegidos; había muchos cambios previos y archivos sin seguimiento. HEAD `7b2a401` es del 06-09, por lo que el historial de commits no explica las revisiones de octubre: se contrastaron fuentes, tests, inputs, recibos, logs de despliegue y cronologías, indicando dónde no hay diff histórico fiable.

Los módulos activos y las compatibilidades que los afectan recibieron más atención que Web/archivos retirados. Las pruebas de publicación usan transportes simulados; las mutaciones de payload son copias o memoria. No se confundieron con respuestas reales del modelo. En la primera fase no se hizo acceso a servicios remotos. La ampliación posterior sí consultó literatura pública, sin consultar servicios operativos. Algunas capturas técnicas normales escriben mirror, por lo que ejecutarlas habría salido del alcance offline autorizado.

Tipos de evidencia usados:

| Tipo | Qué acredita | Qué no acredita |
|---|---|---|
| Prueba sintética | Aceptación/rechazo y comportamiento de código bajo condiciones explícitas | Que un modelo produzca esa respuesta ni rentabilidad |
| Replay de original | Compatibilidad del validador con un recibo/caso fechado | Nueva ejecución del modelo, publicación o recuperación real |
| Captura técnica real archivada | Datos/alcance suministrados entonces | Juicio financiero ni estado cloud actual |
| Ejecución real de modelo archivada | Respuesta efectiva, búsqueda/uso/errores de ese intento | Veracidad completa de fuentes o resultado económico |
| Resultado financiero observado | Requeriría precios/ejecución/horizontes y comparadores definidos | No se midió en esta auditoría |

La lectura de código no se convierte automáticamente en política correcta: las discrepancias con requisitos se registran como defectos/propuestas. No se usan precios futuros para juzgar decisiones pasadas ni se verifica hoy una noticia como si eso probara qué podía conocerse entonces.

## 3. Propósito actual y evolución relevante

El sistema nació con generación Markdown, rutas por modelos/días y más campos operativos; hoy esas bases no son una referencia de corrección. La evolución relevante es:

| Cambio | Propósito actual | Evidencia y límite |
|---|---|---|
| Adaptativo y mantenimiento 3+ | Cambiar rutinas sin full por ticker; reservar high para autoridad crítica/ITV | Recibos reales; no demostración automática de ahorro global |
| Semántico 9–15 | Separar datos financieros, procedencia y render | Cálculos/identidades verificables; narrativa no se convierte en teorema |
| Continuidad/autoridad 14–23 | Justificar cambio de CURRENT, distinguir antecedente/live, no pagar full por formato | Pruebas negativas y originales; hay rigidez residual TLN |
| Volumen 25–27/34 | Aritmética verificable, sesión/dirección correctas, no doble techo por distancia | Código y replays; permanece texto viejo en consolidado 35 |
| Vigencia 28/selección 38 | Comprar soportes actuales, permitir ausencia y separar convicción de existencia | Originales favorables y desfavorables; no cuota ni éxito predictivo demostrado |
| Plan 29/35 | Retirar stops/target y después resistencia por preferencia explícita | No restituir esos campos como «corrección» |
| Lectura 30–33 | Investigación interna, informe breve, síntesis causal sin borrar hechos | Proyección tipada; memoria pública/oculta separada, juicio editorial no garantizado |
| Extensión 36/37 | Estimación prospectiva inferior para color/lectura, sin exigir test exacto | Plumbing probado; calibración de estimaciones pendiente |
| Opciones 31/39 | Conservar detalle adquirido y observar origen CURRENT fuera del TOP | Captura técnica real y controles; muestreo no es mercado completo |

No hay regla automática de ruptura por porcentaje/ATR/cierres. **Sí hay convenciones cuantitativas de selección y medida**: ventanas aproximadas 1/2 ATR-EM, diferencia 5 puntos, proximidad~0,35 ATR para mismo bloque salvo independencia, amplitudes preferidas 1/1,5% y límite 2%, reacción 5 sesiones. No confundir la prohibición de ruptura mecánica con ausencia de parámetros.

Pesos correctos: **Estructura 25, Volumen 20, Opciones 25, Confluencia 15, Durabilidad 15**. Categorías y pilares incluyen cortes 70/85/95; visibilidad 65 en Mercado no cambia la categoría sólido 70. Una puntuación no es probabilidad. Tesis, Setup y Fortaleza son ejes diferentes.

El cuaderno estratégico pide separar nota y estado de tesis, pero deja sin definir disparador operativo y ejecución de salida. El schema actual no expone un estado de tesis independiente; no se implementó durante esta auditoría.

## 4. Mapa del sistema real

La [arquitectura actualizada](architecture.md) contiene el recorrido, responsabilidades, componentes y fechas. Síntesis:

`adquisición → raw/slim → preparación/catálogo → contexto/prompt/schema congelados → modelo → validación/reparación → retain/update/full → memoria/ancla → render → publicación/consumidores`.

- Raw calcula indicadores desde OHLCV y cadenas Tradier. Perfil de volumen es una aproximación diaria; reacciones usan sesiones completas. TOP y vencimientos son selección/muestreo.
- Slim reduce la entrada. Opciones 31 conserva quotes/contribuciones; 39 añade observaciones dirigidas del CURRENT tipado en las mismas descargas.
- IBKR proporciona titulares/acciones y estado de analistas; Finnhub interviene en calendario. No hay un dataset fundamental estructurado completo. Investigación pública dentro de la llamada complementa, no transforma un titular en artículo leído.
- Preparación comprueba fuentes/horas, carga CURRENT/ancla/propiedad, congela input/policy/instrucciones. Catálogo vincula identidad con contenido/alcance; el modelo no inventa hashes.
- Medium revisa y puede actualizar; high hace full. La única reparación medium recibe errores reunidos. Repetido contrato inválido no compra high por sí solo.
- Retain conserva finanzas/fechas y registra revisión; update conserva autoridad full; full renueva ancla/ITV. Presentación y extensiones pueden variar sin fingir renovación financiera.
- Publicación multiformato y estado es secuencial. Sheet, reports y móvil leen proyecciones distintas; coherencia completa requiere contrastarlas.

Configuración local 39: gpt-6.1-sol medium/high, investigación habilitada en ambos, ITV5, máximo 6 modelos, límites de 240 s para medium y 1.200 s para high, con arranque y ejecución cronometrados por separado, snapshot 24 h. Luna es alias de rol.

El prefijo 39 efectivo es financiero v12 y diez piezas de contrato; mantenimiento añade daily 35. Full 77.380 caracteres y mantenimiento 86.592; no tokens. Inputs reales38 seleccionados: APP 225.045, AUR 206.078, IBKR triage 216.717, IBKR full 246.970 caracteres. comparison ocupa 90–105 k compactados. Ya hay aliases de deduplicación; no se demostró que esta carga cause errores. Sí se comprobó una contradicción literal de Volumen.

Raw/slim origins 39 y controller solid 65 tienen evidencias guardadas de activación/health/tráfico, pero **no se consultó despliegue remoto 17-10**. Algunas funciones auditadas coinciden por AST con fuentes archivadas de esos builds; eso no verifica todo el runtime actual.

## 5. Hallazgos priorizados

P1 significa corregir pronto por control esencial o dato de decisión; P2 defecto/acotación relevante; evaluación/producto se presenta aparte. No son señales para operar acciones. Cada hallazgo se amplía en su anexo, con código ejecutable cuando procede.

Convención de rutas de esta sección: los módulos de runner citados sin carpeta están en `src/local_runner/`; raw/main.py y slim/main.py corresponden a `gcp_functions/support_resistances_raw/main.py` y `gcp_functions/support_resistances_slim/main.py`; los prompts están en `prompts/`. Las rutas completas, artefactos y reproducciones figuran en los anexos.

### H01 · P1 · El feed puede declarar cobertura reciente aunque la consulta no terminó

**Clasificación:** defecto demostrado en originales; confianza alta. **Impacto:** mantenimiento admite una aparente ausencia de noticias/acciones no establecida por el proveedor. También falta representación fiable de hasMore/saturación.

**Evidencia:** `ibkr_analyst_probe.py:138-144` convierte None en []; ib_insync instalado `ib.py:2142-2161` retorna None tras timeout; `ibkr_news_update.py:279-289` marca ok/truncated=false/hora nueva. Analistas también avanzan as_of en `ibkr_analyst_update.py:103-117`. La señal hasMore se descarta en la librería; un lote de 300 titulares sigue truncated=false.

**Caso real:** MU/CRWV/IBKR 15-10, fuente `logs/source_updates/2026-10-15/12-01-14`, inputs de `logs/batch/2026-10-15/12-01-08`: timeout, count 0/status ok, medium sin web_search, publicación de MU/CRWV retain e IBKR update. OKLO 14-10 aporta caso analistas. 94/3.128 archivos log de fuentes de octubre contienen ese timeout (53 news,41 analysts); no son 94 análisis independientes ni 94 noticias perdidas. Los 92 logs de fuentes del 16-10 no lo muestran. No se sabe qué noticia, si alguna, se omitió.

**Alternativa/guarda:** vacío exitoso es válido; excepción normal y contenedor antiguo sí se rechazan. El problema es crear un éxito nuevo a partir de fallo, no reutilizar siempre last_good de forma indebida.

**Propuesta y aceptación:** preservar estado terminal/error/hasMore; no avanzar latest/as_of sin éxito; paginar o marcar cobertura incompleta. Timeout/error y truncamiento no llegan como fuente completa; vacío terminado sí. Usar ruta premodelo existente, sin nueva llamada financiera. [Datos D1/D8 y reproducción](audit_work_20261017/data.md).

### H02 · P1 · La sesión abierta se etiqueta como volumen del último día completo

**Clasificación:** defecto demostrado; confianza alta. **Alcance:** 46/46 inputs 16-10, sin demostrar perjuicio económico.

`raw/main.py:2635-2655` usa days[-20:] y days[-1] sin filtrar sesión abierta; `slim/main.py:150-151` lo publica como volume_last_complete_day. APP captura 16:14:23 UTC con volumen 16 oct 932.192/ratio 0,194; price_history.last_session es 15 oct y ese bloque sí es correcto. Recalculando solo con 20 barras cerradas ya congeladas, cambia el componente auxiliar D_volume_tape en 42/46 casos; AMAT pasa de ratio 0,471/-5 a 1,811/+10. **No es un recálculo de Fortaleza ni prueba de que el modelo usara ese componente.**

**Contraevidencia:** historia/reacciones sí excluyen el día en curso; razones de varios modelos se basan en la barra cerrada 15 oct. No atribuir toda decisión a volumen parcial.

**Propuesta:** conjunto temporal compartido para campos llamados completed/last_close, intradía separado. **Aceptación:** variar barra abierta no cambia ese ratio/indicador; historia sin barra abierta conserva resultado y el cierre real tiene contrato explícito. Sin repuntuar originales. [Datos D2](audit_work_20261017/data.md).

### H03 · P1 · Respuesta y bundle no quedan ligados de extremo a extremo al artefacto validado

**Clasificación:** defecto reproducido de detección de corrupción/edición local; impacto potencial alto; confianza alta. **No se encontró corrupción original en la muestra.**

`adaptive_codex.py:168-171,235-247` persiste hashes de entrada/prompt/schema, no respuesta. `adaptive_stage.py:303-322` reabre response; `semantic_binding.py:40-50` lo enlaza de nuevo en memoria. En copia IBKR 16-10, cambiar solo summary.narrative mantiene recibo/eventos intactos y pasa reuse_only/full_document, con modelo prohibido.

La misma responsabilidad incompleta aparece después: `adaptive_stage.py:750-780` no liga el bundle a la revisión. En CAT copiado, cambiar solo espejo plan.entry 728–732→800–810 manteniendo semantic_report/MD permite alcanzar upload simulado; memoria no detecta ese espejo. reference_key no abarca todos los derivados.

**Guarda/alternativas:** binding durante una llamada, bases/ancla/memoria y contrato exacto sí protegen. 101 recibos/91 payloads originales son congruentes. Archivos locales confiables reducen probabilidad, pero no detectan copy/restore equivocado. Un clasificador de prosa no resolvería procedencia.

**Propuesta:** digest durable de respuesta y manifiesto del bundle validado; comparación de legacy con agent_message original cuando sea posible, sin reescribir congelados. **Aceptación:** mutaciones independientes response/plan/decision/semantic/MD/HTML fallan antes de escritura; originales y reintentos idénticos pasan sin modelo adicional. [Integridad INT-01, R1/R2](audit_work_20261017/integrity.md).

### H04 · P1 · Una revisión validada puede saltarse la frescura al reanudarse

**Clasificación:** defecto reproducido; impacto condicionado a publicación tardía; confianza alta; ningún caso histórico tardío identificado.

`adaptive_stage.py:421-427` devuelve review.ok antes de data_ready, incluso reuse_only usado por recovery; publish no comprueba frescura. Copia CAT 16-10 pendiente, reloj 23-10: data_ready directo rechaza, analyze+publish llegan al transporte simulado con 0 llamadas data_ready. generated_at sigue 16-10: **no es redatado**, es nueva admisión a publicación con input caducado.

**Guarda/alternativa:** base/ancla iguales y ausencia de revisión más nueva protegen autoridad. La propiedad actual se comprueba en recover_adaptive_receipt --execute, no en publish ordinario; esas guardas tampoco prueban que mercado/fuentes no cambiaron. Recovery sin review validado sí comprueba frescura. Completar un commit parcial inmediato puede ser legítimo y necesita distinguirse.

**Propuesta/aceptación:** comprobar frescura antes del primer compromiso tardío y definir aparte finalización idempotente de compromiso parcial. Candidate>24 h no inicia publicación; inmediato/partial legítimo sí; conservar ITV original/fechas y ninguna nueva llamada por caducar staging. [INT-02/R3](audit_work_20261017/integrity.md).

### H05 · P2 · Dos zonas financieramente incompatibles pasan la ruta full

**Clasificación:** defecto de contrato demostrado; impacto potencial medio/alto; confianza alta; no incidencia publicada encontrada.

`semantic_report.py:467-471` retorna para>=35 después de validar cada zona, sin relación entre ambas. Financiero v12:52,79-83 exige Washout distinto/inferior. AUR full 36 proyectado sintéticamente 39: duplicar Entry 4,97–5,03 como Washout pasa; AMD intercambiar bloques 531–535 y 580–583 también pasa hasta publication_fields.

**Contraevidencia:** 45 publicaciones 16-10,26 con ambas zonas,0 duplicadas/solapadas/invertidas. No falla la generación en todos los casos. Proximidad puede exigir juicio sobre estructuras independientes.

**Propuesta/aceptación:** relaciones inequívocas compartidas por ambos roles: duplicado/inversión rechazados, ausencia/solo Entry/promoción válida preservadas, sin convertir 0,35 ATR en veto universal ni forzar casillas. [Finanzas F1](audit_work_20261017/financial.md).

### H06 · P2 · TLN: cita autenticada en otra ubicación provoca reparación y repuntuación

**Clasificación:** defecto demostrado de contrato de herencia; confianza alta. **Impacto observado:** repair real y Volumen 13→16/total+3; no prueba de que 13 o 16 sea económicamente mejor.

TLN 16-10 promueve Washout 349,5–351,5 y conserva 13. s38 identifica el CURRENT exacto y está en change_review.previous_evidence, como pide daily 35:59-65. `volume_arithmetic.py:59-77,139-152` solo reconoce herencia si se repite en block.evidence. Rechazo único: select_profile_and_reaction_sources. Añadir solo s38 ahí valida 13 sin cambiar cifras/texto/juicio; repair real añade cita y recalcula 16 justificándolo por promoción de casilla.

**Guarda:** identidad CURRENT, rango/Volumen exactos y autoridad son necesarias; ancla vieja no sirve. El problema es duplicar ubicación, no retirar esa guarda. La reparación no demuestra que recalcular fuera necesario.

**Propuesta/aceptación:** resolver procedencia tipada pertinente o declarar inequívocamente el contrato; indicar corrección mínima posible sin dirigir una nota. Mismo original validable con su fuente; solo ancla/stale/rango o Volumen distinto siguen sin herencia. Sin corregir publicación retrospectivamente. [Finanzas F2/repro](audit_work_20261017/financial.md).

### H07 · P2 · Expected move cambia de unidad por una heurística de magnitud

**Clasificación:** defecto reproducible; confianza alta; no incidencia en valores presentes del lote 16-10.

Raw ya produce porcentaje en `main.py:794-822`; slim `main.py:162,578-591` multiplica por 100 si abs<=1:0,75%→75%,1%→100%,1,01%→1,01%. Otro campo por expiración sí usa fracción, lo que explica la intención pero no hace válidas unidades indistintas.

**Propuesta/aceptación:** unidad por campo/versión, no otra heurística. Probar 0,01/0,75/1/1,01/10,29 y coherencia 100*dólares/spot; valores grandes y campos por expiración correctos. [Datos D4](audit_work_20261017/data.md).

### H08 · P2 · Filtro de gamma elimina contratos para métricas que no necesitan gamma

**Clasificación:** defecto reproducible; confianza alta en código, frecuencia real desconocida.

`raw/main.py:1993-2021` descarta contrato sin gamma y convierte OI ausente en 0. Ese parser alimenta OI total, straddle/expected move y maxpain además de TOPgamma. Wire sintético: call OI 100/gamma 0,02, put OI 900/gamma ausente produce ratio 0 en vez de 9 observado. Directed 39 conserva correctamente put 900/gamma unknown.

Esto **no** denuncia la diferencia legítima entre TOPgamma-elegible y OI dirigido de todos observados. Denuncia presentar otras métricas después del filtro sin declarar cobertura. No hay XML original suficiente para medir contratos reales perdidos.

**Propuesta/aceptación:** parser conserva campos/identidad, consumidores eligen elegibilidad y anotan exclusiones; unknown distinto de 0; OI/quotes válidos no dependen de gamma; TOP en contratos completos exacto. [Datos D5](audit_work_20261017/data.md).

### H09 · P2 · Pared superior genera distancia inferior cero y proximidad falsa

**Clasificación:** defecto en originales; confianza alta; impacto en indicador auxiliar, no nota financiera demostrada.

`raw/main.py:4094-4104` calcula una lista inferior pero procesa todas las paredes con abs(min(0,d)); cualquier superior pasa a 0 y activa PUTWALL_NEAR +5 (:4149-4151). En 6/46 inputs 16-10, la conversión genera un falso PUTWALL_NEAR +5: AUR,IONQ,LRCX,PLTR,QBTS,RKLB. PLTR quote 187,255 tiene todos los puts del TOP 190–200 y nearest_put_wall_dist_pct=0.

**Alternativa descartada:** ni medir cualquier pared cercana explica que una superior arbitrariamente distante sea cero. Controles inferiores 2%/8% funcionan.

**Propuesta/aceptación:** seleccionar lado antes de distancia; solo superiores da ausencia/desconocido inferior, inferior 8% no activa, inferior 2% sí. Conservar ranking/fuente y no repuntuar informes. [Datos D3](audit_work_20261017/data.md).

### H10a · P2 · Captura reciente no garantiza datos recientes

**Clasificación:** defecto de admisión reproducible; confianza alta; no proveedor stale original identificado en la muestra del 16-10.

`technical_preparation.py:6-33` acepta una sola barra de enero dentro de un snapshot de octubre; `adaptive_stage.py:238-253` comprueba fechas de envoltorio. Raw as_of es serialización, sin fecha/base de quote elegida.

**Guarda:** OHLCV malformado/duplicado sí se rechaza; no sustituye la fecha del dato. Una IPO o festivo puede justificar menos historia, por lo que exigir 20 barras sin contexto tampoco es solución.

**Propuesta/aceptación:** captured_at, quote_at, history_last_session y sesión esperada separados. Datos antiguos no rejuvenecen con envoltorio; casos IPO/festivo/cierre y datos válidos pasan. Riesgo: bloquear historia legítimamente breve o una sesión aún no publicada si se impone una fecha universal. [Datos D6](audit_work_20261017/data.md).

### H10b · P2 · La selección de cotización admite libros inválidos

**Clasificación:** defecto reproducible; confianza alta en código; frecuencia real desconocida. `raw/main.py:1144-1153` acepta midpoint bid 0/ask 100/last 99→50 y libro cruzado. Cero/cero puede fallar más adelante en vez de usar last válido. No se encontró un libro inválido original en la muestra del 16-10.

**Protección/alternativa:** rechazar precio final no positivo limita algunos casos, pero no detecta un midpoint positivo de un libro inválido. Last tampoco es siempre una alternativa adecuada: debe conocerse su fecha y procedencia.

**Propuesta/aceptación:** seleccionar quote con calidad, fecha y procedencia explícitas. Libro inválido usa alternativa válida/fechada o falla; libro válido conserva resultado. Riesgo: sustituir automáticamente una cotización actual por un last antiguo. [Datos D7](audit_work_20261017/data.md).

### H11 · P2 · Publicación multiformato puede quedar parcialmente visible

**Clasificación:** comportamiento demostrado ante fallo inyectado; riesgo operativo plausible, incidencia/frecuencia real no establecida.

`gcs_uploader.py:136-174,215-224` escribe MD/HTML/JSON/snapshots/mirror secuencialmente; luego ancla/current/review. Fallo simulado en tercera copia deja MD/HTML nuevos y JSON viejo. Lock es local, sin CAS multi-host. `analysis_state.py:61-81` escribe fallback de ancla antes de subir: fallo deja ancla local adelantada; current usa orden contrario.

**Contraevidencia:** excepción visible, no published_at; reintento de staging idempotente probado y 91 payloads coherentes. Una instalación/escritor reduce riesgo, no lo elimina entre formatos.

**Alternativas:** aceptar consistencia eventual con estado explícito, o versiones inmutables con manifest/puntero final y CAS. No más validadores financieros por defecto. **Aceptación:** fallos después de cada escritura dejan versión completa anterior/nueva o pendiente visible; ancla/current avanzan solo según commit definido; retries sin modelo/fechas nuevas; dos escritores si ese alcance se soporta. [INT-03/R4](audit_work_20261017/integrity.md).

### H12 · P2 · Último intento fallido y último informe válido no llegan separados al lector

**Clasificación:** defecto de integración/observabilidad; caso APP 16-10; confianza alta.

`adaptive_stage.py:843-846` guarda failure local; `run_batch.py:2351-2371,2648-2663,2712-2717` cierra intento sin publish ticker. Lote/orden conservan fallo. Móvil deriva last_attempt_status del latest (`mobile_api/projection.py:49-53,72-83`); Sheet lee mirror válido, reader normal omite error/status. El productor conserva el latest previo; el CURRENT original de APP estaba fechado 15-10. Así, algunos consumidores no pueden conocer bloqueo 16-10. Esta conclusión no procede de una lectura remota 17-10.

**No es ocultación total ni redatado:** preservar el informe anterior es correcto; el fallo sí está en logs/progreso. El test consumidor con latest.failed presupone un productor que adaptativo no tiene.

**Propuesta/aceptación:** estado de intento separado enlazado al último informe válido; end-to-end válido→blocked→éxito en productor/consumidores mantiene cifras/fecha y muestra/quita aviso correctamente. [INT-04](audit_work_20261017/integrity.md).

### H13a · P2 · Contradicción activa de Volumen

**Clasificación:** contradicción literal demostrada; confianza alta. Impacto financiero plausible, sin causalidad observada en una nota concreta.

`adaptive_revision35.md:207-212` conserva stronger<=3%gate para superar 15; overlay 34:7-11 y financiero 12/código eliminan ese techo. Ambos aparecen en full/mantenimiento 39. El orden/override ofrece salida correcta, pero obliga al modelo a reconciliar texto incompatible. No se atribuye una nota errónea concreta a ello.

**Propuesta/aceptación:** una definición financiera vigente por composición versionada, preservando contratos congelados. El prefijo efectivo de ambos roles debe contener una sola regla de Volumen sin perder controles de muestra, magnitud, recencia o dirección. Riesgo de consolidación: eliminar una guarda todavía necesaria. [Finanzas F3](audit_work_20261017/financial.md).

### H13b · P2 · Certificado de coherencia: coste contractual sin prueba de verdad

**Clasificación:** decisión discutible; coste observado y reproducción demostrada; confianza alta sobre el contrato, limitada sobre su utilidad financiera.

7 de 8 repairs 16-10 fueron plan_coherence,1 TLN Volumen. GEV original pasa cambiando solo plan_explanation:null por objeto con todos los campos null, sin nuevo texto/cifras. El certificado fuerza declarar revisión de dependencias, pero no comprueba su verdad. No es clasificador de prosa y no debe rellenarse automáticamente.

**Propuesta/aceptación:** un único contrato de cambios/dependencias. Medir repairs y contradicciones reales, sin eliminar revisión/autoridad ni rellenar certificados automáticamente. Conservar controles negativos de explicación contradictoria y positivos de herencia exacta. La simplificación no debe confundir declarar una revisión con haberla realizado. [Finanzas F4](audit_work_20261017/financial.md).

### H14a · Evidencia · La calidad financiera sigue sin evaluación empírica suficiente

**Clasificación:** falta de evidencia empírica; confianza alta sobre lo hallado en el repositorio, sin concluir que los criterios sean incorrectos.

No se halló calibración fuera de muestra de rúbrica, ventanas, ITV5 o extensión inferior. Varias familias comparten precio/volumen y no son observaciones estadísticamente independientes. La precisión de una cota no equivale a confianza. El verde puede comunicar más certeza de la disponible; requiere evaluación de comprensión/resultado, no margen universal.

**Contraevidencia/límite:** pruebas de cálculo y casos de razonamiento coherente sí existen; acreditan esas preguntas, no la utilidad predictiva. No se midió rentabilidad ni se usaron resultados futuros para juzgar originales.

**Propuesta/aceptación:** evaluación de sección 10, con denominadores, comparadores e incertidumbre predefinidos. No presentar ordinales como probabilidad ni introducir umbrales nuevos sin justificación. Riesgo: confundir selección retrospectiva o cambios de mercado con mejora causal. [Finanzas F5](audit_work_20261017/financial.md).

### H14b · Producto · Falta definir y representar el estado de tesis separado de su nota

**Clasificación:** carencia de producto por definir; confianza alta sobre el contrato actual. `semantic_report.py:114-125` expone notas/motivos/narrativa; riesgo thesis_change es interno. El acuerdo del cuaderno pide eje separado de estado de tesis, pero el disparador operativo sigue abierto.

**Protección/límite:** las guardas de deterioro y autoridad full continúan. La ausencia de ese campo no demuestra que se ignore todo riesgo empresarial; impide exponer el estado separado acordado.

**Propuesta/aceptación:** definir semántica, evidencia, consumidor y actualización antes de cambiar campos/acciones. No inferir tesis rota solo de nota ni implementar venta automática como corrección documental. Riesgo: convertir una definición pendiente en una regla de ejecución no autorizada. [Finanzas F6](audit_work_20261017/financial.md).

### H15 · Mantenibilidad · Documentación y estado reproducible divergían

**Clasificación:** discrepancias documentales demostradas; corregidas en los documentos de sección 12. Riesgos de reconstrucción/deploy y universo siguen abiertos.

README, batch, arquitectura y operations mezclaban Markdown libre, Web principal, fallback y calendarios retirados. Handoff/codex_analysis contenían muchos «Current/vigente» históricos y full 35«EN CURSO» pese a summaryfinal 46/46. Se corrigió descripción, no código ni política.

La ruta AGENTS «todos»/--from-gcs sigue apuntando a tickers.json, mientras menú Mercado usa tickers_market.json. Core --config-gcs no actualiza noticias/analistas sin flags, a diferencia de Mercado; se explicitó. No se resolvió intención del usuario sustituyendo universos.

El árbol acumulado no está reflejado en commits; buildspatch sobre imágenes activas no equivalen a desplegar todo el repo. Un test 34 espera revisión 34/35 y falla con 39; no ajustar producción para satisfacerlo.

**Propuesta/aceptación:** commits/manifiesto reproducibles, tests por contrato/revisión, documentación vigente única. Resolver universo como decisión explícita futura. La auditoría deja baseline y archivo histórico; no cierra la deuda operativa.

## 6. Clasificación de parches e interacciones

| Mecanismo y problema original | Estado actual y clasificación | Qué conservar / qué simplificar |
|---|---|---|
| CURRENT/ancla para no renovar ITV en mantenimiento | Mejora integrada; 44 mantenimientos naturales conservan época | Separación, hashes/fechas; no fusionar ambos objetos |
| Identidades de fuentes frente a índices adivinados | Protección necesaria; reordenación conserva identidad | Scope/content, antecedentes fechados y copia por código |
| Observación dirigida 23/39 ante ausencia en ranking | Mejora integrada de adquisición,39 financiero aún pendiente | Muestreo y estados explícitos; no available→retain |
| Detalles opciones 31 | Mejora integrada: conserva información adquirida | No inferir liquidez por quote presente; parser agregado H08 pendiente |
| Madurez/dirección/calibración 26/27 | Protección necesaria de medida | Sesiones completas y dirección; no usar como confirmación obligatoria |
| Fórmula 34 contra doble techo | Mejora integrada de cálculo, integración textual incompleta | Mantener controles históricos; retirar regla vieja en futura composición |
| Herencia compra→compra | Compatibilidad justificada, ubicación de cita rígida H06 | Mismo CURRENT/rango/Volumen, no ancla; una resolución de procedencia |
| Ausencias/selección 22/28/38 | Cambio legítimo de producto/criterio | Sin cuotas, vigencia positiva; cierre mínimo geometría H05 |
| Extensión 36/37 | Función de presentación con hipótesis financiera | Misma llamada, rango/fecha/fuentes; evaluación de cota pendiente |
| Reader 32/33/35/38 | Mejora integrada de presentación | No borrar hechos ni redatar, fallback editorial conservador |
| Normalización/certificado de textos | Protección + complejidad redundante parcial | Revisión explícita, no verdad por wrapper; simplificación H13 |
| Una reparación | Protección razonable contra bucles/coste | No full por rechazo mecánico; agrupar errores independientes |
| Timeouts/recibos 27/capacidad | Protección necesaria, pruebas positivas/negativas | Ambigüedad visible, sin sustitución; completar frontera durable H03/H04 |
| Publicación/recovery de staging | Recuperación justificada, consistencia temporal incompleta | Originales intactos, reintento exacto; definir commit H11 |
| Históricos<=38 | Compatibilidad necesaria, no deuda eliminable sin más | Versiones exactas; reducir ramas solo con archivo/replay equivalente |

Interacciones relevantes: H01 puede hacer que un retain correcto para su entrada parezca mejor informado de lo real. H02/H08/H09 pueden contaminar contexto aunque la rúbrica final sume bien. H06/H13 producen llamadas y cambios que una estadística final de éxito no distingue. H03/H04/H11 afectan el paso entre candidato válido y objeto consumido. H12 impide que parte de los lectores vea esa degradación operativa. Por ello no basta corregir un prompt ni añadir otro validador de JSON.

## 7. Pruebas y casos reales contrastados

Suites focalizadas concluidas: **350 tests aprobados y 1 fallido** (59 operación+71 datos+66 finanzas+154 integridad); 184 subtests aprobados reportados por las baterías que los contabilizaron (46+5+133). No se suman ejecuciones inconclusas ni pruebas históricas citadas por documentos. Finanzas tuvo un timeout inicial sin resultado utilizable; se obtuvo después resultado acotado. La primera salida de pruebas de raíz se perdió por reinicio del runtime de herramientas y se repitió para conservar registro; se cuenta una sola vez.

El fallo `tests/test_volume_rubric_v34.py:231` exige configuración 34 o 35 frente a 39 vigente. Es expectativa obsoleta de activación, no demostración de cálculo 34 incorrecto. No se modificó test/config ni se ocultó por deselect. No se afirma que toda la suite del repositorio pase: se eligieron pruebas por preguntas y se inspeccionaron mocks/fixtures.

[Resultado operativo registrado](audit_work_20261017/root_tests.txt), [argumentos/exit](audit_work_20261017/root_tests_result.json); resultados detallados y reproducción en los tres anexos.

| Muestra | Selección y denominador | Resultado comprobado / límite |
|---|---|---|
| Full 36,14 oct 16-07-07 |46 tickers por petición expresa |46 publicados,46 calls,0 retry; no 46 escaladas |
| Natural 38,16 oct 15-58-24 |46 tickers, incluye fallos |45 publicados:18 retain/26 update/1 full; 55 calls:46 triage/8 repair/1 report; 1 retry lote |
| Ambos corpus anteriores |92 ticker/ejecución,91 publicaciones; 101 recibos |0 desajustes input-response-eventos; 91 memorias/proyecciones congruentes; 81 MD de staging exactos |
| Natural 38 retain |18 casos |Fechas/precio/slim/modelo exactos; no informe rejuvenecido |
| Natural 38 mantenimiento |44 casos |Ancla/época exactas; 45 publicados guardan latest_review con snapshot nuevo |
| APP 38 |Un fallo conocido |Reconoce TOP≠desaparición y bloquea; 39 captura posterior no recupera original |
| AMD/ASML/CCJ |Retain favorable |Razona sobre penetración/recuperación de sesión 15, no simple cruce |
| NVDA/SPCX/AUR |Promoción o cambio limitado |Puede promover conservando componentes y actualizar motivos sin repuntuar |
| IBKR 38 |Único full natural |Escala por resultados publicados/premisa protegida, no mera cercanía calendario |
| TLN/GEV |Reparaciones adversas |Reproducciones distinguen cita/certificado de cambio financiero necesario |
| MU/CRWV/IBKR 15 oct |Casos feed defectuoso |Timeout→vacío→modelo→publicación, sin afirmar noticia material ausente |
| AUR/USAR históricos |Memoria corregida y contrato nullable |Replays y controles negativos; no recuperación real nueva |
| Originales ausentes full 36 |9 escenarios revisados en tests38 |Conservación/autenticación; fixture no decide si se debía comprar |
| Captura APP origins 39 |16 oct 21:07:48 UTC |Put 255 fuera del TOP llega; verificación técnica, no nueva ejecución financiera |

[Inventario de9lotes seleccionados](audit_work_20261017/batch_inventory.json) incluye revisiones 25/26/27/28/29/31/35/36/38. No se agregan como tasa de éxito universal: universo compartido, full solicitados, cambios rápidos y reintentos sesgan comparación. Los contadores de presupuesto de ese inventario son entradas de calls, no necesariamente todos los intentos históricos; failed_call_history requiere tratamiento aparte.

Qué revelan los tests: fuentes/memoria/base/propiedad/capacidad tienen negativos útiles, incluyendo procesos compartiendo admisión. Fixtures de extensión como lower*.987654321 prueban plumbing, no pronóstico. Fixtures de decoder failed pueden asumir un productor inexistente H12. Tests que fijan revisión activa envejecen. El valor está en qué hipótesis refutan, no en el número.

## 8. Carencias de datos, metodología y observabilidad

- No se conservan todas las respuestas wire/cadenas/252 OHLCV utilizados; un hash no reconstruye datos. Impide auditar pérdidas/ajustes del proveedor retrospectivamente.
- Ajustes de splits, moneda, deliverable/multiplicador contractual y base de quote no están explícitos en slim. Raw supone 100 por contrato; no se probó que contratos reales de la muestra fueran ajustados.
- Se considera día anterior al snapshot UTC como cerrado; puede omitirse una sesión ya cerrada esa tarde. Expiración se compara por fecha, sin hora contractual. No inventar cutoff universal.
- TOP 3 expiraciones/5 strikes y filtros de familias limitan observabilidad; dato fuera de ranking no implica inexistencia. Vista OI 60 DTE parcialmente no llega a slim; es pérdida de cobertura ya adquirida, no razón automática para ampliar contexto.
- Titulares son pistas; varias acciones por firma se condensan en last_event/target_last_event. Ausencia en ese resumen no demuestra ausencia de toda noticia o acción.
- No hay balance/earnings estructurado completo; investigación web y autoridad fechada importan. Su trazabilidad no equivale a verificación independiente de cada afirmación.
- Muestreo de soportes, medida histórica y selección modelo pueden compartir sesgo de supervivencia/selección; cinco sesiones no acredita causalidad del nivel.
- No hay métricas de calibración, falsos retain, cambios innecesarios y abstención con adjudicación independiente mantenidas como evaluación de producto.
- Frontera entre último informe válido y último intento/commit necesita responsabilidad única; un JSONstatus no resuelve todas las vistas.

Cada carencia exige efecto proporcional: incertidumbre explícita para cobertura parcial no esencial; limitar confianza cuando evidencia es débil; impedir un cálculo si falta unidad/base; bloquear admisión si una fuente requerida no terminó. No penalizar automáticamente cada componente por la misma falta ni escalar para que un modelo mayor invente el dato.

## 9. Qué funciona y conviene conservar

La contraevidencia examinada apoya confianza acotada en:

- Conservación de fechas y autoridad entre 18 retains/26 updates y ancla full.
- Identidades exactas del catálogo y rechazo de fuentes históricas como origen vivo.
- Rúbrica aritmética de Volumen cuando la pareja fuente/calculada es aplicable; dirección y madurez diferenciadas.
- Investigación en la misma llamada y memoria que no publica cada búsqueda.
- Rechazo APP sin inferir desaparición por ranking; adquisición 39 dirigida sin descarga adicional por consulta.
- Datos financieros separados del render, ausencia legítima de zonas, selección editorial conservadora ante metadatos inválidos.
- Un solo repair, no fallback automático, evidencia de timeouts y reducción compartida de concurrencia.
- Recuperaciones que preservan originales y compatibilidades versionadas, aunque requieren cerrar H03/H04.

No retirar estas guardas para reducir fallos visibles. El objetivo es eliminar ambigüedad/redundancia y hacer fieles los contratos de adquisición y publicación.

## 10. Alternativas y plan de mejoras

| Orden | Propuesta | Tipo / impacto / esfuerzo orientativo | Dependencias y riesgos |
|---|---|---|---|
|1|Terminación/cobertura IBKR y volumen cerrado H01/H02|Corrección, alto, bajo-medio|Conservar vacío válido/last_good; revisar entradas sin alterar originales |
|2|Manifiesto/digest duradero + frescura antes del commit H03/H04|Corrección de integridad, alto, medio|Recibos legacy, reintentos parciales y autoridad; no invalidar recuperación legítima |
|3|Relaciones entre compras y herencia H05/H06|Corrección de contrato, medio-alto, bajo-medio|No añadir veto financiero arbitrario ni obligar nueva nota |
|4|Unidades/parser/lado/quote/frescura H07–H10|Correcciones de datos, medio-alto, medio|Contratos/consumidores versionados; cambios de métrica no autorizan repuntuación automática |
|5|Intento separado y commit multiformato H11/H12|Integración/simplificación, alto, medio-alto|Elegir consistencia eventual explícita o puntero atómico; lectores compatibles |
|6|Composición única de prompts/cambios H13|Simplificación sin criterio nuevo, medio, medio|Congelados exactos; controlar riesgo de perder una guarda al consolidar |
|7|Baseline de código/despliegue/tests H15|Mantenibilidad, alto, medio|No mezclar árbol histórico ni desplegarlo accidentalmente |
|8|Estado de tesis y evaluación H14|Producto/metodología/experimento, alto potencial, variable|Definición del usuario, cohortes y evidencia antes de cambiar reglas |

Esfuerzo relativo, no presupuesto prometido. No se propone más llamadas de modelo como solución por defecto. Un contrato de dato/commit único suele proteger mejor que varias excepciones distribuidas. Consolidar prompts es recomendable para legibilidad, pero no debe alterar el criterio sin revisión explícita.

### Cómo evaluar utilidad futura, sin ejecutar el experimento

1. Registrar prospectivamente todas las preparaciones naturales y el universo disponible entonces, incluidos blocked/failed y retirados. Separar tickers de intentos, llamadas, repairs y revisiones de la misma zona.
2. Definir antes resultados y horizontes: error factual, retraso en detectar riesgo empresarial, juicio exante de vigencia/materialidad, visita/penetración/recuperación, excursión adversa/favorable y comportamiento de extensión. No elegir horizonte después de ver el rebote.
3. Comparar con plan conservado y referencia técnica sencilla acordada; para calidad de full/mantenimiento usar muestra ciega equilibrada de éxitos/fallos/ausencias. Una comparación contra full adicional requeriría autorización/coste propios y no es necesaria para corregir defectos deterministas.
4. Jueces ciegos al modelo/revisión y futuro para corrección exante; resultados posteriores se miden aparte. Desacuerdos/error de adjudicación se conservan.
5. Cohortes cronológicas, prueba fuera de muestra, estratos por liquidez/régimen/sector y control de correlación de observaciones. Incluir universo que desapareció; evitar supervivencia, lookahead y contaminación de selección.
6. Medir calibración ordinal de fuerza y abstención, estabilidad útil frente a inercia, falsas retiradas/cambios sin motivo y cobertura de riesgos. Registrar consumo/latencia con recibos, cache y reintentos, no con deltas de quota agregada.
7. No calcular rentabilidad de «la estrategia» sin acordar entrada ejecutable, tamaño, salida, costes, slippage, divisa y horizonte. El producto actual no los define todos y retiró stops/target; proponerlos es un cambio de producto aparte.
8. Fijar criterios de aceptación, periodo/denominador e incertidumbre antes de experimentar. Varias revisiones simultáneas/mercado cambiante impiden atribuir causalidad a una política por comparar dos lotes.

## 11. Matriz de cobertura y cierre por evidencia

Estados: **comprobado** significa pregunta acotada contrastada, no área perfecta; **parcial** identifica límite material; **pendiente** requiere evidencia no disponible/no autorizada.

| Área / fases | Revisado | Comprobado | Parcial o pendiente |
|---|---|---|---|
| Propósito/config/rutas 1 | AGENTS,canónicos,config,runner,worker |39 local; 38 natural; modelos/esfuerzos; universos distintos | Intención «todos»/Mercado; host/runtime remoto actual |
| Raw/slim 1/3 | Productores,captura 39,46 inputs | H02/H07–H10; directed 39/estados; 71 tests | Wire completo, ajustes, exhaustividad proveedor |
| Fuentes informativas 2/3 | Adapters,librería instalada,logs,inputs | H01 real; None y 300 sintéticos | Noticias concretas omitidas; recuperación posterior de intervalos |
| Catálogo/contexto 1/3 | Identidades,pointers,aliases | Reordenación/valores/antecedentes; composición efectiva | Pertinencia semántica completa de cada fuente |
| Finanzas 2 | Prompt compuesto,schemas,validadores,casos | H05/H06/H13; pesos/cálculo; decisiones favorables | Calidad predictiva/causal, todas las narrativas |
| Parches/historia 4 | Revisiones influyentes y recibos | Clasificación/interacciones/compatibilidad | Git posterior 06 sep incompleto; causalidad de cada mejora |
| Memoria/autoridad 5 | CURRENT/ancla/ownership/ITV/recovery |101 recibos 91 payloads; 18 retain 44 mantenimientos; H03/H04 | Corrupción/fallo remoto real no observado; multi-host |
| Publicación/lectores 5 | Uploader/controller/reports/móvil | Fallo inyectado H11; brecha H12; parsers locales | Estado vivo GCS/Sheet/APK, frecuencia intervalos mixtos |
| Tests/casos 6 | Suites/mocks/fixtures/originales |350 pass 1 fail; reproducciones/oposiciones | Suite completa no ejecutada; no cifra de rentabilidad |
| Alternativas 7 | Datos/metodología/producto/operación | Plan separado por tipo/coste/riesgo | Elección/implementación futura autorizada |
| Documentación 8 | Entrada/canónicos/historial/enlaces | Reescritura aplicada y revisión cruzada | Guías especializadas legacy conservan contexto propio; estado externo no verificado |

Se revisaron explícitamente interacciones y contraevidencia antes de cerrar: originales congruentes limitan H03; quote/history correctos no invalidan H02; overlay correcto limita pero no borra H13; vacío real válido limita H01; muestras sin zonas duplicadas limitan H05; recuperación inmediata válida limita H04. Ningún área se cerró solo por una afirmación documental o una suite verde.

## 12. Cambios documentales aplicados y discrepancias abiertas

| Documento | Cambio aplicado y motivo |
|---|---|
| [README](../README.md) | Motor estructurado 39, sin calendario/fallback retirados; enlace a estado/auditoría |
| [architecture.md](architecture.md) | Punto de entrada vigente, recorrido y responsabilidades, fechas/evidencia/límites |
| [component_map.md](component_map.md) | Topología actual con raw/slim mantenidos, controller y consumidores |
| [codex_adaptive_analysis.md](codex_adaptive_analysis.md) | Una descripción vigente de roles/ensamblado/autoridad y compatibilidad |
| [operations.md](operations.md) | Efectos reales de comandos, diagnóstico actual, límites de recuperación/despliegue |
| [batch_workflow.md](batch_workflow.md) | Adaptativo, universos, fuentes Core, fases, contadores y fallos |
| [standard_analyze_workflow.md](standard_analyze_workflow.md) | Full individual adaptativo frente a fases legacy; dry-run de subida limitado |
| [local_codex_flow.md](local_codex_flow.md) | Ruta vigente y enlace a benchmark/flujo histórico, sin prometer offline |
| [handoff_current.md](handoff_current.md) | Últimos resultados guardados, incidentes y protocolo adaptativo; full 35 terminado |
| [pending_work_current.md](pending_work_current.md) | Hallazgos/aceptación, observaciones futuras y pendientes históricos sin cierre |
| [current_status.md](current_status.md), [model_reference_automation_plan.md](model_reference_automation_plan.md) | Aviso de contexto histórico; contenido de época conservado |
| [history/](history/README.md) | Nueve versiones anteriores conservadas y rotuladas, enlaces relativos contextualizados |
| Este informe y [cuaderno](audit_work_20261017/coverage.md) | Evidencias, cobertura, baseline, resultados y reproducciones |

No se reescribieron auditorías antiguas, recibos, prompts, config, AGENTS ni informes financieros.

**Verificación de cierre:** 479 archivos protegidos coinciden con sus hashes iniciales; nueve documentos históricos reconstruyen exactamente el contenido original al retirar el aviso y revertir únicamente los enlaces adaptados; los enlaces locales de los 27 documentos revisados resuelven y no hay errores de espacios en el diff documental. El [registro de comprobación](audit_work_20261017/verification_results.json) acota el alcance; no se afirma haber hasheado todo el repositorio ni verificado servicios remotos.

**Inconsistencias corregidas:** Web principal/fallback; roles Luna mal interpretados; ruta Markdown libre; calendario/skip legacy; fuente de prompt única falsa; full 35 en curso; «siguiente natural» antiguo como si no hubieran existido lotes posteriores; mapas raw/slim como histórico; confusión 65/70 evitada (visibilidad 65, sólido 70); publicación failed legacy generalizada; comando Core sin describir efecto de refresco.

**Abiertas:** todos/Market; guardas prometidas que el código no cumple H03/H04; verdad/completitud de fuentes H01; divergencias posibles entre árbol e imagen; criterios empíricos/producto H14. Se documenta discrepancia, no se eleva automáticamente el código a requisito correcto.

## 13. Conclusión y comprobaciones pendientes

Podemos confiar de forma acotada en la conservación de autoridad/fechas y en controles tipados que se comprobaron con originales y negativos. No podemos convertir esa confianza en garantía de que el feed fue completo, que una fuente recién envuelta es reciente, que todo candidato validado se publica intacto o que una fortaleza alta predice una buena compra.

La prioridad es hacer fieles las fronteras de **adquisición, validación duradera y publicación**, corregir errores deterministas y reducir ambigüedad contractual sin abandonar riesgo/continuidad. Después corresponde evaluar utilidad financiera y definir el estado de tesis pendiente.

Quedan sin ejecutar, por alcance y falta de evidencia: consultas remotas del estado actual; captura wire adicional; llamadas de modelo; recovery/publicación de históricos; despliegues; evaluación prospectiva y P&L. Cada comprobación concreta y su aceptación está en hallazgos/backlog. No son acciones realizadas ni pendientes que deban dispararse automáticamente.

La documentación actualizada empieza en [architecture.md](architecture.md). Las mejoras del sistema están únicamente propuestas; los incidentes históricos siguen fechados y visibles.

## 14. Ampliación: qué conservaríamos y qué rediseñaríamos

**Esta ampliación evalúa la metodología, no solo su implementación.** Se leyó primero la auditoría de las secciones 1–13 y se investigó literatura primaria, código efectivo y originales ya disponibles. Las consultas bibliográficas son nuevas; no se accedió a servicios operativos ni se ejecutaron experimentos externos, modelos, lotes o cambios del sistema. Los hallazgos H01–H15 siguen abiertos y no se repiten como descubrimientos nuevos.

Si diseñáramos hoy el análisis para su propósito actual, conservaríamos el seguimiento empresarial, la compra opcional en soportes, la separación entre origen, vigencia, fortaleza y selección, y la memoria fechada. **Cambiaríamos primero la calidad de las inferencias y la forma de comprobarlas; después decidiríamos qué señales merecen permanecer.** No hay evidencia para reconstruir el producto alrededor de más indicadores ni para dar por óptima su rúbrica actual.

Las prioridades metodológicas son:

1. Separar observaciones de hipótesis: concentración de opciones no identifica la posición dealer; una prima ATM no es una probabilidad; un máximo posterior no demuestra una defensa tolerable.
2. Revisar qué llega a ser candidato. Parte del descubrimiento ya se limita por distancia y un ganador por familia antes del juicio financiero; ampliar familias sin revisar esa selección puede no resolver la carencia.
3. Medir valor incremental y dependencia. La suma de cinco componentes combina varias transformaciones del mismo precio y da un peso decisivo a opciones sin calibración demostrada.
4. Integrar contexto y acontecimientos de forma más reproducible: qué parte del movimiento es común, qué premisa empresarial cambió y frente a qué expectativa conocida entonces.
5. Expresar horizonte e incertidumbre de forma útil para decidir. Una zona estrecha, una extensión inferior y un color no tienen por sí solos un significado probabilístico ni una instrucción de ejecución.

El diagnóstico no es que el sistema carezca de estructura, noticias o contexto: ya contempla mucho de ello y los casos muestran decisiones matizadas. Las carencias más prometedoras están en **selección de evidencia, representación del recorrido y del tiempo, atribución causal y evaluación**, además de los defectos de adquisición previamente demostrados.

Los anexos forman parte de esta ampliación y contienen matrices por alternativa, referencias de código, fuentes primarias con muestra/horizonte y limitaciones, y casos contrastados:

- [Estructura, familias de soporte y comportamiento del precio](audit_work_20261017/methodology_structure.md).
- [Volumen, opciones, microestructura y confluencias](audit_work_20261017/methodology_volume_options.md).
- [Mercado, sector, empresa, noticias y eventos](audit_work_20261017/methodology_context_events.md).
- [Evaluación, incertidumbre y utilidad para el lector](audit_work_20261017/methodology_evaluation.md).

## 15. Metodología realmente utilizada y sus supuestos

Esta reconstrucción describe el árbol local y los inputs originales examinados. No certifica de nuevo el runtime remoto. La descripción vigente queda incorporada al [motor adaptativo](codex_adaptive_analysis.md#metodología-financiera-vigente-y-límites-de-interpretación).

| Capa | Qué observa y hace actualmente | Qué puede detectar / qué no puede concluir por sí sola |
|---|---|---|
| Contexto técnico | OHLCV diario; 20 sesiones recientes en slim; SMA20/50/200, ATR, RSI, Donchian, Keltner y fuerza relativa SPY20/60; juicio del modelo | Ubicación, tendencia, recuperación o deterioro. RS es diferencia de retornos, no alpha ajustada por beta ni ranking universal |
| Orígenes compradores | Mínimo252 sesiones, pivotes/rango126, gaps estrictos entre barras, AVWAP diario, medias, estructura y puts observados; otras fuentes verificables según contrato | Referencias con origen. El inventario resumido no enumera toda estructura posible y un precio identificado no demuestra compra viable |
| Selección upstream | Distancia mínima por defecto del 5% para gap/rango/AVWAP y un candidato por familia; jerarquía de anclas AVWAP. Mínimo anual, medias y orígenes dirigidos tienen otros caminos | Reduce contexto, pero puede sesgar el descubrimiento hacia referencias lejanas. No es una regla financiera de ruptura ni excluye globalmente todos los soportes próximos |
| Historia de reacción | Hasta252 barras; contactos agrupados, cierre del toque y máximo de las cinco sesiones siguientes; madurez, tolerancia y dirección controladas | Describe episodios bajo esa definición. No reconstruye orden intradía, adversidad anterior al rebote, operación ejecutable ni toda la trayectoria de una referencia dinámica |
| Volumen | Perfil126 sesiones/48 bins, reparto uniforme del volumen diario entre precios de la barra; POC/HVN. Hasta16 de20 puntos del componente derivan de reacciones del precio | Mapa aproximado de actividad y respuestas históricas. No volumen comprador/vendedor, libro de órdenes, absorción observada o perfil intradía real |
| Opciones | Muestra de tres vencimientos; TOP cinco strikes por lado, detalle31 y observación dirigida39; OI/gamma, quotes y escala straddle | Identifica contratos/concentración dentro de esa muestra. No observa inventario neto dealer, cobertura efectivamente ejecutada ni toda la superficie de opciones |
| Juicio financiero | Origen → vigencia actual → fortaleza → selección; Entry/Washout opcionales; continuidad razonada y estimación inferior o null | Puede abstenerse y conservar apoyos viables marginalmente penetrados. No necesita cinco días maduros para reconocer todo apoyo nuevo ni tiene una regla universal de cierre/ATR |
| Fortaleza | Estructura25, Volumen/reacción20, Opciones25, Confluencia15 y Durabilidad15; condiciones de categorías y sumas verificables | Escala convencional de evidencia. No probabilidad de rebote, rentabilidad esperada ni ranking empírico demostrado. Durabilidad tampoco es una probabilidad calibrada |
| Empresa y acontecimientos | Investigación primaria/web en la misma llamada, Tesis/Setup separados, noticias/analistas, agenda, memoria de riesgos y síntesis causal | Puede distinguir deterioro empresarial de presión bursátil. No dispone de un panel uniforme de expectativas históricas, guía previa, realizado y KPIs por premisa |
| Mercado y sector | SPY20/60 en input; instrucciones macro/sector y búsqueda; el controller obtiene además contexto general y benchmarks en otras rutas | No hay ausencia total de contexto. El panel de Mercado no se congela como paquete equivalente en cada input financiero; su etiqueta CNN/VXN tampoco es un régimen validado |
| Vigencia y lectura | Actualización material, retain/update/full, ITV5; informe público resumido; fechas, extensión visual y memoria separadas | Control de revisión y continuidad. ITV no define cuánto dura la hipótesis, y revisión reciente no vuelve actuales todos los hechos heredados |

Hay decisiones deliberadas que no deben presentarse como carencias: dos compras opcionales, no rellenar cuotas, no stops/objetivos/resistencia, no fallos de estilo que compren otra llamada y no clasificador automático de verdad de prosa. En cambio, **no se encontró una decisión documentada basada en comparación empírica** que justifique el 5% de descubrimiento, el peso25 de opciones, las notas auxiliares o la omisión de trayectorias adversas. Son convenciones/limitaciones cuya utilidad sigue abierta; la ausencia de un registro no prueba que nunca se discutieran.

## 16. Ocho oportunidades metodológicas principales

### M01. Reducir inferencias no identificadas y falsa precisión en opciones

**Clasificación:** desajuste matemático demostrado en probabilidad de toque; límites de identificación demostrables; utilidad predictiva pendiente. Confianza alta sobre lo calculado, ninguna atribución de pérdida económica.

La fórmula de prob_touch usa una cola normal terminal. En un ejemplo browniano sin deriva, a una desviación de distancia la probabilidad terminal es15,87% y la de tocar31,73%; no representan el mismo suceso. No procede duplicar el porcentaje actual: su escala EM es otra aproximación y el mercado no tiene por qué seguir ese proceso. El straddle ATM tampoco es sigma por definición; EM/RV no acredita IV barata/cara. La aproximación ATM con DTE entero y mínimo artificial de tiempo da en APP atm_iv=14,1143 como fracción anualizada, equivalente a 1411,43%, usando el mínimo artificial de tiempo para DTE=0; no es una IV observada directamente.

Calls menos puts ponderados por OI/gamma no identifica signo dealer: los mismos contratos públicos admiten inventarios netos largos, cortos o compensados. La existencia de mecanismos de cobertura documentados no permite inferir el inventario que falta. La investigación con posiciones netas muestra además que gran exposición bruta puede coexistir con efectos limitados; no todo nocional implica impacto grande. [Cboe, posiciones y cobertura](https://www.cboe.com/insights/posts/volatility-insights-evaluating-the-market-impact-of-spx-0-dte-options/), [Amaya et al., estudio SPX](https://cdn.cboe.com/resources/education/research_publications/gammasqueezes.pdf).

**Propuesta:** conservar contratos, concentración, vencimientos y calidad; proponer retirada del porcentaje actual de toque y de las atribuciones de signo dealer/IV barata. Comparar un mapa descriptivo sin esas etiquetas, max pain ni confianza auxiliar. Si se desea probabilidad, definir evento/horizonte, estimarla y calibrarla por separado. No comprar datos nuevos para salvar una etiqueta. La implementación vigente permanece intacta.

Datos/cálculo/instrucción: faltan inventario neto y tiempos consistentes; varias mejoras semánticas usan datos ya adquiridos. Coste bajo/medio, cero llamadas financieras adicionales por diseño. Flujo clasificado o reconstrucción dealer sería otra investigación, costosa y con cobertura incompleta. El anexo de opciones distingue lo observado de cada inferencia y aporta contraejemplos reproducidos.

### M02. Buscar mejor antes de añadir familias de soporte

**Clasificación:** restricción de representación comprobada; oportunidad financiera plausible, no mejora demostrada.

En46 inputs del16-10 hay64 candidatos gap/rango/AVWAP y ninguno a menos del5%; sí hay mínimos, medias y AVWAP dirigidos próximos por otros caminos. AMD recibe una curva próxima ya conocida, mientras el candidato AVWAP ordinario es más lejano. Esto limita una acusación de ceguera general, pero plantea una asimetría entre descubrir un soporte y mantener uno identificado antes.

**Propuesta prioritaria:** comparar un inventario pequeño y diverso sin ese filtro fijo con el actual, manteniendo el mismo presupuesto de candidatos y el derecho a no seleccionar. Después estudiar estructura multiescala, secuencias de ruptura/retest y anclas de evento fechadas. Los gaps y AVWAP ya existen: falta transmitir mejor algunos bordes/estados, comparar la jerarquía actual con alternativas de anclaje predeclaradas y dar contexto de formación; no añadirlos de nuevo como supuesta novedad.

Puede ayudar cuando la volatilidad y distancia porcentual no guardan relación estable, ante reprecificación empresarial o cuando una jerarquía oculta una alternativa cercana. Puede fallar por exceso de niveles, anclas elegidas retrospectivamente, duplicación de un mismo bloque o selección oportunista del que mejor encaja. No impone primer mínimo, recuperación automática, segundo hueco o compra de ruptura. El coste principal es cálculo/identidad/contexto, no un nuevo modelo; requiere ajustar contratos solo si supera la comparación. Véanse [familias, líneas y casos](audit_work_20261017/methodology_structure.md).

### M03. Evaluar el recorrido y la disponibilidad histórica, además del máximo favorable

**Clasificación:** límite de medición comprobado; alternativa con fundamento directo y utilidad por contrastar.

El high posterior de cinco días puede coexistir con una caída previa importante. Contactos separados pueden compartir ventana y no ser ensayos independientes. Un nivel seleccionado hoy usando la misma historia sobre la que se cuentan sus reacciones no ha pasado una prueba predictiva fuera de muestra.

Además, la reacción se calcula sobre la coordenada horizontal actual. En AMD, una curva anclada6-10 tiene un último test registrado28-09: describe ese precio horizontal anterior, no un test de la curva antes de existir. No se ha demostrado que el informe público cometiera esa atribución. La distinción debe conservarse antes de convertirla en evidencia de AVWAP o de opciones históricas.

**Propuesta:** guardar eventos/serie y disponibilidad de cada origen; comparar cierre, máxima excursión favorable/adversa, tiempo hasta recuperación, aproximación desde arriba/abajo y dependencia entre episodios. Mantener explícita la ambigüedad de OHLC diario. No convertir MAE en un stop nuevo ni recalificar originales con una definición posterior. Los pivotes que necesitan dos barras posteriores solo estarían disponibles tras esas barras.

Puede distinguir un rebote útil de uno precedido por deterioro intolerable y separar horizontes. Puede añadir ruido y parámetros si no se fija primero qué decisión mejora. Coste medio de cálculo/almacenamiento; no necesariamente nuevos datos prospectivos ni modelos. Datos intradía solo se justificarían para una pregunta que los datos diarios no puedan resolver.

### M04. Poner a prueba la rúbrica y simplificar señales redundantes

**Clasificación:** pesos convencionales y ausencia de validación; dependencia parcialmente estructural; sesgo efectivo del modelo no demostrado.

La suma actual es trazable, pero sus componentes no son cinco experimentos independientes. Repetición, tasa, magnitud y recencia reutilizan episodios; OI y gamma comparten contratos; medias, AVWAP y perfil reutilizan precio/volumen. Transformaciones distintas pueden aportar información adicional: compartir datos no implica inutilidad, pero tampoco justifica contar cada nombre como otra confirmación.

Con Opciones=0 el máximo aritmético es75, así que una zona no puede ser fuerte85. A la vez,25 de71 zonas publicadas tienen Opciones0: las opciones no son requisito de selección. Ambas observaciones importan. Cambiar pesos para subir notas o visibilidad sería otra arbitrariedad.

**Propuesta:** primero comparar mismos hechos con/sin notas raw de fuerza/confianza y etiquetas ambiguas; después estudiar una representación por evidencias sin bonus de confluencia y opciones como contexto, no cuota obligatoria del total. Una tercera vía es calibrar una escala ordinal sencilla contra resultados definidos. Ensayar estos cambios por separado, sin redistribuir puntos automáticamente ni confundir score/100 con probabilidad.

La alternativa debe justificar mejor ordenamiento, incertidumbre y decisión, incluyendo abstenciones. Puede empeorar consistencia si elimina una compresión útil; por eso requiere evaluación ciega. Coste bajo de datos, medio de evaluación y cambios de contrato si se adoptara; cero llamadas adicionales por defecto. La búsqueda de combinaciones también sobreajusta: [Novy-Marx, señales múltiples](https://www.nber.org/papers/w21329).

### M05. Contexto común y específico, con menos relato causal forzado

**Clasificación:** capacidad parcial comprobada; integración útil plausible, no filtro rentable demostrado.

Ya hay SPY, tendencia, noticias y búsqueda macro/sector. El panel de Mercado obtiene QQQ/VXN/sentimiento y algunos benchmarks, pero no llega congelado de forma equivalente a cada análisis. No basta con copiarlo: sesión, hora, retorno y drawdown tienen bases diferentes; un ETF puede incluir el propio activo y representar mal su negocio.

**Propuesta:** paquete compacto de observaciones comunes fechadas y exposición sectorial razonada, comparado también sin etiqueta agregada CNN/VXN. Su primera función sería distinguir presión compartida y cambio empresarial, no vetar compras contrarian ni sumar otro score. Retorno residual/beta, amplitud o dispersión son alternativas posteriores si añaden algo a retornos simples; requieren historia y estabilidad que no deben presuponerse.

La evidencia de momentum sectorial justifica estudiar contexto, pero sus horizontes mensuales no validan un filtro diario de soportes. Los resultados de crashes de momentum se refieren a estrategias distintas del producto long en retrocesos. [Moskowitz y Grinblatt](https://onlinelibrary.wiley.com/doi/10.1111/0022-1082.00146), [Daniel y Moskowitz](https://www.kentdaniel.net/papers/published/jfe_16.pdf).

Puede ayudar en caídas simultáneas y divergencias, o simplemente repetir lo que el modelo ya sabe. Falsos positivos: atribución al sector sin transmisión al emisor, doble descuento del mismo riesgo y pérdida de compras tempranas. Coste medio de sincronización/mapeos; algunos datos ya existen, pero reutilizarlos no es gratis. No exige otra llamada. La exposición conjunta de cartera es contexto compatible; imponer límites de posición sería cambio de producto.

### M06. Premisas empresariales y sorpresa verificable, antes que más noticias

**Clasificación:** investigación existente; normalización/reproducibilidad incompletas; valor informativo plausible con evidencia externa condicionada.

IBKR, ASML, CCJ y RKLB muestran que el sistema ya distingue hechos incorporados, transmisión empresarial, eventos pendientes y fuentes inaccesibles. La carencia no es “añadir fundamentales”. Es conservar un pequeño registro comparable de premisa, expectativa disponible, realizado, implicación y cuestión abierta. Crecer interanualmente, superar guía y superar consenso son comparaciones distintas.

**Propuesta:** fichas por acontecimiento material con fecha de disponibilidad, periodo, unidad, base GAAP/ajustada, guía previa y expectativa cuando exista. KPIs específicos del negocio, no DCF diario universal. La SEC ofrece hechos y documentos, pero consultar hoy el último dato no reconstruye lo conocido entonces ni proporciona consenso/guía listos para trading. [SEC, API y datos XBRL](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

La literatura diferencia reacciones con noticias identificadas y movimientos sin causa informativa identificada; no autoriza a llamar reversión rentable a cualquier caída sin titular. La evidencia de drift tras resultados tiene límites relevantes de liquidez y costes. [Boudoukh et al.](https://pages.stern.nyu.edu/~jboudouk/text_20121223.pdf), [Chordia et al.](https://business.columbia.edu/faculty/research/liquidity-and-post-earnings-announcement-drift).

Puede mejorar detección de deterioro, riesgo de gap y el próximo dato que cambiaría la tesis. Puede fallar por consenso revisado, mezcla de periodos, KPIs no comparables o hechos simultáneos. Coste medio/alto para expectativas históricas y mapeos; una ficha manual de factibilidad precedería a automatizar. La misma llamada puede interpretarla. Analistas siguen siendo evidencia contextual: su target y horizonte no son objetivo swing ni ventaja demostrada.

### M07. Horizonte, rango e incertidumbre entendibles para el lector

**Clasificación:** descripciones verificadas y riesgo de interpretación; no se ha medido todavía confusión del usuario.

Las71 zonas activas de45 publicaciones tienen anchura mediana0,714% y0,113 ATR del input de revisión; extremos0,051–0,205 ATR. No es necesariamente el ATR de formación de una zona heredada. Esa estrechez puede servir a una alerta, pero no prueba precisión estadística del soporte. La extensión inferior es una estimación razonada, no stop, cuantil ni garantía; el color no resuelve la ejecución.

**Propuesta:** comparar la lectura actual con una ficha breve que distinga zona operativa, estructura que la respalda, condición pendiente, horizonte de la evidencia, dato que cambiaría el juicio y fechas pertinentes. Mantener la síntesis causal existente; no reintroducir tesis/setup repetidos, inventarios de fuentes ni un diario de búsqueda. Si falta precisión, expresar ese límite puede ser mejor que inventar otra banda.

Evaluar comprensión de “dentro de zona”, “viable”, “confirmado” y “comprar”, y de informe heredado frente a revisión reciente. Una presentación más persuasiva no es necesariamente más correcta. El coste inicial es bajo, con igual juicio financiero y sin otra llamada; cambiar rangos requeriría evaluación financiera aparte. [Medición reproducible y propuesta de tareas](audit_work_20261017/methodology_evaluation.md).

### M08. Revisar según qué puede cambiar, conservando continuidad y riesgo

**Clasificación:** hipótesis de mejora de cadencia/contenido; ITV5 actual no validado ni demostrado incorrecto.

La vigencia de una cotización, una cadena, una reacción, una tesis y un evento usa relojes diferentes. Un vencimiento puede agotar parte de la evidencia antes del horizonte de compra; una fecha de evento cumplida no significa que ya exista resolución. Una nueva noticia no siempre cambia el juicio, y un riesgo antiguo puede seguir activo sin titulares nuevos.

**Propuesta:** distinguir anunciado, ocurrido, resultado conocido e implicación incorporada; medir retraso ante cambios materiales y llamadas/cambios innecesarios. Conservar ITV como referencia mientras una alternativa se evalúa en sombra. Primero mejorar el contenido temporal de la revisión; cambiar rutas o cadencia solo con evidencia posterior. La continuidad merece conservarse, pero su coste de oportunidad también debe medirse.

Coste bajo/medio de representación y registro; ninguna nueva llamada automática propuesta. Puede fallar por agenda incompleta, eventos inesperados o un criterio de materialidad demasiado estrecho. No sustituir revisión financiera por el calendario ni activar full por cualquier proximidad.

## 17. Evidencia a favor, en contra y alternativas que no priorizaría

La evidencia externa no es homogénea. Los anexos indican si se accedió al texto completo, a una presentación del autor o solo al abstract primario. Los resultados se conservan con su mercado, muestra y horizonte; no se acumulan como votos a favor del sistema.

| Familia investigada | Evidencia pertinente | Implicación y límite para el diseño |
|---|---|---|
| Patrones y soportes | Algunos patrones diarios contienen información; niveles FX publicados anticipan interrupciones intradía. [Lo, Mamaysky y Wang](https://web.mit.edu/wangj/www/pap/LoMamayskyWang00.pdf), [Osler](https://www.newyorkfed.org/medialibrary/media/research/epr/00v06n2/0007osle.pdf) | Merece estudiar niveles ex ante y controles comparables. No valida pesos, etiquetas de fuerza ni rentabilidad swing en acciones; la fortaleza estimada en el estudio FX no ordenó bien los rebotes |
| Reversión frente a continuación | Reversión depende de volatilidad/turnover; noticias identificadas y contexto pueden cambiar la dinámica. [Dai et al.](https://www.nber.org/papers/w30917) | Condicionar la pregunta al tipo de caída puede ser mejor que añadir otro oscilador. La presentación de autores reconoce límites fuera de microcaps; no prueba una compra en un soporte concreto |
| Cobertura y vencimientos | Hay clustering de acciones cerca de strikes en vencimiento y mecanismos de cobertura documentados. [Ni, Pearson y Poteshman](https://www.sciencedirect.com/science/article/pii/S0304405X05000577) | Motiva horizonte y posición real, no max pain global ni soporte comprador de varias semanas. OI bruto no identifica quién debe comprar |
| Volumen y microestructura | El desequilibrio de eventos del libro explica movimientos muy cortos mejor que volumen agregado en la muestra estudiada. [Cont, Kukanov y Stoikov](https://arxiv.org/html/1011.6402v3) | Ayuda a no llamar flujo comprador al OHLCV. No justifica pagar libro intradía para elegir zonas swing sin una hipótesis adicional |
| Sorpresa y relato | Estudios de noticias, earnings y sorpresas monetarias observan efectos condicionados al contenido y expectativas | Distinguir sorpresa, hecho y presión de precio. Sus horizontes, costes y universos no permiten imponer una puntuación automática de sentimiento |
| Búsqueda de estrategias | Resultados históricos de reglas pueden desaparecer fuera de muestra; multiplicar combinaciones aumenta sobreajuste. [Sullivan, Timmermann y White](https://eprints.lse.ac.uk/119144/1/dp303.pdf), [Bailey et al.](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) | Registrar alternativas negativas, separar tiempos y penalizar búsqueda. Ni una prueba estadística ni un ejemplo favorable sustituyen una evaluación bien diseñada |

Hay un **fundamento plausible** para anclas de evento, lectura multiescala, trayectorias, contexto sectorial y fichas de premisas. Falta validación específica de su aporte incremental en este producto. La documentación de AVWAP describe su cálculo y uso, no una ventaja empírica; no se encontró validación primaria suficientemente comparable para incorporar por defecto Fibonacci, order blocks o fair value gaps inferidos de OHLCV. No se afirma que ninguna fuente pueda existir ni que esas prácticas sean siempre inútiles.

| Decisión de diseño propuesta | Componentes y motivo | Condición que podría cambiar la decisión |
|---|---|---|
| Conservar | Origen/vigencia/selección separados; abstención; historia fechada; riesgo; memoria causal; continuidad; opciones por identidad y expiración; madurez/dirección de reacciones | Ajustes acotados solo si mantienen esas funciones y mejoran utilidad observada |
| Revisar con prioridad | Candidatos cercanos/diversos; trayectoria; significado de opciones/EM; peso de componentes; horizonte y precisión de lectura | Ensayos E1–E6 y datos corregidos; no más puntos o zonas por objetivo |
| Proponer retirada o sustitución | Porcentaje de toque actual; atribución de signo dealer; IV barata/cara desde EM/RV; max pain como imán; notas auxiliares sin calibración | Retener una versión solo si su objeto está bien definido y demuestra información adicional. La fórmula correcta no basta |
| Simplificar antes de ampliar | Bonus de confluencia, etiquetas agregadas de régimen, repetición de noticias/contexto | Conservar si una comparación ciega muestra compresión útil sin falsas certezas u omisiones |
| Posponer adquisición cara | Trades intradía, libro/footprint, flujos open-close, inventario dealer, superficie completa, vanna/charm | Pregunta concreta no resoluble con datos actuales, disponibilidad suficiente y ventaja neta frente a base sencilla |
| No incorporar por popularidad | Más osciladores, patrones geométricos arbitrarios, etiquetas de liquidez no observada, regla “todo gap se rellena” | Hipótesis falsable, horizonte compatible y evidencia incremental independiente |
| Separar como cambio de producto | Estrategia de rupturas, timing de ejecución, tamaño, stops, objetivos, ventas o límites automáticos de cartera | Definición de propósito y evaluación ejecutable propias; no presentarlos como parche a los soportes actuales |

## 18. Casos históricos disponibles y controles contrarios

Se eligieron casos por preguntas metodológicas y decisiones diversas, no por rentabilidad futura: retención, retirada/promoción, nueva zona, ausencia, incertidumbre informativa y fallo. Son principalmente el natural38 del16-10; varios comparten mercado y zonas heredadas. No son una muestra representativa de varios regímenes ni un backtest. Se contrastó el conjunto completo para los conteos, incluyendo APP fallido.

| Caso conocido entonces | Oportunidad que ilustra | Contraevidencia o límite |
|---|---|---|
| AMD: AVWAP próximo en observación dirigida y otro lejano en candidatos; Entry531–535 conservada con Opciones0 | Diferenciar descubrimiento y continuidad; fechar la trayectoria de anclas | El sistema sí dispone de algunos apoyos próximos y selecciona sin opciones; no hubo omisión general demostrada |
| GEV: suelo previo871,125 y reacción15-10; añade869–875 sin opciones | Estructura/reacción pueden bastar; exigir una nueva familia no siempre aporta | No establece defensa futura ni superioridad de ese rango |
| TLN: gap337,22 ya observado y Washout336,5–338,5 | Transmitir mejor geometría y distinguir confluencias | Gap no es familia ausente. La reparación contractual previa no prueba ni refuta utilidad del gap |
| SPCX: barra15-10 enteramente bajo150; promueve144,75–145,5 y deja Washout vacío | Representar secuencia y bloque común | Más candidatos pueden duplicar el bloque; una ausencia puede ser la mejor decisión |
| SOFI: recuperación de una sesión; MP: origen antiguo aún no visitado; IREN: nuevo mínimo con incertidumbre | Separar edad del origen, madurez estadística y viabilidad presente | No todo soporte exige rebote reciente; tampoco todo nuevo mínimo es una compra. Ninguno demuestra una regla rentable |
| AUR: Entry conservada tras penetración; Washout ausente pese a referencias inferiores | Revisión ciega de coherencia entre falta de confirmación, selección y motivo heredado | Tensión para investigar, no prueba automática de error ni autorización para llenar la casilla |
| IBKR: resultados y monetización; ASML: recapitulación/corrección inaccesible; CCJ: titulares repetidos | Fichas de premisas y asuntos abiertos con expectativas/fechas | Ya hay razonamiento causal y separación de hechos incorporados; nueva ficha debe mejorar esa base real |
| LRCX: tesis conservada, compras anteriores retiradas y sustituidas por zonas inferiores; RKLB: riesgo antiguo Neutron sigue activo | Separar empresa, precio y reloj del riesgo | Ausencia de deterioro empresarial demostrado no rescata una compra perdida; ausencia de titulares nuevos no cierra un riesgo |
| APP: put270 con80,7% gamma en vencimiento del día pero44,3% OI; original bloqueado | Desglosar plazo y no confundir bases de respaldo | Dominante no es exclusivo. La captura técnica39 posterior no estaba disponible al intento original ni lo recupera |

Rutas, selectores y números completos están en los tres anexos de dominio. Los descriptivos nuevos usan46 inputs y45 publicaciones,71 zonas: [datos y hashes](audit_work_20261017/methodology_descriptive_cases.json), [reproducción local](audit_work_20261017/methodology_descriptive_check.py), [resultado](audit_work_20261017/methodology_descriptive_check_result.json).

Otros descriptivos acotan la exposición a supuestos:193 de230 filas TOPput tienen vencimiento dominante16-10 y24 tickers tienen las cinco filas dominadas por ese día. Son filas de strikes, no porcentaje de nocional o zonas elegidas. Hay111 porcentajes de toque entre los46 inputs. Presencia en el contexto no demuestra que el modelo los usara causalmente.

## 19. Prioridades y plan concreto de evaluación

### Orden propuesto

Este es un orden de investigación, no autorización de implementación. Los defectos H de adquisición/integridad siguen siendo dependencias para una evaluación limpia. Corregir un dato no demuestra una metodología mejor; cambiar una metodología no compensa un dato incompleto.

| Prioridad | Propuesta / utilidad esperada | Solidez de evidencia | Coste y requisito siguiente |
|---|---|---|---|
| 1 | M01: retirar inferencias que el dato/cálculo no identifica; preservar observaciones y plazo | Alta sobre el desajuste; beneficio decisorio sin medir | Bajo/medio; aclarar semántica y comparar sin etiquetas. Mismos datos,0 llamadas adicionales por diseño |
| 1 | M03: recorrido, origen temporal y episodios | Alta sobre lo que falta en el resumen actual; beneficio plausible | Medio de cálculo/archivo; factibilidad con historia conservada y E3 |
| 1 | M06/M05: premisas/eventos y contexto mínimo fechado | Capacidad actual comprobada; evidencia externa condicionada | Medio, mayor si se compra consenso histórico; E5/E1 por separado |
| 2 | M02: inventario cercano/diverso y anclas ex ante | Restricción comprobada; ganancia sin demostrar | Bajo/medio, mismo presupuesto de contexto; E2 antes de más familias |
| 2 | M04: quitar priors, luego comparar rúbrica simple | Dependencia/convenciones comprobadas; alternativa incierta | Bajo de datos, medio de evaluación; E4 sin torneo de pesos |
| 2 | M07: lectura de horizonte/condición e incertidumbre | Riesgo plausible; datos descriptivos, no prueba de confusión | Bajo; E6 con mismo contenido financiero |
| 3 | M08: cadencia/materialidad; panel temporal de opciones | Relojes distintos observables; política óptima desconocida | Medio de registro; E7 en sombra, no modificar ITV ahora |
| Condicional | Microestructura, flujo clasificado y probabilidades calibradas | Evidencia en objetos/mercados concretos; transporte incierto | Alto de datos/mantenimiento; solo tras una pregunta incremental no resuelta |

No se cotizaron licencias ni se prometen ahorros. Cero llamadas adicionales se refiere al diseño de producción que podría interpretar datos mejores en la llamada existente; una comparación futura entre respuestas del modelo tendría un presupuesto propio y no fue ejecutada.

### Referencias, muestra y separación temporal

**B0** son los originales actuales. **B1** sería la misma metodología con defectos deterministas corregidos y aprobados; hoy no existe como variante implementada. **B2** es una referencia sencilla predeclarada de estructura conocida entonces, con igual universo y datos. Cada alternativa A cambia un eje frente a B1. Comparar contra B0 sirve para impacto total; comparar contra B1 separa mejora metodológica de reparación de datos.

Unidad: ticker por episodio de decisión, con zonas y revisiones dependientes anidadas. Se incluyen fallos, bloqueos, ausencia de zona, eventos no resueltos y candidatos descartados. No seleccionar solo contactos o resultados publicados. Las dos compras del mismo ticker y46 acciones del mismo día no son observaciones independientes.

Plan de muestra propuesto:

1. **Desarrollo/factibilidad:** originales disponibles hasta16-10-2026, incluidos los casos ya examinados. Sirven para definir etiquetas y descubrir ambigüedades; nunca serían la confirmación final ciega.
2. **Piloto futuro, sujeto a autorización:** episodios consecutivos durante6–8 semanas; objetivos de factibilidad de60 episodios distintos y30 acontecimientos materiales para contexto/eventos, si se alcanzan. Son metas operativas, no tamaño suficiente para demostrar una mejora. No crear revisiones financieras duplicadas para llenar la muestra.
3. **Validación temporal:** tramo posterior, con todos los casos consecutivos y ventanas móviles solo dentro de este tramo. Estimar variabilidad/dependencia y fijar tamaño necesario para el efecto mínimo relevante. Incluir calma, estrés/rebote, divergencia sectorial y eventos; una ventana sin esos estados no permite afirmar generalidad.
4. **Confirmación:** tramo cronológico posterior intacto, con fecha de cierre/tamaño fijados antes de abrir resultados. Si no hay potencia o diversidad suficiente, limitar la afirmación. Cualquier ampliación se decide antes de abrir resultados o mediante una regla secuencial predeclarada; nunca prolongar después de ver significación insuficiente ni buscar el segmento ganador. Separar etiquetas que crucen fronteras, al menos según el horizonte máximo y dependencia real. Reservar activos/sectores si se pretende generalizar fuera del universo de desarrollo.

No hay calendario de ejecución iniciado. El piloto sugerido permite planificar una evaluación concreta sin fingir que unas pocas semanas bastan. Universo y ajustes deben ser los conocidos entonces, incluyendo retiradas/cambios de integrantes; noticias, consenso y anclas necesitan fecha de disponibilidad. Un modelo actual puede conocer hechos posteriores por entrenamiento, aun con input congelado: sus replays no serían una prueba temporal limpia. Son preferibles juicios originales o evaluación prospectiva en sombra.

### Hipótesis y métricas

Se proponen3/5/10/20 sesiones para estudiar sensibilidad, con **un horizonte primario elegido antes de confirmar**; no son nuevas reglas del producto. Se separan tiempo desde publicación y desde primer contacto. Una vela que contiene la hora de publicación no acredita orden de fill y máximo favorable.

| Ensayo | Hipótesis y comparación | Métrica principal propuesta / controles |
|---|---|---|
| E1, contexto | B1 vs datos comunes/sectoriales mínimos; etiqueta agregada en brazo separado | Menos errores materiales de atribución y vigencia ante juez ciego; controlar causalidad inventada, doble penalización y omisiones de riesgo |
| E2, candidatos | Igual presupuesto, distancia/diversidad alternativa y anclas fechadas | Cobertura de candidatos aptos omitidos y utilidad posterior sobre todos los episodios; emparejar distancia/anchura/volatilidad, controlar cantidad y usar referencias placebo comparables |
| E3, recorrido | Mismas visitas, high5d vs MAE/MFE/cierre/tiempo y dependencia | Mejor ordenamiento de recorridos futuros y juicio de vigencia; no confundir máximo favorable con P&L. Mantener selección para aislar el resumen |
| E4, simplificación | Mismos hechos con/sin priors; luego opciones descriptivas; después rúbrica alternativa | Valor incremental fuera de muestra, estabilidad y falsas certezas. Registrar componentes retirados también de textos derivados para una ablación limpia |
| E5, acontecimientos | E5a: misma evidencia organizada en premisas/expectativa/realizado/pendiente. E5b, separado: añadir evidencia primaria/expectativas congeladas frente a E5a | Omisiones o afirmaciones materiales erróneas y retraso desde evidencia disponible; distinguir efecto de representación y dato nuevo. Incluir sorpresas de ambos signos, consenso ausente y divulgación parcial |
| E6, lector | Misma decisión, presentación actual vs horizonte/condición/fecha explícitos | Errores en tareas concretas, tiempo de comprensión y conservación de riesgos; ciego y contrabalanceado, no preferencia estética como único resultado |
| E7, actualización | Cadencia actual vs acontecimientos que justificarían revisión, primero en sombra | Detección tardía de riesgos, cambios injustificados y llamadas evitables; mantener seguridad y medir coste real por intento |

Para zonas: publicar frecuencia de visita y plazo sobre todas las decisiones; después reacción condicionada al contacto, con su denominador separado. Registrar MFE, MAE y cierre, normalizados por escala congelada en t0; gaps y orden intradía ambiguo permanecen explícitos. Zonas lejanas casi nunca visitadas no ganan por unos pocos contactos favorables. La fortaleza se evalúa primero como escala ordinal, no como probabilidad. Una variante probabilística exigiría evento preciso y calibración/Brier; un rango más ancho no gana solo por cubrir más. [Gneiting y Raftery](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf).

Para juicios y lector: pares ciegos al brazo, modelo, resultado posterior y decisión publicada cuando esa sea objeto de evaluación; rúbrica de errores definida antes, desacuerdos conservados. Más acuerdo o confianza no equivale a verdad. Los eventos repetidos pertenecen al mismo episodio.

Para P&L: harían falta ejecución, tamaño, salida, costes, spread, slippage, gaps y restricciones acordadas. No se inventan para cerrar esta ampliación. La utilidad informativa puede evaluarse antes; si se define una estrategia después, todos los brazos comparten reglas ejecutables y costes.

### Control de búsqueda y decisión final

Predeclarar una hipótesis primaria por ensayo, pocos contrastes y todas las variantes examinadas, incluidos resultados negativos. Probar primero retiradas simples y un cambio cada vez; combinar solo después de demostrar información adicional. Separar inferencia por ticker, fecha y episodios solapados. Ajustar múltiples pruebas a la familia real: por ejemplo Holm en pocos contrastes confirmatorios; procedimientos de búsqueda dependiente si se abre un universo grande. No seleccionar pesos, umbrales, horizonte o benchmark después de ver el ganador.

**Adoptar:** intervalo ajustado del beneficio incremental supera una mejora mínima útil fijada antes de confirmación, sin degradar riesgo/observabilidad ni depender de un único episodio o parámetro estrecho; costes de datos, mantenimiento y comprensión justifican la ganancia. **Descartar:** precisión suficiente excluye esa mejora o aparece un deterioro material no compensado. **Investigar más:** incertidumbre amplia, cobertura insuficiente o heterogeneidad no prevista. “No significativo” no prueba equivalencia.

La mejora mínima debe expresarse en la tarea elegida: errores materiales por100 análisis, retraso en horas, MAE en ATR o decisiones útiles por100 episodios. No sería riguroso inventar una ganancia económica sin una estrategia de ejecución. Los criterios y procedimientos están desarrollados en el [protocolo de evaluación](audit_work_20261017/methodology_evaluation.md); no se ejecutaron esos experimentos.

## 20. Incertidumbres, documentación aplicada y cierre de la ampliación

### Qué sigue sin resolverse

- No sabemos qué familias, pesos o ventanas dan ventaja neta en este universo/horizonte. La literatura revisada motiva hipótesis y límites; no sustituye datos propios fuera de muestra.
- Falta concretar el horizonte principal y la tarea de decisión que tendría prioridad: descubrir más oportunidades útiles, reducir daño antes de rebote, detectar deterioro o mejorar comprensión. Pueden entrar en conflicto; no se optimizan todas con una nota única por defecto.
- No conocemos inventario dealer ni todas las órdenes, noticias o expectativas disponibles al mercado. Añadir razonamiento no recupera esos datos ausentes.
- Los originales permiten trazabilidad de decisiones, pero no una serie homogénea de varios regímenes ni todos los candidatos descartados, wires y perfiles intradía históricos.
- No se midió cuánto influye cada campo auxiliar en el juicio del modelo, ni cuánto confunde el lector rango, extensión, color y confirmación. Son preguntas de evaluación, no errores de comportamiento ya probados.
- No se revalidó producción remotamente ni se cerraron incidentes H. Los defectos de datos y autoridad pueden contaminar cualquier futura evaluación si no se separan.

### Cambios documentales de esta segunda fase

| Documento | Actualización aplicada |
|---|---|
| Este informe, §§14–20 | Diagnóstico metodológico, evidencia favorable/contraria, oportunidades/retiradas, prioridades y evaluación |
| [Motor adaptativo](codex_adaptive_analysis.md) | Método realmente utilizado, familias, cálculos, pesos y límites; ninguna instrucción operativa nueva |
| [Arquitectura](architecture.md) y [README](../README.md) | Acceso directo a metodología y evaluación; alcance de lo que puede afirmarse |
| [Relevo](handoff_current.md) | Resultado de la ampliación y límites, sin cambiar el estado operativo ni cerrar incidentes |
| [Backlog](pending_work_current.md) | M01–M08 como propuestas pendientes, distintas de correcciones H y cambios de producto |
| Anexos metodológicos y [cobertura](audit_work_20261017/methodology_coverage.md) | Fuentes primarias, comparaciones, casos, costes y reproducción descriptiva conservados |

Las secciones1–13 registran la primera fase. Sus cifras de tests y límites de acceso remoto no se presentan como pruebas nuevas de esta ampliación. Esta segunda fase añadió bibliografía pública y comprobaciones locales descriptivas; ninguna consulta técnica en vivo, llamada financiera, experimento externo ni modificación de comportamiento.

La [verificación específica](audit_work_20261017/methodology_verification_results.json) registra huellas de479 archivos protegidos y91 originales usados en la medición, enlaces locales y alcance documental. Se conserva el resultado anterior por separado. Las mejoras del sistema siguen **propuestas, sin implementar**.

La respuesta a la pregunta central es conservar la disciplina de decisión y memoria, revisar la selección y el significado de las evidencias, simplificar antes de sumar señales y someter las alternativas a comparación temporal. La evidencia más firme de esta ampliación permite afirmar **qué no significan varios cálculos actuales**; cuál metodología decide mejor sigue siendo una cuestión empírica pendiente de los ensayos definidos.
