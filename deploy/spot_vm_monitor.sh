#!/bin/bash
# Spot VM Auto-Restart Script
# Run this via Cloud Scheduler or cron to ensure the trading bot stays running
# Spot VMs can be preempted by GCP, this script restarts them automatically

set -e

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-your-project-id}"
ZONE="${GCE_ZONE:-us-central1-a}"
INSTANCE_NAME="${GCE_INSTANCE:-tqqq-trading-bot}"

# Get instance status
STATUS=$(gcloud compute instances describe "${INSTANCE_NAME}" \
    --zone="${ZONE}" \
    --project="${PROJECT_ID}" \
    --format="get(status)" 2>/dev/null || echo "NOT_FOUND")

echo "$(date): Instance ${INSTANCE_NAME} status: ${STATUS}"

case "${STATUS}" in
    "RUNNING")
        echo "Instance is running. No action needed."
        ;;
    "TERMINATED"|"STOPPED")
        echo "Instance is stopped. Starting..."
        gcloud compute instances start "${INSTANCE_NAME}" \
            --zone="${ZONE}" \
            --project="${PROJECT_ID}"
        echo "Instance started successfully."
        ;;
    "STAGING"|"PROVISIONING"|"STOPPING"|"SUSPENDING")
        echo "Instance is in transitional state. Waiting..."
        ;;
    "NOT_FOUND")
        echo "ERROR: Instance not found!"
        exit 1
        ;;
    *)
        echo "Unknown status: ${STATUS}"
        ;;
esac
