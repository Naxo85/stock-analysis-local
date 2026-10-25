# Retroceso relativo actual de QQQ — 19-10-2026

El usuario pidió únicamente el episodio actual en Excel/Sheets y en la app, y
señaló expresamente el espacio superior libre de Mercado. La tabla inferior no
debe desplazarse ni cambiar de tamaño. No pidió un historial visible.

## Cálculo y datos

- Se reutilizan las barras diarias de QQQ ya adquiridas por el controlador.
  No hay otra descarga, modelo, análisis financiero o modificación de cartera.
- La referencia es el máximo de cierre del tramo seguido. Una caída del 5%
  abre un episodio; solo un rebote del 5% desde su mínimo de cierre lo termina
  y permite seguir el máximo del tramo siguiente. No es el máximo histórico
  ni el máximo intradía móvil de seis meses.
- Se excluye la vela del día antes de las 16:00 ET. Se exige el cierre esperado
  y se muestra su fecha propia. Si el proveedor todavía no lo entrega, se
  indica que falta el cierre; una ausencia nunca se transforma en cero.
- Un hueco en la serie reinicia la sincronización. Se exige un ciclo posterior
  observado de caída/rebote antes de dar por conocido el tramo. Duplicados,
  valores inválidos o tramo inicial ambiguo producen N/D.
- El calendario ordinario es el ya utilizado por el sistema. Un cierre
  extraordinario no modelado se trata conservadoramente como hueco. Las medias
  sesiones no se admiten anticipadamente: el corte de esta vista es 16:00 ET.
- El aviso es descriptivo. No modifica zonas, fuerza, puntuaciones, riesgo,
  modelos, ITV, universos ni autoridad de publicación.

## Presentación y límites

- Únicamente C2:H7: título, porcentaje numérico grande, estado, umbral del 5%,
  máximo y fecha, cierre y fecha y base de cálculo. Ámbar para episodio abierto.
- El escritor solo emite mergeCells/repeatCell/updateCells dentro de ese bloque;
  no inserta filas o columnas ni modifica dimensiones. A9/C9/C10 y A12:H27
  quedan fuera. El panel existente A2:A8 y el DD6M conservan sus significados.
- La API móvil lee las mismas celdas tipadas y sus etiquetas. No recalcula la
  señal ni interpreta DD6M como retroceso relativo. La app muestra una tarjeta
  con el cierre fechado y sin listado de episodios.

## Verificación local

- 40 pruebas del controlador: nueve nuevas de episodios, exclusión intradía,
  desconocidos, huecos y límites geométricos, más general_market, market_sheet
  y market_metrics.
- 18 pruebas de la API: tres nuevas de igualdad con las celdas de Sheets,
  desconocido distinto de cero y compatibilidad con una hoja antigua.
- Compilación/firma Android y puesta en servicio: evidencia en los subdirectorios
  controller/mobile y en los logs de `.tmp/qqq_pullback_20261019/`.

## Despliegue

Los overlays se construyen sobre la imagen inmutable activa de cada servicio.
El primer empaquetado rechazó una diferencia entre los módulos fuente e instalado
del controlador; la primera compilación móvil detectó una colisión de importación
en el directorio temporal. No se activó ninguna de esas imágenes. El overlay
corregido inserta únicamente los fragmentos autorizados en anclas exactas y únicas,
preserva el resto del código de cada copia y comprueba por AST la sintaxis. Los
módulos nuevos no pueden existir previamente. Se conservan configuración,
secretos, permisos, capacidad, tags previos y tráfico hasta verificar staging.
Los JSON controller/mobile registran hashes, resultados y activación efectivos.
La APK conserva la firma existente. Una compilación o prueba en emulador no
demuestra que el teléfono físico haya recibido la actualización.

## Resultado comprobado

Corrección visual posterior solicitada por el usuario: el porcentaje pasa de23 a
14puntos. Controller `stock-controller-qqq-font-20261019` activo100% sobre la imagen
QQQ anterior, mismo runtime. El overlay verifica el módulo exacto y reemplaza solo
ese tamaño en las dos copias. No cambia datos, celdas, fusiones o dimensiones.
Evidencia específica en `font/`. El historial se cachea por fecha de mercado:
la siguiente captura diaria incorpora el cierre anterior; no es una lectura
intradía ni se garantiza una descarga nueva inmediatamente a las16:00ET.

- Ambos servicios activados al100%, salud200 y hashes de runtime previos exactos.
  Controller: `stock-controller-qqq-pullback-20261019`; móvil:
  `stock-mobile-api-qqq-pullback-20261019`.
- El siguiente refresco natural de Mercado publicó C2:H7: −6,56%, máximo de
  cierre759,66 del06Oct y cierre709,80 del16Oct. No se lanzó un lote de análisis.
- Lectura independiente por conector:70 celdas de títulos/cabeceras/controles
  comparadas sin diferencias; la cuadrícula conserva27 filas/38 columnas.
  Revisión visual nativa en Sheets: sin recortes y resumen en fila12.
  Evidencia: `structure_verification.json` y `sheet-current.png`.
- Paridad móvil real16:06:13UTC: porcentaje y seis etiquetas iguales a las
  celdas verificadas, sin stale ni avisos de fuentes. `mobile_parity.json`.
  También pasó la verificación habitual401/405/404/no-store, informe y cadencia.
- Android: assembleRelease/testDebugUnitTest/lintDebug/assembleDebug y
  assembleDebugAndroidTest correctos; firma existente verificada. SHA256 final
  `bc5728dd3d8684d52fa11da06f0263578258619a14c71d4b550add8a693215eb`.
  Test instrumentado nuevo compilado, sin ejecución ni teléfono físico.
