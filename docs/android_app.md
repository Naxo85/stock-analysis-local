# Growth para Android

Actualización21-10-2026: etiqueta en Tabla `E hoy`, `E mañana`, `E en N días`, roja hoy/mañana y naranja2–7días. Tarjeta desplegada con fecha/horario cuando se suministra; caduca por fecha Europe/Madrid sobre datos guardados. API/calendario del controlador activos y verificados,10avisos concordantes con Sheet y LRCXrojo. APK firmada nueva compilada/unit/lint; requiere instalarla para ver la etiqueta en el teléfono, que no se ha verificado físicamente. [Evidencia](audit_earnings_20261021/README.md).

**Puesta en servicio18-10-2026:** aviso del último intento separado del último informe válido, compatible con manifest-v1. APK firmado disponible en `releases/android/Growth-0.1.0.apk`, SHA256 `736802a719a50fcb7f167653a55c6949577e403a646bdaa33ce5f7b1d9db43d4`, con la identidad de firma existente. Compilación release/unit/lint offline, nueve pruebas instrumentadas, revisión visual y conexión real del APK firmado en emulador verificadas; no se verificó instalación en teléfono físico. [Resultados y límites](audit_work_20261017/execution/activation/android/README.md).

Primera version: 0.1.0. Proyecto nativo en `android/`, Kotlin y Jetpack Compose.
El diseno toma como referencia la maqueta Panel. Incluye modo claro, oscuro y
apariencia del dispositivo. Requiere Android 8.0 o posterior.

## Alcance

Simplificación posterior19-10: por petición del usuario, el bloque QQQ queda en
una sola línea «Caída QQQ» y porcentaje. La API admite la vista compacta C2 y la
tarjeta anterior C3. Se han retirado de la pantalla los detalles circundantes;
el cálculo y la fecha de origen siguen disponibles en la nota de Sheets.

Actualización19-10-2026: Inicio añade **Retroceso QQQ**, solo el episodio actual,
leyendo exactamente el porcentaje y las etiquetas fechadas del bloque C2:H7 de
Mercado. Usa cierres diarios, umbral5% y reinicio tras rebote5% desde el mínimo;
no lo confunde con DD6M ni con la cotización intradía. Desconocido se muestra como
tal. APK conectado recompilado/firma existente/unit/lint correctos; la prueba de
interfaz nueva está compilada, pero no se ejecutó en dispositivo. El teléfono
físico requiere instalar esta actualización. [Evidencia](audit_qqq_pullback_20261019/README.md).

- Inicio: regimen de riesgo, QQQ hoy, DD6M y VXN; espacio reservado para las
  futuras noticias generales Growth. Debajo se mantienen los titulares IBKR
  que ya aparecen en informes publicados, con sus fechas; no se presentan
  como noticias generales en tiempo real.
- Cambios: catalizadores de impacto absoluto >=7 nuevos o actualizados,
  proximos eventos nuevos o modificados, cambios de Tesis de al menos 0,5 y
  acciones relevantes de analistas. No incluye ajustes de Entrada, Washout,
  Resistencia o Setup ni catalizadores cuyo titular sea solo una lectura
  tecnica de precios. Cada tarjeta muestra ticker, fecha, tipo y titular; se
  pulsa para ver el detalle y abrir el informe. En los eventos, la etiqueta
  visible dice "Proximo evento" y la fecha indica cuando se espera, junto
  con "nuevo" o "actualizado" para aclarar el cambio. Compara el ultimo informe
  valido con el anterior de la misma empresa, no con la ultima visita.
  Para reconocer el mismo catalizador usa la fuente, fecha y similitud del
  titular. Un cambio de redaccion o de impacto estimado por si solo no genera
  aviso. "Actualizado" requiere cambio de fecha, estado expresado en el
  titular o cifra comparable del titular; una cifra simplemente omitida no
  cuenta. Los hechos anteriores a siete dias no aparecen como noticia nueva
  solo por incorporarse por primera vez a un informe.
  La ausencia de un catalizador futuro se etiqueta como "deja de figurar":
  no se deduce que este cancelado. Se excluyen reiteraciones de analistas y
  variaciones de precio objetivo inferiores al 15 %.
