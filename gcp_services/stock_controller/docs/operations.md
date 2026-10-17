# Operacion del refresco de Mercado

## Autoridad y alcance

El comando nuevo prepara o escribe `Valor`, `Dia`, `Fuerza`, `5d`, `20d`,
`Vol` y `DD6M` en `Mercado`. Nunca cambia el contenido ni las notas de `Ent.`,
`Wash.`, `Res.` o `Nota`; solo recalcula los fondos de proximidad de `Ent.`,
`Wash.` y `Res.` con cada nuevo precio.

El universo y las coordenadas se leen de `config/market_sheet_layout.json`. La
publicacion se rechaza por completo si falla cualquier ticker; no se compactan
filas ni se presenta una mezcla de datos viejos y nuevos como correcta.

La cartera declarada se guarda en `config/portfolio.json`. Cada ticker conserva
solo su numero de shots: `#00FFFF` para uno y `#00B8D4` para dos o mas. Al retirar
una posicion, el reconciliador restaura el fondo blanco. El mismo comando
actualiza `Pos.` y `Shots` en el resumen de grupos y escribe en la primera
columna de cada ticker los shots totales abiertos en su subsector.
No se inventan cantidades, precios de compra ni fechas que el usuario no haya
proporcionado.

La operacion estandar es:

```powershell
& '.\.venv\Scripts\python.exe' -m stock_analysis.controller.update_portfolio --set RKLB=1 --set OKLO=2 --remove SPCX --publish
```

`--set` y `--remove` pueden repetirse. El comando actualiza el estado declarativo
y reconcilia los 47 fondos de ticker en una sola llamada a Sheets.

La identidad del publicador REST debe tener permiso de editor sobre el
spreadsheet. Un token valido de Google Cloud no concede por si solo acceso al
archivo de Drive; un `403` es un fallo total sin cambios parciales.

La identidad declarada es
`stock-analysis-sheets@recipe-generator-429817.iam.gserviceaccount.com`. El
cliente la impersona sin claves descargadas y solicita tokens de una hora
limitados al alcance de Google Sheets. La cuenta local necesita el rol
`roles/iam.serviceAccountTokenCreator` sobre esa identidad, y la hoja debe estar
compartida con la cuenta de servicio como editora.

## Proveedor y carga

- Cotizaciones: una peticion por lote a Tradier por ejecucion. Incluye los 47
  tickers visibles, los 14 benchmarks de grupo y QQQ para el panel general. En
  sesion regular se usa `last`; en premarket y postmarket se usa el punto medio
  del `bid/ask` solo si ambas puntas tienen menos de 15 minutos y la horquilla
  no supera el 5% del punto medio. Una horquilla ausente, antigua, cruzada o
  demasiado ancha hace fallback a `last`.
- Historico diario: una peticion por ticker y dia ET, con cache en
  `artifacts/cache/tradier/`.
- Calculos: locales y deterministas.
- Publicacion: un `spreadsheets.batchUpdate` para las dos tablas y el resumen.
- Resolucion de filas: una lectura por lote de las dos columnas `Ticker` antes
  de escribir; el mapa resultante respeta cualquier orden manual de cada tabla.
- Geometria: el mismo batch termina restaurando los anchos declarados de
  `A:AH`; no existen columnas auxiliares de ordenacion.
- Sentimiento: CNN Fear & Greed se lee en cada refresco desde el proxy, que
  aplica por si mismo la unica cache de 15 minutos; VXN realiza una sola consulta Yahoo `^VXN` cada cinco
  minutos efectivos. Yahoo no se usa para cotizar tickers ni QQQ.
- Fechas de analisis: dos contratos pequenos en
  `gs://stock-analysis-system-naxo85/runtime/analysis-status/`, cacheados cinco
  minutos. El batch legacy solo replica `profile`, `finished_at`, `success` y
  `failed`; `stock-controller` no recibe acceso al bucket historico legacy.
  Cloud Run usa sus credenciales nativas; la ejecucion local cae en `gcloud`
  cuando no existe Application Default Credentials.

