# Plan de reconstruccion del sistema de analisis

Estado: borrador de arquitectura para discusion e implementacion incremental.

Este documento define como reconstruir el sistema alrededor de una unica autoridad operativa, conservar lo que ya funciona y sustituir el sistema actual solo cuando el reemplazo haya demostrado paridad y fiabilidad. No define la estrategia de compra: esa conversacion vive en `docs/estrategia_compra_bolsa.md` y ninguna regla de inversion se incorpora aqui sin haber sido discutida.

## 1. Objetivo

Construir un sistema en el que sea facil responder, desde un solo mapa:

- quien calcula cada dato;
- donde se conserva;
- quien puede modificarlo;
- como llega a Google Sheets;
- que ocurre cuando falla una etapa;
- como se repite o recupera una ejecucion;
- que parte sigue dependiendo del ordenador local.

El resultado no se llamara `v2`. Durante la transicion, el sistema actual se identifica como `legacy`; los componentes definitivos reciben nombres por su funcion.

## 2. Reglas de la reconstruccion

### 2.1 Decisiones confirmadas

1. Todo el codigo definitivo se crea en una estructura nueva.
2. Reutilizar no significa importar el runtime de `legacy`: se copia la logica util, se revisa, se caracteriza con pruebas y se refactoriza dentro del nuevo limite.
3. `legacy` no se borra ni se apaga hasta completar una ejecucion paralela satisfactoria y disponer de vuelta atras.
4. Google Sheets es una interfaz de trabajo, no el motor distribuido del sistema.
5. `stock-controller` sera el unico escritor programatico de la hoja.
6. Apps Script queda reducido a menu, botones y envio de comandos.
7. El agente local ejecuta Codex e IBKR, pero no coordina el sistema ni escribe directamente en la hoja.
8. No se fuerza una arquitectura de microservicios. Se empieza con pocos componentes de responsabilidad amplia y cohesionada.
9. La hoja muestra un unico universo repartido en dos tablas balanceadas. No existe una categoria visual distinta para Trading y Core.
10. Los grupos de sector o subsector siguen siendo datos aunque no generen minitablas. Permiten resumir exposicion y evitar comprar demasiadas empresas que se mueven por el mismo factor.
11. Las dos tablas son nativas y su orden pertenece al usuario. Los publicadores resuelven la fila por ticker y nunca reordenan automaticamente.

### 2.2 Disciplina documental

Cada decision de este plan se clasifica como una de estas tres cosas:

- **Confirmada**: ya acordada en la conversacion.
- **Diseno tecnico**: elegida para poder construir; se puede revisar si las pruebas muestran una opcion mejor.
- **Pendiente de estrategia**: no se implementa como regla de compra hasta discutirla.

Los documentos del sistema actual son la linea base, no el destino:

- `docs/architecture.md`
- `docs/component_map.md`
- `docs/system_audit_2026-09-04.md`
- `docs/operations.md`
- `docs/batch_workflow.md`

## 3. Arquitectura objetivo

```text
Google Sheets / Apps Script
            |
            | comandos y lectura visual
            v
     stock-controller
       |     |      |
       |     |      +--> Google Sheets (unico escritor)
       |     +---------> GCS (informes y snapshots)
       +---------------> Firestore (jobs, estado y locks)
            |
            +--> market-worker
            |
            +--> analysis-agent local
                       |
                       +--> Codex
                       +--> IBKR Gateway
```

### 3.1 `stock-controller`

Responsabilidades:

- exponer la API de comandos;
- validar configuracion y peticiones;
- crear y coordinar jobs;
- aplicar idempotencia, locks y reintentos;
- decidir que resultado es publicable;
- mantener el estado calculado;
- renderizar y escribir Google Sheets;
- publicar informes y snapshots;
- registrar errores sin hacer parecer nuevos los datos antiguos.

No le corresponde:

- obtener todo el dato financiero directamente;
- ejecutar Codex;
- depender de la geometria historica de filas de la hoja.

### 3.2 `market-worker`

Responsabilidades:

- precios e historicos;
- opciones y datos tecnicos disponibles;
- contexto de mercado y benchmarks;
- metricas deterministas;
- preparacion determinista de las evidencias tecnicas para soportes;
- contratos tecnicos necesarios para el analisis.

