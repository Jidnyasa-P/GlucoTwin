#!/usr/bin/env python
"""Final evaluation on the held-out TEST patients using FROZEN models produced by scripts/train.py.
Writes experiments/results.json, experiments/benchmark_report.md and docs/figures/*.png.
Every number in the report is computed here; nothing is typed by hand.

    python scripts/evaluate.py [--data data/generated] [--models models]
"""
import argparse, hashlib, json, platform, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib, lightgbm, numpy as np, pandas as pd, sklearn
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

from glucotwin.config import (CALIB_HOURS, GLOBAL_SEED, HORIZONS_MIN, HYPER_THRESHOLD, INTERVAL_ALPHA, HORIZON_STEPS)
from glucotwin.evaluation import metrics as M
from glucotwin.evaluation.protocol import assert_no_leakage, build_dataset, make_splits
from glucotwin.forecasting.features import VARIANTS, VARIANT_DESCRIPTIONS
from glucotwin.forecasting.models import GlucoModel, PersistenceForecaster
from glucotwin.forecasting.pipeline import features_for
from glucotwin.ingestion.loaders import load_cohort

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data/generated"); ap.add_argument("--models", default="models")
ap.add_argument("--seed", type=int, default=GLOBAL_SEED)
a = ap.parse_args()
mdir = Path(a.models)
H = len(HORIZON_STEPS)

readings, profiles = load_cohort(a.data)
splits = make_splits(profiles.patient_id, a.seed); assert_no_leakage(splits)
sel = json.loads(Path("experiments/model_selection.json").read_text())
primary_variant = sel["chosen_variant"]
test = build_dataset(readings, profiles, splits["test"])
vsel = build_dataset(readings, profiles, splits["val_select"])

lg = {v: GlucoModel.load(mdir / "ablations" / f"lgbm_{v}.joblib") for v in VARIANTS}
ridge = joblib.load(mdir / "ablations" / "ridge_cgm.joblib")
primary = GlucoModel.load(mdir / "glucotwin_model.joblib")
assert primary.version == sel["model_version"] == lg[primary_variant].version, "frozen model mismatch - re-run train.py"
pers = PersistenceForecaster()

vm = test.valid_input
Y, pat = test.Y[vm], test.patient[vm]
pred = {"persistence": pers.predict(features_for(test, "cgm")), "ridge_cgm": ridge.predict(features_for(test, "cgm"))}
for v in VARIANTS:
    pred[f"lgbm_{v}"] = lg[v]._point(features_for(test, v))
PRIM = f"lgbm_{primary_variant}"

# ---- 1. per-horizon point metrics on IDENTICAL cases -----------------------------------------
per_h = {k: {} for k in pred}
for h, hm in enumerate(HORIZONS_MIN):
    ok = np.isfinite(Y[:, h])
    ns = set()
    for k in pred:
        r = M.point_metrics(Y[ok, h], pred[k][ok, h]); per_h[k][hm] = r; ns.add(r["n"])
    assert len(ns) == 1, "models were scored on different cases"          # DT-010

# ---- 2. paired patient-bootstrap CI: primary vs persistence, personalization, static --------------
def boot(a_key, b_key):
    out = {}
    for h, hm in enumerate(HORIZONS_MIN):
        ok = np.isfinite(Y[:, h])
        ea, eb = np.abs(Y[ok, h] - pred[a_key][ok, h]), np.abs(Y[ok, h] - pred[b_key][ok, h])
        d, lo, hi = M.patient_bootstrap_diff(pat[ok], ea, eb, 1000, seed=a.seed)
        out[hm] = {"mae_diff": d, "ci95_low": lo, "ci95_high": hi}
    return out
boot_vs_pers = boot(PRIM, "persistence")
boot_vs_ridge = boot(PRIM, "ridge_cgm")
boot_personal = boot("lgbm_cgm_personal", "lgbm_cgm")
boot_static = boot("lgbm_cgm_static", "lgbm_cgm")
boot_tod = boot("lgbm_cgm_tod", "lgbm_cgm")

# ---- 3. patient-level results -------------------------------------------------------------------
rows = []
for pid in np.unique(pat):
    m = pat == pid
    r = {"patient": pid}
    for k in ("persistence", PRIM):
        errs = [np.mean(np.abs(Y[m & np.isfinite(Y[:, h]), h] - pred[k][m & np.isfinite(Y[:, h]), h])) for h in range(H)]
        r[f"{k}_mae_mean"] = float(np.mean(errs)); r[f"{k}_mae_60"] = float(errs[3]); r[f"{k}_mae_120"] = float(errs[7])
    rows.append(r)
