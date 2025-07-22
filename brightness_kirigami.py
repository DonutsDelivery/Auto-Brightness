#!/usr/bin/env python3

import sys
import os
import json
import threading
import time
from PyQt5.QtWidgets import QApplication
from PyQt5.QtQml import QQmlApplicationEngine, qmlRegisterType
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, pyqtProperty
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
        self.refresh_timer.start(10000)  # Refresh every 10 seconds
        
        # Initial monitor detection
        threading.Thread(target=self._detect_monitors_thread, daemon=True).start()
    
    def load_config(self):
        """Load configuration from file"""
        default_config = {
            "latitude": None,
            "longitude": None,
            "min_brightness": 0.3,
            "max_brightness": 1.0,
            "update_interval": 300,
            "displays": [],
            "transition_duration": 30,
            "auto_brightness_enabled": True
        }
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                return {**default_config, **config}
        except (FileNotFoundError, json.JSONDecodeError):
            return default_config
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
            self.configChanged.emit()
        except Exception as e:
            self.statusChanged.emit(f"Error saving config: {e}", "error")
    
    # Properties for QML binding
    @pyqtProperty(bool, notify=configChanged)
    def autoBrightnessEnabled(self):
        return self._config.get("auto_brightness_enabled", True)
    
    @pyqtProperty(bool, notify=configChanged) 
    def locationOverride(self):
        return bool(self._config.get("latitude") and self._config.get("longitude"))
    
    @pyqtProperty(float, notify=configChanged)
    def latitude(self):
        return self._config.get("latitude", 0.0) or 0.0
    
    @pyqtProperty(float, notify=configChanged)
    def longitude(self):
        return self._config.get("longitude", 0.0) or 0.0
    
    @pyqtProperty(float, notify=configChanged)
    def minBrightness(self):
        return self._config.get("min_brightness", 0.3) * 100
    
    @pyqtProperty(float, notify=configChanged)
    def maxBrightness(self):
        return self._config.get("max_brightness", 1.0) * 100
    
    # Slots for QML actions
    @pyqtSlot(bool)
    def setAutoBrightnessEnabled(self, enabled):
        self._config["auto_brightness_enabled"] = enabled
        self.save_config()
    
    @pyqtSlot(bool)
    def setLocationOverride(self, enabled):
        if not enabled:
            self._config["latitude"] = None
            self._config["longitude"] = None
            self.save_config()
    
    @pyqtSlot(float, float)
    def setLocation(self, lat, lon):
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            self._config["latitude"] = lat
            self._config["longitude"] = lon
            self.save_config()
            self.statusChanged.emit("Location updated successfully", "success")
        else:
            self.statusChanged.emit("Invalid coordinates", "error")
    
    @pyqtSlot(float, float)
    def setBrightnessRange(self, min_val, max_val):
        self._config["min_brightness"] = min_val / 100
        self._config["max_brightness"] = max_val / 100
        self.save_config()
    
    @pyqtSlot()
    def applySettings(self):
        """Apply settings and restart service"""
        self.statusChanged.emit("Applying settings...", "info")
        
        def restart_service():
            try:
                import subprocess
                subprocess.run(['systemctl', '--user', 'restart', 'auto-brightness.service'], 
                             check=True, capture_output=True)
                self.statusChanged.emit("Settings applied successfully!", "success")
            except subprocess.CalledProcessError:
                self.statusChanged.emit("Error restarting service", "error")
        
        threading.Thread(target=restart_service, daemon=True).start()
    
    @pyqtSlot()
    def refresh_monitors(self):
        """Refresh monitor list"""
        threading.Thread(target=self._detect_monitors_thread, daemon=True).start()
    
    def _detect_monitors_thread(self):
        """Background thread to detect monitors"""
        try:
            self._monitors = self.monitor_control.detect_monitors()
            self.monitorsChanged.emit()
            if self._monitors:
                self.statusChanged.emit(f"Found {len(self._monitors)} monitor(s)", "success")
            else:
                self.statusChanged.emit("No monitors detected", "warning")
        except Exception as e:
            self.statusChanged.emit(f"Monitor detection failed: {e}", "error")
    
    @pyqtProperty('QVariantList', notify=monitorsChanged)
    def monitors(self):
        """Return list of monitors for QML"""
        monitor_list = []
        for monitor_id, info in self._monitors.items():
            monitor_list.append({
                'id': monitor_id,
                'name': f"Display {monitor_id}: {info['model']}",
                'model': info['model'],
                'bus': info['i2c_bus'],
                'capabilities': info.get('capabilities', {})
            })
        return monitor_list
    
    @pyqtSlot(str)
    def selectMonitor(self, monitor_id):
        """Select a monitor for control"""
        self._current_monitor = self._monitors.get(monitor_id)
        if self._current_monitor:
            self.statusChanged.emit(f"Selected: {self._current_monitor['model']}", "info")
    
    @pyqtSlot(str, int)
    def setMonitorBrightness(self, monitor_id, brightness):
        """Set monitor brightness"""
        monitor = self._monitors.get(monitor_id)
        if monitor and monitor['i2c_bus']:
            success = self.monitor_control.set_brightness(monitor['i2c_bus'], brightness)
            if success:
                self.statusChanged.emit(f"Brightness set to {brightness}%", "success")
            else:
                self.statusChanged.emit("Failed to set brightness", "error")
    
    @pyqtSlot(str, int)
    def setMonitorContrast(self, monitor_id, contrast):
        """Set monitor contrast"""
        monitor = self._monitors.get(monitor_id)
        if monitor and monitor['i2c_bus']:
            success = self.monitor_control.set_contrast(monitor['i2c_bus'], contrast)
            if success:
                self.statusChanged.emit(f"Contrast set to {contrast}%", "success")
            else:
                self.statusChanged.emit("Failed to set contrast", "error")
    
    @pyqtSlot(str, str)
    def setInputSource(self, monitor_id, input_code):
        """Set monitor input source"""
        monitor = self._monitors.get(monitor_id)
        if monitor and monitor['i2c_bus']:
            success = self.monitor_control.set_input_source(monitor['i2c_bus'], input_code)
            if success:
                self.statusChanged.emit(f"Input source changed", "success")
            else:
                self.statusChanged.emit("Failed to change input", "error")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Auto Brightness & Monitor Control")
    app.setOrganizationName("KDE")
    app.setOrganizationDomain("kde.org")
    
    # Register Python types for QML
    qmlRegisterType(BrightnessController, "BrightnessControl", 1, 0, "BrightnessController")
    
    # Create QML engine
    engine = QQmlApplicationEngine()
    
    # Create controller instance
    controller = BrightnessController()
    engine.rootContext().setContextProperty("brightnessController", controller)
    
    # Load QML file
    qml_file = os.path.join(os.path.dirname(__file__), "brightness_kirigami.qml")
    engine.load(qml_file)
    
    if not engine.rootObjects():
        return -1
    
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())