# Subauditoría de integridad, memoria, recuperación y consumidores — 17-10-2026

Documento de trabajo para integrar en la auditoría principal. Solo se han leído originales y ejecutado pruebas locales aisladas. No se ha llamado a modelos, recuperado o publicado un ticker, leído servicios remotos ni cambiado código, configuración, prompts o tests. Las operaciones de publicación de las reproducciones se sustituyeron por transportes simulados que no realizan E/S externa.

## Diagnóstico

La separación entre informe mantenido, ancla full, fecha financiera y memoria de revisión funciona en la muestra real examinada. Hay controles útiles contra cambio de base/ancla, contratos distintos, memoria alterada, fuentes de otra época, propiedad desconocida y reutilización ambigua. Las migraciones de presentación y el retain no equivalen a una revisión financiera nueva; el código y los originales examinados mantienen esa distinción.

La frontera durable posterior al modelo está menos protegida de lo que sugiere la descripción general de integridad. Se han reproducido tres fallos de control distintos: aceptación de una respuesta local cambiada después de su recibo, publicación de espejos JSON cambiados después de validar y omisión de frescura al reanudar una revisión ya validada. No se ha encontrado corrupción histórica en la muestra: son defectos de detección y control demostrados con copias. También se confirma que la publicación puede quedar parcialmente visible y que el intento fallido adaptativo no alimenta el estado de intento por ticker de los consumidores.

## Alcance y método

Lectura inicial de AGENTS.md y documentación canónica: handoff_current, pending_work_current, codex_adaptive_analysis y operations. Se contrastaron después los módulos activos y tests, sin adoptar como conclusiones los resultados anteriores.

Responsabilidades examinadas:

| Etapa | Implementación principal | Resultado |
|---|---|---|
| Identidad/propiedad | src/local_runner/ownership.py:5-17 | Requiere registro único y booleano explícito; no confunde ausencia con false. Override explícito individual en adaptive_stage.py:857-860. |
| Carga de autoridad | analysis_state.py:30-58; adaptive_current.py:16-47 | Ancla separada de current; comprobaciones de símbolo, cronología y vínculo del current. Fallback local solo ante excepción de lectura, con la limitación indicada en INT-03. |
| Preparación congelada | adaptive_stage.py:32-46,96-203 | Datos no se refrescan tras admisión de modelo; se congelan policy e instrucciones. Nuevas preparaciones39; originales36/38 usados bajo sus versiones. |
| Admisión/reuso | adaptive_stage.py:275-395; semantic_binding.py:14-60 | Input, instrucciones, schema, modelo y esfuerzo se comprueban. Vínculo de respuesta en memoria fuerte durante la llamada, incompleto al reabrirla. |
| Memoria | review_memory.py:11-91 | Datos, report_key y anchor_key comprobados; retain conserva época financiera y añade revisión actual; full abre época nueva. |
| ITV | adaptive_policy.py:80-97; adaptive_stage.py:398-444 | Cinco sesiones; confianza en full Sol high; recuperación usa ITV original autenticada, no recalculada para forzar otro modelo. |
| Publicación | adaptive_stage.py:742-817; gcs_uploader.py:79-224 | Lock local y guardas antes de escrituras, reintento desde staging. No transacción multiformato ni digest durable del bundle. |
| Recuperación | recover_adaptive_receipt.py:17-54 | Copia originales, prohibición de modelo, propiedad antes de execute, guardas normales. Atajo de revisión validada evita revalidación de frescura. |
| Sheet | analysis_worker/reports.py; run_sync.py; controller/analysis_sheet.py | Consume espejo válido y campos estructurados. Universo completo, categorías/fuerza/ausencias y extensión tipada comprobadas. |
| Lectura web/móvil | reports_reader/main.py; mobile_api/projection.py | Lecturas independientes por formato; móvil distingue último informe válido/intento solo si existe failed en latest. La ruta adaptativa no lo escribe. |

Las rutas de adquisición, calidad financiera, prompts finales, transporte de modelo, concurrencia de admisión y métricas globales se coordinan con los demás ejes de la auditoría. Aquí se revisa su frontera con integridad y publicación, no su totalidad.

## Muestra de originales y contraevidencia

