// Push Button + Buzzer Module
const PushBuzzModule = (function () {
    let btnBadge, btnStateText, btnCount, buzzBadge, buzzStateText;
    let buzzToggle, buzzBeep, buzzFreq, buzzFreqVal, patBtns;
    let presses = 0;
    let buzzerOn = false;
    let holdOn = false;
    let freqTimer = null;

    function init() {
        btnBadge = document.getElementById('btnBadge');
        btnStateText = document.getElementById('btnStateText');
        btnCount = document.getElementById('btnCount');
        buzzBadge = document.getElementById('buzzBadge');
        buzzStateText = document.getElementById('buzzStateText');
        buzzToggle = document.getElementById('buzzToggle');
        buzzBeep = document.getElementById('buzzBeep');
        buzzFreq = document.getElementById('buzzFreq');
        buzzFreqVal = document.getElementById('buzzFreqVal');
        patBtns = document.querySelectorAll('.buzz-pat');

        BLEManager.onTopic('button/state', (p) => {
            const pressed = p === '1' || p.toUpperCase() === 'PRESSED';
            btnBadge.className = 'motion-badge ' + (pressed ? 'detected' : 'no-motion');
            btnStateText.textContent = pressed ? 'PRESSED' : 'RELEASED';
            if (pressed) btnCount.textContent = ++presses;
        });

        // Firmware reports e.g. "STATE: ON", "STATE: OFF" or "STATE: 2500" (tone)
        BLEManager.onTopic('buzzer/status', (p) => {
            const v = p.replace(/^STATE:\s*/i, '').trim().toUpperCase();
            buzzerOn = v !== 'OFF' && v !== '0' && v !== '';
            buzzBadge.className = 'motion-badge buzz-badge ' + (buzzerOn ? 'detected' : 'no-motion');
            buzzStateText.textContent = buzzerOn ? 'BUZZING' : 'SILENT';
            if (!buzzerOn && holdOn) setHold(false);   // pattern/beep ended or device stopped it
        });

        buzzToggle.addEventListener('click', async () => {
            setHold(!holdOn);
            await BLEManager.send(`PUB buzzer/state ${holdOn ? 'ON' : 'OFF'}`);
        });
        buzzBeep.addEventListener('click', () => BLEManager.send('PUB buzzer/beep 200'));
        patBtns.forEach(b => b.addEventListener('click', () => {
            setHold(false);
            BLEManager.send(`PUB buzzer/play ${b.dataset.pat}`);
        }));

        // Debounce slider so we don't flood the BLE link
        buzzFreq.addEventListener('input', (e) => {
            buzzFreqVal.textContent = e.target.value;
            clearTimeout(freqTimer);
            freqTimer = setTimeout(() => BLEManager.send(`PUB buzzer/freq ${e.target.value}`), 150);
        });
    }

    function setHold(on) {
        holdOn = on;
        buzzToggle.classList.toggle('on', on);
        buzzToggle.textContent = on ? 'Stop' : 'Hold ON';
    }

    function setEnabled(enabled) {
        [buzzToggle, buzzBeep, buzzFreq, ...patBtns].forEach(el => { el.disabled = !enabled; });
        if (!enabled) {
            setHold(false);
            btnBadge.className = 'motion-badge no-motion';
            btnStateText.textContent = 'RELEASED';
            buzzBadge.className = 'motion-badge buzz-badge no-motion';
            buzzStateText.textContent = 'SILENT';
        }
    }

    return { init, setEnabled };
})();
