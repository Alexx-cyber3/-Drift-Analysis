let driftChart;
const chartCtx = document.getElementById('driftChart').getContext('2d');

// Initialize Chart
function initChart() {
    driftChart = new Chart(chartCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Micro-Drift Intensity',
                data: [],
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: '#30363d' },
                    ticks: { color: '#8b949e' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#8b949e' }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

// Update Dashboard UI
function updateUI(data) {
    // Update Stats
    document.getElementById('drift-score').innerText = data.average_drift.toFixed(4);
    document.getElementById('events-count').innerText = parseInt(document.getElementById('events-count').innerText) + data.total_analyzed;
    
    // Update Intent Forecast
    const intentEl = document.getElementById('intent-status');
    const intentDesc = intentEl.nextElementSibling;
    if (data.forecast_prob > 20) {
        intentEl.innerText = 'HIGH RISK';
        intentEl.className = 'stat-value text-danger';
        intentDesc.innerHTML = '<i class="bi bi-exclamation-octagon-fill me-1"></i> Prediction: Imminent Threat';
    } else if (data.forecast_prob > 10) {
        intentEl.innerText = 'CAUTION';
        intentEl.className = 'stat-value text-warning';
        intentDesc.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-1"></i> Prediction: Increasing Drift';
    } else {
        intentEl.innerText = 'NORMAL';
        intentEl.className = 'stat-value text-success';
        intentDesc.innerHTML = '<i class="bi bi-clock-history me-1"></i> Prediction: No Threat';
    }

    const threatProb = (data.threat_count / data.total_analyzed) * 100;
    const threatEl = document.getElementById('threat-prob');
    const progressEl = document.getElementById('threat-progress');
    
    threatEl.innerText = `${threatProb.toFixed(1)}%`;
    progressEl.style.width = `${threatProb}%`;
    
    if (threatProb > 15) {
        threatEl.className = 'stat-value threat-high';
        progressEl.className = 'progress-bar bg-danger';
    } else if (threatProb > 5) {
        threatEl.className = 'stat-value threat-med';
        progressEl.className = 'progress-bar bg-warning';
    } else {
        threatEl.className = 'stat-value threat-low';
        progressEl.className = 'progress-bar bg-success';
    }

    // Update Chart
    const now = new Date().toLocaleTimeString();
    driftChart.data.labels.push(now);
    driftChart.data.datasets[0].data.push(data.average_drift);
    
    if (driftChart.data.labels.length > 20) {
        driftChart.data.labels.shift();
        driftChart.data.datasets[0].data.shift();
    }
    driftChart.update();

    // Update Alerts
    const alertList = document.getElementById('alert-list');
    if (data.logs.length > 0) {
        if (alertList.innerHTML.includes('No active threats')) alertList.innerHTML = '';
        
        data.logs.forEach(log => {
            if (log.is_threat) {
                const item = document.createElement('div');
                item.className = 'list-group-item bg-transparent border-bottom border-secondary py-2';
                item.innerHTML = `
                    <div class="d-flex justify-content-between">
                        <span class="text-danger small fw-bold">HIGH DRIFT DETECTED</span>
                        <span class="text-muted tiny">${new Date().toLocaleTimeString()}</span>
                    </div>
                    <div class="small text-white">Score: ${log.drift_score.toFixed(4)}</div>
                    <div class="text-white tiny">Login: ${log.login_time}h | Command: ${log.cmd_complexity.toFixed(2)}</div>
                `;
                alertList.prepend(item);
            }
        });
        
        const count = alertList.querySelectorAll('.text-danger').length;
        document.getElementById('alert-count').innerText = count;
    }
}

// Event Listeners
document.getElementById('init-btn').addEventListener('click', async () => {
    const btn = document.getElementById('init-btn');
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Establishing Baseline...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/initialize', { method: 'POST' });
        const result = await response.json();
        
        document.getElementById('system-status').innerText = 'OPERATIONAL';
        document.getElementById('system-status').className = 'stat-value text-success';
        document.getElementById('analyze-btn').disabled = false;
        btn.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Baseline Ready';
        alert('Behavioral Baseline Established Successfully.');
    } catch (err) {
        console.error(err);
        btn.disabled = false;
        btn.innerText = 'Retry Initialization';
    }
});

document.getElementById('analyze-btn').addEventListener('click', async () => {
    const btn = document.getElementById('analyze-btn');
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Analyzing...';
    
    try {
        const response = await fetch('/api/analyze');
        const data = await response.json();
        updateUI(data);
    } catch (err) {
        console.error(err);
    } finally {
        btn.innerHTML = '<i class="bi bi-play-fill me-1"></i> Run Drift Analysis';
    }
});

// Init
initChart();
