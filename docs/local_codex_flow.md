# Local Codex Flow

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
- creating `latest.json`;
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

Internally, Python reads `codex_input.md` and passes the full prompt through stdin to:

```powershell
codex exec --output-last-message output/RKLB/latest.md -
```

Codex only generates markdown. Python handles validation, JSON, uploads, and logs.

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
gs://stock-analysis-reports-naxo85/RKLB/latest.json
```

Successful snapshots:

```text
gs://stock-analysis-reports-naxo85/RKLB/YYYY-MM-DD/HH-MM-SS.md
gs://stock-analysis-reports-naxo85/RKLB/YYYY-MM-DD/HH-MM-SS.json
```

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

If validation fails, `latest.json` has `analysis_status: "failed"` and the failure is visible.

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