## Ejecucion

El secreto se entrega por entorno y nunca se guarda en el repositorio:

```powershell
$env:TRADIER_TOKEN = '<secret>'
& '.\.venv\Scripts\python.exe' -m stock_analysis.market_worker.run_refresh --force --output artifacts\market_snapshot.json
```

El adaptador `scripts/run_market_refresh.ps1` intenta obtener `tradier-token`
desde Secret Manager cuando la variable no existe. El valor vive solo en el
proceso de PowerShell.

El comando anterior es un dry-run. Para publicar:

```powershell
& '.\.venv\Scripts\python.exe' -m stock_analysis.market_worker.run_refresh --publish
```

Sin `--force`, el proceso se omite fuera de 04:00-20:00 ET.

## Refresco cloud programado

`Cloud Scheduler` invoca cada minuto `POST /market/refresh` en el servicio
privado `stock-controller`. El controlador usa hora de Nueva York y Firestore
para reclamar de forma atomica un unico bucket efectivo:

- mercado regular: un minuto;
- premarket y postmarket: cinco minutos;
- mercado cerrado, fines de semana y festivos bursatiles ordinarios: una hora.

Las invocaciones que caen dentro de un bucket ya publicado no consultan Tradier
ni escriben en Sheets. El estado y lease viven en
`stock_analysis_runtime/market_refresh`. Cloud Scheduler autentica con OIDC y
solo su cuenta tiene `roles/run.invoker`.

El historico diario de los 47 tickers, los 14 benchmarks y QQQ se conserva comprimido en
`gs://stock-analysis-system-naxo85/runtime/market-history/`. Asi, los arranques
de Cloud Run reutilizan una unica descarga diaria y Tradier solo recibe una
peticion agrupada de cotizaciones durante los refrescos normales.

