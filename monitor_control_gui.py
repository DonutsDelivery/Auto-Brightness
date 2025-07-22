#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import threading
import time
from monitor_control import DDCIMonitorControl
from plasma_theme import plasma_theme

class MonitorControlGUI:
    """Comprehensive Monitor Control Panel GUI"""
    
    def __init__(self, master=None):
        if master is None:
            self.root = tk.Tk()
            self.standalone = True
        else:
            self.root = master
            self.standalone = False
            
        self.monitor_control = DDCIMonitorControl()
        self.monitors = {}
        self.current_monitor = None
        
        self.setup_ui()
        self.refresh_monitors()
    
    def setup_ui(self):
        """Setup the monitor control panel interface"""
        if self.standalone:
            self.root.title("Monitor Control Panel")
            self.root.geometry("900x650")
            self.root.resizable(True, True)
            # Apply Plasma theme for standalone mode
            plasma_theme.apply_to_window(self.root)
        
        # Create main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        header_frame = ttk.Frame(main_frame, style='Inner.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="Monitor Control Panel", 
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)
        
        ttk.Button(header_frame, text="Refresh Monitors", 
                  command=self.refresh_monitors).pack(side=tk.RIGHT)
        
        # Monitor selection
        selection_frame = ttk.LabelFrame(main_frame, text="Monitor Selection", padding=10)
        selection_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.monitor_var = tk.StringVar()
        self.monitor_combo = ttk.Combobox(selection_frame, textvariable=self.monitor_var,
                                         state="readonly", width=50)
        self.monitor_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.monitor_combo.bind('<<ComboboxSelected>>', self.on_monitor_selected)
        
        # Create notebook for different control categories
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Basic Controls Tab
        self.basic_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.basic_frame, text="Basic Controls")
        self.setup_basic_controls()
        
        # Input Sources Tab
        self.input_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.input_frame, text="Input Sources")
        self.setup_input_controls()
        
        # Color Settings Tab
        self.color_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.color_frame, text="Color Settings")
        self.setup_color_controls()
        
        # Advanced Controls Tab
        self.advanced_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.advanced_frame, text="Advanced")
        self.setup_advanced_controls()
        
        # Config Management Tab
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="Profiles")
        self.setup_config_controls()
        
        # Status bar with theme colors
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, 
                              relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(10, 0))
        
        # Configure status colors
        status_colors = plasma_theme.get_status_colors()
        style = ttk.Style()
        style.configure('Status.TLabel', foreground=status_colors['info'])
        status_bar.configure(style='Status.TLabel')
    
    def setup_basic_controls(self):
        """Setup basic brightness/contrast controls"""
        # Brightness control
        brightness_frame = ttk.LabelFrame(self.basic_frame, text="Brightness", padding=10)
        brightness_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.brightness_var = tk.IntVar()
        self.brightness_scale = ttk.Scale(brightness_frame, from_=0, to=100,
                                        variable=self.brightness_var, orient=tk.HORIZONTAL,
                                        length=400, command=self.on_brightness_change)
        self.brightness_scale.pack(side=tk.LEFT, padx=(0, 10))
        
        self.brightness_label = ttk.Label(brightness_frame, text="0%")
        self.brightness_label.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(brightness_frame, text="Get Current", 
                  command=self.get_current_brightness).pack(side=tk.LEFT)
        
        # Contrast control
        contrast_frame = ttk.LabelFrame(self.basic_frame, text="Contrast", padding=10)
        contrast_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.contrast_var = tk.IntVar()
        self.contrast_scale = ttk.Scale(contrast_frame, from_=0, to=100,
                                      variable=self.contrast_var, orient=tk.HORIZONTAL,
                                      length=400, command=self.on_contrast_change)
        self.contrast_scale.pack(side=tk.LEFT, padx=(0, 10))
        
        self.contrast_label = ttk.Label(contrast_frame, text="0%")
        self.contrast_label.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(contrast_frame, text="Get Current", 
                  command=self.get_current_contrast).pack(side=tk.LEFT)
    
    def setup_input_controls(self):
        """Setup input source switching controls"""
        input_frame = ttk.LabelFrame(self.input_frame, text="Input Source Selection", padding=10)
        input_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Current input display
        current_frame = ttk.Frame(input_frame, style='Inner.TFrame')
        current_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(current_frame, text="Current Input:").pack(side=tk.LEFT)
        self.current_input_label = ttk.Label(current_frame, text="Unknown", 
                                           font=('Arial', 10, 'bold'))
        self.current_input_label.pack(side=tk.LEFT, padx=(10, 0))
        
        ttk.Button(current_frame, text="Refresh", 
                  command=self.get_current_input).pack(side=tk.RIGHT)
        
        # Input selection buttons
        self.input_buttons_frame = ttk.Frame(input_frame, style='Inner.TFrame')
        self.input_buttons_frame.pack(fill=tk.BOTH, expand=True)
        
        # Will be populated when monitor is selected
    
    def setup_color_controls(self):
        """Setup color preset and RGB controls"""
        # Color presets
        preset_frame = ttk.LabelFrame(self.color_frame, text="Color Presets", padding=10)
        preset_frame.pack(fill=tk.X, padx=10, pady=10)
        
        current_preset_frame = ttk.Frame(preset_frame, style='Inner.TFrame')
        current_preset_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(current_preset_frame, text="Current Preset:").pack(side=tk.LEFT)
        self.current_preset_label = ttk.Label(current_preset_frame, text="Unknown",
                                            font=('Arial', 10, 'bold'))
        self.current_preset_label.pack(side=tk.LEFT, padx=(10, 0))
        
        ttk.Button(current_preset_frame, text="Refresh", 
                  command=self.get_current_preset).pack(side=tk.RIGHT)
        
        self.preset_buttons_frame = ttk.Frame(preset_frame, style='Inner.TFrame')
        self.preset_buttons_frame.pack(fill=tk.BOTH, expand=True)
        
        # RGB Controls (if supported)
        rgb_frame = ttk.LabelFrame(self.color_frame, text="RGB Adjustment", padding=10)
        rgb_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Red
        red_frame = ttk.Frame(rgb_frame, style='Inner.TFrame')
        red_frame.pack(fill=tk.X, pady=2)
        ttk.Label(red_frame, text="Red:", width=10).pack(side=tk.LEFT)
        self.red_var = tk.IntVar()
        ttk.Scale(red_frame, from_=0, to=100, variable=self.red_var, 
                 orient=tk.HORIZONTAL, length=300).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(red_frame, textvariable=self.red_var).pack(side=tk.LEFT)
        
        # Green  
        green_frame = ttk.Frame(rgb_frame, style='Inner.TFrame')
        green_frame.pack(fill=tk.X, pady=2)
        ttk.Label(green_frame, text="Green:", width=10).pack(side=tk.LEFT)
        self.green_var = tk.IntVar()
        ttk.Scale(green_frame, from_=0, to=100, variable=self.green_var,
                 orient=tk.HORIZONTAL, length=300).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(green_frame, textvariable=self.green_var).pack(side=tk.LEFT)
        
        # Blue
        blue_frame = ttk.Frame(rgb_frame, style='Inner.TFrame')
        blue_frame.pack(fill=tk.X, pady=2)
        ttk.Label(blue_frame, text="Blue:", width=10).pack(side=tk.LEFT)
        self.blue_var = tk.IntVar()
        ttk.Scale(blue_frame, from_=0, to=100, variable=self.blue_var,
                 orient=tk.HORIZONTAL, length=300).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(blue_frame, textvariable=self.blue_var).pack(side=tk.LEFT)
        
        ttk.Button(rgb_frame, text="Apply RGB Settings", 
                  command=self.apply_rgb_settings).pack(pady=(10, 0))
    
    def setup_advanced_controls(self):
        """Setup advanced monitor controls"""
        # Power management
        power_frame = ttk.LabelFrame(self.advanced_frame, text="Power Management", padding=10)
        power_frame.pack(fill=tk.X, padx=10, pady=10)
        
        power_buttons_frame = ttk.Frame(power_frame, style='Inner.TFrame')
        power_buttons_frame.pack()
        
        ttk.Button(power_buttons_frame, text="Turn On", 
                  command=lambda: self.set_power_mode('01')).pack(side=tk.LEFT, padx=5)
        ttk.Button(power_buttons_frame, text="Turn Off", 
                  command=lambda: self.set_power_mode('05')).pack(side=tk.LEFT, padx=5)
        ttk.Button(power_buttons_frame, text="Standby", 
                  command=lambda: self.set_power_mode('04')).pack(side=tk.LEFT, padx=5)
        
        # All supported features
        features_frame = ttk.LabelFrame(self.advanced_frame, text="All Features", padding=10)
        features_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create treeview for all features
        columns = ('Feature', 'Name', 'Current Value', 'Possible Values')
        self.features_tree = ttk.Treeview(features_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.features_tree.heading(col, text=col)
            self.features_tree.column(col, width=150)
        
        scrollbar = ttk.Scrollbar(features_frame, orient=tk.VERTICAL, command=self.features_tree.yview)
        self.features_tree.configure(yscrollcommand=scrollbar.set)
        
        self.features_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Feature control
        control_frame = ttk.Frame(features_frame, style='Inner.TFrame')
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(control_frame, text="Set Value:").pack(side=tk.LEFT)
        self.feature_value_var = tk.StringVar()
        ttk.Entry(control_frame, textvariable=self.feature_value_var, width=10).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(control_frame, text="Apply", command=self.apply_feature_value).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(control_frame, text="Refresh All", command=self.refresh_features).pack(side=tk.LEFT, padx=(5, 0))
    
    def setup_config_controls(self):
        """Setup configuration save/load controls"""
        config_frame = ttk.LabelFrame(self.config_frame, text="Monitor Profiles", padding=10)
        config_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Current config display
        current_config_frame = ttk.Frame(config_frame, style='Inner.TFrame')
        current_config_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(current_config_frame, text="Export Current Settings", 
                  command=self.export_config).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(current_config_frame, text="Import Settings", 
                  command=self.import_config).pack(side=tk.LEFT)
        
        # Quick presets
        preset_frame = ttk.LabelFrame(config_frame, text="Quick Presets", padding=10)
        preset_frame.pack(fill=tk.X, pady=(10, 0))
        
        preset_buttons_frame = ttk.Frame(preset_frame, style='Inner.TFrame')
        preset_buttons_frame.pack()
        
        ttk.Button(preset_buttons_frame, text="Gaming Mode", 
                  command=lambda: self.apply_preset("gaming")).pack(side=tk.LEFT, padx=5)
        ttk.Button(preset_buttons_frame, text="Movie Mode", 
                  command=lambda: self.apply_preset("movie")).pack(side=tk.LEFT, padx=5)
        ttk.Button(preset_buttons_frame, text="Work Mode", 
                  command=lambda: self.apply_preset("work")).pack(side=tk.LEFT, padx=5)
    
    def refresh_monitors(self):
        """Refresh the list of available monitors"""
        self.update_status("Detecting monitors...", 'warning')
        
        def detect_thread():
            self.monitors = self.monitor_control.detect_monitors()
            self.root.after(0, self.update_monitor_list)
        
        threading.Thread(target=detect_thread, daemon=True).start()
    
    def update_monitor_list(self):
        """Update the monitor selection combobox"""
        monitor_list = []
        for monitor_id, info in self.monitors.items():
            display_name = f"Display {monitor_id}: {info['model']} (Bus {info['i2c_bus']})"
            monitor_list.append(display_name)
        
        self.monitor_combo['values'] = monitor_list
        if monitor_list:
            self.monitor_combo.current(0)
            self.on_monitor_selected(None)
        
        if monitor_list:
            self.update_status(f"Found {len(monitor_list)} monitor(s)", 'success')
        else:
            self.update_status("No monitors detected", 'error')
    
    def on_monitor_selected(self, event):
        """Handle monitor selection change"""
        selection = self.monitor_combo.get()
        if not selection:
            return
        
        # Extract monitor ID from selection
        monitor_id = selection.split(':')[0].replace('Display ', '')
        self.current_monitor = self.monitors.get(monitor_id)
        
        if self.current_monitor:
            self.update_controls_for_monitor()
            self.update_status(f"Selected: {self.current_monitor['model']}", 'info')
    
    def update_controls_for_monitor(self):
        """Update all controls based on the selected monitor"""
        if not self.current_monitor:
            return
        
        bus = self.current_monitor['i2c_bus']
        capabilities = self.current_monitor.get('capabilities', {})
        features = capabilities.get('features', {})
        
        # Update input source buttons
        self.update_input_buttons(features.get('60', {}))
        
        # Update color preset buttons  
        self.update_preset_buttons(features.get('14', {}))
        
        # Get current values
        self.get_current_brightness()
        self.get_current_contrast()
        self.get_current_input()
        self.get_current_preset()
        
        # Update features tree
        self.refresh_features()
    
    def update_input_buttons(self, input_feature):
        """Update input source selection buttons"""
        # Clear existing buttons
        for widget in self.input_buttons_frame.winfo_children():
            widget.destroy()
        
        values = input_feature.get('values', {})
        if not values:
            ttk.Label(self.input_buttons_frame, text="Input switching not supported").pack()
            return
        
        for code, name in values.items():
            ttk.Button(self.input_buttons_frame, text=name,
                      command=lambda c=code: self.set_input_source(c)).pack(side=tk.LEFT, padx=5, pady=5)
    
    def update_preset_buttons(self, preset_feature):
        """Update color preset buttons"""
        # Clear existing buttons
        for widget in self.preset_buttons_frame.winfo_children():
            widget.destroy()
        
        values = preset_feature.get('values', {})
        if not values:
            ttk.Label(self.preset_buttons_frame, text="Color presets not supported").pack()
            return
        
        for code, name in values.items():
            ttk.Button(self.preset_buttons_frame, text=name,
                      command=lambda c=code: self.set_color_preset(c)).pack(side=tk.LEFT, padx=5, pady=5)
    
    def refresh_features(self):
        """Refresh the features tree with current values"""
        if not self.current_monitor:
            return
        
        # Clear existing items
        for item in self.features_tree.get_children():
            self.features_tree.delete(item)
        
        bus = self.current_monitor['i2c_bus']
        features = self.current_monitor.get('capabilities', {}).get('features', {})
        
        for feature_code, feature_info in features.items():
            name = feature_info.get('name', 'Unknown')
            values = feature_info.get('values', {})
            
            # Get current value
            current_value = self.monitor_control.get_vcp_value(bus, feature_code)
            current_str = str(current_value) if current_value is not None else "Unknown"
            
            # Format possible values
            if values:
                possible_values = ", ".join([f"{k}:{v}" for k, v in values.items()])
            else:
                possible_values = "0-100" if feature_code in ['10', '12'] else "Variable"
            
            self.features_tree.insert('', tk.END, values=(feature_code, name, current_str, possible_values))
    
    def apply_feature_value(self):
        """Apply a value to the selected feature"""
        selection = self.features_tree.selection()
        if not selection or not self.current_monitor:
            return
        
        item = self.features_tree.item(selection[0])
        feature_code = item['values'][0]
        
        try:
            value = int(self.feature_value_var.get())
            bus = self.current_monitor['i2c_bus']
            
            if self.monitor_control.set_vcp_value(bus, feature_code, value):
                self.update_status(f"Set feature {feature_code} to {value}")
                self.refresh_features()
            else:
                self.update_status(f"Failed to set feature {feature_code}")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number")
    
    # Event handlers for controls
    def on_brightness_change(self, value):
        val = int(float(value))
        self.brightness_label.config(text=f"{val}%")
        if self.current_monitor:
            bus = self.current_monitor['i2c_bus']
            self.monitor_control.set_brightness(bus, val)
    
    def on_contrast_change(self, value):
        val = int(float(value))
        self.contrast_label.config(text=f"{val}%")
        if self.current_monitor:
            bus = self.current_monitor['i2c_bus']
            self.monitor_control.set_contrast(bus, val)
    
    def get_current_brightness(self):
        if self.current_monitor:
            bus = self.current_monitor['i2c_bus']
            brightness = self.monitor_control.get_brightness(bus)
            if brightness is not None:
                self.brightness_var.set(brightness)
                self.brightness_label.config(text=f"{brightness}%")
    
    def get_current_contrast(self):
        if self.current_monitor:
            bus = self.current_monitor['i2c_bus']
            contrast = self.monitor_control.get_contrast(bus)
            if contrast is not None:
                self.contrast_var.set(contrast)
                self.contrast_label.config(text=f"{contrast}%")
    
    def get_current_input(self):
        if self.current_monitor:
            bus = self.current_monitor['i2c_bus']
            input_code = self.monitor_control.get_input_source(bus)
            if input_code:
                # Find the name for this input code
                features = self.current_monitor.get('capabilities', {}).get('features', {})
                input_feature = features.get('60', {})
                input_name = input_feature.get('values', {}).get(input_code, f"Code {input_code}")
                self.current_input_label.config(text=input_name)
    
    def get_current_preset(self):
        if self.current_monitor:
            bus = self.current_monitor['i2c_bus']
            preset_code = self.monitor_control.get_color_preset(bus)
            if preset_code:
                # Find the name for this preset code
                features = self.current_monitor.get('capabilities', {}).get('features', {})
                preset_feature = features.get('14', {})
                preset_name = preset_feature.get('values', {}).get(preset_code, f"Code {preset_code}")
                self.current_preset_label.config(text=preset_name)
    
    def set_input_source(self, input_code):
        if self.current_monitor:
            bus = self.current_monitor['i2c_bus']
            if self.monitor_control.set_input_source(bus, input_code):
                self.update_status(f"Switched to input {input_code}")
                self.get_current_input()
            else:
                self.update_status("Failed to switch input")
    
    def set_color_preset(self, preset_code):
        if self.current_monitor:
            bus = self.current_monitor['i2c_bus']
            if self.monitor_control.set_color_preset(bus, preset_code):
                self.update_status(f"Applied color preset {preset_code}")
                self.get_current_preset()
            else:
                self.update_status("Failed to apply preset")
    
    def set_power_mode(self, power_code):
        if self.current_monitor:
            bus = self.current_monitor['i2c_bus']
            if self.monitor_control.set_power_mode(bus, power_code):
                self.update_status(f"Set power mode {power_code}")
            else:
                self.update_status("Failed to set power mode")
    
    def apply_rgb_settings(self):
        if not self.current_monitor:
            return
        
        bus = self.current_monitor['i2c_bus']
        success = True
        
        # Set Red (feature 16)
        if not self.monitor_control.set_vcp_value(bus, '16', self.red_var.get()):
            success = False
        
        # Set Green (feature 18)
        if not self.monitor_control.set_vcp_value(bus, '18', self.green_var.get()):
            success = False
        
        # Set Blue (feature 1A)
        if not self.monitor_control.set_vcp_value(bus, '1A', self.blue_var.get()):
            success = False
        
        if success:
            self.update_status("RGB settings applied")
        else:
            self.update_status("Failed to apply some RGB settings")
    
    def export_config(self):
        if not self.current_monitor:
            return
        
        bus = self.current_monitor['i2c_bus']
        config = self.monitor_control.export_monitor_config(bus)
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export Monitor Configuration"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(config, f, indent=2)
                self.update_status(f"Configuration exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export configuration: {e}")
    
    def import_config(self):
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Import Monitor Configuration"
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    config = json.load(f)
                
                if self.monitor_control.import_monitor_config(config):
                    self.update_status(f"Configuration imported from {filename}")
                    self.update_controls_for_monitor()
                else:
                    self.update_status("Failed to import configuration")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import configuration: {e}")
    
    def apply_preset(self, preset_name):
        """Apply a predefined preset configuration"""
        presets = {
            "gaming": {"brightness": 80, "contrast": 75, "color_preset": "05"},
            "movie": {"brightness": 40, "contrast": 60, "color_preset": "08"},
            "work": {"brightness": 60, "contrast": 70, "color_preset": "0B"}
        }
        
        preset = presets.get(preset_name)
        if not preset or not self.current_monitor:
            return
        
        bus = self.current_monitor['i2c_bus']
        
        # Apply settings
        self.monitor_control.set_brightness(bus, preset["brightness"])
        self.monitor_control.set_contrast(bus, preset["contrast"])
        self.monitor_control.set_color_preset(bus, preset["color_preset"])
        
        self.update_status(f"Applied {preset_name} preset")
        self.update_controls_for_monitor()
    
    def update_status(self, message, status_type='info'):
        """Update the status bar with themed colors"""
        self.status_var.set(message)
        
        # Apply appropriate color based on status type
        status_colors = plasma_theme.get_status_colors()
        style = ttk.Style()
        
        if status_type == 'success':
            style.configure('Status.TLabel', foreground=status_colors['success'])
        elif status_type == 'warning':
            style.configure('Status.TLabel', foreground=status_colors['warning'])
        elif status_type == 'error':
            style.configure('Status.TLabel', foreground=status_colors['error'])
        else:  # info
            style.configure('Status.TLabel', foreground=status_colors['info'])
        
        self.root.update_idletasks()
    
    def run(self):
        """Run the GUI (for standalone mode)"""
        if self.standalone:
            self.root.mainloop()

if __name__ == "__main__":
    app = MonitorControlGUI()
    app.run()