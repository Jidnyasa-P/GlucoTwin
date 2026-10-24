"""Central configuration: every tunable constant lives here so docs and code cannot drift apart."""
from __future__ import annotations

PROJECT_NAME = "GlucoTwin"  # provisional: another public repo already uses this name (see README)
DISCLAIMER = (
    "GlucoTwin is an educational research proof of concept. It is not clinically validated and must "
    "not be used to diagnose, treat, or make medication decisions. All demonstration patient records "
    "are synthetic unless explicitly identified otherwise. Forecasts may be wrong, and the prototype "
    "is not a substitute for professional medical judgment."
)

# ---- time / sampling -------------------------------------------------------------------------
SAMPLING_MIN = 15                    # CGM grid (matches the ShanghaiT2DM sampling interval)
WINDOW_POINTS = 5                    # 60-minute input window = 5 readings at 15 min (t-60 ... t)
HORIZON_STEPS = list(range(1, 9))    # 1..8 steps ahead
HORIZONS_MIN = [s * SAMPLING_MIN for s in HORIZON_STEPS]   # 15 ... 120 minutes
LOCAL_TZ = "Asia/Kolkata"            # used only for time-of-day features and display
STALE_AFTER_MIN = 20                 # stream is stale if newest reading is older than this
FUTURE_TOLERANCE_MIN = 5             # reading time stamps may not exceed receipt time by more than this

# ---- physiological plausibility / units ------------------------------------------------------
UNIT = "mg/dL"
GLUCOSE_VALID_RANGE = (20.0, 600.0)  # outside this a CGM value is rejected as implausible
MMOL_TO_MGDL = 18.016

# ---- evaluation protocol (declared BEFORE final test evaluation) ---------------------------------
CALIB_HOURS = 48                     # per-patient calibration period: history/baseline only, never scored
MIN_CALIB_READINGS_FRAC = 0.6        # patients with less calibration coverage are excluded from all models
SPLIT_FRACTIONS = {"train": 60, "val_select": 10, "val_calibrate": 10, "test": 20}  # patient counts for N=100
INTERVAL_ALPHA = 0.2                 # 80 % nominal prediction interval (split conformal)
HYPER_THRESHOLD = 180.0              # mg/dL; ADA/ATTD consensus "level 1 hyperglycemia" threshold
PARSIMONY_REL_TOL = 0.01             # a richer feature variant must beat the simplest by >1 % validation MAE
GLOBAL_SEED = 2026

LGBM_PARAMS = dict(
    n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=50,
    subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
    deterministic=True, force_row_wise=True, n_jobs=2, verbose=-1,
)
RIDGE_ALPHA = 1.0
