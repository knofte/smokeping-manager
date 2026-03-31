#!/bin/bash
set -e

# smokeping-manager installer for Ubuntu/Debian with existing SmokePing
# Usage: sudo bash install.sh

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo bash install.sh"
    exit 1
fi

INSTALL_DIR="/opt/smokeping-manager"
SERVICE_USER="smokeping"
SMOKEPING_CONFIG_DIR="/etc/smokeping/config.d"

echo "=== SmokePing Manager Installer ==="
echo ""

# Check that SmokePing is installed
if ! dpkg -l smokeping >/dev/null 2>&1; then
    echo "WARNING: SmokePing does not appear to be installed."
    echo "Install it first: apt install smokeping"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 1
fi

# Install dependencies
echo "[1/5] Installing dependencies..."
apt-get install -y python3 python3-pip git >/dev/null 2>&1
pip3 install flask gunicorn >/dev/null 2>&1

# Clone or update repo
echo "[2/5] Installing smokeping-manager..."
if [ -d "$INSTALL_DIR" ]; then
    cd "$INSTALL_DIR"
    git pull origin master
else
    git clone https://github.com/knofte/smokeping-manager.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Generate a random secret key if not already set
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Create environment file
echo "[3/5] Creating configuration..."
if [ ! -f /etc/smokeping-manager.env ]; then
    cat > /etc/smokeping-manager.env <<EOF
SPM_SECRET_KEY=${SECRET_KEY}
SPM_ADMIN_USER=admin
SPM_ADMIN_PASSWORD=admin
SPM_CONFIG_DIR=${SMOKEPING_CONFIG_DIR}
SPM_INCLUDE_FILE=managed-targets
SPM_PID_FILE=/var/run/smokeping/smokeping.pid
SPM_HOST=0.0.0.0
SPM_PORT=5000
SPM_DEBUG=false
#SPM_CGI_PATH=/usr/lib/cgi-bin/smokeping.cgi
SPM_DATABASE=${INSTALL_DIR}/smokeping-manager.db
EOF
    echo "  Config written to /etc/smokeping-manager.env"
    echo "  IMPORTANT: Change the admin password!"
    echo "    sudo nano /etc/smokeping-manager.env"
else
    echo "  Config already exists at /etc/smokeping-manager.env (skipping)"
fi

# Install systemd service (if available)
echo "[4/5] Setting up service..."
if command -v systemctl >/dev/null 2>&1; then
    cat > /etc/systemd/system/smokeping-manager.service <<EOF
[Unit]
Description=SmokePing Manager
After=network.target smokeping.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=/etc/smokeping-manager.env
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable smokeping-manager
    echo "  systemd service installed and enabled"
    HAS_SYSTEMD=1
else
    echo "  systemd not found — skipping service install"
    echo "  You can run manually: python3 ${INSTALL_DIR}/app.py"
    echo "  Or set up your own init script (supervisord, rc.d, etc.)"
    HAS_SYSTEMD=0
fi

# Add @include to SmokePing Targets if not already there
echo "[5/5] Configuring SmokePing integration..."
TARGETS_FILE="${SMOKEPING_CONFIG_DIR}/Targets"
INCLUDE_LINE="@include managed-targets"
if [ -f "$TARGETS_FILE" ]; then
    if ! grep -q "managed-targets" "$TARGETS_FILE"; then
        echo "" >> "$TARGETS_FILE"
        echo "$INCLUDE_LINE" >> "$TARGETS_FILE"
        echo "  Added '$INCLUDE_LINE' to $TARGETS_FILE"
    else
        echo "  @include already present in $TARGETS_FILE"
    fi
    # Create empty managed-targets file if it doesn't exist
    touch "${SMOKEPING_CONFIG_DIR}/managed-targets"
else
    echo "  WARNING: $TARGETS_FILE not found. You'll need to add '@include managed-targets' manually."
fi

echo ""
echo "=== Installation complete ==="
echo ""
echo "  Web UI:  http://$(hostname -I | awk '{print $1}'):5000"
echo "  Login:   admin / admin (change in /etc/smokeping-manager.env)"
echo ""
if [ "${HAS_SYSTEMD:-0}" = "1" ]; then
    echo "  Start:   sudo systemctl start smokeping-manager"
    echo "  Status:  sudo systemctl status smokeping-manager"
else
    echo "  Start:   cd ${INSTALL_DIR} && python3 app.py"
fi
echo ""
echo "  NEXT STEPS:"
echo "  1. Change the admin password in /etc/smokeping-manager.env"
echo "  2. Start the service (see above)"
echo "  3. Open the web UI and add your first group + host"
echo ""
