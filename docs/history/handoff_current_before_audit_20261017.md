> Archivo histórico preservado el 17-10-2026. Sus referencias a «actual», «vigente» o «siguiente» corresponden a la fecha de cada entrada. No es una guía de ejecución vigente. Consulte [arquitectura actual](../architecture.md), [relevo](../handoff_current.md) y [backlog](../pending_work_current.md). Se ajustaron únicamente rutas relativas de enlaces al archivar.

# Relevo operativo actual

## Revision39: observar opciones de las zonas vigentes fuera del TOP (16-10)

ACTIVA para nuevas preparaciones; congelados<=38 exactos. Incidencia original
orden20261016-155445-849-market-cfa04d68, batch2026-10-16/15-58-24:
45/46 publicados (18conservados,26actualizados,1full IBKR), APP bloqueado y
1reintento de lote. CURRENT Entry249.5-250.5 dependia de puts250; snapshot
16:14:23 no los exportaba en TOP. Recibo medium correcto, bloqueo por dato
esencial no disponible, no error de prosa/rubrica. Reintentar el mismo input no
podia descubrir el strike. No se ha recuperado ni republicado APP.

Runner39 deriva tipo/strike de fuentes tipadas de Entry/Washout CURRENT activos,
incluidas comparaciones citadas; nunca del precio/rango/prosa/ancla vieja.
Slim/raw devuelven observaciones dirigidas aun fuera del TOP, leyendo las mismas
cadenas Tradier/vencimientos ya descargados en esa peticion. TOP/precios/ranking
sin cambios, sin descargas extra para la consulta dirigida ni llamadas de modelo.
available no significa compra vigente; not_observed solo en el muestreo; cero,
desconocido y descarga fallida no se confunden. OI dirigido incluye todos los
contratos observados, no solo gamma-elegibles como TOP; base explicita. Cobertura
antes de congelar/admitir modelo. Fuentes/binding, riesgo, rubrica y autoridad
intactos; positivo solo put observado no expirado con OI/gamma positivo. Sin
conservar, repuntuar, escalar ni rellenar automaticamente.

Raw support-resistances-raw-origins39-20261016 y slim
support-resistances-slim-origins39-20261016 activos100%, runtime y tags anteriores
conservados. Parche minimo sobre imagenes options31, AST de resto exacto;
verificador offline dentro de cada imagen. Builds raw
3cd9dfbc-f64d-4711-8cbb-3629208f3e7c y slim
d2caa950-2fcf-4cff-9b64-7e2d3187af18 SUCCESS. Probes por tag exacto sin symbol
a0% antes de activar; tag temporal retirado. Controller solid65 NO tocado.

Captura tecnica real APP21:07:48UTC: puts250 y255 disponibles en16/23/30oct;
TOP265,262.5,270,260,250. El255 queda fuera del TOP y llega completo. No implica
vigencia financiera ni corrige el reporte viejo. Solo mirror tecnico normal,
sin modelo/lote/recovery/publicacion financiera. Evidencia y detalles en
logs/deploy_origins39/ y docs/audit_option_origins_20261016.md.
Config39 mantiene Sol6.1 medium/high, ITV5, concurrencia6, financiero v12 y
support_validity37. Regresion final106tests+5subtests correctos (1replay historico
masivo deselectado), incluidos29controles nuevos. Politica39 cargada/verificada;
git diff --check sin errores. Observar siguiente natural39; no duplicar lote ni cambiar
recibo38 bajo APP fallido.

## Visibilidad de soportes >=65 publicada (15-10)

Autorización explícita del usuario. Se rebasó el parche mínimo sobre la imagen
activa support-validity36 sha256:c4b112f80abe117ca4078cb96bde258fe9dbe2ec1884d535173055de3ce1ea14;
build d105761c-38fe-4269-88be-591dd9ec7594 SUCCESS,3 pruebas dentro de
imagen. Imagen resultante sha256:51e7a0b8861f147da210ec61e97dda0a35b291b639bbb6e256c74fc8cb7742cf.
Revisión stock-controller-solid65-20261015 probada a0% con Ready,
ContainerHealthy y /health autenticado; después activa100%, runtime/tags previos
exactos. Entrada/Washout visibles desde nota numérica65; categoría sólido sigue
desde70, bordes85/95 y colores/extensiones36 intactos. Versión presentación14.
POST /analysis/refresh devolvió analysis_reports_unchanged porque la proyección
ya estaba sincronizada. Lectura directa de Mercado: ASML Washout T9 muestra
1576,0-1584,0, nota68/100 (moderado); Entrada S9 vacía. Sin modelo, lote,
repuntuación ni republicación de informes. Evidencia
.tmp/solid65-deploy-20261015/evidence/ y script .tmp/deploy_solid65_20261015.py.
Un primer build f404fa1c falló antes de publicar por asumir versión11 de
presentación; el build final detectó la versión activa13 y la subió a14.

## Revision38: origen, vigencia y fortaleza sin descarte por baja conviccion (15-10)

Auditoria de9 tickers sin ambas zonas del full36:7 minimos nuevos del14 sin
defensas historicas completadas; IREN28.93 y MP37.81 si tenian una defensa
historica del29-jul. No se concluye que esos dos deban comprarse ni se rellenan
las casillas: se corrige la confusion entre poca confluencia y ausencia de origen.
Ver docs/audit_support_selection_20261015.md, tabla9casos y causas originales.

Financiero v12 sustituye las frases que rechazaban entradas aceptables y exigian
conjuntamente todas las familias. Misma politica para full/medium/repair38:
una defensa antigua, poca confluencia o ausencia de rebote reciente no son veto
automatico a un origen inferior verificable; rubrica y riesgo puntuan las carencias.
Evaluar candidatos antes de casillas: uno inferior apto puede ser Entrada; Washout
es otro bloque distinto y puede faltar. Sin cuota, minima nota, relajacion de
fuentes, ventanas nuevas, regla de ruptura o rescate de soporte perdido.
Sobre cotizacion sigue haciendo falta un juicio positivo de vigencia actual.
Opciones de vencimiento inmediato no ganan excepcion a su respaldo independiente.

Reader38: Sin zona de compra seleccionada + motivo concreto. No clasifica prosa,
no agrega enum/guardas/paid repair/full ni corrige motivos protegidos por estilo.
Migracion retain de encabezado mantiene numeros, finanzas, notas/fechas/ancla/ITV.
Congelados<=37 conservan instrucciones/schemas/render original; extension37 intacta.
Config38 ACTIVA para nuevas preparaciones. Mismos Sol6.1 medium/high, ITV5,
concurrencia6 y schema.76 regresiones +16 casos nuevos verificados,12subtests;
23 focalizados repetidos correctos tras cerrar la implementacion.3 controles
adicionales de migracion/ancla correctos.46 informes/66zonas exactos; parser del
consumidor conserva datos de Sheet y limites. No nuevo smoke vivo: observar
juicio del modelo en el siguiente natural, no predecir menos vacios.
En la primera bateria3 fixtures usaban ancla anterior al full nuevo; corregidos
para usar su epoca autentica. Ancla vieja sigue rechazada, no guarda relajada.
No modelo/lote/recovery/publicacion/cloud ni informes editados en esta tarea.

## Revision37: estimacion prospectiva del limite inferior (14-10)

Corrige la instruccion que mezclaba estimar con confirmar una defensa observada.
support_validity_v37 sustituye al36 SOLO en nuevas preparaciones full y medium;
congelados<=36 exactos. Misma llamada/contrato de datos/consumidor36. Fuentes
actuales fundamentan una estimacion, no necesitan contener su numero literal.
Sin rebote actual/test exacto obligatorio; sin formula de porcentaje/ATR/cierres.
Mantener coherencia con penetraciones que se juzgan viables, nunca bajar el
limite por cotizacion ni rescatar un soporte perdido. Null requiere carencia
estructural esencial concreta; null item hereda limites conocidos sin cambios.
Evaluar vacios tambien en retain, preservando19 conocidos salvo evidencia nueva.
No nueva guarda, repair/full pagado, investigacion extra, cambio de rango/notas,
fecha financiera, ancla ni ITV por completar este dato. Config37 ACTIVA para
nuevas preparaciones; modelos/esfuerzos, ITV5 y concurrencia6 intactos.
72 pruebas y12subtests pasan;5 casos adicionales de preparacion/herencia pasan
tras ampliar freeze hasta37. Incluye46 publicaciones originales,66zonas y
los19 limites heredados exactos, misma autoridad y pipeline retain con1llamada
simulada. No nuevo smoke vivo: comprobar el juicio en el siguiente natural37.
No modelos/lote/recovery/publicacion ni cambios cloud en esta intervencion.
Los47 vacios originales NO completados con precios manuales; fixtures sinteticas
solo comprueban contrato/preservacion, no validan el juicio financiero del modelo.

## Full36 solicitado por usuario TERMINADO (14-10,16:53UTC)

Orden20261014-160514-market-full36-c7070c8c; launcher oculto57284 (lock del
proceso Python50292) mediante scripts/launch_full_market_command.py y lock
normal, sin cola/progreso activo previo. Scope GCS tickers_market.json46,
--analysis-mode reference, max-parallel6, noticias/analistas y upload-real.
Renovacion expresa full Sol6.1 high para TODOS, no46escaladas; siguientes
lotes normales nuevos usan Sol6.1 medium/high adaptativo37. Incluye criterio de
extension inferior estimada para colores, sin inventar limites no defendibles.
Batch logs/batch/2026-10-14/16-07-07 terminado46/46,0fallidos/reintentos.
Resultado launcher status=ok, exit0, fin16:53:49UTC, duracion2911.499s.
46full por peticion expresa, no escaladas.66zonas activas:19extensiones
conocidas y47lower_bound=null explicitamente razonados;26zonas ausentes.
No rechazos del parser de extensiones. En varios null el modelo exigio defensa
observada/precision confirmada para lo que debia ser una estimacion prospectiva.
Informes/publicaciones originales intactos; sync projection19limites/46tickers.
No duplicar ni reanudar. Logs logs/full_market_launch/20261014-160514-market-full36-c7070c8c/.

## Revision36: extension inferior estimada y colores de compra (14-10)

ACTIVA para nuevas preparaciones, por acuerdo del usuario. Verde fosforito
dentro del rango y por debajo SOLO hasta una extension inferior defendible
aportada por el modelo; fuera, fondo normal. Retirados verde claro y rojo suave
de Entrada/Washout y la antigua regla universal del1,5%. Mantener viabilidad
compradora antes de estimar extension: no rescatar soportes perdidos, no stop,
target, nueva guarda Sol ni garantia de demanda. No regla porcentual/ATR/cierres.

support_validity_review es comun full/mantenimiento/retain36. Code copia fuentes
CURRENT exactas, vincula el rango y fecha prepared_at. Null hereda SOLO rango
exacto activo; null lower_bound retira la extension. Dato imposible, fuente
desconocida/historica/no disponible o rango sustituido retira el verde inferior;
nunca failure/repair/escalada por metadatos visuales. Fecha financiera, notas,
ancla y ITV no se modifican por actualizar este dato en retain. Una linea discreta
fechada en el informe y nota de celda; auditoria interna conserva razon/fuentes.
Prompt financiero v11 + overlay prompts/support_validity_v36.md; congelados<=35
conservan schemas/prompts/recibos exactos. Mismos Sol6.1 medium/high, ITV5 y6calls.

Controlador stock-controller-support-validity36-20261014 al100%, Ready y
ContainerHealthy; /health privado autenticado OK antes de activacion. Build
102052ff-8de3-4eae-b340-0dcf56c5271d SUCCESS;42 pruebas dentro de imagen.
Parche funcional de5 modulos sobre imagen activa inmutable35, no despliegue
del arbol sucio. Runtime, secretos, service account y tags existentes exactos.
Layout GCS: solo format_rules.entry_proximity, generation guard/readback exacto.
Sync guarda proyeccion pequena de extensiones; refresco de cotizaciones lee1
objeto GCS acotado, liga por ticker/rango mostrado y usa su rango exacto aunque
la hoja muestre1decimal. Lectura fallida/cotizacion no valida no extiende verde.

67 pruebas locales +12subtests y1 caso adicional de fuente no disponible pasan;
incluye46 bases retenidas sin editar cifras, fechas ni archivos congelados,
full original, pipeline retain con1 llamada simulada y formato MD/HTML/JSON.
Los tests historicos de pipeline congelan ahora su reloj, no relajan frescura real.
No modelos, lote, recovery ni republicacion de informes en esta intervencion.
Los informes existentes NO tienen limites: ahora solo verde dentro del rango;
el siguiente natural36 podra aportar extensiones tambien durante retain.

POST /analysis/refresh published46, missing[], sin reordenar. Lectura Sheet:
46tickers,92celdas de compra con fondo normal, cero cambios de valores/notas/
textFormatRuns/validaciones en los5campos de analisis;0zonas visibles dentro
del precio de esa lectura, coherente con0fosforitos. API visual/formatos, sin
nuevo analisis para inventar limites. Evidencia logs/support_validity36/.

El árbol local conserva el intento solid65 anterior en
.tmp/solid65-deploy-20261014. No usar su Dockerfile basado en35: el parche
autorizado del15-10 se construyó sobre la imagen36 activa y preserva esta lógica.

La revision automatica rechazo un job de extraccion/exportacion de codigo de
imagen a artefacto remoto. No se ejecuto; su config se retiro. Despliegue final
usa parche dentro de imagen privada sin esa extraccion/exportacion.

## Visibilidad de soportes desde 65: preparación local del14-10, publicada el15-10

Por aclaración del usuario, el cambio es solo de visibilidad: Entrada/Washout
con nota numérica >=65 aparecen en Mercado aunque sigan siendo moderados.
La categoría sólido conserva 70; puntuaciones, componentes, pilares, colores
y bordes 85/95 permanecen igual. El filtro visible local de Sheet es 65 y la
versión de presentación es 12 para aplicar la proyección sin recalcular ni
republicar informes. Pruebas focalizadas pasan.
La revisión automática rechazó entonces la subida a Cloud Build por falta de
autorización explícita. El usuario la otorgó el15-10; el despliegue final y
la verificación de ASML se detallan al inicio de este relevo.

## Etiquetas A9/C4 por funcion, no por modelo historico (13-10)

Retirados nombres Luna/Sol fijos de las notas adaptativas: Revision con
conservados/actualizados e Informes completos. No cambios en modelos, conteos,
fechas, heartbeat, fallos ni ruta financiera. Web legacy conserva proveedores.
Apps Script publicado con diff de un unico archivo analysis_completion_sync.js;
relectura remota exacta al local, otros14 archivos iguales. Evidencia en
.tmp_apps_script_push/20261013-224637/{original,work}. Pruebas JS de progreso,
resumen final y menu pasan. A9 nota actual corregida mediante mascara note;
valor/formato exactos, C4 vacio sin tocar. Lectura verificada despues.
El resumen de A9 correspondia al full35 final46/46,0fallidos,44min,
fin13-10 22:15 Europe/Madrid; Luna era etiqueta obsoleta, no uso real de ese modelo.

## Full35 solicitado por usuario EN CURSO (13-10,19:30UTC)

Orden20261013-192826-market-full35, lanzamiento oculto PID38080 mediante
scripts/launch_full_market_command.py bajo lock normal y cola/progreso previo
comprobados. Scope tickers_market.json vigente46, --analysis-mode reference,
max-parallel6, actualizacion de noticias/analistas y upload-real. Sol6.1 high
para TODOS por renovacion expresa, no escaladas ni mantenimiento. Revision35:
solo Entrada/Washout, rubric34 y formato editorial33; modelo/politica normales
de siguientes lotes automaticos no alterados. No duplicar ni reanudar este run.
Lote logs/batch/2026-10-13/19-30-44. Heartbeat local/remoto19:31:25UTC running,
46totales,1preparado, CRWV analizando/MU preparando,0fallos/reintentos.
Arranque confirmado, no resultado final. Launcher/result en
logs/full_market_launch/20261013-192826-market-full35/ y stdout/stderr hermanos.

## Revision35: solo Entrada y Washout (13-10)

ACTIVA para nuevas preparaciones por peticion del usuario. Elimina seleccion,
calculo y mantenimiento de resistencia de AMBOS roles, schemas y prompts v11/35;
catalogo y contexto financiero ya no presentan la resistencia archivada como tarea.
No elimina observaciones tecnicas de oferta utiles para juzgar soportes/riesgo.
Conserva metodologia34, fortalezas/viabilidad compradora, fuentes/binding, riesgo,
una reparacion, ITV5, modelos medium/high y concurrencia6. Congelados<=34 exactos.
Retain migra por codigo dos zonas, con fechas/precios/notas/fortalezas/ancla exactos
y rebind de memoria; no paga full ni reinicia ITV por este cambio de alcance.
Informes ya publicados NO republicados: desaparicion al proximo flujo natural,
incluidos retenidos. No interpretar esto como nuevo analisis vivo.

Sheet Mercado: U/AJ vacias (46 celdas, valores y notas) y ocultas, sin desplazar
indices/formulas/tablas. Comparacion inmediata: vecinos y46enlaces exactos.
Relectura tras refresco:46vacias y46enlaces; ASTS conserva mismo destino pero su
formato/link fue normalizado por escritor externo (slash antes de query), no por
las cuatro peticiones acotadas que quitaron Res. Ningun cambio en precios/notas.
Runtime GCS table_template.show_resistance=false, unico campo cambiado con
ifGenerationMatch; copia previa y lectura posterior en logs/resistance35/.
Controlador no escribe resistencia/bordes/proximidad y layout respeta columnas
ocultas; parser acepta plan35 sin resistencia, conserva controles de soportes.
Sync presentation11 incluye flag en version. Enlaces de Tesis previos conservados.

Build96dbb31d-fafe-4871-b343-9712876b6706 SUCCESS;54 tests dentro de imagen.
Derivado de imagen activa843b642..., parche exacto solo cuatro modulos; no despliegue
del arbol sucio completo. Revision stock-controller-support-only-20261013,
digest570316a1f4c4442e705b047a2921d33bd535c78aa95d7b87efe3524b03e7b4fd,
Ready/ContainerHealthy y /health autenticado OK a0%, luego trafico100%.
Runtime/IAM/cuenta/secretos intactos; tag temporal retirado, strengthtest intacto.
/analysis/refresh devuelve skipped analysis_reports_unchanged tras sync natural.
89 tests locales pasan (409.61s), incluyendo full/mantenimiento35 reales adaptados
offline,46bases retenidas exactas, freeze34, fuentes/riesgo y herencia Volumen.
Sin modelos, lote, recovery ni publicaciones de informes. Observar siguiente
natural35; no inventar ahorro medido de tokens ni garantizar calidad viva por tests.

## Revision34: perfil de volumen sin segundo castigo a la historia (13-10)

ACTIVA SOLO para nuevas preparaciones. v10 financiero; congelados<=33 exactos.
Distancia POC/HVN solo puntua proximidad, no limita de nuevo toda la reaccion.
Siguen perfil diario max3, muestra/tasa, magnitud, ultimo rebote, recencia y direccion.
Pesos25+20+25+15+15, Opciones25 y cortes70/85/95/pilares intactos. Sin cuota de zonas.
Full/mantenimiento/repair comparten regla34. rubric_change en mantenimiento SOLO
para Volumen, rango y otros componentes exactos, decision previa y fuentes actuales
completas citadas; delta exacto entre formulas<=33 y34. Ya migrado no repite permiso.
No es noticia ni prior_error. Herencia null sigue fechada; vigencia compradora primero.
No cambios automaticos a notas, rangos, narrativa, ITV o ancla; una reparacion normal.
23 pruebas nuevas+83 regresiones correctas;48 recibos originales y54 cuentas exactas.
Sensibilidad sobre mismas capturas:5/54 cambian,49 iguales; no nuevos informes.
Ver docs/audit_volume_rubric_20261013.md. Config34 activa, mismos Sol6.1 medium/high,
ITV5, concurrencia6. Sin modelos/lote/recovery/publicacion/cloud. Observar proximo
natural34; no prometer mas soportes visibles ni cambiar Opciones por intuicion.

## Enlaces de Tesis restaurados (13-10)

El usuario detecto que las puntuaciones de Tesis ya no abrian el informe.
Lectura real: 46/46 celdas contenian puntuacion/nota pero ningun enlace
en textFormatRuns ni formato de celda. Restauracion acotada por ticker:
solo link, subrayado, color de texto y hyperlinkDisplayType; valores, notas
y fondos exactos verificados antes/despues. No modelos ni informes nuevos.

Correccion en analysis_sheet: enlace de celda completa ademas de rich text,
con mascara explicita de los campos del vinculo; evita depender de runs que
se borran al escribir userEnteredValue. Global sort ya conserva formato completo.
run_sync presentation_version 9->10 para aplicar proyeccion sin nuevo informe.
30 pruebas focalizadas pasan; 3 tambien dentro de la imagen desplegada.

Build37338aa4-3cbf-46c6-a19e-3d3e42a3e701 basado en imagen activa inmutable
71d7fbe..., solo parche de dos modulos; sin desplegar otros cambios locales.
Revision stock-controller-report-links-20261013 Ready/Active/ContainerHealthy,
GET /health autenticado200, trafico100% y runtime/secretos/cuenta preservados.
La revision automatica rechazo activar sin arranque y tambien el tag inicialmente;
comprobacion IAM privada y documentacion oficial permitieron prueba tag0%,
health y activacion tras Ready/Healthy. Tag temporal retirado; strengthtest previo intacto.
/analysis/refresh200 skipped por reports unchanged despues de sincronizacion natural.
Relectura final46enlaces HTML exactos y puntuaciones/notas/fondos iguales.
Evidencia logs/report_link_audit/{before,after,verification,revision-active,service-after}.json
y build.log, health-staged.json, sync-result.json. No lote, modelos, recovery,
publicacion de informes, fechas/anclas/ITV o politica financiera modificados.


## Revision33: catalizadores como sintesis causal, no archivo (13-10)

ACTIVA para nuevas preparaciones. ASTS fresh32 publicado14:55:33UTC tras timeout
inicial Tradier antes de modelo y reintento normal. Original exitoso:
logs/adaptive_individual/20261013T144923435879/ASTS. La orden encolada
20261013-144204-ASTS-fresh32 conserva su primer fallo de datos; no confundirlo
con el informe posterior publicado. No se reescribio ese resultado historico.

Problema editorial real: los11 hechos recibieron show_in_report=true y el
renderer los mostro correctamente. Reader32 no bastaba: criterio amplio de
relevancia empresarial y v8 pedia toda la narrativa desde earnings en bullets.
V9 sustituye ese parrafo en ambos roles; no cambia la rubrica/plan/investigacion.
Nuevo reader_assessment full y reader_review mantenimiento distinguen driver,
background y covered. Cada driver tiene mecanismo actual y brief publico;
covered enlaza al mismo tema, background permanece solo en memoria. Conserva
hechos/fechas/fuentes/impactos completos y autoridad de riesgos/ITV intacta.
Un error editorial conserva visibilidad sin fallo financiero, repair ni full
adicional. Grupos ligados al contenido exacto, no indices aproximados; cambio
de un miembro invalida el brief viejo antes de ocultar evidencia nueva.

29 tests focalizados correctos, incluida proyeccion offline ASTS11->3 temas
con11 hechos conservados. Es una seleccion de prueba, NO una nueva respuesta
real del modelo ni una garantia de tres temas futuros. Regresiones semanticas,
financieras/volumen y congelados previos verificadas; ver auditoria33.
Sin modelos reales, lotes, publicaciones o cloud en esta correccion. ASTS
publicado permanece exacto; observar siguiente natural33 sin lote extra.

## Revision32: informe visible sin redundancias (13-10)

ACTIVA solo para nuevas preparaciones; congelados<=31 intactos. Peticion del
usuario: resumen independiente, sin bloques Tesis/Setup ni conclusion repetida;
catalizadores que importen ahora, evento util y plan breve. Render tipado separado
de finanzas: puntuaciones/razones internas y espejos de hoja siguen iguales.
Visibilidad editorial explicita en la misma llamada full o mantenimiento;
sin umbral de edad/nota, sin borrar hechos/fechas ni memoria de noticias.
reader_catalog vincula cIDs al CURRENT autenticado; identidad por contenido
impide ocultar otro hecho si cambia/reordena. Errores de seleccion conservan
visibilidad; nunca causan fallo financiero, repair o escalada. Riesgo sigue.
Retain/update migran presentacion en publicacion normal con rebind de memoria,
sin cambiar generated_at, antiguedad ITV ni ancla. Narrativa protegida heredada
NO se reescribe por estilo; nuevos full reciben instrucciones independientes.
Legacy sin estructura se omite de esta migracion por seguridad.
Ver docs/audit_reader_report_20261013.md. 16 pruebas nuevas; regresion100 tests
y44 subtests; ultima ejecucion focalizada43 tests y32 subtests, todos correctos.
Sin modelos reales, lote nuevo, cloud, recuperacion ni republicacion. Los44/46
de full31 siguen siendo el ultimo resultado historico, no reparado/publicado aqui.

## CRWV/MU full31: herencia de Volumen entre compras (13-10)

Full31 termino44/46, CRWV y MU fallidos por el mismo defecto:
update_not_allowed_volume_arithmetic: entry: select_profile_and_reaction_sources.
Ambos promovieron Washout a Entry con rango y Volumen exactos del CURRENT;
el validador solo reconocia herencia dentro de la misma casilla. No faltaban
caracteres ni habia calculo nuevo. Corregido en volume_arithmetic para>=28,
contrato que ya permite contexto entre campos del plan. Cita explicita del
bloque comprador opuesto en CURRENT autenticado + rango/Volumen exactos;
no ancla obsoleta, resistencia, fuente parcial ni coincidencia aproximada.
Calculo declarado sigue verificandose; cambio de rango/Volumen no se exime.
Los controles de origen live, materialidad, riesgo, geometria y binding siguen.
Respuestas/recibos originales de AMBOS pasan offline sin editar decisiones.
Sin modelos, relanzamientos, recovery, publicaciones ni checkpoint modificados.
Fallo historico44/46 permanece; no afirmar que ya se han publicado los2.
Ver docs/audit_buy_zone_volume_20261013.md y tests/test_buy_zone_volume_inheritance.py.
No cambio de prompts/modelos/config ni cloud; nuevos procesos cargan el fix.

## Full31 solicitado de nuevo por usuario (13-10,12:39UTC)

Orden20261013-123945-market-full31. Lanzamiento oculto PID29396 mediante
scripts/launch_full_market_command.py y lock habitual. Preflight de cola:
0pendientes; progreso anterior full29 completed46/46. launch.json registra
--analysis-mode reference, tickers_market.json, actualizacion noticias/analistas,
upload-real y max-parallel6. Config31, Sol6.1 high para TODOS por peticion expresa,
no escaladas ni mantenimiento; no cambia modo auto de futuros lotes.
Logs logs/full_market_launch/20261013-123945-market-full31{.stdout.log,.stderr.log}
y subcarpeta launch.json/result.json. Arranque confirmado: lote
logs/batch/2026-10-13/12-41-28, progreso remoto running46 con heartbeat
12:41:48UTC, preparandoCCJ,0fallidos/reintentos. NO duplicar ni reanudar el full29.

## Revision31: auditoria de fortaleza y evidencia de opciones (13-10)

ACTIVA para nuevas preparaciones. Ver docs/audit_strength_evidence_20261013.md:
35campos antes visibles ahora <70,17retirados; no son52rupturas ni52rebajas sobre
el mismo soporte. Trayectorias originales CAT/IBKR/ASML/HIMS revisadas.
Causa tecnica: raw descargaba quotes y cadenas por fecha, pero el agregado y
slim descartaban ese detalle; modelo debia evaluar liquidez/persistencia sin el.
option_details conserva contribuciones por vencimiento y quotes observadas
sin nuevas descargas, scores ni cambio de agregados/ranking. Alcance SOLO
contratos parseados/vencimientos muestreados. Ausencia, quote cero/cruzada,
timestamp ausente/antiguo NO prueban liquidez ni cero OI universal.

Contrato31 compartido por full/mantenimiento y repair: etiqueta dominante no
es vencimiento exclusivo; nueva cobertura no es evento nuevo; no doble penalizacion
automatica de una carencia en otros componentes. Durabilidad evalua todo el soporte;
riesgo real/errores previos siguen. No recuperar notas automaticamente ni cambiar
rubrica/umbrales. GEV factors decia77 pero suma67: autorizar solo fundamentos en
factors, totales/categorias derivados por renderer; sin regex/gate por estilo.

Raw/slim options31-20261013 Ready y100% verificados, runtime igual al anterior.
Builds dcd7dd33-34dd-4dc9-a489-1efd8b8a9ae3 y c22a07b1-5444-45cc-938a-29d4dbb82ab7.
Logs deploy_options31. AST aditivo contra fuentes desplegadas28; no capture real,
modelos/lote/publicacion/checkpoint durante esta auditoria. Modelo real con dato
nuevo queda para siguiente natural, no prometer notas ni cumplimiento de prosa.
114tests y79subtests correctos, incluidos46recibos originales sin cambiar fortalezas.
Modelos/esfuerzos/ITV/concurrencia exactos. Congelados<=30 no se reinterpretan.

## Revision30: informe breve, investigacion separada (13-10)

Usuario pidio limites por seccion y aplicar los problemas editoriales de MRVL.
ACTIVA solo para preparaciones nuevas. v8 financiero, mantenimiento/contrato30,
report_reader_style_v30; misma rubrica, schemas financieros, modelos, ITV5,
concurrencia y autoridad. No cambios de informes publicados, bases o checkpoints.
El full29 ya congelado NO cambia ni se relanza; MRVL no ha sido resumido.

Presupuestos de redaccion (frases/palabras maximas): motivo Tesis/Setup1/20
cada uno; narrativa3/60; motivo de zona2/45; catalizador2/40; evento, conclusion
y nota2/35. Son limites de escritura en la misma llamada, no rechazo de tickers,
truncado, CSS que oculte texto, escalada o editor adicional. No prometer numero
de lineas visuales fijo entre pantallas. Cantidad de catalizadores materiales
sin cap. Riesgos/atribucion/limitaciones relevantes permanecen.

