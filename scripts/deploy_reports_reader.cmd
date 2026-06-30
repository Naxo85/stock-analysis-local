@echo off
setlocal

set "PROJECT_ID=recipe-generator-429817"
set "REGION=europe-southwest1"
set "SERVICE=reports"
set "SOURCE_DIR=%~dp0..\gcp_functions\reports_reader"
set "BUCKET=stock-analysis-reports-naxo85"
set "SERVICE_ACCOUNT=714254943648-compute@developer.gserviceaccount.com"

gcloud.cmd run deploy %SERVICE% ^
  --quiet ^
  --project %PROJECT_ID% ^
  --region %REGION% ^
  --source "%SOURCE_DIR%" ^
  --allow-unauthenticated ^
  --ingress all ^
  --memory 512Mi ^
  --timeout 300 ^
  --max-instances 20 ^
  --service-account %SERVICE_ACCOUNT% ^
  --update-env-vars GCS_BUCKET=%BUCKET%,ALLOWED_ORIGIN=*

endlocal
