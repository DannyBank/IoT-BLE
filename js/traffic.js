// Traffic Light Module
const TrafficModule = (function () {
    let lights = {};
    let btnFadeIn, btnFadeOut;
    let currentColor = 'RED';

    function init() {
        lights = {
            RED: document.getElementById('tlRed'),
            YELLOW: document.getElementById('tlYellow'),
            GREEN: document.getElementById('tlGreen')
        };

        btnFadeIn = document.getElementById('btnFadeIn');
        btnFadeOut = document.getElementById('btnFadeOut');
    }

    async function setLight(color) {
        // Ensure color name is uppercase and exact string
        currentColor = String(color).trim().toUpperCase();

        // Update web UI preview state
        Object.keys(lights).forEach(c => lights[c].classList.remove('active'));
        if (lights[currentColor]) {
            lights[currentColor].classList.add('active');
        }

        // Transmit exact command payload (PUB traffic/state RED)
        const payload = `PUB traffic/state ${currentColor}`;
		console.log(payload);
        await BLEManager.send(payload);
    }

    async function fade(direction) {
        const dir = String(direction).trim().toUpperCase();
        // Transmit exact format expected by MicroPython (e.g. PUB traffic/fade IN:RED)
        const payload = `PUB traffic/fade ${dir}:${currentColor}`;
        await BLEManager.send(payload);
    }

    function setEnabled(enabled) {
        if (btnFadeIn) btnFadeIn.disabled = !enabled;
        if (btnFadeOut) btnFadeOut.disabled = !enabled;
    }

    return { init, setLight, fade, setEnabled };
})();