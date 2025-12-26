#!/bin/bash
# Create GCP Service Account for GitHub Actions CD
# Run this once to set up the service account and get the key

set -e

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-short-term-trade}"
SA_NAME="github-actions-deploy"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="gcp-sa-key.json"

echo "=== GitHub Actions CD Setup ==="
echo "Project: ${PROJECT_ID}"
echo ""

# Create service account
echo "Creating service account..."
gcloud iam service-accounts create ${SA_NAME} \
    --display-name="GitHub Actions Deploy" \
    --project="${PROJECT_ID}" 2>/dev/null || echo "Service account already exists"

# Grant required roles
echo "Granting permissions..."
ROLES=(
    "roles/artifactregistry.writer"      # Push/tag images
    "roles/cloudbuild.builds.builder"    # Cloud Build
    "roles/storage.admin"                # Cloud Build logs
    "roles/compute.instanceAdmin.v1"     # SSH to GCE
    "roles/iap.tunnelResourceAccessor"   # IAP tunnel for SSH
    "roles/iam.serviceAccountUser"       # Act as service account
)

for role in "${ROLES[@]}"; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="${role}" \
        --quiet
done

# Create key file
echo "Creating key file..."
gcloud iam service-accounts keys create ${KEY_FILE} \
    --iam-account="${SA_EMAIL}" \
    --project="${PROJECT_ID}"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Key file created: ${KEY_FILE}"
echo ""
echo "Next steps:"
echo ""
echo "1. Copy the key content:"
echo "   cat ${KEY_FILE}"
echo ""
echo "2. Go to GitHub repo → Settings → Secrets and variables → Actions"
echo ""
echo "3. Create new secret:"
echo "   Name: GCP_SA_KEY"
echo "   Value: (paste the entire JSON content)"
echo ""
echo "4. Delete the local key file (security):"
echo "   rm ${KEY_FILE}"
echo ""
echo "5. Push to main branch to trigger deployment!"
