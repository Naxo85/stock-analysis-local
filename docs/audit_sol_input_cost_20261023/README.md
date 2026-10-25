# Auditoría corregida: entrada y caché de las revisiones con Sol

**Seguimiento:** por orden posterior del usuario se restauró Sol medium y se
investigaron las cinco vías, incluida la interacción compresión/caché. Ver
[investigación ampliada](followup/README.md). Tras autorización posterior está
activo también el [schema compartido](implementation/README.md), sólo en nuevas
revisiones/reparación. La discrepancia de configuración del final quedó resuelta.

23 de octubre de 2026. Sustituye la priorización de coste de la
[auditoría anterior](../audit_input_cost_20261023/README.md), cuyo corpus era el
lote de Luna del 23/10. Usarlo para priorizar el ahorro de una política con
revisiones Sol fue un error: **en los dos lotes Sol las revisiones representan
el 85–88% del coste calculado y no hubo reparaciones**.

## Evidencia elegida

| Lote real | Modelo/esfuerzo de revisión verificado en recibos | Resultado | Reparaciones |
|---|---|---|---:|
| 21/10, `06-52-46` | GPT-6.1 Sol medium, 46 llamadas | 44 conservados, 2 completos; 46/46 publicados | 0 |
| 22/10, `12-32-48` | GPT-6.1 Sol medium, 46 llamadas | 30 conservados, 13 actualizados, 3 completos; 46/46 publicados | 0 |

El 22/10 es la referencia principal porque incluye actualizaciones reales; el
21/10 contrasta estabilidad y coincide con el lote original descrito por el
usuario. No son los pilotos posteriores de tres tickers, ni revisiones Luna
reclasificadas. Los completos usan Sol high.

Se autentican los hashes de las 92 entradas y respuestas contra sus recibos.
Los 460 archivos originales examinados permanecen intactos. Sólo hay cálculos,
copias en memoria y artefactos de auditoría: cero llamadas a modelos, consultas
financieras, lotes, recuperaciones o publicaciones.

## El gasto que importa con Sol

| Uso registrado de las revisiones | 21/10 | 22/10 |
|---|---:|---:|
| Tokens de entrada totales, caché incluida | 7.705.154 | 11.961.093 |
| Entrada en caché | 2.340.352 | 6.342.400 |
| Entrada sin caché | 5.364.802 | 5.618.693 |
| Salida, razonamiento incluido | 65.680 | 93.668 |
| Créditos calculados: revisiones | 290,51 | 320,21 |
| Créditos calculados: completos | 40,09 | 57,57 |
| Parte del coste calculado en revisiones | **87,9%** | **84,8%** |

