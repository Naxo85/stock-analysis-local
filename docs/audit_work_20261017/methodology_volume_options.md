# Metodología de volumen, opciones, microestructura y confluencia — 17-10-2026

Ampliación independiente de [la auditoría principal](E:/stock-analysis-local/docs/audit_analysis_system_20261017.md). Pregunta: si se diseñara hoy el sistema para seguimiento empresarial y selección opcional de compras en soportes, ¿qué merece conservarse, cambiarse o quedar fuera? Esta revisión trata utilidad y validez económica, además de corrección contractual. No propone restaurar resistencia/stops retirados ni forzar zonas.

**Intervención:** lectura local, consultas bibliográficas a fuentes primarias y agregaciones descriptivas de originales congelados. Único archivo escrito: este anexo. No se cambiaron código, prompts, parámetros, tests, informes originales ni despliegue; no hubo modelos, batches, recuperación, publicación, descargas de cotizaciones actuales ni experimentos externos. Los horizontes 3/5/10/20 sesiones son escenarios de evaluación propuesta, no una política nueva. Los defectos de adquisición ya probados se remiten a [data.md](E:/stock-analysis-local/docs/audit_work_20261017/data.md); corregirlos no validaría por sí solo la metodología.

## 1. Juicio de diseño

Conservaría el mapa fechado de precio, volumen, identidades de opciones y vencimientos, la separación origen/viabilidad/fortaleza/selección, el derecho a no seleccionar compras y la continuidad de juicios auténticos. Conservaría las reacciones históricas como descripciones explícitas del pasado, con muestras y horizontes visibles.

Cambiaría la interpretación causal de las opciones y la precisión aparente. El sistema observa concentración de contratos y una sensibilidad teórica; no observa el inventario neto de quienes cubren, su estrategia ni sus operaciones de cobertura. Por tanto, no ha identificado un mecanismo comprador en un put wall. Tampoco ha demostrado que Opciones deba pesar 25/100 o que sus subcriterios agreguen utilidad predictiva a la estructura. Esto es una hipótesis de diseño pendiente, no evidencia de que las opciones sean inútiles.

Retiraría del razonamiento operativo la lectura de gamma_regime como signo conocido de dealers, las probabilidades de toque actuales y la etiqueta IV barata/cara obtenida de straddle/RV. Pondría max pain y las notas auxiliares de fuerza/confianza en la primera comparación de eliminación: aportan etiquetas y supuestos redundantes cuya utilidad no está demostrada. Mantendría sus observaciones primitivas cuando sean útiles para investigar, sin defender una variable solo porque ya tiene parser, catálogo o test.

No incorporaría de entrada profundidad de libro, footprint, vanna/charm o flujos clasificados de pago. Pueden responder preguntas reales, pero su coste, latencia, cobertura y horizonte deben justificarse contra una base sencilla. La ausencia de una técnica puede ser una decisión acertada.

## 2. Qué calcula realmente el sistema

Convención: raw = [gcp_functions/support_resistances_raw/main.py](E:/stock-analysis-local/gcp_functions/support_resistances_raw/main.py), slim = [gcp_functions/support_resistances_slim/main.py](E:/stock-analysis-local/gcp_functions/support_resistances_slim/main.py). Las líneas corresponden al árbol local auditado. La correspondencia de algunas funciones con las fuentes archivadas del despliegue39 está en data.md; no equivale a verificar remotamente todo el runtime.

| Objeto | Implementación y alcance efectivo | Supuesto económico añadido al usarlo |
|---|---|---|
| TOP puts/calls | Tres vencimientos, cinco strikes por lado, ordenados por agregado de gamma absoluta×OI×100×spot²; el slim vuelve a ordenar por distancia. Raw:60–63,1993–2021,2364 y 3738; slim:391–419. | Concentración de sensibilidad implica atención/posible efecto local; no demuestra demanda compradora ni defensa. TOP tampoco es universo completo. |
| Observación dirigida39 | Identidades CURRENT fuera del TOP en las mismas cadenas; estados observado/no observado y OI cero/desconocido separados. Raw:1878–1943; slim:338–340. | Acredita presencia y alcance. No acredita que comprar allí sea bueno; es una mejora de observabilidad, no una nueva señal rentable. |
| gamma_regime | Calls menos puts, usando gamma absoluta y OI, con multiplicador100. Raw:3904–3929; expuesto en slim y trend. | Asigna signos de inventario por tipo de opción; no hay posiciones netas dealer en la entrada. |
| EM semanal | Suma de mid call+put del strike más cercano a spot. Selección4–9 días calendario; fuera de esa ventana escala sqrt(5/DTE). Raw:73–74,794–824,2255–2319. | Straddle como escala de incertidumbre, ventana variable como semana y difusión estacionaria para escalar. No es directamente sigma ni una banda física68%. |
| ATM IV por vencimiento | Straddle/(0,8×spot×sqrt(DTE/365)), con T mínimo1e-6. Raw:3932–3985. | Aproximación ATM y temporal; DTE entero pierde las horas restantes del vencimiento de hoy. No es la IV de proveedor preservada sin transformación. |
| IV/RV | EM_pct_1w / RV20 semanal; RV es std(logreturns)×sqrt252/sqrt52. Raw:3079–3132. | Compara una prima straddle normalizada con desviación estándar y la llama IV/RV. Trend la clasifica barata/cara:4158–4160. |
| Probabilidad de toque | 100×[1−Φ(distancia/EM)], con RV como alternativa; raw:3146–3187,3663–3697. Slim:361 conserva el porcentaje. | Confunde cola terminal con primer paso y EM con sigma; no incluye ajuste empírico ni definición de probabilidad física/neutra al riesgo. |
| Max pain | Strike que minimiza suma OI×intrínseco al vencimiento. Raw:2321–2362,3989–4028. | No incluye primas, inventarios netos, coberturas, costes ni nuevas operaciones. No es beneficio/pérdida total de dealers ni fuerza que deba atraer spot. |
| Perfil de volumen | 126 sesiones cerradas; cada volumen diario repartido uniformemente entre bins tocados por low/high;48 bins, POC y cuatro HVN; approximate=true. Raw:1197–1289. | Supone distribución intradía no observada. Identifica un mapa aproximado de actividad histórica, no órdenes actuales ni volumen negociado exacto a cada precio. |
| Reacción histórica | Hasta252 sesiones; episodios de toque colapsados; cierre del toque y máximo high de las cinco sesiones siguientes. Raw:1328–1421. | Ese máximo favorable y un cierre admitido equivalen a defensa. No observa orden del recorrido posterior ni drawdown antes del rebote; no exige aproximación desde arriba. |
| AVWAP | Media acumulada de precio típico diario (H+L+C)/3 ponderado por volumen desde ancla. Raw:1682–1703. | Aproximación diaria de VWAP; tampoco es una orden pendiente ni coste real de todos los propietarios actuales. |
| Confluencia/Durabilidad | Juicio estructurado: familias independientes y supervivencia al horizonte; financiero v12:113–125. | Nombres de familias no garantizan independencia estadística; supervivencia no está calibrada como probabilidad. |
| Trend/confidence | Suma de reglas RSI, medias, Donchian, paredes, régimen, EM/RV y volumen; confidence=35+45×cobertura+0,2×abs(bias), acotada20–95. Raw:4130–4238; slim:422. | Cobertura/coincidencia de indicadores se presenta como confianza; no es tasa histórica de acierto. Es auxiliar, no Fortaleza financiera. |

