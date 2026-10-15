import bluetooth
import time
import neopixel
import dht
from machine import Pin, PWM, ADC, I2C
from micropython import const
import sys
import gc
import math
import random

# Optional pieces: if a file didn't get copied to the board (or won't compile for lack of
# RAM) the hub still boots, with Bluetooth + whatever else works. Check the REPL for "[!]".
try:
    import ahtx0
except Exception as e:
    ahtx0 = None
    print("[!] ahtx0.py unavailable - AHT20 disabled:", e)
try:
    from bmp280 import BMP280
except Exception as e:
    BMP280 = None
    print("[!] bmp280.py unavailable - BMP280 disabled:", e)
try:
    import wifi_link
except Exception as e:
    wifi_link = None
    print("[!] wifi_link.py unavailable - WiFi disabled:", e)

WIFI_HANDLE_BASE = 1000      # WiFi client ids (BLE connection handles are small ints)
gc.collect()
print("[BOOT] imports done, free RAM:", gc.mem_free())

# ==========================================
# HARDWARE CONFIGURATION
# ==========================================

LED_RING_PIN = 14
PIR_PIN = 27
SERVO_PIN = 13
TRAFFIC_RED_PIN = 25
TRAFFIC_YELLOW_PIN = 26
TRAFFIC_GREEN_PIN = 33

# --- NEW HARDWARE PINS & CONFIGURATIONS ---
BUTTON_PIN = 18
DHT11_PIN = 4
BUZZER_PIN = 12
TEMT6000_PIN = 34
I2C_SDA_PIN = 21
I2C_SCL_PIN = 22

NUM_LEDS = 8

# FIX 4 (brownouts): cap ring brightness (0.0 - 1.0) to reduce current draw.
# Also power the servo and ring from a separate 5V supply with a COMMON GROUND.
RING_BRIGHTNESS = 0.3

ring = neopixel.NeoPixel(Pin(LED_RING_PIN, Pin.OUT), NUM_LEDS)

def set_ring_color(r, g, b):
    r = int(max(0, min(255, r)) * RING_BRIGHTNESS)
    g = int(max(0, min(255, g)) * RING_BRIGHTNESS)
    b = int(max(0, min(255, b)) * RING_BRIGHTNESS)
    for i in range(NUM_LEDS):
        ring[i] = (r, g, b)
    ring.write()


def turn_off_ring():
    for i in range(NUM_LEDS):
        ring[i] = (0, 0, 0)
    ring.write()


turn_off_ring()

pir_sensor = Pin(PIR_PIN, Pin.IN, Pin.PULL_DOWN)

servo_pwm = PWM(Pin(SERVO_PIN), freq=50)


def set_servo_angle(angle):
    """Maps 0-180 degrees to SG90 duty (ESP32 10-bit: ~26 = 0deg, ~123 = 180deg)."""
    angle = max(0, min(180, angle))
    duty = int(26 + (angle / 180.0) * 97)
    servo_pwm.duty(duty)

set_servo_angle(0)

tl_pins = {
    "RED": PWM(Pin(TRAFFIC_RED_PIN), freq=1000, duty=0),
    "YELLOW": PWM(Pin(TRAFFIC_YELLOW_PIN), freq=1000, duty=0),
    "GREEN": PWM(Pin(TRAFFIC_GREEN_PIN), freq=1000, duty=0),
}


def set_traffic_light(color_state):
    """Turns on the requested light (RED/YELLOW/GREEN); anything else turns all off."""
    for color, pwm_obj in tl_pins.items():
        pwm_obj.duty(1023 if color == color_state else 0)


def fade_traffic_light(color, direction):
    """Fades a light IN (0->1023) or OUT (1023->0). Blocking (~0.5s)."""
    if color not in tl_pins:
        return
    target_pwm = tl_pins[color]
    if direction == "IN":
        for duty in range(0, 1024, 32):
            target_pwm.duty(duty)
            time.sleep_ms(15)
        target_pwm.duty(1023)
    elif direction == "OUT":
        for duty in range(1023, -1, -32):
            target_pwm.duty(duty)
            time.sleep_ms(15)
        target_pwm.duty(0)