La configuracion declarada del despliegue esta en
`config/gcp_market_refresh.json`; el reconciliador de infraestructura se ejecuta
con:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy_market_refresh_cloud.ps1
```

### Primera validacion cloud

El 2026-09-05 se desplego `stock-controller-00003-7nb` en
`europe-southwest1` y se activo `stock-analysis-market-refresh` en
`europe-west1`:

- primera peticion valida: `published`, 46 tickers, bucket cerrado de 60
  minutos;
- segunda peticion del mismo bucket: `skipped`;
- primer historico persistente: `2026-09-05.zip`, 705392 bytes;
- pulsos automaticos posteriores: HTTP 200 en aproximadamente 0,2 segundos;
- IAM de Cloud Run: unicamente `stock-analysis-scheduler` tiene
  `roles/run.invoker`.

### Primera publicacion real validada

El 2026-09-05 se ejecuto un refresco forzado completo desde este repositorio:

```text
OK published=46 requests=67
```

El snapshot no contenia fallos. Se releyeron desde Google Sheets AMD, MU, RKLB,
PLTR, IBKR y HIMS, repartidos entre seis bloques, y sus siete valores efectivos
coincidieron exactamente con el snapshot local. La comprobacion estructural
posterior devolvio `PLAN changes=0`.

La ejecucion uso Tradier, el secreto `tradier-token`, impersonacion sin claves
de la cuenta tecnica y una unica publicacion `spreadsheets.batchUpdate`. Fue una
prueba manual; no activa ninguna tarea periodica.

### Migracion real de benchmarks

El 2026-09-05 se sustituyeron las formulas de las 14 bandas por valores
calculados en `stock-controller`:

```text
OK published=46 benchmarks=14 requests=81
```

Tradier devolvio en una unica cotizacion agrupada los 46 tickers y los 14 ETF,
sin fallos. La ejecucion con historicos cacheados tardo aproximadamente
3 segundos. Se releyeron las 14 bandas desde Sheets y coincidieron con el
snapshot publicado. `AuxMercado` permanece como referencia de transicion, pero
ya no es una dependencia de ejecucion ni el reconciliador restaura sus formulas.

La revision final `stock-controller-00005-vv5` recibio el 100% del trafico. El
primer bucket cloud con benchmarks (`closed:2026-09-05T18:00:00-04:00`)
termino sin error en 4,756 segundos. El ZIP diario paso de 705392 a 898048 bytes
al incorporar los 15 historicos adicionales.

### Migraciones de layout

El 2026-09-07 se sustituyo el mosaico por `Trading`, `Resumen de grupos` y
`Core`. La migracion de `Grupo/Ticker` a `banda de color/Ticker` valido primero
los 46 simbolos y actualizo las dos columnas en un unico `batchUpdate`, sin
limpiar precios, soportes ni notas. La revision
`stock-controller-00019-2w8` recibio el 100% del trafico.

La segunda migracion del mismo dia elimino los margenes reservados `A:C`,
desplazo `Trading` a `A:L`, coloco el panel general en `O` y llevo Resumen/Core
a `P:AA`. Se ejecuto como un unico `batchUpdate` con columnas temporales y
validacion previa del universo, para no pisar datos durante los movimientos.
La revision `stock-controller-00020-lqv` recibio el 100% del trafico.

El diseno posterior integro ambos universos visibles en dos tablas equivalentes
de 23 tickers, sin partir grupos. El resumen paso debajo de ellas a `O:V`, con
la etiqueta combinada en `O`, banda de color en `P` y ETF en `Q`. La revision
`stock-controller-00021-4sw` recibio el 100% del trafico.

El ajuste final convirtio `A:L` y `P:AA` en tablas nativas, retiro el orden
automatico y las columnas auxiliares, mantuvo el panel en `O`, anadio los shots
agregados a la banda de cada ticker y concentro la explicacion de DD6M en sus
cabeceras. La huella del sincronizador incluye desde entonces la geometria de
las tablas, de modo que moverlas invalida una proyeccion anterior. La revision
`stock-controller-00024-fst` recibio el 100% del trafico.

La revision `stock-controller-00025-rbp` corrigio los enlaces de `Nota`: el
reader sigue usando el mismo `latest.html`, pero la hoja solicita explicitamente
`format=html` en lugar de entregar `latest.md` como texto sin renderizar.

La revision `stock-controller-00026-qfb` mantuvo las dos tablas nativas y anadio
el selector global `O12:O13`. Los criterios `Nota`, `Sector` y `Fuerza` ordenan
el universo completo antes de repartirlo de forma balanceada entre ambos lados.
La capacidad, las filas de separacion, el resumen y el alto de la hoja se
derivan del numero de tickers y grupos del manifiesto.

Las publicaciones limpian los bordes horizontales internos antes de restaurar
el contorno y los separadores verticales. Esto evita que una antigua division
de grupo viaje con su fila al cambiar el orden global.

La revision `stock-controller-00028-fwk` aplica esta limpieza con `NONE`, el
valor de borrado exigido por la API de Google Sheets, y sirve el 100% del
trafico.

La misma reparacion puede aplicarse sin refrescar datos:

```powershell
& '.\.venv\Scripts\python.exe' -m stock_analysis.controller.repair_market_borders
```

La verificacion viva posterior devolvio:

```text
OK tickers=46 market_rows=46 groups=14 markdown_links=46
PLAN changes=0
```

## Autoridad periodica

`stock-controller` es el unico escritor programatico de las siete columnas
automaticas, las metricas del resumen de grupos y `A2:A10` de `Mercado`. Los componentes legacy pueden seguir manteniendo sus
hojas anteriores durante la transicion, pero no poseen ni actualizan esta
superficie nueva. No debe instalarse un trigger de Apps Script sobre las mismas
celdas.

## Orden global de las tablas de mercado

El refresco no presupone que un ticker siga en la tabla o fila declarada
originalmente. Antes de publicar valida las 47 identidades y lee el contenido de
ambas tablas. El universo conjunto debe coincidir exactamente con el manifiesto.

Las dos superficies siguen siendo tablas nativas equivalentes. El selector
`C10`, rotulado en `C9`, ofrece `Nota`, `Sector` y `Fuerza`. El controlador
ordena los 47 tickers como una sola lista, escribe los primeros 24 en `J:U` y
los restantes en `W:AH`; no usa columnas auxiliares ni cambia el tipo de tabla.
El resumen de grupos se coloca una fila vacia debajo del bloque superior de `A:H`.
Con la geometria actual ocupa `A12:H27`, pero se desplaza si crece ese bloque.
`Nota` y `Fuerza` colocan primero el valor mayor y dejan los ausentes al final.
`Sector` usa el orden de grupos de `config/market_sheet_layout.json` y conserva
el orden relativo dentro de cada color.

Los valores 47, 24 y 23 son el estado actual. La geometria se deriva del universo
de `groups`: la izquierda recibe `ceil(N/2)`, la derecha `floor(N/2)` y el
resumen se mueve debajo de la tabla mas larga. Para incorporar o retirar un
ticker solo se modifica su grupo; las listas fisicas de los bloques no se
mantienen por duplicado.

El refresco intradia aporta la `Fuerza` nueva antes de ordenar. La sincronizacion
de informes aporta la `Nota` nueva antes de ordenar. Los otros criterios usan el
ultimo valor visible. Si falta un ticker, hay un duplicado o aparece uno
inesperado, la publicacion completa se cancela antes del `batchUpdate`.

## Reconciliacion estructural

La estructura deseada de `Mercado` vive en
`config/market_sheet_layout.json`. Antes de modificarla se obtiene un plan de
diferencias contra las dos tablas nativas, el rango con nombre del resumen y
las fusiones reales de Google Sheets:

```powershell
& '.\.venv\Scripts\python.exe' -m stock_analysis.controller.reconcile_sheet plan
```

`plan` es de solo lectura. Enumera tablas nativas, rangos con nombre y fusiones
de titulo que deben retirarse o restaurarse. Un resultado
`PLAN changes=0` significa que esa estructura coincide con el manifiesto.

Para inspeccionar tambien las peticiones REST sin enviarlas:

```powershell
& '.\.venv\Scripts\python.exe' -m stock_analysis.controller.reconcile_sheet plan `
  --requests-output artifacts\sheet_structure_requests.json
```

