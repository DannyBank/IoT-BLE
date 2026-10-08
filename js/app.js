document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initRingControls();
    initServoControls();
    initBuzzerControls();
    initSensorChart();

    document.getElementById("btn-connect").addEventListener("click", () => {
        bleManager.connect();
    });

    document.getElementById("btn-clear-logs").addEventListener("click", () => {
        document.getElementById("console-log").innerHTML = "";
    });

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