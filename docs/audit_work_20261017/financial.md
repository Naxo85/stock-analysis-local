# Auditoría financiera y contexto del modelo — 17-10-2026

Notas independientes para integrar en `docs/audit_analysis_system_20261017.md`. Ámbito: criterios, prompts realmente ensamblados, autoridad full/mantenimiento/reparación, evidencia de volumen, selección de soportes, extensiones, noticias y muestra de originales. Solo lecturas, pruebas locales y esta nota; ningún modelo, lote, despliegue ni publicación.

## Resultado y clasificación

El diseño actual está deliberadamente centrado en comprar soportes: Entry y Washout opcionales, fuerza separada de selección, sin stops/objetivos/resistencia numéricos. No hay fundamento para restaurar el diseño antiguo. Hay evidencia favorable de que la separación entre origen, vigencia, nota y selección funciona en varios originales38; no hay demostración de utilidad predictiva, de calibración de pesos o de superioridad económica.

Hallazgos prioritarios de este ámbito:

1. **Defecto demostrado — geometría entre las dos compras no validada.** Un full39 puede pasar con dos rangos idénticos o con Washout por encima de Entry.
2. **Defecto demostrado de contrato de herencia — TLN.** Una cita CURRENT ya autenticada en `change_review.previous_evidence` no habilita herencia de Volumen si no se repite en `evidence`. El rechazo real produjo una reparación que subió Volumen13 a16, aunque añadir solo la cita duplicada permitía conservar13.
3. **Riesgo plausible / contradicción literal activa.** El prompt39 contiene a la vez la vieja condición de nodo <=3% para superar15 de Volumen y la política34 que la elimina. Código34 y varios textos posteriores son correctos, pero el montaje mantiene órdenes incompatibles.
4. **Complejidad contractual observada.** 7 de8 reparaciones del lote16oct se activaron por `plan_explanation=null`; GEV pasa al sustituir únicamente null por un objeto con todos sus campos null, sin nuevo texto ni decisión.
5. **Falta de evidencia y decisión metodológica discutible.** Pesos, umbrales, ventanas y extensión inferior son convenciones reproducibles, no predicciones empíricamente validadas.
6. **Carencia de producto pendiente de definición.** Existe nota de Tesis y evaluación interna de riesgos, pero no un estado de tesis separado y tipado pese al acuerdo del cuaderno estratégico.
7. **Riesgo plausible de carga de contexto y mantenibilidad.** Prompt39 full77.380 caracteres; mantenimiento86.592. Inputs reales38 de la muestra entre206.078 y246.970 caracteres. Ya existe deduplicación sin pérdida; no se ha probado que la carga cause decisiones erróneas.

## Configuración y ensamblado reales

`config/codex_analysis.json`: routing_revision39, production_enabled=true, mantenimiento gpt-6.1-sol medium, full gpt-6.1-sol high, ambos research habilitado, ITV5 para prioridad y seguimiento, límite6 de modelos,240/1200 segundos, snapshot24h. «Luna» es un nombre de rol legado, no otra identidad de modelo.

`src/local_runner/adaptive_stage.py:176-194` sustituye las versiones anteriores, y para39 produce:

- Financiero: `prompts/stock_analysis_semantic_v12.md`.
- Contrato, en orden: `adaptive_revision35.md`, `volume_arithmetic_v25.md`, `evidence_direction_v27.md`, `report_reader_style_v35.md`, `strength_evidence_v31.md`, `reader_report_v35.md`, `catalyst_editorial_v33.md`, `volume_rubric_v34.md`, `support_validity_v37.md`, `option_origins_v39.md`.
- Mantenimiento antepone `daily_maintenance_semantic_v35.md` y el encabezado FINANCIAL POLICY AND RUBRIC.
- Full añade `adaptive_codex.report_instructions(...research=True,semantic=True)`: investigación pública de fundamentos/earnings/hechos, autoridad técnica del snapshot, fuentes con fechas, fuentes como datos, no instrucciones; fecha prepared_at; salida JSON.
- `adaptive_stage.py:275-299`: triage_repair usa MISMO prefijo de mantenimiento y mismo schema, mantiene research de noticias según config; la reparación es un objeto dentro del input, creado por `adaptive_repair.repair_context`.
- Reparación39: corrección única, mismo contrato/fuentes congeladas, puede retirar una propuesta injustificada; añade explícitamente35/34/37/38/39, sin nueva autoridad financiera. Las instrucciones de29 se sustituyen por35 antes de enviarse (`adaptive_repair.py:36-139`).

