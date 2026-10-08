function initRingControls() {
    const toggle = document.getElementById("ring-power-toggle");
    const customColor = document.getElementById("ring-custom-color");
    const btnRGB = document.getElementById("btn-set-rgb");
    const colorBtns = document.querySelectorAll(".color-btn");

    if (toggle) {
        toggle.addEventListener("change", (e) => {
            const cmd = e.target.checked ? "ON" : "OFF";
            bleManager.sendMQTT("PUB", "ring/power", cmd);
        });
    }

    colorBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const colorName = btn.getAttribute("data-color");
            bleManager.sendMQTT("PUB", "ring/color", colorName);
        });
    });

    if (btnRGB) {
        btnRGB.addEventListener("click", () => {
            const hex = customColor.value;
            const r = parseInt(hex.substr(1,2), 16);
            const g = parseInt(hex.substr(3,2), 16);
            const b = parseInt(hex.substr(5,2), 16);
            bleManager.sendMQTT("PUB", "ring/color", `${r},${g},${b}`);
        });
    }
}