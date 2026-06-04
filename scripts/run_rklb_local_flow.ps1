param(
    [string]$PythonPath = "C:\Users\ignac\AppData\Local\Programs\Python\Python312\python.exe"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Preparing RKLB local Codex input..."
& $PythonPath -m src.local_runner.run_one RKLB --prepare

Write-Host ""
Write-Host "Codex-assisted step required:"
Write-Host "Lee output/RKLB/codex_input.md y guarda el analisis en output/RKLB/latest.md"
Write-Host ""
Write-Host "This helper stops here on purpose."
Write-Host "It does not generate markdown automatically."
Write-Host "It does not run validation automatically."
Write-Host "It does not upload anything."
Write-Host ""
Write-Host "Next command after Codex writes latest.md:"
Write-Host "& '$PythonPath' -m src.local_runner.run_one RKLB --validate"
Write-Host ""
Write-Host "Optional dry-run test upload after validation passes:"
Write-Host "& '$PythonPath' -m src.local_runner.run_one RKLB --upload-test"
