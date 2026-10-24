"""Leakage-resistant evaluation protocol: patient-disjoint splits + per-patient calibration period.

* Splits are by PATIENT (a person never appears in two splits; all recordings of a person stay together).
* Each patient's first CALIB_HOURS are history/baseline only; forecast origins start AFTER that period
  in every split, so personalization baselines never use the data being scored.
* Overlapping windows are harmless for leakage here because windows of one patient never cross splits.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from ..config import CALIB_HOURS, HORIZON_STEPS, MIN_CALIB_READINGS_FRAC, SAMPLING_MIN, WINDOW_POINTS
from ..timeutils import local_minutes_of_day
from ..forecasting.features import STATIC_FEATURES

DEMO_PATIENTS = ("SYNTH-001", "SYNTH-002", "SYNTH-003")   # always held out (test) so the live demo uses unseen patients


def make_splits(patient_ids: Sequence[str], seed: int, demo_ids: Sequence[str] = DEMO_PATIENTS) -> Dict[str, List[str]]:
    ids = sorted(set(patient_ids))
    n = len(ids)
    n_test = max(1, round(0.20 * n)); n_vs = max(1, round(0.10 * n)); n_vc = max(1, round(0.10 * n))
    rng = np.random.default_rng(seed)
    demo = [d for d in demo_ids if d in ids]
    rest = [i for i in rng.permutation([i for i in ids if i not in demo]).tolist()]
    test = (demo + rest)[:n_test]
    rest = [i for i in rest if i not in test]
    sel, cal, train = rest[:n_vs], rest[n_vs:n_vs + n_vc], rest[n_vs + n_vc:]
    return {"train": sorted(train), "val_select": sorted(sel), "val_calibrate": sorted(cal), "test": sorted(test)}


@dataclass
class Dataset:
    patient: np.ndarray            # (n,) patient id per forecast origin
    origin_ts: pd.DatetimeIndex    # (n,) forecast origin (UTC)
    W: np.ndarray                  # (n,5) input window
    Y: np.ndarray                  # (n,8) future truth (NaN where missing/beyond record)
    tod_min: np.ndarray            # (n,) local minutes of day
    base_mean: np.ndarray
    base_std: np.ndarray
    static: pd.DataFrame           # (n, 4)
    excluded: Dict[str, str]

    @property
    def observed(self): return np.isfinite(self.W[:, 4])
    @property
    def valid_input(self): return np.isfinite(self.W).all(axis=1)
    def horizon_mask(self, h_idx: int): return self.valid_input & np.isfinite(self.Y[:, h_idx])
    @property
    def full_target_mask(self): return self.valid_input & np.isfinite(self.Y).all(axis=1)
    def __len__(self): return len(self.patient)

    def subset(self, mask) -> "Dataset":
        m = np.asarray(mask)
        return Dataset(self.patient[m], self.origin_ts[m], self.W[m], self.Y[m], self.tod_min[m],
                       self.base_mean[m], self.base_std[m], self.static[m].reset_index(drop=True), self.excluded)


def build_dataset(readings: pd.DataFrame, profiles: pd.DataFrame, patient_ids: Sequence[str],
                  calib_hours: float = CALIB_HOURS) -> Dataset:
    H = max(HORIZON_STEPS)
    prof = profiles.set_index("patient_id")
    parts, excluded = [], {}
    calib_steps = int(round(calib_hours * 60 / SAMPLING_MIN))
    for pid in patient_ids:
        d = readings[readings.patient_id == pid]
        if d.empty or pid not in prof.index:
            excluded[pid] = "no readings or profile"; continue
        s = d.set_index("timestamp")["glucose_mg_dl"].sort_index()
        s = s[~s.index.duplicated(keep="first")]
        grid = pd.date_range(s.index.min().round(f"{SAMPLING_MIN}min"), s.index.max().round(f"{SAMPLING_MIN}min"),
                             freq=f"{SAMPLING_MIN}min", tz="UTC")
        g = s.copy(); g.index = g.index.round(f"{SAMPLING_MIN}min")
        g = g[~g.index.duplicated(keep="first")].reindex(grid).to_numpy(float)
        n = len(g)
        if n <= calib_steps + WINDOW_POINTS + H:
            excluded[pid] = "record shorter than calibration period + window + horizon"; continue
        calib = g[:calib_steps]
        if np.isfinite(calib).sum() < MIN_CALIB_READINGS_FRAC * calib_steps:
            excluded[pid] = "insufficient calibration-period coverage"; continue
        bm, bs = float(np.nanmean(calib)), float(np.nanstd(calib))
        gp = np.concatenate([g, np.full(H, np.nan)])
        W = sliding_window_view(g, WINDOW_POINTS)                      # row j -> origin j+4
        Y = np.stack([gp[WINDOW_POINTS - 1 + h: WINDOW_POINTS - 1 + h + len(W)] for h in HORIZON_STEPS], axis=1)
        origin_idx = np.arange(WINDOW_POINTS - 1, n)
        keep = origin_idx >= calib_steps                                # origins strictly after calibration
        ts = grid[origin_idx][keep]
        st = pd.DataFrame({"hba1c_prior_pct": prof.loc[pid, "hba1c_prior_pct"], "age_years": prof.loc[pid, "age_years"],
                           "bmi": prof.loc[pid, "bmi"], "diabetes_years": prof.loc[pid, "diabetes_years"]},
                          index=range(int(keep.sum())))[STATIC_FEATURES].astype(float)
        parts.append(Dataset(np.full(len(ts), pid), ts, W[keep], Y[keep], local_minutes_of_day(ts),
                             np.full(len(ts), bm), np.full(len(ts), bs), st, {}))
    if not parts:
        raise ValueError("no usable patients")
    cat = lambda f: np.concatenate([f(p) for p in parts])
    return Dataset(cat(lambda p: p.patient), parts[0].origin_ts.append([p.origin_ts for p in parts[1:]]),
                   np.vstack([p.W for p in parts]),
                   np.vstack([p.Y for p in parts]), cat(lambda p: p.tod_min), cat(lambda p: p.base_mean),
                   cat(lambda p: p.base_std), pd.concat([p.static for p in parts], ignore_index=True), excluded)


def assert_no_leakage(splits: Dict[str, List[str]]) -> None:
    names = list(splits)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            inter = set(splits[a]) & set(splits[b])
            if inter:
                raise AssertionError(f"patient leakage between {a} and {b}: {sorted(inter)[:5]}")
