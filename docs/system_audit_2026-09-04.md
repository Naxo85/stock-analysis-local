# Auditoria integral del sistema - 2026-09-04

## Resumen ejecutivo

El sistema funciona como una arquitectura hibrida: Google Sheets y Apps Script
actuan como interfaz, GCS como bus y almacenamiento, Cloud Run como capa de
consulta y calculo, y un PC Windows como motor real de analisis. El flujo local
esta bien cubierto por pruebas unitarias, pero la seguridad y la operacion tienen
varios puntos que conviene corregir antes de seguir ampliando funcionalidad.

Hallazgos prioritarios:

1. **Critico:** un servicio registra la cabecera completa de Tradier, incluido el
   token Bearer, en Cloud Logging.
2. **Alto:** el lector de informes es publico y su parametro `debug=true` devuelve
   el JSON completo, que incluye contexto interno de IBKR y el snapshot tecnico.
3. **Alto:** hay servicios publicos desplegados cuyo codigo activo no esta bajo
   control de versiones en este repositorio; todos usan la cuenta de servicio de
   Compute por defecto.
4. **Medio:** el bucket carece de acceso uniforme, prevencion publica forzada,
   versionado, retencion y reglas de ciclo de vida.
5. **Medio:** la automatizacion depende de una tarea Windows de inicio de sesion
   interactivo en un unico PC y no existe un bloqueo global entre ejecuciones.

El mapa de componentes y la secuencia operativa estan en
[`component_map.md`](component_map.md).

## Alcance y metodo

La auditoria cubrio:

- codigo Python activo en `src/`, `gcp_functions/` y `scripts/`;
- Apps Script en `apps_script/`;
- configuracion, prompts, pruebas y documentacion;
- separacion entre codigo activo y `incoming_from_gcp/`, que es solo referencia
  historica;
- configuracion desplegada de Cloud Run, GCS, Secret Manager y Apps Script,
  consultada en modo lectura;
- tarea local `Stock Analysis Command Worker`;
- pruebas Python y pruebas JavaScript ejecutables con el Node instalado.

No se modifico infraestructura ni se leyeron valores secretos. Tampoco se lanzo
un analisis real de un ticker. La paridad exacta entre los ficheros locales de
Apps Script y el codigo abierto en el editor remoto no se verifico, porque
`clasp status` enumera el proyecto local pero no compara contenidos remotos.

## Arquitectura observada

### Interfaz y orquestacion

- La hoja es **Google Sheets**, no un libro de Microsoft Excel. No se detecto
  ninguna integracion activa con Excel.
- La hoja `Bolsa_2026` contiene los perfiles Trading y Core en grupos de columnas
  distintos.
- Apps Script exporta listas a GCS, publica ordenes, consulta resultados, refresca
  precios y datos tecnicos, y actualiza objetivos y notas.
- La orden se escribe en `commands/pending/`; el worker local la mueve a
  `commands/running/` y publica el resultado en `completed/` o `failed/`.

### Motor local

- `src.local_runner.run_one` ejecuta el flujo individual: IBKR, fuentes previas,
  endpoint slim, prompt, Codex CLI, validacion, HTML/JSON y subida.
- `src.local_runner.run_batch` prepara fuentes comunes, aplica la politica de
  modelos y ejecuta tickers en paralelo.
- El flujo normal usa titulares recientes de IBKR sin preagregacion por IA. La
  agregacion con Gemini existe, pero es opcional y no forma parte de la ruta
  diaria predeterminada.
- IBKR Gateway/IBC se ejecuta localmente contra `127.0.0.1:7497` en modo de solo
  lectura.

### GCP y almacenamiento

- GCS conserva configuracion, cola, estados, informes vigentes, snapshots,
  historial, estado de referencias y el paquete de bootstrap de IBKR.
- `reports` sirve informes desde GCS a Apps Script.
- `support-resistance-values` calcula metricas de mercado usadas por los refrescos
  de la hoja.
- `support-resistances-slim` entrega el JSON tecnico usado por el analizador
  local.
