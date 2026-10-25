# Auditoría de entrada, caché y coste — 23 de octubre de 2026

**Corrección de alcance:** este documento analiza el lote **Luna del 23/10**.
Su prioridad de reparar Luna/full no representa el gasto de las revisiones Sol.
La [auditoría corregida con los lotes Sol del 21 y 22/10](../audit_sol_input_cost_20261023/README.md)
sustituye esa priorización: en Sol, las revisiones concentran el 85–88% del coste
calculado, sin reparaciones. Este documento conserva evidencia histórica de Luna.

**La reducción conservando todos los datos es real pero moderada: los prototipos
ahorran hasta un 11% de caracteres del conjunto normalizado de entrada. La
oportunidad potencial de caché es mayor, pero no está demostrada en facturación.
En el lote original, el mayor coste calculado procede de los full Sol, no de
las revisiones Luna.**

Auditoría solicitada por el usuario tras comparar Sol low/medium. Cero llamadas
a modelos, lotes, recuperaciones, refrescos financieros o publicaciones. No se
modificó producción, modelos, prompts, reglas financieras ni inputs originales.
Los prototipos viven sólo en esta carpeta y no se importan desde el ejecutor.

## Corpus y unidades

- 46 entradas reales de mantenimiento del lote `logs/batch/2026-10-23/14-18-22`.
  Sus hashes se verificaron contra los recibos y permanecieron intactos.
- 18 reparaciones con uso registrado y 9 full completados. Otra reparación tuvo
  timeout sin uso registrado; el coste calculado no incluye su consumo desconocido.
- Los tres casos Sol de prueba no son una anomalía: las 26 revisiones originales
  sin web tienen una mediana registrada de **136.821 tokens de entrada**.
- Las mediciones de estructura usan **caracteres Unicode**, no tokens ni cuota.
  No hay tokenizer compatible verificado disponible en los runtimes examinados.
  No se instaló nada ni se usó una API de conteo.
- El denominador de «entrada visible» suma JSON de usuario, instrucciones y
  schema compactado. No reconstruye instrucciones ocultas ni el render interno
  del servidor. Los nuevos textos de decodificación aún no se han añadido:
  las ganancias de los codecs son previas a ese pequeño coste adicional.

Evidencia reproducible: `inventory.json`, `variants.json`, `cache_layout.json`,
`rollup.json`, `summary.json` y sus scripts homónimos/indicados al final.

## 1. De dónde sale el volumen

La entrada normalizada media tiene 491.875 caracteres: aproximadamente75,1%
JSON de datos,21,9% instrucciones y3,0% schema de salida.

Dentro del JSON ya compactado:

| Bloque físico | Porcentaje de caracteres del JSON |
|---|---:|
| Comparaciones y última revisión | 30,8% |
| Informe CURRENT y su captura histórica | 25,8% |
| Técnico actual | 18,4% |
| Ancla full y su captura histórica | 8,3% |
| Noticias y memoria de sus revisiones | 6,6% |
| Mapa de referencias para deduplicación | 5,7% |
| Catálogo de fuentes | 2,7% |

Esto describe ubicación física, no información independiente. Las referencias
ya evitan copias exactas; eliminar un bloque puede mover los mismos datos a
otro bloque. Por ejemplo, quitar ambos snapshots históricos y volver a
compactar sólo reduce1,6% del JSON porque sus registros siguen presentes en
catálogos/otros contextos. Además deja rutas de fuente incompletas: ese
experimento es diagnóstico, NO un contexto apto para publicación.

El transporte `pointer-diff-v1` ya estaba activo en este corpus. Ninguna
reducción nueva vuelve a contar su ahorro anterior.

## 2. Prototipos exactos de reducción adicional

| Alternativa | Ganancia medida | Alcance y coste de implementación |
|---|---:|---|
| Capturas históricas como diferencias respecto al técnico completo | 9,55% del JSON;7,18% de entrada visible | Conserva valores, orden y presencia; requiere que el modelo interprete correctamente otro transporte |
| Una sola copia del destino de cada alias | 3,14% del JSON;2,36% de entrada visible | El destino queda en el mapa; el marcador redundante pasa a null. Mayor riesgo de lectura por confusión con null financiero |
| Definiciones compartidas `$defs` en el schema | 47,23% del schema;1,43% de entrada visible | Mismo contrato expandido; más sencillo que cambiar datos financieros |
| Las tres anteriores combinadas | 12,70% del JSON;10,97% de entrada visible | No sumar porcentajes separados ni llamarlo11% de tokens/cuota |

