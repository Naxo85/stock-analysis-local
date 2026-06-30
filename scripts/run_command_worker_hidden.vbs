Option Explicit

Dim shell, fso, scriptDir, workerScript, powershell, command, exitCode

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
workerScript = fso.BuildPath(scriptDir, "process_command_queue_once.ps1")
powershell = shell.ExpandEnvironmentStrings("%SystemRoot%") & _
  "\System32\WindowsPowerShell\v1.0\powershell.exe"
command = """" & powershell & """ -NoProfile -ExecutionPolicy Bypass " & _
  "-File """ & workerScript & """ -NoPause"

' Window style 0 keeps the minute worker completely hidden. Waiting preserves
' Task Scheduler's IgnoreNew behavior while an analysis is still running.
exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode
