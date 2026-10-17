# Estrategia de compra en bolsa

Documento vivo de este chat para construir, discutir y validar una estrategia de
compra en bolsa.

## Contrato del documento

Este documento no debe contener reglas estratégicas, principios operativos,
criterios de compra, criterios de venta ni flujos de decisión que no hayan sido
discutidos antes en la conversación.

Cada contenido nuevo debe entrar en una de estas categorías:

- **Acordado**: algo que hemos discutido y aceptado explícitamente.
- **Hipótesis en debate**: una idea que estamos probando, todavía no aprobada.
- **Pregunta abierta**: una duda que necesitamos resolver antes de convertirla
  en regla.
- **Contexto**: información descriptiva recibida del usuario o del sistema, sin
  implicar todavía una decisión estratégica.

Si una idea suena razonable pero no se ha discutido, no debe presentarse como
principio. Primero debe formularse como pregunta o hipótesis en debate.

## Contexto recibido

El usuario quiere usar este chat durante una conversación larga para definir una
estrategia rigurosa de compra en bolsa.

La estrategia debe construirse a partir de:

- más de un año de experiencia invirtiendo;
- aciertos;
- fallos;
- lecciones aprendidas;
- revisión crítica de ideas propias;
- discusión lenta de cada paso antes de cerrarlo.

El usuario ha mostrado una hoja tipo panel de seguimiento con tickers, métricas
técnicas, rangos, nota, analistas, momentum y contexto de mercado. Esa hoja es
contexto operativo, no una estrategia aceptada por sí misma.

## Acordado

- Este documento será el cuaderno propio de este chat.
- El documento debe conectarse con la documentación general del proyecto.
- La estrategia no debe cerrarse deprisa.
- Cada regla debe discutirse antes de quedar escrita como criterio aceptado.
- Hay que dudar de cada parte de la estrategia hasta estar razonablemente
  convencidos.
- No se deben inventar principios iniciales ni hacerlos pasar por consensos.
- La estrategia se ideara desde cero, con calma, sin intentar corregir de una
  vez el enfoque anterior.
- Mantendremos un registro numerado y estable de los problemas detectados.
- De vez en cuando revisaremos la estrategia construida para comprobar que
  problemas resuelve, cuales resuelve solo parcialmente y cuales siguen
  abiertos.
- Un problema no se considerara resuelto sin discutir explicitamente la
  respuesta que ofrece la estrategia.
- Los analisis diarios del proyecto deben actuar como capa de proteccion frente
  al deterioro empresarial y la ruptura de la tesis.
- La nota numerica y el estado de la tesis son ejes distintos. Una nota baja no
  significa que la tesis este rota ni impide que el ticker pueda ofrecer una
  recuperacion importante.
- Si la tesis de una empresa se rompe, hay que salir de la posicion. Esa
  situacion no debe tratarse como un dip ni justificar nuevas compras por el
  mero hecho de que el precio haya caido mucho.

## Hipótesis en debate

- Cada ticker puede tener una profundidad de correccion caracteristica,
  relacionada con su volatilidad y beta, a partir de la cual su presion vendedora
  puede reducirse. Esta observacion no implica que exista un suelo ni que el
  ticker no pueda seguir cayendo.
- El comportamiento anterior puede dejar de servir si una correccion normal se
  transforma en mercado bajista, si hay compresion general de multiplos o si se
  deteriora la tesis de la empresa.
- Los mecanismos de proteccion y el margen tolerable podrian ser distintos para
  una operacion de trading y para una compra de un dip excepcionalmente
  profundo.
- Los stop loss son una herramienta candidata para limitar determinados
  escenarios, pero todavia no se ha acordado como usarlos, donde situarlos ni en
  que tipo de operacion tendrian sentido.

## Preguntas abiertas

- Qué lecciones concretas salen de los aciertos del último año.
- Qué lecciones concretas salen de los fallos del último año.
- Qué tipo de compras queremos distinguir: trading, core, oportunidad puntual u
  otro marco.
- Qué papel debe jugar la hoja actual en la decisión final de compra.
- Qué información falta antes de tomar una decisión real.
- Como clasificar de forma util los tickers de beta y volatilidad media y alta.
- Como normalizar la profundidad del dip de cada ticker para no comparar de
  forma directa, por ejemplo, una caida del 20% en AMD con una del 50% en RKLB.
- Como distinguir una correccion normal de una transicion a mercado bajista.
- Como proteger la cuenta si la caida del Nasdaq se acerca o supera el 20% y se
  produce una compresion fuerte de multiplos.
