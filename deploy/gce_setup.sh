#!/bin/bash
# Compute Engine setup script for Claude Code automation
# This script sets up a GCE instance to run Claude Code CLI for strategy analysis

set -e

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-your-project-id}"
ZONE="${GCE_ZONE:-us-central1-a}"
INSTANCE_NAME="${GCE_INSTANCE:-tqqq-trading-bot}"
MACHINE_TYPE="e2-small"
USE_SPOT="true"
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

# Get GitHub token from Secret Manager
GITHUB_TOKEN=$(gcloud secrets versions access latest --secret="github-token" 2>/dev/null || echo "")

# Clone or pull repository
if [ -d "tqqq-trading-system" ]; then
    cd tqqq-trading-system
    git pull
else
    if [ -n "$GITHUB_TOKEN" ]; then
        git clone https://${GITHUB_TOKEN}@github.com/DoKyungHan0114/My-trading-bot.git tqqq-trading-system
    else
        git clone https://github.com/DoKyungHan0114/My-trading-bot.git tqqq-trading-system
    fi
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

# Setup systemd service for trading bot (main service)
cat > /etc/systemd/system/tqqq-trading-bot.service << 'SERVICE_EOF'
[Unit]
Description=TQQQ Live Trading Bot
After=network.target

[Service]
Type=simple
User=tqqq
WorkingDirectory=/home/tqqq/tqqq-trading-system
Environment=PATH=/home/tqqq/tqqq-trading-system/venv/bin:/usr/local/bin:/usr/bin
ExecStart=/home/tqqq/tqqq-trading-system/venv/bin/python main.py --mode paper
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Setup systemd service for scheduler (optional)
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
systemctl enable tqqq-trading-bot
systemctl start tqqq-trading-bot

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

    # Build create command
    CREATE_CMD="gcloud compute instances create ${INSTANCE_NAME} \
        --zone=${ZONE} \
        --machine-type=${MACHINE_TYPE} \
        --service-account=${SERVICE_ACCOUNT} \
        --scopes=cloud-platform \
        --image-family=debian-12 \
        --image-project=debian-cloud \
        --boot-disk-size=20GB \
        --boot-disk-type=pd-standard \
        --metadata-from-file=startup-script=/tmp/startup-script.sh \
        --tags=tqqq-runner \
        --project=${PROJECT_ID}"

    # Add Spot VM options if enabled (70% cheaper)
    if [ "${USE_SPOT}" = "true" ]; then
        echo "Using Spot VM (preemptible) for cost savings..."
        CREATE_CMD="${CREATE_CMD} \
            --provisioning-model=SPOT \
            --instance-termination-action=STOP \
            --maintenance-policy=TERMINATE"
    fi

    eval "${CREATE_CMD}"
fi

rm /tmp/startup-script.sh

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Instance: ${INSTANCE_NAME}"
echo "Type: ${MACHINE_TYPE} $([ "${USE_SPOT}" = "true" ] && echo "(Spot VM - 70% cheaper)")"
echo "Estimated cost: ~\$6-8/month"
echo ""
echo "Commands:"
echo "  # SSH into instance"
echo "  gcloud compute ssh ${INSTANCE_NAME} --zone=${ZONE}"
echo ""
echo "  # View trading bot logs"
echo "  gcloud compute ssh ${INSTANCE_NAME} --zone=${ZONE} -- journalctl -u tqqq-trading-bot -f"
echo ""
echo "  # Check bot status"
echo "  gcloud compute ssh ${INSTANCE_NAME} --zone=${ZONE} -- systemctl status tqqq-trading-bot"
echo ""
echo "  # Switch to live trading (CAUTION!)"
echo "  # Edit /etc/systemd/system/tqqq-trading-bot.service and change --mode paper to --mode live"
echo ""
echo "IMPORTANT - Before starting:"
echo "  1. Create .env secret in Secret Manager:"
echo "     gcloud secrets create tqqq-env-file --data-file=.env"
echo ""
echo "  2. For Spot VM auto-restart, set up monitoring:"
echo "     ./deploy/spot_vm_monitor.sh  # Run via cron or Cloud Scheduler"
echo ""
if [ "${USE_SPOT}" = "true" ]; then
echo "NOTE: Spot VM may be preempted by GCP. The bot will auto-restart when VM restarts."
echo "      Consider running spot_vm_monitor.sh every 5 min via Cloud Scheduler for auto-restart."
fi
