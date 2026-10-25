# Auditoría financiera del lote natural del 18 de octubre de 2026

Lote: logs/batch/2026-10-18/09-08-40. Revisión independiente de las 46 decisiones y sus antecedentes congelados. No se ejecutó ningún modelo, reintento de lote, recuperación ni publicación, ni se editaron originales. Tras la revisión local se autorizaron únicamente lecturas retrospectivas de las URLs ya citadas por tres notas nuevas; se distinguen de lo que recibió el modelo.

**Resultado:** no se ha identificado un error financiero material en las decisiones revisadas. Esto no certifica que las zonas sean óptimas, rentables o predictivas. Hay una limitación editorial concreta en MU y límites de reconstrucción de las fuentes web. La ejecución correcta de las guardas es una evidencia adicional, no una sustitución del juicio financiero.

**Qué se verificó de nuevo**

El replay puro financial_guard_replay.py ejecutó el binding contra el recibo real y el input congelado, la decisión y cobertura en los 46 casos; maintenance_document y validation_result en los 21 updates; herencia autenticada en retain, geometría, selección editorial y extensión en ambas ramas. Reconstruyó la investigación desde los eventos locales y comparó documento semántico y Markdown. Resultado: **46/46 pasan, 46 documentos semánticos iguales y 46 renders iguales**, en 189,203 segundos. No se llamó a stage.analyze ni se sustituyeron fuentes por actuales. Los valores guards/ITV fueron los registrados; este replay no rehace adquisición ni asegura cobertura externa universal.

Además se leyó la razón de las 46 decisiones, contrastando el mérito de todos los cambios y las no selecciones con OHLC reciente, orígenes, componentes, antecedentes y texto público. Los JSON por caso permiten separar comparación mecánica de valoración independiente.

**Cambios observados**

| Comprobación | Resultado |
|---|---|
| Revisión en input, política y fuente slim | 40 en 46/46 |
| Decisiones | 25 retain, 21 update, 0 full |
| Ancla y última fecha full | Igualdad estructural exacta en 46/46 |
| Fechas financieras de retain | Exactas en 25/25 |
| Rangos y fortalezas de retain | Exactos en 25/25; extensiones separadas en 3 |
| Tesis numérica, razón de tesis, narrativa, catalizadores y evento tipado | Protegidos, iguales en 46/46 |
| Setup numérico | Cambia en AMAT, AUR, GOOG y MU |
| Algún rango cambia | AMAT, AUR, CAT, CLS, GOOG, HOOD, IBKR, MRVL, MU y TSLA |
| Promoción Washout→Entry con sus cinco componentes exactos | GOOG, HOOD, IBKR, MRVL y TSLA |
| Rescoring con mismo rango | CAT, COIN, IONQ e IREN |
| Zonas nuevas respecto al plan anterior | 8; Volumen nuevo coincide con aritmética en las 8 |
| Zonas activas | 72 antes, 70 después; 45 Entry y 25 Washout |
| Geometría | Los 25 pares son inferiores, distintos y no solapados |
| Sumas de componentes | Coinciden con los 70 scores publicados |
| Extensiones | 70 estimaciones finitas; no son garantías ni stops |
| Nuevo estado de tesis informativo | Ninguno: no hubo full, ni migración artificial desde mantenimiento |

No deben confundirse 21 updates con 21 nuevos planes: seis son principalmente correcciones de interpretación gamma (APP, INTC, LRCX, ORCL, SOFI, SPCX), dos son notas informativas sin cambios de compra (CIFR, QBTS), tres ajustan opciones del mismo rango (COIN, IONQ, IREN; IONQ además actualiza una noticia), y diez alteran algún rango (CAT también ajusta componentes y explicación). Esta clasificación es por resultado principal, no por causalidad exclusiva.

**Efectos de la metodología que sí se ven**

Diez motivos internos de Setup dejan de utilizar gamma negativa/coberturas amplificadoras como una condición demostrada. Seis updates se concentran en esa corrección y otros cuatro la incorporan junto a cambios de plan. No se infiere una nueva posición de intermediarios a partir de calls-minus-puts, ni se alteran las notas automáticamente. El Markdown final no contiene afirmaciones de régimen dealer inferido de ese signo; la aparición de intermediarios en INTC es una limitación explícita.

