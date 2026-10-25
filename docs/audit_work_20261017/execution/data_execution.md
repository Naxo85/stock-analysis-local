# Ejecución local de correcciones de datos — 17 octubre 2026

Responsable: rama data_audit. Alcance autorizado H01/H02/H07/H08/H09/H10a/H10b y M01 raw/slim, con hook M03 coordinado con raíz. Sin llamadas al broker/proveedor, modelos, batches operativos, cloud, recovery, publicación ni mutación de originales. La consulta externa realizada fue la página primaria de calendario NYSE para horarios/medio días.

## Estado de aplicación y verificación

Cambios están en staged_data/manifest.json con hashes de destino antes de cada aplicación y del contenido propuesto. El entorno no permite escribir varios fuentes directamente (EPERM; apply_patch acusa reparse point); raíz aplica copias acotadas con revisión de permiso. No se cambiaron ACLs. Algunas primeras versiones ya están aplicadas. Versión final aplicada por raíz y suite final PASADA:121tests recolectados más5subtests de fallos inyectados, exit_code0,44casos nuevos en test_data_measurements_v40. Resultados y hashes de fuentes guardados en data_test_results.json.

40 casos nuevos parametrizados de la primera versión aplicada PASARON mediante safe_test_runner.py (red/procesos externos bloqueados). La regresión anterior de cinco archivos mostró sólo fallos esperables de fixtures: cotización sin timestamps bloqueada por contrato40 y comparación integral contra auxiliares retirados. Se conserva el objetivo de comparación de primitivas/geometría, se actualiza la fixture con fechas válidas y se prueba la retirada por separado. La versión final añade negativos de preservación last_good IBKR y de captura/continuidad diaria.

## Correcciones y contrato nuevo

