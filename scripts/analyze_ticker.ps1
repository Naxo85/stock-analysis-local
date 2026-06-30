param(
    [string]$Ticker,
    [switch]$NoPause
)

. (Join-Path $PSScriptRoot 'stock_analysis_launcher_common.ps1')

try {
    if (-not $Ticker) {
        Add-Type -AssemblyName Microsoft.VisualBasic
        $Ticker = [Microsoft.VisualBasic.Interaction]::InputBox(
            'Introduce el ticker que quieres analizar:',
            'Analizar ticker',
            ''
        )
    }

    $Ticker = ([string]$Ticker).Trim().ToUpperInvariant()

    if (-not $Ticker) {
        Write-Host 'Operacion cancelada.' -ForegroundColor Yellow
        return
    }

    if ($Ticker -notmatch '^[A-Z0-9.\-]{1,15}$') {
        throw "Ticker no valido: $Ticker"
    }

    Write-Host "Iniciando analisis completo: $Ticker" -ForegroundColor Cyan
    Write-Host 'El proceso puede tardar varios minutos. No cierres esta ventana.' -ForegroundColor Yellow
    Write-Host ''
    Invoke-StockAnalysisPython -Arguments @(
        '-m', 'src.local_runner.run_one',
        $Ticker,
        '--run-full'
    )
    Write-Host "OK ${Ticker}: analisis generado y subido." -ForegroundColor Green
}
catch {
    Write-Host "FAILED ${Ticker}: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
    if (-not $NoPause) {
        Wait-StockAnalysisLauncher
    }
}
