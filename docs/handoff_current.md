# Relevo operativo actual

Actualizado el **17-10-2026** tras una auditoría independiente de solo lectura operativa. Esta intervención cambió documentación y conservó reproducciones aisladas: **sin modelos, lotes, recuperación, publicación ni despliegue**. Punto de entrada: [arquitectura](architecture.md). Hallazgos: [auditoría](audit_analysis_system_20261017.md). Trabajo abierto: [backlog](pending_work_current.md).

## Estado local y última evidencia guardada

- Nuevas preparaciones: revisión 39, Sol 6.1 medium para mantenimiento y high para full, ITV5, techo 6 modelos. Configuración local leída 17-10; no se sustituyó modelo.
- Último lote natural seleccionado: `logs/batch/2026-10-16/15-58-24`, orden `20261016-155445-849-market-cfa04d68`, congelado 38. Terminó 45/46:18 retain,26 update,1 full IBKR; APP fallido. 55 llamadas registradas (46 triage,8 repair,1 report), un reintento de lote. Sin fallback.
- Full 36 solicitado por el usuario: `2026-10-14/16-07-07`,46/46,0 reintentos,46 full solicitados; no fueron 46 escaladas. 66 zonas,19 extensiones conocidas y 47 null en ese momento.
- Full 35 `2026-10-13/19-30-44` también terminó 46/46; la antigua entrada «EN CURSO» queda en el archivo como historia, no como estado actual.
- Full 31 `2026-10-13/12-41-28` conserva 44/46 históricos, CRWV/MU fallidos; publicaciones posteriores de esos tickers no cambian aquel resultado.
- No se encontró ejecución financiera 39 en la muestra revisada. Verificación 39 disponible: captura técnica real APP y tests offline; el siguiente natural 39 sigue pendiente de observar.

## Despliegues: comprobados en sus registros, no consultados de nuevo

Raw `support-resistances-raw-origins39-20261016` y slim `support-resistances-slim-origins39-20261016` tienen evidencia de build, revisión/probes a 0%, activación 100% y runtime preservado en `logs/deploy_origins39/`. La captura APP 16-10 21:07:48 UTC observa puts 250/255 en 16/23/30 oct; 255 fuera del TOP llega completo. Esto no valida vigencia compradora ni corrige APP.

Controller `stock-controller-solid65-20261015`: visibilidad Entry/Washout desde 65, sólido desde 70, extensión 36 y colores preservados; evidencia en `.tmp/solid65-deploy-20261015/evidence/`. El build se basó en la imagen activa 36, no en el intento 14-10 basado en 35. No usar el Dockerfile antiguo ni desplegar todo el árbol acumulado.

Los servicios pueden haber cambiado después de esos registros; la auditoría no consultó su estado remoto. El árbol tiene muchos cambios previos sin commit y HEAD 06-09; no atribuir todo el estado actual al último commit.

## Incidentes y límites que siguen abiertos

| Asunto | Estado al cierre documental |
|---|---|
| APP 16-10 | Bloqueado por ausencia de observación de puts 250 en input 38. No recuperado/republicado. 39 mejora adquisición futura, no ese recibo |
| Timeout IBKR convertido en feed vacío reciente | Defecto demostrado; originales MU/CRWV/IBKR 15-10 llegaron a modelo/publicación con ese estado. No se sabe qué noticia, si alguna, faltó |
| Volumen de sesión abierta rotulado completo |46/46 inputs 16-10; altera indicador auxiliar de volumen en 42. No atribuirle automáticamente notas financieras |
| Integridad durable de respuesta/bundle | Reproducciones aceptan cambios en copias; 101 recibos/91 publicaciones originales examinados sin discrepancias |
| Frescura tras validación | Revisión pendiente puede eludir chequeo 24 h al reanudar; no caso real tardío identificado |
| Geometría/herencia/contrato | Zonas idénticas aceptadas sintéticamente; TLN reparación por cita redundante observada; texto contradictorio de Volumen en prompts |
| Publicación y consumidores | Secuencia multiformato no atómica; último intento fallido no está separado del último informe válido para todos los lectores |
| Calidad financiera | Sin validación predictiva/empírica de la rúbrica o de ITV5. Tests y publicaciones no la sustituyen |

