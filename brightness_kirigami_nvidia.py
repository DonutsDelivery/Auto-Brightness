#!/usr/bin/env python3

import sys
import os
import json
import threading
import time

# Set environment variables for NVIDIA compatibility before importing Qt
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['QT_QUICK_BACKEND'] = 'software'  # Force software rendering
os.environ['QSG_RENDER_LOOP'] = 'basic'
os.environ['QML_DISABLE_DISK_CACHE'] = '1'
# Disable Vulkan to avoid NVIDIA conflicts
os.environ['QT_VULKAN_LIB'] = ''
os.environ['VK_ICD_FILENAMES'] = ''

from PyQt5.QtWidgets import QApplication
from PyQt5.QtQml import QQmlApplicationEngine, qmlRegisterType
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, pyqtProperty, QUrl
from PyQt5.QtGui import QIcon
from monitor_control import DDCIMonitorControl

class BrightnessController(QObject):
    """Backend controller for brightness and monitor management"""
    
    # Signals for QML
    configChanged = pyqtSignal()
    statusChanged = pyqtSignal(str, str)  # message, type
    monitorsChanged = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.config_path = "/home/user/Documents/auto-brightness/config.json"
        self._config = self.load_config()
        self.monitor_control = DDCIMonitorControl()
        self._monitors = {}
        self._current_monitor = None
        
        # Auto-refresh monitors
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_monitors)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
        
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
    
    @pyqtProperty(float, notify=configChanged)
    def maxBrightness(self):
        return self._config.get("max_brightness", 1.0) * 100
    
    @maxBrightness.setter
    def maxBrightness(self, value):
        self._config["max_brightness"] = value / 100
        self.save_config()
    
    @pyqtProperty(bool, notify=configChanged)
    def autoBrightnessEnabled(self):
        return self._config.get("auto_brightness_enabled", True)
    
    @autoBrightnessEnabled.setter 
    def autoBrightnessEnabled(self, value):
        self._config["auto_brightness_enabled"] = value
        self.save_config()
    
    @pyqtProperty(bool, notify=configChanged)
    def locationOverride(self):
        return bool(self._config.get("latitude") and self._config.get("longitude"))
    
    @pyqtProperty(str, notify=configChanged)
    def latitude(self):
        return str(self._config.get("latitude", ""))
    
    @latitude.setter
    def latitude(self, value):
        try:
            lat = float(value) if value.strip() else None
            if lat is not None and not (-90 <= lat <= 90):
                self.statusChanged.emit("Latitude must be between -90 and 90", "error")
                return
            self._config["latitude"] = lat
            self.save_config()
        except ValueError:
            self.statusChanged.emit("Invalid latitude format", "error")
    
    @pyqtProperty(str, notify=configChanged)
    def longitude(self):
        return str(self._config.get("longitude", ""))
    
    @longitude.setter
    def longitude(self, value):
        try:
            lon = float(value) if value.strip() else None
            if lon is not None and not (-180 <= lon <= 180):
                self.statusChanged.emit("Longitude must be between -180 and 180", "error")
                return
            self._config["longitude"] = lon
            self.save_config()
        except ValueError:
            self.statusChanged.emit("Invalid longitude format", "error")
    
    @pyqtProperty('QVariant', notify=monitorsChanged)
    def monitors(self):
        return list(self._monitors.values())
    
    @pyqtProperty(str, notify=monitorsChanged)
    def currentMonitor(self):
        return self._current_monitor or ""
    
    @currentMonitor.setter
    def currentMonitor(self, monitor_id):
        self._current_monitor = monitor_id
        self.monitorsChanged.emit()
    
    @pyqtSlot()
    def refresh_monitors(self):
        """Refresh the list of available monitors"""
        try:
            monitors = self.monitor_control.detect_monitors()
            self._monitors = {}
            
            for monitor in monitors:
                bus_id = str(monitor.get('bus_id', ''))
                self._monitors[bus_id] = {
                    'id': bus_id,
                    'name': monitor.get('name', f'Monitor {bus_id}'),
                    'capabilities': monitor.get('capabilities', [])
                }
            
            if not self._current_monitor and self._monitors:
                self._current_monitor = list(self._monitors.keys())[0]
            
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
    
    @pyqtSlot(str, int, int)
    def setMonitorValue(self, monitor_id, vcp_code, value):
        """Set a VCP value for a monitor"""
        try:
            if monitor_id in self._monitors:
                success = self.monitor_control.set_vcp_value(int(monitor_id), vcp_code, value)
                if success:
                    self.statusChanged.emit(f"Set monitor {monitor_id} VCP {vcp_code} to {value}", "success")
                else:
                    self.statusChanged.emit(f"Failed to set monitor {monitor_id} VCP {vcp_code}", "error")
        except Exception as e:
            self.statusChanged.emit(f"Error setting monitor value: {e}", "error")

def main():
    # Set additional NVIDIA-specific environment variables
    os.environ['__GL_SHADER_DISK_CACHE'] = '0'
    os.environ['__GL_THREADED_OPTIMIZATIONS'] = '0'
    
    app = QApplication(sys.argv)
    app.setApplicationName("Auto Brightness & Monitor Control")
    app.setOrganizationName("AutoBrightness")
    
    # Register the controller type
    qmlRegisterType(BrightnessController, "BrightnessControl", 1, 0, "BrightnessController")
    
    # Create QML engine
    engine = QQmlApplicationEngine()
    
    # Set import paths for Kirigami
    qml_paths = [
        "/usr/lib/qt/qml",
        "/usr/lib/qt5/qml", 
        "/usr/lib/x86_64-linux-gnu/qt5/qml",
        "/usr/share/qt5/qml"
    ]
    
    for path in qml_paths:
        if os.path.exists(path):
            engine.addImportPath(path)
    
    # Load the QML file
    qml_file = os.path.join(os.path.dirname(__file__), "brightness_kirigami_simple.qml")
    
    if not os.path.exists(qml_file):
        print(f"QML file not found: {qml_file}")
        return 1
    
    engine.load(QUrl.fromLocalFile(qml_file))
    
    if not engine.rootObjects():
        print("Failed to load QML file")
        return 1
    
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())