Causa MRVL: instrucciones financieras trasladaban comparaciones, alternativas
y correcciones al Motivo y duplicaban cambios de nota en Narrativa; se han
reubicado en evidencia/razonamiento internos. No diario de busquedas/rumores no
verificados ni manual del sistema en Conclusion. Proposito nuevo de resistencia
no demuestra error anterior. Vigencia sobre quote requiere respaldo positivo
actual, no solo ausencia de ruptura; juicio financiero/reglas28 intactos.
Renderer30 acorta solo el estado mecanico a Precio en la captura.
Mantenimiento no gana permiso de reescribir tesis/narrativa protegida por estilo;
herencia literal sigue. Textos nuevos/autorizados siguen presupuestos.

Verificacion offline: test_reader_budgets_v30.py, test_plan_scope_v29.py,
test_support_brief_v28.py, tests/test_semantic_presentation.py,
tests/test_quote_decision_stability.py, tests/test_adaptive_luna_repair.py.
MRVL original conserva contenido financiero, fuentes y render de29; mismos
schemas29/30, rubrica numerica identica, freeze de ambos roles y repair probados.
No nueva llamada financiera: el cumplimiento editorial real queda por observar
en la siguiente generacion natural autorizada, no en un lote duplicado.
Nota del entorno: pytest-of-ignac tuvo WinError5; pruebas usan basetemp temporal
nuevo y acotado, sin cambiar permisos globales ni tocar el run.

## Lote full29 autorizado TERMINADO (13-10, 11:51 UTC)

Usuario pidio renovar los46 como nuevas referencias y confirmo lanzarlo.
Orden20261013-110415-market-full29; lote logs/batch/2026-10-13/11-06-58.
Modo reference explicito para TODOS, Sol6.1 high; contrato29, max_parallel6.
Lista vigente tickers_market.json (46), no tickers.json legacy (38).
Arranque verificado: progress running46, heartbeat11:07:18Z, prepare CCJ.
Launcher oculto scripts/launch_full_market_command.py bajo command_worker.lock;
logs/full_market_launch/20261013-110415-market-full29.stdout.log y stderr.log.
Resultado final verificado en logs/full_market_launch/20261013-110415-market-full29/result.json:
46/46 publicados,0fallidos, exit0; fin11:51:20UTC. SOFI publicado11:23:39UTC.
Los46full fueron solicitados como renovacion, no46escaladas criticas.
La orden45/46SOFI090123 corresponde al lote anterior; no una recaida nueva.
Sin automatizacion nueva ni reanudacion/recovery del historico.
La renovacion es puntual: no se cambio el modo automatico normal posterior.

## Revision29: plan de compra sin stops y resistencia unica (13-10)

ACTIVA para preparaciones nuevas, por peticion explicita del usuario. Entry,
Washout y resistencia OPERATIVA con la misma rubrica de fortaleza. Retirados
management_stop, structural_stop y target de schemas/salida/contexto financiero/
catalogo/geometry y prompts normales/repair. No calculos de stops/R ni guards
por cruzar stops retirados. Riesgo real, tesis, posiciones, incertidumbre, fuentes,
aritmetica y ITV5 siguen. Sol6.1 medium/high y concurrencia6 sin cambio.
Elige barrera relevante para el rebote desde entradas; no techo mas fuerte remoto
ni primer obstaculo mecanico sobre quote. Mantener antigua resistencia solo si
sirve; mejora rutinaria demostrada no exige inventar error previo o noticia nueva.

Retain migra presentacion en publicacion natural: solo tres bloques, valores y
razones restantes/fortalezas/fechas/captura/ancla exactos, memoria autenticada
re-vinculada y MD/HTML/JSON juntos. No nuevo analisis, no cambio de ITV, no
llamada extra. Congelados<=28 conservan prompts/schemas/recibos y guards viejos.
No informe real publicado, modelo, lote, recovery o despliegue cloud en este cambio.
188 tests y144 subtests offline pasan, incluidos los46originales, siguiente
contexto, retain completo con publicador simulado, full/update y consumidor local.
Ver docs/audit_plan_scope_20261013.md. Observar proximo NATURAL, no duplicarlo.
CRDO: su resumen largo heredado sigue protegido; la instruccion breve de28 solo
afecta redaccion full nueva. No afirmar que la migracion29 lo ha resumido.

## SOFI13-10 / contrato de evidencia del mismo plan corregido

Ver docs/audit_sofi_20261013.md. Natural28 09-03-29 termino45/46:
36retain,9update,0full; SOFI failed tras una reparacion y retry de lote reutilizado.
Promover washout a entrada estaba permitido pero el validador rechazaba citar
ambos campos; tambien confundia el stop protegido como contexto con dato live.
Ademas ocultaba errores posteriores al primero por bloque en el unico repair.
Corregido >=28: contexto autentico suplementario separado de prueba de cambio/
origen actual; falta de fuente live sigue rechazada. Todos los errores se agrupan
con campo/token/pointer. Riesgo/stops/geometria/fuentes/recibos y<=27 intactos.
Ambas respuestas ORIGINALES pasan offline sin cambiar contenido, numeros o fuentes.
Dos baterias pasan:183tests+226subtests y92tests+133subtests (16tests comunes).
No modelo, lote, recovery/publicacion. SOFI sigue anterior,45/46 historico intacto.
Config28/modelos/ITV/concurrencia/prompts no cambiados; correccion local de validador.


## Revision28: vigencia de compra y resumen ejecutivo (13-10)

ACTIVA para nuevas preparaciones. Ver docs/audit_support_brief_20261013.md.
Lote natural27 08-03-29 termino46/46,37retain/3update/6full,0failed/retries;
QCOM/RDDT/KTOS ya publicaron. Exito operativo no demuestra buenos juicios:
varios retain trataban falta de ruptura registrada/test5d pendiente como razon
suficiente para conservar compras sobre precio; faltaba secuencia OHLCV reciente.
Raw/slim history28-20261013 sirven100%, runtime preservado. price_history entrega
20 sesiones completas; smoke LRCX exacto entre capas, ultima12-10. Sin modelos.
Captura ausente/malformada falla ANTES de modelo/freeze (reintento de datos existente),
no se convierte en perdida de soporte. Viejos recibos<=27 no exigen el campo.
Prompt compartido/repair: vigencia actual antes de continuidad/fortaleza historica,
test5d inmaduro no obliga a esperar. Sin borrar por porcentaje, ATR o cruces marginales.
Resumen nuevo: razones breves, narrativa corta, detalles en catalizadores/plan/audit.
Notas publicas concisas; no gate de longitud, truncado ni Sol por estilo.
No informes/niveles/notas/fechas/anclas/checkpoints reescritos ni lote duplicado.
207 tests distintos y197 subtests offline pasan; proyeccion de46originales intacta.
Pendiente observar decisiones/editorial en proximo lote NATURAL28, no afirmar que
pruebas deterministas garantizan juicio del modelo. Desfase captura Sheet vs informe
CRDO/LRCX no diagnosticado como parte de este cambio; auditar consumidor aparte.


## Revision27 / incidente12-10 corregido (13-10)

Ver docs/audit_run_20261012_204228.md. Orden20261012-203855-568-market-8ec34f16,
lote20-42-28:42/46 original,28retain/6update/8full. QCOM/RDDT/KTOS timeout;
IONQ rechazo indebido de aritmetica de resistencia con rebotes de soporte.
Arranque CLI ya no consume los240/1200s de ejecucion: ambas fases acotadas por
el mismo plazo configurado, solo primer turn.started cambia de fase. Eventos y
stderr durables; timeout completo recupera respuesta sin modelo, terminal fallido
transitorio permite retry con contrato exacto, ambiguo bloquea. Preflight readonly
reconecta una vez ante transporte fallido; nunca modelos ni mutaciones.
Direccion medida determina aplicabilidad de aritmetica, no tipo actual de zona.
Prompts/contexto27 para preparaciones nuevas, congelados<=26 exactos.
Recovery autentica ITV original sin recalcular edad hoy; vigencia/base/ancla/
ownership siguen. IONQ publicado con recibo original12-10 21:00:34Z, cero modelos,
canonical/espejo releidos exactos. logs/recoveries/20261013T071438944721/recovery.json.
No se regeneraron los otros3 ni se reescribio el lote. Observar proximo natural27.
No cambios de modelos, concurrencia, rubrica o ITV5; sin despliegue cloud.
Verificacion:458 tests y461 subtests offline pasan. Config27 activa para nuevas
preparaciones; no se ha hecho smoke de modelo/lote vivo ni promesa de cero fallos.

## Revision26: aplicabilidad y mediciones historicas estables (09-10 tarde)

Dos mejoras SISTEMICAS autorizadas; no se editaron informes ni checkpoints.
Guard estructural: solo owned=false explicito y ambas compras ausentes en el
CURRENT tipado autenticado convierten el cruce del stop historico en pregunta
de revision medium, no full automatico. Tambien evita reutilizar la compra ya
retirada del ancla. QBTS original queda revisable; ASTS activo, owned/unknown,
riesgo, autoridad de stops e ITV5 siguen protegidos. No fuerza retain.

Productor: las reacciones excluian hoy pero su ATR/tolerancia incluian hoy.
Ahora historial y calibracion usan sesiones completas. ATR tecnico vivo y
tolerancia de la zona actual NO cambian. measurement_basis identifica metodo,
historia OHLC y parametros. Nueva historia cerrada/correcciones/zonas distintas
pueden cambiar la medicion; no es congelacion permanente de estadisticas.
Contexto26 compara solo registros de igual familia/tipo/nivel, sin aproximar.
Datos legacy sin base son no comparables, no prueba de nueva defensa fallida.
Instrucciones normales y reparacion distinguen recalibracion/materialidad;
no hay umbral arbitrario de puntos ni excepcion al calculo25 o riesgo real.

Verificacion offline: 332 tests (97+234+1 nuevo posterior), incluidos originales
QBTS/ASTS, variacion intradia, nueva/corregida historia, slim, contrato26 ambos
roles y reparacion, congelados25 intactos. No modelos ni lote/smoke financiero.
Servicios raw/slim evidence26-20261009 basados en imagen activa inmutable;
diff AST limita cambios a _annotate_support_evidence / _slim_level_evidence.
Builds 06777e3c-9e51-4862-bc57-d745e7b17b6f / e8028492-697f-4b08-a402-a4e21acdb084.
Auditoria despliegue: logs/deploy_evidence26. Ambos servicios Ready,100% trafico
releido hacia evidence26-20261009, sondeo sin simbolo400, configuracion runtime
y anotaciones operativas intactas. Tags temporales quitados; tag previo intacto.
Config26 activa para nuevas preparaciones; observar siguiente lote NATURAL.
Congelados<=25 mantienen prompts/recibos exactos. No reinterpretar lote45/46.

## AUR memoria de correccion manual reparada (09-10 tarde)

Lote15-39-36 orden20261009-153647-982-market-b5b93ae3:45/46,38retain,
5update(GEV/HOOD/QCOM/MRVL/TSM),2full(ASTS/QBTS). AUR failed antes de modelo:
correccion manual de la manana copio memoria ligada al informe anterior.
Constructor corregido con rebind autenticado; publicador valida memoria antes de
escribir. 227tests pasan, incluidos7 de siguiente ciclo/recovery/45originales.
AUR canonical/espejo/current reparados y releidos, sin modelos/run/ancla tocada:
logs/memory_repairs/20261009T163642544667/AUR/audit.json. Contenido/fecha/cifras
intactos. Lote sigue45/46; NO afirmar AUR revisado esta tarde ni falsear checkpoint.
Ver docs/audit_run_20261009_153936.md. Pendientes NO cambiados: recalculo de
historia por ATR actual provoca cuatro updates de materialidad discutible;
QCOM corrige error previo. ASTS full justificado; QBTS guard sobre plan ya sin
posicion ni entradas, full evitable. No se modifico politica/rubrica/productor.

## Revision25: aritmetica de Volumen y correccion AUR (09-10)

Lote natural24 logs/batch/2026-10-09/10-10-37: 46/46 publicados, 39 retain,
6 update y NVDA full. AUR introdujo un error: magnitud 4,91/2,46=1,996
recibe 2 puntos por superar 1,5x, no 1. Volumen correcto 12, fortaleza 63.
LRCX 11 y MRVL 14 verificados; no error de metodologia ni instrucciones.

Nuevas preparaciones activas25, congeladas <=24 mantienen exactos contratos.
volume_calculation vincula profile_source y reaction_source seleccionados por el
modelo a registros exactos del catalogo presentes en evidence. El runner calcula
los cinco subcriterios y limites de la rubrica v6 al CENTRO de la zona, con
Decimal sin redondear y fecha de la captura seleccionada (tambien historica).
Permite perfil/reaccion de fuentes distintas; no elige zona ni dictamina respaldo.
Null hereda rango/Volumen exactos o deja una cuenta no estructurada a juicio;
no inventa datos no disponibles, no parsea prosa ni los convierte en perdida.
Mismatch recibe la unica reparacion existente. Repetido solo aritmetico falla
visible sin automatico Sol/retain. Riesgo, autoridad, ITV y otros errores intactos.
Mismo Sol6.1 medium/high, concurrencia6 y timeouts. No modelo/lote de prueba.

240 pruebas pasan: 16 nuevas (original AUR, LRCX/MRVL, full NVDA, limites,
cap/rebote reciente, centro real, fuentes exactas/reordenadas, binding y herencia,
una reparacion/repetido sin Sol, preparacion25 y consumidor); 78 semanticas,
129 contratos/riesgo/revisiones y 17 reparacion anterior. Verificacion offline,
no promesa sobre decisiones futuras del modelo. git diff --check correcto.

AUR corregido por peticion humana, sin falsear recibo/modelo: provider manual,
generation_model manual-arithmetic-correction. Publicado 11:01 UTC,
generated_at 2026-10-09T11:00:21.146213+00:00; cambia solo Volumen 11->12 y
fortaleza derivada 62->63. Tesis/Setup/niveles/stops/captura y fechas de texto
exactos; ancla full 2026-10-09T06:48:26.998416+00:00 intacta, ITV no reset.
Ownership vigente y base/ancla comprobados por publicador normal.
Canonical y espejo releidos: Volumen12/63, provider manual; ancla identica.
Historico original del lote conserva AUR62 y sus recibos intactos.
Evidencia logs/corrections/20261009T110021146213/AUR/correction.json.
Herramienta correct_volume_arithmetic rechaza base/revision/ancla/captura/
ownership cambiados; el constructor puro conserva los juicios y marca la autoridad
humana. No reemplaza una reparacion de respuesta modelo por un recibo inventado.

## Enlaces Yahoo reparables en refresco (09-10)

CLS estaba como stringValue sin formula ni hyperlink; ordenar por Sector copiaba
esa celda defectuosa. Restaurado en hoja real (tras ordenar: Mercado!K9) con su
formula HYPERLINK y formato de enlace. Lectura final:46/46 enlaces Yahoo correctos.

global_sheet_sort ahora repara formula/destino ausentes o incorrectos al generar
el plan usado por market/refresh y analysis/refresh. Si el orden no cambia, escribe
solo las celdas afectadas; si cambia, lleva la celda reparada a su destino.
Conserva fondos/shots, notas y datos de analisis. Enlaces validos no se reescriben.
No requiere reconstruir tablas. changed sigue indicando solo cambio de orden.

136 tests del controlador correctos, incluidos4 nuevos de reparacion estable,
tras mover, idempotencia y URL incorrecta/separador alternativo. Los4 tambien
pasan dentro de la imagen de produccion parcheada.
Cloud Build f027ca3f-0422-467b-bd0b-020934acd37f SUCCESS; imagen derivada de
support22 inmutable826660fb86763687b117cbc5b0e0358ca47bb3ec90f6fcc7731d3b7ac0520bf4,
modificando solo global_sheet_sort.py (instalado y copia src).
Revision stock-controller-ticker-links-20261009 sirve100%; health200.
Spec runtime antes/despues identica excepto imagen; ruta temporal de prueba retirada.
Evidencia:logs/cls_link_repair (diff build, specs y health).
La primera comprobacion uso equivocadamente latestReadyRevisionName del servicio
para una revision sin trafico; se verifico Ready/ContainerHealthy de la revision
y health200 por ruta de prueba ANTES de activar. No batch/modelo ni Gateway.

## Revision24: USAR sin operacion / stop no aplicable (09-10)

Lote natural23 logs/batch/2026-10-09/06-40-36, orden
20261009-063647-217-market-40b0d2c7: final45/46,23retain,16update,6full;
USAR unico failed, un reintento de lote sobre el MISMO recibo Sol high. No segunda
generacion. Los6publicados full: AUR/CLS/HIMS/ASTS/QBTS por ITV5, SPCX por acuerdo
Grain posterior al informe. No confundir revisiones de mantenimiento con full ITV.

USAR retiro ambas entradas y explico stop de gestion no aplicable, owned=false.
Schema admitia null, validador por campo exigia numero sin considerar el plan.
Correccion general en contratos>=22: validar aplicabilidad con ambas entradas y
owned explicitamente false; cualquier entrada activa o propiedad true/desconocida
rechaza stop ausente. Motivo/fuentes/binding/continuidad siguen; estructural y
objetivo no opcionales. Mantenimiento NO gana permiso para borrar stops.
Nuevas preparaciones24 aclaran la regla; prompts/schemas/recibos<=23 intactos.
Modelos/effort/ITV5/concurrencia6/timeouts sin cambios. Consumer cloud ya compatible;
no despliegue, Gateway ni lote/modelo de prueba. Render: stop No aplicable.

USAR original ya pasa en copia offline, mismo texto/cifras/fuentes/fecha de Sol.
45informes publicados conservan proyeccion y siguen aceptados por consumer.
Recuperacion real publicada: logs/recoveries/20261009T073430215071/recovery.json.
USAR analysis_status=ok, fecha original 2026-10-09T07:01:20.019029+00:00;
publicacion 07:35:10 UTC. Cero llamadas nuevas; originales intactos y ownership
vigente false comprobado; bases/ancla verificadas por publicador normal.
Historico del lote sigue45/46: no reescribir comando/checkpoint para fingir exito.
Con la recuperacion quedan disponibles los46 informes (23retain,16update,7full).
Pruebas: 183 casos de revisiones y 145 de contratos/fuentes/etapas/reparacion/news/
fecha pasan; incluye12 de aplicabilidad24, replay original USAR y los45publicados.
Un test esperaba modelo Luna fijo; ahora comprueba modelo/effort de politica.
git diff --check correcto. Sin smoke nuevo de modelos, observar lote natural.
Dry-run previo: logs/recoveries/20261009T072742173710/recovery.json.
Herramienta recover_adaptive_receipt separa recuperacion de historia, impide nuevas
llamadas y verifica ownership vigente + bases/ancla antes de publicar.

## Historial revision23

## Revision23: captura tecnica y autoridad de mantenimiento (09-10)

Nueva preparacion activa23; <=22 conserva sus inputs/prompts/recibos exactos.
Modelos SIN cambios: Sol6.1 medium mantenimiento, high completo, ITV5, max6.
Incidentes originales: orden20261008-194708-734-market-aa029d7b,
lote logs/batch/2026-10-08/19-49-44. Final44/46:20retenidos,13actualizados,
11completos; ASML/LRCX fallidos. Cuatro timeouts de preparacion recuperados
(NBIS/MRVL/MU/KTOS). No todos los11Sol fueron cambios criticos/ITV: MU confundio
los umbrales3/5%; CRDO trato una correccion de rubrica como competencia exclusiva
de Sol. CCJ contiene una cuestion de razonamiento de stop protegido: no se ha
ampliado su autoridad ni declarado automaticamente injustificada. Riesgos/noticias
de otros escalados requieren juicio; no se ha impuesto un numero de regenerados.

Cambios de raiz:
- Raw reutiliza expiraciones/cadenas dentro de UNA peticion, no cache persistente.
  Opciones: excepcion en extras, walls o overview devuelve502 ANTES del espejo,
  no objeto/lista vacia con200. Tambien detecta errores devueltos dentro de scopes
  del overview; no convierte una captura parcial en exito.
  Estado no_future_expirations explicito distingue ausencia legitima de error.
- Slim transmite estado y observaciones de anclas AVWAP solicitadas. Se recalculan
  fechas exactas con OHLCV actual, fuera del filtro de distancia/ranking del
  listado candidato. Sin cobertura del ancla devuelve unavailable, nunca empieza
  en una fecha posterior. No implica soporte vigente ni invalida por estar encima.
- Preparacion23 solicita las anclas previas y valida captura ANTES de congelar
  input/admitir modelo. El reintento de lote existente vuelve a descargar tras
  fallo de captura; no reutiliza un dictamen sobre ese input incompleto.
  No se sobrescriben inputs ya admitidos ni se reintenta un modelo con datos
  inventados. Un blocked financiero posterior sigue visible, no fallback a high.
- Techo de Volumen/reaccion calculado por codigo en contexto (por registro,
  no puntuacion final ni mandato de cambio). 3-5% puede llegar15 si cumple ambas
  familias; >15 exige <=3% y el resto de requisitos. No rebaja automatica.
- Politica23 consolidada: aplicar bien la rubrica/corregir razon tecnica editable
  es mantenimiento aunque el autor fuera Sol. Cambiar metodologia/tesis/stop
  protegido o riesgo sigue high. Entradas nulas22, evidencia y repair se mantienen.

Cloud raw capture23b-20261009 y slim capture23-20261009, derivados de las imagenes
inmutables complete-window-20261008 cambiando SOLO main.py; mismo runtime/env/
recursos/service account y dependencias. Build raw final528f6a72-7b8f-45a2-9a65-f15198386825
(incluye error walls/overview); slim15d7e40e-4fff-4961-9432-7587f54be88a.
Primera revision23raw af94f3b3-a545-431d-b825-415de1fd0ab1 reemplazada por23b.
Spec anterior/nueva identica
excluyendo imagen. Dockerfile.capture23 documenta base inmutable de cada servicio.
No lote/modelo/republicacion/recuperacion ni Gateway tocados. ASML/LRCX originales
siguen failed historicos; NO afirmar recuperados por haber corregido el sistema.

Tests: test_capture_routing_v23.py usa originales ASML/LRCX/MU/CRDO, limites de
rubrica, aislamiento de cache, fallo sin espejo, contrato de ancla y flujo23.
Comparacion handler raw completo antes/despues contra fuente cloud previa con
misma respuesta Tradier simulada: mismos valores (excepto nuevos metadatos),
solo2descargas de opciones en nuevo frente a multiples repetidas. Sin red/modelos.
Verificacion final:367tests de cadena (349anteriores+18nuevos) tras activar23,
20tests nuevos al cerrar tambien walls/overview, y22tests productor:391casos
distintos correctos. Handler de activo sin opciones sigue200; fallos de cada
componente no publican espejo. Probes cloud sin simbolo devuelven400 esperado
sin consulta de mercado ni escrituras. Tests no predicen el juicio de un
modelo vivo. Observar siguiente lote NATURAL23, sin duplicarlo como prueba.

## Revision22: compras en soporte y ausencia explicita (08-10)

Activa solo para nuevas preparaciones. Peticion FINAL: si la zona superior esta
realmente perdida y no hay soporte inferior defendible, dejar Entrada/Washout
vacios. El usuario retiro la opcion de conservarlos como compra tras recuperacion.
Una pequena perforacion no prueba ruptura: sin regla automatica porcentual/ATR/
numero de cierres. Evaluar vigencia, luego alternativas; no inventar soportes.
Contrato tipado permite range/strength=null para ambas entradas con motivo y
evidencia. Null del bloque de update sigue heredando. Riesgos/stops/ITV protegidos.
Routing lee la ausencia autentica, no interpreta Markdown como fallo de formato.
Sin entrada no implica Sol high ni reinicio ITV. Medidas y noticias no cambiadas.
Modelos: Sol6.1 medium mantenimiento; Sol6.1 high completo; ITV5 y concurrencia6.
Congelados <=21 intactos. No modelos/lotes ni republicacion de informes existentes.

Publicador cloud: stock-controller-support22-20261008, trafico100%, health ok.
Imagen derivada EXACTAMENTE de la imagen activa quote-groups-fix-20260929:
solo reports.py (aceptar ausencia tipada22); config/dependencias/runtime intactos.
Build b72be6b1-79d5-4d26-8131-b3757a75796c. Comparacion del archivo desplegado previo
confirma solo ese cambio; spec Cloud Run identica salvo imagen. 47 informes locales
estructurados validos producen identico registro de hoja antes/despues.
10 pruebas nuevas offline: retirada, no alternativa, alternativa inferior,
restauracion posterior, hoja vacia, llamada unica, ITV, riesgo, evidencia, geometria
y congelados21. Controller132 pruebas pasan. Esto NO es un smoke de modelo vivo.
Ver test_buy_support_v22.py; observar decision financiera en siguiente lote natural.

## Cambio de modelo de mantenimiento 08-10 (peticion del usuario)

Nuevas preparaciones: triage_model=gpt-6.1-sol, triage_effort=medium.
Sustituye a gpt-6-luna high en revision/mantenimiento; informes completos e ITV
siguen con gpt-6.1-sol high. Sin cambios de reglas, ITV5, concurrencia ni timeouts.
No se ha lanzado un lote/modelo ni modificado recibos ya preparados. Las menciones
historicas a Luna describen el rol anterior, no el modelo configurado ahora.

## Auditoria de cadena 08-10 / revision21

Usuario exige verificar defecto Y no-regresion, no solo pasar validador.
Auditoria detallada: docs/audit_chain_20261008.md. Originales usados: lote
2026-10-08/14-53-35; resultado historico intacto45/46,37retain,7Luna,1Sol,AMATfailed.
No modelos, lote, Gateway, publicaciones, recuperaciones ni cambios de checkpoint.

Causas y cambios21:
- Procedencia por texto creada/persistida por runner; comparison.text_origins
  distingue snapshot del parrafo, snapshot del contenedor y ultima revision.
  Se reutiliza fecha original conocida (conclusion/MU ancla); desconocida queda
  desconocida. Copias identicas no redatan. Render fecha heredada sin dump de JSON.
- plan_explanation: cada parrafo no-null es {text,review}; no revision global
  que autorice reescribir todo. Null conserva literalmente. Motivo structural_stop
  solo null; valores/rubrica/tesis/riesgos mantienen protecciones.
- Actualizacion solo de texto identico es retain, no informe nuevo. Riesgo/agenda
  siguen evaluandose. Contrato tipado repetidamente invalido falla tras un repair,
  no escala automaticamente a Sol por error mecanico. Escaladas financieras siguen.
- IREN: run_one individual omitia --owned y enviaba false sin leer cartera.
  Individual y --tickers manual consultan el MISMO config/tickers.json de mercado.
  Error/dato ambiguo no se convierte en false; --owned/--no-owned son explicitos.
- Nuevos daily21/shared21/repair21 coherentes; recibos/prompts<=20 congelados.
  Config21 para nuevas preparaciones; modelos/effort/ITV5/concurrencia6 intactos.

Verificacion ampliada338 tests offline correctos tras activar21;
incluye37 conservados originales sin cambios de ruta, resultados financieros
WDC/NBIS/SPCX intactos, fuentes SPCX reconstruidas de eventos reales, fecha USAR
13.515 dentro de entrada (no13.265 del contenedor), MU heredado del ancla1019.98,
ediciones acotadas preservando otros parrafos/numeros, cadenas de dos updates,
llamadas/repair/ITV, publicacion con base/ancla/revision cambiadas y propiedad.
Proyeccion de los informes publicados conserva Markdown original con su banner
historico y todos los textos/cifras; no se re-renderizan archivos conservados.
La prueba inicial comparo cuerpo renderizado con Markdown con banner: se corrigio
el montaje del test, no los originales ni el render historico para acomodarlo.
Estos tests no predicen criterio futuro de modelos ni verifican toda noticia.

Correccion de interpretacion anterior: AMAT tiene origen de parrafo DESCONOCIDO;
no basta comparar su frase con517.27 del contenedor para demostrar error historico.
Fixture AMAT demuestra autoridad de edicion acotada, NO que el modelo deba editar.
SPCX solo consta busqueda/snippet para algunos detalles, no articulo completo;
OKLO ya estaba bajo entrada en ultima revision. No afirmar todo era cambio nuevo.

Pendiente operativo: observar siguiente lote NATURAL21. No duplicarlo. Informes
anteriores NO reescritos: MU publicado aun tiene cinco motivos genericos; una
restauracion puntual debe usar originales y preservar estado vigente, no un lote
regenerado. AMAT historico sigue failed. No confundir correccion del sistema con
recuperacion de publicaciones anteriores ni tests de contrato con verdad financiera.

## Historial revision20

## Revision20 activa 08-10: cerrar AMAT y el contrato de mantenimiento

Peticion: corregir y completar lo anterior, sin lote/modelos de prueba. Se comprobo
que no habia run_batch/adaptive_stage/run_one activos; Gateway no tocado.
Lote examinado: logs/batch/2026-10-08/14-53-35, orden
20261008-145055-309-market-ee431061. Resultado HISTORICO:45/46 publicados,
37conservados,7actualizados Luna,1Sol(IREN);AMAT fallido tras correccion dirigida
y reintento de lote. No recuperado, republicado ni maquillado en esta intervencion.

Causas comprobadas en AMAT/triage.json, triage_repair.json y input.json:
- Revision19 ya estaba activa. La correccion previa fue INCOMPLETA: solo admitia
  referencia historica para plan_explanation, no para otros comentarios.
- Primer intento: routine_note/wrong_scope_current_evidence y cinco motivos
  vacios rechazados por exigir copia completa del plan. Existia una contradiccion
  verdadera: motivo de Entrada decia dentro con snapshot517.27 frente519-521.
- Pero Luna tambien interpreto MAL la nota previa:520.08 ->517.27 era una
  comparacion historica valida, no520.08 atribuido al snapshot actual. No aprobar
  automaticamente toda la primera propuesta por corregir el contrato.
- Segundo intento: comentario interno 'no anado nota' en routine_note con review
  null; missing_review. Ademas copiaba textos de snapshot antiguo como nueva
  explicacion, perdiendo procedencia de conclusion. No problema de proveedor.

