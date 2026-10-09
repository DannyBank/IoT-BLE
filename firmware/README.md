# ESP32 firmware

Copy `main.py`, `bmp280.py` and `ahtx0.py` to the ESP32 (all three in the same folder).

Pins (from your config): button GPIO18, DHT11 GPIO4, buzzer GPIO12, TEMT6000 GPIO34, I2C SDA 21 / SCL 22.
GPIO12 is a boot-strapping pin: if the board fails to boot with the buzzer attached, move it to e.g. GPIO19.

Topics published: `temt6000/light` (%), `temt6000/raw`, `aht20/temperature`, `aht20/humidity`,
`bmp280/temperature`, `bmp280/pressure` (hPa), `dht11/temperature`, `dht11/humidity`, `button/state`, `buzzer/status`.
Buzzer commands: `PUB buzzer/state ON|OFF|<Hz>`, `buzzer/beep <ms>`, `buzzer/play CHIRP|ALARM|SOS`, `buzzer/freq <Hz>`.

On boot the REPL prints `[I2C] devices found: [...]` - expect 0x38 (AHT20) and 0x76 or 0x77 (BMP280).

## WiFi (alternative to Bluetooth)

The ESP32 runs Bluetooth **and** WiFi at the same time. WiFi carries the exact same `SUB` / `PUB` / `MQTT:topic:payload` messages over a WebSocket (`ws://<ip>/ws`), and the device also serves the web app itself from `/www`.

1. `cp wifi_config.example.py wifi_config.py`, then set `SSID`, `PASSWORD` (and change `AP_PASSWORD`).
2. `pip install mpremote`, connect the board over USB, run `./upload.sh` (copies the firmware + the web app to `/www`).
3. Watch the REPL for `[WiFi] Connected. Browse to http://192.168.x.x/`.
4. On any phone/PC on the same network open that address. The app picks WiFi automatically when Bluetooth isn't available.

If the router can't be joined within `STA_TIMEOUT_S`, the board starts its own access point (`AP_SSID`) - join it and browse to `http://192.168.4.1/`.

In the app, **Auto** tries Bluetooth first and falls back to WiFi. After one successful Bluetooth connection the ESP32 reports its WiFi address (`sys/ip`) and the app remembers it.

Notes:
- Open the app as `http://...` (served by the ESP32 or a local file). An `https://` page (e.g. GitHub Pages) can't open `ws://` connections - browsers block it as mixed content.
- Up to 3 WiFi clients plus Bluetooth at once. There is no password on the WebSocket, so only run it on a network you trust.
- If Bluetooth can't start, the device logs it and keeps working over WiFi.
