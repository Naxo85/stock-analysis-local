> Contexto histórico: este documento conserva decisiones/evidencia de su época; no describe el motor vigente17-10-2026 ni autoriza ejecutar sus planes. Consulte [arquitectura actual](architecture.md), [motor adaptativo](codex_adaptive_analysis.md), [relevo](handoff_current.md) y [backlog](pending_work_current.md).

# Plan de referencias por modelos y automatización diaria

## 1. Objetivo

Reducir el consumo de los análisis recurrentes sin permitir que los modelos de
menor capacidad cambien de forma arbitraria la nota o la tesis vigente.

El sistema combinará:

- una referencia semanal autoritativa;
- seguimiento diario con un modelo más económico;
- escalado al modelo superior cuando aparezca un cambio material;
- ejecución automática local con Windows e IB Gateway/IBKR disponibles.

## 2. Decisiones cerradas

### 2.1 Niveles de modelo

| Nivel del ticker | Referencia | Seguimiento diario | Revisor superior |
|---|---|---|---|
| Prioritario | Sol `medium` | Tierra `medium` | Sol |
| Seguimiento | Tierra `medium` | Luna `medium` | Tierra; Sol si se promociona |

La configuración de esfuerzo inicial es `medium`. Se cambiará solo después de
comparaciones ciegas sobre inputs congelados y medición de calidad y consumo.

### 2.2 Propiedad y prioridad

La propiedad se obtiene de las hojas:

- Trading: columna C;
- Core: columna AF.

Reglas:

1. Un ticker poseído es prioritario y usa referencia Sol con independencia de su nota.
2. Un ticker no poseído sube al nivel Sol cuando una revisión superior confirma una nota de 7,0 o más.
3. Un ticker no poseído baja al nivel Tierra cuando una referencia Sol lo sitúa por debajo de 6,5.
4. Entre 6,5 y 6,9 conserva el nivel anterior para evitar cambios continuos.
5. Luna nunca puede promocionar directamente un ticker. Tierra debe confirmar primero el cambio y Sol debe confirmar la entrada al nivel prioritario.

La nota usada para clasificar será la nota oficial de la referencia confirmada,
no una propuesta diaria ni un valor provisional de la hoja.

### 2.3 Autoridad sobre la nota

- La nota oficial queda bloqueada por el modelo que creó la referencia vigente.
- Tierra o Luna pueden proponer una nota distinta, pero no publicarla directamente.
- Una propuesta diaria se guarda separada de la nota oficial.
- Si el revisor superior confirma el cambio, su informe pasa a ser la nueva referencia desde ese momento, aunque sea entre semana.

Campos mínimos de seguimiento:

```json
{
  "reference_model": "gpt-5.6-sol",
  "reference_generated_at": "2026-08-16T21:00:00Z",
  "reference_score": 7.2,
  "proposed_score": 7.2,
  "published_score": 7.2,
  "score_review_requested": false,
  "priority_reason": "owned_excel",
  "ownership_source": "trading:C"
}
```

## 3. Cambios materiales y puerta de confianza

El análisis diario marca un cambio como material cuando se cumple cualquiera de
estas condiciones:

1. Propone variar la nota en 1,0 punto o más respecto a la referencia. Este
   umbral es independiente del 7,0 usado para promocionar un ticker a Sol.
2. Detecta un catalizador nuevo de impacto alto.
3. Detecta un cambio material de tesis o narrativa.
4. Detecta un cambio estructural/técnico que invalida o transforma el escenario vigente.
5. Tierra confirma que un ticker de seguimiento debe alcanzar 7,0 o más y solicita su promoción a Sol.

Para cada cambio material el modelo informa por separado:

- confianza en que la referencia anterior ha quedado invalidada;
- confianza en que la propuesta nueva es mejor.

La confianza efectiva es el menor de ambos valores. Para Tierra, el runner
aplica estas bandas de forma determinista:

- menos de 65: no publica el cambio material ni llama al modelo superior; publica
  un seguimiento actual que conserva la nota y los niveles oficiales vigentes;
- de 65 a 84: retiene el candidato y llama al modelo superior;
- 85 o más: permite publicar directamente, manteniendo bloqueada la nota oficial;
- riesgo material urgente: llama al modelo superior con independencia del porcentaje.

Excepción acotada: un cambio `structural_technical` con evidencia fuerte puede
pedir revisión superior desde 60. Esta excepción nunca autoriza publicación
directa. Sirve para no mantener niveles objetivamente invalidados solo porque
la confianza quedó ligeramente por debajo de 65.

Cuando se conserva la referencia, `latest` pasa a ser un seguimiento fechado
en el día que incluye un aviso destacado y la referencia oficial completa. La
nota y los niveles de Sheets siguen saliendo de esa referencia; la celda de
Nota se marca en amarillo claro y explica en una nota qué fecha sigue siendo
oficial. El candidato material queda archivado aparte.