Corpus A: logs/batch/2026-10-14/16-07-07/adaptive, full36 expresamente solicitado, 46 publicados. Corpus B: logs/batch/2026-10-16/15-58-24/adaptive, revisión natural38, 45 publicados de46 y APP bloqueado. El total son92 combinaciones ticker/ejecución, con91 publicaciones; no92 empresas independientes. Los101 recibos exitosos contienen llamadas de mantenimiento/full/reparación, no101 análisis independientes.

Comprobación independiente sobre ambos corpus:

- 101 recibos exitosos: SHA del input coincide con el recibo y respuesta coincide, tras quitar blancos exteriores, con el único agent_message terminado del evento original. Cero discrepancias.
- 91 payloads publicados:47 full,26 updates y18 retains. Los91 pasan read_memory, reference_document y el parser estructurado del controlador; Entry/Washout de espejo JSON coinciden con semantic_report. Cero discrepancias.
- 81 bundles tienen latest.md staged; los81 coinciden exactamente con analysis_markdown del JSON. Diez retains no generaron MD nuevo: la ausencia de ese fichero staged es coherente con no cambiar presentación.
- En el natural16-10,18 retains conservan exactamente generated_at, latest_price, slim_as_of, slim_snapshot, generation_model y reasoning_effort del CURRENT previo.
- Los26 updates utilizan completed_at de su recibo original. Los44 mantenimientos conservan ancla y last_full_report_at exactos. Los45 publicados guardan en latest_review el slim congelado de la revisión nueva. Cero discrepancias.

Casos con intención de muestreo explícita:

| Caso | Qué discrimina | Qué demuestra / límite |
|---|---|---|
| IBKR16-10, full38 | Escalada real y nueva época full; recibo high con10 búsquedas | Original congruente con eventos/input y proyección. La copia permite probar la debilidad durable sin introducir información futura en el juicio financiero. |
| CAT16-10, update38 | Cambio con Entry728-732, extensión723 y Washout ausente | Fecha de respuesta original, ancla conservada, espejo tipado congruente. Base para reproducciones de staging/frescura; sus números originales no se modifican. |
| AMD16-10 y todos18 retains | Caso ordinario sin publicación financiera nueva | Fechas y snapshot de informe exactos; memoria registra revisión. No se atribuye nueva investigación a la fecha antigua del informe. |
| APP16-10, blocked38 | Fallo después de respuesta correcta | failure.json: triage_blocked_insufficient_evidence a16:19:48UTC. CURRENT previo generado15-10 07:39:24UTC, revisión12:17:20UTC. Se preserva; no existe nuevo payload publicable. |
| AUR09-10, corrección y memoria | Incidente real desfavorable, no solo fixtures exitosas | test_correction_memory reconstruye el artefacto defectuoso y su reparación autorizada; el digest viejo falla y el rebinding preserva la historia. No se reejecutó recovery real. |
| USAR09-10, full congelado23 | Ausencia de compras y protección no aplicable con owned=false | Replay de respuesta original en copia con reloj histórico y NO MODEL/NO REFRESH; conserva números/textos/fecha. Prueba de compatibilidad y validador, no validación financiera nueva. |

## INT-01 — El artefacto durable no queda ligado de extremo a extremo a lo que se validó

**Clasificación:** defecto demostrado de detección de corrupción/edición local; impacto potencial alto, alcance reuso de recibos y publicación desde staging, confianza alta. No es una demostración de ataque, firma criptográfica de OpenAI ni corrupción ocurrida en producción.

Dos síntomas de la misma responsabilidad incompleta:

1. adaptive_codex.py:168-171,235-247 guarda hashes del input, instrucciones y esquema, pero no un hash de la respuesta en el recibo exitoso. adaptive_stage.py:303-322 verifica ese contrato y vuelve a leer el .response actual. semantic_binding.py:40-50 crea entonces el hash de respuesta sobre ese texto actual. El evento original duradero existe, pero no se compara en ese camino. El chequeo de eventos de noticias autentica su log; no autentica el texto de respuesta reabierto.
2. adaptive_stage.py:750-780 comprueba review/base/ancla/memoria antes de publicar, pero no verifica que latest.json/latest.md/latest.html sean exactamente el bundle validado. read_memory utiliza reference_key, que en adaptive_cache.py:101-104 incluye fecha/modelo/Markdown, no los espejos plan/decision. Los consumidores leen plan/decision directamente: reports.py:121-141,215-250. El sobre semantic_report sí dispone de hashes (semantic_report.py:221-235,934-935), pero no liga los espejos ni el HTML y no se revalida allí.

