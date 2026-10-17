# Origenes de opciones fuera del ranking: revision39

## Incidencia original

Orden20261016-155445-849-market-cfa04d68, lote2026-10-16/15-58-24.
45/46 publicados:18conservados,26actualizados,1full; APP bloqueado y1reintento
de lote. APP no tuvo fallo de puntuacion/prosa: decision blocked, evidence_gap
essential_data, todos los flags de riesgo false. Entrada CURRENT249.5-250.5
dependia de puts250; snapshot16-oct solo exportaba TOP272.5,270,275,265,280.
El recibo medium termino correctamente; el reintento reutilizo el contrato y no
aporto el dato ausente. No se ha recuperado/publicado APP en esta intervencion.

El ranking no es un seguimiento de identidades: salir del TOP no demuestra ni
desaparicion, ni perdida, ni supervivencia de las opciones de una zona vigente.
La adquisicion dirigida existente solo cubria anclas AVWAP, no strikes.

## Cambio de adquisicion39

El runner deriva identidades tipo/strike exclusivamente de los registros tipados
citados por CURRENT Entry/Washout activos y sus fuentes de extension inferior.
Incluye conservadoramente comparaciones de opciones citadas dentro de esos
bloques; deduplica. No recorre el ancla Sol obsoleta, campos retirados, narrativa
ni el universo completo. Un rango o numero en prosa no inventa un strike.

option_origins=put:250,... viaja runner->slim->raw. Raw lee las respuestas XML
de las mismas cadenas y vencimientos ya usados por el TOP. La cache es local
a una peticion; la identidad de URL/params coincide. No mas descargas por ese
seguimiento ni cache entre capturas. No nuevos vencimientos ni lista TOP mayor.
Se conserva una observacion completa por identidad incluso si no aparece en TOP.

- available: se observo contrato en el muestreo; no acredita soporte vigente.
- not_observed: no se observo en esas cadenas; no afirma ausencia global.
- OI cero es lectura numerica, no contrato ausente ni error de descarga.
- OI/greeks desconocidos conservan ausencia de metrica. No se descarta el contrato
  simplemente porque el parser del ranking no podia utilizar su gamma.
- Identidad incompleta en una cadena queda unavailable explicito; error HTTP,
  timeout o XML fallido aborta la captura antes de mirror/admitir el modelo.
- OI dirigido suma contratos observados, no solo elegibles por gamma como TOP.
  aggregate_oi_basis explicita la diferencia: no comparar bases distintas como
  cambio de respaldo. Cero/gamma desconocida no demuestran liquidez ejecutable.
- Sin expiraciones futuras exitosamente observadas, la ausencia queda explicita
  y acotada. Fuente ausente/incompleta no se convierte en resultado financiero.

Antes de congelar39, el runner verifica cobertura exacta de identidades, estado,
detalle por vencimiento y correspondencia. No puntua ni decide operaciones.
La observacion actual llega al catalogo normal s; codigo copia la fuente exacta.
Origen positivo requiere put observado con OI/gamma positivo en vencimiento no
pasado. Observaciones negativas siguen siendo hechos validos para evaluar perdida
o falta de respaldo, pero no pueden crear una nueva compra como origen positivo.
Rubrica, continuidad, riesgo, autoridad, ITV5, modelos y concurrencia intactos.

Nuevo footer option_origins_v39 para full/medium y repair. Mas observabilidad
no equivale a noticia o prior_error; no automaticamente conservar, repuntuar,
rellenar ni escalar. No nuevas llamadas de modelo ni paid repair por metadata.
Congelados<=38 y el APP fallido original permanecen exactos, no se les cambia
el input bajo un recibo admitido. La correccion actua en nuevas preparaciones.

## Publicacion y verificacion

