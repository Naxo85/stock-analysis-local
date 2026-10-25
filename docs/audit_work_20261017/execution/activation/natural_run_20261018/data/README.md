# Fuentes del lote natural del 18-10-2026

Se examinaron las **46 preparaciones** de `logs/batch/2026-10-18/09-08-40`, sus contratos congelados, progreso, capturas originales IBKR y archivos técnicos. Esta auditoría sólo lee artefactos locales; no llama proveedores/modelos, no publica y no modifica los históricos.

## Resultado de los controles

| Área | Evidencia real | Límite de lo demostrado |
|---|---|---|
| Admisión | 46/46 inputs reproducen `data_ready` con su fecha de preparación; contrato/routing40 | No se usa la fecha de hoy para rejuvenecer inputs |
| Sesiones y volumen | 46 ventanas de20 sesiones, hasta16 Oct, sin duplicados ni OHLCV inválidos. Fecha, acciones y volumen relativo a20 d recalculados46/46 | Lote dominical; no ejercita rechazo natural de una vela intradía abierta |
| Cotización | 46 quotes disponibles con timestamp del proveedor y sesión esperada16 Oct | Edad de fin de semana explícita; disponible no equivale a cotización en vivo del domingo |
| Opciones | 46 capturas completas de vencimientos muestreados; 60 identidades dirigidas y180 registros por vencimiento con OI reproducido | No cobertura de todo el mercado ni observaciones simultáneas verificadas |
| Orígenes fueraTOP | 7 identidades en6 tickers observadas sin depender del ranking | Available no significa soporte viable ni obliga a conservarlo |
| Unidades | 46 straddles cumplen move_abs/precio=move_pct en fracción, con unidades explícitas y probabilidad=none | No distribución probabilística calibrada |
| Adversidad | 503 objetos path reproducidos exactamente desde los archivos, pasando por la limpieza real del slim; orden intradía desconocido en503 | No son503 operaciones ni ensayos independientes;45 tickers tienen algún rebote positivo que acaba con cierre negativo |
| Archivo | 46 archivos válidos por hash/esquema,54.824.820 bytes,46 capturas de opciones completas y34 ventanas anuales completas | 12 declaran historia anual incompleta; no se presenta como datos perfectos |
| Contexto de modelo | 0 campos de cuerpo/identidad de archivo técnico en los46 triage.input;0 auxiliares retirados presentes en slim actual | Los antecedentes históricos conservan su propia representación |
| Tenencia | 46 bools de input coinciden con ruta y procedencia del universo Mercado seleccionado | No ejercita el fallback individual/manual a Mercado: los46 tenían autoridad explícita de universo |

El archivo anual conserva, sin corregir ni inventar, nueve barras del19-03 con OHLC no numérico (AMAT,HIMS,LRCX,MP,MRVL,OKLO,RKLB,SOFI,USAR); CAT17-10-2025 yTSM16-03-2026 tienen close menor que low; SPCX tiene historia corta y la primera fila11-06 inválida. Se declaran estas carencias y las observaciones afectadas no se convierten en resultados negativos ficticios. Los20 d recientes siguen completos. No atribuimos las inconsistencias a splits, dividendos o causa del proveedor sin evidencia.

Los7 orígenes fueraTOP son CAT730/735, IBKR84, INOD50, IREN28, MRVL240 yTSM410. APP250/255 sí están ambos enTOP hoy; su éxito nuevo no recupera el fallo16 Oct ni vuelve este caso una prueba fueraTOP. Las1.378 identidades de contrato visibles conservan4 OI cero y21 bid cero: cero no se convierte en ausencia ni acredita liquidez. No hubo OI desconocido ni OI positivo con gamma ausente entre las180 observaciones dirigidas; ese control negativo no fue ejercitado aquí.

Las132 diferencias del primer replay bruto de trayectorias eran exclusivamente claves con null eliminadas por `support_resistances_slim.main._clean`. Al aplicar la función real,503/503 coinciden exactamente. Los resultados conservan el indicador previo para que esta explicación sea verificable, sin cambiar datos ni expectativas financieras.

## Noticias: cobertura real y coste

Todas las **118 capturas** terminaron con evento terminal recibido y hasMore=False:46 noticias generales,46 analistas y26 backfills de prepare desde el ancla full. Los92 logs de fuente no contienen errores/timeouts/retry; el progreso no declara first_error, reinicio ni deferred_retry, y los46 earnings tienen attempts=1. Las cinco noticias vacías (CLS,INOD,LEU,MP,USAR) provienen de cachés no vacías agotadas y filtradas a su ventana; no de una descarga fallida convertida en vacío. Alcance: caché disponible del proveedor, no exhaustividad del universo de noticias.

