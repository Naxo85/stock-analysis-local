# Ampliación metodológica: estructura, familias de soporte y comportamiento del precio

Fecha: 17-10-2026. Anexo independiente al [informe principal](../audit_analysis_system_20261017.md). Pregunta: **si diseñáramos hoy la metodología para el propósito actual, ¿qué conservaríamos, qué cambiaríamos y qué estamos dejando fuera?**

Se revisaron productores raw/slim, instrucciones vigentes, autoridad de selección y originales congelados; se consultaron fuentes públicas primarias. Solo se escribe este anexo. No se descargaron precios, ejecutaron modelos, lotes, experimentos externos, recovery, publicaciones ni pruebas de rentabilidad. Los recuentos son lecturas de JSON originales, no nuevas decisiones. La investigación pública amplía el alcance inicialmente offline del informe; no cambia las decisiones financieras existentes.

## 1. Juicio principal y prioridades

Conservaría la compra en soportes opcionales, la separación origen/vigencia/fortaleza/selección, el contexto empresarial y de eventos, la cronología reciente y la continuidad de juicios fechados. **No empezaría añadiendo más indicadores.** Primero compararía la representación actual con una versión que entregue mejor los datos estructurales ya calculados, menos candidatos preseleccionados de forma opaca y menos puntuaciones auxiliares sin calibración.

La cobertura actual incluye mínimos, pivotes agrupados, gaps, AVWAP, medias, canales, perfil diario aproximado, reacciones y opciones. Lo que falta no es “análisis técnico” en general. Hay tres decisiones distintas: qué observa el productor, qué candidatos exporta y qué puede seleccionar cada rol. La selección previa de una familia puede excluir una oportunidad antes del juicio financiero; también puede reducir ruido útilmente. El coste de ampliarla no se justifica por el mero hecho de que sea posible.

Prioridad de investigación propuesta, sin activación:

1. Comparar listas actuales con candidatos próximos y estructura reciente fechada, preservando presupuesto de contexto y capacidad de abstenerse.
2. Separar historia del precio horizontal de historia de una referencia dinámica; medir adversidad y persistencia junto al máximo favorable.
3. Comparar conservar frente a retirar los priors crudos y familias redundantes. La carga de probar utilidad incremental corresponde también a lo que ya existe.
4. Solo después estudiar anclajes de evento, estructura multiescala o datos intradía. No convertir cada carencia en un nuevo gate ni en una llamada adicional.

Los horizontes **3/5/10/20 sesiones** que se proponen abajo son brazos de evaluación, no una nueva definición de swing ni una política de compra/salida.

## 2. Qué cubre realmente el sistema

Convención de referencias: **raw** = `gcp_functions/support_resistances_raw/main.py`; **slim** = `gcp_functions/support_resistances_slim/main.py`; **financiero** = `prompts/stock_analysis_semantic_v12.md`. Las líneas corresponden al árbol leído el 17-10.

