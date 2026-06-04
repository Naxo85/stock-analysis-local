# Agent Operating Notes

This repository is the local control center for the stock analysis system.

## Hard Rules

- Do not use Gemini, Vertex AI, `gemini-stock-analyze`, or `stock-analyze-batch` as the analysis motor.
- Do not modify `incoming_from_gcp/` unless the user explicitly asks for it.
- Do not upload to GCS without explicit user confirmation.
- Do not deploy Cloud Run functions or Apps Scripts without explicit user confirmation.
- Do not commit unless the user explicitly asks for a commit.
- Do not store secrets, tokens, service-account files, or credentials in the repo.

## Local Analysis Flow

The daily analysis motor is local Codex/ChatGPT Plus assisted generation.

GCP remains auxiliary infrastructure:

- slim endpoint for technical JSON;
- GCS bucket for report storage when uploads are explicitly enabled;
- reader endpoint for Google Sheet/app consumption;
- Apps Script for Sheet integration.

## Python In Codex

Inside Codex, `python` or `py` may fail even if Python works in the user's terminal. If needed, use:

```text
C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe
```

Example:

```powershell
& 'C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe' -m src.local_runner.run_one RKLB --prepare
```

## Failure Visibility

Failures must stay visible.

- Do not create an empty `latest.md` as if it were valid.
- If validation fails, create a JSON failure artifact with `analysis_status: "failed"`.
- Do not let old successful data appear to be a fresh successful run.

## Reference Snapshot

`incoming_from_gcp/` is the imported reference snapshot of the previous GCP system. Treat it as source material and historical reference, not as the place for new local implementation.
