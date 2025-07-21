#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk
import json
import subprocess
import sys
import os

class SimpleBrightnessControl:
    def __init__(self):
        self.config_path = "/home/user/Documents/auto-brightness/config.json"
        self.config = self.load_config()
        
        self.root = tk.Tk()
        self.root.title("🔆 Brightness Control")
        self.root.geometry("300x150")
        self.root.resizable(False, False)
        
        # Keep window on top but allow it to lose focus
        self.root.attributes('-topmost', False)
        
        # Position in a convenient location
        self.root.geometry("+50+50")
        
        self.setup_ui()
        
    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except:
            return {"min_brightness": 0.3, "max_brightness": 1.0}
    
    def save_config_and_restart(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            # Restart service
            subprocess.run(['systemctl', '--user', 'restart', 'auto-brightness.service'], 
                         check=True, capture_output=True)
            
            self.status_label.config(text="✓ Applied successfully!", foreground="green")
            self.root.after(2000, lambda: self.status_label.config(text="Ready", foreground="black"))
            
        except Exception as e:
            self.status_label.config(text="✗ Error applying", foreground="red")
            
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title = ttk.Label(main_frame, text="🔆 Brightness Control", 
                         font=('Arial', 12, 'bold'))
        title.pack(pady=(0, 15))
        
        # Night brightness
        night_frame = ttk.Frame(main_frame)
        night_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(night_frame, text="🌙 Night:", width=8).pack(side=tk.LEFT)
        
        self.min_var = tk.DoubleVar(value=self.config.get("min_brightness", 0.3) * 100)
        min_scale = ttk.Scale(night_frame, from_=10, to=80, variable=self.min_var, 
                             orient=tk.HORIZONTAL, length=150, command=self.on_min_change)
        min_scale.pack(side=tk.LEFT, padx=(5, 5))
        
        self.min_label = ttk.Label(night_frame, text=f"{int(self.min_var.get())}%", 
                                  font=('Arial', 9, 'bold'), width=4)
        self.min_label.pack(side=tk.LEFT)
        
        # Day brightness
        day_frame = ttk.Frame(main_frame)
        day_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(day_frame, text="☀️ Day:", width=8).pack(side=tk.LEFT)
        
        self.max_var = tk.DoubleVar(value=self.config.get("max_brightness", 1.0) * 100)
        max_scale = ttk.Scale(day_frame, from_=50, to=100, variable=self.max_var,
                             orient=tk.HORIZONTAL, length=150, command=self.on_max_change)
        max_scale.pack(side=tk.LEFT, padx=(5, 5))
        
        self.max_label = ttk.Label(day_frame, text=f"{int(self.max_var.get())}%",
                                  font=('Arial', 9, 'bold'), width=4)
        self.max_label.pack(side=tk.LEFT)
        
        # Apply button
        apply_btn = ttk.Button(main_frame, text="Apply Settings", 
                              command=self.apply_settings)
        apply_btn.pack(pady=(15, 5))
        
        # Status
        self.status_label = ttk.Label(main_frame, text="Ready", 
                                     font=('Arial', 8))
        self.status_label.pack()
        
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
        self.config["min_brightness"] = self.min_var.get() / 100
        self.config["max_brightness"] = self.max_var.get() / 100
        self.save_config_and_restart()
        
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = SimpleBrightnessControl()
    app.run()