No se mandan todos los prompts históricos acumulados: los bloques35 sustituyen muchos anteriores. Sí permanece contenido viejo dentro del consolidado35, además de overlays posteriores.

Reconstrucción local exacta de concatenaciones y wrappers (sin prepare/modelo), caracteres Unicode, no tokens:

| Parte | Caracteres |
|---|---:|
| Prefijo full39 efectivo | 77.380 |
| Prefijo mantenimiento39 efectivo | 86.592 |
| adaptive_revision35 | 20.440 |
| volume_arithmetic25 | 1.225 |
| evidence_direction27 | 806 |
| reader_style35 | 4.451 |
| strength_evidence31 | 2.262 |
| reader_report35 | 1.709 |
| catalyst_editorial33 | 4.600 |
| volume_rubric34 | 2.389 |
| support_validity37 | 2.972 |
| option_origins39 | 1.542 |

Contextos **ORIGINALES38**, leídos de `logs/batch/2026-10-16/15-58-24/adaptive/<ticker>/<kind>.input.json`:

| Original | Archivo completo, caracteres | comparison serializado compacto | reference | slim | research_memory |
|---|---:|---:|---:|---:|---:|
| APP triage |225.045|105.488|46.230|28.453|ausente|
| AUR triage |206.078|97.132|47.156|32.681|ausente|
| IBKR triage |216.717|90.186|50.987|30.906|ausente|
| IBKR report |246.970|90.186|50.987|30.906|24.726|

Las columnas de campos se calcularon con JSON.stringify; el archivo completo usa su formato original. No son sumas exactas ni métricas de coste. En APP, deterministic ocupa69.101 y latest_published_review22.100 caracteres. En AUR latest_published_review34.161. `adaptive_delta.py:26-61` enumera diferencias exactas sin materialidad automática. `adaptive_context.py:42-105` ya representa duplicados mediante aliases. Esto contradice una acusación de repetir indiscriminadamente todos los objetos, pero no elimina la carga de árboles/pointers/comparaciones. No medir degradación cognitiva sin experimento controlado.

## Requisitos financieros vigentes: qué decide cada capa

### Soportes

`stock_analysis_semantic_v12.md:47-100` exige evaluar origen objetivo, papel comprador actual, fortaleza y selección por separado. Un origen inferior no necesita múltiples defensas ni un rebote nuevo; un mínimo móvil/strike aislado tampoco es automáticamente soporte. Un soporte por encima de cotización requiere vigencia positiva, no solo «no se ha probado ruptura». Se permiten ambas compras ausentes y se revisan también ausencias anteriores.

Hay convenciones cuantitativas reales, pese a que no se permite una regla automática de ruptura: ventanas aproximadas de1ATR/1EM y2ATR/2EM, diferencia de5 puntos para selección, proximidad~0,35ATR para mismo bloque salvo independencia clara, amplitudes preferidas1%/1,5% y límite2% (`v12:49-56`). La prohibición de porcentajes/ATR/cierres automáticos se refiere a declarar ruptura/forzar cambios, no significa ausencia de parámetros en selección. No convertir esa distinción en contradicción inexistente.

Continuidad (`v12:20-25,48`) protege juicios válidos, permite error demostrado y mejora material; `adaptive_revision35:239-284` antepone vigencia a continuidad. `maintenance_change.py:8-20` rechaza quote_only/missing_from_snapshot/no_material_change/unresolved como justificación declarada. Eso comprueba contrato, no la verdad semántica de elegir backing_changed.

### Fortaleza

**Pesos correctos:** Estructura25 + Volumen20 + Opciones25 + Confluencia15 + Durabilidad15. No confundir orden ni dar25 a Confluencia.

