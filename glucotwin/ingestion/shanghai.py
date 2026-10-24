"""Adapter: ShanghaiT2DM (Zhao et al., Sci Data 2023) -> GlucoTwin's unified cohort schema.

!! STATUS: NOT VERIFIED AGAINST THE REAL FILES. The dataset host (figshare) was unreachable from the build
!! environment, so this adapter encodes ASSUMPTIONS about the published layout (per-recording CSV/XLS(X) files named
!! '<patient>_<n>_<date>.*' with a date/time column and a 'CGM' column; one summary table with a 'Patient Number'
!! column). It is tested only on a tiny fixture in that assumed layout (tests/test_real_adapter.py). Every inference it
!! makes (units, time zone, columns) is returned in the summary so a human can verify it before trusting results.
!!
!! Licence: terms of the dataset were NOT verified (sources disagree: CC BY 4.0 vs no explicit licence). Do not
!! redistribute the raw or prepared files; keep them local (data/real_prepared/ is git-ignored). Cite Zhao et al. 2023.

Leakage safeguard: all recordings of one person share one patient_id, so patient-level splits never separate them.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..config import MMOL_TO_MGDL, SAMPLING_MIN

SOURCE_LABEL = "ShanghaiT2DM (open dataset; real patients)"
DEFAULT_TZ = "Asia/Shanghai"       # ASSUMPTION: device-local clock; verify against the dataset documentation


def _read(path: Path) -> pd.DataFrame:
    suf = path.suffix.lower()
    if suf == ".csv":
        for enc in ("utf-8", "utf-8-sig", "gbk"):
            try: return pd.read_csv(path, encoding=enc)
            except UnicodeDecodeError: continue
        raise ValueError(f"cannot decode {path}")
    if suf in (".xls", ".xlsx"):
        try: return pd.read_excel(path)
        except ImportError as e: raise ImportError("reading Excel files needs: pip install openpyxl xlrd") from e
    raise ValueError(f"unsupported file type: {path}")


def _find(df: pd.DataFrame, include: List[str], exclude: Optional[List[str]] = None) -> Optional[str]:
    for c in df.columns:
        lc = str(c).lower()
        if all(k in lc for k in include) and not any(x in lc for x in (exclude or [])):
            return c
    return None


def _patient_key(path: Path) -> str:
    m = re.match(r"(\d+)", path.stem)
    if not m: raise ValueError(f"cannot derive patient id from file name {path.name!r} (expected '<digits>_...')")
    return m.group(1)


def parse_recording(path: Path, tz: str = DEFAULT_TZ) -> (pd.Series, Dict):
    df = _read(path)
    tcol = _find(df, ["date"]) or _find(df, ["time"])
    gcol = _find(df, ["cgm"], exclude=["cbg"])
    if tcol is None or gcol is None:
        raise ValueError(f"{path.name}: need a date/time column and a CGM column; found {list(df.columns)[:8]}")
    notes = {"file": path.name, "time_col": str(tcol), "cgm_col": str(gcol)}
    t = pd.to_datetime(df[tcol], errors="coerce")
    g = pd.to_numeric(df[gcol], errors="coerce")
    ok = t.notna() & g.notna()
    t, g = t[ok], g[ok]
    if g.empty: return pd.Series(dtype=float), {**notes, "n": 0}
    if "mmol" in str(gcol).lower():
        g = g * MMOL_TO_MGDL; notes["unit_inferred"] = "mmol/L (from header) -> converted to mg/dL"
    elif "mg" in str(gcol).lower():
        notes["unit_inferred"] = "mg/dL (from header)"
    elif g.median() < 35:
        raise ValueError(f"{path.name}: CGM unit ambiguous (median {g.median():.1f}, no unit in header); refusing to guess")
    else:
        notes["unit_inferred"] = "mg/dL (from magnitude; header had no unit)"
    t = t.dt.tz_localize(tz, ambiguous="NaT", nonexistent="NaT")
    keep = t.notna(); t, g = t[keep].dt.tz_convert("UTC"), g[keep]
    s = pd.Series(g.to_numpy(float), index=pd.DatetimeIndex(t).round(f"{SAMPLING_MIN}min"))
    s = s[~s.index.duplicated(keep="first")].sort_index()
    notes.update({"n": int(len(s)), "tz_assumed": tz})
    return s, notes


def _hba1c_pct(v: float, header: str) -> float:
    if not np.isfinite(v): return np.nan
    h = header.lower()
    if "mmol/mol" in h.replace(" ", "") or ("mmol" in h and "mol" in h): return round(0.0915 * v + 2.15, 1)   # IFCC -> NGSP
    if "%" in h: return round(v, 1)
    return round(0.0915 * v + 2.15, 1) if v > 20 else round(v, 1)       # unit not stated: infer from magnitude


def parse_summary(path: Path) -> (pd.DataFrame, Dict):
    df = _read(path)
    idc = _find(df, ["patient", "number"]) or _find(df, ["patient"])
    if idc is None: raise ValueError(f"{path.name}: no patient-number column")
    cols = {"age": _find(df, ["age"]), "sex": _find(df, ["gender"]) or _find(df, ["sex"]), "bmi": _find(df, ["bmi"]),
            "dur": _find(df, ["duration"]), "a1c": _find(df, ["hba1c"])}
    notes = {"summary_file": path.name, "columns_used": {k: (str(v) if v is not None else None) for k, v in cols.items()}}
    rows = []
    for _, r in df.iterrows():
        pk = re.match(r"(\d+)", str(r[idc]).strip())
        if not pk: continue
        num = lambda c: pd.to_numeric(r[c], errors="coerce") if c is not None else np.nan
        sex_raw = r[cols["sex"]] if cols["sex"] is not None else None
        sex = "F" if str(sex_raw).strip() in ("1", "1.0", "F", "Female") else "M" if str(sex_raw).strip() in ("2", "2.0", "M", "Male") else "unknown"
        rows.append({"patient_key": pk.group(1), "age_years": num(cols["age"]), "sex": sex, "bmi": num(cols["bmi"]),
                     "diabetes_years": num(cols["dur"]),
                     "hba1c_prior_pct": _hba1c_pct(float(num(cols["a1c"])), str(cols["a1c"] or "")) if cols["a1c"] else np.nan})
    return pd.DataFrame(rows), notes


def prepare_shanghai(raw_dir, out_dir, tz: str = DEFAULT_TZ) -> Dict:
    raw, out = Path(raw_dir), Path(out_dir)
    files = sorted(p for p in raw.rglob("*") if p.suffix.lower() in (".csv", ".xls", ".xlsx") and "__MACOSX" not in str(p))
    summ = [p for p in files if "summary" in p.name.lower()]
    recs = [p for p in files if p not in summ and re.match(r"\d+", p.stem)]
    if not recs: raise FileNotFoundError(f"no recording files like '<patient>_<n>_<date>.csv/.xls[x]' found under {raw}")
    by_patient: Dict[str, List[pd.Series]] = {}
    notes: List[Dict] = []
    for p in recs:
        s, n = parse_recording(p, tz); notes.append(n)
        if len(s): by_patient.setdefault(_patient_key(p), []).append(s)
    prof = pd.DataFrame()
    prof_notes = {}
    if summ:
        prof, prof_notes = parse_summary(summ[0])
    rows, profiles = [], []
    for key, parts in sorted(by_patient.items()):
        s = pd.concat(parts); s = s[~s.index.duplicated(keep="first")].sort_index()
        pid = f"SHT2-{key}"
        rows.append(pd.DataFrame({"patient_id": pid, "timestamp": s.index, "glucose_mg_dl": s.to_numpy(), "source": SOURCE_LABEL}))
        pr = prof[prof.patient_key == key].iloc[0].to_dict() if len(prof) and (prof.patient_key == key).any() else {}
        profiles.append({"patient_id": pid, "age_years": pr.get("age_years", np.nan), "sex": pr.get("sex", "unknown"),
                         "bmi": pr.get("bmi", np.nan), "diabetes_years": pr.get("diabetes_years", np.nan),
                         "hba1c_prior_pct": pr.get("hba1c_prior_pct", np.nan),
                         "diagnosis": "Type 2 diabetes mellitus (ShanghaiT2DM)", "medications": "not extracted by this adapter",
                         "source": SOURCE_LABEL})
    readings = pd.concat(rows, ignore_index=True)
    out.mkdir(parents=True, exist_ok=True)
    readings.to_csv(out / "readings.csv.gz", index=False)
    pd.DataFrame(profiles).to_csv(out / "profiles.csv", index=False)
    import json
    (out / "meta.json").write_text(json.dumps({"local_tz": tz, "source": SOURCE_LABEL, "warning": "unverified adapter; local only; do not redistribute"}, indent=2))
    return {"n_recording_files": len(recs), "n_patients": len(by_patient), "n_readings": int(len(readings)),
            "tz_assumed": tz, "per_file_notes": notes[:5], "n_file_notes": len(notes), "profile_notes": prof_notes}
