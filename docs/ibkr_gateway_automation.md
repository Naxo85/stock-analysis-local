# IB Gateway automático, IBC y Secret Manager

Esta guía es la referencia operativa del acceso local a IBKR. Describe el estado
implantado, cómo funciona durante un análisis y cómo reconstruirlo en otro
ordenador sin guardar credenciales en Git.

## 1. Estado implantado

El sistema usa **IB Gateway**, no TWS, porque expone la misma API y consume menos
recursos. IBC automatiza el inicio de sesión de la cuenta simulada.

| Elemento | Estado actual |
|---|---|
| Cuenta | IBKR paper/simulada |
| Aplicación | IB Gateway offline 10.50 |
| Automatización de login | IBC 3.24.1 |
| API | `127.0.0.1:7497` |
| Permisos API | Solo lectura |
| Inicio | Automático antes de preparar o ejecutar análisis |
| Interfaz | Escritorio privado; sin consola ni dialogos en el escritorio del usuario |
| Credenciales | Google Secret Manager + copia local ignorada por Git |

TWS ya no forma parte del arranque automático. Esto evita el `Daily Lineup`,
otros pop-ups promocionales y la interfaz completa de negociación.

## 2. Flujo de ejecución

```text
run_one --prepare / --run-full          run_batch
              |                            |
              +---- ensure_gateway --------+
                            |
                 handshake API real y read-only
                    en 127.0.0.1:7497
                       /            \
                  responde        no responde
                     |                 |
              continuar          iniciar IBC
                                      |
                              login en IB Gateway paper
                                      |
                         esperar hasta 180 s y verificar
```

`run_batch` hace una única comprobación compartida antes del lote. Sus procesos
`run_one` reciben `--skip-ibkr-gateway-ensure` para no repetir el arranque.

Desde el 04/10, el sondeo comprueba primero si escucha el puerto TCP. Un puerto
cerrado durante login retorna no disponible sin imprimir errores repetidos de
ib_insync. Si escucha, sigue siendo obligatorio el handshake API read-only;
abrir el puerto no se acepta como prueba de Gateway operativa. La limpieza
previa/recovery usa Win32 nativo en vez de PowerShell/CIM sin timeout: solo la
ruta exacta del Java aislado, verificada otra vez en el mismo handle que se
termina, y espera acotada. No se mata Java por nombre ni por PID sin comprobar.
Errores de acceso/limpieza bloquean un arranque duplicado y quedan visibles.
Desde el08/10 se distingue ademas un proceso que YA esta terminando de una
denegacion real. Se consulta su estado antes de la imagen, y se espera dentro
del mismo plazo15s si QueryFullProcessImageName/TerminateProcess fallan durante
su cierre asincrono. Solo salida confirmada en el mismo handle permite omitir
el proceso; un acceso denegado persistente sigue fallando. Si falla OpenProcess,
un handle solo de espera puede confirmar salida, pero nunca autorizar cierre.
La recuperacion espera su launcher antes de limpiar hijos restantes. Probado
con regresiones de cada carrera y dos ciclos Gateway reales: recuperacion de
perfil y siguiente arranque limpios, API read-only y cero ventanas interactivas.
Esto NO demuestra el origen interno del rechazo del perfil cifrado; se conserva
el original archivado, sin cambiar ACL, credenciales ni permisos globales.
Probado offline y con inventario real de solo lectura; no se reinicio Gateway
para la correccion original del04/10. El rechazo de perfil visto el 04/10 ya fue recuperado
por el mecanismo anterior; la causa raiz del cifrado no esta demostrada.

La disponibilidad de la API es ahora un **preflight estricto** para `--prepare`
y `--run-full`: no se consume modelo ni se publica un informe nuevo si Gateway
no puede iniciarse. Una vez conectada la API, los refrescos concretos de
analistas y noticias siguen siendo no bloqueantes y pueden usar el último estado
local válido si falla una petición individual.

## 3. Componentes y rutas

Código versionado:

| Ruta | Función |
|---|---|
| `src/local_runner/ibkr_gateway_manager.py` | Handshake, arranque, espera y diagnóstico |
| `scripts/setup_ibkr_gateway_autostart.ps1` | Genera la configuración local desde prompt o Secret Manager |
| `scripts/sync_ibkr_secret_manager.ps1` | Publica credenciales y consulta el estado del secreto |
| `scripts/publish_ibkr_gateway_bundle.ps1` | Construye, sanea y publica el bundle privado |
| `scripts/bootstrap_ibkr_gateway.ps1` | Descarga, verifica, instala, restaura y prueba Gateway |
| `tests/test_ibkr_gateway_manager.py` | Pruebas del preflight y del arranque oculto |

Elementos locales excluidos por `.gitignore`:

| Ruta | Contenido |
|---|---|
| `.local/ibc/` | IBC 3.24.1 y `StartIBC.bat` |
| `.local/ibgateway/ibgateway-offline/` | Instalación aislada de IB Gateway |
| `.local/ibgateway-settings/` | Ajustes locales de Gateway |
| `secrets/ibc/config.ini` | Login, contraseña y configuración efectiva de IBC |
| `logs/tws/ibc-*.log` | Log de cada intento de arranque |

Los binarios bajo `.local/` no caben en Secret Manager. Se conserva una copia
saneada y versionada en el bucket privado. Los ajustes de usuario y los logs no
forman parte de ese bundle. Secret Manager limita cada payload a 64 KiB:
[límite oficial](https://docs.cloud.google.com/secret-manager/docs/reference/rest/v1/SecretPayload).

### 3.1 Bundle privado actual

```text
gs://stock-analysis-reports-naxo85/bootstrap/ibkr/
├── latest.json
└── ibgateway-10.50_ibc-3.24.1_20260814/
    ├── manifest.json
    └── ibgateway-10.50_ibc-3.24.1_20260814.zip
```

Datos verificados:

```text
Tamaño comprimido: 320,4 MB
SHA-256: d5d832c27a7d2ae98057cfe6d1add0ede43433a0f95379633784802047fb2d0e
Credenciales: no incluidas
Rutas del ordenador de origen: no incluidas
```

El publicador crea una zona temporal, copia únicamente los componentes
necesarios, vacía `IbLoginId`, `IbPassword`, `FIXLoginId` y `FIXPassword`, elimina
metadatos del instalador con rutas locales y sustituye `-DvmOptionsPath` por un
marcador portable. Antes de comprimir también busca identificadores del equipo
de origen en todos los archivos de texto relevantes.

`latest.json` apunta a una versión inmutable y contiene tamaño, versiones,
URI y SHA-256. El bootstrap no acepta manifiestos que apunten fuera de la ruta
privada autorizada.

La ACL del objeto se comprobó después de publicarlo: solo propietarios,
editores y lectores del proyecto pueden descargarlo; no existen entradas
`allUsers` ni `allAuthenticatedUsers`.

Para reconstruir el bundle localmente sin publicar:

```powershell
.\scripts\publish_ibkr_gateway_bundle.ps1
```

Para publicar una versión nueva de forma explícita:

```powershell
.\scripts\publish_ibkr_gateway_bundle.ps1 -ExecuteUpload
```

El bundle ocupa aproximadamente 0,32 GiB. En Standard Storage regional de
Madrid representa alrededor de un céntimo de dólar al mes, más operaciones o
transferencia aplicables. Referencia: [precios oficiales de Cloud Storage](https://cloud.google.com/storage/pricing?hl=es).

## 4. Configuración efectiva de seguridad

El generador de `config.ini` fija:

```ini
TradingMode=paper
OverrideTwsApiPort=7497
ReadOnlyApi=yes
AcceptIncomingConnectionAction=accept
StoreSettingsOnServer=no
MinimizeMainWindow=yes
ExistingSessionDetectedAction=primaryoverride
```

Las conexiones se limitan al host local. La cuenta es simulada y la API es de
solo lectura, por lo que el runner no puede enviar órdenes.

El proceso se inicia con `CREATE_NO_WINDOW`: la consola de Java/IBC no permanece
abierta. La salida se redirige a `logs/tws/`. Gateway puede funcionar sin una
ventana visible mientras el proceso Java siga activo.

### Aislamiento de ventanas activado y verificado el 28/09

`CREATE_NO_WINDOW` oculta la consola pero no garantiza ocultar los dialogos
Java. El modo privado crea IBC y sus hijos en un
escritorio Win32 privado desde el inicio. Conserva los logs y la API, no cambia
el escritorio del usuario y no abre una ventana visible si falla el aislamiento.
El manager actual recupera el error de `ibg.xml` mediante el log y la recreacion
acotada del perfil; ya no llama al helper historico que pulsaba Yes con el raton.

Activacion persistente en `.local/background_windows.json` con `ibkr=true`,
consultada en cada arranque. `ANALYSIS_PRIVATE_DESKTOP=1` fuerza el modo y `=0`
permite volver explicitamente al arranque antiguo para diagnostico.
Verificado sin lote activo mediante
`python scripts/verify_ibkr_cold_starts.py --private-desktop`: recuperacion real
del perfil rechazado por log, arranque recuperado y siguiente reinicio frio
limpios, handshake read-only y cero ventanas en el escritorio interactivo.
El perfil rechazado se conservo bajo `.local/ibgateway-settings-archive/`.
Gateway queda operativo en el escritorio privado; no se realizaron operaciones
de trading ni se enviaron analisis. No repetir pruebas en frio durante un lote.

## 5. Secret Manager

Configuración actual:

```text
Proyecto: recipe-generator-429817
Secreto:  stock-analysis-ibkr-paper-credentials
Formato:  JSON con username y password
Versión:  una versión habilitada
Réplica:  automática
```

El valor nunca se muestra en la consola ni se escribe en el repositorio. Para
publicarlo, el script crea un JSON temporal, lo entrega a `gcloud` como archivo
y lo elimina en un bloque `finally`.

La capa gratuita de Secret Manager incluye, por cuenta de facturación, seis
versiones activas y 10.000 accesos mensuales. Nuestro uso normal es una versión
y accesos ocasionales. Los límites se agregan entre proyectos de la misma
cuenta de facturación. Referencia: [precios oficiales de Secret Manager](https://cloud.google.com/secret-manager/pricing?hl=es).

Comprobar metadatos sin leer el valor:

```powershell
.\scripts\sync_ibkr_secret_manager.ps1 `
  -Action Status `
  -ProjectId recipe-generator-429817
```

Salida esperada:

```text
OK Secret Manager: recipe-generator-429817/stock-analysis-ibkr-paper-credentials (1 version(es) habilitada(s)).
```

## 6. Operación diaria

No es necesario abrir Gateway manualmente. Un análisis normal lo comprueba y,
si hace falta, lo inicia:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.run_one RKLB --run-full
```

Comprobar únicamente la API, sin arrancarla:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.ibkr_gateway_manager --check-only
```

Comprobar o arrancar Gateway:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.ibkr_gateway_manager
```

Resultados posibles:

```text
OK IBKR: already_running en 127.0.0.1:7497.
OK IBKR: started en 127.0.0.1:7497.
FAILED IBKR: <motivo>
```

El ordenador debe estar encendido o suspendido con una tarea capaz de
despertarlo. El arranque de Gateway no puede encender un PC completamente
apagado. Tras una reanudación, el siguiente análisis vuelve a hacer el handshake
y recupera Gateway si es necesario.

## 7. Reconstrucción en otro ordenador

### 7.1 Requisitos

1. Clonar el repositorio y ejecutar `scripts/setup_new_pc.ps1`.
2. Instalar y autenticar Google Cloud SDK con una cuenta autorizada.
3. Configurar el proyecto `recipe-generator-429817`.

Comprobar Google Cloud:

```powershell
gcloud.cmd auth login
gcloud.cmd config set project recipe-generator-429817
gcloud.cmd auth list
```

### 7.2 Bootstrap completo

Desde la raíz del repositorio:

```powershell
.\scripts\bootstrap_ibkr_gateway.ps1
```

El comando realiza, por orden:

1. descarga `latest.json` y el ZIP privado desde GCS;
2. verifica el SHA-256 antes de instalar;
3. comprueba que las cuatro credenciales estén vacías en la plantilla;
4. instala IBC y Gateway bajo `.local/` sin sobrescribir instalaciones existentes;
5. reescribe `ibgateway.vmoptions` con la ruta del nuevo repositorio;
6. restaura las credenciales desde Secret Manager;
7. inicia Gateway oculto y exige un handshake API real.

El resultado local sensible se crea únicamente en:

```text
secrets/ibc/config.ini
```

No imprime usuario ni contraseña. Para descargar y auditar sin instalar:

```powershell
.\scripts\bootstrap_ibkr_gateway.ps1 -VerifyOnly
```

Si se utiliza otro proyecto, secreto o manifiesto:

```powershell
.\scripts\bootstrap_ibkr_gateway.ps1 `
  -ProjectId otro-proyecto `
  -SecretId otro-secreto `
  -ManifestUri gs://otro-bucket/ruta/latest.json
```

La protección de URI debe modificarse en el script si se cambia de bucket.

### 7.3 Prueba posterior

Con Gateway cerrado:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.ibkr_gateway_manager
.\.venv\Scripts\python.exe -m src.local_runner.ibkr_gateway_manager --check-only
```

Después puede ejecutarse una preparación sin publicación:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.run_one RKLB --prepare
```

## 8. Alta inicial o cambio de contraseña

Para crear la configuración local escribiendo las credenciales de forma
interactiva:

```powershell
.\scripts\setup_ibkr_gateway_autostart.ps1
```

Para publicar esa configuración en Secret Manager:

```powershell
.\scripts\sync_ibkr_secret_manager.ps1 `
  -Action Upload `
  -ProjectId recipe-generator-429817
```

Cada `Upload` añade una versión. Después de verificar la nueva versión, deben
destruirse las antiguas para mantener una sola versión activa:

```powershell
gcloud.cmd secrets versions list stock-analysis-ibkr-paper-credentials `
  --project=recipe-generator-429817

gcloud.cmd secrets versions destroy VERSION_ANTIGUA `
  --secret=stock-analysis-ibkr-paper-credentials `
  --project=recipe-generator-429817
```

Nunca destruyas la versión más reciente antes de probar la restauración.

## 9. Diagnóstico

| Síntoma | Interpretación o acción |
|---|---|
| `API Client: disconnected` en Gateway | Normal cuando ningún script está consultando IBKR |
| `Historical Data Farm: inactive` | Normal hasta que se solicita histórico |
| Aparece una consola negra | El arranque no está usando el manager actualizado; revisar `CREATE_NO_WINDOW` |
| Aparece `Daily Lineup` | Se ha abierto TWS; el flujo automático debe usar IB Gateway |
| `Downloading settings from server failed` | Se evitó usando Gateway e IBC con `StoreSettingsOnServer=no` |
| `We are having trouble loading your settings` / falta `ibg.xml` | Antes del arranque se recupera la transaccion o copia diaria disponible. Si Gateway rechaza otra vez el archivo durante el login, el manager detiene su proceso, archiva exclusivamente el perfil identificado y lo recrea una vez. Una segunda repeticion falla explicitamente; no se acepta como sano solo porque responda la API. |

### Reinicio limpio de un perfil cifrado en bucle

El 20/08/2026 se confirmó un caso en el que `ibg.xml`, `ibg.tmp.xml` y las
copias diarias parecían válidas, pero Gateway retiraba `ibg.xml` durante cada
login y volvía a mostrar el diálogo de recuperación. Marcar *Don't display this
message again* no resolvía el problema porque el fallo ocurría antes de cargar
esa preferencia.

La solución verificada fue:

1. cerrar únicamente el proceso Java de la instalación local de Gateway;
2. mover el subdirectorio cifrado de la cuenta fuera de
   `.local/ibgateway-settings/`, conservando `jts.ini`;
3. arrancar Gateway mediante el manager para recrear el perfil;
4. hacer un segundo arranque en frío y confirmar en el log que aparecen
   `Login has completed` y `Configuration tasks completed`, sin el texto
   `trouble loading your settings`.

El perfil anterior se conservó de forma recuperable en:

```text
.local/ibgateway-settings-archive/account-before-clean-reset-20260820-194302/
```

Mientras Gateway está abierto es normal que exista `ibg.tmp.xml`. Si el
proceso termina antes de consolidarlo, el manager lo promueve a `ibg.xml` en el
siguiente arranque.

Historicamente, desde el 28/08/2026, el bucle de arranque exigia dos comprobaciones antes de
aceptar el aviso: el log de IBC debe contener el mensaje completo de
recuperación (`trouble loading your settings`, `File does not exist` y
`Would you like to try recovering`) y Windows debe exponer una ventana titulada
`IBKR Gateway` de clase `SunAwtDialog`. Como los botones Swing no son controles
Win32 nativos, se pulsa el centro relativo estable de `Yes` y se restaura la
posición original del cursor. La desaparición de `SunAwtDialog` se verificó en
vivo el 28/08/2026, manteniéndose la API disponible en `127.0.0.1:7497`.
Ese helper ya no se llama: el manager vigente recupera por log, conservando y
recreando una vez el perfil rechazado. No mueve el raton ni pulsa botones en el
escritorio del usuario, tambien cuando el dialogo existe en un escritorio privado.
| `ibkr_gateway_autostart_not_configured` | Falta alguno de los archivos locales requeridos |
| `ibkr_gateway_autostart_failed` | Revisar el `exit_code` y el log indicado |
| `ibkr_gateway_autostart_timeout` | Gateway no completó login/API en 180 segundos |
| Secret Manager devuelve permiso denegado | Autenticar `gcloud` con la cuenta correcta y revisar IAM del proyecto |
| El PC está apagado | Gateway no puede arrancar; usar suspensión y una tarea con wake |

El manager solo termina procesos Java cuyo ejecutable coincide exactamente con
la instalación aislada de este repositorio. No mata otras aplicaciones Java.

## 10. Validaciones realizadas

### Incidente 23/09/2026

El aviso de perfil reaparecio el 21/08 tras los dos arranques limpios del 20/08.
La restauracion del archivo cifrado no garantizaba que Gateway lo aceptase;
el manejo del dialogo tampoco dejo marcadores de aceptacion en los logs.
El 23/09 se archivo el perfil completo, conservando `jts.ini`, y el perfil
nuevo paso dos reinicios en frio y consultas API reales sin ese aviso.

El manager ya no acepta un handshake como prueba suficiente si el log registra
el error exacto de recuperacion. Detiene su propio Gateway, archiva solo el
subdirectorio de cuenta identificado en el error y lo recrea una unica vez.
Si vuelve a fallar, devuelve `ibkr_gateway_settings_recovery_repeated`.
No copia automaticamente las mismas copias diarias rechazadas una y otra vez.

La cascada de logins tambien se amplificaba por fallos ajenos a IBKR: los
timeouts de noticias incluyen lecturas previas de GCS. Ahora solo reinician
Gateway si su API no responde. El bloqueo de GCS por un PID ya terminado y los
hijos de procesos que sobrevivian a timeouts se corrigieron separadamente.

Prueba repetible de arranques en frio (requiere que no haya lote usando IBKR):
`python scripts/verify_ibkr_cold_starts.py`.

El 14 de agosto de 2026 se comprobó:

- inicio en frío de la cuenta paper con Gateway cerrado;
- handshake real mediante `ib_insync` en `127.0.0.1:7497`;
- API de solo lectura;
- creación del secreto y su versión 1;
- restauración desde Secret Manager con la misma huella SHA-256 que el fichero original;
- reinicio sin consola visible y API disponible después del reinicio;
- recuperación automática de `ibg.xml` cuando falta pero existe una copia diaria cifrada válida;
- pruebas automatizadas del manager y de su flag `CREATE_NO_WINDOW`;
- construcción y auditoría del bundle saneado de 320,4 MB;
- publicación privada del ZIP, manifiesto versionado y `latest.json`;
- descarga real desde GCS y validación de SHA-256;
- instalación completa en una raíz temporal independiente;
- reescritura portable de `ibgateway.vmoptions`, Java presente y credenciales vacías;
- eliminación de la copia redundante de credenciales en `.local/ibc/config.ini`.

El plan de modelos Sol/Terra/Luna y las tareas de programación semanal se
mantienen aparte en [`model_reference_automation_plan.md`](model_reference_automation_plan.md).
