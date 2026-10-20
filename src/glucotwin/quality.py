from __future__ import annotations
import pandas as pd

MIN_GLUCOSE, MAX_GLUCOSE = 20.0, 600.0

def validate_observation(timestamp, glucose_mg_dl, existing: pd.DataFrame | None = None):
    """Return (accepted, normalized_timestamp, status/reason); never silently repairs bad values."""
    try:
        ts = pd.Timestamp(timestamp)
        if ts.tzinfo is None: ts = ts.tz_localize("UTC")
        else: ts = ts.tz_convert("UTC")
    except Exception:
        return False, None, "invalid_timestamp"
    try: value = float(glucose_mg_dl)
    except (TypeError, ValueError): return False, ts, "invalid_glucose_value"
    if not (MIN_GLUCOSE <= value <= MAX_GLUCOSE): return False, ts, "glucose_out_of_supported_range"
    if existing is not None and not existing.empty and (pd.to_datetime(existing.timestamp, utc=True) == ts).any():
        return False, ts, "duplicate_timestamp"
    if existing is not None and not existing.empty and ts <= pd.to_datetime(existing.timestamp, utc=True).max():
        return False, ts, "out_of_order_timestamp"
    return True, ts, "accepted"

def quality_status(observations: pd.DataFrame, now=None, stale_minutes=15, min_points=12):
    if observations is None or observations.empty: return {"status":"insufficient_data", "warnings":["No observations available"], "forecast_allowed":False}
    ts = pd.to_datetime(observations.timestamp, utc=True)
    warnings=[]
    age = ((pd.Timestamp(now or pd.Timestamp.now(tz="UTC")) - ts.max()).total_seconds()/60)
    if age > stale_minutes: warnings.append(f"Stream stale: latest reading is {age:.0f} minutes old")
    if len(observations) < min_points: warnings.append(f"Need at least {min_points} observations; found {len(observations)}")
    diffs = ts.sort_values().diff().dropna().dt.total_seconds()/60
    if not diffs.empty and (diffs > 10).any(): warnings.append("Gap detected in recent observation stream")
    allowed = len(observations) >= min_points and age <= stale_minutes
    return {"status":"reliable_for_demo" if allowed and not warnings else ("warning" if warnings else "reliable_for_demo"),
            "warnings":warnings, "forecast_allowed":allowed, "age_minutes":round(age,1)}
