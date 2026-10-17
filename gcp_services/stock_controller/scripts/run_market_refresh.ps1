param(
    [switch]$Publish,
    [switch]$Force,
    [string]$Output = "artifacts\market_snapshot.json",
    [string]$RequestsOutput = "artifacts\market_requests.json",
    [string]$GoogleProject = "recipe-generator-429817",
    [string]$TradierSecret = "tradier-token"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found: $python"
}
if (-not $env:TRADIER_TOKEN) {
    $env:TRADIER_TOKEN = & gcloud.cmd secrets versions access latest `
        --secret=$TradierSecret `
        --project=$GoogleProject
    if ($LASTEXITCODE -ne 0 -or -not $env:TRADIER_TOKEN) {
        throw "TRADIER_TOKEN is not configured and Secret Manager lookup failed"
    }
}

$arguments = @(
    "-m", "stock_analysis.market_worker.run_refresh",
    "--output", $Output,
    "--requests-output", $RequestsOutput
)
if ($Publish) { $arguments += "--publish" }
if ($Force) { $arguments += "--force" }

Push-Location $repo
try {
    & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Market refresh failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