`v12:109-132` define cinco componentes, subcriterios, categorías40/70/85/95 y pilares mínimos70/85/95. `semantic_report.py:441-448` valida componentes/pilares. Total y categoría se derivan; no son una probabilidad. Setup/10 no es Fortaleza/10, y Tesis/10 excluye mera caída/técnico sin transmisión al negocio (`v12:27-42`).

Volumen es el componente realmente aritmético bajo fuentes estructuradas seleccionadas: `volume_arithmetic.py:15-57` usa Decimal, distancia al centro, cinco subcriterios, recencia de sesiones y techos34. `volume_arithmetic.py:128-179` verifica la suma de fuentes declaradas; null permite herencia exacta o deja el juicio cuando no hay pareja estructurada completa. No garantiza que cualquier texto/selección de fuente sea financieramente pertinente. `volume_rubric.py:38-75` añade techos al contexto, no decide niveles ni asigna notas.

La eliminación34 de penalización doble por distancia de POC/HVN está implementada en líneas49-51; muestra/repeticiones/recencia/magnitud conservadas. Dirección27 impide usar rechazo bajista como rebote comprador. No recomendar retirar esos controles por simplificar.

Opciones31/39 distingue cobertura muestreada, dominante frente a exclusivo, OI agregado dirigido frente a gamma elegible TOP y observado frente a soporte comprador. `semantic_report.py:262-295` exige para origen dirigido disponible un put observado, fecha no anterior al snapshot y OI o gamma positivo. Fecha de expiración se compara por día: no afirma precisión intradía de expiración. Cuestión temporal delegada al análisis de datos.

### Extensión inferior

`support_validity_v37.md` exige estimación prospectiva, no defensa exactamente observada en el límite, y coherencia con penetración aceptada. Prohíbe ampliar solo para acomodar la cotización. `support_validity.py:40-94` comprueba bound positivo finito<=borde inferior, fuentes CURRENT/slim resolubles y no unavailable, y vincula rango/fecha. Null item hereda SOLO rango idéntico; cambio/retirada no hereda. El programa no valida que el número sea económicamente sensato ni una probabilidad: es juicio del modelo y metadata visual. Fecha no se renueva al heredar. Esto es límite del diseño, no prueba de que todas las estimaciones sean erróneas.

### Noticias y routing

`daily_maintenance_semantic_v35.md:18-43,74-106` separa retain/update/escalate/blocked, incertidumbre esencial de imperfección normal, hecho empresarial de opinión y propuesta insider de ejecución. Riesgo verdadero impide publicar mantenimiento; falta técnica esencial bloquea, no la arregla un modelo mayor. `adaptive_codex.py:78-103` permite investigación full en fuentes primarias y no mezclar nuevos precios web. `reader33` selecciona drivers actuales sin borrar hechos internos; una nota nueva no se introduce bajo mera revisión editorial.

La guarda de cobertura/frescura no demuestra exhaustividad o recepción completa si el proveedor marca incorrectamente ok; véanse hallazgos de datos. Estos fallos reducen el valor de un retain aunque el modelo razone coherentemente sobre su entrada.

## F1 — Dos compras incoherentes pasan la ruta full

**Clasificación:** defecto demostrado; confianza alta. Impacto potencial medio/alto: plan lector con compras duplicadas o Washout superior, contrario a objetivo vigente. No se ha observado en publicaciones de la muestra.

**Causa:** `semantic_report.py:467-471` retorna para>=35 tras validar cada zona por separado. No comprueba relación entre Entry/Washout. `v12:52,79-83,133,148` pide bloques distintos, Washout inferior. `full_document:681-710` llama esta función; `validation_result` devuelve ok después; `publication_fields` proyecta el resultado.

**Reproducciones locales (recibos auténticos como fixture, payload mutado SOLO en memoria y binding sintético; NO son ejecución modelo39 ni publicación):**

