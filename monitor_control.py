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
                        monitors[current_monitor]['model'] = model_match.group(1).strip()
            
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

        # Fall back to DDC
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

        # Fall back to DDC
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

        # For other VCP codes, use DDC if available
        bus = monitor.get('i2c_bus')
        if bus:
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

        # For other VCP codes, use DDC
        bus = monitor.get('i2c_bus')
        if bus:
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