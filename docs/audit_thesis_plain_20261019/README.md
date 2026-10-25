# Tesis INTC en negrita — 19-10-2026

INTC en Mercado!AK13 conservaba `userEnteredFormat.textFormat.bold=true`; los demás campos y el enlace eran correctos. No corresponde a ninguna regla financiera vigente. El escritor de Tesis renovaba valor, nota y enlace sin fijar el peso del texto; el ordenador conserva el formato de la celda. No hay evidencia que permita atribuir quién o qué escritura histórica activó la negrita.

El usuario autorizó quitarla. La reparación real escribió únicamente `textFormatRuns` sobre la celda de INTC, con su tipografía/enlace existentes y `bold=false`. Sheets normalizó el fragmento uniforme a formato de celda; lectura posterior: `bold=false` tanto en userEnteredFormat como effectiveFormat, valor/nota/enlace exactos. La misma representación explícita se añade al fragmento de `_score_cell` para las actualizaciones futuras, sin ampliar máscaras ni tocar los otros campos de análisis.

23tests+3subcasos de análisis, enlaces y ordenación pasan. Parche de una línea funcional en la función importada, sobre la imagen activa inmutable del arreglo de enlaces. No cambia presentation_version15 ni vuelve a escribir46 puntuaciones; la celda actual ya está corregida. Sin modelos, informes o cambios de política financiera.

El script [de despliegue](../../scripts/deploy_thesis_plain_20261019.py) verifica por AST que la función activa coincide con la local salvo el único `bold=false`, y conserva runtime/tráfico/tags previos durante staging. Evidencias de build/health/activación se guardan en este directorio.

Activado100% como `stock-controller-thesis-plain-20261019`, imagen `sha256:07493149954f745ac094441bcc5c5e88f3b10cef84ac1eb5180205b7de5cd3e2`, build `ea5be3e4-fd68-4c0d-ba94-33a1bebacebd`.7tests+3subcasos dentro de la imagen, health autenticado200 y runtime idéntico (`55818844a728f2a7665d7ff7bdcddb0ee2c4a9ad1d21781c4619a78a781aed1b`). Los enlaces normalizados del parche anterior siguen cubiertos. La inspección de Google Sheets a100% mostró INTC con el mismo peso de letra que GOOG/NVDA y su enlace conservado. [Lectura antes/después](live_format_repair.json), [activación](active.json).
