# Ampliación metodológica: evaluación y utilidad de la decisión

Fecha: 17-10-2026. Anexo de investigación del [informe](../audit_analysis_system_20261017.md). Nada de lo propuesto aquí está implementado. No se ejecutaron backtests externos, modelos, análisis financieros nuevos ni operaciones. La comprobación local es descriptiva.

## Pregunta que debe responder la evaluación

La tarea vigente selecciona compras long-only en soportes y vigila riesgo empresarial. No define una estrategia completa de tamaño, ejecución y salida. Por ello hay tres evaluaciones diferentes:

1. **Calidad del análisis:** datos correctos, fuente pertinente, riesgo material detectado, juicio ex ante defendible, incertidumbre explícita y actualización oportuna.
2. **Utilidad de la zona:** oportunidad de alcanzarla, reacción posterior, recorrido adverso/favorable, persistencia y riesgo de evento, siempre respecto de referencias comparables.
3. **Rentabilidad ejecutable:** exige acordar órdenes, fills, tamaño, salida, costes y restricciones. No se puede inferir de las dos anteriores ni de un máximo posterior.

Esta separación es una propuesta de diseño de evaluación, no una regla nueva de compra. Tampoco se demuestra que un análisis sea útil solo porque sus explicaciones resulten convincentes.

## Evidencia primaria sobre cómo evaluar