**Reproducción R1, original copiado:** IBKR del16-10. Se copian instrucciones, policy, report.input, report.response, report.receipt y eventos a TemporaryDirectory. Se cambia únicamente summary.narrative de la copia de .response. El input se reconstruye desde input.json más guards/review_flags/itv/triage del input enviado. Con call_codex convertido en excepción NO MODEL, model_call(reuse_only=True), bind_response y full_document aceptan el texto alterado. Recibo y eventos copiados permanecen byte a byte iguales. Los hashes de todos los ficheros originales de primer nivel siguen iguales.

Salida relevante: altered_response_reused=true; altered_narrative_validated='CORRUPCION LOCAL DE AUDITORIA: texto sustituido despues de la llamada.'; original_receipt_unchanged=true; original_events_unchanged=true; originals_unchanged=True.

**Reproducción R2, staging copiado:** CAT del16-10. Se quita published_at únicamente de la copia de review.json para representar validación terminada/publicación pendiente. Se cambia solo plan.entry en latest.json de728-732 a800-810; semantic_report y Markdown permanecen728-732. read_memory acepta y publish alcanza el transporte simulado. No se cambia recibo, modelo, fuentes, rangos originales ni una sola publicación real.

Salida: unchanged_semantic_range={lower:728,upper:732}; mutated_plan_range={lower:800,upper:810}; upload_reached=1; memory_check_passed=true.

**Contraevidencia/protección vigente:** el binding durante una llamada impide modificar respuesta/base después de enlazarlas; los originales de101 recibos y91 payloads están congruentes. La suite rechaza cambios de input/modelo/schema/base/ancla y memoria. La narrativa libre no debe pasar por un clasificador de veracidad: aceptar un contenido financiero del modelo forma parte del diseño. El defecto es afirmar/reutilizar la procedencia original de texto que se cambió después, no que el renderer acepte prosa libre.

**Alternativas consideradas:** archivos locales confiables por contrato hacen poco probable una edición accidental, pero no dan la comprobación durable prometida y no protegen frente a un copy/restore equivocado. Revalidar solo JSON/schema o volver a llamar al modelo no detecta quién produjo el texto. Comparar todo el bundle con el artefacto validado sí resuelve ese problema sin tocar criterio financiero.

**Recomendación propuesta, no implementada:** recibo durable con digest de respuesta y manifiesto de bundle validado; en recibos históricos, comparar cuando sea posible con el agent_message original ya guardado, sin reescribir recibos congelados. Verificar espejos numéricos desde la autoridad tipada o ligarlos al manifiesto. Publicación verifica bytes y consistencia antes de la primera escritura.

**Aceptación:** controles negativos alterando por separado .response, plan, decision, semantic_report, MD y HTML deben fallar sin llamada pagada ni escritura externa; originales válidos y reintentos idénticos deben seguir pasando; no nuevas guardas de prosa y ninguna modificación retroactiva de originales.

## INT-02 — Revisión ya validada omite la comprobación de frescura en recuperación/publicación

**Clasificación:** defecto demostrado; impacto medio/alto si una publicación se retrasa más allá de24h, confianza alta. No se ha encontrado un caso histórico que haya publicado por esta vía datos caducados.

adaptive_stage.py:421-427 retorna review.json analysis_status=ok antes de leer input/policy o llamar data_ready. Se aplica también con reuse_only=True, que recover_adaptive_receipt.py:35 utiliza. publish (749-817) comprueba bases, ancla, revisiones más nuevas y memoria, pero no frescura. La verificación normal sí está en data_ready:238-253. La documentación y el comentario receipt_itv:398-402 afirman que la frescura sigue usando la hora actual.

