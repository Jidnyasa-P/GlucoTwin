import numpy as np, pandas as pd, pytest
from glucotwin.digital_twin.engine import TwinEngine
from glucotwin.digital_twin.store import TwinStore
from glucotwin.evaluation.protocol import build_dataset, make_splits
from glucotwin.forecasting.models import GlucoModel
from glucotwin.forecasting.pipeline import train_matrix
from glucotwin.ingestion.loaders import PROFILE_FIELDS
from glucotwin.synthetic.generator import generate_cohort

FAST = dict(n_estimators=40, num_leaves=7, n_jobs=1)


@pytest.fixture(scope="session")
def cohort():
    return generate_cohort(n_patients=20, days=8, seed=7)


@pytest.fixture(scope="session")
def splits(cohort):
    return make_splits(cohort[1].patient_id, 7)


def fit_tiny(cohort, splits, variant="cgm_tod", seed=7):
    r, p = cohort
    tr, vc = build_dataset(r, p, splits["train"]), build_dataset(r, p, splits["val_calibrate"])
    X, Y, _ = train_matrix(tr, variant); Xc, Yc, _ = train_matrix(vc, variant)
    return GlucoModel(variant, seed=seed, params=FAST).fit(X, Y).calibrate(Xc, Yc)


@pytest.fixture(scope="session")
def tiny_model(cohort, splits):
    return fit_tiny(cohort, splits)


def profile_of(p, pid):
    row = p[p.patient_id == pid].iloc[0]
    return {k: (row[k].item() if hasattr(row[k], "item") else row[k]) for k in PROFILE_FIELDS}


@pytest.fixture
def loaded(cohort, splits, tiny_model):
    """Engine with one held-out SYNTHETIC patient loaded with 5 days of history, plus its remaining stream."""
    r, p = cohort
    pid = splits["test"][0]
    s = r[r.patient_id == pid].set_index("timestamp").glucose_mg_dl
    cut = s.index[0] + pd.Timedelta(days=5)
    eng = TwinEngine(TwinStore(":memory:"), tiny_model)
    eng.register_patient(pid, profile_of(p, pid), {k: "SYNTHETIC" for k in PROFILE_FIELDS}, "SYNTHETIC", s[s.index < cut])
    return eng, pid, s[s.index >= cut]
