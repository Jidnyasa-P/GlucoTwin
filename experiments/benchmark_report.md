# Benchmark report

**Data status: SYNTHETIC ONLY — not clinical evidence.**

- Split: 18 train patients / 6 held-out patients
- Windows: 10494 train / 3498 test
- Sampling: 5 minutes
- Target: glucose 30 minutes after the end of the input window

| Model | n | MAE (mg/dL) | RMSE (mg/dL) | R² |
|---|---:|---:|---:|---:|
| persistence_last_value | 3498 | 9.468 | 12.304 | 0.434 |
| hist_gradient_boosting | 3498 | 7.003 | 8.975 | 0.6988 |

## Interpretation

These are measured results on generated synthetic sequences only. They are not clinical evidence. The benchmark uses the same held-out windows for both models and holds out entire synthetic patient IDs. The generator creates structured trends and meal-like pulses; its patterns may make performance easier or harder than real CGM. Do not use these values to make treatment decisions.
