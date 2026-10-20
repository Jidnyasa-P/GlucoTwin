"""Train a demonstration next-step model and save a portable joblib artifact."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import joblib,pandas as pd
from glucotwin.data import generate_glucose_series
from glucotwin.features import build_supervised,FEATURES
from sklearn.ensemble import HistGradientBoostingRegressor
root=Path(__file__).resolve().parents[1]
frames=[generate_glucose_series(f'TRAIN-{i:03d}',n=600,seed=500+i) for i in range(20)]
profiles={f'TRAIN-{i:03d}':{'age_years':30+(i*7)%45,'diabetes_duration_years':1+(i*3)%20,'hba1c_percent':6.0+(i%10)*.22} for i in range(20)}
sup=build_supervised(pd.concat(frames,ignore_index=True),horizon_steps=1,profiles=profiles)
model=HistGradientBoostingRegressor(max_iter=120,learning_rate=.07,max_leaf_nodes=15,l2_regularization=2.0,random_state=42).fit(sup[FEATURES],sup.target)
(root/'models').mkdir(exist_ok=True)
joblib.dump({'model':model,'features':FEATURES,'version':'synthetic-hgb-next-step-v1'},root/'models/glucotwin_demo.joblib')
print(f'Saved demonstration model; training windows={len(sup)}; synthetic only.')
