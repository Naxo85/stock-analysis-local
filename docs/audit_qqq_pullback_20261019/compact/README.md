# Vista compacta — 19-10-2026

Petición del usuario: retirar toda la información visible alrededor del porcentaje.
Solo queda una línea «Caída QQQ: −6,56%», con tipografía10 y tintado discreto.
La fecha del cierre, fuente y método permanecen en la nota de la celda.

- Se retira la tarjeta previa dentro de C2:H7 y se combina únicamente C2:E2.
  No se insertan filas/columnas, no se cambian dimensiones ni se toca la tabla
  inferior o los indicadores originales A2:A8/controles A9 y C9:C10.
- El valor sigue siendo numérico; el rótulo procede del formato de número, con
  secciones explícitas positiva/negativa/cero/texto. Falta de datos no es cero.
- La API admite ambos formatos durante la transición. Lee la celda C2 en la
  vista compacta; conserva compatibilidad con C3 en la tarjeta anterior.
- La APK solo muestra «Caída QQQ» y el porcentaje. No muestra estado, umbral,
  precios, fechas ni explicación. La identidad y firma existentes se conservan.
- Misma adquisición y cálculo: no se modifica el indicador, cadencia, informes,
  modelos, universo ni cartera. No hay otro lote de análisis.
- Verificación local:9 pruebas del cálculo/escritura y19 de API, más compilación
  release Android, pruebas unitarias y lint correctos. Sin teléfono físico.

Los overlays parten de las imágenes inmutables activas. La API se cambia mediante
el bloque exacto preexistente, preservando código ajeno; el módulo de presentación
del controlador se compara por AST antes de sustituirlo. Ambos conservan runtime.
La primera compilación móvil rechazó una diferencia fuera del bloque y no se
activó. La compilación inicial del controlador se sustituyó antes de staging para
explicitar el formato de números negativos. Los intentos quedan conservados.


Activación verificada: stock-controller-qqq-compact-20261019 y stock-mobile-api-qqq-compact-20261019 al100%, salud200 y runtime conservado. El refresco natural mostró únicamente «Caída QQQ: -6,56%» en C2; el resto de C2:H7 queda vacío. Cuadrícula27×38 y resumen en fila12, comprobados en la vista nativa (sheet-current.png). Paridad exacta con la API autenticada17:33:58UTC. APK firmado recompilado; teléfono físico no verificado.