Hubo341 páginas,86.838 filas brutas sumadas por adquisición y1.846 filas filtradas sumadas; son conteos repetidos entre capturas, no noticias independientes. **239 páginas** están enteramente antes de la ventana solicitada y consumen1.652,875 s acumulados. Su propósito actual es certificar EOF; no contienen nuevas noticias útiles para esa ventana.

El proceso de fuentes dura2.929,617 s (48 min49,6 s), frente a3.112,627 s del lote completo. Su desglose observado es1.567,9 s noticias,1.055,59 s analistas y306,127 s de resto (backfill de consenso, persistencia y otros costes no desglosados aquí). Los26 backfills de noticias durante prepare añaden470,465 s de procesos parcialmente solapados; **no deben sumarse a la duración de pared**.

En cada uno de los46 tickers, las2–3 capturas tienen idéntica secuencia de identidad, texto y hora. NVDA lo muestra con tres capturas de14 páginas y4.065 identidades:337,156 s de adquisición, con130,75 s del proceso inicial de noticias,95,64 s del proceso de analistas y122,98 s del backfill. El primer feed usa CURRENT−24 h; prepare necesita la cobertura del ancla full−24 h. No se puede resolver omitiendo el backfill o cambiando la etiqueta temporal del feed corto.

## Alternativa concreta evaluada localmente

Se derivaron las118 ventanas conservadas desde la **primera captura bruta de cada ticker**, con filtro exacto y comparación ordenada de provider/articleId/texto/hora: **118/118 hashes iguales**. De las341 páginas observadas,134 pertenecen a esas46 primeras capturas y207 a descargas repetidas. Las repeticiones consumieron1.455,060 s de adquisición observada. Es evidencia de redundancia de este corpus, **no un ahorro de latencia desplegado ni garantía de igualdad en una sesión con noticias nuevas**. Tampoco prueba equivalencia del parser de analistas, actualizaciones de consenso o eventos downstream; esta evaluación compara la materia prima y sus vistas temporales.

Propuesta pendiente: adquirir una sola captura por ticker/proveedor dentro de una preparación, con inicio que cubra las ventanas de noticias, analistas y ancla, hasta EOF real; congelar el archivo por hash, contract/provider, consulta, respuesta, fecha y pruebas de cobertura; derivar vistas separadas conservando el timestamp real. Nunca relabelar como nueva una captura antigua ni ampliar su cobertura a horas posteriores. Si está caducada o cambian proveedor/contrato/alcance, obtener otra captura explícita.

Afecta a `update_analysis_sources_pipeline` (orquestación hoy secuencial news→analistas), los consumidores/probes de noticias y analistas, y `adaptive_stage.prepare` (backfill por ventana de ancla). Requiere transmitir el ancla/ventanas necesarias antes de adquirir y enlazar cada vista a su captura. Debe probarse con estos118 casos más negativos de ventana insuficiente, nueva noticia entre snapshots, timestamps, error/timeout, deduplicación, identidad y last_good. Este encargo no implementa el cambio, no reduce clocks, no elimina EOF ni abre concurrencia IBKR.

## Evidencias

- `aggregate.json`, `per_symbol.json`: censo46 y comparación16 Oct.
- `raw_acquisitions.json`, `redownloads.json`: las118 capturas, páginas, tiempo y fingerprint.
- `offline_window_equivalence.json`:118 derivaciones, hashes, rutas y límites.
- `archives.json`:46 archivos, cobertura y errores declarados.
- `supplementary_checks.json`:503 replays, historial de comparación bruto, barras inválidas, contratos, vacíos y92 logs.
- `additional_numeric_checks.json`: volumen/straddle46 y7 orígenes fueraTOP.
- `checks_summary.json`: recuentos de controles.
- `audit_data.py` y`audit_supplement.py`: reproducción local, sin red. `evidence_manifest.json` identifica los archivos de entrada leídos; `INDEX.sha256.json` identifica esta entrega.

No se encontró una anomalía de admisión en los46 inputs. Sí se encontró una ineficiencia de integración medible. El lote ejercita la adquisición completa, las nuevas representaciones y su propagación; no demuestra alfa, no prueba todos los negativos y no completa la investigación de pesos/ranking/cadencia.
