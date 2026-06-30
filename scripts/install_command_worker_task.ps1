Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$taskName = 'Stock Analysis Command Worker'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workerScript = Join-Path $PSScriptRoot 'run_command_worker_hidden.vbs'
$wscript = Join-Path $env:SystemRoot 'System32\wscript.exe'
$userId = "$env:USERDOMAIN\$env:USERNAME"

$arguments = "`"$workerScript`""

$action = New-ScheduledTaskAction `
    -Execute $wscript `
    -Argument $arguments `
    -WorkingDirectory $repoRoot

$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 1)

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description 'Procesa una orden de análisis pendiente en GCS cada minuto.' `
    -Force | Out-Null

Write-Host "Tarea instalada: $taskName" -ForegroundColor Green
Write-Host "Usuario: $userId"
Write-Host 'Frecuencia: cada minuto'
Write-Host 'Instancias simultáneas: IgnoreNew'
