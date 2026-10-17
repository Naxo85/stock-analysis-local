# Flujo local Codex

Estado vigente 17-10-2026: véanse [arquitectura](architecture.md), [contrato adaptativo](codex_adaptive_analysis.md) y [flujo individual](standard_analyze_workflow.md).

El motor normal utiliza Sol 6.1 medium para mantenimiento y high para full. El modelo devuelve datos financieros estructurados; el código valida y renderiza Markdown/HTML/JSON. El antiguo «Codex solo escribe latest.md desde codex_input.md» describe una ruta legacy, no el adaptativo vigente.

`config/codex_analysis.json` y los prompts efectivamente ensamblados determinan nuevas preparaciones 39. Los originales congelados conservan sus contratos. `incoming_from_gcp/` sigue siendo histórico.

## Diagnóstico y benchmarks

La [versión anterior de esta guía](history/local_codex_flow_before_audit_20261017.md) conserva el benchmark de modelos, perfiles antiguos, fases de generación Markdown y ejemplos de CLI. Esos ejemplos no fijan los modelos actuales ni autorizan llamadas pagadas.

`benchmark_models.py` prepara/genera candidatos y puede consumir modelos aunque no publique; no equivale a prueba offline de contrato ni validación de utilidad financiera. Evaluaciones futuras deben comparar entradas fechadas, referencias, calidad factual y resultados definidos de antemano. No se ejecutó benchmark ni experimento financiero durante esta auditoría.

Recuperación sin modelo usa recibos originales con sus guardas y limitaciones; no reanudar con prompts nuevos ni fabricar una respuesta para hacer pasar el contrato. Procedimientos actuales en [operaciones](operations.md) y [relevo](handoff_current.md).