Luna tiene una autoridad más limitada:

- sin cambio material, publica el seguimiento y los ajustes operativos normales;
- con cambio material por debajo de 65, mantiene en el informe la conclusión
  discutida de la referencia, actualiza el resto y publica sin llamar a Tierra;
- con cambio material desde 65, retiene el candidato y llama a Tierra;
- con riesgo urgente, llama siempre a Tierra;
- Luna nunca publica directamente un cambio material, aunque declare 85-100.

El marcador `candidate_applies_material_change` confirma si el cuerpo del
informe incorporó la propuesta material. Para publicar por debajo de 65 con Luna
debe ser `false`; si Luna pide revisión debe ser `true`.

Los porcentajes tienen topes por evidencia: sin evidencia nueva verificable,
64; con evidencia débil o ambigua, 74; con evidencia fuerte pero sin apoyo
independiente, 84. Por tanto, superar 85 exige invalidación explícita, evidencia
fuerte y una segunda confirmación independiente.

Como control de calibración, una muestra determinista del 10 % de los cambios
materiales de Tierra que superarían 85 se envía igualmente a Sol. La muestra
es estable por ticker y fecha para que un reintento no cambie la decisión.

No provocan escalado por sí solos:

- cambios de categoría de nota;
- cambios rutinarios de entrada;
- ajustes de stop;
- pequeñas variaciones de soportes, resistencias o precio;
- vencimientos ordinarios de opciones.

Tierra y Luna pueden actualizar entradas cuando tengan una razón nueva y
concreta. El informe completo de referencia se incluirá en su input y se
marcará como autoritativo para evitar recalibraciones por estilo.

## 4. Flujo semanal

### 4.1 Domingo por la noche

La referencia semanal se genera el domingo por la noche, inicialmente a las
23:00 `Europe/Madrid`, con horario configurable.

1. Cargar Trading y Core, incluida la propiedad de C y AF.
2. Cargar la última referencia confirmada y determinar el nivel de cada ticker.
3. Comprobar IB Gateway/IBKR mediante conexión API real, no solo por puerto abierto.
4. Actualizar noticias, analistas y eventos de IBKR.
5. Preparar una vez los inputs vigentes.
6. Ejecutar Sol para el nivel prioritario.
7. Ejecutar Tierra para el nivel de seguimiento.
8. Validar, publicar y guardar cada resultado como nueva referencia semanal.
9. Escribir un resumen con modelo, tokens, duración, resultado y fecha de datos.

La ejecución del domingo es obligatoria aunque no haya una nueva sesión de
mercado, porque debe incorporar noticias del fin de semana y renovar la
referencia de la semana siguiente.

### 4.2 Opciones disponibles el domingo

Las expiraciones y cadenas de opciones utilizadas por el sistema proceden de
Tradier a través de `support_resistance_values`, no de TWS.

El domingo se utilizarán:

- las expiraciones semanales ya listadas;
- el open interest asentado del cierre del viernes;
- las últimas cotizaciones y griegas disponibles del viernes;
- gamma, walls, max pain y demás métricas derivadas de esa fotografía.

Cada referencia debe guardar y validar `options_as_of`. No se debe presentar la
fotografía del viernes como si procediera de negociación del domingo.

## 5. Flujo diario

### 5.1 Lunes a jueves

El seguimiento ordinario se ejecutará de lunes a jueves. El viernes, una vez
cerrado el mercado, no se repite el análisis porque el domingo se generará la
referencia semanal. El sábado también se omite. La hora automática queda
pendiente; mientras tanto el lanzamiento es manual desde Excel.

1. Verificar que no existe otro batch activo.
2. Comprobar IB Gateway/IBKR y actualizar las fuentes recientes.
3. Omitir el ticker si no hay nueva sesión, noticia ni evento desde la última ejecución.
4. Ejecutar Tierra para los tickers cuya referencia sea Sol.
5. Ejecutar Luna para los tickers cuya referencia sea Tierra.
6. Comparar cada candidato con su referencia autoritativa.
7. Aplicar la puerta de confianza y mantener bloqueada la nota oficial.
8. Para Tierra: conservar lo vigente por debajo de 65, revisar entre 65 y 84 y publicar desde 85.
9. Para Luna: publicar alineado con la conclusión anterior por debajo de 65 y llamar a Tierra desde 65.
10. Publicar únicamente el resultado confirmado del revisor cuando exista revisión.

El batch económico termina primero. Después se lanzan conjuntamente los
tickers marcados para revisión, respetando el límite de paralelismo.

### 5.2 Refresco de opciones del lunes

El lunes no se esperará a la mañana europea: antes de la apertura
estadounidense no existe negociación nueva de opciones.

