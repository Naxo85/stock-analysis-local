# Especificacion auditable de la hoja Mercado

Este documento explica que significa cada elemento visible de `Mercado`. No
convierte una regla tecnica heredada en una regla de inversion aprobada.

## Estados

- `Acordado`: comportamiento discutido y aceptado para el sistema nuevo.
- `Caracterizado`: comportamiento legacy reproducido con evidencia, pendiente
  de decidir si debe mejorarse.
- `Prototipo`: visible en la hoja de prueba, pero aun no conectado al runtime.
- `Pendiente`: falta una definicion o decision verificable.

## Fuentes de verdad

- Geometria, colores y umbrales visuales:
  `config/market_sheet_layout.json`.
- Formulas legacy recuperadas:
  `docs/baseline/sheet_formulas_2026-09-05.md`.
- Arquitectura y propietarios de los datos:
  `docs/plan_reconstruccion_sistema.md`.
- Estrategia de inversion: documento independiente; ninguna formula de esta
  hoja constituye por si sola una orden de compra o venta.

## Columnas visibles

| Columna | Valor mostrado y calculo | Propietario futuro | Estado |
|---|---|---|---|
| # / Banda | Columna estrecha a la izquierda del ticker. El color identifica el subsector y el numero muestra la suma de shots abiertos en todo ese subsector, repetida junto a cada componente. Se actualiza desde `config/portfolio.json`. | controller/renderer | Implementado; clasificacion, paleta y cartera declaradas en configuracion |
| Ticker | Simbolo normalizado, identidad estable de fila y enlace `https://finance.yahoo.com/quote/{ticker}/`. Antes de escribir se resuelven las filas reales. `#00FFFF` indica1shot y `#00B8D4` indica2o más; earnings conserva símbolo/fondo: naranja fino2–7días, rojo grueso hoy/mañana y fecha en nota. | controller/renderer | Enlace/cartera/earnings implementados; earnings activado21Oct y verificado LRCXK8rojo |
| Valor | Precio util de Tradier. En mercado regular usa `last`; en premarket y postmarket usa el punto medio del `bid/ask` solo si ambas puntas tienen menos de 15 minutos y la horquilla no supera el 5% del punto medio. Si la cotizacion extendida es antigua o demasiado ancha, conserva `last` para no fabricar movimientos con liquidez inexistente. Los 47 precios se solicitan en una llamada por lote; no existe fallback exclusivo a Yahoo. | market-worker | Implementado; publicacion cloud periodica activa y validada |
| Dia | `(precio_actual / cierre_de_la_ultima_sesion_completa) - 1`. En premarket, mercado regular y postmarket el numerador es el precio vivo correspondiente y la referencia es el ultimo cierre anterior; en fin de semana o festivo bursatil se conserva el movimiento de la ultima sesion. | market-worker | Implementado y caracterizado |
| Fuerza | `10 * (0,8 * percentil(5d / Vol) + 0,2 * percentil(20d / Vol))`, redondeado a dos decimales. La muestra incluye conjuntamente los 47 tickers de todas las tablas. Como en legacy, un ratio ausente o con volatilidad cero se convierte en cero. | market-worker | Implementado con universo global; metodologia pendiente de auditoria financiera |
| 5d | `precio_actual / cierre_de_referencia_5 - 1`. La referencia es el cierre situado cinco sesiones antes del ultimo cierre completo; durante la sesion el numerador es vivo. | market-worker | Implementado y caracterizado |
| 20d | Igual que `5d`, usando veinte sesiones. | market-worker | Implementado y caracterizado |
| Vol | `ATR20 / ultimo_cierre`. Limita cada True Range al 25% del cierre anterior, recorta el 10% inferior y superior y aplica Wilder a la serie ordenada y recortada. | market-worker | Implementado con paridad; metodologia pendiente de auditoria financiera |
| DD6M | Muestra `precio_actual / maximo_de_cierre_de_126_sesiones - 1`. Si el precio vivo marca maximo, vale cero. El color usa el percentil de severidad frente a ventanas equivalentes de hasta 756 sesiones. Las celdas no repiten notas; la cabecera explica los cortes de color. No es una senal de compra. | market-worker | Implementado y caracterizado |
| Ent. | Rango de soporte operativo normal extraido de un analisis validado. Su fondo se recalcula con cada cotizacion: morado bajo el rango, verde intenso dentro o hasta 0,5% por encima, verde claro entre 0,5% y 1,5% por encima y fondo base mas lejos. La nota muestra el stop como distancia al punto medio de este soporte, no al precio vivo. | analysis-agent/renderer + market-worker para el fondo | Implementado |
| Wash. | Rango de soporte mas profundo extraido de un analisis validado. Aplica la misma proximidad dinamica. La distancia porcentual de su stop usa el punto medio de Washout, de forma independiente a Entrada y al precio vivo. | analysis-agent/renderer + market-worker para el fondo | Implementado |
| Res. | Resistencia estructural mas fuerte del analisis, independiente del objetivo operativo y sin penalizacion por distancia. Solo es visible con fortaleza solida o superior (>=70/100). Su fondo es azul brillante dentro o hasta 0,5% por debajo de la zona y azul suave entre 0,5% y 1,5% por debajo. La nota muestra distancia, fuerza 0-100, desglose y factores. | analysis-agent/renderer + market-worker para el fondo | Implementado |
| Nota | Valoracion sintetica del analisis en escala 0-10 y enlace al informe HTML renderizado. No representa por si sola el estado de la tesis: una nota baja no significa tesis rota. | analysis-agent | Separacion entre nota y tesis acordada; rubrica completa pendiente de auditoria |

