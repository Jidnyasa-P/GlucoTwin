import numpy as np, pandas as pd
from glucotwin.data_quality.validation import (ACCEPTED, CONFLICT, DUPLICATE, REJECTED_TS, REJECTED_VAL, assess_input_quality, validate_observation)

NOW = pd.Timestamp("2026-01-10T12:00:00Z")


def test_valid_reading_accepted_and_snapped():           # DT-002 (unit part)
    r = validate_observation("2026-01-10T11:58:00Z", 140, NOW)
    assert r.ok and r.grid_ts == pd.Timestamp("2026-01-10T12:00:00Z") and r.value == 140.0


def test_timezone_offsets_normalised_to_utc():
    r = validate_observation("2026-01-10T17:30:00+05:30", 140, NOW)
    assert r.ts_utc == pd.Timestamp("2026-01-10T12:00:00Z")


def test_duplicate_identical_ignored():                  # DT-003
    g = pd.Timestamp("2026-01-10T12:00:00Z")
    assert validate_observation(g, 140, NOW, {g: 140.0}).status == DUPLICATE


def test_duplicate_conflict_is_deterministic_first_write_wins():   # DT-003
    g = pd.Timestamp("2026-01-10T12:00:00Z")
    outs = {validate_observation(g, 150, NOW, {g: 140.0}).status for _ in range(5)}
    assert outs == {CONFLICT}


def test_invalid_timestamps_rejected():                  # DT-004
    for bad in (None, "not a date", "2026-01-10 12:00:00", float("nan")):    # naive stamps are ambiguous -> rejected
        assert validate_observation(bad, 140, NOW).status == REJECTED_TS, bad
    assert validate_observation("2026-01-10T15:00:00Z", 140, NOW).status == REJECTED_TS   # future


def test_invalid_values_rejected():                      # DT-004
    for bad in (float("nan"), float("inf"), "abc", None, True, 5, 9999, -3):
        assert validate_observation(NOW, bad, NOW).status == REJECTED_VAL, bad


def _series(minutes, vals):
    return pd.Series(vals, index=pd.DatetimeIndex([NOW - pd.Timedelta(minutes=m) for m in minutes]))


def test_quality_ok_full_window():
    q = assess_input_quality(_series([60, 45, 30, 15, 0], [1.0 * v for v in (120, 125, 130, 135, 140)]).sort_index(), NOW)
    assert q.status == "ok" and q.window_complete and q.forecast_allowed


def test_missing_readings_flagged():                     # DT-005
    q = assess_input_quality(_series([60, 30, 15, 0], [120, 130, 135, 140]).sort_index(), NOW)
    assert q.status == "withheld_insufficient" and q.n_missing_in_window == 1 and not q.forecast_allowed


def test_stale_stream_flagged():                         # DT-006
    s = _series([105, 90, 75, 60, 45], [120, 125, 130, 135, 140]).sort_index()
    q = assess_input_quality(s, NOW)
    assert q.status == "withheld_stale" and "stale" in q.reasons[0]


def test_no_data():
    assert assess_input_quality(pd.Series(dtype=float, index=pd.DatetimeIndex([], tz="UTC")), NOW).status == "withheld_no_data"
