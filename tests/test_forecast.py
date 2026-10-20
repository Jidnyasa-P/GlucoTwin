import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import pandas as pd
from glucotwin.data import generate_glucose_series
from glucotwin.features import build_supervised,FEATURES
from glucotwin.forecast import GlucoseForecaster
from sklearn.ensemble import HistGradientBoostingRegressor

def test_forecast_structure_and_explanation():
    frames=[generate_glucose_series(f'T{i}',n=80,seed=i) for i in range(3)]
    sup=build_supervised(pd.concat(frames,ignore_index=True),horizon_steps=1)
    model=GlucoseForecaster(HistGradientBoostingRegressor(max_iter=10,random_state=1)).fit(sup,sup.target)
    f=model.predict(frames[0].glucose_mg_dl.tail(12),frames[0].timestamp.max(),horizon_steps=6)
    assert len(f.values_mg_dl)==6 and len(f.timestamps)==6
    assert len(f.lower_mg_dl)==len(f.upper_mg_dl)==6
    assert f.model_version and f.explanation

def test_untrained_model_fails_explicitly():
    model=GlucoseForecaster()
    try: model.predict([100]*12,pd.Timestamp.now(tz='UTC'),horizon_steps=1)
    except RuntimeError as e: assert 'trained' in str(e)
    else: assert False
