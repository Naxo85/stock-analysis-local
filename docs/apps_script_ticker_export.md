# Apps Script Ticker Export

This script exports the ticker list from the Google Sheet to GCS:

```text
gs://stock-analysis-reports-naxo85/config/tickers.json
```

## Where To Paste It

Open the Apps Script project attached to the Google Sheet and paste:

```text
apps_script/export_tickers_to_gcs.gs
apps_script/update_targets_and_notes.gs
```

The sheet must contain a tab named:

```text
Bolsa_2026
```

The first row must contain a header named:

```text
Ticker
```

## Manual Function

Run this function from Apps Script:

```javascript
exportTickersToGcs()
```

The script also adds a Sheets menu:

```text
Análisis IA -> Exportar tickers a GCS
Análisis IA -> Actualizar target y nota
```

## Permissions

The script uses the active user's Apps Script OAuth token:

```javascript
ScriptApp.getOAuthToken()
```

No service account or secret is stored in the code.

The executing user must have permission to write this GCS object:

```text
gs://stock-analysis-reports-naxo85/config/tickers.json
```

Apps Script will request permissions for spreadsheet access and external URL fetches.

## JSON Shape

The generated object has this shape:

```json
{
  "generated_at": "2026-06-05T00:00:00.000Z",
  "source_sheet": "Bolsa_2026",
  "ticker_column": "Ticker",
  "count": 3,
  "tickers": ["RKLB", "GOOG", "IBKR"]
}
```

Tickers are trimmed, uppercased, deduplicated, and kept in sheet order.

## Verify

After running the Apps Script function:

```powershell
gcloud storage cat gs://stock-analysis-reports-naxo85/config/tickers.json
```