- Siguen desplegados `support-resistances-raw`, `gemini-stock-analyze` y
  `stock-analyze-batch`, aunque no forman parte del flujo local diario actual.

### APIs externas

Se detectaron dependencias con IBKR, Tradier, Yahoo Finance, Finnhub, Financial
Modeling Prep, Nasdaq, CNN Fear & Greed, RapidAPI, Gemini, Codex CLI y Google
Cloud Storage. Algunas son fallback u opcionales; el mapa visual distingue esas
rutas.

## Hallazgos

### AUD-01 - Critico - Credenciales expuestas en código y logs

**Evidencia:** `gcp_functions/support_resistance_values/main.py:593-607` construye
la cabecera `Authorization` y registra el diccionario completo a nivel `error`.
Tambien registra cabeceras y cuerpo de respuesta. La fuente de
`support-resistances-raw` recuperada el 2026-09-04 contenia asimismo un token de
Tradier y un PAT de GitHub escritos en claro; ambos literales se retiraron antes
de incorporarla al repositorio.

**Impacto:** cualquier principal con acceso a Cloud Logging puede recuperar el
token mientras los registros existan. Las credenciales incluidas en el fichero
recuperado deben considerarse expuestas aunque ya no aparezcan en la copia
local. El volumen y el nivel de log dificultan ademas detectar errores reales.

**Accion:** retirar inmediatamente ese log, redactar todas las cabeceras
sensibles, rotar `tradier-token`, revocar o rotar el PAT de GitHub y
revisar/eliminar los registros afectados segun la politica de conservacion. En
el mismo fichero hay un literal con aspecto de credencial antigua en un
comentario (`main.py:22`); debe eliminarse y rotarse si alguna vez fue valido.

### AUD-02 - Alto - Informes completos accesibles sin autenticacion

**Evidencia:** `scripts/deploy_reports_reader.cmd:11-22` despliega `reports` con
`--allow-unauthenticated`, `--ingress all` y CORS `*`.
`gcp_functions/reports_reader/main.py:61-66` devuelve el objeto completo cuando
se usa `debug=true`. Ese objeto incorpora acciones de analistas, titulares IBKR y
el snapshot slim en `src/local_runner/run_one.py:1718-1723`.

**Impacto:** un tercero que conozca o enumere un ticker puede consultar mas datos
que los necesarios para la hoja. La exposicion tambien aumenta el coste y la
superficie para abuso.

**Accion:** autenticar el endpoint o restringir el ingreso, eliminar `debug` de
produccion o protegerlo con autorizacion separada, limitar CORS y devolver solo
el contrato minimo consumido por Apps Script.

### AUD-03 - Alto - Servicios desplegados sin fuente activa reproducible

**Evidencia:** `support-resistances-slim` y `support-resistances-raw` estan
desplegados, pero su fuente vigente no existe en el arbol activo. Para slim hay
una copia historica y el 2026-09-04 se recupero una fuente completa de raw bajo
`incoming_from_gcp/support-resistances-raw/`. Esa copia fue saneada para retirar
credenciales literales, pero todavia no se ha contrastado con la revision o la
imagen desplegada y sus dependencias se han inferido. `support-resistance-values`
si tiene fuente activa, pero no un script de despliegue equivalente al de
`reports`.

**Impacto:** no se puede reconstruir con certeza el entorno productivo, revisar
un cambio desplegado ni recuperar el servicio de forma determinista.

**Accion:** recuperar la fuente exacta de cada revision desplegada, incorporarla
al arbol activo, fijar dependencias y crear scripts o CI de despliegue que
registren revision, imagen y commit.

### AUD-04 - Alto - Perimetro Cloud Run demasiado amplio

**Evidencia desplegada:** los seis servicios relacionados (`reports`,
`support-resistance-values`, `support-resistances-slim`,
`support-resistances-raw`, `gemini-stock-analyze` y `stock-analyze-batch`) aceptan
trafico externo sin autenticacion efectiva. Todos usan la cuenta de servicio de
Compute por defecto. `support-resistance-values` si obtiene `TRADIER_TOKEN` desde
Secret Manager; los valores no se inspeccionaron.

