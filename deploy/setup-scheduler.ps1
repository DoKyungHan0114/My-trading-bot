# Setup Cloud Scheduler for Trading Bot (Windows PowerShell)
# Run this after deploying the API to Cloud Run

$ErrorActionPreference = "Stop"

# Configuration
$PROJECT_ID = gcloud config get-value project
$REGION = "us-central1"
$SERVICE_NAME = "tqqq-trading-api"
$SCHEDULER_NAME = "tqqq-trading-tick"

# Get the Cloud Run service URL
$SERVICE_URL = gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)'

if (-not $SERVICE_URL) {
    Write-Error "Could not get Cloud Run service URL"
    exit 1
}

Write-Host "Cloud Run Service URL: $SERVICE_URL"

# Create service account for Cloud Scheduler (if not exists)
$SA_NAME = "scheduler-invoker"
$SA_EMAIL = "${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

$saExists = gcloud iam service-accounts describe $SA_EMAIL 2>$null
if (-not $saExists) {
    Write-Host "Creating service account: $SA_EMAIL"
    gcloud iam service-accounts create $SA_NAME --display-name="Cloud Scheduler Invoker"
}

# Grant Cloud Run invoker role
Write-Host "Granting Cloud Run invoker role..."
gcloud run services add-iam-policy-binding $SERVICE_NAME `
    --region=$REGION `
    --member="serviceAccount:${SA_EMAIL}" `
    --role="roles/run.invoker"

# Delete existing scheduler job if exists
$jobExists = gcloud scheduler jobs describe $SCHEDULER_NAME --location=$REGION 2>$null
if ($jobExists) {
    Write-Host "Deleting existing scheduler job..."
    gcloud scheduler jobs delete $SCHEDULER_NAME --location=$REGION --quiet
}

# Create Cloud Scheduler job
# Runs every minute during US market hours (9:30 AM - 4:00 PM ET)
Write-Host "Creating Cloud Scheduler job..."
gcloud scheduler jobs create http $SCHEDULER_NAME `
    --location=$REGION `
    --schedule="*/1 9-16 * * 1-5" `
    --time-zone="America/New_York" `
    --uri="${SERVICE_URL}/api/trading/tick" `
    --http-method=POST `
    --oidc-service-account-email=$SA_EMAIL `
    --oidc-token-audience=$SERVICE_URL `
    --attempt-deadline="60s" `
    --description="Trigger trading tick every minute during market hours"

Write-Host ""
Write-Host "============================================"
Write-Host "Cloud Scheduler setup complete!"
Write-Host "============================================"
Write-Host ""
Write-Host "Scheduler: $SCHEDULER_NAME"
Write-Host "Schedule: Every minute, Mon-Fri 9:30 AM - 4:00 PM ET"
Write-Host "Target: ${SERVICE_URL}/api/trading/tick"
Write-Host ""
Write-Host "To test manually:"
Write-Host "  gcloud scheduler jobs run $SCHEDULER_NAME --location=$REGION"
Write-Host ""
Write-Host "To view logs:"
Write-Host "  gcloud run services logs read $SERVICE_NAME --region=$REGION"
