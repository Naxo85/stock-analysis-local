> Archivo histórico preservado el 17-10-2026. Sus referencias a «actual», «vigente» o «siguiente» corresponden a la fecha de cada entrada. No es una guía de ejecución vigente. Consulte [arquitectura actual](../architecture.md), [relevo](../handoff_current.md) y [backlog](../pending_work_current.md). Se ajustaron únicamente rutas relativas de enlaces al archivar.

# Mapa de componentes

Este documento representa el sistema observado el 2026-09-04. La hoja de calculo
es **Google Sheets**; no se detecto una integracion activa con Microsoft Excel.

## Topologia general

```mermaid
flowchart TB
    user[Usuario]

    subgraph workspace[Google Workspace]
        sheets[Google Sheets<br/>Bolsa_2026]
        gas[Apps Script<br/>menus, formulas y triggers]
    end

    subgraph gcp[Google Cloud]
        gcs[(Cloud Storage<br/>config, cola, informes y snapshots)]
        reports[Cloud Run: reports]
        values[Cloud Run:<br/>support-resistance-values]
        slim[Cloud Run:<br/>support-resistances-slim]
        raw[Cloud Run:<br/>support-resistances-raw]
        legacy[Cloud Run heredado:<br/>gemini-stock-analyze y stock-analyze-batch]
        secrets[Secret Manager<br/>IBKR y Tradier]
    end

    subgraph pc[PC Windows local]
        task[Programador de tareas<br/>cada minuto]
        worker[command_worker.py]
        batch[run_batch.py]
        runner[run_one.py]
        gateway[IB Gateway + IBC<br/>127.0.0.1:7497]
        codex[Codex CLI]
        local[(data, output y logs locales)]
        bootstrap[Scripts de bootstrap<br/>y despliegue]
    end

    subgraph external[APIs y servicios externos]
        ibkr[IBKR]
        tradier[Tradier]
        market[Yahoo, Finnhub, FMP<br/>Nasdaq, CNN y RapidAPI]
        gemini[Gemini API<br/>agregacion opcional]
        web[Fuentes web<br/>consultadas por Codex]
    end

    user --> sheets
    sheets <--> gas

    gas -->|exporta tickers| gcs
    gas -->|crea orden pendiente| gcs
    gas -->|lee informe reducido| reports
    reports -->|lee latest| gcs
    gas -->|calculo tecnico por lote| values
    gas -->|precios, riesgo y earnings| market

    task --> worker
    worker -->|reclama orden y publica estado| gcs
    worker --> batch
    worker --> runner
    batch --> runner

    runner <--> local
    runner -->|snapshot tecnico| slim
    runner -->|generacion del informe| codex
    codex --> web
    runner -->|latest, snapshots e historial| gcs

    gateway <--> ibkr
    runner --> gateway
    batch --> gateway
    runner -. agregacion opcional .-> gemini

    values --> tradier
    values --> market
    slim -. backend historico; confirmar .-> raw
    raw -. proveedor no versionado aqui .-> market

    secrets -->|credenciales IBKR| bootstrap
    secrets -->|token mediante secretKeyRef| values
    bootstrap --> gateway
    bootstrap <--> gcs

    legacy -. fuera del flujo diario .-> gcs

    classDef active fill:#d9ead3,stroke:#38761d,color:#000;
    classDef optional fill:#fff2cc,stroke:#bf9000,color:#000;
    classDef legacy fill:#eeeeee,stroke:#777,color:#333,stroke-dasharray: 5 5;
    classDef risk fill:#f4cccc,stroke:#990000,color:#000;

    class sheets,gas,gcs,task,worker,batch,runner,gateway,codex,local,bootstrap active;
    class reports,values,slim risk;
    class gemini optional;
    class raw,legacy legacy;
```

Leyenda:

- verde: componente activo bajo control local;
- rojo: componente activo expuesto a Internet o con un hallazgo de seguridad;
- amarillo: ruta opcional;
- gris discontinuo: servicio heredado o relacion pendiente de confirmar.

## Secuencia de una orden desde la hoja

```mermaid
sequenceDiagram
    actor U as Usuario
    participant S as Google Sheets
    participant A as Apps Script
    participant G as GCS
    participant W as Worker Windows
    participant R as Runner local
    participant I as IBKR Gateway
    participant C as Cloud Run slim
    participant X as Codex CLI y web
    participant P as Cloud Run reports

    U->>S: Analizar ticker, Trading o Core
    S->>A: Menu de analisis
    A->>G: commands/pending/<id>.json
    A-->>S: Registra id y activa trigger temporal

    loop Cada minuto
        W->>G: Busca una orden pendiente
    end

    W->>G: Mueve pending a running
    W->>R: Ejecuta run_one o run_batch
    R->>I: Handshake y datos IBKR
    R->>C: Solicita snapshot tecnico
    R->>G: Lee referencia o informe previo
    R->>X: Genera el Markdown con el prompt versionado
    R->>R: Valida y crea JSON y HTML
    R->>G: Publica latest, snapshots, historial y estado
    W->>G: commands/completed o commands/failed

    loop Trigger temporal de Apps Script
        A->>G: Consulta resultado de la orden
    end

    A->>P: Solicita informe reducido
    P->>G: Lee <ticker>/latest.json
    P-->>A: Scores, entradas, objetivos y analistas
    A->>S: Actualiza celdas y elimina trigger
    S-->>U: Resultado visible
```

## Objetos principales en GCS

```text
config/
  tickers.json
  tickers_core.json
commands/
  pending/  running/  completed/  failed/
  status/latest.json
batch/status/
  latest_trading.json
  latest_core.json
<TICKER>/
  latest.md
  latest.html
  latest.json
  <fecha>/<hora>.{md,html,json}
  history.json
_analysis_state/<TICKER>/reference.json
_local_test/<TICKER>/latest.*
bootstrap/ibkr/
  latest.json
  <version>/...
```

## Responsabilidad por componente

| Componente | Responsabilidad | Fuente de verdad |
| --- | --- | --- |
| Google Sheets | Interfaz y cartera visible | Hoja `Bolsa_2026` |
| Apps Script | Comandos, formulas, refrescos y sincronizacion | `apps_script/` mas propiedades remotas |
| Worker local | Consumo de la cola y despacho | `src/local_runner/command_worker.py` |
| Runner local | Politica, generacion, validacion y publicacion | `src/local_runner/` y `prompts/` |
| IBKR Gateway | Datos IBKR y sesion de broker de solo lectura | Proceso local y Secret Manager |
| GCS | Bus asincrono y almacenamiento durable | `stock-analysis-reports-naxo85` |
| Cloud Run `reports` | Adaptador de informes para la hoja | `gcp_functions/reports_reader/` |
| Cloud Run tecnico | Snapshots y metricas de mercado | Fuente parcial en este repositorio |
| APIs externas | Precios, noticias, eventos y sentimiento | Cada proveedor externo |

