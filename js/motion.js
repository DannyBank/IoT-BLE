// PIR Motion Sensor Module
const MotionModule = (function () {
    let motionBadge, motionStateText;

    function init() {
        motionBadge = document.getElementById('motionBadge');
        motionStateText = document.getElementById('motionStateText');

        BLEManager.onNotification((msg) => {
            if (msg.includes('MQTT:motion/state:')) {
                const state = msg.split(':')[2].trim().toUpperCase();
                updateState(state === 'TRUE' || state === 'MOTION' || state === '1');
            }
        });
    }

    function updateState(isDetected) {
        if (isDetected) {
            motionBadge.className = 'motion-badge detected';
            motionStateText.textContent = 'MOTION DETECTED';
        } else {
            motionBadge.className = 'motion-badge no-motion';
            motionStateText.textContent = 'NO MOTION';
        }
    }

    return { init };
})();