La sincronizacion de analisis tolera altas incompletas: publica todos los
informes validos y deja vacias solamente `Ent.`, `Wash.`, `Res.` y `Nota` del ticker que
aun no tenga informe. Una ausencia no borra ni bloquea los valores del resto.

## Resumen de grupos

El resumen ocupa `A:H`, una fila vacia debajo del bloque superior. El selector
de orden comparte altura con `Trading/Core`, en `C9:C10`; por eso el titulo del
resumen empieza en la fila 12, la cabecera en la 13 y cada grupo desde la 14:

```text
Sector / Grupo | Banda | ETF | Dia | 20d | DD6M | Pos. | Shots
```

Las tres magnitudes de mercado se calculan en `stock-controller` con datos de
Tradier y se escriben como valores numericos en la misma publicacion que las
siete columnas de los tickers.
La hoja `AuxMercado` y `GOOGLEFINANCE` ya no participan en el runtime.

- `Dia`: precio actual dividido por el cierre de la sesion anterior menos uno.
- `DD6M`: exactamente el mismo calculo que en los tickers: precio actual frente
  al maximo de cierre de las ultimas 126 sesiones. Si el precio actual marca
  maximo, vale cero. El percentil no se muestra numericamente, pero aplica los
  mismos cortes de color que las tablas: rojo desde 95, rosa entre 90 y 94 y
  sin color por debajo de 90.
- `20d`: retorno de una ventana de 20 sesiones que incluye la sesion actual;
  por tanto la referencia es el cierre de la primera de esas 20 sesiones.
- `Pos.` cuenta tickers del grupo presentes en cartera y `Shots` suma sus shots
  en `config/portfolio.json`. Ambos incluyen conjuntamente las dos tablas.
El retorno de 20 sesiones de `QQQ` se muestra una sola vez en el panel general
central; no se repite en cada grupo.

## Panel general

El panel ocupa exclusivamente `A2:A10`; la columna `A` mide 180 px y queda a
la izquierda de las dos tablas de tickers. No pertenece a ninguna tabla. Su
contenido es:

```text
Regimen de riesgo: puntuacion/100
VXN: regimen

QQQ Dia: porcentaje
QQQ 20d: porcentaje
Nasdaq: porcentaje vs max. 6m

Trading: dd/MM/yyyy
Core: dd/MM/yyyy
```

Las lineas de regimen y VXN se muestran en negrita. En las lineas de fecha,
solo las palabras `Trading` y `Core` van en negrita; los dos puntos y la fecha
mantienen el peso normal.

- `QQQ Dia` y `QQQ 20d` usan Tradier y las mismas definiciones que el resumen
  de grupos. `Nasdaq: ... vs max. 6m` conserva en cambio la definicion legacy:
  precio vivo de QQQ frente al maximo intradia de las ultimas 126 sesiones.
  Por eso puede ser algo mas negativo que el `DD6M` basado en cierres.
- La puntuacion de riesgo conserva la formula legacy caracterizada. Parte del
  CNN Fear & Greed y suma el ajuste de nivel VXN: `+4` por debajo de 20, `0`
  entre 20 y 25, `-8` entre 25 y 30, `-15` entre 30 y 35 y `-25` desde 35.
  Ademas resta `18` si VXN sube al menos un 20% en el dia, resta `10` si sube
  al menos un 10% y suma `5` si cae al menos un 10%. El resultado se redondea
  y limita a 0-100.
- La linea de riesgo antepone el punto de color de su tramo y conserva en su
  nota la fecha y fuente del sentimiento, la leyenda de puntuaciones y la
  explicacion del ajuste.
- Los regimenes de riesgo son `Strong Risk-on` desde 76, `Risk-on` desde 56,
  `Mixto` desde 45, `Risk-off` desde 25 y `Strong Risk-off` por debajo de 25.
