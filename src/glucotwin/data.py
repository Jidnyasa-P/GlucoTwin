from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime, timezone

SYNTHETIC_PATIENT = {
    "patient_id": "SYNTH-001", "provenance": "SYNTHETIC DEMONSTRATION DATA",
    "age_years": 54, "diabetes_type": "Type 2 (synthetic profile)",
    "diabetes_duration_years": 8, "hba1c_percent": 7.4,
    "medication_history": "Example historical context only; not a recommendation",
}

def generate_glucose_series(patient_id: str = "SYNTH-001", n: int = 288, seed: int = 7,
                            start: str = "2026-01-01T00:00:00Z") -> pd.DataFrame:
    """Generate clearly synthetic 5-minute readings for reproducible software demos."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    baseline = 118 + rng.normal(0, 5)
    circadian = 12 * np.sin(2 * np.pi * t / 288 - 0.8)
    meal_bumps = sum(a * np.exp(-0.5 * ((t-c)/5.0)**2) for c, a in [(72, 42), (150, 35), (225, 48)])
    drift = np.cumsum(rng.normal(0, 0.55, n))
    glucose = np.clip(baseline + circadian + meal_bumps + drift + rng.normal(0, 7, n), 55, 280)
    times = pd.date_range(start=start, periods=n, freq="5min", tz="UTC")
    return pd.DataFrame({"patient_id": patient_id, "timestamp": times, "glucose_mg_dl": np.round(glucose, 1),
                         "provenance": "SYNTHETIC"})

def load_demo_data():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    profile = pd.read_csv(root / "data/sample_synthetic/patient_profile.csv").iloc[0].to_dict()
    obs = pd.read_csv(root / "data/sample_synthetic/glucose_observations.csv", parse_dates=["timestamp"])
    obs["timestamp"] = pd.to_datetime(obs["timestamp"], utc=True)
    return profile, obs
