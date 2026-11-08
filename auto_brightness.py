#!/usr/bin/env python3

import json
import time
import subprocess
import requests
from datetime import datetime, timezone, timedelta
import math
import logging
import sys
import os
import re
from contextlib import contextmanager

# Installed copies live in /usr/bin; the shared modules live in /usr/share/donut-monitor-control.
_SHARE_DIR = "/usr/share/donut-monitor-control"
if os.path.isdir(_SHARE_DIR) and _SHARE_DIR not in sys.path:
    sys.path.append(_SHARE_DIR)

from donut_monitor_common import resolve_config_path, qdbus_binary

QDBUS = qdbus_binary()

# Import the hybrid monitor control for KDE + DDC support
try:
    from monitor_control import HybridMonitorControl, run_ddcutil, serialized_ddc_access
    HAS_HYBRID_CONTROL = True
except ImportError:
    HAS_HYBRID_CONTROL = False
    HybridMonitorControl = None

    def run_ddcutil(args, *, timeout=20.0, check=True):
        """Fallback used only when the shared monitor-control module is absent."""
        return subprocess.run(
            ['ddcutil', *args],
            capture_output=True,
            text=True,
            check=check,
            timeout=timeout,
        )

    @contextmanager
    def serialized_ddc_access(timeout=30.0):
        yield


