"""Glue between Dataset objects and forecasters (shared by train.py, evaluate.py and tests)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import HORIZON_STEPS
from ..evaluation.protocol import Dataset
from .features import compute_features


def features_for(ds: Dataset, variant: str, rows_mask=None) -> pd.DataFrame:
    """Feature frame for rows with a complete input window (optionally further restricted)."""
    m = ds.valid_input if rows_mask is None else (ds.valid_input & rows_mask)
    return compute_features(ds.W[m], variant, tod_min=ds.tod_min[m], base_mean=ds.base_mean[m],
                            base_std=ds.base_std[m], static=ds.static[m].reset_index(drop=True))


def train_matrix(ds: Dataset, variant: str):
    """(X, Y, mask) for rows with a complete input window; Y may hold NaN where a horizon is unobserved."""
    m = ds.valid_input
    return features_for(ds, variant), ds.Y[m], m


def mean_val_mae(model_pred: np.ndarray, Y: np.ndarray) -> float:
    errs = []
    for h in range(len(HORIZON_STEPS)):
        ok = np.isfinite(Y[:, h])
        errs.append(np.mean(np.abs(Y[ok, h] - model_pred[ok, h])))
    return float(np.mean(errs))