**Reproducción R3:** copia CAT16-10 con marcador published_at retirado solo en copia; reloj local simulado23-10. data_ready directo rechaza stale_or_missing_prepared_timestamp. analyze(reuse_only=True) seguido de publish, con todos los transportes sustituidos y NO MODEL, acepta el candidate; data_ready_calls=0, bundle_upload_calls_simulated=1, remote_copies_simulated=2. published_at simulado23-10; generated_at sigue16-10 16:03:47UTC.

**No se confunde con redatado:** la fecha financiera queda bien preservada. El problema es admitir la publicación pendiente de una decisión tomada con fuentes que ya no cumplen la frescura exigida para la operación de recuperación. Una base que no cambió no demuestra que el mercado no cambió.

**Contraevidencia:** receipt-only sin review validada sí llama data_ready y mantiene ITV original; las guardas rechazan base/ancla/revisión más nueva y recovery execute comprueba propiedad actual. Los tests existentes cubren recuperación con reloj histórico y reintento parcial inmediato. Esas pruebas no cubren un review validado pendiente durante días.

**Recomendación propuesta:** distinguir explícitamente el compromiso inicial de una revisión y la reparación idempotente de un compromiso ya parcial. Antes del primer compromiso tardío, verificar frescura con reloj actual; un reintento exacto que solo completa copias de un commit ya aceptado debe regirse por una política explícita y trazable. No recalcular ITV para comprar otra llamada ni cambiar fechas del recibo; si ya no es publicable, mostrar la condición y esperar la siguiente preparación autorizada.

**Aceptación:** candidato validado con fuentes>24h no puede iniciar nueva publicación; candidato reciente y reintento parcial legítimo siguen funcionando; se preservan receipt completed_at, ITV original, ownership y guardas de base/ancla. Ninguna llamada de modelo por el mero vencimiento de staging.

## INT-03 — La publicación multiformato es secuencial y puede quedar parcialmente visible

**Clasificación:** comportamiento demostrado ante fallo inyectado y riesgo operacional plausible; confianza alta en el mecanismo, incidencia/frecuencia real no establecida. Prioridad media; no equivale a haber observado reportes contradictorios en GCS actual.

El plan de subida escribe latest.md, latest.html, latest.json, snapshots y espejo Sheet por separado (gcs_uploader.py:136-174,215-224). Después se guarda referencia full, current y review (adaptive_stage.py:781-809). El lock output/SYMBOL/adaptive_publish.lock es local (742-746); no ofrece exclusión entre hosts y las escrituras no usan CAS/generation match. El lector web sirve cada formato directamente sin manifest compartido (reports_reader/main.py:37-53,105-113).

**Reproducción R4:** build_real_upload_plan real y upload_artifacts real, con subprocess.run sustituido por un transporte en memoria que falla la tercera operación. Resultado: latest.md=new-md, latest.html=new-html y latest.json=old-json. La excepción queda visible; no se marca published_at. Esos lectores pueden observar el intervalo mixto, que dura hasta una reparación completa.

**Interacción adicional:** save_reference_payload escribe reference.json local antes del upload remoto (analysis_state.py:61-81). Con fallo simulado, el fallback local queda en nueva ancla aunque la remota no se actualice. La protección de current hace lo contrario, subiendo antes de actualizar fallback local (adaptive_stage.py:799-805). La guarda remota posterior normalmente impide publicar sobre ancla incompatible; el riesgo principal es inconsistencia transitoria/uso local divergente y trabajo posterior inútil, no prueba de publicación financiera incorrecta.

**Contraevidencia:** reintento desde staging está implementado y el test test_adaptive_maintenance_stage.py:338-371 demuestra idempotencia después de fallar current. Los lectores de Sheet usan espejo JSON válido y el sync no acepta universo incompleto. Los91 payloads originales analizados están congruentes. El lock y las guardas protegen correctamente el caso común de escritores de la misma instalación.

**Alternativas y recomendación:** documentar formalmente consistencia eventual puede ser suficiente si el producto acepta esos intervalos y el estado se hace visible. Para coherencia estricta, escribir versiones inmutables con hashes y cambiar un manifest/puntero confirmado por ticker al final; todos los lectores seleccionan esa versión. Un CAS de ese puntero aporta además defensa entre hosts. Empezar por delimitar el contrato de commit y observar fallos, no por duplicar validadores financieros.