No elige el soporte final, no conoce la disposicion de Google Sheets y nunca escribe en ella. El modelo decide `Entrada` y `Washout` usando esas evidencias dentro de la llamada ordinaria de analisis.

### 3.3 `analysis-agent`

Proceso local de Windows encargado de:

- reclamar jobs cerrados y versionados;
- asegurar que IBKR esta disponible cuando sea necesario;
- ejecutar el analisis con Codex;
- validar localmente el resultado antes de devolverlo;
- enviar resultado, diagnostico y version del contrato al controlador.

No decide por su cuenta que filas modificar ni publica directamente.

### 3.4 Almacenamiento e infraestructura

| Recurso | Autoridad |
|---|---|
| Firestore | Jobs, estado calculado, locks, cartera declarada y auditoria de eventos |
| GCS | Informes, snapshots y artefactos versionados |
| Google Sheets | Entradas manuales declaradas e interfaz visual |
| Secret Manager | Credenciales y secretos |
| Cloud Scheduler | Activacion de procesos cloud |
| Programador de tareas de Windows | Despertar el equipo y lanzar el agente local |

No habra sincronizacion circular. Cada campo tendra una autoridad declarada.

## 4. Hoja de calculo objetivo

### 4.1 Estructura general

La hoja usa dos tablas y un resumen, no un mosaico de minitablas:

- una tabla a la izquierda contiene 23 tickers;
- un panel central unico contiene regimen de riesgo, VXN, QQQ y fechas de los
  analisis, recuperando la lectura contextual de la hoja anterior;
- otra tabla equivalente a la derecha contiene los otros 23 tickers;
- `Resumen de grupos`, debajo de ambas tablas y separado por dos filas vacias,
  concentra el contexto de sector o subsector.

Reglas confirmadas:

- no existe un minimo de componentes por grupo;
- un grupo de dos tickers es valido si tiene identidad propia y aporta lectura;
- tampoco se fragmenta por taxonomia academica si juntar varios nombres resulta mas util;
- el agrupamiento se almacena como configuracion, no se deduce de la posicion fisica de las filas;
- las dos tablas quedan balanceadas y la distribucion inicial no parte grupos;
- el usuario puede ordenar cada tabla nativa por cualquier columna;
- ninguna publicacion de mercado, analisis o cartera altera ese orden;
- el escritor resuelve cada ticker por identidad estable y nunca presupone un numero de fila fijo.

La pertenencia a cada mitad, grupos y ETF se declara en
`config/market_sheet_layout.json` y es revisable sin cambiar el codigo.

### 4.2 Resumen de grupos

El resumen inferior centrado muestra una fila por grupo. Sustituye las antiguas
lineas repetidas encima de cada minitabla y permite leer conjuntamente contexto
de mercado y exposicion de cartera.

Campos iniciales:

| Campo | Significado |
|---|---|
| Sector / Grupo | Familia y subsector operativo en una sola celda |
| Banda | Correspondencia cromatica con los tickers del grupo |
| ETF | Benchmark operativo elegido para el grupo |
| Dia | Variacion de la sesion |
| 20d | Rendimiento de las ultimas 20 sesiones |
| DD6M | Caida desde el maximo de cierre de los ultimos seis meses |
| Pos. | Numero de tickers del grupo que estan en cartera |
| Shots | Suma de shots declarados en el grupo |

Los recuentos incluyen ambas tablas. No se colorean como alerta ni se
deduce todavia un limite de concentracion: esa regla pertenece a la estrategia
y debe discutirse antes de implementarla.

### 4.3 Columnas visibles

Orden de partida acordado:

