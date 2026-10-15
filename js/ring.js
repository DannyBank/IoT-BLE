// NeoPixel Ring Module
const RingModule = (function () {
    let isPowerOn = false;
    let powerBtn, customColorInput;
    let animBtns, animStopBtn, speedSlider, speedVal;
    let currentAnim = null;
    let speedTimer = null;

    function init() {
        powerBtn = document.getElementById('powerBtn');
        customColorInput = document.getElementById('customColor');
        animBtns = document.querySelectorAll('#ringAnims .btn-anim');
        animStopBtn = document.getElementById('ringAnimStop');
        speedSlider = document.getElementById('ringSpeed');
        speedVal = document.getElementById('ringSpeedVal');

        powerBtn.addEventListener('click', async () => {
            isPowerOn = !isPowerOn;
            const cmd = isPowerOn ? 'PUB ring/power ON' : 'PUB ring/power OFF';
            await Link.send(cmd);
            updatePowerUI(isPowerOn);
            if (!isPowerOn) showAnim(null);     // powering off also stops any animation
        });

        customColorInput.addEventListener('change', async (e) => {
            const hex = e.target.value;
            const r = parseInt(hex.substr(1, 2), 16);
            const g = parseInt(hex.substr(3, 2), 16);
            const b = parseInt(hex.substr(5, 2), 16);
            await sendColor(`${r},${g},${b}`);
        });

        // Animations: tap to start, tap the running one again to stop
        animBtns.forEach(btn => btn.addEventListener('click', () => {
            const name = btn.dataset.anim;
            if (currentAnim === name) stopAnimation(); else startAnimation(name);
        }));
        animStopBtn.addEventListener('click', stopAnimation);

        // Debounce the speed slider so we don't flood the link (the ESP32 keeps only the newest value)
        speedSlider.addEventListener('input', (e) => {
            speedVal.textContent = e.target.value;
            clearTimeout(speedTimer);
            speedTimer = setTimeout(() => Link.send(`PUB ring/speed ${e.target.value}`), 120);
        });

        // Stay in sync with the device (another browser tab/phone, or a power-off from the board)
        Link.onTopic('ring/status', (p) => {
            const m = p.match(/^ANIM:\s*(\w+)/i);
            if (m) {
                const name = m[1].toUpperCase();
                if (name === 'NONE') {
                    showAnim(null);
                } else {
                    showAnim(name);
                    isPowerOn = true;
                    updatePowerUI(true);
                }
                return;
            }
            const s = p.match(/^SPEED:\s*(\d+)/i);
            if (s) {
                speedSlider.value = s[1];
                speedVal.textContent = s[1];
            }
        });
    }

    async function startAnimation(name) {
        showAnim(name);
        if (!isPowerOn) {
            isPowerOn = true;
            updatePowerUI(true);
        }
        await Link.send(`PUB ring/anim ${name}`);   // the ESP32 powers the ring on by itself
    }

    async function stopAnimation() {
        showAnim(null);
        await Link.send('PUB ring/anim NONE');
    }

    function showAnim(name) {
        currentAnim = name;
        animBtns.forEach(b => b.classList.toggle('active', b.dataset.anim === name));
    }

    async function sendColor(colorName) {
        if (!isPowerOn) {
            isPowerOn = true;
            updatePowerUI(true);
            await Link.send('PUB ring/power ON');
        }
        await Link.send(`PUB ring/color ${colorName}`);
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
        animBtns.forEach(b => { b.disabled = !enabled; });
        animStopBtn.disabled = !enabled;
        speedSlider.disabled = !enabled;
        if (!enabled) {
            isPowerOn = false;
            updatePowerUI(false);
            showAnim(null);
        }
    }

    return { init, sendColor, setEnabled };
})();
