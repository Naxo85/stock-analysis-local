Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$desktop = [Environment]::GetFolderPath('Desktop')
$powershell = Join-Path $PSHOME 'powershell.exe'
$shell = New-Object -ComObject WScript.Shell

$shortcuts = @(
    @{ Name = 'Analizar Trading'; Script = 'analyze_trading.ps1' },
    @{ Name = 'Analizar Core'; Script = 'analyze_core.ps1' },
    @{ Name = 'Analizar Ticker'; Script = 'analyze_ticker.ps1' }
)

foreach ($item in $shortcuts) {
    $scriptPath = Join-Path $PSScriptRoot $item.Script
    $shortcutPath = Join-Path $desktop ($item.Name + '.lnk')
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $powershell
    $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
    $shortcut.WorkingDirectory = $repoRoot
    $shortcut.Description = $item.Name + ' - stock-analysis-local'
    $shortcut.IconLocation = "$powershell,0"
    $shortcut.Save()
    Write-Host "Creado: $shortcutPath"
}

Write-Host ''
Write-Host 'Accesos directos instalados.' -ForegroundColor Green
