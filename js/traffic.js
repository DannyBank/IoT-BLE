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
        currentColor = color;
        Object.keys(lights).forEach(c => lights[c].classList.remove('active'));
        if (lights[color]) lights[color].classList.add('active');

        await BLEManager.send(`PUB traffic/state ${color}`);
    }

    async function fade(direction) {
        const cmd = `PUB traffic/fade ${direction}:${currentColor}`;
        await BLEManager.send(cmd);
    }

    function setEnabled(enabled) {
        btnFadeIn.disabled = !enabled;
        btnFadeOut.disabled = !enabled;
    }

    return { init, setLight, fade, setEnabled };
})();