- AUR full36, `logs/batch/2026-10-14/16-07-07/adaptive/AUR`, contexto proyectado39. Control: Entry4.97–5.03, Washoutnull, ok. Sustituir ambitious_entry por deepcopy(entry): ambos4.97–5.03, ok.
- AMD mismo lote. Control: Entry580–583, Washout531–535, ok. Intercambiar los dos bloques completos: Entry531–535, Washout580–583, ok, y `publication_fields` se construye. No cambia fuentes ni cálculo interno de cada bloque.

**Contraste favorable:**45 publicaciones originales del16oct,26 con ambas compras,0 duplicadas/solapadas/invertidas. APP no publicado. No existe evidencia aquí de pérdidas reales o de defecto en todas las decisiones. Una geometría no trivial entre estructuras próximas seguirá necesitando juicio; no extrapolar a una regla rígida0,35ATR.

**Recomendación:** decidir una validación mínima de relaciones que ya son inequívocas en el mandato —duplicación exacta, orden de Washout— compartida por ambos roles, sin clasificador de prosa ni nuevo modelo. Preservar posibilidad de zonas próximas realmente independientes. Criterio: originales válidos sin cambios; controles duplicado/invertido rechazados; absent/soloEntry/promoción legítima siguen pasando. Solo propuesta.

## F2 — TLN: ubicación redundante de la misma cita causa rechazo y repuntuación

**Clasificación:** defecto de contrato entre procedencia ya aportada y herencia; confianza alta en reproducción. Impacto observado: una reparación real, Volumen13→16 y total+3; no se afirma cuál nota refleja mejor el soporte.

Original: `logs/batch/2026-10-16/15-58-24/adaptive/TLN/{input.json,triage.response,triage_repair.input.json,triage_repair.response}`, revisión38.

La primera respuesta promueve Washout349.5–351.5 a Entry conservando componentes19/13/8/11/10. Cita s38, el CURRENT Washout autenticado, en `change_review.previous_evidence=[s39,s38]`, pero no lo duplica en `plan.entry.evidence`. `volume_arithmetic._inherited_buy_volume:59-77` solo busca en evidence; luego `validate:139-152` exige seleccionar pareja para cálculo nuevo. Error único: `entry: select_profile_and_reaction_sources`.

Contrato visible: `daily_maintenance_semantic_v35:59-65` pide precisamente previous_evidence para justificar cambio y exige CURRENT. `volume_arithmetic_v25:5,10` exige pareja al crear/cambiar Volumen y permite null para rango/Volumen exactamente iguales. `adaptive_revision35:219-220` permite contexto histórico entre campos del mismo plan. No hay orden visible equivalente que explique que la misma cita CURRENT deba repetirse en evidence para conservar aritmética al promover.

**Reproducción:**

1. Original autenticado con binding de fixture: rechazo único citado.
2. Añadir solamente `s38` a `plan.entry.evidence`: validación ok, rango349.5–351.5 y Volumen13. No cifra/texto/juicio/fuente nueva.
3. Recibo de reparación real: ok, añade s38 pero también calcula Volumen16 y afirma que la promoción requiere nuevo cálculo. El mismo rango y otros componentes se conservan.

Explicación alternativa considerada: separar evidence de previous_evidence puede ser una disciplina deliberada para distinguir respaldo y motivo de cambio. Eso protege una responsabilidad real, pero en este caso el bloque opuesto está autenticado, sus cifras coinciden exactamente y la misma respuesta declara herencia; la reproducción demuestra que no falta información, solo su ubicación duplicada. La severidad financiera es moderada: no se prueba que16 sea incorrecto ni que el código eligiera automáticamente esa nota.

La protección de herencia es necesaria: origen CURRENT exacto, mismo rango/Volumen, no ancla vieja ni resistencia. Esa protección no exige conceptualmente duplicar la ubicación de una referencia ya autenticada al mismo bloque. La alternativa de recalcular puede ser admisible si se justifica materialidad propia; aquí la explicación invoca la selección principal/corrección de contrato como necesidad, precisamente lo que pretendía evitar la herencia de la zona.

