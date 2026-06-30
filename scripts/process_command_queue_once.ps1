param(
    [switch]$NoPause
)

. (Join-Path $PSScriptRoot 'stock_analysis_launcher_common.ps1')

$scriptExitCode = 0

try {
    Write-Host 'Comprobando una orden pendiente...' -ForegroundColor Cyan
    Invoke-StockAnalysisPython -Arguments @(
        '-m', 'src.local_runner.command_worker',
        '--once'
    )
    Write-Host 'Worker finalizado.' -ForegroundColor Green
}
catch {
    Write-Host "FAILED WORKER: $($_.Exception.Message)" -ForegroundColor Red
    $scriptExitCode = 1
}
finally {
    if (-not $NoPause) {
        Wait-StockAnalysisLauncher
    }
}

exit $scriptExitCode
