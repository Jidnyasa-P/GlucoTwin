import numpy as np, pandas as pd, pytest
from glucotwin.config import HORIZONS_MIN
from glucotwin.evaluation.protocol import build_dataset
from glucotwin.forecasting.features import CGM_FEATURES, VARIANTS, compute_features
from glucotwin.forecasting.models import GlucoModel, PersistenceForecaster
from glucotwin.forecasting.pipeline import features_for, train_matrix
from tests.conftest import fit_tiny


def test_feature_values_known_window():
    f = compute_features(np.array([[100., 110, 120, 130, 140]]), "cgm").iloc[0]
    assert f.g0 == 140 and f.d15 == 10 and f.d60 == 40 and f.slope_per_h == pytest.approx(40.0) and f.accel == 0
    assert f.mean_60 == 120 and f.range_60 == 40 and list(compute_features(np.ones((1, 5)) * 100, "cgm").columns) == CGM_FEATURES


def test_missing_context_raises():
    for v in ("cgm_tod", "cgm_personal", "cgm_static"):
        with pytest.raises(ValueError): compute_features(np.ones((1, 5)) * 100, v)
    with pytest.raises(ValueError): compute_features(np.ones((1, 4)) * 100, "cgm")


def test_persistence_returns_latest(cohort, splits):
    ds = build_dataset(*cohort, splits["test"]); X = features_for(ds, "cgm")
    p = PersistenceForecaster().predict(X); assert (p == X["g0"].to_numpy()[:, None]).all() and p.shape[1] == 8


def test_training_is_reproducible(cohort, splits, tiny_model):      # DT-011
    again = fit_tiny(cohort, splits)
    ds = build_dataset(*cohort, splits["test"]); X = features_for(ds, "cgm_tod")
    assert np.allclose(tiny_model.predict(X)[0], again.predict(X)[0], atol=1e-9) and tiny_model.version == again.version


def test_conformal_coverage_on_calibration_set(cohort, splits, tiny_model):
    vc = build_dataset(*cohort, splits["val_calibrate"]); X, Y, _ = train_matrix(vc, "cgm_tod")
    p, lo, hi = tiny_model.predict(X)
    for h in range(8):
        ok = np.isfinite(Y[:, h]); assert np.mean((Y[ok, h] >= lo[ok, h]) & (Y[ok, h] <= hi[ok, h])) >= 0.79


def test_explanation_is_additive_and_faithful(cohort, splits, tiny_model):   # DT-016
    ds = build_dataset(*cohort, splits["test"]); X = features_for(ds, "cgm_tod").iloc[:50]
    pred = tiny_model.predict(X)[0]
    for hm in (30, 60, 120):
        c, base = tiny_model.contributions(X, hm)
        recon = X["g0"].to_numpy() + base + c.sum(1).to_numpy()
        assert np.allclose(recon, pred[:, HORIZONS_MIN.index(hm)], atol=1e-6)


def test_explanation_changes_when_input_changes(loaded):               # DT-016
    eng, pid, _ = loaded
    a = eng.get_state(pid)["latest_forecast"]["explanation"]["horizons"]["60"]["contributions"]
    sc_input = eng.scenario(pid, 40, "window"); assert sc_input["available"]
    X = {c["feature"]: c["value"] for c in a}; assert X["g0"] == pytest.approx(eng.get_state(pid)["last_value"])


def test_ood_flag(tiny_model):
    X = compute_features(np.array([[395., 396, 397, 398, 399]]), "cgm_tod", tod_min=np.array([600.]))
    assert tiny_model.ood_reasons(X)[0] and tiny_model.ood_mask(X)[0]


def test_save_load_roundtrip(tmp_path, tiny_model, cohort, splits):
    tiny_model.save(tmp_path / "m.joblib"); m2 = GlucoModel.load(tmp_path / "m.joblib")
    X = features_for(build_dataset(*cohort, splits["test"]), "cgm_tod").iloc[:20]
    assert m2.version == tiny_model.version and np.allclose(m2.predict(X)[0], tiny_model.predict(X)[0])


def test_committed_model_and_results_consistent():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    if not (root / "models/glucotwin_model.joblib").exists(): pytest.skip("model not trained")
    m = GlucoModel.load(root / "models/glucotwin_model.joblib")
    assert m.version == json.loads((root / "experiments/model_selection.json").read_text())["model_version"]
    assert m.version == json.loads((root / "experiments/results.json").read_text())["model_version"]
    import sys; sys.path.insert(0, str(root / "scripts")); import update_readme
    readme = (root / "README.md").read_text()
    assert update_readme.render(readme) == readme, "README results block is stale: run python scripts/update_readme.py"


def test_all_models_scored_on_same_cases_in_evaluate_script():       # DT-010
    import pathlib
    assert "models were scored on different cases" in (pathlib.Path(__file__).resolve().parents[1] / "scripts/evaluate.py").read_text()
