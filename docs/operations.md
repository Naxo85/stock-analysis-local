# Mapa de operaciones vigente

Actualizado 17-10-2026. Entradas: [arquitectura](architecture.md), [relevo](handoff_current.md), [backlog](pending_work_current.md). Los procedimientos y antecedentes anteriores se conservan en el [archivo histórico](history/operations_before_audit_20261017.md).

## Operaciones y efectos

| Necesidad | Entrada | Efectos |
|---|---|---|
| Analizar ticker solicitado | `run_one TICKER --run-full` | Fuentes, modelo high, validación y publicación real |
| Mantenimiento diario | `run_batch`, [comandos](batch_workflow.md) | Fuentes, modelos adaptativos y publicación |
| Renovar referencias | Batch con `--analysis-mode reference` | Full high por ticker; requiere renovación expresa |
| Ver rutas | `run_batch ... --routing-plan` | Sin Gateway/modelos/uploads; puede leer GCS |
| Pruebas locales | Suites focalizadas y fixtures aisladas | Revisar aislamiento antes: no todos los scripts verify son offline |
| Simular subida de artefactos existentes | `run_one TICKER --upload-real` sin `--execute-upload-real` | Plan de subida, no simulación financiera completa |
| Recuperar recibo | `recover_adaptive_receipt` | Copia/validación; `--execute` publica; limitaciones abiertas |
| Reconciliar progreso | `progress_reconciliation` | `--execute` modifica indicador, no informe |
| Refrescar Mercado | Controller `/analysis/refresh` | Escribe proyección/Sheet, sin implicar nuevo informe |
| Captura técnica raw/slim | Endpoints/verificadores vivos | Puede refrescar mirror técnico; no es lectura sin efectos |
| Despliegue | Script específico, revisión/runtime/tráfico | Efecto externo; código local probado no demuestra despliegue |

## Uso normal

Leer antes [handoff_current.md](handoff_current.md). Para un ticker autorizado:

```powershell
& '.\.venv\Scripts\python.exe' -m src.local_runner.run_one RKLB --run-full
```

Listas y diferencias entre «todos», Mercado y Core: [batch_workflow.md](batch_workflow.md). La política local actual es 39, Sol 6.1 medium/high, ITV5 y techo 6. Web principal, fallback automático y calendario semanal de modelos son históricos.

Respuesta exitosa habitual: `OK RKLB: análisis generado y subido.`. Fallo: `FAILED RKLB: <error_type> - <error_message>`. Diagnósticos detallados cuando se solicitan.

## Diagnóstico

1. Identificar orden, ticker, lote y estrategia; comprobar heartbeat y actividad.
2. Revisar contrato congelado, recibos/eventos, review/failure y fase exacta.
3. Separar adquisición, contrato, juicio bloqueado, reparación, transporte y publicación. Reintento de lote no equivale a nueva llamada.
4. Contrastar CURRENT/ancla con originales; no editarlos ni renovar fechas por presentación.
5. Comprobar los consumidores afectados antes de declarar coherencia de publicación.
6. Recuperación, publicación y despliegue requieren su alcance autorizado; no se deducen del permiso de auditar.

La auditoría 17-10 no ejecutó ninguna operación externa. Hay defectos reproducidos de frescura tras interrupción, integridad duradera y estado de fallo; las guardas actuales no garantizan una recuperación correcta en todos los casos. Véanse [informe](audit_analysis_system_20261017.md) y backlog.

## Windows y entorno

Usar `.venv/Scripts/python.exe`; [instalación](new_computer_setup.md). Google Cloud SDK desde PowerShell:

```powershell
cmd /c gcloud.cmd ...
```

Evitar gcloud.ps 1 bloqueado por la política local. Lanzadores auxiliares autorizados ocultos; no detener procesos ajenos por nombre global.

- [Gateway/IBC](ibkr_gateway_automation.md): preflight de conexión no garantiza cobertura completa de titulares; timeout convertido en vacío válido es un defecto abierto.
- [Cola](command_queue.md): acciones de análisis y cartera son distintas; no probar visualización comprando/vendiendo.
- [Android](android_app.md): código/proyección local no certifica servicio o APK actualmente instalados.
- Fuentes mantenidas: `gcp_functions/support_resistances_raw/` y `support_resistances_slim/`; `incoming_from_gcp/` es histórico.
- [Prompts efectivos](codex_adaptive_analysis.md): el archivo stock_analysis_system_prompt no describe por sí solo el motor adaptativo.

## Despliegues documentados

Raw/slim origins 39 del 16-10 y controller solid 65 del 15-10 tienen registros guardados de build, revisión, health/tráfico y runtime. No se consultó su estado remoto 17-10. Solid 65 partió de support-validity 36; el intento anterior basado en 35 no es el artefacto activo documentado. No desplegar el árbol acumulado como si fuera el parche mínimo probado.

Los secretos se usan por referencia: no copiar valores de archivos históricos ni exponerlos en diagnósticos. Un test dentro de una imagen solo acredita ese artefacto. Los procedimientos legacy y detalles históricos siguen en el [archivo](history/operations_before_audit_20261017.md).