Se programará un refresco técnico ligero a las 09:45 `America/New_York`, unos
15 minutos después de la apertura regular:

1. Volver a obtener cadena, OI, IV, griegas, gamma, walls y max pain.
2. Comparar la estructura con la fotografía usada el domingo.
3. No repetir por defecto el análisis completo con Sol.
4. Solicitar revisión superior solo si el cambio de opciones altera materialmente el escenario estructural.

La programación debe basarse en `America/New_York`, no en una hora fija de
Madrid, para absorber las semanas en las que Estados Unidos y Europa cambian
de horario en fechas distintas.

## 6. Publicación y artefactos

Se mantendrán separados:

- `reference`: último informe confirmado por el modelo autoritativo;
- `candidate`: propuesta diaria todavía no confirmada;
- `canonical/latest`: informe que puede consumir la hoja;
- `escalation`: motivos y evidencia de la revisión solicitada.

Un candidato escalado nunca debe sustituir a `canonical/latest` antes de la
revisión superior.

Metadatos mínimos de la referencia:

```text
symbol
reference_model
reference_reasoning_effort
reference_generated_at
reference_score
reference_tier
owned
ownership_source
options_as_of
input_hash
```

Metadatos mínimos de una decisión diaria:

```text
reference_score
proposed_score
material_change_reasons
candidate_applies_material_change
urgent_risk
reference_invalidation_confidence
replacement_confidence
raw_effective_confidence
effective_confidence
evidence_quality
independent_support
confidence_cap_applied
previous_conclusion
invalidation_evidence
proposed_replacement
strongest_counterargument
evidence_to_keep_reference
decision
```

## 7. Automatización local e IB Gateway

Se crearán tareas específicas en Windows Task Scheduler; no dependerán de que
la aplicación de escritorio de Codex esté abierta. El runner seguirá usando
`codex exec` no interactivo con la autenticación local existente.

Condiciones operativas:

- el ordenador puede estar encendido o suspendido con temporizadores de activación;
- un ordenador apagado requiere encendido programado por BIOS/UEFI o Wake-on-LAN;
- la sesión de Windows debe permanecer iniciada, aunque esté bloqueada;
- IB Gateway debe estar abierto, autenticado y con API disponible en `127.0.0.1:7497`;
- no se guardarán credenciales ni segundo factor de IBKR en scripts;
- se utilizará un lock compartido para impedir batches manuales, de cola y programados simultáneos.

Política de fallo de IB Gateway para estas tareas:

1. No iniciar modelos si la comprobación API de IB Gateway falla.
2. Reintentar cada 15 minutos durante un máximo inicial de dos horas.
3. Si no se recupera, registrar el batch como fallido y no publicar datos nuevos.
4. Si falla el domingo, generar la referencia pendiente antes del siguiente seguimiento diario.
5. No publicar un análisis nuevo apoyado en una referencia semanal caducada.

## 8. Componentes previstos

Los nombres definitivos se decidirán durante la implementación, pero se prevén:

- un orquestador semanal/diario que divida tickers por modelo;
- un almacén de estado de referencias y niveles;
- una comparación determinista y una cola local de escalados;
- un refresco técnico de opciones independiente del análisis completo;
- scripts para instalar, probar y eliminar las tareas programadas;
- resumen estructurado de cada ejecución y métricas de consumo.

Se reutilizarán `run_one.py`, `run_batch.py`, los lanzadores existentes, la
lectura de análisis anterior, la validación, el uploader y el patrón actual de
instalación de tareas de Windows.

## 9. Fases de implementación

### Fase 1: contratos y estado

- [x] Extender la exportación de Trading/Core con propiedad C/AF.
- [x] Definir el esquema de referencia, candidato, nivel y escalado.
- [x] Guardar referencias separadas del último informe diario.
- [x] Añadir tests de prioridad, promoción, descenso e histéresis.

### Fase 2: generación por niveles

- [x] Permitir batches agrupados por modelo y esfuerzo.
- [x] Incluir el informe completo de referencia en el input diario.
- [x] Bloquear la nota oficial frente a cambios del modelo diario.
- [x] Implementar la puerta determinista 65/85 y los topes por calidad de evidencia.
- [x] Retener candidatos escalados hasta obtener revisión superior.

### Fase 3: referencias del domingo

- [x] Implementar el orquestador semanal/manual por calendario.
- [ ] Guardar y validar `options_as_of`.
- [ ] Ejecutar un domingo real en modo de prueba sin publicación.
- [ ] Comparar el resultado con una ejecución manual equivalente.

### Fase 4: seguimiento y opciones del lunes

- [x] Implementar Tierra/Luna según el modelo de referencia.
- [x] Implementar la cola de revisión Tierra/Sol al terminar el batch económico.
- [ ] Implementar el refresco ligero del lunes a las 09:45 de Nueva York.
- [ ] Probar que un cambio rutinario de opciones no lanza Sol.
- [ ] Probar que un cambio estructural sí solicita revisión.

