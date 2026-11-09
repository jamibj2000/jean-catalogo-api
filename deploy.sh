#!/usr/bin/env bash
# Deploy de catalogo-cloud-api a Cloud Run (Linux/macOS/Cloud Shell)
# Uso: ./deploy.sh mi-proyecto-gcp [region]
set -euo pipefail

PROJECT_ID="${1:?Uso: ./deploy.sh PROJECT_ID [REGION]}"
REGION="${2:-us-central1}"
SERVICE="catalogo-cloud-api"
BUCKET="${BUCKET:-${PROJECT_ID}-catalogo-imagenes}"

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com storage.googleapis.com iamcredentials.googleapis.com

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1 || \
  gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access

gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member=allUsers --role=roles/storage.objectViewer
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$SA" --role=roles/storage.objectAdmin
gcloud iam service-accounts add-iam-policy-binding "$SA" --member="serviceAccount:$SA" --role=roles/iam.serviceAccountTokenCreator

echo '[{"origin":["*"],"method":["GET","PUT","HEAD"],"responseHeader":["Content-Type"],"maxAgeSeconds":3600}]' > /tmp/gcs-cors.json
gcloud storage buckets update "gs://$BUCKET" --cors-file=/tmp/gcs-cors.json

gcloud run deploy "$SERVICE" --source . --region "$REGION" --allow-unauthenticated \
  --service-account "$SA" --memory 512Mi --cpu 1 --min-instances 0 --max-instances 3 \
  --set-env-vars "GCS_BUCKET_NAME=$BUCKET,CORS_ORIGINS=*"

echo "LISTO -> $(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')/docs"
