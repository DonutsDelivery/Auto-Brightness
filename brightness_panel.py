#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk
import json
import subprocess
import threading
import sys
from pathlib import Path

class BrightnessPanelWidget:
    def __init__(self):
        self.config_path = "/home/user/Documents/auto-brightness/config.json"
        self.config = self.load_config()
        
        # Create a small floating panel widget
        self.create_panel_widget()
        
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
    
    def create_panel_widget(self):
        self.root = tk.Tk()
        self.root.title("🔆 Brightness")
        self.root.geometry("200x120")
        
        # Position in top-right corner
        self.root.geometry("+%d+%d" % (
            self.root.winfo_screenwidth() - 220,
            20
        ))
        
        # Make it stay on top and look like a widget
        self.root.attributes('-topmost', True)
        self.root.resizable(False, False)
        
        # Minimize to taskbar instead of system tray
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_taskbar)
        
        self.setup_widget_ui()
        
    def setup_widget_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header with current brightness info
        current_night = int(self.config.get("min_brightness", 0.3) * 100)
        current_day = int(self.config.get("max_brightness", 1.0) * 100)
        
        header = ttk.Label(main_frame, text="🔆 Auto Brightness", 
                          font=('Arial', 10, 'bold'))
        header.pack(pady=(0, 10))
        
        # Quick info
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(info_frame, text=f"🌙 Night: {current_night}%", 
                 font=('Arial', 8)).pack()
        ttk.Label(info_frame, text=f"☀️ Day: {current_day}%", 
                 font=('Arial', 8)).pack()
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        
        settings_btn = ttk.Button(btn_frame, text="⚙️ Settings", 
                                 command=self.open_full_settings, width=12)
        settings_btn.pack(side=tk.TOP, pady=2, fill=tk.X)
        
        restart_btn = ttk.Button(btn_frame, text="🔄 Restart", 
                                command=self.restart_service, width=12)
        restart_btn.pack(side=tk.TOP, pady=2, fill=tk.X)
        
    def minimize_to_taskbar(self):
        self.root.withdraw()  # Hide window but keep in taskbar
        
    def show_from_taskbar(self):
        self.root.deiconify()  # Show window again
        self.root.lift()
        
    def open_full_settings(self):
        # Create full settings window
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
            
        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Brightness Settings")
        self.settings_window.geometry("380x220")
        self.settings_window.resizable(False, False)
        
        # Center the settings window
        self.settings_window.geometry("+%d+%d" % (
            self.settings_window.winfo_screenwidth() // 2 - 190,
            self.settings_window.winfo_screenheight() // 2 - 110
        ))
        
        self.setup_full_settings_ui()
    
    def setup_full_settings_ui(self):
        main_frame = ttk.Frame(self.settings_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="🔆 Auto Brightness Settings", 
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Sliders frame
        sliders_frame = ttk.Frame(main_frame)
        sliders_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Night brightness
        night_frame = ttk.Frame(sliders_frame)
        night_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(night_frame, text="🌙 Night Brightness:", 
                 font=('Arial', 10)).pack(side=tk.LEFT)
        
        self.min_var = tk.DoubleVar(value=self.config.get("min_brightness", 0.3) * 100)
        self.min_scale = ttk.Scale(night_frame, from_=10, to=80, 
                                  variable=self.min_var, orient=tk.HORIZONTAL,
                                  length=180, command=self.on_min_change)
        self.min_scale.pack(side=tk.LEFT, padx=(10, 5))
        
        self.min_label = ttk.Label(night_frame, text=f"{int(self.min_var.get())}%",
                                  font=('Arial', 10, 'bold'), width=4)
        self.min_label.pack(side=tk.LEFT)
        
        # Day brightness
        day_frame = ttk.Frame(sliders_frame)
        day_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(day_frame, text="☀️ Day Brightness:", 
                 font=('Arial', 10)).pack(side=tk.LEFT)
        
        self.max_var = tk.DoubleVar(value=self.config.get("max_brightness", 1.0) * 100)
        self.max_scale = ttk.Scale(day_frame, from_=50, to=100,
                                  variable=self.max_var, orient=tk.HORIZONTAL, 
                                  length=180, command=self.on_max_change)
        self.max_scale.pack(side=tk.LEFT, padx=(10, 5))
        
        self.max_label = ttk.Label(day_frame, text=f"{int(self.max_var.get())}%",
                                  font=('Arial', 10, 'bold'), width=4)
        self.max_label.pack(side=tk.LEFT)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack()
        
        ttk.Button(button_frame, text="✓ Apply Settings", 
                  command=self.apply_settings).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="🔄 Restart Service", 
                  command=self.restart_service).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="✕ Close", 
                  command=self.settings_window.destroy).pack(side=tk.LEFT)
        
        # Status
        self.status_label = ttk.Label(main_frame, text="Ready", 
                                     foreground="green", font=('Arial', 9))
        self.status_label.pack(pady=(15, 0))
    
    def on_min_change(self, value):
        val = int(float(value))
        self.min_label.config(text=f"{val}%")
        if val >= self.max_var.get():
            self.max_var.set(val + 10)
            self.max_label.config(text=f"{int(self.max_var.get())}%")
    
    def on_max_change(self, value):
        val = int(float(value))
        self.max_label.config(text=f"{val}%")
        if val <= self.min_var.get():
            self.min_var.set(val - 10)
            self.min_label.config(text=f"{int(self.min_var.get())}%")
    
    def apply_settings(self):
        self.status_label.config(text="Applying settings...", foreground="orange")
        self.settings_window.update()
        
        # Update config
        self.config["min_brightness"] = self.min_var.get() / 100
        self.config["max_brightness"] = self.max_var.get() / 100
        self.save_config()
        
        # Update main widget display
        self.refresh_widget_info()
        
        # Restart service
        threading.Thread(target=self._restart_service_thread, daemon=True).start()
    
    def restart_service(self):
        threading.Thread(target=self._restart_service_thread, daemon=True).start()
    
    def _restart_service_thread(self):
        try:
            subprocess.run(['systemctl', '--user', 'restart', 'auto-brightness.service'], 
                         check=True, capture_output=True)
            
            if hasattr(self, 'status_label'):
                self.settings_window.after(0, lambda: self.status_label.config(
                    text="✓ Settings applied successfully!", foreground="green"))
                self.settings_window.after(3000, lambda: self.status_label.config(
                    text="Ready", foreground="green"))
                
        except subprocess.CalledProcessError:
            if hasattr(self, 'status_label'):
                self.settings_window.after(0, lambda: self.status_label.config(
                    text="✗ Error restarting service", foreground="red"))
    
    def refresh_widget_info(self):
        # Reload config and update widget display
        self.config = self.load_config()
        self.root.destroy()
        self.create_panel_widget()
        self.setup_widget_ui()
        
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = BrightnessPanelWidget()
    app.run()