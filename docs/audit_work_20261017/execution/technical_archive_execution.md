# Archivo técnico prospectivo: ejecución local

Fecha: 18 de octubre de 2026 (Europe/Madrid). Alcance adicional M 02/M 04/C 01. Implementación local e inactiva: ninguna adquisición nueva, llamada de modelo, publicación, despliegue, commit o modificación de la configuración activa. El archivo complementario no es una nueva guarda financiera.

## Resultado útil y límite

Se añadió un contrato validable e inmutable, un exportador local utilizable y la integración opt-in raw → slim → preparación. Conserva las observaciones que la captura ya había descargado y que antes se reducían a 20 sesiones y selecciones TOP/dirigidas. Esto prepara el estudio posterior de contexto y candidatos usando las barras realmente disponibles (M 02/M 04), y la revisión de contratos de opciones de los vencimientos muestreados (C 01). No ejecuta esas comparaciones, no demuestra rentabilidad y no completa ausencias del proveedor.

El replay exportó 184 inputs con historia de la colección deduplicada de 598 rutas: 46 por fecha del 13 al 16 de octubre, todos con 20 sesiones. Ninguno permite reconstruir 252 sesiones completas ni respuestas originales de cadenas completas. Los 1.938 bloques derivados con option_details son registros seleccionados, no contratos únicos ni cobertura del mercado. No se reconstruyen barras desde hashes, métricas o datos posteriores.

## Código e integración

- src/local_runner/technical_archive.py: codec puro technical-observations-v1, schema 1; copia portable idéntica en gcp_functions/support_resistances_raw/technical_archive.py.
- src/local_runner/archive_technical_observations.py: CLI local, escritura inmutable/idempotente y extracción del sidecar antes del contexto financiero.
- gcp_functions/support_resistances_raw/main.py: conserva filas y respuestas ya obtenidas dentro de la misma petición; añade el sidecar después de publicar el espejo financiero y sobre un diccionario nuevo.
- gcp_functions/support_resistances_slim/main.py: transporte opcional separado de la construcción financiera de slim.
- src/local_runner/run_one.py y adaptive_stage.py: extracción antes de guardar input.json. Preparaciones congeladas siguen su retorno previo sin recapturarse.
- src/local_runner/adaptive_policy.py: flag booleano apagado si falta, disponible sólo para nuevas preparaciones 40.
- tests/test_technical_archive_v40.py:39 casos, incluidos transporte y preparación reales con adaptadores simulados, negativos de cobertura/identidad y fallos no bloqueantes.

La colección local va a data/technical_archive/SYMBOL/<archive_id>.json cuando se habilita la preparación. El identificador es SHA-256 del contenido canónico y el descriptor incluye también el hash exacto del archivo escrito. Temporal, fsync y enlace exclusivo permiten creación inmutable: repetir bytes idénticos es idempotente y un conflicto de contenido es visible. No se añade base de datos, feed ni servicio.

## Evidencia conservada

1. Todas las filas diarias descargadas que consumió raw, no sólo las últimas 252. Son filas parseadas del proveedor, no bytes HTTP originales. Incluye símbolo, ventana solicitada, recepción local, snapshot_as_of, calendario y cierres adicionales. Conserva aparte consultas ya realizadas de SPY u otros benchmarks; excluye sólo el recibo primario por índice, incluso cuando otro historial tiene el mismo símbolo.
2. Cobertura sobre 252 sesiones completadas esperadas según ese calendario y snapshot. Declara inválidos, duplicados, huecos y filas abiertas/futuras, que conserva pero excluye de la ventana completada. Más de 252 filas recibidas no implica cobertura completa. Un hueco no se atribuye automáticamente a IPO o halt.
3. El response.text exacto de XML de respuestas exitosas cacheadas, con hash de su codificación UTF-8. No afirma conservar bytes HTTP originales ni headers. Endpoint y parámetros permitidos identifican la petición. No se copian tokens, autorización, cabeceras ni objetos requests.
4. Identidad y campos económicos presentes en XML: símbolo/root, vencimiento, strike, lado, tamaño y deliverable si existen. No inventa ausencias ni reconstruye deliverables desde ticker/strike. Contradicciones, formato desconocido o identidad incompleta impiden afirmar completa la muestra y quedan señalados junto al cuerpo conservado. Un options vacío reconocido es distinto de XML desconocido.
5. Vencimientos descargados e identidades validadas son conjuntos separados. sampled_capture_complete describe únicamente esa muestra esperada y su estructura/identidad verificable. market_complete, sincronía y verificación económica del deliverable permanecen false; fecha efectiva OI desconocida. No registra intentos fallidos ni afirma todo el mercado.
6. Recepción local, snapshot_as_of y fecha efectiva del proveedor son relojes diferentes. Un timestamp nuevo de recepción no renueva OI/Greeks. Exportar un original conserva su snapshot y hash originales; la fecha actual figura sólo en el resumen de ejecución.

## Independencia financiera y política de fallo

Raw exige EVALUATION_ARCHIVE_ENABLED=true y query evaluation_archive=1. La preparación exige además technical_archive_enabled=true y revisión 40. La configuración activa continúa 39 sin flag. Ausente/false no solicita ni genera sidecar. El extractor elimina siempre _evaluation_archive y _evaluation_archive_error, incluso apagado. Copia el contexto excluyendo primero ambos campos para no duplicar el XML que va a retirar.

Todos los imports y la construcción opcional de raw están dentro de un try específico. Error de empaquetado, tamaño, codec o serialización añade un error de archivo fuera de finanzas y mantiene la respuesta financiera. Fallos de disco, validación, hash o identidad del sidecar en el runner generan work/technical_archive_failure.json con fecha/error/hash y un aviso, continuando con slim limpio bajo las guardas existentes. No compran reparación, recaptura ni llamada adicional. Si tampoco se puede escribir el fallo, queda el error de persistencia en el log; no se declara que el archivo exista. El CLI, cuya única tarea es archivar, sí termina con error ante archivo inválido.

Un símbolo incompatible en el slim financiero real sigue siendo error de captura. Es distinto de un sidecar contradictorio, que por sí solo no invalida las finanzas. La guarda independiente de adquisición 40 de data rechaza underlying/vencimiento explícitamente contradictorios antes de caché y no depende de este flag.

Revisión independiente de la guarda final: _validate_option_chain_identity no compara root OCC directamente con el subyacente solicitado. Admite un root ajustado coherente con el símbolo contractual, identidad ausente y formatos no reconocidos. Sólo compara un OCC decodificado de forma segura con sus campos explícitos, vencimiento solicitado, lado y strike. El XML desconocido no se trata como cadena vacía. No se detectó un bloqueo financiero causado por un fallo del archivo opcional. La validación de cobertura del archivo puede ser más conservadora para roots ajustados cuya correspondencia económica desconoce; marca parcial, conserva datos y continúa finanzas.

## Replay de originales y costes

Resultado durable: .tmp/audit_execution_20261017/archive_replay_results.json.
Reproductor: .tmp/audit_execution_20261017/test_archive_original_replay.py.
Ejemplo CAT exacto: .tmp/audit_execution_20261017/archive_original_example.json.

El replay compara hashes de 598 originales antes/después; exporta los 184 con historia y repite cada exportación. Los 598 hashes permanecieron idénticos. Cada archivo exportado pasa validación y conserva exactamente filas, snapshot y hash del input original.

| Medición | Resultado |
|---|---:|
| Rutas originales inspeccionadas | 598 |
| Inputs con 20 sesiones exportados | 184 |
| Inputs sin historia conservada, omitidos | 414 |
| Historia 252 completa / opciones completas | 0 / 0 |
| Tamaño total de 184 archivos | 4.883.621 bytes |
| Mínimo / mediana / máximo por archivo | 23.930 / 26.125 / 29.547 bytes |
| Tiempo local, incluidas verificaciones y segunda exportación | 51,069 s |
| Fixture sintético:270 filas,2 respuestas XML,1 contrato | 29.677 bytes |

