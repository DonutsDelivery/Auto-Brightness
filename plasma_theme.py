#!/usr/bin/env python3

import subprocess
import tkinter as tk
from tkinter import ttk
import os

class PlasmaTheme:
    """KDE Plasma theme integration for tkinter applications"""
    
    def __init__(self):
        self.colors = {}
        self.fonts = {}
        self.load_plasma_theme()
        
    def load_plasma_theme(self):
        """Load color scheme and fonts from KDE Plasma"""
        try:
            # Get color scheme name
            self.scheme_name = self._get_kde_config('General', 'ColorScheme') or 'Default'
            
            # Load colors
            self.colors = {
                'window_bg': self._parse_rgb(self._get_kde_config('Colors:Window', 'BackgroundNormal')),
                'window_fg': self._parse_rgb(self._get_kde_config('Colors:Window', 'ForegroundNormal')),
                'button_bg': self._parse_rgb(self._get_kde_config('Colors:Button', 'BackgroundNormal')),
                'button_fg': self._parse_rgb(self._get_kde_config('Colors:Button', 'ForegroundNormal')),
                'view_bg': self._parse_rgb(self._get_kde_config('Colors:View', 'BackgroundNormal')),
                'view_fg': self._parse_rgb(self._get_kde_config('Colors:View', 'ForegroundNormal')),
                'selection_bg': self._parse_rgb(self._get_kde_config('Colors:Selection', 'BackgroundNormal')),
                'selection_fg': self._parse_rgb(self._get_kde_config('Colors:Selection', 'ForegroundNormal')),
                'tooltip_bg': self._parse_rgb(self._get_kde_config('Colors:Tooltip', 'BackgroundNormal')),
                'tooltip_fg': self._parse_rgb(self._get_kde_config('Colors:Tooltip', 'ForegroundNormal')),
            }
            
            # Fallback colors if KDE config fails
            if not any(self.colors.values()):
                self._set_fallback_colors()
            
            # Additional derived colors
            self._derive_additional_colors()
            
        except Exception as e:
            print(f"Failed to load Plasma theme: {e}")
            self._set_fallback_colors()
    
    def _get_kde_config(self, group, key):
        """Get configuration value from KDE"""
        try:
            result = subprocess.run(
                ['kreadconfig5', '--group', group, '--key', key],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def _parse_rgb(self, rgb_string):
        """Parse RGB string from KDE config (e.g., '45,55,66')"""
        if not rgb_string:
            return None
        try:
            r, g, b = map(int, rgb_string.split(','))
            return f"#{r:02x}{g:02x}{b:02x}"
        except (ValueError, AttributeError):
            return None
    
    def _set_fallback_colors(self):
        """Set fallback colors for dark theme"""
        self.colors = {
            'window_bg': '#2d3742',
            'window_fg': '#fcfdfd',
            'button_bg': '#34404c',
            'button_fg': '#fcfdfd',
            'view_bg': '#2d3742',
            'view_fg': '#fcfdfd',
            'selection_bg': '#9267d7',
            'selection_fg': '#ffffff',
            'tooltip_bg': '#31363b',
            'tooltip_fg': '#eff0f1',
        }
    
    def _derive_additional_colors(self):
        """Derive additional colors from base colors"""
        # Hover colors (slightly lighter)
        self.colors['button_hover'] = self._lighten_color(self.colors['button_bg'], 0.1)
        self.colors['button_active'] = self._lighten_color(self.colors['button_bg'], 0.2)
        
        # Disabled colors (semi-transparent)
        self.colors['disabled_fg'] = self._blend_colors(self.colors['window_fg'], self.colors['window_bg'], 0.5)
        
        # Frame/border colors
        self.colors['frame_bg'] = self._lighten_color(self.colors['window_bg'], 0.05)
        self.colors['border'] = self._lighten_color(self.colors['window_bg'], 0.2)
        
        # Scale/progress colors
        self.colors['scale_trough'] = self._darken_color(self.colors['window_bg'], 0.1)
        self.colors['scale_thumb'] = self.colors['selection_bg']
    
    def _lighten_color(self, color, factor):
        """Lighten a color by a factor (0-1)"""
        if not color or not color.startswith('#'):
            return color
        
        r = int(color[1:3], 16)
        g = int(color[3:5], 16) 
        b = int(color[5:7], 16)
        
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def _darken_color(self, color, factor):
        """Darken a color by a factor (0-1)"""
        if not color or not color.startswith('#'):
            return color
            
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def _blend_colors(self, color1, color2, alpha):
        """Blend two colors with alpha (0-1)"""
        if not color1 or not color2 or not color1.startswith('#') or not color2.startswith('#'):
            return color1
            
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        
        r = int(r1 * alpha + r2 * (1 - alpha))
        g = int(g1 * alpha + g2 * (1 - alpha))
        b = int(b1 * alpha + b2 * (1 - alpha))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def is_dark_theme(self):
        """Check if current theme is dark"""
        bg = self.colors.get('window_bg', '#ffffff')
        if bg and bg.startswith('#'):
            # Calculate luminance
            r = int(bg[1:3], 16) / 255
            g = int(bg[3:5], 16) / 255
            b = int(bg[5:7], 16) / 255
            luminance = 0.299 * r + 0.587 * g + 0.114 * b
            return luminance < 0.5
        return False
    
    def configure_ttk_style(self):
        """Configure ttk styles to match Plasma theme"""
        style = ttk.Style()
        
        # Configure basic styles
        style.configure('TLabel',
                       background=self.colors['window_bg'],
                       foreground=self.colors['window_fg'],
                       font=('Liberation Sans', 9))
        
        style.configure('TFrame',
                       background=self.colors['window_bg'],
                       borderwidth=0)
        
        style.configure('TLabelFrame',
                       background=self.colors['window_bg'],
                       foreground=self.colors['window_fg'],
                       borderwidth=1,
                       relief='solid',
                       bordercolor=self.colors['border'])
        
        style.configure('TLabelFrame.Label',
                       background=self.colors['window_bg'],
                       foreground=self.colors['window_fg'],
                       font=('Liberation Sans', 9, 'bold'))
        
        # Configure all nested frames to use theme background
        style.configure('Inner.TFrame',
                       background=self.colors['window_bg'])
        
        style.configure('Control.TFrame', 
                       background=self.colors['window_bg'])
        
        # Button styles
        style.configure('TButton',
                       background=self.colors['button_bg'],
                       foreground=self.colors['button_fg'],
                       borderwidth=1,
                       relief='raised',
                       font=('Liberation Sans', 9))
        
        style.map('TButton',
                 background=[('active', self.colors['button_hover']),
                           ('pressed', self.colors['button_active'])],
                 relief=[('pressed', 'sunken')])
        
        # Notebook styles (Plasma-like tabs)
        style.configure('TNotebook',
                       background=self.colors['window_bg'],
                       borderwidth=1,
                       bordercolor=self.colors['border'])
        
        style.configure('TNotebook.Tab',
                       background=self.colors['button_bg'],
                       foreground=self.colors['button_fg'],
                       padding=[16, 10],
                       borderwidth=1,
                       font=('Liberation Sans', 9))
        
        style.map('TNotebook.Tab',
                 background=[('selected', self.colors['selection_bg']),
                           ('active', self.colors['button_hover'])],
                 foreground=[('selected', self.colors['selection_fg'])],
                 bordercolor=[('selected', self.colors['selection_bg'])])
        
        # Scale styles
        style.configure('TScale',
                       background=self.colors['window_bg'],
                       troughcolor=self.colors['scale_trough'],
                       borderwidth=0,
                       lightcolor=self.colors['scale_thumb'],
                       darkcolor=self.colors['scale_thumb'])
        
        # Combobox styles
        style.configure('TCombobox',
                       background=self.colors['view_bg'],
                       foreground=self.colors['view_fg'],
                       fieldbackground=self.colors['view_bg'],
                       borderwidth=1,
                       relief='solid',
                       bordercolor=self.colors['border'])
        
        # Entry styles
        style.configure('TEntry',
                       background=self.colors['view_bg'],
                       foreground=self.colors['view_fg'],
                       fieldbackground=self.colors['view_bg'],
                       borderwidth=1,
                       relief='solid',
                       bordercolor=self.colors['border'])
        
        # Treeview styles
        style.configure('Treeview',
                       background=self.colors['view_bg'],
                       foreground=self.colors['view_fg'],
                       fieldbackground=self.colors['view_bg'],
                       borderwidth=0)
        
        style.configure('Treeview.Heading',
                       background=self.colors['button_bg'],
                       foreground=self.colors['button_fg'],
                       font=('Liberation Sans', 9, 'bold'))
        
        style.map('Treeview',
                 background=[('selected', self.colors['selection_bg'])],
                 foreground=[('selected', self.colors['selection_fg'])])
        
        # Progressbar styles
        style.configure('TProgressbar',
                       background=self.colors['selection_bg'],
                       troughcolor=self.colors['scale_trough'],
                       borderwidth=0,
                       lightcolor=self.colors['selection_bg'],
                       darkcolor=self.colors['selection_bg'])
    
    def apply_to_window(self, window):
        """Apply theme to a tkinter window"""
        if hasattr(window, 'configure'):
            window.configure(bg=self.colors['window_bg'])
        
        # Configure ttk styles
        self.configure_ttk_style()
    
    def get_status_colors(self):
        """Get colors for status indicators"""
        if self.is_dark_theme():
            return {
                'success': '#27ae60',  # Green
                'warning': '#f39c12',  # Orange
                'error': '#e74c3c',    # Red
                'info': '#3498db'      # Blue
            }
        else:
            return {
                'success': '#2ecc71',
                'warning': '#e67e22', 
                'error': '#c0392b',
                'info': '#2980b9'
            }

# Global theme instance
plasma_theme = PlasmaTheme()