- Como diferenciar previamente una operacion de trading de una compra de dip
  profundo y que consecuencias debe tener esa clasificacion.
- Que condiciones observables de los analisis determinan que una tesis esta
  deteriorandose o ya se ha roto, mediante un estado separado de la nota
  numerica.
- Como debe ejecutarse la salida por tesis rota y que hacer si el deterioro se
  conoce mediante un gap, si el analisis diario falla o si las senales son
  contradictorias.

## Caso de referencia: apalancamiento durante una correccion

Relato aproximado aportado por el usuario; las cifras sirven como referencia y
no como reconstruccion contable exacta:

- Capital propio inicial cercano a 155.000 EUR.
- Compra del primer dip cuando el Nasdaq habia caido aproximadamente un 4% desde
  maximos, elevando la exposicion hasta cerca de 2x.
- Los tickers individuales habian corregido de forma desigual, aproximadamente
  entre un 10% y un 30%, segun su volatilidad.
- Durante el primer rebote, el capital propio llego aproximadamente a 172.000
  EUR, sin que el Nasdaq recuperase maximos. Se mantuvo el apalancamiento
  esperando ese objetivo.
- En la siguiente caida, el capital propio regreso aproximadamente a
  130.000-140.000 EUR. Se realizaron nuevas compras conforme bajaban los
  tickers, hasta superar 3x de exposicion.
- Con el Nasdaq cerca de un 12% por debajo de maximos, el capital propio llego a
  rondar 70.000 EUR y fue necesario vender para evitar una liquidacion
  automatica.
- Al dia siguiente, un rebote aproximado del 3% en el Nasdaq produjo una subida
  cercana al 50% del capital propio, hasta unos 105.000 EUR.
- Durante la recuperacion posterior se redujeron posiciones hasta acercarse de
  nuevo a 150.000 EUR y quedar aproximadamente en 2x.
- Se vendieron varios grupos que recuperaban mejor, mientras permanecieron en
  cartera subsectores que despues quedaron rezagados.
- En una caida posterior, con el Nasdaq otra vez alrededor de un 4% por debajo
  de maximos, el capital propio ha oscilado aproximadamente entre 115.000 y
  135.000 EUR manteniendo cerca de 2x.
- Como ejemplo de las diferencias de volatilidad, con el Nasdaq cerca de -12%,
  AMD habia corregido aproximadamente un 20% y RKLB alrededor de un 50%.

## Banco de problemas a resolver

Este registro no contiene reglas ni soluciones aprobadas. La numeracion se
mantendra estable para poder referirnos a cada problema durante la conversacion.

