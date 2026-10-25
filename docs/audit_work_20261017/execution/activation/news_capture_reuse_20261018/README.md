# Reutilización de noticias IBKR por ejecución — 18-10-2026

**Implementada en el flujo local habitual y comprobada sin red.** Las próximas órdenes individuales y de lote adquieren una captura nueva por ticker/proveedor/contrato y la comparten entre noticias, analistas y la ampliación hasta el ancla full. No se reutiliza el lote histórico como fuente futura. No requiere despliegue ni cambiar la revisión financiera40, modelos o configuración. El worker inicia Python nuevo para cada orden.

## Problema y cambio

La [auditoría natural](../natural_run_20261018/README.md) encontró118 adquisiciones para46tickers:46 vistas generales,46 de analistas y26 ampliaciones hasta el ancla. El adaptador ya agotaba todo el caché disponible del proveedor antes del filtro temporal; repetir la descarga para cambiar el inicio de la ventana duplicaba trabajo.207 páginas y1.455,060s de adquisición acumulada eran repetidos; esos segundos se solapan parcialmente y no predicen el ahorro de duración total.

`ibkr_news_capture.py` conserva el payload completo y su prueba de paginación/EOF en objetos locales inmutables con SHA256. Identifica ejecución, ticker, proveedor, contrato cualificado y conexión. Un lock por identidad serializa consumidores concurrentes. La escritura crea objetos completos y un índice; una descarga fallida no deja una captura utilizable. No se usa un caché global de noticias entre órdenes.

`update_analysis_sources_pipeline` y `adaptive_stage` comparten `<batch>/news_captures`; el flujo individual crea su propio directorio de ejecución y lo pasa a ambos preflights y al backfill. Los wrappers transmiten `--capture-dir` y `--capture-max-age-seconds`. El límite sale de la política vigente:24horas actualmente. Esta cifra limita admisión, no permite mezclar órdenes ni garantiza actualidad intradía. Las invocaciones independientes sin esos argumentos conservan la ruta anterior.

Cada vista refiltra las filas brutas desde su fecha inicial, incluso anterior a la primera ventana, después de verificar la modalidad exacta de captura completa. Conserva `coverage.requested_window`, EOF, `generated_at`, `provider_fetched_at` y el límite final originales; añade `view_window`, `derived_at` y `capture_ref`. Una derivación no es una nueva observación. Noticias y estado de analistas rechazan reemplazar un estado conocido más reciente; permiten la misma fecha para ampliar el intervalo. Los raw derivados usan hora de operación con microsegundos para evitar colisiones.

La conexión y cualificación IBKR se mantienen para comprobar identidad; se evitan las adquisiciones repetidas de titulares, no todas las conexiones. BRFUPDN, si se necesita para inicializar analistas, tiene captura distinta de DJ-N. No cambia el parser, consenso, selección de titulares, rúbrica, ITV, modelo, concurrencia ni número de llamadas de análisis.

## Verificación y resolución

| Punto | Comprobación | Resolución |
|---|---|---|
| Reutilización entre procesos | Pipeline, wrappers, preflight individual y backfill comparten directorio; retries conservan identidad | Implementado y verificado localmente |
| Cobertura y fallo parcial | EOF real, método/cursor/páginas, identidades, orden, counts y digest; fallo no crea índice válido | Implementado; no se rebaja cobertura |
| Fechas y estados más nuevos | Corte original inmutable, rechazo por caducidad/futuro, last-good más reciente conservado | Implementado; no renovación artificial |
| Preparaciones futuras | Dos órdenes separadas: la posterior adquiere una noticia añadida y la anterior mantiene su corte | Control determinista aprobado, no observación nueva de mercado |
| Equivalencia histórica |118/118 vistas,46 adquisiciones mediante el módulo aplicado;236 comparaciones de transformación de analistas | Aprobado en este corpus |
| Admisión al modelo |46 contextos naturales con vistas derivadas admitidos;138 mutaciones de cobertura, frescura y ventana rechazadas | Aprobado sin ejecutar modelos |
| Congelados y originales | Cuatro clases de admisión previa impiden refrescar input;504 artefactos históricos y4 módulos ajenos del índice previo sin cambios | Conservados |
| Tiempo futuro | No se ha ejecutado una nueva orden real tras el parche | Medir en el siguiente uso natural; no hay ahorro de pared demostrado aún |

