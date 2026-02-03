from flask import Flask, render_template, jsonify, request, send_from_directory
from drift_engine import DriftEngine
import os

app = Flask(__name__)
engine = DriftEngine()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/api/initialize', methods=['POST'])
def initialize():
    """Establish the behavioral baseline."""
    engine.generate_synthetic_data(n_samples=1000, anomaly_rate=0.02)
    engine.train_baseline()
    return jsonify({"status": "Baseline established", "samples": 1000})

@app.route('/api/analyze', methods=['GET'])
def analyze():
    """Perform real-time drift analysis on a new batch of data."""
    # Simulate receiving 50 new events with higher potential for drift
    new_data = engine.generate_synthetic_data(n_samples=50, anomaly_rate=0.15)
    results, forecast_prob = engine.detect_drift(new_data)
    
    # Calculate summary stats
    threat_count = int(results['is_threat'].sum())
    avg_drift = float(results['drift_score'].mean())
    
    # Prepare logs for frontend
    logs = results.sort_values(by='drift_score', ascending=False).head(10).to_dict(orient='records')
    
    return jsonify({
        "threat_count": threat_count,
        "average_drift": avg_drift,
        "forecast_prob": forecast_prob,
        "logs": logs,
        "total_analyzed": 50
    })

if __name__ == '__main__':
    # Create a dummy favicon if it doesn't exist
    favicon_path = os.path.join(app.root_path, 'static', 'favicon.ico')
    if not os.path.exists(favicon_path):
        with open(favicon_path, 'wb') as f:
            f.write(b'\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x01\x00\x18\x00\x10\x00\x00\x00\x16\x00\x00\x00')

    app.run(debug=True)