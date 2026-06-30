# IBKR Analysts And News Roadmap

## Objetivo

Mejorar el pipeline local de analisis de acciones usando IBKR TWS API News como fuente primaria de informacion reciente, con dos fases separadas:

1. Analistas primero: extraer acciones de analistas, price targets y ratings desde `BRFUPDN`, y popular la hoja.
2. Catalizadores despues: usar noticias generales de IBKR como radar incremental para que una IA barata haga triage antes del analisis final.

El flujo diario `analiza RKLB` no debe romperse. Si IBKR, TWS o el triage fallan, el analisis debe poder seguir con el flujo actual.

## Estado Conocido

- TWS Paper esta instalado y probado localmente.
- TWS Paper escucha en `127.0.0.1:7497`.
- `ib_insync` conecta correctamente con `ib.connect("127.0.0.1", 7497, clientId=..., readonly=True)`.
- Providers encontrados con `reqNewsProviders()`:
  - `BRFG`: Briefing.com General Market Columns.
  - `BRFUPDN`: Briefing.com Analyst Actions.
  - `DJNL`: Dow Jones Newsletters.
  - `DJ-N`: Dow Jones Global Equity Trader.
- Metodos validados:
  - `reqNewsProviders()`.
  - `reqHistoricalNews(conId, providerCode, startDateTime, endDateTime, totalResults)`.
  - `reqNewsArticle(providerCode, articleId)`.
- `BRFUPDN` devuelve upgrades, downgrades, initiated, reiterated, ratings y price targets.
- `DJ-N` devuelve mucho volumen y ruido, pero tambien noticias utiles.
- `BRFG` devuelve menos volumen y parece mas concentrado en contexto de calidad.
- `DJNL` no aporto en la prueba inicial con MU.
- Finnhub `/calendar/earnings` funciona para obtener ultimo earnings y proximos earnings usando `FINN_KEY`.
- La key local se guarda en `.env.local`, que esta ignorado por git.

## Principios

- No filtrar noticias generales por keywords antes de IA.
- No exigir que el titular mencione el ticker o la empresa.
- Usar ventana desde el ultimo analisis del ticker, con solape adaptativo.
- Guardar raw siempre para auditoria.
- Separar analistas de noticias generales.
- Separar llamadas por provider para que un provider no consuma el cupo de otro.
- No llamar `DJ-N+BRFG+DJNL` en una sola request.
- La IA barata hace triage, no decide la tesis final.
- Codex final decide que entra como catalizador real.

## Fase 1: Analistas Primero

### 1. Crear probe local de IBKR Analysts

Crear un comando local pequeno, por ejemplo:

```powershell
python -m src.local_runner.ibkr_analyst_probe RKLB --days 14
```

Responsabilidades:

- Conectar a TWS en `127.0.0.1:7497`.
- Si hay `FINN_KEY`, obtener `previous_earnings_date` con Finnhub y usarlo como inicio de ventana.
- Si Finnhub falla o no hay key, usar fallback por `--days`.
- Resolver contrato con `Stock(ticker, "SMART", "USD")`.
- Obtener `conId`.
- Llamar `reqHistoricalNews(conId, "BRFUPDN", start, "", totalResults)`.
- Guardar titulares raw y limpios.
- Imprimir resumen minimo: provider, conteo, fechas, ejemplos.

Salida raw sugerida:

```text
data/ibkr_news_raw/{TICKER}/{timestamp}.BRFUPDN.json
```

### 2. Parsear acciones de analistas

Construir parser para titulares `BRFUPDN` usando datos reales.

Campos objetivo:

- `firm`
- `action`: `initiated`, `upgraded`, `downgraded`, `reiterated`, `maintained`, `resumed`, `target_raised`, `target_lowered`, etc.
- `rating`
- `rating_bucket`: `buy`, `hold`, `sell`, `unknown`
- `price_target`
- `previous_price_target`
- `published_at`
- `articleId`
- `headline_raw`
- `headline_clean`
- `parse_status`
- `warnings`

Importante: guardar el titular raw aunque el parser falle.

### 3. Tratar anomalías de price target

No usar un umbral fijo de upside como anomalia. En tickers growth, +50% o incluso +100% puede ser normal.

Reglas preferidas:

- Comparar targets contra el grupo de targets recientes del mismo ticker.
- Usar mediana como dato principal.
- Usar media solo como complemento.
- Marcar como sospechoso un target aislado que parezca 10x/100x respecto al grupo.
- Si varias firmas coinciden en targets altos, no tratarlo como anomalia.
- Si solo hay 1 target, mostrarlo como dato individual, no como consenso fuerte.
- Si un target numerico parece sospechoso, conservar raw y excluirlo del consenso calculado hasta revisar.

