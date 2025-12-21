#!/bin/bash
# Compute Engine setup script for Claude Code automation
# This script sets up a GCE instance to run Claude Code CLI for strategy analysis

set -e

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-your-project-id}"
ZONE="${GCE_ZONE:-us-central1-a}"
INSTANCE_NAME="${GCE_INSTANCE:-tqqq-claude-runner}"
MACHINE_TYPE="e2-medium"
SERVICE_ACCOUNT="tqqq-claude-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=== TQQQ Trading System - GCE Claude Runner Setup ==="
echo "Project: ${PROJECT_ID}"
echo "Zone: ${ZONE}"
echo "Instance: ${INSTANCE_NAME}"
echo ""

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable compute.googleapis.com --project="${PROJECT_ID}"
gcloud services enable secretmanager.googleapis.com --project="${PROJECT_ID}"

# Create service account
echo "Creating service account..."
gcloud iam service-accounts create tqqq-claude-sa \
    --display-name="TQQQ Claude Runner Service Account" \
    --project="${PROJECT_ID}" 2>/dev/null || echo "Service account already exists"

# Grant necessary roles
echo "Granting permissions..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/datastore.user"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/logging.logWriter"

# Create startup script
cat > /tmp/startup-script.sh << 'STARTUP_EOF'
#!/bin/bash
set -e

# Install dependencies
apt-get update
apt-get install -y python3 python3-pip python3-venv git curl

# Install Node.js (for Claude Code)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Create app user
useradd -m -s /bin/bash tqqq || true

# Clone repository
su - tqqq << 'USER_EOF'
cd /home/tqqq

# Clone or pull repository
if [ -d "tqqq-trading-system" ]; then
    cd tqqq-trading-system
    git pull
else
    git clone https://github.com/YOUR_REPO/tqqq-trading-system.git
    cd tqqq-trading-system
fi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Create .env from Secret Manager
gcloud secrets versions access latest --secret="tqqq-env-file" > .env 2>/dev/null || echo "No env secret found"

USER_EOF

# Setup systemd service for scheduler
cat > /etc/systemd/system/tqqq-scheduler.service << 'SERVICE_EOF'
[Unit]
Description=TQQQ Trading Scheduler
After=network.target

[Service]
Type=simple
User=tqqq
WorkingDirectory=/home/tqqq/tqqq-trading-system
Environment=PATH=/home/tqqq/tqqq-trading-system/venv/bin:/usr/local/bin:/usr/bin
ExecStart=/home/tqqq/tqqq-trading-system/venv/bin/python -m automation.scheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable tqqq-scheduler
systemctl start tqqq-scheduler

echo "Startup complete!"
STARTUP_EOF

# Check if instance exists
if gcloud compute instances describe "${INSTANCE_NAME}" --zone="${ZONE}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "Instance ${INSTANCE_NAME} already exists. Updating..."
    gcloud compute instances add-metadata "${INSTANCE_NAME}" \
        --zone="${ZONE}" \
        --metadata-from-file=startup-script=/tmp/startup-script.sh \
        --project="${PROJECT_ID}"
else
    echo "Creating instance ${INSTANCE_NAME}..."
    gcloud compute instances create "${INSTANCE_NAME}" \
        --zone="${ZONE}" \
        --machine-type="${MACHINE_TYPE}" \
        --service-account="${SERVICE_ACCOUNT}" \
        --scopes="cloud-platform" \
        --image-family="debian-12" \
        --image-project="debian-cloud" \
        --boot-disk-size="20GB" \
        --boot-disk-type="pd-standard" \
        --metadata-from-file=startup-script=/tmp/startup-script.sh \
        --tags="tqqq-runner" \
        --project="${PROJECT_ID}"
fi

rm /tmp/startup-script.sh

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Instance created: ${INSTANCE_NAME}"
echo ""
echo "To SSH into the instance:"
echo "  gcloud compute ssh ${INSTANCE_NAME} --zone=${ZONE}"
echo ""
echo "To view scheduler logs:"
echo "  gcloud compute ssh ${INSTANCE_NAME} --zone=${ZONE} -- journalctl -u tqqq-scheduler -f"
echo ""
echo "IMPORTANT: Configure Claude API key on the instance:"
echo "  1. SSH into the instance"
echo "  2. Run: claude config set api_key YOUR_ANTHROPIC_API_KEY"
echo ""
echo "Or store it in Secret Manager:"
echo "  gcloud secrets create claude-api-key --data-file=- <<< 'YOUR_API_KEY'"
