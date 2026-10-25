# Revisión independiente de readiness local40

Revisión local, sin llamadas remotas ni modelos. Evidencia ejecutable: check_local_readiness.py y local-readiness-results.json. Configuración activa al revisar:39; candidata:40.

## Hallazgo corregible H12

adaptive_stage.run_individual hacía require_activation, propiedad, referencia, preflight Codex, Gateway y actualización de fuentes antes del try y antes de crear work (líneas989–1006 previas a corrección). Reproducción con mocks de un fallo de fuente: excepción original escapó, record_attempt=0, record_failure=0 y work inexistente. El canario tiene su propio activation_prepare_failure; por tanto un canario aprobado no probaba esa visibilidad del flujo individual. No había modelo ni publicación posterior al fallo, pero consumidores no conocían el intento.

Corrección aplicada y verificada en individual_stage_manifest.json: crear identidad/directorio del intento antes del preflight, try cubriendo las fases y failure.json con fase/tipo/causa/fecha; reutilizar record_failure para conservar causa raíz si falla el aviso remoto. Ninguna propiedad se inventa y ningún informe/fecha financiera se genera por el error. La ruta completa individual sigue forzando full conforme a su comportamiento anterior; batch continúa con triage/ITV.

## Comprobaciones sin bloqueo adicional confirmado

- Candidata cambia exactamente routing_revision, publication_protocol, latest_attempt_publication_enabled, technical_archive_enabled y publication_auth. Modelos, esfuerzos medium/high, web, ITV5, paralelismo6, timeout y frescura24h idénticos39.
- load_policy no tiene caché en proceso: se verificó con archivos temporales39→40. prepare congela policy/input/prompts; analyze y publish leen la política congelada, y bundle verifica su hash. No se debe reinterpretar un work39 como40 por activarconfig.
- run_one --run-full individual Codex llega a run_individual y conserva owned=None hasta consultar propiedad explícita. Canario mantenimiento equivale a prepare/analyze directo para casos elegidos; un run_full individual sigue siendo full forzado, no una prueba de selección automática batch. Batch invoca adaptive_stage con cada etapa y transmite owned/force_full desde route.
- latest_attempt usa work/policy.json cuando existe y config actual antes del congelado. GcsStore recibe publication_auth en commit y aviso. SDK instalados en .venv: storage3.13.0/auth2.56.2; gcloud.cmd presente. requirements-manifest.txt optativo necesario también al instalar el runner en otro equipo.
- CLI auth bridge fija cuenta/proyecto para CAS/attempt y no usa ADC silenciosamente; lectores del servicio mantienen ADC. Lecturas de autoridad y aliases compatibles siguen usando el CLI activo, sin argumento account explícito: la identidad activa fue verificada igual a la fijada durante A1. Cambio posterior de cuenta CLI es un límite operativo y puede producir fallo visible de lectura/mirror, no fallback de autoridad.
- load_reference_payload y load_current_report resuelven primero manifest confirmado (anchor/current). Error de transporte/corrupción no se confunde con ausencia de manifest. Publication guards validan base/ancla/review/frescura, y commit vuelve a comprobar frescura justo antes de CAS. ITV deriva del full anchor y sólo full lo reinicia. Cachétriage incluye política, schemas, instrucciones y estado temporal; añadir40/auth no reutiliza una clave39 accidentalmente.
- Consumer Ready100% ya demostrado en A1, con46informes legacy íntegros. Esto no activa config por sí mismo; raíz debe promover fuentes40 y política candidata en orden coordinado.

## Propiedad corregida y conservación del universo

La coerción previa de owned ausente/no booleano a false quedó corregida. Individual y selección manual usan estrictamente config/tickers_market.json, según AGENTS; --owned/--no-owned siguen siendo overrides explícitos. En --from-gcs/--config-gcs, un booleano explícito mantiene la autoridad de la lista seleccionada, su universo y orden; un valor ausente/no booleano se resuelve en Mercado una sola vez o falla visible por dato desconocido/ambiguo. No se infiere ausencia de una lista ni se cambia ninguna cartera/config remota.

Lectura real autorizada encontró38/30/46 registros booleanos únicos en trading/core/Mercado. Replays locales preservaron todos los tickers, orden, bool y etiquetas, sin lecturas adicionales para listas completas. Trading04-sep y Mercado16-oct discrepan en18 símbolos compartidos; core03-sep y Mercado16-oct en4. Esto describe fuentes/fechas diferentes, no prueba cantidades actuales. LEU/MRNA coinciden false antes/después; inputLEU ya admitido se conservó byte a byte (hash en ownership-replay-results.json).

## Entrada por interfaz y trabajador

command_worker construye una orden nueva con sys.executable -m run_one/run_batch y execute_command inicia Popen por solicitud; no importa ni guarda una política de análisis en el trabajador. run_batch inicia también un proceso adaptive_stage por etapa. Las nuevas solicitudes recargan configuración/fuentes de código sin reiniciar el worker. Sólo la reanudación del mismo command_id incompleto reutiliza su checkpoint/input/policy congelados, intencionadamente. Mock de ambas acciones confirma módulos/subprocesos sin ejecutar análisis. El launcher normal usa la .venv del repositorio salvo override STOCK_ANALYSIS_PYTHON; no se detuvo ni reinició nada.

## Estado

Ajuste H12 aplicado con hashes exactos y verificado: 37 pruebas y 11 subpruebas pasan en5.59s (test_individual_attempt_lifecycle, test_publication_consumers y test_run_batch_pipeline), con harness aislado sin red/procesos externos. Aprobación limitada del flujo local nuevo40, sujeta a los canarios/fuentes y activación coordinada por raíz, con las correcciones de propiedad indicadas. No se ha aprobado rentabilidad ni resultado financiero de canarios. No se han revisado los cambios de timeoutIBKR en paralelo (propiedad financiera/datos).

Verificación final tras procedencia batch: 76 pruebas y45 subpruebas pasan en3.33s con aislamiento; seis casos nuevos verifican transporte, identidad/booleano, origen explícito/fallback, persistencia y congelados. Replays38/30/46 exactos con procedencia. final_integration_review.json comprueba candidata40 frente a activa39: sólo cambian los cinco campos previstos; modelos/esfuerzos iguales, auth explícita coincide con identidad inspeccionada, SDK presentes. Los estados remotos son evidencia de la verificación A1 ya realizada (07:23–07:24UTC), sin una nueva consulta ni mutación. No encontré bloqueadores locales adicionales; promoción40 sigue condicionada a canarios/fuentes coordinados por raíz.