class AutoBrightnessService:
    def __init__(self, config_path=None):
        if config_path is None:
            # Same file the GUI edits: per-user config, seeded from /etc/donut-monitor-control
            config_path = resolve_config_path()
        self.config_path = config_path
        self.config = self.load_config()
        self.setup_logging()

        # Initialize hybrid monitor control if available
        self.hybrid_control = None
        if HAS_HYBRID_CONTROL and HybridMonitorControl is not None:
            try:
                self.hybrid_control = HybridMonitorControl()
                logging.info("Using HybridMonitorControl (KDE + DDC)")
            except Exception as e:
                logging.warning(f"Could not initialize HybridMonitorControl: {e}")
                self.hybrid_control = None

        # Track fullscreen state per monitor
        self.fullscreen_monitors = set()
        # Mapping from X output names (DP-1, etc) to KDE monitor IDs (kde_0, etc)
        self._output_to_kde_map = {}
        # Detect session type and desktop environment
        self._session_type = os.environ.get('XDG_SESSION_TYPE', 'x11')
        self._desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').upper().split(':')[-1]  # e.g. "GNOME", "KDE"
        # Track last brightness set per display to avoid redundant DDC calls
        self._last_brightness = {}
        # Cache the stable display topology; brightness calculation still runs
        # at the configured update interval.
        self._cached_displays = []
        self._display_cache_signature = ()
        self._display_cache_refreshed_at = 0.0

    def get_fullscreen_monitors(self):
        """Detect which monitors have fullscreen windows.

        Tries GNOME Shell extension DBus first, falls back to KWin for KDE.
        """
        fullscreen_monitors = set()

        # Try GNOME Shell extension first
        try:
            result = subprocess.run(
                ['gdbus', 'call', '--session',
                 '--dest', 'online.donutsdelivery.DonutMonitorControl.FullscreenMonitor',
                 '--object-path', '/online/donutsdelivery/DonutMonitorControl/FullscreenMonitor',
                 '--method', 'online.donutsdelivery.DonutMonitorControl.FullscreenMonitor.GetFullscreenMonitors'],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                # Parse output like "([0, 1],)" — array of monitor indices
                monitors_str = result.stdout.strip()
                monitor_indices = re.findall(r'\d+', monitors_str)
                for idx in monitor_indices:
                    fullscreen_monitors.add(idx)
                if fullscreen_monitors:
                    logging.debug(f"GNOME fullscreen monitors: {fullscreen_monitors}")
                return fullscreen_monitors
        except (subprocess.TimeoutExpired, Exception) as e:
            logging.debug(f"GNOME fullscreen detection not available: {e}")

        # Fall back to KWin for KDE
        try:
            result = subprocess.run(
                [QDBUS, '--literal', 'org.kde.KWin', '/WindowsRunner', 'org.kde.krunner1.Match', ''],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode != 0:
                return fullscreen_monitors

            window_uuids = re.findall(r'0_\{([0-9a-f-]+)\}', result.stdout)
            if not window_uuids:
                return fullscreen_monitors

            monitor_geometry = self._get_monitor_geometry()

            for uuid in window_uuids:
                try:
                    info_result = subprocess.run(
                        [QDBUS, 'org.kde.KWin', '/KWin', 'org.kde.KWin.getWindowInfo', f'{{{uuid}}}'],
                        capture_output=True, text=True, timeout=1
                    )
                    if info_result.returncode != 0:
                        continue

                    output = info_result.stdout
                    fullscreen_match = re.search(r'fullscreen:\s*(true|false)', output)
                    if not (fullscreen_match and fullscreen_match.group(1) == 'true'):
                        continue

                    x_match = re.search(r'^x:\s*(\d+)', output, re.MULTILINE)
                    y_match = re.search(r'^y:\s*(\d+)', output, re.MULTILINE)
                    w_match = re.search(r'^width:\s*(\d+)', output, re.MULTILINE)
                    h_match = re.search(r'^height:\s*(\d+)', output, re.MULTILINE)

                    if x_match and y_match and w_match and h_match:
                        x, y = int(x_match.group(1)), int(y_match.group(1))
                        w, h = int(w_match.group(1)), int(h_match.group(1))
                        cx, cy = x + w // 2, y + h // 2

                        for monitor_id, geom in monitor_geometry.items():
                            mx, my, mw, mh = geom
                            if mx <= cx < mx + mw and my <= cy < my + mh:
                                fullscreen_monitors.add(monitor_id)
                                break

                except (subprocess.TimeoutExpired, Exception):
                    continue

        except (subprocess.TimeoutExpired, Exception) as e:
            logging.debug(f"KWin fullscreen detection failed: {e}")

        return fullscreen_monitors

    def _get_output_to_kde_mapping(self):
        """Build mapping from output names (DP-1, etc.) to KDE display IDs using EDID model names.

        This is necessary because kscreen output indices don't correspond to
        KDE ScreenBrightness display numbers. We use the monitor model name
        from EDID to match outputs to KDE displays.
        """
        output_to_kde = {}

        # Skip KDE-specific mapping on non-KDE desktops
        if self._desktop != 'KDE':
            return output_to_kde

        # Get monitor names from KDE ScreenBrightness
        kde_labels = {}
        if self.hybrid_control:
            # Ensure monitors are detected first
            if not self.hybrid_control.monitors:
                self.hybrid_control.detect_monitors()

            for kde_id in self.hybrid_control.monitors.keys():
                try:
                    # Extract display number from kde_N
                    display_num = kde_id.replace('kde_', '')
                    result = subprocess.run(
                        [QDBUS, 'org.kde.ScreenBrightness',
                         f'/org/kde/ScreenBrightness/display{display_num}',
                         'org.freedesktop.DBus.Properties.Get',
                         'org.kde.ScreenBrightness.Display', 'Label'],
                        capture_output=True, text=True, timeout=2
                    )
                    if result.returncode == 0:
                        label = result.stdout.strip()
                        kde_labels[kde_id] = label
                        logging.debug(f"KDE display {kde_id} label: {label}")
                except Exception as e:
                    logging.debug(f"Could not get label for {kde_id}: {e}")

        # Get EDID model names for each DRM output
        drm_base = '/sys/class/drm'
        try:
            for entry in os.listdir(drm_base):
                # Match card*-DP-*, card*-HDMI-*, etc.
                match = re.match(r'card\d+-(.+)', entry)
                if not match:
                    continue

                output_name = match.group(1).replace('-A-', '-')  # HDMI-A-1 -> HDMI-1
                edid_path = os.path.join(drm_base, entry, 'edid')

                if not os.path.exists(edid_path):
                    continue

                try:
                    result = subprocess.run(
                        ['edid-decode', edid_path],
                        capture_output=True, text=True, timeout=2
                    )
                    if result.returncode == 0:
                        # Extract product name from EDID
                        product_match = re.search(r"Display Product Name:\s*'([^']+)'", result.stdout)
                        if product_match:
                            product_name = product_match.group(1)
                            logging.debug(f"Output {output_name} EDID product: {product_name}")

                            # Find matching KDE display
                            for kde_id, label in kde_labels.items():
                                if product_name in label:
                                    output_to_kde[output_name] = kde_id
                                    logging.debug(f"Mapped {output_name} -> {kde_id} (via '{product_name}')")
                                    break
                except Exception as e:
                    logging.debug(f"Could not read EDID for {output_name}: {e}")
        except Exception as e:
            logging.debug(f"Could not enumerate DRM outputs: {e}")

        return output_to_kde

    def _get_monitor_geometry(self):
        """Get geometry of each monitor.

        Uses kscreen-doctor on KDE (works on both Wayland and X11),
        with xrandr fallback for non-KDE X11 sessions.

        Returns geometry dict with output names (DP-1, HDMI-1) as keys.
        Also builds a mapping from output names to KDE monitor IDs.
        """
        geometry = {}

        # Build output-to-KDE mapping using EDID names
        self._output_to_kde_map = self._get_output_to_kde_mapping()

        # Try GNOME Mutter DisplayConfig on GNOME Wayland
        if self._desktop == 'GNOME' and self._session_type == 'wayland':
            try:
                import dbus
                bus = dbus.SessionBus()
                proxy = bus.get_object('org.gnome.Mutter.DisplayConfig',
                                       '/org/gnome/Mutter/DisplayConfig')
                iface = dbus.Interface(proxy, 'org.gnome.Mutter.DisplayConfig')
                state = iface.GetCurrentState()
                # state: (serial, monitors, logical_monitors, properties)
                monitors = state[1]
                logical_monitors = state[2]

                # Build connector -> current mode resolution
                connector_modes = {}
                for monitor in monitors:
                    # monitor: ((connector, vendor, product, serial), [modes], properties)
                    connector = str(monitor[0][0])
                    modes = monitor[1]
                    for mode in modes:
                        # mode: (mode_id, width, height, refresh, scale, [supported_scales], properties)
                        props = mode[6] if len(mode) > 6 else {}
                        if props.get('is-current', False):
                            connector_modes[connector] = (int(mode[1]), int(mode[2]))
                            break

                # Build geometry from logical monitors
                for lm in logical_monitors:
                    # lm: (x, y, scale, transform, primary, [(connector, vendor, product, serial)], properties)
                    lm_x, lm_y = int(lm[0]), int(lm[1])
                    lm_monitors = lm[5]
                    for lm_mon in lm_monitors:
                        connector = str(lm_mon[0])
                        if connector in connector_modes:
                            w, h = connector_modes[connector]
                            geometry[connector] = (lm_x, lm_y, w, h)

                if geometry:
                    logging.debug(f"GNOME Mutter geometry: {geometry}")
            except Exception as e:
                logging.debug(f"GNOME Mutter DisplayConfig failed: {e}")

        # Try kscreen-doctor (KDE on both Wayland and X11) — skip on GNOME to avoid hang
        if not geometry and self._desktop != 'GNOME':
            try:
                result = subprocess.run(
                    ['kscreen-doctor', '--outputs'],
                    capture_output=True, text=True, timeout=5
                )

                if result.returncode == 0:
                    # Strip ANSI color codes from output
                    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                    clean_output = ansi_escape.sub('', result.stdout)

                    # Parse kscreen-doctor output to get output name and geometry
                    # Format: Output: 1 DP-1 uuid ... Geometry: 1440,1440 2560x1440
                    current_output = None
                    for line in clean_output.split('\n'):
                        # Match output line: "Output: 1 DP-1 uuid"
                        output_match = re.search(r'Output:\s*\d+\s+(\S+)', line)
                        if output_match:
                            current_output = output_match.group(1)  # e.g., DP-1, HDMI-1, eDP-1
                            continue

                        # Match geometry line: "Geometry: 1440,1440 2560x1440"
                        geom_match = re.search(r'Geometry:\s*(\d+),(\d+)\s+(\d+)x(\d+)', line)
                        if geom_match and current_output:
                            x, y, w, h = int(geom_match.group(1)), int(geom_match.group(2)), int(geom_match.group(3)), int(geom_match.group(4))
                            geometry[current_output] = (x, y, w, h)

                            # Also add geometry for the mapped KDE ID
                            if current_output in self._output_to_kde_map:
                                kde_id = self._output_to_kde_map[current_output]
                                geometry[kde_id] = (x, y, w, h)

                            current_output = None

            except (subprocess.SubprocessError, FileNotFoundError):
                pass  # kscreen-doctor not available, try xrandr

        # Fallback to xrandr for X11 sessions without KDE
        if not geometry and self._session_type == 'x11':
            try:
                result = subprocess.run(
                    ['xrandr', '--listmonitors'],
                    capture_output=True, text=True, timeout=5
                )

                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                        # Format: 0: +*DP-2 1920/527x1080/296+0+0  DP-2
                        parts = line.split()
                        if len(parts) >= 4:
                            match = re.search(r'(\d+)/\d+x(\d+)/\d+\+(\d+)\+(\d+)', parts[2])
                            if match:
                                w, h, x, y = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
                                output_name = parts[-1]  # e.g., DP-2
                                geometry[output_name] = (x, y, w, h)

                                # Add geometry for KDE ID if we have a mapping (from EDID)
                                if output_name in self._output_to_kde_map:
                                    kde_id = self._output_to_kde_map[output_name]
                                    geometry[kde_id] = (x, y, w, h)
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

        logging.debug(f"Monitor geometry: {geometry}, output map: {self._output_to_kde_map}")
        return geometry

    def _monitor_has_fullscreen(self, display, fullscreen_monitors):
        """Check if a display has a fullscreen window"""
        if display in fullscreen_monitors:
            return True

        # Check if any fullscreen monitor's output name maps to this display
        for fs_monitor in fullscreen_monitors:
            # If fullscreen monitor is an output name (like DP-1), check our mapping
            if fs_monitor in self._output_to_kde_map:
                if self._output_to_kde_map[fs_monitor] == display:
                    return True

        return False

    def load_config(self):
        default_config = {
            "latitude": None,
            "longitude": None,
            "min_brightness": 0.1,
            "max_brightness": 1.0,
            "update_interval": 300,
            "display_refresh_interval": 1800,
            "displays": [],
            "transition_duration": 30,
            "auto_brightness_enabled": True
        }
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                return {**default_config, **config}
        except FileNotFoundError:
            logging.warning(f"Config file not found at {self.config_path}, using defaults")
            return default_config
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON in config file {self.config_path}")
            return default_config
    
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    def get_location(self):
        if self.config["latitude"] and self.config["longitude"]:
            return self.config["latitude"], self.config["longitude"]
        
        try:
            response = requests.get("http://ip-api.com/json/", timeout=10)
            data = response.json()
            if data["status"] == "success":
                return data["lat"], data["lon"]
        except Exception as e:
            logging.error(f"Failed to get location: {e}")
        
        return None, None
    
    def get_sun_times(self, lat, lon):
        try:
            url = f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lon}&formatted=0"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if data["status"] == "OK":
                sunrise = datetime.fromisoformat(data["results"]["sunrise"].replace('Z', '+00:00'))
                sunset = datetime.fromisoformat(data["results"]["sunset"].replace('Z', '+00:00'))
                return sunrise, sunset
        except Exception as e:
            logging.error(f"Failed to get sun times: {e}")
        
        return None, None
    
    def calculate_solar_elevation(self, lat, lon, dt):
        """Calculate solar elevation angle in degrees"""
        # Get Julian day number
        a = (14 - dt.month) // 12
        y = dt.year + 4800 - a
        m = dt.month + 12 * a - 3
        jdn = dt.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
        
        # Convert UTC time to fractional day
        hour_decimal = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
        jd = jdn + (hour_decimal - 12) / 24.0
        
        # Days since J2000.0
        n = jd - 2451545.0
        
        # Mean longitude of Sun
        L = (280.460 + 0.9856474 * n) % 360
        
        # Mean anomaly
        g = math.radians((357.528 + 0.9856003 * n) % 360)
        
        # Ecliptic longitude
        lambda_sun = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
        
        # Solar declination
        declination = math.asin(0.39795 * math.sin(lambda_sun))
        
        # Equation of time (minutes)
        eot = 4 * (lon - 15 * (dt.utcoffset().total_seconds() / 3600 if dt.utcoffset() else 0)) + \
              229.18 * (0.000075 + 0.001868 * math.cos(math.radians(n)) - 
                       0.032077 * math.sin(math.radians(n)) - 
                       0.014615 * math.cos(2 * math.radians(n)) - 
                       0.040849 * math.sin(2 * math.radians(n)))
        
        # True solar time
        tst = hour_decimal * 60 + eot
        
        # Hour angle
        hour_angle = math.radians(15 * (tst / 60 - 12))
        
        # Solar elevation
        lat_rad = math.radians(lat)
        elevation = math.asin(math.sin(declination) * math.sin(lat_rad) + 
                             math.cos(declination) * math.cos(lat_rad) * math.cos(hour_angle))
        
        return math.degrees(elevation)

    def calculate_brightness(self, sunrise, sunset):
        now = datetime.now(timezone.utc)
        lat = self.config["latitude"]
        lon = self.config["longitude"]

        # Calculate solar elevation angle
        elevation = self.calculate_solar_elevation(lat, lon, now)

        logging.info(f"Solar elevation: {elevation:.1f}°")

        min_brightness = self.config["min_brightness"]
        max_brightness = self.config["max_brightness"]

        # Check if elevation scaling is enabled
        use_scaling = self.config.get("use_elevation_scaling", True)

        if not use_scaling:
            # Simple day/night mode with twilight transition
            # -6° to 6° is the transition zone (civil twilight through early morning)
            if elevation <= -6:
                logging.info("Full brightness mode - night (below civil twilight)")
                return min_brightness
            elif elevation <= 6:
                # Smooth transition during twilight (-6° to 6°)
                factor = (elevation + 6) / 12.0  # 0 at -6°, 1 at 6°
                brightness = min_brightness + (factor * (max_brightness - min_brightness))
                logging.info(f"Full brightness mode - twilight transition ({factor*100:.0f}%)")
                return brightness
            else:
                logging.info("Full brightness mode - day (sun above 6°)")
                return max_brightness

        # Convert elevation to brightness using a curve that accounts for sun height
        #
        # The sun's maximum elevation varies by latitude and season:
        # - Summer solstice: 90° - latitude + 23.5°
        # - Winter solstice: 90° - latitude - 23.5°
        # At 56°N: summer max ~57°, winter max ~10°
        #
        # Brightness curve:
        # - Below -6° (civil twilight): minimum brightness
        # - -6° to 0° (twilight): 0% to 30% of range
        # - 0° to 15°: 30% to 70% of range (morning/evening, low winter sun)
        # - 15° to 40°: 70% to 100% of range (good daylight)
        # - Above 40°: 100% (bright midday sun)

        if elevation <= -6:
            # Deep night (civil twilight and below)
            return min_brightness
        elif elevation <= 0:
            # Civil twilight to horizon - smooth transition
            twilight_factor = (elevation + 6) / 6.0
            return min_brightness + (0.3 * (max_brightness - min_brightness) * twilight_factor)
        elif elevation <= 15:
            # Low sun (sunrise/sunset, or winter midday at high latitudes)
            # 0° -> 30%, 15° -> 70%
            factor = 0.3 + 0.4 * (elevation / 15.0)
            return min_brightness + (factor * (max_brightness - min_brightness))
        elif elevation <= 40:
            # Good daylight - sun reasonably high
            # 15° -> 70%, 40° -> 100%
            factor = 0.7 + 0.3 * ((elevation - 15) / 25.0)
            return min_brightness + (factor * (max_brightness - min_brightness))
        else:
            # Bright midday sun (elevation > 40°)
            return max_brightness
    
    def _connected_display_signature(self):
        """Return connected DRM connector names without probing monitor DDC."""
        connectors = []
        drm_base = '/sys/class/drm'
        try:
            for entry in sorted(os.listdir(drm_base)):
                status_path = os.path.join(drm_base, entry, 'status')
                if not os.path.isfile(status_path):
                    continue
                with open(status_path) as status_file:
                    if status_file.read().strip() == 'connected':
                        connectors.append(entry)
        except OSError as e:
            logging.debug(f"Could not read DRM connector state: {e}")
        return tuple(connectors)

    def get_displays(self, force_refresh=False):
        """Get displays while avoiding a full NVIDIA DDC scan every cycle."""
        if self.config["displays"]:
            return self.config["displays"]

        now = time.monotonic()
        signature = self._connected_display_signature()
        topology_changed = bool(self._cached_displays) and signature != self._display_cache_signature
        refresh_interval = max(
            int(self.config.get("update_interval", 300)),
            int(self.config.get("display_refresh_interval", 1800)),
        )
        cache_is_current = (
            self._cached_displays
            and signature == self._display_cache_signature
            and now - self._display_cache_refreshed_at < refresh_interval
        )
        if not force_refresh and cache_is_current:
            return list(self._cached_displays)

        if self.hybrid_control:
            try:
                monitors = self.hybrid_control.detect_monitors(
                    include_capabilities=False,
                    force_refresh=force_refresh or topology_changed,
                )
                detection_succeeded = self.hybrid_control.last_detection_succeeded
                if monitors and detection_succeeded:
                    display_ids = list(monitors.keys())
                    if topology_changed or display_ids != self._cached_displays:
                        self._last_brightness.clear()
                    self._cached_displays = display_ids
                    self._display_cache_signature = signature
                    self._display_cache_refreshed_at = now
                    logging.info(f"Found {len(display_ids)} displays via HybridMonitorControl")
                    return list(display_ids)
                if monitors and not detection_succeeded and self._cached_displays:
                    logging.warning("Display refresh was incomplete; retaining cached topology")
                    return list(self._cached_displays)
                if topology_changed and detection_succeeded:
                    self._cached_displays = []
                    self._display_cache_signature = signature
                    self._display_cache_refreshed_at = now
                    self._last_brightness.clear()
                    return []
            except Exception as e:
                logging.warning(f"HybridMonitorControl detection failed: {e}")

        if self._cached_displays:
            logging.warning("Display refresh failed; retaining the last known monitor topology")
            return list(self._cached_displays)

        # Fall back to ddcutil
        try:
            result = run_ddcutil(['detect', '--brief'])
            displays = []
            for line in result.stdout.split('\n'):
                if 'I2C bus:' in line and '/dev/i2c-' in line:
                    i2c_path = line.split('/dev/i2c-')[1].strip()
                    displays.append(i2c_path)
            if displays:
                self._cached_displays = displays
                self._display_cache_signature = signature
                self._display_cache_refreshed_at = now
            return list(displays)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, TimeoutError, OSError) as e:
            logging.error(f"Failed to get displays via ddcutil: {e}")
            return []
    
    def ensure_proper_contrast(self, display):
        """Ensure the monitor has adequate contrast for brightness changes to be visible"""
        # Skip KDE-only displays - they don't have DDC access for contrast control
        if display.startswith('kde_'):
            return

        try:
            # Check current contrast
            result = run_ddcutil(['--bus', display, 'getvcp', '12'], timeout=5)
            
            # Parse contrast value
            current_contrast = None
            for line in result.stdout.split('\n'):
                if 'current value' in line.lower():
                    import re
                    value_match = re.search(r'current value\s*=\s*(\d+)', line)
                    if value_match:
                        current_contrast = int(value_match.group(1))
                        break
            
            if current_contrast is not None:
                # If contrast is too low (less than 50%), set it to 75% for optimal visibility
                if current_contrast < 50:
                    run_ddcutil(['--bus', display, 'setvcp', '12', '75'], timeout=5)
                    logging.info(f"Adjusted display {display} contrast from {current_contrast}% to 75% for better visibility")
                else:
                    logging.debug(f"Display {display} contrast is adequate at {current_contrast}%")
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, TimeoutError, OSError) as e:
            # Some monitors don't support contrast control, that's okay
            logging.debug(f"Could not check/adjust contrast for display {display}: {e}")
        except Exception as e:
            logging.warning(f"Unexpected error checking contrast for display {display}: {e}")

    def _get_monitor_label(self, display):
        """Get the label for a monitor to use as stable identifier for offsets"""
        if self.hybrid_control and display in self.hybrid_control.monitors:
            mon = self.hybrid_control.monitors[display]
            return mon.get('label') or mon.get('model') or display
        return display

    def get_monitor_offset(self, display):
        """Get brightness offset for a specific monitor

        Looks up by monitor label for persistence across reboots.
        Also checks by display ID for backwards compatibility.
        """
        offsets = self.config.get("monitor_offsets", {})
        # Try by label first (new behavior)
        label = self._get_monitor_label(display)
        if label in offsets:
            return offsets[label]
        # Fall back to display ID (backwards compatibility)
        return offsets.get(display, 0)

    def set_brightness(self, display, brightness):
        """Set brightness for a display - uses hybrid control if available"""
        # Apply monitor-specific offset
        offset = self.get_monitor_offset(display)
        brightness_percent = int(brightness * 100) + offset
        # Clamp to valid range
        brightness_percent = max(0, min(100, brightness_percent))

        # Skip if brightness hasn't changed since last set
        if self._last_brightness.get(display) == brightness_percent:
            logging.debug(f"Display {display}: brightness unchanged at {brightness_percent}%, skipping DDC call")
            return True

        if offset != 0:
            logging.info(f"Display {display}: base {int(brightness * 100)}% + offset {offset:+d}% = {brightness_percent}%")

        # Try hybrid control first (works for all monitors)
        if self.hybrid_control:
            try:
                success = self.hybrid_control.set_brightness(display, brightness_percent)
                if success:
                    self._last_brightness[display] = brightness_percent
                    logging.info(f"Set display {display} brightness to {brightness_percent}%")
                    return True
                else:
                    logging.warning(f"HybridMonitorControl failed for {display}, trying ddcutil")
            except Exception as e:
                logging.warning(f"HybridMonitorControl error for {display}: {e}")

        # Fall back to ddcutil for bus-based displays (skip kde_ displays)
        if display.startswith('kde_'):
            logging.error(f"Cannot set brightness for KDE display {display} without HybridMonitorControl")
            self._display_cache_refreshed_at = 0.0
            self._last_brightness.pop(display, None)
            return False

        try:
            run_ddcutil(['--bus', display, 'setvcp', '10', str(brightness_percent)])
            self._last_brightness[display] = brightness_percent
            logging.info(f"Set display {display} brightness to {brightness_percent}%")
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, TimeoutError, OSError) as e:
            logging.error(f"Failed to set brightness for display {display}: {e}")
            self._display_cache_refreshed_at = 0.0
            self._last_brightness.pop(display, None)
            return False

    def set_brightness_targets(self, targets):
        """Apply one scheduled generation to all monitors without interleaving."""
        results = {}
        with serialized_ddc_access():
            for display, brightness in targets.items():
                results[display] = self.set_brightness(display, brightness)
        return results
    
    def run(self):
        logging.info("Starting DonutMonitorControl daemon (donut-monitord)")
        
        # Check if auto brightness is enabled
        if not self.config.get("auto_brightness_enabled", True):
            logging.info("Auto brightness is disabled. Service will not adjust brightness automatically.")
            logging.info("Monitoring configuration changes...")
            
            # Monitor config changes while disabled
            while True:
                try:
                    # Reload config to check if enabled
                    self.config = self.load_config()
                    if self.config.get("auto_brightness_enabled", True):
                        logging.info("Auto brightness re-enabled. Starting brightness control.")
                        break
                    
                    time.sleep(30)  # Check every 30 seconds
                    
                except KeyboardInterrupt:
                    logging.info("Service stopped by user")
                    return
                except Exception as e:
                    logging.error(f"Unexpected error: {e}")
                    time.sleep(60)
        
        lat, lon = self.get_location()
        if not lat or not lon:
            logging.error("Could not determine location. Please set latitude and longitude in config.")
            return
        
        logging.info(f"Location: {lat:.2f}, {lon:.2f}")
        
        displays = self.get_displays(force_refresh=True)
        if not displays:
            logging.error("No displays found")
            return
        
        logging.info(f"Found displays: {displays}")

        # Validate monitor offsets - warn about offsets for non-existent monitors
        offsets = self.config.get("monitor_offsets", {})
        # Build list of valid labels
        valid_labels = [self._get_monitor_label(d) for d in displays]
        for offset_key in offsets.keys():
            # Check if offset key matches any display ID or label
            if offset_key not in displays and offset_key not in valid_labels:
                logging.warning(f"Monitor offset configured for '{offset_key}' but display not found. "
                              f"Available displays: {displays}, labels: {valid_labels}")

        # Ensure proper contrast on all displays at startup
        logging.info("Checking and adjusting contrast levels for optimal brightness visibility...")
        for display in displays:
            self.ensure_proper_contrast(display)
        
        # Track iterations to periodically re-check contrast
        iteration_count = 0
        
        while True:
            try:
                # Reload config each iteration to check for changes
                self.config = self.load_config()

                # Check if auto brightness was disabled
                if not self.config.get("auto_brightness_enabled", True):
                    logging.info("Auto brightness disabled. Pausing automatic adjustments.")
                    time.sleep(30)
                    continue

                # Refresh display list each iteration to handle KDE renumbering
                new_displays = self.get_displays()
                if new_displays != displays:
                    logging.info(f"Display list changed: {displays} -> {new_displays}")
                    displays = new_displays

                # Update location if it changed
                new_lat, new_lon = self.get_location()
                if new_lat != lat or new_lon != lon:
                    lat, lon = new_lat, new_lon
                    logging.info(f"Location updated: {lat:.2f}, {lon:.2f}")
                
                # Check for fullscreen windows if enabled
                fullscreen_enabled = self.config.get("fullscreen_brightness_enabled", False)
                fullscreen_brightness = self.config.get("fullscreen_brightness", 1.0)
                fullscreen_poll_interval = 30  # Check fullscreen every 30 seconds

                sunrise, sunset = self.get_sun_times(lat, lon)
                if sunrise and sunset:
                    brightness = self.calculate_brightness(sunrise, sunset)

                    # If fullscreen detection is enabled, poll more frequently
                    if fullscreen_enabled:
                        polls_per_update = self.config["update_interval"] // fullscreen_poll_interval
                        logging.info(f"Fullscreen detection enabled, polling {polls_per_update} times")
                        for poll in range(max(1, polls_per_update)):
                            # Reload config to catch changes
                            self.config = self.load_config()
                            if not self.config.get("fullscreen_brightness_enabled", False):
                                break

                            fullscreen_monitors = self.get_fullscreen_monitors()

                            if fullscreen_monitors:
                                logging.debug(f"Fullscreen detected on outputs: {fullscreen_monitors}, mapping: {self._output_to_kde_map}")

                            targets = {}
                            for display in displays:
                                has_fs = self._monitor_has_fullscreen(display, fullscreen_monitors)
                                if has_fs:
                                    logging.debug(f"Setting {display} to fullscreen brightness {fullscreen_brightness}")
                                    targets[display] = fullscreen_brightness
                                else:
                                    targets[display] = brightness
                            self.set_brightness_targets(targets)

                            time.sleep(fullscreen_poll_interval)
                    else:
                        # Normal mode - just set brightness and wait
                        self.set_brightness_targets({display: brightness for display in displays})
                        logging.info(f"Updated brightness to {brightness:.2f}")
                        time.sleep(self.config["update_interval"])
                else:
                    logging.warning("Could not get sun times, skipping update")
                    time.sleep(self.config["update_interval"])

                # Periodically re-check contrast levels (every 10 iterations ~ every hour at 5min intervals)
                iteration_count += 1
                if iteration_count % 10 == 0:
                    logging.debug("Periodic contrast check...")
                    for display in displays:
                        self.ensure_proper_contrast(display)
                
            except KeyboardInterrupt:
                logging.info("Service stopped by user")
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                time.sleep(60)

if __name__ == "__main__":
    service = AutoBrightnessService()
    service.run()