# ESP32 firmware

Copy `main.py`, `bmp280.py` and `ahtx0.py` to the ESP32 (all three in the same folder).

Pins (from your config): button GPIO18, DHT11 GPIO4, buzzer GPIO12, TEMT6000 GPIO34, I2C SDA 21 / SCL 22.
GPIO12 is a boot-strapping pin: if the board fails to boot with the buzzer attached, move it to e.g. GPIO19.

Topics published: `temt6000/light` (%), `temt6000/raw`, `aht20/temperature`, `aht20/humidity`,
`bmp280/temperature`, `bmp280/pressure` (hPa), `dht11/temperature`, `dht11/humidity`, `button/state`, `buzzer/status`.
Buzzer commands: `PUB buzzer/state ON|OFF|<Hz>`, `buzzer/beep <ms>`, `buzzer/play CHIRP|ALARM|SOS`, `buzzer/freq <Hz>`.

On boot the REPL prints `[I2C] devices found: [...]` - expect 0x38 (AHT20) and 0x76 or 0x77 (BMP280).
