#!/usr/bin/env python3

import subprocess
import json
import logging
import re
from typing import Dict, List, Optional, Tuple, Any


class KDEScreenBrightness:
    """KDE PowerDevil ScreenBrightness DBus interface for monitor control.

    This uses the same interface as KDE Plasma's brightness controls,
    which can access monitors that ddcutil cannot detect.
    """

    DBUS_SERVICE = "org.kde.ScreenBrightness"
    DBUS_PATH = "/org/kde/ScreenBrightness"
    DBUS_PATH_PREFIX = "/org/kde/ScreenBrightness/display"
    DBUS_INTERFACE = "org.kde.ScreenBrightness.Display"

    def __init__(self):
        self.monitors = {}
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('KDEScreenBrightness')

    def _call_dbus(self, display_index: int, method: str, *args) -> Optional[str]:
        """Call a DBus method on a display"""
        path = f"{self.DBUS_PATH_PREFIX}{display_index}"
        cmd = ['qdbus', self.DBUS_SERVICE, path, method] + [str(a) for a in args]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            self.logger.error(f"DBus call failed: {e}")
            return None

    def _get_property(self, display_index: int, property_name: str) -> Optional[str]:
        """Get a DBus property from a display"""
        path = f"{self.DBUS_PATH_PREFIX}{display_index}"
        cmd = ['qdbus', self.DBUS_SERVICE, path,
               'org.freedesktop.DBus.Properties.Get',
               self.DBUS_INTERFACE, property_name]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            self.logger.error(f"DBus property get failed: {e}")
            return None

    def is_available(self) -> bool:
        """Check if KDE ScreenBrightness interface is available"""
        try:
            result = subprocess.run(
                ['qdbus', self.DBUS_SERVICE, self.DBUS_PATH, 'org.kde.ScreenBrightness.DisplaysDBusNames'],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0 and result.stdout.strip()
        except Exception:
            return False

    def _get_display_names(self) -> list:
        """Get list of display names from KDE ScreenBrightness"""
        try:
            result = subprocess.run(
                ['qdbus', self.DBUS_SERVICE, self.DBUS_PATH, 'org.kde.ScreenBrightness.DisplaysDBusNames'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return [name.strip() for name in result.stdout.strip().split('\n') if name.strip()]
        except Exception as e:
            self.logger.error(f"Failed to get display names: {e}")
        return []

    def detect_monitors(self) -> Dict[str, Dict[str, Any]]:
        """Detect all monitors via KDE ScreenBrightness interface"""
        monitors = {}

        # Get actual display names from KDE (e.g., display1, display2, display4)
        display_names = self._get_display_names()

        for display_name in display_names:
            # Extract the index from display name (e.g., "display1" -> 1)
            try:
                idx = int(display_name.replace('display', ''))
            except ValueError:
                continue

            label = self._get_property(idx, "Label")
            if label is None:
                continue

            max_brightness = self._get_property(idx, "MaxBrightness")
            brightness = self._get_property(idx, "Brightness")

            monitor_id = f"kde_{idx}"
            monitors[monitor_id] = {
                'display_num': str(idx),
                'kde_index': idx,
                'model': label,
                'label': label,
                'max_brightness': int(max_brightness) if max_brightness else 10000,
                'brightness': int(brightness) if brightness else 0,
                'backend': 'kde',
                'capabilities': {
                    'features': {
                        '10': {'name': 'Brightness', 'values': {}}
                    }
                }
            }
            self.logger.info(f"Found KDE display {idx}: {label}")

        self.monitors = monitors
        return monitors

    def get_brightness(self, monitor_id: str) -> Optional[int]:
        """Get brightness for a monitor (returns 0-100)"""
        if monitor_id not in self.monitors:
            return None

        kde_index = self.monitors[monitor_id]['kde_index']
        max_val = self.monitors[monitor_id]['max_brightness']

        brightness = self._get_property(kde_index, "Brightness")
        if brightness is not None:
            # Convert from 0-max_brightness to 0-100
            return int(int(brightness) * 100 / max_val)
        return None

    def set_brightness(self, monitor_id: str, brightness_percent: int) -> bool:
        """Set brightness for a monitor (0-100)"""
        if monitor_id not in self.monitors:
            self.logger.error(f"Monitor {monitor_id} not found")
            return False

        kde_index = self.monitors[monitor_id]['kde_index']
        max_val = self.monitors[monitor_id]['max_brightness']

        # Convert from 0-100 to 0-max_brightness
        brightness_value = int(brightness_percent * max_val / 100)

        # Call SetBrightness(int brightness, uint flags)
        # flags=0 means normal brightness change
        path = f"{self.DBUS_PATH_PREFIX}{kde_index}"
        cmd = ['qdbus', self.DBUS_SERVICE, path,
               f'{self.DBUS_INTERFACE}.SetBrightness',
               str(brightness_value), '0']

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.logger.info(f"Set brightness to {brightness_percent}% on {monitor_id}")
                return True
            else:
                self.logger.error(f"Failed to set brightness: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to set brightness: {e}")
            return False


class RawDDCIMonitorControl:
    """Raw I2C DDC/CI control for monitors that ddcutil can't auto-detect.

    Some NVIDIA GPU/driver combinations don't expose a DRM connector-to-i2c
    mapping in sysfs, causing ddcutil to skip monitors that are otherwise
    fully DDC/CI capable.  This class probes NVIDIA i2c adapters directly
    and talks DDC/CI over raw I2C.
    """

    DDC_ADDR = 0x37       # DDC/CI slave address
    EDID_ADDR = 0x50      # EDID slave address
    I2C_SLAVE = 0x0703    # ioctl request code

    def __init__(self):
        self.monitors = {}  # bus_str -> monitor info
        self.logger = logging.getLogger('RawDDCI')

    # ---- low-level helpers ------------------------------------------------

    @staticmethod
    def _open_bus(bus: int):
        import fcntl, os as _os
        fd = _os.open(f'/dev/i2c-{bus}', _os.O_RDWR)
        return fd

    def _probe_ddc(self, bus: int) -> bool:
        """Return True if DDC/CI address responds on *bus*."""
        import fcntl, os as _os
        try:
            fd = self._open_bus(bus)
            try:
                fcntl.ioctl(fd, self.I2C_SLAVE, self.DDC_ADDR)
                # Try a tiny read — will raise OSError if nothing there
                _os.read(fd, 1)
                return True
            except OSError:
                return False
            finally:
                _os.close(fd)
        except OSError:
            return False

    def _read_edid_name(self, bus: int) -> Optional[str]:
        """Read the product name from EDID on *bus*."""
        import fcntl, os as _os
        try:
            fd = self._open_bus(bus)
            try:
                fcntl.ioctl(fd, self.I2C_SLAVE, self.EDID_ADDR)
                _os.write(fd, bytes([0]))
                edid = _os.read(fd, 128)
                # Search descriptor area for 0x00 0x00 0xFC (product name tag)
                for i in range(54, 110):
                    if edid[i] == 0x00 and edid[i + 1] == 0x00 and edid[i + 2] == 0xFC:
                        raw = edid[i + 4:i + 17]
                        return raw.decode('ascii', errors='replace').strip().rstrip('\x00')
            finally:
                _os.close(fd)
        except Exception:
            pass
        return None

    # ---- DDC/CI VCP protocol ---------------------------------------------

    def _vcp_get(self, bus: int, feature: int) -> Optional[Tuple[int, int]]:
        """Read a VCP feature.  Returns (current, max) or None."""
        import fcntl, os as _os, time as _time
        fd = self._open_bus(bus)
        try:
            fcntl.ioctl(fd, self.I2C_SLAVE, self.DDC_ADDR)
            length = 0x82  # 0x80 | 2
            cmd = 0x01     # VCP Get
            chk = 0x6E ^ 0x51 ^ length ^ cmd ^ feature
            _os.write(fd, bytes([0x51, length, cmd, feature, chk]))
            _time.sleep(0.05)
            resp = _os.read(fd, 12)
            if len(resp) >= 10 and resp[2] == 0x02 and resp[3] == 0x00:
                max_val = (resp[6] << 8) | resp[7]
                cur_val = (resp[8] << 8) | resp[9]
                return cur_val, max_val
        except Exception as e:
            self.logger.debug(f"VCP get 0x{feature:02x} on bus {bus} failed: {e}")
        finally:
            _os.close(fd)
        return None

    def _vcp_set(self, bus: int, feature: int, value: int) -> bool:
        """Write a VCP feature value."""
        import fcntl, os as _os, time as _time
        fd = self._open_bus(bus)
        try:
            fcntl.ioctl(fd, self.I2C_SLAVE, self.DDC_ADDR)
            length = 0x84  # 0x80 | 4
            cmd = 0x03     # VCP Set
            val_hi = (value >> 8) & 0xFF
            val_lo = value & 0xFF
            chk = 0x6E ^ 0x51 ^ length ^ cmd ^ feature ^ val_hi ^ val_lo
            _os.write(fd, bytes([0x51, length, cmd, feature, val_hi, val_lo, chk]))
            _time.sleep(0.05)
            return True
        except Exception as e:
            self.logger.debug(f"VCP set 0x{feature:02x}={value} on bus {bus} failed: {e}")
            return False
        finally:
            _os.close(fd)

    # ---- public API -------------------------------------------------------

    def detect_unmapped_monitors(self, known_buses: set) -> Dict[str, Dict[str, Any]]:
        """Scan NVIDIA i2c adapters not in *known_buses* for DDC-capable monitors."""
        monitors = {}
        try:
            import os as _os
            sysfs = '/sys/bus/i2c/devices'
            for entry in sorted(_os.listdir(sysfs)):
                if not entry.startswith('i2c-'):
                    continue
                bus = int(entry.split('-')[1])
                if str(bus) in known_buses:
                    continue
                # Only probe NVIDIA adapters
                try:
                    name_path = _os.path.join(sysfs, entry, 'name')
                    with open(name_path) as f:
                        adapter_name = f.read().strip()
                    if 'NVIDIA' not in adapter_name:
                        continue
                except Exception:
                    continue

                if not self._probe_ddc(bus):
                    continue

                product = self._read_edid_name(bus) or f'Unknown (i2c-{bus})'
                result = self._vcp_get(bus, 0x10)  # brightness
                if result is None:
                    continue

                bus_str = str(bus)
                monitors[bus_str] = {
                    'display_num': bus_str,
                    'i2c_bus': bus_str,
                    'model': product,
                    'label': product,
                    'backend': 'raw_ddc',
                    'max_brightness': result[1],
                    'brightness': result[0],
                    'capabilities': {
                        'features': {
                            '10': {'name': 'Brightness', 'values': {}}
                        }
                    }
                }
                self.logger.info(f"Found unmapped DDC monitor on i2c-{bus}: {product}")
        except Exception as e:
            self.logger.debug(f"Unmapped monitor scan failed: {e}")

        self.monitors.update(monitors)
        return monitors

    def get_brightness(self, bus_str: str) -> Optional[int]:
        result = self._vcp_get(int(bus_str), 0x10)
        return result[0] if result else None

    def set_brightness(self, bus_str: str, brightness_percent: int) -> bool:
        ok = self._vcp_set(int(bus_str), 0x10, brightness_percent)
        if ok:
            self.logger.info(f"Set VCP feature 10 to {brightness_percent} on bus {bus_str} (raw)")
        return ok


class DDCIMonitorControl:
    """DDC/CI Monitor Control System"""
    
    def __init__(self):
        self.monitors = {}
        self.vcp_features = {}
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for DDC/CI operations"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('DDCIControl')
    
    def detect_monitors(self) -> Dict[str, Dict[str, Any]]:
        """Detect all available monitors and their capabilities"""
        try:
            result = subprocess.run(
                ['ddcutil', 'detect', '--brief'], 
                capture_output=True, text=True, check=True
            )
            
            monitors = {}
            current_monitor = None
            
            for line in result.stdout.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                # Parse display information
                if line.startswith('Display'):
                    display_match = re.search(r'Display (\d+)', line)
                    if display_match:
                        current_monitor = display_match.group(1)
                        monitors[current_monitor] = {
                            'display_num': current_monitor,
                            'i2c_bus': None,
                            'model': 'Unknown',
                            'capabilities': {}
                        }
                
                elif current_monitor and 'I2C bus:' in line:
                    i2c_match = re.search(r'/dev/i2c-(\d+)', line)
                    if i2c_match:
                        monitors[current_monitor]['i2c_bus'] = i2c_match.group(1)
                
                elif current_monitor and 'Monitor:' in line:
                    model_match = re.search(r'Monitor:\s*(.+)', line)
                    if model_match:
                        model_raw = model_match.group(1).strip()
                        monitors[current_monitor]['model'] = model_raw
                        # Extract clean product name from "MFG:Product Name:Serial"
                        parts = model_raw.split(':')
                        if len(parts) >= 2 and parts[1].strip():
                            monitors[current_monitor]['label'] = parts[1].strip()
                        else:
                            monitors[current_monitor]['label'] = model_raw
            
            # Get capabilities for each monitor
            for monitor_id, monitor_info in monitors.items():
                if monitor_info['i2c_bus']:
                    capabilities = self.get_monitor_capabilities(monitor_info['i2c_bus'])
                    monitors[monitor_id]['capabilities'] = capabilities
            
            self.monitors = monitors
            return monitors
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to detect monitors: {e}")
            return {}
    
    def get_monitor_capabilities(self, bus: str) -> Dict[str, Any]:
        """Get DDC/CI capabilities for a specific monitor"""
        try:
            result = subprocess.run(
                ['ddcutil', '--bus', bus, 'capabilities'],
                capture_output=True, text=True, check=True
            )
            
            capabilities = {
                'model': 'Unknown',
                'mccs_version': 'Unknown',
                'features': {}
            }
            
            current_feature = None
            
            for line in result.stdout.split('\n'):
                line = line.strip()
                
                # Parse model
                if line.startswith('Model:'):
                    capabilities['model'] = line.split(':', 1)[1].strip()
                
                # Parse MCCS version
                elif line.startswith('MCCS version:'):
                    capabilities['mccs_version'] = line.split(':', 1)[1].strip()
                
                # Parse VCP features
                elif line.startswith('Feature:'):
                    feature_match = re.search(r'Feature:\s*([0-9A-Fa-f]+)\s*\((.+?)\)', line)
                    if feature_match:
                        feature_code = feature_match.group(1).upper()
                        feature_name = feature_match.group(2)
                        current_feature = feature_code
                        capabilities['features'][feature_code] = {
                            'name': feature_name,
                            'values': {}
                        }
                
                # Parse feature values
                elif current_feature and line and 'Values:' not in line:
                    value_match = re.search(r'([0-9A-Fa-f]+):\s*(.+)', line)
                    if value_match:
                        value_code = value_match.group(1).upper()
                        value_name = value_match.group(2)
                        capabilities['features'][current_feature]['values'][value_code] = value_name
            
            return capabilities
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to get capabilities for bus {bus}: {e}")
            return {}
    
    def get_vcp_value(self, bus: str, feature_code: str) -> Optional[int]:
        """Get current value of a VCP feature"""
        try:
            result = subprocess.run(
                ['ddcutil', '--bus', bus, 'getvcp', feature_code],
                capture_output=True, text=True, check=True
            )
            
            # Parse the output to extract current value
            for line in result.stdout.split('\n'):
                if 'current value' in line.lower():
                    value_match = re.search(r'current value\s*=\s*(\d+)', line)
                    if value_match:
                        return int(value_match.group(1))
            
            return None
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to get VCP value for feature {feature_code} on bus {bus}: {e}")
            return None
    
    def set_vcp_value(self, bus: str, feature_code: str, value: int) -> bool:
        """Set value of a VCP feature"""
        try:
            subprocess.run(
                ['ddcutil', '--bus', bus, 'setvcp', feature_code, str(value)],
                capture_output=True, text=True, check=True
            )
            self.logger.info(f"Set VCP feature {feature_code} to {value} on bus {bus}")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to set VCP feature {feature_code} to {value} on bus {bus}: {e}")
            return False
    
    def set_brightness(self, bus: str, brightness_percent: int) -> bool:
        """Set monitor brightness (0-100%)"""
        return self.set_vcp_value(bus, '10', brightness_percent)
    
    def get_brightness(self, bus: str) -> Optional[int]:
        """Get current monitor brightness"""
        return self.get_vcp_value(bus, '10')
    
    def set_contrast(self, bus: str, contrast_percent: int) -> bool:
        """Set monitor contrast (0-100%)"""
        return self.set_vcp_value(bus, '12', contrast_percent)
    
    def get_contrast(self, bus: str) -> Optional[int]:
        """Get current monitor contrast"""
        return self.get_vcp_value(bus, '12')
    
    def set_input_source(self, bus: str, input_code: str) -> bool:
        """Set monitor input source"""
        try:
            input_value = int(input_code, 16)
            return self.set_vcp_value(bus, '60', input_value)
        except ValueError:
            self.logger.error(f"Invalid input source code: {input_code}")
            return False
    
    def get_input_source(self, bus: str) -> Optional[str]:
        """Get current monitor input source"""
        value = self.get_vcp_value(bus, '60')
        if value is not None:
            return f"{value:02X}"
        return None
    
    def set_color_preset(self, bus: str, preset_code: str) -> bool:
        """Set monitor color preset"""
        try:
            preset_value = int(preset_code, 16)
            return self.set_vcp_value(bus, '14', preset_value)
        except ValueError:
            self.logger.error(f"Invalid color preset code: {preset_code}")
            return False
    
    def get_color_preset(self, bus: str) -> Optional[str]:
        """Get current monitor color preset"""
        value = self.get_vcp_value(bus, '14')
        if value is not None:
            return f"{value:02X}"
        return None
    
    def set_power_mode(self, bus: str, power_code: str) -> bool:
        """Set monitor power mode"""
        try:
            power_value = int(power_code, 16)
            return self.set_vcp_value(bus, 'D6', power_value)
        except ValueError:
            self.logger.error(f"Invalid power mode code: {power_code}")
            return False
    
    def get_supported_features(self, bus: str) -> Dict[str, Any]:
        """Get all supported features for a monitor"""
        for monitor_id, monitor_info in self.monitors.items():
            if monitor_info['i2c_bus'] == bus:
                return monitor_info.get('capabilities', {}).get('features', {})
        return {}
    
    def export_monitor_config(self, bus: str) -> Dict[str, Any]:
        """Export current monitor configuration"""
        config = {
            'bus': bus,
            'settings': {}
        }
        
        features = self.get_supported_features(bus)
        for feature_code, feature_info in features.items():
            current_value = self.get_vcp_value(bus, feature_code)
            if current_value is not None:
                config['settings'][feature_code] = {
                    'name': feature_info['name'],
                    'value': current_value
                }
        
        return config
    
    def import_monitor_config(self, config: Dict[str, Any]) -> bool:
        """Import monitor configuration"""
        bus = config.get('bus')
        settings = config.get('settings', {})
        
        if not bus:
            self.logger.error("No bus specified in configuration")
            return False
        
        success = True
        for feature_code, setting in settings.items():
            value = setting.get('value')
            if value is not None:
                if not self.set_vcp_value(bus, feature_code, value):
                    success = False

        return success


class HybridMonitorControl:
    """Hybrid monitor control using KDE ScreenBrightness (preferred) + DDC/CI fallback.

    This class provides access to all monitors by:
    1. Using KDE's ScreenBrightness DBus interface (works for all monitors KDE can see)
    2. Falling back to DDC/CI for advanced VCP controls not available via KDE
    """

    def __init__(self):
        self.kde = KDEScreenBrightness()
        self.ddc = DDCIMonitorControl()
        self.raw_ddc = RawDDCIMonitorControl()
        self.monitors = {}
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('HybridMonitorControl')

    def detect_monitors(self) -> Dict[str, Dict[str, Any]]:
        """Detect monitors using KDE interface (preferred) with DDC fallback"""
        monitors = {}

        # Try KDE first - it can see all monitors
        if self.kde.is_available():
            kde_monitors = self.kde.detect_monitors()
            for mid, minfo in kde_monitors.items():
                monitors[mid] = minfo
            self.logger.info(f"Found {len(kde_monitors)} monitors via KDE ScreenBrightness")

        # Also detect via DDC for additional VCP features
        ddc_monitors = self.ddc.detect_monitors()

        # Map DDC monitors to KDE monitors by matching model names
        for kde_id, kde_info in monitors.items():
            kde_label = kde_info.get('label', '').lower()
            for ddc_id, ddc_info in ddc_monitors.items():
                ddc_model = ddc_info.get('model', '').lower()
                # Check if models match (partial match)
                if any(part in kde_label for part in ddc_model.split(':') if len(part) > 3):
                    # Merge DDC capabilities into KDE monitor
                    monitors[kde_id]['i2c_bus'] = ddc_info.get('i2c_bus')
                    monitors[kde_id]['ddc_available'] = True
                    if ddc_info.get('capabilities'):
                        monitors[kde_id]['capabilities'] = ddc_info['capabilities']
                    self.logger.info(f"Linked KDE monitor {kde_id} to DDC bus {ddc_info.get('i2c_bus')}")
                    break

        # If KDE not available, use DDC monitors directly
        if not monitors:
            for ddc_id, ddc_info in ddc_monitors.items():
                monitors[ddc_id] = ddc_info
                monitors[ddc_id]['backend'] = 'ddc'

        # Scan for unmapped monitors (DDC-capable but invisible to ddcutil)
        known_buses = {m.get('i2c_bus') for m in monitors.values() if m.get('i2c_bus')}
        raw_monitors = self.raw_ddc.detect_unmapped_monitors(known_buses)
        for mid, minfo in raw_monitors.items():
            monitors[mid] = minfo
        if raw_monitors:
            self.logger.info(f"Found {len(raw_monitors)} additional monitor(s) via raw I2C probe")

        self.monitors = monitors
        return monitors

    def get_brightness(self, monitor_id: str) -> Optional[int]:
        """Get brightness using appropriate backend"""
        if monitor_id not in self.monitors:
            return None

        monitor = self.monitors[monitor_id]

        # Prefer KDE backend
        if monitor.get('backend') == 'kde':
            return self.kde.get_brightness(monitor_id)

        # Raw DDC (unmapped monitors)
        if monitor.get('backend') == 'raw_ddc':
            return self.raw_ddc.get_brightness(monitor.get('i2c_bus', monitor_id))

        # Fall back to ddcutil DDC
        bus = monitor.get('i2c_bus')
        if bus:
            return self.ddc.get_brightness(bus)

        return None

    def set_brightness(self, monitor_id: str, brightness_percent: int) -> bool:
        """Set brightness using appropriate backend"""
        if monitor_id not in self.monitors:
            self.logger.error(f"Monitor {monitor_id} not found")
            return False

        monitor = self.monitors[monitor_id]

        # Prefer KDE backend
        if monitor.get('backend') == 'kde':
            return self.kde.set_brightness(monitor_id, brightness_percent)

        # Raw DDC (unmapped monitors)
        if monitor.get('backend') == 'raw_ddc':
            return self.raw_ddc.set_brightness(monitor.get('i2c_bus', monitor_id), brightness_percent)

        # Fall back to ddcutil DDC
        bus = monitor.get('i2c_bus')
        if bus:
            return self.ddc.set_brightness(bus, brightness_percent)

        return False

    def set_vcp_value(self, monitor_id: str, feature_code: str, value: int) -> bool:
        """Set VCP value - brightness uses KDE, others use DDC"""
        if monitor_id not in self.monitors:
            return False

        monitor = self.monitors[monitor_id]

        # For brightness (VCP 10), prefer KDE
        if feature_code == '10':
            if monitor.get('backend') == 'kde':
                return self.kde.set_brightness(monitor_id, value)
            if monitor.get('backend') == 'raw_ddc':
                return self.raw_ddc.set_brightness(monitor.get('i2c_bus', monitor_id), value)

        # For other VCP codes, use DDC if available
        bus = monitor.get('i2c_bus')
        if bus and monitor.get('backend') != 'raw_ddc':
            return self.ddc.set_vcp_value(bus, feature_code, value)

        # If no DDC but KDE and brightness, use KDE
        if feature_code == '10' and monitor.get('backend') == 'kde':
            return self.kde.set_brightness(monitor_id, value)

        self.logger.warning(f"Cannot set VCP {feature_code} on {monitor_id} - no DDC available")
        return False

    def get_vcp_value(self, monitor_id: str, feature_code: str) -> Optional[int]:
        """Get VCP value"""
        if monitor_id not in self.monitors:
            return None

        monitor = self.monitors[monitor_id]

        # For brightness, prefer KDE
        if feature_code == '10' and monitor.get('backend') == 'kde':
            return self.kde.get_brightness(monitor_id)

        # Raw DDC
        if feature_code == '10' and monitor.get('backend') == 'raw_ddc':
            return self.raw_ddc.get_brightness(monitor.get('i2c_bus', monitor_id))

        # For other VCP codes, use ddcutil DDC
        bus = monitor.get('i2c_bus')
        if bus and monitor.get('backend') != 'raw_ddc':
            return self.ddc.get_vcp_value(bus, feature_code)

        return None

    def get_monitor_capabilities(self, monitor_id: str) -> Dict[str, Any]:
        """Get capabilities for a monitor"""
        if monitor_id not in self.monitors:
            return {}

        monitor = self.monitors[monitor_id]

        # If DDC is available, get full capabilities
        bus = monitor.get('i2c_bus')
        if bus:
            return self.ddc.get_monitor_capabilities(bus)

        # Otherwise return basic brightness capability
        return monitor.get('capabilities', {})