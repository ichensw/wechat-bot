#!/bin/bash
# WeChat Bot - systemd service installation script
# Usage: sudo bash deploy/install_service.sh
# Or:   sudo bash deploy/install_service.sh /path/to/custom/config.yaml

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_NAME="wechat-bot"
PYTHON_BIN="$(which python3 2>/dev/null || echo /usr/bin/python3)"
CONFIG_FILE="${1:-$BOT_DIR/config.yaml}"

echo "========================================="
echo " WeChatBot v2.0 - Service Installer"
echo "========================================="
echo ""
echo "Bot directory:  $BOT_DIR"
echo "Python binary:  $PYTHON_BIN"
echo "Service name:   $SERVICE_NAME"
echo "Config file:    $CONFIG_FILE"
echo ""

# Verify bot directory
if [ ! -f "$BOT_DIR/main.py" ]; then
    echo "❌ main.py not found in $BOT_DIR"
    exit 1
fi

# Verify config file
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Config file not found: $CONFIG_FILE"
    echo "   Run 'python3 main.py --init -c $CONFIG_FILE' first"
    exit 1
fi

# Create service user if not exists
if ! id "$SERVICE_NAME" &>/dev/null; then
    echo "Creating service user: $SERVICE_NAME"
    useradd -r -s /bin/false "$SERVICE_NAME" 2>/dev/null || true
fi

# Create data directory
mkdir -p "$BOT_DIR/data"
chown -R "$SERVICE_NAME":"$SERVICE_NAME" "$BOT_DIR/data" 2>/dev/null || true

# Install dependencies if needed
if [ ! -d "$BOT_DIR/.venv" ]; then
    echo "Installing Python dependencies..."
    python3 -m venv "$BOT_DIR/.venv"
    "$BOT_DIR/.venv/bin/pip" install --quiet -r "$BOT_DIR/requirements.txt" 2>/dev/null || \
    "$BOT_DIR/.venv/bin/pip" install --quiet wcferry pyyaml flask apscheduler requests
    PYTHON_BIN="$BOT_DIR/.venv/bin/python"
fi

# Create systemd service file
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=WeChatBot - WeChatFerry Monitoring Bot v2.0
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_NAME
Group=$SERVICE_NAME
WorkingDirectory=$BOT_DIR
ExecStart=$PYTHON_BIN $BOT_DIR/main.py -c $CONFIG_FILE
Restart=on-failure
RestartSec=10
StartLimitBurst=5
StartLimitIntervalSec=60

StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$BOT_DIR/data
PrivateTmp=true

# Environment
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONIOENCODING=utf-8

[Install]
WantedBy=multi-user.target
EOF

echo "Service file created: /etc/systemd/system/${SERVICE_NAME}.service"

# Reload and enable
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" 2>/dev/null || true

echo ""
echo "✅ Installation complete!"
echo ""
echo "Commands:"
echo "  sudo systemctl start $SERVICE_NAME      # Start"
echo "  sudo systemctl stop $SERVICE_NAME       # Stop"
echo "  sudo systemctl restart $SERVICE_NAME    # Restart"
echo "  sudo systemctl status $SERVICE_NAME    # Status"
echo "  sudo journalctl -u $SERVICE_NAME -f    # Logs"
echo ""
echo "⚠️  Before starting:"
echo "  1. Edit $CONFIG_FILE (set webhook.token)"
echo "  2. Ensure WeChat is logged in (or WCF HTTP server is reachable)"
echo "  3. Run 'python3 main.py --check' to verify connectivity"
