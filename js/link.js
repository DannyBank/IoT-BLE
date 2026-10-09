// Link: one connection facade over the Bluetooth and WiFi transports.
// All feature modules talk to Link; they don't care which transport is carrying the data.
const Link = (function () {
    const SUBSCRIPTIONS = [
        'ring/status', 'motion/state', 'traffic/status',
        'temt6000/light', 'temt6000/raw', 'aht20/temperature', 'aht20/humidity',
        'bmp280/temperature', 'bmp280/pressure', 'dht11/temperature', 'dht11/humidity',
        'button/state', 'buzzer/status',
        'sys/ip'                       // the ESP32 tells us its WiFi address
    ];
    const LS_MODE = 'hub.transport';
    const LS_HOST = 'hub.wifiHost';

    let active = null;                 // transport currently carrying traffic
    let activeLabel = '';
    let rxBuffer = '';
    let ui = { onState: () => {}, log: () => {} };
    const callbacks = [];
    const hostListeners = [];

    // ---- persistence (best effort: storage can be unavailable)
    function load(key, fallback) {
        try { return localStorage.getItem(key) || fallback; } catch (e) { return fallback; }
    }
    function save(key, value) {
        try { localStorage.setItem(key, value); } catch (e) { /* ignore */ }
    }

    // ---- incoming data: chunks -> complete lines -> subscribers
    function handleData(text) {
        rxBuffer += text;
        let nl;
        while ((nl = rxBuffer.indexOf('\n')) >= 0) {
            const message = rxBuffer.slice(0, nl).trim();
            rxBuffer = rxBuffer.slice(nl + 1);
            if (!message) continue;
            ui.log('rx', `<- ${message}`);
            callbacks.forEach(cb => cb(message));
        }
        if (rxBuffer.length > 512) rxBuffer = '';     // safety: never grow unbounded
    }

    function onNotification(callback) {
        callbacks.push(callback);
    }

    // Subscribe a callback to one topic of "MQTT:<topic>:<payload>" lines
    function onTopic(topic, callback) {
        callbacks.push((msg) => {
            const start = msg.indexOf('MQTT:');
            if (start < 0) return;
            const rest = msg.slice(start + 5);
            const i = rest.indexOf(':');
            if (i < 0 || rest.slice(0, i) !== topic) return;
            callback(rest.slice(i + 1).trim());
        });
    }

    // The device reports its WiFi address; remember it so WiFi works next time.
    onTopic('sys/ip', (ip) => {
        if (!/^[\d.]+$/.test(ip)) return;
        save(LS_HOST, ip);
        hostListeners.forEach(cb => cb(ip));
    });
    function onHostLearned(cb) { hostListeners.push(cb); }

    // ---- sending
    async function send(payload) {
        if (!active) return;
        try {
            await active.send(payload);
            window.App.log('tx', `-> ${payload}`);
        } catch (err) {
            window.App.log('err', `TX Error: ${err.message}`);
        }
    }

    // ---- connecting
    function transportFor(kind) {
        return kind === 'ble' ? BLEManager : WiFiManager;
    }

    async function tryTransport(kind, host) {
        const transport = transportFor(kind);
        const label = kind === 'ble' ? 'Bluetooth' : 'WiFi';
        rxBuffer = '';
        const name = await transport.connect({
            log: ui.log,
            onData: handleData,
            onClosed: () => {
                if (active === transport) {
                    active = null;
                    ui.log('sys', `${label} link closed.`);
                    ui.onState(false);
                }
            }
        }, host);

        active = transport;
        activeLabel = label;
        ui.onState(true, `${name} (${label})`);
        ui.log('sys', `${label} connected & subscribing...`);
        if (kind === 'wifi') save(LS_HOST, host);
        for (const topic of SUBSCRIPTIONS) {
            await send('SUB ' + topic);
        }
        return true;
    }

    // mode: 'auto' (Bluetooth, then WiFi), 'ble', or 'wifi'
    async function connect(mode, hostInput, onState, log) {
        ui = { onState, log };
        save(LS_MODE, mode);
        const host = WiFiManager.normalizeHost(hostInput);
        let order;
        if (mode === 'ble') order = ['ble'];
        else if (mode === 'wifi') order = ['wifi'];
        else order = BLEManager.isAvailable() ? ['ble', 'wifi'] : ['wifi'];

        for (let i = 0; i < order.length; i++) {
            const kind = order[i];
            if (kind === 'wifi' && !host) {
                log('err', 'WiFi: enter the ESP32 address (it is remembered automatically after one Bluetooth connection).');
                continue;
            }
            try {
                return await tryTransport(kind, host);
            } catch (err) {
                // The user dismissing the Bluetooth chooser is a "no", not a failure to work around.
                if (kind === 'ble' && err && err.name === 'NotFoundError') {
                    log('sys', 'Bluetooth device selection cancelled.');
                    break;
                }
                log('err', `${kind === 'ble' ? 'Bluetooth' : 'WiFi'}: ${err.message || err}`);
                if (i < order.length - 1) log('sys', 'Trying WiFi instead...');
            }
        }
        onState(false);
        return false;
    }

    function disconnect() {
        if (active) active.disconnect();
    }

    return {
        connect,
        disconnect,
        send,
        onNotification,
        onTopic,
        onHostLearned,
        isConnected: () => !!(active && active.isConnected()),
        transportLabel: () => activeLabel,
        savedMode: () => load(LS_MODE, 'auto'),
        savedHost: () => load(LS_HOST, '')
    };
})();
