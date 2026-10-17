# Auditoría de fortaleza y cobertura — 13-10-2026

## Alcance y evidencia original

Comparación de los 46 tickers: último registro correcto del 29-09 en
output/<ticker>/history.json frente a publicación congelada de
logs/batch/2026-10-13/11-06-58/adaptive/<ticker>/publish/output/<ticker>/latest.json.
Se revisaron las explicaciones de las 52 zonas que dejaron de mostrarse, y la
secuencia de referencias intermedias CAT/IBKR/ASML/HIMS desde el 02-10.
No se llamó a modelos ni se regeneraron o republicaron informes.

El último full autorizado terminó 46/46, cero fallidos, a las 11:51:20 UTC.
SOFI publicado a las 11:23:39 UTC. La notificación 45/46 SOFI corresponde a otra
orden de las 09:01, no a este lote. C4 queda fuera del alcance por decisión del usuario.

| Medida | 29-09 | Full13-10 |
|---|---:|---:|
| Entrada >=70 |39|12|
| Washout >=70 |28|3|
| Entrada >=85 |7|0|
| Washout >=85 |3|0|

52 campos antes visibles dejan de serlo: 35 tienen un rango vigente <70,
17 ahora son nulos. Esto NO significa 52 soportes físicos rotos: algunas zonas
cambiaron de función o fueron sustituidas. Los umbrales 70/85/95 y los pesos
25+20+25+15+15 no cambiaron. El bloque numérico conservado del prompt antiguo
coincide con la rúbrica financiera actual. No se modifican para forzar visibilidad.

## Causa técnica demostrada y corregida

El productor descargaba bid/ask y cadenas separadas por vencimiento.
Las cuatro funciones de walls agregaban OI/gamma por strike, elegían un vencimiento
dominante y descartaban las cotizaciones contractuales y contribuciones por fecha.
Slim conservaba el total y esa etiqueta, no el detalle. El consumidor no podía
verificar liquidez contractual ni reparto por vencimiento aunque se hubiesen
descargado. El prompt exigía valorar ambas cosas.

Consecuencia observada: se repite la carencia en CAT, IBKR, ASML, AUR, CCJ, CRDO,
NBIS, TSLA y otros. TSLA declara literalmente que la misma falta limita Opciones
y Durabilidad. Esto demuestra pérdida de observabilidad y riesgo de doble
penalización; NO permite calcular cuántos puntos debe recuperar cada ticker.

Arreglo de datos: option_details viaja desde las cadenas ya descargadas, por
cada wall seleccionado, tanto vía TOP como soportes/resistencias, a slim y catálogo.
Incluye fechas muestreadas, OI/gamma contribuyente y bid/ask/fechas de cada contrato
observado. No nueva descarga, consulta de modelos, score, ranking ni origen ficticio.
Cadenas fuera de muestra o contratos no parseados siguen fuera del alcance.
Un strike no observado no se convierte en cero OI universal. Los contratos
gamma cero quedan observables sin incorporarlos al agregado heredado.
Bid cero, horquilla cruzada, falta de fecha o cotización antigua NO prueban liquidez.

Arreglo de interpretación31, compartido por full/mantenimiento/reparación:
- Vencimiento dominante no equivale a vencimiento exclusivo.
- Nueva cobertura no equivale a nuevo respaldo ni falta de dato a deterioro.
- No penalizar automáticamente otros componentes por la misma carencia.
- Durabilidad evalúa el conjunto del soporte, incluidas familias independientes;
  riesgo de evento o dependencia real de opciones sí pueden limitarla.
- No regalar puntos ni conservar una nota antigua demostrablemente errónea.
- Sin filtro de prosa, puerta nueva, cuota, recalibración automática o llamada extra.

## Recorrido de los cuatro casos prioritarios

|Caso|Evidencia y conclusión|
|---|---|
|CAT 87→65|No fue una única rebaja sobre soporte intacto. Pasó por otros bloques (810/820) y volvió a 800–804 el 09-10. Hubo confluencias distintas y el put800 actual tiene menor dominio. La opacidad de vencimientos/liquidez afectaba sus explicaciones. No procede restaurar 87 por código.|
|IBKR 89→73|Primera rebaja89→84 explicada por pérdida de coincidencia Donchian/Keltner. Después cambian nodo/historia seleccionada y riesgo de resultados; desde07-10 aparece explícitamente carencia de spread/persistencia. Causa mixta, no evidencia de que todos los16puntos sean pérdida real ni error.|
|ASML79→69|79→78→76→75→69. Varían AVWAP/medias y concentración de opciones; un paso citó AVWAP ausente del slim (omisión no prueba invalidez, ya abordada por observación independiente23). Persisten8/13defensas en datos finales. Resultados cercanos pueden limitar durabilidad; no inferir desaparición del agregado por su etiqueta16-10.|
|HIMS88→80 (85→80 último)|Cambio final apoyado: nodo de volumen diario más cercano29.0408 queda4% del centro; no se omitió un HVN cercano en esa captura. Techo de volumen15 frente18; gamma put28 pasa26.4% a14.8%, opciones20→18. Durabilidad13 se conserva: no doble penalización automática. No hay arreglo demostrado de esa bajada.|