**Recomendación:** resolver procedencia de herencia desde las citas tipadas pertinentes del cambio, con iguales comprobaciones de identidad CURRENT/rango/Volumen, o aclarar de forma inequívoca el contrato si se decide conservar la duplicación. La reparación debe señalar la posibilidad de corregir únicamente la cita y conservar juicio, sin dirigir una nota. No automatizar conservar13 ni publicar una corrección. Criterio: original TLN válido al reconocer misma procedencia; referencia soloancla/stale/rango distinto/Volumen distinto siguen rechazados como herencia; repetición de repairs no repuntúa sin motivo financiero independiente.

## F3 — Dos reglas de Volumen incompatibles en el prefijo39

**Clasificación:** contradicción literal demostrada; riesgo plausible sobre decisiones/coste, no daño observado atribuible.

`adaptive_revision35.md:207-212` conserva la regla antigua: superar15 necesita el «stronger <=3% gate». Después se concatena `volume_rubric_v34.md:7-11`, que elimina distancia como condición de los techos. El financiero v12:126 y código `volume_arithmetic.py:49-51` también usan34. La búsqueda en ambas concatenaciones efectivas39 confirmó presencia simultánea.

La precedencia del overlay34 y sus nombres ofrece una explicación razonable para que el modelo aplique lo correcto; no decir que todos los resultados usan la fórmula vieja. Además la aritmética de una pareja explícita completa rechazaría una suma antigua incompatible, por lo que parte del impacto plausible es reparación/coste o selección equivocada, no necesariamente publicar un cálculo incorrecto. Sin embargo adaptive35 se presenta como consolidación que reemplaza34 y mantiene el texto obsoleto, por lo que el modelo recibe una tarea evitable de reconciliar instrucciones.

**Recomendación:** próxima versión con una sola definición vigente de rúbrica y manifiesto de partes. Preservar bytes/prompt de contratos congelados, no corregir retrospectivamente recibos. Prueba de aceptación: ensamblado nuevo contiene una sola regla de techos; replays históricos siguen su revisión. No otro overlay que simplemente niegue otra vez el anterior.

## F4 — Certificado de plan_explanation: coste real y valor probatorio limitado

**Clasificación:** complejidad contractual / decisión discutible, no defecto demostrado por sí sola. Protege el examen de texto dependiente sin analizar prosa; no retirarlo sin reemplazo.

8 reparaciones originales16oct: GEV,LEU,LRCX,QBTS,RKLB,SOFI,SPCX por plan_coherence; TLN por Volumen. Denominador46 tickers,26 publicaciones update;8 reparaciones de modelo no equivalen al único reintento del lote. 7/26 updates requirieron confirmar esta parte del contrato. El patrón ya aparece en15oct.

`review_contract.py:123-177` exige wrapper si cambia rango. `adaptive_revision35:19-31` define campos null como certificación de que el texto previo sigue aplicando. No se valida semánticamente esa afirmación.

GEV16oct: primera respuesta cambia Washoutnull a869–875 y mantiene Entry898–902. Rechazo único plan_coherence. Reproducción modifica SOLO:
```json
{"plan_explanation":{"setup_reason":null,"conclusion":null,"reasons":{"entry":null,"ambitious_entry":null}}}
```
en vez de `plan_explanation:null`; todo pasa, mismas cifras/motivos/Setup/conclusión y componentes20/14/0/7/11. La reparación real hace ese certificado y ajustes de redacción interna; no una nueva investigación necesaria. SPCX además tenía una conclusión nueva y revisada por la ruta standalone antes de fallar por wrapper ausente.

**Recomendación:** unificar el lugar de autoría/revisión de dependencias y hacer inequívoco en el schema el certificado requerido en la misma llamada; comparar alternativa de un solo bloque de cambios y revisión frente a dos rutas de texto. No rellenar certificados automáticamente ni dar por revisado texto no examinado. Medir reducción de reparaciones manteniendo detección de contradicciones reales, autoridad y conservación literal de texto no afectado.

## F5 — Convenciones, precisión y evaluación

**Clasificación:** falta de evidencia empírica, no demostración de mala metodología.

No se halló validación fuera de muestra de pesos25/20/25/15/15, fronteras70/85/95, diferencia5, ventanas1/2ATR-EM,0,35ATR, amplitudes1–2%, ITV5, reacción5sesiones o pisos estimados. Los tests prueban identidad, aritmética y aceptación; no rentabilidad ni que fortaleza70 sea mejor económicamente que69.