Campos sugeridos:

```json
{
  "target_median": 42.0,
  "target_mean": 44.5,
  "target_count": 6,
  "targets_excluded_count": 1,
  "warnings": ["one_target_parse_suspect"]
}
```

### 4. Construir consenso reciente IBKR

Este consenso no es consenso total de mercado. Es consenso reciente derivado de acciones de analistas vistas en `BRFUPDN`.

Salida sugerida:

```text
data/analyst_consensus/{TICKER}/latest.json
data/analyst_consensus/{TICKER}/{timestamp}.json
```

Campos:

- `source`: `IBKR_BRFUPDN`
- `as_of`
- `window_start`
- `window_end`
- `analyst_count`
- `firm_count`
- `rating_counts`
- `target_median`
- `target_mean`
- `target_low`
- `target_high`
- `target_count`
- `recent_actions`
- `excluded_targets`
- `warnings`

Este archivo debe alimentar la capa ya creada de calidad de analistas.

### 5. Integrar con la capa de calidad

Pasar `data/analyst_consensus/{TICKER}/latest.json` por `src/local_runner/analyst_quality.py`.

La capa debe:

- Penalizar datos viejos.
- Penalizar poca cobertura.
- Penalizar targets muy dispersos.
- Marcar targets sospechosos.
- Distinguir consenso reciente IBKR de consenso completo de mercado.

### 5b. Pasar resumen compacto al analisis final

Ademas de usar el resumen para Excel, conviene pasar una version reducida al `codex_input.md` del analisis final.

No pasar todo `data/analyst_ratings/{TICKER}/current.json`, porque contiene demasiada informacion operativa y puede consumir contexto sin aportar valor.

Formato sugerido:

```json
{
  "source": "IBKR_ANALYST_RATINGS",
  "basis": "post_earnings_only",
  "quality": "high",
  "active_firm_count": 18,
  "rating_counts": {"buy": 17, "hold": 1, "sell": 0},
  "target_median": 1512.5,
  "target_mean": 1552.78,
  "target_low": 1100,
  "target_high": 2000,
  "notable_recent_actions": [
    "Barclays maintained Overweight, raised PT to 2000 from 1175",
    "Goldman maintained Neutral, raised PT to 1100 from 900"
  ]
}
```

Reglas:

- Codex debe tratarlo como contexto externo, no como motor principal del analisis.
- Si la calidad es `low` o `none`, no usarlo para justificar nota, entrada ni salida.
- Si hay divergencia clara entre analistas y tecnico/opciones, mencionarla solo si aporta contexto real.
- El resumen debe ser breve: objetivo aproximado de 10-20 lineas maximo en JSON.

### 6. Popular Excel: columna AB

Prioridad del usuario: preferir analistas al stop loss en columna `AB`.

Nota conocida: el stop loss de `AB` se mete desde el Apps Script que actualiza notas y washouts. Antes de modificar, localizar el mapping exacto en:

```text
apps_script/update_targets_and_notes.gs
```

Nuevo valor sugerido para `AB`:

```text
$42 | 4-2-0
```

Si no hay calidad suficiente:

```text
Analistas: sin datos fiables
```

Si hay datos pero pocos:

```text
PT $42 | 1 firma | Buy | baja cobertura
```

Reglas:

- No mostrar un target viejo como fresco.
- No mezclar targets sospechosos en la mediana.
- No sobrescribir otras columnas sin revisar dependencias.
- Mantener raw/historico para auditoria.

### 7. Batch para tickers

Cuando el parser funcione para un ticker, extender a:

- ticker individual,
- `config/tickers_core.json`,
- `config/tickers.json`.

Respetar limites practicos de TWS:

- llamadas separadas por provider,
- pausas entre tickers si IBKR rate-limit,
- no bloquear el analisis si TWS no esta abierto.

## Fase 2: Catalizadores Y Noticias Generales

### 8. Crear fetch de noticias generales

Providers:

- `DJ-N`: fuente principal de noticias normales, alto volumen.
- `BRFG`: fuente separada, menor volumen y posiblemente mas calidad.
- `DJNL`: ignorar por ahora salvo nueva evidencia.

Salida raw:

```text
data/news_raw/{TICKER}/{timestamp}.DJ-N.json
data/news_raw/{TICKER}/{timestamp}.BRFG.json
```