Se comprobó reconstrucción exacta en46/46 entradas y8 casos límite: ausencia,
null,0/false,1/1.0,-0.0/0.0, orden de arrays y cambios de longitud. Se preservan
los handles, rutas, fechas y objetos de origen; los índices se usan sólo para
reconstruir bytes lógicos, nunca para adivinar identidad o sustituir fuentes.

El schema pasa de14.935 a7.881 caracteres compactos con20 definiciones nuevas.
Al expandirlas se obtiene exactamente el original. El validador local coincide
en184 comprobaciones:46 respuestas originales admitidas y138 negativos
(enum,booleano y campo requerido) rechazados. No se probó la admisión del schema
factorizado en una llamada real ni se valida calidad financiera con este test.

Recomendación técnica: empezar por factorizar el schema. Estudiar después el
codec de snapshots. No usaría el marcador null como primer cambio: ahorra poco
y añade una ambigüedad que el modelo tendría que resolver. El11% combinado es
un techo observado de estos prototipos, no la recomendación de activarlos juntos.

## 3. Caché: orden y reparación

El serializador visita slim primero para deduplicar, pero después ordena todas
las claves alfabéticamente. Eso coloca `_context_aliases`, dependiente de las
diferencias actuales, al principio del JSON. Un cambio ahí rompe la coincidencia
antes de llegar a los bloques históricos estables.

Prototipo: almacenar el ancla full primero, después CURRENT y el técnico; dejar
el mapa de alias al final y conservar el orden superior al serializar. En45
pares22→23 (VST sin pareja de triage),42anclas son idénticas. El prefijo común
medio pasa de86 a103.730 caracteres; el tamaño del JSON aumenta0,36%. Se
reconstruyen exactamente los90 contextos comparados. Ese prefijo representa
27,7% del JSON nuevo, NO27,7% de ahorro ni de caché efectiva.

