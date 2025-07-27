#!/usr/bin/env python3

import sys
import os
import json
import threading
import time

# Set environment variables for Qt6 and GPU acceleration
os.environ['QT_QPA_PLATFORM'] = 'xcb'
# Enable hardware acceleration - remove software rendering for GPU acceleration
os.environ['QSG_RHI_BACKEND'] = 'opengl'  # Use OpenGL for GPU acceleration
os.environ['QSG_RHI_DEBUG_LAYER'] = '0'  # Disable debug layer for performance
os.environ['QML_DISABLE_DISK_CACHE'] = '0'  # Enable disk cache for better performance
os.environ['QML_USE_GLYPHCACHE_WORKAROUND'] = '0'  # Disable glyph cache workaround
# GPU acceleration optimizations
os.environ['QT_OPENGL_BUGLIST'] = '0'  # Disable OpenGL bug workarounds
os.environ['QT_QUICK_CONTROLS_HOVER_ENABLED'] = '1'  # Enable hardware hover effects
os.environ['QSG_RENDER_LOOP'] = 'threaded'  # Use threaded render loop for better performance

# Import Qt6 instead of Qt5
try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtQml import QQmlApplicationEngine, qmlRegisterType
    from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, pyqtProperty, QUrl
    from PyQt6.QtGui import QIcon
    QT_VERSION = 6
except ImportError:
    print("PyQt6 not available, falling back to PyQt5")
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtQml import QQmlApplicationEngine, qmlRegisterType
    from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, pyqtProperty, QUrl
    from PyQt5.QtGui import QIcon
    QT_VERSION = 5

from monitor_control import DDCIMonitorControl