Los ajustes CAT/COIN/IONQ/IREN distinguen contratos ya vencidos de contratos posteriores observados. No concluyen desaparición por salir del TOP ni por cambiar el vencimiento dominante. CAT conserva estructura/Volumen/confluencia y ajusta supervivencia global del soporte; los otros tres cambian solo Opciones. Las promociones no recalculan un Volumen heredado usando la captura nueva. Las ocho zonas nuevas sí aportan cálculos explícitos.

Las decisiones consideran trayectorias completas y efectos adversos: por ejemplo, AUR retira su única Entrada tras la reversión, pero reconoce que aún existen puts posteriores y analiza referencias inferiores. AMD, NVDA y SNDK admiten penetraciones con respaldo concreto, sin una regla automática de cierre/ATR. Los resultados no demuestran que estas distinciones anticipen mejor el mercado.

Las primas de straddle se describen con su vencimiento y como escala observada, no como probabilidad calibrada ni sustituto automático semanal. Las evaluaciones de AMD, NVDA, TSLA y TSM distinguen los tests de un precio horizontal de la trayectoria de una media anclada. La heurística de alcance y la independencia estructural siguen siendo juicios financieros; pasar geometría no los valida empíricamente.

**Casos destacados y contraevidencia**

- APP actualiza explicaciones, mantiene 249,5–250,5 y fortaleza35. El input contiene puts250 con OI510/1677/631 para23Oct/30Oct/6Nov, y255 también observado. Se considera el bloque260 y su reacción15Oct, sin exigir cinco sesiones maduras; la reversión16Oct limita su superioridad. Es una nueva preparación40 que usa el último informe válido15Oct: no recupera ni borra el fallo16Oct. No se prueba que250 sea óptimo frente a260.
- TLN conserva349,5–351,5 y336,5–338,5, fortalezas64/58 y fecha16Oct. Extensión principal349,15→348: el mínimo348,35/cierre354,81, el nodo348,8613 y la media351,3033 están en las fuentes. Es una estimación nueva fechada, no una defensa garantizada. No hubo cambio de rango que ejercitara aquí la antigua reparación de promoción TLN.
- MRNA conserva185/170, fortalezas55/55 y las fechas históricas14Oct. El mínimo reciente208,92 no toca esos bloques. ESMO24Oct y la prima con plazo30Oct justifican explícitamente conservar la excepción de alcance; no convierten esa prima en probabilidad. Opciones heredadas no se presentan como observación nueva. El full canario anterior no se publicó y no aparece adoptado como ancla ni como estado de tesis.
- NVDA conserva215/210: mínimo213,32 superior al212,85 previo, dentro de extensión212,5; puts215 por5265/1782/10333 en19/21/23Oct observados. Esto respalda un juicio de soporte penetrado, no demanda futura probada. La cobertura del feed y las noticias examinadas no garantizan ausencia de toda noticia material.
- ASML amplía1610→1590 por recuperación desde1594,0297 y contexto1600; PLTR amplía184,5→182 usando mínimos182,03/182,94 y media50, no una distancia fija a la cotización. Las dos conservan rango, fuerza y fecha del informe. La precisión del bound sigue siendo juicio, no calibración validada.
- Ausencias: AUR termina sin ninguna compra;21 símbolos no seleccionan Washout. CRWV, LEU, OKLO y USAR reconocen referencias inferiores concretas y explican por qué no las seleccionan; no afirman que la ausencia de cinco sesiones maduras elimine su origen. CAT y AMAT incorporan nuevas zonas inferiores con límites de calidad, sin una cuota universal.

**Coherencia sin certificado vacío: prueba causal acotada**

coherence_guard_replay.py toma las respuestas naturales exactas y evalúa únicamente reconcile_plan_explanation. De15 updates con plan_explanation=null, nueve cambian rangos: AMAT, AUR, CLS, GOOG, HOOD, IBKR, MRVL, MU y TSLA. La rama histórica39 de esa guarda devuelve nueve errores plan_coherence; la rama40 devuelve cero. Código: src/local_runner/review_contract.py:123–142. No se intentó admitir toda la respuesta bajo un contrato histórico distinto ni ejecutar otro modelo. Esto demuestra la eliminación de esa causa concreta de rechazo para estas respuestas; **no demuestra nueve llamadas ahorradas** ni atribuye toda la diferencia de repairs frente al16Oct a este parche.

