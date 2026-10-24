"""Unified on-disk schema (works for synthetic data AND for prepared real data).

readings CSV:  patient_id, timestamp (ISO-8601 UTC), glucose_mg_dl (NaN = missing), source [, steps, heart_rate_bpm]
profiles CSV:  patient_id, age_years, sex, bmi, diabetes_years, hba1c_prior_pct, diagnosis, medications, source
Every row carries a `source` label so provenance survives all the way to the dashboard.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_READING_COLS = ["patient_id", "timestamp", "glucose_mg_dl", "source"]
REQUIRED_PROFILE_COLS = ["patient_id", "age_years", "sex", "bmi", "diabetes_years", "hba1c_prior_pct", "source"]
PROFILE_FIELDS = ["age_years", "sex", "bmi", "diabetes_years", "hba1c_prior_pct", "diagnosis", "medications"]


def load_readings(path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_READING_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing required columns {missing}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.sort_values(["patient_id", "timestamp"]).reset_index(drop=True)


def load_profiles(path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_PROFILE_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing required columns {missing}")
    return df


def load_cohort(directory):
    """Load a prepared cohort. If `meta.json` names a local_tz, time-of-day features switch to that zone."""
    d = Path(directory)
    meta = d / "meta.json"
    if meta.exists():
        import json
        from ..timeutils import set_local_tz
        tz = json.loads(meta.read_text()).get("local_tz")
        if tz: set_local_tz(tz)
    rp = next((d / n for n in ("readings.csv.gz", "readings.csv") if (d / n).exists()), None)
    if rp is None or not (d / "profiles.csv").exists():
        raise FileNotFoundError(f"{d}: expected readings.csv[.gz] and profiles.csv (see scripts/generate_synthetic_data.py)")
    return load_readings(rp), load_profiles(d / "profiles.csv")
