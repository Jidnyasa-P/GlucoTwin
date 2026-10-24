import json, socket
import numpy as np, pandas as pd, pytest
from glucotwin.config import HORIZONS_MIN
from glucotwin.digital_twin.engine import SCENARIO_LABEL, TwinEngine
from glucotwin.digital_twin.store import TwinStore
from tests.conftest import profile_of


def feed(eng, pid, stream, n):
    st = None
    for t, v in list(stream.items())[:n]:
        st = eng.tick(pid, t) if np.isnan(v) else eng.process_observation(pid, t, v, "replay:SYNTHETIC", received_at=t)
    return st


def first_valid(stream):
    return next((t, v) for t, v in stream.items() if not np.isnan(v))


def test_load_profile_creates_state(loaded):              # DT-001
    eng, pid, _ = loaded
    st = eng.get_state(pid)
    assert st["patient_id"] == pid and st["source_label"] == "SYNTHETIC"
    assert st["n_observations"] > 400 and st["baseline"] is not None and st["clock_ts"] and st["last_value"]
    assert set(st["profile"]) >= {"age_years", "hba1c_prior_pct"}


def test_new_observation_updates_state_and_forecast(loaded):   # DT-002
    eng, pid, stream = loaded
    before = eng.get_state(pid); n0 = before["n_observations"]
    t, v = first_valid(stream)
    after = eng.process_observation(pid, t, v, "replay:SYNTHETIC", received_at=t)
    assert after["n_observations"] == n0 + 1 and after["clock_ts"] > before["clock_ts"]
    assert after["last_value"] == v
    assert after["latest_forecast"]["id"] != before["latest_forecast"]["id"]
    assert after["latest_forecast"]["as_of_ts"] > before["latest_forecast"]["as_of_ts"]
    assert any(a == "forecast_generated" for a in eng.store.get_audit(pid)["event_type"])


def test_duplicate_handled_deterministically(loaded):    # DT-003
    eng, pid, stream = loaded
    t, v = first_valid(stream); eng.process_observation(pid, t, v, "x", received_at=t)
    n = eng.get_state(pid)["n_observations"]; fid = eng.get_state(pid)["latest_forecast"]["id"]
    eng.process_observation(pid, t, v, "x", received_at=t)            # identical
    eng.process_observation(pid, t, v + 30, "x", received_at=t)       # conflicting
    st = eng.get_state(pid)
    assert st["n_observations"] == n and st["last_value"] == v         # first write wins
    assert st["latest_forecast"]["id"] == fid                          # no new forecast from rejected data
    types = list(eng.store.get_audit(pid)["event_type"])
    assert "duplicate_ignored" in types and "conflict_quarantined" in types
    assert list(eng.store.get_quarantine(pid)["status"]) == ["conflict_quarantined"]


def test_invalid_input_quarantined(loaded):              # DT-004
    eng, pid, stream = loaded
    t, v = first_valid(stream); clock = pd.Timestamp(eng.get_state(pid)["clock_ts"])
    n = eng.get_state(pid)["n_observations"]
    eng.process_observation(pid, t, 9999, "x", received_at=t)
    eng.process_observation(pid, "2026-01-10 12:00:00", 140, "x", received_at=t)
    eng.process_observation(pid, t + pd.Timedelta(hours=5), 140, "x", received_at=t)
    q = eng.store.get_quarantine(pid)
    assert len(q) == 3 and eng.get_state(pid)["n_observations"] == n
    assert set(q["status"]) == {"rejected_invalid_value", "rejected_invalid_timestamp"}


def test_missing_observation_withholds_forecast(loaded):  # DT-005
    eng, pid, stream = loaded
    items = list(stream.items())
    st = None
    for t, v in items[:12]:
        st = eng.process_observation(pid, t, v, "x", received_at=t) if not np.isnan(v) else eng.tick(pid, t)
    # skip one slot then deliver the next: the window now has a hole
    t2, v2 = items[13]
    if np.isnan(v2): pytest.skip("synthetic gap landed here")
    st = eng.process_observation(pid, t2, v2, "x", received_at=t2)
    assert st["status"] == "withheld_insufficient" and st["latest_forecast"] is None and st["quality"]["n_missing_in_window"] >= 1


def test_stopped_stream_triggers_stale_warning(loaded):  # DT-006 / DT-008
    eng, pid, _ = loaded
    clock = pd.Timestamp(eng.get_state(pid)["clock_ts"])
    st = eng.tick(pid, clock + pd.Timedelta(minutes=45))
    assert st["status"] == "withheld_stale" and st["latest_forecast"] is None and "stale" in st["reasons"][0]
    assert "forecast_withheld" in list(eng.store.get_audit(pid)["event_type"])


