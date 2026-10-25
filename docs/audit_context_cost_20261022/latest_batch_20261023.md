# Coste y fallos del lote natural del 23 de octubre

Auditoría de lectura de `logs/batch/2026-10-23/14-18-22`. Sin llamadas a modelos,
reintentos, recuperación ni publicación. Reproducción: `audit_latest_batch.py`;
datos agregados: `latest_batch_usage.json`.

Ampliación posterior: `escalations_20261023.md` comprueba las cuatro escaladas
con las listas completas originales. Confirma la brecha de composición entre
errores de Volumen y justificación; el interrogante de enrutado inferior queda
resuelto allí. Corrección no aplicada.

Resultado: 34/46 publicados (17 conservados, 9 actualizados, 8 completos),
12 fallidos. Hubo 74 llamadas admitidas: 46 revisiones Luna high, 19 reparaciones
Luna high (18 completadas y un timeout), 9 completos Sol 6.1 high.

| Etapa | Entrada sin caché | Entrada en caché | Salida, incluido razonamiento |
|---|---:|---:|---:|
| Revisiones Luna | 6.793.296 | 4.904.832 | 228.763 |
| Reparaciones Luna con uso registrado | 2.627.838 | 1.851.648 | 100.689 |
| Completos Sol | 1.936.344 | 14.068.352 | 129.197 |

El timeout puede tener consumo no registrado. Los tokens de razonamiento son
un subconjunto de salida, no se suman otra vez. No existe en esta auditoría una
conversión validada de estos totales al porcentaje semanal incluido en Plus.

Cinco decisiones iniciales de Luna fueron `escalate`: CRWV, WDC, SPCX, MRNA y
TSLA. Las otras cuatro llamadas completas (AMD, AMAT, SNDK y ASTS) proceden de
la ruta automática después de una reparación rechazada. Sus `update_rejected.json`
registran `update_not_allowed_change_not_established: setup:
wrong_scope_current_evidence` y `next=sol_review`. Sumaron 826.517 tokens de
entrada sin caché, 5.980.032 en caché y 56.425 de salida. No vencía ITV.

El código de `adaptive_stage.py` excluye de Sol ciertos errores cuando todos los
elementos del conjunto de incidencias pertenecen a una clase. Por tanto, el
primer mensaje mostrado no demuestra que el conjunto fuera exclusivamente de
justificación: hay que reconstruir todas las incidencias antes de concluir que
esas cuatro escaladas fueron innecesarias. Sí demuestra que no fueron cuatro
decisiones iniciales independientes de Luna por riesgo empresarial. Prioridad:
auditar esas cuatro rutas y distinguir errores de respuesta de riesgo real.

Los fallos originales están auditados en
`docs/audit_batch_retries_20261023/README.md`: nueve de Volumen, dos de contrato
de justificación y un timeout. Los doce reintentos exteriores no generaron
llamadas nuevas. No suprimirlos como supuesto ahorro de tokens.

La guía `selected-sources-v1` de Volumen se añadió después y no figura en la
política congelada de este lote. Tiene comprobaciones offline, pero aún no prueba
de mejora en producción. El transporte pointer-diff-v1 sí estaba activo.
La codificación tabular sigue desactivada; su piloto de dos mantenimientos no
validaba actualizaciones ni reparaciones. El resultado actual impide presentar
Luna high como sustitución ya validada con igual fiabilidad.

Recomendación: resolver primero fiabilidad y rutas de escalada, manteniendo
rúbrica, fuentes, riesgo y autoridad; no bajar más razonamiento basándose en
este lote ni atribuir un ahorro semanal concreto a precios de créditos.
