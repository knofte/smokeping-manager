#!/bin/bash
set -e

# SmokePing Manager Agent installer
# Installs the agent on a slave server to poll the master for config.
#
# Usage: sudo bash install.sh --master https://smokeping.example.com --key spm_abc123...

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo bash install.sh --master URL --key KEY"
    exit 1
fi

MASTER_URL=""
SLAVE_KEY=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --master) MASTER_URL="$2"; shift 2;;
        --key) SLAVE_KEY="$2"; shift 2;;
        *) echo "Unknown option: $1"; exit 1;;
    esac
done

if [ -z "$MASTER_URL" ] || [ -z "$SLAVE_KEY" ]; then
    echo "Usage: sudo bash install.sh --master URL --key KEY"
    exit 1
fi

INSTALL_DIR="/opt/smokeping-agent"

echo "=== SmokePing Manager Agent Installer ==="

# Check SmokePing is installed
if ! command -v smokeping >/dev/null 2>&1; then
    echo "WARNING: SmokePing not found. Install it first: apt install smokeping"
fi

# Install agent
echo "[1/3] Installing agent..."
mkdir -p "$INSTALL_DIR"
cp smokeping_agent.py "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/smokeping_agent.py"

# Create env file
echo "[2/3] Creating configuration..."
cat > /etc/smokeping-agent.env <<EOF
SPM_MASTER_URL=${MASTER_URL}
SPM_SLAVE_KEY=${SLAVE_KEY}
SPM_CONFIG_PATH=/etc/smokeping/config.d/Targets
SPM_PID_FILE=/var/run/smokeping/smokeping.pid
SPM_POLL_INTERVAL=60
EOF

# Create systemd service
echo "[3/3] Installing service..."
if command -v systemctl >/dev/null 2>&1; then
    cat > /etc/systemd/system/smokeping-agent.service <<EOF
[Unit]
Description=SmokePing Manager Agent
After=network.target smokeping.service

[Service]
Type=simple
User=root
EnvironmentFile=/etc/smokeping-agent.env
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/smokeping_agent.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable smokeping-agent
    echo ""
    echo "=== Installation complete ==="
    echo "  Start:  sudo systemctl start smokeping-agent"
    echo "  Status: sudo systemctl status smokeping-agent"
    echo "  Logs:   sudo journalctl -u smokeping-agent -f"
else
    echo ""
    echo "=== Installation complete ==="
    echo "  No systemd — run manually:"
    echo "  python3 ${INSTALL_DIR}/smokeping_agent.py"
fi
