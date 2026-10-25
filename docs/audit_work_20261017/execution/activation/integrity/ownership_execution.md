# Corrección de autoridad y procedencia de propiedad

Se corrigieron dos desviaciones del flujo habitual sin cambiar cartera, selección de tickers, fuentes remotas ni modelos. Individual/manual consulta Mercado según AGENTS; listas GCS conservan owned booleano explícito de la lista seleccionada. Ausente o no booleano exige una coincidencia única y booleana en Mercado; desconocido/ambiguo/error falla antes de Gateway/modelo. No se infiere owned=false de ausencia en lista. Los overrides individuales --owned/--no-owned siguen siendo explícitos.

## Evidencia de fuentes, sin inventario de cartera

| Fuente | Fecha declarada | Registros | Generación leída |
| --- | --- | ---: | ---: |
| config/tickers.json | 2026-09-04T14:32:47.719Z | 38 | 1788532368490683 |
| config/tickers_core.json | 2026-09-03T13:23:52.349Z | 30 | 1788441832999840 |
| config/tickers_market.json | 2026-10-16T15:54:45.057Z | 46 | 1792166085774014 |

Las tres fuentes reales tienen registros únicos y booleanos explícitos. Trading/Mercado presentan 18 discrepancias entre símbolos comunes y core/Mercado 4; son diferencias entre fuentes y fechas, no afirmaciones sobre cantidades actuales ni autorización para sincronizar posiciones. No se escribió ninguna de esas configuraciones. Replays de copias observadas conservaron universo/orden/booleanos/etiquetas exactos 38/30/46, con cero consultas adicionales para estos datos completos. Hashes de las copias en ownership-replay-results.json.

LEU y MRNA mantienen false en ambas fuentes. El input LEU ya admitido permanece exactamente con SHA256 aee374b1253c52537a0e4f11c9500cc1aa69cbbdfffa0e5528cc9391a647a3e0; no se reescribió su evidencia histórica. La diferencia de TLN se comunicó antes de su preparación. Esto evita reinterpretar el canario congelado por una corrección posterior.

## Trazabilidad mínima de nuevas preparaciones

BatchConfig conserva el contexto de cada TickerRecord resuelto y lo pasa sólo a prepare mediante --ownership-json. input.ownership conserva symbol, owned, selection_source y ownership_source. selection_source identifica la lista/selección; ownership_source conserva su etiqueta original o, para resolución faltante/manual, la URI Mercado ya consultada. No se deduce una autoridad independiente a partir de una etiqueta arbitraria. La validación exige claves exactas, símbolo y booleano idénticos a la ruta, fuente de selección no vacía y etiqueta string/null; limita el argumento a 8 KiB. No hay consultas nuevas.

La traza queda incluida en el input que el recibo/binding existente protege desde su congelación. No autentica criptográficamente una fuente externa, no certifica posiciones actuales ni añade una generación GCS que no se capturó en el flujo normal. Las lecturas anteriores de inspección sí guardan sus generaciones en esta evidencia separada. Las preparaciones/checkpoints existentes no reciben campos retroactivos; la salida temprana preserva bytes/policy/prompts. Un stage histórico sin argumento opcional conserva su contrato.

## Cola e interfaz

command_worker.build_execution (373) selecciona sys.executable -m run_one o run_batch por cada orden; execute_command (548) crea Popen nuevo. El worker no conserva la política financiera en memoria. run_batch inicia también un proceso adaptive_stage por etapa. El launcher normal usa .venv, salvo override explícito STOCK_ANALYSIS_PYTHON. Nuevas órdenes tras la activación recargan config 40 sin reinicio; sólo el mismo command_id incompleto puede reanudar un checkpoint congelado (_resume_batch_execution_if_available, 479). Dos acciones de interfaz verificadas con Popen simulado, sin invocar procesos/modelos. No se detuvo ni reinició el worker.

## Verificación y alcance

Primera regresión: 51 tests y 31 subtests pasan en 1.50 s, con red/procesos externos bloqueados; cubre datos ausentes/no booleanos, fuentes explícitas, duplicados, fallo de lectura, lifecycle individual y pipeline. Evidencia: ownership_test_results.json. Replays: ownership-replay-results.json. Después de aplicar la ampliación de procedencia, 76 tests y 45 subtests pasan en 3.33 s, incluyendo sus 6 casos nuevos y regresión de consumidores. Evidencia: ownership_provenance_test_results.json. Replays repetidos38/30/46 también confirman provenance_matches_resolved_records=true sin consultas adicionales.

Archivos seguros para conservación: este informe, local_readiness_review.md, individual_lifecycle_test_results.json, ownership_test_results.json, ownership_provenance_test_results.json y ownership-replay-results.json. No hace falta incorporar ownership-source-*.json ni ownership-authority-comparison.json (configuraciones/listados completos) a documentación durable.