| Fuente examinada | Resultado pertinente y límite |
|---|---|
| [Sullivan, Timmermann y White, 1998/1999](https://eprints.lse.ac.uk/119144/1/dp303.pdf), texto completo, pp. 3 y 30 | Casi 8.000 reglas sobre DJIA 1897–1996, con corrección por búsqueda. Hay resultados históricos favorables, pero no se repiten de forma convincente en 1987–1996; también estudian futuros S&P. No concluye que cualquier soporte actual sea inútil. Exige comparar contra todo el conjunto de alternativas investigadas. |
| [Harvey, Liu y Zhu, 2014/2016](https://www.nber.org/papers/w20592), abstract oficial indexado; acceso directo devolvió 403 | La investigación de cientos de factores hace inadecuada la significación habitual sin corrección por múltiples pruebas. Su umbral estimado pertenece a ese estudio de factores; no se importa como criterio universal para este sistema. |
| [Bailey, Borwein, López de Prado y Zhu, The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf), texto completo, pp. 5–7 | La selección entre muchos backtests y el conocimiento del supuesto holdout pueden sobreajustar. Propone medir ese riesgo. Ni su procedimiento ni un holdout garantizan estabilidad futura; aquí interesa conservar el registro de ensayos y separar tiempos, no añadir otra nota de calidad automática. |
| [McLean y Pontiff, 2015/2016](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365), abstract del publisher | Estudia 97 predictores transversales: sus retornos disminuyen fuera de muestra y después de publicarse. Son carteras de predictores, no las zonas actuales. Motiva revisar transporte temporal y costes, sin asumir que una regla publicada conserva su ventaja. |
| [Gneiting y Raftery, 2007](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf), texto completo, §3.1 | Las reglas propias, como Brier para eventos, permiten evaluar pronósticos probabilísticos con incentivos coherentes. No convierten una nota ordinal en probabilidad: primero deben definirse evento, horizonte y pronóstico. |
| [Novy-Marx y Velikov, 2014/2016](https://www.nber.org/papers/w20721), abstract oficial indexado; texto directo no accesible | Compara anomalías después de costes y formas de mitigarlos; distingue mantener de entrar como mecanismo de reducción de rotación. No valida la regla exacta de continuidad actual, pero ofrece fundamento para medir cambios innecesarios y costes, además de la calidad aislada de una nueva señal. |
| [Novy-Marx, 2015](https://www.nber.org/papers/w21329), referencia/abstract oficial indexados | Combinar señales añade otra dimensión a la búsqueda de estrategias. La implicación para esta auditoría es registrar también pesos, interacciones y filtros ensayados; no tratar una combinación de indicadores como una sola prueba preespecificada. |

Los abstracts y los textos completos no tienen la misma profundidad de comprobación. Ninguna de estas fuentes valida empíricamente la combinación actual de pesos, opciones, soportes e ITV. Fechas de indexación web no se confundieron con publicación del estudio.

## Comprobación local nueva: precisión nominal y componentes

Se leyeron únicamente los originales del natural 38 del 16-10-2026, 15:58:24: 46 inputs, 45 publicaciones, 71 zonas activas (45 Entry y 26 Washout); APP no tiene publicación nueva. Son zonas correlacionadas y parcialmente heredadas, no 71 operaciones independientes.

El [registro descriptivo](methodology_descriptive_cases.json) conserva rutas, rangos, componentes, fechas y SHA-256 de los 91 archivos. La anchura porcentual es 100 × (upper-lower)/centro. La anchura en ATR divide por el ATR10 del input de revisión; **no** se afirma que sea el ATR utilizado al formar una zona heredada.

- Anchura relativa: mínimo 0,278%, mediana 0,714%, máximo 1,200%.
- Anchura/ATR actual de revisión: mínimo 0,051; mediana 0,113; máximo 0,205.
- Opciones tiene cero en 25 de 71 zonas; por tanto el sistema sí selecciona compras sin ese componente positivo. Eso no demuestra neutralidad del peso en la clasificación o visibilidad.
- MRNA Entry 184,5–185,5 representa 0,051 ATR de revisión; AUR Entry 4,97–5,03 representa 0,205. Son extremos descriptivos, no casos elegidos por rentabilidad posterior.

La estrechez puede ser útil para una alerta u orden concreta. También puede sugerir una precisión de localización que el OHLCV diario y el origen difuso no sostienen. No se demuestra el segundo supuesto con estas cifras. Deben compararse comprensión, contacto real y respuesta posterior, separando **subrango operativo**, **estructura que lo sustenta** e **incertidumbre**.

Puede repetirse con el [programa local](methodology_descriptive_check.py); se guardó su [resultado](methodology_descriptive_check_result.json). No se eliminaron ceros, fallos, valores incómodos ni zonas heredadas para mejorar el resumen. Los componentes son los publicados; no se cambiaron pesos ni recalcularon notas.

## Protocolo común propuesto, todavía sin ejecutar

### Referencias y unidad

- **B0:** decisiones publicadas originales, preservadas con su contrato y limitaciones.
- **B1:** misma metodología y fuentes con las correcciones deterministas de datos previamente aprobadas, cuando existan. Separarla de B0 evita atribuir a una metodología nueva una mejora debida a arreglar un dato. Hoy B1 es una referencia propuesta, no una versión implementada.
- **B2:** referencia sencilla preespecificada, por ejemplo último bloque horizontal confirmado disponible entonces, con el mismo universo y restricciones de información. No optimizar qué referencia sencilla usar después de ver resultados.
- **A:** una sola variación conceptual respecto de B1. Misma hora, universo, candidatos cuando proceda, información disponible y presupuesto. La matriz debe incluir también “sin nuevo indicador” y versiones que eliminan información.

Unidad primaria: **ticker × episodio de decisión**, con subregistros por zona. Una zona heredada durante cinco revisiones no son cinco descubrimientos. Delimitar episodios antes de medir, conservar visitas posteriores dependientes y agrupar inferencia por ticker y fecha/bloque de mercado. Las dos zonas del mismo ticker no son independientes.

### Etiquetas y tiempos

- Congelar t0 como instante en que el lector podía disponer del análisis. Una vela diaria que contiene t0 no permite ordenar máximo, mínimo y publicación; usar sesiones posteriores completas o datos intradía autenticados si se adquirieran para ese fin.
- Evaluar 3, 5, 10 y 20 sesiones como **horizontes experimentales propuestos**, con uno primario predeclarado. No son política actual ni autorización para vender en esas fechas. Si el propósito final elige otro horizonte, debe fijarse antes del ensayo confirmatorio.
- Medir primero visita a la zona y tiempo hasta visita sobre todas las decisiones, incluidas ausencias. Después medir reacción condicionada al contacto; publicar ambos denominadores. Una regla lejana que casi nunca se visita no gana por tener buenos pocos contactos.
- Separar reacción desde el cierre de la primera barra de contacto de reacción desde el nivel. Con OHLC diario no asegurar entrada ejecutada antes del máximo favorable. Informar gaps a través de toda la zona y barras con orden intradía ambiguo.
- MFE/MAE: excursiones favorable/adversa normalizadas por una escala congelada en t0, y retorno a horizonte fijo. No renovar ATR a posteriori para mejorar el resultado. No usar únicamente el máximo de cinco días: omite el daño previo, persistencia y plazo.
- La extensión inferior actual no es un cuantil. Puede medirse penetración, recuperación y fallos por episodio, pero no atribuirle cobertura del 90% sin haber definido y estimado ese pronóstico.
- Para notas ordinales: ordenamiento fuera de muestra, monotonía por grupos y dispersión. Brier/log-loss solo si una variante emite probabilidades explícitas de eventos definidos, con calibración aprendida exclusivamente en entrenamiento.

### Muestra, particiones y sesgos

1. Universo disponible en cada fecha, también excluidos, suspendidos, sin opciones, retirados, sin zona y fallidos. No reconstruir pasado con integrantes actuales.
2. Datos corporativos y de noticias con hora de disponibilidad, versiones conocidas entonces y acciones corporativas verificadas; no la serie o el consenso corregidos hoy.
3. Formación de niveles y anclas solo con observaciones hasta t0. Si se elige el nivel y se cuentan sus reacciones en las mismas 252 barras, eso es descripción in-sample, no prueba predictiva.
4. Particiones cronológicas de desarrollo, validación y confirmación final intacta; la fracción/calendario final se fija tras un estudio de potencia, sin mirar el resultado de la alternativa. Purga de etiquetas que crucen fronteras y separación temporal acorde con el horizonte máximo y dependencia de episodios.
5. Walk-forward en validación, sin retocar la alternativa después de cada fracaso confirmatorio. Reservar también activos/sectores no usados para elegir parámetros cuando se pretenda generalizar.
6. Estratificar por liquidez, volatilidad, tendencia/régimen, eventos y cobertura de opciones. No convertir todos esos estratos en búsquedas de “dónde sí funcionó”: predeclarar pocos contrastes.
7. Registro completo de familias, variantes, parámetros, horizontes y métricas ensayadas, incluidas negativas. Ajustar comparación múltiple a la familia real (Holm para pocas hipótesis confirmatorias; Reality Check/SPA si se compara un conjunto amplio y dependiente). Estos métodos no curan una muestra sesgada.
8. Intervalos con dependencia temporal/transversal; no tratar 46 acciones del mismo día como 46 mercados independientes. Informar tamaño efectivo y potencia. Los pocos lotes actuales sirven para factibilidad y casos, no para fijar pesos fiables.
9. Si se evalúa P&L en una fase posterior, misma ejecución en todos los brazos, spread, comisiones, impacto, slippage, gaps y financiación/divisa pertinentes. No introducir salidas escogidas para favorecer una señal.

### Decisión de adopción

Antes de abrir confirmación: fijar una métrica primaria, el coste tolerable y la mejora mínima relevante. Regla propuesta: adoptar solo si el intervalo de confianza ajustado del beneficio incremental supera esa mejora mínima, no empeora las restricciones de riesgo/observabilidad acordadas y el resultado no depende de un único activo, episodio o parámetro estrecho. Si precisión suficiente excluye la mejora mínima, descartar. Si los intervalos siguen amplios, cobertura insuficiente o resultado heterogéneo sin explicación preespecificada, seguir investigando; no llamar a eso éxito. Ampliar confirmación después de ver resultados exige una regla secuencial previamente fijada; de lo contrario se diseña una nueva confirmación y se conserva el resultado inconcluso anterior.

La mejora mínima no debe inventarse para cerrar esta auditoría: depende de ejecución o tarea del lector aún no acordadas. Ejemplos de unidades apropiadas son reducción de MAE en ATR, errores materiales por 100 análisis, retraso de detección en horas, oportunidades útiles por 100 episodios y coste por revisión. No exige necesariamente rentabilidad ni una nueva llamada de modelo para evaluar un dato.

## Experimentos prioritarios concretos

| Ensayo | Comparación e hipótesis | Métrica primaria / controles | Adoptar, descartar o investigar |
|---|---|---|---|
| E1. Contexto de mercado/sector | B1 vs mismo análisis con paquete compacto fechado; no un veto de tendencia | Error ciego al distinguir caída específica de sistémica y juicio de vigencia/materialidad; retorno relativo y MAE solo como secundarios | Adoptar si reduce errores materiales sin aumentar falsas retiradas/llamadas injustificadas. Descartar si repite lo ya interpretado. Estratos y noticias iguales |
| E2. Candidatos multiescala/evento | B1 vs conjunto alternativo acotado con origen y formación verificables | Cobertura de candidatos aptos omitidos, visita y respuesta a horizonte; referencias emparejadas por distancia/anchura/volatilidad y controles placebo | Adoptar solo ganancia fuera de muestra más allá de ofrecer más oportunidades de escoger. Sin cuota de dos zonas; controlar número de candidatos |
| E3. Reacción dependiente del recorrido | Resumen actual de defensas vs mismas visitas con MAE, cierre, tiempo, posterior mínimo y dependencia | Capacidad de ordenar reacciones futuras o juzgar vigencia, manteniendo reglas de selección/modelo | Conservar detalle si cambia decisiones justificadamente o mejora predicción; retirar campos que no aportan. No sumar nuevas métricas como cinco pilares adicionales |
| E4. Opciones y ablación de la rúbrica | Rúbrica actual vs omitir priors ambiguos; después mapa de concentración sin signo dealer; probar peso solo en fase separada | Valor incremental de opciones condicionado a estructura, régimen, liquidez, vencimiento y horizonte, incluyendo zonas con opciones=0 | Si no hay ganancia estable tras costes/datos, simplificar/reducir función antes de comprar feeds. No redistribuir puntos por defecto ni restaurar notas originales |
| E5. Eventos y sorpresa | E5a: misma evidencia organizada en premisas/esperado/realizado/pendiente. E5b, separado: E5a más evidencia primaria/expectativas congeladas adicionales | Omisiones/falsas afirmaciones, identificación de riesgo de gap, retraso de detección; casos favorables y adversos. Separar ganancia de organización y de dato nuevo | Adoptar E5a si mejora comprensión o exactitud sin omisiones; E5b solo si añade mejora incremental que justifica adquisición. No atribuir PEAD a cualquier noticia positiva |
| E6. Horizonte/anchura/lector | Informe actual vs misma decisión con plazo de evidencia, condición pendiente y distinción entre zona/estimación | Errores “está en verde → comprar ahora”, comprensión de fechas y evento, tiempo para responder tareas | Prueba emparejada y contrabalanceada de casos, sin mostrar dos versiones seguidas al mismo lector. Adoptar claridad sin ocultar riesgo; no premiar solo preferencia estética |
| E7. Revisión/materialidad | Cadencia/continuidad actual vs registro de acontecimientos que exige nueva evaluación, primero en sombra | Riesgos materiales detectados tarde, llamadas evitables, cambios injustificados, conservación de evidencia | Mantener ITV como referencia de seguridad mientras se mide. No reducir llamadas a costa de omisiones ni usar novedad de feed como materialidad automática |

Las primeras comprobaciones de parsers, candidatos, etiquetas y comprensión pueden ser deterministas o humanas, sin modelos adicionales. Comparar juicios del modelo exigiría en el futuro un ensayo acotado y autorizado, con modelo, esfuerzo, herramientas y contexto controlados; **no se ejecutó aquí**. Un modelo actual releyendo un evento pasado puede conocer el futuro por entrenamiento: el replay de juicio no es un backtest temporal limpio. Preferir decisiones originales o evaluación prospectiva en sombra.

## Simplificación y límites de producto

La continuidad actual puede reducir rotación y reinterpretaciones marginales; no prueba que el umbral de cinco puntos sea óptimo. Ensayar ablaciones en vez de optimizar decenas de pesos. Priorizar contexto incremental, procedencia y trayectorias sobre otra suma de indicadores.

Una tarjeta de decisión puede resumir la condición vigente, dato faltante, evento que la altera y fecha de revisión con el mismo juicio financiero. Añadir una orden de entrada, tamaño, stop, objetivo o apalancamiento cambia el producto: requiere definición propia y no se introduce como “hacer más útil el informe”.

La cartera real puede concentrar el mismo riesgo en varios tickers. Informar exposición correlacionada es una oportunidad de contexto; imponer límites o liquidaciones es otra responsabilidad. Un soporte correcto no garantiza capacidad de soportar la caída antes del rebote.
