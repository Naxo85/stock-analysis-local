Option Explicit

Dim shell, fso, scriptDir, installer, powershell, command, exitCode

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
installer = fso.BuildPath(scriptDir, "install_command_worker_task.ps1")
powershell = shell.ExpandEnvironmentStrings("%SystemRoot%") & _
  "\System32\WindowsPowerShell\v1.0\powershell.exe"
command = """" & powershell & """ -NoProfile -ExecutionPolicy Bypass " & _
  "-File """ & installer & """"

exitCode = shell.Run(command, 1, True)

If exitCode = 0 Then
  MsgBox "Tarea instalada. El worker comprobará GCS cada minuto.", _
    vbInformation, "Stock Analysis"
Else
  MsgBox "No se pudo instalar la tarea. Código: " & exitCode, _
    vbCritical, "Stock Analysis"
End If