Los lotes originales usaron modelos/prefijos distintos: esto simula una
disposición comparable con el mismo modelo. La caché real también depende
del prefijo renderizado por el servidor, schema, opciones y disponibilidad.
[OpenAI Docs](https://developers.openai.com/api/docs/guides/prompt-caching)
explica que una sesión conservada no garantiza un hit y que los cambios
anteriores al punto reutilizable pueden impedirlo.

**Reordenar el JSON no basta.** Este ejecutor entrega todo el JSON como el
texto de una única entrada por stdin. La documentación de GPT-5.6+ describe
breakpoints implícitos en finales de mensajes elegibles, no en cualquier campo
interior del JSON. Hay que confirmar una frontera de mensaje/cache soportada
por Codex para el ancla estable; sin ella, el prefijo común calculado puede no
ser reutilizable. No se propone mover fuentes financieras a instrucciones de
desarrollador ni cambiar a autenticación API para conseguirlo.

Las reparaciones merecen atención: las18completadas conservan las mismas
instrucciones que su llamada inicial, pero **las18cambian el schema** para añadir
enums de fuentes. Once tienen cero entrada en caché. El schema puede afectar al
prefijo antes de las instrucciones; eso es un mecanismo plausible de pérdida de
caché, no una causalidad probada por estos recibos.

La arquitectura actual también limpia el historial al terminar cada llamada.
Una reparación vuelve a suministrar el contexto completo en una sesión limpia.
Posible mejora posterior: reservar una conversación sólo para ese ticker hasta
terminar su única reparación, con contrato estable y feedback añadido al final,
y limpiarla antes de otro ticker. Mantener la validación de fuentes aunque se
evalúe trasladar las opciones de fuente del schema al feedback. Esto requiere
trabajo de ejecutor y pruebas de aislamiento; no basta cambiar una bandera de
caché ni conservar conversaciones viejas entre tickers.

El mensaje original de esa conversación sí tendría un final elegible antes del
feedback. Los recibos tendrían que autenticar el historial exacto y el feedback,
no fingir que el hash de un JSON aislado representa una conversación distinta.

No hay retención diaria garantizada demostrada en este CLI. Los controles/TTL
de la API no deben trasladarse sin más a Codex con autenticación ChatGPT. No se
propone ningún warmup, keepalive ni llamada extra para mantener una caché.

## 4. Instrucciones

El prefijo común suma107.520 caracteres: mantenimiento10.377; política financiera
40.626; contrato41 25.234; overlays de rúbrica, dirección, presentación y fuentes,
el resto. No se encontraron párrafos exactos repetidos de más de80caracteres.
No hay un recorte grande consistente en borrar duplicados de texto idéntico.

Se puede estudiar una compilación específica de mantenimiento que preserve la
rúbrica/criterios de Sol pero separe instrucciones exclusivas de autoría full,
renderizado y campos protegidos. No se ha medido un recorte seguro de ese texto:
hay que mapear cada obligación y excepción a su regla vigente. Borrar la política
de40.626caracteres dejaría a mantenimiento sin la rúbrica que debe aplicar.
No se redactó ni activó otro prompt en esta auditoría.

## 5. Dónde priorizar para el coste del lote

Aplicando las tarifas Standard de créditos publicadas para cada modelo a su
entrada sin caché, entrada en caché y salida registrada:

| Etapa | Créditos calculados | Parte del total calculado |
|---|---:|---:|
| 46 revisiones Luna high | 21,07 | 10,9% |
| 18 reparaciones Luna con uso conocido | 8,29 | 4,3% |
| 9 completos Sol high | 164,29 | 84,8% |

Fuente: [tarifas oficiales](https://learn.chatgpt.com/docs/pricing). Es un cálculo
de créditos, NO reparto demostrado del20% semanal incluido en Plus. Se excluye
uso desconocido del timeout. El mayor número bruto de tokens de una etapa no
implica el mayor coste: modelo y caché importan.

Los cuatro full AMD/AMAT/SNDK/ASTS originados por la brecha de combinación de
errores sumaron70,38créditos calculados,36,3% de ese total. No es ahorro gratis:
tres terminaron publicados; bloquearlos sin corregir los errores de Luna dejaría
tres fallos adicionales. Tampoco se puede dar por inocuo su riesgo: en pruebas
posteriores low/medium, AMD fue escalado por un juicio estructural explícito.
El motivo original del fallback sigue siendo un defecto contractual distinto.

Por eso el primer objetivo es **resolver calidad de reparación y composición
de guardas**, manteniendo riesgo/ITV y fallos visibles. La guía de Volumen ya
añadida se medirá en el próximo uso natural; no inventar otra corrección igual.
Los12reintentos exteriores del lote no hicieron llamadas nuevas: suprimirlos
no reduce este consumo de modelo.

Reducir la entrada de mantenimiento ayuda, pero por sí solo afecta a una parte
pequeña del coste de este lote mientras sigan esos9full. El beneficio cambiaría
si se vuelve a Sol para todas las revisiones; aquí no se cambió esa política.

## Orden de trabajo propuesto

1. Corregir la composición del enrutado y revisar la eficacia de la reparación
   de Volumen, sin convertir respuestas inválidas en éxitos ni esconder riesgos.
2. Factorizar el schema. Para la disposición estable, confirmar primero una
   frontera elegible en el protocolo de Codex; no prometer ahorro por reordenar
   campos. Nueva opción para próximas preparaciones; congelados/full exactos.
3. Estudiar schema/sesión de reparación estables; proteger aislamiento por ticker
   y autenticación del contexto/respuesta antes de esperar ahorro por caché.
4. Si hace falta más reducción, evaluar el codec exacto de snapshots con casos
   que realmente hagan updates/repair. El piloto de tablas previo no validaba eso.
5. Para un salto mayor haría falta otra arquitectura: resumen determinista de
   descubrimiento con acceso puntual a registros completos e históricos. El modelo
   tendría que poder solicitar cualquier fuente/alternativa y el código validar
   contra el congelado íntegro. No cuantificado ni diseñado como cambio activo:
   puede ahorrar o provocar más rondas/omisiones. No promete reducir50%.

No se recomienda recortar noticias por antigüedad, olvidar riesgos no resueltos,
quitar anclas completas, truncar candidatos/opciones ni deducir que una fuente
ausente carece de importancia. Ninguno de esos cambios se hizo aquí.

## Reproducibilidad y alcance

Usar `.venv\Scripts\python.exe` con `inspect_inputs.py`, `measure_variants.py`,
`cache_layout.py`, `rollup.py` y `summarize.py` de esta carpeta. `prototypes.py`
contiene sólo codecs de estudio; `schema_factored.prototype.json` es un artefacto
para revisar. Los errores iniciales por falta de jsonschema se resolvieron usando
el comprobador del repo y expansión exacta; no se instalaron dependencias.

Los modelos y consumidores actuales no reciben estos codecs. No hay prueba de
reducción efectiva de tokens/cuota ni de equivalencia de interpretación del
modelo. La auditoría sí demuestra tamaños, reconstrucción, checks de schema,
estabilidad de prefijo y reparto calculado de uso original.