def test_forecast_structure_units_horizon(loaded):       # DT-007
    eng, pid, stream = loaded
    st = feed(eng, pid, stream, 6)
    fc = st["latest_forecast"]
    assert fc["horizons_min"] == HORIZONS_MIN and HORIZONS_MIN[-1] == 120 and len(fc["values"]) == 8
    assert all(l <= v <= u for l, v, u in zip(fc["lower"], fc["values"], fc["upper"]))
    assert fc["model_version"] == eng.model.version and fc["interval_nominal"] == pytest.approx(0.8)
    assert all(20 < v < 600 for v in fc["values"]) and pd.Timestamp(fc["as_of_ts"]) == pd.Timestamp(st["last_obs_ts"])


def test_no_forecast_when_no_data():                     # DT-008
    from tests.conftest import fit_tiny
    eng = TwinEngine(TwinStore(":memory:"), None)
    eng.register_patient("P", {}, {}, "SYNTHETIC")
    assert eng.get_state("P")["latest_forecast"] is None and eng.get_state("P")["status"] == "no_data"


def test_no_model_withholds(loaded):
    eng, pid, stream = loaded
    eng.model = None
    t, v = first_valid(stream); st = eng.process_observation(pid, t, v, "x", received_at=t)
    assert st["status"] == "withheld_no_model" and st["latest_forecast"] is None


def test_scenario_is_distinct_and_labelled(loaded):      # DT-009
    eng, pid, stream = loaded; feed(eng, pid, stream, 6)
    sc = eng.scenario(pid, 30, "latest"); sc2 = eng.scenario(pid, 30, "window")
    assert sc["available"] and sc["is_hypothetical"] and sc["label"] == SCENARIO_LABEL and "HYPOTHETICAL" in sc["label"]
    assert sc["scenario"]["values"] != sc["base"]["values"] and sc2["scenario"]["values"] != sc["scenario"]["values"]
    zero = eng.scenario(pid, 0, "latest")
    assert zero["scenario"]["values"] == pytest.approx(zero["base"]["values"])
    assert eng.get_state(pid)["latest_forecast"]["id"] == eng.get_state(pid)["latest_forecast"]["id"]
    assert "scenario_run" in list(eng.store.get_audit(pid)["event_type"])
    assert not eng.scenario(pid, 1000, "window")["available"]


def test_scenario_unavailable_when_stale(loaded):
    eng, pid, _ = loaded
    eng.tick(pid, pd.Timestamp(eng.get_state(pid)["clock_ts"]) + pd.Timedelta(hours=2))
    assert eng.scenario(pid, 10)["available"] is False


def test_empty_store_no_crash():                         # DT-012
    eng = TwinEngine(TwinStore(":memory:"), None)
    assert eng.store.patient_ids() == []
    with pytest.raises(KeyError): eng.get_state("none")


def test_restart_reloads_saved_state(tmp_path, cohort, splits, tiny_model):   # DT-013
    r, p = cohort; pid = splits["test"][0]
    s = r[r.patient_id == pid].set_index("timestamp").glucose_mg_dl; cut = s.index[0] + pd.Timedelta(days=5)
    db = tmp_path / "t.sqlite"
    e1 = TwinEngine(TwinStore(db), tiny_model)
    e1.register_patient(pid, profile_of(p, pid), {}, "SYNTHETIC", s[s.index < cut])
    feed(e1, pid, s[s.index >= cut], 5); a = e1.get_state(pid); e1.store.close()
    e2 = TwinEngine(TwinStore(db), tiny_model); b = e2.get_state(pid)
    for k in ("clock_ts", "last_value", "n_observations", "status", "baseline"): assert a[k] == b[k], k
    assert a["latest_forecast"]["values"] == b["latest_forecast"]["values"]
    assert len(e2.store.get_forecasts(pid)) >= 2 and len(e2.store.get_audit(pid)) > 3


def test_previous_forecasts_and_revision_inspectable(loaded):
    eng, pid, stream = loaded; feed(eng, pid, stream, 4)
    f = eng.store.get_forecasts(pid, 10); assert len(f) >= 3 and all(x["model_version"] == eng.model.version for x in f)
    rev = eng.get_state(pid)["latest_forecast"]["explanation"]["revision_vs_previous"]
    assert rev["common_times"] and all(abs(c["revision"] - (c["current"] - c["previous"])) < 1e-6 for c in rev["common_times"])


def test_core_flow_works_offline(loaded, monkeypatch):   # DT-014
    eng, pid, stream = loaded
    def boom(*a, **k): raise AssertionError("network access attempted")
    monkeypatch.setattr(socket.socket, "connect", boom)
    st = feed(eng, pid, stream, 4); assert st["latest_forecast"] is not None and eng.scenario(pid, 10)["available"]
