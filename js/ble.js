class BLEManager {
    constructor() {
        this.device = null;
        this.gattServer = null;
        this.txCharacteristic = null;
        this.rxCharacteristic = null;

        this.UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
        this.UART_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e";
        this.UART_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e";

        this.onMessageCallback = null;
    }

    async connect() {
        try {
            console.log("Requesting BLE Device...");
            this.device = await navigator.bluetooth.requestDevice({
                filters: [{ namePrefix: "ESP32" }],
                optionalServices: [this.UART_SERVICE_UUID]
            });

            this.device.addEventListener('gattserverdisconnected', this.onDisconnected.bind(this));

            console.log("Connecting to GATT Server...");
            this.gattServer = await this.device.gatt.connect();

            console.log("Getting UART Service...");
            const service = await this.gattServer.getPrimaryService(this.UART_SERVICE_UUID);

            console.log("Getting Characteristics...");
            this.txCharacteristic = await service.getCharacteristic(this.UART_TX_UUID);
            this.rxCharacteristic = await service.getCharacteristic(this.UART_RX_UUID);

            await this.txCharacteristic.startNotifications();
            this.txCharacteristic.addEventListener('characteristicvaluechanged', this.handleNotification.bind(this));

            this.updateUIStatus(true);
            this.subscribeTopics();
            logConsole("Connected to BLE device successfully!");
        } catch (error) {
            console.error("Connection failed", error);
            logConsole("BLE Connection failed: " + error);
            this.updateUIStatus(false);
        }
    }

    onDisconnected() {
        logConsole("BLE Device Disconnected");
        this.updateUIStatus(false);
    }

    updateUIStatus(isConnected) {
        const dot = document.getElementById("ble-status-indicator");
        const text = document.getElementById("ble-status-text");
        const btn = document.getElementById("btn-connect");

        if (isConnected) {
            dot.className = "status-dot connected";
            text.innerText = "Connected";
            btn.innerHTML = '<i class="fa-solid fa-plug-circle-check"></i> Connected';
        } else {
            dot.className = "status-dot disconnected";
            text.innerText = "Disconnected";
            btn.innerHTML = '<i class="fa-solid fa-bluetooth-b"></i> Connect BLE';
        }
    }

    subscribeTopics() {
        const topics = [
            "ring/status", "servo/status", "traffic/status", 
            "motion/state", "button/state", "buzzer/status",
            "dht11/temperature", "dht11/humidity",
            "aht20/temperature", "aht20/humidity", "bmp280/pressure",
            "temt6000/raw", "temt6000/light"
        ];

        topics.forEach(t => this.sendMQTT("SUB", t));
    }

    sendMQTT(cmd, topic, payload = "") {
        if (!this.rxCharacteristic) {
            logConsole("Cannot send message: Not connected.");
            return;
        }

        const msg = `${cmd} ${topic} ${payload}`.trim();
        const encoder = new TextEncoder();
        this.rxCharacteristic.writeValue(encoder.encode(msg + "\n"));
        logConsole(`[TX] ${msg}`);
    }

    handleNotification(event) {
        const decoder = new TextDecoder('utf-8');
        const raw = decoder.decode(event.target.value);
        logConsole(`[RX] ${raw.trim()}`);

        if (this.onMessageCallback) {
            this.onMessageCallback(raw.trim());
        }
    }
}

const bleManager = new BLEManager();