#!/bin/bash
# Cloud Scheduler setup script for TQQQ Trading System
# Sets up scheduled jobs for intraday analysis

set -e

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-your-project-id}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE_URL="${CLOUD_RUN_URL:-https://tqqq-trading-api-xxxxx-uc.a.run.app}"
SERVICE_ACCOUNT="tqqq-scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=== TQQQ Trading System - Cloud Scheduler Setup ==="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service URL: ${SERVICE_URL}"
echo ""

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable cloudscheduler.googleapis.com --project="${PROJECT_ID}"
gcloud services enable run.googleapis.com --project="${PROJECT_ID}"

# Create service account for scheduler (if not exists)
echo "Creating service account..."
gcloud iam service-accounts create tqqq-scheduler-sa \
    --display-name="TQQQ Scheduler Service Account" \
    --project="${PROJECT_ID}" 2>/dev/null || echo "Service account already exists"

# Grant Cloud Run invoker role
echo "Granting permissions..."
gcloud run services add-iam-policy-binding tqqq-trading-api \
    --region="${REGION}" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/run.invoker" \
    --project="${PROJECT_ID}"

# Delete existing jobs (for updates)
echo "Cleaning up existing jobs..."
gcloud scheduler jobs delete tqqq-analysis-morning \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || true

gcloud scheduler jobs delete tqqq-analysis-afternoon \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || true

# Create morning analysis job (11:00 AM ET = 16:00 UTC in winter, 15:00 UTC in summer)
# Using 15:00 UTC for simplicity (during DST)
echo "Creating morning analysis job (11:00 AM ET)..."
gcloud scheduler jobs create http tqqq-analysis-morning \
    --location="${REGION}" \
    --schedule="0 15 * * 1-5" \
    --time-zone="America/New_York" \
    --uri="${SERVICE_URL}/api/analyze" \
    --http-method=POST \
    --oidc-service-account-email="${SERVICE_ACCOUNT}" \
    --oidc-token-audience="${SERVICE_URL}" \
    --attempt-deadline="540s" \
    --description="Morning intraday analysis at 11:00 AM ET" \
    --project="${PROJECT_ID}"

# Create afternoon analysis job (2:30 PM ET)
echo "Creating afternoon analysis job (2:30 PM ET)..."
gcloud scheduler jobs create http tqqq-analysis-afternoon \
    --location="${REGION}" \
    --schedule="30 14 * * 1-5" \
    --time-zone="America/New_York" \
    --uri="${SERVICE_URL}/api/analyze" \
    --http-method=POST \
    --oidc-service-account-email="${SERVICE_ACCOUNT}" \
    --oidc-token-audience="${SERVICE_URL}" \
    --attempt-deadline="540s" \
    --description="Afternoon intraday analysis at 2:30 PM ET" \
    --project="${PROJECT_ID}"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Scheduled jobs created:"
gcloud scheduler jobs list --location="${REGION}" --project="${PROJECT_ID}"
echo ""
echo "To test a job manually:"
echo "  gcloud scheduler jobs run tqqq-analysis-morning --location=${REGION}"
echo ""
echo "To view job logs:"
echo "  gcloud logging read 'resource.type=cloud_scheduler_job' --project=${PROJECT_ID} --limit=10"