| Columna | Contenido | Responsable inicial | Observacion visual |
|---|---|---|---|
| # / Banda | Shots totales abiertos en el subsector | `stock-controller` + configuracion | Celda estrecha; el color identifica el subsector y se repite en el resumen |
| Ticker | Simbolo y enlace | `stock-controller` | Fondo azul fluorescente si esta en cartera; tono mas intenso con dos o mas shots |
| Valor | Ultimo precio util | `market-worker` | Mismo comportamiento inicial que ahora |
| %d | Variacion diaria | `market-worker` | Mismo comportamiento inicial que ahora |
| Fuerza | Metrica actual de fuerza | logica portada y auditada | Se conserva inicialmente sin redefinirla |
| 5d | Rendimiento a 5 sesiones | `market-worker` | Mismo calculo inicial que ahora |
| 20d | Rendimiento a 20 sesiones | `market-worker` | Mismo calculo inicial que ahora |
| Volatilidad | Volatilidad usada actualmente | `market-worker` | Se conserva inicialmente |
| DD rel. 6M | Distancia relativa actual | `market-worker` | No se sustituye por el nuevo indice de dip en esta fase |
| Entrada | Soporte operativo normal | analisis validado | Color indica proximidad; borde indica fortaleza; la nota contiene el stop y una resistencia solo cuando sea suficientemente fuerte |
| Washout | Soporte ambicioso | analisis validado | Color indica proximidad; borde indica fortaleza; la nota contiene el stop y una resistencia solo cuando sea suficientemente fuerte |
| Nota | Valoracion sintetica actual | analisis validado | Se sincroniza desde decision.score del ultimo informe valido |

`Entrada` sustituye el nombre visual ambiguo `target`. `Washout` corresponde al nivel ambicioso.
Los stops y la resistencia no ocupan columnas visibles independientes; se
muestran como notas asociadas a `Entrada` y `Washout`.

### 4.4 Datos internos no visibles

Se conservan en el contrato de datos para calculos, analisis y trazabilidad, pero no ocupan columnas permanentes:

- ATR;
- put wall y call wall;
- EMA20 y pendiente de EMA20;
- HVN/POC;
- AVWAP;
- RSI14;
- PCR OI;
- zero gamma;
- volumen relativo;
- analistas;
- momentum;
- fecha de earnings;
- componentes y explicacion de la fortaleza de cada soporte.

Que no sean visibles no permite convertirlos en reglas opacas: cualquier dato que altere una salida visible debe quedar registrado en el snapshot y ser inspeccionable.

### 4.5 Semantica visual

Decisiones confirmadas:

- el color de relleno de `Entrada` y `Washout` sigue indicando si el precio esta lejos, cerca o dentro del rango;
- la fortaleza no consume otra columna: se representa con el borde de la celda del soporte;
- una nota de celda muestra puntuacion, categoria y factores del soporte;
- no habra una leyenda permanente en la zona derecha;
- el fondo del ticker queda reservado para indicar que existe posicion;
- earnings se representa sin ocupar una columna y sin tapar el estado de cartera;
- Analistas y Momentum desaparecen de la vista.

Diseno tecnico que debe probarse visualmente antes de consolidarlo:

| Fortaleza | Borde propuesto |
|---|---|
| 0-39 debil | Sin borde especial |
| 40-69 moderado | Sin borde especial |
| 70-84 solido | Sin borde especial |
| 85-94 fuerte | Azul marino grueso |
| 95-100 excepcional | Azul brillante grueso |

La escala no decide si comprar. Comunica la calidad estimada del nivel y ayuda a interpretar entrada, stop y contexto.

Earnings21Oct: borde naranja fino entre2 y7días naturales y rojo grueso hoy/mañana, con fecha exacta en nota. Fondo reservado para cartera. Desplegado/autorizado y verificado LRCXK8rojo. [Decisión0008](decisions/0008-avisos-de-resultados.md).

## 5. Flujos operativos

### 5.1 Refresco de mercado

1. Scheduler o comando crea un job idempotente.
2. `stock-controller` entrega al `market-worker` un universo y una version de contrato.
3. El worker devuelve datos normalizados, benchmarks y diagnosticos.
4. El controlador valida completitud y antiguedad.
5. Solo despues actualiza el estado y renderiza la hoja en una operacion controlada.
6. Si falla, se conserva visible el ultimo dato valido con estado de antiguedad; no se presenta como refrescado.

### 5.2 Analisis de ticker o lote

1. El comando declara alcance: ticker, grupo o universo.
2. El controlador prepara un job autocontenido.
3. El agente local lo reclama y ejecuta Codex una sola vez por ticker dentro del flujo ordinario.
4. El modelo decide los niveles y la respuesta incluye soportes, stops ligados, fortaleza, nota, informe y evidencias estructuradas.
5. El controlador valida el contrato y coherencia entre campos.
6. Un resultado invalido queda fallido y visible; no sustituye el ultimo resultado bueno.
7. Un resultado valido se versiona en GCS y se publica en Sheet.

