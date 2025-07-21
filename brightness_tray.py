#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk
import json
import subprocess
import threading
import sys
from pathlib import Path
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

class BrightnessTray:
    def __init__(self):
        self.config_path = "/home/user/Documents/auto-brightness/config.json"
        self.config = self.load_config()
        self.settings_window = None
        
        if TRAY_AVAILABLE:
            self.setup_tray()
        else:
            print("System tray not available. Install: pip install pystray pillow")
            self.create_settings_window()
            
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
    
    def create_tray_icon(self):
        # Create a simple brightness icon
        image = Image.new('RGB', (64, 64), color='black')
        draw = ImageDraw.Draw(image)
        
        # Draw sun-like icon
        draw.ellipse([16, 16, 48, 48], fill='yellow', outline='orange', width=2)
        
        # Draw rays
        rays = [(32, 4, 32, 12), (32, 52, 32, 60), (4, 32, 12, 32), 
                (52, 32, 60, 32), (12, 12, 18, 18), (46, 46, 52, 52),
                (46, 18, 52, 12), (18, 46, 12, 52)]
        for ray in rays:
            draw.line(ray, fill='orange', width=2)
            
        return image
    
    def setup_tray(self):
        icon_image = self.create_tray_icon()
        
        menu_items = [
            pystray.MenuItem("Settings", self.show_settings),
            pystray.MenuItem("Restart Service", self.restart_service),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f"Night: {int(self.config.get('min_brightness', 0.3) * 100)}%", 
                           None, enabled=False),
            pystray.MenuItem(f"Day: {int(self.config.get('max_brightness', 1.0) * 100)}%", 
                           None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.quit_app)
        ]
        
        self.tray_icon = pystray.Icon(
            "auto_brightness",
            icon_image,
            "Auto Brightness Control",
            pystray.Menu(*menu_items)
        )
    
    def show_settings(self, icon=None, item=None):
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.create_settings_window()
        else:
            self.settings_window.lift()
            self.settings_window.focus_force()
    
    def create_settings_window(self):
        self.settings_window = tk.Tk()
        self.settings_window.title("Auto Brightness Settings")
        self.settings_window.geometry("380x220")
        self.settings_window.resizable(False, False)
        
        # Center the window
        self.settings_window.geometry("+%d+%d" % (
            self.settings_window.winfo_screenwidth() // 2 - 190,
            self.settings_window.winfo_screenheight() // 2 - 110
        ))
        
        self.setup_settings_ui()
        
        if not TRAY_AVAILABLE:
            self.settings_window.mainloop()
    
    def setup_settings_ui(self):
        main_frame = ttk.Frame(self.settings_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="🔆 Auto Brightness Settings", 
                               font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Night brightness slider
        ttk.Label(main_frame, text="🌙 Night Brightness:", 
                 font=('Arial', 10)).grid(row=1, column=0, sticky=tk.W, pady=5)
        
        self.min_var = tk.DoubleVar(value=self.config.get("min_brightness", 0.3) * 100)
        self.min_scale = ttk.Scale(main_frame, from_=10, to=80, 
                                  variable=self.min_var, orient=tk.HORIZONTAL,
                                  length=180, command=self.on_min_change)
        self.min_scale.grid(row=1, column=1, padx=(10, 5), pady=5)
        
        self.min_label = ttk.Label(main_frame, text=f"{int(self.min_var.get())}%",
                                  font=('Arial', 10, 'bold'))
        self.min_label.grid(row=1, column=2, pady=5)
        
        # Day brightness slider  
        ttk.Label(main_frame, text="☀️ Day Brightness:", 
                 font=('Arial', 10)).grid(row=2, column=0, sticky=tk.W, pady=5)
        
        self.max_var = tk.DoubleVar(value=self.config.get("max_brightness", 1.0) * 100)
        self.max_scale = ttk.Scale(main_frame, from_=50, to=100,
                                  variable=self.max_var, orient=tk.HORIZONTAL, 
                                  length=180, command=self.on_max_change)
        self.max_scale.grid(row=2, column=1, padx=(10, 5), pady=5)
        
        self.max_label = ttk.Label(main_frame, text=f"{int(self.max_var.get())}%",
                                  font=('Arial', 10, 'bold'))
        self.max_label.grid(row=2, column=2, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=(20, 0))
        
        apply_btn = ttk.Button(button_frame, text="✓ Apply Settings", 
                              command=self.apply_settings)
        apply_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        restart_btn = ttk.Button(button_frame, text="🔄 Restart Service", 
                                command=self.restart_service)
        restart_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        close_btn = ttk.Button(button_frame, text="✕ Close", 
                              command=self.close_settings)
        close_btn.pack(side=tk.LEFT)
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready", 
                                     foreground="green", font=('Arial', 9))
        self.status_label.grid(row=4, column=0, columnspan=3, pady=(15, 0))
        
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
        if self.settings_window:
            self.settings_window.update()
        
        # Update config
        self.config["min_brightness"] = self.min_var.get() / 100
        self.config["max_brightness"] = self.max_var.get() / 100
        self.save_config()
        
        # Update tray menu if available
        if TRAY_AVAILABLE:
            self.update_tray_menu()
        
        # Restart service
        threading.Thread(target=self._restart_service_thread, daemon=True).start()
    
    def restart_service(self, icon=None, item=None):
        if hasattr(self, 'status_label'):
            self.status_label.config(text="Restarting service...", foreground="orange")
            if self.settings_window:
                self.settings_window.update()
        threading.Thread(target=self._restart_service_thread, daemon=True).start()
    
    def _restart_service_thread(self):
        try:
            subprocess.run(['systemctl', '--user', 'restart', 'auto-brightness.service'], 
                         check=True, capture_output=True)
            
            if hasattr(self, 'status_label') and self.settings_window:
                self.settings_window.after(0, lambda: self.status_label.config(
                    text="✓ Settings applied successfully!", foreground="green"))
                self.settings_window.after(3000, lambda: self.status_label.config(
                    text="Ready", foreground="green"))
                
        except subprocess.CalledProcessError:
            if hasattr(self, 'status_label') and self.settings_window:
                self.settings_window.after(0, lambda: self.status_label.config(
                    text="✗ Error restarting service", foreground="red"))
    
    def update_tray_menu(self):
        if TRAY_AVAILABLE:
            # Update the menu items with new values
            menu_items = [
                pystray.MenuItem("Settings", self.show_settings),
                pystray.MenuItem("Restart Service", self.restart_service),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(f"Night: {int(self.config.get('min_brightness', 0.3) * 100)}%", 
                               None, enabled=False),
                pystray.MenuItem(f"Day: {int(self.config.get('max_brightness', 1.0) * 100)}%", 
                               None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self.quit_app)
            ]
            self.tray_icon.menu = pystray.Menu(*menu_items)
    
    def close_settings(self):
        if self.settings_window:
            self.settings_window.destroy()
            self.settings_window = None
    
    def quit_app(self, icon=None, item=None):
        if TRAY_AVAILABLE:
            self.tray_icon.stop()
        if self.settings_window:
            self.settings_window.destroy()
        sys.exit()
    
    def run(self):
        if TRAY_AVAILABLE:
            # Show settings window initially
            self.show_settings()
            self.tray_icon.run()
        # If no tray available, window is already shown

if __name__ == "__main__":
    app = BrightnessTray()
    app.run()