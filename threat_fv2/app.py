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
    """Establish the behavioral baseline using existing history or a neutral anchor."""
    engine.train_baseline()
    return jsonify({"status": "Baseline established", "samples": len(engine.baseline_data) if engine.baseline_data is not None else 0})

@app.route('/api/analyze', methods=['GET'])
def analyze():
    """Perform real-time drift analysis on REAL captured events."""
    # Get real events from the agent buffer
    new_data = engine.get_real_events()
    
    if new_data.empty:
        # Return empty state if no new events occurred
        return jsonify({
            "threat_count": 0,
            "average_drift": 0.0,
            "forecast_prob": 0.0,
            "drift_slope": 0.0,
            "logs": [],
            "total_analyzed": 0
        })

    results, forecast_prob, slope = engine.detect_drift(new_data)
    
    # Calculate summary stats
    threat_count = int(results['is_threat'].sum())
    avg_drift = float(results['drift_score'].mean())
    
    # Prepare logs for frontend
    logs = results.sort_values(by='drift_score', ascending=False).head(10).to_dict(orient='records')
    
    return jsonify({
        "threat_count": threat_count,
        "average_drift": avg_drift,
        "forecast_prob": forecast_prob,
        "drift_slope": slope,
        "logs": logs,
        "total_analyzed": len(new_data)
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    """Retrieve recent historical data for the chart."""
    history = engine.get_recent_history(limit=50)
    return jsonify(history)

if __name__ == '__main__':
    # Create a dummy favicon if it doesn't exist
    favicon_path = os.path.join(app.root_path, 'static', 'favicon.ico')
    if not os.path.exists(favicon_path):
        with open(favicon_path, 'wb') as f:
            f.write(b'\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x01\x00\x18\x00\x10\x00\x00\x00\x16\x00\x00\x00')

    app.run(debug=True)