# Solapamientos de la rúbrica: evidencia y decisión propuesta

Investigación local del 19-10-2026, limitada al punto 3. Se leyeron los 46 informes
publicados por la orden natural del 18-10 y sus CURRENT congelados, los factores de
sus 70 zonas activas, las 41 auditorías numéricas de Volumen presentes en esos
informes y las reglas/código vigentes. No hubo nuevas llamadas financieras,
capturas, lotes, publicaciones ni modificaciones de producción. Los resultados
descriptivos están en [evidence.json](evidence.json); se reproducen con
`.venv\Scripts\python.exe docs\audit_support_constraints_20261019\overlap\extract_evidence.py`
desde el repositorio. El script guarda
hashes de los 92 originales leídos y sólo escribe su evidencia local.

## Dictamen

**Sí conviene precisar la atribución de evidencia y las familias de confluencia;
no hay evidencia para eliminar de inmediato un componente, regalar puntos por
datos ausentes ni atribuir la caída a un descuento múltiple automático.** Hay
dependencia estructural entre los componentes, pero dependencia estadística no
equivale por sí misma a un error: dos dimensiones pueden responder preguntas
distintas sobre el mismo hecho. Los casos actuales muestran decisiones que evitan
deliberadamente propagar una pérdida a otros componentes.

Existe además un fundamento legado que debe dejar de usarse en el juicio actual:
factores de CRWV y RKLB relacionan el signo gamma supuesto con menor Durabilidad.
Son textos heredados y fechados, no una regla introducida por revisión 40; la
atribución de dealer ya fue retirada de las instrucciones nuevas. Corresponde
revisar si la nota sigue sustentada sin ese argumento, no subir puntos por borrar
la frase. Este saneamiento semántico tiene prioridad sobre modificar pesos.

La corrección acotada propuesta es de interpretación dentro de la llamada
habitual. Debe aclarar qué pregunta contesta cada componente y qué información
adicional fundamenta un descuento distinto, sin nuevos campos obligatorios,
clasificadores de prosa, reparaciones, repuntuación masiva o cambios de pesos.
La conveniencia de mantener Confluencia como bonus aditivo de 15 puntos sigue
siendo una hipótesis metodológica que necesita comparación prospectiva.

## 1. Lo que se repite por construcción

La [rúbrica financiera vigente](../../../prompts/stock_analysis_semantic_v13.md)
dispone Estructura 25, Volumen/reacciones 20, Opciones 25, Confluencia 15 y
Durabilidad 15. En las líneas 116–125 aparecen dependencias concretas:

| Observación | Primer uso | Otro uso posible | Distinción legítima / riesgo |
|---|---|---|---|
| Reacciones históricas | Repetición, tasa, magnitud y recencia de Volumen | Persistencia de Durabilidad; validez multihorizonte de Estructura | Describir cantidad, calidad, vigencia y estabilidad es distinto; no son votos estadísticos independientes |
| Vencimientos observados | Hasta 6 puntos de liquidez/persistencia en Opciones | Hasta 4 de supervivencia a evento/vencimiento en Durabilidad | La primera mide contratos; la segunda debe medir el soporte completo, incluyendo estructura ajena a esos contratos |
| Nodo de volumen cercano | Hasta 3 puntos del perfil diario aproximado | Coincidencia espacial de Confluencia | El mapa puede coincidir con un origen distinto; repetir la misma proximidad sin una segunda familia no acredita otra confirmación |
| SMA, pivote, gap, reacción, AVWAP | Definición/horizonte de Estructura | Familias/coincidencia de Confluencia | Varias transformaciones pueden describir escalas distintas; sus nombres o proveedores no crean independencia |
| Datos desconocidos o pendiente de maduración | No se pueden conceder puntos históricos no observados | Posible rebaja de confianza general | La falta no demuestra fracaso, desaparición ni riesgo nuevo en cada apartado |

No está calibrado cuánto debe pesar cada dimensión ni su aportación incremental.
El informe previo ya había señalado estas dependencias; esta investigación aporta
casos de la orden 18-10 y controles contrarios. Véanse
[metodología de volumen/opciones, §§5–8](../../audit_work_20261017/methodology_volume_options.md)
y [protocolo de evaluación](../../audit_work_20261017/methodology_evaluation.md).