Opciones25 es una elección de peso. Los otros componentes permiten valorar soporte sin opciones, pero máximo sin ellas75, y pilares limitan categorías. La liquidez/multi-expiry afecta Opciones y Durabilidad por aspectos distintos; strength31 advierte no penalizar automáticamente también Estructura/Confluencia por la misma ausencia. Eso reduce doble conteo, no demuestra independencia estadística de componentes derivados del mismo precio/volumen.

Pilares mínimos provocan discontinuidades y obligan a revisar subcriterios cuando suma cruza70/85/95 sin cumplirlos; esta es una decisión metodológica, no simple aritmética ni probabilidad calibrada. No cambiarla por intuición durante esta auditoría.

La extensión37 puede ser razonada y prospectiva, pero un nivel exacto no equivale a intervalo de confianza; el código verifica vinculación y cotas elementales, no capacidad de acotar drawdown. La presentación verde puede comunicar más seguridad que la evidencia disponible: evaluar comprensión del usuario y resultado, no añadir un margen universal.

**Propuesta de evaluación futura, sin ejecutarla:** cohortes cronológicas de todas las preparaciones naturales (incluidas failed/blocked), registrar conjunto conocido entonces y motivos; separar nacimiento/cambio/conservación/promoción, regímenes y liquidez. Métricas de estabilidad y errores humanos adjudicados de vigencia/materialidad; cobertura y latencia de riesgos empresariales; visita/penetración/recuperación de zonas y excursiones adversas por horizontes predefinidos; ordinalidad de fuerza y acierto de extensiones. Comparar con conservar plan y una referencia técnica simple acordada; medir abstención/coste/turnover. Evaluador ciego a revisión/resultado posterior cuando juzga corrección ex ante. No calcular P&L sin regla de ejecución/salida/costes autorizada: el producto actual no define una estrategia completa. No atribuir mejora38 a la política cuando entre capturas también cambió mercado/datos/modelo.

## F6 — Estado de tesis no es un dato independiente

`docs/estrategia_compra_bolsa.md:59-66` registra acuerdo: análisis diario como protección ante deterioro/ruptura, nota y estado distintos. No modificar este cuaderno convirtiendo propuestas en acuerdos.

`semantic_report.py:114-125` solo tipa thesis_score/thesis_reason/setup_score/setup_reason/narrative, catalizadores/evento/plan/conclusión. `v12:29-31` pide distinguir tesis rota/deteriorada/floja/correcta/buena/fuerte, pero en prosa; riesgo thesis_change en mantenimiento es una señal interna de routing. Búsqueda por estado_tesis/thesis_status/thesis_state/estado de tesis en código/prompts no encuentra un campo operativo. Score_category deriva de la nota; no suple el eje independiente.

**Clasificación:** carencia de producto respecto al propósito, con reglas operativas todavía no acordadas. Riesgo: consumidor/usuario infiera estado a partir de nota o no advierta cambio de régimen de tesis. No prueba que el modelo omita todos los deterioros.

**Recomendación:** acordar definición y forma de mostrar «estado de tesis» y su fecha/evidencia/uncertainty separados de nota, sin reintroducir stops ni órdenes automáticas. Luego verificar escalada y presentación explícita cuando corresponda. No imponer enum/acción durante esta auditoría.

## Muestra real favorable y adversa

Se leyeron razones de46 triage16oct y45 proyecciones publicadas, más los originales de las reproducciones y15 reparaciones recientes seleccionadas cronológicamente (no todas las ejecuciones históricas).