Suite aplicada conjunta: **125 pruebas y125 subcasos aprobados**; un warning previo de `eventkit` sobre el event loop. Las pruebas comprueban también concurrencia, scopes copiados, corrupción, pérdida de índice/objeto, atomicidad y reintentos.24 controles independientes adicionales del almacén pasaron. Las cifras de suites y replays describen conjuntos distintos y no se suman como observaciones de mercado. [Verificación](verification.json), [invariantes](invariants.json), [replay final](final_implementation_replay.json), [admisión y órdenes](independent_admission_and_orders.json).

Las236 comparaciones downstream usan estado vacío y estado guardado posterior al lote como controles de transformación. No reconstruyen el estado previo a cada adquisición. El primer replay fija el mismo reloj por par; el replay final conserva el reloj de la primera captura y compara el estado salvo `as_of`, que deliberadamente deja de avanzar en cada derivación. Firmas, acciones y consenso coinciden en el corpus. Los controles de escritura rechazan usar una captura antigua sobre el estado posterior; comparar transformaciones no autoriza esa sobrescritura.

Cuatro fixtures previos de `test_source_pipeline.py` necesitaron proporcionar la dependencia nueva de política; también se simuló la disponibilidad del Gateway, que antes podían consultar realmente. Se conservaron todas sus expectativas de estado, número de retries y liberación de tickers. No se ajustaron resultados esperados para ocultar fallos.

## Límites operativos y recuperación

La captura cubre el caché disponible del proveedor hasta su corte, no todas las noticias del mercado. Si durante esa ejecución llegan titulares nuevos, no aparecen por arte de magia en sus vistas: se muestra la fecha real y la siguiente orden obtiene otra captura. Cambiar a una actualización continua o añadir una política de refresco intralote requeriría una decisión independiente; no se ha introducido silenciosamente.

Una captura existente caducada, alterada o incompatible falla explícitamente; no se borra para forzar otra observación bajo el mismo contrato. La adquisición original fallida no deja índice válido y permite el retry de datos existente. Una nueva orden puede obtener datos nuevos. No refrescar inputs ya admitidos ni copiar directorios de captura entre órdenes. Las guardas de last-good detectan un estado ya más nuevo, pero no convierten todos los archivos locales en una transacción CAS entre escritores independientes.

El resultado está activo para nuevas preparaciones locales. No hubo adquisición IBKR real, búsquedas, modelos, publicaciones, lote duplicado, despliegue ni cambio de históricos durante esta optimización. No requiere actuación externa para cargar el código; la duración real y posibles cambios de noticias dentro del lote quedan para la siguiente ejecución natural.

## Reproducción y trazabilidad

`implementation.patch` y `code_manifest.json` delimitan este encargo frente al árbol anterior, que ya contenía correcciones de la auditoría. No representan un diff completo contra el checkpoint8034b7a. `baseline.json` conserva los hashes previos; los bytes de respaldo están en `.tmp/news_capture_optimization_20261018/baseline`. La política y el arreglo del lock GCS conservan sus hashes.

Desde la raíz del repositorio se pueden ejecutar los cuatro scripts Python de esta carpeta con `.venv/Scripts/python.exe -B`. Detectan la raíz, leen el inventario canónico y los artefactos históricos originales, y escriben únicamente resultados nuevos en `.tmp/news_capture_reuse_recheck`. No llaman proveedores ni modelos. `reproduction_paths.json` documenta el cambio de rutas respecto de los scripts de trabajo; se conserva el mismo cálculo. Los datos originales deben estar disponibles; su ausencia debe fallar, no convertirse en un replay aprobado.

`INDEX.json` enumera los archivos de esta evidencia por tamaño y SHA256, excepto sí mismo. El inventario previo del lote y sus conclusiones fechadas permanecen intactos.
