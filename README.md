# Auto-Brightness

[![Discord](https://img.shields.io/badge/Discord-Join%20Server-5865F2?logo=discord&logoColor=white)](https://discord.gg/ZhvPhXrdZ4)

**[Join our Discord](https://discord.gg/ZhvPhXrdZ4)** for help, feature requests, and discussions.

---

A simple service that automatically adjusts your screen brightness based on the sun's position at your location.

## Features

- Automatic brightness adjustment based on solar elevation
- Per-monitor brightness offset calibration
- Fullscreen detection (pauses auto-brightness for media/games)
- KDE Plasma integration via ScreenBrightness DBus
- DDC/CI support for external monitors
- Kirigami-based GUI for configuration

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/DonutsDelivery/auto-brightness.git
   cd auto-brightness
   ```

2. Install dependencies:
   ```bash
   pip install requests
   ```

3. Install the systemd service:
   ```bash
   cp auto-brightness.service ~/.config/systemd/user/
   systemctl --user enable --now auto-brightness.service
   ```

## Configuration

Edit `config.json` to customize:

- `latitude` / `longitude` - Your location (auto-detected via IP if not set)
- `min_brightness` - Minimum brightness at night (0.0-1.0)
- `max_brightness` - Maximum brightness at midday (0.0-1.0)
- `update_interval` - Seconds between brightness updates
- `monitor_offsets` - Per-monitor brightness adjustments

## GUI

Run the configuration GUI:
```bash
python3 brightness_kirigami_qt6.py
```

## License

MIT