- La linea VXN muestra solo su regimen: `tranquilo`, `normal`, `tension`,
  `risk-off` o `shock`, con los mismos cortes 20/25/30/35. Su nota independiente
  contiene valor, variacion diaria, timestamp y fuente de Yahoo, junto con la
  leyenda de esos tramos. El timestamp es el de la ultima cotizacion real de
  `^VXN`, no el del refresco de la hoja: antes de su sesion y despues de un
  festivo puede corresponder al cierre de varios dias antes.
- CNN se obtiene del proxy existente, que es el unico propietario de su cache
  de 15 minutos. El controlador no añade otra ventana que pueda retrasar el
  timestamp. VXN hace una unica consulta de la serie `^VXN` a Yahoo y se reutiliza
  durante 5 minutos; Yahoo no se usa para los tickers ni para QQQ.
- `Trading` y `Core` son la fecha, en zona Europe/Madrid, del `finished_at` de
  `runtime/analysis-status/latest_trading.json` y `latest_core.json` del bucket
  nuevo. Mientras el motor de analisis siga en legacy, cada batch copia alli un
  contrato minimo al terminar. Sus notas reproducen el desglose `model_usage`
  del batch: rutas base, revisiones, publicados, referencias conservadas y
  fallos. Esta dependencia es transitoria hasta migrarlo.
- Si una fuente auxiliar falla, su linea muestra `N/D` y el snapshot conserva
  el error; las siete columnas de mercado no se presentan como fallidas por una
  indisponibilidad temporal de CNN, VXN o de las fechas de analisis.

La clasificacion de grupos actual es:

| Bloque | Tickers | Benchmark provisional |
|---|---|---|
| Cuantica | IONQ, QBTS | QTUP |
| Memoria | MU, SNDK, WDC | DRAM |
| Espacio y defensa | RKLB, ASTS, SPCX, KTOS | UFO |
| Chips y hardware | AMD, MRVL, CRDO, INTC, QCOM, CLS, TSM, NVDA | SOXX |
| Nuclear y red | LEU, CCJ, OKLO, TLN, GEV | NLR |
| Infraestructura IA | NBIS, CRWV, IREN, CIFR | AIQ |
| Plataformas IA | PLTR, APP, RDDT, INOD, GOOG | IGV |
| Fintech y cripto | HOOD, SOFI, COIN, IBKR | FINX |
| Equipamiento chips | LRCX, AMAT, ASML | EUV |
| Minerales criticos | MP, USAR | REMX |
| Biotecnologia | MRNA | XBI |
| Autonomia | AUR, TSLA | DRIV |
| Salud digital | HIMS | IHF |
| Industriales | RTX, CAT | XLI |

`Ent.`, `Wash.` y `Nota` se publican desde el ultimo informe estructurado y
validado disponible para cada ticker. El refresco intradia no las toca; un
sincronizador independiente las actualiza solo cuando cambia algun informe.

Los grupos buscan utilidad para observar movimientos conjuntos. No afirman que
todos sus componentes tengan el mismo negocio o factor de riesgo. La auditoria
de representatividad y las limitaciones de cada proxy se mantienen en
`docs/benchmark_audit_2026-09-05.md`.

La hoja contiene dos tablas nativas balanceadas: 24 tickers a la izquierda y 23 a la derecha. La izquierda ocupa
`J:U` y la derecha `W:AH`; no representan universos Trading/Core diferentes.
Su contenido depende del orden global elegido y puede mezclar grupos en ambos lados.

El resumen de grupos empieza ahora en la fila 12 y ocupa `A:H`, en paralelo a
las tablas de tickers. Su posicion se deriva del final del bloque superior de
`A`; no es una fila absoluta. `A` combina sector y grupo, `B` conserva la banda de color sin
texto y `C` contiene el ETF. `I` separa el resumen de la tabla izquierda y `V`
separa las dos tablas; ninguna de esas columnas contiene datos ni logica.

Las dos superficies de tickers siguen siendo tablas nativas de Google Sheets,
pero forman una sola lista logica. `C9:C10` ofrece tres ordenes globales:
`Nota`, `Sector` y `Fuerza`. Cada publicacion ordena los 47 tickers, coloca
los primeros 24 a la izquierda y los 23 restantes a la derecha. `Sector` usa el
orden declarado de los grupos de color y conserva el orden relativo dentro de
cada grupo. Antes de escribir, cada proceso resuelve ticker, fila y tabla, y
cancela la publicacion si detecta ausencias, duplicados o simbolos inesperados.

Los valores 47, 24 y 23 describen el universo actual, no una restriccion. El
manifiesto deriva el total desde `groups`, asigna `ceil(N/2)` filas a la tabla
izquierda y `floor(N/2)` a la derecha, y desplaza automaticamente las filas de
separacion, el resumen y el limite inferior de la hoja.

## Reglas visuales definidas

