#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from monitor_control_gui import MonitorControlGUI
from plasma_theme import plasma_theme

class BrightnessControlGUI:
    def __init__(self):
        self.config_path = "/home/user/Documents/auto-brightness/config.json"
        self.config = self.load_config()
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("Auto Brightness & Monitor Control")
        self.root.geometry("900x650")
        self.root.resizable(True, True)
        
        # Apply Plasma theme
        plasma_theme.apply_to_window(self.root)
        
        # Try to keep window on top initially
        self.root.attributes('-topmost', True)
        self.root.after(1000, lambda: self.root.attributes('-topmost', False))
        
        self.setup_ui()
        
    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"min_brightness": 0.3, "max_brightness": 1.0}
    
    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def setup_ui(self):
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Auto-brightness settings tab
        auto_frame = ttk.Frame(self.notebook)
        self.notebook.add(auto_frame, text="Auto Brightness")
        
        main_frame = ttk.Frame(auto_frame, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="Auto Brightness Settings", 
                               font=('Arial', 12, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Auto-brightness enable/disable toggle
        toggle_frame = ttk.Frame(main_frame)
        toggle_frame.grid(row=1, column=0, columnspan=3, pady=(0, 15), sticky=tk.W+tk.E)
        
        self.auto_brightness_enabled = tk.BooleanVar(value=self.config.get("auto_brightness_enabled", True))
        auto_toggle = ttk.Checkbutton(toggle_frame, text="Enable Auto Brightness", 
                                     variable=self.auto_brightness_enabled,
                                     command=self.on_auto_brightness_toggle)
        auto_toggle.pack(side=tk.LEFT)
        
        # Location override section
        location_frame = ttk.LabelFrame(main_frame, text="Location Settings", padding=10)
        location_frame.grid(row=2, column=0, columnspan=3, pady=(0, 15), sticky=tk.W+tk.E)
        
        # Location override toggle
        self.location_override = tk.BooleanVar(value=bool(self.config.get("latitude") and self.config.get("longitude")))
        location_toggle = ttk.Checkbutton(location_frame, text="Override location (use manual coordinates)",
                                         variable=self.location_override,
                                         command=self.on_location_override_toggle)
        location_toggle.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # Latitude input
        ttk.Label(location_frame, text="Latitude:").grid(row=1, column=0, sticky=tk.W, padx=(20, 5))
        self.latitude_var = tk.StringVar(value=str(self.config.get("latitude", "")))
        self.latitude_entry = ttk.Entry(location_frame, textvariable=self.latitude_var, width=15)
        self.latitude_entry.grid(row=1, column=1, sticky=tk.W, padx=(5, 0))
        
        # Longitude input  
        ttk.Label(location_frame, text="Longitude:").grid(row=2, column=0, sticky=tk.W, padx=(20, 5))
        self.longitude_var = tk.StringVar(value=str(self.config.get("longitude", "")))
        self.longitude_entry = ttk.Entry(location_frame, textvariable=self.longitude_var, width=15)
        self.longitude_entry.grid(row=2, column=1, sticky=tk.W, padx=(5, 0))
        
        # Update location override state
        self.update_location_fields()
        
        # Min brightness slider
        ttk.Label(main_frame, text="Night Brightness:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.min_var = tk.DoubleVar(value=self.config.get("min_brightness", 0.3) * 100)
        self.min_scale = ttk.Scale(main_frame, from_=10, to=80, 
                                  variable=self.min_var, orient=tk.HORIZONTAL,
                                  length=200, command=self.on_min_change)
        self.min_scale.grid(row=3, column=1, padx=(10, 0), pady=5)
        
        self.min_label = ttk.Label(main_frame, text=f"{int(self.min_var.get())}%")
        self.min_label.grid(row=3, column=2, padx=(10, 0), pady=5)
        
        # Max brightness slider  
        ttk.Label(main_frame, text="Day Brightness:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.max_var = tk.DoubleVar(value=self.config.get("max_brightness", 1.0) * 100)
        self.max_scale = ttk.Scale(main_frame, from_=50, to=100,
                                  variable=self.max_var, orient=tk.HORIZONTAL, 
                                  length=200, command=self.on_max_change)
        self.max_scale.grid(row=4, column=1, padx=(10, 0), pady=5)
        
        self.max_label = ttk.Label(main_frame, text=f"{int(self.max_var.get())}%")
        self.max_label.grid(row=4, column=2, padx=(10, 0), pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=(20, 0))
        
        ttk.Button(button_frame, text="Apply Settings", 
                  command=self.apply_settings).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="Restart Service", 
                  command=self.restart_service).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="Close", 
                  command=self.root.destroy).pack(side=tk.LEFT)
        
        # Status label
        status_colors = plasma_theme.get_status_colors()
        self.status_label = ttk.Label(main_frame, text="Ready")
        self.status_label.grid(row=6, column=0, columnspan=3, pady=(10, 0))
        # Apply success color
        style = ttk.Style()
        style.configure('Success.TLabel', foreground=status_colors['success'])
        self.status_label.configure(style='Success.TLabel')
        
        # Monitor control panel tab
        monitor_frame = ttk.Frame(self.notebook)
        self.notebook.add(monitor_frame, text="Monitor Control")
        
        # Embed the monitor control GUI
        self.monitor_control_gui = MonitorControlGUI(monitor_frame)
        
        # Apply theme to all newly created widgets
        plasma_theme.apply_to_window(self.root)
    
    def on_auto_brightness_toggle(self):
        """Handle auto-brightness enable/disable toggle"""
        enabled = self.auto_brightness_enabled.get()
        
        # Enable/disable brightness sliders based on toggle
        if enabled:
            self.min_scale.configure(state='normal')
            self.max_scale.configure(state='normal')
        else:
            self.min_scale.configure(state='disabled')
            self.max_scale.configure(state='disabled')
    
    def on_location_override_toggle(self):
        """Handle location override toggle"""
        self.update_location_fields()
    
    def update_location_fields(self):
        """Enable/disable location input fields based on override toggle"""
        if self.location_override.get():
            self.latitude_entry.configure(state='normal')
            self.longitude_entry.configure(state='normal')
        else:
            self.latitude_entry.configure(state='disabled')
            self.longitude_entry.configure(state='disabled')
        
    def on_min_change(self, value):
        val = int(float(value))
        self.min_label.config(text=f"{val}%")
        # Ensure min doesn't exceed max
        if val >= self.max_var.get():
            self.max_var.set(val + 10)
            self.max_label.config(text=f"{int(self.max_var.get())}%")
    
    def on_max_change(self, value):
        val = int(float(value))
        self.max_label.config(text=f"{val}%")
        # Ensure max doesn't go below min
        if val <= self.min_var.get():
            self.min_var.set(val - 10)
            self.min_label.config(text=f"{int(self.min_var.get())}%")
    
    def apply_settings(self):
        # Use theme colors for status
        status_colors = plasma_theme.get_status_colors()
        style = ttk.Style()
        style.configure('Warning.TLabel', foreground=status_colors['warning'])
        
        self.status_label.config(text="Applying settings...")
        self.status_label.configure(style='Warning.TLabel')
        self.root.update()
        
        # Update config
        self.config["min_brightness"] = self.min_var.get() / 100
        self.config["max_brightness"] = self.max_var.get() / 100
        self.config["auto_brightness_enabled"] = self.auto_brightness_enabled.get()
        
        # Update location settings
        if self.location_override.get():
            try:
                lat = float(self.latitude_var.get()) if self.latitude_var.get().strip() else None
                lon = float(self.longitude_var.get()) if self.longitude_var.get().strip() else None
                
                if lat is not None and lon is not None:
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        self.config["latitude"] = lat
                        self.config["longitude"] = lon
                    else:
                        raise ValueError("Coordinates out of range")
                else:
                    raise ValueError("Both latitude and longitude required")
            except ValueError as e:
                status_colors = plasma_theme.get_status_colors()
                style = ttk.Style()
                style.configure('Error.TLabel', foreground=status_colors['error'])
                self.status_label.config(text=f"Invalid coordinates: {e}")
                self.status_label.configure(style='Error.TLabel')
                return
        else:
            # Clear manual coordinates to use auto-detection
            self.config["latitude"] = None
            self.config["longitude"] = None
        
        self.save_config()
        
        # Restart service in background thread
        threading.Thread(target=self._restart_service_thread, daemon=True).start()
    
    def restart_service(self):
        # Use theme colors for status
        status_colors = plasma_theme.get_status_colors()
        style = ttk.Style()
        style.configure('Warning.TLabel', foreground=status_colors['warning'])
        
        self.status_label.config(text="Restarting service...")
        self.status_label.configure(style='Warning.TLabel')
        self.root.update()
        threading.Thread(target=self._restart_service_thread, daemon=True).start()
    
    def _restart_service_thread(self):
        try:
            subprocess.run(['systemctl', '--user', 'restart', 'auto-brightness.service'], 
                         check=True, capture_output=True)
            
            # Update status on main thread with theme colors
            status_colors = plasma_theme.get_status_colors()
            style = ttk.Style()
            style.configure('Success.TLabel', foreground=status_colors['success'])
            
            self.root.after(0, lambda: [
                self.status_label.config(text="Settings applied successfully!"),
                self.status_label.configure(style='Success.TLabel')
            ])
            
            # Clear status after 3 seconds
            self.root.after(3000, lambda: [
                self.status_label.config(text="Ready"),
                self.status_label.configure(style='Success.TLabel')
            ])
                
        except subprocess.CalledProcessError as e:
            status_colors = plasma_theme.get_status_colors()
            style = ttk.Style()
            style.configure('Error.TLabel', foreground=status_colors['error'])
            
            self.root.after(0, lambda: [
                self.status_label.config(text="Error restarting service"),
                self.status_label.configure(style='Error.TLabel')
            ])
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = BrightnessControlGUI()
    app.run()