Correccion GENERAL20, solo nuevas preparaciones:
- Contrato explicito update.public_note={text,review} o null; root routine_note
  desaparece de respuesta Luna. reason/assessments no se publican. Runner conserva
  nota sin editar y su fecha, tambien a traves de actualizaciones sucesivas.
- plan_explanation parcial: null/vacio hereda texto, no borra fundamentos ni
  obliga a copiar seis motivos. Texto identico no elimina procedencia heredada
  de conclusion. Setup puede corregir motivo sin inventar cambio de puntuacion;
  campos independientes no se rechazan como duplicados; mismas cifras protegidas.
- prior_error permite prueba historica autenticada en TODOS los comentarios y
  revisiones de nivel; respaldo cambiado/nuevo nivel sigue necesitando evidencia
  actual. Fuentes inexistentes, riesgo, rubrica, integridad y autoridad permanecen.
- Nuevos daily_maintenance_semantic_v20.md y adaptive_revision20.md consolidan
  instrucciones: no se envian viejos contratos15/16/19 contradictorios. Politica
  financiera v6 y estilo legible se mantienen. Footer de noticias y unico repair
  usan el mismo contrato; no filtros de prosa/puntuacion ni llamadas extra.
- Se mantienen cobertura real de noticias, memoria/operabilidad MRNA/NBIS/USAR/
  IREN, limites de autoridad, ITV5, Luna6high/Sol6.1high y concurrencia6.

Verificacion:267 tests offline correctos (21 nuevos en test_maintenance_text_v20.py),
sin modelos ni red/publicaciones. Ambos intentos originales AMAT reproducen sus
rechazos19; alternativas AUTORIZADAS SOLO COMO FIXTURES pasan20 manteniendo
precios/puntuaciones/nota historica correcta. No prediccion del futuro juicio Luna.
Recibos19 reconstruidos byte-exactos; suites mantienen contratos18 y anteriores.
Pipeline simulado:retain/update una llamada; ITV Sol; un repair corrige o retira;
repeticion de defecto real sigue visible, nunca fallback Sol solo por contrato.
Compilacion y git diff --check correctos (advertencias normales LF/CRLF).

Pendiente operativo, no implementacion a medias: observar siguiente lote NATURAL20.
AMAT del lote anterior sigue failed; no reutilizar/re-etiquetar recibos19 como20.
No afirmar que el schema demuestra verdad financiera ni que no habra errores nuevos.

## Historial revision19

## Revision19 activa 08-10: MRNA / NBIS / USAR / IREN

Usuario: corregir las causas diagnosticadas, no introducir umbrales ni mas llamadas.
Ultimo lote natural13-42-25:45/46 publicados,41retain,4Luna(KTOS/MRNA/NBIS/TSLA),
0Sol; USAR fallo real no recuperado. Individual IREN13:59 termino16:05 Madrid
con full Sol,36.66 en captura16:00; owned=false EN ESTE informe. No confundir
con owned=true de capturas anteriores ni inferir venta real. No habia procesos
run_batch/adaptive_stage/run_one activos al comprobar antes de activar19.

- USAR: news.items y agenda vacios, noticia no requerida, evento09Oct futuro.
  Triage original retain tenia grupo items=[]/no_action/not_applicable. El gate18
  lo rechazo; repair invento e1. En19 esos grupos no aportan cobertura y se ignoran;
  items reales faltantes/duplicados/desconocidos siguen rechazados. No se acepta e1
  inventado ni se convierte un riesgo declarado en retain. Feedback explica lista
  vacia. COPIA del triage original pasa cobertura y ruta retain19 sin otra llamada.
- NBIS: el18 anterior reconciliaba prosa SOLO si cambiaba rango. Este lote arreglo
  conclusion pero dejo target_reason refiriendo270 frente a resistencia ya250.
  Ahora plan_explanation admite correccion coherente sin mover rangos/puntuaciones,
  justificada en change_review.plan_explanation (prior_error/routine_technical).
  Fuentes exactas del propio informe pueden probar contradiccion interna; no
  inventar evento nuevo para satisfacer evidencia current. Riesgo/tesis/stops
  protegidos, incluso expresados en prosa. No regex de precios/puntuacion.
- MRNA: revisar/aclarar el titular antiguo CFO no demuestra error del informe,
  que no afirmaba compra discrecional. Prompt19 distingue investigar de publicar:
  guardar evaluacion/research sin nota nueva salvo error real o efecto relevante
  para lector/decision/riesgo/evento. No suprimir noticias significativas solo
  porque no muevan niveles o porque el hecho sea antiguo.
- IREN: full Sol conserva40.5-40.9/38.85-39.15,stop39.45 y scores79/73, pero
  exige recuperacion/defensa. Eso NO es compra inmediata ni stop actual sin posicion.
  Problema: defensa historica no demuestra soporte vigente; 'sin perdida confirmada'
  no se puede deducir de falta de evidencia. Prompt19 para AMBOS modelos evalua
  operabilidad ANTES de continuidad, separa soporte perdido/referencia historica/
  reclaim futuro y justifica cada entrada con invalidacion propia y asimetria.
  No obliga a bajar niveles ni a Sol por distancia. Alternativa opcional puede
  retirarse con causa financiera; no respaldo por mera ausencia TOP ni corteRR.

19 sustituye el bloque18 en NUEVAS preparaciones (no instrucciones contradictorias
apiladas); schemas/inputs/recibos<=18 permanecen congelados. Fuente financierav6
y overrides15/16/reader17 siguen. Modelos/effort/ITV5/concurrencia6/timeouts intactos.
Tests offline:246 correctos en bateria conjunta,22 nuevos19; reconstruidos los46
recibos18 originales y los17 de bateria previa. Mocks verifican retain/update/ITV,
una correccion, protecciones y numero de llamadas; NO predicen juicio de modelos.
Sin modelos/web de prueba, lotes, recuperaciones, Gateway ni publicaciones.
Informes actuales y fallo USAR originales NO reescritos: siguiente preparacion
natural19 aplica la correccion. No afirmar que pruebas offline repararon el lote.

Pendiente: medir decisiones reales del siguiente lote natural19, especialmente
notas MRNA-like y operabilidad IREN-like. No garantizar criterio financiero por
un schema valido. Escenarios y limites en docs/codex_adaptive_analysis.md.

## Historial revision18

## Revision18 activa 08-10: CIFR / MU / NBIS

Peticion: quitar el 8%, corregir omision MU y aclarar/corregir NBIS de raiz.
Auditoria SOLO lectura del lote 11-31-14 (orden 20261008-112851-470-market-74689eaa):
46/46 publicados,0fallidos;41retain,2Luna(MU/NBIS),3Sol(SOFI/CIFR/SPCX).
Comparacion con 09-32-38, no noticias nuevas buscadas ni modelos/lotes lanzados.

- CIFR: 14.395->14.195 entre lotes; Sol por superar8% respecto a15.52 del ancla,
  no por una nueva noticia. Revision18 no evalua ese umbral ni contra CURRENT
  ni contra SOL; no se sustituye por otro porcentaje. Stops/riesgos/ITV siguen.
- MU: el titular Micron/Samsung 11:05+02 YA estaba en09-32 (DJ-N$1f835f92).
  El evento Samsung fechado08-10 seguia futuro. La memoria confundia feed recibido
  con noticia revisada. Nueva agenda explicita de articulos no evaluados y evento
  vencido; permite agrupar hechos relacionados. Solo cobertura declarada entra en
  ledger; historial<=17 es recibido, no prueba de evaluacion articulo a articulo.
  Lookup opcional permitido, no busqueda ni llamada extra obligatoria. Estado de
  evento anotado por separado del antecedente Sol protegido al actualizar.
- NBIS: alternativa249.835-250 YA estaba en09-32; OI250 si subio10457->13890,
  por tanto no era evidencia literalmente identica. Eso NO demuestra por si solo
  mejora material del plan. Faltaba snapshot de ultima revision RETAIN; ahora se
  guarda junto a su juicio, sin redatar informe ni ITV, y ambos prompts exigen
  comparar ese momento ademas del informe CURRENT. Rank/OI no sustituyen efecto
  en la decision ni ausencia TOP prueba invalidacion. No decidir por una regex.
  Habia ademas contradiccion publicada: resistencia nueva250, motivo Target y
  conclusion aun referian270. Rangos siguen siendo sparse y tipados; al cambiar
  uno, una explicacion conjunta reconcilia Setup/motivos/conclusion sin mover
  otros rangos, stops o puntuaciones. No reemplazo de numeros en prosa por codigo.

Nuevas preparaciones congelan v6+15/16/reader17+override18 y schema18. <=17 intactos.
Un solo repair compartido cobertura/fuentes/coherencia; puede retirar un cambio.
Defectos puramente de cobertura/coherencia/justificacion/selectores no compran Sol
al repetirse: quedan visibles. Riesgo/materialidad/incertidumbre financiera reales
mantienen Sol. Sin cambios de modelos, esfuerzo, concurrencia, timeout ni ITV5.

Verificacion offline: test_review_contract_v18.py, baterias semanticas/routing/
memoria/publicacion:233 pruebas+230subtests pasan en la bateria conjunta,
incluidas23 pruebas nuevas+3subtests; recibos17 reconstruidos exactos.
La bateria ampliada detecto un test legacy dependiente de la fecha real: su fixture
envejecio hasta ITV. Se congelo ese estado SOLO en el test de flags; ITV se prueba
por separado. No se ha cambiado ITV de produccion para acomodar el test.
Sin procesos run_batch/adaptive_stage/run_one activos al activar. Sin publicaciones
ni regeneraciones: los informes/recibos auditados conservan su contenido original.
Pendiente medir juicio real en siguiente lote NATURAL18; tests no garantizan
ausencia de futuras omisiones o decisiones financieras equivocadas del modelo.


## Correccion activa 08-10: CCJ / madurez de reaccion historica

Auditoria del lote natural2026-10-08/09-32-38:46/46,35retain,6Luna,
5Sol,0fallidos. Usuario autoriza corregir SOLO el calculo de CCJ tras discutir
el balance. No se alteran estrategia17, prompts, niveles, puntuaciones ni modelos.
Raiz: _historical_support_reactions admitia una sola barra posterior en un
estadistico denominado max_high_5_sessions, contando tests aun inmaduros.

Ahora solo ventanas completas de cinco sesiones cerradas entran en TODOS los
estadisticos (contador, defensas, tasa, mediana, maximo y ultimo test). Ventanas
parciales son pending_test_count, con fecha y sesiones observadas, no exitos ni
fracasos. Precios incompletos se excluyen aparte; sin muestra completa se informa
unavailable, no cero defensas. Raw y slim transmiten observation_policy y horizonte.
No es una regla de esperar cinco velas para operar ni confirmacion de ruptura:
solo respeta el horizonte de ESTA medicion. No comparar cifras antiguas sin esa
politica como prueba automatica de cambio de respaldo; no restaura puntuaciones.

22 pruebas focales (18 nuevas) y bateria ampliada67 +86subtests correctas;
17 casos fallaban antes de corregir. Incluyen 0..5 sesiones, rebote favorable y
desfavorable, sesion actual, datos ausentes, muestra vacia y paso raw->slim.
Desplegados raw y slim complete-window-20261008,100% trafico verificado ambos.
CPU/memoria/timeout/maxScale y secretos conservados: raw1CPU/256Mi/120s/1;
slim1CPU/512Mi/120s/20. Rollback disponible en raw-nanfix0918 y slim-vp1.

Verificacion real sin modelos: scripts/verify_support_reaction_maturity.py,
respuestas en logs/incidents/20261008-ccj-reaction-maturity/raw.json y slim.json.
Ambos CCJ wall90:8/16 defensas(50%),ultimo test COMPLETO30Sep/rebote5.08%;
test06Oct pendiente con1sesion. Antes lo contaba dentro de17 y mostraba47.1%.
8 niveles comprobados por capa. GET tecnico actualiza su mirror normal; no se
generaron/publicaron informes, no se tocaron snapshots congelados ni anclas.
El informe CCJ publicado conserva su67: no se reescribe a70 ni se relanza lote.
Medir conducta de Luna en siguiente lote natural; esta prueba certifica el dato,
no promete decisiones futuras de modelos. APP/HOOD/CRWV fuera de este cambio.

## Incidente 08-10: Gateway / cierre asincrono WinError5

Orden20261008-073425-499-market-3f0c00fb fallo en ensure_gateway ANTES del
lote/modelos. Log ibc-20261008-093507-007133: rechazo ibg.xml; recuperacion
terminaba su arbol y consultaba imagen de Java en rundown, WinError5.
La primera prueba real de reparacion reprodujo otra ventana de la MISMA
carrera: TerminateProcess sobre Java ya terminando devolvio acceso denegado.

windows_processes consulta estado antes de imagen, y si imagen/terminacion
fallan espera salida confirmada en el MISMO handle y plazo global15s. Solo
una salida confirmada se omite; denegacion persistente, enumeracion incompleta,
PID reutilizado o imagen ajena NO autorizan matar/ignorar/arrancar duplicados.
Recuperacion espera su propio launcher antes de limpiar hijos restantes.
No ACL modificadas, Java por nombre, privilegios globales ni modelos alterados.

38 pruebas focales (18 procesos,16 Gateway,2 news recovery,2 fail-closed).
Una usa un hijo Python propio que sale naturalmente: consulta de imagen del
muerto devuelve WinError31 aqui; funcion corregida reconoce salida. Los casos
WinError5/rundown tambien tienen regresiones simuladas. Verificacion real:
scripts/verify_ibkr_cold_starts.py --private-desktop termino exit0. Ciclo1
restarted:profile_recreated:started, log ibc-20261008-102521-519222.log;
ciclo2 restarted:started, log ibc-20261008-102618-014338.log. Ambos API sana,
sin aviso de recovery en arranque sano,0ventanas interactivas/15privadas.
Gateway queda operativo; orden fallida NO relanzada. Tambien se cubre salida
entre enumeracion/OpenProcess con handle SOLO SYNCHRONIZE: nunca omitir una
denegacion salvo prueba de salida, nunca adquirir permiso de matar por fallback.

