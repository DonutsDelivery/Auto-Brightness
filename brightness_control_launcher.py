#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk
import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brightness_gui import BrightnessControlGUI
from monitor_control_gui import MonitorControlGUI

def main():
    """Main launcher for brightness and monitor control"""
    if len(sys.argv) > 1 and sys.argv[1] == "--monitor-only":
        # Launch only monitor control panel
        app = MonitorControlGUI()
        app.run()
    else:
        # Launch integrated brightness control with monitor panel
        app = BrightnessControlGUI()
        app.run()

if __name__ == "__main__":
    main()