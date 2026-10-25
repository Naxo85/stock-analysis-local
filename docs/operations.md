# Mapa de operaciones vigente

Actualizado 19-10-2026. Entradas: [arquitectura](architecture.md), [relevo](handoff_current.md), [backlog](pending_work_current.md). Los procedimientos y antecedentes anteriores se conservan en el [archivo histórico](history/operations_before_audit_20261017.md).

## Operaciones y efectos

| Necesidad | Entrada | Efectos |
|---|---|---|
| Analizar ticker solicitado | `run_one TICKER --run-full` | Fuentes, modelo high, validación y publicación real |
| Mantenimiento diario | `run_batch`, [comandos](batch_workflow.md) | Fuentes, modelos adaptativos y publicación |
| Renovar referencias | Batch con `--analysis-mode reference` | Full high por ticker; requiere renovación expresa |
| Ver rutas | `run_batch ... --routing-plan` | Sin Gateway/modelos/uploads; puede leer GCS |
| Pruebas locales | Suites focalizadas y fixtures aisladas | Revisar aislamiento antes: no todos los scripts verify son offline |
| Simular subida de artefactos existentes | `run_one TICKER --upload-real` sin `--execute-upload-real` | Plan de subida, no simulación financiera completa |
| Recuperar recibo | `recover_adaptive_receipt` | Copia/validación; `--execute` publica. Exige autoridad, frescura e integridad del contrato exacto; no convierte un original fallido en otro análisis |
| Reconciliar progreso | `progress_reconciliation` | `--execute` modifica indicador, no informe |
| Refrescar Mercado | Controller `/analysis/refresh` | Escribe proyección/Sheet, sin implicar nuevo informe |
| Captura técnica raw/slim | Endpoints/verificadores vivos | Puede refrescar mirror técnico; no es lectura sin efectos |
| Despliegue | Script específico, revisión/runtime/tráfico | Efecto externo; código local probado no demuestra despliegue |

## Uso normal

Leer antes [handoff_current.md](handoff_current.md). Para un ticker autorizado:

```powershell
& '.\.venv\Scripts\python.exe' -m src.local_runner.run_one RKLB --run-full
```

Listas y diferencias entre «todos», Mercado y Core: [batch_workflow.md](batch_workflow.md). La política local actual es 41, Sol 6.1 medium/high, ITV5 y techo 6. Web principal, fallback automático y calendario semanal de modelos son históricos.

Respuesta exitosa habitual: `OK RKLB: análisis generado y subido.`. Fallo: `FAILED RKLB: <error_type> - <error_message>`. Diagnósticos detallados cuando se solicitan.

## Diagnóstico

Capacidad raw desde19Oct: conservar máximo3 a nivel servicio Y revisión (`capacity41-20261019`), mínimo0 e imagen41. Un429 de Cloud Run puede aparecer como502 `raw_endpoint_http_error` en slim. El cliente de preparación usa `technical_http`: máximo3peticiones, presupuesto240s para nuevos intentos, backoff/Retry-After, parámetros completos exactos y fallo persistente visible. No autoriza reintentar modelos ni capturas congeladas. SDK485 no admite `--max` y puede producir409 al reescribir revisiones creadas por APIv2; el [script específico](../scripts/fix_raw_capacity_20261019.py) usa máscara/etag y tráfico por API con la identidad fijada existente. [Incidente y comprobación](audit_lrcx_capacity_20261019/README.md).

Enlaces Tesis: comprobar `hyperlink`, `userEnteredFormat.textFormat.link` y `textFormatRuns` mediante CellData. Sheets puede normalizar un enlace uniforme y omitir los fragmentos; una ordenación que enmascare `textFormatRuns` vacío puede borrar el enlace pese a copiar el formato. El serializador activo desde19Oct reconstruye el fragmento antes de escribir. No basta comprobar `_score_cell` o una copia en memoria. Controller `stock-controller-report-links-sort-20261019`, presentation15,46enlaces reparados desde versiones canónicas. [Reproducción real y pruebas](audit_thesis_links_20261019/README.md). Refrescar la proyección no requiere regenerar informes.

