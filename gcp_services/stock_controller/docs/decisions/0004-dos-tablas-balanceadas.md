# 0004. Dos tablas balanceadas y resumen inferior

Estado: `superseded by 0005`

## Contexto

Separar visualmente `Trading` y `Core` introducia una distincion que ya no se
quiere usar. El resumen superior derecho tambien competia con la lectura de los
tickers y dejaba las dos tablas con alturas muy diferentes.

## Decision

Los 46 tickers forman un unico universo visible repartido en dos tablas de 23.
Si el universo fuese impar, la tabla izquierda tendria un ticker mas. La
distribucion inicial mantiene grupos completos, pero el usuario puede ordenar
cada tabla nativa libremente. Ningun proceso vuelve a imponer un orden.

Las dos tablas comparten titulo, columnas, paleta y reglas visuales. La primera
columna estrecha identifica el grupo por color y muestra los shots totales
abiertos en ese grupo.

El panel general permanece en `O2:O10`, entre ambas tablas. El resumen se mueve
debajo de ellas a `O:V`, tras dos filas vacias. Combina sector y grupo en `O`,
usa `P` como banda de color sin texto y coloca el ETF en `Q`, alineado con el
ticker de la tabla derecha.

## Consecuencias

- Ya no existe una categoria visual Core frente a Trading.
- Las dos tablas tienen igual densidad y altura.
- Ningun grupo queda partido entre lados.
- El resumen conserva la correspondencia cromatica sin repetir dos columnas de
  texto.
- Los perfiles Trading/Core pueden seguir apareciendo temporalmente en las
  fechas del panel porque describen lotes de analisis legacy, no universos de la
  hoja.
