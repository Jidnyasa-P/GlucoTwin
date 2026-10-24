#!/usr/bin/env python
"""Draw the architecture diagram -> docs/architecture.pdf (+ .png)."""
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

fig, ax = plt.subplots(figsize=(16, 9)); ax.set_xlim(0, 160); ax.set_ylim(0, 90); ax.axis("off")
C = {"src": "#dbeafe", "dq": "#fee2e2", "twin": "#dcfce7", "ml": "#fef3c7", "ui": "#ede9fe", "ev": "#e5e7eb"}
def box(x, y, w, h, title, body, c):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.5", fc=C[c], ec="#334155", lw=1.2))
    ax.text(x + w / 2, y + h - 2.2, title, ha="center", va="top", fontsize=10.5, weight="bold", color="#0f172a")
    ax.text(x + w / 2, y + h - 6.2, body, ha="center", va="top", fontsize=8, color="#1e293b", linespacing=1.35)
def arrow(x1, y1, x2, y2, label=None):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color="#334155", lw=1.5))
    if label: ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 1.5, label, ha="center", fontsize=7.5, color="#334155", style="italic")
ax.text(80, 87, "GlucoTwin - system architecture (research proof of concept)", ha="center", fontsize=15, weight="bold")
ax.text(80, 83.6, "Every demo patient and result is SYNTHETIC unless labelled otherwise. Not clinically validated. Not a medical device.", ha="center", fontsize=9, color="#b91c1c")

box(3, 56, 30, 22, "1  Data sources", "Static EHR / history profile\n(age, BMI, diabetes duration,\nprior HbA1c, medications)\n\nDynamic CGM stream, 15-min\n(SYNTHETIC cohort; replay)\nOptional: ShanghaiT2DM adapter\n(local only, unverified)", "src")
box(40, 56, 30, 22, "2  Ingestion + data quality", "tz-aware UTC, snap to 15-min grid\nreject: naive/future time, NaN,\nout-of-range values\nduplicate: ignore / quarantine\n(first write wins)\nstale + missing-window detection", "dq")
box(77, 56, 36, 22, "3  Virtual patient state (twin)", "SQLite: profile + provenance,\nobservations, quarantine,\nforecast history, audit trail\nDerived state: latest value, trend,\npersonal baseline (first 48 h),\nquality status, twin clock", "twin")
box(120, 56, 37, 22, "4  Forecasting + uncertainty", "Features: last 60 min only (no future)\nLightGBM per horizon (15-120 min)\nSplit-conformal 80% intervals\nOOD flag; abstain if stale/incomplete\nBaselines: persistence, ridge", "ml")
box(77, 27, 36, 22, "5  Explainability", "Exact additive LightGBM contributions\n(verified: sum = model output)\nRevision vs previous forecast\nData-quality effect notes\nAssociation, NOT causation", "ml")
box(120, 27, 37, 22, "6  What-if (scenario lab)", "Supported: hypothetical recent\nglucose input, model re-run\nLabelled HYPOTHETICAL\nDisabled: meals, exercise, drugs\n(no learned relationship)", "ml")
box(3, 27, 67, 22, "7  Clinician-facing dashboard (Streamlit)", "Patient overview | Forecast + interval | Explanation | Scenario lab |\nData quality + audit | Model performance (from experiments/results.json)\nControlled tests: stop stream, corrupted / duplicate / future / no-timezone input\nEmpty state, withheld-forecast state, SYNTHETIC badge, disclaimer on every page", "ui")
box(3, 3, 154, 18, "8  Evaluation + safety layer (offline)", "Patient-disjoint split 60/10/10/20 | 48 h per-patient calibration period never scored | variant chosen on val_select only (parsimony rule) | intervals calibrated on val_calibrate\n"
    "Test patients read only by scripts/evaluate.py, which scores persistence, ridge and LightGBM on IDENTICAL cases; patient-bootstrap CIs; ablations; abstention; failure analysis\n54 automated tests (leakage, quality, restart, offline, explanation additivity, reproducibility, dashboard)", "ev")
arrow(33, 67, 40, 67); arrow(70, 67, 77, 67); arrow(113, 67, 120, 67, None); arrow(138, 56, 138, 49); arrow(113, 62, 113, 62)
arrow(120, 60, 113, 60); arrow(95, 56, 95, 49); arrow(77, 36, 70, 36); arrow(120, 36, 113, 36); arrow(95, 27, 95, 21, None)
ax.text(116.5, 69.5, "features", ha="center", fontsize=7, style="italic"); ax.text(116.5, 57.6, "forecast", ha="center", fontsize=7, style="italic")
Path("docs").mkdir(exist_ok=True)
fig.savefig("docs/architecture.pdf", bbox_inches="tight"); fig.savefig("docs/architecture.png", dpi=150, bbox_inches="tight")
print("ok")
