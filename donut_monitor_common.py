"""Shared constants and helpers for DonutMonitorControl.

Used by the daemon (donut-monitord) and the GUI (donut-monitor) so that both
agree on the config file, the systemd unit and the external tools they call.
"""

import glob
import grp
import logging
import os
import pwd
import shutil
import stat
from dataclasses import dataclass
from typing import List, Mapping, Optional

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


# Files the Arch package installs. When they exist the fix needs fewer steps.
I2C_RULE_PACKAGED = "/usr/lib/udev/rules.d/60-donut-monitor-i2c.rules"
I2C_RULE_LOCAL = "/etc/udev/rules.d/60-donut-monitor-i2c.rules"
I2C_MODULES_PACKAGED = "/usr/lib/modules-load.d/donut-monitor-i2c.conf"
I2C_MODULES_LOCAL = "/etc/modules-load.d/i2c-dev.conf"
# Same line as udev/60-donut-monitor-i2c.rules.
I2C_RULE_TEXT = 'SUBSYSTEM=="i2c-dev", KERNEL=="i2c-[0-9]*", TAG+="uaccess", GROUP="i2c", MODE="0660"'
I2C_GROUP = "i2c"

_FAMILY_IDS = {
    "arch": ("arch",),
    "debian": ("debian", "ubuntu"),
    "fedora": ("fedora", "rhel", "centos"),
    "suse": ("suse", "opensuse", "sles"),
    "nixos": ("nixos",),
}
_INSTALL_DDCUTIL = {
    "arch": "sudo pacman -S ddcutil",
    "debian": "sudo apt install ddcutil",
    "fedora": "sudo dnf install ddcutil",
    "suse": "sudo zypper install ddcutil",
}


def read_os_release(path: str = "/etc/os-release") -> Mapping[str, str]:
    """Parse /etc/os-release (KEY=value lines, optional quotes). Empty when unreadable."""
    values = {}
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                key, sep, value = line.strip().partition("=")
                if sep and key and not key.startswith("#"):
                    values[key] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def distro_family(os_release: Optional[Mapping[str, str]] = None) -> str:
    """Return arch, debian, fedora, suse, nixos or other, from ID and ID_LIKE."""
    if os_release is None:
        os_release = read_os_release()
    tokens = [os_release.get("ID", "").lower()] + os_release.get("ID_LIKE", "").lower().split()
    for family, ids in _FAMILY_IDS.items():
        if any(token.startswith(ids) for token in tokens if token):
            return family
    return "other"


@dataclass(frozen=True)
class I2CFacts:
    """What the process can see about /dev/i2c-* without root."""
    family: str
    devices: int                 # number of /dev/i2c-N nodes
    usable: bool                 # this process can open at least one node read/write
    module_loaded: bool          # /sys/module/i2c_dev exists
    node_group: Optional[str]    # group name of the first node
    node_group_rw: bool          # that node is group read/write
    group_exists: bool           # the i2c group exists
    user_in_group: bool          # the account is listed in the group (or has it as primary)
    session_in_group: bool       # this process already carries the group
    rule_installed: bool         # a udev rule for i2c-dev is on disk
    modules_conf_installed: bool # something loads i2c-dev at boot
    ddcutil_present: bool


