# LRCX: rechazo de capacidad antes del análisis — 19-10-2026

Corrección preventiva activa desde14:32:31UTC: raw41 conserva su imagen exacta y permite hasta3instancias en ambos ámbitos; el cliente local reintenta de forma limitada los rechazos temporales de datos antes de admitir el input. **LRCX recuperado y publicado** a14:39:07UTC mediante un full individual nuevo; el lote original y sus dos fallos permanecen intactos.

## Incidente y evidencia

La orden `20261019-114118-market-full41`, lote `logs/batch/2026-10-19/11-45-16`, dejó LRCX fallido en preparación tanto en11:45:40–11:47:30UTC como en12:29:47–12:31:33UTC. No hubo input admitido ni llamada de modelo de LRCX en esos dos intentos. Los otros45tickers se publicaron.

Cloud Run registró para LRCX dos HTTP429 de raw, con `no available instance`, a11:45:59 y12:30:03. El log no asigna instancia al rechazo. Segundos después arrancó una instancia en cada ventana; la primera atendió los siguientes tickers con200. Slim tardó91,45/91,98s en devolver cada502 envolviendo el429; el runner abandonaba `_fetch_slim` inmediatamente y el reintento de lote volvió a encontrarse con un arranque frío. No fue un fallo de research web, del modelo ni una ausencia de datos financieros de LRCX.