pp = pd.DataFrame(rows)
n_better = int((pp[f"{PRIM}_mae_mean"] < pp["persistence_mae_mean"]).sum())

# ---- 4. prediction intervals (primary) ------------------------------------------------------------
Pp, Lo, Hi = primary.predict(features_for(test, primary_variant))
cov = {}; per_pat_cov = []
for h, hm in enumerate(HORIZONS_MIN):
    ok = np.isfinite(Y[:, h]); cov[hm] = M.interval_stats(Y[ok, h], Lo[ok, h], Hi[ok, h])
for pid in np.unique(pat):
    m = pat == pid
    c = [np.mean((Y[m & np.isfinite(Y[:, h]), h] >= Lo[m & np.isfinite(Y[:, h]), h]) &
                 (Y[m & np.isfinite(Y[:, h]), h] <= Hi[m & np.isfinite(Y[:, h]), h])) for h in range(H)]
    per_pat_cov.append(float(np.mean(c)))
cov_summary = {"nominal": 1 - INTERVAL_ALPHA, "per_patient_mean_coverage": {"min": float(np.min(per_pat_cov)),
               "median": float(np.median(per_pat_cov)), "max": float(np.max(per_pat_cov))},
               "n_patients_below_nominal_minus_10pts": int(np.sum(np.array(per_pat_cov) < 1 - INTERVAL_ALPHA - 0.10))}

# ---- 5. abstention / input-quality accounting -----------------------------------------------------
n_obs = int(test.observed.sum()); n_elig = int(vm.sum()); n_slots = len(test)
ood = primary.ood_mask(features_for(test, primary_variant))
abst = {"origins_total_grid_slots": n_slots, "slots_without_reading": n_slots - n_obs,
        "observed_origins": n_obs, "forecast_issued": n_elig, "withheld_incomplete_window": n_obs - n_elig,
        "abstention_rate_among_observed": (n_obs - n_elig) / n_obs, "qualified_out_of_distribution": int(ood.sum()),
        "qualified_rate_among_issued": float(ood.mean())}
ood_err = {"in_dist_mae_mean": float(np.mean([np.mean(np.abs(Y[~ood & np.isfinite(Y[:, h]), h] - Pp[~ood & np.isfinite(Y[:, h]), h])) for h in range(H)])),
           "ood_mae_mean": float(np.mean([np.mean(np.abs(Y[ood & np.isfinite(Y[:, h]), h] - Pp[ood & np.isfinite(Y[:, h]), h])) for h in range(H)])) if ood.any() else None}

# ---- 6. event task: new hyperglycaemia onset (declared before evaluation, see config) -----------
def event_frame(ds):
    m = ds.full_target_mask & (ds.W[:, 4] <= HYPER_THRESHOLD)
    return m, (ds.Y[m] > HYPER_THRESHOLD).any(axis=1)
vm_ev, v_true = event_frame(vsel)
tm_ev, t_true = event_frame(test)
def pick_delta(model_pred_val):
    best = (-1, 0.0)
    for d in np.arange(-30, 12.5, 2.5):
        f = M.prf(v_true, (model_pred_val.max(1) > HYPER_THRESHOLD + d))["f1"]
        f = 0.0 if np.isnan(f) else f
        if f > best[0]: best = (f, float(d))
    return best[1]
ev = {"definition": f"event = latest glucose <= {HYPER_THRESHOLD:g} mg/dL AND true glucose exceeds {HYPER_THRESHOLD:g} mg/dL at any of the next 8 readings (15-120 min)",
      "n_test_origins": int(tm_ev.sum()), "n_test_events": int(t_true.sum()), "event_rate": float(t_true.mean()), "models": {}}
def pred_on(ds, mask, model, variant):
    return model.predict(features_for(ds, variant, mask))[0] if hasattr(model, "boosters") else model.predict(features_for(ds, variant, mask))
for name, mdl, var in (("ridge_cgm", ridge, "cgm"), (PRIM, lg[primary_variant], primary_variant)):
    dlt = pick_delta(pred_on(vsel, vm_ev, mdl, var))          # decision offset tuned on val_select only
    r = M.prf(t_true, pred_on(test, tm_ev, mdl, var).max(1) > HYPER_THRESHOLD + dlt); r["threshold_offset_mgdl"] = dlt
    ev["models"][name] = r
