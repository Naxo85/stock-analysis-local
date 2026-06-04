# Local Codex Flow

This flow prepares one ticker locally, lets Codex generate the markdown, and validates the result without uploading anything to GCS.

It must not call Gemini, Vertex AI, `gemini-stock-analyze`, or `stock-analyze-batch`.

## Prompt Source

The local system prompt now lives at:

```text
prompts/stock_analysis_system_prompt.md
```

It was copied from `SYSTEM_PROMPT` in:

```text
incoming_from_gcp/gemini_stock_analyze/main.py
```

Do not edit this prompt unless there is an explicit decision to change the analysis instructions. `incoming_from_gcp/` remains the immutable reference snapshot; the runner uses the local prompt file first and falls back to the imported GCP file only if the local prompt file does not exist.

The local user prompt template lives at:

```text
prompts/stock_analysis_user_prompt_template.md
```

It is the local Codex equivalent of the `user_prompt` block in `_generate_analysis()`.

## Flujo Actual Repetible Para Un Ticker

The current flow has three scripted phases and one Codex-assisted phase.

1. Prepare local input:

```powershell
python -m src.local_runner.run_one RKLB --prepare
```

If `python` fails inside Codex, use:

```powershell
& 'C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe' -m src.local_runner.run_one RKLB --prepare
```

This generates:

```text
output/RKLB/codex_input.md
data/slim/RKLB/{timestamp}.json
logs/RKLB/{timestamp}.prepare.json
```

2. Codex-assisted generation:

Codex must read:

```text
output/RKLB/codex_input.md
```

and save the final markdown report as:

```text
output/RKLB/latest.md
```

This is still manual/Codex-assisted. The runner does not generate the markdown automatically.

3. Validate local output:

```powershell
python -m src.local_runner.run_one RKLB --validate
```

or:

```powershell
& 'C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe' -m src.local_runner.run_one RKLB --validate
```

If validation passes, it creates:

```text
output/RKLB/latest.json
```

If validation fails, it creates:

```text
output/RKLB/latest.failed.json
```

4. Test upload dry-run:

```powershell
python -m src.local_runner.run_one RKLB --upload-test
```

This prints the `gcloud storage cp` commands that would upload only to `_local_test/`.

5. Real test upload, only after explicit confirmation:

```powershell
python -m src.local_runner.run_one RKLB --upload-test --execute-upload-test
```

This can only write to:

```text
gs://stock-analysis-reports-naxo85/_local_test/RKLB/latest.md
gs://stock-analysis-reports-naxo85/_local_test/RKLB/latest.json
```

It must not touch:

```text
gs://stock-analysis-reports-naxo85/RKLB/latest.md
gs://stock-analysis-reports-naxo85/RKLB/latest.json
```

## Future Non-Interactive Generate Phase

A future `--generate` phase could be added only if there is an approved way to invoke Codex non-interactively. It would likely:

- read `output/{TICKER}/codex_input.md`;
- send it to the approved Codex interface;
- write only `output/{TICKER}/latest.md`;
- avoid Gemini, Vertex AI, `gemini-stock-analyze`, and `stock-analyze-batch`;
- run the same validator before any upload step.

This is not implemented yet. Today, markdown generation remains Codex-assisted.

## Python Command

Inside Codex on this machine, `python` may still point to the WindowsApps alias and `py` may be unavailable. If that happens, use the full Python path:

```powershell
& 'C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe' -m src.local_runner.run_one RKLB --prepare
```

The same path can be used for validation.

## Prepare

Run from the repository root:

```powershell
python -m src.local_runner.run_one RKLB --prepare
```

or, if the short command fails inside Codex:

```powershell
& 'C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe' -m src.local_runner.run_one RKLB --prepare
```

`--prepare` does this:

- Calls only the slim endpoint for the ticker.
- Saves the slim JSON under `data/slim/{TICKER}/`.
- Locates `SYSTEM_PROMPT` in `incoming_from_gcp/gemini_stock_analyze/main.py`.
- Creates `output/{TICKER}/codex_input.md`.
- Writes a prepare log under `logs/{TICKER}/`.

For the first RKLB run, it generated:

```text
data/slim/RKLB/2026-06-04T19-40-30Z.json
output/RKLB/codex_input.md
logs/RKLB/2026-06-04T19-40-30Z.prepare.json
```

## Generate latest.md With Codex

Open:

```text
output/RKLB/codex_input.md
```

Codex should use that file as context and save only the final markdown report as:

```text
output/RKLB/latest.md
```

The generated markdown must contain `Valoración`, `Entrada`, and `Entrada ambiciosa` in the format expected by the current Google Sheet parser.

For the first RKLB run, Codex created:

```text
output/RKLB/latest.md
```

## Validate

Run:

```powershell
python -m src.local_runner.run_one RKLB --validate
```

or:

```powershell
& 'C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe' -m src.local_runner.run_one RKLB --validate
```

`--validate` reads:

```text
output/RKLB/latest.md
```

It checks:

- The markdown is not empty.
- `Valoración: X / 10` exists and contains a numeric score.
- `Entrada` exists and contains a parseable price range.
- `Entrada ambiciosa` exists and contains a parseable price range.

If validation passes, it creates:

```text
output/RKLB/latest.json
```

If validation fails, it creates:

```text
output/RKLB/latest.failed.json
```

Local validation logs are written under:

```text
logs/RKLB/
```

For the first RKLB run, validation passed and generated:

```text
output/RKLB/latest.json
logs/RKLB/2026-06-04T19-45-06Z.validate.json
```

## analysis_status

`analysis_status: "ok"` means the markdown passed the minimum compatibility checks and `latest.json` was created with reader-compatible fields:

- `symbol`
- `generated_at`
- `model`
- `analysis_status`
- `slim_as_of`
- `latest_price`
- `analysis_markdown`
- `grounding`
- `slim_snapshot`

`analysis_status: "failed"` means the markdown was missing, empty, or failed one of the required parser checks. In that case the runner writes `latest.failed.json` and does not create a new valid `latest.json`.

This flow still does not upload anything to GCS and does not deploy any Cloud Run or Apps Script changes.

## Test Upload To GCS

After a ticker has a valid local `latest.md` and `latest.json`, the runner can prepare a GCS test upload under `_local_test/`.

Dry-run is the default:

```powershell
python -m src.local_runner.run_one RKLB --upload-test
```

or inside Codex if the short Python command fails:

```powershell
& 'C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe' -m src.local_runner.run_one RKLB --upload-test
```

The dry-run checks that `gcloud` exists, checks that both local files exist, and rejects the upload if `output/RKLB/latest.json` does not contain:

```json
{
  "analysis_status": "ok"
}
```

The test upload would use only these paths:

```text
gs://stock-analysis-reports-naxo85/_local_test/RKLB/latest.md
gs://stock-analysis-reports-naxo85/_local_test/RKLB/latest.json
```

It does not touch the real production paths:

```text
gs://stock-analysis-reports-naxo85/RKLB/latest.md
gs://stock-analysis-reports-naxo85/RKLB/latest.json
```

To actually upload to `_local_test/`, add the explicit execution flag:

```powershell
python -m src.local_runner.run_one RKLB --upload-test --execute-upload-test
```

Only run that command after reviewing the dry-run output.

After a real test upload, it can be checked with:

```powershell
gcloud storage ls gs://stock-analysis-reports-naxo85/_local_test/RKLB/
```
