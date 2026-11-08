"""Shared constants and helpers for DonutMonitorControl.

Used by the daemon (donut-monitord) and the GUI (donut-monitor) so that both
agree on the config file, the systemd unit and the external tools they call.
"""

import glob
import logging
import os
import shutil
from typing import Optional

APP_NAME = "DonutMonitorControl"
APP_ID = "online.donutsdelivery.DonutMonitorControl"
SERVICE_UNIT = "donut-monitord.service"  # systemd *user* unit, installed to /usr/lib/systemd/user
SHARE_DIR = "/usr/share/donut-monitor-control"

SYSTEM_CONFIG = "/etc/donut-monitor-control/config.json"
# Config locations used by earlier releases (monitor-remote-control and
# auto-brightness-ddcutil). Read only, for migration.
LEGACY_CONFIGS = (
    "/etc/monitor-remote-control/config.json",
    "/etc/auto-brightness/config.json",
)

_log = logging.getLogger("DonutMonitorCommon")


def user_config_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "donut-monitor-control", "config.json")


def resolve_config_path() -> str:
    """Return the config file both the daemon and the GUI use.

    Order: DONUT_MONITOR_CONFIG, then the per-user file. If the per-user file
    does not exist yet, it is seeded from the system default, or from a config
    left by an older release. When the copy fails, the source file is returned
    and used read-only.
    """
    override = os.environ.get("DONUT_MONITOR_CONFIG")
    if override:
        return override

    user = user_config_path()
    if os.path.exists(user):
        return user

    for source in (SYSTEM_CONFIG,) + LEGACY_CONFIGS:
        if os.path.exists(source):
            try:
                os.makedirs(os.path.dirname(user), exist_ok=True)
                shutil.copyfile(source, user)
                _log.info("Copied config %s to %s", source, user)
                return user
            except OSError as e:
                _log.warning("Could not copy %s to %s (%s); reading it in place", source, user, e)
                return source
    return user


def qdbus_binary() -> str:
    """Find a qdbus executable. Arch ships qdbus6 (qt6-tools) or qdbus (qt5-tools)."""
    for name in ("qdbus6", "qdbus", "qdbus-qt6", "qdbus-qt5"):
        if shutil.which(name):
            return name
    return "qdbus"


def i2c_access_problem() -> Optional[str]:
    """Return a message with the exact fix when /dev/i2c-* is unusable, else None."""
    devices = glob.glob("/dev/i2c-[0-9]*")
    if not devices:
        return (
            "No /dev/i2c-* devices found, so the i2c-dev kernel module is not loaded. "
            "Run: sudo modprobe i2c-dev"
            " (the package loads it at boot through /usr/lib/modules-load.d/donut-monitor-i2c.conf)."
        )
    if not any(os.access(dev, os.R_OK | os.W_OK) for dev in devices):
        return (
            "No permission to use /dev/i2c-*, so DDC/CI cannot reach your monitors. "
            "Run: sudo udevadm control --reload && sudo udevadm trigger --subsystem-match=i2c-dev"
            " and, if that is not enough, sudo usermod -aG i2c $USER and log in again."
        )
    return None
