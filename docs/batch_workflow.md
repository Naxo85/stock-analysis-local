# Lotes de análisis: flujo vigente

Actualizado 17-10-2026. Leer antes [handoff_current.md](handoff_current.md). El motor diario es Codex adaptativo 39 para nuevas preparaciones; Web y el calendario Sol/Terra/Luna son compatibilidad explícita. El [historial de esta guía](history/batch_workflow_before_audit_20261017.md) conserva los incidentes antiguos sin presentarlos como lotes en curso.

## Universo y comandos

Estos comandos tienen efectos reales y solo se usan dentro de una solicitud autorizada de análisis. **Esta auditoría no los ejecutó.** Usar el Python del repositorio.

| Entrada | Universo real |
|---|---|
| `--from-gcs` / instrucción «analiza todos» de AGENTS | `config/tickers.json` |
| Menú Mercado / acción `analyze_market` | `config/tickers_market.json`; 46 tickers en la evidencia 16-10 |
| Core | `config/tickers_core.json` |
| `--tickers A,B` | Lista explícita; propiedad por registro vigente, no false supuesto |

No confundir estas listas ni sustituir una silenciosamente. La instrucción AGENTS de «todos» y el menú Mercado siguen usando rutas distintas; la auditoría deja esta discrepancia de intención abierta.

```powershell
& '.\.venv\Scripts\python.exe' -m src.local_runner.run_batch --from-gcs --upload-real --max-parallel 6
```

```powershell
& '.\.venv\Scripts\python.exe' -m src.local_runner.run_batch --config-gcs gs://stock-analysis-reports-naxo85/config/tickers_market.json --analysis-profile trading --update-analysts --update-ibkr-news --upload-real --max-parallel 6
```

```powershell
& '.\.venv\Scripts\python.exe' -m src.local_runner.run_batch --config-gcs gs://stock-analysis-reports-naxo85/config/tickers_core.json --upload-real --max-parallel 6
```

El ejemplo Core sin flags de actualización usa estados locales de noticias/analistas: `--config-gcs` por sí solo no los refresca. Para solicitar ese refresco se añaden explícitamente `--update-analysts --update-ibkr-news`; su ausencia puede producir bloqueo por frescura. No equivale al menú Mercado, que los incluye.

`--upload-real` activa publicación del batch. El batch no ofrece una simulación financiera completa sin publicación: la guarda exige ese flag salvo `--routing-plan`. Este último evita Gateway/modelos/uploads, pero puede leer configuración/referencias remotas; no es un test completamente offline.

`--analysis-mode reference` fuerza full para todos y consume modelos: solo con renovación expresa. El modo adaptativo normal no aplica el antiguo skip viernes/sábado. Concurrencia 6 es techo de modelos, puede reducirse por saturación; runner no supera 8.

## Fases y artefactos

```text
fuentes → prepare → analyze (medium / reparación / full según autoridad) → publish
```

Preparación y publicación pueden solaparse con análisis. El checkpoint determina qué fase falta. Un ticker fallido no debe bloquear los demás; el reintento de lote predeterminado es uno. Un input admitido al modelo permanece congelado; reintentar no debe convertirlo en otra captura ni regenerar una respuesta completada.

En `logs/batch/YYYY-MM-DD/HH-MM-SS/`:

- `strategy.json`, `pipeline_state.json`: estrategia y checkpoint.
- `source_update.json`, `sources/`: actualización y marcadores de fuentes cuando existen.
- `adaptive/<TICKER>/input.json`, `policy.json`, instrucciones/schema: contrato congelado.
- Responses, receipts, eventos/call logs: llamada exacta y evidencia de ejecución.
- `review.json` o `failure.json`: resultado financiero/local.
- `summary.json`, `tickers/`, `sheet_progress.json`, `stall_events.jsonl`: resultados, intentos y progreso.

C4/A9 son espejos. Comparar orden, checkpoint, heartbeat, review/failure y resultado publicado. `success` cuenta tickers publicados, no llamadas; `measured_model_usage` y presupuesto distinguen llamadas y reparaciones. `chatgpt_web_workers=3` puede persistir en metadatos aunque no haya navegador activo.

## Interrupciones y recuperación

Antes de cualquier acción: identificar orden/lote/estrategia exactos, comprobar actividad y lock, conservar originales y consultar el [protocolo actual](handoff_current.md). No iniciar otro lote para completar uno interrumpido ni reanudar un checkpoint Web como adaptativo.

`--resume-pipeline-from` continúa un checkpoint; no equivale a la recuperación sin modelo de un recibo. Esta última usa `src.local_runner.recover_adaptive_receipt` y copias bajo logs/recoveries. El `--execute` publica y requiere la autorización correspondiente. Un recibo anterior conserva su revisión.

**Limitación demostrada 17-10:** una revisión ya validada puede saltarse la comprobación de frescura actual y el bundle preparado no tiene cierre íntegro duradero suficiente. La recuperación no debe describirse como garantizada por sus guardas actuales; véase [auditoría](audit_analysis_system_20261017.md). Esta documentación no repara ni ejecuta esa ruta.

Si una orden terminal dejó progreso running, `progress_reconciliation` compara IDs y heartbeat; heartbeat posterior al cierre bloquea reconciliación. Es una modificación de progreso, no análisis ni recuperación financiera. No ejecutarla por apariencia de C4 sin comprobar evidencia.

## Fallos y compatibilidad

En adaptativo, un fallo guarda failure.json y se refleja en lote/orden; no se alcanza publish del ticker. El último informe válido conserva sus fechas. Los lectores de ese informe pueden no mostrar el intento fallido: defecto de observabilidad abierto. La publicación de error.json/latest.failed descrita en guías antiguas pertenece a otras rutas y no debe generalizarse.

Web solo con proveedor explícito; sus diagnósticos y reglas se conservan en [guía legacy](chatgpt_browser_provider.md). Las pruebas de navegador no son parte de la verificación del motor actual.
