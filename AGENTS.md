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

When the user says:

```text
analiza core
```

run the real batch from `config/tickers_core.json` in GCS with `--max-parallel 2`, unless they specify a different scope.

For batch runs, `--max-parallel 2` is the stable tested setting. To target a sub-15-minute 34 ticker run, use `--max-parallel 6`. Do not exceed the runner cap of `8`; higher parallelism reduces elapsed time, not token usage.

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

Prefer the repository virtual environment:

```text
<repo>\.venv\Scripts\python.exe
```

Example:

```powershell
& '.\.venv\Scripts\python.exe' -m src.local_runner.run_one RKLB --prepare
```

If `.venv` does not exist, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_new_pc.ps1
```

## Windows / GCloud

When using Google Cloud SDK from Codex on Windows, prefer:

```powershell
cmd /c gcloud.cmd ...
```

Do not use bare `gcloud` from PowerShell. It may resolve to `gcloud.ps1`, which
is blocked by the local execution policy.

Prefer checked-in scripts for repeated operations. The operations map is:

```text
docs/operations.md
```
