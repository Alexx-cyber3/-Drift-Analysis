import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
import datetime
import random
import os

class DriftEngine:
    def __init__(self):
        self.model = IsolationForest(contamination=0.1, random_state=42)
        self.is_trained = False
        self.feature_columns = ['hour', 'day_of_week', 'action_type', 'resource_access_count', 'cmd_complexity']
        self.baseline_data = None
        
    def _preprocess(self, df):
        temp_df = df.copy()
        temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'])
        temp_df['hour'] = temp_df['timestamp'].dt.hour
        temp_df['day_of_week'] = temp_df['timestamp'].dt.dayofweek
        
        action_map = {'LOGIN': 0, 'FILE_READ': 1, 'FILE_WRITE': 2, 'DOWNLOAD': 3, 'LOGOUT': 4}
        temp_df['action_type_encoded'] = temp_df['action_type'].map(action_map).fillna(-1)
        
        # Select numeric features for ML
        features = temp_df[['hour', 'day_of_week', 'action_type_encoded', 'resource_access_count', 'cmd_complexity']]
        return features

    def generate_synthetic_data(self, n_samples=1000, anomaly_rate=0.05):
        data = []
        start_time = datetime.datetime.now() - datetime.timedelta(days=1)
        
        for i in range(n_samples):
            is_anomaly = random.random() < anomaly_rate
            
            if is_anomaly:
                hour = random.choice([0, 1, 2, 3, 22, 23]) # Night
                action = random.choice(['DOWNLOAD', 'FILE_WRITE'])
                res_count = random.randint(50, 200)
                cmd_comp = random.uniform(0.7, 1.0)
            else:
                hour = random.randint(9, 18) # Business hours
                action = random.choice(['LOGIN', 'FILE_READ', 'LOGOUT'])
                res_count = random.randint(1, 15)
                cmd_comp = random.uniform(0.1, 0.4)
            
            ts = start_time + datetime.timedelta(seconds=i * 60)
            ts = ts.replace(hour=hour)
            
            data.append({
                'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
                'login_time': hour,
                'action_type': action,
                'resource_access_count': res_count,
                'cmd_complexity': cmd_comp
            })
            
        self.baseline_data = pd.DataFrame(data)
        return self.baseline_data

    def train_baseline(self):
        if self.baseline_data is None:
            self.generate_synthetic_data(anomaly_rate=0) # Pure baseline
            
        X = self._preprocess(self.baseline_data)
        self.model.fit(X)
        self.is_trained = True
        return True

    def detect_drift(self, df):
        if not self.is_trained:
            self.train_baseline()
            
        X = self._preprocess(df)
        # decision_function: lower is more anomalous (range approx -0.5 to 0.5)
        scores = self.model.decision_function(X)
        
        # Micro-drift calculation: 
        # We transform the score so that 0 is perfectly normal and 1 is highly anomalous
        drift_scores = np.clip(0.5 - scores, 0, 1)
        
        results = df.copy()
        results['drift_score'] = drift_scores
        results['is_threat'] = self.model.predict(X) == -1
        
        # Forecasting Logic: 
        # Calculate the 'Forecasting Probability' based on how many 'micro-drifts' (scores > 0.2)
        # are occurring in this batch.
        micro_drift_count = np.sum(drift_scores > 0.2)
        forecast_prob = (micro_drift_count / len(df)) * 100
        
        return results, forecast_prob