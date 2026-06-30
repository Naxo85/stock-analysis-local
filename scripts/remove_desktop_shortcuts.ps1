Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$desktop = [Environment]::GetFolderPath('Desktop')
$names = @(
    'Analizar Trading.lnk',
    'Analizar Core.lnk',
    'Analizar Ticker.lnk',
    'Procesar Cola Una Vez.lnk'
)

foreach ($name in $names) {
    $path = Join-Path $desktop $name
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
        Write-Host "Eliminado: $path"
    }
}

Write-Host 'Accesos directos eliminados.' -ForegroundColor Green