- H01: ib_insync instalado devuelve None en reqHistoricalNewsAsync al timeout (ib.py2142–2161), y su wrapper.historicalNewsEnd ignora _hasMore (wrapper.py1043). decoder.py136 tipa el callback [int,bool]. El adaptador privado captura ese terminal real; RaiseRequestErrors=True vuelve los errores de solicitud explícitos; el finally restaura callback/configuración. None/error/terminal desconocido/hasMore=true fallan antes de persistir latest o completar analistas. Una lista vacía sólo se admite con terminal false. 300 resultados con false también son completos; 1 con true es parcial. No se infiere cobertura de la saturación y no se ejecuta paginación no verificada. Los payloads actuales incorporan coverage y provider_fetched_at. El límite posterior de agregación quedó revisado y resuelto por integrity: analyst_recent_actions.py conserva provider_fetched_at/coverage de last_update, incluidos valores explícitamente desconocidos; data_ready exige esos campos para40 y valida fecha del proveedor, sin rejuvenecer por as_of del wrapper. Los negativos correspondientes están en tests/test_publication_consumers.py. La compatibilidad de congelados mantiene su propio contrato.
- H02: volumen y RV usan barras completas NYSE; cero observado se conserva como cero. RV20/RV60 exige la muestra completa del nombre, en lugar de calcular con dos retornos. La barra abierta sólo queda informativa en current_session. Los mismos helpers completados alimentan reacciones/perfil.
- H07: unidad por campo, no por magnitud: expected_move_1w.percent legacy ya es porcentaje; expected_move.percent por vencimiento es fracción y se convierte siempre ×100. Cubre0.5/1/1.01/100. Ningún recibo congelado se recodifica.
- H08: identidad, OI, gamma y quotes tienen elegibilidad separada. La ausencia de gamma conserva OI/quotes para sus cálculos. OI ausente/negativo/no entero/no finito queda desconocido, no cero. Agregados OI desconocidos son null y los subtotales conocidos llevan nombre explícito; maxpain no finge resultado completo con OI desconocido o todo0. Gamma TOP sigue restringido a contratos elegibles; detalles declaran base gamma_eligible frente a all_observed en dirigidos39.
- H09: el helper legacy de tendencia sólo considera puts con distancia<=0 para la cercanía inferior. Fuente40 retira todo trend_1_2w de salida; la corrección del helper queda probada para reproducciones y evita conservar una implementación incorrecta.
- H10b: libro de acciones exige0<bid<=ask; un libro inválido puede usar last positivo y fechado. Cotización nueva incluye fuente, timestamp proveedor, fetched_at, edad y criterio temporal. Close/prevclose sin fecha no se publican como current. Rechaza falta/fecha anterior a la sesión exigible/futuro incompatible, antes de mirror. Criterio explícito: sesión abierta actual desde09:30ET, o última sesión cerrada fuera de ella; no es garantía de edad en segundos ni de ejecutabilidad.
- H10a: calendario puro market_sessions.py extraído sin cambiar los festivos originales de adaptive_policy, con cierre16ET/13ET y ZoneInfo America/New_York. Detecta última sesión completada en premarket, sesión regular, postcierre, UTC día siguiente, fines de semana, festivos y DST. price_history40 exige fin esperado, OHLCV válidos, unicidad y sesiones consecutivas; una historia corta consecutiva queda observada con cantidad real y window_complete=false, sin atribuir causa IPO. Historia stale falla antes de mirror. Congelados<=39 retienen su validación histórica y no reciben tag40.
- M01: data_contract_revision:40 distingue la semántica de fuente de la revisión del prompt. Se retiran prob_touch_1w_pct, strength_score, trend_1_2w/confidence, dealer_gamma_regime, ATM-IV aproximada y ratios mal llamados IV/RV del nuevo raw/slim. Se conserva straddle ATM a vencimiento real (no weeklyización de días calendario a sesiones), strike, primas, quotes, unidades y alcance; nunca se define sigma/probabilidad. Se conserva gamma call-minus-put como nocional hipotético de contratos largos, con signo dealer unknown, cuenta elegible/desconocida y multiplicadores asumidos. Si no hay gamma elegible no se publica0. Símbolo contractual/root, contract_size, greeks.updated_at, trade/bid/ask dates ya suministrados se conservan. Falta multiplier se rotula assumed_standard_100, no se presenta como verificado. El total no es posición dealer ni flujo hedge. Maxpain conserva mínimo objetivo con falta OI explícita; gap objetivo deja de llamarse confidence.
- M03 (hook): horizontal_path_evidence implementado por raíz se incorpora bajo historical_reaction.path_evidence y slim lo conserva. Son recorridos de coordenada horizontal desde cierre de contacto; no backdating de curva AVWAP, inventario opciones ni fills. No se cambian defense_count ni rúbrica. Las estadísticas de recorrido tienen su intervalo propio declarado.

## Replays conservados

1. data_volume_original_replay.py/json: lee exactamente46 input.json originales del batch16oct15-58-24 y usa las20barras completadas incluidas en cada recibo. Reejecuta los helpers actuales mediante AST (sin importar clientes/red).46/46 fechas de volumen previas no eran la fecha cerrada;42/46 cambian el antiguo D_volume_tape al recalcularlo. AMAT0.471/-5→1.811/+10; MU0.505/-5→1.435/+10; TSLA1.064/0→0.787/-5. No cambia nota financiera, decisión, informe ni rentabilidad observada.
2. data_m01_replay.py/json:46/46 tenían trend auxiliar; el cambio de representación retiraría292campos prob_touch y292strength_score contando supports y resistances, no111supports solamente. Reglas legacy:46PUTWALL_NEAR,36GAMMA_NEG,10GAMMA_POS,10CALLWALL_NEAR_POS_GAMMA,27IV_CHEAP,11EM2W_ATR_LT1,3EM2W_ATR_GT1_6.6reglasPUTWALL_NEAR(+5) falsas por put superior o inferior lejano: AUR/IONQ/LRCX/PLTR/QBTS/RKLB. Cada fila guarda hash/fecha del input. El nuevo auxiliar bias/confidence es ausente, no se inventa un score corregido ni una probabilidad mejor calibrada. No se etiqueta un original como fuente40.

## Fuentes y límites

