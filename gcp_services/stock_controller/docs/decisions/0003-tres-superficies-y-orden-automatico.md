# 0003. Tres superficies y orden automatico

Estado: `superseded by 0004`

## Contexto

El primer renderer representaba cada sector o subsector como una minitabla. La
separacion permitia ver afinidades, pero el resultado era fragmentado, costaba
recorrerlo y hacia dificil comparar el universo completo. La tabla historica de
`Trading` era mas legible, aunque ocultaba la concentracion por grupo.

El usuario quiere conservar esa lectura compacta sin perder la identidad de
sector o subsector, y quiere que cada cambio de nota restaure automaticamente
la agrupacion aunque exista ordenacion manual.

## Decision

`Mercado` se divide en tres superficies declarativas:

- `Trading`, a la izquierda, con los nombres mas volatiles;
- un panel general central entre las tablas, con riesgo, VXN, QQQ y fechas;
- `Resumen de grupos`, arriba a la derecha;
- `Core`, debajo del resumen y separado por dos filas vacias.

`Trading` y `Core` usan actualmente rangos planos con nombre. La primera columna
es una banda estrecha sin texto: su color identifica el grupo y coincide con el
color de ese grupo en el resumen. Los subsectores de un mismo sector comparten
familia cromatica. El ticker ocupa la columna siguiente.

El orden oficial es:

1. posicion del grupo en el manifiesto;
2. `Nota` numerica descendente;
3. ticker alfabetico.

El sincronizador de analisis escribe claves numericas en `M:N` para `Trading` y
`AB:AC` para `Core`, las mantiene ocultas y ejecuta el orden en la misma
publicacion que cambia una o varias notas. El refresco de mercado y las
actualizaciones de cartera resuelven las filas por el texto de `Ticker`, pero no
reordenan.

El resumen mantiene una fila por grupo con sector amplio, benchmark, `Dia`,
`20d`, `DD6M`, numero de posiciones y suma de shots. Las posiciones se cuentan
en ambos universos. El resumen no impone todavia umbrales de concentracion.

La configuracion inicial de `Core` es `NVDA`, `TSM`, `ASML`, `GOOG`, `IBKR`,
`RTX` y `CAT`. El resto del universo actual pertenece a `Trading`. La
clasificacion es configuracion revisable, no logica compilada.

## Consecuencias

- La hoja mantiene una lectura compacta y solo tres encabezados principales.
- La afinidad sectorial sigue visible y auditable sin crear una tabla por grupo.
- La identidad de grupo no repite texto en cada fila y deja mas ancho util para datos.
- Una nota nueva puede mover un ticker, pero nunca fuera de su grupo.
- Las publicaciones no dependen de numeros de fila estables.
- El usuario no puede dejar un orden manual divergente del orden oficial.
- Cambiar una pertenencia o un benchmark exige modificar el manifiesto y
  reconciliar la estructura.
