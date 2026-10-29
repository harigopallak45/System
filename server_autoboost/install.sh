#!/usr/bin/env bash
# ==============================================================================
# AutoBoost Local / Remote Installer
# ==============================================================================

set -e

echo "=== Installing AutoBoost on Linux Server ==="

if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (or with sudo)."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Create config directory
mkdir -p /etc/autoboost
if [ ! -f /etc/autoboost/autoboost.conf ]; then
    echo "Creating /etc/autoboost/autoboost.conf..."
    cp "$SCRIPT_DIR/autoboost.conf" /etc/autoboost/autoboost.conf
fi

# 2. Install daemon
echo "Installing /usr/local/bin/autoboost-daemon..."
cp "$SCRIPT_DIR/autoboost_daemon.py" /usr/local/bin/autoboost-daemon
chmod 755 /usr/local/bin/autoboost-daemon

# 3. Install CLI
echo "Installing /usr/local/bin/autoboost..."
cp "$SCRIPT_DIR/autoboost" /usr/local/bin/autoboost
chmod 755 /usr/local/bin/autoboost

# 4. Install systemd service
echo "Installing /etc/systemd/system/autoboost.service..."
cp "$SCRIPT_DIR/autoboost.service" /etc/systemd/system/autoboost.service
systemctl daemon-reload
systemctl enable autoboost.service
systemctl restart autoboost.service

echo ""
echo "=== AutoBoost Installation Complete! ==="
echo "Status:"
systemctl status autoboost.service --no-pager --lines=5

echo ""
echo "You can now run 'sudo autoboost' or 'sudo autoboost status' anytime!"
