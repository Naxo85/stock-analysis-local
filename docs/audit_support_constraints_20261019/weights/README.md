# Peso de opciones y caída de visibilidad — investigación del 19-10-2026

## Decisión recomendada

No cambiar ahora el peso 25 de Opciones, ni redistribuir puntos para recuperar un número de casillas. El peso produce una dependencia importante, pero los datos examinados no identifican un peso alternativo mejor. Corregir primero la incorporación de evidencia y las carencias de descubrimiento que puedan demostrarse; luego evaluar el valor incremental de Opciones con datos por fecha y episodio.

La nota es una rúbrica ordinal de respaldo observado, no probabilidad calibrada de rebote. Un punto de corte visual no demuestra un mínimo económico rentable. Cambiar el denominador de la nota o el peso exige revisar también el significado de 65/70: mantener el mismo número no preserva su significado.

## Censo reproducible

`census.py` sólo lee originales y escribe `census.json` en esta carpeta. Se ejecuta desde el repositorio con `.venv\Scripts\python.exe docs\audit_support_constraints_20261019\weights\census.py`. El resultado conserva hashes de cada archivo leído y todas las zonas, incluidos ceros, rangos eliminados y componentes heredados. No ejecuta adquisición, modelos, análisis nuevos ni publicación.

| Lote | Informes publicados | Zonas | Tickers con zona | ≥65 | ≥70 | Opciones=0 | Volumen=0 |
|---|---:|---:|---:|---:|---:|---:|---:|
|13Oct19:30|46|67|38|30|18|6|2|
|14Oct16:07|46|66|37|24|13|8|1|
|15Oct12:01|46|64|38|17|8|17|2|
|16Oct15:58|45|71|45|14|5|25|10|
|18Oct09:08|46|70|45|9|3|23|11|

16Oct contiene45 publicaciones, no un falso46/46; APP falló. La comparación referencia→18 utiliza los46 antecedentes exactos del input18, incluido el último válido de APP, y por ello parte de72 zonas. El resto de tablas conserva el universo de publicaciones de cada lote.

Entre14 y18 la media total baja62,59→53,89. Opciones12,89→9,07, Volumen12,71→10,01 y Confluencia9,76→7,51 explican aritméticamente la diferencia agregada; **no prueban una penalización nueva ni repetida del mismo soporte**. La selección38 admite más zonas débiles: los tickers con alguna zona pasan37→45. Además cambia el mercado y cambian los rangos.

### Separación entre mismas zonas y cambio de composición

La identidad usada aquí es ticker+rango numérico exacto, independientemente de Entry/Washout. No se afirma que cada diferencia numérica sea una estructura económica nueva.

-14→18:24 rangos coinciden;19 mantienen los cinco componentes exactos. Los otros cinco suman−2 puntos de Volumen y−8 de Opciones, cero cambio neto en Estructura/Confluencia/Durabilidad. Entre los coincidentes hay8 visibles antes y6 después. Del conjunto de rangos exactos salen16 visibles y entran3:24−2−16+3=9. La mayor parte de la disminución visible pertenece a cambios de composición, no a repuntuar hacia abajo todos los apoyos conservados.
-Referencia inmediata→18:62 rangos coinciden,58 con los cinco componentes exactos. Los cuatro repuntajes cambian Opciones en−16 puntos agregados y Durabilidad+1. Visibilidad coincidente11→9; salen3 visibles y ningún rango nuevo alcanza65. Cinco promociones de Washout conservan sus componentes. No aparece un descuento automático de expiración en todos los pilares.

`transitions.py` localiza el recibo en que desaparece cada uno de los16 rangos visibles14 que ya no están18, y conserva razones/comparaciones en `visible14_removed_trace.json`. Hay16 trazas localizadas. Incluyen recuperaciones fallidas y promoción de apoyos inferiores; RKLB y TSM pasan por revisión fundamental además de técnica. Estas son las razones originales del modelo, no una nueva certificación de cada retirada. Algunas razones antiguas (CLS/MRVL) incluían el signo gamma como refuerzo, interpretación retirada en40: no se usan como causalidad demostrada. La muestra no permite repartir de manera causal toda la caída entre mercado, selección, mejora de cobertura y política.

### Dependencia de opciones que sí está demostrada

