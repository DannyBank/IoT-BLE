// SG90 Servo Motor Module (Tachometer UI)
const ServoModule = (function () {
    let servoSlider, angleValue, needleGroup, tachoArc, tachoContainer;
    let isDragging = false;

    function init() {
        servoSlider = document.getElementById('servoSlider');
        angleValue = document.getElementById('angleValue');
        needleGroup = document.getElementById('needleGroup');
        tachoArc = document.getElementById('tachoArc');
        tachoContainer = document.getElementById('tachoContainer');

        servoSlider.addEventListener('input', (e) => {
            updateAngle(e.target.value, true);
        });

        // Interactive Dragging on SVG Tachometer
        const handleDrag = (e) => {
            if (!isDragging || servoSlider.disabled) return;
            const rect = tachoContainer.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height;
            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;

            let rad = Math.atan2(clientY - cy, clientX - cx);
            let deg = Math.round(rad * (180 / Math.PI)) + 180;
            deg = Math.max(0, Math.min(180, deg));

            servoSlider.value = deg;
            updateAngle(deg, true);
        };

        tachoContainer.addEventListener('mousedown', (e) => { isDragging = true; handleDrag(e); });
        window.addEventListener('mousemove', handleDrag);
        window.addEventListener('mouseup', () => { isDragging = false; });

        tachoContainer.addEventListener('touchstart', (e) => { isDragging = true; handleDrag(e); });
        window.addEventListener('touchmove', handleDrag);
        window.addEventListener('touchend', () => { isDragging = false; });
    }

    function updateAngle(angle, transmit = false) {
        angleValue.textContent = angle;
        // Map 0-180deg to SVG needle rotation (-180 to 0)
        needleGroup.setAttribute('transform', `rotate(${angle}, 100, 100)`);

        // Gauge arc offset
        const maxDash = 251;
        const offset = maxDash - (angle / 180) * maxDash;
        tachoArc.style.strokeDashoffset = offset;

        if (transmit && BLEManager.isConnected()) {
            BLEManager.send(`PUB servo/angle ${angle}`);
        }
    }

    function setEnabled(enabled) {
        servoSlider.disabled = !enabled;
    }

    return { init, setEnabled };
})();