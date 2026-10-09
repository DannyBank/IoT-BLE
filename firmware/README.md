# New sensors – firmware side

Copy `aht20.py`, `bmp280.py`, `sensors.py` to the ESP32 (same folder as your `main.py`).

## Wiring (edit the PIN_* constants at the top of `sensors.py` if you need other pins)

| Part | Sensor pin | ESP32 pin | Notes |
|---|---|---|---|
| AHT20 + BMP280 | VCC / GND | 3V3 / GND | one combined board, shared I2C bus |
| | SDA / SCL | GPIO21 / GPIO22 | addresses 0x38 (AHT20) and 0x76/0x77 (BMP280) auto-detected |
| TEMT6000 | VCC / GND | 3V3 / GND | power from 3.3 V, never 5 V (ADC limit) |
| | SIG | GPIO34 | ADC1, input only |
| DHT11 | VCC / GND | 3V3 / GND | |
| | DATA | GPIO4 | 10 kΩ pull-up to 3V3 if it's a bare 4-pin sensor (3-pin modules have it) |
| Push button | one leg | GPIO27 | other leg to GND, internal pull-up is used |
| Buzzer | + | GPIO25 | – to GND. Active buzzer: `BUZZER_PASSIVE = False` (default). Passive: set `True` |

**Check these against the pins already used by your NeoPixel ring, PIR, servo and traffic LEDs.**

## Hook into your existing broker (3 lines)

```python
import sensors

# 1) after BLE is set up. This must send the same "MQTT:<topic>:<payload>" notification your PIR uses
def publish(topic, payload):
    ble_notify("MQTT:%s:%s" % (topic, payload))     # <- your existing notify/publish function
sensors.init(publish)

# 2) in your PUB command handler, before the existing if/elif chain
if sensors.handle(topic, payload):
    return

# 3) in your main loop (called at least every ~20 ms; avoid long sleeps)
sensors.poll()
```

## Topics

Published by the ESP32 (web app auto-subscribes):
`light/lux`, `aht/temp`, `aht/hum`, `bmp/temp`, `bmp/hpa`, `dht/temp`, `dht/hum`, `btn/state` (1 = pressed), `buzz/on` (1/0).
A failed read is sent as `NA` and shows as `--` in the app.

Commands from the web app: `PUB buzz/set ON|OFF`, `PUB buzz/beep <ms>`, `PUB buzz/play CHIRP|ALARM|SOS`, `PUB buzz/freq <Hz>`.

Topic names are short on purpose: every message stays under 20 bytes so it fits a default BLE notification (MTU 23).
If your broker only forwards topics it knows, add these to its subscribe list.

## Notes
- TEMT6000 lux is an estimate (5 mV/lux on a 10 kΩ breakout) and saturates near ~600 lux at 3.3 V – fine for indoor light, not for sunlight.
- DHT11 reads block ~20 ms with interrupts off, so it's polled only every 5 s. AHT20 conversion is non-blocking.
- Intervals/debounce are constants at the top of `sensors.py`.
