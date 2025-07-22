#!/usr/bin/env python3

import os
import sys
import subprocess

def setup_kirigami_environment():
    """Setup environment variables for Kirigami"""
    # Add Qt QML import paths
    qml_paths = [
        "/usr/lib/qt/qml",
        "/usr/lib/qt6/qml", 
        "/usr/lib/x86_64-linux-gnu/qt5/qml",
        "/usr/lib/x86_64-linux-gnu/qt6/qml"
    ]
    
    existing_path = os.environ.get('QML2_IMPORT_PATH', '')
    if existing_path:
        qml_paths.append(existing_path)
    
    # Set QML import path
    os.environ['QML2_IMPORT_PATH'] = ':'.join(qml_paths)
    
    # Set Qt platform
    if 'QT_QPA_PLATFORM' not in os.environ:
        os.environ['QT_QPA_PLATFORM'] = 'xcb'

def try_kirigami_launch():
    """Try to launch the Kirigami interface"""
    try:
        setup_kirigami_environment()
        
        # Try to launch Kirigami version
        kirigami_script = os.path.join(os.path.dirname(__file__), 'brightness_kirigami.py')
        if os.path.exists(kirigami_script):
            print("Attempting to launch Kirigami interface...")
            subprocess.run([sys.executable, kirigami_script], check=True)
            return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Kirigami launch failed: {e}")
        return False

def fallback_tkinter_launch():
    """Fallback to the tkinter interface"""
    try:
        print("Falling back to tkinter interface...")
        tkinter_script = os.path.join(os.path.dirname(__file__), 'brightness_control_launcher.py')
        if os.path.exists(tkinter_script):
            subprocess.run([sys.executable, tkinter_script], check=True)
            return True
        else:
            print("Tkinter launcher not found")
            return False
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Tkinter launch failed: {e}")
        return False

def main():
    """Main launcher with fallback support"""
    print("Auto Brightness & Monitor Control Launcher")
    print("==========================================")
    
    # Try Kirigami first
    if try_kirigami_launch():
        print("Kirigami interface launched successfully")
        return 0
    
    print("\nKirigami interface unavailable, trying tkinter fallback...")
    
    # Fallback to tkinter
    if fallback_tkinter_launch():
        print("Tkinter interface launched successfully")
        return 0
    
    print("\nBoth interfaces failed to launch")
    print("Please check your Python environment and dependencies")
    return 1

if __name__ == "__main__":
    sys.exit(main())