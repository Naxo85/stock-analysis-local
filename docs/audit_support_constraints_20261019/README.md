# Investigación de los cuatro posibles obstáculos a soportes visibles

Actualización posterior autorizada19Oct: los puntos2/3/4 se implementaron y activaron en revisión41, conservando Opciones25. [Cambios, pruebas y despliegue](implementation/README.md). El cuerpo siguiente conserva la investigación previa y sus límites.

Fecha de investigación:19-10-2026. Corpus financiero vigente examinado: lote natural18-10-2026/09:08,46 informes y70 zonas. Se añaden antecedentes publicados13–16Oct y el archivo técnico congelado del18. Esta investigación no ejecuta un lote nuevo, no llama al motor de análisis, no cambia configuración/rúbrica ni publica informes.

## Dictamen

| Punto | ¿Conviene arreglarlo? | Cambio concreto recomendado | Certeza y límite |
|---|---|---|---|
|1. Peso25 de Opciones|**No cambiar el peso todavía.** Sí investigar su valor incremental después de corregir datos y continuidad.|Conservar peso/escala; distinguir desconocimiento, ausencia observada, mala calidad y nota heredada. Evaluar una alternativa preespecificada con opciones como contexto separado.|La dependencia de visibilidad está medida; no hay peso alternativo validado. Más casillas no demuestra mejores soportes.|
|2. Ceros heredados ante nueva evidencia|**Sí, prioridad alta.**|Permitir una actualización material del conocimiento del mismo soporte sin exigir demostrar que cambió el mercado ni declarar falso error pasado.|Cuatro casos claros del mecanismo de continuidad, no cuatro notas incorrectas demostradas; un quinto contractual débil y un contraejemplo muestran sus límites. Es inconsistencia/ambigüedad de instrucciones y aplicación, no veto numérico universal.|
|3. Descuentos acumulados y confluencia|**Corrección acotada; no eliminar componentes en bloque.**|Definir qué mide cada apartado y qué evidencia independiente añade Confluencia. Evitar usar una incertidumbre como deterioro demostrado. Revisar fundamentos heredados que invocan signo dealer no identificado.|No hay doble descuento automático por expiración en los cuatro repuntajes18, ni techo adicional recortando las41 cuentas de Volumen disponibles. Sí hay ambigüedad de familias y motivos heredados obsoletos.|
|4. Descubrimiento con filtro5%|**Sí, prioridad alta en cobertura dirigida.** Rediseño amplio de candidatos en una segunda fase.|Observar los orígenes activos CURRENT de suelo/gap independientemente de ranking y distancia, con identidad y estado explícitos. Después valorar un conjunto cercano acotado que conserve referencias distantes útiles.|Replay exacto138/138 reproduce omisiones y un caso donde la ausencia influye en comparación. No demuestra que quitar5% globalmente produzca mejores compras.|

El orden práctico recomendado es4 mínimo→2→3 acotado. El cambio de pesos del punto1 queda separado: corregir datos/semántica tiene un criterio de exactitud comprobable; elegir pesos predictivos exige evidencia de utilidad posterior.

## La caída visible y la corrección del diagnóstico inicial

| Lote | Informes | Zonas seleccionadas | Tickers con alguna zona | Visibles≥65 | ≥70 |
|---|---:|---:|---:|---:|---:|
|13Oct19:30|46|67|38|30|18|
|14Oct16:07|46|66|37|24|13|
|15Oct12:01|46|64|38|17|8|
|16Oct15:58|45|71|45|14|5|
|18Oct09:08|46|70|45|9|3|

La primera lectura de medias podía sugerir una rebaja generalizada de los mismos soportes. La comparación por rango exacto la matiza:24 rangos de14Oct permanecen18Oct,19 con los cinco componentes idénticos. Los otros cinco suman−2 puntos de Volumen y−8 de Opciones. Entre esos24, las zonas visibles pasan8→6; salen del conjunto16 rangos visibles y entran3. La identidad exacta puede separar dos geometrías del mismo soporte económico, por lo que no se llama a cada diferencia numérica una nueva estructura.