**Aceptación:** inyectar fallo después de cada operación y verificar que consumidores ven una versión completa anterior o nueva, o un estado explícito pendiente; que ancla/current/memoria no avancen sin commit aceptado; que reintento no cambie fechas ni consuma modelo; incluir dos escritores con bases distintas si se pretende soportar varios hosts.

## INT-04 — El estado del último intento adaptativo no llega a los consumidores por ticker

**Clasificación:** defecto de observabilidad/integración demostrado en el recorrido de código; caso real APP16-10; impacto medio, confianza alta. No afirma que se haya redatado un informe viejo.

adaptive_stage.py:843-846 y877-879 guardan failure.json local. run_batch.py:2648-2663 y2712-2717 convierten ese fallo a resultado terminal; no se publica un latest failed por ticker en la ruta adaptativa. El resumen/progreso de lote sí conserva el fallo: esa es contraevidencia importante contra la afirmación de que el sistema lo oculta totalmente.

En cambio, mobile_api/projection.py:49-53,72-83 deriva last_attempt_status y last_attempt_at del latest público. Como APP conserva latest válido del15-10, ese contrato de consumidor no puede conocer su intento fallido del16-10. El test móvil39-44 presupone un latest.analysis_status=failed que el productor adaptativo no genera. Sheet consume el espejo del último informe válido (analysis_worker/reports.py:21-67) y el lector web normal omite analysis_status/error de su proyección (reports_reader/main.py:116-132). MD/HTML se sirven por separado sin estado de intento.

**Protección que debe conservarse:** preservar el último informe válido con su fecha verdadera es correcto. Sustituirlo por cifras vacías o fingir fecha nueva empeoraría el producto. El problema es que último informe válido y último intento son conceptos distintos y solo uno se transporta de extremo a extremo.

**Recomendación propuesta:** registro separado y versionado de último intento, estado/error/fecha y referencia al último informe válido. Consumidores muestran fallo/pendiente sin borrar ni redatar ese informe. No usar un failure JSON para reemplazar el ancla ni contaminar memoria de revisiones publicadas.

**Aceptación:** escenario end-to-end sintético con informe válido, intento blocked y posterior éxito: batch y API/Sheet/lector deben distinguir cada estado, mantener fecha/números del informe mientras falla y retirar aviso solo cuando corresponda; prueba que use productor y consumidor juntos, no solo fixture failed construido a mano.

## Clasificación de mecanismos revisados

| Mecanismo | Clasificación | Razón / guarda que conservar |
|---|---|---|
| CURRENT separado del full anchor | Mejora integrada y protección necesaria |44 mantenimientos naturales preservan época/ancla; evita reset ITV por cambios rutinarios. |
| Memoria autenticada y rebinding autorizado | Protección necesaria | Caso AUR prueba fallo real detectado y corrección exacta; no retirar integridad para que pase un artefacto. |
| Fechas de textos heredados y retain | Mejora integrada |18 retains conservan fechas/datos; actualización de revisión no es actualización de todos los hechos. |
| Recibo exacto + reuse_only | Protección necesaria, incompleta en frontera durable | Evita llamadas duplicadas y contratos mezclados; conservarla y cerrar INT-01/02. |
| Recuperación en staging separado | Compatibilidad/recuperación justificada | Original fallido no se reescribe como éxito; modelo prohibido; fechas originales. |
| Una reparación con retirada de propuesta inválida | Protección razonable | No obliga a editar ni a aceptar primera propuesta; matriz de tests distingue retain/update/full. No prueba calidad de la decisión modelo. |
| Migraciones32/35/36/38 de presentación | Mejora integrada con pruebas parciales | Mismo contrato financiero conservado; no son evidencia de nueva investigación ni de mejora predictiva. |
| Conversión legacy de escala en consumidor | Compatibilidad histórica, no guardia financiera | reports.py:346-358 y test_analysis_reports.py:272; no retirar sin revisar originales. No consta efecto en muestra actual. |
| Publicación secuencial/reintento | Solución con consistencia eventual, contrato incompleto | Éxito/retry cubiertos; fallos entre escrituras no proporcionan una vista atómica. |
| Último informe válido ante fallo | Protección correcta, integración incompleta | Debe combinarse con estado del último intento, no borrarse. |

