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
    
    def calculate_solar_elevation(self, lat, lon, dt):
        """Calculate solar elevation angle in degrees"""
        # Get Julian day number
        a = (14 - dt.month) // 12
        y = dt.year - a
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
        declination = math.asin(0.39795 * math.cos(lambda_sun))
        
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
        
        # Convert elevation to brightness using a smooth curve
        # Solar elevation ranges from -90° (night) to 90° (noon)
        # We'll use a curve that:
        # - Minimum brightness below -6° (civil twilight)
        # - Smooth transition from -6° to 0° (horizon)
        # - Peak brightness around 30-60° elevation
        
        min_brightness = self.config["min_brightness"]
        max_brightness = self.config["max_brightness"]
        
        if elevation <= -6:
            # Deep night (civil twilight and below)
            return min_brightness
        elif elevation <= 0:
            # Civil twilight to horizon - smooth transition
            twilight_factor = (elevation + 6) / 6.0
            return min_brightness + (0.3 * (max_brightness - min_brightness) * twilight_factor)
        elif elevation <= 15:
            # Early morning/evening - gradual increase
            factor = elevation / 15.0
            return min_brightness + (0.6 * (max_brightness - min_brightness) * factor)
        elif elevation <= 30:
            # Good daylight - steeper increase
            factor = 0.6 + 0.3 * (elevation - 15) / 15.0
            return min_brightness + (factor * (max_brightness - min_brightness))
        else:
            # Peak daylight (elevation > 30°)
            # Use a slight curve to max out around 45-60°
            peak_factor = min(1.0, 0.9 + 0.1 * min(1.0, (elevation - 30) / 30.0))
            return min_brightness + (peak_factor * (max_brightness - min_brightness))
    
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
    
    def ensure_proper_contrast(self, display):
        """Ensure the monitor has adequate contrast for brightness changes to be visible"""
        try:
            # Check current contrast
            result = subprocess.run(['ddcutil', '--bus', display, 'getvcp', '12'], 
                                  capture_output=True, text=True, check=True, timeout=5)
            
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
                    subprocess.run(['ddcutil', '--bus', display, 'setvcp', '12', '75'], 
                                 check=True, capture_output=True, timeout=5)
                    logging.info(f"Adjusted display {display} contrast from {current_contrast}% to 75% for better visibility")
                else:
                    logging.debug(f"Display {display} contrast is adequate at {current_contrast}%")
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            # Some monitors don't support contrast control, that's okay
            logging.debug(f"Could not check/adjust contrast for display {display}: {e}")
        except Exception as e:
            logging.warning(f"Unexpected error checking contrast for display {display}: {e}")

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
                
                # Periodically re-check contrast levels (every 10 iterations ~ every hour at 5min intervals)
                iteration_count += 1
                if iteration_count % 10 == 0:
                    logging.debug("Periodic contrast check...")
                    for display in displays:
                        self.ensure_proper_contrast(display)
                
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