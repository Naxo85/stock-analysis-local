# Flujo estándar de análisis individual

Vigente 17-10-2026. Leer [relevo](handoff_current.md) antes de diagnosticar o ejecutar. La solicitud `analiza RKLB` significa ejecutar el flujo autorizado completo:

```powershell
& '.\.venv\Scripts\python.exe' -m src.local_runner.run_one RKLB --run-full
```

Con proveedor predeterminado Codex y contexto individual, run_one delega en `adaptive_stage.run_individual`: full high según configuración, propiedad del registro vigente salvo override explícito, preparación y contrato congelado, JSON financiero, validación, render y publicación real. No es la secuencia legacy de pedir Markdown libre y parsearlo como autoridad.

```text
preflight/fuentes → prepare → full high → validar estructura financiera → render MD/HTML/JSON → publicar
```

No cambia la política normal de futuros lotes ni autoriza modificar el modelo. `--owned` y `--no-owned` son overrides explícitos; omitirlos no significa cartera ausente.

## Publicación y diagnóstico

GCS conserva latest, snapshots e historial; CURRENT y ancla full tienen roles distintos. Los artefactos exactos individuales se conservan bajo `logs/adaptive_individual/`. El estado fallido adaptativo permanece en failure/resultado, sin publicar un nuevo informe válido ni redatar el anterior.

Los flags sueltos `--prepare`, `--generate`, `--validate` de run_one pertenecen a la interfaz legacy de fases: no reconstruyen por sí solos el mismo contrato adaptativo del full individual. Para investigar un adaptativo se inspeccionan sus artefactos originales y funciones versionadas.

`run_one RKLB --upload-real`, sin `--execute-upload-real`, simula la subida de artefactos existentes. No es un full sin coste de modelo. Publicar, recuperar o regenerar exige alcance autorizado separado de una auditoría.

## Respuesta normal

```text
OK RKLB: análisis generado y subido.
FAILED RKLB: <error_type> - <error_message>
```

No mostrar detalles internos salvo petición. La [arquitectura](architecture.md) y el [motor adaptativo](codex_adaptive_analysis.md) describen garantías y límites; el [texto previo](history/standard_analyze_workflow_before_audit_20261017.md) conserva rutas antiguas de archivos/error sin convertirlas en garantías actuales.
