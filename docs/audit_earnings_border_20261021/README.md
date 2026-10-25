# Grosor del borde naranja — 21-10-2026

Activo100%: `stock-controller-earnings-border-20261021`, health200 y runtime
exacto. Imagen `sha256:ff91cae07d188479532bab9e33232340a1efd526f9764673c12d0c031311b478`.
Ready tardó4m15s, más que el límite180s del CLI; se reconcilió la revisión
existente y se verificó antes de activarla, sin repetir el despliegue.
Diez avisos de Sheet comprobados: seis naranjas y cuatro rojos, todos gruesos.

Solicitud: igualar el grosor naranja al rojo para mejorar su visibilidad.
Único cambio funcional: naranja `SOLID`→`SOLID_THICK` (3px), conservando
`#F29900`, ventanas2–7días y prioridad del rojo en aristas compartidas.

El parche del controlador reemplaza una expresión exacta en el módulo importado
de earnings sobre la imagen inmutable activa. Runtime, tags anteriores y demás
fuentes conservados.11pruebas locales del calendario/renderer aprobadas; la
construcción ejecuta también las regresiones de ordenación y métricas.

La aplicación inmediata usa sólo `updateBorders` sobre las celdas de ticker con
aviso. La lectura de Sheets confirma ancho3 y `SOLID_THICK`; los bordes
compartidos se leen también desde la celda vecina por su normalización nativa.
Inventario, build, staging/activación y comparación de Sheet se guardan aquí.
