from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from .features import make_feature_row, FEATURES

@dataclass
class ForecastResult:
    timestamps: list[str]
    values_mg_dl: list[float]
    lower_mg_dl: list[float]
    upper_mg_dl: list[float]
    model_version: str
    explanation: list[dict]
    status: str = "research_only"

class GlucoseForecaster:
    """Direct multi-horizon-by-recursion model; interval is empirical residual quantile, not clinical calibration."""
    def __init__(self, model=None, residual_abs_error=18.0, model_version="synthetic-hgb-v1"):
        self.model=model or HistGradientBoostingRegressor(max_iter=100, learning_rate=.08, max_leaf_nodes=15, l2_regularization=2.0, random_state=42)
        self.residual_abs_error=float(residual_abs_error); self.model_version=model_version; self.is_fitted=False
    def fit(self, X, y):
        self.model.fit(X[FEATURES], y); self.is_fitted=True
        pred=self.model.predict(X[FEATURES]); self.residual_abs_error=float(np.quantile(np.abs(np.asarray(y)-pred),.90))
        return self
    def predict(self, values, last_timestamp, horizon_steps=24, profile=None):
        if not self.is_fitted: raise RuntimeError("Model must be trained before prediction")
        vals=list(map(float,values)); ts=pd.Timestamp(last_timestamp)
        if ts.tzinfo is None: ts=ts.tz_localize("UTC")
        out=[]
        for _ in range(horizon_steps):
            next_ts=ts+pd.Timedelta(minutes=5)
            row=make_feature_row(vals,next_ts,profile)
            pred=float(self.model.predict(pd.DataFrame([row])[FEATURES])[0])
            # Bounds are heuristic and widen with horizon; not a calibrated clinical interval.
            out.append((next_ts,pred)); vals.append(pred); ts=next_ts
        widths=[self.residual_abs_error*np.sqrt(i+1) for i in range(len(out))]
        explanation=[]
        recent=np.asarray(values[-12:],float)
        explanation.append({"feature":"Most recent glucose", "value":round(float(recent[-1]),1), "interpretation":"Recent level is a model input; not a causal explanation."})
        explanation.append({"feature":"6-reading trend", "value":round(float(np.polyfit(np.arange(6),recent[-6:],1)[0]),2), "interpretation":"Observed short-term slope (mg/dL per 5-minute step)."})
        explanation.append({"feature":"Recent variability", "value":round(float(np.std(recent[-6:])),1), "interpretation":"Standard deviation of the latest six readings."})
        return ForecastResult([t.isoformat() for t,_ in out],[round(v,2) for _,v in out],
            [round(v-w,2) for (_,v),w in zip(out,widths)],[round(v+w,2) for (_,v),w in zip(out,widths)],self.model_version,explanation)

def train_default_model(seed=42):
    from .data import generate_glucose_series
    from .features import build_supervised
    frames=[]
    for i in range(20):
        d=generate_glucose_series(f"SYNTH-TRAIN-{i:03d}",n=500,seed=seed+i)
        frames.append(d)
    profiles={f"SYNTH-TRAIN-{i:03d}": {"age_years": 35+(i*7)%40, "diabetes_duration_years": 1+(i*3)%18, "hba1c_percent": 6.2+(i%8)*0.25} for i in range(20)}
    supervised=build_supervised(pd.concat(frames,ignore_index=True),horizon_steps=1,profiles=profiles)
    return GlucoseForecaster().fit(supervised,supervised.target), supervised