- APP38 blocked: reconoce que el put250 falta del TOP, no infiere desaparición ni pierde soporte por ranking. Sirve de evidencia favorable a disciplina financiera y de defecto de cobertura que39 intenta resolver, no éxito financiero39.
- AMD/ASML/CCJ16oct retain: usan sesión cerrada15oct que penetra y recupera, no exigen una regla fija de cierres. Los demás datos parciales de volumen identificados por agente de datos no convierten esta barra15 en parcial.
- AUR16oct update de motivos tras gamma/reacción, conserva rangos/componentes y fragilidad del vencimiento. Contraejemplo a que todo detalle adicional fuerce subir nota.
- NVDA/SPCX16oct: promoción de soporte inferior con cifras/componentes conservados; demuestra que el diseño puede promover sin optimizar por cuota.
- GEV añade segundo bloque y deja principal; repair por certificado descrito, sin nueva señal.
- IREN/MP15oct: incorporan soporte antes ausente con una defensa histórica; el motivo no trata baja confluencia como inexistencia. No demuestra que comprar fuese rentable.
- IBKR16oct escalate/full: resultados ya publicados amenazan la premisa protegida y evento central; no escala por mera proximidad de calendario. Único full del lote según sus artefactos; causalidad de noticias concretas es juicio del modelo.
- TLN: reparación cambia Volumen aunque herencia13 era validable con la misma cita; no contar publicación correcta como prueba de que esa repuntuación era necesaria.

No se adjudicó rentabilidad posterior, no se descargaron cotizaciones futuras ni se verificaron externamente todas las noticias. Éxito técnico de publicación y criterio financiero son evidencias distintas.

## Pruebas ejecutadas y límites

Comandos con venv, `-B`, sin cacheprovider, temporales bajo `.tmp/audit-financial-20261017-*`; no modificación de tests.

1. Primera batería conjunta timeout120s: resultado inconcluso, no contabilizado como aprobado.
2. `test_support_selection_v38.py`:16 passed,20.34s.
3. `test_support_validity_v36.py tests/test_volume_rubric_v34.py test_support_only_v35.py`:50 passed,1 failed,196.45s.
4. Total concluido66passed/1failed. Fallo: `tests/test_volume_rubric_v34.py:231` espera config activa34o35; config39. Es una expectativa de activación envejecida, no fallo probado en cálculo34. No se ocultó con deselect ni se editó test.
5. Repros mínimos F1,AUR/AMD; F2,TLN; F4,GEV ejecutados con controles originales y copias en memoria.

Valor probatorio de pruebas leídas:

- `test_support_selection_v38.py:71-89` autentica los9 escenarios ausentes de full36; comenta explícitamente que NO elige/rechaza zonas.
- `test_support_validity_v36.py:55-91` usa límites sintéticos `lower*.987654321` para47 faltantes y conserva19 conocidos. Prueba contrato/binding/no mutación, NO calibración de pisos.
- `test_support_only_v35.py:83-105` comprueba preservación de46 bases al retirar resistencia. Justifica migración sin alterar finanzas, no la calidad de cada soporte.
- Tests34 de cálculo y límites son más fuertes para aritmética; no convierten esos techos en hipótesis financieras validadas.
- Los replays con revision cambiada son fixtures de compatibilidad local. Nunca llamarlos recibos reales generados por39.

## Código mínimo reproducible

Ejecutar desde raíz con venv `python -B`; no llama modelos ni red, todos los originales solo se leen:

```python
import json
from copy import deepcopy
from pathlib import Path
from src.local_runner.adaptive_context import model_context
from src.local_runner.semantic_report import (
    full_document, maintenance_document, validation_result,
)
from test_plan_scope_v29 import bound

# F1: duplicación full, contexto39 sintético sobre original36.
p = Path('logs/batch/2026-10-14/16-07-07/adaptive/AUR')
c = json.loads((p/'input.json').read_text(encoding='utf8'))
c['routing_revision'] = 39
r = json.loads((p/'report.response').read_text(encoding='utf8'))
r['plan']['ambitious_entry'] = deepcopy(r['plan']['entry'])
d = full_document(r, model_context(c), binding=bound(c, r, 'report'))
assert validation_result(d).ok
assert d['plan']['entry']['range'] == d['plan']['ambitious_entry']['range']

# F2: mismo dato CURRENT ya citado; solo duplicar su ubicación.
p = Path('logs/batch/2026-10-16/15-58-24/adaptive/TLN')
c = json.loads((p/'input.json').read_text(encoding='utf8'))
r = json.loads((p/'triage.response').read_text(encoding='utf8'))
assert 's38' in r['update']['plan']['entry']['change_review']['previous_evidence']
r['update']['plan']['entry']['evidence'].append('s38')
d = maintenance_document(r, model_context(c), binding=bound(c, r))
assert validation_result(d).ok
assert d['plan']['entry']['strength']['components']['volumen'] == 13

# F4: certificado sin nuevos textos ni cifras.
p = Path('logs/batch/2026-10-16/15-58-24/adaptive/GEV')
c = json.loads((p/'input.json').read_text(encoding='utf8'))
r = json.loads((p/'triage.response').read_text(encoding='utf8'))
r['update']['plan_explanation'] = {
    'setup_reason': None, 'conclusion': None,
    'reasons': {'entry': None, 'ambitious_entry': None},
}
d = maintenance_document(r, model_context(c), binding=bound(c, r))
assert validation_result(d).ok
```

