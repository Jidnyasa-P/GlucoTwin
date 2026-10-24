from __future__ import annotations

from typing import Dict

import numpy as np


def mae(y, p): return float(np.mean(np.abs(y - p)))
def rmse(y, p): return float(np.sqrt(np.mean((y - p) ** 2)))
def r2(y, p):
    ss_res, ss_tot = np.sum((y - p) ** 2), np.sum((y - y.mean()) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


def point_metrics(y, p) -> Dict[str, float]:
    return {"n": int(len(y)), "mae": mae(y, p), "rmse": rmse(y, p), "r2": r2(y, p)}


def prf(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    tp = int(np.sum(y_true & y_pred)); fp = int(np.sum(~y_true & y_pred)); fn = int(np.sum(y_true & ~y_pred))
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * p * r / (p + r) if (tp + fp and tp + fn and (p + r) > 0) else (0.0 if tp + fp + fn else float("nan"))
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f, "n_events": int(y_true.sum()), "n": int(len(y_true))}


def interval_stats(y, lo, hi) -> Dict[str, float]:
    return {"coverage": float(np.mean((y >= lo) & (y <= hi))), "mean_width": float(np.mean(hi - lo)),
            "median_width": float(np.median(hi - lo))}


def patient_bootstrap_diff(patients: np.ndarray, err_a: np.ndarray, err_b: np.ndarray, n_boot: int = 1000, seed: int = 0):
    """95 % bootstrap CI (resampling PATIENTS) of mean(err_a) - mean(err_b). Negative => A better than B."""
    rng = np.random.default_rng(seed)
    ids = np.unique(patients)
    sa = np.array([err_a[patients == i].sum() for i in ids]); sb = np.array([err_b[patients == i].sum() for i in ids])
    cn = np.array([(patients == i).sum() for i in ids], float)
    diffs = []
    for _ in range(n_boot):
        k = rng.integers(0, len(ids), len(ids))
        diffs.append((sa[k].sum() - sb[k].sum()) / cn[k].sum())
    return float(np.mean(err_a) - np.mean(err_b)), float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))
