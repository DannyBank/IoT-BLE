function initBuzzerControls() {
    const btnOn = document.getElementById("btn-buzzer-on");
    const btnOff = document.getElementById("btn-buzzer-off");
    const btnFreq = document.getElementById("btn-buzzer-freq");
    const freqInput = document.getElementById("buzzer-freq");

    if (btnOn) {
        btnOn.addEventListener("click", () => {
            bleManager.sendMQTT("PUB", "buzzer/state", "ON");
        });
    }

    if (btnOff) {
        btnOff.addEventListener("click", () => {
            bleManager.sendMQTT("PUB", "buzzer/state", "OFF");
        });
    }

    if (btnFreq) {
        btnFreq.addEventListener("click", () => {
            const freq = freqInput.value || "2000";
            bleManager.sendMQTT("PUB", "buzzer/state", freq);
        });
    }
}

function updateBuzzerStatus(message) {
    const badge = document.getElementById("buzzer-status-badge");
    if (badge) {
        badge.innerText = message;
        if (message.includes("OFF")) {
            badge.className = "badge badge-off";
        } else {
            badge.className = "badge badge-on";
        }
    }
}