**Impacto:** endpoints costosos o heredados pueden invocarse desde Internet y
heredan mas permisos de los necesarios si la cuenta por defecto es amplia.

**Accion:** retirar o pausar servicios heredados, exigir autenticacion donde sea
posible, aplicar cuotas y crear una cuenta de servicio dedicada y minima por
funcion.

### AUD-05 - Medio - Llamadas HTTP sin timeout

**Evidencia:** varias llamadas Tradier no tienen `timeout`, entre ellas
`gcp_functions/support_resistance_values/main.py:602`, `:905`, `:1016`, `:1056`,
`:1285` y `:1346`.

**Impacto:** una conexion bloqueada puede ocupar una instancia hasta el timeout
de Cloud Run. El servicio esta limitado a una instancia, por lo que una llamada
atascada puede frenar todos los refrescos de Apps Script.

**Accion:** usar una sesion comun con timeouts de conexion y lectura, reintentos
acotados con backoff y respuestas parciales explicitas.

### AUD-06 - Medio - Controles insuficientes en el bucket

**Evidencia desplegada:** `stock-analysis-reports-naxo85` no tiene enlaces IAM
publicos, pero usa ACL/IAM mixtos porque Uniform Bucket-Level Access esta
desactivado. Public Access Prevention figura como heredado. No se observaron
versionado, retencion ni ciclo de vida.

**Impacto:** una ACL accidental puede abrir objetos, y una sobrescritura o
borrado no tiene recuperacion nativa. Los snapshots creceran sin una politica
central de conservacion.

**Accion:** comprobar ACL existentes, habilitar acceso uniforme y Public Access
Prevention, activar versionado o soft delete segun coste, y definir ciclo de vida
para snapshots, comandos y artefactos de bootstrap.

### AUD-07 - Medio - Publicacion de `latest.*` no atomica

**Evidencia:** `src/local_runner/gcs_uploader.py:94-165` sobrescribe, en secuencia,
`latest.md`, `latest.html` y `latest.json`, y despues crea los snapshots.

**Impacto:** un fallo intermedio puede dejar formatos de revisiones distintas o
un informe vigente sin snapshot completo.

**Accion:** subir primero todos los objetos versionados y publicar al final un
manifiesto/puntero unico a la version confirmada. El lector debe resolver ese
puntero.

### AUD-08 - Medio - Un unico PC es parte del plano de ejecucion

**Evidencia desplegada:** la tarea `Stock Analysis Command Worker` esta habilitada,
se ejecuta cada minuto y termino correctamente en la comprobacion. Su modo de
inicio de sesion es `Solo interactivo`.

**Impacto:** si el equipo esta apagado, la sesion esta cerrada o el usuario no
esta disponible, la cola se detiene. Cloud Scheduler no ofrece respaldo: su API
esta deshabilitada en el proyecto.

**Accion:** definir SLO y alertas de antiguedad de cola, comprobar el estado del
worker desde la hoja y decidir si se acepta este punto unico o se migra el worker
a un ejecutor siempre disponible compatible con IBKR y Codex.

### AUD-09 - Medio - No hay bloqueo global de analisis

**Evidencia:** `src/local_runner/command_worker.py:131-137` protege solo al propio
worker con `command_worker.lock`. Los lanzadores manuales y lotes pueden iniciar
otra ejecucion en paralelo.

**Impacto:** dos procesos pueden competir por IBKR, cuotas de Codex y objetos
`latest.*`, o publicar resultados fuera de orden.

**Accion:** introducir un coordinador compartido por ticker y por recurso global,
con propietario, TTL, renovacion y recuperacion tras caidas.

### AUD-10 - Medio - Regresion en el fallback de resultados

