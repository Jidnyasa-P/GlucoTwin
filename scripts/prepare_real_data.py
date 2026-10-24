#!/usr/bin/env python
"""Convert a LOCAL copy of ShanghaiT2DM into GlucoTwin's cohort format (UNVERIFIED adapter; see module docstring).

    python scripts/prepare_real_data.py --raw-dir /path/to/ShanghaiT2DM --out data/real_prepared
    python scripts/train.py    --data data/real_prepared --out models_real
    python scripts/evaluate.py --data data/real_prepared --models models_real
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from glucotwin.ingestion.shanghai import DEFAULT_TZ, prepare_shanghai
ap = argparse.ArgumentParser(); ap.add_argument("--raw-dir", required=True); ap.add_argument("--out", default="data/real_prepared")
ap.add_argument("--tz", default=DEFAULT_TZ, help="time zone of the recorded clock (ASSUMED Asia/Shanghai)"); a = ap.parse_args()
summary = prepare_shanghai(a.raw_dir, a.out, a.tz)
print(json.dumps(summary, indent=2, default=str))
print("\nVERIFY: patient count (expect ~100), reading count (paper reports 112,475 CGM points), units and time zone above.\n"
      "Do NOT redistribute the prepared files; licence terms were not verified.")
