# Troubleshooting

> For portable installations, create and use
> `.\.venv\Scripts\python.exe` with `scripts\setup_new_pc.ps1`. Absolute paths
> tied to `C:\Users\ignac` below describe the original machine only.

## Python Resolution Inside Codex

In the user's normal terminal, `python --version` may work. Inside the Codex execution environment, `python` can still point to the WindowsApps alias:

```text
C:\Users\ignac\AppData\Local\Microsoft\WindowsApps\python.exe
```

That alias may fail with an access error. The `py` launcher may also be unavailable.

The real Python executable found during the RKLB milestone run was:

```text
C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe
```

If `python` or `py` fail inside Codex, use the full path:

```powershell
& 'C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe' --version
& 'C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe' -m src.local_runner.run_one RKLB --prepare
& 'C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe' -m src.local_runner.run_one RKLB --validate
```

## WinError 10013 Calling Slim Endpoint

The first `--prepare` attempt failed with:

```text
WinError 10013
Intento de acceso a un socket no permitido por sus permisos de acceso
```

This was caused by socket/network restrictions in the Codex sandbox while calling the slim endpoint.

The solution was to repeat `--prepare` with elevated permission only for the slim endpoint call. This still does not call Gemini, Vertex AI, `gemini-stock-analyze`, `stock-analyze-batch`, GCS upload, or any deploy command.

## SYSTEM_PROMPT Parsing

The prompt loader initially failed because `SYSTEM_PROMPT` in:

```text
incoming_from_gcp/gemini_stock_analyze/main.py
```

is defined as:

```python
SYSTEM_PROMPT = r"""...""".strip()
```

The original local parser only supported direct string literals. The fix was made in:

```text
src/local_runner/run_one.py
```

It now supports a string literal with optional `.strip()` without executing code from `incoming_from_gcp/`.

## Validation Behavior

If `output/{TICKER}/latest.md` is missing, empty, or does not contain parseable `Valoración`, `Entrada`, and `Entrada ambiciosa`, validation must fail visibly.

The runner should write:

```text
output/{TICKER}/latest.failed.json
```

with:

```json
{
  "analysis_status": "failed",
  "analysis_markdown": ""
}
```

It must not create or upload an empty `latest.md` as if it were valid.
# Apps Script: permisos insuficientes para ScriptApp.getProjectTriggers

Si aparece:

```text
Los permisos especificados no son suficientes para llamar a
ScriptApp.getProjectTriggers
```

añadir al `appsscript.json`, conservando los scopes existentes:

```text
https://www.googleapis.com/auth/script.scriptapp
```

Guardar el manifest y volver a ejecutar la acción para aceptar la nueva
autorización. La orden puede haberse subido a GCS antes del error, por lo que
conviene comprobar el último resultado antes de encolarla de nuevo.
