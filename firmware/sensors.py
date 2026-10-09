# sensors.py - TEMT6000, AHT20+BMP280, DHT11, push button, buzzer for the ESP32 BLE hub.
#
# Non-blocking: call sensors.poll() from your main loop at least every ~20 ms.
# Publishing goes through the callback you give init(): publish(topic, payload_str)
#   -> must emit the same "MQTT:<topic>:<payload>" notification your motion sensor uses.
# Commands from the web app arrive via handle(topic, payload) (see README).
import dht
from machine import Pin, ADC, I2C, PWM
from time import ticks_ms, ticks_diff

# ---------------- CONFIG (edit to match your wiring) ----------------
PIN_I2C_SDA = 21          # AHT20 + BMP280 share this bus
PIN_I2C_SCL = 22
PIN_LIGHT_ADC = 34        # TEMT6000 SIG (ADC1 pin, input-only)
PIN_DHT11 = 4
PIN_BUTTON = 27           # other leg to GND (internal pull-up used)
PIN_BUZZER = 25
BUZZER_PASSIVE = False    # True = passive buzzer (PWM tone), False = active buzzer (on/off)
BUZZER_FREQ = 2000        # Hz, passive only

LIGHT_PERIOD_MS = 2000
ENV_PERIOD_MS = 5000      # AHT20 + BMP280
DHT_PERIOD_MS = 5000      # DHT11 needs >= 1 s between reads
DEBOUNCE_MS = 30
OUTBOX_GAP_MS = 40        # spacing between BLE notifications (avoids stack overflow)
# --------------------------------------------------------------------

_publish = None
_outbox = []
_last_tx = 0
_i2c = None
_aht = None
_bmp = None
_dht = None
_adc = None
_btn = None
_buz = None
_buz_on = False

_next = {'light': 0, 'env': 0, 'dht': 0}
_aht_pending_at = None            # ticks when AHT20 conversion was triggered
_btn_raw = 1
_btn_stable = 1
_btn_changed_at = 0
_buz_off_at = None
_buz_seq = []                     # list of (on_bool, ms)
_buz_seq_i = 0
_buz_seq_at = 0


def _tx(topic, payload, urgent=False):
    item = (topic, str(payload))
    if urgent:
        _outbox.insert(0, item)
    elif len(_outbox) < 40:       # drop if the link is stalled instead of growing forever
        _outbox.append(item)


def _fmt(v, nd=1):
    return 'NA' if v is None else ('%.' + str(nd) + 'f') % v


def init(publish):
    """Set up every sensor independently; a missing one is reported but doesn't stop the rest."""
    global _publish, _i2c, _aht, _bmp, _dht, _adc, _btn, _buz, _btn_raw, _btn_stable
    _publish = publish
    now = ticks_ms()
    for k in _next:
        _next[k] = now

    try:
        _i2c = I2C(0, sda=Pin(PIN_I2C_SDA), scl=Pin(PIN_I2C_SCL), freq=100000)
    except Exception as e:
        print('I2C init failed:', e)
    if _i2c:
        try:
            from aht20 import AHT20
            _aht = AHT20(_i2c)
        except Exception as e:
            print('AHT20 init failed:', e)
        try:
            from bmp280 import BMP280
            _bmp = BMP280(_i2c)
        except Exception as e:
            print('BMP280 init failed:', e)

    try:
        _adc = ADC(Pin(PIN_LIGHT_ADC))
        _adc.atten(ADC.ATTN_11DB)          # 0 - ~3.1 V
    except Exception as e:
        print('TEMT6000 init failed:', e)

    try:
        _dht = dht.DHT11(Pin(PIN_DHT11))
    except Exception as e:
        print('DHT11 init failed:', e)

    _btn = Pin(PIN_BUTTON, Pin.IN, Pin.PULL_UP)
    _btn_raw = _btn_stable = _btn.value()

    if BUZZER_PASSIVE:
        _buz = PWM(Pin(PIN_BUZZER), freq=BUZZER_FREQ, duty=0)
    else:
        _buz = Pin(PIN_BUZZER, Pin.OUT, value=0)
    _tx('btn/state', 1 if _btn_stable == 0 else 0)
    _tx('buzz/on', 0)


# ---------------- TEMT6000 ----------------
def _read_lux():
    # Breakout has a 10 kOhm load: ~0.5 uA/lux -> 5 mV/lux. Saturates near Vcc (~600 lux at 3.3 V),
    # so this is an indoor-light estimate, not a calibrated lux meter.
    n = 16
    total = 0
    for _ in range(n):
        try:
            total += _adc.read_uv() // 1000     # calibrated microvolts -> mV
        except AttributeError:
            total += _adc.read() * 3100 // 4095
    mv = total / n
    return mv / 5.0


# ---------------- Buzzer ----------------
def _buz_set(on):
    global _buz_on
    if BUZZER_PASSIVE:
        try:
            _buz.duty_u16(32768 if on else 0)
        except AttributeError:
            _buz.duty(512 if on else 0)
    else:
        _buz.value(1 if on else 0)
    if on != _buz_on:
        _buz_on = on
        _tx('buzz/on', 1 if on else 0)


