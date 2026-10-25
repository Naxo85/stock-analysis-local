# Ruta de ejecución: aclaración Codex local

Comprobación solo documental; no se lanzó ningún proceso Codex, modelo, app-server ni conexión de red. Las tres llamadas pendientes permanecen detenidas. La última respuesta del usuario no constituye autorización adicional.

## Conclusión

El harness reutiliza la función call_codex existente. Esta ejecuta el binario Codex instalado localmente y su comando exec con autenticación ChatGPT. No introduce un SDK OpenAI, cliente API alternativo, clave API, proveedor, modelo o endpoint nuevo. Decir «enviar al CLI OpenAI» resultó confuso: la ruta solicitada y existente es Codex local, cuyo modelo se atiende en el servidor de OpenAI; local describe dónde corren el CLI, los archivos y el runner, no inferencia del modelo sin red.

## Evidencia de código y proceso observado

- harness.py:200 invoca src.local_runner.adaptive_codex.call_codex; usa modelos/esfuerzos cargados del config vigente. Cambios exclusivos de escenario: contrato financiero40, contexto histórico aislado, research=False y rutas de artefactos temporales.
- adaptive_codex.py:133–149 construye require_codex(), exec, --json, sandbox read-only, modelo configurado, forced_login_method=chatgpt y model_provider=openai. Todos esos argumentos estaban ya en el baseline.
- adaptive_codex.py:163–165 elimina OPENAI_API_KEY, CODEX_API_KEY y OPENAI_BASE_URL del entorno hijo. No se leyó, copió ni imprimió ninguna credencial. Se usa el almacén normal de autenticación Codex ya existente.
- codex_generator.py:173–212 resuelve primero CODEX_CLI_PATH si existe; en Windows, de otro modo prioriza el codex.exe empaquetado con la aplicación de escritorio, luego npm/PATH. Ese archivo es idéntico al baseline.
- El traceback del intento AMD registra el binario efectivo C:/Users/ignac/AppData/Local/OpenAI/Codex/bin/2e5e00daee91c61d/codex.exe y el comando exec. No se ejecutó otro binario.
- Los logs AMD muestran la conexión interna del CLI a wss://api.openai.com/v1/responses y su cambio automático WebSocket→HTTPS después del bloqueo socket10013. Esa reconexión es conducta del binario, no un cambio de transporte programado por el harness ni un cambio de proveedor. El código de resolución no fija una versión de binario, de modo que la igualdad de código no afirma que cada ejecución histórica utilizara la misma versión instalada.
- adaptive_sessions.py:24–65 usa el mismo ejecutable con app-server --stdio para gestionar/revertir la historia de las sesiones propias tras completar una respuesta, manteniendo la caché de prefijo. No es el camino de generación del informe. adaptive_codex.py:221–222 solo llama session.completed si exit_code0 y no timeout. En AMD no hubo reset/app-server por esa rama: timeout, sesión retirada, session_history_cleared=false.

## Diff exacto de adaptive_codex.py

Baseline SHA-256: 156fb05c5f6068028b06a578ea7470f8b7caf50d28b5fca7fb016f446c9a16c7

Actual SHA-256: d5aaa500295c1bd650ec7d129c717aa43adad0cd737a36aa1f6206e30aeb0b65

El único cambio es añadir dos hashes al recibo en líneas236–237:

```diff
+ "response_sha256": hashlib.sha256(response.encode("utf-8")).hexdigest(),
+ "events_sha256": hashlib.sha256((result.stdout or "").encode("utf-8")).hexdigest(),
```

Diff completo guardado en adaptive_codex_baseline.diff. No afecta command, provider, auth, modelo, endpoint, entorno ni transporte. Son comprobantes de integridad para detectar edición de respuestas/eventos. La ruta de timeout de AMD ni siquiera llegó a ese recibo de finalización normal.

Identidad byte por byte contra baseline:

| Archivo | SHA-256 común |
|---|---|
| src/local_runner/codex_generator.py | ff044391dfe986e4a56dd9ad2fb6e888835ff45622ff800cd10d5ea5c2208018 |
| src/local_runner/adaptive_sessions.py | 4d7cd61f5167055b863f25a53f24d066aca36dd35f6abb2456f974bd9ad5d743 |
| config/codex_analysis.json | c2f6269b84c76e62c16732a9eeb8b3f111eb1894d062420a3bc157f54264d3ec |

El config sigue routing39 y gpt-6.1-sol medium/high. La evaluación no activó40. Su copia temporal cambia routing_revision40 y research=False, preservando modelo/esfuerzo/timeout. No hubo cambio a facturación API por clave; el intento carece de usage y no permite deducir coste monetario.

## Estado

AMD: un intento local terminado, sin respuesta y con reconciliación ambigua. No repetir. LEU/TLN/MRNA: no iniciados y detenidos. La ampliación de permisos previamente solicitada era del proceso local para acceder a la red, no una propuesta de cambiar Codex local por otra API; fue rechazada y no se sorteó. No se solicita ni ejecuta ahora ninguna escalación.
