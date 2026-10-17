# Estado observado de legacy - 2026-09-05

Esta fotografia se obtuvo consultando codigo local, pruebas, Google Cloud y el
Programador de tareas de Windows. No contiene credenciales ni valores de
Secret Manager.

## 1. Identidad de la fuente local

```text
Repositorio: E:\stock-analysis-local
Rama: main
HEAD: 18878802b37d53ce9a42b25f278a9271a298d360
Ficheros modificados o no versionados observados: 54
```

El commit por si solo no identifica el comportamiento efectivo porque el arbol
estaba modificado. Los ficheros relevantes se fijan por SHA-256 en
`baseline/legacy_source_manifest.json`.

## 2. Columnas visibles y propietario real

| Dato | Situacion observada | Estado de caracterizacion |
|---|---|---|
| Valor | Apps Script llama `YPRICE` y escribe la celda | Pendiente de aislar proveedor y reglas de sesion |
| `%d` | Cloud Run `support-resistance-values`, funcion Python versionada | 6 casos existentes, todos pasan |
| Fuerza | Formula viva en `R2`; Apps Script consume el resultado | Formula recuperada; falta convertirla en casos ejecutables contra el calculo nuevo |
| 5d | `=DELTA5(D2;F2)` y funcion versionada en `fuerza.gs` | Formula y codigo recuperados |
| 20d | `=DELTA20(D2;F2)` y funcion versionada en `fuerza.gs` | Formula y codigo recuperados |
| Volatilidad | `=ATR20P(D2)` y funcion versionada en `fuerza.gs` | Formula y codigo recuperados |
| `DD rel. 6M` | Cloud Run calcula percentil y drawdown bruto; Apps Script escribe valor, color y nota | 5 casos existentes, todos pasan |
| Entrada / Washout / Nota | Modelo local, informe estructurado, GCS, servicio `reports` y Apps Script | Cubierto parcialmente por pruebas de esquema y continuidad |

Las formulas se recuperaron despues desde la hoja viva en modo lectura. Su
detalle y semantica estan en `docs/baseline/sheet_formulas_2026-09-05.md`.
Esto confirma una de las razones de la reconstruccion: una parte esencial del
comportamiento no estaba reproducible solo desde Git.

## 3. Metricas ya comprobadas

Se ejecutaron en `legacy`:

```text
tests/test_daily_metrics.py
tests/test_drawdown_metrics.py
```

Resultado observado:

```text
11 passed
```

Las fuentes correspondientes son:

```text
gcp_functions/support_resistance_values/daily_metrics.py
gcp_functions/support_resistance_values/drawdown_metrics.py
```

Los casos representativos, entradas y resultados esperados se copiaron como
datos, no como runtime, a
`tests/characterization/fixtures/market_metrics.json`.

## 4. Cloud Run observado

Proyecto y region:

```text
recipe-generator-429817
europe-southwest1
```

Se observaron siete servicios relacionados con bolsa:

| Servicio | Revision lista | Max scale | Invocacion `allUsers` | Uso conocido |
|---|---:|---:|---:|---|
| `gemini-stock-analyze` | `00003-ffz` | 20 | No | Heredado; no forma parte del runner local diario |
| `reports` | `00003-g97` | 20 | Si | Lectura de informes para Apps Script |
| `stock-analyze-batch` | `00002-vdd` | 20 | No | Heredado; no forma parte del runner local diario |
| `support-resistance-values` | `weekend-pct2` | 1 | Si | Precios, opciones y metricas para Sheet |
| `support-resistances-raw` | `00054-hum` | 1 | No | Productor tecnico upstream de slim |
| `support-resistances-slim` | `00004-h5r` | 20 | No | JSON tecnico consumido por el runner local |
| `tickers-stats` | `00019-54f` | 1 | Si | Sin consumidor localizado ni logs en los ultimos 30 dias |

Todos usan la cuenta de servicio Compute predeterminada y `ingress=all`. Los
digests exactos de imagen estan en
`baseline/deployed_services_2026-09-05.json`.

Esta observacion corrige dos generalizaciones de la auditoria anterior:

1. hay siete servicios bursatiles desplegados, no seis;
2. tres permiten `allUsers`, no todos.

Que un servicio este desplegado no demuestra que este en uso. La migracion
exigira localizar un consumidor o clasificarlo expresamente como retirado.

La consulta de Cloud Logging para `tickers-stats` no devolvio entradas en los
30 dias anteriores a la captura. Junto a la ausencia de referencias en el codigo,
esto lo convierte en candidato probable a retirada. No se apagara solo con esta
evidencia porque la retencion o configuracion de logs podria ocultar trafico mas
antiguo.

## 5. Automatizacion observada

Cloud Scheduler:

```text
API deshabilitada en recipe-generator-429817
```

No se habilito durante la inspeccion.

Tarea de Windows activa:

```text
Nombre: Stock Analysis Command Worker
Accion: wscript.exe E:\stock-analysis-local\scripts\run_command_worker_hidden.vbs
Repeticion: PT1M
WakeToRun: false
StartWhenAvailable: true
MultipleInstances: IgnoreNew
Ultimo resultado observado: 0
```

El despertar desde suspension se probo correctamente de forma separada, pero
todavia no forma parte de la tarea productiva.

Los triggers instalados directamente en Apps Script no quedan determinados por
el codigo local. Deben inspeccionarse en el proyecto vivo antes de cerrar la
Fase 0.

El codigo permite crear al menos estos handlers:

```text
syncLatestAnalysisCompletion          cada minuto mientras hay ordenes pendientes
MKT_UPDATE_NASDAQ_RISK_REGIME_EVERY_5M  cada cinco minutos si se instalo manualmente
```

La existencia de funciones instaladoras no prueba que los triggers esten
instalados actualmente.

## 6. Universos observados en GCS

| Perfil legacy | Generado | Tickers |
|---|---|---:|
| Trading | `2026-09-04T14:32:47.719Z` | 38 |
| Core | `2026-09-03T13:23:52.349Z` | 30 |

Las listas exactas estan en `baseline/universe_2026-09-05.json`. Constituyen una
fotografia de entrada, no el agrupamiento definitivo ni una decision de conservar
todos los tickers.

## 7. Dependencias activas confirmadas por codigo

```text
Apps Script value refresh
  -> support-resistance-values

Runner local
  -> support-resistances-slim
  -> support-resistances-raw (upstream de slim)

Apps Script targets, notes y earnings
  -> reports

Runner local
  -> GCS para informes, snapshots, estado y colas
```

`gemini-stock-analyze` y `stock-analyze-batch` permanecen desplegados, pero el
runner local contiene prohibiciones expresas de utilizarlos como motor.

## 8. Pendientes para cerrar la Fase 0

1. Inspeccionar triggers instalados del Apps Script vinculado.
2. Confirmar antes del corte que `tickers-stats` puede retirarse; la evidencia
   actual indica que probablemente esta inactivo.
3. Convertir los casos dorados de formulas de Sheet en pruebas contra el calculo
   nuevo cuando se implemente.
4. Ejecutar la verificacion de hashes antes de portar cada capacidad, porque el
   arbol `legacy` sigue recibiendo mantenimiento.

El ejemplo de contrato de analisis ya esta fijado con datos sinteticos en
`tests/characterization/fixtures/analysis_report.json`. Describe el contrato
actual, incluidos stops legacy que no se adoptan automaticamente en el sistema
nuevo.