Las estadísticas históricas usan ahora sesiones completas y calibración fechada.
Los recuentos legacy no son comparables automáticamente. No se llama defensa
fallida nueva a un cambio de medición, ni se revierte una corrección aritmética válida.

## 35 campos conservados con puntuación <70

Estas filas identifican TODOS los campos; muchos tienen rangos diferentes.
La última columna distingue el respaldo observado, no certifica cada punto subjetivo.

|Ticker/campo|Antes→ahora|Lectura del original actual|
|---|---|---|
|AMAT entrada|81→61|Zona nueva480; opciones secundarias, nodo3.35%; detalle de expiraciones antes no entregado.|
|AMAT washout|72→62|Zona nueva470; reacción57.1%, distinta de antigua480.|
|APP entrada|81→58|Zona nueva266.3–267.3; una sola defensa, familia mínimo/Donchian duplicable.|
|ASML entrada|79→69|Ver trayectoria prioritaria; mezcla de confluencia/evento/cobertura.|
|ASML washout|84→59|Rango distinto; HVN3.24%, sin media/AVWAP próximo.|
|AUR entrada|71→63|Zona5.5 distinta de5; mantiene juicio09-10, no penaliza nueva recalibración.|
|CAT entrada|87→65|Ver trayectoria; rango final coincide, recorrido intermedio no.|
|CCJ entrada|80→67|Zona85 distinta; nodo3.12% limita volumen15, no supuesta defensa fallida.|
|CIFR entrada|80→62|Zona12 distinta; solo2defensas antiguas sin nodo; cobertura de opciones incompleta.|
|CLS washout|79→51|Zona313 distinta; tasa de defensa33.3%, sin opciones propias.|
|COIN entrada|83→67|Zona170 distinta; nodo4.37%, reacción61.9%; persistencia desconocida.|
|COIN washout|86→62|Zona162 distinta; gap/nodo, opciones165 indirectas.|
|CRDO entrada|82→69|Zona180 distinta; AVWAP/SMA, nodo3.58%, opciones180 secundarias.|
|CRWV entrada|84→69|Zona80 distinta; reacción54.2%, nodo>3%; gamma negativa no prueba ruptura por sí sola.|
|CRWV washout|84→61|Zona75.9 distinta; juicio histórico fechado, no nueva observación del gap.|
|GEV washout|73→67|Zona980 distinta. Components suman67, pero factors dice77: contradicción de autoría de total.|
|INOD entrada|79→63|Zona60 distinta; nodo3.26%, defensa60%; faltaba detalle de opciones.|
|LEU entrada|74→63|Rango distinto;2defensas, sin nodo cercano; no duplicar mínimo anual/Donchian.|
|LRCX entrada|87→67|Zona308 distinta; AVWAP y defensa reciente incierta, no simple quote.|
|LRCX washout|72→69|Zona300 distinta; historial69.2%, sin media/AVWAP coincidente.|
|MU entrada|74→57|ZonaAVWAP963–970 distinta; juicio anterior conservado.|
|MU washout|78→62|Zona914–921 distinta; antecedente fechado, no perfil actual inventado.|
|NBIS entrada|89→63|Zona210 distinta; historial fuerte no acredita defensa actual, falta cobertura contractual.|
|NVDA entrada|78→68|Rango distinto; conserva juicio08–09-10 y no recalibración automática.|
|PLTR entrada|74→61|Zona190 distinta;4/8defensas, menor dominio de opciones.|
|QCOM washout|79→65|Zona165 distinta;9/13defensas pero32sesiones, menos confluencia.|
|RDDT entrada|73→64|Zona150 distinta; conserva juicio07-10, diferencia datos actuales/históricos.|
|RDDT washout|77→69|Zona135 distinta; opciones heredadas no reconfirmadas, no cero por ausenciaTOP.|
|SNDK entrada|76→63|Zona1400 distinta;5/7defensas antiguas, poca base reciente.|
|SNDK washout|79→48|Zona1316 distinta; gap/historia antiguos, sin opciones propias.|
|SPCX washout|81→61|Zona155 distinta;3/7defensas,43%, nodo3.95%.|
|TLN washout|73→67|Zona320 distinta; juicio07-10, gamma3.6%, no nueva pérdida por recalibración.|
|TSLA entrada|82→62|Zona370 distinta; texto limita Opciones/Durabilidad por misma carencia contractual.|
|TSM washout|81→64|Zona420 distinta; reacción42.9%, poco dominio de gamma.|
|WDC entrada|86→58|Zona370 distinta;2defensas antiguas y opciones secundarias.|

