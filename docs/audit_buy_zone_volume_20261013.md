# Herencia de Volumen al cambiar el papel de una compra

## Evidencia original

Lote `logs/batch/2026-10-13/12-41-28`, orden
`20261013-123945-market-full31`, final 44/46 con CRWV y MU fallidos.
Sus `report.response`, `report.receipt.json` y `input.json` no se modifican.
Ambos errores: `entry: select_profile_and_reaction_sources`.

- CRWV promueve el washout75.6-76.1 a entrada, Volumen10, componentes intactos.
- MU promueve el washout914-921 a entrada, Volumen16, componentes intactos.
- Ambos seleccionan el bloque del CURRENT como antecedente y fuentes actuales
  para su decision. No afirman haber calculado de nuevo el Volumen heredado.

## Causa y correccion

La exencion existente para una cuenta heredada comparaba solamente con el
campo anterior del mismo nombre. El contrato financiero ya permitia trasladar
un bloque comprador entre Entry y Washout, pero el contrato aritmetico perdia
esa identidad y exigia una medicion nueva. No era un defecto de puntuacion,
un error matematico ni una necesidad de regenerar el informe.

`volume_arithmetic._inherited_buy_volume` reconoce, desde el contrato28,
una cita explicita del bloque comprador opuesto del CURRENT autenticado,
con rango y componente Volumen exactos y `volume_calculation=null`.
La procedencia historica sigue en resolved_facts; no se inventa una medicion
actual ni se copia otra fecha al texto. No se cambia la decision del modelo.

No se extiende la exencion a resistencias, anclas Sol antiguas, rangos
aproximados, cambios de Volumen o citas que solo contienen una cifra.
Una cuenta declarada siempre se valida. Las otras comprobaciones de origen,
materialidad, evidencia, riesgo, geometria y recibos permanecen intactas.
Contratos<=27 mantienen su comportamiento. Prompts/schema/config exactos:
es una correccion del validador compartido, no nueva estrategia financiera.

## Verificacion

`tests/test_buy_zone_volume_inheritance.py` reproduce el fallo con la rama
anterior y valida ambos recibos reales sin modificar el hash de entrada.
Reconstruye guards/review_flags/ITV registrados en report.input.json, no los
de hoy; bind_response autentica el contexto completo contra el recibo original.
Incluye promocion y democion, ruta full/mantenimiento, calculos explicitos,
cambios de rango/Volumen, falta de cita, ancla/resistencia no autorizadas,
fuente parcial, CURRENT adulterado y contratos antiguos.
El replay compara documentos completos antes/despues para los recibos validos
de full29 y full31: contenido, cifras, fechas y fuentes, no solo pasa/no pasa.
Se acompana de las baterias de aritmetica, roles de evidencia, direccion de
reacciones, binding y reparacion de mantenimiento existentes.

Sin modelos, operaciones cloud, modificaciones de informes publicados ni
checkpoint. Los originales fallidos siguen historicos; validar offline no
significa publicarlos. No se reinicio ni interrumpio el lote.
