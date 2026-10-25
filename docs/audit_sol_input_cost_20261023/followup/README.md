# Investigación posterior y vuelta a Sol medium

**Aplicación posterior autorizada:** el esquema compartido ya está activo sólo
para nuevas revisiones/reparación41. Ver [implementación](../implementation/README.md).
El resto de propuestas de este estudio siguen sin activación. El estado «sólo
modelo activado» inferior describe el cierre de la investigación previa.

23/10/2026. Petición: restaurar Sol medium e investigar todas las vías de ahorro
de la auditoría corregida. Se usan los mismos 92 casos reales Sol del 21 y 22,
incluidas las 13 actualizaciones del 22. El lote Luna no determina prioridades.

## Cambio aplicado y comprobado

`config/codex_analysis.json` vuelve a `triage_model=gpt-6.1-sol` y
`triage_effort=medium`. Full permanece `gpt-6.1-sol/high`; revisión41, ITV5,
techo6, transporte pointer-diff y guía de Volumen conservan sus valores.
`load_policy()` acepta y devuelve esa configuración. Hash del archivo:
`2836bde9712e17d3a5ddcbf3cdccc34a034b5719dd42cce616344aebf1a0edd2`.
Los congelados mantienen sus políticas/recibos originales. Se actualizan las
notas operativas para que el alias interno Luna no se confunda con el modelo.

Único cambio de ejecución en esta tarea: los dos campos de modelo/esfuerzo.
Los optimizadores siguientes siguen siendo prototipos offline, sin importación
desde producción. No se ha iniciado ningún thread de modelo, análisis, lote,
recuperación, refresco financiero ni publicación; tampoco llamadas de prueba.

## 1. Esquema de salida compartido: viable, ahorro pequeño por demostrar

