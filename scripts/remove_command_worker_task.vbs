Option Explicit

Dim shell, fso, scriptDir, remover, powershell, command, exitCode

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
remover = fso.BuildPath(scriptDir, "remove_command_worker_task.ps1")
powershell = shell.ExpandEnvironmentStrings("%SystemRoot%") & _
  "\System32\WindowsPowerShell\v1.0\powershell.exe"
command = """" & powershell & """ -NoProfile -ExecutionPolicy Bypass " & _
  "-File """ & remover & """"

exitCode = shell.Run(command, 1, True)

If exitCode = 0 Then
  MsgBox "Tarea eliminada.", vbInformation, "Stock Analysis"
Else
  MsgBox "No se pudo eliminar la tarea. Código: " & exitCode, _
    vbCritical, "Stock Analysis"
End If
