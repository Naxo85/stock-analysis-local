# Apps Script Ticker Export

This script exports the ticker list from the Google Sheet to GCS:

```text
gs://stock-analysis-reports-naxo85/config/tickers.json
```

## Where It Lives

The Apps Script project is linked locally with `clasp`:

```text
apps_script/.clasp.json
```

Project id:

```text
1sfKDncSk4aA9MewoukGQjqAoA3jr3Z0Wj8GetXEez0wSrP8V4XPS30OO
```

Do not blindly push the whole local `apps_script/` directory if the remote may
contain newer or differently named files. Use the safe workflow in:

```text
docs/operations.md
```

## Files

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
Análisis IA -> Exportar tickers trading a GCS
Análisis IA -> Exportar tickers core a GCS
Análisis IA -> Actualizar target y nota trading
Análisis IA -> Actualizar target y nota core
```

## Layout Controlled From Apps Script

The update script can also enforce sheet layout details from source control.

Manual functions:

```javascript
applyAnalysisSheetLayout()
applyTradingAnalysisSheetLayout()
applyCoreAnalysisSheetLayout()
```

Currently this controls:

```text
Trading AB1: Analistas
Trading AB2:AB<last ticker row>: conditional formatting for analyst summary
```

Cell format:

```text
PT median | Buy-Hold-Sell
1512,5 | 17-1-0
```

The range ends at the last non-empty ticker row for each profile, not at the
bottom of the sheet.

It does not touch conditional formatting in other columns.

Analyst summary colors combine consensus and median price-target distance from
current price:

```text
Red: median PT is at least 20% below current price, or sell share is 35%+.
Orange: median PT is at least 10% below current price, or sell share is 20%+.
Neon green: median PT is 35%+ above current price, buy share is 75%+, and sell share is <= 8%.
Strong green: median PT is 25%-35% above current price, buy share is 65%+, and sell share is <= 12%.
Soft green: median PT is 12%-25% above current price, buy share is 50%+, and sell share is < 20%.
Blue: median PT is 25%+ above current price, but consensus is mixed enough to deserve attention.
Yellow: hold share is 45%+, or median PT is less than 12% away from current price.
Bold: current price is at least 98% of median PT, meaning it is within 2% below consensus target or already above it.
```

Thresholds live at the top of `apps_script/update_targets_and_notes.gs`:

```javascript
TARGET_UPDATE_ANALYST_UPSIDE_EXCEPTIONAL
TARGET_UPDATE_ANALYST_UPSIDE_STRONG
TARGET_UPDATE_ANALYST_UPSIDE_POSITIVE
TARGET_UPDATE_ANALYST_DOWNSIDE_CAUTION
TARGET_UPDATE_ANALYST_DOWNSIDE_BAD
TARGET_UPDATE_ANALYST_BUY_SHARE_EXCEPTIONAL
TARGET_UPDATE_ANALYST_BUY_SHARE_STRONG
TARGET_UPDATE_ANALYST_BUY_SHARE_POSITIVE
TARGET_UPDATE_ANALYST_SELL_SHARE_LOW
TARGET_UPDATE_ANALYST_SELL_SHARE_OK
TARGET_UPDATE_ANALYST_SELL_SHARE_MIXED
TARGET_UPDATE_ANALYST_SELL_SHARE_BAD
TARGET_UPDATE_ANALYST_HOLD_SHARE_NEUTRAL
TARGET_UPDATE_ANALYST_NEAR_TARGET
```

`updateTradingTargetsAndNotes()` and `updateCoreTargetsAndNotes()` also apply
the layout before writing values, so routine updates keep the sheet aligned.

## Profiles

Trading uses:

```text
ticker column: D
ambitious entry column: Y
normal entry column: Z
nota column: AA
analyst summary column: AB
GCS object: config/tickers.json
```

Core uses:

```text
ticker column: AG
ambitious entry column: BB
normal entry column: BC
nota column: BD
GCS object: config/tickers_core.json
```

## Entry Range Rules

`Actualizar target y nota trading` and `Actualizar target y nota core` write ranges:

```text
valor_min-valor_max
```

Rules by score:

```text
score >= 7: ambitious entry + normal entry
6 <= score < 7: ambitious entry only
score < 6: no entry columns
```

Trading:

```text
Y: Entrada ambiciosa
Z: Entrada
AA: Nota
AB: Analistas
```

Core:

```text
BB: Entrada ambiciosa
BC: Entrada
BD: Nota
```

Conditional formatting formulas for these range cells live in:

```text
docs/sheet_conditional_formatting.md
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
cmd /c gcloud.cmd storage cat gs://stock-analysis-reports-naxo85/config/tickers.json
```

For core:

```powershell
cmd /c gcloud.cmd storage cat gs://stock-analysis-reports-naxo85/config/tickers_core.json
```
