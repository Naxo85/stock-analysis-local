Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-StockAnalysisRepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

function Get-StockAnalysisPython {
    if ($env:STOCK_ANALYSIS_PYTHON -and (Test-Path -LiteralPath $env:STOCK_ANALYSIS_PYTHON)) {
        return $env:STOCK_ANALYSIS_PYTHON
    }

    $preferred = 'C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe'
    if (Test-Path -LiteralPath $preferred) {
        return $preferred
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw 'No se encontro Python. Define STOCK_ANALYSIS_PYTHON con la ruta a python.exe.'
}

function Invoke-StockAnalysisPython {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $repoRoot = Get-StockAnalysisRepoRoot
    $python = Get-StockAnalysisPython

    Push-Location $repoRoot
    try {
        Write-Host "Repo: $repoRoot"
        Write-Host "Python: $python"
        Write-Host ''

        $env:PYTHONUNBUFFERED = '1'
        & $python @Arguments
        $exitCode = $LASTEXITCODE

        if ($exitCode -ne 0) {
            throw "El proceso termino con codigo $exitCode."
        }
    }
    finally {
        Pop-Location
    }
}

function Wait-StockAnalysisLauncher {
    param(
        [string]$Message = 'Pulsa Enter para cerrar'
    )

    Write-Host ''
    Read-Host $Message | Out-Null
}