La fortaleza del soporte forma parte de la misma peticion y respuesta; no obliga a una segunda llamada al modelo.

### 5.3 Compra y venta declaradas por chat

1. El usuario comunica compra, venta parcial o venta total.
2. El controlador registra un evento append-only.
3. Firestore actualiza el estado materializado de cartera.
4. La siguiente escritura pinta o retira el fondo azul del ticker y actualiza
   los shots agregados de su subsector.

No se mantiene un proceso consultando IBKR continuamente. Una conciliacion con IBKR, si se incorpora, sera explicita y bajo demanda.

### 5.4 Ejecucion diaria con el equipo suspendido

1. El Programador de tareas de Windows despierta el equipo.
2. Inicia el agente local.
3. El agente consulta jobs pendientes al controlador.
4. Levanta o verifica IBKR Gateway cuando el job lo requiere.
5. Ejecuta, entrega resultados y espera confirmacion.
6. El posible retorno a suspension se condiciona a que el usuario no este activo y no haya trabajo pendiente.

El despertar desde suspension ya fue probado fisicamente en este ordenador. La hibernacion queda fuera del alcance actual.

### 5.5 Gestion manual desde `Analisis IA` (pendiente)

Se incorporara al menu de la hoja una entrada de gestion con acciones simples,
similares al dialogo actual de analizar un ticker:

1. `Anadir ticker...`: solicita el simbolo, valida que no exista y permite
   asignarlo a un sector/subsector existente antes de incorporarlo al universo.
2. `Quitar ticker...`: solicita el simbolo, confirma la baja y lo retira del
   universo visible sin borrar sus informes historicos.
3. `Registrar compra...`: solicita ticker y numero de shots que se anaden a la
   posicion declarada.
4. `Registrar venta...`: solicita ticker y numero de shots, o venta total, y
   reduce o elimina la posicion declarada.

Apps Script solo recogera la accion y los datos del dialogo. Enviara un comando
idempotente a `stock-controller`, que validara el ticker, modificara la
configuracion o cartera autoritativa y volvera a publicar las dos tablas
balanceadas, los colores de posicion y los shots del resumen. El procedimiento
de analisis de un ticker no se modifica. Antes de implementarlo hay que cerrar
la UX exacta, la autoridad persistente del universo y el tratamiento de una
posicion cuando se intenta quitar su ticker.

## 6. Contratos y estados

### 6.1 Identidad minima de un job

Todo job incluira:

- `job_id` estable;
- tipo de operacion;
- alcance;
- fecha y version de datos de entrada;
- version del contrato;
- configuracion efectiva;
- numero de intento;
- propietario temporal del lock;
- timestamps de cada transicion;
- resultado o error estructurado.

### 6.2 Estados propuestos

Diseno tecnico inicial:

```text
requested -> queued -> claimed -> running -> validating -> published
                                               |
                                               +-> failed
```

Las transiciones seran atomicas. Repetir una peticion con la misma clave de idempotencia no duplicara una publicacion. La necesidad de `cancelled` se decidira cuando exista una interfaz real de cancelacion.

### 6.3 Versionado

El contrato entre worker, agente y controlador tendra version explicita. Los cambios incompatibles se rechazan con un error legible, no mediante campos silenciosamente ignorados.

## 7. Mapa de migracion

| Capacidad actual | Destino | Tratamiento |
|---|---|---|
| Menus y botones de Apps Script | Apps Script minimo | Reescritura pequena |
| Colas y polling repartidos | `stock-controller` + Firestore | Sustitucion |
| Escrituras de Apps Script y procesos locales | `stock-controller` | Unificacion |
| `support-resistances-raw` | Modulo de `market-worker` | Copiar, revisar y caracterizar |
| `support-resistances-slim` | Modulo de `market-worker` | Integrar con contrato unico |
| `support-resistance-values` | `market-worker` / controlador | Separar calculo de publicacion |
| `reports` / reader | `stock-controller` + GCS | Integrar publicacion y lectura |
| Runner local actual | `analysis-agent` | Copiar logica util y refactorizar |
| Configuraciones de tickers Trading/Core | Universo unico y grupos | Migrar semantica, no duplicacion |
| Columnas tecnicas intermedias | Contrato backend | Retirar de la vista |
| Estado manual de cartera | Firestore + eventos | Crear |
| Scheduler actual | Cloud Scheduler + tarea Windows | Reconfigurar por responsabilidad |

