import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
import datetime
import os
import joblib
from realtime_agent import RealTimeAgent

class DriftEngine:
    def __init__(self):
        self.model_path = 'data/drift_model.joblib'
        self.history_path = 'data/behavior_history.csv'
        self.model = IsolationForest(contamination=0.05, random_state=42, n_estimators=200)
        self.is_trained = False
        self.feature_columns = [
            'hour', 'day_of_week', 'action_type_encoded', 
            'resource_access_count', 'cmd_complexity',
            'action_velocity_5min', 'session_depth'
        ]
        self.baseline_data = None
        
        # Initialize Real-Time Agent
        self.agent = RealTimeAgent(target_folder=os.path.join(os.environ['USERPROFILE'], 'Documents', 'Threat_Test_Zone'))
        self.agent.start()
        
        self._load_memory()

    def _load_memory(self):
        if os.path.exists(self.history_path):
            try:
                self.baseline_data = pd.read_csv(self.history_path)
                print(f"Loaded {len(self.baseline_data)} historical events.")
            except: pass
        
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.is_trained = True
            except: pass

    def _save_memory(self):
        if self.baseline_data is not None:
            self.baseline_data.tail(5000).to_csv(self.history_path, index=False)
        if self.is_trained:
            joblib.dump(self.model, self.model_path)

    def _preprocess(self, df):
        temp_df = df.copy()
        temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'])
        temp_df['hour'] = temp_df['timestamp'].dt.hour
        temp_df['day_of_week'] = temp_df['timestamp'].dt.dayofweek
        
        # Action Map for Real Events
        # We use a helper function to encode since names are now dynamic
        def encode_action(action):
            if action.startswith('START:'): return 1
            action_map = {'FILE_CREATE': 2, 'FILE_WRITE': 3, 'FILE_DELETE': 4, 'FILE_MOD': 5, 'LOGIN': 6}
            return action_map.get(action, 0)

        temp_df['action_type_encoded'] = temp_df['action_type'].apply(encode_action)
        
        for col in self.feature_columns:
            if col not in temp_df.columns:
                temp_df[col] = 0
        return temp_df[self.feature_columns]

    def get_real_events(self):
        events = self.agent.get_new_events()
        if not events:
            return pd.DataFrame()
            
        df = pd.DataFrame(events)
        # Add required feature columns with defaults if missing
        df['action_velocity_5min'] = 0.5 # Default low velocity
        df['session_depth'] = 1 # Default session start
        
        return df

    def train_baseline(self):
        # Without synthetic data, we MUST have some real history to train.
        # If no history exists, we create a tiny "neutral" anchor point 
        # so the model doesn't crash, but it won't be "fake user" data.
        if self.baseline_data is None or len(self.baseline_data) < 5:
             # Create one "anchor" point representing "System Start"
             # This is techinically synthetic but minimal (just 1 row) to init the math.
             anchor = [{
                 'timestamp': datetime.datetime.now(),
                 'user_id': 'SYSTEM',
                 'action_type': 'PROCESS_START',
                 'resource_access_count': 1,
                 'cmd_complexity': 0.1,
                 'action_velocity_5min': 0,
                 'session_depth': 0
             }]
             self.baseline_data = pd.DataFrame(anchor)
            
        X = self._preprocess(self.baseline_data)
        self.model.fit(X)
        self.is_trained = True
        self._save_memory()

    def detect_drift(self, df):
        if df.empty:
            return pd.DataFrame(), 0.0, 0.0

        if not self.is_trained:
            self.train_baseline()
            
        X = self._preprocess(df)
        scores = self.model.decision_function(X)
        drift_scores = np.clip((0.5 - scores), 0, 1) 
        
        results = df.copy()
        results['drift_score'] = drift_scores
        results['is_threat'] = self.model.predict(X) == -1
        
        # Simple Stats
        forecast_prob = np.mean(drift_scores) * 100 if len(drift_scores) > 0 else 0.0
        slope = 0 # Need more points for slope, defaulting 0 for instant
        
        # Intent Logic
        def classify(row):
            if row['action_type'] == 'FILE_DELETE': return "Destruction"
            if row['action_type'] == 'FILE_WRITE': return "Data Modification"
            if row['is_threat']: return "Anomalous Activity"
            return "Normal"
            
        results['intent_prediction'] = results.apply(classify, axis=1)
        
        self.baseline_data = pd.concat([self.baseline_data, df], ignore_index=True)
        self._save_memory()
        
        return results, forecast_prob, slope

    def get_recent_history(self, limit=50):
        if self.baseline_data is None: return []
        return self.baseline_data.tail(limit).to_dict(orient='records')