| Familia / comportamiento | Presencia real | Qué queda fuera y en qué capa |
|---|---|---|
| Mínimo anual | raw197–225,3347–3360 calcula mínimo de252 barras; slim transmite fecha, nivel y reacciones. | Es un extremo, no prueba de demanda. Falta una etiqueta estructural que distinga origen recién formado de pivote confirmado; financiero57–77 ya prohíbe convertir el mínimo móvil automáticamente en soporte. No falta esa instrucción. |
| Suelos y techos de rango | raw230–288,3382–3468: pivotes con dos barras a cada lado,126 sesiones, agrupación por tolerancia, al menos dos toques, un ganador por lado. | No se exportan todos los pivotes, sus fechas de confirmación ni las secuencias HH/HL/LH/LL. Es principalmente selección/cálculo-resumen, no falta de OHLCV en raw. El pivote necesita las dos barras posteriores para conocerse: cualquier replay debe respetar esa disponibilidad. |
| Estructura multihorizonte | SMA20/50/200, Donchian20, Keltner, cambios20/50, fuerza relativa20/60, rangos126 y mínimo252; financiero116 puntúa validez en varios horizontes. | Hay escalas diversas, pero no una jerarquía explícita de pivotes/zonas semanal-diaria ni fecha de confirmación. Medias de distinta longitud no equivalen a observar varias estructuras independientes. |
| Ruptura, penetración, recuperación y retest |20 OHLCV completos en raw1173–1194/slim111–112; financiero138 y adaptive_revision35:239–284 exigen juicio de vigencia y no rescatar automáticamente un soporte perdido como futura recuperación. | La secuencia se interpreta en la llamada; no hay registro estructurado de estados/eventos ni orden intradía. Puede reconstruirse parte de una ruptura/retest reciente con lo existente. Fuera de20 sesiones el modelo depende de resúmenes y antecedentes, no de toda la trayectoria. |
| Gaps | raw3471–3545 detecta gap estricto entre rangos diarios (mínimo actual>máximo previo), selecciona un borde inferior, calcula ambos bordes, fecha, toques y bandera filled. | No representa todos los gaps de apertura respecto al cierre previo. Slim343–385 conserva un nivel/fecha/notas, pero no ambos bordes ni filled como datos tipados. Parte de abierto/relleno sobrevive en notes; no es ausencia total de información. |
| AVWAP | raw1682–1703 usa precio típico diario ponderado por volumen. El selector soporte3556–3660 prefiere gap-up potente, mínimo52w, inicioYTD y suelo de rango. | Devuelve el primer anclaje elegible de esa jerarquía, no compara todas las curvas o todos los eventos. “No sesgado” significaría anclas y disponibilidad fijadas antes de observar el resultado, no elegir a posteriori la curva que coincide mejor. |
| Continuidad AVWAP | raw1662–1678 observa anclas solicitadas fuera del ranking; technical_preparation36–58 obtiene fechas de snapshots/semántica CURRENT y ancla. | Ya existe. No proponer “añadir AVWAP fuera de TOP” como descubrimiento. Observa orígenes previos; no crea un catálogo neutral de nuevos eventos ni demuestra vigencia. |
| POC/HVN | raw1197–1290 distribuye volumen de cada barra por su rango;126 sesiones,48 bins, POC y hasta4 HVN. Slim227–249 conserva método aproximado, anchura y nodos. | No son transacciones observadas a cada precio ni órdenes actuales; no hay perfil intradía real. Puede ser compresión útil de OHLCV o redundancia. Financiero118/130 ya limita y declara la aproximación. |
| Reacciones | raw1328–1420 agrupa contactos consecutivos, excluye ventanas inmaduras, mide cierre del contacto y máximo de las cinco sesiones siguientes; transmite conteos, tasa y magnitudes. | No mide trayectoria adversa entre contacto y máximo, retorno al horizonte, tiempo hasta recuperación ni dirección de llegada. No es un retorno ejecutable ni probabilidad prospectiva. |
| Opciones | Walls TOP, detalle por vencimiento y observación dirigida39; el informe principal detalla cobertura/unidades. | Es una familia adicional de posicionamiento estimado, no una observación directa de órdenes de compra de acciones. Su utilidad incremental debe contrastarse frente a estructura/precio; no obliga a usarla en todos los soportes. |
| Evento empresarial | Noticias, calendario e investigación ya contextualizan riesgo y pueden cambiar autoridad. | No hay generador técnico sistemático de niveles high/low/close o AVWAP de cada anuncio empresarial autenticado. Falta enlace evento-sesión/ancla; la fecha/hora y el ajuste corporativo deben ser válidos antes de calcular. |
| Tendencia y alcanzabilidad | Tendencia1–2w, fuerza relativa y ATR/EM ya existen; financiero49–51 combina fortaleza con ventanas aproximadas1/2 ATR o EM. | No son prueba de probabilidad calibrada. Tendencia, SMA, canales y posición respecto a ellas comparten precio subyacente; más columnas no crean automáticamente información nueva. |

### Selección previa: un límite más relevante que la ausencia nominal de familias

raw51–53 fija por defecto distancia mínima5% para gap, rango y AVWAP; los filtros se aplican en3444–3445,3499–3501 y3575–3588. Para rango/gap se puntúan candidatos y se entrega uno; AVWAP usa una jerarquía. Estos parámetros son de productor, distintos de las ventanas aproximadamente1/2 ATR-EM del prompt. No se consultó hoy configuración remota, por lo que no se deducen overrides activos solo de los defaults.

**Recuento de los46 inputs originales16-10:** hay31 gap_up_lower,20 range_bottom_3_6m y13 avwap_event_support; ninguno de esos64 registros está a menos de5% de la cotización. Hay46 mínimos52w, siete dentro de5%. Hay además un put_wall_gamma en supports. Las listas TOP de puts son otro canal y no están representadas por ese único registro.

La contraevidencia importa: observed_origins aporta12 AVWAP por debajo de la cotización y a menos de5% en10 tickers; medias/Donchian/Keltner y las20 barras también pueden aportar orígenes. No es correcto afirmar “el modelo no recibe soportes cercanos”. En16/46 inputs ATR10/quote es menor que5%; esto muestra que el filtro y la ventana pueden trabajar a escalas distintas, sin demostrar que en esos16 hubiera un soporte omitido valioso. Las bandas de alcance son aproximadas y EM puede ampliar la ventana.