En18Oct,23/70 zonas tienen Opciones0. Ninguna llega65; su máximo es60. Su Estructura media19,39 y Durabilidad10,78 son mayores que en las47 con Opciones positivas (16,85 y9,02), mientras Volumen es parecido (9,96 y10,04). Confluencia también es menor (5,43 frente8,53). Son grupos seleccionados y dependientes, no evidencia causal de que las zonas sin opciones sean mejores o peores.

Sin Opciones, alcanzar65 exige65/75 de los componentes restantes:86,7% de su máximo. Las11 zonas con Volumen0 tampoco llegan65. Cuatro tienen ambos componentes0; incluso el máximo teórico restante es55. Esto describe el diseño de evidencia, no demuestra error aritmético. “No acreditado”, “no observado en la muestra”, “dato ausente”, “respaldo realmente pobre” y “nota heredada” pueden desembocar en el mismo cero y deben distinguirse antes de rediseñar pesos.

Dos sensibilidades puramente aritméticas ilustran por qué “quitar peso a opciones” no es una corrección determinada: restar Opciones y dejar65 produce0 visibles; quitar ese componente y reescalar los75 restantes a100 produce28. Ninguna alternativa ha sido evaluada contra desenlaces y ambas cambian el significado de la nota. No son recomendaciones ni backtests.

## Evidencia primaria externa y alcance

Fuentes consultadas el19-10-2026. Se usaron documentación institucional y trabajos de autores/publishers; no opiniones de redes ni proveedores de señales.

1. [OCC/OIC: General Information](https://www.optionseducation.org/referencelibrary/faq/general-information). El interés abierto registra contratos abiertos; por sí solo no indica una expectativa alcista/bajista y tampoco garantiza liquidez. Esto sostiene conservar límites sobre interpretación, signo dealer y calidad de cotización. No establece que toda concentración de opciones sea inútil.
2. [Ni, Pearson y Poteshman, 2005: Stock price clustering on option expiration dates](https://experts.illinois.edu/en/publications/stock-price-clustering-on-option-expiration-dates/), abstract institucional y [texto del publisher](https://www.sciencedirect.com/science/article/pii/S0304405X05000577). Encuentra concentración de cierres cerca de strikes en vencimientos y evidencia compatible con mecanismos de cobertura/manipulación. Su contexto de expiración y posiciones no valida un soporte comprador general ni asignar25 puntos a OI/gamma sin conocer el signo de las posiciones. Es contraevidencia a eliminar opciones como si no pudieran influir en el subyacente.
3. [Pan y Poteshman: The Information of Option Volume for Future Stock Prices](https://www.nber.org/papers/w10925). La evidencia predictiva emplea volumen iniciado por compradores para abrir posiciones. Esa variable no equivale al OI agregado que recibe este sistema. Su resultado no permite importar la señal ni justificar el peso actual.
4. [Novy-Marx: Backtesting Strategies Based on Multiple Signals](https://www.nber.org/papers/w21329). Combinar y seleccionar señales puede generar sobreajuste considerable. Apoya registrar variantes y evaluar cronológicamente, no ajustar pesos hasta que salgan más casillas.

Ninguna fuente consultada calibra nuestra rúbrica, su umbral65, sus rangos o su horizonte. Tampoco se infiere de esa ausencia que25 sea necesariamente incorrecto.

## Cambio concreto que evaluaría después de corregir los datos

Comparar la rúbrica vigente con una sola alternativa preespecificada que trate opciones como información contextual separada. Mantener candidatos, fecha, universo y juicio de viabilidad iguales en el contraste; no confundir ausencia de cobertura con señal adversa. El objetivo sería medir si opciones mejora el ordenamiento de respuesta/adversidad posterior, condicionado a distancia, estructura, vencimiento y cobertura, y si la separación mejora la comprensión del lector. Los episodios repetidos y las dos zonas del mismo ticker no son observaciones independientes.

El corpus actual sirve para verificar procedencia y lógica. No hay suficientes fechas independientes ni horizontes futuros para estimar pesos óptimos. Cambiar un defecto verificable de representación puede justificarse sin esperar rentabilidad; cambiar un peso predictivo requiere otro tipo de evidencia. Los criterios completos de evaluación ya están en `docs/audit_work_20261017/methodology_evaluation.md` y `docs/execution_audit_20261017.md`.
