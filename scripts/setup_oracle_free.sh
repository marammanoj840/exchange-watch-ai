#!/bin/bash
# ExchangeWatch AI — Oracle Cloud Always Free Automated Setup Script
# Supports: Ubuntu 22.04/24.04 and Oracle Linux 8/9 (x86_64 and aarch64 Ampere A1)
set -e

echo "=================================================="
echo "🚀 Setting up ExchangeWatch AI on Oracle Cloud Always Free"
echo "=================================================="

# Detect application root directory and running user
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CURRENT_USER="$(whoami)"
echo "Target directory : ${APP_DIR}"
echo "Execution user   : ${CURRENT_USER}"

# 1. Update system packages & install OS dependencies
echo "Installing OS packages..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update && sudo apt-get upgrade -y
    sudo apt-get install -y python3 python3-pip python3-venv tesseract-ocr libtesseract-dev git curl
elif command -v dnf &> /dev/null; then
    sudo dnf update -y
    sudo dnf install -y python3 python3-pip git curl tesseract
elif command -v yum &> /dev/null; then
    sudo yum update -y
    sudo yum install -y python3 python3-pip git curl tesseract
else
    echo "Warning: Unrecognized package manager. Please ensure python3, pip, and curl are installed."
fi

# 2. Create virtual environment
echo "Setting up Python virtual environment..."
cd "${APP_DIR}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# 3. Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Create required runtime directories
echo "Creating runtime directories..."
mkdir -p data output logs

# 5. Install & Configure Ollama for Local AI Inference
if ! command -v ollama &> /dev/null; then
    echo "Installing Ollama for local AI model execution..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

echo "Ensuring Ollama service is active..."
sudo systemctl daemon-reload
sudo systemctl enable --now ollama

# Wait briefly for Ollama daemon to initialize
for i in {1..10}; do
    if curl -s http://localhost:11434/api/tags > /dev/null; then
        echo "Ollama service is up and responsive."
        break
    fi
    echo "Waiting for Ollama service to start (attempt $i/10)..."
    sleep 2
done

echo "Pulling llama3.2:1b model (if not already cached)..."
ollama pull llama3.2:1b

# 6. Configure Systemd 24/7 Daemon Service
echo "Configuring Systemd service..."
SERVICE_DEST="/etc/systemd/system/exchangewatch.service"

sudo tee "${SERVICE_DEST}" > /dev/null <<EOF
[Unit]
Description=ExchangeWatch AI — Real-Time NSE/BSE Intelligence Daemon
After=network.target network-online.target ollama.service
Wants=network-online.target ollama.service

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/venv/bin/python -m app.main
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-${APP_DIR}/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable exchangewatch
sudo systemctl restart exchangewatch

echo "=================================================="
echo "✅ ExchangeWatch AI setup complete and running as a 24/7 service!"
echo "Check service status: sudo systemctl status exchangewatch"
echo "View live logs      : sudo journalctl -u exchangewatch -f"
echo "=================================================="
