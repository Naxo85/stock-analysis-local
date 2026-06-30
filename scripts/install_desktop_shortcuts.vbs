Option Explicit

Dim shell, fso, scriptDir, repoRoot, desktop, powershell
Dim names, scripts, i, shortcutPath, scriptPath, shortcut

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
repoRoot = fso.GetParentFolderName(scriptDir)
desktop = shell.SpecialFolders("Desktop")
powershell = shell.ExpandEnvironmentStrings("%SystemRoot%") & _
  "\System32\WindowsPowerShell\v1.0\powershell.exe"

names = Array("Analizar Trading", "Analizar Core", "Analizar Ticker")
scripts = Array("analyze_trading.ps1", "analyze_core.ps1", "analyze_ticker.ps1")

For i = 0 To UBound(names)
  shortcutPath = fso.BuildPath(desktop, names(i) & ".lnk")
  scriptPath = fso.BuildPath(scriptDir, scripts(i))

  Set shortcut = shell.CreateShortcut(shortcutPath)
  shortcut.TargetPath = powershell
  shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File """ & _
    scriptPath & """"
  shortcut.WorkingDirectory = repoRoot
  shortcut.Description = names(i) & " - stock-analysis-local"
  shortcut.IconLocation = powershell & ",0"
  shortcut.Save

  WScript.Echo "Creado: " & shortcutPath
Next

WScript.Echo "Accesos directos instalados."
