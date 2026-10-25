# Enlaces de Tesis perdidos al ordenar — 19-10-2026

Corregido y activado en `stock-controller-report-links-sort-20261019` al100%. La lectura independiente del conector a las14:20:15UTC confirma **46/46 enlaces a la versión comprometida exacta y 46/46 puntuaciones/notas Tesis y Setup conservadas**. No se generó ni republicó ningún informe financiero.

## Causa demostrada y por qué reincidió

La escritura inicial de `_score_cell` ya incluía enlace de celda y rich text desde la reparación del13Oct. Pero Sheets normaliza un único fragmento uniforme: al leerlo devuelve `userEnteredFormat.textFormat.link`, omitiendo `textFormatRuns`. El ordenador global copiaba la celda normalizada y la escribía con la máscara `userEnteredValue,note,textFormatRuns,dataValidation,userEnteredFormat`. En esa operación, enmascarar pero omitir los fragmentos vacía también el enlace, aunque el payload conserve el enlace de formato. El valor y la nota sobreviven. El test anterior sólo copiaba objetos en memoria; no modelaba la normalización de Google entre escritura y lectura.

La hoja inicial tenía46 puntuaciones con valor/nota y **cero enlaces**. En SNDK V4 se restauró el enlace versionado original y se volvió a escribir exactamente el mismo valor/nota mediante el serializador y máscara anteriores: volvió a desaparecer. Con el serializador corregido, la misma operación real conserva el vínculo. No se atribuye esta pérdida a la generación del análisis ni al texto de la nota.

- [Lectura inicial](before_sheet.json).
- [Reproducción real del borrado](sort_reproduction.json).
- [Reproducción real con el parche](patched_sort_reproduction.json).

## Cambio y pruebas

`global_sheet_sort._writable_cell` reconstruye un fragmento uniforme cuando Sheets devuelve un enlace de celda sobre texto y omite los fragmentos. Conserva el formato original y los fragmentos parciales ya existentes; no añade rich text a números, fórmulas, texto vacío o texto sin enlace. `run_sync.presentation_version` pasa14→15 para que el escritor habitual repare la proyección de los informes existentes, sin llamadas de modelo ni cambio de fechas.

La caracterización previa falló en2 casos y pasó en2+3subcasos. Tras el cambio, **55pruebas+3subcasos** pasan en los módulos de Sheet, estructura, ordenación, enlaces, versión de sync y persistencia de puntuaciones. La imagen final ejecutó además los7tests de persistencia y normalización con3subcasos. El test de repetidas normalizaciones cubre la frontera que faltaba en la reparación anterior. La reproducción real complementa la simulación; no se presenta el test unitario como una llamada a Sheets.

- [Fallo previo](baseline_tests.xml), [regresión55](regression_tests.xml).
- [Test nuevo](../../gcp_services/stock_controller/tests/test_normalized_report_link_sort.py).

## Activación y reparación

Se construyó un parche de dos módulos sobre la imagen activa inmutable `bc36dc3f00617dcc98e3711507ca13cdc9243906a27dad9fe8a2c5b53eeb3559`, sin copiar el árbol local con otros cambios. Imagen resultante `643a44e2c32b15b84a1dbdb26fb3b81971576585086c1bef891a5b31fac77336`, build `02e21b21-9525-4071-951c-bce4acf04e6c`. El primer build se detuvo antes de desplegar por una comprobación de versión en una copia fuente no importada; se conservó el fallo y se limitó la migración15 al módulo realmente importado. El serializador se verificó y corrigió en ambas copias equivalentes.

Staging sin tráfico, health autenticado200 y activación100% preservaron runtime, variables, secretos, tags existentes y compatibilidad manifest/publication40. Digest de runtime antes/después: `55818844a728f2a7665d7ff7bdcddb0ee2c4a9ad1d21781c4619a78a781aed1b`. La revisión anterior sigue disponible para rollback. Un rollback debe conservar la semántica de enlaces normalizados; volver al serializador anterior reintroduciría el defecto.

`POST /analysis/refresh` mediante el controller activado terminó `published`,46tickers/46strengths, sin ausentes,19requests y **reordered=true**, en18,398s. La reparación normal y la ordenación se ejercitaron juntas. La comparación por ticker posterior usa los46 `publication.json` canónicos autenticados como autoridad de cada URL. Todos coinciden; puntuaciones y notas Tesis/Setup son exactas frente a la lectura inicial, incluida la advertencia de LRCX. Su fallo anterior no se recuperó ni se presentó como análisis nuevo.

La inspección de Google Sheets en navegador autenticado mostró las puntuaciones subrayadas y reconoció en SNDK V4 el enlace versionado exacto junto a la nota original. No hubo edición financiera por navegador.

- [Versiones canónicas esperadas](expected_links.json), [lectura posterior](after_sheet.json), [comparación46/46](verification.json), [segunda comprobación14:23UTC](final_check.json).
- [Paquete exacto](package.json), [build final](build_status.json), [staging](staged.json), [health](staged_health.json), [activación](active.json), [refresh con ordenación](refresh.json).
- [Script de despliegue con invariantes](../../scripts/deploy_thesis_links_20261019.py).

Modelos, política41, ITV, pesos, visibilidad65/sólido70, universo, cartera, informes/anclas/fechas y fuentes permanecen fuera de este cambio. El arreglo cubre la causa reproducida; no promete inmunidad frente a cualquier futura escritura externa a la hoja.
