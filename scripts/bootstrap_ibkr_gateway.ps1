[CmdletBinding()]
param(
    [string]$ProjectId = 'recipe-generator-429817',
    [string]$ManifestUri = 'gs://stock-analysis-reports-naxo85/bootstrap/ibkr/latest.json',
    [string]$SecretId = 'stock-analysis-ibkr-paper-credentials',
    [string]$DestinationRoot,
    [switch]$SkipCredentialRestore,
    [switch]$SkipGatewayStart,
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $DestinationRoot) {
    $DestinationRoot = $repoRoot
}
$DestinationRoot = [IO.Path]::GetFullPath($DestinationRoot)
$gcloud = (Get-Command gcloud.cmd -ErrorAction Stop).Source
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('ibkr-bootstrap-' + [guid]::NewGuid().ToString('N'))
$manifestPath = Join-Path $tempRoot 'manifest.json'
$archivePath = Join-Path $tempRoot 'bundle.zip'
$extractRoot = Join-Path $tempRoot 'extracted'

function Invoke-GcloudDownload {
    param([string]$Source, [string]$Destination)
    & $gcloud storage cp $Source $Destination --project=$ProjectId --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo descargar $Source"
    }
}

New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null

try {
    Invoke-GcloudDownload -Source $ManifestUri -Destination $manifestPath
    try {
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    }
    catch {
        throw 'El manifiesto del bundle no contiene JSON valido.'
    }

    if ($manifest.schema_version -ne 1 -or $manifest.contains_credentials -ne $false) {
        throw 'El manifiesto no declara un bundle saneado compatible.'
    }
    if ([string]::IsNullOrWhiteSpace([string]$manifest.archive_uri) -or
        [string]::IsNullOrWhiteSpace([string]$manifest.sha256)) {
        throw 'El manifiesto no contiene archive_uri y sha256.'
    }
    if (-not ([string]$manifest.archive_uri).StartsWith('gs://stock-analysis-reports-naxo85/bootstrap/ibkr/')) {
        throw 'El manifiesto apunta fuera de la ruta privada autorizada.'
    }

    Invoke-GcloudDownload -Source ([string]$manifest.archive_uri) -Destination $archivePath
    $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne ([string]$manifest.sha256).ToLowerInvariant()) {
        throw "Checksum SHA256 incorrecto: esperado=$($manifest.sha256) actual=$actualHash"
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($archivePath)
    try {
        $safeExtractRoot = [IO.Path]::GetFullPath($extractRoot).TrimEnd('\') + '\'
        foreach ($entry in $zip.Entries) {
            $entryTarget = [IO.Path]::GetFullPath((Join-Path $extractRoot $entry.FullName))
            if (-not $entryTarget.StartsWith($safeExtractRoot, [StringComparison]::OrdinalIgnoreCase)) {
                throw "Entrada ZIP fuera de la raiz permitida: $($entry.FullName)"
            }
        }
    }
    finally {
        $zip.Dispose()
    }
    [IO.Compression.ZipFile]::ExtractToDirectory($archivePath, $extractRoot)

    $extractedIbc = Join-Path $extractRoot '.local\ibc'
    $extractedGateway = Join-Path $extractRoot '.local\ibgateway\ibgateway-offline'
    foreach ($required in @(
        (Join-Path $extractedIbc 'IBC.jar'),
        (Join-Path $extractedIbc 'config.ini'),
        (Join-Path $extractedIbc 'scripts\StartIBC.bat'),
        (Join-Path $extractedGateway 'ibgateway.vmoptions'),
        (Join-Path $extractedGateway 'jre\bin\java.exe')
    )) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "El bundle esta incompleto: $required"
        }
    }

    $template = Get-Content -LiteralPath (Join-Path $extractedIbc 'config.ini') -Raw
    foreach ($key in @('IbLoginId', 'IbPassword', 'FIXLoginId', 'FIXPassword')) {
        if (-not [regex]::IsMatch($template, "(?m)^$key=$")) {
            throw "El bundle contiene un valor no saneado en $key."
        }
    }

    if ($VerifyOnly) {
        Write-Host "OK bundle verificado: $($manifest.bundle_version)"
        Write-Host "SHA256: $actualHash"
        exit 0
    }

    $destinationIbc = Join-Path $DestinationRoot '.local\ibc'
    $destinationGateway = Join-Path $DestinationRoot '.local\ibgateway\ibgateway-offline'
    $ibcExists = Test-Path -LiteralPath $destinationIbc
    $gatewayExists = Test-Path -LiteralPath $destinationGateway
    if ($ibcExists -xor $gatewayExists) {
        throw 'Instalacion parcial detectada: existen IBC o Gateway, pero no ambos.'
    }

    if (-not $ibcExists) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $destinationIbc) -Force | Out-Null
        New-Item -ItemType Directory -Path (Split-Path -Parent $destinationGateway) -Force | Out-Null
        Copy-Item -LiteralPath $extractedIbc -Destination $destinationIbc -Recurse
        Copy-Item -LiteralPath $extractedGateway -Destination $destinationGateway -Recurse
        Write-Host "OK binarios instalados: $($manifest.bundle_version)"
    }
    else {
        $installedIbcVersion = (Get-Content -LiteralPath (Join-Path $destinationIbc 'version') -Raw).Trim()
        if ($installedIbcVersion -ne [string]$manifest.ibc_version) {
            throw "IBC existente $installedIbcVersion no coincide con $($manifest.ibc_version)."
        }
        $installedVmOptions = Get-Content -LiteralPath (Join-Path $destinationGateway 'ibgateway.vmoptions') -Raw
        if ($installedVmOptions -notmatch ('IB Gateway ' + [regex]::Escape([string]$manifest.ib_gateway_version))) {
            throw "IB Gateway existente no coincide con $($manifest.ib_gateway_version)."
        }
        Write-Host 'OK binarios existentes: no se han sobrescrito.'
    }

    $vmOptionsPath = Join-Path $destinationGateway 'ibgateway.vmoptions'
    $vmOptions = Get-Content -LiteralPath $vmOptionsPath -Raw
    $portablePath = $vmOptionsPath
    $vmOptions = [regex]::Replace(
        $vmOptions,
        '(?m)^-DvmOptionsPath=.*$',
        [System.Text.RegularExpressions.MatchEvaluator]{ param($match) "-DvmOptionsPath=$portablePath" }
    )
    [IO.File]::WriteAllText($vmOptionsPath, $vmOptions, [Text.UTF8Encoding]::new($false))
    New-Item -ItemType Directory -Path (Join-Path $DestinationRoot '.local\ibgateway-settings') -Force | Out-Null

    if (-not $SkipCredentialRestore) {
        $setupScript = Join-Path $repoRoot 'scripts\setup_ibkr_gateway_autostart.ps1'
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setupScript `
            -ProjectId $ProjectId `
            -SecretId $SecretId `
            -RepoRoot $DestinationRoot
        if ($LASTEXITCODE -ne 0) {
            throw 'No se pudieron restaurar las credenciales desde Secret Manager.'
        }
    }

    if (-not $SkipGatewayStart) {
        if ($DestinationRoot -ne [IO.Path]::GetFullPath($repoRoot)) {
            throw 'El arranque solo esta permitido en la raiz del repositorio actual.'
        }
        $python = Join-Path $repoRoot '.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
            throw 'Falta .venv. Ejecuta scripts\setup_new_pc.ps1 antes del bootstrap.'
        }
        & $python -m src.local_runner.ibkr_gateway_manager
        if ($LASTEXITCODE -ne 0) {
            throw 'IB Gateway se instalo, pero no supero el handshake API.'
        }
    }

    Write-Host 'OK bootstrap IBKR completado.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        $resolvedTemp = [IO.Path]::GetFullPath($tempRoot)
        $allowedTemp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
        if (-not $resolvedTemp.StartsWith($allowedTemp, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Ruta temporal no segura: $resolvedTemp"
        }
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
