import os, pytest
from streamlit.testing.v1 import AppTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_app(tmp_path, monkeypatch, init=True):
    monkeypatch.setenv("GLUCOTWIN_DB", str(tmp_path / f"{'a' if init else 'b'}.sqlite"))
    at = AppTest.from_file(os.path.join(ROOT, "app/dashboard.py"), default_timeout=90).run()
    if init:
        [b for b in at.button if "Initialise" in b.label][0].click().run()
    return at


def texts(at): return " ".join([m.value for m in at.markdown] + [w.value for w in at.warning] + [e.value for e in at.error] + [s.value for s in at.success] + [i.value for i in at.info])


def btn(at, key): return [b for b in at.sidebar.button if key in b.label][0]


def test_empty_state_does_not_crash(tmp_path, monkeypatch):            # DT-012
    at = run_app(tmp_path, monkeypatch, init=False)
    assert not at.exception and "No saved patient" in texts(at) and "SYNTHETIC" in texts(at)


def test_dashboard_loads_with_disclaimer_and_all_tabs(tmp_path, monkeypatch):    # DT-018
    at = run_app(tmp_path, monkeypatch)
    assert not at.exception and len(at.tabs) == 6
    t = texts(at); assert "not clinically validated" in t and "SYNTHETIC" in t and "Forecast available" in t


def test_replay_updates_state(tmp_path, monkeypatch):
    at = run_app(tmp_path, monkeypatch)
    n0 = [m.value for m in at.metric if "Observations" in m.label][0]
    btn(at, "+15 min").click().run()
    n1 = [m.value for m in at.metric if "Observations" in m.label][0]
    assert not at.exception and int(n1) >= int(n0)


def test_stale_stream_hides_forecast_in_ui(tmp_path, monkeypatch):
    at = run_app(tmp_path, monkeypatch)
    btn(at, "Stop stream").click().run()
    t = texts(at); assert not at.exception and "WITHHELD" in t and "No forecast is shown" in t and "stale" in t


def test_corrupted_input_is_quarantined_in_ui(tmp_path, monkeypatch):
    at = run_app(tmp_path, monkeypatch)
    btn(at, "corrupted").click().run()
    assert not at.exception and any("rejected_invalid_value" in str(df.value.to_dict()) for df in at.dataframe)


def test_scenario_tab_labelled_hypothetical(tmp_path, monkeypatch):
    at = run_app(tmp_path, monkeypatch); t = texts(at)
    assert "HYPOTHETICAL" in t and "Unsupported controls" in " ".join(e.label for e in at.expander)