## Clasificación de parches y propuestas

| Mecanismo | Evaluación | Qué conservar / qué falta |
|---|---|---|
| Fuentes exactas y binding del runner | Protección necesaria | No sustituir por prosa/checksums del modelo; identidad no demuestra pertinencia |
| v25 aritmética seleccionada + dirección27 | Mejora integrada | Cálculo exacto; corregir redundancia de ubicación TLN sin perder autoridad |
| v28 vigencia antes de continuidad | Mejora integrada, juicio a observar | Evita gracia artificial5d y conservar soporte perdido; no prueba futura rentabilidad |
| v29/v35 retirada de salidas/resistencia | Preferencia de producto legítima y compatibilidad necesaria | No restaurar campos retirados; añadir relación inequívoca entre compras |
| v30–33 separación lector/auditoría/editorial | Mejora integrada | Preserva historia/riesgos; evaluar legibilidad/materialidad, no longitud como gate |
| v31 detalle de opciones y v39 observación dirigida | Mejora de datos justificada | No presume liquidez ni fuerza, no compara bases OI distintas;39 sin modelo natural observado en esta auditoría |
| v34 quitar doble techo por nodo | Metodología coherente internamente | Código y cálculo correctos bajo convenio; limpiar contradicción en prefijo, evaluar resultados |
| v36/37 estimación de extensión | Preferencia visual + hipótesis financiera | Binding/no re-datar correctos; precisión y sentido del verde no validados |
| Certificado plan_explanation | Protección de revisión + complejidad redundante | No borrarlo sin alternativa; reducir rutas de autoría y reparaciones vacías |
| Congelados históricos | Compatibilidad justificada | Preservar contratos; no deuda eliminable por antigüedad |
| ITV5 y medium/high | Política operativa | No prueba suficiencia/óptimo; evaluar cobertura/coste/latencia de riesgos |

## Matriz de cobertura

| Área | Estado | Evidencia y límite |
|---|---|---|
| Config/identidad/ensamblado39 | Comprobado por lectura y reconstrucción | Sin ejecución de modelo39 |
| Prompt full/maintenance/repair | Revisado integralmente en montaje vigente | Contradicción34/35 reproducida; no test cognitivo del modelo |
| Geometría Entry/Washout | Defecto reproducido | Originales45 sin caso publicado |
| Origen/vigencia/ausencias/promoción | Revisado + muestra real | Interpretaciones razonables; no rentabilidad adjudicada |
| Volumen | Reproducción y tests |66pasos financieros/globales de este ámbito,1expectativa obsoleta; TLN real |
| Opciones cobertura/OI/frescura | Parcial, coordinado con datos | Muestreo/date-only; no nueva captura |
| Extensiones | Contrato probado y muestra | Estimación económicamente no validada |
| Noticias/routing | Instrucciones y casos leídos | Integridad del feed externa al razonamiento; hallazgos de datos |
| Riesgo/tesis separada | Requisito/esquema contrastados | Definición operativa de estado y salidas pendiente del usuario |
| Parches/herencia/repair | Contrastado con originales | F2/F4 evitan justificar excepción solo por pasar test |
| Utilidad financiera/predictiva | Pendiente | Necesita evaluación cronológica acordada, no más tests contractuales |
