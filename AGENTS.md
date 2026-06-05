# Agent Operating Notes

This repository is the local control center for the stock analysis system.

The daily analysis engine is the local Codex runner. `incoming_from_gcp/` is a legacy reference snapshot.

## Standard Workflow

When the user says:

```text
analiza RKLB
```

run the standard ticker flow:

```text
prepare -> generate markdown -> validate -> upload real -> minimal response
```

For `RKLB`, that means:

```powershell
python -m src.local_runner.run_one RKLB --run-full
```

Use the slim endpoint for technical JSON. Use GCS for final reports and snapshots. Keep the source-of-truth prompt in `prompts/`.

If the user asks for dry-run, use `--upload-real` without `--execute-upload-real`.

When the user says:

```text
analiza todos
```

run the real batch from `config/tickers.json` in GCS with `--max-parallel 2`, unless they specify a different scope.

## Responses

Normal successful response:

```text
OK RKLB: análisis generado y subido.
```

Normal failed response:

```text
FAILED RKLB: <error_type> - <error_message>
```

Keep routine responses quiet. Do not show internal steps, paths, scores, entries, stops, targets, timings, token estimates, or markdown excerpts unless the user asks for details.

## Failure Visibility

Validation keeps failures visible with `analysis_status: "failed"` in JSON. Failed runs should not make old data look new.

## Python In Codex

If `python` or `py` do not resolve inside Codex, use:

```text
C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe
```

Example:

```powershell
& 'C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe' -m src.local_runner.run_one RKLB --prepare
```
