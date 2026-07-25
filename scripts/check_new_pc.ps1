[CmdletBinding()]
param(
    [switch]$Online,
    [switch]$CheckIbkr
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$script:Failures = 0
$script:Warnings = 0

function Write-Check {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet('OK', 'WARN', 'FAIL')]
        [string]$Status,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    $color = switch ($Status) {
        'OK' { 'Green' }
        'WARN' { 'Yellow' }
        'FAIL' { 'Red' }
    }

    Write-Host "[$Status] $Message" -ForegroundColor $color
    if ($Status -eq 'FAIL') {
        $script:Failures++
    }
    elseif ($Status -eq 'WARN') {
        $script:Warnings++
    }
}

function Test-ExternalCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Names,
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [switch]$Required
    )

    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            Write-Check OK "$Label encontrado: $($command.Source)"
            return $command.Source
        }
    }

    if ($Required) {
        Write-Check FAIL "$Label no encontrado."
    }
    else {
        Write-Check WARN "$Label no encontrado (funcion opcional)."
    }
    return $null
}

function Find-CodexCommand {
    if ($env:LOCALAPPDATA) {
        $binRoot = Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin'
        if (Test-Path -LiteralPath $binRoot) {
            $bundled = Get-ChildItem -LiteralPath $binRoot -Filter codex.exe -Recurse |
                Sort-Object LastWriteTimeUtc -Descending |
                Select-Object -First 1
            if ($bundled) {
                return $bundled.FullName
            }
        }
    }

    if ($env:APPDATA) {
        $npmCodex = Join-Path $env:APPDATA 'npm\codex.cmd'
        if (Test-Path -LiteralPath $npmCodex) {
            return $npmCodex
        }
    }

    foreach ($name in @('codex.cmd', 'codex.exe', 'codex')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }

    return $null
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$envLocal = Join-Path $repoRoot '.env.local'

Write-Host "Comprobando: $repoRoot"
Write-Host ''

if (Test-Path -LiteralPath $venvPython) {
    $version = & $venvPython --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Check OK "Entorno virtual disponible ($version)."
    }
    else {
        Write-Check FAIL 'El Python de .venv no se puede ejecutar.'
    }
}
else {
    Write-Check FAIL 'Falta .venv. Ejecuta scripts\setup_new_pc.ps1.'
}

if (Test-Path -LiteralPath $venvPython) {
    & $venvPython -c "import markdown, ib_insync" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Check OK 'Dependencias Python principales instaladas.'
    }
    else {
        Write-Check FAIL 'Faltan dependencias Python. Repite setup_new_pc.ps1.'
    }
}

if (Test-Path -LiteralPath $envLocal) {
    $finnLine = Get-Content -LiteralPath $envLocal |
        Where-Object { $_ -match '^\s*(FINN_KEY|FINNHUB_API_KEY)\s*=\s*.+$' } |
        Select-Object -First 1
    if ($finnLine -and $finnLine -notmatch '=\s*$') {
        Write-Check OK 'Clave Finnhub configurada en .env.local.'
    }
    else {
        Write-Check WARN 'Completa FINN_KEY en .env.local para el calendario de resultados.'
    }
}
else {
    Write-Check FAIL 'Falta .env.local. Ejecuta setup_new_pc.ps1.'
}

$codex = Find-CodexCommand
if ($codex) {
    Write-Check OK "Codex CLI encontrado: $codex"
}
else {
    Write-Check FAIL 'Codex CLI no encontrado.'
}
$gcloud = Test-ExternalCommand -Names @('gcloud.cmd', 'gcloud') -Label 'Google Cloud SDK' -Required
$null = Test-ExternalCommand -Names @('git.exe', 'git') -Label 'Git' -Required
$null = Test-ExternalCommand -Names @('clasp.cmd', 'clasp') -Label 'clasp'

if ($Online -and $gcloud) {
    $activeAccount = $null
    & $gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>$null |
        Select-Object -First 1 |
        ForEach-Object { $activeAccount = $_ }
    if ($activeAccount) {
        Write-Check OK "GCloud autenticado como $activeAccount."
    }
    else {
        Write-Check FAIL 'GCloud no tiene una cuenta activa. Ejecuta gcloud auth login.'
    }

    & $gcloud storage ls 'gs://stock-analysis-reports-naxo85/config/' 1>$null 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Check OK 'Acceso de lectura al bucket GCS confirmado.'
    }
    else {
        Write-Check FAIL 'No se pudo leer el bucket GCS con la cuenta activa.'
    }

    try {
        $response = Invoke-WebRequest `
            -Uri 'https://support-resistances-slim-714254943648.europe-southwest1.run.app?symbol=RKLB' `
            -Method Get `
            -TimeoutSec 30 `
            -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Check OK 'Endpoint slim accesible.'
        }
        else {
            Write-Check FAIL "Endpoint slim respondio HTTP $($response.StatusCode)."
        }
    }
    catch {
        Write-Check FAIL "No se pudo acceder al endpoint slim: $($_.Exception.Message)"
    }
}
elseif (-not $Online) {
    Write-Check WARN 'Comprobaciones de GCloud y endpoint omitidas; usa -Online.'
}

if ($CheckIbkr) {
    $connection = Test-NetConnection -ComputerName 127.0.0.1 -Port 7497 -WarningAction SilentlyContinue
    if ($connection.TcpTestSucceeded) {
        Write-Check OK 'IBKR TWS/Gateway escucha en 127.0.0.1:7497.'
    }
    else {
        Write-Check WARN 'IBKR TWS/Gateway no escucha en 127.0.0.1:7497.'
    }
}
else {
    Write-Check WARN 'IBKR no comprobado; usa -CheckIbkr con TWS/Gateway abierto.'
}

Write-Host ''
if ($script:Failures -eq 0) {
    Write-Host "Equipo preparado ($script:Warnings avisos opcionales)." -ForegroundColor Green
    exit 0
}

Write-Host "Configuracion incompleta: $script:Failures fallos, $script:Warnings avisos." -ForegroundColor Red
exit 1