Copia previa intacta en logs/incidents/20261008-gateway-access-denied/
profile-before-verification. Archivo rechazado preservado bajo
.local/ibgateway-settings-archive/*-rejected-20261008-102519-476717.
Esto arregla el recuperador; NO demuestra causa interna del rechazo cifrado
ibg.xml. Promover tmp con cabecera valida no probo que Gateway lo aceptara:
la primera prueba lo promovio y fue rechazado igualmente. No inventar que
la suspension, credenciales o ACL del archivo causaron ese rechazo.
No lote relanzado, modelos, publicaciones ni checkpoint cambiados.

## Vigente 08-10: revision17 / informe de lectura, no diario de depuracion

Usuario abrio CAT y pidio limpiar el texto. Causas: quote serializado como JSON,
links escapados mas URLs crudas duplicadas, resumen sin parrafos y relato de
correcciones/aritmetica de la rubrica dentro del Plan. Nuevas preparaciones17
anaden report_reader_style.md a AMBOS modelos y render legible: enlaces nombrados,
parrafos separados, sin JSON de quote, prefijos de continuidad repetidos ni
desglose/factors publicos. Componentes/factors/fuentes siguen integros en JSON.
No cambian niveles, puntuaciones, modelos, ITV, rutas ni memoria16. Contratos
<=16 conservan render anterior; no llamadas extra ni filtros estilisticos.
Prosa heredada no se regenera por estilo; full Sol la mejora cuando corresponda.

CAT21-27 corregido AHORA en la vista HTML del enlace de la hoja. Edicion de
lectura acotada por hash en config/report_presentation_CAT_20261007.json; numericos,
fechas y advertencias importantes conservados. Script refresh_report_presentation
genera reader.md/html, comprueba JSON/HTML remoto frente a local y generation,
guarda backup local y publica SOLO latest.html con precondicion de generation.
Lectura remota posterior identica. Canonical latest.md/json, current/ancla,
recibos y snapshots historicos NO cambiados. No reanalizado ni redatada ITV.
Vista reducida de16055 a7581 caracteres; sin JSON, sumas ni enlaces duplicados.
Si el usuario se refiere a la app Android (no respondio aun), esa vista lee el
Markdown canonico y NO ha sido migrada aqui. No afirmar que el APK fue actualizado.

76 pruebas offline correctas:4 nuevas reader + HTML/semantica/memoria16/deltas.
Verifican numeros/fechas/fuentes intactos, links seguros, render viejo exacto y
overlay incapaz de editar precios/puntuaciones/fechas. No pruebas modelo/lote.

## Historial revision16

## Vigente 08-10: revision16 / continuidad y significado del dato

Ultimo NATURAL auditado: 2026-10-07/21-27-11,46/46 publicados,36retain,
6Luna(COIN,CRDO,HIMS,KTOS,MRNA,USAR),4Sol(CAT,GOOG,RKLB,SPCX),0fallidos.
Una correccion Luna KTOS (scope); ningun Sol por ITV/rechazo mecanico.
GOOG/SPCX defendibles (SPCX omision, no proyecto nuevo); CAT discutible por
exposicion no establecida; RKLB titular generico05Oct no identificado ni por Sol.
HIMS/CRDO notas acotadas; MRNA ya evaluada16-35; USAR aclaracion perdida por
sustituir nota; COIN vencimiento dominante confundido con exclusivo; KTOS movio
zona siguiendo minimo aun en primer test. Publicado no significa bien juzgado.

Nuevas preparaciones16: v6+overrides15/16 AMBOS modelos; <=15 quedan exactos.
Luna6high/Sol6.1high, ITV5, concurrencia6, timeouts, una correccion y autoridad
financiera SIN cambios. Sin cuotas, filtros de prosa/puntuacion o mas llamadas.

review_memory: estado publicado current tambien para RETAIN, ligado al informe
y ancla con integridad. No redatar ni resetear ITV. Fuentes exactas, assessments
historicos y extractos separados; mismo ID con contenido distinto no es identico.
No-search posterior no borra research. Memoria plana deduplicada sin grafos ni
cuota; full Sol la recibe y empieza nueva epoca. No es un veredicto cacheado ni
verificacion independiente. Publicacion antigua no pisa revision mas reciente.
news_note fechado persiste separado del routine_note tecnico. Un cambio tecnico
NO borra aclaraciones. Luna mantiene resumen acumulativo si una novedad util lo
justifica; note_history interno fechado, no lista creciente visible. Render sin
duplicados. Full Sol reconcilia las aclaraciones con el nuevo informe.

comparison.technical_evidence_semantics documenta productor, sin tocar snapshots:
TOP wall agrega OI/gamma por strike multi-expiry; expiration es dominante, no
prueba de desaparicion del resto. Desglose ausente no es cero. Extremos moviles
Donchian/anuales y primer test no demuestran por si solos nuevo rol/defensa/rotura.
Instrucciones: justificar cambio antes de elegir alternativa; scope/pointer no
autoriza repuntuar componentes. Escalada requiere conexion concreta al ticker y
conclusion afectada, no cuerpo inaccesible/titular generico; riesgo directo material
sigue Sol incluso sin dano confirmado. Memoria/contrato no prueban toda la prosa.

Pruebas offline:216 integracion/semantica/politica (incluye16 nuevas16);208
adaptativas correctas tras activar16 (baterias solapadas, no sumar). Contratos15
reconstruyen hashes originales46. No modelos/research/lotes/uploads/recuperaciones,
ni procesos/Gateway. Informes publicados NO reescritos. Medir siguiente NATURAL16;
no prometer juicios futuros desde mocks. Revision15 SPCX previo no fue recuperado:
el nuevo lote21-27 si publico SPCX, son ejecuciones distintas.

## Historial revision15

## Vigente 07-10: revision15 / auditoria Luna-Sol y fuentes sin recursion

Ultimo lote NATURAL 2026-10-07/16-35-33: 18:35-18:50 Madrid, 45/46 publicados,
38 retain,5 Luna(CCJ,IREN,MP,USAR,NVDA),2 Sol(INTC,TSM); fallo SPCX. Sol fue por
Terafab; esto no certifica todos sus hechos ni los cinco cambios Luna.
SPCX NO llego al modelo: input2934067 caracteres > limite servicio1048576.
Raiz comprobada: full Sol13-40 selecciono bloques de informe antiguo en facts;
scalar_pointers expandio tambien facts/resolved_facts de la auditoria anterior.
Esa trazabilidad se convirtio recursivamente en hechos nuevos y engordo el input.
Reintento termino call_already_reserved_no_duplicate: no confundirlo con causa.

NUEVAS preparaciones15 conservan v6 + prompts/adaptive_revision15.md congelado
para AMBOS modelos. <=14 inputs/prompts/schemas/recibos no se reinterpretan.
No se recupero SPCX ni se republico ningun informe. Medir siguiente NATURAL.
Modelos Luna6high/Sol6.1high, ITV5, concurrencia6, una correccion, timeouts y
rubrica SIN cambios; ninguna nueva llamada/cuota/fallback ni puerta de prosa.

15 separa vista financiera de auditoria: verifica envelope ORIGINAL local antes
de construir input; conserva Markdown completo, snapshots, fuentes y juicios.
Source_catalog historico contiene range/reason/strength, no grafos internos.
normalize_plan no expande auditorias como hechos; serialize_model_input omite
envelopes duplicados y trazabilidad interna, NO autentica una copia recortada.
Originales completos quedan en input.json; binding local conserva su autoridad.
COPIA SPCX15:139716 caracteres;46 entradas examinadas, max225096(AMD), ninguna
excede maximo servicio. Copias offline, NO recibos15 ni predicciones del modelo.

update.change_review extiende materialidad a setup/conclusion/routine_note;
scope fundamental_or_structural fuerza Sol aun si risk falso; essential_data
sigue blocked. Fuentes current/previous validas, pure justificacion persistente
falla visible sin comprar Sol. No comprobacion de palabras/puntuacion. Aun es
juicio del modelo clasificar bien: NO garantiza verdad semantica de toda prosa.
maintenance_handoff lleva propuestas rechazadas y TODOS errores de cada intento,
marcados no publicados/no verificados. Sol recibe instrucciones para reevaluar.
News15 conserva observaciones y snippet util: apertura con 'Total lines' no lo
sobrescribe. Captura citas de todos los assessments; interpretacion Luna separada.
INTC real: logs NO contienen texto de pagina, solo snippet+metadata. Se indica
page_content_available=false y verificar fuente si material; no inventar texto.

Verificacion: baterias offline256/208/64 correctas (con solapamiento, NO sumarlas
como tests distintos), incluidas17 nuevas15. Cubren SPCX/INTC originales,
contratos14 exactos, fuentes, cinco generaciones sin crecimiento recursivo,
protecciones, scope, correccion, retiro, ITV y handoff completo. Un test de politica
activa seguia esperando13 desde antes de este cambio; ahora espera15, sin alterar
sus expectativas de modelos/effort/ITV. Ninguna llamada modelo real ni publicacion.

## Historial revision14

## Vigente 07-10: revision14 / motivo del cambio separado del nuevo origen

Activa SOLO nuevas preparaciones: *_semantic_v6.md / contrato v6. Frozen <=13
conservan sus prompts/schemas/inputs/recibos. Luna6 high / Sol6.1 high, ITV5,
concurrencia6, timeouts, guardas, rubric y UNA correccion sin cambios.

Ultimo lote natural auditado: 2026-10-07/13-40-06, revision13,15:40->16:00 Madrid,
46/46 publicados,0fallidos/reintentos de lote,41retain/2Luna(CAT,LEU)/3Sol
(GOOG,SPCX,KTOS),20min14s. CAT/LEU tuvieron una correccion cada uno; no fueron
fallos finales. GEV retain. GOOG acuerdo anunciado06Oct12:30 ya suministrado y
mencionado por Luna; texto fundamental seguia en negociacion. NO noticia nueva
de dos horas. SPCX titular FCC07Oct14:58, ausente en captura14:03; cobertura
atribuye aprobacion al06Oct, no confundir entrada al feed con momento del hecho.

CORRECCION DEL DIAGNOSTICO CAT: wall800 estaba en reference, NO en current.
Su triage inicial no la encontro; repair invento que seguia vigente y reutilizo
reaccion vieja, citando s11 = wall810 actual. Mi explicacion anterior de que Luna
corrigio la lectura de una wall800 vigente era incorrecta. LEU sustituyo143.3-144.3
por135.2-136.2 por faltar gap143.845 en lista, admitiendo no probar cierre/ruptura.
No presentar las dos reparaciones como decisiones financieras correctas.

Raiz: politica completa convertia ausencia en nivel huerfano, contradictoria con
estabilidad; validador comprobaba alternativa pero no motivo independiente del
cambio y forzaba ambitious por existir algun soporte inferior. 14 elimina esas
instrucciones y esa ultima puerta mecanica (en Luna Y Sol); idoneidad sigue juicio.
Cada bloque editado Luna (tambien mismos rangos/nueva puntuacion) tiene change_review:
basis, evidencia previous CURRENT/current slim y explicacion. Motivos aceptables:
cambio real de respaldo, error demostrado o mejora material; missing_from_snapshot,
quote_only/no_material_change/unresolved NO autorizan publicar una edicion.
Fuentes cortas verificadas por scope/identidad, historial no se declara live;
auditoria enlazada por hash calculado por codigo, fuera del Markdown y sin anidar
copias recursivas del historial. El motivo NO se valida por palabras/puntuacion.
plan_origin_observations muestra presencia exacta con handles; ausencia UNKNOWN,
no veredicto automatico, no nuevo umbral de precio, no busqueda/modelo adicional.

Una reparacion revisa POR QUE cambiar antes de escoger otra zona; puede retirar
edicion injustificada y retain tras evaluar riesgo. Datos tecnicos ESENCIALES
ausentes: blocked, nunca inventar ni Sol por listado. Si repite SOLO fallo de
justificacion: maintenance_change_justification_failed_no_sol visible; no publicar
ni forzar retain. Errores financieros mezclados mantienen su revision Sol.
La comprobacion tipada verifica motivo declarado y fuentes, NO garantiza verdad
de toda prosa ni detecta todo juicio equivocado de un modelo que clasifica mal.
No afirmar que el esquema prueba semanticamente una invalidacion/mejora material.

421 tests offline correctos:17 nuevos14 +78semanticos +208adaptativos tests/
+80adaptativos root +14stable +21quote13 +3continuidad. CAT/LEU originales intactos;
copias con motivo de ausencia EXPLICITAMENTE clasificado por humano rechazan14,
NO son nuevas respuestas reales ni recibos13 convertidos. Recibos13 reconstruyen
hash exacto. Integra preparacionv6, retiro en unica correccion sin redatar, fallo
persistente sin Sol, riesgo mixto/ITV, protecciones, fuentes falsas y scopes.
Sin modelos/research/uploads/lotes/recuperaciones/procesos/Gateway. Medir siguiente
lote NATURAL; no probar otro lote ni prometer decisiones futuras desde mocks.

## Historial 07-10: revision13 / cotizacion, confirmacion y decision separadas

Usuario exige solucionar la raiz de GEV y reescrituras sin cambio de decision.
Activa SOLO nuevas preparaciones: *_semantic_v5.md y contrato v5. Frozen <=12
conserva sus inputs/prefix/schema/recibos; NO reinterpretar ni republicar el lote.
Luna6 high / Sol6.1 high, ITV5, concurrencia6, timeouts y una correccion intactos.
No nuevas llamadas, umbrales de porcentaje/ATR/cierres, quotas ni puertas de prosa.

Raiz GEV: instrucciones mezclaban ubicacion y ruptura; objetivo se elegia como
siguiente wall sobre el mid, no salida desde la entrada. En10-28-09 target1020
paso a1040 con mid1021.375 (+0.135%), bid1018.76/ask1023.99 atravesando1020,
sin confirmacion nueva suministrada. En11-51-12 volvio a1020 y Setup5.4->5.0.
No atribuir a todos los cambios nuevas noticias ni llamar a ese cruce ruptura.

13 corrige las instrucciones conflictivas de AMBOS modelos: conservar niveles
validos, evaluar salida DESDE entradas, separar ubicacion/confirmacion/accion.
No promover/degradar objetivo o Setup por oscilar sobre una wall. Cruce de una
horquilla, incluso entera a un lado, NO demuestra defensa/ruptura/ejecucion.
Confirmacion requiere juicio sobre fuentes reales, no un patron obligatorio.
Con owned=false stop de gestion es proteccion hipotetica, no orden ejecutada ni
motivo suficiente de reescritura. Guardas de posiciones/riesgo/ITV siguen intactas.
Si solo cambio la frase del precio pero sigue la misma condicion/decision,
retain con fecha/precio originales. Un cambio REAL de condiciones, error previo,
respaldo perdido, riesgo o aclaracion documental importante sigue siendo accionable.
Conclusiones nuevas deben expresar decision/condiciones, no ubicacion transitoria.

comparison.plan_quote_observations deriva posiciones exactas old/current y
solape de bid/ask respecto al plan AUTENTICADO. Es observacion, no trayecto,
ruptura confirmada, fuente/origen live, clasificador de relevancia ni routing.
No borra datos ni cambia schemas, rubrica o decisiones devueltas por el modelo.

Otro problema raiz: update solo de noticia heredaba conclusion antigua bajo
fecha/precio nuevos. 13 guarda conclusion_provenance original por codigo y la
muestra fechada; sucesivos updates NO renuevan esa procedencia. Conclusion
realmente revisada usa nuevo snapshot. Sin analizar palabras ni reescribir texto,
hash queda en auditoria no vista. Estado del plan rotulado 'en el snapshot', no
confirmacion. Render y schemas <=12 mantienen sus etiquetas/contratos anteriores.

Ultimo lote NATURAL: orden20261007-114837-543-market-dabb3e9c,
logs/batch/2026-10-07/11-51-12, revision12,46/46 publicados,0fallidos/reintentos/
correcciones Luna; UTC11:51:12->12:10:49 (~19min37s). 38retain/6Luna/2Sol.
Luna GEV unico cambio numerico; AMAT/INTC/TSM/MRNA/USAR solo notas/conclusion,
con entradas/stops/objetivos/notas intactos. USAR aclaro venta fiscal RSU y tenencia
posterior, no compra. Sol MU nueva autorizacion de huelga; TSLA aclaracion Terafab
sin acuerdo/alcance economico: NO dar ambos como necesariamente justificados.

Verificacion404 tests offline correctos:208 adaptativos tests/,78 semanticos,
80 adaptativos root,14 estabilidad12,21 nuevos13 y3 continuidad. Incluye lectura
sin cambios de46 originales, hash EXACTO de inputs/recibos12 para los seis casos,
quote ambiguo GEV, stop INTC sin posicion y guarda con posicion, noticia USAR,
retain sin redatar, actualizaciones dispersas, una correccion, Sol/ITV/integridad,
primera generacion sin base y procedencia de conclusiones sucesivas.
Modelos/publicacion de integracion SIMULADOS. No ejecucion real de modelos,
research, uploads, lote duplicado, recuperacion ni cambios de procesos/Gateway.
No afirmar que pruebas/mocks demuestran futuras decisiones Luna. Medir13 en el
siguiente lote NATURAL; no prometer que nunca aparezca otro error de juicio.

## Historial 07-10: revision12 / mantenimiento estable y fuentes cortas

Usuario autoriza conservar niveles/notas salvo cambio util; no optimizar de nuevo
por variaciones minimas. Activa SOLO nuevas preparaciones: contratos *_v4.md.
Frozen <=11 siguen inputs/prefix/schema/recibos originales; no reinterpretarlos.
Luna6 high /Sol6.1 high, ITV5, concurrencia6, timeouts y UNA correccion intactos.
Sin quota, umbral porcentual, redondeo automatico ni llamada adicional.

Raiz34 updates: contrato anterior exigia reconstruir los cuatro bloques y
permitia refresco/recalificacion sin efecto operativo. Ahora update es disperso:
null hereda bloque autenticado, Setup y conclusion; solo se generan los cambios
necesarios. Precio/fecha/spread/retocar texto/ranking o reinterpretar igual evidencia
NO son por si solos motivo de update. Mismos origenes conservan rangos EXACTOS
y notas salvo error demostrable; nueva zona requiere mejora MATERIAL o invalididad.
Comparar primero CURRENT: deltas desde Sol ya incorporados no son nuevos.
Cruce operativo, cambio real de respaldo, error demostrado o informacion rutinaria
importante pueden actualizar; riesgos/guardas/ITV siguen Sol. Null ambicioso hereda;
retirarlo exige bloque completo range/strength null. Setup ambos null o ambos datos.
Propuesta completamente vacia se conserva sin nueva fecha ni correccion pagada.
Hechos heredados quedan fechados/historicos con hash del informe origen: no live.

ASML: no pedir hash largo como direccion fuente al modelo. Catalogo reconstruido
de originales ofrece claves cortas s1,s2,... ligadas al recibo/input REAL; no indices
contados, hash transcrito o remapeo aproximado. Sources son objetos completos.
Schema normal es ESTABLE entre tickers (sesiones/cache); SOLO la correccion
enumera claves exactas validas para impedir repetir selector inexistente.
Si tras la unica correccion persiste SOLO selector inexistente, fallo visible
maintenance_source_selection_failed_no_sol, no informe Sol para ocultar transporte.
Errores financieros mezclados, origen perdido, expiraciones y riesgos NO se
clasifican como fallo mecanico inocuo y conservan su ruta de revision.

Ultimo lote NATURAL terminado: orden20261007-102541-336-market-dc72a2e6,
logs/batch/2026-10-07/10-28-09,46/46,0fallidos,9retain/34Luna/3Sol.
Sol ASML evitable por selector truncado, OKLO incertidumbre documental de ventas
ya suministradas, SPCX financiacion material pendiente de incorporar (previo fallo).
Luna34:8cambios niveles,21solo notas/componentes,5solo texto/datos; no34novedades.
Mediana delta precio0.17%,26/34<0.5%; snapshots~76min de mediana.
No se reescribio/publico este lote; solo COPIA de ASML prueba contrato nuevo con
rangos/componentes/Setup intactos. Recibos/copias de prueba sinteticos no autorizan
publicacion. Probar integracion real en siguiente lote natural, no duplicado.

Verificacion:354 tests bateria focal de mantenimiento/fuentes/policy/binding/fechas,
tests nuevos de sparse, preparacionv4, modelos SIMULADOS, repair/Sol/ITV/retain,
no mutacion, auditoria fechada y originales ASML. Sin modelos/research/uploads.
Suite global detecto expectativa legacy de modelo5.6 en test_analysis_profiles
(produccion ya6.1, no cambiado aqui); test Windows process_control falla dentro
del sandbox pero PASA aislado fuera del sandbox, sin cambio de ese codigo.
No afirmar toda la suite global verde ni que el ahorro real ya esta medido.

## Nota compacta C4 desplegada 07-10

Usuario aprobo cinco lineas: Mercado en curso · N/total publicados;
Luna: conservados/actualizados; Sol: informes completos;
Fallidos/reintentos; tiempo transcurrido/restante estimado (~).
Sin duplicar Publicados ni mostrar preparados/validados/listas de trabajadores
en vista sana. Cifras siguen siendo RESULTADOS PUBLICADOS, no llamadas pagadas.
Conservado significa revisado por Luna y mantenido. Reintentos Codex usa
pipeline_retries, nunca basura Web legacy. Ceros visibles; reparto ausente
se marca pendiente, no se inventa. Desclasificados/failed tickers siguen visibles;
sin senal conserva advertencia, ultima actividad y hora en TZ de la Sheet.

Solo analysisCodexProgressNote_ en apps_script/analysis_completion_sync.gs.
Legacy Web y resumen final intactos. Cuatro suites Node correctas: progreso/C4,
resumen final, menu mercado, targets/notas. Ejemplo3/46 reproduce cinco lineas;
singular/plural, ETA desconocida, estados failed/completed/stale y no mutacion.
Deploy con push_apps_script_file: doble pull/diff, unica funcion cambiada;
readback remoto igual byte a byte a local,14 otros archivos remotos intactos.
Backups/verificacion: .tmp_apps_script_push/20261007-123809/{original,work,verified}.
Proyecto configurado apps_script/.clasp.json (no ID historico de operations).
Se vera al siguiente refresco natural de C4, sin forzar ejecucion del script.
No modelos, pruebas de lote, checkpoints/publicaciones, procesos o Gateway.

Comprobacion adicional fuera de este cambio: test_next_earn_fallback.js falla
con borrador local fuerza.gs (espera '?' y recibe ''), pero pasa con fuerza.js
remoto ORIGINAL. No se modifico/subio ese borrador; no afirmar incidencia nueva
de produccion por esa diferencia ni que toda la suite local JS esta verde.

## Presentacion corregida 07-10: informe humano separado de auditoria

El usuario mostro plan INTC con93 lineas de Evidencia actual, JSON completos y
rutas /slim/...: NO lo pedia el modelo, lo volcaba render_document desde
resolved_facts. Error de separacion de capas, no motivo para quitar validacion
financiera, fuentes o pedir un nuevo analisis al modelo.

Renderer ya NO imprime resolved_facts/records/punteros internos en el plan.
Siguen completos en semantic_report.data.plan, con identidad/fecha/origen actual
o historico y hash de antecedente. Mantiene niveles, porcentajes, continuidad,
motivos, fortalezas/desglose/factores y campos protegidos. Cada nivel ahora tiene
subtitulo y parrafos separados; HTML ya no los aplasta en un unico parrafo.
No hay schema/prompt/modelo/routing nuevo, ni truncamiento o resumen financiero.

INTC original re-renderizado SOLO en memoria:15598->4011 caracteres en Plan
(-74.3%),93 lineas internas fuera de la vista,138 facts retenidos en auditoria.
Publicaciones/recibos originales intactos. No modelos ni uploads, migracion de
informes historicos, procesos o lotes. Se aplica a futuros renders Luna/Sol;
un retain conserva su Markdown publicado antiguo, no lo migra automaticamente.
432 tests offline correctos (345 tests/ incluidos HTML +80 root +7 formatos),
5 regresiones nuevas de presentacion: ambos modelos, HTML real, no mutacion,
persistencia de auditoria/numeros y original INTC sin editar artefactos.

## Estado vigente 07-10: revision11 / contratos raiz RDDT, AUR, SPCX

Activa SOLO para nuevas preparaciones: semantic contract v3, prompts nuevos
*_semantic_v3.md / semantic_report_contract_v3.md. <=10 conserva sus inputs,
prefijos, schemas y recibos: JAMAS corregir su hash/respuesta en disco o
reetiquetar recibos viejos como11 para publicarlos. Modelos Luna high /Sol6.1 high,
ITV5, concurrencia6, timeouts, guardas y una correccion Luna sin cambios.

Ultimo lote TERMINADO: orden20261007-091005-371-market-338f5931, carpeta
logs/batch/2026-10-07/09-12-17. Resultado FAILED:44/46 publicados,3 conservados,
37 actualizados Luna,4 Sol publicados (MRVL/NVDA/MU/RDDT). Fallidos AUR y SPCX,
dos reintentos de lote que reutilizaron respuestas y repitieron el mismo error.
SPCX tambien genero un Sol, pero NO lo publico: no sumarlo a los4 publicados.
Heartbeat final2026-10-07T09:33:41.471586+00:00. No recuperados en este trabajo.

RDDT: propuesta y correccion Luna validas citaban /source_catalog/ID/value...
y /source_catalog/ID. Contrato10 solo aceptaba ID/campo o puntero original:
incoherencia entre catalogo JSON de entrada y resolucion, NO cambio critico.
11 define direccion canonica /source_catalog/ID/value[/campo], aliases de nodo
y handle exacto; mismo resolver en normalizacion, validacion y evidencia/URLs.
Reconstruye catalogo desde originales; metadata /pointer no es evidencia,
IDs/campos inexistentes siguen rechazados, sin adivinar offsets o vecinos.

AUR: Luna omitio un caracter del hash (63/64), invalid_update_base_hash en ambos
intentos. 11 elimina ESE campo del schema/salida del modelo; runner verifica
input_sha256 del recibo REAL y vincula respuesta JSON exacta a base/ancla/fuentes
congeladas antes de adjuntar research. Sustitucion de respuesta, recibo ajeno o
autoridad cambiada rechazan sin llamada automatica. Publicacion mantiene control
de base/ancla actual/nueva. No inferir el hash ni corregir el recibo10 original.

SPCX: Sol valido citaba stops anteriores164/104.5 mediante /reference/plan/...
en facts. Contrato10 solo admitia facts slim/snapshot, confundiendolos con pruebas
actuales y rechazando update_not_allowed_unproven_technical_fact_source.
11 separa historical_report: datos del informe autenticado, fecha de informe y
hash en auditoria estructurada (ya no volcado en vista). Nunca origen live.
Espejos JSON antiguos y semantic_data cacheada no son autoridad: se verifica
semantic_report persistido contra datos/Markdown o se importa Markdown legacy.
No permite a Luna modificar stops/tesis ni autorizar zonas nuevas sin origen live.

MRVL/NVDA/MU tenian ultima ancla Oct5, no un Sol nuevo de hacia una hora:
fallaron en lote07-50-26. Nuevas noticias: InvestorDay/targets MRVL, acuerdo
Netlist MU y propuesta material de financiacion de chips NVDA. SPCX escalo por
esa propuesta de40B; no convertir propuesta en deuda emitida. RDDT fue evitable.
Los cinco fallidos07-50-26 (incluidos QCOM/GOOG) fueron publicados en el NUEVO
lote09-12-17: no reanudar el antiguo para volver a publicarlos.

Verificacion offline:423 tests (336 tests/ +80 root +7 formatos),22 nuevos de11.
Incluye Luna/repair/Sol/retain/ITV, preparacionv3, transporte lossless,
prohibicion de publicar base/ancla alterada, negativos de integridad/fuentes.
COPIAS de propuestas originales AUR/RDDT (ambas)/Sol SPCX pasan11 sin cambiar
rangos, razones, puntuaciones o rubrica. Se omite hash solo en COPIA del nuevo
schema; recibos11 sinteticos offline, NO recibos10 reinterpretados o publicados.
Originales intactos; AUR10 sigue rechazado bajo SU contrato.
Medida readonly46 inputs:11 suma mediana1.81% de bytes empaquetados respecto10
(mediana3686 bytes,max2.35%). No es medida de tokens/cache reales ni promesa
de ahorro. No modelos, research, uploads, pruebas de lote, recuperacion o cambio
de procesos/Gateway. Monitor anterior sigue PAUSED. Medir siguiente lote NATURAL.

Las secciones siguientes son historial de despliegue y evidencias anteriores;
no son instrucciones de recuperar lotes antiguos ni el estado vigente.

## Historial 07-10: revision10 / fuentes por identidad y continuidad por codigo

Activa SOLO para nuevas preparaciones. No reinterpretar checkpoints/recibos <=9
como revision10 ni sustituir sus prompts/schemas. Modelos Luna high /Sol6.1 high,
ITV5, concurrencia6, timeouts, guards y una correccion dirigida Luna intactos.
No cuotas, minimos de busqueda, sustituciones ni llamadas extra.

Raiz de seis escaladas evitables del lote 07-50-26: contrato9 obligaba al modelo
a contar posiciones de arrays y citar escalares, rechazaba comparison auxiliar,
pedía una etiqueta redundante transition y solo mostraba el primer error. CRDO
tenia ademas la misma URL SEC con CIK numerico con/sin ceros a la izquierda.
No eran seis cambios criticos del negocio ni problemas de puntuacion.

Nuevo source_catalog: IDs compactos ligados a scope/grupo/contenido completo;
seleccion de registro/objeto o campo, no recuento de indices. Se reconstruye de
originales congelados, nunca del catalogo devuelto por el modelo. Un handle
inexistente/colision/fuente ausente sigue siendo error: NO se remapea un indice
al vecino ni se inventa origen. Objetos facts se expanden mecanicamente a
valores originales con identidad/expiry e historial. Una misma fila de opciones
se imprime una vez, no una vez por metrica; datos tipados completos permanecen.
transition ya NO es campo de salida: codigo deriva continuidad de rangos exactos,
sin elegir precios/fortaleza. comparison es auxiliar, nunca origen/fact live.
Una correccion recibe errores independientes de fuentes y bloques juntos;
una violacion de esquema sigue fallando antes. No prometer lista de todo error
semantico posible: no hay un juez mecanico de toda la prosa.

URL identity comun a tool provenance/validacion10: solo CIK numerico EDGAR
se normaliza para el mismo HTTPS/host/accession/documento/query/fragmento.
Conserva URL realmente observada; no redirects, aliases de host ni links en
snippets autorizan fuentes. URL recuperada no prueba la verdad de la noticia.
WDC: instrucciones generales separan propuesta/exposicion real/mitigantes;
capacidad interna/overflow sustituible puede ser observacion rutinaria acotada,
pero amenaza creible a insumo critico/central puede exigir Sol antes de cierre
o dano realizado. NO se fuerzan flags ni se clasifica WDC automaticamente.

Verificacion offline: 401 tests correctos (314 tests/ +80 root +7 formatos),
22 nuevos tests de contrato10 y extension de transporte de ambos modelos.
Evaluacion en COPIAS de respuestas9: CRDO/LRCX/CIFR pasan con contrato10 y fuentes
identificadas; IBKR/AMD/NBIS pasan seleccionando por identidad las walls auditadas
84/600/210 (antes indice5 inexistente, realmente4). Solo en evaluacion se expresa
esa seleccion conocida: produccion JAMAS adivina un offset. Rangos, puntuaciones,
razones y otras decisiones financieras de esas seis propuestas intactos.
TSLA sigue rechazado: origen actual AVWAP352.3704 no respalda zona360-361.
Es replay contrafactual, NO resultado de un nuevo modelo ni recibos9 ahora validos.

Medida readonly sobre46 entradas: catalogo suma mediana10.07% de bytes de input
empaquetado (7.01%-13.39%, media16274 bytes). No truncamiento; aliases lossless,
schema/prefix estables sin enums por ticker. Ahorro neto/cache/conteo Sol debe
medirse en siguiente lote NATURAL, no se garantiza por bytes o mocks.
Prompts nuevos *_semantic_v2.md y semantic_report_contract_v2.md. V1 intactos.

Lote anterior sigue 41/46 publicado, cinco fallidos NO recuperados (detalle
debajo). No hubo modelos, research, uploads, recuperacion, pruebas de lote ni
cambio de procesos/Gateway en este trabajo. Monitor sigue PAUSED.

## Estado vigente 07-10: corregida regresion de notas de routing revision9

Orden 20261007-074725-433-market-b0532be0, lote 2026-10-07/07-50-26:
terminado FAILED, 41/46 publicados (30 Luna updates /11 Sol /0 conservados).
Cinco fallidos: MRVL, NVDA, MU, QCOM, GOOG. Todos con
invalid_maintenance_edits_without_update, tambien en sus cinco reintentos de
lote, anteriores a esta correccion. No confundirlo con fallo financiero/modelo.

Causa: revision9 delegaba routing al contrato antiguo de ediciones revision8;
ese contrato trata routine_note no vacia como una modificacion aunque decision
sea escalate/retain/blocked y update=null. Luna dio notas explicativas validas.
La revision9 ya NO delega al validador legacy: valida su esquema/evidencias y
usa una funcion comun de decision (guardas/riesgos/incertidumbre/gaps). Solo
update explicito autoriza cambios, nunca una nota. Notas originales intactas,
legacy <=8 conserva contrato propio. No se vacian notas ni se cambia el prompt,
schema, modelo, hash de recibos, politica, fechas, ancla o ITV para sortearlo.

379 pruebas offline correctas: 292 tests/ +80 root adaptativos +7 formatos.
Incluye cinco pruebas nuevas y fixture de retain con nota, decisiones distintas,
proteccion de autoridad/evidencias, integracion escalate->Sol sin correccion Luna
y replay readonly de respuestas originales MRVL/NVDA/MU/QCOM/GOOG sin editar
artefactos. Salidas de mock T0..T5 NO son una ejecucion de modelos reales.
MRVL/NVDA/MU/GOOG ahora enrutan a Sol y QCOM a retain con SU respuesta original.

Codigo corregido, resultados del lote NO recuperados ni republicados aqui.
No se lanzo/reanudo ningun lote, modelo o research; no se paro ningun proceso.
Para recuperar usar SOLO ese checkpoint con recibos originales, no regenerar
los 41 publicados ni repetir Luna. Confirmar ausencia de otro lote antes de
recuperar y conservar controles de edad/publicacion. Cuatro Sol seguirian
siendo llamadas necesarias; QCOM no requiere modelo nuevo. Monitor sigue PAUSED.

La seccion del 06-10 detalla la arquitectura revision9; su ultima evidencia de
lote era anterior a este primer lote natural con JSON. Tests no son prueba de
recuperacion publicada ni garantia de cero errores futuros.

## Estado vigente 06-10: revision9 / contrato financiero estructurado v1

El usuario exige quitar la dependencia de frases/puntuacion de raiz, no ampliar
regex. Config routing_revision9 activa SOLO nuevas preparaciones. Luna high /
Sol 6.1 high, ITV5, concurrencia6, timeouts y correccion Luna unica intactos.
No cuotas, limites nuevos, busquedas obligatorias ni sustitucion de modelos.

Flujo nuevo, tanto Luna como full Sol: JSON financiero -> controles de datos ->
render Markdown/HTML y espejos JSON por codigo. Nunca validate_markdown para
estos candidatos, tampoco despues del banner Luna ni en auditoria de revision9.
No before/after, matches de texto, etiquetas dictadas al modelo, formulas de
continuidad o numero de frases/delimitadores. La prosa libre no determina validez.
El motor deriva fecha/precio/snapshot/cotizacion congelada/posicion/porcentajes,
total/categoria de fuerza y numeros anteriores EXACTOS. El modelo puntua los
cinco componentes con la MISMA rubrica, no devuelve suma/categoria duplicadas.

Luna devuelve update con Setup y CUATRO bloques tecnicos completos (Entrada,
ambiciosa, resistencia, objetivo) y conclusion. Tesis/motivos/narrativa,
catalizadores/evento y ambos stops/motivos los copia codigo desde base verificada;
no hay campos de update que autoricen cambiarlos. Hash base sigue estricto.
Rangos positivos/ordenados, transicion numerica real, pilares/maximos y geometria
siguen controlados. Nuevo nivel Luna exige origen vigente bajo el mismo gate
previo; no imponer ese registro de proximidad a full Sol (su autoridad es mayor:
retest de antiguo techo o HVN no es automaticamente un origen falso).

Hechos tecnicos: pointers escalares a fuente original, no cifras repetidas en
frases. Se copian valor, snapshot e identidad/expiry/metricas del registro de
opciones; se rechazan punteros inventados, expirados/inactivos y copias actuales
contradictorias. Historicos se rotulan explicitamente, no se refrescan como live.
Esto prueba procedencia, no independencia ni verdad semantica de toda la prosa.
Materialidad/incertidumbre esencial siguen juicio del modelo; no prometer cero
Sol ni cero futuros errores financieros. Noticias mantienen web opcional y
procedencia tool real; citas en update tambien se capturan, solo en contrato9.

Persistencia semantic_report v1 guarda datos + SHA datos y SHA Markdown exacto.
Siguientes preparaciones leen esa autoridad; no vuelven a deducir el plan de
prosa. Solo informes legacy se importan una vez en memoria. Verificado importar
las bases reference/Sol de los 46 tickers originales, sin datos obligatorios
ausentes ni editar sus archivos. Espejos/publicaciones historicos intactos.
JSON de app/Sheet conserva schema_version7 y claves anteriores, desde DATOS,
incluido explanation en catalizadores/evento; el raw report.response ahora es
JSON en revision9 y latest.md sigue siendo el informe legible.

Prompts nuevos: stock_analysis_semantic.md (politica financiera/rubrica),
daily_maintenance_semantic.md (autoridad/materialidad), semantic_report_contract.md
(transporte de datos). Prefijos/schema estables entre tickers; Luna y reparacion
comparten contrato. Legacy <=8 conserva instrucciones/esquemas/recibos/hashes;
no migrar ni reinterpretar checkpoints existentes como revision9. Las rutas
individuales/legacy Markdown siguen compatibilidad, no son este motor nuevo.

Verificacion final: 374 pruebas offline (350 anteriores +24 nuevas), incluidas
integracion JSON/HTML/publicacion staging MOCK, source conflicts/expiry, hashes,
precision, prosa arbitraria, transporte versionado, preparacion real con fuentes
MOCK, reintento financiero unico y recovery sin repeticion. Las pruebas fallan
deliberadamente si la ruta9 llama al validador o al constructor de espejos de
Markdown. No llamadas reales, research, Gateway, reinicio de procesos, subida,
recuperacion o lote duplicado. Medir respuesta/calidad/coste del esquema nuevo
en siguiente lote NATURAL; tests no demuestran conducta real del modelo nuevo.
Ultimo lote observado sigue COMPLETED 46/46 (6 conservados /23 Luna /17 Sol),
monitor PAUSED. Reconciliacion remota MRNA historica sigue tarea separada.

Las secciones siguientes son despliegues/resultados HISTORICOS.

## Estado vigente 06-10: revision8 / mantenimiento v9, auditoria del lote cerrada

Orden 20261006-092105-602-market-0823050e, batch 2026-10-06/09-24-30:
COMPLETED 46/46, cero fallidos/reintentos pipeline/fallback. Publicados: seis
conservados, 23 updates Luna, 17 Sol. Llamadas: 44 Luna iniciales, 15 correcciones,
17 Sol; MRNA/SPCX directos por movimiento >=8%, ninguna ITV vencida. El monitor
vigilar-lote-de-mercado-actual esta PAUSED y no cubre lotes futuros.

Usuario autoriza corregir causas comunes tras auditar los 17. Config ahora
routing_revision8 / maintenance contract v9 SOLO para nuevas preparaciones.
Modelos high, ITV5, concurrencia6, un unico reintento Luna y timeouts intactos.
Sin cuotas ni override automatico de escaladas semanticas. Criticos, fuentes
esenciales fallidas, stops protegidos e incertidumbre esencial siguen visibles.

Correcciones verificadas:
- Lector de citas compartido: puntuacion de frase no pertenece a URL desnuda;
  Markdown/autolink y URL devuelta conservan identidad exacta. Solo resultados
  completados realmente observados autorizan fuentes, nunca snippet/prosa inventada.
- Campos de snapshot usan etiquetas comunes, incluida Instantanea tecnica y
  quote Snapshot. Herencia exige timestamp/quote antiguos demostrados; se
  refrescan hora UTC y bid/ask/spread juntos. Datos explicitos falsos, tiempos
  multiples o ambiguos siguen rechazados. Solo metadatos, no nuevos precios web.
- Revision8 deriva precio heredado demostrado, Estado actual posicional y
  porcentajes ausentes de campos numericos completos desde niveles elegidos/
  slim congelado. NO elige niveles, stops, puntuaciones ni origenes; full gate sigue.
- Identidad de wall reconoce precio explicito con calificadores, no cantidades
  de contratos/gamma como strikes. Strike/side/expiry/metricas siguen estrictos.
- Continuidad reconoce verbos sin exigir dos puntos; comprueba valores previos,
  solapamiento y origen. Rebase de motivos heredados usa el mismo reconocimiento.
- Correccion unica recibe chequeo de TODOS los before y diagnostico tipado de
  fortalezas fallidas (componentes, suma, categoria y factores). Sin fuzzy apply,
  sin segunda reparacion ni regenerar por telemetria. No duplica before validos.
- Prompt distingue venta propuesta bajo plan existente, opinion que repite un
  riesgo conocido, adopcion ajena sin transmision y plazo ya vencido antes del
  ultimo Sol. Exige separar necesidad tecnica/stop de materialidad fundamental.
  Requiere verificar identidad/fecha del filing frente al titular, no confundir
  tablas de ventas previas con la propuesta actual. NO garantiza decisiones futuras.
- Token numerico entero antes de interpretar locale: 208.9032 ya no se divide
  en 208.903 + 2. Formato de precios previos conserva precision y desambigua tres
  decimales sin cambiar valor. Revision8 reparsea espejos numericos plan/validation
  en COPIAS desde Markdown original; hashes/fechas/ancla/datos almacenados intactos.
  Se observo MRNA resistance.upper=208903 en espejo derivado, Markdown=208.9032;
  no se reescribieron publicaciones ni historia. Proxima preparacion/proyeccion
  usa los niveles correctos; una reconciliacion remota retroactiva es separada.
- Prueba multiproceso detecto WinError5 al replace atomico por lector Windows.
  Se reintenta SOLO replace de estado bajo el mismo lock durante ventana breve;
  errores persistentes quedan visibles. Nunca trunca estado ni repite un modelo.

Replay completo offline con fuentes web reconstruidas: AMAT repair, SNDK initial,
PLTR initial/repair, TLN initial/repair, NBIS initial/repair y CIFR repair pasan
full validation SIN editar respuesta/input/recibo. CCJ initial conserva error
REAL: total80 vs componentes78 (volumen16 aunque factores expresan18); feedback
ahora muestra discrepancia para que Luna decida la correccion con rubrica.
NO afirmar que el recibo CCJ original ya pasa, ni forzar sumar/reasignar scores.
Se mantiene rechazo real de CIFR initial por soporte inferior omitido y SNDK
repair por before parafraseado. Seis de siete tienen propuesta original validable;
esto no predice la decision de nuevas llamadas ni autoriza republicar historicos.
Los 23 updates Luna publicados siguen teniendo propuesta aceptada en replay.

Verificacion: 208 tests adaptativos tests/, 80 root, 21 validador, 13 schema,
seis scores, diez tolerancia, tres continuidad, dos fechas y siete formatos
previos: 350 pruebas offline correctas (17 nuevas generales/adversariales/recibos).
Las variantes incluyen fuente inventada, query distinta, metrica/expiry falsa,
stop/hash protegido, metadatos no demostrados, UTC, integridad y sharing Windows.
scripts/audit_adaptive_rejections.py ahora reconstruye fuentes tool de cada call;
--evaluate-routing-revision 8 usa una COPIA en memoria, nunca migra checkpoint.
No se lanzaron modelos, busquedas reales, batch duplicado, Gateway, uploads ni
recuperaciones. No se cambiaron resultados publicados, contadores o recibos.
Medir routing/materialidad/coste en siguiente lote NATURAL, no prometer cero Sol.
Las secciones de abajo son despliegues/resultados HISTORICOS, no estado actual.

## Estado vigente 05-10: noticias web opcionales en Luna (revision7)

Usuario autoriza implementar consulta de noticias por Luna. Config vigente:
routing_revision7, luna_news_research_enabled=true, maintenance prompt v8.
Modelos/high, ITV cinco sesiones, concurrencia seis, timeout y reintento unico
no cambian. SOLO nuevas preparaciones; policies/inputs/prefijos/recibos viejos
quedan congelados. Revision<=6 no habilita web Luna aunque una copia de config
incluya la flag. Esquema JSON sigue igual a revision5/6; no campo obligatorio nuevo.

Web se habilita en triage y triage_repair, dentro de la MISMA llamada existente,
solo para aclarar noticia/facto publico especifico necesario. Sin sweep completo,
busqueda obligatoria, minimo/maximo de fuentes, cuotas ni llamada extra de research.
Read-only, shell/apps/otros tools desactivados; no login, formularios, mensajes,
trades ni datos privados en queries/URLs. Snapshot tecnico sigue congelado y
autoritativo; web NO aporta precios/niveles/opciones ni tapa fuente esencial fallida.
Consulta rutinaria resuelta puede conservar/actualizar. requires_research y
evidence_gap=research significan investigacion ESENCIAL pendiente para Sol,
no que Luna haya usado una herramienta. Criticos/contradiccion fundamental,
guardas, ITV o incertidumbre esencial siguen Sol; misma autoridad protegida.

adaptive_news_research captura SOLO URLs citadas por Luna y realmente devueltas
por web tools completados; fecha de retrieval, tool count/hash y provenance de
discovery, NO fact-check independiente. Eventos originales permanecen logs.
news.luna_research agrega metadata recuperable por call kind; interpretacion
permanece separada en triage.news.assessment. NO inyectar prosa del modelo en
raiz de evidencia: una URL inventada alli podria autorizarse a si misma. Links
en titulo/snippet tampoco autorizan citas: solo el source URL observado.
Sol recibe fuentes y assessment cuando escala. Reparacion conserva fuentes
previas; reanudacion reconstruye desde recibo/eventos intactos sin nueva llamada.
Review registra fuentes/contadores. IBKR feed/input original nunca se reescribe.

Cache de DECISION no guarda ni reutiliza turns con busquedas reales (o count
desconocido cuando web habilitada): noticias externas pueden cambiar sin cambiar
feeds congelados. Con cero busquedas medidas se conserva reuse exacto habitual.
Cache de PREFIJO/session limpia sigue estable/compartida para Luna y correccion.
No se prometen tokens ahorrados hasta medir batch natural. No copiar una decision
web vieja como verificacion actual ni tocar recibos historicos.

321 tests offline correctos: 191 adaptativos tests/, 80 root, 21 validador,
13 schema, seis scores y diez tolerancia. 17 regresiones nuevas: transporte CLI
MOCK con web live/ChatGPT auth/read-only/shell off/modelo intacto, schema/prefix
legacy, rutina en una Luna, Sol con fuentes, ITV/guardas directas, fuente truncada,
hash/count de eventos, fuentes observadas/no self-authority, cache y recuperacion.
OpenAI Docs usada: live/disabled confirmado en
https://learn.chatgpt.com/docs/config-file/config-reference . Sin API key/migracion
API/browser, modelo real, research real de tickers, Gateway, subida o batch duplicado.
El nuevo uso REAL de noticias Luna se observara en siguiente batch NATURAL; estos
tests NO prueban outcome/consumo/entitlement real de la cuenta. Estado previo
sigue 44/46, CLS/RDDT sin recuperar/publicar. Lo de abajo es despliegue anterior.

## Estado vigente 05-10: escalada causal, sin cuotas ni nuevas llamadas

Usuario pide corregir escaladas dudosas de raiz. Routing revision6 / maintenance
contract v7 activos SOLO para nuevas preparaciones. Esquema de respuesta igual
a revision5: motivo causal usa reason/assessments/evidence existentes, NO nuevo
campo ni gate de frases/puntuacion. Incertidumbre significa esencial para decidir,
no cualquier detalle ausente. Feed sin cuerpo no obliga research: identificar
riesgo concreto, conclusion afectada y por que retain/update no lo resuelve.
Riesgo adverso directo material puede exigir Sol aun sin cuerpo; no exigir dano
demostrado ni etiquetar todos los anuncios positivos como rutinarios. Distinguir
comentario de hecho nuevo, relaciones especulativas de transmision respaldada,
y titulares repetidos de eventos economicos distintos. No excepciones por ticker.

comparison.plan_source_inventory lista presencia EXACTA dentro de rangos actuales,
con pointers separados a slim actual y reference.slim_snapshot historico. NO decide
independencia, fuerza, vigencia del expiry o perdida global; mirar fuentes completas
y origenes cercanos/movidos. No tolerancias, caps, puntuacion ni routing automatico.
Luna debe quitar peso actual de walls old-only y recalcular bloque completo/Setup;
considerar alternativas permitidas o ausencia real de ambiciosa, nunca inventarlas.

CORRECCION a explicacion anterior al usuario: AVWAP TSLA 351.3628 figuraba SOLO
en snapshot HISTORICO, no en supports actual. Entrada ambiciosa no tiene items
actuales in-range en este inventario. No justificar retain por ese AVWAP ni prometer
que TSLA evita Sol. El helper demuestra presencia, no verdicts de nueva Luna.

304 tests offline correctos: 174 adaptativos tests/, 80 root, 21 validador,
13 schema, seis scores y diez tolerancia. Ocho nuevas regresiones cubren origenes
actuales/historicos, pointers, lossless transport, duplicados, expiry distinto,
precision exacta, schema igual y riesgo/guards/research/essential_data intactos.
Las 46 entradas originales quedan identicas; contextos <=5 no reciben inventario.
Sin llamadas reales/modelos, research externo, Gateway, subida o lote duplicado.
Modelos/high/ITV5/concurrencia6/reintento unico intactos. Prefijo compartido estable.
Observar decisiones/coste en siguiente batch NATURAL, no afirmar ahorro medido
ni numero Sol contrafactual definitivo. Estado previo sigue 44/46, CLS/RDDT sin
recuperacion/publicacion. Lo de abajo registra despliegues anteriores.

## Estado vigente 05-10: causas raiz de opciones, ediciones y routing

Usuario pide corregir TODO y buscar causas raiz, no excepciones por ticker.
En el mismo lote 12-38-33, se identificaron tres fallos comunes del contrato:

- Lector de opciones confundia porcentajes tras 'gamma put' y cantidades de
  contratos tras 'put wall' con strikes. Ahora distingue identidad y metricas,
  resuelve walls sin precio SOLO contra una zona etiquetada con identidad unica,
  y mantiene wall/side/strike/expiry por separado. Walls consecutivos con lado
  elidido heredan solo ese lado, no sus cifras. Comas/puntos y coma no delimitan
  la autoridad de las metricas. Gamma en ambos ordenes y OI (share%) se validan.
  Fechas numericas de expiracion tienen rol explicito; ratios 1/10 no son fechas.
- Ediciones MRNA eran textualmente identicas salvo delimitadores Markdown **.
  Se localiza SOLO campo completo etiquetado/unico, equivalente caracter por
  caracter excepto **; NO busqueda fuzzy ni cambios de numeros/puntuacion/prosa.
  Hash, spans de autoridad, solapamientos, campos protegidos y stops siguen
  estrictos. Rechazo real adjunta indice/before y lineas fuente como feedback,
  nunca como reemplazo automatico. Opciones adjuntan fuentes actuales e historicas.
- 'blocked' confundia noticia investigable con fallo de recoleccion. Nuevo
  routing_revision=5 y maintenance contract v6 requieren evidence_gap tipado:
  none/research/essential_data. research escala Sol; essential_data bloquea.
  Preflight de fuentes sigue ANTES de cualquier modelo. Feed completo solo con
  titulares NO es incompleto por faltar cuerpo; tampoco se declara inocuo.
  Revision <=4 conserva su contrato/blocked original: no editar recibos congelados.

NBIS/GOOG/MRNA/CLS: ambos recibos Luna originales pasan apply_update y validador
completo SIN reescribirlos; INOD inicial tambien. SPCX original del primer lote
pasa y valida separadamente sus dos walls. TSLA NO era solo sintaxis: put $350
09-Oct/OI4412 aparecia en snapshot viejo, NO en fuentes actuales. Sigue
rechazado; feedback permite corregir la atribucion historica y valorar soporte
independiente, nunca inventar respaldo actual. Ausencia de toplist no demuestra
por si sola desaparicion total del soporte. No forzar retain ni quotas Sol.

Verificacion offline: 166 tests adaptativos tests/, 80 adaptativos root,
21 validador, 13 schema, seis scores y diez tolerancia/replay = 296 correctos.
Controles negativos incluyen metricas falsas en TODOS los ordenes/separadores,
OI porcentual incorrecto, wall ambiguo, expiry incorrecta, hash/campo protegido,
before numericamente distinto, fuente truncada y contrato legacy.
scripts/audit_adaptive_rejections.py reproduce solo en memoria, sin modelos,
staging/publicacion. La integracion de research construye Sol bundle con modelo
MOCK; essential_data no llama report, preflight truncado no llama ningun modelo.

Modelos/effort/ITV5/concurrencia6 y reintento Luna unico no cambiaron. Esquema
tipado compartido entre tickers; el prefijo nuevo es estable, no enum dinamico.
Activacion solo nuevas preparaciones naturales. Ninguna llamada real/modelo,
subida ni lote duplicado en esta correccion. NO sustituir Sol publicado por
Luna historico ni alterar contadores retrospectivos. Estado publicado sigue
44/46; CLS/RDDT NO recuperados. El viejo blocked RDDT no se convierte por buscar
palabras en su reason. Recuperacion operativa es tarea separada; no prometer
46/46 ni cero futuros fallos sustantivos. Secciones siguientes son historicas.

## Estado vigente 05-10: lote 12-38-33 y retirada de bloqueos cosmeticos

Orden 20261005-123554-217-market-768681bc terminada a 13:08:49 UTC (15:08
Madrid): 44/46 publicados, CLS/RDDT fallidos. Resultado publicado: 21 conservados,
12 Luna updates, 11 Sol; llamadas: 46 Luna iniciales + ocho correcciones,
12 Sol (CLS no publicado). Cero ITV/guardas directas/fallback/capacidad.
Dos reintentos pipeline repitieron recibos fallidos, no generaron recuperacion.
Dos correcciones evitaron Sol (CRDO/GEV); cinco Sol publicados provinieron de
rechazos rutinarios (NBIS/GOOG/TSLA/MRNA/INOD), seis de escaladas explicitas.

Usuario autoriza arreglar de raiz la familia CLS y quitar validaciones
cosmeticas, no rebajar calidad numerica. ELIMINADO contar 2-4 factores por
puntos y coma: evidencia textual sigue obligatoria; el numero recomendado es
guia de concision, NO limite duro. No se intenta inferir semantica contando
separadores ni se amplian catalogos de frases/tickers. El texto completo se
conserva. Desglose lee cinco componentes tipados con separadores variables y
puntua igual; nota admite separadores/puntuacion final usuales. Siguen estrictos
maximos/denominadores/suma/categoria/pilares; componente ausente/duplicado,
numeros/prosa extra en desglose y factores vacios se rechazan.
Retiradas llamadas productivas a los parches cosmeticos de continuacion de
walls y calificadores negativos. Sus helpers quedan solo para regresiones
historicas; no alteran nuevas propuestas. Prompt maintenance v5 y prompt Sol
comun coherentes; routing_revision4/luna_repair_version1/modelos/ITV sin cambios.

Auditoria encontro INOD: 'dentro de la zona segun el mid de $69.885' era
rechazado por gramatica, no por posicion. Se permite la cifra mid si coincide
con latest_price a su precision; posicion incorrecta o mid falso siguen fallando.
Etiquetas/campos/secciones siguen necesarias para parser y proteccion de Tesis;
before literal/unico evita editar otra ocurrencia; hash/fuentes/stops/origen,
geometria y snapshots no se eliminan por considerarlos presentacion.

Replay completo offline: CLS original y otros once recibos Sol pasan sin
reescribirlos ni llamar modelos. ASML y 16 incidencias previas tambien pasan.
INOD propuesta Luna ORIGINAL pasa apply_update con model_context real y
validacion completa, sin cambiar input/recibo. No aplicable y Sin zona
verificable tambien toleran puntuacion final; declarar una zona real con
fortaleza No aplicable sigue rechazado. Verificacion: 150 tests adaptativos,
80 root adaptativos, 21 validador, 13 schema, seis scores y diez nuevos
de tolerancia/replay: 280 correctos, incluyendo 840 variantes de desglose.
No recuperado/publicado CLS, no sustituido INOD Sol publicado, no cambiado
RDDT: su bloqueo por titulares sin cuerpos sigue pendiente de auditoria de
routing; el feed IBKR es completo/status ok (no fallo de recoleccion).
Las secciones siguientes son HISTORICAS; no confundir su 42/46 con este lote.

## Estado vigente 05-10: segundo lote fallido y correccion Luna acotada

Orden 20261005-102917-247-market-0c09e7f9, batch 10-31-51: terminado
42/46 publicados, MU/TSLA/IBKR/CLS fallidos; 18 conservados, 15 Luna update,
9 Sol. Los nueve pasaron por Luna: cero ITV vencida/guardas obligatorias,
cero fallback/capacidad. Cuatro reintentos pipeline repitieron recibos fallidos.
Este fue el segundo lote; el mas reciente es 12-38-33, documentado arriba.

Usuario autoriza corregir defectos y UN reintento dirigido de Luna antes de Sol.
Nuevas preparaciones congelan luna_repair_version=1 y prompt maintenance v4
(routing_revision sigue 4). Update rechazado reparable recibe MISMO informe/
fuentes/prefijo/schema/modelo high, respuesta anterior y motivo exacto; una
segunda propuesta rechazada va a Sol. blocked/fuentes esenciales ausentes,
hash/base corrupto y timeout/ejecucion ambigua siguen fallando visiblemente.
Guardas/ITV siguen directas a Sol. Recibos/reserva/usage triage_repair separados;
el contrato de sesiones Luna limpio comparte prefijo, no historial. Versiones
congeladas sin flag NO adquieren llamadas adicionales al reanudarlas.

Normalizaciones estrechas: no-op unico omitido (no constituye solo un informe
nuevo), OI porcentual no se interpreta como contratos pero exige oi_share_pct
real; dos calificadores negativos observados no cuentan como quinto factor.
Snapshot generico frontal SOLO con formato/timestamp/bid/ask/spread demostrados
por slim; estado 'segun el mid' admite aviso, nunca cambia geometria. Reemplazo
literal de UNA nota diaria se canaliza por la puerta existente de routine_note;
propuestas contradictorias con dos notas necesitan correccion, no fusion ciega.
Prompt exige before literal con negritas, sin noops, todas las metricas vigentes,
nota en su campo, y separa cautela de spread de ausencia esencial de cotizacion.
Tesis/Narrativa/catalizadores/stops/origen/validador completo siguen protegidos.

Replay sin modelos/publicaciones: TSLA/IREN/LRCX/QCOM/TLN originales pasan
validacion completa; IBKR con before literalmente corregido pasa en fixture
offline (NO respuesta modelo ni permiso de publicar). MU original sigue
rechazado por doble nota; fixture que elimina ese conflicto destapa metrica
sin respaldo suficiente. AMD conserva su rechazo de metrica sin prueba.
CLS conserva blocked original por incertidumbre de quote; instrucciones nuevas
evitan asumir que todo spread ancho bloquea, no garantizan una futura decision.
141 hashes de artifacts originales intactos. Evidencia:
logs/incidents/20261005-luna-repair/offline_replay.json.

No relanzado/recuperado/publicado este lote; sus cuatro fallidos SIGUEN pendientes.
No reemplazar Sol ya publicado por candidatos historicos Luna. Gateway,
Apps Script y procesos no tocados. Pruebas nuevas/regresiones offline;
ninguna llamada de calentamiento/modelo ni otro lote de prueba. Medir nueva
politica en siguiente lote NATURAL, no garantizar porcentaje de retencion.
Verificacion final: 150 tests adaptativos en tests/, 80 adaptativos root,
41 regresiones de validador/schema/continuidad/fechas/reintentos y dos suites
JS correctas. Rechazo de metrica adjunta campo, cifra declarada, valor/fuente
actuales y strike/vencimiento al feedback; no solo un codigo generico.

## Nota de progreso compacta 05-10 (solo presentacion)

Usuario solicita acortar nota y conservar desglose Luna/Sol. Codex en C4
queda en seis lineas para su ejemplo: publicados/preparados/validados,
conservados/actualizados Luna/nuevos Sol (resultados publicados, NO llamadas),
actividad y tiempo/ETA. Fallos/reintentos solo si existen; heartbeat bruto
solo cuando obsoleto, con SIN SENAL y rojo conservados. JSON/checker sin cambios.
Ambas suites JS pasan; deploy aislado analysis_completion_sync.gs y pull
confirman target exacto y otros 14 archivos remotos identicos:
.tmp_apps_script_push/20261005-124556/{original,work,readback}.
NO se ha detenido, reiniciado ni probado otro batch/modelo. El run activo
recibe formato nuevo en siguiente refresco normal del trigger, sin write manual C4.

## Recuperacion autorizada MU 05-10: COMPLETED 46/46

Usuario dice "hazlo" a recuperar solo MU sin repetir los otros 45 ni llamar
modelos. Misma orden 20261005-075355-374-market-17cba93b/checkpoint 07-57-20.
MU staged con stage.main y call_codex/reserve PROHIBIDOS; recibo original
reutilizado, MD/JSON/HTML validados. Resume oficial publica MU intento3 y
reconcilia worker/progreso remotos: COMPLETED/ok 46/46, cero fallidos.
Resultado final 27 conservados, SNDK/MU actualizados Luna, 17 Sol; dos
reintentos pipeline historicos, cero fallback. No se rehicieron los 45 ok.
MU published_at 2026-10-05T10:15:54.140290+00:00; generated_at ORIGINAL
2026-10-05T08:12:27.071327+00:00; ancla Sol/ITV del 03-10 preservada.
Verificados 400 hashes protegidos (otros 45 bundles/recibos/reviews y fuentes
MU), ledger codex_budget byte-identico: cero llamadas/consumo nuevo en recuperacion.
GCS MU/latest.json coincide exactamente con staging validado; current y ancla
releidos; progress/latest, status/latest y completed/ID concuerdan 46/46.
Evidencia logs/incidents/20261005-MU-recovery/{before,verified,remote_verified}.json.
Gateway no tocada. Los cuatro smokes aislados descritos debajo son previos
a esta recuperacion y NO cambian contadores/consumo del lote natural.

## Estado vigente 05-10: parches rutinarios reparados y Luna comprobada

Orden 20261005-075355-374-market-17cba93b, logs/batch/2026-10-05/07-57-20:
45/46 publicados, MU fallido; 46 llamadas Luna high, 17 Sol 6.1 high.
27 conservados / SNDK actualizado / 17 regenerados. Todos pasaron por Luna,
cero ITV vencida (age_sessions=1), cero guardas directas/fallback/capacidad.
MU pidio sustituir fecha desnuda 03-10-2026, presente en fecha del analisis
y snapshot. Contrato ambiguo; intento 2 repitio MISMO recibo sin otra llamada.
Ocho Sol por rechazo de update: seis campos agrupados (MP/NVDA/OKLO/ORCL/
RKLB/SPCX), dos porcentajes incorrectos (KTOS/LRCX). RKLB tambien cambiaba
Narrativa protegida. Otros nueve escalados por Luna, incluido CRWV por supuesto
conflicto de continuidad y MRVL por evento aun futuro. Riesgos concretos
APP/INTC/QCOM, quote TLN y dudas reales de origen deben seguir visibles.

Usuario pide resolver: revision4 acepta union de campos editables SOLO cuando
su intervalo intermedio es whitespace; no atraviesa prosa/headings protegidos.
Fecha desnuda repetida se resuelve SOLO en campo frontal unico cuando es su
valor exacto y after equivale a prepared_at; nunca cambia snapshot/catalizador.
Porcentajes se calculan mecanicamente de rangos elegidos y latest_price con
Decimal, misma precision/separador; valores de niveles/stops no se modifican.
Snapshot visible heredado exacto se refresca SOLO si timestamp anterior esta
demostrado por reference.slim_snapshot.as_of; se toma slim.as_of y se audita.
Fecha erronea explicita, parches arbitrarios ambiguos, hash, motivos/valores de
stops, Tesis/Narrativa/catalizadores/evento, origen y validador completo siguen
protegidos. Revision3 conserva puertas anteriores. No cupos ni cambio de modelo.

Prompt maintenance contract v3 (routing_revision sigue 4), congelado solo en
nuevas preparaciones: no editar Narrativa ni sus comparaciones tecnicas; usar
routine_note fechada. Stop estructural EXENTO del rebase de continuidad; motivos
identicos restantes ya son rebased por runner. Override compartido entre
produccion/evaluacion elimina contradiccion anterior. Evento conocido aun futuro
no equivale a resultado nuevo; riesgo critico/incertidumbre esencial sigue Sol.

Replay ORIGINAL: MU + siete de ocho rechazos pasan TODA validacion, junto con
SNDK. RKLB original sigue rechazado por narrativa protegida (no se debilita).
Staging MU REAL en temp, usando contrato/recibo original, valida MD/JSON/HTML,
preserva completed_at y ancla/ITV Sol, con modelo/reserva/upload prohibidos.
Hashes input/respuesta/recibo originales intactos. No publicar candidatos Luna
antiguos sobre los Sol ya publicados; no alterar sus contadores retrospectivos.

Cuatro llamadas aisladas Luna high, cero Sol/publicacion/lote:
RKLB update valido, CRWV update valido, MRVL retain; recorte hipotetico de guia
35% + liquidez escala. Evidencia logs/adaptive_patch_evaluation/
20261005T100407635184/summary.json y replay.json. Input 154944, cache 0 (prefijo
nuevo), output 18210 incluido razonamiento 11878. No extrapolar cuota/ahorro ni
garantizar decisiones futuras; medir siguiente lote NATURAL, no repetir batch.
133 tests adaptativos en tests/, 80 root adaptive, 46 regresiones de validador/
fechas/schema/continuidad/reintentos, ambas suites JS correctas.

Estado previo a la autorizacion: MU seguia fallido y lote 45/46. Recuperacion
posterior ya completada y verificada 46/46 en la seccion superior; no repetirla.
Gateway no reiniciada ni tocada. Prueba de arranque natural sigue pendiente.

## Estado vigente 04-10: lote revision 4 y correcciones de fecha/arranque

Orden 20261004-070402-774-market-17217b16, logs/batch/2026-10-04/07-12-55:
COMPLETED 46/46, cero fallidos/reintentos de analisis/fallback; 43 conservados,
TSLA actualizado Luna y APP/NVDA regenerados Sol. Luna high efectivo en 46
recibos; Sol 6.1 high en dos. 17m12s pipeline, 25m45s desde inicio worker.
Progreso GCS y resultado worker ok comprobados, sin editar ni repetir lote.
APP escalo por incertidumbre sobre titular judicial y necesidad de investigar.
NVDA propuso update tecnico, pero omitio la fecha del analisis: el rechazo
update_not_allowed_stale_report_date causo una llamada Sol evitable.

Usuario pide arreglar lo fallado. apply_update revision 4 completa SOLO una
fecha frontal valida, pasada y heredada exactamente de current cuando Luna
omite actualizarla; se registra fuente prepared_at y hash de linea. Fechas
explicitamente cambiadas a valor incorrecto, futuras, ausentes, ambiguas o
malformadas siguen rechazadas. Retain no refresca fecha. No se altera ancla
Sol, fecha completa/ITV, precio, fundamentos ni contrato/prompt/cache.
Revision 3 conserva semantica anterior. Respuesta NVDA original pasa TODA
la validacion tras esa unica normalizacion, sin modelo ni publicacion:
logs/adaptive_delta_evaluation/20261004T083510366913/replay.json.
Hashes input/respuesta guardados; recibos/checkpoint e informe Sol publicado
intactos. No reemplazar el Sol actual por aquel candidato Luna mas antiguo.

IBKR: el primer arranque mostro rechazo de ibg.xml y la recuperacion existente
YA archivo ese perfil a las 09:09:27 Madrid; segundo arranque limpio. No fue
solo cambio de puerto: ambos arranques configuraron 4002 -> 7497.
Evidencia logs/tws/ibc-20261004-090604-284081.log y
ibc-20261004-091003-247333.log. No atribuir causa raiz del cifrado a suspension
sin evidencia. Los ConnectionRefused durante sondeo eran puerto aun cerrado.
Se anade precomprobacion TCP silenciosa; puerto abierto AUN exige handshake
API real read-only. Limpieza de Java aislado ahora nativa por ruta ejecutable
exacta, revalidada sobre mismo handle antes de terminar, espera acotada y fallo
visible; sustituye PowerShell/CIM sin timeout. Nunca mata Java por nombre,
PID sin verificar ni aplicaciones personales. Gateway abierta no tocada.

Verificacion offline: 122 tests adaptativos, 94 regresiones, suites Gateway/
procesos/pipeline y ambas JS correctas. Inventario nativo real SOLO LECTURA
identifica Python y Gateway correctamente; cero procesos terminados. Sin
reinicio frio de Gateway, llamadas modelo, batch, GCS o Sheet nuevos.
La mejora del arranque necesita observacion natural, no prueba de que nunca
reaparezca rechazo de ajustes. No repetir smokes reales por defecto.

## Estado vigente 04-10: diferencias deterministas y Luna high (revision 4)

Usuario acepta corregir sobreescaladas y subir Luna de medium a high. No se
activa xhigh: su mejora/coste incremental no estan medidos. Sol sigue 6.1 high,
ITV maximo cinco sesiones, techo seis con control de capacidad; sin nuevos cupos,
fallback ni sustitucion de modelos. Revision 4 solo en nuevas preparaciones;
los 46 hashes de entradas/recibos historicos revision 3 siguen identicos.

Ultimo lote terminado 03-10 18-29-23: 46/46, 27 conservados y 19 Sol,
cero actualizaciones Luna, cero reintentos de analisis/fallback, 21m56s.
Auditoria: MP confundia 47 > 46.795; NVDA alegaba diferencias entre markdowns
iguales; titulares ya suministrados y cambios tecnicos historicos se trataban
como nuevos. No todas las 19 escaladas se consideran injustificadas.

adaptive_delta.py entrega diferencias exactas contra current y Sol, identidad
y cronologia de noticias/analistas, igualdad de markdowns y geometria numerica.
Solo as_of/mirror_url se separan como metadatos de captura; no se redondean ni
filtran cambios reales. Noticia ya suministrada NO equivale a riesgo evaluado;
omision material, incertidumbre, guardas e ITV siguen requiriendo Sol.
Prompt/contexto revision 4 usan estos hechos sin forzar conservar. Luna high
puede resolver cambios tecnicos rutinarios en su primera llamada como antes.

Pruebas reales aisladas, cuatro llamadas Luna high y cero Sol/batch/publicacion:
NVDA conserva; MP actualiza sin Sol. MP destapo rechazo de una nota tecnica
con noticias vacias; se corrigio autoridad de notas SOLO revision 4, exigiendo
cambio real y evidencia slim actual. La MISMA respuesta pasa validacion completa
sin regenerar. Fixture critico inicial se descartaba por decir explicitamente
que no era noticia real; corregida la instruccion contrafactual del harness,
un recorte hipotetico de guia del 35% escala a Sol. Fallos iniciales preservados.

Evidencia: logs/adaptive_delta_evaluation/20261003T220938915701/ (primeros casos),
20261003T221157527525/ (critico corregido),
20261003T221324262864/replay.json (MP validado sin llamada).
Consumo de las cuatro llamadas: 130752 entrada, 0 cache, 7737 salida,
incluidos 4460 de razonamiento. No es A/B medium/high ni medida de cuota semanal.
110 tests adaptive + 94 tests de regresion pasan, ambas suites JS correctas.
No se toco ningun batch activo, Gateway, GCS ni Sheet. Medir ahorro/escaladas/cache
en siguiente lote NATURAL; no extrapolar dos casos a 46 ni garantizar ahorro.

## Estado vigente 03-10: concurrencia sensible a capacidad

Peticion expresa tras recordar INTC 02-10: seis se mantiene como techo, no
concurrencia fija ante saturacion. Control compartido por TODOS los procesos
Luna/Sol en .local/codex-analysis-workspace/capacity/, con bloqueo y diario.
Fallo terminal de capacidad confirmado, sin respuesta final: 6 -> 3 -> 1 en
episodios sucesivos; los fallos de la misma tanda se deduplican. No se cancelan
llamadas activas ni se cambia modelo. Nuevas admisiones esperan cooldown y hueco.
Espera 10/20/40/80/120 s + jitter 0-2; Retry-After valido siempre es minimo.
Recuperacion de uno en uno, despues de tres respuestas correctas y 30 s desde
el ultimo cambio. No son cupos de informes ni tokens. No llamadas de calentamiento.

Reintentos siguen en pases existentes del batch, no hay segundo bucle oculto.
Cuota/auth/contexto no se reintentan como capacidad; timeout real/resultado
ambiguo se protegen. Si agota espera SIN CLI/modelo, recibo no_model_started
permite re-admision solo con contrato/hash igual y sin evidencia de ejecucion;
reserva consulta cuota de nuevo. Contador separado, no coste/consumo desconocido.
Recibos/ledger incluyen capacity_control; resumen model_admissions_not_started.
Estado corrupto bloquea, PID muerto libera hueco, fallo de limpieza no pierde
respuesta completada. No se modifica politica/prefijo/modelos congelados.

Pruebas deterministas, seis procesos reales SIN modelo, recuperacion/recibos/
cuota/contabilidad y regresion de mantenimiento. No batch, llamadas de modelo,
subidas de informes ni cambios en Apps Script; Gateway existente intacto.
Detalles: docs/codex_adaptive_analysis.md, tests/test_adaptive_capacity.py.
Verificacion final: 288 tests y 208 subtests pasan, ambas suites JS correctas;
registro logs/incidents/20261003-adaptive-capacity/audit.json. Sin llamadas reales.

## Estado vigente 03-10: mantenimiento Luna activado (revision 3)

Usuario autoriza auditar escenarios y rehacer estrategia: Luna ahora conserva,
actualiza cambios tecnicos rutinarios en SU PRIMERA llamada o escala a Sol por
cambio critico/incertidumbre/investigacion. Modelos 6 Luna medium / 6.1 Sol high
sin sustitucion; seis simultaneos, ITV maximo cinco sesiones desde full Sol.
No cupos/topes de gasto/informes/retenciones ni fallback automatico.

Current mantenido separado del ancla Sol inmutable en _analysis_state/TICKER.
Noticias/acciones/memoria y comparacion acumulada siguen desde Sol. Luna no
reinicia ITV; corruptos/futuros/mismatch y fuentes incompletas bloquean. Candidato
completo valida precio/porcentajes/estado/geometria/origen/proteccion fundamental
y validador existente; cambios de stop de gestion numerico requieren Sol.
Rebase mecanico solo de motivos heredados exactos + nivel igual, fechando la
justificacion historica. Metricas copiadas inequívocas del mismo wall se refrescan
solo si numero previo/origen estan confirmados; nunca notas/pesos/tesis automaticos.
Auditoria registrada y validacion completa del texto exacto publicado.

Pruebas reales aisladas: Luna conserva sin cambios y escala noticia critica
sintetica. Fixture de precio +0.5% conservado razonablemente; reemplazado por
cambio de fuerza real de wall sintetico (no noticia/dato real de ORCL). Dos
respuestas update destaparon continuidad historica no rebased. Se corrigio
tambien el fixture para quitar memoria Sol que produccion no manda a Luna,
sin editar recibos anteriores. La tercera respuesta update, con contrato
equivalente a produccion, tuvo cache 15.104/30.397 tokens de entrada y mostro
un separador que dividia un mismo factor de opciones. Agrupacion mecanica
estrecha de vecinos demostrados recupera ESE MISMO recibo en staging completo:
MD/JSON/HTML validos, banner incluido, sin llamar de nuevo ni publicar.
Respuestas/recibos originales intactos; artifacts fallidos historicos conservados.
Evidencia: logs/adaptive_maintenance_evaluation/20261003T110709119629/staging_replay/.
Los 46 formatos reales pasan puertas nuevas; replay de 16 informes del 02-10
con llamadas/reservas prohibidas sigue pasando bajo politica histórica.
Verificacion final: 265 tests, 175 subtests y ambas suites JS pasan. Seis llamadas
Luna aisladas, cero Sol, 224.984 tokens entrada (15.104 cache), 8.129 salida.
Registro consolidado: logs/adaptive_maintenance_evaluation/final_audit.json.

Replay de 46 inputs del lote terminado: 45 Luna primero / 1 Sol directo APP;
NO son 45 conservados ni actualizados garantizados. El batch 03-10 anterior
sigue COMPLETED 46/46, 46 Sol/11 Luna; no se ha repetido ni editado.
Nueva config routing_revision=3 solo para nuevas preparaciones. Reanudar
checkpoint viejo conserva su politica/prompt/recibos, no migrarlo en caliente.

Contadores published-only separan Sol nuevos, Luna actualizados y conservados;
analysis_outcomes muestra candidatos validados/tickers pendientes de publicar.
Apps Script SOLO analysis_completion_sync.gs publicado y pull confirmado igual
con los otros 14 ficheros remotos identicos al original:
.tmp_apps_script_push/20261003-124240/verified_readback.json.
No se refresco retrospectivamente C4 del lote anterior ni se subieron informes.

Estrategia y matriz de escenarios: docs/codex_adaptive_analysis.md. Queda medir
siguiente lote NATURAL: decisiones/razones, normalizaciones, escaladas rechazadas,
tokens/cache efectivos y fallos. No afirmar ausencia de fallos futuros ni ahorro
de cuota garantizado. No repetir estos smokes por defecto.

## Estado anterior 03-10: enrutamiento adaptativo corregido (revision 2)

El lote 20261003-074314-470-market-668e79b5 termino COMPLETED 46/46 a
08:37:33 UTC (10:37 Madrid), cero fallidos/fallback: 46 informes Sol y
11 triages Luna, todos completados. Cero ITV vencidas; NO fueron 46 revisiones
por antiguedad. De los 35 Sol directos, 31 incluian vencimiento de opciones;
cuatro incluian "Entrada ambiciosa: Sin zona verificable" como falso error.
Las causas se solapan. Los otros 11 escalaron por verdictos Luna guardados.

Aplicada routing_revision=2 en config: mismo strike con muro put vigente y
OI/gamma positivo pasa a Luna para comparar fuerza real, no se conserva a
ciegas. La ausencia explicita de entrada ambiciosa tambien pasa a Luna. Un
stop ya roto en la referencia es aviso para revision, no nueva ruptura.
Siguen obligando a Sol la perdida de origen sin reemplazo vigente, nueva
ruptura de stop, perdida de fuerza y demas guardas; ITV maximo cinco sesiones.
Sin cupos de informes/retenciones, nuevos topes ni cambios de modelos.

Replay offline de los 46 inputs EXACTOS: Sol directo baja de 35 a 18;
Luna primero sube de 11 a 28. Esto NO predice cuantos conservara Luna:
podra escalar por cambios materiales o incertidumbre. Evidencia durable:
logs/incidents/20261003-adaptive-routing/offline_audit.json.
No nuevas llamadas de modelo, lote, publicaciones ni modificaciones de
checkpoint/respuestas. Se aplica a nuevas preparaciones automaticamente.
Politicas/instrucciones congeladas previas conservan semantica revision 1
para reconstruir contexto y recuperar recibos sin repetir llamadas.

Verificacion: 191 tests y 51 subtests pasan; replay completo de 16 informes
del 02-10 en staging temporal con reloj historico y llamadas/reservas
PROHIBIDAS pasa sin regenerar ni subir. La primera prueba con reloj actual
rechazo correctamente snapshots historicos por frescura; no se relajo esa
proteccion. Resta medir retenciones/consumo del siguiente lote natural.

## Estado vigente 03-10: ASML recuperado sin otra llamada

Run terminado 20261003-074314-470-market-668e79b5, logs/batch/2026-10-03/07-48-11.
ASML: Sol completo correctamente a 08:00 UTC; validador conto como quinto
factor el punto y coma interno de una frase final "Fortaleza anterior: 78;
baja por ...". No es el defecto del punto final del desglose del dia anterior.
Corregido: comentario explicito de fortaleza anterior al comienzo de una
frase se excluye SOLO del conteo de factores; se conserva todo el texto.
Una quinta evidencia real, suma/categoria/maximos incorrectos siguen fallando.

ASML original pasa validacion completa sin modificar report.response. Recovery
por stage.lock/publish.lock con call_codex y reserve bloqueados: cero llamadas,
ledger ASML identico y fecha de generacion original 08:00:00.974864 UTC.
Publicado y leido GCS ok a 08:30:32 UTC. No detenido ni relanzado el batch;
checkpoint vivo no editado. El reintento normal reutilizo review.json y
published_at: ASML reconciliado ok en intento 2. Lote final 46/46, cero fallidos,
un reintento de lote y cero Web; summary.json confirma fin a 08:37:33 UTC.

Copias/evidencia logs/incidents/20261003-asml-factor-comment/082952082262/;
recovery_verified.json confirma hash original, fecha y lectura remota.
180 tests y 38 subtests pasan. Diff check del validador correcto. Pruebas
sinteticas independientes de logs y replay del ASML original incluidas.
No afirmar que estos tests cubren cualquier formato futuro.

## Estado vigente 03-10: cartera vacia por venta total comunicada

El usuario comunica que vendio todas las posiciones el 02-10 y pide quitar
todos los shots de la hoja. Aplicado positions={} a cartera local y runtime
GCS; Mercado conserva los 46 tickers en seguimiento, sin colores de posicion,
con Pos./Shots y bandas de grupo a cero. tickers_market marca owned=false.
No se borraron tickers, grupos, analisis ni informes.

Verificados valores reales de la hoja, colores, contadores, universo y GCS;
layout remoto identico. Operacion 20261003-close-all-shots-user.
Copias previas y verificacion:
logs/market_tracking/20261003-close-all-shots-user/.
Se registro cierre a cero por ticker en applied_tracking_commands para que
snapshots anteriores no restablezcan posiciones. Fechas de publicacion
confirmadas tras actualizar la hoja. Sin ordenes de tracking pendientes.
No se enviaron operaciones al broker: registro de ventas ya realizadas.

Durante la lectura se encontro --snapshot-at duplicado en el parser del
gestor de shots. Eliminada la declaracion duplicada; CLI --help correcto.
No interpretar posiciones de los apartados historicos como cartera vigente.

## Estado vigente 02-10 09:58 UTC: lote adaptativo recuperado

Orden 20261002-074741-market-f5aa68a5, checkpoint logs/batch/2026-10-02/07-50-20:
originalmente 25/46 publicados y 21 fallidos; ahora COMPLETED 46/46, cero
fallidos, cero Web/fallback. Resultado completed y progreso remoto leidos y
confirmados; PLTR latest.json remoto tambien ok. Proceso de recuperacion cerrado.
No se lanzo otro lote: los 25 registros ok del checkpoint siguen identicos.

El usuario pidio arreglar todos los fallos observados. Recuperados 16 informes
guardados, respuesta original byte a byte y sin llamadas nuevas: SNDK, TSM,
MRVL, IREN, AMAT, INOD, QBTS, HOOD, QCOM, CRDO, MU, RDDT, CCJ, USAR, APP, TSLA.
Correcciones de validador: punto final en desglose, precios previos explicitos
en lineas de cambio y ausencia de nivel previo con referencias a otros niveles.
Se mantienen comprobaciones numericas, sumas, origen y precios inventados.
No atribuir sin evidencia la antiguedad exacta de esos parsers: la nueva
adaptacion/reutilizacion hacia inutiles los reintentos sobre respuestas validas.

GOOG/PLTR/MRNA tenian un hueco real de noticias desde el informe completo:
backfill IBKR real, releido y validado (no solo modificar metadata). ORCL tenia
snapshot tecnico parcial sin soporte, congelado por prepare: ahora se comprueba
antes de congelar y puede refrescarse un fallo de datos previo a cualquier
reserva de modelo. Entradas admitidas a modelos siguen inmutables, incluso
si un crash no dejo recibo. INTC termino con turn.failed por capacidad: se
permite reintento confirmado de ese fallo terminal transitorio; no de timeout,
reserva ambigua, respuesta completada ni agotamiento de cuota. Historial y
artefactos fallidos archivados; no cambiar modelo ni activar fallback.

Recuperacion: cinco llamadas Sol (solo esos cinco) y tres Luna. El resto se
reutilizo. Primera reanudacion rechazo orden de tickers antes de llamadas:
routes_for reordenaba tras las ITV ya terminadas. Corregido orden congelado
del checkpoint y lectura de referencia local al reanudar. Fechas originales
de generacion se conservan: republicar no reinicia edad ITV. adaptive_review
persistido, contadores regenerados/conservados y modelos efectivos corregidos.

Copias previas y stdout: logs/incidents/20261002-adaptive-recovery/094654835721/;
primer intento sin llamadas: 094240326222/. Evidencia original de errores
sigue guardada, no confundir failure.json historico con resultado vigente.
178 tests y 32 subtests pasan; replay completo de los 16 produce MD/JSON/HTML
validos con llamadas/reservas prohibidas. git diff --check correcto.

Lote completo: 46 informes Sol, 21 triages Luna; 47 llamadas Sol contando una
fallida de consumo desconocido. Cache registrada Sol 25341440/29468638 tokens
de entrada; Luna 159232/535613. No prometer descuento de cuota ni ahorro futuro:
este primer lote no retuvo informes. Sin nuevos topes, sin relanzar exitosos.
La incidencia C4 y notas anteriores son historia; sus fallos ya se diagnosticaron.

## Estado vigente 02-10: ordenes de shots acumulables

Incidente confirmado: venta MRVL de las 07:33:02 UTC termino a las 07:35:18
con 1 shot. Compra CLS enviada a las 07:34:21 llevaba snapshot MRVL=2 y lo
restauro a 2 al terminar a las 07:37:16; ambas ordenes figuraban ok.
No se perdieron objetos de cola: la reconciliacion de snapshots antiguos
sobrescribia deltas anteriores.

Corregido: fecha de captura anterior a leer colores; IDs con milisegundos;
proteccion de tickers modificados desde la captura, tambien durante la
publicacion. El observed_shots antiguo tampoco vuelve a imponer su valor
sobre esos tickers. Altas/bajas posteriores a la captura se preservan.
Compatibilidad con ordenes antiguas mediante created_at. Registro durable
antes de publicar y reintentos por ID sin repetir el delta. Historial GCS
incluye la operacion actual, a diferencia del codigo anterior.

Worker programado usa --drain y consume varias ordenes en un mismo arranque,
conservando --once para diagnostico. Mantiene sondeo cada minuto y bloqueo
durante los analisis; no prometer respuesta instantanea. No se ha detenido
el batch vivo 20261002-074741-market-f5aa68a5 ni se ha lanzado otro.

MRVL recuperado desde el resultado ya confirmado (sin otra venta); CLS=2
conservado. Verificados colores reales y cartera GCS, resto de posiciones
preservado. Copias y evidencia: logs/incidents/20261002-tracking-queue/.
La fecha de republicacion protege tambien contra snapshots tomados durante
la recuperacion. Ambos Apps Script publicados mediante doble pull con diff
de un solo archivo por push y pull final coincidente:
.tmp_apps_script_push/20261002-100835 y 20261002-100953.
La primera publicacion fallo por DNS cuando no habia Internet; reintentada
tras confirmar el usuario que volvio la conexion.

Verificacion: 32 pruebas Python (6 tracking, 17 worker, 9 regresiones de cola)
y prueba JS de menu correctas; git diff --check correcto. No prueba artificial
con nuevas compras/ventas reales. Resta observar siguientes ordenes naturales.

## Presentacion C4 adaptada 02-10

Apps Script analysis_completion_sync.gs distingue provider=codex de Web:
motor Codex, flujo Luna/Sol, fase combinada sin inventar subfase, listas activas,
conservados/regenerados publicados y contadores de fallos/reintentos de lote.
Sin trabajadores/chats/adjuntos/fallback Web. Guarda y color SIN SENAL intactos;
ETA desconocida muestra '-'. Los publicados sin clasificacion se declaran asi,
sin inventar generacion Sol. Vista legacy preservada para chatgpt-browser.
Dos suites JS y 25 tests pipeline/progreso pasan; texto probado con progreso real.
Script aislado publicado con double-pull/diff en .tmp_apps_script_push/20261002-101644;
readback confirma igualdad y otros 14 archivos remotos intactos. No se tocaron
runner/modelos ni se reinicio/detuvo el lote 20261002-074741-market-f5aa68a5.
A 08:15 UTC habia 1 publicado y 6 fallidos: fallos reales, NO diagnosticados
ni resueltos por esta tarea UI. No declarar lote sano. No se leyo la celda remota;
la nota nueva se aplica por el trigger permanente en su siguiente sincronizacion.

## Estado vigente 01-10: cache proveedor corregida

El usuario pidio aplicar la correccion. La CLI instalada asigna prompt_cache_key
por thread nuevo: estabilizar solo instrucciones no bastaba. Ahora call_codex
reutiliza slots exclusivos por contrato/rol y los limpia despues de cada llamada
con thread/revert del protocolo INSTALADO (thread/rollback de docs Web ya no
existe en 0.159.2). Se verifica contexto durable vacio antes de reusar; respuesta,
recibo y eventos quedan en artifacts. Fallo de limpieza retira slot sin repetir
llamada ni perder respuesta valida. Sin acumular informes/tickers en contexto,
sin API key, compaction pagada, calentamiento dummy o cambios de auth global.
Luna y Sol conservan instrucciones/modelos/sesiones separados; seis simultaneos.

Dos pruebas reales Luna autorizadas: conservar/escalar correctos, misma sesion,
limpieza confirmada y sin avisos. Entrada 18382/18805; salida 765/513. Segunda
llamada 7936 cacheados (42.2%), frente a cero previo. Evidencias en
logs/adaptive_evaluation/20261001T212644147776. Esto no prueba descuento de cuota
ni ahorro garantizado de lote. No batch, informe Sol nuevo ni publicaciones.
El primer lote natural sigue pendiente; no repetir smokes por defecto.
Verificacion final: 120 tests Python pasan (56 runner/adaptativo/sesiones,
64 validacion/estado/politica/continuidad/resumen), cinco peticiones locales con
CLI instalada comprueban claves separadas Luna/Sol y cero mezcla de tickers.
La primera orden de tests uso imports tests.* no disponibles en este arbol;
repetidos mediante unittest discover pasan. Sin nuevas llamadas reales.

## Estado vigente: revision de ahorro solicitada 01-10

Esta seccion sustituye los controles numericos y el circuito global descritos
en el estado anterior. Quitados: 180000 caracteres, 1000 acciones, pauta 1200
palabras Luna, cuatro rondas/seis fuentes Sol y busqueda obligatoria. Fallos
aislados por ticker; otros siguen, sin repetir reservas ambiguas ni fallback.
Cuota real/frescura/validacion siguen activas, sin reservas ni topes por lote.

Implementados los cinco ahorros aprobados: saltar Luna si Sol es obligatorio,
compartir solo objetos/arrays identicos en JSON minificado (roundtrip sin perdida),
esquema/prefijo invariantes, memoria de investigacion fechada ligada al informe,
cache de Luna exacta y sensible a dia/ITV/eventos. Memoria no es verificacion
independiente ni cache completa de paginas. Nunca reusar un hecho historico
como si fuese actual. Datos/frescura/guardas/edad se comprueban antes de cache.

Modelos simultaneos SEIS efectivos: descubierto y corregido retorno de un solo
worker para Codex en _analysis_worker_count. Configurar seis antes no bastaba.
Esperas por llamada: Luna 240 s, Sol 1200 s. No se lanzo lote ni se publico.
Ver detalles y evidencias finales en docs/codex_adaptive_analysis.md.
Dos smokes reales v3 pasan conservar/escalar; entrada 18382/18805 tokens,
salida 712/542, cache proveedor cero. Resumen recuperado offline del fallo
de impresion cp1252, sin otra llamada: logs/adaptive_evaluation/20261001T164501420386.
Deduplicacion probada sin perdida: CAT -39.68%, NVDA -31.37% caracteres;
no llamarlo porcentaje de tokens. Replay Sol sin cambios valida staging en
logs/adaptive_replay/20261001T164632190532. No publicaciones ni lote.
Verificacion final: 116 tests Python y dos suites JS pasan; diff --check OK.
Los apartados anteriores siguen como historia, no como limites activos.

## Estado vigente 01-10 11:45 UTC: Codex adaptativo activado

Actualizacion por peticion expresa: ITV a las 5 sesiones bursatiles para TODOS
los tickers, incluidos tracking/watchlist (antes 10). El usuario rechazo los
topes inventados de 12 informes/ITV: retirados TODOS los topes por lote de
informes, ITV, llamadas y tokens. Tampoco se aplican desde politicas congeladas
anteriores ni bloquean la compatibilidad del ledger al cambiar solo esos campos.
Se mantiene contabilidad de consumo, cuota real, concurrencia y validacion.
Una ITV que falle queda visible, nunca reinicia edad por revision Luna.
Sin lanzar lote.

El usuario aclara que Codex YA funcionaba y solo pide adaptar modelos/rutas,
no reconstruirlo. Comprobado ultimo lote 30-Sep 46/46 Codex y ningun batch vivo.
Se conservan fuentes, validador y publicacion existentes. El bloqueo temporal
de activacion era de esta implementacion, no una averia del Codex anterior.

El usuario autorizo tambien la investigacion publica. Prueba aprobada Sol 6.1
high CAT completada: logs/adaptive_smoke/20261001T113503724136. Doce rondas Web,
solo consultas publicas. 1135122 entrada acumulada, 991232 cacheada (87.3%),
143890 no cacheada, 9088 salida. No confundir entrada acumulada entre llamadas
de herramientas con tamano inicial del prompt ni con coste de suscripcion.

La primera validacion encontro un defecto del adaptador: entregaba JSON al
validador antiguo sin sus campos de niveles anteriores. Corregido usando su
formatter existente y seccion slim, SIN relajar reglas ni regenerar informe.
Replay pasa JSON/Markdown/HTML: logs/adaptive_replay/20261001T114431812136/audit.json.
La validacion fallida del smoke original se conserva como evidencia historica.
Luna retener/escalar ya probado (ver docs/codex_adaptive_analysis.md).

production_enabled=true; report_web_research_enabled=true. Mantener controles
de cuota real, fuente fresca y validacion. Pauta nueva de investigacion
<=4 rondas/6 fuentes aun sin medicion real; no es limite duro. Sin topes de
gasto por lote ni ahorro prometido.
Recibos recuperados verifican contexto, instrucciones, esquema, modelo/esfuerzo
y busqueda observada, sin repeticion automatica ante llamada ambigua.

Apps Script: desplegado SOLO analysis_completion_sync.gs con etiquetas Codex
principal y resumen retenciones/regeneraciones. Pull posterior exacto en
.tmp_apps_script_push/20261001-134454; resto remoto preservado.
No lote ni publicaciones de informes en esta sesion. El siguiente lanzamiento
normal usa Luna medium + Sol 6.1 high por cambios/ITV. Su coste y fiabilidad
a escala de lote quedan por medir; no bloquear por repetir smokes ya pasados.
No reanudar checkpoints Web bajo estrategia adaptativa.
Verificacion final: 110 tests Python y dos suites JS pasan; git diff --check OK.
Cuenta ChatGPT/modelos exactos reconfirmados. Cuota consumida entonces 60%.
El usuario rechazo expresamente el corte del 70%: retirado de config y codigo,
tambien al leer politicas congeladas anteriores. Sin porcentaje reservado;
se mantiene bloqueo por cuota agotada/desconocida, sin presupuestos por lote.
No se usaron resets ni se lanzo lote para este cambio.

## Historia de implementacion 01-10 (gates siguientes ya superados)

Ultima actualizacion 01-10 11:30 UTC: el usuario autoriza todas las llamadas de
modelo necesarias, sin consultar cada vez. Siete llamadas adicionales realizadas
(181755 tokens entrada / 8870 salida). Sol 6.1 high CAT paso validador completo;
5888/32595 tokens de entrada cacheados (18.1%), sin prometer ahorro general.
Luna ya conserva un informe Sol respaldado sin cambios y escala la perdida
sintetica de soporte/rotura de stops. Corregidos falsos positivos temporales y
referencias inventadas: enum de fuentes existentes + resolucion JSON Pointer.
Replay offline del staging real paso JSON/Markdown/HTML. 86 pruebas Python y
dos suites JS correctas. Evidencias y limites en docs/codex_adaptive_analysis.md.

Bloqueo nuevo, NO permiso para mas llamadas Codex: la prueba Sol con busqueda
web publica fue rechazada ANTES de ejecutarse por el revisor de seguridad,
porque la salida de consultas a terceros requiere autorizacion especifica.
Se ha preguntado al usuario si autoriza investigacion publica sin cartera,
posiciones ni textos privados en consultas. Esperar respuesta; no eludir el
rechazo. El informe Sol congelado bajo tesis por falta de datos fundamentales:
no equivale a una ITV investigada. production_enabled=false y
report_web_research_enabled=false; no batch/publicaciones/despliegue remoto.
Los apartados siguientes describen las fases previas de la implementacion.

El usuario autorizo implementar Luna diario + Sol alto por cambios/ITV y cache.
El nuevo default del runner es Codex adaptativo; no hay navegadores ni API key.
Politica y operacion: `docs/codex_adaptive_analysis.md` y
`config/codex_analysis.json`. No interpretar las prohibiciones historicas de
migracion Web que siguen debajo como vigentes frente a esta autorizacion nueva.

Actualizacion posterior 01-10: el usuario actualizo Codex y autorizo las dos
llamadas Luna. Preflight de cuenta ChatGPT/modelos confirma gpt-6.1-sol high y
gpt-6-luna medium. No hace falta modelo provisional. Las DOS llamadas terminaron:
`logs/adaptive_smoke/20261001T105912`. CAT 26931 entrada/1110 salida; NVDA
35204 entrada/1159 salida. CERO cached_input_tokens en ambas (no sumar reasoning
otra vez). JSON valido NO equivale a semantica valida: CAT confundio una
correccion historica de resistencia con un cambio nuevo; ademas hubo rutas de
evidencia inexistentes. Ambos snapshots actuales eran iguales a los de referencia.

Corregido localmente: prompt temporal v2, contexto sin cambios historicos ni
recibos duplicados, referencias JSON Pointer verificadas antes de escalar a Sol,
y rechazo de recibos con hash de contexto diferente. Conserva informe completo,
ambos snapshots y todas las noticias/acciones actuales. Reduccion medida de
caracteres: CAT 11.5%, NVDA 24.4%; NO son ahorros medidos de tokens/cache.
Pendientes nuevas pruebas reales v2 y un informe Sol validado, con autorizacion
adicional acotada (las dos llamadas autorizadas ya se consumieron). No hubo
batch, publicacion ni navegador. Etiquetas Apps Script aun locales. No decir
que ya se puede lanzar ni afirmar ahorro de cache.

Verificacion: 83 pruebas Python enfocadas correctas, dos suites JavaScript de
progreso/resumen correctas, ambas entradas CLI --help y git diff --check OK.
Pruebas locales: guardas, ITV, presupuestos, fallos sin fallback, conservacion
de fechas, recuperacion de resultados y bloqueo de sobrescritura de un informe
posterior; tambien regresiones del pipeline, progreso y politica anterior.
La continuidad ya se incluia en el prompt antiguo; ahora tambien es una guarda
ejecutable que no permite conservar soportes por inercia.

Actualizado el 2026-10-01. Este documento es el punto de entrada para una
sesion nueva. Antes de lanzar, reanudar o corregir un analisis, contrastar este
estado con `docs/pending_work_current.md`, `docs/chatgpt_browser_provider.md` y
los artefactos del ultimo batch.

## Diagnostico del 01-10: bloqueo Cloudflare confirmado en las peticiones internas

- Actualizacion 08:35 UTC: el usuario inicio sesion manual en Chrome, abrio
  Analisis y confirmo hecho. Advirtio avisos Google y una pestana de Keepa.
  Auditoria de solo lectura (`scripts/inspect_analysis_chrome_profile.py`):
  ruta dedicada E:/stock-analysis-local/.local/chatgpt-browser-profile distinta
  del perfil personal C:/Users/ignac/AppData/Local/Google/Chrome/User Data;
  contiene una entrada de cuenta Google y siete extensiones, incluida Keepa.
  No era un perfil limpio. El estado actual de sincronizacion no se pudo
  establecer con los campos revisados. No se leyeron cookies ni tokens.
  Se anaden --disable-extensions y --disable-sync a los lanzadores Chromium
  manuales/automaticos y al diagnostico: solo banderas del proceso dedicado,
  no se borran extensiones/cuentas ni se edita el perfil personal. La prueba
  inicial de este turno ya llevaba las extensiones desactivadas por Playwright;
  --disable-sync explicito se agrego despues (no afirmar que se probo antes).
- El Chrome autenticado tambien encontro 403 con cabecera Cloudflare: primero
  200 en cuenta/modelos/proyectos, luego 403 en comprobacion de cuenta,
  conversaciones y sentinel/finalize. Evidencia:
  `logs/browser_startup/chromium/20261001T083510Z.json` y PNG. No hubo prompt,
  lote, fallback ni publicacion. Esto descarta que cambiar a Chrome baste;
  no demuestra la regla exacta que produce el bloqueo. El usuario vio ademas
  un popup de traduccion Chrome: no confundir una capa UI con los rechazos
  HTTP observados. Se reconocen etiquetas ingles/espanol. No ocultar señales
  de automatizacion ni intentar eludir el control de acceso.
  Regresion: 169 pruebas y 2 subpruebas correctas.

- Actualizacion 07:55 UTC: el usuario pide continuar hasta tener solucion,
  autoriza probar otro navegador y solicita ayuda solo si es necesaria. Se
  confirmo que el launcher Firefox usa `-profile` sobre los perfiles persistentes,
  no una copia temporal. No hay historial Git de ese archivo nuevo para
  atribuir con certeza un cambio causal a una revision concreta.
- Existe Chrome instalado en Program Files (x86) y el runner ya admite
  Chromium/Playwright. El perfil dedicado `.local/chatgpt-browser-profile`
  pertenecia a ese Chrome, no al navegador personal. Se probo visible mediante
  `scripts/check_chatgpt_chromium.py`: llega a ChatGPT sin desafio ni error de
  cuenta, pero SIN sesion iniciada. Resultado `chatgpt_login_required`, no un
  preflight sano. Evidencia `logs/browser_startup/chromium/20261001T075455Z.json`
  y PNG. No se uso login automatico ni se copiaron cookies de Firefox.
- Para continuar hace falta una unica asistencia: ejecutar
  `verificar_chatgpt_chrome.cmd` desde el escritorio remoto, iniciar sesion con
  la cuenta habitual, abrir Analisis y cerrar SOLO ese Chrome. Launcher creado,
  no ejecutado por el agente. Despues probar el mismo perfil con el diagnostico,
  verificar proyecto/Sol-Alta y adaptar cualquier contrato Chromium que falle
  ANTES de enviar un ticker Web sin fallback. No activar el proveedor Chromium
  para el lote todavia: la ruta antigua no tiene todas las guardas de Firefox.
  El diagnostico nuevo si rechaza compositor anonimo y challenges de red/UI.
  La prueba cerro su navegador; 168 pruebas y 2 subpruebas locales correctas.

- Actualizacion 07:49 UTC: a peticion del usuario se probo arranque escalonado
  tras mas de cinco minutos sin Firefox del analisis (ultima respuesta previa
  07:42:43 UTC; nuevo arranque 07:48:15). Se anadio SOLO al diagnostico
  `check_chatgpt_workers.py --sequential --stagger-seconds 30`: abre un perfil,
  verifica proyecto/modelo, conserva la sesion y espera antes del siguiente;
  se detiene al primer fallo. No se cambio la politica de arranque del batch.
  El primer perfil (1), estando SOLO, recibio 403 Cloudflare en cuenta/modelos/
  proyectos y fallo pese a tres recargas. No llegaron a abrirse 2/3.
  Evidencia: `logs/browser_startup/worker-1/20261001T074907126248Z-worker-1-attempt-1.json`.
  No basta esta pausa/arranque individual, pero no descarta efectos acumulados
  de mayor duracion. No afirmar que quedo demostrada la causa por simultaneidad
  ni que los perfiles 1/3 siguen sanos: los exitos anteriores fueron puntuales.
  Pruebas locales: 164 y 2 subpruebas correctas. Navegador de prueba cerrado;
  sin prompts, lote, fallback, relogin ni publicacion.

- Actualizacion 07:43 UTC: el usuario recupero los perfiles 2 y 3 con UN clic
  manual de `Volver a cargar`, aporto captura de ambos dentro de Analisis y
  confirmo su cierre. El preflight automatico posterior autentico los tres;
  perfiles 1 y 3 pasaron proyecto/modelo y ocultacion. Perfil 2 cargo cuenta,
  modelos, sidebar y conversaciones con 200, pero al abrir el proyecto recibio
  un nuevo 403 Cloudflare en el gizmo Analisis y `conversation/init`:
  `logs/browser_startup/worker-2/20261001T074044704874Z-worker-2-attempt-0.json`.
- Una unica comprobacion aislada posterior del perfil 2 reprodujo el bloqueo
  desde carga de cuenta pese a tres clics ordinarios; evidencia
  `20261001T074252865029Z-worker-2-attempt-1.json`. Esta prueba fue inmediatamente
  posterior al arranque simultaneo: NO descarta un efecto acumulado o temporal
  de ese arranque. No descartar la guarda ni copiar cookies entre perfiles.
  La recuperacion manual no estabilizo ese perfil en automatizacion; no pedir
  repetir identicamente la recarga como si fuera un arreglo comprobado.
  No se hizo smoke, batch, fallback ni publicacion. Se preservaron los
  archivos locales CCJ previos en `logs/incidents/20261001-web-smoke/CCJ-before/`
  preparando el smoke condicional que NO llego a lanzarse.
  Un intento de diagnostico se rechazo correctamente por un sondeo concurrente
  de command_worker; su candado se libero solo, no se paro ni modifico.

- Actualizacion 07:15 UTC: el usuario aporto seis capturas del perfil 1;
  `Volver a cargar` recupero su cuenta, el proyecto Analisis y los menus de
  razonamiento/modelo. Se implementaron hasta tres clics ordinarios de
  recuperacion al detectar el error de cuenta, con diez segundos de espera
  entre ellos y sin ampliar el deadline de arranque ni clicar desafios.
  Los bloqueos de red no se borran al recargar: requieren un 2xx real.
  Agotamiento sin Cloudflare tiene error propio `chatgpt_account_load_failed`,
  aparta el worker y no provoca fallback masivo en un lote.
- Dos preflights reales verificaron el perfil 1 con proyecto, Sol/Alta y cero
  ventanas visibles. Su red devolvio 200 en cuenta, modelos y proyecto, sin
  necesitar recargas automaticas. Evidencia individual:
  `logs/browser_startup/worker-1/20261001T071216397195Z-worker-1-attempt-0.json`.
  No atribuir esta recuperacion al nuevo retry: ocurrio tras la accion manual.
- El preflight conjunto termino con `authenticated=1`, `disabled=(2,3)`.
  Ambos hicieron los TRES clics reales de `Volver a cargar`, pero persistieron
  403 con `cf-mitigated: challenge` en perfil/modelos/proyectos. Evidencia:
  `logs/browser_startup/worker-2/20261001T071346299392Z-worker-2-attempt-1.json`
  y worker-3 `20261001T071348303862Z-worker-3-attempt-1.json`. Los diagnosticos
  guardan eventos de red sin query/cookies/cuerpos y las horas de los clics.
  Esto demuestra la causa inmediata del mensaje, no el detonante de la regla
  Cloudflare. No se enviaron prompts ni se publicaron informes; no hubo batch.
- Estado anterior (ya completado, ver 07:43 UTC): se necesitaba recuperar
  solo los perfiles 2 y 3 por la via normal; lanzador
  `verificar_chatgpt_perfiles_2_3.cmd` preparado pero NO ejecutado. El usuario
  debe abrir Analisis en ambos y cerrarlos. Despues, repetir preflight completo
  y un unico smoke Web sin fallback. No pedir repetir el perfil 1 sin evidencia
  nueva. Los navegadores del preflight ya se cerraron.

- El usuario pide seguir hasta validar que puede lanzar el lote y solicitar
  ayuda solo cuando sea necesaria. Autoriza las reparaciones y verificaciones
  necesarias; mantiene rechazada una migracion a API/cuota Codex.
- Un solo perfil 1 visible, fuera del sandbox y sin prompts, reprodujo
  `No hemos podido cargar tu cuenta`. La captura de Resource Timing mostro
  HTTP 403 para perfil, modelos, proyectos y conversaciones, mientras otras
  peticiones respondian 200. Una segunda captura pasiva WebDriver BiDi
  confirmo en esos 403 las cabeceras `cf-mitigated: challenge` y
  `server: cloudflare`. Esto prueba el bloqueo Cloudflare de esas peticiones;
  no demuestra la senal concreta por la que se activa.
- Evidencia: `logs/browser_startup/worker-1/20260930T221510984424Z-worker-1-attempt-0.startup.json`
  y `20260930T221834448198Z-worker-1-attempt-0.network.json` (UTC, ya dia 1
  en Madrid). La peticion especifica de `Analisis` tambien recibio 403.
  El clic/reintento de la aplicacion no lo recupero. Ambas pruebas cerraron
  su Firefox; no hubo generacion, publicacion ni fallback.
- La clasificacion anterior por mera presencia de `/cdn-cgi/.../jsd/api.js`
  producia falsos positivos: ese script tambien esta en paginas normales.
  Se corrige y se anade observacion pasiva de los 403 con cabecera real,
  con gracia acotada y borrado del bloqueo cuando el mismo endpoint da 200.
  No se guardan cookies, cuerpos, cabeceras de autorizacion ni query strings.
  El arranque ya no acepta el compositor mientras `Cargando perfil` sigue
  activo o quedan peticiones esenciales bloqueadas. Se conserva el cierre
  explicito sin Codex cuando se requiere verificacion humana.
- Se evita recargar el home ya abierto y se excluyen los botones de la barra
  lateral de la comprobacion de contexto del compositor. Un boton `Nuevo
  chat en Analisis` en la barra lateral no prueba estar dentro del proyecto.
  Regresion: 141 pruebas y 2 subpruebas correctas.
- `check_chatgpt_workers.py --worker-id 1` ahora abre solo ese perfil.
  `--verify-model` comprueba proyecto y modelo sin mensajes;
  `--verify-background` admite tanto privado como ocultacion interactiva.
- Comprobacion anterior (ya completada, ver actualizacion superior): se pidio
  al usuario una comprobacion normal del perfil 1 mediante
  `verificar_chatgpt_perfil1.cmd`: entrar en `Analisis`, desplegar el selector
  de modelo y cerrar Firefox. En ese momento estaba pendiente; no abrir el perfil con
  Selenium mientras el usuario lo comprueba. Si funciona manualmente,
  contrastar la misma sesion con el preflight exacto; si aparece desafio,
  la interaccion humana corresponde al usuario. No eludir Cloudflare.
- Pendiente: validar los tres perfiles y un smoke Web real sin fallback,
  despues confirmar que puede lanzar su lote. El arreglo de selectores por
  si solo no subsana el rechazo externo demostrado.

## Lote del 30-09: 46/46 publicados, cero Web, 46 Codex

- Se aislo un fallo de selector distinto de Cloudflare: el HTML real del
  worker 3 tenia el proyecto `Analisis` con
  `data-app-action-sidebar-project-id` y boton `Nuevo chat en Analisis`,
  mientras el automatismo buscaba el marcador antiguo `#compose`.
  `_click_selenium_project` usa ahora el ID estable y la etiqueta del boton,
  conservando el selector antiguo como respaldo. La navegacion directa espera
  el contexto asincrono; el retry reconoce `Volver a cargar` y el poll del
  compositor tolera elementos obsoletos. 71 pruebas enfocadas y 2 subpruebas
  correctas. El preflight real posterior, sin prompts ni publicacion, no pudo
  validar la ruta: worker 1 mostro `No hemos podido cargar tu cuenta` y
  `StaleElementReferenceException`, worker 2 quedo deshabilitado por
  `chatgpt_human_verification_required`, y worker 3 mostro el error de carga
  de cuenta y termino tambien en verificacion humana. Diagnosticos:
  `logs/browser_startup/worker-{1,2,3}/20260930T210*-attempt-*`.
  El fallo de selector esta corregido localmente, pero no afirmar que el
  proyecto abre hasta superar un preflight real. No repetir pruebas Web en
  bucle ni lanzar batch mientras persistan desafio/carga de cuenta.
- A peticion del usuario se volvio el 30-09 al modo Firefox anterior:
  `.local/background_windows.json` tiene `firefox=false`, `ibkr=true`.
  Firefox arranca en el escritorio interactivo y se oculta tras crear la
  sesion; puede verse brevemente. Al salir del escritorio privado, el
  launcher restaura explicitamente los ajustes de renderizado anteriores,
  porque Firefox habia persistido el compositor software en los tres perfiles.
  `test_firefox_desktop.py`: 22 pruebas correctas. Un preflight real sin
  prompts ni publicacion (`check_chatgpt_workers.py --verify-project`) termino
  con tres perfiles autenticados pero los tres fallaron al abrir `Analisis`:
  `chatgpt_project_not_open`. Diagnosticos en
  `logs/browser_startup/worker-{1,2,3}/20260930T205*-attempt-0.*`.
  Los workers 1 y 2 conservaron `Cargando perfil`; el 3 mostraba `Analisis`
  en el texto DOM, pero la navegacion al proyecto volvio al home. No se vio
  un challenge bloqueante en las capturas finales. El proceso de prueba cerro
  los navegadores y no se genero ningun analisis. Esta prueba descarta que
  quitar el escritorio privado baste por si solo. No lanzar un lote: la ruta
  Web sigue sin validar.
- Verificacion manual iniciada a peticion del usuario: un intento de abrir el
  perfil 1 desde la ejecucion remota lanzo Firefox, pero no mostro ventana en
  su escritorio interactivo. Se interrumpio ese intento y se comprobo que no
  quedaba Firefox del analisis. Se creo `verificar_chatgpt_web.cmd` en la raiz
  para que el usuario lo abra desde el propio escritorio remoto. El usuario lo
  ejecuto: aparecieron tres ventanas y el desafio de Cloudflare desaparecio
  solo tras unos diez segundos, sin pulsar la casilla. El lanzador abre las
  tres ventanas sin esperar a su cierre; se corrigio su mensaje, que antes
  decia erroneamente que estaban cerradas. El usuario confirmo el cierre de
  las tres ventanas. El preflight de `check_chatgpt_workers.py
  --verify-background` dio `healthy=3`, `disabled=()` fuera del sandbox,
  con cero ventanas interactivas y 11 ventanas privadas por worker. No se
  enviaron prompts ni se publicaron informes. Un preflight previo dentro del
  sandbox fallo durante el resize inicial con `Browsing context has been
  discarded`, igual que el fallo ambiental documentado el 28-09; no indica
  que Cloudflare siga activo. Tras autorizacion explicita del usuario, se
  ejecuto un smoke `CCJ --generate --generation-provider chatgpt-browser
  --no-generator-fallback --chatgpt-browser-max-attempts 1` fuera del sandbox.
  Fallo antes de enviar el prompt o adjunto: el home de ChatGPT mostro el
  compositor, pero el panel lateral permanecio en `Cargando perfil`, sin el
  proyecto `Analisis`. La recuperacion de navegador repitio la navegacion y
  fallo otra vez con `chatgpt_project_not_open: Analisis`. Evidencia:
  `output/CCJ/browser_diagnostics/20260930T162117373954Z-CCJ-attempt-1.*`,
  `20260930T162309657179Z-CCJ-attempt-1.*` y
  `output/CCJ/generation_metadata.json` (`status=failed`, `provider_used=null`,
  `web_attempt_count=1`). `latest.md` no cambio; no hubo fallback, publicacion
  ni lote nuevo. La ruta Web sigue sin validar; no lanzar un batch suponiendo
  que el challenge manual resolvio este segundo problema.
- El usuario aclaro que en las tres ventanas manuales vio el proyecto y el
  resto de ChatGPT, no solo el home. El contraste controlado del 30-09 a las
  18:15 UTC, sin enviar prompts, reproduce la diferencia: el worker 1 oculto
  sigue en `Cargando perfil` y no abre `Analisis`
  (`logs/browser_startup/worker-1/20260930T181531787845Z-worker-1-attempt-0.*`);
  el worker 2 recibio de nuevo `chatgpt_human_verification_required` bajo
  Selenium (`logs/browser_startup/worker-2/20260930T181346309329Z-worker-2-attempt-1.*`).
  El preflight tuvo 2 workers autenticados y el chequeo de proyecto devolvio
  codigo 1; Firefox no registro crashes el 30-09. La verificacion manual no
  basta para asegurar el modo automatizado. `check_chatgpt_workers.py` acepta
  ahora `--verify-project --worker-id 1` para comprobar el contexto sin enviar
  contenido. En lote, `chatgpt_project_not_open` y
  `chatgpt_project_context_not_confirmed` tampoco activan Codex fallback.
  Regresion enfocada: 42 pruebas correctas. Sigue pendiente resolver la carga
  de perfil en Selenium oculto o escoger con el usuario una ruta soportada;
  no repetir el smoke ni lanzar un lote hasta tener una prueba Web sana.
- Para aislar el escritorio privado se probo el mismo perfil 1 en Firefox
  headless autentico con `scripts/diagnose_chatgpt_headless_project.py
  --worker-id 1`, sin prompt ni publicacion. Tambien termino en
  `chatgpt_human_verification_required`. Esto no prueba que el escritorio
  privado cause `Cargando perfil`; demuestra que cambiarlo por headless no es
  una solucion fiable. No automatizar ni eludir Cloudflare. La documentacion
  oficial de Sign in with ChatGPT describe una ruta de Responses API para
  proyectos locales elegibles usando el plan ChatGPT con consentimiento OAuth;
  no se ha comprobado la elegibilidad de esta cuenta ni el acceso al modelo,
  y no se ha iniciado ninguna migracion. Requiere decision explicita del
  usuario porque altera la arquitectura y puede tener limites distintos.
- El usuario rechazo expresamente la via Sign in with ChatGPT/Responses API
  porque consumiría uso de su plan o creditos. No proponerla como solucion
  operativa ni implementarla sin una nueva peticion expresa. Mantener la
  investigacion en la ruta ChatGPT Web, sin batch ni prompts de prueba hasta
  aclarar el fallo. El detonante exacto de la nueva puntuacion/desafio de
  Cloudflare no es visible en los diagnosticos locales; no afirmar que fue
  causado por IP, volumen, cambios de codigo o escritorio remoto sin pruebas.

- Orden `20260930-094041-market-74923418`, checkpoint
  `logs/batch/2026-09-30/09-46-02/`. El progreso local y el remoto acabaron
  `completed 46/46`, pero `generation_providers` confirma 0 ChatGPT Web y
  46 Codex fallback; `failed=0` no significa que Web haya funcionado.
- Los diagnosticos de arranque de los tres workers, entre 09:51 y 09:54 UTC,
  muestran `chatgpt_firefox_navigation_failed: prompt_not_available`.
  La captura HTML contiene `/cdn-cgi/challenge-platform/` y Turnstile; la
  captura de pantalla pide verificacion humana de Cloudflare. Los tres
  workers quedaron deshabilitados. Los siguientes tickers registran
  `chatgpt_no_healthy_browser_workers` y fueron a Codex. No se sabe por que
  Cloudflare presento hoy el desafio; no atribuirlo sin prueba a GPU, red o
  escritorio remoto.
- El `SIN SEÑAL` fue otro problema: el resultado del command worker conserva
  varios timeouts de 25 s al subir `commands/progress/latest.json`, mientras
  el checkpoint local avanzaba. El remoto finalmente llego a `completed` a
  las 10:33:57 UTC. La causa de esos timeouts GCS sigue sin demostrarse.
- Correccion local posterior al lote, sin lanzar analisis ni publicar:
  detectar el desafio humano por la pagina de Cloudflare, apartar el worker y
  no activar fallback Codex en lote ante ese desafio o al quedarse sin workers
  Web. El lote debe fallar visiblemente en vez de publicar masivamente por
  Codex. El CLI `login --worker-id {1,2,3}` permite abrir visiblemente cada
  perfil real con candado exclusivo para que el usuario complete el desafio;
  no se han abierto ventanas en esta sesion. Pruebas locales enfocadas: 115
  correctas y 2 subpruebas; pendiente validacion real controlada antes del
  siguiente lote. Cloudflare no admite Selenium para resolver desafios de
  produccion, por lo que la validacion manual puede no persistir al volver a
  automatizar. Esta correccion no rehace los 46 informes ya publicados.

## Mantenimiento del 29-09, despliegue del controlador en validacion

- El controlador local conserva la ultima cotizacion valida por ticker, con
  precio, variacion, fuente y hora; rechaza ceros y respuestas vacias en
  premarket/postmarket y muestra antiguedad en la nota de la Sheet. La cache
  se guarda en GCS para sobrevivir cambios de instancia y de dia.
- `Resumen de grupos` se ordena por variacion `Dia` numerica descendente,
  moviendo filas A:H completas. El refresco de cartera lee el orden fisico
  antes de escribir posiciones y shots. La suite local del controlador pasa
  131 pruebas. La revision `stock-controller-quote-groups-fix-20260929` sirve
  el 100 % desde las 18:36 UTC. El refresco programado de las 18:37 UTC
  devolvio HTTP 200, `published=46`, 15 benchmarks y 73 requests; la
  verificacion por API devolvio `OK tickers=46 market_rows=46 groups=14
  html_links=46 sort='Tesis' sorted=True`. Incluye comprobacion nueva del
  orden numerico de grupos y alineacion ETF/posiciones/shots. La cache de
  cotizaciones existe en GCS. No se observo aun un ticker realmente sin
  bid/ask tras el despliegue; esa ruta esta cubierta por pruebas locales.
- La primera revision `stock-controller-quote-groups-20260929` fallo en el
  refresco de las 18:31 UTC antes de escribir la hoja: Sheets omite
  `startColumn` cuando vale cero. El trafico se devolvio de inmediato a la
  revision anterior, se corrigio el lector y se simulo la ordenacion con las
  14 filas reales sin escribir. La revision corregida paso `/health` por URL
  de prueba antes de recibir trafico.
- `docs/batch_workflow.md` describe el flujo Mercado vigente y
  `docs/operations.md` distingue el enrutado historico. La prueba antigua
  que fijaba una cartera exacta se sustituyo por invariantes sin cambiar
  posiciones. La herramienta de reconciliacion del progreso esta en
  `src/local_runner/progress_reconciliation.py`: rechaza un heartbeat mas
  reciente que el cierre de la orden, como el del batch reanudado; esa guarda
  se comprobo contra GCS en modo lectura.
- Se revisaron los archivos tocados y `git diff --check` no dio errores de
  espacios. La busqueda de marcadores de claves conocidos en `src/`, `docs/`
  y `gcp_services/` no dio coincidencias. El arbol sigue mezclando numerosos
  cambios anteriores y `gcp_services/` entero no esta seguido por Git; no
  se ha creado un commit que los mezcle.

## Lote del 29-09: reanudado desde el checkpoint original

- Tras autorizacion expresa, smoke real CCJ por ChatGPT Web con
  `--no-generator-fallback --chatgpt-browser-max-attempts 1`: generacion y
  validacion correctas, `gpt-5.6-sol`, sin publicacion ni nuevos crashes GPU
  (111 minidumps antes y despues). CCJ no se salto en el batch por esta prueba.
- Reanudacion lanzada oculta mediante `scripts/resume_batch_command.py` con
  `logs/incidents/20260929-browser-gcs/resume_command.json` y el checkpoint
  original. PID del launcher 33944, `run_batch` PID 29704/40396 al arrancar.
  Log de cierre en `logs/incidents/20260929-browser-gcs/resume.stdout.log` y
  stderr homologo. A las 18:23:20 UTC, el progreso local y
  `commands/progress/latest.json` remoto coincidian: `running`, 27/46,
  `command_id=20260929-160621-market-d41c8302`, tres workers Web activos,
  ninguno deshabilitado. No declarar completo o sano hasta ver resumen final,
  proveedores, reintentos, fallbacks y stalls; el estado puede cambiar.

## Parada anterior del 29-09 y diagnostico que motivo la reanudacion

- Mitigacion posterior, sin reanudar: solo los Firefox del analisis en
  escritorio privado fuerzan compositor software, desactivan D3D11 software
  y desactivan el proceso GPU. La primera prueba solo con compositor software
  produjo 11 minidumps GPU mas (100 -> 111), por lo que era insuficiente.
  Tras desactivar tambien `layers.gpu-process.enabled`, preflight real de los
  tres perfiles: healthy=3, cero ventanas interactivas, cero minidumps nuevos
  (111 -> 111). Los tres perfiles guardaron la preferencia. Override de
  diagnostico `ANALYSIS_FIREFOX_SOFTWARE_RENDERING=0` restaura los valores
  por defecto al arrancar; el Firefox personal no se modifica.
- La publicacion de progreso ahora prioriza `commands/progress/latest.json`,
  limita cada subida a 25 s y omite la copia secundaria de la orden si falla
  `latest`. Antes se subia primero la copia de la orden y ambas podian bloquear
  60 s cada una, dejando C4 sin latido. La mitigacion esta cubierta por pruebas
  locales, pero el origen externo de los timeouts GCS no se ha demostrado.
  Regresion: 57 pruebas enfocadas correctas y dos de limpieza de procesos
  Windows correctas fuera del sandbox. No se publico un latido de prueba ni
  se genero/subio un analisis; un preflight sano no certifica el lote completo.

- Orden `20260929-160621-market-d41c8302`, checkpoint
  `logs/batch/2026-09-29/16-08-41/pipeline_state.json`. El usuario pidio
  detenerlo y revisar el problema; el arbol exacto de `run_batch` (PID 26004)
  se termino a las 17:51 UTC. Se verifico que no quedaban `run_batch` ni
  geckodriver/Firefox de ese arbol. Gateway siguio activo; el
  `command_worker` cerro tras registrar el resultado `failed`. No se lanzo
  otro analisis ni se reinicio Gateway.
- Checkpoint JSON valido: 46 tickers, 27 `ok` publicados, 6 en `analyze` y
  13 en `prepare`. `sheet_progress.json` conserva 27/46, 24 Web, tres fallback
  (`MRNA`, `PLTR`, `GOOG`), seis reintentos Web, cero reintentos de pipeline;
  worker 1 desactivado. Los 19 no publicados deben reanudarse desde el
  checkpoint, no desde una orden nueva. Los intentos en vuelo al detenerse
  pueden repetirse; comprobar publicacion por ticker antes de asumir duplicados.
- La terminacion intencional dejo el resultado de `command_worker` local y
  `commands/status/latest.json` remoto como `failed` a las 17:51:06 UTC. Su
  `error_message` procede de la ultima linea de stdout y **no** explica la
  parada. El progreso local y `commands/progress/latest.json`, que habian
  quedado `running 27/46`, se reconciliaron el 29-09 como `failed 27/46`;
  la lectura posterior de GCS lo verifico. Se conservaron los 19 tickers no
  publicados y el checkpoint; no se reanudo ni se modifico la orden.
- Diagnosticos de fallbacks: MRNA fallo primero en `attach` y luego perdio
  conexion local con geckodriver (`WinError 10061`); PLTR perdio geckodriver
  durante `wait_response` y de nuevo en el reintento; GOOG agoto dos lecturas
  de Marionette/navegacion de 120 s, tras lo que worker 1 fue apartado.
- Firefox dejo 66 crashes en los perfiles de este lote: 65 procesos `gpu`
  repartidos entre los tres workers y un proceso principal. Este ultimo,
  a las 17:46:37 UTC, registro `Failed to launch GPU process after 3 attempts`,
  `failed to get compositor device` y `FEATURE_FAILURE_D3D11_NO_DEVICE`.
  Hubo 42 crashes GPU el 28-09 y solo un crash de proceso principal el 27-09.
  El modo de escritorio privado de Firefox esta activo (`firefox=true`) desde
  el 28-09, por lo que es una hipotesis de relacion temporal con el compositor
  del entorno remoto, **no** causalidad demostrada. No hay evento Display 4101
  del run; el ultimo encontrado es del 19-09. Tampoco se demostro OOM.
- El segundo problema es la telemetria GCS: el tail del resultado conserva al
  menos 16 advertencias de `gcloud storage cp` agotando 60 s al subir el
  progreso. Eso explica el heartbeat remoto intermitente y `SIN SEÑAL` aunque
  el lote avanzara. No esta demostrado si comparte causa con Firefox.
- El payload de recuperacion se reconstruyo del resultado local porque la
  orden GCS original se elimino al finalizar. La reanudacion autorizada ya
  comenzo como se indica arriba. Nunca pulsar una orden Mercado fresca para
  completar los 19: crearia un lote nuevo en lugar de continuar este.

## Fallo de preflight del 29-09: sesion Selenium invalida; recuperacion corregida

- Orden `20260929-132139-market-e799e98b`: failed, lote `13-28-36`, 0/46.
  El fatal exacto fue `InvalidSessionIdException: Tried to run command without
  establishing a connection`, durante la comprobacion del compositor, antes
  de preparar/enviar/publicar tickers. Resultado local en
  `logs/command_worker/2026-09-29/20260929-132139-market-e799e98b.json`;
  progreso en `logs/batch/2026-09-29/13-28-36/sheet_progress.json`.
- Los tres perfiles registraron 12 minidumps de proceso GPU entre 13:28:49 y
  13:29:33 UTC. Habia versiones 156.0.1 y 157.0 y memoria fisica al 89-95 %;
  estos datos no prueban que la actualizacion o la RAM causaran los crashes.
  No consta motivo OOM. Inspeccion de campos seleccionados, sin subir dumps ni
  cambiar perfiles: `scripts/inspect_firefox_crashes.py --date 2026-09-29`.
- Defecto de recuperacion confirmado: open/preflight capturaban RuntimeError,
  pero las excepciones nativas Selenium no heredan de esa clase. La sesion
  invalida tampoco se reconocia como reiniciable. Se abortaba todo el preflight
  y no quedaba diagnostico del intento, aunque otro worker estuviera sano.
- Tras autorizacion del usuario, launch y autenticacion comparten ahora un
  bucle acotado (dos reinicios). Reconoce el tipo y los mensajes exactos de
  sesion invalida; conserva el candado del perfil y tolera el fallo de quit
  del driver muerto. Captura JSON incluso sin pagina/capturas disponibles.
  Los errores desconocidos siguen propagandose; no se ocultan bugs de codigo.
- Preflight aparta los workers agotados y reconstruye la cola con los sanos.
  Si ninguno queda, falla visiblemente, conserva la causa y marca cero workers;
  no deja navegadores muertos disponibles ni leases bloqueados. La recuperacion
  de transporte durante una peticion sigue limitada a antes de send: no replay
  por sesion invalida durante/despues del envio.
- Regresion `test_dead_browser_session_recovery.py`: el codigo anterior fallo
  15 de las 21 pruebas iniciales, incluida la excepcion real desde el poll del
  compositor. Con la correccion y una prueba adicional de JSON: 146 pruebas y
  2 subpruebas correctas en la suite enfocada, incluidas entradas CLI reales,
  ventanas privadas, adjuntos, proyecto y prohibicion de replay tras send.
- Preflight real sin enviar prompts/adjuntos, completado a las 15:55:55 UTC:
  healthy=3, disabled=(), cero ventanas interactivas en los tres perfiles.
  Worker 3 produjo StaleElementReferenceException a las 15:55:04 UTC y se
  recupero con el nuevo handler; no fue InvalidSessionIdException esta vez.
  Evidencia en `logs/browser_startup/worker-N/20260929T1555*-attempt-*.json`.
  Se cerraron los navegadores de prueba; Gateway conserva PID 27588, sin reinicio.
- No se relanzo/reanudo la orden ni se cambiaron informes, Sheet o estado GCS.
  La causa original de los crashes GPU y la validacion de un lote completo
  siguen pendientes; un preflight sano no demuestra un batch sin fallback.

## Fallo de arranque del 28-09: ImportError introducido en el cambio de ventanas

- Orden `20260928-080204-market-802a2b31`: failed en 0,843 s, a las
  08:02:53 UTC. Causa exacta: run_batch (y tambien run_one) conservaban el hook
  `configure_background_launch`, pero windows_desktop ya no lo exportaba tras
  cambiar a configuracion persistente. Error del cambio local, no de Gateway
  ni de ChatGPT. No se inicio un lote/checkpoint ni se analizo/publico un ticker.
- El fallo se comprobo en el resultado local de command_worker y en
  `commands/status/latest.json` remoto. `commands/progress/latest.json` aun
  describe el lote anterior del 27-09: no confundirlo con la nueva orden.
- La prueba de tres perfiles reales verificaba el navegador, no la entrada
  `python -m run_batch`. Las pruebas importadas tampoco ejecutaban `__main__`.
  Una edicion fallida habia dejado aplicados hooks parciales; no asumir que un
  error de apply_patch revierte automaticamente todas las operaciones anteriores.
- Restaurado el hook compatible: valida las opciones persistentes de Firefox y
  Gateway, sin imponer una variable global ni anular ajustes por componente.
  La activacion privada de `.local/background_windows.json` sigue conservada.
- Nueva regresion `test_background_cli_entrypoints.py`: ejecuta las siete
  entradas reales con `--help`, sin redes, navegadores, analisis ni publicaciones.
  Antes del arreglo reprodujo exactamente dos fallos (run_batch/run_one);
  ambas entradas directas `--help` ya salen con codigo 0 tras corregirlo.
  Regresion completa enfocada: 135 pruebas y 2 subpruebas correctas, incluyendo
  las siete entradas CLI y conservando pruebas de ventanas/proyecto/adjuntos.
- No se ha relanzado la orden ni modificado su estado remoto; no hay checkpoint
  parcial que reanudar. Cualquier nuevo run necesita autorizacion del usuario.

## Segundo lote del 27-09: seis fallbacks diagnosticados y corregidos en codigo

- Orden `20260927-101117-market-fbe4ae7e`, lote `10-13-48`: completado 46/46,
  40 Web y 6 Codex; seis reintentos Web, cero de pipeline. Cinco (`AUR`, `CAT`,
  `CLS`, `GEV`, `HIMS`) se encadenaron en worker 2: timeout de navegacion,
  perdida del contexto de Analisis y reutilizacion de la pagina general como
  chat de grupo. La causa externa del primer timeout no esta demostrada.
- Recuperacion ahora reconoce `project_context_not_confirmed` y transporte
  fallido antes del envio; reinicia solo ese worker, vuelve al proyecto y
  verifica de nuevo Sol/Alta. Un navegador nuevo recibe una peticion completa,
  no una reparacion de una respuesta que no existe en esa sesion.
- La ruta de error no guarda una pagina general no confirmada como chat.
  Invalidar/reabrir tambien limpia URL y grupo anteriores. Se conserva el
  soporte de URL canonica raiz despues de una peticion Web correcta.
- Si el reinicio falla o vuelve a fallar la navegacion antes del envio, el
  worker queda en cuarentena durante ese lote y sale de la cola. Los siguientes
  tickers usan los otros workers; si no queda ninguno, fallan explicitamente
  para permitir el fallback habitual, sin dejar hilos bloqueados en la cola.
  El ticker afectado aun puede acabar en fallback si agota la recuperacion.
- ASML: primera respuesta sin acceso al adjunto; el feedback solicitaba
  Tesis/Setup y tambien Valoracion, que luego rechazaba por mezcla de contratos.
  El validador ya no exige Valoracion cuando valida notas separadas; mantiene
  compatibilidad con informes legacy y rechazo de notas fuera de rango/mixtas.
- Verificacion offline: 116 pruebas y 2 subpruebas correctas. Reproducciones
  en `test_project_recovery_regressions.py`, incluidos errores reales, modelo
  tras reinicio, cuarentena, cola sin workers y feedback de puntuaciones.
  No se han lanzado navegadores, analisis, subidas ni reinicios del run.
  Queda validacion real de estas correcciones en el siguiente run autorizado;
  no considerar esta prueba local evidencia de un lote completo sin fallback.

## Ventanas Firefox/Gateway: ACTIVADO y verificado el 28-09

- El usuario confirmo que el run estaba parado y autorizo las comprobaciones
  pendientes. El ultimo checkpoint, `2026-09-27/14-15-58`, figura completed
  46/46; no habia run_batch, run_one, geckodriver ni Java Gateway activos antes
  de las pruebas. Esto no certifica los proveedores de ese lote.
- Activacion persistente de esta instalacion en
  `.local/background_windows.json`: `firefox=true`, `ibkr=true`. Se consulta
  en cada arranque; no depende de reiniciar el command worker ni de una variable
  temporal. El fichero local esta ignorado por Git. Los perfiles reales bajo
  `.local` y el manager Gateway usan el modo privado en el proximo lote.
  `ANALYSIS_PRIVATE_DESKTOP=1` fuerza el modo (tambien para perfiles externos);
  `=0` es la salida explicita de diagnostico. Login manual Firefox sigue visible.
- Causa corregida: se ocultaba Firefox despues de conectar WebDriver, con
  destello inicial y posible recuperacion visible; Gateway solo ocultaba la
  consola. CreateProcessW establece ahora el escritorio privado desde creacion,
  sin cambiar el escritorio del usuario ni caer a una ventana visible si falla.
- Firefox real: dos arranques locales con perfiles temporales, escritura DOM,
  segunda ventana, resize y cierre/reapertura correctos. Cero ventanas en el
  escritorio interactivo y foco conservado en ambos ciclos. El intento dentro
  del sandbox fallo por contexto descartado; las dos pruebas completas fuera
  del sandbox pasaron. Logs: `logs/firefox_background/geckodriver-{1,2}.log`.
- La activacion persistente se verifico despues con los tres perfiles reales:
  `scripts/check_chatgpt_workers.py --verify-background`, healthy=3, ningun
  worker desactivado, cero ventanas interactivas en los tres. Cierre completo
  comprobado; no se enviaron prompts/adjuntos ni se publico ningun analisis.
- Gateway: `scripts/verify_ibkr_cold_starts.py --private-desktop`. El primer
  intento reprodujo el error exacto de ajustes; el manager conservo el perfil
  rechazado en `.local/ibgateway-settings-archive/` y lo recreo por log, sin
  raton ni clic en el escritorio del usuario. Arranque recuperado y siguiente
  reinicio frio limpios: API read-only sana, sin error de recuperacion y cero
  ventanas interactivas (15 ventanas Java privadas en cada comprobacion).
  Logs: `ibc-20260928-094122-836334.log` (rechazado y archivado),
  `ibc-20260928-094400-453833.log` y `ibc-20260928-094536-409333.log` (sanos),
  bajo `logs/tws/`. Handshake final correcto; Gateway queda abierto oculto.
- Regresion enfocada: 126 pruebas y 2 subpruebas pasan. Incluye persistencia,
  override, configuracion invalida que falla explicitamente, aislamiento tras
  recuperacion, logs/handles, y regresiones anteriores de proyecto y adjuntos.
  No se lanzo un batch ni se hizo una prueba de generacion de contenido.

## Incidente browser del 27-09: corregido; smoke de contenido pendiente

- La orden `20260927-080604-market-2829c615` publico 46/46, pero solo 34 por
  ChatGPT Web y 12 por fallback Codex. Once fallbacks (`NBIS`, `LRCX`, `QCOM`,
  `ASML`, `CRDO`, `AUR`, `LEU`, `TSLA`, `KTOS`, `USAR`, `OKLO`) compartieron
  una carrera de hidratacion: ChatGPT mostraba `add-context` mientras seguia en
  `Cargando perfil`, sin haber montado aun el input de archivo. Hubo 35 fallos
  de adjuntos y tres referencias DOM obsoletas; 16 tickers se recuperaron por
  temporizacion en el segundo intento.
- Selenium espera ahora el input real despues de pulsar `+`. Si persiste
  `chatgpt_attachment_control_not_found`, o el DOM queda obsoleto antes del
  envio, reinicia solo ese worker y reintenta localmente. Nunca reinicia por
  DOM obsoleto despues de `send`, para no duplicar una peticion.
- `MP` fue el fallback restante: cinco factores separados por `;` incumplian
  el contrato de 2-4 y el error generico no orientaba la correccion. El
  validador incluye ahora explicitamente ese limite en el feedback.
- Regresion enfocada: 97 pruebas y 2 subpruebas correctas. Smoke real AMD sin
  fallback: adjunto confirmado (`attach=0.047s`), envio, respuesta y extraccion
  Web completos en un intento. El candidato no se promovio porque Sol omitio
  `Motivo de Tesis` y `Motivo de Setup`, fallo de contenido independiente de
  la interfaz. Queda repetir un smoke expresamente autorizado hasta obtener
  tambien validacion final correcta.

## Cambio de puntuaciones del 27-09: desplegado

- La nota mixta se sustituye por dos dimensiones independientes: Tesis /10
  (narrativa, catalizadores, evidencia y riesgos del negocio) y Setup /10
  (asimetria de la entrada propuesta, estructura tecnica y confirmacion actual).
  Un sell-off sectorial no rebaja Tesis sin evidencia de impacto en el negocio.
  Setup alto no autoriza comprar fuera de la zona; Estado actual sigue separado.
- Prompt, validacion de nuevas generaciones, JSON schema 7, archivo historico y
  politica de continuidad adaptados. `decision.score` conserva el alias de
  Tesis en informes nuevos; `score_basis` distingue `thesis` de `legacy_mixed`.
  No comparar ambas bases ni generar falsas alertas por la migracion. Las
  referencias antiguas fuerzan recalibracion, no bloqueo de la nota mixta.
- Cloud Run: revision `stock-controller-tesis-setup-20260927`, 100% de trafico.
  Layout GCS `runtime/config/market_sheet_layout.json` migrado a schema 5.
  Mercado tiene 38 columnas: bloques J:W e Y:AL; Tesis en V/AK, Setup en W/AL.
  Selector C10: Tesis, Setup, Sector, Fuerza. Tesis es el orden inicial.
- Proyeccion y verificacion real correctas: 46 tickers, 46 filas, 14 grupos,
  46 enlaces HTML, orden Tesis comprobado. Cabeceras verificadas por API y
  visualmente. Conservados niveles y colores de cartera. Los informes antiguos
  muestran `Ver` con enlace y Setup vacio: NO inferir dos notas desde la antigua.
- Ambos schedulers, `stock-analysis-market-refresh` y
  `stock-analysis-report-refresh`, reactivados y ENABLED tras la migracion.
  No se ha lanzado un batch ni generado un informe nuevo para este cambio.
  Queda comprobar ambas puntuaciones en el siguiente analisis normal.
- Backups de layout, celdas y peticiones previas en
  `gcp_services/stock_controller/artifacts/score-migration-20260927T095330Z/`.
  El plan previo esta en el directorio hermano terminado en `095015Z`.
  Se retiraron solo dos filas residuales duplicadas fuera del cuerpo canonico
  (ASML/OKLO); sus originales siguen entre los 46 y el respaldo las conserva.
- Pruebas: 165 del runner correctas; 66 enfocadas del controlador correctas.
  Suite completa del controlador: 126/127 correctas. El unico fallo restante
  es previo y ajeno al cambio: `test_declared_portfolio_contains_rklb_not_spcx`
  presupone una cartera historica que ya no coincide con la configuracion real.
  No se ha modificado la cartera para satisfacer esa prueba.

## Ultima evidencia del lote (25-09; no revalidada el 27-09)

- C4 quedo mostrando `FALLO` aunque la reanudacion manual seguia activa porque
  aquel proceso se lanzo directamente con `run_batch`: no heredaba
  `ANALYSIS_COMMAND_ID`, `ANALYSIS_COMMAND_ACTION` ni el destino de progreso en
  GCS. Se detuvo solo ese arbol y se reanudo el mismo checkpoint mediante
  `scripts/resume_batch_command.py`, asociado otra vez a la orden
  `20260925-082301-market-5e431b82`. A las 14:58 Madrid el progreso remoto era
  `running`, 7/46 publicados, 0 fallidos, tres workers Web activos y sin
  fallback; una lectura directa de Google Sheets confirmo `Mercado!C4 =
  RUNNING 7/46`. No volver a reanudar una orden de Sheet invocando `run_batch`
  directamente: usar siempre el recuperador de comando para conservar su ID,
  heartbeat y cierre remoto.
- La orden Mercado del 25-09 `20260925-082301-market-5e431b82` fallo antes de
  crear checkpoint: el recuperador de IB Gateway intento archivar el perfil
  rechazado mientras el Java aislado aun mantenia handles abiertos y recibio
  `PermissionError [WinError 5]`. El manager termina ahora tambien el Java
  aislado, espera su salida y reintenta el archivado durante una ventana
  acotada. La recuperacion real archivo el perfil a las 13:43 Madrid, abrio la
  API y supero dos reinicios en frio consecutivos sin dialogo de recuperacion.
  Regresion enfocada: 15 pruebas correctas; la prueba Windows de terminacion
  de procesos se repitio fuera del sandbox y paso.
- Como no existia lote parcial, se relanzo Mercado directamente. Checkpoint
  actual: `logs/batch/2026-09-25/11-52-49/pipeline_state.json`, 46 tickers,
  tres workers Web y `--max-parallel 6`. El lote cruzo el preflight y esta en
  preparacion/analisis. Confirmar heartbeat y resumen antes de darlo por
  terminado.
- Durante ese relanzamiento Windows nego una vez el `replace` atomico de
  `pipeline_state.json.tmp`, marcando CRWV como fallido de preparacion. La
  escritura del checkpoint reintenta ahora durante 10 segundos los bloqueos
  transitorios. Regresion de pipeline/reanudacion: 18 pruebas correctas. El
  checkpoint se reanudo como proceso oculto independiente, promovio los
  artefactos validos de AMD/MRNA/PLTR/SNDK y lanzo CRWV como intento 2. Log:
  `logs/incidents/20260925-gateway-recovery/resume.stdout.log`.

- El lote del 24-09 `20260924-130837-market-0dcd6994` fallo en preflight a las
  15:16 Madrid, 0/46, con `chatgpt_firefox_navigation_failed: prompt_not_available`.
  Checkpoint: `logs/batch/2026-09-24/13-12-52/pipeline_state.json`.
  Se corrigio la clasificacion del error: dos reinicios acotados del worker;
  si sigue fallando, preflight conserva los otros workers sanos. Los fallos de
  arranque guardan PNG/HTML/texto/JSON en `logs/browser_startup/worker-N/`.
  La comprobacion real sin enviar analisis abrio correctamente los 3 workers.
  Pruebas de navegador: 60 correctas. La reanudacion archiva el fatal_error
  previo y vuelve a running, sin dejar C4 permanentemente en failed.
- C4 se leyo directamente en Mercado el 24-09: ya mostraba `FALLO` (con tilde),
  fondo rojo. Apps Script remoto coincide con el local; no se ha publicado
  ningun cambio de la hoja. No se pudo confirmar la causa del vacio anterior.
- El usuario autorizo explicitamente enviar AMD y reanudar los 46 por Web.
  El primer smoke detecto otro cambio real del menu: al abrirlo el boton pierde
  las antiguas marcas de datos y muestra `Esfuerzo de razonamiento`. Se corrigio
  Selenium y Playwright para reconocer el titulo, abrir `Seleccionar modelo`,
  confirmar Sol y controlar el nuevo slider con el menuitem de flechas (su
  thumb ARIA esta oculto). Evidencia: diagnosticos AMD del 24-09 a las 14:01 UTC.
  El segundo smoke termino el 24-09 a las 14:12 UTC: provider chatgpt-browser,
  Sol/high, un intento, cero reintentos y cero fallback; validacion independiente
  correcta. Regresion total enfocada: 85 pruebas (60 navegador, 3 reanudacion,
  22 pipeline/progreso). Se lanzo la recuperacion del checkpoint original con
  `scripts/resume_batch_command.py`; log en
  `logs/incidents/20260924-browser-startup/resume.stdout.log`. Confirmar el
  heartbeat/progreso actual antes de asumir que sigue vivo.
- Reanudacion comprobada el 24-09 a las 16:16 Madrid: heartbeat nuevo,
  fase prepare (AMD/MRNA), sin fatal_error activo; lectura directa de Mercado!C4
  devuelve `RUNNING 0/46` con fondo verde. El batch sigue en curso, no terminado.
- El lote recuperado del 23-09 termino 47/47 segun `resume2.stdout.log`; las
  notas de progreso de 17/47 mas abajo son historicas, no el estado vigente.

- Incidente del 23-09, orden `20260923-160945-market-f8749c05`, checkpoint
  `logs/batch/2026-09-23/16-13-20/pipeline_state.json`: lote reanudado tras
  parada controlada para reparar IBKR y bloqueos de GCS. Copia previa en
  `logs/incidents/20260923-ibkr-recovery/batch-before-stop/`.
- El aviso de `ibg.xml` reaparecia desde el 21-08, incluso tras la prueba limpia
  del 20-08. El perfil rechazado se archivo en
  `.local/ibgateway-settings-archive/account-before-clean-reset-20260923/`.
  El nuevo perfil paso el primer arranque y dos reinicios en frio sin aviso,
  con handshake real y noticias de IONQ correctos. Ante otra repeticion exacta
  del error, el manager conserva y recrea exclusivamente el perfil identificado
  una vez; una segunda repeticion falla explicitamente.
- Se confirmo ademas un candado GCS con PID terminado `30088`: OpenProcess
  devolvia un handle aunque el proceso habia finalizado. Ahora se consulta
  GetExitCodeProcess. Noticias de RKLB completas (GCS + IBKR) funcionaron en
  menos de cuatro segundos despues del arreglo. Los timeouts de noticias solo
  reinician Gateway si falla su handshake, y los subprocess de noticias,
  lecturas GCS, progreso y etapas terminan su arbol Windows al agotar el plazo.
  Gcloud usa un proceso/un hilo por defecto porque el batch ya paraleliza
  objetos. La publicacion pendiente de MRVL se recupero sin regenerar analisis.
- La prueba real de CRDO genero y valido por ChatGPT Web en un intento, sin
  fallback. El lote se reanudo a las 19:49 Madrid con el mismo command_id y
  checkpoint mediante `scripts/resume_batch_command.py`; log
  `logs/incidents/20260923-ibkr-recovery/resume2.stdout.log`. La configuracion
  GCS habia reordenado los mismos 47 tickers: la reanudacion conserva ahora el
  orden del checkpoint y los metadatos de cada registro, rechazando cambios
  de conjunto. Regresion enfocada: 53 pruebas correctas. No interpretar los
  cuatro fallbacks y reintentos anteriores a la reparacion como errores nuevos.
- Comprobacion de las 19:53 Madrid: 17/47 publicados (13 antes de la parada),
  heartbeat local y remoto renovado, tres workers activos en `wait_response`
  (CAT/RDDT/ASML), ningun stall activo y ningun nuevo arranque Gateway desde
  el segundo reinicio de prueba a las 19:27. El lote sigue en curso; esto no
  certifica todavia el resultado final ni un lote entero sin fallback.

- La orden `20260922-102347-market-4a20967d` termino inicialmente 16/47. La
  causa Web fue una comprobacion fragil del proyecto: la URL actual conserva el
  identificador `g-p-*` pero ya no siempre el slug `-analisis` ni el antiguo
  control ARIA. Tambien faltaba reconocer el boton ingles `Retry`. El runner ya
  compara el identificador estable del proyecto, acepta el contexto valido sin
  aquel ARIA, reconoce `Retry` y reinicia solo el worker afectado ante un estado
  de navegacion roto.
- Los 31 fallidos quedaron recuperados y publicados: `SNDK` paso primero como
  smoke real sin fallback y los otros 30 terminaron en
  `logs/batch/2026-09-22/13-37-28/`. Resultado conjunto: 31/31 por
  `chatgpt-browser`, primer intento, cero reintentos Web, cero reintentos de
  pipeline, cero fallback y cero fallos.
- El falso positivo de migracion de `Resistencia estructural` tambien quedo
  corregido. El validador reconoce siete formas observadas de declarar que no
  existia una resistencia previa, sin dejar de rechazar precios anteriores
  inventados.
- La columna `Res.` esta activa en ambos bloques de `Mercado`. El informe schema
  v6 entrega la resistencia estructural mas fuerte, independiente del objetivo
  operativo, con fuerza 0-100 y desglose verificable. Solo para tickers poseidos,
  la celda usa azul suave cuando el precio queda a 0,5-1,5 % de la zona y azul
  brillante cuando esta dentro o hasta un 0,5 % por debajo. Los tickers sin
  posicion conservan el fondo normal. `Res.` solo es visible si la resistencia
  es solida o superior (>=70/100); las debiles y moderadas quedan vacias.
  `Entrada` y `Washout` ya no repiten la resistencia en sus notas.
- El verde fosforito de `Entrada` y `Washout` queda reservado al precio dentro
  del rango; por encima no se aplica color de proximidad. Hasta un 1,5 % por
  debajo del limite inferior se usa verde suave y, mas abajo, rojo suave. El
  rojo de `Entrada` se suprime cuando el precio ya ha alcanzado el `Washout`
  visible, para que no coincida con un `Washout` fosforito. La configuracion
  runtime se publico y `/analysis/refresh` la aplico con respuesta HTTP 200.
- El layout runtime de 36 columnas se publico en GCS, la hoja se reconcilio,
  se repoblaron 47 valores, 15 referencias, los 47 informes y las 24 posiciones,
  y la verificacion final devolvio `OK tickers=47 market_rows=47 groups=14
  html_links=47 sort='Nota' sorted=True`. El verificador distingue ahora los
  marcos azules intencionados de fuerza >=85 de bordes internos residuales.
- Cloud Run sirve al 100 % la revision
  `stock-controller-deploy20260923191500`. Los jobs
  `stock-analysis-market-refresh` y `stock-analysis-report-refresh` estan
  `ENABLED` y completaron invocaciones posteriores sin codigo de error.
- Regresion final: 266 pruebas del motor y 10 subpruebas, 47 pruebas de
  integracion y 116 del controlador correctas.
- El estado local posterior a la recuperacion del dia 22 no describe el lote
  del dia 23. Consultar siempre su heartbeat, checkpoint y procesos actuales.

## Referencia historica del batch del 2026-09-21

- El 2026-09-21 se corrigieron las causas conocidas de los 13 fallbacks: la
  deteccion Web ya reconoce cambio del ultimo turno, actividad del agente y el
  control `Detener`; los adjuntos esperan la hidratacion de la interfaz; y la
  continuidad sin valor anterior distingue referencias tecnicas de una falsa
  atribucion al plan previo.
- Regresion local: 304 pruebas y 3 subpruebas correctas; el conjunto enfocado
  suma 102 pruebas correctas.
- Smokes reales posteriores al arreglo: `APP` y `RKLB` finalizaron mediante
  `chatgpt-browser`, `gpt-5.6-sol`, razonamiento `high`, un intento, cero
  reintentos y validacion correcta. Falta todavia un batch completo de
  validacion antes de dar por cerrado el incidente a escala de mercado.

- Orden historica: `20260921-114944-market-8ad5bf32`.
- Batch local historico: `logs/batch/2026-09-21/11-54-11/`.
- Resultado funcional: 47/47 publicados en 1 h 35 min.
- Resultado del proveedor: 34 ChatGPT Web y 13 Codex fallback.
- Reintentos: 17 internos de Web y 3 completos de pipeline.
- No hubo bloqueos por demasiadas solicitudes.
- Medias Web registradas: 184,6 s de cola, 249,1 s de ejecucion real y 73,6 s
  fuera de Web por intento completado.

Ese `47/47` historico solo significaba que todos los tickers acabaron
publicados; no demostraba que el flujo Web estuviera sano. Sus 13 fallbacks ya
fueron auditados y la recuperacion real posterior de 31 tickers fue totalmente
Web, pero aun conviene observar el siguiente lote natural completo.

## Incidente corregido; pendiente validacion de batch

Los 13 tickers que terminaron en fallback fueron `INTC`, `ORCL`, `NBIS`,
`ASML`, `RDDT`, `RKLB`, `LEU`, `CCJ`, `INOD`, `USAR`, `APP`, `QBTS` y `OKLO`.
La auditoria de las evidencias conservadas agrupo los fallos asi:

- `chatgpt_send_not_started` y
  `chatgpt_send_control_not_ready_after_local_recovery`: afectaron a la mayoria.
  Eran falsos negativos cuando ChatGPT virtualizaba los turnos: en varias
  capturas la peticion, la actividad y hasta la respuesta completa estaban
  visibles. El detector ahora combina snapshot del ultimo turno, actividad del
  agente, bloque Markdown y control `Detener`, evitando tambien el segundo clic.
- `chatgpt_attachment_control_not_found`: en ambos intentos de `CCJ` la pagina
  seguia en `Loading profile`. El runner ahora espera la hidratacion del input o
  del menu de adjuntos antes de fallar.
- `chatgpt_assistant_response_not_started`: en `OKLO` ya existian `Pensando`,
  actividad de herramientas y el control `Detener`, aunque aun no existia el
  contenedor final de assistant. Esas señales ahora cuentan como inicio real y
  mantienen viva la espera hasta el timeout total.
- `invented_previous_level: Entrada ambiciosa has no authoritative prior
  value`: el validador confundia referencias historicas en `Factores` con una
  atribucion al plan anterior. Ahora solo rechaza una afirmacion explicita de
  continuidad inventada, y el prompt prohibe usar formulas de continuidad
  cuando el valor figura como `no extraida`.
- `ASML` tuvo una respuesta corregida completa visible que el contador de turnos
  no reconocio; queda cubierto por la misma correccion de virtualizacion.

Tambien se registro al menos un timeout al subir
`commands/progress/latest.json` a GCS. Fue una advertencia recuperable, pero
puede hacer que `C4` parezca parado aunque el batch siga trabajando.

### Evidencia autoritativa

- Resultado de la orden:
  `logs/command_worker/2026-09-21/20260921-114944-market-8ad5bf32.json`.
- Resumen y proveedores:
  `logs/batch/2026-09-21/11-54-11/summary.json`.
- Progreso, contadores y tiempos:
  `logs/batch/2026-09-21/11-54-11/sheet_progress.json`.
- Estado durable para reanudacion:
  `logs/batch/2026-09-21/11-54-11/pipeline_state.json`.
- Anomalias temporales:
  `logs/batch/2026-09-21/11-54-11/stall_events.jsonl`.
- Capturas por intento:
  `output/<TICKER>/browser_diagnostics/` (`.json`, `.png`, `.html` y `.txt`).
- Progreso remoto:
  `gs://stock-analysis-reports-naxo85/commands/progress/latest.json`.

No diagnosticar solo con `C4`, la ventana de Firefox o el ultimo texto de la
consola. Son superficies parciales.

## Protocolo para un lote atascado o fallido

1. Identificar `command_id` y batch exactos. Leer primero el progreso remoto,
   el resultado de `command_worker` y `sheet_progress.json`.
2. Comprobar heartbeat, fase, ticker, worker, intento y `active_stage`. Separar
   espera de cola, ejecucion Web real y tiempo no Web.
3. Abrir el diagnostico exacto del intento. Comparar JSON, PNG, HTML y texto
   antes de concluir que fallo la carga, el envio o la respuesta.
4. Distinguir tres niveles: reintento Web, fallback Codex y reintento completo
   del pipeline. Un ticker publicado puede haber atravesado los tres.
5. Si se esta afinando ChatGPT Web, reproducir con un solo ticker,
   `--no-generator-fallback` y un solo intento visible. El fallback puede
   terminar el ticker, pero oculta el defecto que se intenta corregir.
6. Si cambia la interfaz, seguir entero
   `docs/chatgpt_browser_provider.md#interface-change-runbook`; no parchear un
   selector aislado sin revisar compositor, adjuntos, envio, stop y mensajes.
7. Conservar checkpoint y diagnosticos antes de detener. Reanudar con
   `--resume-pipeline-from` en vez de iniciar otro lote que duplique trabajo.
8. Tras el arreglo, ejecutar primero una prueba Web real de un ticker sin
   fallback. Solo despues validar un lote completo y comparar fallbacks,
   reintentos, stalls y duracion con este baseline.
9. No declarar un incidente resuelto porque el batch publique 47/47. La
   condicion de cierre es que la causa concreta quede reproducida, corregida y
   cubierta por prueba o por un lote real verificable.

## Arquitectura que no debe confundirse

- El flujo vigente es `Mercado`; Trading/Core son compatibilidad legacy y no
  deben reaparecer en la hoja principal.
- ChatGPT Web con GPT-5.6 Sol y razonamiento Alta es la ruta principal y tiene
  autoridad para aplicar cambios materiales.
- Codex es fallback automatico. El usuario retiro la propuesta de politica
  temporal Sol/Tierra, recuento nuevo por modelo y fecha Sol-equivalente.
- Hay tres trabajadores Firefox persistentes. `--max-parallel 6` permite
  solapar preparacion, analisis y publicacion, pero no crea seis sesiones Web.
- Cada trabajador agrupa cinco tickers por chat. El usuario confirmo que ya
  estan dentro del proyecto `Analisis`; conservarlos. El batch ya no programa
  borrado diferido ni hace falta renombrarlos.
- `C4` es un espejo de progreso. La fuente de verdad es GCS mas los artefactos
  locales del batch.
- Un estado final `completed` en progreso y un resultado `ok` de la orden son
  diferentes de un lote Web sin fallback.

## Trabajo terminado en esta sesion

Se implemento la administracion de posiciones y seguimiento desde el menu
`Analisis IA`:

- `He comprado 1 shot...` suma un shot; si el ticker es nuevo, solicita grupo
  y lo incorpora al seguimiento.
- `He vendido 1 shot...` resta un shot; vender el ultimo conserva el ticker sin
  color.
- `Quitar ticker del seguimiento...` elimina seguimiento y posicion restante.
- La orden incluye una fotografia de colores/shots de toda la hoja para
  reconciliar configuracion local obsoleta antes de aplicar el cambio.
- Estas ordenes no escriben estado de analisis ni deben tocar `C4`.
- Se actualizan conjuntamente layout, cartera, universo, colores, banda del
  grupo y columnas `Pos.`/`Shots`.
- El layout vivo se publica en
  `gs://stock-analysis-system-naxo85/runtime/config/market_sheet_layout.json`.

Archivos principales:

- `apps_script/market_portfolio_menu.gs`
- `apps_script/export_tickers_to_gcs.gs`
- `apps_script/analysis_command_queue.gs`
- `src/local_runner/manage_market_tracking.py`
- `src/local_runner/command_worker.py`
- `gcp_services/stock_controller/src/stock_analysis/controller/sheet_layout.py`

El Apps Script real fue actualizado y el menu se verifico en la hoja. Se abrio
el dialogo de compra y se cancelo; falta una operacion reversible real de
extremo a extremo para validar persistencia, refresco cloud y contadores.

El controlador cloud sirve al 100 % la revision
`stock-controller-quote-groups-fix-20260929`, comprobada con el refresco de
las 18:37 UTC. Se descubrio anteriormente que un despliegue podia
crear una revision correcta y dejar el trafico fijado a la anterior; el script
de despliegue ahora usa sufijo unico y fuerza `--to-latest`. Siempre comprobar
revision servida y trafico, no solo que `gcloud run deploy` termine bien.

## Verificacion realizada

- `tests/test_command_worker.py`: 17 pruebas correctas.
- `tests/test_market_tracking.py`: 6 pruebas correctas.
- `tests/test_market_analysis_menu.js`: correcto.
- `gcp_services/stock_controller/tests/test_sheet_layout.py`: 17 correctas.
- `gcp_services/stock_controller/tests/test_portfolio_sheet.py`: 8 correctas.
- Total de esta funcionalidad: 48 pruebas Python mas la prueba JavaScript.
- Ruff no estaba instalado en el entorno, por lo que no se ejecuto.

## Prioridad recomendada para la siguiente sesion

1. Observar el siguiente lote natural de 47 tickers y confirmar que mantiene la
   ruta Web sin `project_not_open`, reintentos ni fallback; la recuperacion real
   de los 31 fallidos ya fue limpia.
2. Verificar que `C4` se vacia al finalizar y que un timeout de subida de
   progreso se reintenta o reconcilia sin dejar estado enganoso.
3. Ejecutar una compra/venta reversible desde el menu y comprobar hoja, GCS y
   refresco posterior.
4. Observar en un refresco natural de premarket/postmarket un ticker sin
   bid/ask y confirmar que su nota muestra la edad de la muestra conservada.
   El despliegue, la ordenacion de grupos y la cache GCS ya estan verificados.
5. Continuar el resto de `docs/pending_work_current.md`. Los chats y la
   politica Sol/Tierra retirada no requieren trabajo.

## Precauciones del workspace

- El arbol de trabajo contiene muchos cambios y archivos nuevos acumulados.
  No revertir, limpiar ni reformatear en masa.
- `incoming_from_gcp/` es referencia legacy; no es la fuente de verdad.
- Usar `.venv\Scripts\python.exe` para Python del repositorio.
- En Windows, invocar Google Cloud como `cmd /c gcloud.cmd ...`.
- Los cambios de Apps Script no estan activos por existir localmente: hay que
  publicarlos en el proyecto real y recargar la hoja.
- Los cambios del controlador no estan activos hasta desplegar una revision y
  confirmar que recibe el 100 % del trafico.
