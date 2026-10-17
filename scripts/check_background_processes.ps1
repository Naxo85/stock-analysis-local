$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$processes = Get-CimInstance Win32_Process
$rows = foreach ($proc in $processes) {
    $command = [string]$proc.CommandLine
    if ($proc.Name -notmatch '^(pythonw?|firefox|geckodriver|java)\.exe$') { continue }
    if ($command -notmatch 'stock-analysis-local|src\.local_runner|chatgpt-firefox|firefox-isolation') { continue }
    $role = $proc.Name
    if ($command -match 'src\.local_runner\.([\w]+)') { $role = $Matches[1] }
    elseif ($command -match 'scripts[\\/]([\w.-]+)') { $role = $Matches[1] }
    [pscustomobject]@{
        pid = $proc.ProcessId
        parent = $proc.ParentProcessId
        role = $role
        executable = $proc.ExecutablePath
        started = [string]$proc.CreationDate
    }
}
$rows | ConvertTo-Json -Depth 3
Get-ChildItem -LiteralPath (Join-Path $repoRoot 'logs\batch') -Filter sheet_progress.json -Recurse |
    Sort-Object LastWriteTime -Descending | Select-Object -First 3 | ForEach-Object {
        $progress = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
        [pscustomobject]@{path=$_.FullName; status=$progress.status; heartbeat=$progress.heartbeat_at; completed=$progress.completed; total=$progress.total} | ConvertTo-Json
    }
