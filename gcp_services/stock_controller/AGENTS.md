# Agent Operating Notes

This repository is the clean implementation of the stock analysis system.

## Source of truth

- Follow `docs/plan_reconstruccion_sistema.md` for agreed architecture and scope.
- Treat `E:\stock-analysis-local` as read-only legacy reference unless the user
  explicitly requests a maintenance change there.
- Do not introduce investment rules that have not been discussed with the user.

## Migration discipline

- New runtime code must not import modules from `stock-analysis-local`.
- Before porting behavior, add a characterization test or fixture for it.
- Preserve one owner for each datum and one programmatic Google Sheets writer.
- Keep model decisions separate from deterministic preparation and validation.
- Keep architecture decisions in `docs/decisions/`.

## Local workflow

Prefer the repository virtual environment:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
```

Keep routine responses concise. Report tests that could not be run.

