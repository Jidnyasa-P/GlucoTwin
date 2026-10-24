"""Explicit timezone handling. Everything internal is tz-aware UTC; local time is for features/display only."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple, Union

import numpy as np
import pandas as pd

from .config import LOCAL_TZ, SAMPLING_MIN

TimeLike = Union[str, datetime, pd.Timestamp]


def parse_timestamp(ts: TimeLike) -> Tuple[Optional[pd.Timestamp], str]:
    """Parse to tz-aware UTC. Naive or unparseable stamps are rejected (ambiguous), never guessed."""
    if ts is None or (isinstance(ts, float) and np.isnan(ts)):
        return None, "timestamp missing"
    try:
        t = pd.Timestamp(ts)
    except Exception:
        return None, f"timestamp not parseable: {ts!r}"
    if pd.isna(t):
        return None, "timestamp missing"
    if t.tzinfo is None:
        return None, "timestamp has no timezone offset (ambiguous); supply ISO-8601 with offset, e.g. +05:30 or Z"
    return t.tz_convert("UTC"), ""


def snap_to_grid(t: pd.Timestamp, step_min: int = SAMPLING_MIN) -> pd.Timestamp:
    """Round to the nearest sampling-grid time (device clocks jitter by a few minutes)."""
    return t.round(f"{step_min}min")


_active_tz = LOCAL_TZ


def set_local_tz(tz: str) -> None:
    """Time-of-day features must use the zone in which the data were recorded (e.g. Asia/Shanghai for ShanghaiT2DM)."""
    global _active_tz
    _active_tz = tz


def get_local_tz() -> str:
    return _active_tz


def local_minutes_of_day(ts: pd.Series | pd.DatetimeIndex | pd.Timestamp):
    """Minutes since local midnight in the data's local zone - used for time-of-day features only."""
    if isinstance(ts, pd.Timestamp):
        loc = ts.tz_convert(_active_tz)
        return loc.hour * 60 + loc.minute
    idx = pd.DatetimeIndex(ts)
    loc = idx.tz_convert(_active_tz)
    return (loc.hour * 60 + loc.minute).to_numpy().astype(float)


def to_local_str(t: pd.Timestamp) -> str:
    return t.tz_convert(LOCAL_TZ).strftime("%Y-%m-%d %H:%M IST")


def iso(t: pd.Timestamp) -> str:
    return t.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