def collect_i2c_facts() -> I2CFacts:
    nodes = sorted(glob.glob("/dev/i2c-[0-9]*"))
    usable = any(os.access(node, os.R_OK | os.W_OK) for node in nodes)

    node_group = None
    node_group_rw = False
    if nodes:
        try:
            info = os.stat(nodes[0])
            node_group = grp.getgrgid(info.st_gid).gr_name
            node_group_rw = (info.st_mode & (stat.S_IRGRP | stat.S_IWGRP)) == (stat.S_IRGRP | stat.S_IWGRP)
        except (OSError, KeyError):
            pass

    group_exists = False
    user_in_group = False
    session_in_group = False
    try:
        entry = grp.getgrnam(I2C_GROUP)
        group_exists = True
        account = pwd.getpwuid(os.getuid())
        user_in_group = account.pw_name in entry.gr_mem or account.pw_gid == entry.gr_gid
        session_in_group = entry.gr_gid in os.getgroups()
    except KeyError:
        pass

    return I2CFacts(
        family=distro_family(),
        devices=len(nodes),
        usable=usable,
        module_loaded=os.path.isdir("/sys/module/i2c_dev"),
        node_group=node_group,
        node_group_rw=node_group_rw,
        group_exists=group_exists,
        user_in_group=user_in_group,
        session_in_group=session_in_group,
        rule_installed=os.path.exists(I2C_RULE_PACKAGED) or os.path.exists(I2C_RULE_LOCAL),
        modules_conf_installed=os.path.exists(I2C_MODULES_PACKAGED) or os.path.exists(I2C_MODULES_LOCAL),
        ddcutil_present=shutil.which("ddcutil") is not None,
    )


def plan_i2c_fix(facts: I2CFacts) -> Optional[str]:
    """Turn the facts into a message with the exact commands, or None when i2c works."""
    if facts.usable:
        return None

    if facts.family == "nixos":
        return (
            "DDC/CI cannot use /dev/i2c-*. Add this to your NixOS configuration, run "
            "sudo nixos-rebuild switch, then log out and back in:\n"
            "  hardware.i2c.enable = true;\n"
            '  users.users.<your user>.extraGroups = [ "i2c" ];'
        )

    lines: List[str] = []
    if not facts.ddcutil_present:
        install = _INSTALL_DDCUTIL.get(facts.family, "install ddcutil with your package manager")
        lines += ["ddcutil is not installed. Run:", f"  {install}"]

    if facts.devices == 0:
        if facts.module_loaded:
            lines.append(
                "The i2c-dev kernel module is loaded but the kernel lists no I2C adapters, "
                "so the GPU driver may not be loaded. Check: ls /sys/bus/i2c/devices"
            )
            return "\n".join(lines)
        lines.append("No /dev/i2c-* devices exist because the i2c-dev kernel module is not loaded. Run:")
        lines.append("  sudo modprobe i2c-dev")
        if not facts.modules_conf_installed:
            lines.append(f"  echo i2c-dev | sudo tee {I2C_MODULES_LOCAL}")
        lines.append("Then click Refresh. If access is still denied, the app lists the permission steps next.")
        return "\n".join(lines)

    commands: List[str] = []
    rule_works = facts.node_group == I2C_GROUP and facts.node_group_rw
    if not rule_works:
        if not facts.group_exists:
            commands.append(f"sudo groupadd -r -f {I2C_GROUP}")
        if not facts.rule_installed:
            commands.append(f"echo '{I2C_RULE_TEXT}' | sudo tee {I2C_RULE_LOCAL}")
        commands.append("sudo udevadm control --reload && sudo udevadm trigger --subsystem-match=i2c-dev")
    if not facts.user_in_group:
        commands.append(f"sudo usermod -aG {I2C_GROUP} $USER")

    if commands:
        lines.append("No permission to use /dev/i2c-*, so DDC/CI cannot reach your monitors. Run:")
        lines += [f"  {command}" for command in commands]
        lines.append("Then log out and back in.")
    elif not facts.session_in_group:
        lines.append(
            f"You are in the {I2C_GROUP} group but this session started before that. "
            "Log out and back in, then click Refresh."
        )
    else:
        lines.append(
            "/dev/i2c-* exists but this account cannot open it. Check the owner and mode with "
            "ls -l /dev/i2c-* and your udev rules."
        )
    return "\n".join(lines)


def i2c_access_problem() -> Optional[str]:
    """Return a message with the exact fix when /dev/i2c-* is unusable, else None.

    Reads only world-visible state (/dev, /etc/group, /etc/os-release), no root.
    """
    return plan_i2c_fix(collect_i2c_facts())