### Fase 5: tareas de Windows

- [ ] Crear instalador y desinstalador de las tareas programadas.
- [ ] Añadir wake desde suspensión, `StartWhenAvailable`, reintentos y `IgnoreNew`.
- [x] Integrar un preflight estricto común: realizar un handshake API real en
  `127.0.0.1:7497`, arrancar IB Gateway paper mediante IBC si falla y esperar
  antes de consumir modelo.
- [x] Instalar IB Gateway offline e IBC de forma local y aislada, sin credenciales
  en Git y con API de solo lectura.
- [x] Completar una prueba en frío de login paper con Gateway previamente cerrado.
- [x] Guardar las credenciales paper en Google Secret Manager para poder restaurarlas
  en otro ordenador sin incluirlas en Git.
- [ ] Añadir el lock compartido para impedir arranques concurrentes.
- [ ] Probar suspensión, sesión bloqueada, Gateway cerrado y recuperación posterior.

### Fase 6: despliegue progresivo

- [ ] Ejecutar primero con 2-3 tickers de cada nivel sin subir resultados reales.
- [ ] Ejecutar una semana completa en paralelo con el flujo actual.
- [ ] Revisar escalados aceptados/rechazados y posibles cambios omitidos.
- [ ] Activar publicación real para un subconjunto.
- [ ] Extender a Trading y Core completos cuando se cumplan los criterios de aceptación.

## 10. Métricas y controles

Registrar por ticker y batch:

- modelo y esfuerzo;
- tokens de entrada, caché, salida y razonamiento;
- coste relativo estimado;
- número y motivo de escalados;
- escalados confirmados y rechazados;
- cambios de nota confirmados;
- duración y reintentos;
- frescura de referencia, opciones e IBKR;
- fallos de validación y publicación.

Como control de falsos negativos, una muestra periódica de tickers no escalados
se comparará con Sol. Los tickers de seguimiento tendrán además una auditoría
ocasional con Sol aunque Tierra/Luna no hayan solicitado promoción.

## 11. Criterios de aceptación

El sistema podrá sustituir al flujo diario actual cuando:

1. Ningún candidato sin confirmar pueda aparecer como informe vigente.
2. Los poseídos usen siempre referencia Sol.
3. Las promociones y descensos respeten 7,0/6,5 y la banda de histéresis.
4. La nota diaria permanezca estable sin evidencia material.
5. Los cuatro motivos principales de escalado tengan tests positivos y negativos.
6. El domingo genere referencias válidas con `options_as_of` trazable.
7. El refresco del lunes no repita Sol salvo cambio estructural.
8. Un fallo de IB Gateway impida publicación nueva y produzca un error visible.
9. No existan ejecuciones duplicadas entre tareas, órdenes manuales y cola GCS.
10. Una semana de comparación muestre ahorro medible sin deterioro material de calidad.

## 12. Parámetros iniciales configurables

```json
{
  "promote_to_sol_score": 7.0,
  "demote_to_terra_score": 6.5,
  "daily_score_review_delta": 1.0,
  "daily_confidence_review_min": 65.0,
  "daily_structural_confidence_review_min": 60.0,
  "daily_confidence_direct_min": 85.0,
  "daily_confidence_audit_rate": 0.10,
  "owned_always_sol": true,
  "weekly_reference_day": "Sunday",
  "weekly_reference_time": "23:00",
  "weekly_reference_timezone": "Europe/Madrid",
  "monday_options_refresh_time": "09:45",
  "monday_options_refresh_timezone": "America/New_York",
  "tws_host": "127.0.0.1",
  "tws_port": 7497,
  "tws_retry_minutes": 15,
  "tws_retry_window_minutes": 120
}
```

## 13. Migración de credenciales de IB Gateway

La guía operativa completa y vigente está en
[`ibkr_gateway_automation.md`](ibkr_gateway_automation.md). Este apartado resume
únicamente la decisión dentro del plan de modelos.

Las credenciales paper se guardan en Google Secret Manager como un único secreto
JSON llamado `stock-analysis-ibkr-paper-credentials`. El fichero generado para IBC
continúa en `secrets/ibc/config.ini` y queda fuera de Git.

Para publicar las credenciales configuradas en este ordenador:

```powershell
.\scripts\sync_ibkr_secret_manager.ps1 -Action Upload -ProjectId recipe-generator-429817
```

Para reconstruir todo en otro ordenador después de autenticar `gcloud`:

```powershell
.\scripts\bootstrap_ibkr_gateway.ps1
```

Debe conservarse una sola versión habilitada. Al cambiar la contraseña se publica
una versión nueva y, tras comprobarla, se destruye la anterior para no acumular
versiones activas.
