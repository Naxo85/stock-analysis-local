# 0005. Orden global sobre dos tablas nativas

Estado: `accepted`

## Contexto

Las dos tablas reducen la altura de la hoja, pero una ordenacion nativa solo
afecta a una de ellas. Por tanto, ordenar la izquierda por nota no puede llevar
automaticamente a su primera fila el mejor ticker del universo completo.

## Decision

Se conservan las tablas nativas `A:L` y `P:AA` y se tratan como una sola lista
logica de 46 tickers. El selector central `O13` admite `Nota`, `Sector` y
`Fuerza`. Cada publicador lee ambas tablas, calcula el orden global, reparte
23 filas en cada lado y despues escribe sus datos nuevos usando la identidad
compuesta de ticker, tabla y fila.

El reparto no fija 23 como capacidad permanente. Se calcula como `ceil(N/2)` a
la izquierda y `floor(N/2)` a la derecha; el resumen y el alto de la hoja se
derivan de la tabla mas larga. El universo se declara una sola vez dentro de
los grupos.

`Nota` y `Fuerza` son descendentes. `Sector` usa el orden de grupos declarado y
mantiene estable el orden previo dentro de cada grupo. No se crean columnas
auxiliares y no se modifica el tipo de tabla.

## Consecuencias

- El mejor ticker por nota o fuerza aparece arriba a la izquierda.
- Un ticker puede pasar de una tabla a la otra sin perder valores, formatos,
  notas ni enlaces.
- Los sectores se agrupan por la misma clasificacion cromatica del resumen.
- La seleccion se aplica en el siguiente refresco de mercado o de analisis.
- Los controles nativos siguen disponibles, pero el siguiente refresco restaura
  el criterio global seleccionado.
