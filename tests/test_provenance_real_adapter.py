import numpy as np, pandas as pd, pytest
from pathlib import Path
from glucotwin.ingestion.loaders import load_readings, load_profiles
from glucotwin.ingestion.shanghai import parse_recording, prepare_shanghai

ROOT = Path(__file__).resolve().parents[1]


def test_sample_data_is_labelled_synthetic():                        # DT-017
    r = load_readings(ROOT / "data/sample_synthetic/readings.csv"); p = load_profiles(ROOT / "data/sample_synthetic/profiles.csv")
    assert set(r.source) == {"SYNTHETIC"} and set(p.source) == {"SYNTHETIC"} and all("SYNTHETIC" in d for d in p.diagnosis)


def test_observation_and_profile_provenance_in_state(loaded):         # DT-017
    eng, pid, stream = loaded
    st = eng.get_state(pid); assert st["source_label"] == "SYNTHETIC" and set(st["provenance"].values()) == {"SYNTHETIC"}
    t = stream.dropna().index[0]; eng.process_observation(pid, t, 140, "manual_entry:demo", received_at=t)
    srcs = {r[0] for r in eng.store.db.execute("SELECT DISTINCT source FROM observations")}
    assert "manual_entry:demo" in srcs


def _fixture(tmp: Path, unit="CGM (mg / dl)", n=96 * 4):
    t = pd.date_range("2021-07-30 00:03", periods=n, freq="15min")
    for name, off in (("1001_0_20210730.csv", 0), ("1001_1_20210901.csv", 5), ("1002_0_20210730.csv", 0)):
        pd.DataFrame({"Date": t + pd.Timedelta(days=off), unit: 120 + 30 * np.sin(np.arange(n) / 8), "CBG (mg / dl)": np.nan}).to_csv(tmp / name, index=False)
    pd.DataFrame({"Patient Number": ["1001_0_20210730", "1002_0_20210730"], "Age (years)": [60, 50], "Gender (Female=1, Male=2)": [1, 2],
                  "BMI (kg/m2)": [25.0, 28.0], "Duration of Diabetes (years)": [5, 10], "HbA1c (mmol/mol)": [64, 53]}).to_csv(tmp / "Shanghai_T2DM_Summary.csv", index=False)


def test_adapter_groups_recordings_per_patient(tmp_path):
    raw = tmp_path / "raw"; raw.mkdir(); _fixture(raw)
    s = prepare_shanghai(raw, tmp_path / "out")
    assert s["n_patients"] == 2 and s["n_recording_files"] == 3
    r = load_readings(tmp_path / "out/readings.csv.gz"); p = load_profiles(tmp_path / "out/profiles.csv")
    assert set(r.patient_id) == {"SHT2-1001", "SHT2-1002"} and "ShanghaiT2DM" in r.source.iloc[0]
    assert p.set_index("patient_id").loc["SHT2-1001", "hba1c_prior_pct"] == pytest.approx(8.0, abs=0.05)   # 64 mmol/mol -> ~8.0 %
    assert r.timestamp.dt.tz is not None and (tmp_path / "out/meta.json").exists()


def test_adapter_converts_mmol_and_refuses_ambiguous_units(tmp_path):
    raw = tmp_path / "r"; raw.mkdir()
    pd.DataFrame({"Date": pd.date_range("2021-01-01", periods=8, freq="15min"), "CGM (mmol / L)": [6.0] * 8}).to_csv(raw / "1_0.csv", index=False)
    s, n = parse_recording(raw / "1_0.csv"); assert s.iloc[0] == pytest.approx(6.0 * 18.016, abs=0.1)
    pd.DataFrame({"Date": pd.date_range("2021-01-01", periods=8, freq="15min"), "CGM": [6.0] * 8}).to_csv(raw / "2_0.csv", index=False)
    with pytest.raises(ValueError, match="ambiguous"): parse_recording(raw / "2_0.csv")


def test_adapter_missing_files_error(tmp_path):
    with pytest.raises(FileNotFoundError): prepare_shanghai(tmp_path, tmp_path / "o")
