"""SQLite persistence for twin state, observations, quarantined input, forecasts and the audit trail."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients(patient_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
  source_label TEXT NOT NULL, created_at TEXT NOT NULL, state_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT NOT NULL, ts_utc TEXT NOT NULL,
  ts_raw TEXT, value REAL NOT NULL, source TEXT NOT NULL, ingested_at TEXT NOT NULL, UNIQUE(patient_id, ts_utc));
CREATE TABLE IF NOT EXISTS quarantine(id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT NOT NULL, ts_raw TEXT, value_raw TEXT,
  status TEXT NOT NULL, reason TEXT NOT NULL, received_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS forecasts(id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT NOT NULL, generated_at TEXT NOT NULL,
  as_of_ts TEXT NOT NULL, model_version TEXT NOT NULL, horizons_min TEXT NOT NULL, values_json TEXT NOT NULL, lower_json TEXT,
  upper_json TEXT, interval_nominal REAL, status TEXT NOT NULL, explanation_json TEXT, inputs_json TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT, logged_at TEXT NOT NULL, twin_clock TEXT,
  event_type TEXT NOT NULL, detail_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_obs ON observations(patient_id, ts_utc);
"""


def _j(o) -> str:
    return json.dumps(o, default=lambda x: float(x) if isinstance(x, (np.floating, np.integer)) else str(x))


def _now() -> str:
    return pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


