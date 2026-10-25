# Visibilidad de soportes desde50 — 22Oct2026

El usuario pidió «que se muestren desde50». Entrada/Washout de Mercado
usan umbral50 inclusivo;49 queda oculto y50 conserva categoría moderado.
Sólido70, fuerte85 y excepcional95, pesos y selección siguen iguales.

Código local: `analysis_sheet.SUPPORT_STRENGTH_VISIBLE_THRESHOLD=50` y
`run_sync.presentation_version=17` para renovar proyecciones existentes.
Los16tests de analysis_sheet pasan, incluida frontera49/50 y bordes85/95.

Despliegue mínimo sobre imagen inmutable activa, conservando runtime/tags y
comportamiento anterior. La primera compilación falló sin despliegue al detectar
una copia secundaria distinta en `/app/src`; se capturó la fuente importada
activa (umbral65, versión16) antes de ajustar el parche para ambas copias.
Los archivos JSON de este directorio registran compilación, staging, health,
activación y refresco cuando se completan. No modelos, lote, nuevos informes
financieros ni operaciones de cartera.

Completado: controller `stock-controller-visibility50-20261022` activo100%,
runtime y tags previos conservados, health200.45tests dentro de la imagen pasan
(`build_success.log`). Refresh46/46, sin faltantes ni reordenación.
Lectura independiente por Google Drive/Sheets:46identidades conservadas;
42zonas antes ocultas ahora visibles con fortaleza50–64, incluida CAT50.
Los valores/notas financieros ya visibles permanecen exactos. Mercado y
seguimiento continuaron cambiando por sus escritores normales; no son una
baseline inmutable de cotizaciones o cartera. `sheet_verification.json`
registra las celdas comprobadas (coordenadas cero-based). Formatos/notas leídos
por API; sin comprobación visual del navegador en esta tarea.

Compilaciones fallidas previas sin despliegue:
`4571b153-0cbf-49b6-9884-762bdfe7c326` y
`2d893ce6-f51a-4ab8-bba1-12270c102dc6`.
La copia histórica secundaria de run_sync se conserva; el módulo importado
efectivo actualiza presentation16→17. Ambas copias de analysis_sheet reciben50.