Este mapa es una hipotesis de destino. Antes de portar cada capacidad se localizan sus consumidores reales y se crea una prueba de caracterizacion con datos conocidos.

## 8. Estructura de codigo propuesta

Diseno tecnico inicial:

```text
src/
  stock_analysis/
    contracts/
    controller/
      api/
      jobs/
      publishing/
      sheets/
      state/
    market_worker/
      market_data/
      options/
      metrics/
      supports/
      benchmarks/
    analysis_agent/
      runner/
      codex/
      ibkr/
      wake/
    shared/
      config/
      observability/
tests/
  characterization/
  contracts/
  integration/
  end_to_end/
```

Se comparte solo infraestructura y contratos estables. La logica de negocio permanece con su propietario para evitar volver a crear dependencias invisibles.

## 9. Fases y puertas de salida

### Fase 0. Congelar la linea base

- reconciliar documentacion con despliegues y codigo realmente activos;
- capturar ejemplos anonimizados de entradas y salidas actuales;
- crear pruebas de caracterizacion para metricas que se mantienen "como ahora";
- enumerar secretos, permisos, schedules y endpoints sin copiarlos al documento.

Salida: sabemos que comportamiento debe preservarse y que piezas estan realmente vivas.

### Fase 1. Contratos y configuracion

- definir esquemas de ticker, benchmark, soporte, analisis, cartera y job;
- crear validadores y fixtures;
- definir el manifiesto unico de universo, grupos, benchmarks y columnas;
- fijar autoridades de cada campo.

Salida: los componentes pueden evolucionar contra contratos ejecutables.

### Fase 2. Esqueleto de infraestructura

- desplegar `stock-controller` y `market-worker` en entorno de prueba;
- crear colecciones de Firestore, rutas de GCS e identidades de servicio;
- implementar logs correlacionados por `job_id`;
- comprobar idempotencia y recuperacion de locks.

Salida: un job sintetico recorre el sistema sin tocar la hoja real.

### Fase 3. Renderer de Google Sheets

- crear la nueva hoja o pestana con nombre definitivo por funcion;
- montar las dos tablas balanceadas y `Resumen de grupos`;
- renderizar columnas, resumen y notas;
- verificar ordenacion manual, formato y resolucion por ticker;
- probar visualmente cartera, earnings, proximidad y bordes de fortaleza.

Salida: la hoja se puede usar sin dependencias de filas fijas y la publicacion de
analisis respeta el orden elegido sin afectar a los refrescos intradia.

### Fase 4. Datos de mercado y paridad

- portar Valor, `%d`, 5d, 20d, Volatilidad, DD rel. 6M y Fuerza;
- portar datos internos necesarios;
- comparar resultados con `legacy` sobre sesiones conocidas;
- documentar diferencias intencionadas.

Salida: paridad cuantificada y errores/antiguedad visibles.

### Fase 5. Soportes, stops y fortaleza

- portar la preparacion tecnica de soportes y mantener la seleccion final dentro del analisis del modelo;
- corregir niveles desaparecidos mediante validacion del contrato;
- incorporar Entrada, Washout, sus stops ligados y fortaleza en una unica respuesta;
- probar que relleno, borde y nota conviven correctamente.

Salida: ningun soporte obsoleto sobrevive como actual y cada nivel publicado es trazable.

Esta fase implementa representacion y coherencia tecnica. Las reglas de compra, venta y construccion de posicion siguen pendientes de la conversacion estrategica.

### Fase 6. Agente local

- portar runner, integracion Codex e IBKR;
- eliminar escritura directa y orquestacion local;
- implementar claim, heartbeat, entrega y reintento seguro;
- ejecutar ticker individual y lote con el contrato definitivo.

Salida: el mismo job puede recuperarse despues de un reinicio sin duplicar publicacion.

### Fase 7. Operacion diaria

