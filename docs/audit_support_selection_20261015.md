# Seleccion de soportes: existencia no equivale a fortaleza

## Evidencia original

Lote 2026-10-14/16-07-07, orden
20261014-160514-market-full36-c7070c8c, 46/46 publicados. Se inspeccionaron los
input.json, report.response y publish/output/<ticker>/latest.json originales.
El progreso remoto coincidia con este ultimo lote terminado en la consulta del15.
No son cotizaciones actuales del15 ni una nueva recomendacion de compra.

66 zonas seleccionadas,53 por debajo de70;26 casillas ausentes.9 tickers sin
ninguna compra,8 con solo Entrada y29 con las dos. El renderer no oculta por
fortaleza dentro del informe: range=null producia el literal Sin zona verificable.
El umbral independiente de visibilidad en Sheet no origina estos null financieros.

| Ticker | Evidencia suministrada el14 | Evaluacion del descarte original |
| --- | --- | --- |
| ASTS | Minimo42.32 creado ese dia, sin tests historicos completados; put40 sin reaccion medida y sin volumen proximo. | Dejar vacio es defendible con esa evidencia; un minimo movil no acredita por si solo un origen comprador. No imponer un rebote reciente a otro origen objetivamente respaldado. |
| CIFR | Minimo10.03 del mismo dia; lista supports sin segundo origen independiente. | No hay que fabricar Entrada ni Washout por completitud. Las opciones inmediatas sin respaldo suficiente no obligan a comprar. |
| IREN | Origen inferior28.93 del29-jul, una defensa historica medida; cotizacion31.245. Su recencia/confluencia limitadas motivaron el descarte. | Es un candidato real, no inexistencia de soporte. Una sola defensa/ausencia de rebote reciente no lo vetan automaticamente. Debe evaluarse y puntuarse antes de decidir; no se fuerza su seleccion offline. |
| LEU | Gap y continuacion vendedora; minimo122.56 del dia14 sin reaccion completada. | Ausencia compatible con perdida del papel previo y falta de otro origen suficientemente respaldado; no diagnosticar soporte nuevo solo por sobreventa. |
| MP | Origen37.81 del29-jul con una defensa medida; cotizacion39.72. Put40 con respaldo de vencimientos desiguales. | La escasa repeticion/volumen no prueban inexistencia. Evaluar el origen inferior tambien como posible Entrada, no solo como una segunda compra que necesite otra previa. Riesgo y vigencia siguen siendo juicio financiero. |
| OKLO | Minimo29.25 del dia14; opciones29 del mismo entorno, sin segunda estructura acreditada. | No forzar dos rangos del mismo bloque ni confundir primer extremo en curso con soporte demostrado. No nuevo veto general por primer contacto. |
| QBTS | Minimo12.30 del dia14, reacciones historicas no disponibles; opciones inferiores sin origen independiente suficiente. | Vacio defendible segun el respaldo observado, no por nota minima. Datos no disponibles no se convierten en defensas fallidas. |
| SOFI | Minimos descendentes y perdida de la zona anterior; nuevo extremo14.12 del dia14, put14 sin reaccion completa. | No conservar soporte perdido ni duplicar el mismo bloque como Washout. Rechazo no puede reducirse a que la sesion siga abierta. |
| USAR | Extremo10.39 del dia14 en primer test, sin otro soporte inferior identificado. | No llenar con el minimo que se desplaza. Una ausencia legitima sigue permitida sin Sol adicional. |

La evidencia distingue escenarios; no prueba que todos los descartes originales
fueran optimos ni permite decidir una compra mediante reglas offline. Los nueve
recibos quedan intactos, sin precios ni puntuaciones corregidos manualmente.

## Causa en las instrucciones

El financiero v11 decia que Entrada no podia ser una zona aceptable/de compromiso
y debia combinar soporte, opciones, estructura, narrativa y asimetria. Otra frase
permitia expresamente zonas moderadas/debiles. Esa tension mezcla calidad con
admisibilidad y favorece exigir una compra ya confirmada en vez de puntuar el
mejor soporte disponible. El literal para cualquier null afirmaba inexistencia
verificable, aunque los motivos reconocieran referencias historicas descartadas.

## Correccion38

- v12 sustituye esas frases, compartido full/medium/repair. Separa origen,
  vigencia, fortaleza y seleccion; poca confluencia, una defensa o ausencia de
  rebote reciente no son vetos por si solos para un origen inferior verificable.
- Las familias aportan a la rubrica; no se exigen todas conjuntamente. No se
  modifica la formula ni los pilares70/85/95, las ventanas de alcance, las reglas
  de opciones de vencimiento inmediato o la evaluacion de riesgo.
- Evaluar los candidatos antes de asignar casillas: uno inferior apto puede ser
  Entrada. Washout necesita otro bloque inferior distinto y adecuado; no cuota.
- Sobre cotizacion sigue haciendo falta juicio positivo de vigencia actual.
  No basta que no exista una ruptura demostrada. No rescatar soporte perdido ni
  convertir coordenadas/minimos moviles/strikes aislados en compras por sistema.
- Null conserva motivo concreto: no se identifica origen comprador, o hay
  referencias no seleccionadas por limitacion especifica. Sin clasificador de
  prosa, enum adicional, rechazo editorial, llamada extra ni nueva ruta Sol.
- Reader>=38 dice Sin zona de compra seleccionada y mantiene el motivo, sin
  inferir automaticamente su clase. En retain puede migrar el encabezado sin
  cambiar null, numeros, motivos protegidos, notas, fechas, ancla ni ITV.
- Las ausencias previas tambien se evaluan en la misma llamada. Null heredado
  no demuestra falta de candidatos; si sigue justificado se conserva exacto.
- No se fuerzan cambios en los9 ni en las66 zonas seleccionadas. Las decisiones
  nuevas exigen el change_review normal, respaldo actual y autoridad vigentes.
  Cambiar instrucciones no demuestra por si solo prior_error de cada informe.
- Preparaciones<=37 congeladas mantienen instrucciones, schemas y renderer
  original; nuevas usan38, financiero v12 y extension inferior37 sin cambios.

## Verificacion y limite

Pruebas offline sobre los9 escenarios originales,46 proyecciones/66 zonas,
compatibilidad de recibos full ausentes/moderados, origen/fuentes, riesgo,
migracion retain, preparacion versionada y pipeline de una sola llamada simulada.
No modelo, lote duplicado, recovery, publicacion o despliegue cloud para probar.
La calidad de las nuevas selecciones se observara en el proximo run natural;
no se predice cuantos vacios deben desaparecer.

Resultado:76 regresiones y16 nuevos casos verificados,12subtests;23focalizados
repetidos pasan al cierre, mas3controles de ancla. Las3primeras fixtures de
migracion usaban el ancla de entrada anterior al full, no su nueva epoca; se
corrigieron sin cambiar codigo de integridad y se confirma rechazo del ancla
vieja. El consumidor conserva exactamente los registros de Sheet al cambiar el
encabezado de ausencia. V11 congelado sin cambios (SHA256 normalizado UTF8
ede70fefce43775712bf9b20682963040dd2a935c30f55cff7b884da43d4ef0f).
Config38 activa; modelos/esfuerzos/ITV/concurrencia intactos. No prueba de modelo
real para38 ni garantia de que cualquier zona debil deba seleccionarse.
