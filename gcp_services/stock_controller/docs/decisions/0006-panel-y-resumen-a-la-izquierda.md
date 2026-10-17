# 0006 - Panel y resumen a la izquierda

## Decision

La columna informativa se situa en `A`, con el resumen de grupos debajo en
`A:H`. La primera tabla ocupa `J:U` tras la columna separadora `I`; la segunda
ocupa `W:AH` tras la separadora `V`.

## Motivo

El panel deja de interrumpir la lectura horizontal de las dos tablas y el
resumen comparte un bloque lateral estable con la informacion general.

## Consecuencias

Las dos tablas siguen formando una unica lista logica y conservan el selector
global en `A12:A13`. Cualquier cambio de geometria se reconcilia desde
`config/market_sheet_layout.json`.
