// WiFi (WebSocket) transport. Same text protocol as Bluetooth, carried by ws://<esp32>/ws
const WiFiManager = (function () {
    let ws = null;

    function isAvailable() {
        return typeof WebSocket !== 'undefined';
    }

    // "http://192.168.1.50/" / "esp32-hub.local:80" -> "192.168.1.50" / "esp32-hub.local:80"
    function normalizeHost(value) {
        return String(value || '').trim().replace(/^[a-z]+:\/\//i, '').replace(/\/.*$/, '');
    }

    function isLocal(host) {
        return /^(localhost|127\.|\[::1\])/.test(host);
    }

    function connect(h, host) {
        return new Promise((resolve, reject) => {
            if (!isAvailable()) return reject(new Error('WebSocket is not supported in this browser'));
            if (location.protocol === 'https:' && !isLocal(host)) {
                return reject(new Error(
                    'This page is loaded over HTTPS, so the browser blocks ws:// connections. ' +
                    `Open http://${host}/ (served by the ESP32) or open the app from a local file instead.`));
            }
            h.log('sys', `Connecting to ws://${host}/ws ...`);
            let opened = false;
            let socket;
            try {
                socket = new WebSocket(`ws://${host}/ws`);
            } catch (err) {
                return reject(err);
            }
            ws = socket;
            const timer = setTimeout(() => { try { socket.close(); } catch (e) {} reject(new Error('timed out - is the ESP32 on the same network?')); }, 7000);

            socket.onopen = () => { opened = true; clearTimeout(timer); resolve(host); };
            socket.onmessage = (e) => { if (typeof e.data === 'string') h.onData(e.data); };
            socket.onerror = () => {};
            socket.onclose = () => {
                clearTimeout(timer);
                if (opened) {
                    if (ws === socket) ws = null;
                    h.onClosed();
                } else {
                    reject(new Error('could not reach the device'));
                }
            };
        });
    }

    function disconnect() {
        if (ws) { try { ws.close(); } catch (e) {} }
    }

    async function send(payload) {
        if (!ws || ws.readyState !== WebSocket.OPEN) throw new Error('WiFi not connected');
        ws.send(payload + '\n');
    }

    return {
        isAvailable,
        normalizeHost,
        connect,
        disconnect,
        send,
        isConnected: () => !!(ws && ws.readyState === WebSocket.OPEN)
    };
})();
