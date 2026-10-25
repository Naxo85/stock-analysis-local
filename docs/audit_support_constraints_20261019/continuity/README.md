# Continuidad y ceros heredados — auditoría offline del 19-10-2026

**Recomendación: corregir de forma acotada la incorporación de evidencia nueva al juicio actual.** Existe un mecanismo comprobable que conserva Opciones=0 después de observar opciones aplicables. El motivo expreso en varios casos es que la cobertura anterior no permite demostrar un cambio del mercado. Eso evita correctamente inventar un incremento de OI, pero no resuelve si el juicio actual debe incorporar información que antes era desconocida. Es una ambigüedad de política/instrucciones y aplicación del juicio, no una prohibición numérica del validador.

La corrección debe permitir una actualización justificada del conocimiento con la misma rúbrica, rango y llamada ordinaria; no asignar puntos por contrato observado, por aparecer en TOP o para llegar a65. Tampoco obliga a cambiar todos los ceros ni prueba que ninguna zona concreta deba superar65.

## Alcance y reproducción

Lectura de contratos y resultados congelados de cinco lotes:14-Oct16:07,15-Oct07:21,15-Oct12:01,16-Oct15:58 y18-Oct09:08. Se leyeron handoff/backlog vigentes antes de la investigación. No se han llamado modelos, descargado datos, ejecutado lotes, cambiado producción ni publicado informes.

`analyze.py` genera `evidence.json` desde `input.json`, `triage.json` y `publish/current_state.json`. Empareja rangos exactos, permitiendo el cambio de slot Entry/Washout. No confunde una zona nueva con repuntuación de la misma. `inspect.py` ofrece vistas reducidas y trazas. Todos los archivos derivados permanecen en esta carpeta.

```text
.venv\Scripts\python.exe docs\audit_support_constraints_20261019\continuity\analyze.py
.venv\Scripts\python.exe docs\audit_support_constraints_20261019\continuity\inspect.py stats
.venv\Scripts\python.exe docs\audit_support_constraints_20261019\continuity\inspect.py compare_puts MP NVDA SPCX TSLA AMD INOD
```

El barrido de puts próximos usa medio ATR solamente para localizar casos que requieren lectura; **no es regla de pertinencia, soporte, puntuación ni compra**. Las cinco coincidencias exactas siguientes no dependen de esa distancia auxiliar. OI y porcentajes son los agregados gamma-elegibles de cada captura; no se comparan sus magnitudes entre coberturas como si fueran flujos.

## Qué está comprobado

En el18-Oct hay70 zonas activas,23 con Opciones=0. Las23 heredan el mismo rango y el mismo cero de CURRENT; ninguna nace ese día. Cinco tienen puts observados exactamente dentro de su rango. Una sexta, AMD, tiene puts próximos que el propio modelo utiliza como respaldo de viabilidad.

| Zona vigente | Total fechado | Opciones | Observación actual dentro del rango | Evidencia de continuidad |
|---|---:|---:|---|---|
| MP Entry37,7–38 |38|0|Put38:1.130OI,8,6% gamma put;140/153/837OI en23Oct/30Oct/6Nov|Reconoce corroboración actual; conserva0 por no poder demostrar cuánto cambió frente a cobertura anterior |
| NVDA Washout209,5–210,5 |51|0|Put210:16.879OI,13,5%;4.213/1.140/11.526OI en19/21/23Oct|Reconoce nueva cobertura; declara que no obliga a repuntuar |
| SPCX Entry144,75–145,5 |60|0|Put145:6.802OI,7,1%;498/384/5.920OI en19/21/23Oct|Conserva cero heredado y dice que cobertura nueva no demuestra error anterior |
| TSLA Entry353,5–355 |55|0|Put355:4.193OI,10,2%;2.008/1.997/188OI en19/23/26Oct|Promueve el antiguo Washout y conserva0; trata puts actuales como contexto adicional |
| INOD Entry52–52,5 |46|0|Put52:99OI,5,9%;73/20/6OI en23Oct/30Oct/6Nov|Cita horquillas amplias y escaso respaldo; caso menos concluyente de puntuación incorrecta |

Los primeros cuatro son evidencia clara de la dificultad de incorporar conocimiento favorable nuevo. La cantidad exacta de puntos sigue necesitando juicio financiero: concentración relativa, vecinos, distancia, liquidez y vencimientos. INOD ilustra por qué observación positiva no implica una nota elevada. La presencia contractual tampoco acredita defensa, flujo comprador o signo dealer.

Fuentes directas del lote18-Oct:

