let envChart = null;

function initSensorChart() {
    const ctx = document.getElementById('envChart');
    if (!ctx) return;

    envChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'DHT11 Temp (°C)',
                    data: [],
                    borderColor: '#ef4444',
                    tension: 0.3,
                    fill: false
                },
                {
                    label: 'AHT20 Temp (°C)',
                    data: [],
                    borderColor: '#f97316',
                    tension: 0.3,
                    fill: false
                },
                {
                    label: 'AHT20 Humidity (%)',
                    data: [],
                    borderColor: '#06b6d4',
                    tension: 0.3,
                    fill: false
                },
                {
                    label: 'Light Level (%)',
                    data: [],
                    borderColor: '#eab308',
                    tension: 0.3,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    grid: { color: '#334155' },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    grid: { color: '#334155' },
                    ticks: { color: '#94a3b8' }
                }
            },
            plugins: {
                legend: { labels: { color: '#f8fafc' } }
            }
        }
    });
}

function updateSensorData(topic, value) {
    const timestamp = new Date().toLocaleTimeString();

    if (topic === "button/state") {
        const btnVal = document.getElementById("button-value");
        const btnIcon = document.getElementById("button-icon");
        if (btnVal) btnVal.innerText = value;
        if (btnIcon) {
            btnIcon.className = value === "PRESSED" 
                ? "fa-solid fa-hand-pointer sensor-icon active-pressed" 
                : "fa-solid fa-hand-pointer sensor-icon";
        }
    } else if (topic === "dht11/temperature") {
        document.getElementById("dht11-temp").innerText = `${value} °C`;
        addChartData(timestamp, 0, parseFloat(value));
    } else if (topic === "dht11/humidity") {
        document.getElementById("dht11-hum").innerText = `${value} %`;
    } else if (topic === "aht20/temperature") {
        document.getElementById("aht20-temp").innerText = `${value} °C`;
        addChartData(timestamp, 1, parseFloat(value));
    } else if (topic === "aht20/humidity") {
        document.getElementById("aht20-hum").innerText = `${value} %`;
        addChartData(timestamp, 2, parseFloat(value));
    } else if (topic === "bmp280/pressure") {
        document.getElementById("bmp280-press").innerText = `${value} hPa`;
    } else if (topic === "temt6000/raw") {
        document.getElementById("temt6000-raw-val").innerText = `Raw ADC: ${value}`;
    } else if (topic === "temt6000/light") {
        document.getElementById("temt6000-light-percent").innerText = `${value} %`;
        document.getElementById("temt6000-bar").style.width = `${Math.min(100, Math.max(0, value))}%`;
        addChartData(timestamp, 3, parseFloat(value));
    }
}

function addChartData(timeStr, datasetIdx, val) {
    if (!envChart) return;

    if (envChart.data.labels.length > 15) {
        envChart.data.labels.shift();
        envChart.data.datasets.forEach(ds => ds.data.shift());
    }

    if (envChart.data.labels.length === 0 || envChart.data.labels[envChart.data.labels.length - 1] !== timeStr) {
        envChart.data.labels.push(timeStr);
    }

    envChart.data.datasets[datasetIdx].data.push(val);
    envChart.update('none');
}