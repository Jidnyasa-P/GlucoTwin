import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import pandas as pd
from glucotwin.data import generate_glucose_series,SYNTHETIC_PATIENT
from glucotwin.quality import validate_observation,quality_status
from glucotwin.twin import DigitalTwin
from glucotwin.features import build_supervised,FEATURES
from glucotwin.evaluation import regression_metrics

def test_synthetic_generator_is_deterministic_and_labeled():
    a=generate_glucose_series(n=20,seed=5); b=generate_glucose_series(n=20,seed=5)
    assert a.glucose_mg_dl.equals(b.glucose_mg_dl)
    assert set(a.provenance)=={'SYNTHETIC'}

def test_valid_observation_updates_state(tmp_path):
    obs=generate_glucose_series(n=20)
    twin=DigitalTwin(SYNTHETIC_PATIENT,obs,db_path=tmp_path/'audit.jsonl')
    ts=obs.timestamp.max()+pd.Timedelta(minutes=5)
    out=twin.ingest(ts,123)
    assert out['accepted'] is True and len(twin.observations)==21
    assert twin.current_glucose==123
    assert (tmp_path/'audit.jsonl').exists()

def test_duplicate_invalid_and_out_of_order_rejected(tmp_path):
    obs=generate_glucose_series(n=20); twin=DigitalTwin(SYNTHETIC_PATIENT,obs,db_path=tmp_path/'audit.jsonl')
    assert twin.ingest(obs.timestamp.iloc[-1],123)['reason']=='duplicate_timestamp'
    assert twin.ingest(obs.timestamp.iloc[-1]+pd.Timedelta(minutes=5),999)['reason']=='glucose_out_of_supported_range'
    assert twin.ingest(obs.timestamp.iloc[-1]-pd.Timedelta(minutes=5),123)['reason']=='duplicate_timestamp'
    assert twin.ingest('not-a-date',123)['reason']=='invalid_timestamp'

def test_quality_warns_when_stale_or_insufficient():
    obs=generate_glucose_series(n=5)
    q=quality_status(obs,now=obs.timestamp.max()+pd.Timedelta(hours=1))
    assert not q['forecast_allowed'] and len(q['warnings'])>=2

def test_feature_builder_and_patient_separated_supervised_data():
    obs=pd.concat([generate_glucose_series('A',n=40),generate_glucose_series('B',n=40,seed=8)])
    sup=build_supervised(obs,horizon_steps=6)
    assert all(c in sup for c in FEATURES)
    assert set(sup.patient_id)=={'A','B'}
    assert len(sup)>0

def test_metrics_actual_values():
    m=regression_metrics([1,2,3],[1,3,3])
    assert m['n']==3 and m['mae_mg_dl']==round(1/3,3)
