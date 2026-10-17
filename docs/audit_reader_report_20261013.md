# Revision32: separar informe visible de memoria financiera

## Peticion y alcance

El usuario elimina Tesis/Setup como secciones publicas, no quiere introducir
esas etiquetas dentro del resumen y elimina la conclusion redundante. Quiere
ocultar catalizadores menores/antiguos sin impacto actual sin olvidar sus hechos
y fechas; mantener un evento util y un plan breve. No solicito alterar notas,
rubrica, niveles, modelos, esfuerzos, ITV5 o concurrencia.

## Implementacion

- `reader_report.py` renderiza resumen independiente, catalizadores seleccionados,
  evento util y plan. Conserva notas sustantivas y procedencia temporal.
- Puntuaciones, razones y conclusion siguen en JSON interno. El parser de hoja
  obtiene los mismos valores desde datos tipados, no desde encabezados eliminados.
- Full32 selecciona `show_in_report`; se separa del registro financiero mediante
  identidades derivadas por codigo del contenido exacto de cada evento.
- Mantenimiento32 recibe catalogo CURRENT autenticado y seleccion nullable
  `reader_review`. Puede acompanarse de retain: no es una actualizacion financiera.
- Ningun corte por edad, nota o cantidad. Hechos ocultos permanecen completos en
  semantic_data y contexto; hechos materialmente adversos no deben ocultarse.
- Seleccion incompleta/invalida conserva la vista; flags full invalidos muestran
  el hecho. No causa fallo financiero ni llamada adicional. El schema enviado al
  modelo sigue siendo explicito; solo la validacion editorial es conservadora.
- IDs desconocidos nunca eligen otro elemento; reordenar no cambia identidad;
  un evento cuyo contenido cambia no hereda automaticamente una ocultacion vieja.
- Migracion natural retain/update autentica bases, recalcula proyeccion, conserva
  fechas/ITV/ancla y vuelve a vincular memoria. No modifica artefactos originales.
- No se reescribe narrativa heredada protegida por estilo. El siguiente full
  natural redactara el resumen independiente; no se paga Sol para acortarlo.
- Preparaciones<=31 mantienen prompts/schemas/render congelados. Legacy no
  estructurado queda fuera de la migracion por seguridad.

## Verificacion offline

`test_reader_report_v32.py`:16 tests cubren render y JSON financiero, igualdad
de registro parseado para la hoja, noticias viejas relevantes y recientes menores,
no borrar memoria, restaurar visibilidad, reordenar y cambio de evento, flags
erroneos, migracion retain idempotente, contexto futuro, respuesta full32 vinculada
al recibo, riesgo protegido, staging/publicacion retain sin nuevo modelo, update
real SOFI y preparacion congelada32 frente a render original31.

Regresion:100 tests +44 subtests en reader_budgets_v30, plan_scope_v29,
semantic_presentation, semantic_contract_v3, adaptive_luna_repair,
volume_arithmetic y plan_evidence_roles.

Tras endurecer tolerancia editorial y ampliar pruebas:43 tests +32 subtests
correctos (reader_report_v32, semantic_contract_v3, semantic_presentation).
No equivalen a un smoke de modelo ni garantizan su criterio editorial.

## Activacion

Config32 para nuevas preparaciones. Modelos medium/high, ITV5 y cap6 intactos.
Sin ejecucion de modelos, lote duplicado, publicaciones, recovery ni cambios cloud.
Observar el siguiente run natural; los informes existentes no se republicaron.