## 17 campos retirados: no equivalen todos a soportes rotos

|Ticker/campo|Motivo observado en informe actual|
|---|---|
|ASTS entrada/washout|Antiguos bloques perdidos; mínimos inferiores sin respaldo suficiente.|
|CAT washout|Alternativas inferiores evaluadas; no segundo bloque convincente. No declarar roto todo el histórico.|
|CIFR washout|11.72 y12 pertenecen al mismo bloque operativo, no dos compras.|
|CRDO washout|180 promovido al bloque principal; nodo inferior aislado y suelo remoto no bastan.|
|HOOD washout|Alternativas con reacción floja; nueva alcanzabilidad no acredita mejora de decisión.|
|IREN entrada/washout|Antiguos bloques perdieron función compradora; opciones inferiores/historia antigua no bastan.|
|MP entrada|Secuencia gap/caída mantiene pérdida de antiguos bloques; alternativa sin defensa suficiente.|
|OKLO entrada|Zona32 con trayectoria vendedora, sin base defendida; no falso reclaim.|
|ORCL washout|133 mismo bloque principal;130 con1/3defensas antiguas.|
|PLTR washout|173.3–174 fuera del horizonte operativo; retirada NO afirma ruptura física.|
|QBTS entrada|14–15 sin función compradora actual;13.5 poco respaldo.|
|RKLB washout|Alternativas sin bloque independiente suficientemente defendible; no por ausencia de stop.|
|SOFI washout|Promovido a entrada principal: no se destruyó ese soporte ni debe duplicarse.|
|USAR entrada|Antiguos bloques perdidos;12 sin defensa suficiente en secuencia reciente.|
|WDC washout|Alternativas del mismo bloque o sin defensas; no obligar a rellenar.|

Los motivos son rastreables y distintos de una regla mecánica por cotización.
No hay base para restituir las17 zonas automáticamente ni para atribuir las52
pérdidas visibles solo a un endurecimiento nuevo de la rúbrica.

## GEV: fuente única del total

Original report.response: E17+V17+O12+C11+D10=67. Su factors decía77, sólido.
La proyección/Sheet67 es correcta; el error está en repetir un total libremente
en texto. Instrucción31 reserva total/categoría al renderer y pide solo fundamentos
en factors. No se analiza puntuación gramatical, no se falla ticker por estilo,
no se toca la publicación original. No afirmar que una instrucción garantiza
obediencia futura del modelo: observar la próxima generación natural.

## Verificación y límites

Activado31 solo para nuevas preparaciones. Raw/slim options31-20261013,
Ready y100% tráfico verificados; runtime preservado. Registros deploy_options31.
114tests y79subtests correctos. No captura técnica real ni modelos de prueba;
la observación financiera en producción corresponde al siguiente lote natural.

test_strength_evidence_v31.py compara las cuatro funciones originales desplegadas
con las nuevas: mismos agregados, ranking, clusters, fechas dominantes y número
de llamadas. Flujo completo con red simulada mantiene precios, rutas y contenido
anterior, excluyendo únicamente datos aditivos y reloj de captura. Comprueba
raw→slim→catálogo, quotes ausentes/cruzadas/cero y expiraciones no observadas.
Las46respuestas originales vuelven a validarse conservando rangos y fortalezas.
Contratos29/30 permanecen idénticos;31 compartido por ambos roles y reparación.
AST del despliegue verifica que únicamente se agrega evidencia, no algoritmos
financieros, configuración runtime o red nueva.

Esto corrige una causa de datos y su interpretación, no predice las notas que
emitirá el siguiente modelo. No objetivo de recuperar las10zonas fuertes ni
promesa de cero fallos. No modelos de prueba, lote duplicado o edición de informes.
