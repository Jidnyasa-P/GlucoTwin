from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import pandas as pd
from glucotwin.data import generate_glucose_series,SYNTHETIC_PATIENT
root=Path(__file__).resolve().parents[1]
(root/'data/sample_synthetic').mkdir(parents=True,exist_ok=True)
pd.DataFrame([SYNTHETIC_PATIENT]).to_csv(root/'data/sample_synthetic/patient_profile.csv',index=False)
generate_glucose_series(n=288,seed=7).to_csv(root/'data/sample_synthetic/glucose_observations.csv',index=False)
print('Generated 1 synthetic profile and 288 synthetic glucose observations.')
