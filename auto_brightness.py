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

class AutoBrightnessService:
    def __init__(self, config_path=None):
        if config_path is None:
            # Try local config first, then system config
            local_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
            if os.path.exists(local_config):
                config_path = local_config
            else:
                config_path = "/etc/auto-brightness/config.json"
        self.config_path = config_path
        self.config = self.load_config()
        self.setup_logging()
        
    def load_config(self):
        default_config = {
            "latitude": None,
            "longitude": None,
            "min_brightness": 0.1,
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
    
    def calculate_brightness(self, sunrise, sunset):
        now = datetime.now(timezone.utc)
        
        # Full daylight
        if sunrise <= now <= sunset:
            return self.config["max_brightness"]
        
        # Calculate twilight periods (1 hour after sunset / before sunrise)
        twilight_duration = 3600  # 1 hour in seconds
        
        # Evening twilight (just after sunset)
        evening_twilight_end = sunset + timedelta(seconds=twilight_duration)
        if sunset < now <= evening_twilight_end:
            return 0.5  # 50% during dusk
        
        # Morning twilight (just before sunrise)  
        morning_twilight_start = sunrise - timedelta(seconds=twilight_duration)
        if morning_twilight_start <= now < sunrise:
            return 0.5  # 50% during dawn
        
        # Deep night - minimum brightness
        return self.config["min_brightness"]
    
    def get_displays(self):
        if self.config["displays"]:
            return self.config["displays"]
        
        try:
            result = subprocess.run(['ddcutil', 'detect', '--brief'], 
                                  capture_output=True, text=True, check=True)
            displays = []
            for line in result.stdout.split('\n'):
                if 'I2C bus:' in line and '/dev/i2c-' in line:
                    i2c_path = line.split('/dev/i2c-')[1].strip()
                    displays.append(i2c_path)
            return displays
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to get displays via ddcutil: {e}")
            return []
    
    def set_brightness(self, display, brightness):
        try:
            brightness_percent = int(brightness * 100)
            subprocess.run(['ddcutil', '--bus', display, 'setvcp', '10', str(brightness_percent)], 
                         check=True, capture_output=True)
            logging.info(f"Set display {display} brightness to {brightness_percent}%")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to set brightness for display {display}: {e}")
    
    def run(self):
        logging.info("Starting Auto Brightness Service")
        
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
        
        displays = self.get_displays()
        if not displays:
            logging.error("No displays found")
            return
        
        logging.info(f"Found displays: {displays}")
        
        while True:
            try:
                # Reload config each iteration to check for changes
                self.config = self.load_config()
                
                # Check if auto brightness was disabled
                if not self.config.get("auto_brightness_enabled", True):
                    logging.info("Auto brightness disabled. Pausing automatic adjustments.")
                    time.sleep(30)
                    continue
                
                # Update location if it changed
                new_lat, new_lon = self.get_location()
                if new_lat != lat or new_lon != lon:
                    lat, lon = new_lat, new_lon
                    logging.info(f"Location updated: {lat:.2f}, {lon:.2f}")
                
                sunrise, sunset = self.get_sun_times(lat, lon)
                if sunrise and sunset:
                    brightness = self.calculate_brightness(sunrise, sunset)
                    
                    for display in displays:
                        self.set_brightness(display, brightness)
                    
                    logging.info(f"Updated brightness to {brightness:.2f}")
                else:
                    logging.warning("Could not get sun times, skipping update")
                
                time.sleep(self.config["update_interval"])
                
            except KeyboardInterrupt:
                logging.info("Service stopped by user")
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                time.sleep(60)

if __name__ == "__main__":
    service = AutoBrightnessService()
    service.run()