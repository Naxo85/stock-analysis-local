# Prueba real de tablas —22Oct2026

Autorizada por el usuario.12 llamadas:8 de lectura y4 de mantenimiento histórico,
todas GPT-6 Luna high con la sesión ChatGPT existente. Sin web, reparaciones,
fallback, informes full ni publicación. No se activan tablas en producción.

## Lectura verificable

8/8 llamadas aprobadas; 154 comprobaciones exactas.
Cuatro escenarios: vencimientos, cero/null/ausencia, identidad con filas reordenadas,
y CURRENT/ancla/observación actual.77 preguntas por formato; no154 hechos independientes.
Los registros proceden de LEU21Oct. El caso cero/null/ausencia contiene modificaciones
controladas declaradas, no nuevas observaciones de mercado. Respuestas esperadas
congeladas antes de las llamadas, cotejadas por código contra sus valores completos.

## Mantenimiento con contexto completo

| Ticker | Original | Tablas | Entrada original | Entrada tablas | Reducción entrada |
|---|---|---|---:|---:|---:|
| LEU | retain | retain | 127,642 | 120,951 | 5.24% |
| TSLA | escalate | escalate | 162,400 | 153,338 | 5.58% |

4/4 respuestas pasan los controles ejercitados.
Entrada acumulada: 290,042 original frente a 274,289 tablas: **5.43% menos tokens de entrada**.
Mismo schema e instrucciones (incluido el decoder tabular) en ambos formatos, orden
alternado y workspaces independientes. Baseline usa el transporte por referencias
ya activado. Los inputs originales y recibos del lote se conservaron por hash.

Los controles abarcan schema, binding al input real, decisión/autoridad y cobertura
de agenda cuando corresponde. Retain no se convierte en un documento actualizado;
escalate no genera full. No se ha ejercitado actualización de rangos/puntuaciones
ni reparación de una actualización en esta muestra. No atribuir calidad financiera
general ni causalidad al formato a partir de dos casos y una ejecución por variante.

## Revisión del contenido y decisión de adopción

Las decisiones y los cuatro flags de riesgo coinciden en las dos parejas.
En LEU ambos conservan las compras ausentes y tratan la discrepancia del objetivo
de Needham como dato no utilizable. El original propone una selección editorial
de catalizadores y la variante tabular hereda la anterior; no son salidas idénticas.
En TSLA ambos escalan por la misma novedad corporativa pendiente de investigación.
Sin embargo, la variante tabular agrupa n1–n9 como critical_change: n1 y n2 sólo
aportan titulares de resultados de SpaceX y n3 una lista de valores; no contienen
el hecho de los comités suministrado en n4–n9. Ninguno de esos tres registros
incluye cuerpo de artículo. El formato original los separa de los titulares
críticos. Esta asociación excesiva está en auditoría interna y no cambia la ruta,
pero es un límite de calidad que el schema/coverage no detecta. No se crea por
ello un gate de prosa, reparación pagada o escalado adicional en producción.
Una ejecución por variante no permite atribuir causalmente la diferencia a las tablas.
**No activar tablas todavía.** La prueba de lectura pasa; el contraste de juicio
es limitado y contiene esta discrepancia. El ahorro observado es moderado y
no justifica afirmar equivalencia general, especialmente sin casos update/repair.

## Consumo y límites

| Fase/formato | Entrada | Caché incluida | Salida | Razonamiento incluido en salida |
|---|---:|---:|---:|---:|
| Lectura/original | 46,287 | 6,144 | 1,990 | 318 |
| Lectura/tabular | 45,489 | 0 | 2,201 | 529 |
| Mantenimiento/original | 290,042 | 0 | 4,696 | 2,265 |
| Mantenimiento/tabular | 274,289 | 0 | 4,443 | 2,689 |

Lectura: contador semanal usado 94%→94%.

Mantenimiento: contador semanal usado 94%→95%.

El contador es redondeado, puede actualizarse con retraso y se comparte con otras
actividades; no demuestra consumo cero ni permite atribuir un coste exacto a la prueba.
Diferencias de caché, salida y razonamiento impiden trasladar el porcentaje de
reducción de entrada directamente a ahorro semanal. No se ejecutan llamadas extra
para igualar caché o medir cuotas.

## Evidencia

- Lectura: `logs\table_reading_test\20261022T144755704687`.
- Mantenimiento: `logs\table_maintenance_test\20261022T145022489730`.
- Scripts: run_table_reading_test.py, run_table_maintenance_test.py.
- Comparación agregada: table_test_summary.json.
- Cada llamada conserva input, schema, instrucciones identificadas por hash,
  eventos, respuesta y recibo de uso. Las respuestas de una variante no se
  incluyen en el contexto de la otra.
