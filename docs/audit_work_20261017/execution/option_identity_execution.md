## Guarda adicional H08/H10: identidad explícita de opciones (18 octubre)

Este hallazgo adicional se demostró con transporte simulado, no en un incidente histórico. Antes, una solicitud CAT/23-Oct admitía un contrato que declaraba OTHER/30-Oct y el observador dirigido lo rotulaba disponible bajo23-Oct con OI100 y gamma1.0M. Un XML <garbage/> se interpretaba como cadena vacía. Se conserva la copia exacta previa en option_identity_before_main.py; option_identity_before_after.py/json conserva el control antes/después y hashes.

| Referencia | Guarda adicional | Evidencia y alcance |
|---|---|---|
| H08 | Identidad de adquisición separada de elegibilidad OI/gamma: underlying explícito distinto, vencimiento explícito distinto, OCC inequívoco contrario a fecha solicitada/campos presentes y raíz XML de cadena desconocida se rechazan antes del cache | Control sintético original pasa antes y falla después; no se demuestra ningún informe histórico contaminado |
| H10 / procedencia | Cuerpo de proveedor contradictorio no se convierte en observación completa; esta verificación actúa con archivo opcional apagado o encendido | No mide frescura adicional, no cambia H10a/b anteriores ni depende del éxito del archivo de investigación |

La raíz OCC no se compara automáticamente con el ticker: raíces ajustadas coherentes se admiten. Campos ausentes, símbolos no decodificables con seguridad y vacíos legítimos <options/> / <options>null</options> mantienen su semántica. Una fecha OCC inequívoca distinta de la solicitada se rechaza incluso sin expiration_date. El archivo opcional sigue siendo no bloqueante; ningún fallo de disco/formato de archivo se ha convertido en guarda financiera.

43 pruebas específicas offline PASAN sobre staging: contradicciones independientes, caso original, fecha OCC sin campo de vencimiento, identidad ajustada, ausencia legacy, cache y capturas on/off. El replay antes/después conserva iguales los controles de raíz ajustada (multiplier150), campos ausentes y cadena vacía legítima. Manifest de2archivos: option_identity_manifest.json; resultados: option_identity_test_results.json. La aplicación y regresión combinada posteriores se documentan abajo. No fuentes externas, modelos ni publicación.


### Verificación final aplicada

Raíz aplicó option_identity_manifest.json y los dos hashes destino coinciden exactamente con el manifiesto (raw fc24e74b6656255cd3f027ba04ec50279437dc345a7750dd76b4d2c4944b2d0b). La regresión combinada sobre fuentes aplicadas PASA:197 tests +5 subtests, exit_code0,12.78s. Desglose44 datos,29 orígenes39,20 captura,22 slim,39 archivo y43 identidad. Los129 avisos son deprecaciones datetime.utcnow ya existentes, incluidos replays legacy; no fallos.

Comando exacto desde E:/stock-analysis-local:

```text
E:\stock-analysis-local\.venv\Scripts\python.exe -B .tmp\audit_execution_20261017\safe_test_runner.py -- test_data_measurements_v40.py test_option_origins_v39.py test_capture_routing_v23.py tests\test_support_resistances_slim_evidence.py tests\test_technical_archive_v40.py tests\test_option_response_identity_v40.py
```

Resultado y hashes de17 archivos en option_identity_combined_results.json. Controles finales: contradicciones no entran en cache ni se convierten en origen disponible; con archivo apagado/encendido el rechazo es el mismo. Raíces ajustadas coherentes, campos ausentes, símbolos no decodificables y vacíos legítimos conservan valores/cache. Sidecar y errores de archivo permanecen fuera de modelo/espejo; fallo opcional no bloquea finanzas. No apareció un defecto que requiriera otra edición. Los43 casos de identidad y39 de archivo están incluidos en197, no se suman de nuevo. No hubo red, modelos, publicación ni edición de originales.
