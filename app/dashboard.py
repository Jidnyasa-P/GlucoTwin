"""GlucoTwin clinician-facing dashboard (Streamlit).   Run:  streamlit run app/dashboard.py

RESEARCH PROTOTYPE. SYNTHETIC patients. Not clinically validated. Not for diagnosis, treatment or medication decisions.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

import pandas as pd
import streamlit as st

from charts import context_figure, contribution_figure, forecast_figure, scenario_figure
from glucotwin.config import DISCLAIMER, HORIZONS_MIN, LOCAL_TZ, PROJECT_NAME, STALE_AFTER_MIN, UNIT
from glucotwin.digital_twin.demo import DEFAULT_DB, DEFAULT_SAMPLE_DIR, Replayer, init_demo, load_sample
from glucotwin.digital_twin.engine import SCENARIO_LABEL, TwinEngine
from glucotwin.digital_twin.store import TwinStore
from glucotwin.forecasting.models import GlucoModel
from glucotwin.timeutils import iso, to_local_str

DB_PATH = os.environ.get("GLUCOTWIN_DB", str(DEFAULT_DB))
MODEL_PATH = os.environ.get("GLUCOTWIN_MODEL", str(ROOT / "models" / "glucotwin_model.joblib"))
SAMPLE_DIR = os.environ.get("GLUCOTWIN_SAMPLE", str(DEFAULT_SAMPLE_DIR))

st.set_page_config(page_title=f"{PROJECT_NAME} - research prototype", layout="wide", page_icon="🩺")


@st.cache_resource
def get_engine(db_path: str, model_path: str):
    model = GlucoModel.load(model_path) if Path(model_path).exists() else None
    return TwinEngine(TwinStore(db_path), model)


@st.cache_data
def get_sample(sample_dir: str):
    try:
        return load_sample(sample_dir)
    except Exception:
        return None, None


engine = get_engine(DB_PATH, MODEL_PATH)
sample = get_sample(SAMPLE_DIR)
replayer = Replayer(engine, sample[0]) if sample[0] is not None else None

STATUS_STYLE = {"ok": ("success", "Forecast available"), "qualified_out_of_distribution": ("warning", "Forecast qualified: input outside training range"),
                "withheld_stale": ("error", "Forecast WITHHELD: stream stale"), "withheld_insufficient": ("error", "Forecast WITHHELD: insufficient input"),
                "withheld_no_data": ("error", "Forecast WITHHELD: no data"), "withheld_no_model": ("error", "Forecast WITHHELD: no model"),
                "withheld_insufficient_context": ("error", "Forecast WITHHELD: missing context")}


def badge(status: str):
    kind, text = STATUS_STYLE.get(status, ("info", status))
    getattr(st, kind)(f"**{text}**")


# ----------------------------------------------------------------------------------------------- header
st.title(f"🩺 {PROJECT_NAME}: an explainable, personalized glucose Digital Twin")
st.warning("**Research prototype - SYNTHETIC patients - not clinically validated.** " + DISCLAIMER)

# ----------------------------------------------------------------------------------------------- empty state
patients = engine.store.patient_ids()
if not patients:
    st.info("No saved patient found. This is the empty state: the twin has no data yet.")
    if sample[0] is None:
        st.error(f"Sample data not found in `{SAMPLE_DIR}`. Run `python scripts/generate_synthetic_data.py`.")
    elif st.button("Initialise SYNTHETIC demo patients", type="primary"):
        init_demo(engine, SAMPLE_DIR); st.rerun()
    st.stop()

# ----------------------------------------------------------------------------------------------- sidebar
pid = st.sidebar.selectbox("Patient (SYNTHETIC)", patients, index=0)
state = engine.get_state(pid)
st.sidebar.caption(f"Twin clock: {to_local_str(pd.Timestamp(state['clock_ts']))}" if state["clock_ts"] else "Twin clock: not started")
if engine.model is None:
    st.sidebar.error("No trained model loaded: forecasts are withheld. Run `python scripts/train.py`.")
else:
    st.sidebar.caption(f"Model: `{engine.model.version}`")

if replayer is not None and pid in replayer.streams:
    st.sidebar.subheader("Replay recorded SYNTHETIC stream")
    st.sidebar.caption(f"{replayer.remaining(pid)} recorded 15-min slots remaining. Not a live device.")
    c1, c2 = st.sidebar.columns(2)
    if c1.button("▶ +15 min"): replayer.step(pid, 1); st.rerun()
    if c2.button("⏩ +1 h"): replayer.step(pid, 4); st.rerun()

st.sidebar.subheader("Controlled data-quality tests")
clock = pd.Timestamp(state["clock_ts"]) if state["clock_ts"] else None
if clock is not None:
    if st.sidebar.button("⏸ Stop stream (advance clock +30 min, no data)"): engine.tick(pid, clock + pd.Timedelta(minutes=30)); st.rerun()
    if st.sidebar.button("☠ Inject corrupted value (9999 mg/dL)"):
        engine.process_observation(pid, clock + pd.Timedelta(minutes=15), 9999, "injected_test", received_at=clock + pd.Timedelta(minutes=15)); st.rerun()
    if st.sidebar.button("⏭ Inject future-dated reading (+3 h)"):
        engine.process_observation(pid, clock + pd.Timedelta(hours=3), 150, "injected_test", received_at=clock); st.rerun()
    if st.sidebar.button("🕓 Inject reading without timezone"):
        engine.process_observation(pid, "2026-01-14 20:00:00", 150, "injected_test", received_at=clock); st.rerun()
    if state["last_obs_ts"] and st.sidebar.button("♊ Inject conflicting duplicate of latest slot"):
        engine.process_observation(pid, state["last_obs_ts"], (state["last_value"] or 100) + 25, "injected_test", received_at=clock); st.rerun()
    st.sidebar.subheader("Inject a valid manual reading")
    v = st.sidebar.number_input(f"Glucose ({UNIT}) at twin clock + 15 min", 20, 600, int(state["last_value"] or 140), 1)
    if st.sidebar.button("➕ Add reading"):
        t = clock + pd.Timedelta(minutes=15); engine.process_observation(pid, t, v, "manual_entry:demo", received_at=t); st.rerun()
if st.sidebar.button("↺ Reset demo database"):
    engine.store.db.executescript("DELETE FROM patients; DELETE FROM observations; DELETE FROM quarantine; DELETE FROM forecasts; DELETE FROM audit; DELETE FROM meta;")
    engine.store.db.commit(); init_demo(engine, SAMPLE_DIR); st.rerun()

tab_over, tab_fc, tab_exp, tab_sc, tab_qa, tab_perf = st.tabs(
    ["1 · Patient overview", "2 · Forecast", "3 · Explanation", "4 · Scenario lab", "5 · Data quality & audit", "6 · Model performance"])

fc = state["latest_forecast"]

# ----------------------------------------------------------------------------------------------- 1 overview
with tab_over:
    left, right = st.columns([1, 1])
    with left:
        st.subheader(f"{pid}  ·  source: `{state['source_label']}`")
        prof = pd.DataFrame([{"Field": k, "Value": str(v), "Provenance": state["provenance"].get(k, "")} for k, v in state["profile"].items()])
        st.dataframe(prof, hide_index=True)
        st.caption("Static/history fields feed the twin state and this display. Whether the model uses them is reported in Model performance.")
    with right:
        badge(state["status"])
        if state["reasons"]: st.write("Reasons: " + "; ".join(state["reasons"]))
        a, b, c = st.columns(3)
        a.metric(f"Latest glucose ({UNIT})", f"{state['last_value']:.0f}" if state["last_value"] is not None else "-")
        b.metric("Trend (60 min)", f"{state['trend_mgdl_per_h']:+.0f} {UNIT}/h" if state["trend_mgdl_per_h"] is not None else "n/a")
        c.metric("Observations stored", state["n_observations"])
        if state["last_obs_ts"]:
            st.write(f"Latest reading: **{to_local_str(pd.Timestamp(state['last_obs_ts']))}**  ({state['last_obs_ts']})")
            st.write(f"Twin clock: {to_local_str(pd.Timestamp(state['clock_ts']))}; minutes since last reading: "
                     f"**{state['quality']['minutes_since_last']:.0f}** (stale after {STALE_AFTER_MIN})")
        if state["baseline"]: st.write(f"Personal baseline (first 48 h): mean {state['baseline']['mean']:.0f}, SD {state['baseline']['std']:.0f} {UNIT}")
    st.plotly_chart(forecast_figure(state, hours_back=12, title="Recent observed glucose"))
    if sample[0] is not None and state["clock_ts"]:
        ctx = sample[0][(sample[0].patient_id == pid) & (sample[0].timestamp <= pd.Timestamp(state["clock_ts"]))].tail(48)
        if len(ctx) and "steps" in ctx: st.plotly_chart(context_figure(ctx))

# ----------------------------------------------------------------------------------------------- 2 forecast
with tab_fc:
    badge(state["status"])
    if fc is None:
        st.error("**No forecast is shown.** " + ("; ".join(state["reasons"]) or "Inputs are inadequate."))
        st.caption("Safe behaviour: when input is stale, incomplete, or the model is unavailable, GlucoTwin withholds the forecast instead of showing false precision.")
        history = engine.store.get_forecasts(pid, 1)
        if history: st.caption(f"Most recent earlier forecast (#{history[0]['id']}, origin {history[0]['as_of_ts']}) is superseded and not shown as current.")
    else:
        show_truth = st.checkbox("Overlay recorded later values from the replay (for verification only; never fed to the model)", False)
        truth = None
        if show_truth and replayer is not None and pid in replayer.streams:
            t0 = pd.Timestamp(fc["as_of_ts"]); truth = replayer.truth(pid, t0, t0 + pd.Timedelta(minutes=max(fc["horizons_min"])))
        st.plotly_chart(forecast_figure(state, truth=truth))
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Forecast origin", to_local_str(pd.Timestamp(fc["as_of_ts"])))
        m2.metric("Horizon", f"up to {max(fc['horizons_min'])} min")
        m3.metric("Interval", f"{fc['interval_nominal']:.0%} (split conformal)")
        m4.metric("Model version", fc["model_version"])
        st.caption(f"Generated at (wall clock): {fc['generated_at']} · forecast #{fc['id']} · unit {UNIT} · times IST (UTC+05:30)")
        t0 = pd.Timestamp(fc["as_of_ts"])
        tbl = pd.DataFrame({"Time (IST)": [(t0 + pd.Timedelta(minutes=h)).tz_convert(LOCAL_TZ).strftime("%H:%M") for h in fc["horizons_min"]],
                            "Horizon (min)": fc["horizons_min"], f"Forecast ({UNIT})": fc["values"],
                            "Interval low": fc["lower"], "Interval high": fc["upper"]})
        st.dataframe(tbl, hide_index=True)
        st.info("Intervals are marginal (calibrated across patients on synthetic validation data), constant-width per horizon, and may under-cover individual patients.")
    st.subheader("Forecast history (previous forecasts are kept)")
    hist = engine.store.get_forecasts(pid, 15)
    if hist:
        st.dataframe(pd.DataFrame([{"id": h["id"], "origin (UTC)": h["as_of_ts"], "generated (wall clock)": h["generated_at"], "model version": h["model_version"],
                                    "status": h["status"], "+60 min": h["values"][3], "+120 min": h["values"][7]} for h in hist]), hide_index=True)

# ----------------------------------------------------------------------------------------------- 3 explanation
with tab_exp:
    if fc is None or not fc.get("explanation"):
        st.error("No explanation: no forecast is currently available. " + "; ".join(state["reasons"]))
    else:
        ex = fc["explanation"]
        hz = st.radio("Horizon", [int(k) for k in ex["horizons"]], index=1, horizontal=True, format_func=lambda h: f"+{h} min")
        st.plotly_chart(contribution_figure(ex, hz))
        st.write(ex["summary"])
        st.caption(f"Method: {ex['method']}. Max additivity error for the displayed horizons: "
                   f"{max(h['additivity_error'] for h in ex['horizons'].values()):.1e} mg/dL (explanation reproduces the model output).")
        st.warning(ex["causal_note"])
        rev = ex.get("revision_vs_previous")
        st.subheader("Change since the previous forecast")
        if rev and rev["common_times"]:
            st.dataframe(pd.DataFrame([{"Time (IST)": pd.Timestamp(c["time_utc"]).tz_convert(LOCAL_TZ).strftime("%H:%M"), "Previous forecast": c["previous"],
                                        "Current forecast": c["current"], "Revision": c["revision"]} for c in rev["common_times"]]), hide_index=True)
            st.caption(f"Compared with forecast #{rev['previous_forecast_id']} (origin {rev['previous_as_of']}, model {rev['previous_model_version']}).")
        else:
            st.info("No earlier forecast with overlapping times is available yet. Advance the replay or add a reading.")
        st.subheader("Effect of data quality on this forecast")
        q = state["quality"]
        st.write(f"Window complete: **{q['window_complete']}**; missing readings in the last 60 min: **{q['n_missing_in_window']}**; "
                 f"missing in the last 24 h: **{(q['missing_fraction_24h'] or 0):.0%}**; status: **{state['status']}**. "
                 "Missing or stale input is never imputed: the forecast is withheld instead.")

# ----------------------------------------------------------------------------------------------- 4 scenario lab
with tab_sc:
    st.error("**" + SCENARIO_LABEL + "**")
    st.write("Supported control: alter the glucose values the model sees, then compare forecasts. This is an input-sensitivity check of the model.")
    cA, cB = st.columns(2)
    delta = cA.slider(f"Change in recent glucose ({UNIT})", -60, 60, 20, 5)
    scope = cB.radio("Apply to", ["latest", "window"], format_func=lambda s: "latest reading only" if s == "latest" else "all readings in the last 60 min", horizontal=True)
    with st.expander("Unsupported controls (disabled on purpose)"):
        st.number_input("Carbohydrate intake (g)", 0, 200, 0, disabled=True)
        st.number_input("Exercise (minutes)", 0, 180, 0, disabled=True)
        st.selectbox("Medication change", ["not supported"], disabled=True)
        st.caption("The model has no such inputs and no relationship was learned or validated, so these controls are disabled instead of inventing effects. "
                   "GlucoTwin never suggests medication or insulin changes.")
    sc = engine.scenario(pid, delta, scope)
    if not sc["available"]:
        st.error("Scenario unavailable: " + sc["reason"])
    else:
        st.plotly_chart(scenario_figure(sc, state))
        tb = pd.DataFrame({"Horizon (min)": sc["horizons_min"], f"Original ({UNIT})": [round(x, 1) for x in sc["base"]["values"]],
                           f"Hypothetical ({UNIT})": [round(x, 1) for x in sc["scenario"]["values"]],
                           "Difference": [round(b - a, 1) for a, b in zip(sc["base"]["values"], sc["scenario"]["values"])]})
        st.dataframe(tb, hide_index=True)
        if sc["ood_reasons"]: st.warning("Hypothetical input is outside the training range: " + "; ".join(sc["ood_reasons"]))

# ----------------------------------------------------------------------------------------------- 5 quality & audit
with tab_qa:
    q = state["quality"] or {}
    a, b, c = st.columns(3)
    a.metric("Minutes since last reading", f"{q.get('minutes_since_last', float('nan')):.0f}" if q.get("minutes_since_last") is not None else "-")
    b.metric("Missing in last 60 min", q.get("n_missing_in_window", "-"))
    c.metric("Missing in last 24 h", f"{(q.get('missing_fraction_24h') or 0):.0%}")
    badge(state["status"])
    if state["reasons"]: st.write("Why: " + "; ".join(state["reasons"]))
    st.subheader("Quarantined / rejected input")
    qd = engine.store.get_quarantine(pid)
    st.dataframe(qd[["id", "status", "reason", "ts_raw", "value_raw", "received_at"]] if len(qd) else pd.DataFrame({"info": ["nothing quarantined yet"]}), hide_index=True)
    st.subheader("Audit trail (newest first)")
    au = engine.store.get_audit(pid)
    if len(au):
        au["detail"] = au["detail_json"].apply(lambda s: json.dumps(json.loads(s))[:240])
        st.dataframe(au[["id", "logged_at", "twin_clock", "event_type", "detail"]], hide_index=True)

# ----------------------------------------------------------------------------------------------- 6 performance
with tab_perf:
    rp = ROOT / "experiments" / "results.json"
    if not rp.exists():
        st.info("No evaluation results found. Run `python scripts/train.py` then `python scripts/evaluate.py`.")
    else:
        R = json.loads(rp.read_text())
        st.error(R["WARNING"] + f"  Data source(s): {', '.join(R['data_sources'])}.")
        st.write(f"Model `{R['model_version']}` · primary variant `{R['primary_variant']}` · test patients: {R['split_patients']['test']} (held out) · "
                 f"patient-disjoint split, 48 h per-patient calibration period excluded from scoring.")
        rows = []
        for hm in map(str, HORIZONS_MIN):
            ph = R["per_horizon"]
            rows.append({"Horizon (min)": int(hm), "Persistence MAE": ph["persistence"][hm]["mae"], "Ridge MAE": ph["ridge_cgm"][hm]["mae"],
                         "Primary MAE": ph[f"lgbm_{R['primary_variant']}"][hm]["mae"], "Interval coverage": R["intervals"]["per_horizon"][hm]["coverage"]})
        st.dataframe(pd.DataFrame(rows).round(3), hide_index=True)
        st.caption(f"MAE in {UNIT}; nominal interval coverage {R['intervals']['nominal']:.0%}. Full tables, CIs, ablations and failure analysis: experiments/benchmark_report.md")
        ab = R["abstention"]
        st.write(f"Abstention (incomplete input window): **{ab['abstention_rate_among_observed']:.1%}** of observed origins; out-of-distribution qualification: {ab['qualified_rate_among_issued']:.2%}.")
        st.warning("Synthetic-data results measure recovery of the synthetic generator, not clinical performance. The time-of-day gain is expected by construction "
                   "(scheduled synthetic meals). No clinical validation; type 1/type 2 generalisation is not claimed.")