- Informes: busqueda y cuadricula de tickers de tres columnas. Al seleccionar
  uno se abre su resumen debajo de toda la fila, con acceso al texto completo.
  La cabecera indica la fecha del ultimo informe valido.
- Tabla: lista compacta con busqueda, filtros Compra/Venta/Cartera y orden
  por senal, Tesis, Setup, Fuerza, Dia o Ticker. Al desplegar se ven Entrada,
  Washout, Resistencia, fortalezas y momentum. Compra significa precio dentro
  de Entrada o Washout; Venta, posicion en cartera con precio dentro de
  Resistencia. Una cotizacion antigua se marca como "ultimo precio en zona"
  y no como senal actual. Son marcadores visuales, no ordenes automaticas.
- Cache privada para lectura sin conexion. Los errores no convierten datos
  guardados en datos nuevos. Cerrar sesion elimina esa copia.

La app solo consulta datos. No lanza analisis ni opera posiciones. La fuerza
de mercado (/10) y la fortaleza de cada soporte (/100) se presentan por separado.

## Datos y acceso

`gcp_services/mobile_api/` contiene una API independiente con dos rutas:

```
GET /v1/dashboard
GET /v1/reports/<TICKER>
```

Ambas requieren un bearer aleatorio. La API almacena solamente su SHA-256;
el codigo se guarda en `.local/mobile/access-code.txt` y nunca se compila en la
APK. Android lo cifra con una clave AES/GCM del Android Keystore. Las copias
de seguridad del sistema estan desactivadas para esta app.

La cuenta `stock-mobile-reader` tiene `storage.objectViewer` en
los buckets de sistema e informes y permiso lector de la hoja Mercado. No
necesita claves descargadas, permiso de escritura ni acceso a IBKR/Tradier.

Fuentes:

- Layout/cartera: GCS `runtime/config/`.
- Precio, variacion y hora: GCS `runtime/market-quotes/latest.json`.
- Fuerza, momentum, resumen de grupos y panel general: lectura de Mercado.
- Analisis: `<TICKER>/latest.json` y `<TICKER>/history.json` en el bucket de
  informes. El historial compacto permite comparar catalizadores y proximos
  eventos aunque los informes ya esten publicados. Si el ultimo intento
  fallo, usa el espejo valido de `runtime/analysis-reports/` y muestra ambas
  fechas/estados. Un JSON fallido nunca se presenta como informe nuevo.

La API conserva su proyeccion durante 60 segundos y avisa si tiene que devolver
una copia previa por fallo de fuentes. Cloud Scheduler invoca el controlador de
Mercado cada minuto; el controlador decide que ejecuciones corresponden a la
sesion y publica tanto la hoja como la ultima cotizacion valida en GCS. La app
lee esa misma publicacion a traves de la API: no llama a Tradier ni programa
otro refresco de cotizaciones. La API le indica cuando volver a consultar,
tomando el intervalo de `data_refresh.session_intervals_minutes` del layout
de Mercado y adelantando la consulta al cambio de sesion. Si el layout no
incluye un intervalo valido, la app espera la actualizacion manual o una
nueva apertura; no inventa un intervalo de respaldo. El 01-10-2026 los
intervalos configurados eran 1 min regular, 5 min pre/posmercado y 60 min
cerrado; son configuracion observada, no una politica propia de la app. El
job de Mercado no publica una nueva muestra de precio durante el cierre; la
app conserva su hora observada. Los
indicadores de Sheets y las cotizaciones son fuentes distintas: no se
atribuye a las metricas de Sheets la hora del ultimo analisis.
La tabla muestra la hora de cada precio y diferencia una zona con cotizacion
reciente de una zona detectada con el ultimo precio disponible. No envia
notificaciones en segundo plano ni ordenes de compraventa.

## Compilacion y firma

Desde la raiz del repositorio:

```
.venv\Scripts\python.exe scripts\android_toolchain.py
.venv\Scripts\python.exe scripts\build_android.py --task=testDebugUnitTest,lintDebug
.venv\Scripts\python.exe scripts\build_android.py
```

El instalador descarga JDK, Gradle y SDK bajo `.local/android` y verifica los
checksums de distribucion. No cambia JAVA_HOME o PATH globales. El SDK no es
necesario en el telefono.

