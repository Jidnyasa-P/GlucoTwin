#!/usr/bin/env python
"""Replay the recorded SYNTHETIC stream into the twin and print each state/forecast update.

    python scripts/replay_stream.py --patient SYNTH-001 --steps 12
    python scripts/replay_stream.py --patient SYNTH-001 --steps 12 --stop-after 6   # stream stops: stale warning
"""
import argparse, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from glucotwin.digital_twin.demo import Replayer, init_demo, load_sample
from glucotwin.digital_twin.engine import TwinEngine
from glucotwin.digital_twin.store import TwinStore
from glucotwin.forecasting.models import GlucoModel

ap = argparse.ArgumentParser()
ap.add_argument("--patient", default="SYNTH-001"); ap.add_argument("--steps", type=int, default=12)
ap.add_argument("--stop-after", type=int, default=None, help="stop feeding data after N steps, then advance the clock 60 min")
ap.add_argument("--model", default="models/glucotwin_model.joblib"); ap.add_argument("--db", default=None, help="default: temp DB")
a = ap.parse_args()
db = a.db or str(Path(tempfile.mkdtemp()) / "replay.sqlite")
eng = TwinEngine(TwinStore(db), GlucoModel.load(a.model))
init_demo(eng); rp = Replayer(eng, load_sample()[0])
print("[SYNTHETIC replay - not a live device]  patient", a.patient)
print(f"{'twin clock (UTC)':20s} {'status':30s} {'latest':>7s} {'+60min fc':>10s} {'80% interval':>16s}  fc#")
def show(st):
    f = st["latest_forecast"]
    fc = f"{f['values'][3]:10.1f} [{f['lower'][3]:6.1f},{f['upper'][3]:6.1f}]" if f else f"{'withheld':>10s} {'':>16s}"
    print(f"{st['clock_ts']:20s} {st['status']:30s} {st['last_value'] or float('nan'):7.1f} {fc}  {f['id'] if f else '-'}")
show(eng.get_state(a.patient))
for i in range(a.steps):
    if a.stop_after is not None and i >= a.stop_after: break
    show(rp.step(a.patient))
if a.stop_after is not None:
    st = eng.tick(a.patient, pd.Timestamp(eng.get_state(a.patient)["clock_ts"]) + pd.Timedelta(minutes=60)); show(st); print("reason:", st["reasons"])
