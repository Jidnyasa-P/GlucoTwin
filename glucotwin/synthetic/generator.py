"""Synthetic type-2-diabetes-like CGM cohort.  EVERYTHING produced here is SYNTHETIC.

Purpose: a reproducible, openly shareable stand-in for data that cannot be redistributed or reached
from every environment. It exercises the pipeline (ingestion, quality checks, twin, forecasting).

What this generator is NOT: a validated physiological simulator. Glucose = per-patient baseline +
meal-driven excursions (gamma-shaped absorption) + dawn bump + autocorrelated noise + sensor noise.
Static-profile -> dynamics links (e.g. prior HbA1c reflecting baseline glucose) exist BY CONSTRUCTION,
so any model gain attributed to them on this data is an artifact of the generator, not a finding.
Meal timing is fixed-schedule-with-jitter BY CONSTRUCTION, so time-of-day features help here for
that reason only.  Wearable columns (steps, heart rate) are generated INDEPENDENTLY of glucose.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import GLOBAL_SEED, SAMPLING_MIN

GENERATOR_VERSION = "synthetic-generator-v1"
SOURCE_LABEL = "SYNTHETIC"
START_UTC = pd.Timestamp("2026-01-04T18:30:00Z")  # = 2026-01-05 00:00 IST (local midnight)
INTERNAL_STEP_MIN = 5

_MEDS = ["metformin", "metformin + DPP-4 inhibitor", "metformin + sulfonylurea", "lifestyle management only"]


def _kernel(shape=3.0, scale=25.0, length_min=360):
    t = np.arange(0, length_min, INTERNAL_STEP_MIN, dtype=float)
    k = t ** (shape - 1) * np.exp(-t / scale)
    return k / k.max()


def _simulate_patient(rng: np.random.Generator, days: int):
    n = days * 24 * 60 // INTERNAL_STEP_MIN
    base = float(np.clip(rng.normal(130, 22), 90, 200))          # fasting-level baseline (mg/dL)
    gain = float(np.clip(rng.lognormal(np.log(1.6), 0.3), 0.7, 3.2))   # mg/dL per gram carbohydrate (peak)
    carb_scale = float(np.clip(rng.normal(1.0, 0.18), 0.6, 1.5))
    dawn = float(np.clip(rng.normal(8, 3), 0, 18))
    noise_sd = float(np.clip(rng.normal(7, 1.5), 3, 12))
    meal_plan = [(7.5, 45, 12), (13.0, 70, 18), (19.75, 65, 18)]
    snack = rng.random() < 0.5
    if snack:
        meal_plan.append((16.5, 25, 8))
    shift_h = rng.normal(0, 0.5)  # patient-specific schedule offset (hours)

    impulses = np.zeros(n)
    for d in range(days):
        for hour, carbs, sd in meal_plan:
            if rng.random() < 0.05:   # skipped meal
                continue
            t_h = d * 24 + hour + shift_h + rng.normal(0, 0.6)
            idx = int(round(t_h * 60 / INTERNAL_STEP_MIN))
            if 0 <= idx < n:
                impulses[idx] += max(5.0, rng.normal(carbs, sd) * carb_scale)
    exc = np.convolve(impulses, _kernel())[:n] * gain

    hours = (np.arange(n) * INTERNAL_STEP_MIN / 60.0) % 24
    dawn_curve = dawn * np.exp(-(((hours - 6.0) / 1.6) ** 2))

    phi = np.exp(-INTERNAL_STEP_MIN / 90.0)
    eps = rng.normal(0, 1, n)
    ou = np.zeros(n)
    for k in range(1, n):
        ou[k] = phi * ou[k - 1] + noise_sd * np.sqrt(1 - phi ** 2) * eps[k]

    g = base + exc + dawn_curve + ou
    return np.clip(g, 45, 420), base, gain


def generate_cohort(n_patients: int = 100, days: int = 14, seed: int = GLOBAL_SEED):
    """Return (readings_df, profiles_df).  readings: patient_id, timestamp(UTC), glucose_mg_dl,
    steps, heart_rate_bpm, source.  Missing sensor readings are ABSENT rows' NaN glucose values."""
    master = np.random.default_rng(seed)
    step = SAMPLING_MIN // INTERNAL_STEP_MIN
    rows, profiles = [], []
    for i in range(1, n_patients + 1):
        pid = f"SYNTH-{i:03d}"
        rng = np.random.default_rng(master.integers(0, 2**32 - 1))
        g5, base, gain = _simulate_patient(rng, days)
        g = g5[::step] + rng.normal(0, 3.5, len(g5[::step]))      # CGM sensor noise
        g = np.round(np.clip(g, 40, 400))
        n = len(g)
        # missingness: isolated missing readings + a few dropout episodes (synthetic sensor gaps)
        miss = rng.random(n) < 0.015
        for _ in range(rng.poisson(1.5)):
            s = rng.integers(0, n - 30); L = rng.integers(2, 25)
            miss[s:s + L] = True
        g = g.astype(float); g[miss] = np.nan

        ts = START_UTC + pd.to_timedelta(np.arange(n) * SAMPLING_MIN, unit="min")
        hrs = ((np.arange(n) * SAMPLING_MIN / 60.0) % 24)
        daytime = ((hrs > 7) & (hrs < 21)).astype(float)
        steps = np.maximum(0, rng.normal(180 * daytime, 120 * daytime + 5)).round()   # independent of glucose
        hr = np.round(rng.normal(68, 4) + 0.04 * steps + rng.normal(0, 2.5, n))        # independent of glucose
        rows.append(pd.DataFrame({"patient_id": pid, "timestamp": ts, "glucose_mg_dl": g,
                                  "steps": steps, "heart_rate_bpm": hr, "source": SOURCE_LABEL}))

        age = float(np.clip(rng.normal(56, 10), 30, 82))
        bmi = float(np.clip(rng.normal(27.5, 4), 18.5, 42))
        dur = float(np.clip(rng.gamma(2.0, 3.0), 0.5, 30))
        eag = base + 30 + rng.normal(0, 10)                  # prior lab, drawn BEFORE the monitoring window
        profiles.append({
            "patient_id": pid, "age_years": round(age), "sex": rng.choice(["F", "M"]),
            "bmi": round(bmi, 1), "diabetes_years": round(dur, 1),
            "hba1c_prior_pct": round((eag + 46.7) / 28.7, 1),
            "diagnosis": "Type 2 diabetes mellitus (SYNTHETIC record)",
            "medications": str(rng.choice(_MEDS)),
            "source": SOURCE_LABEL, "generator": GENERATOR_VERSION,
        })
    readings = pd.concat(rows, ignore_index=True)
    return readings, pd.DataFrame(profiles)
