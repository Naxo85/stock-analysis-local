# Trabajo pendiente

## Prioridad 1: lanzamiento sin comandos

Construir el sistema completo para iniciar análisis sin escribir comandos manualmente.

- [x] Crear los lanzadores para analizar trading, core y un ticker solicitado por ventana.
- [x] Crear instaladores PowerShell/VBS para generar los accesos directos en el escritorio.
- [x] Ejecutar el instalador desde la sesión normal de Windows y confirmar los accesos.
- [x] Probar el acceso de ticker con una ejecución real correcta.
- [ ] Probar las órdenes automáticas de trading/core; ejecutan y suben batches reales.
- [x] Diseñar una cola de órdenes en GCS con estados `pending`, `running`, `completed` y `failed`.
- [x] Implementar `src/local_runner/command_worker.py` con modo `--once`.
- [x] Evitar ejecuciones duplicadas mediante identificadores, lock local y reclamación de órdenes en `running`.
- [x] Crear `scripts/install_command_worker_task.ps1` para instalar una tarea programada de Windows.
- [x] Crear scripts para ejecutar manualmente y eliminar la tarea.
- [x] Configurar la tarea para comprobar GCS cada minuto y no lanzar otra instancia si una sigue activa.
- [x] Instalar la tarea en Windows y comprobar que recoge una orden sin pulsar el acceso manual (`INOD`).
- [x] Añadir al código del menú de Google Sheets: `Analizar trading`, `Analizar core` y `Analizar ticker...`.
- [x] Hacer que Apps Script escriba las órdenes en GCS sin acceder directamente al ordenador local.
- [x] Exportar automáticamente la lista actual de trading/core antes de encolar su batch.
- [x] Copiar el Apps Script actualizado al proyecto real y probar órdenes con `MU` e `INOD`.
- [x] Implementar publicación del último resultado y consulta desde Google Sheets.
- [x] Implementar actualización automática de notas/targets tras un resultado `ok`.
- [ ] Copiar `analysis_completion_sync.gs` al proyecto real; el trigger se crea temporalmente al encolar.
- [ ] Probar que un ticker completado actualiza su fila sin usar el menú manual.
- [ ] Documentar instalación, seguridad, logs, recuperación de errores y operación diaria.
- [x] Probar el flujo automático con un ticker.
- [ ] Probar core/trading con alcance controlado y finalmente batches completos.

## Apps Scripts

- [ ] Guardar en el repo la versión final de `recalcYPRICE2()` para trading.
- [ ] Guardar en el repo la versión final de `recalcYPRICE2_CORE()` para core.
- [ ] Sincronizar `apps_script/update_targets_and_notes.gs` con la versión final que funciona en Google Apps Script.
- [ ] Confirmar que las versiones guardadas en el repo coinciden con las que están activas en Google Sheets.

## Core

- [ ] Confirmar que Momentum se escribe en `BE`.
- [ ] Configurar `momentumColumn: 57` para el perfil core.
- [ ] Confirmar que existe y funciona `updateCoreTargetAndNoteForRow(row)`.
- [ ] Confirmar que `recalcYPRICE2_CORE()` actualiza solo la fila afectada cuando Momentum cruza un umbral operativo.
- [ ] Verificar que los logs muestran `momentum=<numero>` en vez de `momentum=null`.

## Cache de precios

- [ ] Confirmar que trading ya no guarda `LP_DICT_V1` en `ScriptProperties`.
- [ ] Sustituir `LP_DICT_CORE_V1` por `CacheService` en core.
- [ ] Ejecutar una vez la limpieza de `LP_DICT_V1` y `LP_DICT_CORE_V1`.
- [ ] Mantener `ScriptProperties` solo para configuración y estados pequeños.

## Prompt y análisis

- [x] Pedir rangos de Entrada y Entrada ambiciosa operativos y accionables.
- [x] Pedir el subrango con mayor confluencia cuando la zona técnica sea amplia.
- [x] Cargar el último informe válido como contexto del siguiente análisis.
- [x] Incluir fecha, nota, narrativa, catalizadores, próximo evento y rangos anteriores en un bloque compacto.
- [x] Buscar novedades con un solape de 5-7 días para no perder catalizadores alrededor de la fecha de corte.
- [x] Pedir estabilidad de nota y narrativa cuando no exista un motivo material para cambiarlas.
- [x] Analizar desde cero cuando no exista informe anterior, sin inventar continuidad.
- [ ] Probar el contexto anterior en un nuevo `--run-full` y revisar el `codex_input.md` generado.
- [ ] Medir si el contexto mejora consistencia y si cambia el consumo de tokens; no se presupone ahorro porque el bloque anterior también consume entrada.
- [ ] Ejecutar un análisis nuevo para comprobar que desaparecen rangos excesivamente amplios como `900-950`.
- [ ] Revisar si los límites orientativos de anchura necesitan ajustes después de varios análisis reales.
- [ ] Regenerar informes antiguos solo si interesa actualizar sus rangos; no cambian automáticamente.

## Versionado

- [ ] Revisar todos los cambios locales pendientes.
- [ ] Auditar que no haya secretos ni credenciales.
- [ ] Separar los cambios en commits lógicos.
- [ ] Hacer commit y push cuando trading, core y cache estén confirmados.

## Orden recomendado

1. Recoger las versiones finales activas de los Apps Scripts.
2. Guardarlas completas en el repo.
3. Verificar simetría entre trading y core.
4. Probar Momentum y actualización individual en core.
5. Confirmar la migración de caches.
6. Probar el nuevo prompt con uno o dos tickers.
7. Revisar, commitear y hacer push.
