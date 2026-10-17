[CmdletBinding()]
param(
    [string]$ProjectId,
    [string]$SecretId = 'stock-analysis-ibkr-paper-credentials',
    [string]$RepoRoot
)

$ErrorActionPreference = 'Stop'
if ($RepoRoot) {
    $repoRoot = [IO.Path]::GetFullPath($RepoRoot)
}
else {
    $repoRoot = Split-Path -Parent $PSScriptRoot
}
$ibcTemplate = Join-Path $repoRoot '.local\ibc\config.ini'
$configDir = Join-Path $repoRoot 'secrets\ibc'
$configPath = Join-Path $configDir 'config.ini'
$settingsDir = Join-Path $repoRoot '.local\ibgateway-settings'

if (-not (Test-Path -LiteralPath $ibcTemplate -PathType Leaf)) {
    throw "No se encuentra IBC en $ibcTemplate"
}

$plainPassword = $null
$passwordPointer = [IntPtr]::Zero

if ($ProjectId) {
    $gcloud = (Get-Command gcloud.cmd -ErrorAction Stop).Source
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $secretJson = & $gcloud secrets versions access latest `
            --secret=$SecretId `
            --project=$ProjectId 2>$null
        $accessExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($accessExitCode -ne 0) {
        throw "No se pudo leer el secreto '$SecretId' del proyecto '$ProjectId'."
    }

    try {
        $credentials = ($secretJson -join [Environment]::NewLine) | ConvertFrom-Json
    }
    catch {
        throw "El secreto '$SecretId' no contiene JSON valido."
    }

    $login = [string]$credentials.username
    $plainPassword = [string]$credentials.password
    if ([string]::IsNullOrWhiteSpace($login) -or [string]::IsNullOrEmpty($plainPassword)) {
        throw "El secreto '$SecretId' debe contener username y password."
    }
}
else {
    $login = Read-Host 'Usuario de la cuenta IBKR paper'
    $securePassword = Read-Host 'Password de la cuenta IBKR paper' -AsSecureString
    $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
}

try {
    $content = Get-Content -LiteralPath $ibcTemplate -Raw
    $sanitizedTemplate = $content

    $values = [ordered]@{
        IbLoginId = $login
        IbPassword = $plainPassword
        TradingMode = 'paper'
        AcceptNonBrokerageAccountWarning = 'yes'
        StoreSettingsOnServer = 'no'
        MinimizeMainWindow = 'yes'
        ExistingSessionDetectedAction = 'primaryoverride'
        OverrideTwsApiPort = '7497'
        ReadOnlyLogin = 'yes'
        ReadOnlyApi = 'yes'
        AcceptIncomingConnectionAction = 'accept'
        ReloginAfterSecondFactorAuthenticationTimeout = 'yes'
    }

    foreach ($entry in $values.GetEnumerator()) {
        $pattern = '(?m)^' + [regex]::Escape($entry.Key) + '=.*$'
        $replacement = $entry.Key + '=' + $entry.Value
        $content = [regex]::Replace(
            $content,
            $pattern,
            [System.Text.RegularExpressions.MatchEvaluator]{ param($match) $replacement }
        )
    }

    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    New-Item -ItemType Directory -Path $settingsDir -Force | Out-Null
    [IO.File]::WriteAllText($configPath, $content, [Text.UTF8Encoding]::new($false))

    foreach ($key in @('IbLoginId', 'IbPassword', 'FIXLoginId', 'FIXPassword')) {
        $pattern = '(?m)^' + [regex]::Escape($key) + '=.*$'
        $sanitizedTemplate = [regex]::Replace($sanitizedTemplate, $pattern, "$key=")
    }
    [IO.File]::WriteAllText($ibcTemplate, $sanitizedTemplate, [Text.UTF8Encoding]::new($false))
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    $plainPassword = $null
}

Write-Host "Configuracion guardada fuera de Git: $configPath"
Write-Host 'Plantilla local de IBC saneada: no conserva credenciales.'
if ($ProjectId) {
    Write-Host "Credenciales restauradas desde Secret Manager: $ProjectId/$SecretId"
}
Write-Host 'IB Gateway se iniciara en modo paper, API de solo lectura y puerto 7497.'
