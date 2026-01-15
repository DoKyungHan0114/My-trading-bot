#!/bin/bash
# Setup Cloud Scheduler for Trading Bot
# Run this after deploying the API to Cloud Run

set -e

# Configuration
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
SERVICE_NAME="tqqq-trading-api"
SCHEDULER_NAME="tqqq-trading-tick"

# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')

if [ -z "$SERVICE_URL" ]; then
    echo "Error: Could not get Cloud Run service URL"
    exit 1
fi

echo "Cloud Run Service URL: $SERVICE_URL"

# Create service account for Cloud Scheduler (if not exists)
SA_NAME="scheduler-invoker"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe $SA_EMAIL &>/dev/null; then
    echo "Creating service account: $SA_EMAIL"
    gcloud iam service-accounts create $SA_NAME \
        --display-name="Cloud Scheduler Invoker"
fi

# Grant Cloud Run invoker role
echo "Granting Cloud Run invoker role..."
gcloud run services add-iam-policy-binding $SERVICE_NAME \
    --region=$REGION \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/run.invoker"

# Delete existing scheduler job if exists
if gcloud scheduler jobs describe $SCHEDULER_NAME --location=$REGION &>/dev/null; then
    echo "Deleting existing scheduler job..."
    gcloud scheduler jobs delete $SCHEDULER_NAME --location=$REGION --quiet
fi

# Create Cloud Scheduler job
# Runs every minute during US market hours (9:30 AM - 4:00 PM ET)
# Cron: minute hour day month weekday
# ET is UTC-5 (or UTC-4 during DST)
# 9:30 AM ET = 14:30 UTC (winter) or 13:30 UTC (summer)
# 4:00 PM ET = 21:00 UTC (winter) or 20:00 UTC (summer)
# Using broader range to cover both: 13:30 - 21:00 UTC

echo "Creating Cloud Scheduler job..."
gcloud scheduler jobs create http $SCHEDULER_NAME \
    --location=$REGION \
    --schedule="*/1 13-21 * * 1-5" \
    --time-zone="America/New_York" \
    --uri="${SERVICE_URL}/api/trading/tick" \
    --http-method=POST \
    --oidc-service-account-email=$SA_EMAIL \
    --oidc-token-audience=$SERVICE_URL \
    --attempt-deadline="60s" \
    --description="Trigger trading tick every minute during market hours"

# ============================================
# Daily Report Scheduler
# ============================================
DAILY_REPORT_SCHEDULER="tqqq-daily-report"

# Delete existing daily report scheduler if exists
if gcloud scheduler jobs describe $DAILY_REPORT_SCHEDULER --location=$REGION &>/dev/null; then
    echo "Deleting existing daily report scheduler..."
    gcloud scheduler jobs delete $DAILY_REPORT_SCHEDULER --location=$REGION --quiet
fi

# Create daily report scheduler - runs at 4:30 PM ET on weekdays
echo "Creating daily report scheduler..."
gcloud scheduler jobs create http $DAILY_REPORT_SCHEDULER \
    --location=$REGION \
    --schedule="30 16 * * 1-5" \
    --time-zone="America/New_York" \
    --uri="${SERVICE_URL}/api/reports/daily" \
    --http-method=POST \
    --oidc-service-account-email=$SA_EMAIL \
    --oidc-token-audience=$SERVICE_URL \
    --attempt-deadline="120s" \
    --description="Send daily trading report after US market close"

echo ""
echo "============================================"
echo "Cloud Scheduler setup complete!"
echo "============================================"
echo ""
echo "Trading Tick Scheduler: $SCHEDULER_NAME"
echo "  Schedule: Every minute, Mon-Fri 9:30 AM - 4:00 PM ET"
echo "  Target: ${SERVICE_URL}/api/trading/tick"
echo ""
echo "Daily Report Scheduler: $DAILY_REPORT_SCHEDULER"
echo "  Schedule: Mon-Fri 4:30 PM ET"
echo "  Target: ${SERVICE_URL}/api/reports/daily"
echo ""
echo "To test manually:"
echo "  gcloud scheduler jobs run $SCHEDULER_NAME --location=$REGION"
echo "  gcloud scheduler jobs run $DAILY_REPORT_SCHEDULER --location=$REGION"
echo ""
echo "To view logs:"
echo "  gcloud run services logs read $SERVICE_NAME --region=$REGION"
