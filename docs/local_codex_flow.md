# Local Codex Flow

> Portable installations use `.\.venv\Scripts\python.exe`, created by
> `scripts\setup_new_pc.ps1`. Any user-specific absolute Python path retained
> below is a historical troubleshooting example for the original machine.

> Portable installations use `.\.venv\Scripts\python.exe`, created by
> `scripts\setup_new_pc.ps1`. Any user-specific absolute Python path retained
> below is a historical troubleshooting example for the original machine.

The standard analysis engine is the local Python runner plus Codex markdown generation. `incoming_from_gcp/` is a legacy reference snapshot.

## Architecture

Python orchestrates the run:

```text
prepare -> generate -> validate -> upload
```

Codex only generates the final markdown. It receives `codex_input.md` and writes `latest.md`.

Python remains responsible for:

- calling the slim endpoint;
- saving slim JSON;
- creating `codex_input.md`;
- invoking Codex when `codex exec` is available;
- validating markdown;
- creating `latest.json` and a styled `latest.html` from the validated Markdown;
- uploading latest files and snapshots;
- recording OK/FAILED.

This makes the operational flow faster and quieter: Codex does the part that adds judgment, while Python handles deterministic orchestration.

## Prompt Source

The local system prompt lives at:

```text
prompts/stock_analysis_system_prompt.md
```

It was copied from the original `SYSTEM_PROMPT`. Change it only after an explicit decision to change the analysis instructions.

The local user prompt template lives at:

```text
prompts/stock_analysis_user_prompt_template.md
```

## Standard Command

Human command:

```text
analiza RKLB
```

Operational meaning:

```text
python -m src.local_runner.run_one RKLB --run-full
```

The full runner executes:

```text
prepare -> generate -> validate -> upload real
```

Normal output is minimal:

```text
OK RKLB: análisis generado y subido.
```

or:

```text
FAILED RKLB: <error_type> - <error_message>
```

## Debug Commands

Use the individual phases only when debugging a run:

```powershell
python -m src.local_runner.run_one RKLB --prepare
python -m src.local_runner.run_one RKLB --generate
python -m src.local_runner.run_one RKLB --validate
python -m src.local_runner.run_one RKLB --upload-real
python -m src.local_runner.run_one RKLB --upload-real --execute-upload-real
```

The upload phase is dry-run unless `--execute-upload-real` is present.

The generation phase happens between prepare and validate:

```text
read output/RKLB/codex_input.md
write output/RKLB/latest.md
```

During prepare, the runner also tries to read the previous uploaded report:

```text
gs://stock-analysis-reports-naxo85/RKLB/latest.json
```

If it exists and has `analysis_status: "ok"`, `codex_input.md` includes a compact previous-analysis context: previous date, score, narrative, catalysts, key event, entry ranges, and exit target. Codex uses it as an operational memory and consistency anchor, not as a hard constraint.

If no previous report exists, the ticker is treated as new and the analysis starts from scratch. The runner does not fail or invent previous context.

Internally, Python reads `codex_input.md` and passes the full prompt through stdin to:

```powershell
codex exec -m gpt-5.6-sol -c 'model_reasoning_effort="medium"' --output-last-message output/RKLB/latest.md -
```

El análisis individual y los perfiles de trading y core fijan `gpt-5.6-sol`
con `medium`. El batch de core detecta automáticamente `tickers_core.json`.
Ambos valores se pasan explícitamente a Codex, sin depender de la configuración
global. Se pueden sobrescribir con `--model` y `--reasoning-effort`.

Codex only generates markdown. Python handles validation, JSON, uploads, and logs.
The HTML conversion is deterministic and does not invoke Codex or consume tokens.

## Model And Effort Benchmark

Use the isolated benchmark runner to compare models or reasoning efforts without
touching `latest.md`, `latest.json`, or GCS:

```powershell
python -m src.local_runner.benchmark_models RKLB
```

The default comparison is:

```text
gpt-5.6-terra:xhigh
gpt-5.6-sol:medium
```

Pass explicit candidates to reuse the tool for future comparisons:

```powershell
python -m src.local_runner.benchmark_models RKLB `
  --candidate gpt-5.6-terra:high `
  --candidate gpt-5.6-sol:medium
```

A single candidate is also supported for adding a historical baseline:

```powershell
python -m src.local_runner.benchmark_models RKLB --reuse-input `
  --candidate gpt-5.5:medium
```

Entry-stability regressions can reuse an exact frozen input and override only
the current price while explicitly keeping news, supports, options, and all
other context unchanged:

```powershell
python -m src.local_runner.benchmark_models RKLB `
  --input-path benchmarks/RKLB/<RUN_ID>/input/codex_input.md `
  --scenario-price 75 `
  --candidate gpt-5.6-sol:medium `
  --candidate gpt-5.6-terra:xhigh