Además, selección38 permite publicar zonas débiles que antes podían quedar ausentes. Los tickers con alguna zona pasan37→45; no se ha aislado cuánto de ese aumento se debe a la política y cuánto al mercado o a las alternativas observadas. Incorporar zonas débiles puede reducir la media del conjunto sin endurecer la valoración de las anteriores. Las16 desapariciones de rangos antes visibles están trazadas a recibos originales, con motivos de pérdida de papel comprador, promoción de apoyo inferior y, en dos casos, revisión fundamental. Son razones del modelo, no certificación retrospectiva de cada decisión. Algunas incluyen interpretaciones gamma históricas posteriormente retiradas.

Por tanto, hay dos preguntas distintas: por qué se perdieron zonas fuertes anteriores y por qué apoyos nuevos/actuales no alcanzan65. Los defectos2/4 pueden afectar la segunda, pero no explican causalmente toda la caída24→9. El umbral del controller es65 y el recuento de las nueve zonas coincide con la captura; no se identificó un filtro visual adicional.

Reproducción y tablas completas: [pesos y censo](weights/README.md), [census.json](weights/census.json), [traza de los16 rangos](weights/visible14_removed_trace.json).

## 1. Opciones: efecto importante, peso alternativo no demostrado

En18Oct23/70 zonas tienen Opciones0, y ninguna supera60. Sin ese componente,65 exige86,7% de los75 puntos restantes. Hay11 zonas con Volumen0; tampoco llegan65. Cuatro tienen ambos componentes0, de modo que el máximo teórico restante es55.

Eso demuestra que el índice combina calidad estructural con cantidad/calidad de respaldo acreditado. No demuestra que una zona sin opciones deba ser igual de fuerte que otra con respaldo pertinente. Tampoco justifica tratar una carencia del muestreo como prueba de que el mercado no tiene ese respaldo.

La comparación de grupos es ilustrativa: las23 zonas sin puntos de opciones tienen Estructura media19,39 y Durabilidad10,78, superiores a16,85 y9,02 en las47 con opciones; Volumen es casi igual. Es posible que estemos ocultando estructuras defendibles por falta de otra familia, pero no tenemos desenlaces comparables que establezcan si ese filtro ayuda o perjudica.

Eliminar Opciones sin reescalar da0 visibles; reescalar los otros75 puntos a100 da28. Son sensibilidades aritméticas, no resultados económicos. Mantener65 después de cambiar escala no conserva su significado. No se elige la variante que más casillas produce.