La firma personal se conserva en `.local/mobile/growth-release.jks`; su clave
esta en `signing-password.txt` en el mismo directorio ignorado por Git. Ambos
deben guardarse en una copia privada para poder actualizar la app sin
desinstalarla. No incluir estos archivos en commits ni en la distribucion.

El script lee la URL de `.local/mobile/deployment.json`, construye la APK,
verifica su firma y copia el resultado a `releases/android/Growth-0.1.0.apk`,
con un SHA-256 al lado. Antes de distribuir, comprobar que la URL no este vacia.

Si no hay despliegue autorizado, o con `--offline`, construye
`Growth-0.1.0-local.apk`. Esa edicion incluye la fotografia privada verificada
por `verify_mobile_data.py`, abre las cuatro pantallas sin codigo ni servidor,
y muestra permanentemente su condicion local y la fecha de los datos. Los
informes completos se incluyen como assets; no hay actualizaciones de red.
Por contener la copia de la cartera y sus informes, esta APK es para uso
personal y no debe publicarse como una distribucion abierta.

## Despliegue

```
.venv\Scripts\python.exe scripts\deploy_mobile_api.py
```

El script crea exclusivamente la API `stock-mobile-api` en europe-southwest1,
su identidad lectora y sus permisos. Cloud Run admite trafico externo, pero
las rutas de datos exigen el codigo privado; solo `/health` es publico. Limite:
cero instancias minimas, dos maximas, 512 MiB y un CPU por instancia.

Servicio desplegado el 30-09-2026, tras la autorizacion del usuario para la
version conectada:
`https://stock-mobile-api-qauoswkmwa-no.a.run.app`.
Actualizado el 01-10-2026, con autorizacion expresa, para entregar la sesion
de mercado y su intervalo a la app. Se corrigio el Dockerfile para incluir
`market_session.py` tras detectar que la primera revision devolvia 503; la
revision corregida supera la comprobacion del servicio real.
El despliegue habilita Google Drive API para conceder a la identidad nueva el
permiso lector de Mercado. La primera peticion puede necesitar esperar a que
se propaguen los permisos de invocacion; el script reintenta esa comprobacion.

No ejecuta refrescos ni despliega el controlador existente. Conserva logs de
despliegue y datos de verificacion bajo `.local/mobile/`, sin imprimir el codigo.

Para revocar todos los accesos, cambiar el codigo de `.local/mobile/access-code.txt`
y redesplegar. Los dispositivos tendran que introducir el nuevo codigo. La
APK no requiere recompilarse mientras la URL del servicio se conserve.

## Verificacion

```
.venv\Scripts\python.exe -m unittest discover -s gcp_services\mobile_api\tests -v
.venv\Scripts\python.exe scripts\verify_mobile_data.py
.venv\Scripts\python.exe scripts\verify_mobile_service.py
```

La segunda orden usa la autoridad local existente para leer fuentes sin
desplegar servicios ni conceder nuevos permisos. Las salidas verificadas quedan
en `.local/mobile/dashboard-verified.json`, `report-verified.json` y el paquete
privado `offline/` que utiliza la edicion local.
La tercera verifica el servicio desplegado: acceso autenticado, rechazo de
codigos ausentes/incorrectos, metodos de escritura rechazados, informe completo
y respuestas sin cache HTTP. Guarda evidencia en `.local/mobile/live-verification.json`.

La preparacion opcional del emulador de pruebas vive en
`scripts/prepare_android_emulator.py`; los datos del dispositivo tambien quedan
en `.local/android`. No utiliza telefonos fisicos conectados.

Para repetir las comprobaciones de interfaz:

```
.venv\Scripts\python.exe scripts\build_android.py --offline --task=assembleRelease,testDebugUnitTest,lintDebug,assembleDebug,assembleDebugAndroidTest
.venv\Scripts\python.exe scripts\start_android_emulator.py
.venv\Scripts\python.exe scripts\test_android_emulator.py
.venv\Scripts\python.exe scripts\stop_android_emulator.py
```

