[CmdletBinding()]
param(
    [string]$ProjectId = 'recipe-generator-429817',
    [string]$BucketUri = 'gs://stock-analysis-reports-naxo85/bootstrap/ibkr',
    [string]$BundleVersion = 'ibgateway-10.50_ibc-3.24.1_20260814',
    [switch]$ExecuteUpload
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$ibcSource = Join-Path $repoRoot '.local\ibc'
$gatewaySource = Join-Path $repoRoot '.local\ibgateway\ibgateway-offline'
$buildBase = Join-Path $repoRoot '.tmp\ibkr-bundle-build'
$artifactDir = Join-Path $repoRoot ".tmp\ibkr-bundles\$BundleVersion"
$workRoot = Join-Path $buildBase ([guid]::NewGuid().ToString('N'))
$packageRoot = Join-Path $workRoot 'package'
$ibcDestination = Join-Path $packageRoot '.local\ibc'
$gatewayDestination = Join-Path $packageRoot '.local\ibgateway\ibgateway-offline'
$archiveName = "$BundleVersion.zip"
$archivePath = Join-Path $artifactDir $archiveName
$manifestPath = Join-Path $artifactDir 'manifest.json'
$latestPath = Join-Path $artifactDir 'latest.json'

function Assert-SafeBuildPath {
    param([string]$Path)
    $resolvedBase = [IO.Path]::GetFullPath($buildBase).TrimEnd('\') + '\'
    $resolvedPath = [IO.Path]::GetFullPath($Path).TrimEnd('\') + '\'
    if (-not $resolvedPath.StartsWith($resolvedBase, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Ruta temporal fuera del area permitida: $Path"
    }
}

foreach ($required in @(
    (Join-Path $ibcSource 'IBC.jar'),
    (Join-Path $ibcSource 'config.ini'),
    (Join-Path $ibcSource 'scripts\StartIBC.bat'),
    (Join-Path $gatewaySource 'ibgateway.vmoptions'),
    (Join-Path $gatewaySource 'jre\bin\java.exe')
)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Falta un componente requerido: $required"
    }
}

Assert-SafeBuildPath -Path $workRoot
New-Item -ItemType Directory -Path $ibcDestination -Force | Out-Null
New-Item -ItemType Directory -Path $gatewayDestination -Force | Out-Null
New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null

try {
    foreach ($name in @('IBC.jar', 'config.ini', 'LICENSE.txt', 'README.txt', 'version', 'userguide.pdf')) {
        $source = Join-Path $ibcSource $name
        if (Test-Path -LiteralPath $source -PathType Leaf) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $ibcDestination $name)
        }
    }
    Copy-Item -LiteralPath (Join-Path $ibcSource 'scripts') -Destination $ibcDestination -Recurse

    Get-ChildItem -LiteralPath $gatewaySource -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $gatewayDestination -Recurse
    }

    $ibcConfigPath = Join-Path $ibcDestination 'config.ini'
    $ibcConfig = Get-Content -LiteralPath $ibcConfigPath -Raw
    foreach ($key in @('IbLoginId', 'IbPassword', 'FIXLoginId', 'FIXPassword')) {
        $pattern = '(?m)^' + [regex]::Escape($key) + '=.*$'
        if (-not [regex]::IsMatch($ibcConfig, $pattern)) {
            throw "La plantilla IBC no contiene $key."
        }
        $ibcConfig = [regex]::Replace($ibcConfig, $pattern, "$key=")
    }
    [IO.File]::WriteAllText($ibcConfigPath, $ibcConfig, [Text.UTF8Encoding]::new($false))

    $vmOptionsPath = Join-Path $gatewayDestination 'ibgateway.vmoptions'
    $vmOptions = Get-Content -LiteralPath $vmOptionsPath -Raw
    if (-not [regex]::IsMatch($vmOptions, '(?m)^-DvmOptionsPath=.*$')) {
        throw 'ibgateway.vmoptions no contiene -DvmOptionsPath.'
    }
    $vmOptions = [regex]::Replace(
        $vmOptions,
        '(?m)^-DvmOptionsPath=.*$',
        '-DvmOptionsPath=__IBKR_GATEWAY_VMOPTIONS__'
    )
    [IO.File]::WriteAllText($vmOptionsPath, $vmOptions, [Text.UTF8Encoding]::new($false))

    foreach ($relativePath in @(
        '.install4j\inst_jre.cfg',
        '.install4j\pref_jre.cfg',
        '.install4j\response.varfile'
    )) {
        $candidate = Join-Path $gatewayDestination $relativePath
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            Remove-Item -LiteralPath $candidate -Force
        }
    }

    $sanitizedConfig = Get-Content -LiteralPath $ibcConfigPath -Raw
    foreach ($key in @('IbLoginId', 'IbPassword', 'FIXLoginId', 'FIXPassword')) {
        if (-not [regex]::IsMatch($sanitizedConfig, "(?m)^$key=$")) {
            throw "La credencial $key no quedo vacia en el paquete."
        }
    }

    $forbiddenMachineText = @(
        'stock-analysis-local',
        'C:\Users\ignac',
        'c:\users\ignac'
    )
    $textExtensions = @('.ini', '.txt', '.cfg', '.conf', '.properties', '.vmoptions', '.varfile', '.xml', '.bat')
    foreach ($file in Get-ChildItem -LiteralPath $packageRoot -Recurse -File) {
        if ($textExtensions -notcontains $file.Extension.ToLowerInvariant()) {
            continue
        }
        $text = Get-Content -LiteralPath $file.FullName -Raw
        foreach ($forbidden in $forbiddenMachineText) {
            if ($text.IndexOf($forbidden, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
                throw "El paquete conserva una ruta local en $($file.FullName)."
            }
        }
    }

    foreach ($existing in @($archivePath, $manifestPath, $latestPath)) {
        if (Test-Path -LiteralPath $existing -PathType Leaf) {
            Remove-Item -LiteralPath $existing -Force
        }
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory(
        $packageRoot,
        $archivePath,
        [IO.Compression.CompressionLevel]::Optimal,
        $false
    )

    $archive = Get-Item -LiteralPath $archivePath
    $hash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $remoteBase = $BucketUri.TrimEnd('/') + '/' + $BundleVersion
    $manifest = [ordered]@{
        schema_version = 1
        bundle_version = $BundleVersion
        created_utc = [DateTime]::UtcNow.ToString('o')
        archive_name = $archiveName
        archive_uri = "$remoteBase/$archiveName"
        sha256 = $hash
        size_bytes = $archive.Length
        ib_gateway_version = '10.50'
        ibc_version = '3.24.1'
        contains_credentials = $false
        secret_project = $ProjectId
        secret_id = 'stock-analysis-ibkr-paper-credentials'
    }
    $manifestJson = $manifest | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText($manifestPath, $manifestJson, [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($latestPath, $manifestJson, [Text.UTF8Encoding]::new($false))

    Write-Host "OK bundle: $archivePath"
    Write-Host "SHA256: $hash"
    Write-Host ("Tamano comprimido: {0:N1} MB" -f ($archive.Length / 1MB))

    if ($ExecuteUpload) {
        $gcloud = (Get-Command gcloud.cmd -ErrorAction Stop).Source
        & $gcloud storage cp $archivePath "$remoteBase/$archiveName" --project=$ProjectId --quiet
        if ($LASTEXITCODE -ne 0) { throw 'Fallo al subir el archivo del bundle.' }
        & $gcloud storage cp $manifestPath "$remoteBase/manifest.json" --project=$ProjectId --quiet
        if ($LASTEXITCODE -ne 0) { throw 'Fallo al subir el manifiesto versionado.' }
        & $gcloud storage cp $latestPath ($BucketUri.TrimEnd('/') + '/latest.json') --project=$ProjectId --quiet
        if ($LASTEXITCODE -ne 0) { throw 'Fallo al publicar latest.json.' }
        Write-Host "OK GCS: $remoteBase"
    }
    else {
        Write-Host 'DRY RUN: no se ha subido nada. Usa -ExecuteUpload para publicar.'
    }
}
finally {
    if (Test-Path -LiteralPath $workRoot) {
        Assert-SafeBuildPath -Path $workRoot
        Remove-Item -LiteralPath $workRoot -Recurse -Force
    }
}
