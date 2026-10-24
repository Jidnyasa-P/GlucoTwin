"""Patient-state engine: the Digital Twin update loop.

    observation -> validate -> (quarantine | append) -> recompute recent features -> quality check
                -> forecast (or withhold) -> explain -> persist state + audit

State is DERIVED from stored observations plus a small persisted status record, so it survives restarts.
Time semantics: `received_at` is when the twin received the packet. Live use defaults to the wall clock;
replay/demo passes the simulated clock explicitly so staleness is evaluated against replay time.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..config import (CALIB_HOURS, DISCLAIMER, GLUCOSE_VALID_RANGE, HORIZONS_MIN, MIN_CALIB_READINGS_FRAC, SAMPLING_MIN, WINDOW_POINTS)
from ..data_quality.validation import (ACCEPTED, DUPLICATE, QualityReport, assess_input_quality, validate_observation)
from ..explainability.contributions import explain_forecast
from ..forecasting.features import STATIC_FEATURES, compute_features, requires
from ..forecasting.models import GlucoModel
from ..timeutils import iso, local_minutes_of_day, parse_timestamp, snap_to_grid
from .store import TwinStore

SCENARIO_LABEL = ("MODEL-BASED HYPOTHETICAL INPUT. This shows how the forecasting model responds to altered recent glucose "
                  "values. It is not a prediction of any intervention's effect, not evidence of causation, and not medical advice.")


def compute_baseline(series: pd.Series) -> Optional[Dict]:
    """Personal baseline from the patient's FIRST `CALIB_HOURS` hours of data (never from scored data)."""
    if len(series) == 0: return None
    start = series.index.min()
    end = start + pd.Timedelta(hours=CALIB_HOURS)
    if series.index.max() < end - pd.Timedelta(minutes=SAMPLING_MIN): return None
    cal = series[(series.index >= start) & (series.index < end)]
    if len(cal) < MIN_CALIB_READINGS_FRAC * CALIB_HOURS * 60 / SAMPLING_MIN: return None
    return {"mean": float(cal.mean()), "std": float(cal.std(ddof=0)), "n": int(len(cal)), "start": iso(start)}