## Pruebas ejecutadas y qué no demuestran

Comando base: .venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider. No se instalaron dependencias ni se habilitó red.

1. tests/test_adaptive_maintenance_stage.py, tests/test_semantic_contract_v3.py, test_review_continuity_v16.py, test_correction_memory.py, tests/test_adaptive_date_recovery.py, test_reaction_direction_v27.py: **88 passed,109 subtests passed**,47.55s.
2. Consumidor: test_analysis_reports, test_analysis_sheet, test_support_validity, test_support_only_sheet, test_analysis_sync_version bajo gcp_services/stock_controller/tests y mobile_api/tests/test_mobile_api.py, con el src del controlador en sys.path: **54 passed,10 subtests passed**,1.29s.
3. test_no_trade_stop_v24.py: **12 passed,14 subtests passed**,12.99s.

Total de esta subauditoría:154 tests y133 subtests. Los subtests no son muestras de decisiones financieras independientes. Adicionalmente, cuatro reproducciones nuevas inline con TemporaryDirectory y transportes simulados, más las dos comprobaciones independientes del corpus descritas arriba. Los scripts de comprobación no usan recovery execute ni modelos.

Evaluación crítica de las pruebas existentes:

- Positivo: no se limitan a roundtrip happy-path; hay memoria/base/ancla alterada, respuesta de contrato diferente, ownership/ausencia, fuente no vigente, fecha conservada y modelo prohibido. AUR y USAR usan artefactos reales, no únicamente respuestas diseñadas para pasar.
- Límite: los tests de publicación suelen sustituir _upload entero; no ejercitan las siete escrituras ni el lector entre ellas. La prueba parcial actual solo falla después de que el bundle ya se supone subido.
- Límite: las pruebas de ResponseBinding alteran la respuesta después de crear el objeto en memoria; no cubren respuesta alterada antes de reconstruir ese binding tras reinicio.
- Límite: frescura se congela correctamente para replays históricos; eso no prueba el caso de un review ya ok que se reanuda días después.
- Límite: fixture móvil failed representa un contrato que no produce la ruta adaptativa actual.
- Una respuesta original y una publicación congruente prueban ejecución/procedencia y transporte bajo estas comprobaciones; no prueban veracidad de noticias, predicción, rentabilidad ni selección financieramente óptima.

## Cobertura y pendientes

| Área | Estado | Evidencia/límite |
|---|---|---|
| Retain/update/full y fecha/ancla/memoria | Comprobado localmente |91 publicaciones,44 mantenimientos ancla exacta,154tests focalizados. |
| Respuesta durable y bundle validado | Defectos reproducidos |INT-01; originales de la muestra sin discrepancia. |
| Recuperación con recibo sin modelo | Comprobado offline | USAR y controles; pendiente cerrar atajo de review validada. |
| Frescura antes del modelo | Comprobado por código/tests | No equivale a frescura antes de publicar; INT-02. |
| Coherencia ante interrupción de upload | Parcial; riesgo reproducido | INT-03; no estado GCS actual consultado ni fallo real provocado. |
| Concurrencia multihost de publicación | Riesgo plausible, no comprobado en vivo | Lock local y ausencia CAS; no se afirma que hoy existan varios escritores. |
| Propiedad | Comprobado en entrada/recovery | Registro explícito y recuperación comprueban; publicación ordinaria usa propiedad congelada. No se ha probado un cambio de cartera durante llamada ni se propone una guarda financiera automática. |
| Consumidor Sheet/modelo tipado | Comprobado localmente |91 proyecciones y tests; tráfico/runtime cloud actual fuera de autorización. |
| Web/móvil y fallo por ticker | Brecha de contrato demostrada | Código productor/consumidor y APP; no lectura del cliente desplegado hoy. |
| Estado desplegado | Evidencia previa, sin nueva verificación remota | Artefactos de despliegue/docs son antecedentes; este trabajo no certifica tráfico ni código de imagen hoy. |
| Calidad financiera/predictiva | No inferible de estas pruebas | Debe evaluarse en otro eje; cero recomendaciones de compra resultan de esta subauditoría. |

## Propuesta de prioridades sin implementación