class TwinStore:
    def __init__(self, path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    @contextmanager
    def tx(self):
        try:
            yield self.db
            self.db.commit()
        except Exception:
            self.db.rollback(); raise

    def close(self): self.db.close()

    # ---- patients --------------------------------------------------------------------------
    def patient_ids(self) -> List[str]:
        return [r[0] for r in self.db.execute("SELECT patient_id FROM patients ORDER BY patient_id")]

    def has_patient(self, pid) -> bool:
        return self.db.execute("SELECT 1 FROM patients WHERE patient_id=?", (pid,)).fetchone() is not None

    def put_patient(self, pid, profile, provenance, source_label, state):
        with self.tx() as d:
            d.execute("INSERT OR REPLACE INTO patients VALUES(?,?,?,?,?,?)",
                      (pid, _j(profile), _j(provenance), source_label, _now(), _j(state)))

    def get_patient(self, pid) -> Optional[Dict]:
        r = self.db.execute("SELECT * FROM patients WHERE patient_id=?", (pid,)).fetchone()
        if r is None: return None
        return {"patient_id": r["patient_id"], "profile": json.loads(r["profile_json"]), "provenance": json.loads(r["provenance_json"]),
                "source_label": r["source_label"], "created_at": r["created_at"], "state": json.loads(r["state_json"])}

    def set_state(self, pid, state):
        with self.tx() as d:
            d.execute("UPDATE patients SET state_json=? WHERE patient_id=?", (_j(state), pid))

    # ---- observations ------------------------------------------------------------------------
    def put_observation(self, pid, ts_utc: pd.Timestamp, ts_raw: str, value: float, source: str):
        with self.tx() as d:
            d.execute("INSERT INTO observations(patient_id,ts_utc,ts_raw,value,source,ingested_at) VALUES(?,?,?,?,?,?)",
                      (pid, ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), ts_raw, float(value), source, _now()))

    def bulk_put_observations(self, pid, series: pd.Series, source: str):
        rows = [(pid, t.strftime("%Y-%m-%dT%H:%M:%SZ"), t.isoformat(), float(v), source, _now())
                for t, v in series.dropna().items()]
        with self.tx() as d:
            d.executemany("INSERT OR IGNORE INTO observations(patient_id,ts_utc,ts_raw,value,source,ingested_at) VALUES(?,?,?,?,?,?)", rows)
        return len(rows)

    def get_slot(self, pid, ts_utc: pd.Timestamp) -> Optional[float]:
        r = self.db.execute("SELECT value FROM observations WHERE patient_id=? AND ts_utc=?",
                            (pid, ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))).fetchone()
        return None if r is None else float(r[0])

    def get_series(self, pid, until: Optional[pd.Timestamp] = None, since: Optional[pd.Timestamp] = None, limit_last: Optional[int] = None) -> pd.Series:
        q, a = "SELECT ts_utc, value FROM observations WHERE patient_id=?", [pid]
        if until is not None: q += " AND ts_utc<=?"; a.append(until.strftime("%Y-%m-%dT%H:%M:%SZ"))
        if since is not None: q += " AND ts_utc>=?"; a.append(since.strftime("%Y-%m-%dT%H:%M:%SZ"))
        if limit_last: q = f"SELECT * FROM ({q} ORDER BY ts_utc DESC LIMIT {int(limit_last)}) ORDER BY ts_utc"
        else: q += " ORDER BY ts_utc"
        rows = self.db.execute(q, a).fetchall()
        idx = pd.DatetimeIndex([pd.Timestamp(r[0]) for r in rows], tz="UTC") if rows else pd.DatetimeIndex([], tz="UTC")
        return pd.Series([r[1] for r in rows], index=idx, dtype=float)

    def first_obs_ts(self, pid) -> Optional[pd.Timestamp]:
        r = self.db.execute("SELECT MIN(ts_utc) FROM observations WHERE patient_id=?", (pid,)).fetchone()
        return None if r[0] is None else pd.Timestamp(r[0])

    def count_observations(self, pid) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM observations WHERE patient_id=?", (pid,)).fetchone()[0])

    # ---- quarantine / forecasts / audit -------------------------------------------------------
    def add_quarantine(self, pid, ts_raw, value_raw, status, reason, received_at):
        with self.tx() as d:
            d.execute("INSERT INTO quarantine(patient_id,ts_raw,value_raw,status,reason,received_at) VALUES(?,?,?,?,?,?)",
                      (pid, str(ts_raw), str(value_raw), status, reason, str(received_at)))

    def get_quarantine(self, pid, limit=50) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM quarantine WHERE patient_id=? ORDER BY id DESC LIMIT ?", self.db, params=(pid, limit))

    def add_forecast(self, pid, as_of, model_version, horizons, values, lower, upper, nominal, status, explanation, inputs) -> int:
        with self.tx() as d:
            c = d.execute("INSERT INTO forecasts(patient_id,generated_at,as_of_ts,model_version,horizons_min,values_json,lower_json,upper_json,"
                          "interval_nominal,status,explanation_json,inputs_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                          (pid, _now(), as_of.strftime("%Y-%m-%dT%H:%M:%SZ"), model_version, _j(horizons), _j(values), _j(lower), _j(upper),
                           nominal, status, _j(explanation), _j(inputs)))
            return int(c.lastrowid)

    @staticmethod
    def _fc(r) -> Dict:
        return {"id": r["id"], "patient_id": r["patient_id"], "generated_at": r["generated_at"], "as_of_ts": r["as_of_ts"],
                "model_version": r["model_version"], "horizons_min": json.loads(r["horizons_min"]), "values": json.loads(r["values_json"]),
                "lower": json.loads(r["lower_json"]) if r["lower_json"] else None, "upper": json.loads(r["upper_json"]) if r["upper_json"] else None,
                "interval_nominal": r["interval_nominal"], "status": r["status"],
                "explanation": json.loads(r["explanation_json"]) if r["explanation_json"] else None,
                "inputs": json.loads(r["inputs_json"]) if r["inputs_json"] else None}

    def get_forecast(self, fid) -> Optional[Dict]:
        r = self.db.execute("SELECT * FROM forecasts WHERE id=?", (fid,)).fetchone()
        return None if r is None else self._fc(r)

    def get_forecasts(self, pid, limit=20) -> List[Dict]:
        return [self._fc(r) for r in self.db.execute("SELECT * FROM forecasts WHERE patient_id=? ORDER BY id DESC LIMIT ?", (pid, limit))]

    def add_audit(self, pid, event_type, detail, twin_clock=None):
        with self.tx() as d:
            d.execute("INSERT INTO audit(patient_id,logged_at,twin_clock,event_type,detail_json) VALUES(?,?,?,?,?)",
                      (pid, _now(), None if twin_clock is None else str(twin_clock), event_type, _j(detail)))

    def get_audit(self, pid, limit=200) -> pd.DataFrame:
        df = pd.read_sql_query("SELECT id, logged_at, twin_clock, event_type, detail_json FROM audit WHERE patient_id=? ORDER BY id DESC LIMIT ?",
                               self.db, params=(pid, limit))
        return df

    # ---- meta --------------------------------------------------------------------------------
    def get_meta(self, key, default=None):
        r = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return default if r is None else r[0]

    def set_meta(self, key, value):
        with self.tx() as d:
            d.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (key, str(value)))