**Interpretación:** una metodología diseñada hoy separaría inventario observable, elegibilidad y selección. Compararía el filtro actual con un inventario compacto, diverso por bloque y horizonte, que incluya estructuras próximas sin forzar su selección. Conservar “todos los niveles posibles” sería una mala alternativa: infla contexto, aumenta falsas coincidencias y hace más fácil justificar retrospectivamente cualquier precio.

### Autoridad: capacidad de razonar no equivale a capacidad de elegir

`src/local_runner/semantic_report.py:298–315` reconoce para nuevas zonas de mantenimiento supports, put_walls_top, observed_origins, option_origins39 y ciertas medias/canales. No enumera cualquier mínimo del price_history ni todo HVN como origen automático. Las líneas451–459 explican la excepción full: puede reconstruir, por ejemplo, resistencia rota como soporte o combinación HVN/estructura.

La pregunta de utilidad es anterior al contrato: ¿mejoran esas estructuras la selección bajo el mandato actual? Si no, su exclusión puede ser correcta. Si sí, habría que expresar su identidad y evidencia en la misma llamada, sin convertir una oportunidad rutinaria en escalado high por simple limitación de catálogo. No propongo autorizar al medium cualquier cifra ni retirar las guardas de procedencia.

Usar una antigua resistencia como posible origen de un soporte presente no exige restaurar el campo público Resistencia ni volver a investigar salidas. Tampoco autoriza conservar una compra perdida a la espera de un reclaim futuro: el papel actual debe demostrarse con la secuencia disponible.

## 3. Tres distinciones metodológicas que cambiaría

### Historia horizontal, trayectoria dinámica y evidencia predictiva

En raw1441–1467, las reacciones reciben **el nivel numérico actual** y las252 barras cerradas. Para un AVWAP, eso estudia dónde reaccionó históricamente el precio alrededor de la coordenada que la curva tiene hoy. No recalcula la curva en cada sesión desde su ancla. Para un put, tampoco demuestra que el mismo OI existiera en las fechas de los rebotes.

Ejemplo verificable: `AMD/input.json#/slim/levels/observed_origins/2` del16-10 contiene AVWAP anclado06-10 a600,8444 y `historical_reaction.last_test_date=2026-09-28`. El test anterior al anclaje es perfectamente posible para un precio horizontal. No puede ser defensa de esa curva posterior. El caso no demuestra que el informe publicado cometiera esa atribución; es una diferencia de significado que debe quedar explícita.

Conservaría historia horizontal como descriptor del área. Compararía añadir, o sustituirla por, reacción a la curva conocida en cada fecha **solo para referencias dinámicas**. La segunda mide otra pregunta y no es necesariamente mejor: AVWAP cambia con cada sesión, exige fijar identidad/fecha del ancla y puede multiplicar los parámetros. El cálculo correcto no convierte ninguna de las dos medidas en evidencia causal.

Hay además selección retrospectiva del nivel: extremos, clusters y anclas se eligen con la historia disponible hoy, y luego se describe la reacción sobre parte de esa misma historia. Esto es válido para describir un soporte actual; **no es una prueba fuera de muestra de cómo habría funcionado elegirlo entonces**. No es el defecto de madurez5d ya protegido: incluso todas las ventanas maduras pueden pertenecer al conjunto usado para elegir el nivel. Para evaluar poder predictivo hay que generar candidatos con información disponible en t, congelarlos y medir después; no puntuar hoy retrospectivamente los “mejores” niveles sobre sus propios rebotes.

### Máximo favorable y compra defendible

La medida vigente mira un máximo de las cinco sesiones siguientes y exige que el cierre del contacto no quede demasiado bajo. Puede registrar rebote aunque haya una excursión adversa posterior grande antes del máximo; también omite un rebote intradía del propio contacto porque la ventana favorable empieza al día siguiente. Ninguna de esas convenciones es necesariamente errónea para su propósito descriptivo, pero no responde sola a “¿fue una buena entrada?”.

Compararía tres descriptores de la misma historia congelada: máximo favorable, mínimo adverso y cierre a horizonte, acompañados de tiempo hasta recuperación. Para compra en soporte añadiría dirección de llegada y separación entre rechazo desde arriba, cruce desde abajo y travesía del rango, cuando el OHLCV permite saberlo. Si una barra contiene ambos recorridos posibles, la etiqueta debe ser ambigua. No inferir orden high/low, absorción de órdenes, ejecución exacta ni “sweep de liquidez” a partir de una vela diaria.

No trasladaría estas medidas automáticamente a stops, salidas o nuevas condiciones de retención. Primero evaluarían la utilidad de familias y del diagnóstico; una estrategia ejecutable completa requeriría otro mandato.

