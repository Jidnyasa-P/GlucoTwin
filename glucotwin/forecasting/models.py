"""Forecasters: persistence baseline, ridge baseline, LightGBM primary model with split-conformal intervals.

All learned forecasters predict the CHANGE from the latest reading (delta = y(t+h) - g0), one model per horizon.
Because LightGBM's native `pred_contrib` gives exact additive per-feature contributions to this delta, the
explanation shown in the dashboard is a faithful decomposition of the actual model output.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from ..config import HORIZON_STEPS, HORIZONS_MIN, INTERVAL_ALPHA, LGBM_PARAMS, RIDGE_ALPHA, GLOBAL_SEED
from .features import VARIANTS

MODEL_FORMAT = 1


class PersistenceForecaster:
    name = "persistence"
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.repeat(X["g0"].to_numpy(float)[:, None], len(HORIZON_STEPS), axis=1)


class RidgeForecaster:
    name = "ridge"
    def __init__(self, alpha: float = RIDGE_ALPHA):
        self.alpha, self.scaler, self.models = alpha, None, []
    def fit(self, X: pd.DataFrame, Y: np.ndarray):
        self.scaler = StandardScaler().fit(X.to_numpy(float))          # fit on TRAIN only
        Xs = self.scaler.transform(X.to_numpy(float))
        g0 = X["g0"].to_numpy(float)
        self.models = []
        for h in range(len(HORIZON_STEPS)):
            m = np.isfinite(Y[:, h])
            self.models.append(Ridge(alpha=self.alpha).fit(Xs[m], Y[m, h] - g0[m]))
        return self
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        Xs = self.scaler.transform(X.to_numpy(float)); g0 = X["g0"].to_numpy(float)
        return np.stack([g0 + m.predict(Xs) for m in self.models], axis=1)


class GlucoModel:
    """LightGBM per-horizon delta models + split-conformal absolute-residual intervals + OOD ranges."""
    name = "lightgbm"

    def __init__(self, variant: str = "cgm", seed: int = GLOBAL_SEED, params: Optional[dict] = None):
        if variant not in VARIANTS:
            raise ValueError(f"unknown variant {variant}")
        self.variant, self.seed = variant, seed
        self.params = {**LGBM_PARAMS, **(params or {})}
        self.features: List[str] = VARIANTS[variant]
        self.boosters: List[lgb.Booster] = []
        self.conformal_q: Optional[np.ndarray] = None
        self.interval_alpha = INTERVAL_ALPHA
        self.n_calibration: Optional[int] = None
        self.ood_ranges: Dict[str, tuple] = {}
        self.train_info: Dict = {}

    # -- training -------------------------------------------------------------------------------
    def fit(self, X: pd.DataFrame, Y: np.ndarray):
        X = X[self.features]
        g0 = X["g0"].to_numpy(float)
        self.boosters = []
        for h in range(len(HORIZON_STEPS)):
            m = np.isfinite(Y[:, h])
            est = lgb.LGBMRegressor(random_state=self.seed, **self.params)
            est.fit(X[m], Y[m, h] - g0[m])
            self.boosters.append(est.booster_)
        self.ood_ranges = {c: (float(np.percentile(X[c], 0.5)), float(np.percentile(X[c], 99.5)))
                           for c in ("g0", "slope_per_h")}
        self.train_info = {"n_train_rows": int(len(X)), "variant": self.variant, "seed": self.seed, "params": self.params}
        return self

    def calibrate(self, X: pd.DataFrame, Y: np.ndarray):
        """Split conformal on a calibration set that is disjoint (by patient) from training."""
        pred = self._point(X)
        q = []
        for h in range(len(HORIZON_STEPS)):
            m = np.isfinite(Y[:, h]); r = np.abs(Y[m, h] - pred[m, h]); n = len(r)
            level = min(1.0, math.ceil((n + 1) * (1 - self.interval_alpha)) / n)
            q.append(float(np.quantile(r, level, method="higher")))
        self.conformal_q = np.array(q)
        self.n_calibration = int(len(X))
        return self

    # -- inference ------------------------------------------------------------------------------
    def _point(self, X: pd.DataFrame) -> np.ndarray:
        X = X[self.features]; g0 = X["g0"].to_numpy(float)
        return np.stack([g0 + b.predict(X) for b in self.boosters], axis=1)

    def predict(self, X: pd.DataFrame):
        p = self._point(X)
        if self.conformal_q is None:
            return p, None, None
        return p, p - self.conformal_q, p + self.conformal_q

    def contributions(self, X: pd.DataFrame, horizon_min: int):
        """Exact additive contributions to the predicted CHANGE at one horizon. Returns (contrib_df, base_value)."""
        h = HORIZONS_MIN.index(horizon_min)
        X = X[self.features]
        c = self.boosters[h].predict(X, pred_contrib=True)
        return pd.DataFrame(c[:, :-1], columns=self.features), c[:, -1]

    def ood_mask(self, X: pd.DataFrame) -> np.ndarray:
        m = np.zeros(len(X), bool)
        for c, (lo, hi) in self.ood_ranges.items():
            v = X[c].to_numpy(float); m |= (v < lo) | (v > hi)
        return m

    def ood_reasons(self, X: pd.DataFrame) -> List[List[str]]:
        out = []
        for _, row in X.iterrows():
            r = []
            for c, (lo, hi) in self.ood_ranges.items():
                if not lo <= row[c] <= hi:
                    r.append(f"{c}={row[c]:.1f} outside the training range [{lo:.1f}, {hi:.1f}] (0.5-99.5 pct)")
            out.append(r)
        return out

    # -- versioning / persistence --------------------------------------------------------------
    @property
    def version(self) -> str:
        h = hashlib.sha256()
        for b in self.boosters:
            h.update(b.model_to_string().encode())
        if self.conformal_q is not None:
            h.update(np.round(self.conformal_q, 6).tobytes())
        return f"glucotwin-lgbm-{self.variant}-{h.hexdigest()[:8]}"

    def save(self, path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"format": MODEL_FORMAT, "variant": self.variant, "seed": self.seed, "params": self.params,
                     "boosters": [b.model_to_string() for b in self.boosters], "conformal_q": self.conformal_q,
                     "alpha": self.interval_alpha, "n_calibration": self.n_calibration,
                     "ood_ranges": self.ood_ranges, "train_info": self.train_info}, path)

    @classmethod
    def load(cls, path) -> "GlucoModel":
        d = joblib.load(path)
        if d.get("format") != MODEL_FORMAT:
            raise ValueError("incompatible model file format")
        m = cls(d["variant"], d["seed"], d["params"])
        m.boosters = [lgb.Booster(model_str=s) for s in d["boosters"]]
        m.conformal_q, m.interval_alpha, m.n_calibration = d["conformal_q"], d["alpha"], d["n_calibration"]
        m.ood_ranges, m.train_info = d["ood_ranges"], d["train_info"]
        return m