1. Identificar orden, ticker, lote y estrategia; comprobar heartbeat y actividad.
2. Revisar contrato congelado, recibos/eventos, review/failure y fase exacta.
3. Separar adquisición, contrato, juicio bloqueado, reparación, transporte y publicación. Reintento de lote no equivale a nueva llamada.
4. Contrastar CURRENT/ancla con originales; no editarlos ni renovar fechas por presentación.
5. Comprobar los consumidores afectados antes de declarar coherencia de publicación.
6. Recuperación, publicación y despliegue requieren su alcance autorizado; no se deducen del permiso de auditar.

La fase inicial de auditoría17-10 fue local. La puesta en servicio18-10 desplegó las correcciones adoptadas y verificó fuentes, consumidores y canarios aislados. Véanse [matriz](execution_audit_20261017.md) y [evidencia](audit_work_20261017/execution/activation/README.md). No se publicaron los informes de los canarios ni se recuperaron incidentes antiguos. Un lote natural pendiente no se sustituye por uno duplicado.

La [activación41 del19-10](audit_support_constraints_20261019/implementation/README.md) completó tres correcciones: actualización material de conocimiento del mismo soporte, fundamentos independientes de los componentes y observación dirigida de suelos/gaps CURRENT con identidad exacta. Opciones25, visibilidad65/solid70, selección y filtro global5% permanecen iguales. La disponibilidad de un origen no concede viabilidad ni retención, y el cambio de instrucciones no repuntúa informes por código. El juicio financiero41 se observará en el siguiente flujo natural, sin lote duplicado.

## Windows y entorno

Usar `.venv/Scripts/python.exe`; [instalación](new_computer_setup.md). Google Cloud SDK desde PowerShell:

```powershell
cmd /c gcloud.cmd ...
```

Evitar gcloud.ps1 bloqueado por la política local. Lanzadores auxiliares autorizados ocultos; no detener procesos ajenos por nombre global.

- [Gateway/IBC](ibkr_gateway_automation.md): preflight de conexión no garantiza cobertura completa de titulares; la adquisición ahora exige terminal real y cobertura verificada. Timeout/error/paginación incompleta conservan last_good y fallan visibles, sin redatar un vacío.
- [Cola](command_queue.md): acciones de análisis y cartera son distintas; no probar visualización comprando/vendiendo.
- [Android](android_app.md): APK firmado y probado contra el servicio en emulador; disponible en `releases/android/Growth-0.1.0.apk`. La instalación en teléfono físico no se verificó.
- Fuentes mantenidas: `gcp_functions/support_resistances_raw/` y `support_resistances_slim/`; `incoming_from_gcp/` es histórico.
- [Prompts efectivos](codex_adaptive_analysis.md): el archivo stock_analysis_system_prompt no describe por sí solo el motor adaptativo.

## Publicación vigente y fuentes41

Las fuentes activas al100% son `support-resistances-raw-origins41-20261019` y `support-resistances-slim-origins41-20261019`; reports/mobile/controller conservan publication40 al100%. La política41 se activó el19-10-2026 a las10:49:08UTC, cambiando únicamente routing_revision40→41: SHA25610745943fc7b3e7043071b01d283ac68661dbe6a1c7409c76466e4760d4718c4. Se conservaron runtime, variables y referencias de secretos de las fuentes.304pruebas+6subcasos y una captura técnica real CLS a10:46:30UTC verificaron la identidad del suelo290,88 y su admisión41. La activación no llamó modelos ni publicó informes financieros; la captura pudo refrescar el mirror técnico habitual. [Recibos y controles](audit_support_constraints_20261019/implementation/README.md).

Como antecedente, la puesta en servicio18-10 activó raw source40-audit, slim source40-active y reports/mobile/controller publication40. A1 preservó runtime salvo imagen; A2 añadió EVALUATION_ARCHIVE_ENABLED en raw y fijó RAW_BASE_URL canónico en slim, conservando el resto. Controller se construyó como parche sobre la imagen realmente activa y conserva solid65, extensión de compra y Res oculta. Las revisiones anteriores quedan disponibles para rollback compatible.

La política habilita `manifest-v1`, `latest_attempt_publication_enabled` y `technical_archive_enabled`. Seis objetos inmutables se escriben antes del CAS por ticker. Los consumidores compatibles leen esa versión; aliases y Sheet son proyecciones posteriores. La cuenta de servicio del controller dispone de lectura del bucket de informes. Se comprobó CAS, historia, fallo sin informe y coherencia de46 informes existentes en entorno real; el test de proyección del controller no escribió Sheet.

