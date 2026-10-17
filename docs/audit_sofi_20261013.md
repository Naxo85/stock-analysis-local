# SOFI — rechazo de relaciones dentro del mismo plan

Orden20261013-090123-968-market-a7509600, lote09-03-29, revision28.
Resultado historico45/46:36retain,9update,SOFI failed. Las seis revisiones extra
de tickers publicados eran reparaciones medium, NO seis informes full. SOFI tuvo
ademas su propia reparacion:46 llamadas iniciales+7reparaciones=53,0full high.

## Causa comprobada

SOFI propuso retirar compra15.50–15.56 y promover washout14.88–14.92 a entrada
principal, sin segunda alternativa. Ambos mensajes originales quedaron completos;
no timeout, falta de datos ni fallo de transporte. Primera respuesta09:10:30Z,
reparacion09:12:14Z. El retry de lote reutilizo recibos y repitio el rechazo,
no hizo una tercera llamada y no recupero SOFI.

1. validate_change exigia que cada referencia previa al plan fuera el MISMO
   campo que se edita. Rechazo s36(washout) al promoverlo a entry, y s37(entry)
   al explicar por que desaparece el duplicado de washout. Esto contradice la
   operacion de promover un soporte existente permitida por la politica.
2. El current_evidence del washout combinaba fuentes actuales con s40, el stop
   estructural protegido del CURRENT, como restriccion para alternativas.
   El control lo trataba como si se intentara acreditar un dato de mercado nuevo.
3. Cada bloque abortaba al primer error: la reparacion recibio los dos rechazos
   unrelated_previous_block, NO el problema posterior de scope. Lo arreglo y
   entonces aparecio wrong_scope_current_evidence. La prueba previa no cubria
   una promocion entre campos con restriccion protegida;207tests no lo certificaban.

## Correccion sistemica

Para contratos>=28, el validador distingue observacion actual, contexto del plan
autenticado y evidencia historica. Referencias a otros campos complementan, no
sustituyen, la evidencia de la decision previa afectada. Un contexto del plan no
sustituye la fuente actual exigida por backing_changed/material_improvement.
prior_error conserva su permiso historico anterior. Origen de nueva zona,
autoridad, stops, geometria, riesgo y binding se verifican por separado, intactos.
Los roles se derivan en codigo y quedan en audit, no se publican como prosa.

Todos los errores independientes se recogen con campo/token/pointer y se pasan
completos a la unica reparacion. No mas rondas, modelos ni fallback; no filtros
de redaccion ni conversion de historia en observacion actual. <=27 sin cambios.
No hace falta otra revision de prompts: la operacion ya estaba permitida.

## Evidencia de verificacion y estado

Ambas respuestas ORIGINALES de SOFI pasan ahora con su binding original,
sin quitar/mover fuentes, editar texto, precios, puntuaciones o stops. Tests
comparan tambien autoridad y contenido inmutados. No equivale a certificar
por codigo el juicio financiero: demuestra que desaparece el rechazo espurio.

test_plan_evidence_roles.py reproduce originales y ataques: solo datos historicos,
campo previo ajeno sin ancla propia, referencias desconocidas, scope erroneo,
errores multiples en una sola reparacion, binding alterado, cambios de stops,
riesgo estructural, zonas inventadas/invertidas y contrato antiguo.
Primera bateria183tests+226subtests; segunda92tests+133subtests, con cinco negativos
adicionales e integracion de riesgo/stops/aritmetica. Ambas pasan;16tests comunes.
No modelo, nuevo lote, recovery ni publicacion. SOFI sigue con informe anterior;
la orden original conserva45/46 y su fallo, no se ha falseado como exito.
