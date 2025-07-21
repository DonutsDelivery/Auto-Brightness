#!/bin/bash

set -e

echo "Installing Auto Brightness Service for Arch Linux..."

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)" 
   exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed. Installing..."
    pacman -Sy python python-pip --noconfirm
fi

if ! python3 -c "import requests" &> /dev/null; then
    echo "Installing required Python packages..."
    pip install requests
fi

echo "Creating directories..."
mkdir -p /opt/auto-brightness
mkdir -p /etc/auto-brightness

echo "Copying files..."
cp auto_brightness.py /opt/auto-brightness/
chmod +x /opt/auto-brightness/auto_brightness.py

cp config.json /etc/auto-brightness/
chmod 644 /etc/auto-brightness/config.json

USERNAME=${SUDO_USER:-$USER}

echo "Installing systemd service for user $USERNAME..."
mkdir -p /home/$USERNAME/.config/systemd/user
cp auto-brightness.service /home/$USERNAME/.config/systemd/user/
chown $USERNAME:$USERNAME /home/$USERNAME/.config/systemd/user/auto-brightness.service

echo "Enabling service for user $USERNAME..."
sudo -u $USERNAME systemctl --user daemon-reload
sudo -u $USERNAME systemctl --user enable auto-brightness.service

echo ""
echo "Installation complete!"
echo ""
echo "Configuration:"
echo "- Edit /etc/auto-brightness/config.json to customize settings"
echo "- Set your latitude/longitude for better accuracy"
echo "- Adjust min_brightness and max_brightness (0.1 to 1.0)"
echo "- Modify update_interval (seconds between updates)"
echo ""
echo "Usage:"
echo "  Start service: systemctl --user start auto-brightness.service"
echo "  Stop service:  systemctl --user stop auto-brightness.service"
echo "  View logs:     journalctl --user -u auto-brightness.service -f"
echo ""
echo "The service will start automatically on login."