import numpy as np, pandas as pd
from glucotwin.config import CALIB_HOURS
from glucotwin.evaluation.protocol import assert_no_leakage, build_dataset, make_splits
from glucotwin.forecasting.features import VARIANTS, compute_features
from glucotwin.forecasting.pipeline import features_for
from glucotwin.digital_twin.engine import compute_baseline
import pytest


def test_splits_are_patient_disjoint_and_complete(cohort, splits):       # DT-015
    assert_no_leakage(splits)
    allp = [p for v in splits.values() for p in v]
    assert len(allp) == len(set(allp)) == cohort[1].patient_id.nunique()
    assert {"SYNTH-001", "SYNTH-002", "SYNTH-003"} <= set(splits["test"])    # demo patients are held out


def test_assert_no_leakage_detects_overlap():
    with pytest.raises(AssertionError): assert_no_leakage({"train": ["a", "b"], "test": ["b"]})


def test_splits_deterministic(cohort):
    assert make_splits(cohort[1].patient_id, 7) == make_splits(cohort[1].patient_id, 7)


def test_origins_start_after_calibration_period(cohort, splits):         # DT-015
    r, p = cohort; ds = build_dataset(r, p, splits["test"])
    first = r.groupby("patient_id").timestamp.min()
    for pid in splits["test"]:
        m = ds.patient == pid
        assert ds.origin_ts[m].min() >= first[pid] + pd.Timedelta(hours=CALIB_HOURS)


def test_features_cannot_depend_on_future_values(cohort, splits):        # DT-015
    r, p = cohort; pid = splits["test"][0]
    base = build_dataset(r, p, [pid])
    cut = base.origin_ts[len(base) // 2]
    r2 = r.copy(); m = (r2.patient_id == pid) & (r2.timestamp > cut)
    r2.loc[m, "glucose_mg_dl"] = 999.0                                    # corrupt EVERYTHING after the cut
    mod = build_dataset(r2, p, [pid]); idx = np.where(base.origin_ts <= cut)[0]
    for v in VARIANTS:
        a = features_for(base, v).reset_index(drop=True); b = features_for(mod, v).reset_index(drop=True)
        ok_a, ok_b = base.valid_input, mod.valid_input
        rows = [i for i in idx if ok_a[i] and ok_b[i]]
        ia = np.cumsum(ok_a) - 1; ib = np.cumsum(ok_b) - 1
        pd.testing.assert_frame_equal(a.iloc[[ia[i] for i in rows]].reset_index(drop=True), b.iloc[[ib[i] for i in rows]].reset_index(drop=True))


def test_personal_baseline_uses_only_calibration_period(cohort, splits):
    r, p = cohort; pid = splits["test"][0]
    s = r[r.patient_id == pid].set_index("timestamp").glucose_mg_dl.dropna()
    b1 = compute_baseline(s); s2 = s.copy(); s2[s2.index >= s.index[0] + pd.Timedelta(hours=CALIB_HOURS)] = 400
    assert compute_baseline(s2)["mean"] == b1["mean"]
    d1, d2 = build_dataset(r, p, [pid]), None
    assert d1.base_mean[0] == pytest.approx(b1["mean"], rel=1e-9) or abs(d1.base_mean[0] - b1["mean"]) < 1.0   # grid-vs-raw rounding only


def test_ridge_scaler_fit_on_train_only(cohort, splits):
    from glucotwin.forecasting.models import RidgeForecaster
    from glucotwin.forecasting.pipeline import train_matrix
    r, p = cohort
    tr, te = build_dataset(r, p, splits["train"]), build_dataset(r, p, splits["test"])
    X, Y, _ = train_matrix(tr, "cgm"); rf = RidgeForecaster().fit(X, Y)
    assert np.allclose(rf.scaler.mean_, X.to_numpy().mean(0))
    assert not np.allclose(rf.scaler.mean_, features_for(te, "cgm").to_numpy().mean(0))