El servicio y la revisión raw tenían ambos máximo1, mínimo0 implícito, concurrencia80,1CPU/256Mi y120s. Se observan el límite, los rechazos y los arranques fríos; no se atribuye una carga CPU concreta ni se inventa un fallo del proveedor Tradier. Google describe este429 como falta de capacidad disponible con límite de instancias y recomienda margen y reintento temporal; [diagnóstico oficial](https://docs.cloud.google.com/run/docs/troubleshooting#abort-request) y [semántica de ambos límites](https://docs.cloud.google.com/run/docs/configuring/max-instances).

- [Intentos originales](original_attempts.json), [logs de fallo](failure_logs.json), [contexto de peticiones/arranques](capacity_context.json).
- [Configuración anterior raw](raw-before.json), [slim](slim-before.json).

## Cambio del cliente

`technical_http.read_slim_response`, utilizado por `_fetch_slim`, mantiene la misma petición completa (ticker, AVWAP, opciones, orígenes de soporte y archivo). Reintenta solamente HTTP429/503 directo o502 con el contrato exacto `raw_endpoint_http_error` y prefijo429/503 de requests. No busca la palabra429 en cualquier mensaje. No reintenta401/403/404, errores de contenido/JSON, errores de conexión ni llamadas de modelo.

Máximo3peticiones por captura y presupuesto de240s para admitir nuevos intentos, con timeout individual acotado por el tiempo restante. Espera2/4s más jitter y respeta `Retry-After` válido, incluida fecha HTTP. Si la espera no cabe, conserva el fallo en lugar de adelantarse. Expiración y agotamiento conservan el error real; el sistema sigue sin aceptar una captura incompleta ni refrescar last_good con vacío. El presupuesto limita reintentos y timeouts de socket; no se afirma que urllib imponga un deadline absoluto frente a un servidor que entregue bytes indefinidamente.

Los reintentos se registran como `technical_source_capacity` con intento, estado HTTP/raw, demora, tiempo restante y motivo de agotamiento. Sólo el cuerpo200 final pasa a JSON/archivo/admisión. No se reutiliza un input congelado ni se modifica la política financiera o el modelo. Los nuevos procesos de cada orden cargan el cliente corregido.

## Capacidad y activación

`support-resistances-raw-capacity41-20261019` activo100% con la misma imagen `sha256:e61de924e4e09eadbc7c8f38a97598d7ddf01f4e85b3561449fee4049ba45180`. Máximo1→3 a nivel servicio y revisión, mínimo0 conservado. Ningún cambio en CPU, memoria, concurrencia, timeout, secretos, variables, IAM, fuentes o lógica41. Tags anteriores conservados y candidato validado con petición sin símbolo400, que no llama al proveedor ni escribe mirrors.

El SDK485 no conoce `--max`. Su primer comando falló al parsear, sin cambio. La API oficial con máscara exacta y etag creó el candidato; la validación previa sin nombre nuevo devolvió409 sin modificar el servicio. Un intento posterior de añadir tag mediante el SDK falló por diferencias de representación de configuración, por lo que se completó tráfico/tag con la misma API, sin volver a aplicar capacidad. La API materializa tres defaults equivalentes: minScale0, cpu-throttling=true y sessionAffinity=false. Tras normalizarlos, el hash de todo el runtime salvo el máximo es idéntico antes/después: `2a2d33f44a8e61a98e5cc64faab76d9cec0f3b10021c95aee11823bc46460c73`. No se declara igualdad binaria de representaciones diferentes.

El script usa la autenticación GCloud existente con cuenta/proyecto fijados, tokens sólo en memoria y actualización de tres campos (`scaling.maxInstanceCount`, `template.revision`, `template.scaling.maxInstanceCount`), seguida de tráfico explícito. No añadió permisos ni cambió seguridad. Un rollback a la revisión anterior devolvería su máximo1; conservar ambos límites3 en un rollback compatible.

- [Operación de capacidad](service-scaling-operation.json), [lectura de comprobación](service-scaling.json), [inspección normalizada](stage_inspection.json).
- [Staging](raw-staged.json), [probe](raw-probe.json), [activación](raw-active.json).
- [Script de corrección](../../scripts/fix_raw_capacity_20261019.py), [cliente](../../src/local_runner/technical_http.py), [pruebas](../../tests/test_technical_http_retry.py).

## Validación y recuperación individual

La caracterización previa del fallo429→502 falla con el código anterior. Tras el cambio pasan108tests+17subcasos de transporte, archivo técnico, admisión41, intentos individuales, noticias compartidas y plazos. Incluye los dos errores exactos originales, selector completo idéntico, un único archivo final, presupuesto/reintentos, Retry-After y errores permanentes. [Caracterización](baseline_tests.xml), [regresión](regression_tests.xml).

Se ejecutó únicamente `run_one LRCX --run-full`, con fuentes nuevas y modelo high configurado, después de comprobar que no había otro análisis activo. La ruta individual resuelve propiedad actual y conserva autoridad CAS. El lote original no se reanuda ni se reescribe: [hashes iniciales](recovery-start.json), [stdout](recovery.stdout.log), [stderr](recovery.stderr.log), [resultado exitoso e integridad del lote anterior](recovery-result.json).

La adquisición raw de14:34:22UTC terminó200 en8,470s en la revisión nueva, en una sola petición con los cinco selectores completos; [logs](recovery_source_logs.json) y [comprobación](recovery_sources_verified.json). La recuperación no necesitó ejercitar los reintentos en vivo; éstos se probaron con los dos errores exactos, sin provocar otra saturación real.

Una llamada `gpt-6.1-sol` high con investigación,6operaciones web,0repair/0fallback, terminó14:38:55UTC y pasó la validación habitual. Commit14:39:07UTC, versión `15395777fcd6499790c90a7da9d0ed42e8c104fceaa9801272736ae281cc7576`; proceso terminado0 a14:39:55UTC. Verificados los seis objetos inmutables por el contrato/digest del manifest, intento canónico `succeeded`, JSON íntegro (`debug=true`) y HTML públicos exactos200. El primer comparador de lectura usó la vista JSON resumida por defecto; se corrigió el verificador para solicitar el JSON íntegro, sin cambiar el informe ni el lector. [Verificación de publicación](publication_verified.json).

Sheet se actualizó por el escritor habitual: LRCX enlaza esa versión y ya no muestra el aviso de fallo. Los46enlaces siguen presentes y los45restantes conservan sus URLs previas. [Lectura posterior](sheet_after.json), [comprobación](sheet_verification.json). No se forzó una segunda sincronización ni otro análisis.

No se fuerza un arranque frío, saturación ni lote duplicado para probar. Las pruebas reproducen el rechazo, y la recuperación real contrasta la integración. No se promete que una caída persistente de infraestructura nunca pueda producir un fallo: los rechazos persistentes deben seguir siendo visibles sin inventar un informe.
