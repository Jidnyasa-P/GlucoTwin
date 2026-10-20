import numpy as np
import pandas as pd
DYNAMIC_FEATURES = [f"lag_{i}" for i in range(1, 13)] + ["mean_3", "mean_6", "std_6", "slope_6", "hour_sin", "hour_cos"]
STATIC_FEATURES = ["age_years", "diabetes_duration_years", "hba1c_percent"]
FEATURES = DYNAMIC_FEATURES + STATIC_FEATURES

def make_feature_row(values, timestamp=None, profile=None):
    x=np.asarray(values,dtype=float)
    if len(x)<12: raise ValueError("At least 12 recent glucose values are required")
    recent=x[-12:][::-1]
    ts=pd.Timestamp(timestamp or pd.Timestamp.now(tz="UTC"))
    if ts.tzinfo is None: ts=ts.tz_localize("UTC")
    hour=ts.hour+ts.minute/60
    row=dict(zip(DYNAMIC_FEATURES, list(recent)+[float(np.mean(x[-3:])),float(np.mean(x[-6:])),float(np.std(x[-6:])),float(np.polyfit(np.arange(6),x[-6:],1)[0]),float(np.sin(2*np.pi*hour/24)),float(np.cos(2*np.pi*hour/24))]))
    profile=profile or {}
    # Explicit missing-value defaults are for demo profile compatibility only.
    row.update(age_years=float(profile.get("age_years",50)),diabetes_duration_years=float(profile.get("diabetes_duration_years",5)),hba1c_percent=float(profile.get("hba1c_percent",7.0)))
    return row

def build_supervised(observations: pd.DataFrame, horizon_steps=6, profiles=None):
    """Create within-patient windows; static profile fields are joined by patient ID."""
    rows=[]; profiles=profiles or {}
    for pid, group in observations.groupby("patient_id"):
        g=group.sort_values("timestamp").reset_index(drop=True)
        vals=g.glucose_mg_dl.to_numpy(); profile=profiles.get(pid,{})
        for i in range(12, len(g)-horizon_steps+1):
            ts=pd.Timestamp(g.timestamp.iloc[i-1])
            row=make_feature_row(vals[:i],ts,profile)
            row.update(patient_id=pid, target=float(vals[i+horizon_steps-1]), target_timestamp=g.timestamp.iloc[i+horizon_steps-1])
            rows.append(row)
    return pd.DataFrame(rows)
