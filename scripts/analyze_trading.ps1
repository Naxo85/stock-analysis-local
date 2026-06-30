param(
    [ValidateRange(1, 8)]
    [int]$MaxParallel = 6,
    [switch]$NoPause
)

. (Join-Path $PSScriptRoot 'stock_analysis_launcher_common.ps1')

try {
    Write-Host 'Iniciando analisis completo: TRADING' -ForegroundColor Cyan
    Write-Host 'El batch puede tardar varios minutos. No cierres esta ventana.' -ForegroundColor Yellow
    Write-Host ''
    Invoke-StockAnalysisPython -Arguments @(
        '-m', 'src.local_runner.run_batch',
        '--from-gcs',
        '--upload-real',
        '--max-parallel', [string]$MaxParallel
    )
    Write-Host 'OK TRADING: batch completado.' -ForegroundColor Green
}
catch {
    Write-Host "FAILED TRADING: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
    if (-not $NoPause) {
        Wait-StockAnalysisLauncher
    }
}
