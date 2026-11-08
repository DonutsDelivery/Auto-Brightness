#!/usr/bin/env python3

print("=== TESTING ENHANCED INTERFACE ===")

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

try:
    from brightness_gui import BrightnessControlGUI
    print("✓ Successfully imported BrightnessControlGUI")
    
    app = BrightnessControlGUI()
    print(f"✓ Created GUI instance")
    print(f"✓ Window title: {app.root.title()}")
    print(f"✓ Window size: {app.root.geometry()}")
    print(f"✓ Has auto_brightness_enabled: {hasattr(app, 'auto_brightness_enabled')}")
    print(f"✓ Has location_override: {hasattr(app, 'location_override')}")
    print(f"✓ Has notebook: {hasattr(app, 'notebook')}")
    
    print("\n=== LAUNCHING ENHANCED INTERFACE ===")
    app.run()
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()