Guardar por noticia:

- `source`
- `ticker`
- `conId`
- `providerCode`
- `articleId`
- `published_at_raw`
- `headline_raw`
- `headline_clean`
- `article.fetched`
- `article.articleType`
- `article.articleText`
- `triage.status`

### 9. Ventana desde ultimo analisis

La ventana siempre parte del ultimo analisis del ticker.

Si hay ultimo analisis:

```text
start = last_analysis_time - adaptive_overlap
end = now
```

Solape sugerido:

- Analisis diario: 12-24 horas.
- 2-7 dias desde el ultimo analisis: 1-2 dias.
- Mas de 7 dias: 3 dias.
- Mas de 21 dias: 5 dias.

Si no hay analisis anterior:

```text
start = now - 30 dias
```

Ademas:

- Deduplicar por `articleId`.
- Deduplicar titulares casi iguales.
- Guardar IDs ya vistos.
- No repetir noticias ya procesadas salvo que haya novedad material.

### 10. Pasar catalizadores anteriores al triage

Al triage IA se le debe pasar:

- fecha del ultimo analisis,
- catalizadores mostrados en el ultimo analisis,
- titulares nuevos de IBKR,
- instrucciones para no reciclar catalizadores anteriores salvo novedad material.

Objetivo:

- Reducir repeticiones.
- Detectar si una noticia nueva es continuacion real o solo eco de algo ya usado.

### 11. Triage IA barato

Usar Gemini Flash / Flash-Lite o modelo barato equivalente.

Input:

- titulares limpios,
- provider,
- fecha,
- ticker,
- catalizadores previos,
- opcionalmente cuerpo de noticia si ya esta disponible.

Output estructurado:

```json
{
  "id": "IBKR:DJ-N:DJ-N$1ec663cd",
  "keep": true,
  "score": 7,
  "category": "sector_readthrough",
  "direction": "bearish_or_cooling",
  "needs_article_body": true,
  "reason": "Read-through sectorial relevante desde competidor/par del ticker."
}
```

Reglas:

- La IA puede descartar ruido sin miedo.
- La IA no debe inventar impacto si el titular no lo justifica.
- La IA debe conservar noticias indirectas si afectan sector, competidores, clientes, proveedores, regulacion o mercado especifico del ticker.
- No usar keywords previas como filtro.

### 12. Descargar cuerpos solo cuando haga falta

Usar `reqNewsArticle(providerCode, articleId)`.

Estrategia:

- Si hay pocos titulares, se pueden descargar todos.
- Si hay muchos, descargar solo:
  - `needs_article_body = true`,
  - noticias con score alto,
  - noticias ambiguas pero potencialmente materiales.

Limpiar HTML/entities antes de pasarlo al analisis final.

### 13. Pasar candidatos a Codex final

Codex recibe:

- resumen del triage,
- noticias seleccionadas,
- catalizadores anteriores,
- cuerpos disponibles de noticias seleccionadas,
- instrucciones de no convertir todo en catalizador.

Reglas de prompt:

- Estos son candidatos, no verdades.
- Solo convertir en catalizador lo que afecte tesis, precio, riesgo, validacion, narrativa o proximo evento clave.
- No inventar catalizadores si ninguno supera el umbral real.
- Buscar web solo si falta contexto, hay movimiento no explicado o se necesita confirmar una noticia critica.

## Orden De Implementacion

1. `ibkr_analyst_probe` para `BRFUPDN`.
2. Guardado raw de analyst actions.
3. Parser de rating/target/firma.
4. Consenso reciente IBKR.
5. Integracion con `analyst_quality.py`.
6. Resumen compacto de analistas para `codex_input.md`.
7. Columna `AB` en Apps Script para resumen de analistas.
8. Batch para tickers core.
9. Fetch raw `DJ-N` y `BRFG`.
10. Ventana desde ultimo analisis + dedupe.
11. Gemini Flash triage con catalizadores anteriores.
12. Cuerpos de noticias seleccionadas.
13. Integracion del bloque `news_triage` en `codex_input.md`.

## Decisiones Pendientes

- Formato exacto de columna `AB`.
- Si conservar stop loss en otra columna o retirarlo de la hoja.
- Ventana inicial sin analisis anterior: 30 dias o menor.
- Umbral de score para pasar noticias a Codex final.
- Si Gemini Flash corre local via API o en Cloud Function/Cloud Run.
- Limites practicos de TWS para batch real.
