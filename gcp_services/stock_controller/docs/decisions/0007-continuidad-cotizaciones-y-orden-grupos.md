# ADR 0007: continuidad de cotizaciones y orden diario de grupos

Fecha: 2026-09-29

## Decisión

El proveedor Tradier conserva por ticker la última muestra intradía válida
(`price`, `day_change`, `source`, `observed_at`). Se guarda localmente en
`latest_quotes.json` y en
`gs://stock-analysis-system-naxo85/runtime/market-quotes/latest.json`, separado
del ZIP de histórico diario. Una respuesta sin precio válido, con cero o con
`close` sin transacción actual no sustituye la muestra. Si no hay muestra
anterior, el ticker falla explícitamente y el refresco rechaza una publicación
parcial. Un cero real de variación permanece como `0.0` en la caché. Las
cotizaciones reutilizadas llevan una nota con hora, fuente y antigüedad.

El refresco de Mercado lee la tabla de grupos A:H, incorpora las nuevas
métricas D:F y ordena filas completas por Día numérico descendente. Los
empates conservan el orden físico previo y los valores ausentes van al final.
El actualizador de cartera lee ese orden antes de escribir `Pos.`/`Shots`.

## Motivo y límites

El mismo ticker puede carecer temporalmente de bid/ask en sesiones extendidas.
Mostrar `0,00 %` a partir de una respuesta incompleta sugeriría una nueva
observación inexistente. Mantener la última muestra y señalar su edad conserva
continuidad sin fingir actualidad. La caché compartida sobrevive reinicios de
Cloud Run y cambios de fecha; no sustituye el histórico diario.

La ordenación mueve también los colores, enlaces y posiciones para que no se
desalineen del ETF. El refresco de análisis no escribe esta tabla; Mercado
sigue siendo su único escritor automático de A:H. La publicación se hace en
una única llamada `batchUpdate`.

## Verificación

Las pruebas locales cubren premarket, postmarket, fin de semana, cero real,
respuesta vacía, ausencia sin caché, orden numérico, empates y preservación
de las celdas G:H. El refresco programado de las 18:37 UTC del 29-09 publicó
46 cotizaciones con HTTP 200; la verificación por API comprobó 14 filas de
grupo ordenadas con ETF y contadores alineados, y la caché GCS existe. Sigue
pendiente observar en vivo una respuesta Tradier sin bid/ask después del
despliegue.
