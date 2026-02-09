let driftChart;
let monitorInterval = null;
const chartCtx = document.getElementById('driftChart').getContext('2d');

// Initialize Chart
async function initChart() {
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
            animation: { duration: 0 }, // Disable animation for performance during streaming
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1.0, // Normalize drift score
                    grid: { color: '#30363d' },
                    ticks: { color: '#8b949e' }
                },
                x: {
                    grid: { display: false },
                    ticks: { 
                        color: '#8b949e', 
                        maxRotation: 45,
                        minRotation: 45,
                        autoSkip: true,
                        maxTicksLimit: 20
                    } 
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });

    // Load History
    try {
        const response = await fetch('/api/history');
        const history = await response.json();
        
        history.forEach(point => {
            // Format timestamp slightly better if needed, or just use raw string if it's "HH:MM:SS"
            // The backend sends 'timestamp' as full YYYY-MM-DD HH:MM:SS string usually
            const label = new Date(point.timestamp).toLocaleTimeString();
            driftChart.data.labels.push(label);
            driftChart.data.datasets[0].data.push(point.drift_score);
        });
        driftChart.update();
    } catch (err) {
        console.error("Failed to load history:", err);
    }
}

// Update Dashboard UI
function updateUI(data) {
    // Update Stats
    document.getElementById('drift-score').innerText = data.average_drift.toFixed(4);
    document.getElementById('events-count').innerText = parseInt(document.getElementById('events-count').innerText) + data.total_analyzed;
    
    // Update Intent Forecast based on Prob + Slope
    const intentEl = document.getElementById('intent-status');
    const intentDesc = intentEl.nextElementSibling;
    
    let trendText = "";
    if (data.drift_slope > 0.005) trendText = "Escalating";
    else if (data.drift_slope < -0.005) trendText = "Subsiding";
    else trendText = "Stable";

    if (data.forecast_prob > 50) {
        intentEl.innerText = 'CRITICAL';
        intentEl.className = 'stat-value text-danger';
        intentDesc.innerHTML = `<i class="bi bi-exclamation-octagon-fill me-1"></i> Trend: ${trendText} (High Risk)`;
    } else if (data.forecast_prob > 20) {
        intentEl.innerText = 'WARNING';
        intentEl.className = 'stat-value text-warning';
        intentDesc.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> Trend: ${trendText}`;
    } else {
        intentEl.innerText = 'NORMAL';
        intentEl.className = 'stat-value text-success';
        intentDesc.innerHTML = `<i class="bi bi-check-circle me-1"></i> Trend: ${trendText}`;
    }

    const threatProb = data.total_analyzed > 0 ? (data.threat_count / data.total_analyzed) * 100 : 0;
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
    
    if (driftChart.data.labels.length > 100) {
        driftChart.data.labels.shift();
        driftChart.data.datasets[0].data.shift();
    }
    driftChart.update();

    // Update Alerts
    const alertList = document.getElementById('alert-list');
    if (data.logs.length > 0) {
        // Clear "No active threats" message if it exists
        if (alertList.innerHTML.includes('No active threats')) alertList.innerHTML = '';
        
        // We only want to prepend new high-score items to avoid UI clutter
        // For this demo, we prepend the top 2 from the batch
        data.logs.slice(0, 3).forEach(log => {
            if (log.is_threat || log.drift_score > 0.4) {
                const item = document.createElement('div');
                item.className = 'list-group-item bg-transparent border-bottom border-secondary py-2';
                
                let intentBadge = '<span class="badge bg-secondary">Anomaly</span>';
                if(log.intent_prediction === 'Data Exfiltration') intentBadge = '<span class="badge bg-danger">Exfiltration</span>';
                if(log.intent_prediction === 'Privilege Escalation') intentBadge = '<span class="badge bg-danger">Priv Escalation</span>';
                if(log.intent_prediction === 'Automated Attack / Bot') intentBadge = '<span class="badge bg-warning text-dark">Bot Activity</span>';
                
                item.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <span class="text-white fw-bold small">${log.action_type.replace('START:', 'APP:')}</span>
                        ${intentBadge}
                    </div>
                    <div class="d-flex justify-content-between">
                        <span class="text-muted tiny">${log.user_id || 'System'}</span>
                        <span class="text-muted tiny">${new Date().toLocaleTimeString()}</span>
                    </div>
                    <div class="small text-white mt-1">
                        Drift: <span class="${log.drift_score > 0.7 ? 'text-danger' : 'text-warning'}">${log.drift_score.toFixed(3)}</span> | 
                        Res: ${log.resource_access_count}
                    </div>
                `;
                alertList.prepend(item);
            }
        });
        
        // Keep list size manageable
        while (alertList.children.length > 20) {
            alertList.removeChild(alertList.lastChild);
        }
        
        const count = alertList.querySelectorAll('.text-danger').length; // Rough count estimate
        document.getElementById('alert-count').innerText = document.querySelectorAll('#alert-list .list-group-item').length;
    }
}

async function runAnalysis() {
    const btn = document.getElementById('analyze-btn');
    if(btn) btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Analyzing...';
    
    try {
        const response = await fetch('/api/analyze');
        const data = await response.json();
        updateUI(data);
    } catch (err) {
        console.error(err);
    } finally {
        if(btn) btn.innerHTML = '<i class="bi bi-play-fill me-1"></i> Run Drift Analysis';
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

document.getElementById('analyze-btn').addEventListener('click', runAnalysis);

document.getElementById('auto-monitor').addEventListener('change', (e) => {
    if (e.target.checked) {
        // Start monitoring
        runAnalysis(); // Run once immediately
        monitorInterval = setInterval(runAnalysis, 2000); // Then every 2s
        document.getElementById('analyze-btn').disabled = true;
        document.getElementById('system-status').innerText = 'MONITORING';
        document.getElementById('system-status').className = 'stat-value text-warning blink';
    } else {
        // Stop monitoring
        clearInterval(monitorInterval);
        monitorInterval = null;
        document.getElementById('analyze-btn').disabled = false;
        document.getElementById('system-status').innerText = 'OPERATIONAL';
        document.getElementById('system-status').className = 'stat-value text-success';
    }
});

// Init
initChart();