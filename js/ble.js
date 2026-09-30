// BLE Core Module
const BLEManager = (function () {
    const UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
    const UART_RX_CHAR_UUID  = "6e400002-b5a3-f393-e0a9-e50e24dcca9e";
    const UART_TX_CHAR_UUID  = "6e400003-b5a3-f393-e0a9-e50e24dcca9e";

    let bleDevice = null;
    let rxCharacteristic = null;
    let txCharacteristic = null;
    let notificationCallbacks = [];

    async function connect(onStateChange, logCallback) {
        try {
            logCallback('sys', 'Requesting Bluetooth devices...');
            
            bleDevice = await navigator.bluetooth.requestDevice({
                filters: [
                    { namePrefix: 'ESP32' },
                    { services: [UART_SERVICE_UUID] }
                ],
                optionalServices: [UART_SERVICE_UUID]
            });

            bleDevice.addEventListener('gattserverdisconnected', () => {
                logCallback('sys', 'Device disconnected.');
                onStateChange(false);
                rxCharacteristic = null;
                txCharacteristic = null;
            });

            logCallback('sys', `Connecting to ${bleDevice.name}...`);
            const server = await bleDevice.gatt.connect();

            logCallback('sys', 'Discovering Nordic UART Service...');
            const service = await server.getPrimaryService(UART_SERVICE_UUID);

            rxCharacteristic = await service.getCharacteristic(UART_RX_CHAR_UUID);
            txCharacteristic = await service.getCharacteristic(UART_TX_CHAR_UUID);

            await txCharacteristic.startNotifications();
            txCharacteristic.addEventListener('characteristicvaluechanged', (e) => {
                const message = new TextDecoder('utf-8').decode(e.target.value).trim();
                logCallback('rx', `<- ${message}`);
                notificationCallbacks.forEach(cb => cb(message));
            });

            onStateChange(true, bleDevice.name);
            logCallback('sys', 'BLE Connected & Subscribed!');

            // Auto-subscribe to essential topic telemetry
            await send('SUB ring/status');
            await send('SUB motion/state');
            await send('SUB traffic/status');

        } catch (error) {
            logCallback('err', `Error: ${error.message || error}`);
            onStateChange(false);
        }
    }

    function disconnect() {
        if (bleDevice && bleDevice.gatt.connected) {
            bleDevice.gatt.disconnect();
        }
    }

	async function send(payload) {
		if (!rxCharacteristic) return;
		try {
			const encoder = new TextEncoder();
			// Append explicit newline '\n' to signify frame completion
			const data = encoder.encode(payload.trim() + '\n');
			await rxCharacteristic.writeValueWithResponse(data);
			window.App.log('tx', `-> ${payload}`);
		} catch (err) {
			window.App.log('err', `TX Error: ${err.message}`);
		}
	}

    function onNotification(callback) {
        notificationCallbacks.push(callback);
    }

    return {
        connect,
        disconnect,
        send,
        onNotification,
        isConnected: () => !!(bleDevice && bleDevice.gatt.connected)
    };
})();