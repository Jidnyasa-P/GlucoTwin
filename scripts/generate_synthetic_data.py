#!/usr/bin/env python
"""Generate the SYNTHETIC cohort used for training/evaluation.  python scripts/generate_synthetic_data.py"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from glucotwin.config import GLOBAL_SEED
from glucotwin.synthetic.generator import generate_cohort

p = argparse.ArgumentParser()
p.add_argument("--out", default="data/generated")
p.add_argument("--n-patients", type=int, default=100)
p.add_argument("--days", type=int, default=14)
p.add_argument("--seed", type=int, default=GLOBAL_SEED)
p.add_argument("--sample-out", default="data/sample_synthetic", help="also write the 3 demo patients here (committed to git)")
a = p.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
r, pr = generate_cohort(a.n_patients, a.days, a.seed)
r.to_csv(out / "readings.csv.gz", index=False)
pr.to_csv(out / "profiles.csv", index=False)
print(f"[SYNTHETIC] wrote {len(r):,} rows, {r.patient_id.nunique()} patients, "
      f"{r.glucose_mg_dl.isna().mean():.2%} missing glucose -> {out}")

from glucotwin.evaluation.protocol import DEMO_PATIENTS
if a.sample_out:
    so = Path(a.sample_out); so.mkdir(parents=True, exist_ok=True)
    r[r.patient_id.isin(DEMO_PATIENTS)].to_csv(so / "readings.csv", index=False)
    pr[pr.patient_id.isin(DEMO_PATIENTS)].to_csv(so / "profiles.csv", index=False)
    print(f"[SYNTHETIC] wrote demo sample ({len(DEMO_PATIENTS)} patients) -> {so}")
