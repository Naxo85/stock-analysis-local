param(
    [ValidateRange(1, 8)]
    [int]$MaxParallel = 6,
    [switch]$NoPause
)

. (Join-Path $PSScriptRoot 'stock_analysis_launcher_common.ps1')

try {
    Write-Host 'Iniciando analisis completo: CORE' -ForegroundColor Cyan
    Write-Host 'El batch puede tardar varios minutos. No cierres esta ventana.' -ForegroundColor Yellow
    Write-Host ''
    Invoke-StockAnalysisPython -Arguments @(
        '-m', 'src.local_runner.run_batch',
        '--config-gcs', 'gs://stock-analysis-reports-naxo85/config/tickers_core.json',
        '--upload-real',
        '--max-parallel', [string]$MaxParallel
    )
    Write-Host 'OK CORE: batch completado.' -ForegroundColor Green
}
catch {
    Write-Host "FAILED CORE: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
    if (-not $NoPause) {
        Wait-StockAnalysisLauncher
    }
}
