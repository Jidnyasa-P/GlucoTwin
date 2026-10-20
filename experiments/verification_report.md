# Verification report

Executed in the supplied container on 20 October 2026. Results below reflect this environment, not a claim that every target OS or UI environment has been tested.

- `python scripts/generate_synthetic_data.py`: PASS — generated 1 synthetic profile and 288 synthetic glucose observations.
- `pytest -q`: PASS — 8 tests passed in 0.80 seconds on the final run.
- `python scripts/evaluate.py`: PASS — generated benchmark JSON and Markdown. The final run used 18 synthetic training patients, 6 held-out synthetic patients, 10,494 training windows and 3,498 test windows.
- `python -m compileall -q src app scripts`: PASS — Python source files compile.
- `python scripts/replay_stream.py`: PASS on an earlier run — accepted a new timestamped synthetic reading and updated the twin state. Its summary uses wall-clock age, so the deliberately historical demo timeline is marked stale when compared with current time; the dashboard offers a simulated-clock stale-stream test.
- Dashboard execution: NOT RUN in this container because Streamlit was not installed in the runtime. It is listed in `requirements.txt`; install dependencies and use the README command to run it locally. Syntax compilation passed, but this is not equivalent to an interactive UI smoke test.
- Clean virtual-environment installation: NOT VERIFIED in this container.
- Real-data evaluation and clinical validation: NOT PERFORMED.

## Final synthetic benchmark

| Model | Test windows | MAE (mg/dL) | RMSE (mg/dL) | R² |
|---|---:|---:|---:|---:|
| Persistence baseline | 3,498 | 9.468 | 12.304 | 0.4340 |
| HistGradientBoostingRegressor | 3,498 | 7.003 | 8.975 | 0.6988 |

Target: synthetic glucose 30 minutes after the end of the 60-minute input window. Both models use the same held-out windows. Entire synthetic patient IDs are held out from training. Static synthetic profile fields (age, diabetes duration, HbA1c) are model inputs, but their incremental value is not separately ablated. The synthetic generator is not a physiological simulator; these metrics are not clinical evidence.
