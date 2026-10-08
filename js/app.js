document.addEventListener("DOMContentLoaded", () => {
    // Safely initialize controls if functions are loaded
    if (typeof initTabs === "function") initTabs();
    if (typeof initRingControls === "function") initRingControls();
    if (typeof initServoControls === "function") initServoControls();
    if (typeof initBuzzerControls === "function") initBuzzerControls();
    if (typeof initSensorChart === "function") initSensorChart();

    const connectBtn = document.getElementById("btn-connect");
    if (connectBtn) {
        connectBtn.addEventListener("click", async () => {
            if (!navigator.bluetooth) {
                alert("Web Bluetooth is not supported in this browser context.\nPlease run on HTTPS or http://localhost using Chrome/Edge.");
                return;
            }
            try {
                await bleManager.connect();
            } catch (err) {
                console.error("BLE Connect Error:", err);
            }
        });
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
                if (typeof updateMotionState === "function") updateMotionState(payload);
            } else if (topic === "buzzer/status") {
                if (typeof updateBuzzerStatus === "function") updateBuzzerStatus(payload);
            } else {
                if (typeof updateSensorData === "function") updateSensorData(topic, payload);
            }
        }
    }
}