ev["models"]["persistence"] = M.prf(t_true, np.zeros_like(t_true))   # persistence cannot cross the threshold by definition

# ---- 7. failure analysis ----------------------------------------------------------------------------
e120 = np.abs(Y[:, 7] - pred[PRIM][:, 7]); okk = np.isfinite(e120)
order = np.argsort(-np.where(okk, e120, -1))[:200]
idx_valid = np.where(vm)[0]
tod_hour = (test.tod_min[vm] // 60).astype(int)
by_hour = {int(hh): float(np.mean(e120[okk & (tod_hour == hh)])) for hh in range(24) if (okk & (tod_hour == hh)).any()}
slope = features_for(test, "cgm")["slope_per_h"].to_numpy()
phase = {"rising_>30mgdl_per_h": float(np.mean(e120[okk & (slope > 30)])), "falling_<-30": float(np.mean(e120[okk & (slope < -30)])),
         "flat_|slope|<=30": float(np.mean(e120[okk & (np.abs(slope) <= 30)]))}
worst = [{"patient": str(pat[i]), "origin_utc": str(test.origin_ts[idx_valid[i]]), "latest": float(test.W[idx_valid[i], 4]),
          "true_120": float(Y[i, 7]), "pred_120": float(pred[PRIM][i, 7])} for i in order[:5]]

# ---- 8. provenance & reproducibility -------------------------------------------------------------------
rp = next(p for p in (Path(a.data) / "readings.csv.gz", Path(a.data) / "readings.csv") if p.exists())
results = {
  "data_sources": sorted(readings["source"].unique()),
  "WARNING": "Results on SYNTHETIC data measure recovery of the synthetic generator's dynamics. They are NOT clinical evidence.",
  "data_md5": hashlib.md5((__import__("gzip").open(rp).read() if rp.suffix == ".gz" else rp.read_bytes())).hexdigest(), "seed": a.seed, "model_version": primary.version,
  "primary_variant": primary_variant, "calibration_hours": CALIB_HOURS,
  "env": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "lightgbm": lightgbm.__version__, "sklearn": sklearn.__version__},
  "split_patients": {k: len(v) for k, v in splits.items()}, "test_patients": splits["test"], "excluded_test": test.excluded,
  "test_origin_counts": {"grid_slots": n_slots, "complete_input_windows": n_elig},
  "per_horizon": per_h, "bootstrap_primary_vs_persistence": boot_vs_pers, "bootstrap_primary_vs_ridge": boot_vs_ridge,
  "bootstrap_personalization_vs_cgm": boot_personal, "bootstrap_static_vs_cgm": boot_static, "bootstrap_tod_vs_cgm": boot_tod,
  "patient_level": {"n_patients": len(pp), "n_primary_better_than_persistence_mean_mae": n_better, "table": pp.round(2).to_dict("records")},
  "intervals": {"per_horizon": cov, **cov_summary}, "abstention": abst, "ood_error": ood_err, "event_task": ev,
  "failure_analysis": {"mae120_by_local_hour": by_hour, "mae120_by_trend_phase": phase, "worst_5_at_120min": worst},
}
Path("experiments").mkdir(exist_ok=True)
def _clean(o):                       # strict JSON: NaN/inf -> null
    if isinstance(o, dict): return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_clean(v) for v in o]
    if isinstance(o, (float, np.floating)): return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer): return int(o)
    return o
Path("experiments/results.json").write_text(json.dumps(_clean(results), indent=2, allow_nan=False))

# ---- figures --------------------------------------------------------------------------------------------
Path("docs/figures").mkdir(parents=True, exist_ok=True)
fig, ax = plt.subplots(figsize=(7, 4))
for k, st in (("persistence", "k--"), ("ridge_cgm", "b-o"), ("lgbm_cgm", "c-s"), (PRIM, "r-o")):
    ax.plot(HORIZONS_MIN, [per_h[k][h]["mae"] for h in HORIZONS_MIN], st, label=k, ms=4)
