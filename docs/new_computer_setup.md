# Preparar un ordenador nuevo

Esta guia deja el ordenador nuevo listo para ejecutar el flujo diario. El
codigo y los scripts llegan mediante Git; las cuentas y secretos se configuran
manualmente porque no deben guardarse en el repositorio.

## 1. Antes de salir: ordenador actual

El repositorio remoto debe contener todos los cambios que quieras llevarte.
Comprueba:

```powershell
git status
git log --oneline origin/main..HEAD
```

Si quedan cambios correctos, revisalos, crea los commits y sube la rama:

```powershell
git push origin main
```

No subas `.env.local`, credenciales JSON, tokens ni claves. La configuracion
secreta debe copiarse por un medio privado o volver a crearse en el nuevo
ordenador.

Guarda por separado:

- el valor de `FINN_KEY` o `FINNHUB_API_KEY`;
- `GEMINI_API_KEY` o `GOOGLE_API_KEY`, solo si lo utilizas;
- acceso a la cuenta de Google con permisos sobre
  `gs://stock-analysis-reports-naxo85`;
- acceso a GitHub si el repositorio no es publico;
- credenciales de IBKR, si usaras TWS/Gateway.

## 2. Instalar programas en el ordenador nuevo

Instala:

1. Git para Windows.
2. Python 3.12 de 64 bits. Activa la opcion para añadir Python a `PATH`.
3. Codex Desktop e inicia sesion con la cuenta que ejecutara los analisis.
4. Google Cloud SDK.

Opcional:

5. IBKR TWS o IB Gateway para noticias, analistas y eventos.
6. Node.js LTS y `@google/clasp` para gestionar Apps Script.

Reinicia PowerShell despues de instalar herramientas que modifican `PATH`.

## 3. Clonar y preparar Python

Elige una carpeta de trabajo y ejecuta:

```powershell
git clone https://github.com/Naxo85/stock-analysis-local.git
Set-Location .\stock-analysis-local
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\setup_new_pc.ps1
```

El script:

- crea `.venv` dentro del repositorio;
- actualiza `pip`;
- instala `requirements.txt`;
- crea `.env.local` desde `.env.example` si no existe.

Para instalar tambien dependencias de pruebas y desarrollo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\setup_new_pc.ps1 -WithDevDependencies
```

## 4. Configurar secretos locales

Abre `.env.local` y completa al menos una clave Finnhub:

```dotenv
FINN_KEY=tu_clave
```

La clave de Gemini es opcional:

```dotenv
GEMINI_API_KEY=tu_clave
```

`.env.local` esta ignorado por Git. No lo añadas manualmente a un commit.

## 5. Autenticar Google Cloud

En una consola nueva:

```powershell
gcloud.cmd auth login
gcloud.cmd config set project recipe-generator-429817
gcloud.cmd auth list
gcloud.cmd storage ls gs://stock-analysis-reports-naxo85/config/
```

La ultima orden debe listar la configuracion del bucket. Para ejecutar el flujo
real, la cuenta necesita leer configuraciones e informes y escribir informes y
snapshots.

En PowerShell usa preferentemente `gcloud.cmd`; el launcher `.ps1` puede quedar
bloqueado por la politica de ejecucion.

## 6. Comprobar Codex

Codex Desktop incluye normalmente el ejecutable que usa el runner. Comprueba:

```powershell
codex --version
```

Si el comando no esta en `PATH`, el runner intenta localizar automaticamente el
ejecutable incluido bajo `%LOCALAPPDATA%\OpenAI\Codex\bin`.

Tambien puede fijarse una ruta explicita para una consola:

```powershell
$env:CODEX_CLI_PATH = 'C:\ruta\a\codex.exe'
```

La cuenta de Codex debe tener acceso al modelo configurado por el runner.

## 7. IBKR opcional

Para conservar la actualizacion de analistas y noticias:

1. instala TWS o IB Gateway;
2. inicia sesion;
3. habilita conexiones API;
4. permite conexiones locales;
5. usa el puerto paper `7497`.

El flujo principal considera esta actualizacion no bloqueante. Sin TWS puede
generar el informe, pero no dispondra de noticias/analistas nuevos de IBKR.

## 8. Verificacion completa

Con TWS cerrado:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\check_new_pc.ps1 -Online
```

Con TWS abierto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\check_new_pc.ps1 -Online -CheckIbkr
```

El verificador no muestra valores secretos. Comprueba:

- `.venv` y paquetes Python;
- presencia de `.env.local` y de una clave Finnhub;
- Git, Codex y Google Cloud SDK;
- cuenta activa y lectura del bucket GCS;
- acceso al endpoint slim;
- puerto de IBKR, si se solicita.

## 9. Primera prueba

Primero prepara un ticker sin subir resultados:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.run_one RKLB --prepare
```

Despues ejecuta el flujo real:

```powershell
.\.venv\Scripts\python.exe -m src.local_runner.run_one RKLB --run-full
```

Respuesta esperada:

```text
OK RKLB: analisis generado y subido.
```

## 10. Utilidades opcionales

Instalar accesos directos de escritorio:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\install_desktop_shortcuts.ps1
```

Instalar el worker de la cola como tarea programada:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\install_command_worker_task.ps1
```

Comprobar `clasp`:

```powershell
npm install --global @google/clasp
clasp login
cmd /c scripts\apps_script_status.cmd
```

Estas utilidades no son necesarias para ejecutar `analiza RKLB` desde Codex.