def _buz_stop():
    global _buz_off_at, _buz_seq
    _buz_off_at = None
    _buz_seq = []
    _buz_set(False)


def beep(ms=200):
    global _buz_off_at
    _buz_stop()
    _buz_set(True)
    _buz_off_at = ticks_ms() + max(20, min(int(ms), 5000))


def play(name):
    global _buz_seq, _buz_seq_i, _buz_seq_at
    patterns = {
        'ALARM': [(True, 200), (False, 100)] * 5,
        'CHIRP': [(True, 60), (False, 60), (True, 60)],
        'SOS': [(True, 100), (False, 100)] * 3 + [(True, 300), (False, 100)] * 3 + [(True, 100), (False, 100)] * 3,
    }
    seq = patterns.get(name.upper())
    if not seq:
        return
    _buz_stop()
    _buz_seq = seq
    _buz_seq_i = 0
    _buz_seq_at = ticks_ms()
    _buz_set(seq[0][0])


def set_freq(hz):
    if BUZZER_PASSIVE:
        _buz.freq(max(100, min(int(hz), 10000)))


def handle(topic, payload):
    """Route PUB commands from the web app. Returns True if the topic was ours."""
    global _buz_off_at
    p = payload.strip()
    try:
        if topic == 'buzz/set':
            _buz_stop()
            _buz_set(p.upper() in ('ON', '1', 'TRUE'))
        elif topic == 'buzz/beep':
            beep(int(p) if p else 200)
        elif topic == 'buzz/play':
            play(p)
        elif topic == 'buzz/freq':
            set_freq(int(p))
        else:
            return False
    except Exception as e:
        print('sensors.handle error:', topic, p, e)
    return True


# ---------------- Main poll ----------------
def poll():
    global _last_tx, _aht_pending_at, _btn_raw, _btn_stable, _btn_changed_at
    global _buz_off_at, _buz_seq, _buz_seq_i, _buz_seq_at
    now = ticks_ms()

    # Button: debounce (polled, ~30 ms)
    if _btn:
        raw = _btn.value()
        if raw != _btn_raw:
            _btn_raw = raw
            _btn_changed_at = now
        elif raw != _btn_stable and ticks_diff(now, _btn_changed_at) >= DEBOUNCE_MS:
            _btn_stable = raw
            _tx('btn/state', 1 if raw == 0 else 0, urgent=True)

    # Buzzer timers
    if _buz_off_at is not None and ticks_diff(now, _buz_off_at) >= 0:
        _buz_off_at = None
        _buz_set(False)
    if _buz_seq and ticks_diff(now, _buz_seq_at) >= _buz_seq[_buz_seq_i][1]:
        _buz_seq_i += 1
        if _buz_seq_i >= len(_buz_seq):
            _buz_seq = []
            _buz_set(False)
        else:
            _buz_seq_at = now
            _buz_set(_buz_seq[_buz_seq_i][0])

    # Light
    if _adc and ticks_diff(now, _next['light']) >= 0:
        _next['light'] = now + LIGHT_PERIOD_MS
        try:
            _tx('light/lux', int(_read_lux()))
        except Exception as e:
            print('TEMT6000 read failed:', e)
            _tx('light/lux', 'NA')

    # AHT20 (two-phase so we never block for the 80 ms conversion) + BMP280
    if _aht_pending_at is not None and ticks_diff(now, _aht_pending_at) >= 85:
        _aht_pending_at = None
        try:
            t, h = _aht.read()
            _tx('aht/temp', _fmt(t))
            _tx('aht/hum', _fmt(h))
        except Exception as e:
            print('AHT20 read failed:', e)
            _tx('aht/temp', 'NA')
            _tx('aht/hum', 'NA')
    if ticks_diff(now, _next['env']) >= 0:
        _next['env'] = now + ENV_PERIOD_MS
        if _aht:
            try:
                _aht.trigger()
                _aht_pending_at = now
            except Exception as e:
                print('AHT20 trigger failed:', e)
        if _bmp:
            try:
                t, p = _bmp.read()
                _tx('bmp/temp', _fmt(t))
                _tx('bmp/hpa', _fmt(p))
            except Exception as e:
                print('BMP280 read failed:', e)
                _tx('bmp/temp', 'NA')
                _tx('bmp/hpa', 'NA')

    # DHT11 (blocks ~20 ms with IRQs off, so keep the period long)
    if _dht and ticks_diff(now, _next['dht']) >= 0:
        _next['dht'] = now + DHT_PERIOD_MS
        try:
            _dht.measure()
            _tx('dht/temp', _dht.temperature())
            _tx('dht/hum', _dht.humidity())
        except Exception as e:
            print('DHT11 read failed:', e)
            _tx('dht/temp', 'NA')
            _tx('dht/hum', 'NA')

    # Drain outbox, one notification per OUTBOX_GAP_MS
    if _outbox and _publish and ticks_diff(now, _last_tx) >= OUTBOX_GAP_MS:
        _last_tx = now
        topic, payload = _outbox.pop(0)
        try:
            _publish(topic, payload)
        except Exception as e:
            print('publish failed:', e)
