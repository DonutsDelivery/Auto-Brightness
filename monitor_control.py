#!/usr/bin/env python3

import subprocess
import json
import logging
import re
from typing import Dict, List, Optional, Tuple, Any

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