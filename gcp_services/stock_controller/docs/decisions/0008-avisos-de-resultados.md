# 0008 — Avisos de resultados en el ticker

Decisión acordada y desplegada con autorización explícita del usuario el21-10-2026; LRCXrojo verificado en MercadoK8 y API.

- Entre2 y7 días naturales: borde naranja grueso `#F29900`, `SOLID_THICK`, igual que el rojo (ajuste solicitado21Oct).
- Hoy o mañana: borde rojo grueso `#D93025`, `SOLID_THICK`.
- Fecha pasada, desconocida, inválida o a más de7 días: sin aviso.
- Fecha del día en Europe/Madrid; ventana de días naturales.
- Nota con fecha exacta, horario cuando se suministra explícitamente, fuente y fecha del resumen publicado. Esta última no se presenta como hora de adquisición del calendario.
- Símbolo, enlace y fondo de cartera intactos; otras notas conservadas.

El calendario procede de `analyst_ratings_summary.next_earnings_date` en informes válidos, producido por la adquisición Finnhub existente. No se infiere de `next_event`, noticias o prosa. El sincronizador guarda una proyección fechada `earnings` en su estado; el refresco habitual reutiliza esa pequeña lectura y recalcula el aviso después de ordenar y reconstruir bordes. Cambiar de color o retirar la marca no requiere modelo ni informe nuevo.

La API móvil consume la misma proyección. Android muestra `E hoy`, `E mañana` o `E en N días`, incluyendo caducidad al abrir una copia sin conexión y colores legibles con tema oscuro.

No añade push, reglas de inversión ni cambios de cartera/modelos/informes. Activar requiere desplegar controlador/API, sincronizar la proyección existente y verificar estilos reales de Sheets. La APK nueva requiere instalación en el teléfono.
