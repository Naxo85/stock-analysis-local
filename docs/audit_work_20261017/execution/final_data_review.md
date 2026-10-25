# Revisión final independiente de datos — 17-10-2026

Solo lectura y comprobaciones locales; único entregable nuevo: esta nota. HEAD sigue en 8034b7afb20c5a3fbe151d36429fe608160b3c16. Sin commit, red, modelo, escalación ni edición canónica. Se contrastaron informe original, anexos de datos/metodología, matriz de ejecución, código vigente y resultados guardados.

## Resultado y precisiones necesarias

No se encontró una nueva regresión material de H01/H02/H07–H10. Los hashes actuales de los fuentes de datos coinciden con data_test_results.json (121 pruebas y 5 subtests); los de calendario/price_path coinciden con la ejecución posterior de 80 pruebas. Las suites se solapan: NO sumarlas como 201 pruebas distintas. No se repitieron sin cambios que lo justificasen.

La terminación IBKR distingue vacío completo, timeout/error y hasMore. raw/slim separan sesión completa, unidad, OI desconocido, elegibilidad gamma y procedencia de quote. La revisión adicional del wrapper está hecha: analyst_recent_actions.py conserva provider_fetched_at/coverage y adaptive_stage.py:260–268 los exige en40 y comprueba la fecha del proveedor. Los negativos del wrapper están en tests/test_publication_consumers.py. No afirmar que el contenido informativo sea exhaustivo o verdadero por pasar esos controles.

Precisiones para el cierre documental:

1. **Trayectoria:** comparison_extensions.json e historical_path_examples.json actuales contienen 64 detalles/47 extremos adversos anteriores/2 órdenes ambiguos/9 cierres negativos tras excursión favorable. Cuadran con la matriz. Son 54 identidades ticker/coordenada/contacto/fin distintas. El conjunto completo, antes de limitar detalle, suma65 eventos y55 identidades. No confundir estos dos denominadores. methodology_execution_review.md conserva una frase antigua diciendo que esos archivos permanecían con detalle8: quedó desactualizada tras el nuevo replay de raíz. Los agregados actuales conservan todos los contactos; ninguna omisión del detalle se transforma en éxito.
2. **OHLC:** las 51 discrepancias entre copias son9 ticker/fecha únicos, todos de septiembre. No son51 barras independientes ni51 etiquetas de futuro perdidas. El registro y exclusión conservadora son correctos.
3. **Estado C01:** evaluación local ya terminada; la fila «panel en evaluación» debe actualizarse al consolidar. El panel de 98 filas era parcial: el cierre usa todas las 1.938 filas. En data_execution.md se intercambiaron las etiquetas H10 a/H10 b en dos viñetas: H10 a es antigüedad/historia, H10 b selección de quote; implementación y matriz están bien.
4. **M01:** se retiraron los auxiliares engañosos especificados; max pain numérico se conserva, con restricción explícita de no inferir atracción. No describirlo como eliminado ni como señal validada. La comparación ciega de juicio sin priors/max pain no se ha completado con una nueva respuesta de modelo.

## Coherencia de cifras y alcance

- C01: 5.814 filas por familia/vencimiento −294 copias exactas =5.520 observaciones identidad/día;0 conflictos. Son2.630 pseudoidentidades incluyendo registros no observados;2.591 se restringía a contratos observados. OI:5.453 positivos+11 ceros registrados+56 no observados =5.520. Pares:2.873 comparables+17 no comparables =2.890;1.895 aumentos+813 descensos+165 iguales =2.873. Quotes:5.298 positivos ordenados+166 con lado cero =5.464. Los22 agregados gamma con OI0 y OI contractual positivo permanecen separados. Los11 ceros históricos no autentican cero del proveedor; la fecha efectiva de OI y la identidad económica completa faltan.
- M02:58 inventarios con pivotes adicionales,55 listas de precios diferentes; no contradicción.38 pares/104 candidatos por brazo/19 frente a 45 contactos son correctos, pero sólo a 1 sesión y con distancia mediana9,04% frente a 5,80%. No permiten adoptar ranking.
- M03/M04:242 episodios/191 ticker-rango distintos;100 horizontes5 d completos,76 contactos y69 recorridos posteriores, en2 fechas. El horizonte del evaluador parte de decisión; el helper mide cinco sesiones posteriores al cierre de contacto. La ablación de Opciones rho0,778 y fortaleza–MAE rho−0,009 coinciden con JSON; no prueban pesos mejores, inutilidad ni calibración.10/20 sesiones siguen ausentes.
- M05–M08: RS no equivale a serie sectorial alineada; presencia de noticias no equivale a expectativas/materialidad; renderer probado no mide comprensión humana;588 revisiones/710 recibos/35 reparaciones no identifican llamadas evitables. El cierre los trata adecuadamente como límites, sin atribuir alpha.

## Trabajo local útil aún posible, sin ser una regresión bloqueante

- **M02:** control exploratorio de visitas a 1 sesión emparejando distancia/escala en los candidatos ya archivados, deduplicando referencias coincidentes y conservando pares sin comparación. Es ejecutable sin red/modelos; sólo mediría cuánto de 19/45 explica proximidad. No produce trayectorias3/5/10/20 ni justifica adoptar un ranking. Los criterios confirmatorios y horizonte deben fijarse antes de otra muestra.
- **Reproducibilidad prospectiva:** preparar contrato/fixtures de recibo de adquisición para las 252 barras y cadenas completas ya descargadas, con alcance, tiempos y hash, sin cabeceras sensibles. Hoy siguen sin conservarse todos esos datos; un hash no reconstruye los candidatos/contratos perdidos. Preparar y probar ese archivo local es posible; obtener capturas nuevas o activar almacenamiento operativo requeriría el paso externo autorizado correspondiente. No se puede recuperar retrospectivamente lo nunca conservado.

No sustituir las carencias esenciales por más cálculos: faltan varios regímenes/fechas futuras independientes, expectativas fechadas, fecha efectiva de OI, deliverable/ajustes completos, inventario dealer, secuencia intradía y adjudicación humana de materialidad/comprensión. Con los límites declarados, no hay base para cambiar pesos, ITV o convertir EM/OI en probabilidades o flujo firmado. Las correcciones de datos pueden cerrarse localmente; validación predictiva, comparación de modelos y activación externa son estados separados.


Actualización posterior: el control M02 identificado arriba ya se ejecutó, con diseño fijo y resultados completos en m02_distance_control.md/json. Las referencias H10a/H10b, wrapper y detalle64/54 frente a65/55 de mis notas se corrigieron. La conservación prospectiva del recibo de adquisición está asignada a integrity; esta rama no la da por terminada hasta su entrega.
