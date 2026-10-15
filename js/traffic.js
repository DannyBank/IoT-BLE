// Traffic Light Module
const TrafficModule = (function () {
    let lights = {};
    let btnFadeIn, btnFadeOut;
    let animBtns, animStopBtn, speedSlider, speedVal;
    let currentColor = 'RED';
    let currentAnim = null;
    let speedTimer = null;

    // ---- on-screen preview of the running animation (mirrors the ESP32 timings) ----
    let speed = 5;
    let previewRaf = 0;
    let previewT = 0;
    let previewLast = 0;

    // Each returns lamp intensities [red, yellow, green] (0..1) at animation time t (ms)
    const FRAMES = {
        CYCLE(t) {
            const x = t % 8000;
            if (x < 3000) return [0, 0, 1];
            if (x < 4000) return [0, 1, 0];
            if (x < 7000) return [1, 0, 0];
            return [1, 1, 0];
        },
        CAUTION(t) { return [0, Math.floor(t / 500) % 2 === 0 ? 1 : 0, 0]; },
        CHASE(t) {
            const s = Math.floor(t / 220) % 3;
            return [s === 0 ? 1 : 0, s === 1 ? 1 : 0, s === 2 ? 1 : 0];
        },
        CROSSFADE(t) {
            const p = (t % 3600) / 1200;
            return [0, 1, 2].map(c => {
                let d = Math.abs(p - c);
                d = Math.min(d, 3 - d);
                return 1 - d;
            });
        },
        STROBE(t) {
            const x = t % 900;
            const on = x < 80 || (x >= 160 && x < 240) ? 1 : 0;
            return [on, on, on];
        }
    };

    function previewLoop(now) {
        if (!currentAnim) return;
        previewT += (now - previewLast) * speed / 5;
        previewLast = now;
        const v = FRAMES[currentAnim](previewT);
        [lights.RED, lights.YELLOW, lights.GREEN].forEach((el, i) => {
            const k = Math.max(0, Math.min(1, v[i]));
            el.style.opacity = (0.25 + 0.75 * k).toFixed(2);
            el.style.filter = k > 0.5 ? 'drop-shadow(0 0 12px currentColor)' : 'none';
        });
        previewRaf = requestAnimationFrame(previewLoop);
    }

    function startPreview(name) {
        stopPreview();
        currentAnim = name;
        Object.values(lights).forEach(el => { el.classList.remove('active'); el.classList.add('preview'); });
        previewT = 0;
        previewLast = performance.now();
        previewRaf = requestAnimationFrame(previewLoop);
        animBtns.forEach(b => b.classList.toggle('active', b.dataset.anim === name));
    }

    function stopPreview() {
        cancelAnimationFrame(previewRaf);
        currentAnim = null;
        Object.values(lights).forEach(el => {
            el.classList.remove('preview');
            el.style.opacity = '';
            el.style.filter = '';
        });
        if (animBtns) animBtns.forEach(b => b.classList.remove('active'));
    }

    function init() {
        lights = {
            RED: document.getElementById('tlRed'),
            YELLOW: document.getElementById('tlYellow'),
            GREEN: document.getElementById('tlGreen')
        };

        btnFadeIn = document.getElementById('btnFadeIn');
        btnFadeOut = document.getElementById('btnFadeOut');
        animBtns = document.querySelectorAll('#tlAnims .btn-anim');
        animStopBtn = document.getElementById('tlAnimStop');
        speedSlider = document.getElementById('tlSpeed');
        speedVal = document.getElementById('tlSpeedVal');

        // Tap to start, tap the running one again to stop
        animBtns.forEach(btn => btn.addEventListener('click', () => {
            const name = btn.dataset.anim;
            if (currentAnim === name) stopAnimation(); else startAnimation(name);
        }));
        animStopBtn.addEventListener('click', stopAnimation);

        speedSlider.addEventListener('input', (e) => {
            speed = parseInt(e.target.value, 10);
            speedVal.textContent = e.target.value;
            clearTimeout(speedTimer);
            speedTimer = setTimeout(() => Link.send(`PUB traffic/speed ${e.target.value}`), 120);
        });

        // Stay in sync with the device (another client started/stopped something)
        Link.onTopic('traffic/status', (p) => {
            const m = p.match(/^ANIM:\s*(\w+)/i);
            if (m) {
                const name = m[1].toUpperCase();
                if (name === 'NONE') {
                    if (currentAnim) { stopPreview(); clearLights(); }
                } else if (FRAMES[name] && name !== currentAnim) {
                    startPreview(name);
                }
                return;
            }
            const s = p.match(/^SPEED:\s*(\d+)/i);
            if (s) {
                speed = parseInt(s[1], 10);
                speedSlider.value = s[1];
                speedVal.textContent = s[1];
            }
        });
    }

    function clearLights() {
        Object.values(lights).forEach(el => el.classList.remove('active'));
    }

    async function startAnimation(name) {
        startPreview(name);
        await Link.send(`PUB traffic/anim ${name}`);
    }

    async function stopAnimation() {
        stopPreview();
        clearLights();
        await Link.send('PUB traffic/anim NONE');
    }

    async function setLight(color) {
        // A manual colour replaces any running animation (the ESP32 does the same)
        stopPreview();

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
        await Link.send(payload);
    }

    async function fade(direction) {
        stopPreview();
        const dir = String(direction).trim().toUpperCase();
        // Transmit exact format expected by MicroPython (e.g. PUB traffic/fade IN:RED)
        const payload = `PUB traffic/fade ${dir}:${currentColor}`;
        await Link.send(payload);
    }

    function setEnabled(enabled) {
        if (btnFadeIn) btnFadeIn.disabled = !enabled;
        if (btnFadeOut) btnFadeOut.disabled = !enabled;
        if (animBtns) animBtns.forEach(b => { b.disabled = !enabled; });
        if (animStopBtn) animStopBtn.disabled = !enabled;
        if (speedSlider) speedSlider.disabled = !enabled;
        if (!enabled && currentAnim) { stopPreview(); clearLights(); }
    }

    return { init, setLight, fade, setEnabled };
})();