El [prompt financiero v12](E:/stock-analysis-local/prompts/stock_analysis_semantic_v12.md:110) asigna Estructura 25, Volumen/reacción 20, Opciones 25, Confluencia 15 y Durabilidad 15. Dentro de Opciones reparte8 puntos concentración,6 dominio vecino,5 cercanía y6 liquidez/presencia en vencimientos. No hay estimación local de aportación incremental que justifique esas proporciones. Con Opciones=0, los otros máximos suman75: una zona no puede llegar a fuerte 85 aunque alcance el máximo en las demás familias. Es una consecuencia de diseño, no un bug ni una prohibición de seleccionar. La nota depende por construcción de disponer de esa familia; conviene comparar también un perfil de evidencias, sin total único. El orden correcto de cálculo y las sumas verificables impiden algunos errores; no convierten la escala en una medida científica.

## 3. Opciones: qué inferencia sí soportan los datos

### 3.1 OI/gamma: separar exposición hipotética, signo y cobertura efectiva

OI cuenta contratos abiertos; cada contrato tiene comprador y vendedor. No identifica quién está largo, qué contraparte ajustará delta o qué parte de su cartera ya compensa el riesgo. La fuente operativa OCC tampoco equipara OI con dirección ni liquidez. [OIC/OCC, definiciones de OI y liquidez](https://www.optionseducation.org/referencelibrary/faq/general-information).

Un contraejemplo algebraico basta para delimitar gamma_regime: una call y una put con idénticos OI y gamma producen calls−puts=0. El mismo registro público es compatible con dealers cortos en ambas, largos en ambas o posiciones compensadas; esas carteras tendrían sensibilidades netas diferentes. No es un problema que resuelva más razonamiento del modelo sobre el mismo JSON.

La literatura sí ofrece mecanismos de cobertura que afectan precios. La diferencia metodológica decisiva es medir posiciones netas o disponer de datos que permiten reconstruirlas. [Cboe explica su cálculo con identificación de participantes](https://www.cboe.com/insights/posts/volatility-insights-evaluating-the-market-impact-of-spx-0-dte-options/); [Ni et al.2021 documentan un canal no informativo](https://academic.oup.com/rfs/article-abstract/34/4/1952/5873587). Ninguno valida la equivalencia put OI positivo=soporte comprador durable ni el proxy calls−puts de este sistema.

**Conservar:** strike, expiración, OI, gamma/fecha, concentración relativa, quotes/calidad y cobertura; usar expresiones como concentración observada y sensibilidad bajo un supuesto de cobertura. **Cambiar:** dejar signo dealer desconocido; si se estudia un mecanismo, mostrar escenarios neto largo/corto/compensado y comprobar si la conclusión depende del supuesto. No traducir concentración a una obligación de retener o seleccionar.

**Unidades:** gamma×OI×multiplicador×spot² es una sensibilidad nocional por unidad de cambio relativo del precio. Si se desea expresar ajuste aproximado ante1%, hace falta el factor0,01 y declarar esa perturbación. El nombre gamma_usd_millions no declara el shock; no debe compararse sin más con cifras externas “por1%”. No se afirma aquí un error universal100× porque el contrato actual no define ese shock. Para comparar relevancia entre acciones habría que normalizar además frente a liquidez/volumen monetario y reconocer que sensibilidad potencial no es flujo ejecutado.

**Dato faltante prioritario, barato:** conservar contract_size, identidad completa y greeks.updated_at cuando estén presentes. Tradier documenta greeks horarios; spot y quotes pueden tener otra frecuencia. La fórmula de exposición puede combinar estados de tiempos distintos aunque la captura sea reciente. Hoy quote detail31 ayuda, pero no resuelve el timestamp de gamma ni el inventario. [Tradier, frecuencia de mercado](https://docs.tradier.com/docs/market-data), [campos de quotes](https://docs.tradier.com/docs/quotes). Preservación y cálculo determinista requieren0 llamadas adicionales al modelo.

### 3.2 Horizonte, vencimientos y durabilidad

Tres vencimientos no representan un plazo uniforme: en los originales del16 oct aparecen0/7/14DTE,0/3/5,0/3/7 y, para LEU,0/35/63. Un componente llamado B_options_7_21DTE no cambia esa selección. El mismo ranking puede estar dominado por contratos que vencen ese día o por una estructura mensual muy distinta.

Que un strike aparezca en varios vencimientos es **cobertura transversal temporal**, no persistencia demostrada de la misma posición a través de varias capturas. OI de hoy más OI de otra expiración tampoco prueba quién renueva. Para estudiar persistencia real hacen falta capturas por identidad, cambios de cobertura y calendario, sin comparar bases incompatibles de OI dirigido y TOPgamma.

Conservaría las instrucciones v12:145–146 que prohíben justificar una compra más allá del vencimiento únicamente con ese bloque, y el detalle por expiración31. Añadiría al cálculo una separación descriptiva de contribución que vence antes/después de cada horizonte candidato3/5/10/20 sesiones, junto con la cobertura efectiva. Debe ser análisis de sensibilidad, no un nuevo corte universal de viabilidad. No trasladar directamente gamma de hoy a dentro de20 sesiones: depende de spot, volatilidad y tiempo.

Los resultados de pinning en días de vencimiento justifican estudiar un mecanismo local y temporal. No prueban soporte durable semanas. En [Ni, Pearson y Poteshman2005](https://www.sciencedirect.com/science/article/pii/S0304405X05000577), la concentración al cierre es principalmente compatible con permanecer cerca de strikes ya próximos; no con atraer sistemáticamente acciones lejanas hacia un strike. No hay motivo para tratar el mínimo global de pago como objetivo inevitable.

### 3.3 Max pain y flujos: eliminar una inferencia, evaluar otra

Max pain resume una función de pagos brutos. Su mínimo puede ser matemáticamente correcto y carecer de poder operativo. El campo confidence de raw:4027 mide separación entre mínimos dentro de esa función; no confianza probabilística. Slim no lo conserva, lo que ya evita una parte de la falsa precisión. El strike max_pain sí permanece en options.

Propuesta preferida: retirarlo del argumento para elegir compras y de cualquier lenguaje de imán; comparar un contexto sin max pain con la base actual. Mantenerlo solo como dato de investigación si muestra aporte incremental condicionado a proximidad, expiración y demás información. Esto ahorra contexto y no requiere nuevas fuentes. La ausencia de un paper validando exactamente el cálculo no prueba que nunca sirva; la carga de justificar su utilidad debe recaer en conservarlo como señal, no en crear un guard adicional para protegerlo.

Una alternativa distinta es flujo de opciones clasificado: compras para abrir frente a ventas/cierres, participante y horizonte. [Pan y Poteshman](https://www.mit.edu/~junpan/5919.pdf) investigan ese tipo de volumen, no OI bruto, y atribuyen buena parte de la información a componentes no públicos. Es una oportunidad plausible para3/5 sesiones, con coste y extrapolación importantes; no permite rebautizar el ratio OI actual como señal equivalente.

[Cboe Open-Close](https://datashop.cboe.com/cboe-options-open-close-volume-summary) ofrece desglose por participante/lado/apertura-cierre en sus bolsas. Esto no cubre automáticamente todas las bolsas ni reconstruye toda la cartera dealer: hacen falta historia desde origen, otras plazas, ajustes y reglas de neteo. No se consultaron tarifas ni se compraron datos. Antes de pagar, definir una hipótesis que esas variables puedan distinguir y un comparador con OI simple;0 llamadas LLM adicionales en producción si el cálculo queda determinista.

## 4. Incertidumbre: EM, IV/RV y probabilidades

### 4.1 Conservar una escala de rango sin prometer una distribución

La identidad de pago de un straddle europeo es |S_T−K|. Bajo valoración neutral al riesgo, su prima descontada mide una esperanza de ese pago, con supuestos y ajustes; una opción americana añade ejercicio temprano y dividendos. No es la probabilidad física de rebote, ni desviación estándar por definición. Para una normal centrada, E|X|=sigma×sqrt(2/pi), aproximadamente0,798sigma. Esa igualdad ilustra por qué incluso en un caso ideal straddle y sigma son distintos; no es una corrección universal aplicable a las acciones auditadas.

La [metodología oficial VIX](https://cdn.cboe.com/resources/vix/VIX_Methodology.pdf) ilustra otra construcción: varianza implícita agregando opciones de múltiples strikes y vencimientos que encuadran un plazo. No propongo copiar el VIX de índice a acciones; muestra que una sola suma ATM y una medida de varianza responden a objetos diferentes.

Propuesta mínima: conservar prima ATM observada, strike, vencimiento, tiempo real restante, spot/base y horquilla de estimación bid/ask, denominándola escala implícita de movimiento de ese vencimiento. No convertirla automáticamente en banda68% ni precio objetivo. Corregir primero unidades, parser y quotes señalados en H07/H08/H10b. Después distinguir dato observado, aproximación y extrapolación.

Para comparar contra RV hay dos caminos defendibles: comparar volatilidades con el mismo horizonte y medida, o conservar straddle/RV con su nombre literal y calibración propia. La regla actual IV_CHEAP_LT_1_0 no tiene esa equivalencia. En APP, la fila de vencimiento16 oct tiene atm_iv=14,1143 en unidades de sigma anual, resultado muy elevado de dividir el straddle3,075 por el tiempo mínimo artificial cuando DTE=0; no es una observación directa de IV14,1143 del proveedor. La representación intradía del tiempo es material incluso sin cambiar fuentes. Un ratio0,8 puede surgir por la diferencia de funcional aun bajo el ejemplo normal; no demuestra prima barata. Earnings, saltos y estructura temporal hacen especialmente frágil escalar sqrt(t). Tampoco corresponde usar5 días de negociación como5 días calendario sin declarar reloj.

No hace falta una superficie completa para mejorar esto. La primera alternativa útil es menor precisión, vencimiento explícito y rango de sensibilidad; una estructura por plazo o separación de varianza de evento vendría después si mejora la evaluación. Skew/asimetría de riesgo puede aportar más a las compras que otro indicador direccional de OI, pero requiere conservar IV/quotes por strike, validar cobertura y no atribuir probabilidades físicas a una densidad implícita sin más.

### 4.2 prob_touch: error de objeto, no mera calibración pendiente

Raw calcula la cola de una normal terminal y la etiqueta toque. Bajo un proceso browniano aritmético sin deriva, con desviación a horizonte sigma_H y barrera positiva d, P(X_H≥d)=1−Φ(d/sigma_H); P(max X_t≥d)=2×[1−Φ(d/sigma_H)]. Con d=sigma_H son15,87% y31,73%. La diferencia aparece incluso antes de introducir drift, saltos, volatilidad variable o EM mal identificado. A distancia casi0, la cola terminal se aproxima a50%, mientras el primer paso se aproxima a100%.

Este contraejemplo demuestra que el cálculo actual no estima el objeto anunciado bajo su interpretación natural. **No autoriza a duplicar los porcentajes actuales:** EM no es sigma, el mercado no satisface ese proceso por defecto y el sistema no ha calibrado ninguna probabilidad de camino. Además, tocar una compra y que esta funcione son sucesos distintos.

Propuesta preferida: retirar el porcentaje del contexto decisorio y conservar distancia/ATR, distancia/escala implícita y horizonte con calidad. Si se decide ofrecer probabilidades más adelante, definir por separado tocar zona, penetrar extensión, rebote favorable, movimiento adverso y retorno terminal. Comparar modelos con base de frecuencia condicionada y puntuar calibración, Brier y utilidad. No premiar un porcentaje porque tenga fórmula cerrada.

### 4.3 Fuerza y confianza no son una capa de incertidumbre independiente

Las notas raw de walls parten de7,8 y agregan concentración, cluster, OI y cercanía temporal (raw:2129–2168); no son Fortaleza financiera. El auxiliar trend tiene su propia nota de confianza por cobertura y magnitud del bias. Un campo9,5 o89 puede anclar el juicio aunque sus ingredientes ya estén en el contexto. No se demostró ese efecto en modelos originales, pero hay una comparación barata que lo puede distinguir: mismos datos primitivos sin las etiquetas auxiliares, frente al contexto actual.

Una descripción de incertidumbre útil separaría: disponibilidad/frescura; error de medición/aproximación; estabilidad del nivel ante decisiones razonables de cálculo; tamaño/dependencia de muestra; incertidumbre causal; y resultados futuros. No son seis descuentos automáticos sobre la misma falta. La inexistencia de un dato debe poder quedar como desconocido sin fabricar un cero ni duplicar penalización entre Opciones, Confluencia y Durabilidad.

## 5. Volumen, reacciones y evidencia compartida

### 5.1 El perfil diario aproxima algo no identificable con OHLCV

Dos días pueden tener idénticos open100/high110/low90/close100 y volumen1millón, con casi todas las operaciones de uno en95 y del otro en105. OHLCV no distingue esos perfiles. El reparto uniforme devuelve lo mismo. Este ejemplo lógico no usa un precio futuro ni un experimento de mercado.

El flag approximate y máximo3 puntos del perfil diario son buenos límites existentes. Pero “POC317,0603” sigue teniendo una precisión aparente muy superior a su bin y a su identificación. Preferiría región/bin y sensibilidad a resolución/ventana, no cuatro decimales como coordenada conocida. El coste inicial es local, sin modelo: repetir de forma predefinida resoluciones y ventanas razonables y mostrar si el mismo bloque persiste. No elegir a posteriori el binning que mejor confirme la compra.

Un perfil intradía de trades mejoraría la medición de volumen ejecutado por precio. Aun así no mostraría órdenes futuras ni propietarios que defenderán el nivel. Debe competir contra el perfil diario y contra ningún perfil en el horizonte swing, antes de añadir feeds. [Cont, Kukanov y Stoikov](https://arxiv.org/html/1011.6402v3) relacionan movimientos muy cortos con desequilibrio de eventos del libro, que no equivale a volumen diario agregado. Su resultado no valida comprar un HVN durante20 sesiones.

### 5.2 Qué significa hoy defensa histórica

El método actual usa sesiones completas, espera cinco posteriores, excluye ventanas inmaduras y distingue reacción alcista de rechazo bajista. Es mejor que contar cada toque o llamar fallo a un evento todavía no maduro. Esas propiedades deben conservarse.

Pero su resultado exacto es: cierre del día de toque≥nivel−tolerancia, seguido de un high suficiente en cinco sesiones. Puede existir una caída fuerte antes de ese high. Un cruce ascendente desde abajo también puede entrar en esa definición. Los episodios separados por una sesión sin toque pueden compartir buena parte de su ventana futura; colapsar toques consecutivos no crea independencia entre todos los eventos. La tasa de defensa no es una frecuencia de operaciones ganadoras ejecutables.

La tolerancia usa el mayor entre0,5% del nivel y0,2ATR; el mínimo rebote el mayor entre1% y mediaATR en porcentaje. La historia se reevalúa con ATR histórico reciente de sesiones completas, no necesariamente con el ATR disponible en cada antiguo toque. La comparación ya separa recalibración de nuevos hechos: es una protección valiosa, pero una medición al estado actual no es un backtest causal de decisiones antiguas.

Alternativa: conservar las estadísticas descriptivas y añadir, para evaluación, eventos con aproximación desde arriba/abajo, MFE y MAE desde un origen declarado, cierre final, tiempo de recuperación y ambigüedad de orden intradía. Cuando una barra toca barreras favorable y adversa, no inventar qué ocurrió primero. Para datos diarios se puede reportar ambigüedad o usar cotas conservadoras. No hace falta investigar intradía cada caso ni imponer automáticamente una ruptura a la política vigente.

El registro de eventos individuales y la serie completa permitirían revisar estos cálculos; ahora el modelo recibe agregados y20 barras recientes, insuficientes para reconstruir252 sesiones. Falta principalmente conservación/representación y cálculo, no otra llamada de análisis. El origen de los niveles también debe quedar fechado: probar hoy un nivel elegido a partir de toda esa misma historia es descripción retrospectiva, no selección ex ante independiente.

### 5.3 La rúbrica suma métricas relacionadas

Del máximo20 de Volumen/reacción, hasta16 puntos vienen de repetición, tasa, magnitud y recencia de los mismos episodios de precio; el perfil aporta hasta4 y actualmente3 con OHLCV. El nombre completo es más fiel que “volumen puro”. No hay una lectura separada de participación compradora/vendedora ni verificación de volumen durante cada defensa.

Cantidad de defensas y tasa comparten numerador; magnitud y éxito dependen del mismo rebote; recencia puede pertenecer a esa misma muestra. Son distintas vistas útiles, pero no cuatro confirmaciones independientes. Tampoco hacen independientes a OI y gamma_share, ni a una SMA, un AVWAP y un pivote el hecho de tener nombres distintos. Dos proveedores del mismo precio no constituyen dos mecanismos. A la vez, distintas transformaciones de precio pueden aportar información de escala o plazo: compartir materia prima no vuelve inútil cada derivada; impide tratarlas sin justificación como votos estadísticamente independientes.

Propuesta: explicar por familia qué observación nueva aporta cada pieza y qué decisión cambia. Mantener familia de precio/estructura, actividad negociada, contratos de opciones y acontecimientos empresariales con dependencias explícitas; permitir que dentro de una familia haya dimensiones distintas sin multiplicar su independencia. Confluencia puede ser una descripción de alineación; no merece15 puntos extra por definición si ya remunera la misma señal en otros componentes.

No propondría cambiar hoy todos los pesos. Compararía tres diseños: rúbrica actual; componentes descritos sin bonus separado de confluencia; y una versión donde opciones es contexto/condición, sin cuota25 independiente. No redistribuir esos puntos mecánicamente ni usar la comparación para elevar niveles hasta70/85. El resultado deseable puede ser una tabla menor de evidencias y limitaciones en vez de otra suma.

Una estimación con pocos tests necesita incertidumbre, no solamente un techo. Como ilustración matemática, un intervalo Wilson95% para2/2 éxitos es aproximadamente34%–100%, frente a72%–100% para10/10. Incluso esos intervalos suponen ensayos independientes y una probabilidad estable, que aquí no están garantizados. Los contadores y caps actuales ayudan; añadir un intervalo sin reconocer dependencia tampoco calibraría el soporte. Para evaluar, agrupar episodios solapados y mostrar sensibilidad por régimen es más honesto que interpretar100% como certeza.

## 6. Casos locales ex ante: aportación y no aportación demostrables

Todos los valores siguientes pertenecen a capturas archivadas; no se usa el precio posterior ni se infiere rentabilidad. “Aporta” significa que distingue una pregunta con la información disponible, no que prediga retorno. Las rutas apuntan a originales completos; al ser JSON con datos repetidos se especifica el selector del bloque raíz.

| Caso y artefacto | Qué puede decidirse con ese dato | Qué no demuestra |
|---|---|---|
| [APP input16 oct16:14UTC](E:/stock-analysis-local/logs/batch/2026-10-16/15-58-24/adaptive/APP/input.json), slim.levels.put_walls_top, strike270: OI2619;16/23/30oct aportan1161/607/851; gamma722,843/87,784/84,761. | El vencimiento de hoy domina80,7% de gamma de ese strike pero44,3% de OI. Detalle31 distingue sensibilidad inmediata y contratos posteriores; dominante no es exclusivo. | Ninguna de las dos proporciones identifica signo neto dealer, continuidad de las posiciones o defensa futura. Tampoco justificaría eliminar automáticamente el nivel al vencer el primer bloque. |
| Mismo APP: expected_move15,85USD/5,82%, DTE7; RV20 semanal7,2%; iv_to_rv0,808; regla IV_CHEAP_LT_1_0 activada. | Identifica una comparación de medidas que realmente llega al indicador auxiliar. | No acredita IV barata, descuento económico ni cambio de Fortaleza. La objeción metodológica existe aunque la unidad porcentaje de este ejemplo sea correcta. |
| Mismo APP: support52_week_low260,59, prob_touch22,9%, raw strength9,5; reacción unavailable, pending_test_count1 con1sesión. | La ventana inmadura se distingue correctamente de fracaso; existe una coordenada de estructura con muestra de reacción insuficiente. | La etiqueta22,9% no estima toque correctamente;9,5 no es probabilidad ni fortaleza financiera. No obliga a seleccionar ni a vetar ese mínimo. |
| Mismo APP: perfil126 sesiones, bin_width7,5294, POC317,0603. | Expone resolución y aproximación; permite saber que el nodo no es una transacción precisa observada. | Cuatro decimales no autorizan precisión al céntimo; no se identifica el perfil intradía real. |
| [APP captura técnica39,21:07UTC](E:/stock-analysis-local/logs/deploy_origins39/live-source.json), slim raíz levels.option_origins: put255 disponible fuera del TOP; OI1391/655/297 en16/23/30oct. | El cambio de representación recupera una identidad solicitada que el ranking omite. Distingue falta de observación y desaparición;255 conserva datos de plazos posteriores. | Esta captura posterior es solo demostración técnica39, no información retroactivamente disponible al modelo de16:14 ni recuperación financiera del APP fallido. Disponible tampoco significa compra viable ni liquidez: bid0/ask0,25 en el bloque16 oct. |
| [PLTR input16 oct](E:/stock-analysis-local/logs/batch/2026-10-16/15-58-24/adaptive/PLTR/input.json): quote187,255; TOPputs190–200. | Ordenar lado/ubicación impide llamar soporte inferior a cualquier put. | El tipo put no transforma un strike superior en compra actual; corregir el bug de distancia no probaría la causalidad del wall. |

Agregación adicional del conjunto completo de **46 inputs**16 oct, incluidos los de intentos no publicados:230 filas TOPput,193 con vencimiento dominante16 oct;24 tickers tienen las cinco filas dominantes ese día. Es un conteo de filas de strike, no193/230 del nocional ni de zonas elegidas. Todos los46 inputs incluyen porcentajes de toque en algún support:111 filas. gamma_regime resulta negative en36 y positive en10; son salidas del proxy, no36 inventarios dealer cortos observados. Esto demuestra exposición al supuesto y desajuste potencial del horizonte, no uso causal por el modelo ni resultado económico.

La integración de la auditoría también encontró selección con Opciones=0 en25/71 zonas de45 publicaciones16 oct; véase [descriptivos del informe](E:/stock-analysis-local/docs/audit_work_20261017/methodology_descriptive_cases.json). Esa contraevidencia impide afirmar que opciones sea requisito universal de compra. No prueba que su peso no influya en categorías, orden o exclusión de otras candidatas.

## 7. Matriz de oportunidades, carencias y descartes

Estado describe capacidad actual: **E** existente explícita; **I** indirecta/parcial; **N** no disponible; **D** descartada como incorporación por defecto. Una ausencia N no implica un defecto. Coste bajo/medio/alto es relativo de ingeniería/datos, no presupuesto monetario cotizado. Todas las propuestas de producción pueden usar la misma llamada financiera: **0 llamadas LLM adicionales**. Experimentos que requieran nuevas respuestas necesitarían un presupuesto posterior específico; no se ejecutaron.

| Propuesta | Estado actual / carencia principal | Decisión propuesta y coste incremental | Utilidad que tendría que demostrar |
|---|---|---|---|
| Identidad dirigida y detalle por expiración | E39/E31; falta de alcance completo deliberada | Conservar; cero descargas extra para misma muestra; coste bajo de mantenimiento | Evitar falsa desaparición y permitir distinguir contribuciones. Ya hay caso técnico positivo, no prueba alpha. |
| Timestamp de OI/gamma/quotes, multipliers y raíz | I; datos parcialmente suministrados pero descartados / contrato temporal insuficiente | Preservar antes de recalcular; ingeniería baja,0 datos extra cuando el wire lo trae | Misma observación no cambia de unidad ni rejuvenece; incertidumbre temporal explícita. |
| Separación de elegibilidad por consumidor | I; parser gamma condiciona OI/EM/maxpain | Corregir adquisición; coste bajo/medio,0 modelos | Métricas no pierden contratos por un campo que no utilizan; bases comparables. |
| Signo neto dealer | N; falta de datos de cartera/participante | Dejar desconocido; retirar atribución conocida. Escenarios locales baratos | Conclusión robusta a signos plausibles; si no, abstención sobre el mecanismo. |
| Dealers/flujo open-close clasificado | N; feed/historia/cobertura y capacidad de reconstrucción | D como requisito inicial; investigación futura condicionada, coste alto de datos/ingeniería | Aporte incremental a3/5 sesiones sobre OI simple, no reproducir un paper con otra variable. |
| Contribución por horizonte3/5/10/20 | I por expiraciones31; falta cálculo y definición | Separar descriptivamente, coste bajo, mismos datos; obtener cadenas adicionales solo si una evaluación lo justifica | Saber qué respaldo observado caduca antes del horizonte sin inferir ruptura automática. |
| Persistencia por identidad en el tiempo | I por snapshots/continuidad; no panel homogéneo de contratos | Conservar panel reducido y cobertura, coste medio de almacenamiento/cálculo | Distinguir roll, precio y cambio real de posiciones; menor falso relato de pérdida/ganancia. |
| EM por vencimiento/calidad | E como straddle; falta reloj y semántica consistentes | Sustituir escala semanal ficticia por prima/plazo explícitos y sensibilidad; coste bajo/medio | Mejor medición sin ampliar llamadas ni prometer68%. |
| Skew/estructura temporal y riesgo de evento | I por expiraciones/quotes; faltan IV preservadas, cobertura e interpretación | Candidato después de saneamiento, coste medio;0 llamadas LLM; más datos solo si faltan strikes/plazos | Explicar asimetría o incertidumbre de eventos mejor que EM único; no otra señal de soporte sin causalidad. |
| Probabilidad de toque calibrada | N; hay fórmula de otro objeto | Retirar porcentaje actual; candidato futuro con modelo estadístico y etiquetas claras, coste medio/alto | Calibración/valor de decisión frente a base simple; rechazo si solo aumenta apariencia de precisión. |
| Max pain | E; falta validación útil, no falta parser | Eliminar del argumento de compra por defecto; coste bajo | Retenerlo solo si comparación ciega acredita aporte incremental específico de horizonte. |
| Perfil diario | E approximate; distribución por precio no identificable | Mantener como mapa aproximado si aporta; regiones/sensibilidad; coste bajo | Estabilidad espacial y aporte frente a sin perfil. |
| Perfil de trades intradía | N; falta dato y procesamiento | D como requisito inmediato; candidato si falla aproximación de forma relevante, coste alto | Mejor selección a3/5/10/20, no simplemente gráfico más preciso. |
| Libro/OFI/footprint intradía | N; falta dato, reloj y modelo de ejecución | D para el núcleo swing actual; coste alto/operativo continuo | Pregunta de ejecución concreta y beneficio neto, no extrapolar estudios de segundos/minutos. |
| Reacciones con MAE/MFE/orden/dirección | I; existe high5d y madurez | Conservar eventos/serie y calcular varias dimensiones, coste medio,0 datos nuevos prospectivamente con OHLCV conservado | Separar rebote después de deterioro de una defensa útil; declarar ambigüedad diaria. |
| Dependencia y error de muestra | I por caps/measurement_basis; falta cuantificación y eventos | Estabilidad y agrupación por episodios, coste medio; no descuento automático repetido | Menos confianza espuria, mejor comparación de muestras sin fingir independencia. |
| Confluencia y notas auxiliares | E; falta validación incremental | Comparar sin bonus/etiquetas redundantes; coste bajo de contexto, evaluación posterior | Igual/mejor decisión con menos duplicación e inestabilidad. |
| Vanna/charm, squeeze score, gamma flip modelado | N o no preservados; falta signo, IV temporal y calibración | D como siguiente paso por defecto | Solo estudiar si mecanismos simples y datos firmes dejan una pregunta material sin responder. Más griegas no identifican inventario. |

## 8. Comparaciones futuras específicas de este dominio

El diseño general de evaluación, separación temporal, corrección por múltiples pruebas y utilidad del producto corresponde al informe principal. Aquí se precisa qué comparar. No se ejecutó backtest y ninguna fila implica nueva política automática.

| Pregunta | Referencia y alternativa | Medida y control necesarios | Criterio de adopción o retirada |
|---|---|---|---|
| ¿Aportan las opciones a elegir soporte? | Misma información empresarial/precio y conjunto de candidatos; actual frente a sin Opciones, concentración sin signo y desglose por horizonte | Candidatas ex ante, cobertura y casos sin zona;3/5/10/20 sesiones; toque separado de MFE/MAE y retorno terminal. Controlar vencimiento, evento, liquidez y distancia. | Mantener complejidad/peso solo si mejora fuera de muestra una utilidad predefinida con incertidumbre y estabilidad. Si solo cambia categoría sin mejor decisión, reducir o retirar. |
| ¿Gamma domina a OI simple? | OI por identidad/expiración frente a gamma absoluta y, si se obtuviera, neta observada | Misma muestra de contratos y fechas; cero desconocido separado; registrar rango de sensibilidad por signo | No confundir más ajuste contemporáneo con predicción. El proxy de signo no se adopta porque correlacione en una muestra sin estabilidad. |
| ¿Hay señal max pain independiente? | Precio/ATR, strikes próximos y concentración como base; añadir solo max pain | Cambios de selección y error por distancia/DTE; comparar también contra strike redondo/vecino comparable | Retirar si no supera esas referencias; pinning solo en vencimiento no autoriza semanas. |
| ¿Mejora medir volatilidad en vez de EM ambiguo? | RV20/60 con reloj común; prima ATM observada; IV comparable y estructura temporal | Error/coverage de rangos a cada horizonte, sesgo alrededor de earnings, misma disponibilidad ex ante | Preferir la medida sencilla con calibración estable; si se ofrecen probabilidades exigir Brier y calibración, no cobertura lograda ampliando rangos sin límite. |
| ¿El perfil añade información a los niveles de precio? | Sin perfil; diario actual; mapa estable entre resoluciones; trades intradía solo después | Cambio de candidatos, estabilidad por bin/ventana, aporte incremental con costes y definición del horizonte | Si diario y sin perfil empatan, no financiar intradía sin hipótesis adicional. Si binning domina el resultado, reducir precisión/uso. |
| ¿Reacciones distinguen una defensa útil? | High5d actual frente a eventos con MAE/MFE/cierre y episodios no solapados | No exigir que la selección futura cumpla el antiguo umbral: evaluar varios resultados. Fechar creación del nivel y parámetros. | Sustituir etiqueta defensa si oculta recorridos adversos; no convertir retrospectivamente nuevas etiquetas en fallo del informe antiguo. |
| ¿Confluencia/confidence mejoran lectura o sesgan? | Datos primitivos iguales, con/sin notas raw y bonus separado | Evaluación ciega de coherencia/decisión, desacuerdo, contexto/tokens y falsas certezas; posteriormente utilidad de selección | Conservar solo información marginal. Eliminar notas si no aportan o son interpretadas como probabilidades. |

Una selección vacía puede acertar. La evaluación debe incluir abstenciones y oportunidades descartadas; aumentar cobertura, frecuencia de compra o puntuación media no es un objetivo. Tampoco basta con que una zona sea tocada: una zona que atrae precio y falla inmediatamente puede servir como información de riesgo sin ser una buena compra.

## 9. Fuentes primarias anotadas y límites de extrapolación

Consultadas17-10-2026. Resúmenes breves; sin copiar largos pasajes. La evidencia positiva, la contraevidencia y las propuestas propias están separadas. Documentación de proveedor define datos; no es validación predictiva. Un paper empírico respalda su muestra/método, no los pesos del sistema.

- **OIC/OCC, [General Information](https://www.optionseducation.org/referencelibrary/faq/general-information).** Referencia operativa sobre contratos, OI al cierre y liquidez, no estudio de retornos. Sirve para delimitar qué está observado. No aporta muestra ni horizonte swing ni justifica porcentajes de Fortaleza.
- **Xu/Cboe2023, [Much Ado About0DTEs](https://www.cboe.com/insights/posts/volatility-insights-evaluating-the-market-impact-of-spx-0-dte-options/).** Datos propios SPX y posiciones por participante/lado; análisis intradía. Distingue bruto de neto y documenta compensación de flujos. Evidencia útil sobre identificabilidad y escalas, con interés comercial del editor. No extrapolar SPX centralizado a cada acción ni a soporte de semanas.
- **Amaya, Garcia-Ares, Pearson y Vasquez2025, [0DTE Index Options and Market Volatility](https://cdn.cboe.com/resources/education/research_publications/gammasqueezes.pdf).** SPX/SPXW, julio2020–junio2023, posiciones netas reconstruidas por minuto; modelos GARCH/lineal y contrafactuales de volatilidad diaria/30min. Encuentran efectos limitados respecto a variación habitual, con dependencia del modelo. No experimento aleatorio; no muestra de compras en acciones ni validación de gamma bruto. Contraevidencia a que nocional enorme implique inevitablemente impacto enorme.
- **Ni, Pearson y Poteshman2005, [Stock Price Clustering on Option Expiration Dates](https://www.sciencedirect.com/science/article/pii/S0304405X05000577).** Acciones estadounidenses con opciones1996–2002, cierres y comparación de vencimientos/no vencimientos; evidencia de clustering local y mecanismos de cobertura/manipulación. Es evidencia favorable de efectos de opciones bajo condiciones concretas. No valida max pain global, dirección dealer inferida por tipo ni durabilidad3–20 sesiones.
- **Ni, Pearson, Poteshman y White2021, [Does Option Trading Have a Pervasive Impact…](https://academic.oup.com/rfs/article-abstract/34/4/1952/5873587).** Publicación RFS, abstract primario accesible: evidencia de reequilibrio de coberturas sobre volatilidad y grandes movimientos de acciones. El texto completo publicado no estuvo accesible aquí; no se imputan su muestra/coefs desde versiones preliminares. Refuta descartar todo mecanismo de opciones, pero no acredita la implementación ni permite cuantificar utilidad local.
- **Gârleanu, Pedersen y Poteshman2009, [Demand-Based Option Pricing](https://pages.stern.nyu.edu/~lpederse/papers/DBOP.pdf).** Modelo de cobertura imperfecta y datos de posiciones de dealers/clientes en opciones de índice y acciones. Demanda afecta precios de opciones y sus riesgos no cubribles; evidencia de por qué precio implícito incluye presión de demanda. Su objeto es valoración/estructura de opciones, no un pronóstico de rebote en un strike ni pesos para compras swing.
- **Pan y Poteshman2006, [The Information in Option Volume for Future Stock Prices](https://www.mit.edu/~junpan/5919.pdf).** Ratio de volumen iniciado por compradores para abrir; evidencia a siguiente día/semana y distinción de componentes públicos/no públicos. Fuente del autor, versión previa a publicación. Muestra histórica de acciones/Cboe, no contratos Tradier actuales; no se reestima aquí. Motiva estudiar flujo clasificado; no usar OI agregado como sustituto ni prometer reproducir rentabilidades históricas.
- **Osler2000, [Support for Resistance](https://www.newyorkfed.org/research/epr/00v06n2/0007osle.html).** Niveles proporcionados por seis firmas de divisas1996–98 y cambios intradía; resultados favorables, heterogéneos por firma/par. Es un comparador metodológico útil porque niveles eran suministrados antes del movimiento. Que la vigencia predictiva de niveles alcance varios días en ese estudio no demuestra que una compra en acciones sobreviva varias semanas.
- **Osler2001/2003, [Currency Orders and Exchange-Rate Dynamics](https://www.newyorkfed.org/research/staff_reports/sr125.html).** Órdenes stop/take-profit de un gran banco FX muestran agrupación y mecanismos diferentes. Evidencia microestructural con datos de órdenes reales. No se pueden inferir esos flujos desde OHLCV o etiquetas de opciones de acciones; no prueba de que todos los números redondos sean soportes.
- **Cont, Kukanov y Stoikov2014, [The Price Impact of Order Book Events](https://arxiv.org/html/1011.6402v3).**50acciones S&P500 seleccionadas aleatoriamente, TAQ abril2010; cambios de precio en intervalos cortos explicados por desequilibrio de eventos del libro y profundidad. Modelo empírico de impacto intradía, con volumen agregado menos informativo. Sirve para separar microestructura observada de narración sobre volumen; no valida alpha swing ni exige contratar datos de libro para este producto.
- **Cboe, [VIX Methodology](https://cdn.cboe.com/resources/vix/VIX_Methodology.pdf).** Construcción de volatilidad implícita30d de SPX con varios strikes/vencimientos. Es definición de índice, no validación de probabilidades físicas de tocar niveles. Útil para distinguir varianza implícita y una prima ATM; no receta obligatoria para acciones individuales.
- **Tradier, [Market Data](https://docs.tradier.com/docs/market-data) y [Quotes](https://docs.tradier.com/docs/quotes).** Documentación de frecuencia, identificación, timestamps y multiplicador; permite comparar semántica del proveedor con campos preservados. No certifica frescura de cada original ni valida gamma estimada. Algunos datos faltantes podrían conservarse sin nuevas peticiones; no se comprobó su presencia en XML históricos no retenidos.
- **Cboe DataShop, [Open-Close Volume Summary](https://datashop.cboe.com/cboe-options-open-close-volume-summary).** Especificación comercial de desglose por participante, lado y apertura/cierre en bolsas Cboe. Su alcance es parcial para acciones negociadas en múltiples plazas; disponibilidad de producto no implica que cierre todas las lagunas de inventario. Se consultó capacidad, no precio ni licencia adquirida.

## 10. Reproducción descriptiva conservada

Los dos bloques siguientes se ejecutaron con la venv local: salida correcta y stderr vacío. Código de lectura local, sin imports del runtime de producción, sin red ni escrituras. Python estándar; invocarlo con la venv del repositorio si se desea repetir después. Verifica los denominadores nuevos y los campos de APP. No vuelve a generar análisis ni mide resultados futuros.

```python
import json
from pathlib import Path

ROOT = Path(r'E:/stock-analysis-local')
BASE = ROOT / 'logs/batch/2026-10-16/15-58-24/adaptive'
rows = []
for path in sorted(BASE.glob('*/input.json')):
    payload = json.loads(path.read_text(encoding='utf-8-sig'))
    slim = payload['slim']
    puts = slim['levels'].get('put_walls_top', [])
    supports = slim['levels'].get('supports', [])
    rows.append({
        'symbol': payload['symbol'],
        'put_count': len(puts),
        'dominant_today': sum(x.get('expiration') == '2026-10-16' for x in puts),
        'prob_count': sum(x.get('prob_touch_1w_pct') is not None for x in supports),
        'gamma_regime': slim.get('options', {}).get('gamma_regime'),
    })
print('inputs', len(rows))
print('TOP puts', sum(x['put_count'] for x in rows))
print('dominant 16Oct', sum(x['dominant_today'] for x in rows))
print('all 5 dominant 16Oct', sum(x['dominant_today'] == 5 for x in rows))
print('inputs with probability', sum(x['prob_count'] > 0 for x in rows))
print('support probabilities', sum(x['prob_count'] for x in rows))
print('regimes', {key: sum(x['gamma_regime'] == key for x in rows)
                  for key in sorted({x['gamma_regime'] for x in rows})})
app = json.loads((BASE / 'APP/input.json').read_text(encoding='utf-8-sig'))['slim']
wall = next(x for x in app['levels']['put_walls_top'] if x['level'] == 270)
parts = wall['option_details']['by_expiration']
for key in ['aggregate_oi', 'gamma_usd_millions']:
    values = [x[key] for x in parts]
    print(key, values, 'fraction first expiry', values[0] / sum(values))
print('APP volatility', app['options'])
print('APP supports', app['levels']['supports'])
# Expected counts: 46, 230, 193, 24, 46, 111; regimes negative36/positive10.
```

Contraejemplos matemáticos mínimos, independientes de datos reales y sin pretensión de modelo financiero:

```python
import math
z = 1.0
terminal = 0.5 * math.erfc(z / math.sqrt(2))
first_passage = 2 * terminal  # Brownian arithmetic, zero drift, continuous monitoring ONLY
print('terminal / touch at d=sigma_H:', terminal, first_passage)
print('E|Normal(0,sigma)| / sigma:', math.sqrt(2 / math.pi))
# 0.158655..., 0.317310...; 0.797884...
# Same public OI/gamma, different possible signed inventories:
gamma_call = gamma_put = 1.0
print('calls-minus-puts proxy:', gamma_call - gamma_put)
print('both dealer long:', gamma_call + gamma_put)
print('both dealer short:', -gamma_call - gamma_put)
```

Estas reproducciones no determinan qué inventario existió ni qué probabilidad verdadera tenía APP. Conservan la diferencia entre lo calculado, lo observable y lo que sigue siendo hipótesis.