1. Cerrar INT-01 con identificación durable de respuesta/bundle y controles negativos. Cambio de integridad, sin modificar metodología ni prompts financieros.
2. Delimitar commit inicial/reintento parcial y cerrar INT-02 sin perder fecha ni ITV original.
3. Exponer estado de intento separado (INT-04), preservando último informe válido.
4. Decidir si la consistencia eventual observada es aceptable; si no, manifest de versión y CAS (INT-03). La misma definición de commit resuelve varias excepciones locales de publicación y fallback.
5. Mantener catálogo de pruebas por capa (sintética, replay, captura técnica, modelo real, resultado financiero), evitando sumar tests o publicaciones como evidencia predictiva.

Las guardas de fuente/autoridad/propiedad, una reparación acotada, no fallback silencioso, reloj/fecha original y separación CURRENT/full deben permanecer. Estas propuestas no autorizan un recovery, una nueva llamada ni un despliegue.

## Reproducciones conservadas

Código ejecutado desde la raíz del repositorio con el Python de .venv y -B. Cada bloque es independiente; solo escribe en TemporaryDirectory y sustituye toda función que podría llamar un modelo o escribir remotamente. No ejecutar funciones de recovery o publicación fuera de esos patches.

### R1 — respuesta durable

```python
import json, tempfile, shutil, hashlib
from pathlib import Path
from unittest.mock import patch
from src.local_runner import adaptive_stage as s
from src.local_runner.adaptive_context import unpack_model_context,model_context
from src.local_runner.semantic_binding import bind_response
from src.local_runner.semantic_report import full_document
root=Path.cwd(); origin=root/'logs/batch/2026-10-16/15-58-24/adaptive/IBKR'
original={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in origin.iterdir() if p.is_file()}
with tempfile.TemporaryDirectory() as d:
 w=Path(d)/'work'; w.mkdir()
 for name in ('instructions.md','triage_instructions.md','policy.json','report.input.json','report.response','report.receipt.json','report.events.jsonl'):
  shutil.copy2(origin/name,w/name)
 policy=s.read_json(w/'policy.json'); frozen=unpack_model_context(s.read_json(w/'report.input.json')); context=s.read_json(origin/'input.json')
 for k in ('guards','review_flags','itv','triage','maintenance_handoff','maintenance_repair_history'):
  if k in frozen: context[k]=frozen[k]
 response=s.read_json(w/'report.response'); response['summary']['narrative']='CORRUPCION LOCAL DE AUDITORIA: texto sustituido despues de la llamada.'
 (w/'report.response').write_text(json.dumps(response,ensure_ascii=False),encoding='utf-8')
 with patch.object(s,'call_codex',side_effect=AssertionError('NO MODEL')):
  receipt=s.model_call(root,w,'IBKR',Path(d)/'budget.json',policy,'report',context,reuse_only=True)
  binding=bind_response(context,receipt,'report')
  doc=full_document(json.loads(receipt['text']),model_context(context),binding=binding)
 print(json.dumps({'altered_response_reused':receipt['text']==(w/'report.response').read_text(encoding='utf8'),'altered_narrative_validated':doc['summary']['narrative'],'original_receipt_unchanged':(w/'report.receipt.json').read_bytes()==(origin/'report.receipt.json').read_bytes(),'original_events_unchanged':(w/'report.events.jsonl').read_bytes()==(origin/'report.events.jsonl').read_bytes()},ensure_ascii=False))
print('originals_unchanged', original=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in origin.iterdir() if p.is_file()})
```

### R2 — espejo staged

