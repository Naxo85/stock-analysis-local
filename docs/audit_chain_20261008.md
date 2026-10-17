# Auditoria de continuidad Luna / Sol — 8 octubre 2026

## Alcance y evidencia

Auditoria offline de la cadena preparacion -> entrada real -> mantenimiento ->
reparacion -> Sol -> publicacion. Originales: lote 2026-10-08/14-53-35, orden
20261008-145055-309-market-ee431061. Historico: 45/46 publicados, 37 conservados,
7 Luna, 1 Sol (IREN), AMAT fallido. No reinterpretar ese resultado como revision21.
No modelos, lote duplicado, noticias nuevas, Gateway ni publicaciones de prueba.

## Hallazgos y correcciones de base

| Hallazgo | Causa | Cambio y conservacion comprobable |
|---|---|---|
| USAR: conclusion historica correcta acusada de error | Comparar una frase heredada con el precio del contenedor actualizado | Procedencia por apartado creada por el runner; la conclusion original tiene precio 13.515 dentro de 13.45–13.55, no 13.265. Fecha desconocida se declara desconocida. Nunca inferirla de la fecha actual. |
| MU: cinco motivos sustituidos por texto generico | Una justificacion global permitia reescribir todo el plan; el contrato anterior incentivaba copiarlo | Cada texto editado lleva su propia revision. Null hereda contenido exacto y procedencia. Una correccion de Entrada no da autoridad sobre los otros cinco apartados. Sin clasificador de frases. |
| Fecha perdida al encadenar mantenimientos | Proyeccion financiera omitia fechas de motivos y el contenedor se renovaba | text_provenance persistente, visible en entrada de ambos modelos y render. Texto identico conserva fecha; texto realmente editado recibe snapshot nuevo. Fuentes heredadas no renuevan su primera procedencia. |
| Motivo del stop estructural editable por explicacion conjunta | Bypass de la proteccion del bloque numerico | En schema21 ese campo solo acepta null. No se altera su texto ni su valor con Luna. |
| IREN individual sin posicion, lote con posicion | --owned omitido equivalia a false, sin consultar cartera | Individual lee el mismo config/tickers.json del mercado; ausencia/dato invalido no equivalen a false. --owned / --no-owned son elecciones explicitas. Lote de tickers escritos a mano consulta una vez la misma fuente. |
| Copia literal contabilizada como nuevo informe | update con texto identico no era no-op | Igualdad exacta sin cambios numericos conserva informe/fecha. Riesgo y cobertura se evalúan igualmente; no se decide equivalencia semantica por codigo. |
| JSON mal formado podia comprar Sol tras repair | Rechazo generico no distinguia contrato de riesgo | En21 un error de contrato tipado repetido queda visible tras UNA correccion; no paga Sol por el formato. Riesgos/ITV independientes siguen Sol. |

## Casos y limites de la conclusion

- WDC: cambio de estadistica de madurez ya presente en la revision anterior;
  correccion retrasada, no una nueva perdida de defensa. Se conserva resultado
  financiero de la propuesta original valida; nota anterior no se borra.
- NBIS: cambio real de gamma entre revisiones; pared230 ya existia. No se fuerza
  a conservar ni a cambiar su puntuacion con una regla nueva.
- SPCX: ampliacion de flota defendible como nota rutinaria; log contiene busqueda,
  no cuerpo completo que verifique todos los detalles numericos. Herramientas y
  fuentes se transfieren como descubrimiento, NO como hechos comprobados.
- MRNA/MU: separar frase valida en observacion antigua de operabilidad actual.
  La reparacion no debe reescribir toda la conclusion por un nuevo precio.
- OKLO: ya estaba bajo la entrada en la ultima revision; ese movimiento no es
  nuevo respecto al ultimo retain. Contrato21 exige esa comparacion, sin inventar
  confirmacion de ruptura ni una regla porcentual.
- AMAT: fixture21 permite una correccion acotada del motivo, mantiene la comparacion
  historica520.08->517.27, conclusion, otras razones y todas las cifras.
  La fecha original de ese motivo no esta registrada: el test NO demuestra que
  su frase historica fuera falsa. No usar517.27 como fecha/precio de cada parrafo.

Los candidatos alternativos de las pruebas son escritos deliberadamente para
probar el contrato; NO son respuestas nuevas de Luna ni prueba de que tomara
siempre esas decisiones. Citar fuentes existentes no demuestra toda una prosa.
Cada modelo aun puede equivocarse en materialidad o explicar mal una fuente.

## Matriz de no regresion

- Recibos originales19 reconstruidos con el mismo hash; archivos originales intactos.
- Los37 retain originales siguen retain (incluida reparacion original de AMD).
- WDC/NBIS/SPCX conservan textos financieros, cifras y puntuaciones originales;
  se reconstruye tambien la investigacion SPCX desde sus eventos/recibo real.
- MU/AMAT: correccion acotada mantiene motivos no afectados, precios, fuerzas,
  Setup, conclusion, notas y fuentes historicas validas.
- Dos mantenimientos consecutivos y transporte serializado conservan fechas;
  falta de procedencia no se rellena con una fecha inventada.
- Retain/update una llamada; repair una adicional; ITV llama Sol directamente.
  Error contractual repetido visible; riesgo no ocultado por no-op ni por texto.
- Publicacion antigua no pisa base/ancla/revision mas reciente; fallos de subida
  no se convierten en memoria publicada. Cobertura/news y fuentes protegidas.
- Modelos, esfuerzo, ITV5, concurrencia6, timeouts y limites financieros intactos.

## Estado historico

Verificacion:338 pruebas offline correctas en bateria conjunta tras activar21;
sin modelos/red/publicaciones de prueba. Compilacion correcta. diff --check de
archivos seguidos tocados correcto, salvo avisos normales de conversion LF/CRLF.
La comparacion de archivos publicados usa el Markdown autenticado completo,
incluido su banner historico; el render del cuerpo no contiene ese banner.

Este arreglo no republica los informes existentes ni recupera AMAT. Los motivos
perdidos en MU siguen en los originales anteriores y en las fixtures de auditoria;
no afirmar que se han restaurado en el informe publicado. Su restauracion puntual
debe preservar base vigente, fecha, ancla y memoria; no regenerar un lote para ello.
Medir el juicio real de revision21 en el proximo lote natural, no uno duplicado.
