# Copy this file to the ESP32 as  wifi_config.py  and fill it in.
# (wifi_config.py is git-ignored so your password never gets committed.)

SSID = "YourWiFiName"        # leave "" to always run as an access point
PASSWORD = "YourWiFiPassword"
HOSTNAME = "esp32-hub"

# Fallback access point, used when the router can't be joined within STA_TIMEOUT_S.
# Join it from your phone, then browse to http://192.168.4.1/
AP_SSID = "ESP32-Hub"
AP_PASSWORD = "esp32hub123"  # 8+ characters (WPA2). CHANGE THIS.
STA_TIMEOUT_S = 15
