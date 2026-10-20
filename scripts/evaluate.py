from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np,pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from glucotwin.data import generate_glucose_series
from glucotwin.features import build_supervised,FEATURES
from glucotwin.evaluation import regression_metrics

# Fixed patient-level holdout; no patient's windows cross partitions.
root=Path(__file__).resolve().parents[1]
train_ids=[f'SYNTH-{i:03d}' for i in range(18)]
test_ids=[f'SYNTH-{i:03d}' for i in range(18,24)]
frames=[generate_glucose_series(pid,n=600,seed=100+i) for i,pid in enumerate(train_ids+test_ids)]
all_data=pd.concat(frames,ignore_index=True)
profiles={pid:{"age_years":30+(i*7)%45,"diabetes_duration_years":1+(i*3)%20,"hba1c_percent":6.0+(i%10)*0.22} for i,pid in enumerate(train_ids+test_ids)}
# Train and test windows are generated separately, preserving patient boundaries.
train=build_supervised(all_data[all_data.patient_id.isin(train_ids)],horizon_steps=6,profiles=profiles)
test=build_supervised(all_data[all_data.patient_id.isin(test_ids)],horizon_steps=6,profiles=profiles)
model=HistGradientBoostingRegressor(max_iter=120,learning_rate=.07,max_leaf_nodes=15,l2_regularization=2.0,random_state=42)
model.fit(train[FEATURES],train.target)
pred=model.predict(test[FEATURES]); persistence=test[[f'lag_{i}' for i in range(1,13)]].lag_1.to_numpy()
report={"title":"GlucoTwin synthetic-data benchmark","data_status":"SYNTHETIC ONLY — not clinical evidence","seed":100,"split":{"strategy":"patient-separated holdout","train_patients":len(train_ids),"test_patients":len(test_ids),"train_windows":len(train),"test_windows":len(test),"horizon_minutes":30,"sampling_minutes":5},"features":FEATURES,"static_ehr_features_used":["age_years","diabetes_duration_years","hba1c_percent"],"models":{"persistence_last_value":regression_metrics(test.target,persistence),"hist_gradient_boosting":regression_metrics(test.target,pred)},"caveats":["Synthetic generator is not a physiological simulator.","Patient separation prevents patient overlap but synthetic patients share a generator family.","No real CGM data were downloaded or evaluated.","Metrics do not establish clinical utility or generalization."]}
(root/'experiments').mkdir(exist_ok=True)
(root/'experiments/benchmark_report.json').write_text(json.dumps(report,indent=2))
lines=['# Benchmark report','', '**Data status: SYNTHETIC ONLY — not clinical evidence.**','',f"- Split: {len(train_ids)} train patients / {len(test_ids)} held-out patients",f"- Windows: {len(train)} train / {len(test)} test",'- Sampling: 5 minutes','- Target: glucose 30 minutes after the end of the input window','', '| Model | n | MAE (mg/dL) | RMSE (mg/dL) | R² |','|---|---:|---:|---:|---:|']
for name,m in report['models'].items(): lines.append(f"| {name} | {m['n']} | {m['mae_mg_dl']} | {m['rmse_mg_dl']} | {m['r2']} |")
lines+=['','## Interpretation','', 'These are measured results on generated synthetic sequences only. They are not clinical evidence. The benchmark uses the same held-out windows for both models and holds out entire synthetic patient IDs. The generator creates structured trends and meal-like pulses; its patterns may make performance easier or harder than real CGM. Do not use these values to make treatment decisions.','']
(root/'experiments/benchmark_report.md').write_text('\n'.join(lines))
print('\n'.join(lines))
