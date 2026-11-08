#!/bin/bash

CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/donut-monitor-control/config.json"

case "$1" in
    "get_config")
        if [ -f "$CONFIG_FILE" ]; then
            cat "$CONFIG_FILE"
        else
            echo '{"min_brightness": 0.3, "max_brightness": 1.0}'
        fi
        ;;
    "set_config")
        echo "$2" > "$CONFIG_FILE"
        systemctl --user restart donut-monitord.service
        echo "Config updated and service restarted"
        ;;
    "restart_service")
        systemctl --user restart donut-monitord.service
        echo "Service restarted"
        ;;
    "check_service")
        if systemctl --user is-active --quiet donut-monitord.service; then
            echo "active"
        else
            echo "inactive"
        fi
        ;;
    *)
        echo "Usage: $0 {get_config|set_config|restart_service|check_service}"
        exit 1
        ;;
esac