Se revisó el riesgo que cubría la guarda. Ninguno de los nueve planes públicos mantiene el precio retirado como compra activa. Los bloques cambiados incluyen su razón, y las conclusiones específicas se revisan o la heredada sigue siendo compatible. AMAT deja de ofrecer418–420 y explica410/395; AUR elimina rango y fortaleza sin dejar una compra activa de recuperación. GOOG hereda una conclusión genérica válida y publica razones nuevas de335/330. Los casos sin cambios de rango con texto nulo no generan un nuevo certificado ni permiso para reescribir. Las guardas de fuentes, cambios, binding y geometría siguen ejecutadas en el replay40.

**F1 · Limitación editorial residual, MU (baja)**

El texto público heredado de Washout dice que el gap queda fuera del horizonte ordinario, con etiqueta visible «juicio del15/10/2026». La evaluación18Oct reconoce que780,1999 está ahora a1,91ATR, marginalmente alcanzable, y decide no seleccionarlo por trayectorias adversas y falta de mejora material. No hay un rango o score erróneo demostrado: la fecha protegida es auténtica y la no selección tiene una razón actual. Sin embargo, el lector solo recibe la razón antigua, que ya no explica por completo la decisión actual. Es contraevidencia a equiparar render/coherencia estructural con máxima claridad editorial. No se editó el histórico ni se fuerza una nueva llamada.

**Tres actualizaciones informativas**

