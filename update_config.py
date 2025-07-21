#!/usr/bin/env python3
import sys
import json
import os

def update_config(config_json):
    config_path = "/home/user/Documents/auto-brightness/config.json"
    try:
        config = json.loads(config_json)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print("Config updated successfully")
        return 0
    except Exception as e:
        print(f"Error updating config: {e}")
        return 1

if __name__ == "__main__":
    if len(sys.argv) > 1:
        exit(update_config(sys.argv[1]))
    else:
        exit(1)