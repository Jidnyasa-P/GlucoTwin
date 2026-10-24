#!/usr/bin/env python
"""Render illustrative figures from REAL engine outputs on the SYNTHETIC demo patient (matplotlib; used in docs/deck).
These are renders of the same data the dashboard shows - they are not browser screenshots."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, pandas as pd
from glucotwin.config import HORIZONS_MIN, LOCAL_TZ
from glucotwin.digital_twin.demo import Replayer, init_demo, load_sample
from glucotwin.digital_twin.engine import TwinEngine
from glucotwin.digital_twin.store import TwinStore
from glucotwin.forecasting.models import GlucoModel

out = Path("docs/figures"); out.mkdir(parents=True, exist_ok=True)
eng = TwinEngine(TwinStore(str(Path(tempfile.mkdtemp()) / "f.sqlite")), GlucoModel.load("models/glucotwin_model.joblib"))
init_demo(eng); rp = Replayer(eng, load_sample()[0]); pid = "SYNTH-001"
rp.step(pid, 30)                                       # advance replay 7.5 h into the held-out stream
st = eng.get_state(pid); fc = st["latest_forecast"]
loc = lambda t: pd.DatetimeIndex(pd.to_datetime(t, utc=True)).tz_convert(LOCAL_TZ)
def banner(ax): ax.figure.text(0.01, 0.01, "SYNTHETIC patient - research prototype, not clinically validated", fontsize=8, color="#a00")

# 1. forecast with interval + recorded truth
fig, ax = plt.subplots(figsize=(9, 4.2))
rec = pd.Series([v for _, v in st["recent"]], index=loc([t for t, _ in st["recent"]])).iloc[-24:]
t0 = pd.Timestamp(fc["as_of_ts"]); xs = loc([t0] + [t0 + pd.Timedelta(minutes=h) for h in HORIZONS_MIN]); g0 = fc["inputs"]["window_mg_dl"][-1]
truth = rp.truth(pid, t0, t0 + pd.Timedelta(minutes=120))
ax.plot(rec.index, rec.values, "o-", color="#1f77b4", ms=3, label="Observed (CGM)")
ax.fill_between(xs, [g0] + fc["lower"], [g0] + fc["upper"], color="#d62728", alpha=.15, label="80% prediction interval")
ax.plot(xs, [g0] + fc["values"], "D--", color="#d62728", ms=4, label="Forecast (model, not observed)")
ax.plot(loc(truth.index), truth.values, ":", color="#777", marker="o", ms=3, label="Recorded later values (replay only; never a model input)")
ax.axvline(xs[0], color="#555", ls=":"); ax.axhline(180, color="#aaa", ls=":", lw=1); ax.axhline(70, color="#aaa", ls=":", lw=1)
ax.set(ylabel="Glucose (mg/dL)", xlabel="Time (IST)", title=f"{pid}: observed glucose and 0-120 min forecast"); ax.legend(fontsize=7, loc="lower left"); banner(ax)
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(out / "demo_forecast.png", dpi=160); plt.close(fig)

# 2. explanation
ex = fc["explanation"]["horizons"]["60"]; items = ex["contributions"][:8][::-1]
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.barh([f"{i['label']} = {i['value']:.1f}" for i in items], [i["contribution"] for i in items], color=["#d62728" if i["contribution"] > 0 else "#1f77b4" for i in items])
ax.axvline(0, color="k", lw=.8); ax.set(xlabel="mg/dL contribution to predicted change at +60 min", title=f"Why this forecast? (base {ex['base_value']:+.1f}, total {ex['predicted_change']:+.1f} mg/dL; additive, model-faithful)"); banner(ax)
ax.title.set_fontsize(9); fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(out / "demo_explanation.png", dpi=160); plt.close(fig)

# 3. scenario
sc = eng.scenario(pid, 30, "latest")
fig, ax = plt.subplots(figsize=(8, 3.8)); x = HORIZONS_MIN
for k, c, n in (("base", "#d62728", "Original forecast"), ("scenario", "#7b3fb0", "HYPOTHETICAL: latest reading +30 mg/dL")):
    ax.fill_between(x, sc[k]["lower"], sc[k]["upper"], color=c, alpha=.12); ax.plot(x, sc[k]["values"], "o--", color=c, label=n)
ax.set(xlabel="horizon (min)", ylabel="mg/dL", title="Scenario lab: model-based hypothetical input (NOT a treatment effect)"); ax.legend(fontsize=8); banner(ax)
ax.title.set_fontsize(9); fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(out / "demo_scenario.png", dpi=160); plt.close(fig)

# 4. stale -> withheld
stale = eng.tick(pid, pd.Timestamp(st["clock_ts"]) + pd.Timedelta(minutes=45))
fig, ax = plt.subplots(figsize=(8, 3.2)); ax.axis("off")
ax.text(0.5, 0.62, "FORECAST WITHHELD", ha="center", fontsize=22, color="#a00", weight="bold")
ax.text(0.5, 0.35, stale["reasons"][0], ha="center", fontsize=11); ax.text(0.5, 0.15, "No false precision: stale or incomplete input is never imputed.", ha="center", fontsize=9, color="#555")
fig.savefig(out / "demo_withheld.png", dpi=160); plt.close(fig)
print("figures written:", sorted(p.name for p in out.glob("demo_*.png")), "| status after stop:", stale["status"])
