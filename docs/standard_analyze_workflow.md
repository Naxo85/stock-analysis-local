# Standard Analyze Workflow

## Human Command

```text
analiza RKLB
```

## Meaning

Run:

```powershell
python -m src.local_runner.run_one RKLB --run-full
```

The runner performs:

```text
prepare -> generate markdown -> validate -> upload real -> minimal response
```

The engine is the local Codex runner. The slim endpoint supplies technical JSON. GCS stores reports and snapshots.

Individual phase commands are for debugging only:

```powershell
python -m src.local_runner.run_one RKLB --prepare
python -m src.local_runner.run_one RKLB --generate
python -m src.local_runner.run_one RKLB --validate
python -m src.local_runner.run_one RKLB --upload-real
```

## Real GCS Paths

Latest:

```text
gs://stock-analysis-reports-naxo85/RKLB/latest.md
gs://stock-analysis-reports-naxo85/RKLB/latest.json
```

Snapshots:

```text
gs://stock-analysis-reports-naxo85/RKLB/YYYY-MM-DD/HH-MM-SS.md
gs://stock-analysis-reports-naxo85/RKLB/YYYY-MM-DD/HH-MM-SS.json
```

Failure snapshot:

```text
gs://stock-analysis-reports-naxo85/RKLB/YYYY-MM-DD/HH-MM-SS.error.json
```

## Reader

Markdown:

```text
https://reports-714254943648.europe-southwest1.run.app?symbol=RKLB&format=md
```

JSON:

```text
https://reports-714254943648.europe-southwest1.run.app?symbol=RKLB
```

## Normal Response

```text
OK RKLB: análisis generado y subido.
```

or:

```text
FAILED RKLB: <error_type> - <error_message>
```

Details are shown only on request.
