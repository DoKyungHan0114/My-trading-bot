#!/bin/bash
# Compute Engine setup script for TQQQ Trading Bot (Docker-based)
# Pulls pre-built images from Artifact Registry

set -e

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-your-project-id}"
ZONE="${GCE_ZONE:-us-central1-a}"
REGION="${GCE_REGION:-us-central1}"
INSTANCE_NAME="${GCE_INSTANCE:-tqqq-trading-bot}"
MACHINE_TYPE="e2-small"
USE_SPOT="true"
SERVICE_ACCOUNT="tqqq-claude-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Artifact Registry
AR_REPO="tqqq"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/bot:${IMAGE_TAG}"

echo "=== TQQQ Trading System - GCE Docker Deployment ==="
echo "Project: ${PROJECT_ID}"
echo "Zone: ${ZONE}"
echo "Instance: ${INSTANCE_NAME}"
echo "Image: ${IMAGE_URL}"
echo ""

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable compute.googleapis.com --project="${PROJECT_ID}"
gcloud services enable secretmanager.googleapis.com --project="${PROJECT_ID}"
gcloud services enable artifactregistry.googleapis.com --project="${PROJECT_ID}"

# Create Artifact Registry repository (if not exists)
echo "Setting up Artifact Registry..."
gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="TQQQ Trading Bot images" \
    --project="${PROJECT_ID}" 2>/dev/null || echo "Repository already exists"

# Create service account
echo "Creating service account..."
gcloud iam service-accounts create tqqq-claude-sa \
    --display-name="TQQQ Trading Bot Service Account" \
    --project="${PROJECT_ID}" 2>/dev/null || echo "Service account already exists"

# Grant necessary roles
echo "Granting permissions..."
for role in "roles/datastore.user" "roles/secretmanager.secretAccessor" "roles/logging.logWriter" "roles/artifactregistry.reader"; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${SERVICE_ACCOUNT}" \
        --role="${role}" \
        --quiet
done

# Create startup script
cat > /tmp/startup-script.sh << STARTUP_EOF
#!/bin/bash
set -e

echo "=== Starting TQQQ Trading Bot Setup ==="

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    apt-get update
    apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \$(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io
    systemctl enable docker
    systemctl start docker
fi

# Configure Docker to use Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Pull latest image
echo "Pulling image: ${IMAGE_URL}"
docker pull ${IMAGE_URL}

# Get env file from Secret Manager
echo "Loading environment from Secret Manager..."
mkdir -p /opt/tqqq
gcloud secrets versions access latest --secret="tqqq-env-file" > /opt/tqqq/.env 2>/dev/null || touch /opt/tqqq/.env

# Create systemd service for trading bot
cat > /etc/systemd/system/tqqq-trading-bot.service << SERVICE_EOF
[Unit]
Description=TQQQ Trading Bot (Docker)
After=docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=30
ExecStartPre=-/usr/bin/docker stop tqqq-bot
ExecStartPre=-/usr/bin/docker rm tqqq-bot
ExecStartPre=/usr/bin/docker pull ${IMAGE_URL}
ExecStart=/usr/bin/docker run --rm --name tqqq-bot \\
    --env-file /opt/tqqq/.env \\
    -v /opt/tqqq/logs:/app/logs \\
    ${IMAGE_URL}
ExecStop=/usr/bin/docker stop tqqq-bot

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Create systemd service for Discord bot
cat > /etc/systemd/system/tqqq-discord-bot.service << 'SERVICE_EOF'
[Unit]
Description=TQQQ Discord Bot (Docker)
After=docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=10
ExecStartPre=-/usr/bin/docker stop tqqq-discord
ExecStartPre=-/usr/bin/docker rm tqqq-discord
ExecStart=/usr/bin/docker run --rm --name tqqq-discord \
    --env-file /opt/tqqq/.env \
    ${IMAGE_URL} \
    python discord_bot.py
ExecStop=/usr/bin/docker stop tqqq-discord

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Create update script
cat > /usr/local/bin/tqqq-update << 'UPDATE_EOF'
#!/bin/bash
# Update TQQQ Trading Bot to latest image
set -e
echo "Pulling latest image..."
docker pull ${IMAGE_URL}
echo "Restarting services..."
systemctl restart tqqq-trading-bot
systemctl restart tqqq-discord-bot
echo "Update complete!"
docker images | grep tqqq
UPDATE_EOF
chmod +x /usr/local/bin/tqqq-update

# Setup daily/weekly report timers
cat > /etc/systemd/system/tqqq-daily-report.service << 'SERVICE_EOF'
[Unit]
Description=TQQQ Daily Trading Report
After=docker.service

[Service]
Type=oneshot
ExecStart=/usr/bin/docker run --rm \
    --env-file /opt/tqqq/.env \
    ${IMAGE_URL} \
    python automation/daily_report.py

[Install]
WantedBy=multi-user.target
SERVICE_EOF

cat > /etc/systemd/system/tqqq-daily-report.timer << 'TIMER_EOF'
[Unit]
Description=Run TQQQ Daily Report after US market close

[Timer]
OnCalendar=Mon..Fri 16:30 America/New_York
Persistent=true

[Install]
WantedBy=timers.target
TIMER_EOF

cat > /etc/systemd/system/tqqq-weekly-report.service << 'SERVICE_EOF'
[Unit]
Description=TQQQ Weekly Trading Report
After=docker.service

[Service]
Type=oneshot
ExecStart=/usr/bin/docker run --rm \
    --env-file /opt/tqqq/.env \
    ${IMAGE_URL} \
    python automation/weekly_report.py

[Install]
WantedBy=multi-user.target
SERVICE_EOF

cat > /etc/systemd/system/tqqq-weekly-report.timer << 'TIMER_EOF'
[Unit]
Description=Run TQQQ Weekly Report every Friday

[Timer]
OnCalendar=Fri 17:00 America/New_York
Persistent=true

[Install]
WantedBy=timers.target
TIMER_EOF

# Enable and start services
systemctl daemon-reload
systemctl enable tqqq-trading-bot tqqq-discord-bot
systemctl start tqqq-trading-bot tqqq-discord-bot
systemctl enable tqqq-daily-report.timer tqqq-weekly-report.timer
systemctl start tqqq-daily-report.timer tqqq-weekly-report.timer

echo "=== Startup complete! ==="
docker ps
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

    if [ "${USE_SPOT}" = "true" ]; then
        echo "Using Spot VM for cost savings..."
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
echo "Type: ${MACHINE_TYPE} $([ "${USE_SPOT}" = "true" ] && echo "(Spot VM)")"
echo "Image: ${IMAGE_URL}"
echo ""
echo "=== Commands ==="
echo ""
echo "# SSH into instance"
echo "gcloud compute ssh ${INSTANCE_NAME} --zone=${ZONE}"
echo ""
echo "# View trading bot logs"
echo "gcloud compute ssh ${INSTANCE_NAME} --zone=${ZONE} -- docker logs -f tqqq-bot"
echo ""
echo "# Update to latest image"
echo "gcloud compute ssh ${INSTANCE_NAME} --zone=${ZONE} -- sudo tqqq-update"
echo ""
echo "# Switch to live trading"
echo "# Edit /etc/systemd/system/tqqq-trading-bot.service: change --mode paper to --mode live"
echo ""
echo "=== Before First Deploy ==="
echo ""
echo "1. Build and push image:"
echo "   ./deploy/build.sh"
echo ""
echo "2. Create env secret:"
echo "   gcloud secrets create tqqq-env-file --data-file=.env"
echo ""