### Menos priors y confluencia más honesta

raw203–210 asigna strength_score9,5 al primer test del mínimo anual,8,5 a retests; otros selectores tienen sus escalas6–9,5. Slim360 lo suministra junto a evidencia. En10/46 inputs16-10 hay mínimo52w con strength_score9,5 y reacción histórica unavailable. Es **fortaleza auxiliar raw**, no Fortaleza financiera sobre100. La rúbrica y los casos débiles/ausentes muestran que no gobierna mecánicamente el resultado.

Compararía conservar esa pista frente a retirarla del contexto financiero y entregar solo hechos. Si no mejora selección y estabilidad, eliminarla evita un prior narrativo distinto de la rúbrica. No afirmo que haya inducido sesgo real. El mismo examen corresponde a `prob_touch_1w_pct`: raw3663–3696 calcula una cola normal terminal desde distancia/sigma, no un modelo de primer contacto calibrado; el anexo de datos amplía sus magnitudes. Preferiría retirar o etiquetar correctamente antes de añadir otra falsa precisión.

Confluencia ya prohíbe duplicaciones (financiero113/124). Su problema residual es empírico: gap, media, AVWAP, perfil aproximado, extremo y rebote se calculan en gran parte del mismo OHLCV. Distintas fórmulas pueden aportar información complementaria, pero no son observaciones estadísticamente independientes por su nombre. Compararía agrupación por **dato y mecanismo** frente al conteo de etiquetas. Una coincidencia gap+media+perfil puede delimitar mejor un bloque sin merecer tres votos independientes.

## 4. Evidencia externa: qué respalda y qué no

Los siguientes resúmenes son deliberadamente acotados. No se usa popularidad como validación. La aplicación al sistema que sigue es inferencia propia.