La comprobación independiente posterior de las mismas URLs confirma la emisión CIFR de850M y el canje de40,7Macciones consumados16Oct; las conversiones2030/2031 tienen entrega física por defecto salvo elección distinta. La nota conserva ese límite. [8-K firmado16Oct, líneas92,123–125,141–142](https://www.sec.gov/Archives/edgar/data/1819989/000119312526424297/d313847d8k.htm).

IONQ confirma cierre16Oct y50Macciones/equivalentes más100Mwarrants. Actualizar la nota y ocultar el evento de cierre pendiente es coherente; no se afirma desaparición de dilución ni un saldo de caja actual. [8-K firmado16Oct, líneas69–70 y86](https://www.sec.gov/Archives/edgar/data/1824920/000119312526424230/ionq-20261014.htm).

QBTS atribuye a Robbins la comunicación de una demanda, sin declarar fraude ni sentencia. La página del despacho contiene la errata Millrose que el modelo reconoció y excluyó. El comunicado fechado16Oct aporta el anclaje temporal de esa comunicación. [Robbins](https://robbinsllp.com/d-wave-quantum-inc/), [comunicado de Robbins distribuido16Oct](https://www.tmcnet.com/usubmit/-qbts-stockholder-notice-robbins-llp-reminds-investors-the-/2026/10/16/10464832.htm). No se consultó expediente judicial ni se cuantifica exposición.

Los eventos congelados acreditan búsqueda/apertura, pero no preservan el cuerpo completo; la comprobación de hoy no demuestra qué texto íntegro vio entonces el modelo. primary_sources_retrospective.json conserva URLs, líneas, fechas, extractos breves y hashes de esos extractos; no hash ficticio de una página completa no descargada.

**Límites de la conclusión**

Cero full/repair no ejercita ITV vencido, nuevo estado de tesis, escalada ni recuperación de fallos. Las notas, coberturas y ramas son propias de este lote dominical con la sesión completa del viernes, distintas del16Oct. No se revaloró cada catalizador histórico ni se auditó en esta rama toda la integridad de publicación, cubierta por la revisión paralela. Los70 bounds y los scores son juicios del sistema; no se interpretan como probabilidades de éxito. No hay comparación predictiva fuera de muestra ni prueba de rentabilidad.

**Registro por símbolo**

| Símbolo | Decisión | Revisión independiente |
|---|---|---|
| AMAT | update | Retira 420 tras la reversión completa y selecciona 410/395; OHLC y Volumen 14/6 coinciden con fuentes. Menor confluencia y adversidad del inferior reconocidas. |
| AMD | retain | Retiene pese a penetración: mínimo 526.8324 sobre extensión 525, nodo 525.6537 y puts 525/530. No convierte el mero cruce en pérdida automática. |
| APP | update | Corrige interpretación gamma sin cambiar 250/35 puntos. Orígenes dirigidos 250/255 observados; alternativa 260 examinada sin exigir cinco sesiones maduras. Antecedente 15 Oct, no recuperación 16 Oct. |
| ASML | retain | Retiene rangos 64/68 y amplía extensión 1610→1590 por recuperación desde 1594.0297 y bloque 1600. Estimación prospectiva, no nivel validado ni stop. |
| ASTS | retain | Retiene 40 con mínimo 40.02 superior al 39.87 previo y opciones posteriores.39 se trata como mismo bloque, sin segunda zona forzada. |
| AUR | update | Retira única Entrada tras venta y vencimiento dominante; reconoce 420 puts posteriores y examina 4.5/gap 4.345. Ambos slots ausentes es selección permitida, no falta automática de datos. |
| CAT | update | Retiene 730, reduce Opciones 12→8 y eleva Durabilidad 7→8 por supervivencia de estructura/contacto; añade 700 independiente. No equipara vencimiento a desaparición total. |
| CCJ | retain | Retiene 80; contratos 23/30 Oct ya estaban observados.77.7/75 evaluados con límites concretos; no añade Washout por cuota. |
| CIFR | update | Cambia nota y conclusión por cierre real de financiación/canje; mantiene números. Comprobación SEC retrospectiva apoya hecho y default de conversiones. |
| CLS | update | Retira 312–314 y reemplaza por gap/suelo 283–285; antiguo 290 no declarado roto por ranking. Descarta duplicación del bloque inferior. Volumen 14 reproduce. |
| COIN | update | Mismo rango: Opciones 17→14 tras vencer 7741 puts; confirma 1995 posteriores. Mantiene Volumen 14 y restantes componentes fechados. |
| CRDO | retain | Retiene 169.5–171 con mínimo 168.56 dentro de extensión 166 y cierre 169.7; nodo y opciones posteriores actuales. No nueva defensa madura. |
| CRWV | retain | Retiene 60.3–60.8: mínimo 59.9 superior al 59.51 previo y cierre 61.39. Opciones inferiores 55/50 evaluadas, sin suponer que OI acredita demanda. |
| GEV | retain | Retiene ambas: mínimo 916 posterior a recuperación desde 871.155; reconoce que no fue defensa precisa de 900. Fuentes de precio y opciones separadas. |
| GOOG | update | Promueve 335–336 con cinco componentes exactos del Washout y añade 330. Viejo 340 pierde papel tras sesión completa; geometría no solapada y Volumen 12 nuevo. |
| HIMS | retain | Retiene 27.2–27.4/25.3–25.5; no usa anclas incompletas como actuales. Media 200/opciones y mínimos respaldan continuidad limitada. |
| HOOD | update | Promueve 94.4–95.1 con componentes exactos; no obliga Washout en 90/AVWAPanual con historia adversa. No traslada automáticamente inventario a defensa. |
| IBKR | update | Promueve 81.9–82.3 con componentes exactos; mínimo 82.25 y media 200 actual. Rechaza duplicar 81;80/gap inferior evaluados sin cuotas. |
| INOD | retain | Retiene 52–52.5 con contacto 52.13/cierre 52.82 y gap 47.98 inferior. Mantiene limitación por horquillas y eficacia histórica débil. |
| INTC | update | Corrige dos motivos gamma; rangos y componentes exactos. No convierte signo calls-minus-puts en posición dealer. |
| IONQ | update | Opciones 18→13 por expiración, demás componentes exactos. Nota y ocultación evento por cierre 16 Oct contrastado con 8-K. |
| IREN | update | Opciones 17→13: vencieron 12831 puts; persistencia posterior explícita. Contacto 26.5501/cierre 26.99 sostiene rango sin declararlo consolidado. |
| KTOS | retain | Conserva apoyo incipiente 37.75–38.1; reacción 15 Oct no anulada por siguiente sesión. Puts 39/40 no fuerzan sustitución; sin defensa madura inventada. |
| LEU | retain | Revisita 112.61/cierre 114.94 apoya continuidad débil, sin nueva ventana histórica completa.105/100 examinados; no segunda zona forzada. |
| LRCX | update | Única modificación financiera explicativa: elimina etiqueta gamma como régimen demostrado; notas/rangos/componentes exactos. |
| MP | retain | Conserva mínimo de julio 37.7–38.0 no visitado. Nuevas opciones 38 se reconocen sin llamar actual al componente heredado 0 ni presumir aumento desde ausencia de listado. |
| MRNA | retain | Retiene 185/170 y 55/55; mínimos 208.92 no alcanzan zonas. Excepción de horizonte ESMO documentada, primas con plazo propio sin probabilidad. Canaryfull no publicado ni adoptado. |
| MRVL | update | Promueve 221–223 conservando cinco componentes y añade 215. Volumen 12 nuevo y geometría correcta; AVWAP no reinterpretado como curva históricamente testeada. |
| MU | update | Sustituye 900 por 870 tras reversión; Volumen 14 correcto. Razón pública heredada de Washout queda parcialmente desactualizada, aunque fechada; verF1. |
| NBIS | retain | Retiene 165: venta intensa pero mínimo 163.27 y cierre 165.47 recupera rango, dentro extensión 161.5. Inferioreshistóricos alejados, sin Washoutforzado. |
| NVDA | retain | Retiene 215/210: mínimo 213.32 superior al 212.85 previo y dentro extensión 212.5. OIporvencimiento exacto; no prueba nueva defensa ni signo dealer. |
| OKLO | retain | Retiene 27.5–27.75: mínimo 27.59/cierre 27.97.25 alcanzable pero concentración aislada y estructura insuficiente para selección, sin veto por antigüedad sola. |
| ORCL | update | Elimina causalidad de coberturas no acreditada; Setup 4.7 y todos los niveles/componentes exactos. |
| PLTR | retain | Retiene 190 como bloque amplio penetrado y amplía 184.5→182 por mínimos 182.03/182.94 ymedia 50. Juicio frágil; no garantía de recuperación ni margen fijo aquote. |
| QBTS | update | Añade nota atribuida sobre demanda, no fraude probado; mantiene compra y ausencia. Corroborada retrospectivamente por anuncio fechado 16 Oct. |
| QCOM | retain | Retiene 170–171/165: mínimo 171.9 no vuelve a penetrar principal y fuentes independientes actuales. Antecedente 164.782 no presentado como medición actual. |
| RDDT | retain | Retiene 145/140 sin nuevas visitas; opciones por origen verificadas. Alcance 1.27/1.87 ATR no retira automáticamente apoyos válidos. |
| RKLB | retain | Retiene 50/gap 44.74; contratos 23/30 Oct exactos y nuevosputs 45 como cobertura, no aumento comparado demostrado. Sin repuntuación automática. |
| SNDK | retain | Retiene bloque 1312–1322 penetrado: mínimo 1296.19 superior a 1276 y nodo 1275.6/puts 1300. Extensión 1270 no ampliada para acomodar precio. |
| SOFI | update | Corrige motivo gamma mediante campo atómico existente; rango, Setup y fortaleza sin cambios. |
| SPCX | update | Corrige motivo gamma; conserva 144.75–145.5 y ausencia inferior. No modeloextra ni cambio de tesis. |
| TLN | retain | Retain con extensión 349.15→348: mínimo 348.35/cierre 354.81, nodo 348.8613/media 351.3033. Componentes 64/58, fecha financiera y ancla exactos. |
| TSLA | update | Promueve 353.5–355 con componentes exactos y añade 350 distinto. Extensión 351.5 preserva alcance del bloque; volumen 14 nuevo; no nivel deventa. |
| TSM | retain | Retiene 410/395 con contacto 410.58/cierre 412.61 y origen 410 dirigido; no confunde fueraTOP con ausencia ni AVWAPactual con test de curva. |
| USAR | retain | Retiene 9.8–9.88, sesión 16 no visita; inferiores 9.5/9 examinados sin seleccionar por presencia contractual sola. |
| WDC | retain | Retiene gap 311–313 como antecedente fechado, no origen nuevamente observado. Historial reciente no lo toca; alternativas 320/330/gap 271 evaluadas con límites. |

Artefactos principales: financial_audit.json, per_symbol_financial_review.json, financial_guard_replay.py/.json, coherence_guard_replay.py/.json, financial_component_checks.json, primary_sources_retrospective.json e evidence_manifest.json. Los originales permanecen en el lote indicado.