- [MP, motivo y evaluación](../../../logs/batch/2026-10-18/09-08-40/adaptive/MP/triage.json):líneas4 y23. CURRENT se originó15-Oct con0 por falta de concentración acreditada. Antes figuraban puts40/41/42/44/45; ahora38 está observado. No se conoce el valor anterior de38, por lo que no se demuestra nueva apertura de contratos.
- [NVDA, evaluación](../../../logs/batch/2026-10-18/09-08-40/adaptive/NVDA/triage.json):línea22. El Washout nació16-Oct con0 por no tener concentración verificable suministrada. El put210 no estaba en el TOP anterior y ahora sí. No convertir esa ausencia antigua en OI0 ni afirmar que todos los16.879 contratos son nuevos.
- [SPCX, evaluación](../../../logs/batch/2026-10-18/09-08-40/adaptive/SPCX/triage.json):línea22. La zona nació14-Oct con0 por falta de contrato aplicable observado. El15-Oct07:21 apareció put145 con13.277OI/7,0%;15-Oct12:01 dejó de estar en el TOP;16-Oct aparecía12.869OI/23,9%;18-Oct6.802OI/7,1%. Se mantuvo0 a través de esas observaciones. La comparación de cifras brutas no prueba crecimiento/caída económica por el cambio de expiraciones y elegibilidad.
- [TSLA, evaluación y factores](../../../logs/batch/2026-10-18/09-08-40/adaptive/TSLA/triage.json):líneas23 y81. El rango nació15-Oct12:01 con0 y sin put355 en la lista. El16-Oct se suministraban9.934OI/7,7% en355 y se retuvo el cero. El18-Oct el nuevo Washout350 recibe Opciones13, mientras el rango promovido que contiene355 conserva0. Ambos tienen contratos actuales con distribución por vencimientos. No son idénticos y sus notas no tienen que coincidir, pero el trato distinto por ser heredado/nuevo es explícito.
- [AMD](../../../logs/batch/2026-10-18/09-08-40/adaptive/AMD/triage.json):línea23. Total57 y Opciones0 en531–535. El modelo atribuye respaldo vigente a puts525/530; el530 está1punto bajo el rango,≈0,035ATR del borde, dentro de su extensión reconocida. Es un indicio adicional; la aplicabilidad al rango debe juzgarse, no asumirse por la proximidad.

## No es una explicación suficiente de toda la caída visible

| Lote | Zonas | Opciones0 | Visibles65 | Cambios de Opciones en rangos exactos heredados |
|---|---:|---:|---:|---|
|14-Oct16:07|66|8|24|+9 IONQ Entry |
|15-Oct07:21|63|15|17|+17 INTC, al promover el rango95 |
|15-Oct12:01|64|17|17|Ninguno |
|16-Oct15:58|71|25|14|+5 INTC, al promover el rango90 |
|18-Oct09:08|70|23|9|−4CAT,−3COIN,−5IONQ,−4IREN |

La mayoría de los ceros llegó con nuevos soportes inferiores: la composición de los rangos explica gran parte del descenso agregado. La auditoría general de esta investigación encuentra que sólo24 rangos exactos coinciden entre14 y18,19 conservan todos sus componentes; no hubo un descuento masivo de los mismos soportes. El punto de continuidad puede impedir que algunos se recuperen cuando llega evidencia, pero no explica por sí solo la caída24→9.

No debe prometerse recuperar un número de casillas. MP está en38: incluso asignar el máximo25 a Opciones, sin cambiar justificadamente otros componentes, daría63. NVDA necesitaría14, TSLA10, SPCX5 y AMD8 puntos adicionales para65 si sólo cambiara Opciones; son distancias aritméticas, **no puntuaciones propuestas**. Confluencia sólo puede cambiar si aparece una familia independiente pertinente, no por repetir OI ni por completar el umbral.

## Contraejemplos y límites

**El sistema sí permite subidas.** [INTC15-Oct](../../../logs/batch/2026-10-15/07-21-28/adaptive/INTC/triage.json) pasa Opciones0→17 al promover94,6–95,3; dice expresamente que la cobertura ahora observable no prueba apertura nueva. [INTC16-Oct](../../../logs/batch/2026-10-16/15-58-24/adaptive/INTC/triage.json) pasa13→18 al promover89,6–90,4, justificándolo con concentración y contribuciones observadas. Es inconsistencia de aplicación, no bloqueo universal.

**La continuidad también protege contra rebajas falsas.** Cuando desaparece una fila TOP o cambia el vencimiento dominante, el sistema no debe inferir que ha desaparecido todo el soporte. El18-Oct conserva componentes de muchas zonas pese a cambios de distribución y captura. Las cuatro rebajas de Opciones en el mismo rango tienen justificaciones de vencimiento/respaldo; no se han probado ilegítimas por el mero hecho de bajar.

