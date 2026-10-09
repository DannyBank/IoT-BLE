# wifi_link.py - WiFi transport for the ESP32 hub (runs alongside BLE).
#
#  * NetworkManager : joins your WiFi (STA); if that fails, opens its own access point.
#  * WebLink        : tiny non-blocking HTTP + WebSocket server.
#                       GET /      -> static files from /www (the web app itself)
#                       GET /ws    -> WebSocket carrying the SAME text protocol as BLE
#                                     (client: "SUB topic" / "PUB topic payload",
#                                      server: "MQTT:topic:payload\n")
#
# Nothing here blocks the main loop for more than a few ms; call poll() every loop.
import socket
import time
import os
import hashlib
import binascii

try:
    import network
except ImportError:           # lets the server logic be unit-tested on a PC
    network = None

try:
    import wifi_config as _cfg
except ImportError:
    _cfg = None


def _c(name, default):
    return getattr(_cfg, name, default) if _cfg else default


HANDLE_BASE = 1000            # WiFi client ids start here (BLE connection handles are small ints)
MAX_CLIENTS = 3
MAX_FRAME = 1024
_WS_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_EAGAIN = (11, 35, 115, 119)  # errno values that mean "no data yet" across ports

_MIME = {
    "html": "text/html; charset=utf-8",
    "css": "text/css",
    "js": "application/javascript",
    "json": "application/json",
    "svg": "image/svg+xml",
    "png": "image/png",
    "ico": "image/x-icon",
}


def _would_block(e):
    return bool(e.args) and e.args[0] in _EAGAIN


# ---------------------------------------------------------------- network
class NetworkManager:
    """Non-blocking WiFi bring-up: STA first, access-point fallback after STA_TIMEOUT_S."""

    def __init__(self):
        self.ssid = _c("SSID", "")
        self.password = _c("PASSWORD", "")
        self.hostname = _c("HOSTNAME", "esp32-hub")
        self.ap_ssid = _c("AP_SSID", "ESP32-Hub")
        self.ap_password = _c("AP_PASSWORD", "esp32hub123")
        self.timeout_ms = _c("STA_TIMEOUT_S", 15) * 1000
        self.mode = None            # "STA", "AP" or None while connecting
        self.ip = None
        self._sta = None
        self._t0 = time.ticks_ms()
        self._last_retry = self._t0
        if network is None:
            return
        try:
            network.hostname(self.hostname)
        except Exception:
            pass
        if self.ssid:
            self._sta = network.WLAN(network.STA_IF)
            self._sta.active(True)
            try:
                self._sta.config(pm=network.WLAN.PM_NONE)   # lower latency next to BLE
            except Exception:
                pass
            print("[WiFi] Joining '{}' ...".format(self.ssid))
            self._sta.connect(self.ssid, self.password)
        else:
            print("[WiFi] No SSID configured (wifi_config.py) - starting access point")
            self._start_ap()

    def _start_ap(self):
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        try:
            if len(self.ap_password) >= 8:
                ap.config(essid=self.ap_ssid, authmode=3, password=self.ap_password)   # WPA2-PSK
            else:
                ap.config(essid=self.ap_ssid, authmode=0)                              # open
        except Exception as e:
            print("[WiFi] AP config error:", e)
        self.mode = "AP"
        self.ip = ap.ifconfig()[0]
        print("[WiFi] Access point '{}' up - browse to http://{}/".format(self.ap_ssid, self.ip))

    def poll(self):
        if network is None:
            return
        now = time.ticks_ms()
        if self.mode == "AP":
            return
        if self._sta is None:
            return
        if self._sta.isconnected():
            if self.mode != "STA":
                self.mode = "STA"
                self.ip = self._sta.ifconfig()[0]
                print("[WiFi] Connected. Browse to http://{}/ (or ws://{}/ws)".format(self.ip, self.ip))
            return
        if self.mode == "STA":                       # dropped: retry every 15 s
            self.ip = None
            self.mode = None
            print("[WiFi] Connection lost, retrying")
            self._t0 = now
        if time.ticks_diff(now, self._t0) > self.timeout_ms:
            print("[WiFi] Could not join '{}' - falling back to access point".format(self.ssid))
            self._sta.active(False)
            self._sta = None
            self._start_ap()
        elif time.ticks_diff(now, self._last_retry) > 15000:
            self._last_retry = now
            try:
                self._sta.connect(self.ssid, self.password)
            except Exception:
                pass