| Fuente primaria, publicación y universo | Horizonte, método, resultado y límites |
|---|---|
| [Lo, Mamaysky y Wang, Journal of Finance2000](https://web.mit.edu/wangj/www/pap/LoMamayskyWang00.pdf), acciones estadounidenses1962–1996 | Patrones geométricos definidos con suavizado kernel; comparación de distribuciones de retornos de un día, comenzando tres días después del patrón, con controles/bootstrap. Algunos patrones aportan información; el resultado no implica beneficios extraordinarios. No prueba una zona concreta, los pesos actuales ni swing3–20d. La tendencia de volumen añadió poca información en gran parte del análisis: tampoco respalda acumular señales por intuición. |
| [Osler, NYFed Economic Policy Review2000](https://www.newyorkfed.org/medialibrary/media/research/epr/00v06n2/0007osle.pdf), seis proveedores FX, enero1996–marzo1998 | Cotizaciones indicativas por minuto, rebote15min y sensibilidad30min; niveles publicados frente a10.000 conjuntos aleatorios. Encuentra información sobre interrupciones; heterogeneidad entre pares/proveedores. Persistencia de la señal al menos5d **no es holding5d**. Las estimaciones de fortaleza no ordenaron correctamente los rebotes. No traslada su magnitud a acciones, costes ni compra swing. |
| [Osler, Staff Report125 de2001, publicado JF2003](https://www.newyorkfed.org/research/staff_reports/sr125.html), [texto primario](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr125.pdf) | Casi9.700 órdenes stop/take-profit de un banco FX, septiembre1999–abril2000. Su agrupación ofrece un mecanismo para reversión y aceleración tras niveles. Es microestructura de un intermediario, no prueba de una regla universal de retest ni identificación de órdenes desde OHLCV de acciones. Apoya distinguir rechazo y continuación, no asumir que todo cruce pierde/recupera soporte. |
| [Dai, Medhat, Novy-Marx y Rizova, WP2023/FAJ2024](https://www.nber.org/papers/w30917), [presentación de los autores en Wharton2023](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2023/09/Novy-Marx-Presentation.pdf) | Reversión de acciones EE.UU. y contraste internacional; formación1/5/21d, evolución posterior, grupos por tamaño/volatilidad/turnover y controles. Volatilidad se asocia a reversión inicial más rápida; bajo turnover a mayor persistencia. Presentación reconoce debilidad fuera de microcaps y contaminación por noticias/industria. No estudia órdenes en soportes concretos. PDF íntegro NBER/publisher no accesible en esta sesión; no se atribuyen fechas muestrales o costes no verificados. |
| [TradingView, documentación oficial AVWAP](https://www.tradingview.com/support/solutions/43000669764-anchored-vwap-drawing-tool/) y [Auto Anchored](https://www.tradingview.com/support/solutions/43000652199-vwap-auto-anchored/), sin fecha editorial visible, consultada17-10-2026 | Fuente primaria del producto: define promedio ponderado desde punto elegido y opciones de anclaje/fuente. Es evidencia de definición y uso, sin mercado muestral, experimento, horizonte validado ni rentabilidad. No justifica ventaja predictiva, superioridad de un ancla o independencia de la señal. |

**Inferencia para nuestro propósito:** existe fundamento para estudiar estructura de precios con reglas reproducibles y comparadores; no para conceder de antemano valor a cada familia o a su suma. Reversión y continuación pueden depender del tipo de evento, liquidez y escala temporal. El comportamiento de FX intradía, el patrón diario de acciones y la cartera transversal de reversión responden a preguntas diferentes; no deben sumarse como tres confirmaciones de la rúbrica actual.

No se encontró en las fuentes examinadas una validación directa, comparable al universo/mandato actual, de “todo gap se rellena”, de AVWAP elegido por proximidad, de niveles Fibonacci o de “order blocks/fair value gaps” inferidos de OHLCV. Es límite de esta revisión, no prueba universal de inexistencia. Prescindir de esas familias puede ser correcto. No usaría su popularidad como razón para ampliar el producto.

## 5. Alternativas, clasificación y coste

B/M/A = coste relativo bajo/medio/alto de datos, cálculo y complejidad; son estimaciones de diseño, no presupuestos. Ninguna se implementó.

| Alternativa | Estado actual / carencia | Utilidad hipotética y contraargumento | Comparación y coste |
|---|---|---|---|
| Inventario compacto próximo y diverso | Familias existentes; falta selección menos restrictiva, no nuevo indicador. | Evita perder niveles cercanos por5%/ganador único. Puede aumentar candidatos mediocres y presión por llenar zonas. | Actual vs sin distancia mínima pero mismo presupuesto/diversidad; medir cobertura y abstención. Datos B, cálculo B, contexto M. |
| Estructura multiescala fechada | Existente indirecta en indicadores; faltan pivotes jerárquicos y availability_date. | Distingue retroceso dentro de tendencia de nuevo deterioro. Puede repetir medias/tendencia y retrasar demasiado la confirmación. | Actual vs20 sesiones resumidas; luego semanal/diaria si añade valor. Datos B si raw archivado suficiente, M si hay que ampliar historia; cálculo M. |
| Ruptura/retest como secuencia | Interpretación actual ya exigida; falta resumen estructurado. | Hace comparable un apoyo recuperado con uno perdido, sin regla automática de cierres. OHLCV no resuelve intradía; tipar estados puede rigidizar juicio. | Mismo OHLCV con/sin resumen de hechos y ambigüedad. B/M; no restaurar campo de resistencia/salida. |
| Niveles de evento | Evento empresarial ya contextualizado; falta enlace técnico timestamp-sesión. | El mercado puede reprecificar tras resultados/guía; el nivel viejo puede perder significado. Cualquier reacción no vuelve soporte al high/low del evento. | Anclas predeclaradas por evento material vs anclas actuales; conservar ausencia si no hay respaldo. Datos M por calidad temporal; cálculo B; interpretación M. |
| AVWAP por anclas ex ante | AVWAP y observación dirigida existentes; falta selección neutral de nuevas anclas y trayectoria. | Reduce escoger la curva que mejor encaja. Varias anclas plausibles producen demasiadas curvas y comparten datos. | Jerarquía actual vs catálogo acotado por evento; horizontal vs curva histórica; y sin AVWAP. Datos B/M, cálculo M, contexto M. |
| Gaps con ambos bordes/estado | Cálculo raw existente, transmisión tipada incompleta; open-close distinto no calculado como familia. | Da geometría y recorrido del evento ya observado. Más bordes pueden fabricar dos soportes donde solo hay uno. | Conservar ambos bordes y regla de filled declarada vs nivel+notes; gap intradía cubierto vs gap estricto separados. Datos B, cálculo B/M. |
| Perfil más preciso | Perfil diario existente; datos intradía faltantes. | Permite comprobar si el nodo aproximado representa intercambio real. Puede costar mucho sin mejorar selección swing. | Primero retirar perfil aproximado vs conservarlo; solo si hay valor/relevancia, comparar contra perfil real. Datos A, cálculo/contexto M. |
| Adversidad, persistencia y dirección | Datos diarios de raw existentes; faltan métricas y semántica. | Distingue máximo favorable de defensa tolerable y cruce de rebote. Añadir medidas sin definir utilidad puede crear otra rúbrica arbitraria. | Raw reacción5d vs descriptor de trayectoria3/5/10/20; ambiguos separados. Datos B si historia completa archivada; cálculo M. |
| Regímenes y comparación sectorial | Fuerza relativa SPY y tendencia ya presentes; sectorial raw opcional3704+, no integrado como evidencia equivalente en slim.market_state. | Evita interpretar toda caída conjunta como fallo idiosincrático. La condición sectorial puede retrasar una compra válida o duplicar macro/noticias. | Actual vs retorno residual/estado de evento con timestamps; no veto por sector automático. Datos M, contexto B/M. |
| Retirar priors/duplicaciones | strength_score/prob_touch y varias fórmulas de precio ya presentes. | Menos falsa precisión y anclaje. Podrían aportar una compresión útil que el modelo no reconstruye bien. | Igual input factual, con/sin priors; luego una familia menos cada vez. Datos B, cálculo B, contexto menor. |
| No añadir patrones populares | Fibonacci, pivots algebraicos intradía, etiquetas de liquidez no son necesidad acreditada. | Ausencia puede ser acertada por redundancia, horizonte o evidencia insuficiente. | Solo entrarían en investigación con hipótesis específica y baseline barato; no crear catálogo exhaustivo. Coste evitado. |

No conviene comparar una alternativa rica con una baseline empobrecida artificialmente. Por ejemplo, retirar AVWAP mientras se conserva evidencia derivada de la misma curva dentro del texto heredado no es una ablación limpia; ocultar todo contexto histórico sí cambia otro eje. Hay que registrar exactamente qué información ve cada brazo y qué permanece por continuidad.

## 6. Casos locales ex ante y evaluación propuesta

### Casos de razonamiento, no resultados posteriores

Directorio común verificado: `logs/batch/2026-10-16/15-58-24/adaptive/<TICKER>/`. En cada fila se leyó `input.json` y `publish/output/<TICKER>/latest.json`; los punteros de salida son `/semantic_report/data/plan`. Se contrastan hechos ya disponibles al decidir16-10; no se evalúa qué ocurrió después.

| Caso / fuentes precisas | Evidencia y decisión observadas | Qué enseña y contraevidencia |
|---|---|---|
| AMD: input#/slim/levels/supports, observed_origins, price_history; salida#/.../entry | Cotización541,865; AVWAP agosto536,0945 en observed_origins a1,06%; candidato AVWAP mayo508,1709 a6,22%. Barra15-10 mínimo530,09/cierre562,23. Entry531–535 conservada; Opciones0. | La continuidad dirigida ya evita parte de la selección restrictiva. No demuestra que una nueva ancla próxima se hubiera descubierto sin antecedente. El mínimo penetró antes del cierre recuperado: ubicación y defensa no son iguales. |
| GEV: input#/slim/levels/supports/0 y price_history; salida#/.../ambitious_entry | Suelo871,125 de septiembre;15-10 mínimo871,155 y cierre926,44. Añade869–875 con20/14/0/7/11; Entry898–902 continúa. | Estructura y reacción bastan sin opciones. No prueba que la combinación vaya a defender de nuevo ni que sumar otra familia mejore. El rango tiene origen previo y reacción reciente; no es solo el mínimo del último día. |
| TLN: input#/slim/levels/supports, technicals, volume_profile, price_history; salida#/.../ambitious_entry | Gap337,22 del06-10, mínimo15-10 337,99/cierre353,60; nuevo Washout336,5–338,5 apoyado además por media/perfil. | Gap ya existe y se usa; no venderlo como omisión. Una mejor transmisión de ambos bordes permitiría explicar geometría. Tres transformaciones de OHLCV próximas no prueban tres mecanismos independientes. La reparación13→16 pertenece a otro hallazgo, no valida esta familia. |
| SPCX: input#/slim/price_history y reference; salida#/.../entry, ambitious_entry |15-10 todo el rango bajo150: máximo149,04, mínimo140,66, cierre148,62. Promueve144,75–145,5; Washoutnull porque AVWAP cercano es mismo bloque y otro mínimo/nodo no delimita zona distinta. | Vigencia y abstención ya funcionan en un caso exigente. Un catálogo más amplio podría aportar otra zona, o solo duplicar el bloque; no tomar null como error. OHLCV no prueba el orden exacto del recorrido. |
| SOFI: input#/slim/price_history y levels/supports/0; salida#/.../entry |15-10 mínimo13,86, apertura13,89, cierre15,09; Entry13,9–14; componentes17/0/12/8/8 y advertencia de fragilidad; Washoutnull. | El sistema permite apoyo nuevo sin esperar cinco sesiones maduras; no falta una capacidad general de “leer recuperación”. La reacción de una sesión no demuestra absorción sostenida y no debe recibir la historia inexistente de un apoyo antiguo. |
| MP frente a IREN: mismos punteros | MP conserva37,7–38 desde mínimo37,81 de julio, no visitado15-10 (mínimo38,5967), fortaleza38. IREN sustituye el apoyo anterior por26,5–26,7 tras mínimo26,6/cierre30,39; cotización16-10 27,705, fortaleza48. | Un origen antiguo y uno nuevo pueden ser defendibles con incertidumbres distintas. Requerir siempre test reciente excluiría MP; comprar todo nuevo mínimo banalizaría IREN. Estos dos casos no establecen cuál política es más rentable. |

AUR aporta un caso contrario adicional para revisión ciega: conserva Entry4,97–5,03 tras mínimo4,85/cierre5,40 del15-10, pero mantiene Washout ausente pese a suelo4,795 y gap4,7. Su razón heredada exige defensa reciente/respaldo independiente. Es una tensión útil con la intención38, **no una demostración automática de error**: falta medir si los candidatos son bloques distintos, adecuados y vigentes; el cambio de política por sí solo no prueba prior_error. No introducir por la vía de la evaluación una obligación de elegir el gap.

### Diseños comparativos concretos

**Unidad de evaluación:** ticker, instante de preparación y bloque estructural con identidad; no una fila por familia cuando varias describen el mismo bloque. Separar candidatos no seleccionados, zona elegida, zona heredada y ausencia. Mantener todos los tickers originales, también fallos y datos no disponibles. Los46 casos de octubre sirven para comprobar representaciones y errores de interpretación; son demasiado próximos en tiempo y seleccionados por incidentes para demostrar rendimiento general.

| Pregunta | Brazos propuestos | Medida primaria y criterio para conservar/cambiar |
|---|---|---|
| ¿El productor excluye información útil? | A listas actuales; B mismos datos y presupuesto, candidatos próximos/diversos sin mínimo5%; C baseline simple de pivotes/medias. | Cobertura de orígenes defendibles en revisión ciega ex ante, desacuerdos y falsos candidatos por bloque. Después resultado prospectivo condicionado a distancia/volatilidad. Adoptar B solo si aporta cobertura útil sin crecimiento desproporcionado de ruido/contexto. |
| ¿Aporta la estructura multiescala más que20 OHLCV? | A20 barras actuales; B resumen fechado de pivotes/secuencia; C B+escala semanal. | Calidad de distinguir vigente/perdido/indeterminado, estabilidad entre observadores y menor contradicción con hechos. OOS comparar error de continuación/reversión; retirar escala si no mejora sobre B. |
| ¿Es AVWAP útil por sí mismo o por selección retrospectiva? | A anclas actuales; B anclas predeclaradas y availability_date; C sin AVWAP, manteniendo otras familias. Subprueba horizontal vs curva histórica, sin cambiar anclas. | Ranking de bloques y abstención; MFE/MAE/cierre a3/5/10/20 tras primer contacto futuro. No elegir mejor ancla/horizonte después de ver resultados. Mantener solo si mejora sobre C y no depende de unas pocas fechas. |
| ¿Los gaps añaden algo a estructura simple? | A nivel+notes; B ambos bordes/estado tipados; C sin familia gap, pero misma historia/evento. | Claridad de geometría y decisiones distintas justificadas; resultado condicionado a tamaño/tipo/evento. C puede ganar por simplicidad. No usar porcentaje de “relleno” como éxito comprador sin definir dirección y adversidad. |
| ¿La reacción5d resume calidad? | A estadística actual; B máximo+mínimo+cierre/tiempo; C solo número/edad de contactos. | Ordenación prospectiva de resultados y adecuación al mandato. La medida debe superar C; una tasa alta de máximos favorables con adversidad elevada no basta. |
| ¿Hay doble conteo o priors inútiles? | A contexto actual; B sin strength_score/prob_touch; C agrupación por dato/mecanismo, misma evidencia factual. | Cambios en ranking, justificación, estabilidad y resultado prospectivo; conservar score auxiliar solo si añade información reproducible. No evaluar por “produce notas más altas”. |
| ¿Conviene no seleccionar? | Política actual frente a baseline que siempre selecciona el mejor candidato y baseline que se abstiene salvo evidencia definida ex ante. | Curvas cobertura/calidad y coste de oportunidad; reportar ganancias perdidas y daños evitados. No declarar óptimo al que selecciona más ni al que nunca compra. |

Estas comparaciones son diseños, no experimentos autorizados ni resultados. Primero se puede reconstruir offline el inventario con archivos ya guardados y etiquetar ciegamente. Una comparación nueva de modelos requeriría autorización separada; el informe no la ejecuta ni la incorpora como coste automático de producción.

Para una evaluación futura de precios:

- Congelar antes de medir identidad, rango, ancla, datos, selección, disponibilidad y condiciones. Los pivotes de dos barras solo existen después de esas barras; un anuncio after-hours debe anclarse a una sesión definida. Las referencias dinámicas usan solo información conocida entonces.
- Separar alcanzabilidad de calidad tras contacto: fecha/precio del primer contacto posterior, nunca el toque anterior que ayudó a seleccionar. Contar “no tocado” como resultado distinto de fallo/éxito; publicar tanto denominador total como condicionado al contacto.
- Medir máximo favorable, máximo adverso, cierre y persistencia por horizonte en unidades comparables; comparar contra bloques/niveles control a distancia y volatilidad semejantes. Ninguna métrica aislada equivale a P&L. Una simulación de orden exigiría supuestos explícitos de fill, spread, gap y salida; no están decididos aquí.
- Replays cronológicos, candidatos generados en t y horizontes posteriores no solapados entre entrenamiento/validación. Separar por tiempo y agrupar errores por ticker/fecha para no convertir decenas de zonas expuestas al mismo shock en observaciones independientes.
- Estratificar, sin elegir a posteriori el ganador, por evento empresarial, volatilidad/liquidez, estructura alcista/bajista/lateral y antigüedad del origen. “Antiguo” o “baja convicción” no es una exclusión automática.
- Comparar precisión con coste: bytes de contexto, duplicaciones, revisiones humanas, reparaciones, abstención, estabilidad de rangos y coste operativo. Una mejora pequeña que requiera feed intradía y mucha carga puede perder frente a la versión simple.

**Decisión de diseño defendible hoy:** conservar el núcleo y sus capacidades existentes; priorizar semántica y representación antes de añadir familias; someter también indicadores y puntuaciones actuales a ablación; mantener ausencia como resultado válido. Una metodología más detallada solo merece adoptarse si resuelve una pregunta útil mejor que una alternativa sencilla.

## 7. Reproducción del recuento descriptivo y límites

Lectura sin importación de productores ni llamadas de red, ejecutada en memoria con Node:

```javascript
const fs = await import('node:fs/promises');
const base = 'E:/stock-analysis-local/logs/batch/2026-10-16/15-58-24/adaptive';
const stats = {inputs: 0, families: {}, observed_below_within5: 0,
  stocks_observed_below_within5: 0, atr_below5pct: 0, unmatured_52w_with9_5: 0};
for (const dir of (await fs.readdir(base, {withFileTypes: true})).filter(x => x.isDirectory())) {
  let input;
  try { input = JSON.parse(await fs.readFile(base + '/' + dir.name + '/input.json', 'utf8')); }
  catch (e) { if (e.code === 'ENOENT') continue; throw e; }
  const s = input.slim;
  stats.inputs++;
  if (typeof s.technicals.atr10 === 'number' && typeof s.latest_price === 'number'
      && s.latest_price > 0 && s.technicals.atr10 / s.latest_price < 0.05) stats.atr_below5pct++;
  const near = s.levels.observed_origins.filter(x => x.distance_pct < 0 && x.abs_distance_pct < 5);
  stats.observed_below_within5 += near.length;
  if (near.length) stats.stocks_observed_below_within5++;
  for (const l of s.levels.supports) {
    const f = stats.families[l.type] ??= {n: 0, inside5: 0};
    f.n++;
    if (l.abs_distance_pct < 5) f.inside5++;
    if (l.type === '52_week_low' && l.strength_score === 9.5
        && l.evidence.historical_reaction.status === 'unavailable') stats.unmatured_52w_with9_5++;
  }
}
console.log(JSON.stringify(stats, null, 2));
```

Base absoluta: `E:/stock-analysis-local/logs/batch/2026-10-16/15-58-24/adaptive`. Se omitieron directorios sin input al recorrer; el resultado contiene46 inputs. No se infiere que el catálogo bruto omitiera un candidato mejor porque no se reconstruyeron todos los candidatos no exportados. No se atribuye a los priors un efecto causal sobre el modelo. No se evaluaron rentabilidad, ejecuciones ni evolución posterior. No se transforman propuestas en acuerdos operativos.

Referencias directas para inspección: [raw](E:/stock-analysis-local/gcp_functions/support_resistances_raw/main.py:3347), [slim](E:/stock-analysis-local/gcp_functions/support_resistances_slim/main.py:343), [financiero v12](E:/stock-analysis-local/prompts/stock_analysis_semantic_v12.md:43), [autoridad de origen](E:/stock-analysis-local/src/local_runner/semantic_report.py:298), [anclas dirigidas](E:/stock-analysis-local/src/local_runner/technical_preparation.py:36).