- Calendario primario consultado: https://www.nyse.com/markets/hours-calendars y https://ir.theice.com/press/news-details/2025/NYSE-Group-Announces-2026-2027-and-2028-Holiday-and-Early-Closings-Calendar/ . Cierre13:00ET para acciones en fechas especificadas; no se extrapola el horario de ciertas opciones13:15 a acciones. Reglas regulares ya existentes preservadas. Cierres excepcionales permanecen configurables en market_session(extra); el productor usa calendario publicado estándar y no adivina excepciones futuras.
- OI/multiplier/Greeks/quotes pueden llevar distintas fechas; conservar timestamps no prueba simultaneidad. No se compra dato ni se prueba wire vivo nuevo.
- No existe garantía de split/deliverable equivalente ni volumen intradía real: profile sigue aproximado diario. ATM nearest sampled strike puede no ser delta-neutral. Straddle price es descriptor, no forecast calibrado.
- Los tests demuestran contrato/cálculo y preservación de negativos, no utilidad financiera ni rentabilidad. Las comparaciones de modelos, si raíz las ejecuta, son estudio local y no publicación o efecto causal de performance.

## Revisión adversarial independiente de publicación

Leídos publication_store.py/publication_contract.py/publication_bundle.py y adaptive_stage._publish_manifest; revisión adicional de authority/current/attempt para seguir las ramas. Dos límites concretos enviados a integrity y confirmados/corregidos por esa rama: (1) TOCTOU de staging entre verify_bundle y relecturas tras I/O remoto; podía construir json nuevo con current derivado del payload anterior. Se reemplaza por bytes verificados leídos una sola vez, contexto/policy/payload derivados de ellos y copia privada para legacy. (2) check de frescura antes de subir6objetos permitía cruzar el TTL antes delCAS; before_commit callback revalida justo antes del puntero. Retry de versión ya confirmada no exige rejuvenecer observación, sólo completa publicación idempotente. No hice mutaciones en esos archivos. Pruebas de ambas correcciones pertenecen a integrity.

Control positivo de concurrencia: commit compara generación observada y usa if_generation_match para puntero; errores de descarga/JSON/digest existentes son visibles y no se convierten en fallbacklegacy con puntero válido. Dos lecturas separadas current/anchor pueden cruzar un nuevo full, pero load_current_report verifica sol_anchor_sha256 y aborta antes del modelo; no se observó aceptación de par contradictorio. Bootstrap y escritores legacy requieren activación coordinada: protocolo sigue opt-in, no se ha desplegado.


## Cierre C01 y revisión M02–M08
Resultados y condiciones en methodology_execution_review.md; scripts/JSON C01 y presupuesto de contexto conservados. price_path.py y test_price_path_v40.py aplicados directamente: cierre de contacto dentro de OHLC y detalle3 con resúmenes completos. 55tests relevantes pasan con safe_test_runner. No alteración de rúbrica, originales ni publicación.


## Continuidad de calendario cerrada

price_path.py usa ahora market_session del calendario compartido y acepta extra_closures con fechas ISO explícitas. Cada ventana debe coincidir exactamente con las siguientes cinco sesiones esperadas; un hueco, incluso en ventana parcial, incrementa incomplete_data_count y excluye el evento. No convierte falta de datos en defensa fallida ni adivina suspensiones/IPO. Fines de semana, festivos y cierres excepcionales declarados no son huecos; las sesiones cortas cuentan como sesiones. Contactos en fecha no hábil y fechas inválidas tampoco se aceptan. El contrato corresponde al helper nuevo de fuente40; originales congelados intactos.

80 tests relevantes pasan:16 de recorrido,44 de datos y20 de capture routing. Incluyen hueco con cinco filas posteriores, hueco en ventana parcial, Thanksgiving/fin de semana, cierre excepcional explícito y fila no hábil. Repetido el replay local de presupuesto sobre176 coordenadas: resultados sin cambios. Resultado, comando y hashes en data_test_results.json (path_calendar_validation).


## Control local M02 completado

