import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from sklearn.ensemble import IsolationForest
from prophet import Prophet
import os
import warnings
warnings.filterwarnings("ignore")

class SmartWaterManagement:
    def __init__(self, csv_path="water_usage_data.csv"):
        self.csv_path = csv_path
        self.df = self.load_data()
        self.train_models()

    def load_data(self):
        if os.path.exists(self.csv_path):
            df = pd.read_csv(self.csv_path, parse_dates=["timestamp"])
            df.set_index("timestamp", inplace=True)
            df = df[~df.index.duplicated(keep='last')].sort_index()
            df["water_usage"].fillna(method="ffill", inplace=True)
            df["water_usage"].fillna(df["water_usage"].mean(), inplace=True)
        return df

    def train_models(self):
        cleaned_data = self.df.dropna()
        if not cleaned_data.empty:
            self.model_arima = ARIMA(cleaned_data["water_usage"], order=(5,1,0))
            self.model_fit = self.model_arima.fit()
            self.iso_forest = IsolationForest(contamination=0.05, random_state=42)
            self.iso_forest.fit(cleaned_data[["water_usage"]])
            
            prophet_df = cleaned_data.resample('D').sum().reset_index().rename(columns={"timestamp": "ds", "water_usage": "y"})
            self.prophet_model = Prophet()
            self.prophet_model.fit(prophet_df)

    def detect_leak(self, live_flow_rate, total_water_usage=None):
        if total_water_usage is not None and not np.isnan(total_water_usage):
            new_entry = pd.DataFrame(
                {"timestamp": [pd.Timestamp.now().floor("H")], "water_usage": [total_water_usage]}
            )
            new_entry.set_index("timestamp", inplace=True)
            self.df = pd.concat([self.df, new_entry])
            self.df = self.df[~self.df.index.duplicated(keep='last')].sort_index()
            self.df.to_csv(self.csv_path)
            self.train_models()
        
        try:
            future_forecast = self.model_fit.forecast(steps=1)
            expected_usage = round(float(future_forecast.iloc[0]), 2)
        except Exception as e:
            expected_usage = round(self.df["water_usage"].mean(), 2)
        
        average_usage = self.df["water_usage"].mean()
        threshold = average_usage * 1.5  
        anomaly_score = self.iso_forest.decision_function([[live_flow_rate]])[0]
        
        if live_flow_rate > average_usage:
            leak_status = "Potential Leak" if live_flow_rate < threshold else "Leak Detected"
            overuse_factor = min(1, (live_flow_rate - average_usage) / (threshold - average_usage))
            leak_probability = round(overuse_factor * 100, 2)
        else:
            leak_status = "Normal"
            leak_probability = round(max(0, min(100, anomaly_score * 100)), 2)
        
        return {
            "live_flow_rate": live_flow_rate,
            "expected_usage": expected_usage,
            "leak_status": leak_status,
            "leak_probability": leak_probability,
        }
    
    def predict_weekly_usage(self):
        future = pd.DataFrame({"ds": pd.date_range(start=pd.Timestamp.now(), periods=7, freq="D")})
        forecast = self.prophet_model.predict(future)
        predicted_usage = forecast[['ds', 'yhat']].rename(columns={"ds": "date", "yhat": "predicted_water_usage"})
        last_week_usage = self.df.last("7D").resample('D').sum()[['water_usage']].reset_index().rename(columns={"timestamp": "date"})
        
        return {
            "predicted_next_week": predicted_usage.to_dict(orient="records"),
            "last_week_usage": last_week_usage.to_dict(orient="records")
        }

if __name__ == "__main__":
    smart_water_system = SmartWaterManagement()
    live_flow_rate = 20.2
    total_water_usage = 0
    result = smart_water_system.detect_leak(live_flow_rate, total_water_usage)
    print(result)
    
    weekly_prediction = smart_water_system.predict_weekly_usage()
    print(weekly_prediction)
