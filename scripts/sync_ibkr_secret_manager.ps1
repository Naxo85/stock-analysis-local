[CmdletBinding()]
param(
    [ValidateSet('Upload', 'Status')]
    [string]$Action = 'Upload',
    [string]$ProjectId,
    [string]$SecretId = 'stock-analysis-ibkr-paper-credentials'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $repoRoot 'secrets\ibc\config.ini'
$gcloud = (Get-Command gcloud.cmd -ErrorAction Stop).Source

if (-not $ProjectId) {
    $ProjectId = ((& $gcloud config get-value project 2>$null) -join '').Trim()
}
if ([string]::IsNullOrWhiteSpace($ProjectId) -or $ProjectId -eq '(unset)') {
    throw 'Indica -ProjectId o configura un proyecto activo en gcloud.'
}

function Test-SecretExists {
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $gcloud secrets describe $SecretId --project=$ProjectId --format='value(name)' 2>$null | Out-Null
        $describeExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    return ($describeExitCode -eq 0)
}

if ($Action -eq 'Status') {
    if (Test-SecretExists) {
        $versions = & $gcloud secrets versions list $SecretId `
            --project=$ProjectId `
            --filter='state=ENABLED' `
            --format='value(name)' 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "No se pudieron consultar las versiones de '$SecretId'."
        }
        $enabledCount = @($versions | Where-Object { $_ }).Count
        Write-Host "OK Secret Manager: $ProjectId/$SecretId ($enabledCount version(es) habilitada(s))."
    }
    else {
        Write-Host "MISSING Secret Manager: $ProjectId/$SecretId"
    }
    exit 0
}

if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw "No existe la configuracion local de IB Gateway: $configPath"
}

$content = Get-Content -LiteralPath $configPath -Raw
$loginMatch = [regex]::Match($content, '(?m)^IbLoginId=(.*)$')
$passwordMatch = [regex]::Match($content, '(?m)^IbPassword=(.*)$')
if (-not $loginMatch.Success -or -not $passwordMatch.Success) {
    throw 'La configuracion local no contiene IbLoginId e IbPassword.'
}

$login = $loginMatch.Groups[1].Value.TrimEnd("`r")
$password = $passwordMatch.Groups[1].Value.TrimEnd("`r")
if ([string]::IsNullOrWhiteSpace($login) -or [string]::IsNullOrEmpty($password)) {
    throw 'Las credenciales locales de IB Gateway estan vacias.'
}

& $gcloud services enable secretmanager.googleapis.com --project=$ProjectId --quiet | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo habilitar Secret Manager en '$ProjectId'."
}

if (-not (Test-SecretExists)) {
    & $gcloud secrets create $SecretId `
        --project=$ProjectId `
        --replication-policy=automatic `
        --quiet | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo crear el secreto '$SecretId'."
    }
}

$payload = [ordered]@{
    username = $login
    password = $password
} | ConvertTo-Json -Compress
$tempPath = Join-Path ([IO.Path]::GetTempPath()) ('ibkr-secret-' + [guid]::NewGuid().ToString('N') + '.json')

try {
    [IO.File]::WriteAllText($tempPath, $payload, [Text.UTF8Encoding]::new($false))
    & $gcloud secrets versions add $SecretId `
        --project=$ProjectId `
        --data-file=$tempPath `
        --quiet | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo agregar la version de '$SecretId'."
    }
}
finally {
    if (Test-Path -LiteralPath $tempPath) {
        Remove-Item -LiteralPath $tempPath -Force
    }
    $payload = $null
    $password = $null
}

Write-Host "OK Secret Manager: credenciales guardadas en $ProjectId/$SecretId."
Write-Host 'No se ha mostrado ni subido a Git ningun valor secreto.'
