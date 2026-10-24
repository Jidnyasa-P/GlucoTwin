"""Observation validation + input-quality assessment.  Deterministic, explicit, and logged.

Per-observation policy
  * naive / unparseable / missing timestamp ........... REJECTED   (quarantined with reason)
  * timestamp > receipt time + tolerance (future) ..... REJECTED
  * non-numeric / NaN / inf / bool value .............. REJECTED
  * value outside plausible CGM range ................. REJECTED
  * same grid slot, identical value ................... DUPLICATE_IGNORED
  * same grid slot, different value ................... CONFLICT_QUARANTINED  (first write wins; deterministic)
Nothing is silently imputed: missing readings stay missing and are surfaced in the quality report.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Mapping, Optional

import numpy as np
import pandas as pd

from ..config import (FUTURE_TOLERANCE_MIN, GLUCOSE_VALID_RANGE, SAMPLING_MIN, STALE_AFTER_MIN, WINDOW_POINTS)
from ..timeutils import TimeLike, parse_timestamp, snap_to_grid

ACCEPTED = "accepted"
DUPLICATE = "duplicate_ignored"
CONFLICT = "conflict_quarantined"
REJECTED_TS = "rejected_invalid_timestamp"
REJECTED_VAL = "rejected_invalid_value"


@dataclass
class ValidationResult:
    status: str
    reason: str = ""
    ts_utc: Optional[pd.Timestamp] = None      # raw (UTC) timestamp
    grid_ts: Optional[pd.Timestamp] = None     # snapped to the sampling grid
    value: Optional[float] = None

    @property
    def ok(self) -> bool:
        return self.status == ACCEPTED


def validate_observation(ts: TimeLike, value, received_at: TimeLike,
                         existing: Optional[Mapping[pd.Timestamp, float]] = None) -> ValidationResult:
    recv, why = parse_timestamp(received_at)
    if recv is None:
        raise ValueError(f"received_at must be a tz-aware time: {why}")
    t, why = parse_timestamp(ts)
    if t is None:
        return ValidationResult(REJECTED_TS, why)
    if t > recv + pd.Timedelta(minutes=FUTURE_TOLERANCE_MIN):
        return ValidationResult(REJECTED_TS, f"timestamp is {(t - recv).total_seconds() / 60:.0f} min in the future", ts_utc=t)

    if isinstance(value, (bool, np.bool_)) or value is None:
        return ValidationResult(REJECTED_VAL, f"value not numeric: {value!r}", ts_utc=t)
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ValidationResult(REJECTED_VAL, f"value not numeric: {value!r}", ts_utc=t)
    if not np.isfinite(v):
        return ValidationResult(REJECTED_VAL, "value is NaN or infinite", ts_utc=t)
    lo, hi = GLUCOSE_VALID_RANGE
    if not lo <= v <= hi:
        return ValidationResult(REJECTED_VAL, f"{v:g} mg/dL outside plausible CGM range [{lo:g}, {hi:g}]", ts_utc=t)

    g = snap_to_grid(t)
    if existing is not None and g in existing:
        if abs(existing[g] - v) < 1e-9:
            return ValidationResult(DUPLICATE, "identical reading already stored for this slot", t, g, v)
        return ValidationResult(CONFLICT, f"slot already holds {existing[g]:g}; first write wins, {v:g} quarantined", t, g, v)
    return ValidationResult(ACCEPTED, "", t, g, v)


@dataclass
class QualityReport:
    status: str                      # ok | withheld_no_data | withheld_stale | withheld_insufficient
    reasons: List[str] = field(default_factory=list)
    last_obs_ts: Optional[pd.Timestamp] = None
    minutes_since_last: Optional[float] = None
    window_complete: bool = False
    n_missing_in_window: int = WINDOW_POINTS
    missing_fraction_24h: Optional[float] = None

    @property
    def forecast_allowed(self) -> bool:
        return self.status == "ok"


def assess_input_quality(series: pd.Series, clock: TimeLike) -> QualityReport:
    """`series`: valid readings indexed by tz-aware grid timestamps (UTC). `clock`: the twin's 'now'."""
    now, why = parse_timestamp(clock)
    if now is None:
        raise ValueError(why)
    s = series[series.index <= now].dropna() if len(series) else series
    if len(s) == 0:
        return QualityReport("withheld_no_data", ["no valid readings stored for this patient"])
    last = s.index.max()
    age = (now - last).total_seconds() / 60.0
    day = s[s.index > now - pd.Timedelta(hours=24)]
    miss24 = 1.0 - min(1.0, len(day) / (24 * 60 / SAMPLING_MIN))
    rep = QualityReport("ok", last_obs_ts=last, minutes_since_last=age, missing_fraction_24h=miss24)
    if age > STALE_AFTER_MIN:
        rep.status = "withheld_stale"
        rep.reasons.append(f"newest reading is {age:.0f} min old (limit {STALE_AFTER_MIN} min): stream stale")
        return rep
    expected = [last - pd.Timedelta(minutes=SAMPLING_MIN * k) for k in range(WINDOW_POINTS)]
    missing = [t for t in expected if t not in s.index]
    rep.n_missing_in_window = len(missing)
    rep.window_complete = not missing
    if missing:
        rep.status = "withheld_insufficient"
        rep.reasons.append(f"{len(missing)} of the last {WINDOW_POINTS} expected readings are missing "
                           f"(required: all, no imputation)")
    return rep
