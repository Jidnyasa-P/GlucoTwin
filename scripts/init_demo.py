#!/usr/bin/env python
"""(Re)create the demo database from data/sample_synthetic.   python scripts/init_demo.py [--db PATH] [--reset]"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from glucotwin.digital_twin.demo import DEFAULT_DB, init_demo
from glucotwin.digital_twin.engine import TwinEngine
from glucotwin.digital_twin.store import TwinStore
from glucotwin.forecasting.models import GlucoModel

ap = argparse.ArgumentParser(); ap.add_argument("--db", default=str(DEFAULT_DB)); ap.add_argument("--model", default="models/glucotwin_model.joblib")
ap.add_argument("--reset", action="store_true"); a = ap.parse_args()
if a.reset and Path(a.db).exists(): Path(a.db).unlink()
model = GlucoModel.load(a.model) if Path(a.model).exists() else None
ids = init_demo(TwinEngine(TwinStore(a.db), model))
print(f"initialised {len(ids)} SYNTHETIC demo patients in {a.db}: {ids}; model={model.version if model else 'NONE'}")