- conectar comandos desde Apps Script y chat;
- implementar en `Analisis IA` el alta y baja de tickers y el registro de
  compras, ventas parciales y ventas totales;
- hacer que esos comandos actualicen el universo o la cartera mediante el
  controlador, rebalanceen las tablas y refresquen colores y shots;
- integrar tarea de despertar ya validada;
- definir politica prudente de retorno a suspension;
- documentar operaciones ordinarias y recuperacion.

Salida: el flujo diario funciona sin intervencion tecnica y mantiene auditoria.

### Fase 8. Ejecucion paralela

- ejecutar `legacy` y el sistema definitivo sobre el mismo universo;
- comparar datos, informes, tiempos, fallos y publicaciones;
- simular caida de API, respuesta invalida, lock expirado, Sheet no disponible, IBKR cerrado y equipo reiniciado;
- corregir hasta cumplir los criterios de aceptacion.

Salida: varias ejecuciones completas consecutivas sin diferencias inexplicadas ni errores silenciosos.

### Fase 9. Cambio de autoridad

- congelar cambios funcionales durante el cambio;
- hacer snapshot y copia de configuracion;
- convertir el sistema definitivo en escritor oficial;
- mantener `legacy` disponible pero sin escritura;
- observar y conservar una ruta de vuelta atras probada.

Salida: operacion real estable durante el periodo acordado.

### Fase 10. Retirada de `legacy`

- apagar schedules y endpoints antiguos;
- revocar permisos y secretos que ya no se usan;
- archivar codigo y documentacion historica;
- actualizar el mapa operativo para que solo describa el sistema vivo.

Salida: no quedan dos caminos capaces de modificar el mismo estado.

## 10. Criterios de aceptacion globales

El cambio no se considera terminado hasta demostrar:

1. Un unico propietario por dato y un unico escritor de Sheet.
2. Ninguna dependencia de numeros de fila fijos.
3. Jobs idempotentes, recuperables y trazables de extremo a extremo.
4. Los fallos no hacen pasar datos antiguos por nuevos.
5. Los informes y snapshots pueden reproducir que se publico y por que.
6. El analisis ordinario no necesita una segunda llamada al modelo para puntuar soportes.
7. El sistema despierta este PC desde suspension para el run programado.
8. Ordenar manualmente por `Nota` o cualquier otra columna no rompe el siguiente refresco.
9. Una posicion declarada sobrevive reinicios y se refleja visualmente.
10. `legacy` puede reactivarse durante la ventana de rollback sin reconstruccion improvisada.
11. Las dos tablas y el resumen resultan legibles en una prueba real y los grupos siguen siendo reconocibles sin minitables.
12. Cada diferencia frente a "como ahora" esta probada y documentada como intencionada.

## 11. Decisiones pendientes, en su momento

No bloquean el inicio de las primeras fases:

- cambios futuros de pertenencia a una mitad, grupos o ETF;
- nombre final de la hoja y sus pestanas;
- aspecto definitivo de bordes de fortaleza y marca de earnings;
- ventanas temporales de earnings;
- formula final de stops ligados a soportes;
- criterio cuantitativo definitivo de fortaleza;
- politica de retorno automatico a suspension;
- duracion de la ejecucion paralela y de la ventana de rollback;
- UX y reglas de validacion del gestor de tickers y posiciones del menu
  `Analisis IA`;
- reglas estrategicas para entrar, salir o construir posicion durante dips profundos.

Estas decisiones se resolveran cuando exista el prototipo o la evidencia necesarios. No se rellenan por adelantado con supuestos.

## 12. Primer incremento ejecutable

El primer trabajo de implementacion sera un corte vertical pequeno pero real:

1. Definir contratos de `Ticker`, `Group`, `BenchmarkContext` y `MarketSnapshot`.
2. Declarar un unico manifiesto con ambas mitades, grupos y benchmarks.
3. Obtener datos de mercado sin depender de la Sheet.
4. Renderizar las dos tablas nativas y el resumen sin columnas auxiliares de datos.
5. Ordenar manualmente, publicar mercado, analisis y cartera, y comprobar que cada dato sigue a su ticker.

Este incremento valida pronto la parte mas visible y una de las fronteras mas importantes: datos estructurados por detras y Google Sheets como proyeccion controlada.
