# Avisos de earnings — 21-10-2026

**Estado: activado y comprobado en producción21-10-2026.** El usuario autorizó expresamente la subida/despliegue y activación después del rechazo automático inicial. Controller y API móvil `earnings-20261021` están al100%, con sus runtime/tags anteriores preservados. Refresco de proyección46/46, sin reordenación, y lectura independiente de Sheets/visual Google/móvil correctas: **LRCX K8 tiene cuatro bordes rojos gruesos y nota21/10/2026 · hoy**. SPCX no tiene marca porque su fecha era20Oct.

Contrato: [decisión0008](../../gcp_services/stock_controller/docs/decisions/0008-avisos-de-resultados.md). Borde naranja fino2–7días; rojo grueso hoy/mañana; retirada al pasar la fecha; fecha Europe/Madrid. Nota fechada, identidad/enlace/fondo de cartera conservados. App con etiqueta equivalente y cálculo de vigencia también sobre copia offline.

## Fuentes y reproducción

Lectura real sin modificaciones de los informes publicados: [ejemplos](published_examples.json). SPCX conserva fecha de resultados20Oct, LRCX21Oct. Aplicando reloj20Oct ambos serían rojos; aplicando21Oct sólo LRCX sigue marcado. Verifica la proyección del calendario suministrado, no una investigación independiente de fechas oficiales ni un cambio de informe.

El sincronizador toma sólo `analyst_ratings_summary` válido, conserva `as_of` como fecha del resumen y escribe calendario en `sync-state.json`. El refresco existente reutiliza su lectura de estado para aplicar marcas después de ordenar y restablecer bordes. La API lee el mismo calendario. No se consultan nuevas fuentes ni se cambia autoridad financiera. Fechas no disponibles no se deducen de narrativa.

## Verificación

75pruebas focalizadas del controlador y21API pasan. Incluyen límites0/1/2/7/8, medianoche Madrid, fechas inválidas, expiración sin informe nuevo, movimiento entre tablas, conservación de notas, refresco programado con calendario guardado y máscaras de escritura. Regresión de enlaces normalizados, fuerzas, soportes, puntuaciones y QQQ aprobada. APK conectada compilada con firma existente;8unitarias Android, lint y compilación de APK de interfaz aprobados. La prueba instrumentada no pudo ejecutarse: el emulador privado no dispone del controlador de aceleración requerido; no se instaló ningún driver. Resultado y hashes en [verification.json](verification.json).

Esta tarea no ejecutó modelo, batch, publicación financiera ni operaciones de cartera. Sí escribió la proyección habitual de Sheet para activar marcas. El lote natural `logs/batch/2026-10-21/06-52-46` y el procesamiento de órdenes de cartera estaban activos independientemente: cambiaron enlaces/avisos y algunos fondos durante la comparación. No atribuir esas diferencias a las marcas ni afirmar que toda la hoja quedó idéntica. La lectura final confirma46identidades/enlaces de ticker,46fondos concordantes con cartera vigente y10avisos concordantes con calendario/API. [Verificación Sheet](sheet_verification.json), [paridad móvil](mobile_parity.json). Teléfono físico sin verificar; APK nueva requiere instalación.

## Paquete preparado

`scripts/deploy_earnings_20261021.py` conserva imágenes inmutables y runtime consultados. El primer parche por texto detectó diferencias de ubicación/espaciado; la captura de fuentes exactas permitió validar y aplicar cambios por AST sobre las funciones importadas del paquete instalado. Se conserva el árbol `/app/src` antiguo sin uso, que no equivale al paquete de ejecución. Una prueba de paridad local de API corrigió su detección de raíz al ejecutarse en Docker. Las imágenes finales pasan36tests controller y20API más1paridad de repositorio omitida en imagen (local21/21). Hashes y baselines se vuelven a comprobar antes del despliegue.

Inventarios: [controller](controller/controller_before.json), [mobile](mobile/controller_before.json). Paquetes: `controller/package.json` y `mobile/package.json`. Bases QQQcompact19Oct. Activos: [controller](controller/active.json) `sha256:65f2af4d6808f5c9a8194aabd0f7c9273a76f5446ef2bcc938dbfe07c3ff7665` y [mobile](mobile/active.json) `sha256:e199a1b8167eec3e7a9c33221c69a50a00b64a8531fab18ecbac4c41e55502f8`. Runtime hashes exactos frente a los inventarios. Health200 en ambas revisiones antes de activación.

El stage controller tardó más que el límite180s del CLI, pero terminó Ready en Cloud Run. Se reconcilió la operación existente verificando imagen, runtime, tags, tráfico anterior y Ready; no se repitió despliegue. Después health200 y activación normal. [Stage reconciliado](controller/staged.json), [refresh](controller/refresh.json). Bordes compartidos naranja/rojo se normalizan en Sheets a una sola arista del vecino rojo, según la prioridad definida; lectura final lo verifica sin confundirlo con un borde perdido.
