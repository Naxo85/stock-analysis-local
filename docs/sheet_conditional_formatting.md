# Sheet Conditional Formatting For Entry Ranges

The updater writes entry ranges as text:

```text
valor_min-valor_max
```

In this sheet, both the current price and the entry ranges may behave as text in conditional formatting. Force conversion with `VALOR(...)`.

The formulas below intentionally use:

```text
VALOR($F2)
VALOR(IZQUIERDA(...))
VALOR(EXTRAE(...))
```

instead of regex parsing. This was tested on the sheet with `LRCX`, where:

```text
F3 = 300,84
Z3 = 300,0-315,0
```

and the bright green formula returned `VERDADERO`.

Google Sheets also accepts English function names in this workbook. A compact
rule can be applied to both entry columns at once because `Y2` is adjusted
relatively across `Y2:Z58`.

## Color Meaning

```text
Purple: price is below the lower bound. The entry range has been fully pierced.
Bright green: price is inside the range or up to 0.5% above the upper bound.
Light green: price is more than 0.5% and up to 1.5% above the upper bound.
No color: price is still more than 1.5% above the range.
```

Add the rules in this order for each range:

```text
Purple
Bright green
Light green
```

## Trading: Entrada Ambiciosa

## Trading: Compact Rules For Both Columns

Apply to:

```text
Y2:Z58
```

Purple:

```text
=AND($F2<>"";Y2<>"";VALUE($F2)<VALUE(LEFT(Y2;FIND("-";Y2)-1)))
```

Bright green:

```text
=AND($F2<>"";Y2<>"";VALUE($F2)>=VALUE(LEFT(Y2;FIND("-";Y2)-1));VALUE($F2)<=VALUE(MID(Y2;FIND("-";Y2)+1;99))*1,005)
```

Light green:

```text
=AND($F2<>"";Y2<>"";VALUE($F2)>VALUE(MID(Y2;FIND("-";Y2)+1;99))*1,005;VALUE($F2)<=VALUE(MID(Y2;FIND("-";Y2)+1;99))*1,015)
```

## Trading: Entrada Ambiciosa Only

Apply to:

```text
Y2:Y
```

Purple:

```text
=Y($F2<>"";Y2<>"";VALOR($F2)<VALOR(IZQUIERDA(Y2;ENCONTRAR("-";Y2)-1)))
```

Bright green:

```text
=Y($F2<>"";Y2<>"";VALOR($F2)>=VALOR(IZQUIERDA(Y2;ENCONTRAR("-";Y2)-1));VALOR($F2)<=VALOR(EXTRAE(Y2;ENCONTRAR("-";Y2)+1;99))*1,005)
```

Light green:

```text
=Y($F2<>"";Y2<>"";VALOR($F2)>VALOR(EXTRAE(Y2;ENCONTRAR("-";Y2)+1;99))*1,005;VALOR($F2)<=VALOR(EXTRAE(Y2;ENCONTRAR("-";Y2)+1;99))*1,015)
```

## Trading: Entrada Normal
## Trading: Entrada Normal Only

Apply to:

```text
Z2:Z
```

Purple:

```text
=Y($F2<>"";Z2<>"";VALOR($F2)<VALOR(IZQUIERDA(Z2;ENCONTRAR("-";Z2)-1)))
```

Bright green:

```text
=Y($F2<>"";Z2<>"";VALOR($F2)>=VALOR(IZQUIERDA(Z2;ENCONTRAR("-";Z2)-1));VALOR($F2)<=VALOR(EXTRAE(Z2;ENCONTRAR("-";Z2)+1;99))*1,005)
```

Light green:

```text
=Y($F2<>"";Z2<>"";VALOR($F2)>VALOR(EXTRAE(Z2;ENCONTRAR("-";Z2)+1;99))*1,005;VALOR($F2)<=VALOR(EXTRAE(Z2;ENCONTRAR("-";Z2)+1;99))*1,015)
```

## Core: Compact Rules For Both Columns

Apply to:

```text
BB2:BC
```

Purple:

```text
=AND($AI2<>"";BB2<>"";VALUE($AI2)<VALUE(LEFT(BB2;FIND("-";BB2)-1)))
```

Bright green:

```text
=AND($AI2<>"";BB2<>"";VALUE($AI2)>=VALUE(LEFT(BB2;FIND("-";BB2)-1));VALUE($AI2)<=VALUE(MID(BB2;FIND("-";BB2)+1;99))*1,005)
```

Light green:

```text
=AND($AI2<>"";BB2<>"";VALUE($AI2)>VALUE(MID(BB2;FIND("-";BB2)+1;99))*1,005;VALUE($AI2)<=VALUE(MID(BB2;FIND("-";BB2)+1;99))*1,015)
```

## Core: Entrada Ambiciosa Only

Apply to:

```text
BB2:BB
```

Purple:

```text
=Y($AI2<>"";BB2<>"";VALOR($AI2)<VALOR(IZQUIERDA(BB2;ENCONTRAR("-";BB2)-1)))
```

Bright green:

```text
=Y($AI2<>"";BB2<>"";VALOR($AI2)>=VALOR(IZQUIERDA(BB2;ENCONTRAR("-";BB2)-1));VALOR($AI2)<=VALOR(EXTRAE(BB2;ENCONTRAR("-";BB2)+1;99))*1,005)
```

Light green:

```text
=Y($AI2<>"";BB2<>"";VALOR($AI2)>VALOR(EXTRAE(BB2;ENCONTRAR("-";BB2)+1;99))*1,005;VALOR($AI2)<=VALOR(EXTRAE(BB2;ENCONTRAR("-";BB2)+1;99))*1,015)
```

## Core: Entrada Normal Only

Apply to:

```text
BC2:BC
```

Purple:

```text
=Y($AI2<>"";BC2<>"";VALOR($AI2)<VALOR(IZQUIERDA(BC2;ENCONTRAR("-";BC2)-1)))
```

Bright green:

```text
=Y($AI2<>"";BC2<>"";VALOR($AI2)>=VALOR(IZQUIERDA(BC2;ENCONTRAR("-";BC2)-1));VALOR($AI2)<=VALOR(EXTRAE(BC2;ENCONTRAR("-";BC2)+1;99))*1,005)
```

Light green:

```text
=Y($AI2<>"";BC2<>"";VALOR($AI2)>VALOR(EXTRAE(BC2;ENCONTRAR("-";BC2)+1;99))*1,005;VALOR($AI2)<=VALOR(EXTRAE(BC2;ENCONTRAR("-";BC2)+1;99))*1,015)
```
