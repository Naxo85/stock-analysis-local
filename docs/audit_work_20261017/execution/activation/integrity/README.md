# Cierre A1 e integración local40

A1 está desplegado y verificado: reports, stock-mobile-api y stock-controller quedaron Ready al 100%, con runtime anterior preservado salvo imagen. Se verificaron CAS real en datos sintéticos, lectores/proyección con bucket privado aislado y 46 informes legacy originales sin cambios de contenido/fecha/generación. Se retiraron 36 objetos de prueba, bucket, Job, dos revisiones y tags propios. El bucket temporal conserva la retención soft-delete del proveedor de 7 días; no se afirma purga física inmediata.

La revisión local final (2026-10-18 07:46 UTC) no encontró otro bloqueo de integración A1: policy 40 candidata cambia sólo revisión y los cuatro parámetros de publicación/intentos/archivo/auth, conserva modelos/esfuerzos, y utiliza el puente CLI explícito inspeccionado. ADC de servicios permanece normal. SDK local disponible. En ese momento la configuración global seguía 39, pendiente de canarios/fuentes que coordina raíz; este cierre no afirma que 40 estuviera ya activada ni aprueba resultados financieros.

Se corrigió el fallo de visibilidad individual previo a prepare: el intento conserva identidad/fase/fecha/causa si propiedad, preflight, Gateway o fuentes fallan. Un fallo secundario del aviso no sustituye la causa original. No se crea un informe financiero ni una propiedad por el error. Hay cobertura con flag off y sin informe previo.

Se corrigió propiedad desconocida y autoridad individual/manual: Mercado estricto; bool explícito en listas GCS conserva la lista seleccionada. Datos faltantes/no booleanos se resuelven una vez desde Mercado o fallan antes del modelo. Replays de universos 38/30/46 mantienen selección/orden/bools y ahora procedencia exacta; cero consultas adicionales para los completos. LEU/MRNA coinciden entre fuentes y el input LEU admitido conserva su hash. Los 18/4 desacuerdos históricos son diferencias entre fuentes/fechas, no una orden de sincronizar cartera. No hubo escrituras de configuración de tenencia.

Nueva preparación batch conserva selection_source y ownership_source resueltos en input.ownership mediante argumento opcional validado. Esta traza está protegida por el binding del input posterior; no firma retrospectivamente una fuente externa ni demuestra tenencia actual. Checkpoints/inputs históricos no se reescriben. La interfaz lanza subprocess nuevo por solicitud; recarga configuración sin reinicio del worker, salvo reanudación intencional del mismo trabajo congelado.

Verificación final: 76 pruebas y 45 subpruebas pasan en 3.33 s con red/procesos externos bloqueados. Incluyen 6 casos nuevos de procedencia, propiedad, lifecycle, política, pipeline y consumidores. Son posteriores a las 37+11 del lifecycle y 51+31 de propiedad; no se deben sumar como pruebas únicas. A1 cuenta además con 80 pruebas anteriores de auth/integridad/consumidores y las verificaciones en imagen/cloud documentadas. No se repitieron llamadas cloud al cerrar y no hubo nuevas llamadas de modelo en esta subtarea.

## Evidencia y límites

- index.json es la whitelist durable con SHA256, tamaños, origen y transformación de cada archivo, excepto el propio índice para evitar hash circular. No modifica el manifiesto histórico de 92 archivos.
- runtime_state.json y build_evidence.json conservan digests/guardas/runtime y el fallo inicial CRLF seguido de rebuild exitoso. iam_scope.json documenta la única concesión, objectViewer al controller sobre el bucket de informes; se omitieron identidades personales previas.
- cleanup-results.json, live-cas-result.json, isolated-http-results.json y controller_job_evidence.json acreditan pruebas sintéticas y limpieza. La prueba controller proyectó en memoria con imagen/SA reales, sin escribir Sheet.
- legacy 46-readback.json y active-http-results.json acreditan lectura real intacta. Sheet sigue siendo proyección asíncrona; atomicidad por ticker/manifest, sin transacción global del universo.
- ownership_provenance_test_results.json, ownership-replay-results.json y final_integration_review.json contienen la última verificación local. Las fuentes completas de cartera, cuerpos financieros, recibos/modelos, logs de identidad, secretos y tokens no se copiaron.

El alcance es integridad operativa y readiness A1. Los canarios de modelo, fuentes40, activación final global y Android corresponden a las verificaciones coordinadas por raíz. Las nuevas solicitudes usarán la política activa al prepararse; ningún informe legacy se convirtió ni se redató para demostrarlo.
