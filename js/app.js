document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initRingControls();
    initServoControls();
    initBuzzerControls();
    initSensorChart();

    const connectBtn = document.getElementById("btn-connect");

    if (connectBtn) {
        connectBtn.addEventListener("click", async () => {
            // Check if Web Bluetooth API is supported
            if (!navigator.bluetooth) {
                alert("Web Bluetooth is not supported in this browser or context.\n\nMake sure:\n1. You are using Chrome, Edge, or Opera.\n2. You are using HTTPS or http://localhost (file:// is not supported).");
                return;
            }

            try {
                await bleManager.connect();
            } catch (err) {
                console.error("BLE Connect Exception:", err);
            }
        });
    } else {
        console.error("Connect button ('btn-connect') not found in DOM.");
    }

    const clearLogsBtn = document.getElementById("btn-clear-logs");
    if (clearLogsBtn) {
        clearLogsBtn.addEventListener("click", () => {
            document.getElementById("console-log").innerHTML = "";
        });
    }

    bleManager.onMessageCallback = (msg) => {
        parseIncomingMessage(msg);
    };
});

function logConsole(msg) {
    const logBox = document.getElementById("console-log");
    if (!logBox) return;
    const time = new Date().toLocaleTimeString();
    const line = document.createElement("div");
    line.innerText = `[${time}] ${msg}`;
    logBox.appendChild(line);
    logBox.scrollTop = logBox.scrollHeight;
}

function parseIncomingMessage(msg) {
    if (msg.startsWith("MQTT:")) {
        const parts = msg.split(":");
        if (parts.length >= 3) {
            const topic = parts[1];
            const payload = parts.slice(2).join(":");

            if (topic === "motion/state") {
                updateMotionState(payload);
            } else if (topic === "buzzer/status") {
                updateBuzzerStatus(payload);
            } else {
                updateSensorData(topic, payload);
            }
        }
    }
}