Detalles, prioridad y aceptación en [informe](audit_analysis_system_20261017.md). No interpretar la actualización de esta tabla como corrección implementada.


## Ampliación metodológica de la auditoría

Se añadieron fuentes primarias públicas, reconstrucción crítica del método y casos ex ante en las [secciones14–20 del informe](audit_analysis_system_20261017.md#14-ampliación-qué-conservaríamos-y-qué-rediseñaríamos). Solo se actualizó documentación y se conservaron comprobaciones locales aisladas. No hubo nueva ejecución financiera, consultas operativas externas, recuperación o despliegue; el estado de lotes e incidentes anterior permanece igual.

Hallazgos metodológicos: selección upstream restringe parte del descubrimiento a distancia mínima por defecto5%; la reacción high5d no describe toda la trayectoria adversa; gamma/OI no observa signo dealer; prob_touch calcula una cola terminal y EM/RV no identifica directamente IV barata/cara. Los pesos y notas auxiliares no tienen calibración predictiva demostrada. Hay contexto/empresa ya interpretados, pero faltan paquetes temporales uniformes de mercado/sector y premisas/expectativas de eventos.

Contraevidencia importante: ya se seleccionan compras sin opciones, se usan gaps/AVWAP y se permiten ausencias y retiradas con tesis conservada. No añadir esas capacidades como si faltaran ni imponer mínimos o más zonas. El conteo nuevo46 inputs/45 publicaciones/71 zonas es descriptivo del natural38, sin precios futuros ni prueba de rentabilidad. La captura39 posterior de APP no se usa para corregir retrospectivamente el intento38.

M01–M08 y los ensayos E1–E7 son propuestas pendientes en el [backlog](pending_work_current.md#investigación-metodológica-pendiente-sin-implementación). Incluyen retirar/simplificar antes de añadir señales. No modifican prompts, rúbrica, ITV, modelos o consumidores. No usar este relevo como autorización para ejecutarlos.

## Procedimiento de diagnóstico vigente

1. Identificar orden, batch, ticker, intento y estrategia. Leer resultado de orden, checkpoint y progreso local/remoto cuando la consulta externa esté dentro del alcance.
2. Comprobar heartbeat, fase y actividad/lock antes de considerar una ejecución detenida. C4/A9 son espejos, no autoridad suficiente.
3. Abrir el contrato congelado y recibos/eventos del intento exacto. Separar adquisición, admisión, modelo, reparación, validación y publicación.
4. Comparar bases CURRENT/ancla, propiedad y fechas sin editarlas. No reutilizar un contrato 38 como 39 ni refrescar un input ya admitido al modelo.
5. Distinguir reintento de datos, reintento de lote, reparación y reutilización de recibo. Un fallo ambiguo no autoriza otra llamada.
6. Antes de recuperar, comprobar las limitaciones abiertas de integridad/frescura. Recuperación receipt-only usa `recover_adaptive_receipt`, no lote duplicado. Publicación requiere su alcance autorizado.
7. Antes de declarar éxito, contrastar informe, estado y consumidores. Mantener visible el fallo histórico aunque un ticker publique después.
8. Si se investiga Web legacy, seguir su [guía específica](chatgpt_browser_provider.md), no mezclar sus métricas/controles con el motor adaptativo actual.

No se solicita una nueva prueba pagada para cerrar esta auditoría. Las mejoras financieras/editoriales se observan en ejecuciones naturales autorizadas; las comprobaciones externas pendientes se enumeran sin ejecutarlas.

## Evidencia de esta auditoría e historial

Se ejecutaron suites locales focalizadas y reproducciones con transportes simulados; el [informe](audit_analysis_system_20261017.md) registra cantidades, un test de versión obsoleto y límites. Las cifras de tests anteriores no se suman como nuevas verificaciones ni como resultados económicos.

El [relevo anterior completo](history/handoff_current_before_audit_20261017.md) conserva incidentes, comandos, imágenes y decisiones de septiembre/octubre. Sus «vigente», «en curso» y «siguiente lote» son temporales. Los pendientes antiguos no se cierran por archivarlos: están enlazados en el backlog vigente.
