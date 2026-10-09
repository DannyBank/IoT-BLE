// NeoPixel Ring Module
const RingModule = (function () {
    let isPowerOn = false;
    let powerBtn, customColorInput;

    function init() {
        powerBtn = document.getElementById('powerBtn');
        customColorInput = document.getElementById('customColor');

        powerBtn.addEventListener('click', async () => {
            isPowerOn = !isPowerOn;
            const cmd = isPowerOn ? 'PUB ring/power ON' : 'PUB ring/power OFF';
            await BLEManager.send(cmd);
            updatePowerUI(isPowerOn);
        });

        customColorInput.addEventListener('change', async (e) => {
            const hex = e.target.value;
            const r = parseInt(hex.substr(1, 2), 16);
            const g = parseInt(hex.substr(3, 2), 16);
            const b = parseInt(hex.substr(5, 2), 16);
            await sendColor(`${r},${g},${b}`);
        });
    }

    async function sendColor(colorName) {
        if (!isPowerOn) {
            isPowerOn = true;
            updatePowerUI(true);
            await BLEManager.send('PUB ring/power ON');
        }
        await BLEManager.send(`PUB ring/color ${colorName}`);
    }

    function updatePowerUI(active) {
        if (active) {
            powerBtn.classList.add('active');
        } else {
            powerBtn.classList.remove('active');
        }
    }

    function setEnabled(enabled) {
        powerBtn.disabled = !enabled;
        customColorInput.disabled = !enabled;
        if (!enabled) {
            isPowerOn = false;
            updatePowerUI(false);
        }
    }

    return { init, sendColor, setEnabled };
})();