El ultimo script de pruebas instala y desinstala exclusivamente la app en el
emulador privado `growth-test` (puerto 5580). Comprueba cinco casos Compose y
despues instala la APK firmada, recorre las cuatro pantallas, abre un informe
completo y cambia al tema oscuro. Guarda capturas y resultados en
`releases/android/screenshots/`.
Para verificar solo la APK firmada final, con pruebas de sesion y cache sin
conexion, ejecutar `scripts/test_android_emulator.py --release-only`. Para
instalar una actualizacion en el emulador visible sin borrar su sesion, usar
`scripts/preview_android_update.py`.

## Instalacion

### Ver la app en este PC

Abrir `android/Abrir Growth.cmd` con doble clic. Inicia la ventana del emulador
privado ya instalado y abre Growth, conservando su sesion. Tambien se puede
ejecutar desde la raiz:

```
.venv\Scripts\python.exe scripts\start_android_emulator.py --visible --open-app
```

La ventana permite interactuar con las pantallas usando el raton. Cerrar la
ventana del emulador cuando se termine para liberar memoria. Este acceso usa
la APK que ya esta instalada en ese dispositivo virtual.

### Instalar en un telefono

Transferir la APK al telefono y abrirla. Android puede pedir habilitar la
instalacion desde la aplicacion usada para abrir el fichero. Introducir el
codigo privado una sola vez en la edicion conectada; la local no lo necesita.
La APK no incluye credenciales de Google Cloud,
IBKR, Tradier ni la clave privada de firma.

La edicion conectada esta en `releases/android/Growth-0.1.0.apk`. El codigo se
obtiene de `.local/mobile/access-code.txt`; introducirlo en la pantalla inicial.
Puede instalarse como actualizacion de la edicion local porque ambas conservan
el identificador de paquete y la misma firma personal. No es necesario configurar
permisos de GCP en el telefono ni mantener encendido este PC.

## Estado de esta entrega

La edicion conectada `Growth-0.1.0.apk` esta firmada e instalada en el emulador
privado Android 15. Las cuatro pantallas, el informe completo, el tema oscuro,
la sesion persistente tras reiniciar y la tabla guardada sin red se han probado
con la APK final. La ultima ejecucion de `--release-only` actualiza
`releases/android/screenshots/release-verification.json` con su SHA-256. Se
ejecutaron tambien 5 pruebas de interfaz Compose, pruebas unitarias Android y
15 pruebas de la API. La compatibilidad minima declarada es Android 8; la
prueba de dispositivo se ha realizado en Android 15.

El servicio real se verifico de nuevo el 01-10-2026 a las 09:38 UTC:
46 empresas, 14 grupos de datos, 3 cambios materiales (2 catalizadores y
1 evento) y 80 titulares, sin avisos de fuentes. La reduccion desde 23 avisos
se debe a eliminar falsos cambios por parafrasis, cifras omitidas en el
titular y hechos antiguos reintroducidos como nuevos. No habia en esos informes
una variacion de Tesis ni una accion de analistas que superase los filtros;
ambos tipos estan preparados para informes futuros. La respuesta incluia
`market_session=pre-market`, intervalo configurado de 5 minutos y siguiente
consulta tras 300 segundos. Tambien se
comprobo que el job desplegado `stock-analysis-market-refresh` esta habilitado
y llama al controlador cada minuto. La
verificacion cubrio ademas los 401 sin codigo y con codigo incorrecto, el 405
para POST, un informe completo y la ausencia de cache HTTP. Las cifras
describen esa lectura puntual, no un total fijo.

Auditoria del 01-10-2026: los 46 informes validos son del 30-09 y se comparan
con sus 46 versiones del 29-09. Contienen 198 catalizadores; 103 tienen
impacto absoluto >=7. De esos 103, 100 ya figuraban en la version anterior,
dos son hechos recientes nuevos (TLN y GEV) y uno se incorporo por primera
vez pero describe un hecho del 08-09 (ASML), por lo que queda fuera de la
ventana de siete dias. La auditoria detecto tambien 19 entradas recientes de
impacto 5 o 6 sin coincidencia automatica; son candidatos de menor prioridad,
no 19 noticias confirmadas como nuevas. El recuento de 3 cambios incluye
ademas un proximo evento actualizado de IBKR.

Se conserva `Growth-0.1.0-local.apk` como fotografia privada sin conexion del
30-09-2026. La APK conectada no incluye el codigo de acceso ni la fotografia
privada de la edicion local.