# ---------------------------------------------------------------- server
class WebLink:
    def __init__(self, on_message, on_close, port=80, root="/www"):
        self._on_message = on_message          # fn(handle, bytes)
        self._on_close = on_close              # fn(handle)
        self.root = root
        self._next = HANDLE_BASE
        self._clients = {}                     # handle -> [sock, rxbuf]
        self._pending = []                     # [sock, buf, t0] still sending their HTTP request
        self._srv = socket.socket()
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("0.0.0.0", port))
        self._srv.listen(4)
        self._srv.setblocking(False)
        self.port = port

    # ---- public
    def owns(self, handle):
        return handle in self._clients

    def count(self):
        return len(self._clients)

    def send(self, handle, data):
        c = self._clients.get(handle)
        if not c:
            return
        n = len(data)
        if n < 126:
            frame = bytes([0x81, n]) + data
        else:
            frame = bytes([0x81, 126, n >> 8, n & 0xFF]) + data
        try:
            self._send_all(c[0], frame)
        except Exception:
            self._drop(handle)

    def poll(self):
        self._accept()
        self._service_pending()
        for handle in list(self._clients):
            self._read_client(handle)

    # ---- internals
    @staticmethod
    def _send_all(sock, data):
        sock.settimeout(1.0)
        try:
            mv = memoryview(data)
            while len(mv):
                n = sock.send(mv)
                if not n:
                    raise OSError("closed")
                mv = mv[n:]
        finally:
            sock.settimeout(0)

    def _accept(self):
        for _ in range(4):
            try:
                cl, _addr = self._srv.accept()
            except OSError as e:
                if _would_block(e):
                    return
                return
            cl.settimeout(0)
            self._pending.append([cl, b"", time.ticks_ms()])

    def _service_pending(self):
        for item in list(self._pending):
            sock, buf, t0 = item
            try:
                chunk = sock.recv(512)
            except OSError as e:
                chunk = None if _would_block(e) else b""
            if chunk is None:                              # nothing yet (browsers open idle preconnects)
                if time.ticks_diff(time.ticks_ms(), t0) > 5000:
                    self._pending.remove(item)
                    sock.close()
                continue
            if not chunk:
                self._pending.remove(item)
                sock.close()
                continue
            item[1] = buf = buf + chunk
            if b"\r\n\r\n" in buf:
                self._pending.remove(item)
                try:
                    self._handle_request(sock, buf)
                except Exception as e:
                    print("[WiFi] request error:", e)
                    try:
                        sock.close()
                    except Exception:
                        pass
            elif len(buf) > 2048:
                self._pending.remove(item)
                sock.close()

    def _handle_request(self, sock, raw):
        head = raw.split(b"\r\n\r\n", 1)[0].decode("utf-8", "ignore")
        lines = head.split("\r\n")
        parts = lines[0].split(" ")
        if len(parts) < 2 or parts[0] != "GET":
            self._http(sock, "405 Method Not Allowed", b"GET only")
            return
        path = parts[1].split("?", 1)[0]
        hdr = {}
        for ln in lines[1:]:
            if ":" in ln:
                k, v = ln.split(":", 1)
                hdr[k.strip().lower()] = v.strip()

        if path == "/ws" and "websocket" in hdr.get("upgrade", "").lower():
            self._handshake(sock, hdr)
        else:
            self._static(sock, path)

    def _handshake(self, sock, hdr):
        key = hdr.get("sec-websocket-key")
        if not key or len(self._clients) >= MAX_CLIENTS:
            self._http(sock, "503 Service Unavailable", b"busy")
            return
        accept = binascii.b2a_base64(hashlib.sha1(key.encode() + _WS_GUID).digest())[:-1]
        self._send_all(sock, (
            b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
            b"Connection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n"))
        handle = self._next
        self._next += 1
        self._clients[handle] = [sock, b""]
        print("[WiFi] WebSocket client connected: handle", handle)

    def _http(self, sock, status, body, ctype="text/plain", length=None):
        head = "HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nCache-Control: no-cache\r\nConnection: close\r\n\r\n".format(
            status, ctype, len(body) if length is None else length)
        self._send_all(sock, head.encode())
        if body:
            self._send_all(sock, body)
        sock.close()

    def _static(self, sock, path):
        if path == "/":
            path = "/index.html"
        if ".." in path or "\\" in path:
            self._http(sock, "400 Bad Request", b"bad path")
            return
        full = self.root + path
        try:
            size = os.stat(full)[6]
        except OSError:
            if path == "/index.html":
                self._http(sock, "200 OK", b"<h1>ESP32 Hub</h1><p>WebSocket endpoint is /ws. "
                           b"Upload the web app to /www to serve it from the device.</p>", "text/html")
            else:
                self._http(sock, "404 Not Found", b"not found")
            return
        ext = path.rsplit(".", 1)[-1].lower()
        self._static_stream(sock, full, size, _MIME.get(ext, "application/octet-stream"))

    def _static_stream(self, sock, full, size, ctype):
        f = open(full, "rb")
        try:
            head = ("HTTP/1.1 200 OK\r\nContent-Type: {}\r\nContent-Length: {}\r\n"
                    "Cache-Control: no-cache\r\nConnection: close\r\n\r\n").format(ctype, size)
            self._send_all(sock, head.encode())
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                self._send_all(sock, chunk)
        finally:
            f.close()
            sock.close()

    def _read_client(self, handle):
        c = self._clients.get(handle)
        if not c:
            return
        sock = c[0]
        try:
            chunk = sock.recv(512)
        except OSError as e:
            if _would_block(e):
                return
            self._drop(handle)
            return
        if chunk is None:
            return
        if not chunk:
            self._drop(handle)
            return
        c[1] += chunk
        self._parse_frames(handle)

    def _parse_frames(self, handle):
        while handle in self._clients:
            buf = self._clients[handle][1]
            if len(buf) < 2:
                return
            opcode = buf[0] & 0x0F
            masked = buf[1] & 0x80
            n = buf[1] & 0x7F
            i = 2
            if n == 126:
                if len(buf) < 4:
                    return
                n = (buf[2] << 8) | buf[3]
                i = 4
            elif n == 127 or n > MAX_FRAME or not masked:
                self._drop(handle)
                return
            if len(buf) < i + 4 + n:
                return
            mask = buf[i:i + 4]
            payload = bytearray(buf[i + 4:i + 4 + n])
            for k in range(n):
                payload[k] ^= mask[k & 3]
            self._clients[handle][1] = buf[i + 4 + n:]

            if opcode == 0x1:                       # text
                self._on_message(handle, bytes(payload))
            elif opcode == 0x8:                     # close
                self._drop(handle)
                return
            elif opcode == 0x9:                     # ping -> pong
                try:
                    self._send_all(self._clients[handle][0], bytes([0x8A, len(payload)]) + bytes(payload))
                except Exception:
                    self._drop(handle)
                    return

    def _drop(self, handle):
        c = self._clients.pop(handle, None)
        if not c:
            return
        try:
            c[0].close()
        except Exception:
            pass
        print("[WiFi] WebSocket client gone: handle", handle)
        self._on_close(handle)