ax.set(xlabel="forecast horizon (min)", ylabel="MAE (mg/dL)", title="Held-out test MAE by horizon (SYNTHETIC data)"); ax.legend(); ax.grid(alpha=.3)
fig.tight_layout(); fig.savefig("docs/figures/mae_by_horizon.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(HORIZONS_MIN, [cov[h]["coverage"] for h in HORIZONS_MIN], "g-o"); ax.axhline(1 - INTERVAL_ALPHA, color="k", ls="--", label="nominal 80 %")
ax.set(ylim=(0.5, 1), xlabel="forecast horizon (min)", ylabel="empirical coverage", title="Prediction-interval coverage on held-out test patients (SYNTHETIC)"); ax.legend(); ax.grid(alpha=.3)
fig.tight_layout(); fig.savefig("docs/figures/interval_coverage.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(5, 5))
ax.scatter(pp["persistence_mae_mean"], pp[f"{PRIM}_mae_mean"], c="tab:red"); lim = [0, max(pp.persistence_mae_mean.max(), pp[f"{PRIM}_mae_mean"].max()) * 1.05]
ax.plot(lim, lim, "k--"); ax.set(xlim=lim, ylim=lim, xlabel="persistence MAE (mg/dL)", ylabel="primary model MAE (mg/dL)", title="Per-patient mean MAE (test, SYNTHETIC)"); ax.grid(alpha=.3)
fig.tight_layout(); fig.savefig("docs/figures/per_patient_mae.png", dpi=150); plt.close(fig)

# ---- benchmark report (generated) ---------------------------------------------------------------------------
def tbl(keys):
    h = "| Horizon (min) | " + " | ".join(keys) + " |\n|---|" + "---|" * len(keys) + "\n"
    return h + "".join(f"| {hm} | " + " | ".join(f"{per_h[k][hm]['mae']:.2f} / {per_h[k][hm]['rmse']:.2f} / {per_h[k][hm]['r2']:.3f}" for k in keys) + " |\n" for hm in HORIZONS_MIN)
def btbl(b):
    return "| Horizon | MAE difference (mg/dL) | 95 % CI (patient bootstrap) |\n|---|---|---|\n" + "".join(
        f"| {hm} | {b[hm]['mae_diff']:+.2f} | [{b[hm]['ci95_low']:+.2f}, {b[hm]['ci95_high']:+.2f}] |\n" for hm in HORIZONS_MIN)
def _f(x): return "n/a (no positive predictions)" if x != x else f"{x:.3f}"
def rowev(k, r): return f"| {k} | {r['tp']} | {r['fp']} | {r['fn']} | {_f(r['precision'])} | {_f(r['recall'])} | {_f(r['f1'])} |\n"
evtbl = "| Model | TP | FP | FN | Precision | Recall | F1 |\n|---|---|---|---|---|---|---|\n" + "".join(rowev(k, ev["models"][k]) for k in ("persistence", "ridge_cgm", PRIM))
ptbl = "| Horizon | Coverage (nominal 80 %) | Mean width (mg/dL) | Median width |\n|---|---|---|---|\n" + "".join(
    f"| {hm} | {cov[hm]['coverage']:.3f} | {cov[hm]['mean_width']:.1f} | {cov[hm]['median_width']:.1f} |\n" for hm in HORIZONS_MIN)
report = f"""# Benchmark report (auto-generated by `scripts/evaluate.py` - do not edit by hand)

> **DATA WARNING.** Data source(s): **{', '.join(results['data_sources'])}**. If this says SYNTHETIC, every number below measures how
> well the models recover the *synthetic generator's* dynamics. These are **not clinical results** and say nothing about real patients,
> and nothing about type 2 vs type 1 diabetes in any real population.

## Design
- Data MD5 (of uncompressed readings) `{results['data_md5']}`, seed {a.seed}, model version `{primary.version}` (primary variant: `{primary_variant}` - {VARIANT_DESCRIPTIONS[primary_variant]}).
- Patient-disjoint split: {results['split_patients']}. Test patients: {len(splits['test'])} (demo patients SYNTH-001..003 are among them). Excluded in test: {test.excluded or 'none'}.
- Input window 60 min (5 readings @ 15 min); horizons 15-120 min; first {CALIB_HOURS} h of every patient is calibration-only and never scored.
- Test origins: {n_slots:,} grid slots, {n_obs:,} with a reading, {n_elig:,} with a complete input window (forecast issued).
- Primary variant chosen on `val_select` patients only (parsimony rule, `experiments/model_selection.json`); intervals calibrated on `val_calibrate` patients; the test patients were not used for any choice.
- All models are scored on **identical cases** per horizon (asserted in code).

## 1. Point forecasts: MAE / RMSE (mg/dL) / R2 per horizon
{tbl(['persistence', 'ridge_cgm', 'lgbm_cgm', PRIM])}
Primary model = `{PRIM}`.

### Primary model vs persistence (negative = primary better)
{btbl(boot_vs_pers)}
### Primary model vs ridge baseline
{btbl(boot_vs_ridge)}

## 2. Ablations / experiments (all on the same test cases)
Full MAE / RMSE / R2 for every variant:

{tbl(['lgbm_cgm', 'lgbm_cgm_tod', 'lgbm_cgm_personal', 'lgbm_cgm_static'])}
**Time-of-day vs CGM-only** (`cgm_tod` minus `cgm`):
{btbl(boot_tod)}
> The synthetic generator uses scheduled meals, so a time-of-day gain here is expected *by construction*. It must not be read as evidence that time of day helps in real patients.

**Personalization** (patient baseline from first {CALIB_HOURS} h; `cgm_personal` minus `cgm`):
{btbl(boot_personal)}
**Static EHR fields** (`cgm_static` minus `cgm`):
{btbl(boot_static)}
> Static-to-glucose links in the synthetic data exist by construction, so this experiment cannot establish a real physiological relationship.

## 3. Patient-level results
Primary model has lower mean MAE than persistence for **{n_better} of {len(pp)}** test patients. Per-patient table is in `experiments/results.json`.

![per patient](../docs/figures/per_patient_mae.png)

## 4. Prediction intervals (primary, split conformal, 80 % nominal)
{ptbl}
Per-patient mean coverage: min {cov_summary['per_patient_mean_coverage']['min']:.3f}, median {cov_summary['per_patient_mean_coverage']['median']:.3f}, max {cov_summary['per_patient_mean_coverage']['max']:.3f};
{cov_summary['n_patients_below_nominal_minus_10pts']} of {len(per_pat_cov)} patients are more than 10 points below nominal. Interval width is constant per horizon (split-conformal, non-adaptive), so mean and median widths coincide. Conformal guarantees are *marginal* (averaged over patients), not per-patient.

![coverage](../docs/figures/interval_coverage.png)

## 5. Abstention and input quality
- Grid slots without any reading: {abst['slots_without_reading']:,} of {abst['origins_total_grid_slots']:,}.
- Observed origins where the forecast was **withheld** (incomplete 60-min window, no imputation): {abst['withheld_incomplete_window']:,} of {abst['observed_origins']:,} (**{abst['abstention_rate_among_observed']:.1%}**).
- Forecasts issued but **qualified** as out-of-distribution: {abst['qualified_out_of_distribution']:,} ({abst['qualified_rate_among_issued']:.2%}).
- Mean MAE in-distribution {ood_err['in_dist_mae_mean']:.2f} mg/dL; out-of-distribution {('%.2f' % ood_err['ood_mae_mean']) if ood_err['ood_mae_mean'] is not None else 'n/a (none)'} mg/dL.
- The missingness rate is a parameter of the synthetic generator, not a measured property of any real device.

## 6. Event task: new hyperglycaemia onset (research label, not an alarm)
{ev['definition']}. Test origins eligible: {ev['n_test_origins']:,}; events: {ev['n_test_events']:,} (base rate {ev['event_rate']:.1%}).
Decision offset for each learned model was tuned on `val_select` only.

{evtbl}
Persistence can never predict a threshold crossing from a value at or below the threshold, so its recall is 0 by construction.

## 7. Failure analysis (primary, 120-min horizon)
- MAE by trend phase: {json.dumps({k: round(v, 1) for k, v in phase.items()})}
- Worst five forecasts (patient / origin UTC / latest / true +120 / predicted +120): {'; '.join(f"{w['patient']} {w['origin_utc'][:16]} {w['latest']:.0f}/{w['true_120']:.0f}/{w['pred_120']:.0f}" for w in worst)}
- Meals are unobserved by the model, so excursions that start after the forecast origin cannot be anticipated except through learned schedule regularities.

## Limitations
Synthetic data only in this report; one 14-day record per patient; fixed hyper-parameters; single random seed for the split; no clinical validation; type 2 population claims are not supported.
"""
Path("experiments/benchmark_report.md").write_text(report)
print(report[:2500]); print("\nwrote experiments/results.json, experiments/benchmark_report.md, docs/figures/*.png")
