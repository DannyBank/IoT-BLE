// Main Application Controller
window.App = (function () {
    const connectBtn = document.getElementById('connectBtn');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const terminal = document.getElementById('terminal');
    const iosNotice = document.getElementById('iosNotice');
    const transportSelect = document.getElementById('transportSelect');
    const wifiHost = document.getElementById('wifiHost');

    function init() {
        // No Web Bluetooth in this browser (iOS Safari, http origin, ...): point to WiFi / Bluefy
        if (!navigator.bluetooth) {
            iosNotice.style.display = "block";
        }

        // Restore the last transport + WiFi address. When the page is served by the ESP32
        // itself (http://<ip>/), that address is the obvious default.
        transportSelect.value = Link.savedMode();
        const served = /^[\d.]+(:\d+)?$|\.local(:\d+)?$/.test(location.host) && location.protocol === 'http:';
        wifiHost.value = served ? location.host : Link.savedHost();
        if (served && !navigator.bluetooth) transportSelect.value = 'wifi';
        Link.onHostLearned((ip) => { if (!wifiHost.value) wifiHost.value = ip; });
        const syncHostVisibility = () => {
            wifiHost.style.display = transportSelect.value === 'ble' ? 'none' : '';
        };
        transportSelect.addEventListener('change', syncHostVisibility);
        syncHostVisibility();

        // Initialize modules
        TabManager.init();
        RingModule.init();
        MotionModule.init();
        ServoModule.init();
        TrafficModule.init();
        EnvModule.init();
        PushBuzzModule.init();

        // Connect button handler
        connectBtn.addEventListener('click', () => {
            if (Link.isConnected()) {
                Link.disconnect();
            } else {
                Link.connect(transportSelect.value, wifiHost.value, updateUIConnected, log);
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
            transportSelect.disabled = wifiHost.disabled = true;
        } else {
            statusDot.classList.remove('connected');
            statusText.textContent = 'Disconnected';
            connectBtn.textContent = 'Connect';
            transportSelect.disabled = wifiHost.disabled = false;
        }

        RingModule.setEnabled(isConnected);
        ServoModule.setEnabled(isConnected);
        TrafficModule.setEnabled(isConnected);
        EnvModule.setEnabled(isConnected);
        PushBuzzModule.setEnabled(isConnected);
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