**Evidencia nueva puede no ser material.** INOD99 contratos con horquillas amplias, un dato duplicado de la misma familia, un contrato no aplicable o un cambio sólo de etiqueta pueden no justificar modificación. La recomendación no sustituye juicio por un disparador automático.

## Mecanismo exacto y cambio recomendado

[strength_evidence_v31.md](../../../prompts/strength_evidence_v31.md):4–9 ordena separar cambio de soporte, respaldo, error y cobertura. Líneas21–24 dice correctamente que detalle antes desconocido no es pérdida ni evento financiero nuevo. Falta explicitar que **la nueva evidencia verificable sí puede alterar justificadamente el conocimiento actual**, aunque no demuestre cuándo apareció en el mercado.

[daily_maintenance_semantic_v40.md](../../../prompts/daily_maintenance_semantic_v40.md):58–72 exige motivo de cambio de CURRENT y origen de la alternativa; línea66 prohíbe repuntuación subjetiva de evidencia idéntica;111–112 limita recalcular a respaldo/decisión realmente cambiado. En los casos anteriores, el modelo extiende la cautela hasta conservar una puntuación basada en desconocimiento mientras utiliza positivamente el nuevo dato en la valoración actual.

[maintenance_change.py](../../../src/local_runner/maintenance_change.py):8–10 permite backing_changed, prior_error y material_improvement;197–260 valida vínculos y alcance, no demuestra verdad financiera. No contiene un comparador que impida0→positivo ni exige demostrar delta de OI. Añadir una clasificación de prosa o un mínimo de puntos sería un arreglo equivocado.

Propuesta concreta para una futura revisión autorizada:

1. Explicitar que hay tres causas diferentes: cambio de mercado probado, error pasado probado y actualización material del conocimiento. La tercera puede corregir una puntuación actual fundada en ausencia de observación; no acusa al informe anterior de error ni inventa una apertura/entrada de dinero.
2. Mantener la misma rúbrica y evaluación de viabilidad. Para cada componente afectado, identificar la premisa limitada anterior, qué observación nueva resuelve la carencia, su aplicabilidad y por qué cambia materialmente el juicio actual. Si sólo es otra copia del mismo hecho o detalle irrelevante, conservar.
3. Permitir usar la causa en la llamada ordinaria y en ambos roles. La vía mínima es definir expresamente material_improvement también para mejora de evidencia del mismo soporte; si se quiere máxima trazabilidad, introducir una causa nueva para preparaciones futuras. No reutilizar prior_error ni backing_changed con afirmaciones falsas para superar el contrato.
4. Heredar exactamente rangos y componentes no afectados. Opciones y Confluencia no cambian juntas automáticamente; Durabilidad valora el soporte completo. No mover el precio hacia un strike para facilitar una cita, no elevar notas para65 ni volver a exigir defensas nuevas de un soporte inferior prospectivo.
5. No volver a contabilizar la misma mejora en cada retain. Registrar la evidencia incorporada en el estado financiero/review con su fecha y procedencia. Un retain que sólo anotó la observación pero decidió no incorporarla tampoco debe convertirse en veto perpetuo: la siguiente revisión puede evaluar si ese juicio sigue siendo correcto.
6. Conservar originales, ancla, ITV, pesos, una reparación, ámbitos y controles de fuente/autoridad. Ninguna publicación retrospectiva ni lote duplicado para medir casillas. El próximo flujo natural observará el comportamiento.

Pruebas que harían concreta la futura corrección: MP/NVDA/SPCX/TSLA como casos de dato antes desconocido y ahora aplicable; INTC como subida ya permitida; un caso de contrato distante/horquilla inutilizable; nueva cobertura con los mismos hechos ya incorporados; ausencia TOP; expiración dominante con contribuciones futuras; misma referencia invocada dos veces; fuente actual inválida/expirada; igualdad de componentes no afectados y ancla. Las pruebas deterministas verifican contrato y herencia, **no validan la nota financiera ni el valor predictivo**.

## Conclusión

Sí conviene arreglar este punto, con prioridad alta por coherencia del juicio actual y sin garantía de aumentar soportes visibles. La evidencia confirma un atasco posible y varios casos concretos, además de contraejemplos que impiden llamarlo regla universal. Conviene conservar íntegramente la protección contra falsa pérdida por cobertura y contra repuntuación caprichosa, añadiendo una salida explícita para evidencia nueva material.
