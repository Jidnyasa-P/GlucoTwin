"""Feature construction. ONE code path for training, evaluation and live inference (no train/serve skew).

Every feature uses only readings at or before the forecast origin t.  Window W is ordered oldest->newest
(t-60, t-45, t-30, t-15, t).  `tests/test_leakage.py` verifies that perturbing any future value cannot change a feature.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from ..config import SAMPLING_MIN

CGM_FEATURES = ["g0", "g_m15", "g_m30", "g_m45", "g_m60", "d15", "d30", "d60",
                "slope_per_h", "mean_60", "std_60", "min_60", "max_60", "range_60", "accel"]
TOD_FEATURES = ["tod_sin", "tod_cos"]
PERSONAL_FEATURES = ["g0_minus_base", "base_mean", "base_std", "z0"]
STATIC_FEATURES = ["hba1c_prior_pct", "age_years", "bmi", "diabetes_years"]

# Ordered simplest -> richest (used by the pre-declared parsimony rule).
VARIANTS: Dict[str, list] = {
    "cgm": CGM_FEATURES,
    "cgm_tod": CGM_FEATURES + TOD_FEATURES,
    "cgm_personal": CGM_FEATURES + PERSONAL_FEATURES,
    "cgm_static": CGM_FEATURES + STATIC_FEATURES,
}
VARIANT_DESCRIPTIONS = {
    "cgm": "CGM-derived features only (last 60 min)",
    "cgm_tod": "CGM features + local time of day",
    "cgm_personal": "CGM features + patient baseline from the first 48 h (personalization)",
    "cgm_static": "CGM features + static EHR fields (HbA1c, age, BMI, diabetes duration)",
}
FEATURE_LABELS = {
    "g0": "latest glucose", "g_m15": "glucose 15 min ago", "g_m30": "glucose 30 min ago",
    "g_m45": "glucose 45 min ago", "g_m60": "glucose 60 min ago", "d15": "change over last 15 min",
    "d30": "change over last 30 min", "d60": "change over last 60 min", "slope_per_h": "60-min trend (slope)",
    "mean_60": "60-min mean", "std_60": "60-min variability (SD)", "min_60": "60-min minimum",
    "max_60": "60-min maximum", "range_60": "60-min range", "accel": "trend acceleration",
    "tod_sin": "time of day (sin)", "tod_cos": "time of day (cos)",
    "g0_minus_base": "latest glucose vs patient baseline", "base_mean": "patient baseline mean",
    "base_std": "patient baseline variability", "z0": "latest glucose z-score vs baseline",
    "hba1c_prior_pct": "prior HbA1c (EHR)", "age_years": "age (EHR)", "bmi": "BMI (EHR)",
    "diabetes_years": "diabetes duration (EHR)",
}
_XC = np.array([-30.0, -15.0, 0.0, 15.0, 30.0])


def requires(variant: str) -> Dict[str, bool]:
    f = VARIANTS[variant]
    return {"tod": "tod_sin" in f, "personal": "base_mean" in f, "static": "hba1c_prior_pct" in f}


def compute_features(W: np.ndarray, variant: str = "cgm", tod_min: Optional[np.ndarray] = None,
                     base_mean: Optional[np.ndarray] = None, base_std: Optional[np.ndarray] = None,
                     static: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """W: (n, 5) glucose window oldest->newest (finite). Returns a DataFrame with columns VARIANTS[variant]."""
    W = np.asarray(W, dtype=float)
    if W.ndim != 2 or W.shape[1] != 5:
        raise ValueError("window must have shape (n, 5)")
    g0 = W[:, 4]
    f = {
        "g0": g0, "g_m15": W[:, 3], "g_m30": W[:, 2], "g_m45": W[:, 1], "g_m60": W[:, 0],
        "d15": g0 - W[:, 3], "d30": g0 - W[:, 2], "d60": g0 - W[:, 0],
        "slope_per_h": (W * _XC).sum(1) / (_XC ** 2).sum() * 60.0,
        "mean_60": W.mean(1), "std_60": W.std(1), "min_60": W.min(1), "max_60": W.max(1),
        "range_60": W.max(1) - W.min(1), "accel": (W[:, 4] - W[:, 3]) - (W[:, 3] - W[:, 2]),
    }
    req = requires(variant)
    if req["tod"]:
        if tod_min is None:
            raise ValueError(f"variant {variant!r} requires time-of-day")
        ang = 2 * np.pi * np.asarray(tod_min, float) / 1440.0
        f["tod_sin"], f["tod_cos"] = np.sin(ang), np.cos(ang)
    if req["personal"]:
        if base_mean is None or base_std is None:
            raise ValueError(f"variant {variant!r} requires a personal baseline")
        bm, bs = np.asarray(base_mean, float), np.maximum(np.asarray(base_std, float), 1.0)
        f.update({"g0_minus_base": g0 - bm, "base_mean": bm, "base_std": bs, "z0": (g0 - bm) / bs})
    if req["static"]:
        if static is None:
            raise ValueError(f"variant {variant!r} requires static EHR fields")
        for c in STATIC_FEATURES:
            f[c] = static[c].to_numpy(float)
    return pd.DataFrame({c: f[c] for c in VARIANTS[variant]})
