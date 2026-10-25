# Revisión independiente de la corrección 41

Se implementó `prompts/strength_evidence_v41.md` sin editar el overlay congelado31.
La aclaración distingue la información adicional de cada componente, ausencia de
evidencia frente a evidencia adversa, vencimiento contractual frente a persistencia
del soporte completo y fundamentos heredados de signo dealer no identificado.
No asigna nuevas notas, familias obligatorias, pesos, umbrales ni una nueva puerta
de validación. Se mantiene el juicio financiero en la llamada ordinaria autorizada.

Los nuevos adaptive41 y financial14 se revisaron contra este overlay. La nueva
evidencia aplicable permite revisar materialmente conocimiento sin inventar un
cambio del mercado ni un error previo. Haber recibido, revisado e incorporado un
dato son hechos distintos. La simetría permite una nota mayor o menor; una retención
previa tampoco autoriza editar sin explicar por qué cambia el juicio actual.

## Pruebas de continuidad financiera

`tests/test_strength_evidence_v41.py` pasó **14/14 en131,70s** con:

```text
.venv\Scripts\python.exe -m pytest tests/test_strength_evidence_v41.py -q -p no:cacheprovider
```

Se reconstruyeron los guards, ITV y revisión originales y las fuentes de investigación
registradas. El lado40 autentica el recibo original real; el lado41 usa un recibo
sintético en memoria explícitamente identificado para comparar las mismas respuestas
bajo la nueva revisión, sin fingir una nueva ejecución del modelo.

Los ocho updates APP, CAT, COIN, IONQ, IREN, QBTS, SPCX y TSLA mantienen exactamente
rango, fortaleza, razón y campos comparados bajo40/41. Los cinco retains MP, NVDA,
KTOS, CRWV y RKLB no cambian de decisión por nota baja ni texto heredado. Se verificó
la inmutabilidad de los cuatro archivos originales usados por cada caso y el hash
del overlay31. Esto prueba continuidad de código y ausencia de una repuntuación
automática; **no** valida el nuevo juicio financiero del modelo ni predice cuántas
zonas serán visibles.

## Revisión adversarial source41

La identidad de formación verifica sesiones NYSE consecutivas: dos barras del gap
y cinco alrededor de cada pivote. Los resultados no observados/no disponibles no
se convierten en orígenes positivos. El runner exige cobertura de las identidades
exactas solicitadas antes de admitir el modelo; los campos actuales se enlazan
al catálogo ordinario. La observación de formación no concede por código viabilidad
ni retención, y el esquema de salida financiero permanece separado de esta captura.

Se encontró un defecto acotado en la evidencia auxiliar de la nueva lane: una
sesión ausente posterior a una formación válida no afectaba a `filled`/retests del
gap ni a la etiqueta de ventana completa de `historical_reaction`. La formación
seguía correctamente disponible; esos resúmenes auxiliares podían estar incompletos.
`path_evidence` ya excluía los contactos incompletos, pero la reacción agregada no.

Reproducciones de sólo lectura en `review_source41.py`: retirar WDC2026-04-09 o
CLS2026-08-24 del archivo descargado original mantiene la identidad disponible,
pero inicialmente dejaba `historical_reaction.status=available`,
`observation_policy=complete_forward_window_only` y excluidos incompletos0.
WDC además conservaba `filled=false` sin advertir la sesión ausente. Se notificó
al autor de source41 para corregir exclusivamente estos auxiliares de41, conservando
el origen y los contratos congelados.

Tras la corrección del autor, se repitieron independientemente ambas reproducciones:
WDC y CLS mantienen `status=available` para su formación; la reacción pasa a
`unavailable/missing_historical_session`. WDC deja `filled` sin valor y señala
`unavailable_missing_following_session`. Se revisó también que el pool sólo adjunte
metadatos de identidad a candidatos ordinarios cuya formación exacta pueda verificarse.
La corrección está confinada al nuevo carril41. No quedan hallazgos bloqueantes
identificados en esta revisión; permanecen los límites de cobertura histórica
declarados por las observaciones y la necesidad de juicio financiero ordinario.

No se ejecutaron modelos, nuevas descargas, lotes, publicación ni despliegue para
esta revisión. Las barras originales se copiaron antes de cada mutación sintética.
