// Bluetooth (Web Bluetooth / Nordic UART) transport.
// Transport contract used by Link: isAvailable(), connect(handlers) -> device name,
// send(text), disconnect(), isConnected().  handlers = { log, onData(text), onClosed() }
const BLEManager = (function () {
    const UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
    const UART_RX_CHAR_UUID  = "6e400002-b5a3-f393-e0a9-e50e24dcca9e";
    const UART_TX_CHAR_UUID  = "6e400003-b5a3-f393-e0a9-e50e24dcca9e";

    let bleDevice = null;
    let rxCharacteristic = null;
    let txCharacteristic = null;

    function isAvailable() {
        return !!navigator.bluetooth;
    }

    async function connect(h) {
        if (!isAvailable()) {
            throw new Error('Web Bluetooth is not supported in this browser');
        }
        h.log('sys', 'Requesting Bluetooth devices...');

        bleDevice = await navigator.bluetooth.requestDevice({
            filters: [
                { namePrefix: 'ESP32' },
                { services: [UART_SERVICE_UUID] }
            ],
            optionalServices: [UART_SERVICE_UUID]
        });

        bleDevice.addEventListener('gattserverdisconnected', () => {
            rxCharacteristic = null;
            txCharacteristic = null;
            h.onClosed();
        });

        try {
            h.log('sys', `Connecting to ${bleDevice.name}...`);
            const server = await bleDevice.gatt.connect();

            h.log('sys', 'Discovering Nordic UART Service...');
            const service = await server.getPrimaryService(UART_SERVICE_UUID);

            rxCharacteristic = await service.getCharacteristic(UART_RX_CHAR_UUID);
            txCharacteristic = await service.getCharacteristic(UART_TX_CHAR_UUID);

            await txCharacteristic.startNotifications();
            const decoder = new TextDecoder('utf-8');
            txCharacteristic.addEventListener('characteristicvaluechanged', (e) => {
                // Raw chunks (the ESP32 splits messages into 20-byte notifications);
                // Link reassembles them into lines.
                h.onData(decoder.decode(e.target.value, { stream: true }));
            });
        } catch (err) {
            if (bleDevice.gatt.connected) bleDevice.gatt.disconnect();
            throw err;
        }
        return bleDevice.name;
    }

    function disconnect() {
        if (bleDevice && bleDevice.gatt.connected) {
            bleDevice.gatt.disconnect();
        }
    }

    async function send(payload) {
        if (!rxCharacteristic) throw new Error('Bluetooth not connected');
        const data = new TextEncoder().encode(payload + '\n');
        await rxCharacteristic.writeValue(data);
    }

    return {
        isAvailable,
        connect,
        disconnect,
        send,
        isConnected: () => !!(bleDevice && bleDevice.gatt.connected)
    };
})();