CAS y avisos de intento del runner usan el puente explícito `publication_auth.mode=gcloud-cli` con cuenta/proyecto fijados, porque no había ADC local disponible. Usa la autenticación GCloud ya existente, mantiene tokens solo en memoria y falla sin fallback silencioso. Las lecturas y aliases que usan el CLI conservan su identidad activa, que debe mantenerse concordante con la configuración autorizada. Los servicios conservan ADC y sus referencias de secretos. Esto no modifica el ejecutor Codex, su autenticación ChatGPT ni sus modelos.

Conexión10s, respuesta histórica30s, adquisición180s/16páginas; subprocess de noticias210s y backfill concreto600s con su reintento/Gateway existentes. El reloj de prepare900s y los del modelo no cambian. La semántica de fechas observada difiere del rango documentado: el adaptador recorre hacia atrás con cursor ISO y solapamiento de un segundo, comprueba orden/identidades/progreso y solo completa con `hasMore=False` real. Filtra la ventana exacta después y conserva las observaciones recibidas. La cobertura se refiere al caché disponible del proveedor, no a todas las noticias existentes en el mercado. Cruce de la fecha inicial, respuesta parcial o error no equivalen a fin. Los límites fallan explícitamente y mantienen last_good; no aumentar límites ni aceptar parcial para ocultar un fallo. Control fresco NVDA:14páginas,4.065 identidades únicas,19duplicados y95titulares en ventana; evento terminal recibido y hasMore=False,115,797s de adquisición/116,5s de proceso. Los fallos anteriores por8páginas y75s quedan preservados. Regresión aplicada de datos:88 pruebas+16 subcasos; conjunta UTF8/procedencia/plazos:18+16, con solapamiento

Individuales/manuales resuelven tenencia contra Mercado; los booleanos explícitos del universo de un lote conservan autoridad. Un dato ausente/no booleano se resuelve contra Mercado, sin cambiar la selección38/30/46 ni el orden. Input guarda selección y procedencia de tenencia por separado. Duplicados ambiguos o falta de autoridad fallan.

El worker inicia Python nuevo para cada orden nueva y carga la política vigente; no necesita reinicio por esta activación. Reanudar una orden/recibo congelado conserva su contrato anterior deliberadamente. No editarlo para forzar41: los congelados<=40 conservan sus instrucciones, esquemas y recibos exactos.

## Recuperación y rollback

No volver a lectores que ignoren un manifest existente. Apagar un switch no borra la autoridad ya comprometida ni permite mezclar versiones; conservar lectores compatibles, recibos y puntero, y resolver reintentos por su versión. Las imágenes anteriores se conservan para rollback revisado. El checkpoint8034b7a es previo a la implementación, no una orden para revertir servicios.

Los secretos se usan por referencia: no copiar valores ni exponerlos en diagnósticos. Los auxiliares sintéticos A1 (bucket/objetos/Job/revisiones de prueba) se retiraron. La limpieza A2 fue autorizada expresamente después del rechazo inicial y completada el18-10: eliminados los tres tags propios y únicamente la revisión slim de staging, con producción y rollback comprobados. [Evidencia](audit_work_20261017/execution/activation/cleanup_authorized/README.md). El borrado de objetos del bucket de prueba respeta su retención soft-delete. Los procedimientos legacy y detalles históricos siguen en el [archivo](history/operations_before_audit_20261017.md).

## Lock GCS y reutilización de PID — corrección18-10-2026

`analysis_state.py` guarda PID, inicio de instancia y token para las nuevas lecturas GCS. Un lock legacy `{pid}` solo se recupera como PID reutilizado si Windows demuestra que el proceso actual nació después de la escritura del archivo. Un dueño vivo o desconocido se conserva; errores de acceso no prueban abandono. No borrar por antigüedad ni matar un proceso porque coincida su número. Los plazos60s/2intentos/180s y la autoridad del manifest siguen iguales.

La liberación nueva verifica token e identidad observada; la comparación y el unlink no constituyen una operación atómica y mantienen esa limitación del mutex de archivos. Los callers legacy del pool conservan su API. El diagnóstico sin modelos puede usar `run_batch --config-gcs gs://stock-analysis-reports-naxo85/config/tickers_market.json --routing-plan --generation-provider codex`, con supervisión temporal; no añadir flags de publicación. Consulta GCS y cálculo local, pero no Gateway/fuentes/modelos/lote. [Incidente y pruebas](audit_work_20261017/execution/activation/gcs_lock_incident/README.md).
