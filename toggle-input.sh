#!/bin/bash

# Toggle Input Source Script
# Switches between DP-1 and HDMI-1 input sources using DDC/CI

# VCP code 60 (0x3C) is for input source selection
# Common values: 15=DP-1, 17=HDMI-1 (values may vary by monitor)

# Get current input source from Philips monitor only
current_input=$(ddcutil --mfg=PHL getvcp 60 2>/dev/null | grep -o 'sl=0x[0-9a-f]*' | cut -d'=' -f2)

if [ -z "$current_input" ]; then
    echo "Error: Could not detect current input source"
    notify-send "Input Toggle" "Error: Could not detect current input source" --icon=dialog-error
    exit 1
fi

# Toggle between inputs
case $current_input in
    "0x0f")
        # Currently on DisplayPort-1, switch to HDMI-1
        ddcutil --mfg=PHL setvcp 60 17
        if [ $? -eq 0 ]; then
            notify-send "Input Toggle" "Switched to HDMI-1" --icon=video-display
        else
            notify-send "Input Toggle" "Failed to switch to HDMI-1" --icon=dialog-error
        fi
        ;;
    "0x11")
        # Currently on HDMI-1, switch to DisplayPort-1
        ddcutil --mfg=PHL setvcp 60 15
        if [ $? -eq 0 ]; then
            notify-send "Input Toggle" "Switched to DisplayPort-1" --icon=video-display
        else
            notify-send "Input Toggle" "Failed to switch to DisplayPort-1" --icon=dialog-error
        fi
        ;;
    *)
        # Unknown input, default to DisplayPort-1
        ddcutil --mfg=PHL setvcp 60 15
        if [ $? -eq 0 ]; then
            notify-send "Input Toggle" "Set to DisplayPort-1 (was unknown input $current_input)" --icon=video-display
        else
            notify-send "Input Toggle" "Failed to set DisplayPort-1" --icon=dialog-error
        fi
        ;;
esac