Como referencia general contrastada el 19-10, el
[manual OECD/JRC de indicadores compuestos, p.32](https://www.oecd.org/content/dam/oecd/en/publications/reports/2008/08/handbook-on-constructing-composite-indicators-methodology-and-user-guide_g1gh9301/9789264043466-en.pdf)
explica que combinar dimensiones correlacionadas puede duplicar peso, pero exige
examinar su significado además de la correlación. También advierte que ponderar
por disponibilidad/calidad puede privilegiar lo más fácil de medir. Es
metodología de indicadores, no validación de estos soportes ni de los pesos actuales.

## 2. Contraevidencia a una cascada automática de descuentos

Al comparar cada casilla con la misma casilla y rango de CURRENT congelado, sólo
cuatro zonas repuntúan componentes en la orden 18-10. Las demás diferencias de
casillas no se consideran aquí continuidad del mismo rango: promociones y
sustituciones deben estudiarse por identidad, como hace la auditoría global.

| Misma Entrada | Opciones antes → después | Volumen / Confluencia | Durabilidad antes → después |
|---|---:|---|---:|
| CAT 728–732 | 12 → 8 | 9 y 7, exactos | 7 → 8 |
| COIN 169,5–170,4 | 17 → 14 | 14 y 10, exactos | 8 → 8 |
| IONQ 29,84–30,1 | 18 → 13 | 8 y 11, exactos | 11 → 11 |
| IREN 26,5–26,7 | 17 → 13 | 0 y 8, exactos | 6 → 6 |

COIN explica que no equipara vencimiento con desaparición de todo el soporte.
IONQ conserva Durabilidad porque el gap aporta origen independiente. CAT incluso
la incrementa, al sobrevivir la estructura al vencimiento. Estos casos contradicen
la afirmación de que una pérdida de opciones *necesariamente* se vuelve a restar
en Confluencia y Durabilidad. No demuestran que cada número sea óptimo ni excluyen
errores en otros periodos o al puntuar por primera vez un soporte nuevo.

Fuentes originales: [CAT](../../../logs/batch/2026-10-18/09-08-40/adaptive/CAT/publish/output/CAT/latest.json),
[COIN](../../../logs/batch/2026-10-18/09-08-40/adaptive/COIN/publish/output/COIN/latest.json),
[IONQ](../../../logs/batch/2026-10-18/09-08-40/adaptive/IONQ/publish/output/IONQ/latest.json),
[IREN](../../../logs/batch/2026-10-18/09-08-40/adaptive/IREN/publish/output/IREN/latest.json).

El código de [Volumen](../../../src/local_runner/volume_arithmetic.py) sólo suma
sus subcriterios y verifica techos, dirección, fuentes y herencia; no cambia otros
componentes. Desde revisión 34 la distancia del nodo no impone un segundo techo a
las reacciones. En los **41 cálculos auditados conservados**, la suma de partes
coincide con el resultado en todos: **ningún techo recorta un punto**. Por tanto,
suprimir esos techos no elevaría ninguno de esos 41 valores tal como fueron
calculados. Son cálculos de fechas distintas, muchos heredados; no 41 cálculos
nuevos del 18-10. Para los otros 29 soportes no se infiere una auditoría que no está.

## 3. Los once ceros de Volumen no prueban un bug de unavailable

APP, ASTS, CIFR, IREN, KTOS, LEU, OKLO, QBTS, SOFI, USAR y WDC tienen Volumen 0.
Los motivos distinguen diez casos de historia no disponible/completada y perfil
lejano de WDC, con observaciones históricas que no aportan puntos aplicables.
No deben confundirse los factores heredados con una descripción actualizada de
todas sus fuentes: se respetó su fecha y se examinó su razonamiento original.

Ejemplo especialmente claro: KTOS y USAR tienen un mínimo del 15-10 con una
recuperación observada, un test pendiente de cinco sesiones y nodos diarios muy
lejanos. QBTS tiene la misma limitación de maduración. El análisis **sí selecciona
esas compras**, pero no transforma la recuperación de una sesión en una defensa
histórica de cinco sesiones. La estructura y la viabilidad usan esa reacción;
la estadística histórica espera su ventana. Esto constituye una preferencia por
evidencia madura en el componente correspondiente, no una prueba de que el
soporte haya fallado.

La instrucción de la línea 130 —unavailable no es evidencia negativa ni cero
automático— coexiste con la de no inventar puntos y con criterios numéricos que
requieren observaciones completas. No significa que deba asignarse una nota
positiva arbitraria. El código `calculate` devuelve `None` cuando falta un bloque,
y la validación sin pareja completa no fuerza Volumen 0. Su valor lo decidió el
modelo a partir de la evidencia restante. Si existe un nodo válido o una reacción
externa verificable, debe evaluarse aunque otra pieza falte.

Tampoco es correcto afirmar que once ceros son once malas defensas demostradas:
en diez casos el texto indica carencia/maduración. Para evaluar resultados y
explicar confianza conviene conservar esa distinción, ya presente en las fuentes,
sin imputar medias, regalar el máximo de 4 o cambiar el denominador a conveniencia.

Fuentes: [KTOS](../../../logs/batch/2026-10-18/09-08-40/adaptive/KTOS/publish/output/KTOS/latest.json),
[USAR](../../../logs/batch/2026-10-18/09-08-40/adaptive/USAR/input.json),
[QBTS](../../../logs/batch/2026-10-18/09-08-40/adaptive/QBTS/input.json),
[WDC](../../../logs/batch/2026-10-18/09-08-40/adaptive/WDC/publish/output/WDC/latest.json).

## 4. Ambigüedades que sí merecen corrección acotada

**Confluencia no se interpreta de forma uniforme.** La regla exige familias
realmente distintas y dice que señales derivadas de la misma fuente cuentan como
una sola. Revisión 40 vuelve a advertir que medias, momentum y pivotes de los
mismos precios no son ensayos independientes. Sin embargo:

- SNDK Washout, puntuado el 15-10 y conservado el 18-10: Confluencia 8 (familias 4, coincidencia 4) por
  gap, historial de reacción y SMA200 próxima; Opciones 0 y nodo de volumen lejos.
- TSM Washout, puntuado el 16-10 y conservado el 18-10: Confluencia 9 (familias 6, coincidencia 3),
  describiendo las dos medias como cálculos y horizontes distintos; AVWAP puede
  incorporar actividad negociada y existe un nodo a 2,94%, así que no es un
  experimento puro de duplicación de precio.
- AMD Entrada heredada: Confluencia 10 por media y anclaje; AMD Washout 7 reconoce
  expresamente que perfil y anclaje comparten precio/volumen.
- MP, KTOS, USAR y WDC: una familia recibe Confluencia 0; QBTS recibe 3 aun
  describiendo explícitamente una sola familia de precio.

Esto demuestra margen interpretativo y justifica aclarar el concepto, pero no
permite calcular automáticamente la nota correcta de cada caso. El subcriterio
mezcla cantidad y calidad, y no define una tabla única por número de familias.
No debe presentarse toda diferencia como infracción determinista. Además, aplicar
una definición de independencia más estricta podría **bajar**, no subir, ciertas
notas: no es una reparación diseñada para producir más casillas visibles.

**Durabilidad puede reutilizar una carencia sin explicar una consecuencia distinta.**
KTOS conserva D5 = persistencia 1 + supervivencia 2 + resiliencia 2. El factor dice
que el origen no depende del vencimiento, pero sólo tiene una reacción. Esa misma
escasez limita ya multihorizonte y Volumen. No se identifica en esa explicación
qué evento inmediato justifica reducir el subcriterio de supervivencia. Es un
indicio localizado de atribución poco clara, no prueba suficiente para cambiar
D5 a un número escogido por el auditor. Aun otorgar hipotéticamente los otros dos
puntos de supervivencia dejaría su total en 22, muy lejos de visibilidad 65.

Una formulación precisa debería pedir que Durabilidad evalúe el conjunto y que
el descuento por vencimiento dependa de que **ese soporte** pierda respaldo al
vencer. No tener historia madura puede limitar persistencia; no identifica por
sí mismo un vencimiento adverso. Un evento puede afectar varias dimensiones si
la consecuencia es distinta y está sustentada; prohibir que un hecho aparezca
dos veces también sería un error.

Fuentes: [SNDK](../../../logs/batch/2026-10-18/09-08-40/adaptive/SNDK/publish/output/SNDK/latest.json),
[TSM](../../../logs/batch/2026-10-18/09-08-40/adaptive/TSM/publish/output/TSM/latest.json),
[AMD](../../../logs/batch/2026-10-18/09-08-40/adaptive/AMD/publish/output/AMD/latest.json),
[KTOS original 16-10](../../../logs/batch/2026-10-16/15-58-24/adaptive/KTOS/triage.json).

**Signo gamma supuesto en fundamentos heredados.** Cinco factores vigentes como
antecedentes conservan la expresión gamma negativa o régimen gamma. ASML e IONQ
Washout se limitan a decir que no garantiza absorción/suelo; esa frase no demuestra
por sí sola una rebaja. CRDO afirma que exige estabilización, sin aislar efecto
numérico porque hereda componentes. Los dos vínculos más claros son:

| Factor heredado | Durabilidad | Argumento conservado | Límite de la evidencia |
|---|---:|---|---|
| CRWV Entrada 60,3–60,8 | 9 = 4+2+3 | Una defensa antigua y gamma negativa limitan confianza | La defensa antigua y concentración por vencimiento siguen siendo hechos relevantes; no se sabe cuántos puntos, si alguno, se restaron exclusivamente por el signo |
| RKLB Entrada 49,7–50,1 | 10 = 4+3+3 | Reacción aislada, historial antiguo y régimen gamma negativo mantienen fragilidad | Los dos primeros motivos pueden sostener fragilidad sin el tercero; no cabe imputar una nueva nota al quitarlo |

Los informes originales son del 16-10 y permanecen fechados al heredarse. La
revisión 40 indica que el agregado calls-minus-puts no identifica posición dealer;
no se acusa al runtime40 de haber introducido esa regla. La corrección adecuada es
que el juicio actual no utilice ese signo para limitar D ni para defender una nota
por autoridad histórica. Debe revisar los demás fundamentos y conservar la nota
si siguen justificándola, corregir sólo un error demostrado bajo el contrato
normal y preservar el antecedente original. No hay evidencia para afirmar un
número de visibles perdidas por esta causa; ambos ejemplos siguen visibles en65.

Fuentes: [CRWV](../../../logs/batch/2026-10-18/09-08-40/adaptive/CRWV/publish/output/CRWV/latest.json),
[RKLB](../../../logs/batch/2026-10-18/09-08-40/adaptive/RKLB/publish/output/RKLB/latest.json),
reglas financieras40, líneas169–173 del prompt enlazado.

## 5. Alcance de la corrección y verificación propuesta

Recomendaría incorporar a la próxima composición autorizada, para ambos roles y
su reparación habitual, una aclaración breve:

> Identifica qué observación aporta cada familia y qué pregunta distinta responde
> cada componente. Transformaciones o copias del mismo dato no crean familias
> nuevas. La falta de una familia no prueba deterioro de las otras. Puntúa la
> persistencia de contratos en Opciones y la supervivencia del soporte completo en
> Durabilidad, considerando respaldo independiente. Si un mismo hecho limita más
> de un componente, justifica sus consecuencias diferentes; no repitas el mismo
> descuento. Un test pendiente no es una defensa fallida ni un vencimiento adverso.

La regla40 ya existente sobre signo dealer debe aplicarse también al comprobar
fundamentos heredados: un componente no se sostiene actualmente por un signo de
inventario no identificado. No es una orden de repuntuar toda la cartera ni de
reescribir antecedentes fechados; APP18 ya muestra que retirar una atribución
causal errónea puede conservar rangos/notas cuando queda fundamento suficiente.

Esta aclaración debe integrarse con las reglas existentes, no añadirse como un
overlay contradictorio. No es una nueva fórmula ni autoriza modificar informes
históricos sólo por cambiar la redacción de instrucciones. La definición exacta
de Confluencia requiere acordar si se quiere independencia de familias, diversidad
de transformaciones/horizontes o una combinación explícita: son conceptos distintos.

Antes de activar un cambio de criterio, verificaría fuera de producción:

1. Duplicar una señal de precio o copiar un wall entre listas no añade familia.
   Añadir otro horizonte puede mejorar Estructura si aporta algo real.
2. Vencer contratos manteniendo un gap válido y opciones posteriores no dispara
   descuentos automáticos en todos los apartados. COIN/IONQ son controles positivos
   ya observados; un soporte exclusivamente transitorio es el control contrario.
3. Historia pendiente, descarga fallida, ausencia de tests y defensas observadas
   fallidas conservan estados distintos. Un nodo disponible sigue puntuándose
   aunque la reacción sea unavailable. No se fabrican defensas ni puntos medios.
4. Un soporte nuevo con una reacción y un soporte histórico con pruebas adversas
   no reciben el mismo relato sólo porque ambos sumen Volumen 0.
5. Una referencia real con precio/actividad/opciones distintos puede aportar
   confluencia; compartir materia prima no obliga a ignorar todas las escalas.
6. Retains conservan rangos/notas/fechas/ITV y fuentes. Cambios de criterio no
   constituyen por sí solos error anterior ni cambio de respaldo.

Estos son casos de aceptación semántica para revisión, no clasificadores de texto
ni nuevas pruebas unitarias que pretendan validar un juicio financiero. La
corrección de documentación puede revisarse estáticamente; el efecto del modelo
debe observarse en trabajo natural o en un experimento autorizado por separado.
Reducir pesos, eliminar Confluencia o permitir puntos anticipados por reacciones
no maduras exige otra comparación registrada con horizonte/objetivo/episodios,
datos de época y resultados adversos, no sólo conteos de visibles.

Los 46 tickers y sus dos casillas no son 70 observaciones independientes. Comparten
fecha/régimen y muchos juicios vienen de días anteriores. La evidencia permite
diagnosticar reglas, cálculos y algunas incoherencias; no estimar alpha ni probar
que una suma alternativa produciría mejores compras.