m02_distance_control.md y su script/design/results cierran el control pendiente por distancia.57 niveles idénticos por brazo;47 sustituidos por brazo. Con tolerancia predefinida1punto porcentual y mismo ticker/fecha sólo1par sustituido es comparable, ambos visitados;46sin pareja. La estratificación fija también deja poco solapamiento y distancias residuales: no valida ranking ni explica causalmente toda la diferencia19/45. No hubo red, modelos ni nuevos precios.


## Guarda adicional H08/H10: identidad explícita de opciones (18 octubre)

Este hallazgo adicional se demostró con transporte simulado, no en un incidente histórico. Antes, una solicitud CAT/23-Oct admitía un contrato que declaraba OTHER/30-Oct y el observador dirigido lo rotulaba disponible bajo23-Oct con OI100 y gamma1.0M. Un XML <garbage/> se interpretaba como cadena vacía. Se conserva la copia exacta previa en option_identity_before_main.py; option_identity_before_after.py/json conserva el control antes/después y hashes.

| Referencia | Guarda adicional | Evidencia y alcance |
|---|---|---|
| H08 | Identidad de adquisición separada de elegibilidad OI/gamma: underlying explícito distinto, vencimiento explícito distinto, OCC inequívoco contrario a fecha solicitada/campos presentes y raíz XML de cadena desconocida se rechazan antes del cache | Control sintético original pasa antes y falla después; no se demuestra ningún informe histórico contaminado |
| H10 / procedencia | Cuerpo de proveedor contradictorio no se convierte en observación completa; esta verificación actúa con archivo opcional apagado o encendido | No mide frescura adicional, no cambia H10a/b anteriores ni depende del éxito del archivo de investigación |

La raíz OCC no se compara automáticamente con el ticker: raíces ajustadas coherentes se admiten. Campos ausentes, símbolos no decodificables con seguridad y vacíos legítimos <options/> / <options>null</options> mantienen su semántica. Una fecha OCC inequívoca distinta de la solicitada se rechaza incluso sin expiration_date. El archivo opcional sigue siendo no bloqueante; ningún fallo de disco/formato de archivo se ha convertido en guarda financiera.

43 pruebas específicas offline PASAN sobre staging: contradicciones independientes, caso original, fecha OCC sin campo de vencimiento, identidad ajustada, ausencia legacy, cache y capturas on/off. El replay antes/después conserva iguales los controles de raíz ajustada (multiplier150), campos ausentes y cadena vacía legítima. Manifest de2archivos: option_identity_manifest.json; resultados: option_identity_test_results.json. Pendiente solo aplicación por raíz y regresión combinada sobre archivos aplicados. No fuentes externas, modelos ni publicación.


### Verificación final aplicada

Raíz aplicó option_identity_manifest.json y los dos hashes destino coinciden exactamente con el manifiesto (raw fc24e74b6656255cd3f027ba04ec50279437dc345a7750dd76b4d2c4944b2d0b). La regresión combinada sobre fuentes aplicadas PASA:197 tests +5 subtests, exit_code0,12.78s. Desglose44 datos,29 orígenes39,20 captura,22 slim,39 archivo y43 identidad. Los129 avisos son deprecaciones datetime.utcnow ya existentes, incluidos replays legacy; no fallos.

Comando exacto desde E:/stock-analysis-local:

```text
E:\stock-analysis-local\.venv\Scripts\python.exe -B .tmp\audit_execution_20261017\safe_test_runner.py -- test_data_measurements_v40.py test_option_origins_v39.py test_capture_routing_v23.py tests\test_support_resistances_slim_evidence.py tests\test_technical_archive_v40.py tests\test_option_response_identity_v40.py
```

Resultado y hashes de17 archivos en option_identity_combined_results.json. Controles finales: contradicciones no entran en cache ni se convierten en origen disponible; con archivo apagado/encendido el rechazo es el mismo. Raíces ajustadas coherentes, campos ausentes, símbolos no decodificables y vacíos legítimos conservan valores/cache. Sidecar y errores de archivo permanecen fuera de modelo/espejo; fallo opcional no bloquea finanzas. No apareció un defecto que requiriera otra edición. Los43 casos de identidad y39 de archivo están incluidos en197, no se suman de nuevo. No hubo red, modelos, publicación ni edición de originales.