```

The runner prepares the ticker once and freezes that exact `codex_input.md`,
including the same previous uploaded analysis, for every candidate. Candidate
order and labels are randomized. Each candidate runs in a fresh `codex exec`
session and writes only below:

```text
benchmarks/<TICKER>/<RUN_ID>/
```

For every candidate the benchmark records:

- input, cached-input, output, and reasoning token usage exposed by Codex;
- optional coarse five-hour and weekly snapshots via
  `--include-coarse-quota` (diagnostic only, never used to rank candidates);
- elapsed time, deterministic validation, and basic report-size signals;
- raw Codex JSONL events and separate Markdown/HTML reports.

Open `blind_review.md` first and score reports A/B before opening
`identity.json`. `comparison.json` contains label-based consumption differences.
The benchmark never uploads artifacts. Use `--reuse-input` only when intentionally
testing an already prepared `output/<TICKER>/codex_input.md`.

Five-hour and weekly percentages are account-wide integers. Rounding and
concurrent activity make their per-run deltas unsuitable for model comparison.
The benchmark therefore omits them by default and relies on exact per-turn token
usage from `events.jsonl`. `account/usage/read` is also unsuitable here because
it reports aggregated activity summaries and daily buckets, not one command.

## Full Run

A complete single-ticker run is launched with:

```powershell
python -m src.local_runner.run_one RKLB --run-full
```

That runs:

```text
prepare -> generate -> validate -> upload real
```

It records a run log under `logs/RKLB/` and prints only the OK/FAILED line.

Use the debug `--upload-real` command without `--execute-upload-real` when you want only a dry-run of the upload phase.

If `python` does not resolve inside Codex, use:

```powershell
& 'C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe' -m src.local_runner.run_one RKLB --prepare
```

## GCS Output

Real latest paths:

```text
gs://stock-analysis-reports-naxo85/RKLB/latest.md
gs://stock-analysis-reports-naxo85/RKLB/latest.html
gs://stock-analysis-reports-naxo85/RKLB/latest.json
```

Successful snapshots:

```text
gs://stock-analysis-reports-naxo85/RKLB/YYYY-MM-DD/HH-MM-SS.md
gs://stock-analysis-reports-naxo85/RKLB/YYYY-MM-DD/HH-MM-SS.html
gs://stock-analysis-reports-naxo85/RKLB/YYYY-MM-DD/HH-MM-SS.json
```

After each executed real upload, the runner maintains a bounded archive:

- `latest.md`, `latest.html`, and `latest.json` are always preserved;
- the five most recent successful snapshot sets are preserved;
- the two most recent failed snapshots are preserved;
- older snapshot objects for that ticker are deleted;
- `history.json` keeps compact long-term fields such as date, price, score,
  entry ranges, stops, target, state, catalysts, and next event.

Archive maintenance is non-blocking: an upload that already succeeded is not
reported as failed solely because listing, history update, or pruning fails.

Failed snapshots:

```text
gs://stock-analysis-reports-naxo85/RKLB/YYYY-MM-DD/HH-MM-SS.error.json
```

## Dry-Run And Test Upload

Real upload dry-run:

```powershell
python -m src.local_runner.run_one RKLB --upload-real
```

Test prefix dry-run:

```powershell
python -m src.local_runner.run_one RKLB --upload-test
```

Execute test prefix upload:

```powershell
python -m src.local_runner.run_one RKLB --upload-test --execute-upload-test
```

Test prefix:

```text
gs://stock-analysis-reports-naxo85/_local_test/RKLB/
```

## Validation

Validation keeps the existing parser contract:

- `Valoración: X / 10`
- `Entrada`
- `Entrada ambiciosa`

If validation succeeds, `latest.json` has `analysis_status: "ok"`.
The same validation phase renders `output/TICKER/latest.html` with embedded CSS.

Successful `latest.json` reports also expose `report_schema_version: 2` for the
future Android app. The deterministic structure includes `decision`, `plan`,
`catalysts`, `next_event`, `changes`, and `alerts`; the Markdown remains the
human-readable source report.

App alerts intentionally exclude point-in-time price conditions such as
"inside entry". Events appear as alerts only when they are within seven days.
Routine weekly/monthly options expirations are retained in the structured
detail but never create a home-screen proximity alert.
Score changes are material at 0.7 points or on a category crossing. Plan alerts
ignore small numerical drift and require both a threshold change and a changed
reason: 1.5% for the main entry, 3% for the target, and 3% for the structural
stop. Ambitious entry and management-stop changes remain available in the
structured plan but do not create home-screen alerts.

If validation fails, `latest.json` has `analysis_status: "failed"` and the failure is visible.
No HTML is produced or uploaded for a failed analysis.

## Operational Response

Normal OK response:

```text
OK RKLB: análisis generado y subido.
```

Normal failed response:

```text
FAILED RKLB: <error_type> - <error_message>
```

Show details only when asked: score, entries, paths, timing, token estimates, or full errors.

## Future Batch

Future batch mode should read tickers from:

```text
gs://stock-analysis-reports-naxo85/config/tickers.json
```
El runner incluye explícitamente la fecha local del análisis en
`codex_input.md`. El markdown final debe mostrarla como
`Fecha del análisis: AAAA-MM-DD`.
