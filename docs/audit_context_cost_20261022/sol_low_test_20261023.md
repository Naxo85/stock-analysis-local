# Piloto Sol6.1 low — 23 de octubre

Ampliación autorizada posterior: `sol_medium_comparison_20261023.md` ejecuta
medium sobre los tres mismos inputs y obtiene las mismas decisiones. El
contraste pendiente descrito abajo ya tiene esa observación; los updates
financieros siguen sin ejercitarse. No se activó ningún modelo.

Se ejecutaron las tres llamadas anunciadas, con gpt-6.1-sol / low y autenticación
ChatGPT Plus existente. Sin API key, web, reparación, full, recuperación ni
publicación. La configuración diaria sigue Luna high; no se activó Sol low.

Artefactos: `logs/sol_low_test/20261023T160954879936`. Ejecutor reproducible:
`run_sol_low_test.py`; agregación: `summarize_sol_low_test.py`.

## Diseño y resultados

Fuentes congeladas del lote23Oct para AMD, CLS e IREN, que no habían usado web en
la llamada original. Se mantuvo la política financiera congelada, incluida la
ausencia de la guía posterior selected-sources-v1, para no atribuir su efecto al
modelo. Se deshabilitaron herramientas y se añadió una aclaración de evaluación
con cronología congelada. No se comparó con Sol medium sobre estos mismos inputs.

| Caso | Luna high original | Sol6.1 low | Comprobación realizada |
|---|---|---|---|
| AMD | Update; reparación y posterior fallback a full | Escalate por pérdida estructural con posición registrada | Recibo/input binding y ruta aceptados; sin update financiero |
| CLS | Update; reparación fallida por Volumen | Escalate por pérdida estructural con posición registrada | Recibo/input binding y ruta aceptados; sin update financiero |
| IREN | Update publicado en el lote original | Retain, compras ausentes y espera | Recibo/input binding, ruta y cobertura aprobados |

Tres respuestas terminaron sin errores de los controles ejercitados. Esto NO
equivale a tres informes completos aprobados ni a tres updates válidos. Ninguna
respuesta propuso update: no se ejercitaron aritmética de Volumen, cambios de
rangos/puntuaciones, mantenimiento de textos ni reparación. Las peticiones de
Sol high quedaron registradas; no se ejecutaron.

Revisión manual: las tres posiciones registradas son true; el OHLC del22 y los
precios actuales citados concuerdan con la captura congelada. AMD abrió524,095,
máximo529,98, mínimo502,6 y cierre507,93; CLS abrió289,69, mínimo267,645 y
cierre269,01. Su clasificación de riesgo es explícita, basada en la trayectoria
y no en un error de formato. No hay un comparador independiente que demuestre
si esa clasificación es preferible a una retirada rutinaria de compras.
IREN mantiene el plan sin compras, diferencia datos históricos de actualidad y
discute candidatos inferiores sin inventar una compra. No se observó un fallo
concreto en esa retención; no valida por sí sola todos los juicios económicos.

## Consumo medido

| Concepto | Tres Sol low | Tres Luna high originales, sin reparaciones |
|---|---:|---:|
| Entrada total | 413.832 | 421.702 |
| Entrada en caché | 0 | 32.768 |
| Salida, razonamiento incluido | 3.609 | 20.465 |
| Razonamiento, subconjunto de salida | 219 | 14.609 |

La salida menor refleja también dos escaladas y una retención en vez de redactar
tres updates; no mide sólo el efecto de bajar esfuerzo ni compara con medium.
La entrada grande permanece. En producción, dos de estas decisiones pedirían
un full adicional a la llamada de revisión; aquí no se compró ninguno.

El contador semanal compartido pasó32→35% usado durante la prueba. Redondeo,
latencia y actividad concurrente de la cuenta/conversación impiden atribuir esos
tres puntos exclusivamente a las tres llamadas. Es un dato observado, no una
estimación de cuota por lote ni una demostración de ahorro semanal.

19archivos originales/configuración diarios verificados sin cambios. No se
reutilizarán estos recibos de evaluación para publicar o recuperar el lote.

## Decisión

No activar low a partir de esta muestra. Su capacidad para ejecutar las
actualizaciones que fallaron con Luna queda sin probar; el ahorro total tampoco
queda establecido con dos escaladas. Para comparar low y medium hace falta un
contraste controlado sobre los mismos inputs y casos que ejerzan updates,
sin ejecutar automáticamente los full que soliciten. No se autoriza ni ejecuta
ese contraste adicional mediante esta nota.

Referencia de nomenclatura Light/low y controles de razonamiento:
[OpenAI Docs](https://learn.chatgpt.com/docs/models?surface=web).
