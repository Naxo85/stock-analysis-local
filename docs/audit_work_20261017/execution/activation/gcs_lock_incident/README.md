# Incidente H17: lock GCS con PID reutilizado — 18-10-2026

## Resultado

Corrección local aplicada a analysis_state.py y regresión nueva. Verificación real solo lectura terminada08:49:29UTC:46/46referencias resueltas en244,984s, sin fallback local ni lock residual;0llamadas de modelo y0publicaciones. La orden original 20261018-082922-202-market-cc4da3e3 conserva estado failed; no se reanudó ni repitió el lote, no hubo llamadas de modelo ni publicaciones por este diagnóstico.

## Causa demostrada y alcance de la atribución

La orden analyze_market comenzó08:29:57UTC y falló08:33:09UTC, tras192,034s. El traceback se detiene en routes_for → load_reference_payload → committed_payload → read_text_gcs → _exclusive_read_lock, antes de crear logs/batch y antes de los análisis. El archivo .local/gcs-read.lock tenía exactamente {pid:104024}, escrito08:06:29.403405UTC. El proceso actual con ese PID era conhost.exe, creado08:26:29.156706UTC: nació casi20min después y no podía ser el propietario original. El chequeo antiguo preguntaba únicamente si el PID estaba vivo y por eso agotaba180s.

Una copia aislada con el mismo PID y timestamp reprodujo gcs_read_lock_timeout sin red. Tras el parche, GetProcessTimes devolvió la instancia actual viva con nacimiento posterior, se recuperó esa copia y se adquirió/liberó un lock nuevo con token. El archivo real permaneció intacto durante ambas reproducciones; la lectura real posterior lo recuperó usando el helper corregido, sin matar conhost ni borrar un lock por edad.

El residuo se creó durante la ventana de puesta en servicio. No se conservó la identidad de instancia del proceso original: no se puede atribuir qué subproceso lo creó ni por qué no lo liberó. El defecto PID-only ya existía antes del cambio; la nueva lectura manifest lo hizo visible antes del fallback legacy. La puesta en servicio no verificó la combinación de residuo/PID reutilizado y arranque del universo. No se culpa a GCS ni al borrado posterior de tags Cloud Run, que no toca este archivo local. El fallback local no se amplió para ocultar un posible manifest vigente.

## Cambio y protecciones

- En Windows se consulta el inicio de la instancia mediante GetProcessTimes. Los locks antiguos {pid} se consideran abandonados por reutilización solo cuando el proceso actual nació después de la escritura.
- Los locks nuevos guardan PID, inicio y token. La liberación comprueba el token y la identidad observada del archivo; no elimina otro token observado.
- Estado desconocido, acceso denegado o nacimiento no disponible conserva al posible propietario vivo. Antigüedad por sí sola no basta. Dueño muerto confirmado sigue siendo recuperable.
- Locks incompletos conservan su gracia de5s y el formato viejo del pool permanece compatible. adaptive_sessions.py y codex_generator.py no se modificaron. Configuración40/modelos/ITV intactos; espera180s, petición60s y2intentos iguales.
- Se comprueban bytes/identidad antes de retirar. El compare seguido de unlink mantiene una pequeña carrera preexistente: no es una primitiva atómica de borrado condicionado ni protege frente a compromiso del host. No se presenta como rediseño total del mutex.

## Verificación y contraevidencia

Los8tests anteriores pasaban antes del parche pese a que la reproducción real fallaba. Los19nuevos cubren reutilización legacy/nueva, propietario vivo/unknown, acceso denegado, identidad inválida/futura, lectura incompleta, sustitución observada y liberación por token. Un hijo Python real aislado demuestra exclusión mientras vive y recuperación después de terminarlo; no usa lock productivo, red ni modelos.

Sobre código aplicado:87pruebas y39subcasos aprobados en15,39s. Tres casos antiguos fallan igual antes y después, por fixtures de bundle/cache que no reúnen el contrato actual; no se cambiaron expectativas ni código de publicación para hacerlos pasar. La comparación completa fue68PASS/3FAIL/35subcasos con original y87PASS/3FAIL/39subcasos con staging. La corrida final deselecta esos3de forma explícita; no es una afirmación de toda la suite verde. Ver lock_regression_baseline_comparison.json y applied_tests_result.json/log.

La comprobación real ejecutó --routing-plan para Mercado con46tickers y referencias GCS. Terminó08:49:29UTC tras244,984s, exit0,46rutas distintas resueltas, sin advertencias de fallback local y sin lock al salir. Modelos configurados gpt-6.1-sol, pero0llamadas reales: se hizo solo planificación. stdout privado identificado por SHA2565480f5898a49961e9a34969adfeeaacf3349362a9e123f933b07218412ce2540; stderr vacío. Esta comprobación no sustituye un lote completo ni prueba Gateway, adquisición de fuentes, modelos o publicación. Sí atraviesa exactamente la fase de lecturas/admisión que abortó la orden original.

## Evidencia

Archivos de reproducción y comprobación por hashes en INDEX.json. El fallo original y sus horas están conservados; la salida completa del plan con valores privados de tenencia queda únicamente en .tmp/incident_gcs_lock_20261018, con hash en el resumen. Esta carpeta durable no contiene ese payload ni credenciales. apply_manifest.json identifica los dos archivos de código/test; protected_checks.json compara generador/sesiones/política y el fallo original sin cambios.
