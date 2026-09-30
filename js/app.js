// Main Application Controller
window.App = (function () {
    const connectBtn = document.getElementById('connectBtn');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const terminal = document.getElementById('terminal');
    const iosNotice = document.getElementById('iosNotice');

    function init() {
        // iOS warning check
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
        if (isIOS && !navigator.bluetooth) {
            iosNotice.style.display = "block";
        }

        // Initialize modules
        TabManager.init();
        RingModule.init();
        MotionModule.init();
        ServoModule.init();
        TrafficModule.init();

        // Connect button handler
        connectBtn.addEventListener('click', () => {
            if (BLEManager.isConnected()) {
                BLEManager.disconnect();
            } else {
                BLEManager.connect(updateUIConnected, log);
            }
        });

        // Register Service Worker for PWA compliance
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                const swCode = `self.addEventListener('fetch', (e) => e.respondWith(fetch(e.request)));`;
                const blob = new Blob([swCode], { type: 'text/javascript' });
                navigator.serviceWorker.register(URL.createObjectURL(blob)).catch(() => {});
            });
        }
    }

    function updateUIConnected(isConnected, deviceName = '') {
        if (isConnected) {
            statusDot.classList.add('connected');
            statusText.textContent = deviceName || 'Connected';
            connectBtn.textContent = 'Disconnect';
        } else {
            statusDot.classList.remove('connected');
            statusText.textContent = 'Disconnected';
            connectBtn.textContent = 'Connect';
        }

        RingModule.setEnabled(isConnected);
        ServoModule.setEnabled(isConnected);
        TrafficModule.setEnabled(isConnected);
    }

    function log(type, text) {
        const line = document.createElement('div');
        line.className = `terminal-line ${type}`;
        line.textContent = `[${new Date().toLocaleTimeString().split(' ')[0]}] ${text}`;
        terminal.appendChild(line);
        terminal.scrollTop = terminal.scrollHeight;
    }

    return { init, log };
})();

document.addEventListener('DOMContentLoaded', window.App.init);