# ============================================================
#  Deploy de catalogo-cloud-api a Google Cloud Run (Windows)
#  Uso:  .\deploy.ps1 -ProjectId mi-proyecto-gcp
#  (Si PowerShell bloquea scripts:  Set-ExecutionPolicy -Scope Process Bypass)
# ============================================================
param(
    [Parameter(Mandatory = $true)][string]$ProjectId,
    [string]$Region  = "us-central1",
    [string]$Service = "catalogo-cloud-api",
    [string]$Bucket  = ""
)
$ErrorActionPreference = "Stop"
if (-not $Bucket) { $Bucket = "$ProjectId-catalogo-imagenes" }

Write-Host ">> Proyecto: $ProjectId | Region: $Region | Bucket: $Bucket" -ForegroundColor Cyan
gcloud config set project $ProjectId

Write-Host ">> Habilitando APIs..." -ForegroundColor Cyan
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com storage.googleapis.com iamcredentials.googleapis.com

# Cuenta de servicio por defecto de Cloud Run (Compute Engine default SA)
$ProjectNumber = gcloud projects describe $ProjectId --format="value(projectNumber)"
$SA = "$ProjectNumber-compute@developer.gserviceaccount.com"

Write-Host ">> Creando bucket (si no existe)..." -ForegroundColor Cyan
gcloud storage buckets describe "gs://$Bucket" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    gcloud storage buckets create "gs://$Bucket" --location=$Region --uniform-bucket-level-access
}

Write-Host ">> Permisos: lectura publica + escritura para la API + firma de URLs..." -ForegroundColor Cyan
gcloud storage buckets add-iam-policy-binding "gs://$Bucket" --member=allUsers --role=roles/storage.objectViewer
gcloud storage buckets add-iam-policy-binding "gs://$Bucket" --member="serviceAccount:$SA" --role=roles/storage.objectAdmin
gcloud iam service-accounts add-iam-policy-binding $SA --member="serviceAccount:$SA" --role=roles/iam.serviceAccountTokenCreator

# CORS del bucket (necesario para subir con Signed URL desde el navegador)
$cors = '[{"origin":["*"],"method":["GET","PUT","HEAD"],"responseHeader":["Content-Type"],"maxAgeSeconds":3600}]'
$corsFile = Join-Path $env:TEMP "gcs-cors.json"
Set-Content -Path $corsFile -Value $cors -Encoding ascii
gcloud storage buckets update "gs://$Bucket" --cors-file=$corsFile

Write-Host ">> Desplegando en Cloud Run..." -ForegroundColor Cyan
gcloud run deploy $Service `
  --source . `
  --region $Region `
  --allow-unauthenticated `
  --service-account $SA `
  --memory 512Mi `
  --cpu 1 `
  --min-instances 0 `
  --max-instances 3 `
  --set-env-vars "GCS_BUCKET_NAME=$Bucket,CORS_ORIGINS=*"

$url = gcloud run services describe $Service --region $Region --format="value(status.url)"
Write-Host ""
Write-Host "LISTO -> $url/docs" -ForegroundColor Green