Los 184 inputs originales suman 452.017.498 bytes porque incluyen más contexto; el archivo derivado conserva sólo historia disponible y selecciones de opciones. Esta reducción no estima futuros XML. Los payloads nuevos están bajo .tmp/audit_execution_20261017/archive_originals/ y archive_fixture/, sin duplicarlos en archivos versionados.

Límites: 32 MiB por archivo, 8 MiB por respuesta, 32 respuestas, 2.000 filas por historial y 16 historiales adicionales. Activarlo añade serialización, validación, memoria temporal, almacenamiento y bytes raw→slim→runner; no descargas ni contexto al modelo. No se midieron latencia/p95 productivos, tarifa cloud ni distribución de tamaños de cadenas reales. Superar un límite conserva el análisis y deja visible la pérdida del archivo; no trunca y etiqueta completo.

## Pruebas y artefactos

- Primera integración:39 del archivo +20 de captura pasaron (59 total).
- Replay original:1 passed en 51,19 s; archivo archive_replay_test.log.
- Regresión final sobre raw con guarda de data:197 tests +5 subtests, exit 0,12,78 s. Incluye 44 datos,29 origins 39,20 captura,22 slim,39 archivo y 43 identidad. Evidencia de data: option_identity_combined_results.json con hashes de 17 fuentes.
- La medición de transporte aislada detectó ImportError de google.genai porque el fixture dependía del stub importado por otro módulo. Ese intento no valida transporte y queda descartado como resultado positivo. El cambio posterior sólo limita los mocks de SDK al ámbito del fixture en el fixture, sin cambiar expectativas ni fuente productiva. Resultado aislado final se añade abajo.

Negativos: hash/cobertura manipulados, XML desconocido, identidad contradictoria/ausente, vencimiento no descargado, vacío legítimo, parcial declarando cobertura de mercado, tamaños, disco y error de productor. Preparación guarda sólo slim limpio y reanudar un input congelado no lo recaptura. Harness safe_test_runner.py bloquea sockets externos y procesos no autorizados. No hubo llamadas de modelo ni descarga externa.

## Uso local inmediato y activación futura

Ejemplo sobre un original existente (el replay verificó este exportador local):

    .venv\Scripts\python.exe -m src.local_runner.archive_technical_observations --input logs/batch/2026-10-16/15-58-24/adaptive/CAT/input.json --output-root .tmp/archive-local

El CLI está disponible sin endpoints ni modelos y no activa conservación prospectiva. Para una futura activación autorizada, el paquete debe incluir codec portable y calendario de raw, transporte slim y extractor local. El candidato 40 mantiene el flag apagado. Tras instalar componentes compatibles se habilitarían explícitamente el entorno raw y la política local para nuevas preparaciones, observando la siguiente ejecución natural. No modifica modelos, firmas de recibos congelados ni informes publicados. Ningún paso externo se ha realizado aquí.

### Cierre de verificación aislada

Tras corregir exclusivamente el fixture de importación: 39/39 pruebas de archivo pasaron solas (3,56 s), y la medición aislada pasó (1 prueba, 0,66 s). Logs archive_standalone_tests.log y archive_mock_transport_test.log. Resumen con hashes actuales: archive_final_verification.json. No fue necesario repetir la suite integrada por este cambio de mocks.

Fixture de transporte sintético: 2 peticiones de opciones apagado y 2 encendido, contenido financiero raw y espejo idénticos. Slim limpio: 9566 bytes idénticos antes/después; sidecar canónico: 29713 bytes. Raw: 21416 → 51152 bytes; slim transportado con sidecar: 39302 bytes. Los historiales se simulan iguales en este fixture; el adaptador de historia se comprueba además en su prueba propia. Estas cifras no estiman cadenas ni latencia productivas. Resultado durable: archive_mock_transport_results.json.