class BrightnessController(QObject):
    """Backend controller for brightness and monitor management"""
    
    # Signals for QML
    configChanged = pyqtSignal()
    statusChanged = pyqtSignal(str, str)  # message, type
    monitorsChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Try local config first, then system config
        local_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if os.path.exists(local_config):
            self.config_path = local_config
        else:
            self.config_path = "/etc/monitor-remote-control/config.json"
        self._config = self.load_config()
        self.monitor_control = DDCIMonitorControl()
        self._monitors = {}
        self._current_monitor = None
        
        # Auto-refresh monitors (less frequent for better performance)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_monitors)
        self.refresh_timer.start(120000)  # Refresh every 2 minutes instead of 30 seconds
        
        # Cache for VCP definitions to avoid recreating them
        self._vcp_definitions_cache = None
        
        # Cache for monitor values to reduce ddcutil calls
        self._value_cache = {}
        self._cache_timer = QTimer()
        self._cache_timer.timeout.connect(self._clear_value_cache)
        self._cache_timer.start(5000)  # Clear cache every 5 seconds
        
        # Initial monitor detection
        self.refresh_monitors()
    
    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "min_brightness": 0.3, 
                "max_brightness": 1.0,
                "auto_brightness_enabled": True,
                "latitude": None,
                "longitude": None
            }
    
    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
            self.configChanged.emit()
        except Exception as e:
            self.statusChanged.emit(f"Error saving config: {e}", "error")
    
    # Properties for QML binding
    @pyqtProperty(float, notify=configChanged)
    def minBrightness(self):
        return self._config.get("min_brightness", 0.3) * 100
    
    @minBrightness.setter
    def minBrightness(self, value):
        self._config["min_brightness"] = value / 100
        self.save_config()
        self.configChanged.emit()
    
    @pyqtProperty(float, notify=configChanged)
    def maxBrightness(self):
        return self._config.get("max_brightness", 1.0) * 100
    
    @maxBrightness.setter
    def maxBrightness(self, value):
        self._config["max_brightness"] = value / 100
        self.save_config()
        self.configChanged.emit()
    
    @pyqtProperty(bool, notify=configChanged)
    def autoBrightnessEnabled(self):
        return self._config.get("auto_brightness_enabled", True)
    
    @autoBrightnessEnabled.setter 
    def autoBrightnessEnabled(self, value):
        self._config["auto_brightness_enabled"] = value
        self.save_config()
        self.configChanged.emit()
    
    @pyqtProperty(bool, notify=configChanged)
    def locationOverride(self):
        return bool(self._config.get("latitude") and self._config.get("longitude"))
    
    @pyqtProperty(str, notify=configChanged)
    def latitude(self):
        lat = self._config.get("latitude", "")
        return str(lat) if lat is not None else ""
    
    @latitude.setter
    def latitude(self, value):
        try:
            # Only validate if user enters something
            if value and value.strip():
                lat = float(value.strip())
                if not (-90 <= lat <= 90):
                    self.statusChanged.emit("Latitude must be between -90 and 90", "error")
                    return
                self._config["latitude"] = lat
            else:
                self._config["latitude"] = None
            self.save_config()
        except ValueError:
            if value and value.strip():  # Only show error if user actually entered something
                self.statusChanged.emit("Invalid latitude format", "error")
    
    @pyqtProperty(str, notify=configChanged)
    def longitude(self):
        lon = self._config.get("longitude", "")
        return str(lon) if lon is not None else ""
    
    @longitude.setter
    def longitude(self, value):
        try:
            # Only validate if user enters something
            if value and value.strip():
                lon = float(value.strip())
                if not (-180 <= lon <= 180):
                    self.statusChanged.emit("Longitude must be between -180 and 180", "error")
                    return
                self._config["longitude"] = lon
            else:
                self._config["longitude"] = None
            self.save_config()
        except ValueError:
            if value and value.strip():  # Only show error if user actually entered something
                self.statusChanged.emit("Invalid longitude format", "error")
    
    @pyqtProperty('QVariant', notify=monitorsChanged)
    def monitors(self):
        return list(self._monitors.values())
    
    @pyqtProperty(str, notify=monitorsChanged)
    def currentMonitor(self):
        return self._current_monitor or ""
    
    @currentMonitor.setter
    def currentMonitor(self, monitor_id):
        print(f"DEBUG: Setting current monitor to: {monitor_id}")
        self._current_monitor = monitor_id
        self.detectMonitorCapabilities()
        self.monitorsChanged.emit()
    
    @pyqtProperty('QVariant', notify=monitorsChanged)
    def currentMonitorCapabilities(self):
        if self._current_monitor and self._current_monitor in self._monitors:
            caps = self._monitors[self._current_monitor].get('capabilities', [])
            return caps
        return []
    
    @pyqtProperty('QVariant', notify=monitorsChanged)
    def currentMonitorFeatures(self):
        if self._current_monitor and self._current_monitor in self._monitors:
            return self._monitors[self._current_monitor].get('features', {})
        return {}
    
    @pyqtSlot(str)
    def lookupCity(self, city_name):
        """Look up coordinates for a city name"""
        if not city_name or not city_name.strip():
            return
            
        self.statusChanged.emit(f"Looking up coordinates for {city_name}...", "info")
        
        def lookup_thread():
            try:
                import requests
                # Use a free geocoding service
                url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name.strip()}&count=1&language=en&format=json"
                response = requests.get(url, timeout=10)
                data = response.json()
                
                if data.get('results') and len(data['results']) > 0:
                    result = data['results'][0]
                    lat = result['latitude']
                    lon = result['longitude']
                    city = result['name']
                    country = result.get('country', '')
                    
                    # Update config on main thread
                    self._config["latitude"] = lat
                    self._config["longitude"] = lon
                    self.save_config()
                    
                    self.statusChanged.emit(f"Found {city}, {country}: {lat:.4f}, {lon:.4f}", "success")
                else:
                    self.statusChanged.emit(f"City '{city_name}' not found", "error")
                    
            except Exception as e:
                self.statusChanged.emit(f"Error looking up city: {e}", "error")
        
        threading.Thread(target=lookup_thread, daemon=True).start()
    
    def _clear_value_cache(self):
        """Clear the VCP value cache periodically"""
        self._value_cache.clear()
    
    @pyqtSlot()
    def detectMonitorCapabilities(self):
        """Detect capabilities for the current monitor"""
        if not self._current_monitor:
            return
            
        def detect_thread():
            try:
                # Get capabilities from monitor_control using i2c bus
                if self._current_monitor in self._monitors:
                    bus = self._monitors[self._current_monitor].get('bus')
                    if bus:
                        capabilities_data = self.monitor_control.get_monitor_capabilities(bus)
                        # Extract VCP feature codes
                        features = capabilities_data.get('features', {})
                        vcp_codes = list(features.keys())
                        
                        # Update monitor info on main thread
                        self._monitors[self._current_monitor]['capabilities'] = vcp_codes
                        self._monitors[self._current_monitor]['features'] = features
                        self.monitorsChanged.emit()
                        
            except Exception as e:
                print(f"Error detecting capabilities: {e}")
        
        threading.Thread(target=detect_thread, daemon=True).start()
    
    @pyqtSlot()
    def refresh_monitors(self):
        """Refresh the list of available monitors"""
        try:
            monitors_data = self.monitor_control.detect_monitors()
            self._monitors = {}
            
            for display_id, monitor_info in monitors_data.items():
                bus = monitor_info.get('i2c_bus')
                model = monitor_info.get('model', 'Unknown')
                capabilities_data = monitor_info.get('capabilities', {})
                
                # Extract VCP feature codes
                features = capabilities_data.get('features', {})
                vcp_codes = list(features.keys())
                
                self._monitors[display_id] = {
                    'id': display_id,
                    'name': f"{model} (Display {display_id})",
                    'bus': bus,
                    'capabilities': vcp_codes,
                    'features': features
                }
            
            if not self._current_monitor and self._monitors:
                self._current_monitor = list(self._monitors.keys())[0]
                print(f"DEBUG: Auto-selected first monitor: {self._current_monitor}")
            
            print(f"DEBUG: Monitors after refresh: {list(self._monitors.keys())}")
            for mid, minfo in self._monitors.items():
                print(f"  Monitor {mid}: {minfo['name']}, caps: {len(minfo.get('capabilities', []))}")
            
            self.monitorsChanged.emit()
        except Exception as e:
            print(f"Error refreshing monitors: {e}")
    
    @pyqtSlot()
    def restartService(self):
        """Restart the auto-brightness service"""
        self.statusChanged.emit("Restarting service...", "info")
        
        def restart_thread():
            try:
                import subprocess
                subprocess.run(['systemctl', '--user', 'restart', 'auto-brightness.service'], 
                             check=True, capture_output=True)
                self.statusChanged.emit("Service restarted successfully!", "success")
            except subprocess.CalledProcessError as e:
                self.statusChanged.emit("Error restarting service", "error")
        
        threading.Thread(target=restart_thread, daemon=True).start()
    
    @pyqtSlot(str, str, int)
    def setMonitorValue(self, monitor_id, vcp_code, value):
        """Set a VCP value for a monitor"""
        try:
            if monitor_id in self._monitors:
                bus = self._monitors[monitor_id].get('bus')
                if bus:
                    success = self.monitor_control.set_vcp_value(bus, vcp_code, value)
                    if success:
                        # Update cache with new value for immediate UI feedback
                        cache_key = f"{monitor_id}_{vcp_code}"
                        self._value_cache[cache_key] = value
                        self.statusChanged.emit(f"Set monitor {monitor_id} VCP {vcp_code} to {value}", "success")
                    else:
                        self.statusChanged.emit(f"Failed to set monitor {monitor_id} VCP {vcp_code}", "error")
                else:
                    self.statusChanged.emit(f"No bus found for monitor {monitor_id}", "error")
        except Exception as e:
            self.statusChanged.emit(f"Error setting monitor value: {e}", "error")
    
    @pyqtSlot(str, str, result=int)
    def getMonitorValue(self, monitor_id, vcp_code):
        """Get current VCP value for a monitor with caching"""
        cache_key = f"{monitor_id}_{vcp_code}"
        
        # Check cache first
        if cache_key in self._value_cache:
            return self._value_cache[cache_key]
        
        try:
            if monitor_id in self._monitors:
                bus = self._monitors[monitor_id].get('bus')
                if bus:
                    # Use a quick timeout to avoid hanging on problematic features
                    import subprocess
                    try:
                        result = subprocess.run(
                            ['ddcutil', '--bus', bus, 'getvcp', vcp_code],
                            capture_output=True, text=True, timeout=1, check=True  # Reduced timeout for responsiveness
                        )
                        # Parse the output to extract current value
                        for line in result.stdout.split('\n'):
                            if 'current value' in line.lower():
                                import re
                                value_match = re.search(r'current value\s*=\s*(\d+)', line)
                                if value_match:
                                    value = int(value_match.group(1))
                                    # Cache the result
                                    self._value_cache[cache_key] = value
                                    return value
                        # Cache zero result to avoid repeated failures
                        self._value_cache[cache_key] = 0
                        return 0
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                        # Cache zero result to avoid repeated failures
                        self._value_cache[cache_key] = 0
                        return 0
            self._value_cache[cache_key] = 0
            return 0
        except Exception as e:
            print(f"Error getting monitor value: {e}")
            self._value_cache[cache_key] = 0
            return 0
    
    def _get_vcp_definitions(self):
        """Get VCP definitions with caching"""
        if self._vcp_definitions_cache is not None:
            return self._vcp_definitions_cache
            
        # Cache the definitions for better performance
        vcp_definitions = {
            # Display Control
            '10': {'name': 'Brightness', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            '12': {'name': 'Contrast', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            '13': {'name': 'Backlight Control', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            '87': {'name': 'Sharpness', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            
            # Color Control
            '14': {'name': 'Color Preset', 'type': 'combo', 'values': {
                '1': 'sRGB', '2': 'Adobe RGB', '3': 'Wide Gamut', '4': 'Native', 
                '5': 'User 1', '6': 'User 2', '7': 'User 3', '8': '6500K', 
                '9': '7500K', '10': '9300K', '11': 'Custom'
            }},
            '16': {'name': 'Red Gain', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            '18': {'name': 'Green Gain', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            '1A': {'name': 'Blue Gain', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            '6C': {'name': 'Red Black Level', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '6E': {'name': 'Green Black Level', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '70': {'name': 'Blue Black Level', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '0B': {'name': 'Color Temperature Increment', 'type': 'stepper', 'min': 0, 'max': 20, 'suffix': ''},
            '0C': {'name': 'Color Temperature Request', 'type': 'combo', 'values': {
                '1': '3000K', '2': '4000K', '3': '5000K', '4': '6500K', '5': '7500K', '6': '9300K', '7': '10000K'
            }},
            '56': {'name': 'Hue', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '°'},
            '58': {'name': 'Saturation', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            '59': {'name': 'Color Curve Adjust', 'type': 'stepper', 'min': 0, 'max': 10, 'suffix': ''},
            '5A': {'name': 'Color LUT Size', 'type': 'readonly', 'min': 0, 'max': 65535, 'suffix': ' entries'},
            '5B': {'name': 'Single Point LUT Operation', 'type': 'combo', 'values': {
                '1': 'Upload Red', '2': 'Upload Green', '3': 'Upload Blue', '4': 'Upload All'
            }},
            '1F': {'name': 'Auto Setup', 'type': 'combo', 'values': {
                '1': 'Auto Setup Off', '2': 'Auto Setup On'
            }},
            '8A': {'name': 'Color Saturation', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            
            # Input Control
            '60': {'name': 'Input Source', 'type': 'combo', 'values': {
                '1': 'VGA 1', '2': 'VGA 2', '3': 'DVI 1', '4': 'DVI 2', 
                '15': 'DisplayPort 1', '16': 'DisplayPort 2', '17': 'HDMI 1', 
                '18': 'HDMI 2', '19': 'HDMI 3', '20': 'HDMI 4', '27': 'USB-C'
            }},
            '214': {'name': 'Power Mode', 'type': 'combo', 'values': {
                '1': 'On', '2': 'Standby', '4': 'Suspend', '5': 'Off'
            }},
            
            # Geometry Control
            '20': {'name': 'Horizontal Position', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '30': {'name': 'Vertical Position', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '22': {'name': 'Horizontal Size', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '32': {'name': 'Vertical Size', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '40': {'name': 'Horizontal Pincushion', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '42': {'name': 'Horizontal Pincushion Balance', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '41': {'name': 'Vertical Pincushion', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '43': {'name': 'Vertical Pincushion Balance', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '44': {'name': 'Horizontal Convergence R/B', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '45': {'name': 'Horizontal Convergence M/G', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '46': {'name': 'Vertical Convergence R/B', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '47': {'name': 'Vertical Convergence M/G', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '48': {'name': 'Horizontal Linearity', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '49': {'name': 'Horizontal Linearity Balance', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '4A': {'name': 'Vertical Linearity', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '4B': {'name': 'Vertical Linearity Balance', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '4C': {'name': 'Horizontal Misconvergence', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '4D': {'name': 'Vertical Misconvergence', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '4E': {'name': 'Horizontal Focus', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '4F': {'name': 'Vertical Focus', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': ''},
            '24': {'name': 'Horizontal Frequency', 'type': 'readonly', 'min': 0, 'max': 65535, 'suffix': ' Hz'},
            '33': {'name': 'Vertical Frequency', 'type': 'readonly', 'min': 0, 'max': 65535, 'suffix': ' Hz'},
            
            # Display Scaling & Overscan
            '86': {'name': 'Display Scaling', 'type': 'combo', 'values': {
                '1': 'No Scaling', '2': 'Max Image, No AR', '3': 'Max Image, AR', '4': 'Max Vertical Image', '5': 'Max Horizontal Image'
            }},
            '88': {'name': 'Horizontal Overscan', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': '%'},
            '89': {'name': 'Vertical Overscan', 'type': 'stepper', 'min': 0, 'max': 100, 'suffix': '%'},
            
            # Audio Control
            '8D': {'name': 'Audio Speaker Volume', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            '8F': {'name': 'Audio Microphone Volume', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            '62': {'name': 'Audio Mute', 'type': 'combo', 'values': {'1': 'Muted', '2': 'Unmuted'}},
            '63': {'name': 'Audio Treble', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            '64': {'name': 'Audio Bass', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            '65': {'name': 'Audio Balance L/R', 'type': 'slider', 'min': 0, 'max': 100, 'suffix': '%'},
            '66': {'name': 'Audio Processor Mode', 'type': 'combo', 'values': {
                '1': 'Speaker', '2': 'Headphone', '3': 'External Audio'
            }},
            
            # OSD Control
            'CA': {'name': 'OSD Language', 'type': 'combo', 'values': {
                '1': 'Chinese (Traditional)', '2': 'English', '3': 'French', '4': 'German', '5': 'Italian', 
                '6': 'Japanese', '7': 'Korean', '8': 'Portuguese', '9': 'Russian', '10': 'Spanish',
                '11': 'Swedish', '12': 'Turkish', '13': 'Chinese (Simplified)', '14': 'Portuguese (Brazil)',
                '15': 'Arabic', '16': 'Bulgarian', '17': 'Croatian', '18': 'Czech', '19': 'Danish',
                '20': 'Dutch', '21': 'Estonian', '22': 'Finnish', '23': 'Greek', '24': 'Hebrew',
                '25': 'Hindi', '26': 'Hungarian', '27': 'Latvian', '28': 'Lithuanian', '29': 'Norwegian',
                '30': 'Polish', '31': 'Romanian', '32': 'Serbian', '33': 'Slovak', '34': 'Slovenian',
                '35': 'Thai', '36': 'Ukrainian'
            }},
            'CC': {'name': 'OSD Display Time', 'type': 'stepper', 'min': 1, 'max': 60, 'suffix': ' sec'},
            '52': {'name': 'Active Control', 'type': 'combo', 'values': {
                '1': 'Brightness/Contrast', '2': 'Color Temperature', '3': 'Color Preset',
                '4': 'Audio Volume', '5': 'Audio Balance', '6': 'Red Gain', '7': 'Green Gain',
                '8': 'Blue Gain', '9': 'Focus', '10': 'Auto Setup', '11': 'Factory Reset'
            }},
            '04': {'name': 'Factory Reset', 'type': 'combo', 'values': {
                '1': 'Reset to Factory Defaults', '2': 'Reset Color', '3': 'Reset Geometry'
            }},
            '05': {'name': 'Factory Reset Enable', 'type': 'combo', 'values': {
                '1': 'Cannot Reset', '2': 'Can Reset'
            }},
            '06': {'name': 'Power Mode', 'type': 'combo', 'values': {
                '1': 'On', '2': 'Standby', '4': 'Suspend', '5': 'Off', '6': 'Hard Off'
            }},
            '08': {'name': 'Factory Color Defaults', 'type': 'combo', 'values': {
                '1': 'Reset Color to Factory'
            }},
            '0A': {'name': 'Factory Geometry Defaults', 'type': 'combo', 'values': {
                '1': 'Reset Geometry to Factory'
            }},
            
            # Screen Saver and Power Management
            'D6': {'name': 'DPMS Control', 'type': 'combo', 'values': {
                '1': 'DPMS On', '2': 'DPMS Standby', '3': 'DPMS Suspend', '4': 'DPMS Off'
            }},
            'E0': {'name': 'Screen Saver Control', 'type': 'combo', 'values': {
                '1': 'Screen Saver Off', '2': 'Screen Saver On'
            }},
            'E1': {'name': 'Screen Saver Delay', 'type': 'stepper', 'min': 1, 'max': 255, 'suffix': ' min'},
            'E2': {'name': 'Power LED', 'type': 'combo', 'values': {
                '1': 'Off', '2': 'On'
            }},
            
            # Special Features
            '54': {'name': 'Performance Preservation', 'type': 'combo', 'values': {
                '1': 'No Guarantee', '2': 'Guarantee'
            }},
            '55': {'name': 'Auto Color Setup', 'type': 'combo', 'values': {
                '1': 'Auto Color Setup Off', '2': 'Auto Color Setup On'
            }},
            '1E': {'name': 'Auto Setup Enable', 'type': 'combo', 'values': {
                '1': 'Auto Setup Disabled', '2': 'Auto Setup Enabled'
            }},
            
            # Information (Read-Only)
            'DF': {'name': 'VCP Version', 'type': 'readonly', 'min': 0, 'max': 255, 'suffix': ''},
            'C0': {'name': 'Display Usage Time', 'type': 'readonly', 'min': 0, 'max': 65535, 'suffix': ' hours'},
            'C6': {'name': 'Application Enable Key', 'type': 'readonly', 'min': 0, 'max': 65535, 'suffix': ''},
            'C8': {'name': 'Display Controller Type', 'type': 'readonly', 'min': 0, 'max': 65535, 'suffix': ''},
            'C9': {'name': 'Display Firmware Level', 'type': 'readonly', 'min': 0, 'max': 65535, 'suffix': ''},
            'DC': {'name': 'Display Application', 'type': 'readonly', 'min': 0, 'max': 255, 'suffix': ''},
            'DD': {'name': 'Capabilities Request', 'type': 'readonly', 'min': 0, 'max': 255, 'suffix': ''},
            'DE': {'name': 'Capabilities Reply', 'type': 'readonly', 'min': 0, 'max': 255, 'suffix': ''},
            'F0': {'name': 'OSD', 'type': 'combo', 'values': {
                '1': 'OSD Disabled', '2': 'OSD Enabled'
            }},
            'F1': {'name': 'OSD Language', 'type': 'combo', 'values': {
                '1': 'Chinese', '2': 'English', '3': 'French', '4': 'German', '5': 'Italian'
            }},
            'F2': {'name': 'Status Indicators', 'type': 'combo', 'values': {
                '1': 'Status Indicators Off', '2': 'Status Indicators On'
            }},
            'F3': {'name': 'Auxiliary Power Output', 'type': 'combo', 'values': {
                '1': 'Auxiliary Off', '2': 'Auxiliary On'
            }},
            'F4': {'name': 'Auxiliary Display Data', 'type': 'stepper', 'min': 0, 'max': 255, 'suffix': ''},
            'F5': {'name': 'Auxiliary Display', 'type': 'combo', 'values': {
                '1': 'Auxiliary Display Off', '2': 'Auxiliary Display On'
            }}
        }
        
        # Cache the definitions
        self._vcp_definitions_cache = vcp_definitions
        return vcp_definitions
    
    @pyqtSlot(str, result='QVariant')
    def getFeatureInfo(self, vcp_code):
        """Get detailed information about a VCP feature with caching"""
        vcp_definitions = self._get_vcp_definitions()
        
        # Get base info from monitor capabilities if available
        base_info = {'name': f'VCP {vcp_code}', 'values': {}, 'code': vcp_code}
        if self._current_monitor and self._current_monitor in self._monitors:
            features = self._monitors[self._current_monitor].get('features', {})
            feature_info = features.get(vcp_code, {})
            if feature_info.get('name'):
                base_info['name'] = feature_info['name']
            if feature_info.get('values'):
                base_info['values'] = feature_info['values']
        
        # Enhance with our definitions
        if vcp_code in vcp_definitions:
            definition = vcp_definitions[vcp_code]
            result = {
                'name': definition['name'],
                'type': definition['type'],
                'code': vcp_code,
                'values': definition.get('values', base_info['values']),
                'min': definition.get('min', 0),
                'max': definition.get('max', 255),
                'suffix': definition.get('suffix', '')
            }
            return result
        
        # Fallback for unknown codes
        return {
            'name': base_info['name'],
            'type': 'textfield',
            'code': vcp_code,
            'values': base_info['values'],
            'min': 0,
            'max': 255,
            'suffix': ''
        }

def main():
    print(f"Using Qt{QT_VERSION} for Kirigami interface with GPU acceleration")
    
    # Enable basic GPU optimizations without forcing specific backends
    os.environ['__GL_SHADER_DISK_CACHE'] = '1'  # Enable shader cache for GPU acceleration
    os.environ['__GL_THREADED_OPTIMIZATIONS'] = '1'  # Enable threaded optimizations
    
    # Prevent rendering issues and ensure proper initialization
    os.environ['QSG_INFO'] = '0'  # Reduce Qt scene graph debug output
    os.environ['QT_QPA_PLATFORM'] = 'xcb'  # Force X11 backend for stability
    os.environ['QT_QUICK_BACKEND'] = 'software'  # Use software rendering for reliability
    os.environ['QSG_RENDER_LOOP'] = 'basic'  # Use basic render loop to prevent transparency issues
    
    app = QApplication(sys.argv)
    app.setApplicationName("Monitor Remote Control")
    app.setOrganizationName("MonitorRemoteControl")
    
    # Enable high DPI scaling for crisp graphics on modern displays
    if QT_VERSION == 6:
        # Qt6 handles high DPI automatically, but we can still set some optimizations
        from PyQt6.QtCore import Qt
        try:
            app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings, True)
        except AttributeError:
            pass  # Not available in all Qt6 versions
    else:
        from PyQt5.QtCore import Qt
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Make application single instance
    app.setQuitOnLastWindowClosed(True)
    
    # Check if another instance is already running
    import socket
    
    lock_file = f"/tmp/monitor-remote-control-gui-{os.getuid()}.lock"
    
    try:
        # Try to create a lock socket
        lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        lock_socket.bind(lock_file)
        
        # Register cleanup function
        import atexit
        def cleanup():
            try:
                lock_socket.close()
                if os.path.exists(lock_file):
                    os.unlink(lock_file)
            except:
                pass
        atexit.register(cleanup)
        
    except socket.error:
        # Check if the lock file is stale (process no longer running)
        try:
            # Try to connect to see if another instance is actually running
            test_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            test_socket.connect(lock_file)
            test_socket.close()
            print("Another instance of Auto Brightness & Monitor Control is already running.")
            return 1
        except socket.error:
            # Lock file exists but no process is bound to it - remove stale lock
            try:
                os.unlink(lock_file)
                # Try to create lock again
                lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                lock_socket.bind(lock_file)
                
                # Register cleanup function
                import atexit
                def cleanup():
                    try:
                        lock_socket.close()
                        if os.path.exists(lock_file):
                            os.unlink(lock_file)
                    except:
                        pass
                atexit.register(cleanup)
                
            except Exception as e:
                print(f"Failed to create lock file: {e}")
                return 1
    
    # Set Qt style for better Kirigami compatibility
    app.setStyle("Breeze") if hasattr(app, 'setStyle') else None
    
    # Register the controller type
    qmlRegisterType(BrightnessController, "BrightnessControl", 1, 0, "BrightnessController")
    
    # Create QML engine
    engine = QQmlApplicationEngine()
    
    # Set import paths for Kirigami (Qt6 paths)
    if QT_VERSION == 6:
        qml_paths = [
            "/usr/lib/qt6/qml",
            "/usr/lib/x86_64-linux-gnu/qt6/qml",
            "/usr/share/qt6/qml"
        ]
    else:
        qml_paths = [
            "/usr/lib/qt/qml",
            "/usr/lib/qt5/qml", 
            "/usr/lib/x86_64-linux-gnu/qt5/qml",
            "/usr/share/qt5/qml"
        ]
    
    for path in qml_paths:
        if os.path.exists(path):
            print(f"Adding QML path: {path}")
            engine.addImportPath(path)
    
    # Load the QML file - check multiple locations
    qml_file_locations = [
        os.path.join(os.path.dirname(__file__), "brightness_kirigami_qt6.qml"),  # Development location
        "/usr/share/monitor-remote-control/brightness_kirigami_qt6.qml",  # Installed location
    ]
    
    qml_file = None
    for location in qml_file_locations:
        if os.path.exists(location):
            qml_file = location
            break
    
    if not qml_file:
        print(f"QML file not found in any of these locations: {qml_file_locations}")
        return 1
    
    print(f"Loading QML file: {qml_file}")
    engine.load(QUrl.fromLocalFile(qml_file))
    
    if not engine.rootObjects():
        print("Failed to load QML file")
        return 1
    
    # Get the main window and ensure proper initialization
    root_objects = engine.rootObjects()
    if root_objects:
        main_window = root_objects[0]
        print("Main window initialized successfully")
        
        # Force window to be visible and render properly
        if hasattr(main_window, 'show'):
            main_window.show()
        if hasattr(main_window, 'raise_'):
            main_window.raise_()
        if hasattr(main_window, 'activateWindow'):
            main_window.activateWindow()
            
        # Force immediate refresh to prevent blank/transparent state
        if hasattr(main_window, 'update'):
            main_window.update()
        
        # Ensure window is properly sized and positioned
        if hasattr(main_window, 'setWidth') and hasattr(main_window, 'setHeight'):
            main_window.setWidth(1000)
            main_window.setHeight(700)
    
    print("Kirigami interface loaded successfully!")
    
    # Process events to ensure proper rendering before starting main loop
    app.processEvents()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())