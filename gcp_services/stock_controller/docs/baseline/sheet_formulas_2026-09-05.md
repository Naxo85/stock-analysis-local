# Formulas vivas de la hoja - 2026-09-05

Las formulas se leyeron directamente de la pestana `Bolsa_2026` del archivo
`Bolsa`, sin modificar celdas. Se inspecciono la primera fila de datos de la
tabla Trading.

## 1. Formulas de celda

### Fuerza - R2

```text
=REDONDEAR(
  (
    0,8 * RANGO.PERCENTIL.INC(
      FILTER(
        SI.ERROR(SI($U$2:$U=0; 0; $S$2:$S/$U$2:$U); 0);
        LARGO($S$2:$S&$T$2:$T&$U$2:$U)>0
      );
      SI.ERROR(SI(U2=0; 0; S2/U2); 0)
    )
    +
    0,2 * RANGO.PERCENTIL.INC(
      FILTER(
        SI.ERROR(SI($U$2:$U=0; 0; $T$2:$T/$U$2:$U); 0);
        LARGO($S$2:$S&$T$2:$T&$U$2:$U)>0
      );
      SI.ERROR(SI(U2=0; 0; T2/U2); 0)
    )
  ) * 10;
  2
)
```

### 5d - S2

```text
=DELTA5(D2;F2)
```

### 20d - T2

```text
=DELTA20(D2;F2)
```

### Volatilidad - U2

```text
=ATR20P(D2)
```

## 2. Semantica observada

### 5d y 20d

`DELTA5` y `DELTA20` llaman a `_priceDeltaTD` en `apps_script/fuerza.gs`.

El calculo:

1. descarga OHLC diario;
2. excluye la vela del dia en Nueva York porque puede estar incompleta;
3. usa el precio vivo de la columna F si es valido;
4. lo compara con el cierre situado 5 o 20 sesiones antes del ultimo cierre
   completo;
5. devuelve `spot / cierre_pasado - 1`, redondeado a cuatro decimales.

Por tanto, `5d` no significa cinco cierres completos entre si: durante la sesion
combina precio vivo con un cierre historico completo.

### Volatilidad

`ATR20P` usa `_atr(ticker, 20)` y divide su ATR por el ultimo cierre descargado.

El ATR actual:

1. intenta Yahoo para tres meses, despues Finnhub y finalmente FMP;
2. calcula True Range desde la segunda vela;
3. limita cada True Range al 25% del cierre anterior;
4. conserva hasta 20 observaciones;
5. ordena la ventana y recorta el 10% inferior y superior;
6. aplica suavizado de Wilder sobre la serie ya ordenada y recortada;
7. divide por el ultimo cierre y redondea a cuatro decimales.

Esta descripcion fija el comportamiento; no afirma que ordenar antes del
suavizado sea el mejor metodo. Cualquier mejora futura se comparara de forma
explicita.

### Fuerza

Fuerza es transversal, no una medida absoluta del ticker:

```text
ratio corto = 5d / Volatilidad
ratio medio = 20d / Volatilidad

Fuerza = 10 * (
  0,8 * rango_percentil_inclusivo(ratio corto) +
  0,2 * rango_percentil_inclusivo(ratio medio)
)
```

El resultado se redondea a dos decimales. Los rangos percentiles se calculan
contra todas las filas no vacias de las columnas S:T:U de la tabla actual. Los
errores, volatilidad cero o ratios no calculables se convierten en cero.

Consecuencia pendiente para el nuevo diseno: al separar los tickers en bloques,
hay que decidir si Fuerza se compara contra el universo completo, contra cada
bloque o contra ambos. Mantener exactamente el significado actual implica usar
el universo completo. No se toma esa decision en la linea base.

## 3. Proveedores y cache compartidos

Las tres metricas llaman a `_dailyOHLC`, que usa:

```text
Yahoo -> Finnhub -> FMP
```

La primera respuesta con al menos diez filas se guarda quince minutos en cache
de Apps Script. Este orden de fallback y la cache tambien forman parte del
comportamiento actual, aunque el destino arquitectonico sea `market-worker`.

## 4. Evidencia portable

`tests/characterization/fixtures/sheet_metrics.json` conserva:

- las cuatro formulas normalizadas;
- ejemplos deterministas de 5d, 20d, ATR20P y Fuerza;
- la advertencia sobre el universo transversal de Fuerza.

Las formulas no se ejecutan todavia en el runtime nuevo. Los casos se conectaran
al calculo nuevo al implementar esa capacidad.