Imagenes de base verificadas: raw0de9f8... y slimd63ba7..., ambasoptions31.
AST limita cambios a2funciones nuevas+handler raw,1helper nuevo+handler/fetch/build
slim; restantes funciones/imports/configuracion son exactos al fuente desplegado.
El build contiene main.py, Dockerfile y verificador offline sin credenciales.
No se despliega el arbol sucio ni se exporta codigo de imagen a otro destino.

Prueba de arranque de revision exacta por tag temporal sin asignarle porcentaje,
con peticion SIN symbol: respuesta de aplicacion400 conocida, sin Tradier/mirror.
Luego Ready y ContainerReady/ContainerHealthy, runtime intacto y activacion
explicita. Tags previos se conservan; tag temporal se retira. Procedimiento de
[revision etiquetada sin trafico](https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration).
Los servicios en reposo pueden presentar Active=false/ResourcesAvailable=Unknown;
no se inventa una condicion ContainerHealthy si el esquema expone ContainerReady.
La respuesta HTTP de la revision exacta tambien es obligatoria antes de activar.

Pruebas: ranking/precios/fechas/rutas originales exactos sin query dirigida,
mismo numero de requests en captura completa, consulta fuera del TOP sin request
extra, aislacion entre capturas, ceros/desconocidos/ausencias, errores del proveedor,
propagacion runner/slim/raw, catalogo y hechos exactos, no origen positivo por
ausencia/call/expirado/OI cero, preparacion/freeze original38 y contrato39.
Un comparador legado23 no excluia los campos agregados intencionalmente en28/31;
se actualiza solo su normalizacion historica, conservando igualdad de TODOS los
campos financieros anteriores y pruebas separadas de esos nuevos campos.

Evidencia de builds, revisiones, probes y captura tecnica en logs/deploy_origins39/.
La captura tecnica puede actualizar el mirror normal de JSON tecnico; NO es un
analisis, una publicacion financiera ni una recuperacion del lote. No hay modelo
vivo de39 en esta intervencion; observar el siguiente run natural.

## Resultado desplegado

Raw build3cd9dfbc-f64d-4711-8cbb-3629208f3e7c SUCCESS, imagen
sha256:1597fea0082905ea0b9350c82c72f7a085544469dc1ec94ccd843a10eb89255d.
Slim buildd2caa950-2fcf-4cff-9b64-7e2d3187af18 SUCCESS, imagen
sha256:093854720d2f765dc92e6e507153ff74d64fc66fe96faf13bf1458f7179857bc.
Revisiones support-resistances-{raw,slim}-origins39-20261016 activas100%; runtime
y tags anteriores exactos. Tag temporal originstest39 retirado tras verificar.
El controller solid65 no se ha desplegado/modificado.

Captura real APP2026-10-16T21:07:48.188625+00:00 verifica requested put250/255,
ambos available, vencimientos16/23/30oct. TOP265,262.5,270,260,250: en esta
captura250 volvio al TOP,255 no. La observacion255 prueba el camino real fuera
del TOP; las fixtures originales cubren especificamente250 ausente del TOP.
Captura y resumen en live-source.json/live-source-verification.json. No se
concluye liquidez/viabilidad de la Entrada; lo decidira el siguiente modelo
natural con los datos completos. Inputs/recibos originales APP exactos.
Config cambia SOLO routing_revision38->39; mismos modelos/esfuerzos/ITV/capacidad.

Regresion final ejecutada:106passed,1deselected,5subtestspassed,66.94s.
Incluye29tests nuevos39, captura23, slim, evidencia31, seleccion38 y scope35.
Se excluyo explicitamente test_all_original_report_inputs_and_outputs_remain_untouched
de31 (replay masivo historico), no se afirma haberlo ejecutado. Casos focales
si comprueban input/recibo APP38 intactos y compatibilidad de peticiones antiguas.
load_policy carga39 y verifica modelos/esfuerzos/ITV5/concurrencia6 exactos.
git diff --check termina0, solo avisos preexistentes LF/CRLF del arbol sucio.
