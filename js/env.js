// Environment Sensors Module: TEMT6000, AHT20, BMP280, DHT11
const EnvModule = (function () {
    const STALE_MS = 20000;
    const cards = {};           // topic -> { el, card }
    const lastSeen = new Map(); // card element -> timestamp
    let lightCard, lightVal, lightFill;

    function show(el, payload, decimals) {
        const n = parseFloat(payload);
        el.textContent = (payload === 'NA' || isNaN(n)) ? '--' : n.toFixed(decimals);
    }

    function init() {
        document.querySelectorAll('#tab-env [data-v]').forEach(el => {
            const topic = el.getAttribute('data-v');
            if (!topic) return;
            const card = el.closest('.env-card');
            cards[topic] = { el, card };
            Link.onTopic(topic, (payload) => {
                show(el, payload, topic.startsWith('dht11/') ? 0 : 1);
                touch(card);
            });
        });

        lightCard = document.getElementById('envLight');
        lightVal = lightCard.querySelector('[data-v]');
        lightFill = document.getElementById('lightFill');
        const lightRaw = document.getElementById('lightRaw');
        Link.onTopic('temt6000/light', (payload) => {
            show(lightVal, payload, 1);
            const n = parseFloat(payload);
            lightFill.style.width = isNaN(n) ? '0%' : Math.min(100, n) + '%';
            touch(lightCard);
        });
        Link.onTopic('temt6000/raw', (payload) => { lightRaw.textContent = payload; });

        setInterval(() => {
            const now = Date.now();
            document.querySelectorAll('#tab-env .env-card').forEach(card => {
                const t = lastSeen.get(card);
                card.classList.toggle('stale', !t || now - t > STALE_MS);
            });
        }, 2000);
    }

    function touch(card) {
        lastSeen.set(card, Date.now());
        card.classList.remove('stale');
    }

    function setEnabled(enabled) {
        if (enabled) return;
        document.querySelectorAll('#tab-env [data-v]').forEach(el => { el.textContent = '--'; });
        if (lightFill) lightFill.style.width = '0%';
        const raw = document.getElementById('lightRaw');
        if (raw) raw.textContent = '--';
        lastSeen.clear();
        document.querySelectorAll('#tab-env .env-card').forEach(c => c.classList.add('stale'));
    }

    return { init, setEnabled };
})();
