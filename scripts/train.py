#!/usr/bin/env python
"""Train baselines + LightGBM variants on the TRAIN patients, select the primary variant on VAL_SELECT,
calibrate prediction intervals on VAL_CALIBRATE.  The TEST patients are never read here.

    python scripts/train.py [--data data/generated] [--out models]
"""
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import numpy as np

from glucotwin.config import GLOBAL_SEED, PARSIMONY_REL_TOL
from glucotwin.evaluation.protocol import assert_no_leakage, build_dataset, make_splits
from glucotwin.forecasting.features import VARIANTS, VARIANT_DESCRIPTIONS
from glucotwin.forecasting.models import GlucoModel, PersistenceForecaster, RidgeForecaster
from glucotwin.forecasting.pipeline import features_for, mean_val_mae, train_matrix
from glucotwin.ingestion.loaders import load_cohort

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data/generated")
ap.add_argument("--out", default="models")
ap.add_argument("--seed", type=int, default=GLOBAL_SEED)
a = ap.parse_args()
out = Path(a.out); (out / "ablations").mkdir(parents=True, exist_ok=True)

t0 = time.time()
readings, profiles = load_cohort(a.data)
sources = sorted(readings["source"].unique())
splits = make_splits(profiles.patient_id, a.seed); assert_no_leakage(splits)
print("data sources:", sources, "| split sizes:", {k: len(v) for k, v in splits.items()})
tr = build_dataset(readings, profiles, splits["train"])
vs = build_dataset(readings, profiles, splits["val_select"])
vc = build_dataset(readings, profiles, splits["val_calibrate"])      # NOTE: splits['test'] is never loaded here
print(f"train windows {int(tr.valid_input.sum()):,} | val_select {int(vs.valid_input.sum()):,} | val_cal {int(vc.valid_input.sum()):,}")

val = {}
pers = PersistenceForecaster()
Xv0, Yv, _ = train_matrix(vs, "cgm")
val["persistence"] = {"val_select_mean_mae": mean_val_mae(pers.predict(Xv0), Yv)}

Xt0, Yt0, _ = train_matrix(tr, "cgm")
ridge = RidgeForecaster().fit(Xt0, Yt0)
val["ridge_cgm"] = {"val_select_mean_mae": mean_val_mae(ridge.predict(Xv0), Yv)}
joblib.dump(ridge, out / "ablations" / "ridge_cgm.joblib")

models = {}
for v in VARIANTS:                                    # fixed hyper-parameters (config.LGBM_PARAMS): no search on any split
    Xt, Yt, _ = train_matrix(tr, v); Xv, Yv_, _ = train_matrix(vs, v); Xc, Yc, _ = train_matrix(vc, v)
    m = GlucoModel(v, seed=a.seed).fit(Xt, Yt)
    val[f"lgbm_{v}"] = {"val_select_mean_mae": mean_val_mae(m._point(Xv), Yv_), "description": VARIANT_DESCRIPTIONS[v]}
    m.calibrate(Xc, Yc)
    models[v] = m
    m.save(out / "ablations" / f"lgbm_{v}.joblib")
    print(f"  variant {v:13s} val_select mean MAE = {val[f'lgbm_{v}']['val_select_mean_mae']:.3f} mg/dL")

# pre-declared parsimony rule: simplest variant whose validation MAE is within PARSIMONY_REL_TOL of the best
scores = {v: val[f"lgbm_{v}"]["val_select_mean_mae"] for v in VARIANTS}
best = min(scores.values())
chosen = next(v for v in VARIANTS if scores[v] <= best * (1 + PARSIMONY_REL_TOL))
primary = models[chosen]
primary.save(out / "glucotwin_model.joblib")
sel = {"seed": a.seed, "data_sources": sources, "splits": {k: len(v) for k, v in splits.items()},
       "rule": f"simplest variant within {PARSIMONY_REL_TOL:.0%} of best validation MAE (val_select patients only)",
       "validation": val, "chosen_variant": chosen, "model_version": primary.version,
       "n_calibration_rows": primary.n_calibration, "conformal_q_mgdl": [round(float(x), 3) for x in primary.conformal_q]}
Path("experiments").mkdir(exist_ok=True)
Path("experiments/model_selection.json").write_text(json.dumps(sel, indent=2))
print(f"\nchosen primary variant: {chosen}  ->  {primary.version}   ({time.time() - t0:.0f}s)")