Para reconstruir deliberadamente todo el contenido estructural y el formato
declarado (por ejemplo, tras cambiar columnas o paletas):

```powershell
& '.\.venv\Scripts\python.exe' -m stock_analysis.controller.reconcile_sheet render
```

Para reaplicar solo la fuente declarada de las dos tablas, el resumen y la
columna central, sin reescribir contenido ni estructura:

```powershell
& '.\.venv\Scripts\python.exe' -m stock_analysis.controller.reconcile_sheet apply-font
```

Para reaplicar a la vez la fuente y los anchos declarados:

```powershell
& '.\.venv\Scripts\python.exe' -m stock_analysis.controller.reconcile_sheet apply-layout
```

`render` limpia las tres superficies administradas y exige volver a publicar
mercado, analisis y cartera. No se usa como reparacion rutinaria de datos.

La aplicacion siempre es explicita:

```powershell
& '.\.venv\Scripts\python.exe' -m stock_analysis.controller.reconcile_sheet apply
```

`apply` elimina estructuras incompatibles de `Mercado`, reconstruye las dos
tablas nativas y el resumen de grupos, y restaura cabeceras, tickers, grupos,
fusiones, paleta, alineacion y dimensiones.
Despues vuelve a leer la hoja y exige convergencia en un maximo de tres pasadas.
No modifica las columnas automaticas de mercado ni `Ent.`, `Wash.`, `Res.` o `Nota` de
una tabla que ya esta en su posicion.