class TwinEngine:
    def __init__(self, store: TwinStore, model: Optional[GlucoModel] = None):
        self.store, self.model = store, model

    # ------------------------------------------------------------------ registration
    def register_patient(self, patient_id: str, profile: Dict, provenance: Dict, source_label: str,
                         history: Optional[pd.Series] = None, history_source: Optional[str] = None) -> Dict:
        state = {"clock_ts": None, "status": "no_data", "reasons": ["no observations yet"], "latest_forecast_id": None,
                 "baseline": None, "last_obs_ts": None, "last_value": None}
        self.store.put_patient(patient_id, profile, provenance, source_label, state)
        if history is not None and len(history):
            n = self.store.bulk_put_observations(patient_id, history, history_source or source_label)
            clock = history.dropna().index.max()
            state.update({"clock_ts": iso(clock), "baseline": compute_baseline(self.store.get_series(patient_id))})
            self.store.set_state(patient_id, state)
            self.store.add_audit(patient_id, "profile_loaded", {"n_history_observations": n, "source": source_label,
                                 "profile_fields": sorted(profile), "baseline": state["baseline"]}, clock)
            return self._refresh(patient_id, clock, new_forecast=True, cause="history_loaded")
        self.store.add_audit(patient_id, "profile_loaded", {"n_history_observations": 0, "source": source_label}, None)
        return self.get_state(patient_id)

    # ------------------------------------------------------------------ main loop
    def process_observation(self, patient_id: str, ts, value, source: str = "device",
                            received_at=None) -> Dict:
        p = self.store.get_patient(patient_id)
        if p is None: raise KeyError(f"unknown patient {patient_id}")
        recv = pd.Timestamp.now(tz="UTC").floor("s") if received_at is None else parse_timestamp(received_at)[0]
        if recv is None: raise ValueError("received_at must be tz-aware")
        t, _ = parse_timestamp(ts)
        existing = None
        if t is not None:
            g = snap_to_grid(t); cur = self.store.get_slot(patient_id, g)
            existing = {g: cur} if cur is not None else {}
        res = validate_observation(ts, value, recv, existing)
        prev_clock = p["state"].get("clock_ts")
        clock = max(pd.Timestamp(prev_clock), recv) if prev_clock else recv

        if not res.ok:
            if res.status != DUPLICATE:
                self.store.add_quarantine(patient_id, ts, value, res.status, res.reason, iso(recv))
            self.store.add_audit(patient_id, res.status, {"ts": str(ts), "value": str(value), "reason": res.reason, "source": source}, clock)
            return self._refresh(patient_id, clock, new_forecast=False, cause=res.status)

        self.store.put_observation(patient_id, res.grid_ts, res.ts_utc.isoformat(), res.value, source)
        late = res.grid_ts < (self.store.get_series(patient_id).index.max())
        self.store.add_audit(patient_id, "observation_accepted", {"ts": iso(res.grid_ts), "value": res.value, "source": source,
                             "late_arrival": bool(late)}, clock)
        st = p["state"]
        if st.get("baseline") is None:
            st["baseline"] = compute_baseline(self.store.get_series(patient_id)); self.store.set_state(patient_id, st)
        return self._refresh(patient_id, clock, new_forecast=True, cause="observation_accepted")

    def tick(self, patient_id: str, now) -> Dict:
        """Advance the twin's clock WITHOUT new data (e.g. the stream stopped). Detects staleness."""
        t, why = parse_timestamp(now)
        if t is None: raise ValueError(why)
        p = self.store.get_patient(patient_id)
        prev = p["state"].get("clock_ts")
        clock = max(pd.Timestamp(prev), t) if prev else t
        return self._refresh(patient_id, clock, new_forecast=False, cause="clock_advanced")

    # ------------------------------------------------------------------ internals
    def _window(self, patient_id: str, clock: pd.Timestamp):
        s = self.store.get_series(patient_id, until=clock, limit_last=400)
        return s, assess_input_quality(s, clock)

    def _context(self, patient_id: str, p: Dict, s: pd.Series, last: pd.Timestamp, W: np.ndarray):
        """Build the feature row for the active model variant; returns (X, missing_reasons)."""
        req = requires(self.model.variant)
        kw, miss = {}, []
        if req["tod"]: kw["tod_min"] = np.array([local_minutes_of_day(last)])
        if req["personal"]:
            b = p["state"].get("baseline")
            if b is None: miss.append(f"personal baseline unavailable (needs >= {CALIB_HOURS} h of history)")
            else: kw["base_mean"], kw["base_std"] = np.array([b["mean"]]), np.array([b["std"]])
        if req["static"]:
            try: kw["static"] = pd.DataFrame({c: [float(p["profile"][c])] for c in STATIC_FEATURES})
            except (KeyError, TypeError, ValueError): miss.append("static EHR fields required by the model are missing")
        if miss: return None, miss
        return compute_features(W[None, :], self.model.variant, **kw), []

    def _refresh(self, patient_id: str, clock: pd.Timestamp, new_forecast: bool, cause: str) -> Dict:
        p = self.store.get_patient(patient_id); st = p["state"]; prev_status = st.get("status")
        s, q = self._window(patient_id, clock)
        st.update({"clock_ts": iso(clock), "quality": self._q(q), "last_obs_ts": iso(q.last_obs_ts) if q.last_obs_ts is not None else None,
                   "last_value": float(s.iloc[-1]) if len(s) else None})
        reasons = list(q.reasons); status = q.status
        if not q.forecast_allowed:
            st["latest_forecast_id"] = None
        elif self.model is None:
            status, reasons = "withheld_no_model", ["no trained model file is loaded (run scripts/train.py)"]; st["latest_forecast_id"] = None
        elif new_forecast or st.get("latest_forecast_id") is None:
            last = q.last_obs_ts
            W = np.array([s[last - pd.Timedelta(minutes=SAMPLING_MIN * k)] for k in range(WINDOW_POINTS - 1, -1, -1)])
            X, miss = self._context(patient_id, p, s, last, W)
            if miss:
                status, reasons, st["latest_forecast_id"] = "withheld_insufficient_context", miss, None
            else:
                pred, lo, hi = self.model.predict(X)
                ood = self.model.ood_reasons(X)[0]
                status = "qualified_out_of_distribution" if ood else "ok"; reasons = ood
                prev_fc = self.store.get_forecasts(patient_id, 1)
                expl = explain_forecast(self.model, X, prev_fc[0] if prev_fc else None, last, pred[0])
                fid = self.store.add_forecast(patient_id, last, self.model.version, HORIZONS_MIN, pred[0].round(2).tolist(),
                                              None if lo is None else lo[0].round(2).tolist(), None if hi is None else hi[0].round(2).tolist(),
                                              1 - self.model.interval_alpha, status, expl,
                                              {"window_mg_dl": W.tolist(), "window_end_utc": iso(last), "twin_clock_utc": iso(clock)})
                st["latest_forecast_id"] = fid
                self.store.add_audit(patient_id, "forecast_generated", {"forecast_id": fid, "model_version": self.model.version,
                                     "status": status, "as_of": iso(last)}, clock)
        st["status"], st["reasons"] = status, reasons
        if status.startswith("withheld") and (prev_status != status):
            self.store.add_audit(patient_id, "forecast_withheld", {"status": status, "reasons": reasons, "cause": cause}, clock)
        self.store.set_state(patient_id, st)
        return self.get_state(patient_id)

    @staticmethod
    def _q(q: QualityReport) -> Dict:
        return {"status": q.status, "reasons": q.reasons, "minutes_since_last": q.minutes_since_last,
                "window_complete": q.window_complete, "n_missing_in_window": q.n_missing_in_window,
                "missing_fraction_24h": q.missing_fraction_24h}

    # ------------------------------------------------------------------ read API
    def get_state(self, patient_id: str) -> Dict:
        p = self.store.get_patient(patient_id)
        if p is None: raise KeyError(f"unknown patient {patient_id}")
        st = p["state"]
        s = self.store.get_series(patient_id, limit_last=48)
        fc = self.store.get_forecast(st["latest_forecast_id"]) if st.get("latest_forecast_id") else None
        trend = None
        if st.get("last_obs_ts") and len(s) >= WINDOW_POINTS:
            last = pd.Timestamp(st["last_obs_ts"]); idx = [last - pd.Timedelta(minutes=SAMPLING_MIN * k) for k in range(WINDOW_POINTS - 1, -1, -1)]
            if all(i in s.index for i in idx):
                w = s[idx].to_numpy(); xc = np.array([-30., -15, 0, 15, 30]); trend = float((w * xc).sum() / (xc ** 2).sum() * 60)
        return {"patient_id": patient_id, "source_label": p["source_label"], "profile": p["profile"], "provenance": p["provenance"],
                "clock_ts": st.get("clock_ts"), "status": st.get("status"), "reasons": st.get("reasons", []), "quality": st.get("quality"),
                "last_obs_ts": st.get("last_obs_ts"), "last_value": st.get("last_value"), "trend_mgdl_per_h": trend,
                "baseline": st.get("baseline"), "recent": [(iso(t), float(v)) for t, v in s.items()],
                "latest_forecast": fc, "model_version": self.model.version if self.model else None,
                "n_observations": self.store.count_observations(patient_id), "disclaimer": DISCLAIMER}

    # ------------------------------------------------------------------ what-if (hypothetical) ----
    def scenario(self, patient_id: str, delta_mgdl: float, scope: str = "latest") -> Dict:
        """Re-run the model on a hypothetically altered input. scope: 'latest' (newest reading only) or 'window' (all 5)."""
        if scope not in ("latest", "window"): raise ValueError("scope must be 'latest' or 'window'")
        p = self.store.get_patient(patient_id)
        if p is None: raise KeyError(patient_id)
        if self.model is None: return {"available": False, "reason": "no model loaded", "label": SCENARIO_LABEL}
        clock = pd.Timestamp(p["state"]["clock_ts"]); s, q = self._window(patient_id, clock)
        if not q.forecast_allowed:
            return {"available": False, "reason": "; ".join(q.reasons) or q.status, "label": SCENARIO_LABEL}
        last = q.last_obs_ts
        W = np.array([s[last - pd.Timedelta(minutes=SAMPLING_MIN * k)] for k in range(WINDOW_POINTS - 1, -1, -1)])
        W2 = W.copy()
        if scope == "latest": W2[-1] += delta_mgdl
        else: W2 += delta_mgdl
        lo_b, hi_b = GLUCOSE_VALID_RANGE
        if not ((W2 >= lo_b) & (W2 <= hi_b)).all():
            return {"available": False, "reason": f"altered input leaves the plausible range [{lo_b:g}, {hi_b:g}] mg/dL", "label": SCENARIO_LABEL}
        X1, miss = self._context(patient_id, p, s, last, W)
        if miss: return {"available": False, "reason": "; ".join(miss), "label": SCENARIO_LABEL}
        X2, _ = self._context(patient_id, p, s, last, W2)
        b = self.model.predict(X1); sc = self.model.predict(X2)
        out = {"available": True, "is_hypothetical": True, "label": SCENARIO_LABEL, "delta_mgdl": float(delta_mgdl), "scope": scope,
               "as_of": iso(last), "horizons_min": HORIZONS_MIN, "base_window": W.tolist(), "scenario_window": W2.tolist(),
               "base": {"values": b[0][0].tolist(), "lower": b[1][0].tolist(), "upper": b[2][0].tolist()},
               "scenario": {"values": sc[0][0].tolist(), "lower": sc[1][0].tolist(), "upper": sc[2][0].tolist()},
               "ood_reasons": self.model.ood_reasons(X2)[0], "model_version": self.model.version}
        self.store.add_audit(patient_id, "scenario_run", {"hypothetical": True, "delta_mgdl": delta_mgdl, "scope": scope,
                             "as_of": iso(last)}, clock)
        return out
