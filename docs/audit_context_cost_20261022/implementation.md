# Activación del transporte por referencias — 22-10-2026

Actualización posterior: el usuario autorizó la prueba de tablas. Se ejecutaron
las8llamadas cortas y las4comparaciones de mantenimiento; [resultado real y límites](table_test_report.md).
Tablas no activadas. La descripción de autorización y de pruebas no ejecutadas
inferior conserva el estado previo a esa solicitud.

Autorización: «haz el1», referida a compactar comparaciones, conservando Luna6high
para mantenimiento y Sol6.1high para full.

## Cambio activo

`maintenance_context_transport: pointer-diff-v1` está en la configuración local.
La selección usa la política congelada de cada preparación, no la configuración
global al recuperar un recibo. Ausencia de la opción conserva formato y prefijo
anteriores. No se cambia routing_revision41 ni las fuentes/contratos financieros.

Sólo triage y su reparación reciben el marcador de transporte y sus instrucciones.
Full no recibe ninguno. El contexto lógico conserva los valores completos; sólo
la copia serializada omite previous/current en las filas del diff de mercado.
Se comprueban las rutas, ámbito histórico/actual, presencia y valor exacto antes
de compactar. Al expandir se resuelven primero los aliases y se reconstruye cada
valor desde su fuente original. null, cero y ausencia siguen siendo distintos.
Los catálogos s y rutas lógicas, el orden de listas y las fechas se conservan.

No se editaron inputs/recibos existentes, ni se ejecutaron modelos, batches o
publicaciones financieras. El worker lee la configuración para cada nueva orden.
Las tablas compactas y el reordenamiento para caché no están activados.

## Verificación

- `verify_transport.py`: **63 pruebas y159 subcasos**,3 exclusiones explícitas.
  Incluye roundtrip del corpus46, entradas sin opt-in, datos no interpretables,
  null/cero/ausencia, RFC6901, origen cambiado/incorrecto, alcance por rol y
  recuperación del mismo recibo sin segunda llamada ni migración silenciosa.
  El binding financiero recibe la misma política congelada que la llamada y
  verifica el hash del transporte; no se relajan las guardas de autoridad.
  Revisiones anteriores a41 no adquieren el transporte por heredar una opción moderna.
- `verify_activation.py`: política leída/validada;46/46 roundtrips exactos y
  originales conservados. `activation.json` registra la lectura de vuelta.
- Nuevo JSON:16.507.224 caracteres frente17.149.720 en serialización equivalente
  anterior:3,746% menos. Tras693 caracteres de instrucción adicionales por llamada,
  reducción estimada en caracteres del cuerpo+instrucción añadida:3,561%.
  No es una medición de tokens, cuota Plus ni equivalencia de juicio financiero.
- Una suite histórica más amplia dio95 pruebas aprobadas y11 fallos, además de214
  subcasos aprobados. Los fallos corresponden a expectativas antiguas de revisión17,
  fixtures fechadas3Oct, respuestas simuladas sin evidencia autenticada y pruebas
  de publicación sin los mocks/recibos actuales (fallo de autenticación antes de
  escritura). No se modificaron esas pruebas ni las protecciones de publicación.
  La suite específica excluye el test de configuración17 y dos fixtures antiguas
  de publicación sin bundle; las exclusiones están escritas en el ejecutor.

## Cómo comprobar las tablas antes de activarlas

1. Mantener fuera de producción el codificador tabular de `audit.py`.
2. Construir cuatro ejercicios breves con bloques de datos reales congelados:
   opciones por vencimiento; OI cero frente a null/no observado; misma cotización
   con identidad/fecha distinta; CURRENT frente a ancla histórica. Incluir un
   caso con filas reordenadas para detectar asociaciones por posición supuesta.
3. Para cada ejercicio enviar original y tabular en llamadas independientes de
   Luna6high, sin web, sin publicar ni permitir acceso a la respuesta alternativa:
   **8 llamadas cortas en total**. El schema pide sólo los hechos/IDs solicitados.
   Código compara contra valores extraídos de las fuentes originales, no contra
   la respuesta de otro modelo. Exigir cero errores de cifra, identidad, fecha,
   null/cero/ausencia y asociación fuente-dato; medir tokens/caché/latencia reales.
4. Si pasa, comparar dos casos completos de mantenimiento en ambos formatos
   (4 llamadas adicionales) con la misma política/cronología y validadores.
   Revisar cambios injustificados, riesgo omitido, fuentes equivocadas, escalados
   y repairs. La salida original no es verdad financiera por definición; valorar
   las discrepancias contra las fuentes con revisión humana.
5. No concluir equivalencia general de una muestra pequeña. Si aparecen errores
   de interpretación, conservar formato actual. Si se adopta, observar el próximo
   uso natural, sin lote duplicado ni promoción basada sólo en ahorro.

Estas llamadas **no se han ejecutado**: la petición pregunta cómo comprobarlo y
autoriza activar sólo el punto1. La batería offline existente demuestra identidad
de datos al decodificar, no comprensión por Luna.

## Investigación adicional de caché

CLI instalado: **0.163.0-alpha.11.1**. Se generaron y examinaron452 schemas del
protocolo app-server, incluidos experimentales. No aparecen campos públicos
prompt_cache/retention/TTL, tampoco en la referencia pública de configuración.
`codex_cache_capabilities.json` contiene versión, comando y resultado; no se
ejecutó turn/start ni modelo alguno. Ausencia en schemas no prueba inexistencia
de políticas internas del proveedor.

`cache_history.py` contrasta recibos20→21 por ID de sesión y contrato exacto:
CCJ obtuvo0 tokens cacheados tras9,313h; IREN/MRNA obtuvieron32.640 tras9,307/9,382h;
USAR obtuvo0 tras19,707h. Las llamadas comparten instrucciones y arrancan próximas,
así que no puede distinguirse retención nocturna de calentamiento compartido al
iniciar el lote. Estos datos **no miden un TTL máximo o garantizado**.

La documentación de Responses presenta30m y12h como duraciones mínimas
seleccionables, no como prueba de un máximo universal ni de la política aplicada
a Codex autenticado con ChatGPT. Corrige cualquier lectura de la nota inicial que
tratase12h como un límite rígido. Mantener una sesión no garantiza un cache hit.
No hay respaldo para afirmar caché diaria garantizada ni para activar una opción
desconocida mediante `-c`; no se cambia de autenticación/proveedor/API.

El pool actual reutiliza sesiones por contrato y borra turnos del ticker anterior
para evitar contaminación. Por ello ID persistente tampoco significa que retenga
el bloque de referencia de ESE ticker como prefijo. Aprovecharlo requeriría tanto
baselines independientes primero como fronteras de caché reutilizables y una
estrategia de afinidad por ticker; esto tiene coste/duplicación/retención por medir.

Recomendación: mantener esta optimización en estudio. Si se vuelve a ella, medir
prefijos/recibos en usos naturales, sin warmups ni llamadas de mantenimiento de
caché. No se ha creado ninguna automatización de observación.

Fuentes oficiales consultadas:
- https://learn.chatgpt.com/docs/config-file/config-reference
- https://developers.openai.com/api/docs/guides/prompt-caching
