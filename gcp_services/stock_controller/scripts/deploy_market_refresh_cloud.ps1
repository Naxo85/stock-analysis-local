param(
    [string]$Config = "config\gcp_market_refresh.json"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $repo $Config
$settings = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json

function Invoke-Gcloud {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & gcloud.cmd @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud failed with exit code ${LASTEXITCODE}: $($Arguments -join ' ')"
    }
}

$project = $settings.project
$runRegion = $settings.cloud_run_region
$schedulerRegion = $settings.scheduler_region
$runtimeAccount = $settings.runtime_service_account
$schedulerAccount = $settings.scheduler_service_account
$schedulerAccountId = $schedulerAccount.Split("@")[0]
$bucketUri = "gs://$($settings.history_bucket)"
$revisionSuffix = "deploy" + (Get-Date -Format "yyyyMMddHHmmss")

Invoke-Gcloud services enable `
    run.googleapis.com `
    cloudscheduler.googleapis.com `
    firestore.googleapis.com `
    secretmanager.googleapis.com `
    sheets.googleapis.com `
    artifactregistry.googleapis.com `
    cloudbuild.googleapis.com `
    --project $project

$bucketExists = & gcloud.cmd storage buckets list `
    --project $project `
    --filter "name=$($settings.history_bucket)" `
    --format "value(name)"
if (-not ($bucketExists -contains $settings.history_bucket)) {
    Invoke-Gcloud storage buckets create $bucketUri `
        --project $project `
        --location $runRegion `
        --uniform-bucket-level-access
}

$schedulerAccountExists = & gcloud.cmd iam service-accounts list `
    --project $project `
    --filter "email=$schedulerAccount" `
    --format "value(email)"
if (-not ($schedulerAccountExists -contains $schedulerAccount)) {
    Invoke-Gcloud iam service-accounts create $schedulerAccountId `
        --project $project `
        --display-name "Stock Analysis Scheduler"
}

Invoke-Gcloud secrets add-iam-policy-binding $settings.tradier_secret `
    --project $project `
    --member "serviceAccount:$runtimeAccount" `
    --role roles/secretmanager.secretAccessor

Invoke-Gcloud projects add-iam-policy-binding $project `
    --member "serviceAccount:$runtimeAccount" `
    --role roles/datastore.user `
    --condition None

Invoke-Gcloud storage buckets add-iam-policy-binding $bucketUri `
    --member "serviceAccount:$runtimeAccount" `
    --role roles/storage.objectUser

Push-Location $repo
try {
    Invoke-Gcloud run deploy $settings.service `
        --project $project `
        --region $runRegion `
        --source . `
        --revision-suffix $revisionSuffix `
        --service-account $runtimeAccount `
        --no-allow-unauthenticated `
        --ingress all `
        --max-instances 1 `
        --concurrency 1 `
        --memory 512Mi `
        --timeout 180 `
        --set-env-vars "MARKET_HISTORY_BUCKET=$($settings.history_bucket)" `
        --set-secrets "TRADIER_TOKEN=$($settings.tradier_secret):latest" `
        --quiet
}
finally {
    Pop-Location
}

Invoke-Gcloud run services update-traffic $settings.service `
    --project $project `
    --region $runRegion `
    --to-latest `
    --quiet

$serviceUrl = (& gcloud.cmd run services describe $settings.service `
    --project $project `
    --region $runRegion `
    --format "value(status.url)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $serviceUrl) {
    throw "Could not resolve Cloud Run service URL"
}

Invoke-Gcloud run services add-iam-policy-binding $settings.service `
    --project $project `
    --region $runRegion `
    --member "serviceAccount:$schedulerAccount" `
    --role roles/run.invoker

$schedulerJobs = & gcloud.cmd scheduler jobs list `
    --project $project `
    --location $schedulerRegion `
    --format "value(ID)"

function Set-SchedulerJob {
    param(
        [string]$Name,
        [string]$Endpoint
    )

    $arguments = @(
        "--project", $project,
        "--location", $schedulerRegion,
        "--schedule", $settings.scheduler_cron,
        "--time-zone", $settings.scheduler_time_zone,
        "--uri", "$serviceUrl$Endpoint",
        "--http-method", "POST",
        "--oidc-service-account-email", $schedulerAccount,
        "--oidc-token-audience", $serviceUrl,
        "--attempt-deadline", "180s",
        "--max-retry-attempts", "2"
    )

    if ($schedulerJobs -contains $Name) {
        Invoke-Gcloud scheduler jobs update http $Name @arguments
    }
    else {
        Invoke-Gcloud scheduler jobs create http $Name @arguments
    }
}

Set-SchedulerJob $settings.scheduler_job $settings.endpoint
Set-SchedulerJob $settings.analysis_scheduler_job $settings.analysis_endpoint

Write-Output "Cloud Run: $serviceUrl"
Write-Output "Cloud Scheduler market: $($settings.scheduler_job)"
Write-Output "Cloud Scheduler reports: $($settings.analysis_scheduler_job)"
