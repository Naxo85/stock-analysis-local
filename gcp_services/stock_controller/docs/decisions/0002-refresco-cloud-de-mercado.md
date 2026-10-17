# 0002. Refresco cloud de Mercado

Estado: `accepted`

## Contexto

La hoja `Mercado` necesita actualizar sus 46 tickers aunque el ordenador local
este apagado. El sistema anterior usaba triggers de Apps Script, pero la
reconstruccion busca que calculo, publicacion, errores y permisos tengan un
propietario visible y versionado.

El refresco normal consulta en una sola peticion a Tradier los 46 tickers y los
14 benchmarks. El historico diario, necesario para `5d`, `20d`, `Vol`,
`DD6M` y las bandas de benchmark, no puede
depender del disco efimero de una instancia de Cloud Run.

## Decision

Cloud Scheduler invoca cada minuto mediante OIDC el endpoint privado
`POST /market/refresh` de `stock-controller`. Apps Script y el ordenador local
no participan en este flujo.

El controlador calcula un bucket usando `America/New_York`:

- sesion regular: un minuto;
- premarket y postmarket: cinco minutos;
- fuera de esos horarios, fines de semana y festivos ordinarios: una hora.

Una transaccion de Firestore reclama el bucket con un lease temporal. Un bucket
publicado o ya reclamado responde sin llamar a Tradier ni a Google Sheets.

La cache historica del dia se almacena como un unico ZIP en GCS. Cloud Run la
restaura tras un arranque frio y reutiliza `/tmp` mientras vive la instancia.
Solo vuelve a guardar el ZIP cuando cambia su contenido.

La infraestructura efectiva se declara en `config/gcp_market_refresh.json` y
se reconcilia con `scripts/deploy_market_refresh_cloud.ps1`.

## Consecuencias

- El refresco funciona con el PC apagado.
- Cloud Run es el unico escritor programatico de las columnas automaticas y
  las bandas de benchmark de `Mercado`.
- El endpoint no es publico; solo la cuenta de Cloud Scheduler tiene
  `roles/run.invoker`.
- Los reintentos de Scheduler no duplican publicaciones.
- Un arranque diario puede descargar historicos de Tradier una vez; los ciclos
  siguientes usan la cache persistente y una unica peticion de cotizaciones.
- El estado de la ultima publicacion, duracion, errores y lease queda auditable
  en `stock_analysis_runtime/market_refresh`.