Para probar un estado capturado sin acceso a Google Sheets se puede usar
`plan --state <fichero.json>`. Por seguridad, `apply` rechaza estados capturados.

## Sincronizacion de analisis en Mercado

Las columnas `Ent.`, `Wash.`, `Res.` y `Nota` tienen un escritor separado del
refresco intradia. El origen es el ultimo `latest.json` validado que produce el
runner local existente; este paso no vuelve a llamar al modelo ni recalcula
niveles.

Cada upload real con `analysis_status: ok` conserva sus artefactos habituales y
copia ademas el JSON a:

```text
gs://stock-analysis-system-naxo85/runtime/analysis-reports/<TICKER>.json
```

Un informe fallido nunca pisa ese espejo. `Cloud Scheduler` invoca cada minuto
`POST /analysis/refresh`; el servicio compara las generaciones de los 47
objetos y no lee informes ni escribe la hoja si nada ha cambiado. La primera
carga publica los informes validos disponibles; cualquier informe ausente, fallido o
estructuralmente invalido deja vacias solo sus cuatro celdas de analisis.

La carga inicial desde los informes que ya existen se ejecuta una sola vez:

```powershell
& '.\.venv\Scripts\python.exe' -m stock_analysis.analysis_worker.seed_mirror
```

Para inspeccionar las peticiones sin publicar:

```powershell
& '.\.venv\Scripts\python.exe' -m stock_analysis.analysis_worker.run_sync --force --requests-output artifacts\analysis_sheet_requests.json
```

Para publicar manualmente:

```powershell
& '.\.venv\Scripts\python.exe' -m stock_analysis.analysis_worker.run_sync --publish --force
```

El sincronizador lee primero `Ticker` y `Valor` de ambas tablas para calcular
las distancias mostradas en las notas. Si `A13` contiene `Nota`, redistribuye
ambas tablas con las notas nuevas antes de escribir las cuatro columnas de
analisis:

- `Ent.`: `plan.entry`.
- `Wash.`: `plan.ambitious_entry`.
- `Res.`: `plan.resistance`, la resistencia estructural mas fuerte elegida sin
  penalizar su fortaleza por distancia; solo se publica si su fortaleza es
  `solido` o superior (70/100 o mas).
- `Nota`: `decision.score`, enlazada al informe HTML.
- Stop de entrada: primer valor entre `management_stop` y
  `structural_stop` que quede por debajo del limite inferior de entrada.
- Stop de washout: `structural_stop` solo si queda por debajo del washout.
- Fortaleza: se muestra unicamente si el JSON contiene una fortaleza explicita
  producida por el modelo; el borde se aplica por separado a `Ent.`, `Wash.` y
  `Res.`.
- Orden: controlado globalmente desde `A13`; no existen claves de ordenacion
  ocultas.
- Enlace de `Nota`: abre el `latest.html` renderizado mediante el reader con
  `format=html`; nunca enlaza al Markdown crudo ni al espejo JSON usado por el
  sincronizador.

El color de proximidad usa el valor vivo de la hoja: lavanda bajo el soporte,
verde fosforito dentro del rango o hasta 0,5% por encima, verde palido entre
0,5% y 1,5% por encima, y el fondo normal de la fila fuera de esos casos.
Para `Res.` se usa azul brillante dentro de la zona o hasta 0,5% por debajo,
azul suave entre 0,5% y 1,5% por debajo y fondo normal cuando queda mas lejos.
Una resistencia inferior a 70/100 deja `Res.` completamente vacia.

## Verificacion integral de la hoja viva

La comprobacion de solo lectura valida el universo de 47 tickers, las siete
metricas de mercado, los shots por subsector, las dos tablas nativas, las 14
filas del resumen y que los 47 enlaces de `Nota` abran el informe HTML renderizado:

```powershell
& '.\.venv\Scripts\python.exe' -m stock_analysis.controller.verify_live_sheet
```
