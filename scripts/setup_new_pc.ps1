[CmdletBinding()]
param(
    [switch]$WithDevDependencies,
    [switch]$SkipPackageInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-BasePython {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        try {
            $version = & $python.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
            if ($LASTEXITCODE -eq 0 -and [version]$version -ge [version]'3.11') {
                return $python.Source
            }
        }
        catch {
            # Sigue buscando; el alias de Microsoft Store puede no ser ejecutable.
        }
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            & $py.Source -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
            if ($LASTEXITCODE -eq 0) {
                return "$($py.Source)|-3.12"
            }
        }
        catch {
            # El launcher existe pero Python 3.12 no esta instalado.
        }
    }

    throw @'
No se encontro Python 3.11 o superior.
Instala Python 3.12 desde https://www.python.org/downloads/windows/
activa "Add python.exe to PATH" y vuelve a ejecutar este script.
'@
}

function Invoke-BasePython {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonSpec,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    if ($PythonSpec -like '*|*') {
        $parts = $PythonSpec.Split('|', 2)
        & $parts[0] $parts[1] @Arguments
    }
    else {
        & $PythonSpec @Arguments
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Python termino con codigo $LASTEXITCODE."
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvRoot = Join-Path $repoRoot '.venv'
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'
$envLocal = Join-Path $repoRoot '.env.local'
$envExample = Join-Path $repoRoot '.env.example'

Write-Host "Proyecto: $repoRoot"

if (-not (Test-Path -LiteralPath $venvPython)) {
    $basePython = Get-BasePython
    Write-Host 'Creando entorno virtual .venv...'
    Invoke-BasePython -PythonSpec $basePython -Arguments @('-m', 'venv', $venvRoot)
}
else {
    Write-Host 'El entorno virtual .venv ya existe.'
}

if (-not $SkipPackageInstall) {
    Write-Host 'Actualizando pip...'
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo actualizar pip (codigo $LASTEXITCODE)."
    }

    $requirements = if ($WithDevDependencies) {
        Join-Path $repoRoot 'requirements-dev.txt'
    }
    else {
        Join-Path $repoRoot 'requirements.txt'
    }

    Write-Host "Instalando dependencias desde $requirements..."
    & $venvPython -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudieron instalar las dependencias (codigo $LASTEXITCODE)."
    }
}

if (-not (Test-Path -LiteralPath $envLocal)) {
    Copy-Item -LiteralPath $envExample -Destination $envLocal
    Write-Host 'Creado .env.local. Completa FINN_KEY antes del primer analisis.'
}
else {
    Write-Host '.env.local ya existe; no se ha modificado.'
}

Write-Host ''
Write-Host 'Instalacion local terminada.' -ForegroundColor Green
Write-Host 'Siguiente paso: autentica Codex y GCloud y ejecuta:'
Write-Host '  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_new_pc.ps1 -Online'