| Campo | Condicion | Presentacion |
|---|---|---|
| Dia | `> 0` | Fondo `#E6F4EB`, texto `#137A49` |
| Dia | `< 0` | Fondo `#FDEBEB`, texto `#B32318` |
| Fuerza | `> 8` | Fondo `#00FF00` |
| Fuerza | `> 6` y `<= 8` | Fondo `#B7E1CD` |
| Vol | `>= 6%` | Fondo `#00FF00` |
| Vol | `<= 3%` | Fondo `#F4CCCC` |
| Vol | `> 3%` y `< 6%` | Conserva el fondo blanco de la tabla |
| DD6M | percentil `>= 95` | Fondo `#E06666` |
| DD6M | percentil `>= 90` y `< 95` | Fondo `#F4CCCC` |
| 5d y 20d | cualquier valor | Sin color analitico; conserva el fondo blanco de la tabla |
| Ent. y Wash. | precio por debajo del rango | Fondo `#D9D2E9` |
| Ent. y Wash. | dentro o hasta 0,5% por encima | Fondo `#00FF00` |
| Ent. y Wash. | entre 0,5% y 1,5% por encima | Fondo `#D9EAD3` |
| Ent. y Wash. | mas de 1,5% por encima o nivel ausente | Fondo normal de la fila |
| Res. | dentro o hasta 0,5% por debajo | Fondo `#00B0F0` |
| Res. | entre 0,5% y 1,5% por debajo | Fondo `#CFE2F3` |
| Res. | mas de 1,5% por debajo, por encima de la zona o nivel ausente | Fondo normal de la fila |
| Resto de casos | sin umbral aplicable | Conserva el fondo blanco de la tabla |

Los colores de `Dia`, `Fuerza`, `Vol` y `DD6M` se recalculan en la
publicacion intradia. Los de `Ent.`, `Wash.` y `Res.` se recalculan cuando cambia un
informe validado; ninguno depende del formato previo de la fila.

La geometria exacta de `A:AJ`, el panel `A2:A10`, el selector `A12:A13`, las dos tablas y el resumen `A:H`, anchos,
altos, colores, alineacion, enlaces y la fuente Arial de 10 puntos de las tablas y del panel lateral esta declarada
en `config/market_sheet_layout.json`. El reconciliador elimina las antiguas
estructuras incompatibles, conserva un rango con nombre para el resumen y puede
restaurar las tablas nativas con sus controles. Cada publicacion
intradia reaplica anchos, alineacion, contorno y separadores verticales despues
de `Dia`, `20d`, `Vol` y `DD6M` para corregir cambios accidentales.
Tambien elimina cualquier borde horizontal interno heredado: las lineas de
grupo antiguas no tienen significado dentro del orden global.

## Reglas visuales aun incompletas

- Earnings definido/activado21Oct: naranja fino2–7días, rojo grueso hoy/mañana, fecha en nota; LRCXrojo verificado. [Contrato](decisions/0008-avisos-de-resultados.md).
- Estado visual de dato ausente, dato obsoleto y error de proveedor.

### Contrato de las columnas de analisis

`Ent.` muestra `plan.entry`; `Wash.` muestra `plan.ambitious_entry`; `Res.`
muestra `plan.resistance` solo si su fortaleza es al menos 70/100; y `Nota`
muestra `decision.score` con un decimal y
enlace al informe HTML. Los rangos usan un decimal y coma decimal.

La nota emergente del soporte puede contener `Stop` y `Fortaleza`. La de
`Res.` contiene distancia, fortaleza, desglose y factores. Cada precio incluye
su distancia porcentual respecto al `Valor`
vivo. No se calcula ningun stop nuevo: se descarta cualquier stop del informe
que no quede por debajo del soporte correspondiente. `plan.target` conserva su
funcion de salida operativa y no se reutiliza como resistencia. La fortaleza
solo aparece cuando el informe la declara de forma explicita.

Como defensa ante informes historicos mal parseados, los niveles cuya escala
sea imposible frente al precio de referencia se rechazan. Solo se corrige un
factor `x1000` cuando esa transformacion devuelve el nivel a una relacion
plausible; esta proteccion no crea niveles ni altera rangos validos.

La celda `Nota` conserva el fondo normal salvo dos avisos heredados: amarillo
si se retiene una referencia anterior por baja confianza, y verde o rojo si la
nota cambia al menos 0,5 puntos. La nota emergente explica esos casos.

## Trazabilidad minima exigida

Para cada celda calculada, el snapshot del sistema nuevo debera poder explicar:

```text
valor + timestamp + sesion + proveedor + datos de entrada + version del calculo
```

Para cada dato decidido por el modelo debera conservar ademas el analisis
validado, la version del prompt, la evidencia utilizada y cualquier advertencia
de validacion. Esto permite reconstruir por que la hoja mostraba un valor en una
fecha concreta sin depender del aspecto actual de la celda.
