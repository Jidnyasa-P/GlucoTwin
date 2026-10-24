# Models

| File | What | Tracked in git |
|---|---|---|
| `glucotwin_model.joblib` | Primary LightGBM forecaster (per-horizon, 15-120 min) + split-conformal 80% intervals + out-of-distribution ranges. Variant and version are recorded in `experiments/model_selection.json` (currently `glucotwin-lgbm-cgm_tod-b09655ec`). | Yes (~3.5 MB) |
| `ablations/*.joblib` | Other feature variants and the ridge baseline, used by `scripts/evaluate.py` | No (regenerate with `python scripts/train.py`, ~1 min) |

**Trained on SYNTHETIC data only.** It encodes the synthetic generator's dynamics, not human physiology. Do not use it for any clinical purpose.
Training is deterministic (fixed seed, deterministic LightGBM): re-running `train.py` reproduces the same model version hash.
Model files are `joblib` pickles: only load files you trust.
