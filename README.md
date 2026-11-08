# DonutMonitorControl

[![Website](https://img.shields.io/badge/Website-View%20Project-4285F4?logo=google-chrome&logoColor=white)](https://donutsdelivery.online/#monitorremotecontrol)
[![Discord](https://img.shields.io/badge/Discord-Join%20Server-5865F2?logo=discord&logoColor=white)](https://discord.gg/ZhvPhXrdZ4)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/donutsdelivery)

<p align="center">
  <a href="https://donutsdelivery.online/#monitorremotecontrol">
    <img src="https://donutsdelivery.online/assets/mockups/thumbs/monitorremotecontrol-mockup-1.svg" alt="DonutMonitorControl mockup" width="600">
  </a>
</p>

**[View Project Website](https://donutsdelivery.online/#monitorremotecontrol)** | **[Join our Discord](https://discord.gg/ZhvPhXrdZ4)** for help, feature requests, and discussions.

---

DonutMonitorControl (formerly Monitor Remote Control) sets monitor brightness, contrast, color preset and input source over DDC/CI. A background daemon follows the sun, so the screen is dimmer at night and brighter at midday.

## Features

- Automatic brightness from solar elevation at your location
- Per-monitor brightness offsets
- Pauses auto brightness while a window is fullscreen on a monitor (KDE Plasma, or GNOME with a helper, see below)
- KDE Plasma integration via the ScreenBrightness DBus service
- DDC/CI for external monitors through ddcutil, with a raw I2C fallback
- Kirigami GUI

## What gets installed

| Piece | Name |
| --- | --- |
| GUI | `donut-monitor` |
| Daemon | `donut-monitord`, run by the systemd user unit `donut-monitord.service` |
| App ID | `online.donutsdelivery.DonutMonitorControl` |
| Config | `~/.config/donut-monitor-control/config.json` |
| System default config | `/etc/donut-monitor-control/config.json` |

The GUI and the daemon read and write the same per-user config file. On first run it is copied from the system default. If you used an older release, the config in `/etc/monitor-remote-control/` or `/etc/auto-brightness/` is picked up instead. Set `DONUT_MONITOR_CONFIG` to use another file.

## Installation

### Arch Linux (AUR)

```bash
yay -S donutmonitorcontrol
```

The package provides, conflicts with and replaces `monitor-remote-control`. It installs the udev rule, loads `i2c-dev` at boot and ships the systemd user unit. Then:

```bash
sudo systemctl restart systemd-modules-load
sudo udevadm control --reload && sudo udevadm trigger --subsystem-match=i2c-dev
systemctl --user enable --now donut-monitord.service
```

If a monitor is not found, the GUI says whether `/dev/i2c-*` is missing or not accessible and prints the command to fix it.

### Other distributions (manual)

Install `ddcutil`, Python 3 with `requests` and PyQt6, Qt 6 declarative and Kirigami, `qdbus` (Qt 6 tools) and `gdbus` (glib2) with your package manager, then from a clone of this repository:

```bash
sudo install -Dm755 auto_brightness.py /usr/bin/donut-monitord
sudo install -Dm755 brightness_kirigami_qt6.py /usr/bin/donut-monitor
sudo install -Dm644 monitor_control.py donut_monitor_common.py donut_background.py brightness_kirigami_qt6.qml -t /usr/share/donut-monitor-control
sudo install -Dm644 config.json /etc/donut-monitor-control/config.json
sudo install -Dm644 donut-monitord.service /usr/lib/systemd/user/donut-monitord.service
sudo install -Dm644 udev/60-donut-monitor-i2c.rules /usr/lib/udev/rules.d/60-donut-monitor-i2c.rules
sudo install -Dm644 modules-load.d/donut-monitor-i2c.conf /usr/lib/modules-load.d/donut-monitor-i2c.conf
sudo install -Dm644 sysusers.d/donut-monitor-i2c.conf /usr/lib/sysusers.d/donut-monitor-i2c.conf
sudo install -Dm644 data/online.donutsdelivery.DonutMonitorControl.desktop -t /usr/share/applications
sudo install -Dm644 data/online.donutsdelivery.DonutMonitorControl.metainfo.xml -t /usr/share/metainfo
sudo install -Dm644 data/icons/online.donutsdelivery.DonutMonitorControl.svg -t /usr/share/icons/hicolor/scalable/apps
sudo systemd-sysusers && sudo modprobe i2c-dev
sudo udevadm control --reload && sudo udevadm trigger --subsystem-match=i2c-dev
systemctl --user daemon-reload
systemctl --user enable --now donut-monitord.service
```

The PNG icons in `data/icons/hicolor/` go to `/usr/share/icons/hicolor/<size>/apps/` the same way. If the rule does not give you access (for example when you are not on the active local seat), add yourself to the `i2c` group with `sudo usermod -aG i2c $USER` and log in again.

The manual route has only been checked statically. Nobody has run it on Debian, Fedora or openSUSE.

### Flatpak

Inside a Flatpak sandbox there is no systemd user manager, so the GUI asks `org.freedesktop.portal.Background` for background and autostart instead, with `donut-monitord` as the command. The portal shows the permission prompt and writes the host autostart entry. Outside a sandbox (no `/.flatpak-info`) nothing changes: the package ships `donut-monitord.service` and you enable it with `systemctl --user`. There is no Flatpak manifest in this repository yet, so this path has only been tested against a stand-in portal service.

## Configuration

Edit the config file (see above) or use the GUI:

- `latitude` / `longitude` - Your location (auto-detected via IP if not set)
- `min_brightness` - Minimum brightness at night (0.0-1.0)
- `max_brightness` - Maximum brightness at midday (0.0-1.0)
- `update_interval` - Seconds between brightness updates
- `display_refresh_interval` - Seconds between full DDC topology scans (default: 1800); connector changes refresh immediately
- `monitor_offsets` - Per-monitor brightness adjustments

Restart the daemon after editing by hand: `systemctl --user restart donut-monitord.service`.

## GNOME fullscreen detection

On KDE the daemon asks KWin which windows are fullscreen. On GNOME it first calls the DBus service `online.donutsdelivery.DonutMonitorControl.FullscreenMonitor` (method `GetFullscreenMonitors` on `/online/donutsdelivery/DonutMonitorControl/FullscreenMonitor`) and that needs a GNOME Shell helper that exports it. This repository does not ship that helper. Without it the call fails and the daemon moves on, so auto brightness works but is not paused for fullscreen windows on GNOME.

## GUI

```bash
donut-monitor
```

From a clone, `python3 brightness_kirigami_qt6.py` runs the same GUI. The Tk, tray and Qt 5 variants (`brightness_gui.py`, `brightness_tray.py`, `brightness_panel.py`, `brightness_kirigami.py`) are kept in the repository but are not installed.

## License

MIT, copyright Zero Action (DonutsDelivery). See `LICENSE`.
