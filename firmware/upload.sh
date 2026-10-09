#!/bin/sh
# Copies the firmware and the web app to the ESP32 with mpremote (pip install mpremote).
# Usage: ./upload.sh            (run from the firmware/ folder, board connected over USB)
set -e
cd "$(dirname "$0")"
mpremote fs cp main.py bmp280.py ahtx0.py wifi_link.py :
[ -f wifi_config.py ] && mpremote fs cp wifi_config.py : || echo "!! no wifi_config.py - copy wifi_config.example.py and edit it"
mpremote fs mkdir :www 2>/dev/null || true
mpremote fs mkdir :www/css 2>/dev/null || true
mpremote fs mkdir :www/js 2>/dev/null || true
mpremote fs cp ../index.html :www/index.html
for f in ../css/*.css; do mpremote fs cp "$f" ":www/css/$(basename "$f")"; done
for f in ../js/*.js;  do mpremote fs cp "$f" ":www/js/$(basename "$f")";  done
mpremote reset