La evidencia externa apoya límites de interpretación, no un peso concreto. [OCC/OIC](https://www.optionseducation.org/referencelibrary/faq/general-information) explica que OI no determina dirección ni garantiza liquidez. [Ni, Pearson y Poteshman](https://experts.illinois.edu/en/publications/stock-price-clustering-on-option-expiration-dates/) encuentran influencia de opciones sobre cierres alrededor del vencimiento: es evidencia contraria a descartar toda información de opciones, pero no valida la nota25 de nuestro soporte comprador. [Pan y Poteshman](https://www.nber.org/papers/w10925) emplean volumen comprador de apertura, una variable distinta del OI agregado disponible aquí.

Decisión: conservar el peso por ahora sin llamarlo calibrado; corregir la representación de evidencia antes de evaluar una alternativa. El valor incremental debe medirse por episodio y fecha, controlando distancia, estructura, vencimiento y cobertura. El archivo corto y dependiente no permite concluir que10,15,25 o0 sea óptimo.

## 2. Continuidad: sí hay una dificultad corregible

Las23 notas0 de Opciones del18 son heredadas. Cinco rangos contienen puts actuales observados:

| Zona | Nota total | Opciones | Observación dentro del rango |
|---|---:|---:|---|
|MP37,7–38|38|0|Put38,1.130OI, tres vencimientos|
|NVDA209,5–210,5|51|0|Put210,16.879OI|
|SPCX144,75–145,5|60|0|Put145,6.802OI|
|TSLA353,5–355|55|0|Put355,4.193OI|
|INOD52–52,5|46|0|Put52,99OI y horquillas amplias|

MP/NVDA/SPCX/TSLA reconocen corroboración actual, pero argumentan que cobertura nueva no prueba un cambio del mercado o error previo. La cautela sobre el pasado es correcta. La conclusión de conservar una nota basada en desconocimiento no se sigue necesariamente: ahora se dispone de conocimiento pertinente que podría cambiar el juicio, aunque se desconozca cuándo apareció ese respaldo.

El caso TSLA hace visible la asimetría: su Entry heredada conserva0 con put355 observado, mientras el nuevo Washout350 recibe13 en Opciones. No tienen por qué merecer la misma nota, pero su condición de heredado/nuevo afecta expresamente al tratamiento. El contraejemplo INTC demuestra que no hay un bloqueo universal: el15-Oct pasó0→17 en el mismo rango promovido y el16-Oct13→18, reconociendo que nueva cobertura no probaba apertura nueva.

### Corrección propuesta

- Explicitar una actualización material del conocimiento además de cambio de mercado y error pasado. Aplicarla también al mismo soporte, manteniendo su rango.
- Exigir identificar la premisa anterior limitada, la nueva observación verificable, su aplicabilidad y por qué cambia el juicio actual. El mismo dato reaparecido, otra fila TOP o detalle irrelevante no basta.
- Revisar sólo componentes afectados con la misma rúbrica y llamada ordinaria. OI positivo no asigna puntos automáticamente, ni cambia Confluencia/Durabilidad por arrastre.
- Registrar evidencia incorporada y fecha para que no produzca otra bonificación en cada revisión. Conservar fuentes, ámbito, ancla e ITV.

La vía mínima es aclarar `material_improvement` para mejora material de evidencia del mismo apoyo; una causa nueva explícita sería más trazable pero requiere versionar schema/consumidores. No se debe usar `prior_error` o `backing_changed` fingiendo hechos para sortear el contrato. No se propone una nueva llamada ni un clasificador de prosa.

Esto no promete un incremento de casillas: MP38+25 seguiría63 si nada más cambiara justificadamente. INOD muestra que información positiva pero débil puede no merecer una mejora material. [Auditoría y contraejemplos](continuity/README.md).

## 3. Solapamiento: hay que precisar el significado, no borrar riesgo

La hipótesis de doble castigo automático por vencimiento no se reproduce en18Oct. COIN/IONQ/IREN sólo reducen Opciones; los demás componentes quedan exactos. CAT baja Opciones y sube Durabilidad por supervivencia de respaldo independiente. Las41 auditorías numéricas de Volumen conservadas no sufren recorte adicional de un techo: el resultado es la suma. Incluyen cálculos heredados; no se convierten en41 cálculos contemporáneos.

Un mismo dato puede informar dimensiones distintas: repetición histórica no es lo mismo que supervivencia del soporte más allá de un vencimiento. Que dos notas bajen a la vez no demuestra doble conteo. El [manual OECD/JRC de índices compuestos](https://www.oecd.org/content/dam/oecd/en/publications/reports/2008/08/handbook-on-constructing-composite-indicators-methodology-and-user-guide_g1gh9301/9789264043466-en.pdf),p32, recomienda examinar tanto dependencia estadística como significado de las dimensiones; correlación por sí sola no resuelve la cuestión.

Sí hay ambigüedad aplicada a familias: algunas explicaciones tratan dos medias con distintos horizontes como confluencia, mientras otras agrupan varias observaciones de precio en una sola familia. Estructura, historial y confluencia pueden volver a citar la misma reacción sin explicar qué propiedad distinta aporta cada uso. KTOS ofrece un indicio de este solapamiento, pero no determina una nota correcta alternativa.

También persisten factores internos heredados que citan gamma negativa para limitar confianza/Durabilidad, especialmente CRWV y RKLB. Su fecha histórica no demuestra que40 introduzca esa interpretación; tampoco permite usar el signo dealer no identificado como riesgo actual probado. No se pueden aislar los puntos atribuibles a esa frase ni prometer una subida al retirarla.

### Corrección propuesta

Definir por componente la propiedad valorada y pedir que Confluencia identifique el aporte independiente adicional. Datos no disponibles limitan confianza acreditada; no constituyen deterioro observado. La proximidad de vencimiento sólo reduce supervivencia global cuando el apoyo dependa realmente de ese vencimiento. Revisar fundamentos que empleen inferencias dealer retiradas, sin transformar la retirada de una frase en aumento automático de puntos. Mantener los riesgos que sí estén acreditados.

No imponer que cada dato sólo pueda mencionarse una vez, ni borrar Confluencia/Durabilidad, ni ajustar todas las notas hacia arriba. [Casos, límites y evidencia](overlap/README.md).

## 4. Descubrimiento: la omisión es real, la solución debe preservar identidades

Se reconstruyeron los tres selectores de suelo/gap/AVWAP con el archivo descargado18Oct y su precio exacto. Las coordenadas redondeadas o resultados nulos originales coinciden138/138; ese control no verifica por sí solo identidad, fechas y todos los campos del registro. Al quitar únicamente el filtro5%, el número de ganadores pasa61→71 y hay37 cambios en25tickers:27 sustituciones y10 adiciones. No son37 soportes válidos nuevos ni37 compras.

Nueve de esos37 registros ya llegan exactamente por otra vía;33 tienen alguna referencia a≤0,2ATR, que no es identidad ni prueba de equivalencia. Todos los46 tickers reciben alguna referencia cercana mediante opciones, medias, Donchian u orígenes dirigidos. La limitación es la cobertura de determinadas estructuras, no un veto universal a soportes próximos.

Una comprobación separada identifica20 referencias tipadas de suelos/gaps asociadas a zonas CURRENT activas, correspondientes a19 orígenes únicos; las20 referencias se reconstruyen exactamente en los conjuntos de datos descargados, pero9 orígenes de8 tickers faltan del listado actual:CLS290,88;HIMS27,345;INTC85,62;LRCX251,89;MRVL221,68/225,14;SNDK1287,04;TLN337,22;WDC312,2. No se extrajeron estos orígenes de precios sueltos de prosa. Las9 omisiones son evidencia más directa para la corrección dirigida que el número global de alternativas.

Hay un mecanismo temporal que encaja con la preocupación del usuario: al caer el precio hacia un soporte inferior, éste puede dejar de cumplir la distancia mínima y desaparecer precisamente cuando se acerca. CLS290,88 pasa de8,11% bajo el precio en la referencia a3,72%; WDC312,2 pasa8,89%→4,58%. El filtro es antiguo, no una restricción introducida por40. Su efecto sobre la cobertura puede crecer con la trayectoria del precio.

### Caso concreto: CLS

El archivo permite reproducir un suelo290,88 con dos toques fechados y volumen relativo1,805. Está3,72% bajo el precio y el filtro lo elimina. El CURRENT anterior contenía289,5–292. La comparación del modelo justifica la alternativa283–285 frente al antiguo290,88 indicando que carece de origen actual observado. El origen se reconstruye desde los datos ya descargados: falta en la selección suministrada, no está demostrado que falte en el mercado. Esto no decide cuál rango debería ganar, pero sí demuestra que la comparación recibe información incompleta pertinente.

### Contraejemplo: WDC

El gap312,2 también se omite por estar4,58% bajo el precio. El modelo mantiene311–313 y explica que desaparición de la lista no prueba pérdida. La continuidad está funcionando correctamente en este caso. Reparar cobertura debe permitir confirmar o refutar el origen, no forzar una sustitución ni una subida de nota.

### Corrección mínima recomendada

Extender la observación dirigida ya usada para opciones/AVWAP a los suelos y gaps que justifican CURRENT. Resolverlos por identidad de origen autenticada y datos descargados, independientemente de ranking/distancia. Estados distintos para observado, no reconstruido, ambiguo, datos insuficientes e invalidación realmente medida. No considerar vecino numérico como el mismo origen.

Los nuevos orígenes de rango deben conservar método, fechas de miembros/primer y último toque y fecha en que podían conocerse. Los antecedentes legacy sólo admiten reconciliación exacta e inequívoca; si faltan identidades, devolver incertidumbre. La incorporación requiere una nueva revisión de fuente/input, manteniendo contratos congelados≤40 exactos.

Una segunda fase puede ofrecer un conjunto compacto de candidatos cercanos y diversos, conservando referencias distantes útiles. No recomendaría sustituir globalmente5%→0% como arreglo aislado: cambia ganadores y puede desplazar estructuras válidas, aun cuando sólo se pretendía recuperar cobertura. En LRCX ni siquiera recupera el origen activo251,89: el selector sin filtro elige264,54. Observación dirigida y ranking de candidatos resuelven problemas diferentes.

El replay conserva barras y calidad del archivo original;12 archivos no acreditan ventana anual completa. Esa limitación figura por caso y no se convierte en historia perfecta. Los candidatos omitidos no tienen evaluación predictiva independiente. [Replay, casos y propuesta](discovery/README.md).

## Cómo comprobar una corrección sin convertir esta investigación en otra tanda

Los cambios anteriores son una propuesta concreta, no una activación. Antes de aplicarlos:

1. Versionar instrucciones/observación nuevas y preservar frozen≤40, receipts, anclas y formatos históricos.
2. Reproducir CLS/WDC y los138 controles baseline; negativos de identidad ambigua, rango parecido de otro origen, barra incompleta y origen realmente perdido. Verificar que el catálogo sigue enlazando el objeto exacto.
3. Usar MP/NVDA/SPCX/TSLA e INTC para comprobar que el contrato admite actualización de evidencia sin inventar delta de mercado; probar repetición, dato no aplicable/expirado y preservación de componentes no afectados.
4. Comprobar que las aclaraciones de confluencia no añaden umbrales, cuotas ni descuentos nuevos; no recuperar automáticamente niveles rotos por aumentar cobertura.
5. Observar el siguiente uso natural tras una futura activación: qué evidencia se incorpora, decisiones justificadas, reparaciones y falsas retiradas. El número de casillas es descriptivo; no criterio de éxito.

No hace falta validar alpha para corregir una identidad omitida o una contradicción de conocimiento. Sí hace falta evidencia futura adecuada para cambiar pesos, ranking o interpretar puntuaciones como probabilidad. La [metodología de evaluación existente](../audit_work_20261017/methodology_evaluation.md) sigue siendo la referencia; el [trabajo de Novy-Marx](https://www.nber.org/papers/w21329) aporta fundamento adicional para limitar variantes y evitar escoger combinaciones por su resultado dentro de muestra.

## Evidencia guardada

- [Pesos/censo](weights/README.md):229 estados publicados más46 referencias exactas, con hashes; tablas y descomposición por rango.
- [Continuidad](continuity/README.md):cinco lotes, casos favorables/contrarios y contratos.
- [Solapamiento](overlap/README.md):componentes, auditorías de Volumen y razones heredadas.
- [Descubrimiento](discovery/README.md):46 archivos congelados,138 selecciones/nulos reproducidos y sensibilidad del filtro.

Se consultaron fuentes públicas primarias para metodología; no se renovaron inputs de análisis ni se incorporó información posterior a los replays. La investigación produce documentación y derivados offline únicamente. No afirma que un dispositivo, Sheet o GCS se haya vuelto a verificar el19-Oct.