# ==========================================
# ANIMATIONS (non-blocking: one frame per call, driven from the main loop)
# ==========================================
RING_ANIMS = ("RAINBOW", "BREATHE", "COMET", "SCANNER", "SPARKLE",
              "THEATER", "FIRE", "POLICE", "HEARTBEAT", "WIPE")
TL_ANIMS = ("CYCLE", "CAUTION", "CHASE", "CROSSFADE", "STROBE")
RING_FRAME_MS = 30
TL_FRAME_MS = 20
_TWO_PI = 2 * math.pi

_heat = [0] * NUM_LEDS          # FIRE animation state


def _ring_px(i, r, g, b, k=1.0):
    """Set one pixel at intensity k (0..1), honouring RING_BRIGHTNESS. Caller does ring.write()."""
    k = 0.0 if k < 0 else (1.0 if k > 1 else k)
    s = k * RING_BRIGHTNESS
    ring[i] = (int(max(0, min(255, r)) * s), int(max(0, min(255, g)) * s), int(max(0, min(255, b)) * s))


def _hsv(h, s=1.0, v=1.0):
    """h in degrees -> (r, g, b) 0..255."""
    h = (h % 360) / 60.0
    i = int(h)
    f = h - i
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i % 6]
    return int(r * 255), int(g * 255), int(b * 255)


def _bump(x, a, b):
    """Smooth 0..1..0 hill between a and b (used for the heartbeat)."""
    if x < a or x >= b:
        return 0.0
    return math.sin(math.pi * (x - a) / (b - a))


