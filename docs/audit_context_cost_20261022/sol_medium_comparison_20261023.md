# Sol6.1 medium frente a low — 23 de octubre

**Medium coincide con low en las tres decisiones y los cuatro indicadores de
riesgo de cada caso: AMD y CLS escalan; IREN conserva. No hubo errores en los
controles ejercitados. No hubo ninguna propuesta de actualización financiera.**

Tres llamadas nuevas autorizadas, con gpt-6.1-sol / medium y la autenticación
ChatGPT Plus existente. Sin web, API key, reparación, full, recuperación ni
publicación. No se cambió la configuración diaria (Luna high).

## Comparación controlada

Se reutilizaron byte por byte los tres contextos, vistas, schemas e inputs
esperados del piloto low: `logs/sol_low_test/20261023T160954879936`.
Sólo cambió el esfuerzo low→medium y la palabra correspondiente en el footer
de evaluación. La política financiera congelada continúa sin la guía de Volumen
posterior al lote, igual que en low. Se conservaron fechas y posiciones.

Artefactos medium: `logs/sol_medium_test/20261023T163009901298`.
`identical_fixtures.json` y `comparison.json` documentan la igualdad de inputs.
Los tres recibos y bindings pasaron; cobertura de noticias pasó en la retención.
46 archivos originales, incluyendo los resultados low y la configuración diaria,
verificados sin cambios. Scripts: `run_sol_medium_test.py`, runner común
`run_sol_low_test.py` y `compare_sol_efforts.py`.

| Caso | Low | Medium | Riesgo y evaluación |
|---|---|---|---|
| AMD | Escalate | Escalate | Ambos declaran pérdida estructural con posición registrada; Washout sigue diferenciado y viable |
| CLS | Escalate | Escalate | Ambos distinguen origen histórico identificado de función compradora perdida y consideran el riesgo de posición |
| IREN | Retain | Retain | Ambos mantienen compras ausentes, evalúan candidatos inferiores y no convierten opinión sectorial en un hecho propio |

La lectura comparada no revela una mejora decisoria concreta de medium. Añade
detalle y, en AMD, agrupa más antecedentes de noticias ya revisadas. Ambos
separan la pérdida técnica de una supuesta ruptura empresarial. Esto no es una
validación independiente de que escalar sea superior a retirar compras dentro
del mantenimiento: expresa la coincidencia de los juicios emitidos.

Las escaladas son explícitas por riesgo declarado, no el fallback accidental
por mezcla de errores contractuales auditado en `escalations_20261023.md`.
La coincidencia posterior no cambia el motivo original de aquel fallback.

## Consumo medido de las tres llamadas por esfuerzo

| Métrica | Low | Medium |
|---|---:|---:|
| Entrada | 413.832 | 413.832 |
| Entrada en caché | 0 | 0 |
| Salida, razonamiento incluido | 3.609 | 5.424 |
| Razonamiento, subconjunto de salida | 219 | 914 |
| Total de tokens sin ponderación | 417.441 | 419.256 |

Medium generó 1.815 tokens adicionales de salida. La entrada es idéntica;
estos totales brutos no son unidades de cuota semanal ni demuestran una
reducción equivalente de cuota al usar low. Hay una muestra por caso/esfuerzo;
el orden temporal y la caché no están aleatorizados.

Contador semanal compartido: low32→35% usado; medium36→39% usado. No se pueden
atribuir exactamente esos tres puntos a cada piloto por redondeo, latencia y
actividad compartida de la cuenta. No usar este dato para afirmar coste semanal
idéntico ni para proyectar un lote de46.

## Conclusión y límite

En estos tres casos medium no aporta una mejora observable frente a low, y
genera más salida. Ninguno de los dos ejercitó updates: quedan sin contrastar
la aritmética de Volumen, las modificaciones de rangos/puntuaciones, la
justificación de cambios y su reparación. No declarar low equivalente en
general ni medium validado para resolver los fallos de Luna a partir de esta
muestra. No se activó ningún modelo ni se lanzaron pruebas adicionales.