**Evidencia:** `apps_script/fuerza.gs:751-764` devuelve cadena vacia para un ticker
no encontrado en Nasdaq, aunque el contrato usa `NEXT_EARN_UNKNOWN = '?'`. La
asercion de `tests/test_next_earn_fallback.js:134` falla.

**Impacto:** una celda puede parecer vacia en lugar de distinguir un resultado
desconocido, y el comportamiento difiere entre fallbacks.

**Accion:** devolver la constante contractual y ejecutar esta prueba en CI con
una version de Node compatible.

### AUD-11 - Bajo - Documentacion y ruta real divergen

**Evidencia:** el flujo normal marca los eventos IBKR preagregados como
`not_used` en `src/local_runner/run_one.py:1787-1791`, mientras que partes de
`docs/operations.md` describen la agregacion como entrada ordinaria del prompt.
`docs/desktop_launchers.md` aun presenta el worker como trabajo futuro.

**Accion:** actualizar esos documentos despues de decidir si la agregacion vuelve
a ser parte del flujo diario o permanece opcional. Mantener documentos
historicos claramente etiquetados como tales.

### AUD-12 - Bajo - Mantenibilidad y cobertura

- Las dependencias de `support-resistance-values` no estan fijadas por version.
- Hay dos funciones globales `clearLegacyYpricePropertiesNow` en Apps Script.
- Queda codigo Alpha Vantage inactivo que referencia una variable no definida.
- No hay pruebas del lector `reports`, del endpoint tecnico completo, de la
  agregacion de noticias IBKR ni una prueba de integracion de extremo a extremo.
- No existe una comprobacion automatica de paridad entre codigo local y revisiones
  desplegadas.

## Estado desplegado comprobado

Comprobacion realizada el 2026-09-04 en `europe-southwest1`:

| Componente | Estado observado | Nota |
| --- | --- | --- |
| Apps Script | 1 despliegue `@HEAD` | La paridad de contenidos no fue comparada |
| Worker Windows | Habilitado, cada minuto, ultimo resultado 0 | Requiere sesion interactiva |
| Cloud Scheduler | API deshabilitada | No hay orquestacion por este servicio |
| Secret Manager | `stock-analysis-ibkr-paper-credentials`, `tradier-token` | Solo se listaron nombres |
| GCS | Sin IAM publico; acceso uniforme desactivado | Sin versionado/retencion/lifecycle observados |
| Cloud Run | 6 servicios relacionados desplegados | Publicos y con cuenta de servicio por defecto |

## Verificacion ejecutada

- `pytest -q`: **119 pruebas superadas**, 3 subtests superados y 1 aviso porque
  Windows impidio escribir `.pytest_cache`.
- Parseo AST: **42 ficheros Python validos**.
- `node tests/test_update_targets_and_notes.js`: superado.
- `node tests/test_next_earn_fallback.js`: fallo reproducido en el contrato `?`.
- `git diff --check`: sin errores de whitespace; solo avisos de finales de linea.
- No se pudo usar `node --test` ni `node --check` sobre `.gs` porque el entorno
  tiene Node `v14.16.1`.

## Plan recomendado

### Inmediato

1. Retirar el log de cabeceras, rotar Tradier y revisar Cloud Logging.
2. Cerrar o reducir `reports?debug=true` y retirar endpoints heredados publicos.
3. Corregir el fallback de `NEXT_EARN` y dejar las pruebas JavaScript en verde.

### Corto plazo

1. Recuperar y versionar la fuente exacta de slim/raw y automatizar despliegues.
2. Crear cuentas de servicio minimas y endurecer Cloud Run y GCS.
3. Añadir timeouts/reintentos y una politica de logs estructurados sin datos
   sensibles.
4. Publicar informes mediante versiones inmutables y un manifiesto atomico.

### Siguiente iteracion

1. Diseñar bloqueo global y deteccion de ejecuciones obsoletas.
2. Añadir observabilidad de cola, coste, latencia, fallos y frescura por ticker.
3. Incorporar pruebas de contrato e integracion para Apps Script, Cloud Run y
   GCS, mas una verificacion de deriva entre repositorio y despliegues.
