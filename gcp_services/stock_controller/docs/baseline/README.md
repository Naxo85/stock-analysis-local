# Baseline

Este directorio conserva evidencia no secreta del sistema `legacy` antes de
migrar cada capacidad.

Contenido:

- `observed_state_2026-09-05.md`: lectura humana de infraestructura y flujos.
- `sheet_formulas_2026-09-05.md`: formulas vivas recuperadas de la hoja.
- `../../baseline/legacy_source_manifest.json`: hashes de fuentes efectivas.
- `../../baseline/deployed_services_2026-09-05.json`: revisiones observadas.
- `../../baseline/universe_2026-09-05.json`: universos exportados por la hoja.
- `../../tests/characterization/fixtures/market_metrics.json`: casos dorados.
- `../../tests/characterization/fixtures/sheet_metrics.json`: formulas y casos de hoja.
- `../../tests/characterization/fixtures/analysis_report.json`: contrato sintetico de informe.

Un snapshot no convierte una pieza en correcta ni en candidata automatica a
migracion. Solo permite saber con precision que comportamiento se esta
comparando.