```python
import json,tempfile,shutil
from pathlib import Path
from unittest.mock import patch
from src.local_runner import adaptive_stage as s
from src.local_runner.review_memory import read_memory
root=Path.cwd();origin=root/'logs/batch/2026-10-16/15-58-24/adaptive/CAT'
with tempfile.TemporaryDirectory() as d:
 r=Path(d);w=r/'stage';shutil.copytree(origin,w)
 review=s.read_json(w/'review.json');review.pop('published_at',None);s.write_json(w/'review.json',review)
 context=s.read_json(w/'input.json');p=w/'publish/output/CAT/latest.json';payload=s.read_json(p)
 old=payload['plan']['entry'].copy();payload['plan']['entry']={'lower':800,'upper':810};s.write_json(p,payload)
 read_memory(payload,context['sol_reference'])
 with patch.object(s,'_read_json_gcs',side_effect=[context['reference'],context['sol_reference']]),patch.object(s.one,'_upload') as upload,patch.object(s,'_copy_json') as copy,patch.object(s,'call_codex',side_effect=AssertionError('NO MODEL')):
  s.publish(r,w,'CAT')
  print(json.dumps({'unchanged_semantic_range':payload['semantic_report']['data']['plan']['entry']['range'] if 'data' in payload['semantic_report'] else 'inspect','mutated_plan_range':payload['plan']['entry'],'original_range':old,'upload_reached':upload.call_count,'memory_check_passed':True}))
```

### R3 — frescura

```python
import json,tempfile,shutil
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from src.local_runner import adaptive_stage as s
root=Path.cwd(); origin=root/'logs/batch/2026-10-16/15-58-24/adaptive/CAT'
class Clock(datetime):
 @classmethod
 def now(cls,tz=None): return cls(2026,10,23,16,0,tzinfo=timezone.utc)
with tempfile.TemporaryDirectory() as d:
 r=Path(d);w=r/'stage';shutil.copytree(origin,w)
 review=s.read_json(w/'review.json');review.pop('published_at',None);s.write_json(w/'review.json',review)
 context=s.read_json(w/'input.json');policy=s.read_json(w/'policy.json')
 try: s.data_ready(context,policy,Clock.now())
 except Exception as e: print('control_data_ready',type(e).__name__,str(e))
 with patch.object(s,'datetime',Clock),patch.object(s,'call_codex',side_effect=AssertionError('NO MODEL')),patch.object(s,'data_ready',wraps=s.data_ready) as ready,patch.object(s,'_read_json_gcs',side_effect=[context['reference'],context['sol_reference']]),patch.object(s.one,'_upload') as upload,patch.object(s,'_copy_json') as remote_copy:
  result=s.analyze(r,w,'CAT',r/'budget.json',False,reuse_only=True)
  final=s.publish(r,w,'CAT')
  print(json.dumps({'review_returned':result['status'],'data_ready_calls':ready.call_count,'bundle_upload_calls_simulated':upload.call_count,'remote_copies_simulated':remote_copy.call_count,'published_at':final['published_at'],'report_generated_at':s.read_json(w/'publish/output/CAT/latest.json')['generated_at']}))
```

### R4 — publicación interrumpida

```python
import json,tempfile,subprocess
from pathlib import Path
from unittest.mock import patch
from src.local_runner import gcs_uploader as u,analysis_state as a
with tempfile.TemporaryDirectory() as d:
 r=Path(d)
 for e in ('md','html','json'):(r/('latest.'+e)).write_text('new-'+e,encoding='utf8')
 remote={f'gs://{u.TEST_BUCKET}/TEST/latest.'+e:'old-'+e for e in ('md','html','json')};calls=[]
 def fake(command,**kw):
  calls.append(command)
  if len(calls)==3:raise subprocess.CalledProcessError(1,command)
  remote[command[-1]]=Path(command[-2]).read_text(encoding='utf8')
 with patch.object(u,'require_gcloud',return_value='SIMULATED'),patch.object(u.subprocess,'run',side_effect=fake):
  plan=u.build_real_upload_plan('TEST',r/'latest.json',analysis_status='ok',timestamp_date='2026-10-17',timestamp_time='audit',markdown_source=r/'latest.md',html_source=r/'latest.html',dry_run=False)
  try:u.upload_artifacts(plan)
  except subprocess.CalledProcessError:pass
 print('partial_bundle',json.dumps(remote))
 with patch.object(a,'require_gcloud',return_value='SIMULATED'),patch.object(a.subprocess,'run',side_effect=RuntimeError('transport unavailable')):
  try:a.save_reference_payload(r,'TEST',{'analysis_status':'ok','generated_at':'2026-10-17','analysis_markdown':'new anchor'})
  except RuntimeError:pass
 print('local_reference_after_failed_upload',json.loads((r/'data/analysis_state/TEST/reference.json').read_text(encoding='utf8')))
```
