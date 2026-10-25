# Reintentos del lote natural23Oct

**Cambio de reintentos revertido23Oct:** el usuario no había pedido suprimir
reintentos. Se restauró la selección anterior de todos los tickers fallidos y
se retiraron el filtro y su test específico. Las secciones de corrección y sus
pruebas inferiores documentan la intervención revertida, no el estado vigente.
El diagnóstico del lote se conserva. «Rechazo definitivo» fue una etiqueta
inadecuada: describe el rechazo repetido de la misma respuesta, no imposibilidad
de recuperar el análisis. No se ejecutó otro lote durante la reversión.

Orden `20261023-141107-770-market-fed7b9fd`, lote
`logs/batch/2026-10-23/14-18-22`, estrategia adaptive-codex-v1, revisión41.
Resultado final:34/46 publicados y12fallidos,46minutos aproximadamente.
Fin15:04:12UTC (17:04:12Madrid). No se lanzó otro lote para esta auditoría.

## Fallos y contadores

- Volumen9: CLS (10 esperado/8 declarado), COIN (14/12), MU (16/13);
  GEV, ASML, GOOG, CAT, NBIS (perfil general como fuente de nivel);
  ASTS (cálculo declarado sin evidencia completa en el full posterior).
- Contrato de justificación2: INTC (`review_without_edit`) y TLN
  (`wrong_scope_current_evidence`). Ambos empezaron reparando Volumen;
  no atribuir todo el fallo final exclusivamente a la suma.
- ORCL1: timeout en la reparación; la segunda pasada encuentra la reserva
  y rechaza duplicarla.

La app muestra12reintentos de *pipeline*, no12reparaciones de modelo. Empiezan
14:59:20.726354UTC. El ledger conserva74llamadas:46triage completadas,
18reparaciones completadas,1reparación fallida y9full completadas. Ocho full
publicados; completar la llamada no implica superar la validación financiera.
Ninguna reserva/call comienza después del inicio de la pasada de reintentos.
Los12reintentos no llamaron otra vez al modelo; releen y rechazan las respuestas
existentes. No ahorraron otro coste de modelo ni recuperaron ningún fallo.

## Corrección

El bucle exterior de `run_batch` excluye los rechazos contractuales definitivos
del motor adaptativo, timeouts sin autorización de repetición, reservas ambiguas
y errores conocidos de autenticación. Conserva los fallos originales y el contador
auténtico de intentos; no borra avisos ni cambia la app para ocultarlos.

La adquisición/publicación con fallo transitorio conserva su elegibilidad y el
ejecutor de modelo mantiene la comprobación independiente de transitoriedad y
contrato exacto. No se cambia modelo, rúbrica, fuentes congeladas, informe ni
autoridad. Las ejecuciones legacy conservan su comportamiento.

11tests y10subcasos aprobados: replay de los12errores originales, negativos de
integridad/ambigüedad, transitorios de adquisición/publicación y suites existentes
de resumen/revisión. Diff-check aprobado. Sólo corrige próximas ejecuciones;
no se interrumpe, reanuda ni recupera el lote terminado.

## Pendiente

La mejora de Volumen previa (`audit_volume_feedback_20261023/README.md`) sólo
entra en nuevas políticas. La tasa12/46 y19reparaciones es un problema operativo
real, no prueba de que se haya resuelto la calidad financiera con tests offline.
Observar las mejoras en uso natural; no cambiar modelos silenciosamente ni
relajar validación o subir notas para convertir fallos en éxitos.
