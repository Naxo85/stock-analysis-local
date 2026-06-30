Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$taskName = 'Stock Analysis Command Worker'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($task) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Tarea eliminada: $taskName" -ForegroundColor Green
} else {
    Write-Host "La tarea no existe: $taskName" -ForegroundColor Yellow
}