| N. | Problema observado o hipotesis que exige proteccion | Respuesta de la estrategia | Estado |
|---:|---|---|---|
| 1 | El margen usado para comprar dips es deuda respaldada por una cartera que tambien cae; la utilizacion del maintenance puede dispararse aunque el requisito bruto baje. | Pendiente | Sin resolver |
| 2 | Varias posiciones pueden comprar repetidamente el mismo riesgo por correlacion sectorial, de factores o de apetito por riesgo. | Pendiente | Sin resolver |
| 3 | "Comprar el dip" no distingue por si solo volatilidad temporal, cambio de valoracion, deterioro del negocio, fraude, dilucion o mercado bajista. | Los analisis diarios deben vigilar la tesis mediante un estado separado de la nota; si se rompe, se sale y deja de aplicarse la logica de dip. Falta definir el disparador operativo. | Parcialmente abordado |
| 4 | Comprar mas durante la caida puede aumentar simultaneamente exposicion, concentracion y deuda mientras empeora la cartera. | Pendiente | Sin resolver |
| 5 | Existe riesgo de secuencia: consumir margen en las primeras caidas puede dejar poca capacidad para una caida posterior mas profunda. | Pendiente | Sin resolver |
| 6 | El apalancamiento aumenta la recuperacion porcentual necesaria despues de una perdida y anade el coste de los intereses. | Pendiente | Sin resolver |
| 7 | Cerca del limite de mantenimiento, la decision de vender puede dejar de pertenecer al inversor y pasar al broker. | Pendiente | Sin resolver |
| 8 | En una liquidacion, el broker puede vender posiciones distintas de las que el inversor preferiria vender. | Pendiente | Sin resolver |
| 9 | La expresion "trading o esperar a que recupere" permite transformar una operacion perdedora en inversion sin una decision previa. | Pendiente | Sin resolver |
| 10 | Los intereses, la divisa, los impuestos y el coste de oportunidad introducen un reloj aunque el precio termine recuperandose. | Pendiente | Sin resolver |
| 11 | Los gaps por resultados, noticias o eventos geopoliticos pueden atravesar un stop y amplificar las perdidas con margen. | Pendiente | Sin resolver |
| 12 | El Nasdaq-100 no representa todo el mercado y concentra exposicion en grandes empresas no financieras y factores de crecimiento. | Pendiente | Sin resolver |
| 13 | Hay que definir que significa dedicar el 100% del capital: cuenta de inversion, patrimonio liquido o dinero no necesario a largo plazo. | Pendiente | Sin resolver |
| 14 | La deuda, los intereses y la amenaza de liquidacion cambian la capacidad psicologica de mantener una estrategia durante una caida. | Pendiente | Sin resolver |
| 15 | La caida del Nasdaq no representaba el riesgo real de una cartera de tickers mas volatiles, concentrados y apalancados. | Pendiente | Sin resolver |
| 16 | El mismo porcentaje de dip del Nasdaq puede ocultar estados distintos de amplitud, liderazgo, liquidez y comportamiento de los subsectores. | Pendiente | Sin resolver |
| 17 | El tamano de las posiciones no estaba ajustado a las diferencias de beta y volatilidad entre tickers. | Pendiente | Sin resolver |
| 18 | La sensibilidad era asimetrica: en sesiones de tension la cartera podia caer bastante mas de lo que su comportamiento en los rebotes hacia esperar. | Pendiente | Sin resolver |
| 19 | El apalancamiento aumenta mecanicamente cuando cae el patrimonio, incluso sin nuevas compras; comprar durante la caida lo aumenta otra vez. | Pendiente | Sin resolver |
| 20 | Los objetivos de salida quedaron anclados al maximo anterior del indice y despues a recuperar una cifra concreta de capital propio. | Pendiente | Sin resolver |
| 21 | El primer rebote no tenia un mecanismo previamente definido de desapalancamiento parcial o proteccion de la recuperacion. | Pendiente | Sin resolver |
| 22 | Las compras sucesivas aumentaron el peso de los activos que peor se comportaban y la dependencia de que esos mismos activos recuperasen. | Pendiente | Sin resolver |
| 23 | Al reducir margen se vendieron posiciones que recuperaban mejor, dejando una cartera relativamente mas concentrada en grupos rezagados. | Pendiente | Sin resolver |
| 24 | Un mismo nivel de apalancamiento, por ejemplo 2x, puede representar riesgos muy distintos segun volatilidad, correlacion, liquidez y concentracion. | Pendiente | Sin resolver |
| 25 | La supervivencia de la cuenta dependio del signo de la sesion siguiente, lo que muestra proximidad a un riesgo de ruina o liquidacion. | Pendiente | Sin resolver |
| 26 | La recuperacion del indice no garantiza la recuperacion del patrimonio despues de perdidas apalancadas, compras y ventas intermedias y cambios de composicion. | Pendiente | Sin resolver |
| 27 | La concentracion debe medirse respecto al patrimonio y por factores solapados, no solamente como porcentaje de las posiciones o mediante etiquetas sectoriales. | Pendiente | Sin resolver |
| 28 | Cada ticker podria tener una profundidad de correccion diferente a partir de la cual le cuesta mas seguir cayendo; hay que validar como medirla y cuando deja de ser util. | Pendiente | Hipotesis a validar |
| 29 | Una correccion puede convertirse en mercado bajista y provocar caidas del 70-90% en determinados tickers por compresion de multiplos; la estrategia necesita contemplar proteccion ante ese cambio de regimen. | Pendiente | Sin resolver |

## Registro de decisiones

| Fecha | Tema | Decisión | Estado |
|---|---|---|---|
| 2026-09-04 | Forma del documento | Solo se documentará como regla lo previamente discutido | Acordado |
| 2026-09-04 | Metodo de construccion | Construir la estrategia desde cero y contrastarla periodicamente con el banco numerado de problemas | Acordado |
| 2026-09-04 | Ruptura de tesis | Si se rompe la tesis empresarial, salir de la posicion y no tratar la caida como una oportunidad de dip | Acordado; falta operativizar |
| 2026-09-04 | Nota frente a tesis | La nota numerica no determina por si sola si la tesis esta rota; deben registrarse como ejes separados | Acordado |

## Registro de lecciones

| Fecha | Caso | Lección discutida | Estado |
|---|---|---|---|
| Pendiente | Pendiente | Pendiente | Pendiente |