Se aplican las [tarifas Standard publicadas](https://learn.chatgpt.com/docs/pricing)
de Sol: 50 créditos/M de entrada sin caché, 2,5/M de entrada en caché y 250/M de
salida. El razonamiento es un subconjunto de la salida, no se suma otra vez.
Estos cálculos permiten comparar componentes; **no demuestran cómo se repartió
el porcentaje semanal incluido en Plus**.

En las revisiones del 22/10, la entrada sin caché supone 280,93 créditos; la
entrada en caché 15,86 y toda la salida 23,42. Por tanto, **el 92,7% del coste
calculado de revisión es entrada**, y el 87,7% es entrada sin caché. Reducir la
salida o el esfuerzo de razonamiento no aborda el componente principal observado.

Las revisiones sin web permiten ver el problema sin tanta repetición de
contexto durante búsquedas: mediana de 140.076 tokens el 21/10 (45 casos) y
139.960 el 22/10 (36 casos). En esos subconjuntos sólo el 19,7% y el 19,9% de la
entrada fue caché. El porcentaje agregado de caché del 22/10, 53,0%, no debe
confundirse con la caché de una primera entrada: las continuaciones de las
llamadas con web también acumulan entrada y caché.

Retiro para Sol la anterior prioridad de «arreglar reparaciones/full antes que
reducir contexto»: respondía al comportamiento de Luna. El defecto contractual
de enrutado sigue siendo un asunto separado; estos lotes Sol no muestran que
explicara su consumo.

## Qué ocupa la entrada y cuánto se puede reducir

En el 22/10, el texto visible original es aproximadamente 75,8% JSON, 21,2%
instrucciones y 3,0% schema. Dentro del JSON ya deduplicado, comparación ocupa
41,3%, CURRENT 24,5% y técnico actual 18,2%. Son ubicaciones físicas: los alias
comparten información entre bloques; esos porcentajes no autorizan a borrarlos.

El prefijo de instrucciones es idéntico en las 92 revisiones: 106.821 caracteres,
SHA `fc99ac397098d81051d439538768a6d454460a51d8ba7738b033a57238b8a6ac`.
No se puede quitar la política financiera que aplica la revisión sólo porque
también se use para crear informes. Una compilación de instrucciones específica
de mantenimiento requeriría mapear todas las obligaciones y excepciones; no se
ha demostrado todavía un ahorro seguro de esa parte.

Los congelados de estos lotes son anteriores a `pointer-diff-v1`. Para evitar
presentarlo otra vez como novedad, se normalizaron copias con ese transporte
antes de medir las propuestas adicionales. La normalización ya activa supone
un 2,68% de caracteres del conjunto visible histórico en ambos lotes.

| Prototipo adicional | 21/10 | 22/10, principal |
|---|---:|---:|
| Capturas históricas como diferencias exactas frente al técnico actual | 13,34% | **8,61%** |
| Una sola copia del destino de cada alias | 2,44% | 2,26% |
| Factorización del schema mediante `$defs` | 1,47% | **1,44%** |
| Los tres combinados | **17,23%** | **12,31%** |

Porcentajes de **caracteres Unicode** de JSON + instrucciones + schema, sobre
la base histórica normalizada únicamente al transporte ya activo. No son
porcentajes de tokens, créditos ni cuota. Tampoco simulan todos los cambios de
política posteriores: la guía de Volumen ya activa no se cuenta como propuesta
nueva. El texto necesario para explicar los nuevos codecs aún no está incluido.

Las diferencias históricas reconstruyen exactamente valores, presencia,
null, orden y fuentes antes de resolver alias. Los 92 contextos se reconstruyen
sin cambiar información; eso no demuestra que el modelo interprete igual otro
formato. El schema baja de 14.935 a 7.881 caracteres, con expansión idéntica y
368 comprobaciones locales: 92 respuestas aceptadas y 276 mutantes rechazados.
Entre las respuestas hay 13 actualizaciones publicadas. La admisión del schema
por el proveedor y la interpretación financiera del transporte propuesto no
se han probado con nuevas llamadas.

No empezaría por los alias con null: el ahorro es pequeño y el marcador puede
confundirse con una ausencia financiera. El combinado es un máximo observado
de estos prototipos, no una propuesta de activarlos todos.

## Caché: comparación Sol contra Sol

En los 46 pares 21→22 coinciden modelo, esfuerzo, instrucciones y schema; en
43 coincide también el ancla full íntegra. Ya no existe la confusión de comparar
el prefijo de Sol con el de Luna.

El orden actual coloca el mapa variable de alias antes del contenido estable.
Un prototipo que visita primero el ancla, después CURRENT y técnico, dejando
los alias al final, aumenta el prefijo textual común medio de 123 a 115.259
caracteres sobre copias normalizadas con el mismo transporte. El tamaño del
JSON aumenta un 0,42% respecto a ese mismo transporte. Se reconstruyen los 92
contextos. Es estabilidad textual, **no un hit de caché medido**.

El ejecutor manda todo el JSON como texto de una única entrada por stdin. La
[documentación de caché](https://developers.openai.com/api/docs/guides/prompt-caching)
describe para GPT-5.6+ fronteras implícitas en finales de mensajes elegibles:
no basta un campo estable dentro del JSON. Antes de implementar este orden
hay que confirmar una frontera soportada en el cliente/protocolo de Codex.
Los recibos no demuestran reutilización de un día a otro ni un TTL garantizado.
No se propone cambiar a autenticación API, convertir fuentes en instrucciones
de desarrollador, ni hacer llamadas para mantener caliente la caché.

La investigación de caché de reparación queda secundaria para esta política:
en estos lotes no hubo ninguna reparación sobre la que medir ese beneficio.

## Recomendación corregida

1. Centrar el ahorro en **entrada sin caché de las revisiones Sol**. Mantener
   los completos fuera de estos cambios y retirar la prioridad basada en los
   fallos de Luna.
2. Como primer cambio acotado, estudiar la factorización del schema: conserva
   el contrato expandido y reduce aproximadamente 1,4% del texto visible. Su
   beneficio aislado es modesto.
3. Como principal reducción de volumen medida, preparar el codec exacto de
   capturas históricas: 8,6% en el lote principal y 13,3% en el control, adicional
   al transporte ya activo. Requiere validar comprensión, fuentes y updates;
   los roundtrips por código no bastan para activarlo.
4. En paralelo, investigar una frontera de caché utilizable para el ancla
   estable de la primera revisión. Puede importar más que esos recortes, pero
   hoy no hay una cifra de ahorro efectiva que se pueda prometer.
5. Para reducir mucho más haría falta cambiar qué información se suministra
   de entrada, con acceso puntual al congelado íntegro y validación de fuentes.
   No hay una reducción del 50% demostrada ni un diseño listo para activar.

No se han cambiado modelos, prompts, reglas, producción ni congelados. Se
detecta una discrepancia operativa: pese a la reversión a Sol indicada por el
usuario, `config/codex_analysis.json` todavía declara `triage_model=gpt-6-luna`
y `triage_effort=high` al comprobarlo en esta auditoría. Se deja
señalado; estos resultados proceden de recibos históricos Sol, no de ese archivo.

## Reproducibilidad

Con `.venv\Scripts\python.exe`: `audit.py` genera `results.json`; `cache.py`
genera `cache.json`; `summarize.py` imprime los resultados principales. Los
resultados finales pasan `verify.py`: uso agregado idéntico a los 97 recibos
de revisión/full, modelos/esfuerzos comprobados y originales intactos. Los
codecs proceden de `../audit_input_cost_20261023/prototypes.py`, exclusivamente
offline. No los importa el ejecutor de producción. No hay tokenizer compatible
verificado en los runtimes examinados y no se instalaron dependencias.
