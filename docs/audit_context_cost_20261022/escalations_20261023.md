# Cuatro escaladas automáticas del 23 de octubre

**Comprobadas: AMD, AMAT, SNDK y ASTS llegaron a Sol por una mezcla de errores
contractuales que las guardas individuales bloquean por separado. No hay un
disparador independiente de Sol registrado en esas respuestas.**

Auditoría sin modelo, red, recuperación ni publicación. Se comprobaron los hashes
de entrada y respuesta contra los recibos de las doce llamadas originales
(triage, reparación y full por ticker). Los 48 archivos examinados permanecieron
idénticos. Script: `audit_escalations_20261023.py`; evidencia:
`escalations_20261023.json`.

| Ticker | Incidencias tras reparar | Resultado del full |
|---|---|---|
| AMD | Setup y conclusión citan scope actual incorrecto; Entry omite evidencia de decisión previa; perfil de Volumen incorrecto en Washout | Publicado |
| AMAT | Setup cita scope actual incorrecto; perfiles de Volumen incorrectos en Entry y Washout | Publicado |
| SNDK | Setup y conclusión citan scope actual incorrecto; perfil de Volumen incorrecto en Entry | Publicado |
| ASTS | Setup cita scope actual incorrecto; selección incompleta de fuentes de perfil/reacciones en Entry | Fallido en el full |

En los cuatro: ITV no vencido, guards=[], decisiones originales y reparadas
`update`, uncertainty=false, evidence_gap=none, cuatro indicadores risk=false
y ningún grupo de noticias con critical_change. La reparación no pidió Sol.

## Causa en el código

`adaptive_stage.py` consulta `arithmetic_only`, `review_contract_only`,
`change_justification_only` y `source_selection_only` antes de llegar al fallback
`next=sol_review`. Cada función exige que TODAS las incidencias sean de su
categoría. Una combinación Volumen + justificación hace que todas devuelvan
false. Se reproduce en las cuatro listas exactas de segunda reparación: 4, 3,
3 y 2 incidencias respectivamente. Cada incidencia aislada sí queda bloqueada
por al menos una de esas guardas.

Por tanto, la mezcla de problemas de respuesta abrió una ruta que no se abre
para esos mismos problemas por separado. Es un defecto de composición del
enrutado respecto a la política vigente, no evidencia nueva de riesgo empresarial.
No se ha revalidado predictividad ni afirmado ausencia objetiva de todo riesgo
financiero: la conclusión concierne al disparador registrado de estas llamadas.

## Coste y consecuencia de corregirlo

Los cuatro full sumaron 826.517 tokens de entrada sin caché, 5.980.032 en caché
y 56.425 de salida (razonamiento incluido). No existe conversión demostrada de
estos valores al porcentaje semanal de Plus. Con el mismo resultado de Luna,
una guarda conjunta habría evitado esas cuatro llamadas y mantenido visibles
las propuestas fallidas: AMD/AMAT/SNDK dejarían de figurar como éxitos, ASTS
seguiría fallido. No aumentarían por sí solos los informes válidos.

Corrección propuesta: comprobar que CADA incidencia pertenece a alguna clase
ya excluida de Sol, en lugar de exigir una única clase para todo el conjunto.
Una incidencia desconocida/financiera, riesgo explícito, incertidumbre esencial,
guardas e ITV deben conservar su autoridad. No modificar respuestas, publicar
propuestas rechazadas, forzar retain ni añadir otra reparación automática.

No se implementó la corrección: el encargo era comprobar las escaladas.
La guía de Volumen posterior puede reducir rechazos, pero no cierra esta brecha.

## Alcance de la reproducción

Se ejecutó el replay de clasificadores con las incidencias completas archivadas
en el handoff de entrada a Sol y autenticadas por su recibo. Un intento adicional
de revalidación financiera integral offline fue interrumpido por duración sin
resultado final; no se contabiliza como aprobado. No se llamó al modelo, ni se
ejecutó el stage de análisis o publicación.