La [documentación oficial de Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs#definitions-are-supported)
admite definiciones compartidas mediante `$defs/$ref`. El schema actual de las
92 revisiones es el mismo. El prototipo pasa de 14.935 a 7.881 caracteres
compactos: 47,23% del schema y alrededor de 1,4% del conjunto visible de entrada.

Se ha ampliado la comprobación anterior:

- Expansión idéntica **incluido el orden de propiedades**, relevante para la
  salida estructurada; no sólo igualdad de diccionarios sin orden.
- Objetos cerrados y todos sus campos requeridos; se mantienen nulls, tipos,
  uniones, enums, rangos y patrones del contrato original.
- Las 92 respuestas originales se aceptan; **13.606 mutantes** con campos extra,
  ausentes y tipos incorrectos se rechazan igual en ambos schemas.

Esto deja una implementación acotada: factorizar una copia del schema de nuevas
preparaciones de mantenimiento/reparación, congelar su versión/hash real y
mantener el contrato lógico completo para validación. Full y congelados previos
no deben recibirla. Las restricciones específicas de fuentes de una reparación
deben conservarse, nunca retirarse para intentar mejorar la caché.

No se ha probado una admisión real. Además, menos caracteres enviados no
garantiza menos tokens cobrados: el servidor puede transformar o expandir el
schema. La cifra de 1,4% no debe venderse como ahorro efectivo de cuota. Al
cambiar el schema también cambia el contrato de sesión/caché; su efecto inicial
puede ser adverso. Es la mejora más sencilla de preparar, no un gran recorte.

Evidencia: `schema_factored.prototype.json` y `variants.json`.

## 2. Capturas históricas: el ahorro exige el codec más complejo

Se comparan variantes con el mismo transporte pointer-diff ya activo. Los
porcentajes siguientes son adicionales y usan JSON + instrucciones + schema
como denominador, en caracteres Unicode; el texto explicativo del nuevo codec
todavía no está incluido.

| Variante de capturas históricas | 21/10 | 22/10, principal |
|---|---:|---:|
| Diferencias recursivas, también dentro de listas | 13,34% | 8,61% |
| Diferencias en objetos, listas cambiadas completas | 0,85% | 0,66% |
| Orden estable y diferencias en las tres capturas | 13,29% | 8,51% |
| Orden estable y diferencias sólo en CURRENT/última revisión, ancla sin transformar | 9,53% | 5,09% |

Las cuatro variantes reconstruyen los 92 contextos. Diez casos límite
verifican presencia/ausencia, null, bool/0, enteros/flotantes, cero negativo,
claves especiales y cambios de contenido, longitud u orden de listas. No se
redondean precios ni se sustituye una fuente por otra parecida. Los índices
sirven para reconstruir listas, no para establecer identidades financieras.

**Hallazgo nuevo:** el gran ahorro no procede de una herencia sencilla de
objetos. Depende de aplicar diferencias parciales a listas de registros. El
programa las reconstruye exactamente; aún no se ha probado que Sol haga esa
reconstrucción con la misma fiabilidad al razonar sobre fuentes, vigencia y
aritmética. Reconstruirlo todo antes de enviarlo al modelo elimina este ahorro
de tokens, aunque ahorre almacenamiento/transporte local.

Para una implementación futura habría que versionar el codec y su instrucción,
declarar explícitamente base, lado temporal y presencia, decodificar antes de
resolver alias/validar fuentes, y autenticar tanto el congelado íntegro como los
bytes realmente enviados. El contexto de validación conserva todos los datos.
Nunca interpretar una omisión del patch como ausencia de respaldo. La garantía
local de roundtrip no sustituye evaluar interpretación financiera en updates,
zonas ausentes, fuentes dirigidas y cambios de rol.

No se activa ninguna variante ni se promete calidad equivalente. El combinado
12–17% de la primera auditoría sigue siendo un tamaño de prototipos, no una
ganancia acumulable a otra estrategia de caché.

## 3. Caché: interacción, protocolo y límites del cliente instalado

Las 46 parejas reales Sol→Sol mantienen modelo, esfuerzo, instrucciones y
schema. En 43 el ancla completa también es idéntica. Las pruebas nuevas miden
la interacción con la compresión histórica:

| Disposición textual | Prefijo común medio 21→22 |
|---|---:|
| Orden estable, sin codec nuevo de capturas | 115.259 caracteres |
| Mismo orden, comprimiendo también el ancla contra `/slim` actual | 29.991 |
| Mismo orden, ancla sin transformar | 94.180 |

La representación de un ancla inmutable puede volverse variable si se expresa
como diferencias frente al técnico del día. Por eso compresión y caché deben
compararse como alternativas o combinaciones medidas, no sumar sus beneficios.
También influye el momento en que empieza a variar CURRENT, después del ancla.
Ninguno de esos prefijos es un hit ni un ahorro de crédito medido.

Se inspeccionó el CLI que el runner resuelve realmente:
`codex-cli 0.163.0-alpha.11.1`, 452 schemas del protocolo con experimentales.
No se inició app-server con un thread: sólo se ejecutaron `--version` y la
generación local de metadatos. No aparecen campos públicos de caché/TTL en
los schemas generados; `ContentItem` no declara un breakpoint. La ausencia en
metadatos no demuestra cómo funciona el backend ni que un campo desconocido
vaya a conservarse si se inyecta como JSON libre.

Hay una vía de diseño más concreta que antes: el protocolo instalado contiene
`thread/inject_items`, y la [documentación oficial del app-server](https://learn.chatgpt.com/docs/app-server#inject-items-into-a-thread)
describe añadir mensajes al historial sin generar un turno. Permitiría estudiar
un mensaje **user** con el ancla fechada y otro con el sufijo del día, manteniendo
las fuentes como datos. El runner actual usa un único texto JSON por stdin;
necesitaría un cliente app-server y recibos de todo el historial ordenado.

Pero dos mensajes por sí solos tampoco demuestran la caché: la
[documentación de caché](https://developers.openai.com/api/docs/guides/prompt-caching)
sitúa la escritura implícita en el último mensaje elegible y distingue esa
escritura de las fronteras anteriores de búsqueda. No hay evidencia de que el
cliente actual permita escribir deliberadamente el prefijo del ancla sin una
llamada extra. **Añadir una frontera no demuestra que ese prefijo se guarde.**
No se trasladan controles de la API a la autenticación ChatGPT ni se promete
retención de un día a otro. No se proponen warmups o llamadas para conservarla.

Los propios recibos descartan un arreglo simple de «reutilizar sesión»: las
36 revisiones sin web del 22 ya reutilizaban sesión y limpiaban su historial,
pero sólo tenían 19,9% de entrada en caché y cuatro tenían cero caché. El 21,
cinco de los seis casos sin caché también reutilizaban sesión. Los metadatos
no identifican por sí solos la causa de esos misses.

La reparación en el mismo historial sí tiene una reutilización más directa
del mensaje completo anterior, si sigue disponible; exige aislamiento y
autenticación de historial, y no debe cambiar su schema de fuentes. Sin embargo,
en los dos lotes Sol hubo **cero reparaciones**: no resuelve el gasto observado.

Conclusión: hay una investigación de protocolo concreta, pero **no una bandera
verificada que consiga mucha más caché en estas primeras revisiones diarias**.
No migraría el ejecutor sólo por la coincidencia textual de anclas.

Evidencia: `protocol.json`, `variants.json` y
`../../audit_context_cost_20261022/inspect_codex_cache.py` como antecedente.

## 4. Instrucciones específicas de mantenimiento

Se inventariaron por hash y tamaño los 13 archivos del ensamblado vigente.
La política financiera ocupa 40.626 caracteres y el contrato41 25.234; ambos
incluyen criterios que mantenimiento necesita para juzgar vigencia, continuidad,
riesgo, componentes y fuentes. No equivalen a instrucciones prescindibles de
redacción full. La composición41 sustituye contratos viejos: no está anexando
todos los contratos históricos que aparecen en el código.

La sección identificada explícitamente «sólo full nuevo», ESTADO DE TESIS40,
ocupa 2.114 caracteres: apenas **0,43–0,44%** del conjunto visible de entrada.
Ni siquiera es íntegramente eliminable: contiene la herencia exacta y el
significado/riesgo del estado en mantenimiento. No se propone suprimirla.

Para compactar más habría que reescribir reglas compartidas y mapear cada
obligación, excepción y prioridad, con cambios de prompt y evaluación de calidad.
No hay un recorte grande y seguro demostrado mediante quitar instrucciones
que sólo pertenezcan al full. Se conserva el inventario, sin nuevo prompt activo.

Evidencia: `instructions.json` y ensamblado en `adaptive_stage.prepare`.

## 5. Fuentes bajo demanda: posible arquitectura, ahorro no probado

El catálogo existente ya permite pedir registros por handles exactos, sin
adivinar precios o índices. Se preparó un lector offline vinculado al congelado:
7.576 registros de los 92 contextos vuelven idénticos; 368 solicitudes inválidas
se rechazan (otra vinculación, handle desconocido, ruta usada como handle y
lista vacía). Devolver una copia evita que el consumidor altere el congelado.
El binding es del cliente, nunca un hash que el modelo deba transcribir.

El protocolo instalado expone `dynamicTools` y la
[documentación del app-server](https://learn.chatgpt.com/docs/app-server#dynamic-tool-calls-experimental)
describe las llamadas a herramientas del cliente. Eso ofrece un mecanismo
potencial para un lector local, **no lo habilita en el ejecutor actual**, que
sólo autoriza web dentro de su alcance financiero existente.

Diseño que habría que implementar y evaluar:

1. Preparación conserva el congelado completo y su catálogo autenticado. La
   vista inicial mantiene autoridad, propiedad, fechas, CURRENT, ancla, riesgos,
   agenda completa y descubrimiento de **todos** los candidatos/orígenes con
   estado y cobertura. No seleccionar sólo TOP ni ocultar opciones dirigidas.
2. Una herramienta local `read_sources(handles)` devuelve registros exactos de
   ese único congelado. No descarga datos, no lee archivos arbitrarios, no
   concede a antecedentes autoridad actual y no cambia de captura por error.
   Para otros datos fuera del catálogo hará falta un registro adicional exacto;
   este prototipo no cubre toda la memoria/noticias/comparación.
3. «No cargado» se distingue de null, cero, ausencia y descarga fallida. Toda
   fuente que determine un juicio/cálculo debe estar suministrada o leída; las
   alternativas relevantes deben seguir siendo descubribles antes de elegir.
4. Recibos autentican el historial, orden y respuestas de herramienta; presupuesto
   y timeout cuentan todas las continuaciones. La validación/publicación usa el
   congelado completo, preservando autoridad, riesgo e ITV. Un fallo de lectura
   no se convierte en retención aprobada ni ausencia de soporte.

Una ida y vuelta puede anular el ahorro si el contexto se vuelve a procesar
sin caché. Ejemplo **algebraico, no medición de tokens**: con 24% de entrada fija
y 76% de datos, conservar inicialmente la mitad de los datos deja 62% del tamaño
original. Dos pasadas ya suman al menos124%, antes de cargar detalles. Para
ganar con dos pasadas sin caché, habría que conservar menos del34,2% de los datos
inicialmente, aun suponiendo detalles de tamaño cero. Una caché efectiva cambia
ese cálculo; debe medirse con el protocolo real y todo el uso de la llamada.

El lector demuestra acceso exacto, no una vista inicial financieramente completa
ni ahorro. No se ha diseñado una selección de contexto que preserve calidad y
reduzca50%. No es el siguiente cambio sencillo que recomendaría activar.

## Decisión recomendada después de investigar

- **Hecho:** Sol medium restaurado para revisiones futuras; full high intacto.
- **Primer candidato acotado:** schema compartido. Compatible con el lenguaje
  documentado y comprobado localmente; beneficio real de tokens pendiente.
- **Mayor recorte de tamaño medido:** diferencias históricas dentro de listas.
  Tratarlo como cambio de formato que necesita evaluación financiera; no añadir
  su ahorro al de una caché hipotética. Mantener el ancla literal si se evalúa
  simultáneamente la vía de caché, asumiendo un recorte menor.
- **No activar por estos resultados:** orden para caché, recorte general de
  instrucciones, alias con null o fuentes bajo demanda. No hay ahorro efectivo
  demostrado que compense todavía su complejidad/riesgo de interpretación.

La forma de medir las optimizaciones futuras debe contar entrada sin caché,
caché, salida y todas las rondas; los porcentajes semanales compartidos no
aislan su efecto. No se han añadido llamadas o lotes para obtener esa medición.

## Reproducibilidad

Ejecutar con `.venv\Scripts\python.exe` los scripts de esta carpeta:
`check_policy.py`, `inspect_protocol.py`, `investigate_variants.py`,
`inspect_instructions.py` e `investigate_sources.py`. `../verify.py` conserva
las comprobaciones de recibos/uso de la auditoría original. Los artefactos
JSON son evidencia offline, no opciones nuevas de producción.
