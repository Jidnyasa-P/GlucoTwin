"""Faithful explanations: exact additive per-feature contributions from the actual LightGBM model.

For each reported horizon:  predicted_change = base_value + sum(contributions)   (verified numerically),
and forecast = latest_reading + predicted_change.  These are ASSOCIATIONS inside the model, not causal effects.
Natural-language lines are templated from these numbers; nothing is generated free-form.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from ..config import HORIZONS_MIN
from ..forecasting.features import FEATURE_LABELS
from ..forecasting.models import GlucoModel
from ..timeutils import iso

EXPLAIN_HORIZONS = (30, 60, 120)
CAUSAL_NOTE = ("Contributions describe how this model's output depends on its inputs for this patient and time. "
               "They are associations learned from data, not causal effects, and do not imply any treatment would change glucose.")


def explain_forecast(model: GlucoModel, X: pd.DataFrame, previous: Optional[Dict], as_of: pd.Timestamp, pred_row: np.ndarray) -> Dict:
    g0 = float(X["g0"].iloc[0])
    out = {"method": "LightGBM exact additive contributions (pred_contrib) to the predicted change from the latest reading",
           "causal_note": CAUSAL_NOTE, "latest_glucose": g0, "feature_values": {c: float(X[c].iloc[0]) for c in model.features},
           "horizons": {}}
    for hm in EXPLAIN_HORIZONS:
        contrib, base = model.contributions(X, hm)
        c = contrib.iloc[0]
        total = float(base[0] + c.sum())
        change = float(pred_row[HORIZONS_MIN.index(hm)] - g0)
        items = sorted(({"feature": f, "label": FEATURE_LABELS.get(f, f), "value": float(X[f].iloc[0]), "contribution": float(c[f])}
                        for f in model.features), key=lambda d: -abs(d["contribution"]))
        out["horizons"][str(hm)] = {"base_value": float(base[0]), "predicted_change": change,
                                    "additivity_error": abs(total - change), "contributions": items}
    h60 = out["horizons"]["60"]["contributions"][:3]
    out["summary"] = ("Largest contributions to the +60 min change: " +
                      "; ".join(f"{d['label']} = {d['value']:.1f} ({d['contribution']:+.1f} mg/dL)" for d in h60) + ".")
    if previous and previous.get("values"):
        prev_ts = pd.Timestamp(previous["as_of_ts"]); cur_ts = as_of
        common = []
        for i, hm in enumerate(previous["horizons_min"]):
            t = prev_ts + pd.Timedelta(minutes=hm)
            for j, hn in enumerate(HORIZONS_MIN):
                if cur_ts + pd.Timedelta(minutes=hn) == t:
                    common.append({"time_utc": iso(t), "previous": previous["values"][i], "current": float(pred_row[j]),
                                   "revision": float(pred_row[j] - previous["values"][i])})
        out["revision_vs_previous"] = {"previous_forecast_id": previous["id"], "previous_as_of": previous["as_of_ts"],
                                       "previous_model_version": previous["model_version"], "common_times": common}
    return out