def ring_frame(name, t, color):
    """Draw one frame of ring animation `name` at animation-time t (ms). color = (r, g, b)."""
    n = NUM_LEDS
    r, g, b = color

    if name == "RAINBOW":                      # whole rainbow rotating around the ring
        base = t * 360 // 3000
        for i in range(n):
            _ring_px(i, *_hsv(base + i * 360 // n))

    elif name == "BREATHE":                    # slow inhale / exhale
        k = 0.04 + 0.96 * (1 - math.cos(_TWO_PI * t / 4000)) / 2
        for i in range(n):
            _ring_px(i, r, g, b, k)

    elif name == "COMET":                      # bright head with a fading tail, spinning
        head = (t // 90) % n
        for i in range(n):
            _ring_px(i, r, g, b, 1.0 - ((head - i) % n) * 0.27)

    elif name == "SCANNER":                    # Knight-Rider sweep back and forth
        span = 2 * (n - 1)
        p = (t // 110) % span
        pos = p if p < n else span - p
        for i in range(n):
            _ring_px(i, r, g, b, 1.0 - abs(i - pos) * 0.45)

    elif name == "SPARKLE":                    # random flashes that fade out
        for i in range(n):
            pr, pg, pb = ring[i]
            ring[i] = (pr * 6 // 10, pg * 6 // 10, pb * 6 // 10)
        if random.getrandbits(8) < 110:
            _ring_px(random.randrange(n), r, g, b)

    elif name == "THEATER":                    # marquee chase: every 3rd pixel
        ph = (t // 140) % 3
        for i in range(n):
            _ring_px(i, r, g, b, 1.0 if i % 3 == ph else 0.0)

    elif name == "FIRE":                       # flickering embers (ignores the chosen colour)
        for i in range(n):
            _heat[i] = max(0, _heat[i] - random.randrange(0, 40))
        if random.getrandbits(8) < 150:
            j = random.randrange(n)
            _heat[j] = min(255, _heat[j] + random.randrange(110, 256))
        for i in range(n):
            h = (_heat[i - 1] + 2 * _heat[i] + _heat[(i + 1) % n]) // 4
            _ring_px(i, min(255, h * 2), max(0, min(255, (h - 100) * 2)) // 2, 0)

    elif name == "POLICE":                     # red / blue double flashes on opposite halves
        slot = (t // 60) % 10
        red = slot in (0, 2)
        blue = slot in (5, 7)
        for i in range(n):
            if i < n // 2:
                _ring_px(i, 255, 0, 0, 1.0 if red else 0.0)
            else:
                _ring_px(i, 0, 0, 255, 1.0 if blue else 0.0)

    elif name == "HEARTBEAT":                  # lub-dub
        ph = t % 1100
        k = 0.04 + 0.96 * max(_bump(ph, 0, 160), 0.7 * _bump(ph, 260, 440))
        for i in range(n):
            _ring_px(i, r, g, b, k)

    elif name == "WIPE":                       # fill up pixel by pixel, then empty again
        s = (t // 120) % (2 * n)
        for i in range(n):
            lit = (i <= s) if s < n else (i > s - n)
            _ring_px(i, r, g, b, 1.0 if lit else 0.0)

    ring.write()


def _tl_set(red, yellow, green):
    """Set the three lamps to intensities 0..1 (squared so fades look even to the eye)."""
    for pwm_obj, v in ((tl_pins["RED"], red), (tl_pins["YELLOW"], yellow), (tl_pins["GREEN"], green)):
        v = 0.0 if v < 0 else (1.0 if v > 1 else v)
        pwm_obj.duty(1023 if v >= 1.0 else int(v * v * 1023))


def traffic_frame(name, t):
    """Draw one frame of traffic-light animation `name` at animation-time t (ms)."""
    if name == "CYCLE":                        # real-world sequence: green > amber > red > red+amber
        x = t % 8000
        if x < 3000:
            _tl_set(0, 0, 1)
        elif x < 4000:
            _tl_set(0, 1, 0)
        elif x < 7000:
            _tl_set(1, 0, 0)
        else:
            _tl_set(1, 1, 0)

    elif name == "CAUTION":                    # flashing amber
        on = (t // 500) % 2 == 0
        _tl_set(0, 1 if on else 0, 0)

    elif name == "CHASE":                      # lamps light one after another
        s = (t // 220) % 3
        _tl_set(1 if s == 0 else 0, 1 if s == 1 else 0, 1 if s == 2 else 0)

    elif name == "CROSSFADE":                  # smooth hand-over red > amber > green > red ...
        p = (t % 3600) / 1200.0
        v = []
        for centre in (0, 1, 2):
            d = abs(p - centre)
            d = min(d, 3 - d)
            v.append(1.0 - d)
        _tl_set(v[0], v[1], v[2])

    elif name == "STROBE":                     # emergency double flash on all lamps
        x = t % 900
        on = x < 80 or 160 <= x < 240
        _tl_set(1 if on else 0, 1 if on else 0, 1 if on else 0)

# --- NEW SENSOR & ACTUATOR INITIALIZATIONS ---

# 1. Push Button
push_button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

# 2. DHT11 Sensor
dht_sensor = dht.DHT11(Pin(DHT11_PIN))

# 3. Buzzer (PWM-controlled)
buzzer_pwm = PWM(Pin(BUZZER_PIN), freq=2000, duty=0)
buzzer_freq = 2000   # last tone chosen from the web app
buzzer_is_on = False

BUZZ_PATTERNS = {
    "CHIRP": [(True, 60), (False, 60), (True, 60)],
    "ALARM": [(True, 200), (False, 100)] * 5,
    "SOS": [(True, 100), (False, 100)] * 3 + [(True, 300), (False, 100)] * 3 + [(True, 100), (False, 100)] * 3,
}

def set_buzzer_state(command):
    """Turns buzzer ON, OFF, or sets specific tone frequency."""
    global buzzer_freq, buzzer_is_on
    if command == "ON":
        buzzer_pwm.freq(buzzer_freq)
        buzzer_pwm.duty(512)
        buzzer_is_on = True
    elif command == "OFF":
        buzzer_pwm.duty(0)
        buzzer_is_on = False
    else:
        try:
            freq = int(command)
            if freq > 0:
                buzzer_freq = freq
                buzzer_pwm.freq(freq)
                buzzer_pwm.duty(512)
                buzzer_is_on = True
            else:
                buzzer_pwm.duty(0)
                buzzer_is_on = False
        except ValueError:
            print("[!] Invalid Buzzer payload")

# 4. AHT20 + BMP280 (I2C Bus) - real drivers (ahtx0.py / bmp280.py)
i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=100000)
aht_sensor = None
bmp_sensor = None

_i2c_devices = i2c.scan()
print("[I2C] devices found:", [hex(a) for a in _i2c_devices])

if ahtx0:
    try:
        aht_sensor = ahtx0.AHT20(i2c)
    except Exception as e:
        print("[!] AHT20 init failed:", e)

for _addr in (0x76, 0x77):          # BMP280 boards are strapped to either address
    if BMP280 and _addr in _i2c_devices:
        try:
            bmp_sensor = BMP280(i2c, addr=_addr)
            print("[BMP280] found at", hex(_addr))
        except Exception as e:
            print("[!] BMP280 init failed:", e)
        break


def read_aht20():
    """One conversion gives both values (the library re-measures on every property access)."""
    hum = aht_sensor.relative_humidity          # triggers a measurement, fills the buffer
    b = aht_sensor._buf
    temp = (((b[3] & 0x0F) << 16) | (b[4] << 8) | b[5]) * 200.0 / 0x100000 - 50
    return round(temp, 1), round(hum, 1)

# 5. TEMT6000 Ambient Light Sensor (ADC)
temt6000_adc = ADC(Pin(TEMT6000_PIN))
temt6000_adc.atten(ADC.ATTN_11DB)  # Full range ~0-3.3V


# ==========================================
# BLE & MQTT BROKER CONFIGURATION
# ==========================================
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

_FLAG_WRITE_NO_RESPONSE = const(0x0004)
_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)

_UART_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_TX = (bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E"), _FLAG_NOTIFY)
_UART_RX = (
    bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E"),
    _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE,
)
_UART_SERVICE = (_UART_UUID, (_UART_TX, _UART_RX))

MAX_CONNECTIONS = 4
NOTIFY_CHUNK = const(20)  # safe size with default ATT MTU (23 - 3)
MAX_QUEUE = const(16)


class BLEMQTTBroker:
    DEFAULT_NAME = "ESP32-MQTT-Ring"

    def __init__(self, name=DEFAULT_NAME):
        # Bluetooth is optional: if it can't start, the hub keeps running over WiFi only.
        self._ble = None
        self._handle_tx = self._handle_rx = None
        try:
            self._ble = bluetooth.BLE()
            self._ble.active(True)
            self._ble.irq(self._irq)
            ((self._handle_tx, self._handle_rx),) = self._ble.gatts_register_services(
                (_UART_SERVICE,)
            )
            self._ble.gatts_set_buffer(self._handle_rx, 256)
        except Exception as e:
            print("[!] Bluetooth unavailable, continuing with WiFi only:", e)
            self._ble = None

        # WiFi transport (STA with AP fallback + HTTP/WebSocket server). It is started from the
        # main loop ~1.5 s AFTER Bluetooth is advertising, and any failure only disables WiFi.
        self.net = None
        self.web = None
        self._wifi_failed = wifi_link is None
        self._wifi_start_at = time.ticks_add(time.ticks_ms(), 1500)

        self.connections = set()
        self._subscriptions = {}
        self._name = name
        self.ring_state = "OFF"
        self.current_color = (255, 255, 255)
        self.last_pir_state = -1
        self.last_button_state = -1
        self.last_sensor_poll = 0
        self._buz_seq = []
        self._buz_i = 0
        self._buz_t = 0

        # animation engine state (t = animation clock in ms, advanced by speed each frame)
        self.ring_anim = None
        self.ring_speed = 5            # 1 (slow) .. 10 (fast), 5 = normal
        self._ring_t = 0
        self._ring_last = 0
        self.tl_anim = None
        self.tl_speed = 5
        self._tl_t = 0
        self._tl_last = 0

        self._rx_queue = []

        self._advertise()

    # ---------- WiFi transport ----------
    def poll_wifi(self):
        """Call every loop: keeps WiFi alive, starts the server once we have an IP, services clients."""
        if self._wifi_failed:
            return
        if self.net is None:
            if time.ticks_diff(time.ticks_ms(), self._wifi_start_at) < 0:
                return
            try:
                self.net = wifi_link.NetworkManager()
            except Exception as e:
                print("[!] WiFi start failed, continuing without it:", e)
                self._wifi_failed = True
                return
        self.net.poll()
        if self.web is None and self.net.ip:
            try:
                self.web = wifi_link.WebLink(self._on_web_message, self._on_web_close)
                print("[WiFi] Server ready on http://{}/".format(self.net.ip))
                self.publish("sys/ip", self.net.ip)
            except Exception as e:
                print("[!] WiFi server failed to start:", e)
                self.net.ip = None
        if self.web:
            self.web.poll()

    def _on_web_message(self, handle, raw):
        if len(self._rx_queue) < MAX_QUEUE:
            self._rx_queue.append((handle, raw))

    def _on_web_close(self, handle):
        for topic in self._subscriptions:
            self._subscriptions[topic].discard(handle)

    # ---------- Advertising ----------
    def _advertise(self, interval_us=100000):
        if self._ble is None or len(self.connections) >= MAX_CONNECTIONS:
            return

        name_bytes = self._name.encode("utf-8")

        flags = b"\x02\x01\x06"
        name_payload = bytes([len(name_bytes) + 1, 0x09]) + name_bytes

        uuid_bytes = bytes(reversed(bytes.fromhex("6E400001B5A3F393E0A9E50E24DCCA9E")))
        uuid_payload = bytes([len(uuid_bytes) + 1, 0x07]) + uuid_bytes

        adv_data = flags + name_payload
        resp_data = uuid_payload

        try:
            self._ble.gap_advertise(interval_us, adv_data=adv_data, resp_data=resp_data)
            print("[+] Advertising as '{}'".format(self._name))
        except Exception as e:
            print("[!] Advertising failed: {}".format(e))

    # ---------- BLE IRQ ----------
    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self.connections.add(conn_handle)
            print("[+] Client connected: handle", conn_handle)
            self._advertise()

        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self.connections.discard(conn_handle)
            for topic in self._subscriptions:
                self._subscriptions[topic].discard(conn_handle)
            print("[-] Client disconnected: handle", conn_handle)
            self._advertise()

        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if value_handle == self._handle_rx:
                raw = self._ble.gatts_read(self._handle_rx)
                if len(self._rx_queue) < MAX_QUEUE:
                    self._rx_queue.append((conn_handle, raw))

    # ---------- Main-loop processing ----------
    def process_queue(self):
        if not self._rx_queue:
            return

        batch, self._rx_queue = self._rx_queue, []
        decoded = []
        for conn_handle, raw in batch:
            try:
                payload = raw.decode("utf-8").strip()
            except Exception:
                print("[!] Undecodable packet ignored")
                continue
            if payload:
                decoded.append((conn_handle, payload))

        # Slider-style topics: only the newest value of a burst matters.
        coalesce = ("PUB SERVO/ANGLE", "PUB RING/SPEED", "PUB TRAFFIC/SPEED")
        last_idx = {}
        for i, (_, p) in enumerate(decoded):
            up = p.upper()
            for prefix in coalesce:
                if up.startswith(prefix):
                    last_idx[prefix] = i

        for i, (conn_handle, payload) in enumerate(decoded):
            up = payload.upper()
            skip = False
            for prefix in coalesce:
                if up.startswith(prefix) and last_idx.get(prefix) != i:
                    skip = True
            if skip:
                continue
            self._parse_mqtt_packet(conn_handle, payload)

    def _parse_mqtt_packet(self, conn_handle, payload):
        parts = payload.split(" ", 2)
        command = parts[0].strip().upper()

        if command == "SUB" and len(parts) >= 2:
            topic = parts[1].strip()
            if topic not in self._subscriptions:
                self._subscriptions[topic] = set()
            self._subscriptions[topic].add(conn_handle)
            print("[SUB] Handle {} subscribed to: '{}'".format(conn_handle, topic))
            self.publish_to_handle(conn_handle, "ACK SUB " + topic)
            if topic == "sys/ip" and self.net and self.net.ip:
                # lets the web app learn the WiFi address while connected over Bluetooth
                self.publish_to_handle(conn_handle, "MQTT:sys/ip:{}".format(self.net.ip))

        elif command == "PUB" and len(parts) >= 3:
            topic = parts[1].strip()
            message = parts[2].strip().upper()
            print("[PUB] Received on '{}': {}".format(topic, message))

            if topic == "ring/power":
                if message == "ON":
                    self.ring_state = "ON"
                    if self.ring_anim is None:
                        set_ring_color(*self.current_color)
                    self.publish("ring/status", "POWER: ON")
                elif message == "OFF":
                    self.ring_state = "OFF"
                    self.ring_anim = None
                    turn_off_ring()
                    self.publish("ring/status", "POWER: OFF")
                    self.publish("ring/status", "ANIM: NONE")

            elif topic == "ring/anim":
                self._set_ring_anim(message)

            elif topic == "ring/speed":
                try:
                    self.ring_speed = max(1, min(10, int(message)))
                    self.publish("ring/status", "SPEED: {}".format(self.ring_speed))
                except ValueError:
                    print("[!] Invalid ring speed payload")

            elif topic == "ring/color":
                self._handle_color_command(message)

            elif topic == "servo/angle":
                try:
                    angle = int(message)
                    set_servo_angle(angle)
                    self.publish("servo/status", "ANGLE: {}".format(angle))
                except ValueError:
                    print("[!] Invalid Servo Angle payload")

            elif topic == "traffic/state":
                self._stop_tl_anim()
                set_traffic_light(message)
                self.publish("traffic/status", "STATE: {}".format(message))

            elif topic == "traffic/anim":
                self._set_tl_anim(message)

            elif topic == "traffic/speed":
                try:
                    self.tl_speed = max(1, min(10, int(message)))
                    self.publish("traffic/status", "SPEED: {}".format(self.tl_speed))
                except ValueError:
                    print("[!] Invalid traffic speed payload")

            elif topic == "traffic/fade":
                if ":" in message:
                    self._stop_tl_anim()
                    action, color = message.split(":", 1)
                    action, color = action.strip(), color.strip()
                    fade_traffic_light(color, action)
                    self.publish("traffic/status", "FADE {}: {}".format(action, color))

            elif topic == "buzzer/state":
                self._buz_seq = []
                set_buzzer_state(message)
                self.publish("buzzer/status", "STATE: {}".format(message))

            elif topic == "buzzer/freq":
                global buzzer_freq
                try:
                    buzzer_freq = max(100, min(10000, int(message)))
                    if buzzer_is_on:
                        buzzer_pwm.freq(buzzer_freq)
                except ValueError:
                    print("[!] Invalid Buzzer freq payload")

            elif topic == "buzzer/beep":
                try:
                    self._start_buzzer_sequence([(True, max(20, min(5000, int(message))))])
                except ValueError:
                    print("[!] Invalid Buzzer beep payload")

            elif topic == "buzzer/play":
                if message in BUZZ_PATTERNS:
                    self._start_buzzer_sequence(BUZZ_PATTERNS[message])

            # Re-broadcast payload to topic subscribers
            self.publish(topic, message)

    def _handle_color_command(self, color_str):
        color_map = {
            "RED": (255, 0, 0),
            "GREEN": (0, 255, 0),
            "BLUE": (0, 0, 255),
            "WHITE": (255, 255, 255),
            "YELLOW": (255, 150, 0),
            "PURPLE": (180, 0, 255),
        }

        if color_str in color_map:
            self.current_color = color_map[color_str]
        else:
            try:
                rgb = tuple(int(v) for v in color_str.split(","))
                if len(rgb) == 3:
                    self.current_color = rgb
                else:
                    print("[!] RGB needs exactly 3 values")
                    return
            except Exception:
                print("[!] Invalid RGB color payload.")
                return

        if self.ring_state == "ON" and self.ring_anim is None:
            set_ring_color(*self.current_color)

        self.publish("ring/status", "COLOR: {}".format(self.current_color))

    # ---------- Animations ----------
    def _set_ring_anim(self, name):
        if name in ("NONE", "STOP", "OFF", ""):
            self.ring_anim = None
            if self.ring_state == "ON":
                set_ring_color(*self.current_color)
            self.publish("ring/status", "ANIM: NONE")
        elif name in RING_ANIMS:
            was_on = self.ring_state == "ON"
            self.ring_state = "ON"
            self.ring_anim = name
            self._ring_t = 0
            self._ring_last = time.ticks_ms()
            for i in range(NUM_LEDS):
                _heat[i] = 0
            turn_off_ring()
            if not was_on:
                self.publish("ring/status", "POWER: ON")
            self.publish("ring/status", "ANIM: {}".format(name))
        else:
            print("[!] Unknown ring animation:", name)

    def _stop_tl_anim(self, lights_off=False):
        if self.tl_anim is not None:
            self.tl_anim = None
            if lights_off:
                set_traffic_light("OFF")
            self.publish("traffic/status", "ANIM: NONE")

    def _set_tl_anim(self, name):
        if name in ("NONE", "STOP", "OFF", ""):
            self._stop_tl_anim(lights_off=True)
        elif name in TL_ANIMS:
            self.tl_anim = name
            self._tl_t = 0
            self._tl_last = time.ticks_ms()
            self.publish("traffic/status", "ANIM: {}".format(name))
        else:
            print("[!] Unknown traffic animation:", name)

    def check_animations(self):
        """Advance whichever animations are running; cheap no-op between frames."""
        if self.ring_anim is None and self.tl_anim is None:
            return
        now = time.ticks_ms()
        if self.ring_anim is not None and self.ring_state == "ON":
            dt = time.ticks_diff(now, self._ring_last)
            if dt >= RING_FRAME_MS:
                self._ring_last = now
                self._ring_t += dt * self.ring_speed // 5
                ring_frame(self.ring_anim, self._ring_t, self.current_color)
        if self.tl_anim is not None:
            dt = time.ticks_diff(now, self._tl_last)
            if dt >= TL_FRAME_MS:
                self._tl_last = now
                self._tl_t += dt * self.tl_speed // 5
                traffic_frame(self.tl_anim, self._tl_t)

    def check_pir_sensor(self):
        current_state = pir_sensor.value()
        if current_state != self.last_pir_state:
            self.last_pir_state = current_state
            state_text = "TRUE" if current_state == 1 else "FALSE"
            print("[PIR] State Changed ->", state_text)
            self.publish("motion/state", state_text)

    # ---------- Buzzer beeps / patterns (non-blocking) ----------
    def _start_buzzer_sequence(self, steps):
        self._buz_seq = steps
        self._buz_i = 0
        self._buz_t = time.ticks_ms()
        set_buzzer_state("ON" if steps[0][0] else "OFF")
        self.publish("buzzer/status", "STATE: ON")

    def check_buzzer(self):
        if not self._buz_seq:
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self._buz_t) >= self._buz_seq[self._buz_i][1]:
            self._buz_i += 1
            if self._buz_i >= len(self._buz_seq):
                self._buz_seq = []
                set_buzzer_state("OFF")
                self.publish("buzzer/status", "STATE: OFF")
            else:
                self._buz_t = now
                set_buzzer_state("ON" if self._buz_seq[self._buz_i][0] else "OFF")

    # ---------- SENSOR READING ROUTINES ----------
    def check_push_button(self):
        """Monitors button state with active low pull-up logic."""
        current_state = push_button.value()
        if current_state != self.last_button_state:
            self.last_button_state = current_state
            state_text = "PRESSED" if current_state == 0 else "RELEASED"
            print("[BUTTON] State Changed ->", state_text)
            self.publish("button/state", state_text)

    def poll_periodic_sensors(self, interval_ms=2000):
        """Polls DHT11, AHT20, BMP280, and TEMT6000 periodically."""
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_sensor_poll) >= interval_ms:
            self.last_sensor_poll = now

            # 1. DHT11 Poll
            try:
                dht_sensor.measure()
                temp = dht_sensor.temperature()
                hum = dht_sensor.humidity()
                self.publish("dht11/temperature", str(temp))
                self.publish("dht11/humidity", str(hum))
            except Exception as e:
                print("[!] DHT11 Reading Error:", e)

            # 2. AHT20 Poll
            if aht_sensor:
                try:
                    aht_temp, aht_hum = read_aht20()
                    self.publish("aht20/temperature", str(aht_temp))
                    self.publish("aht20/humidity", str(aht_hum))
                except Exception as e:
                    print("[!] AHT20 read error:", e)

            # 3. BMP280 Poll
            if bmp_sensor:
                try:
                    self.publish("bmp280/temperature", str(round(bmp_sensor.temperature, 1)))
                    self.publish("bmp280/pressure", str(round(bmp_sensor.pressure / 100.0, 1)))  # Pa -> hPa
                except Exception as e:
                    print("[!] BMP280 read error:", e)

            # 4. TEMT6000 Light Level Poll
            light_raw = temt6000_adc.read()
            light_percent = round((light_raw / 4095.0) * 100, 1)
            self.publish("temt6000/raw", str(light_raw))
            self.publish("temt6000/light", str(light_percent))

    # ---------- Notify helpers ----------
    def _notify(self, handle, data):
        """BLE: send in 20-byte chunks. WiFi: one WebSocket frame."""
        if handle >= WIFI_HANDLE_BASE:
            if self.web:
                self.web.send(handle, data)
            return
        if self._ble is None:
            return
        try:
            for i in range(0, len(data), NOTIFY_CHUNK):
                self._ble.gatts_notify(handle, self._handle_tx, data[i:i + NOTIFY_CHUNK])
                time.sleep_ms(8)   # give the BLE stack time to drain; bursts otherwise get dropped
        except Exception as e:
            print("[!] Notify error handle {}: {}".format(handle, e))

    def publish(self, topic, message):
        formatted = "MQTT:{}:{}\n".format(topic, message).encode("utf-8")
        if topic in self._subscriptions:
            for handle in list(self._subscriptions[topic]):
                self._notify(handle, formatted)

    def publish_to_handle(self, conn_handle, message):
        self._notify(conn_handle, "{}\n".format(message).encode("utf-8"))

    def shutdown(self):
        if self._ble:
            try:
                self._ble.gap_advertise(None)
            except Exception:
                pass
            self._ble.active(False)


# ==========================================
# MAIN LOOP  (save this file as main.py on the ESP32)
# ==========================================
def _safe(label, fn, *args):
    """Run one step of the main loop; log and carry on if it raises."""
    try:
        fn(*args)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print("[!] {} error:".format(label))
        sys.print_exception(e)


if __name__ == "__main__":
    print("[BOOT] starting broker")
    broker = BLEMQTTBroker()
    last_gc = time.ticks_ms()

    try:
        while True:
            _safe("process_queue", broker.process_queue)
            _safe("anim", broker.check_animations)
            _safe("wifi", broker.poll_wifi)
            _safe("pir", broker.check_pir_sensor)
            _safe("button", broker.check_push_button)
            _safe("buzzer", broker.check_buzzer)
            _safe("sensors", broker.poll_periodic_sensors, 2000)
            if time.ticks_diff(time.ticks_ms(), last_gc) > 5000:
                last_gc = time.ticks_ms()
                gc.collect()
            time.sleep_ms(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
        broker.ring_anim = broker.tl_anim = None
        turn_off_ring()
        set_traffic_light("OFF")
        set_buzzer_state("OFF")
        servo_pwm.deinit()
        buzzer_pwm.deinit()
        broker.shutdown()
