"""Demo wiring: load the SYNTHETIC sample patients and REPLAY a held-out stream into the twin.
The replay is a recorded synthetic stream - there is no live-device connection anywhere in this project."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ..ingestion.loaders import PROFILE_FIELDS, load_profiles, load_readings
from .engine import TwinEngine
from .store import TwinStore

REPLAY_START_DAY = 10          # first 10 days are loaded as history; days 10-14 are replayed
DEFAULT_SAMPLE_DIR = Path(__file__).resolve().parents[2] / "data" / "sample_synthetic"
DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "runtime" / "glucotwin.sqlite"


def load_sample(sample_dir=DEFAULT_SAMPLE_DIR):
    d = Path(sample_dir)
    return load_readings(d / "readings.csv"), load_profiles(d / "profiles.csv")


def init_demo(engine: TwinEngine, sample_dir=DEFAULT_SAMPLE_DIR, start_day: int = REPLAY_START_DAY) -> list:
    readings, profiles = load_sample(sample_dir)
    done = []
    for pid, d in readings.groupby("patient_id"):
        s = d.set_index("timestamp")["glucose_mg_dl"].sort_index()
        cut = s.index[0] + pd.Timedelta(days=start_day)
        row = profiles[profiles.patient_id == pid].iloc[0]
        label = str(row["source"])
        profile = {k: (row[k].item() if hasattr(row[k], "item") else row[k]) for k in PROFILE_FIELDS if k in row.index}
        prov = {k: f"{label} (generated; not a real patient)" if label == "SYNTHETIC" else f"{label}" for k in profile}
        engine.register_patient(pid, profile, prov, label, history=s[s.index < cut], history_source=f"{label}:history")
        engine.store.set_meta(f"replay_cursor:{pid}", 0)
        done.append(pid)
    return done


class Replayer:
    """Feeds the recorded (held-out) synthetic stream into the twin one 15-min slot at a time."""
    def __init__(self, engine: TwinEngine, readings: pd.DataFrame, start_day: int = REPLAY_START_DAY):
        self.engine, self.start_day = engine, start_day
        self.streams = {}
        for pid, d in readings.groupby("patient_id"):
            s = d.sort_values("timestamp").reset_index(drop=True)
            self.streams[pid] = s[s.timestamp >= s.timestamp.iloc[0] + pd.Timedelta(days=start_day)].reset_index(drop=True)

    def remaining(self, pid) -> int:
        return len(self.streams[pid]) - int(self.engine.store.get_meta(f"replay_cursor:{pid}", 0))

    def step(self, pid, n: int = 1) -> Optional[dict]:
        state = None
        for _ in range(n):
            cur = int(self.engine.store.get_meta(f"replay_cursor:{pid}", 0))
            if cur >= len(self.streams[pid]): break
            row = self.streams[pid].iloc[cur]
            self.engine.store.set_meta(f"replay_cursor:{pid}", cur + 1)
            if np.isnan(row.glucose_mg_dl):
                state = self.engine.tick(pid, row.timestamp)             # recorded sensor gap: no packet arrives
            else:
                state = self.engine.process_observation(pid, row.timestamp, row.glucose_mg_dl, "replay:SYNTHETIC", received_at=row.timestamp)
        return state

    def truth(self, pid, since: pd.Timestamp, until: pd.Timestamp) -> pd.Series:
        """Recorded future values - used ONLY to draw 'what actually happened' next to old forecasts, never as model input."""
        s = self.streams[pid]; m = (s.timestamp > since) & (s.timestamp <= until)
        return s[m].set_index("timestamp")["glucose_mg_dl"].dropna()
