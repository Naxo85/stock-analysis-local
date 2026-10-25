# M02 — Control local de visitas a una sesión por distancia

Se ejecutó m02_distance_control.py sobre candidate_outcomes.json y candidate_comparison.json existentes. Sin nuevas etiquetas/precios, descargas, modelos ni cambios del sistema. Diseño guardado antes de calcular estos controles en m02_distance_control_design.json: intervalos porcentuales [0,2), [2,5), [5,10), [10,infinito); emparejamiento principal dentro del mismo ticker y fecha con diferencia máxima de 1 punto porcentual, sin reemplazo. Los agregados previos 19/45 ya eran conocidos: es un control exploratorio, no una confirmación preinscrita independiente. No se cambiaron bins ni tolerancia tras ver estos resultados.

El algoritmo retira primero niveles idénticos (redondeo a 6 decimales, igual al inventario original). Entre candidatos sustituidos maximiza número de parejas y luego minimiza diferencia total de distancia; desempate determinista. No consulta touched. Se comprueba que invertir todos los resultados conserva las asignaciones en los 38 contextos, además de negativos de tolerancia y un caso donde emparejar codiciosamente perdería una pareja.

## Capacidad, solapamiento y rango

38 contextos, fechas de decisión 13 y 14 octubre; 32 contextos con 3 candidatos,2 con 2 y4 con 1, en ambos brazos: 104 por brazo. Dos contextos TLN mantienen la lista completa. 57 niveles son idénticos en ambos brazos, con 15 visitas en cada uno; no son evidencia incremental. Quedan 47 sustituidos por brazo: 4 visitas baseline y 30 alternativas. La suma reproduce19/45.

Son coordenadas puntuales de ancho cero, con visita low<=nivel<=high en la siguiente sesión completa. No son rangos financieros, ejecuciones ni retornos. Mantener ticker/fecha fija también mantiene precio de referencia, ATR y barra futura; se informa diferencia residual en ATR. No se igualan estructura/familia o hipótesis financiera: precisamente son alternativas diferentes.

## Resultado del emparejamiento principal

Sólo 1 de 47 candidatos sustituidos por brazo consigue pareja; 46 quedan explícitamente sin comparación. APP 13-Oct: 266,84 frente a 269,41, distancias 1,747% y0,801%; diferencia 0,946 puntos porcentuales/0,206 ATR. Ambos niveles se visitan 14-Oct. Resultado emparejado1/1 frente1/1, diferencia 0, sin inferencia de equivalencia ni intervalo de confianza. No se amplió la tolerancia para fabricar una muestra mayor.

El conjunto compartido 57/57 tiene el mismo resultado por definición. Mezclarlo con ese único par daría 58 parejas dominadas por identidad, y no una prueba sobre 47 sustituciones.

## Estratos fijos: visitas/candidatos

| Distancia | Todos baseline | Todos alternativa | Sustituidos baseline | Sustituidos alternativa |
|---|---:|---:|---:|---:|
| 0 a menos de 2% |1/1|11/17|1/1|11/17|
| 2 a menos de 5% |0/0|11/15|0/0|11/15|
| 5 a menos de 10% |18/53|23/54|3/11|8/12|
| 10% o más |0/50|0/18|0/35|0/3|

0/0 significa sin comparador, no tasa cero. Los pools por distancia no igualan ticker/fecha; no deben venderse como efecto controlado. Incluso 5–10% conserva distancias distintas en sustituidos: medianas 7,53% y5,71%.

Como segundo descriptivo predefinido, se comparan celdas ticker/fecha/bin que contengan ambos brazos, con peso igual al menor número de candidatos. En todos los candidatos hay 40 celdas comunes (peso 61), tasas estandarizadas 25,14%/26,23% y diferencia+1,09 puntos porcentuales. Gran parte de esa comparación son los 57 niveles compartidos; la diferencia media absoluta de distancias dentro de celdas sigue siendo 1,90 puntos.

Al retirar idénticos quedan sólo 4 celdas comunes, peso 4:25%/25%, diferencia 0. Tres celdas pertenecen al intervalo amplio>=10% y tienen ambos resultados negativos; sus distancias no son cercanas. Diferencia media absoluta de distancia de las cuatro celdas: 12,10 puntos. Por tanto esta estandarización gruesa TAMPOCO elimina el confusor. Se conservan estos resultados negativos y las 75 celdas con un solo brazo; no se rediseña el bin final buscando otro resultado.

## Qué queda establecido y qué no

La comparación original tiene capacidad igual, pero escaso solapamiento en distancia entre los candidatos que realmente cambia. El resultado es falta de comparabilidad suficiente, no demostración de que proximidad explique causalmente toda la diferencia ni de que los pivotes no aporten nada. No hay base para adoptar ranking o optimizar el filtro del 5% con este archivo.

Sólo hay dos fechas compartidas, activos/episodios dependientes, selección condicionada al archivo y ninguna trayectoria después del contacto de una sesión. No existen aquí etiquetas comparables 3/5/10/20. No se amplían los resultados a candidatos sin pareja ni se convierte mayor visita en mejor compra. Un futuro contraste requiere candidatos comparables por distancia/escala con ventanas posteriores y más fechas independientes; no se inventan ahora esos datos.

Reproducción: .venv\Scripts\python.exe -B .tmp\audit_execution_20261017\m02_distance_control.py. Diseño, hashes de inputs, resultados íntegros, parejas, candidatos sin pareja y celdas se conservan en m02_distance_control_results.json. Las comprobaciones de integridad y emparejamiento pasaron; los dos archivos fuente se verifican sin cambios antes/después.
