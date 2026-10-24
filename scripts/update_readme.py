#!/usr/bin/env python
"""Regenerate the README results block from experiments/results.json (so README numbers can never drift)."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def block() -> str:
    R = json.loads((ROOT / "experiments/results.json").read_text()); P = "lgbm_" + R["primary_variant"]; ph = R["per_horizon"]
    cov = R["intervals"]["per_horizon"]; hs = ["15", "30", "45", "60", "90", "120"]
    L = ["| Horizon (min) | Persistence MAE | Ridge MAE | LightGBM CGM-only MAE | **Primary** (`%s`) MAE | 80%% interval coverage |" % R["primary_variant"], "|---|---|---|---|---|---|"]
    for h in hs:
        L.append(f"| {h} | {ph['persistence'][h]['mae']:.2f} | {ph['ridge_cgm'][h]['mae']:.2f} | {ph['lgbm_cgm'][h]['mae']:.2f} | **{ph[P][h]['mae']:.2f}** | {cov[h]['coverage']:.3f} |")
    b = R["bootstrap_primary_vs_persistence"]["60"]; a = R["abstention"]; e = R["event_task"]["models"][P]
    L += ["", f"MAE in mg/dL on **{R['split_patients']['test']} held-out SYNTHETIC test patients**, {R['test_origin_counts']['complete_input_windows']:,} scored windows, identical cases for all models. "
          f"Data source(s): {', '.join(R['data_sources'])}; data fingerprint `{R['data_md5']}`; model `{R['model_version']}`.", "",
          f"- Primary vs persistence at +60 min: {b['mae_diff']:+.2f} mg/dL (95% patient-bootstrap CI {b['ci95_low']:+.2f} to {b['ci95_high']:+.2f}); better for {R['patient_level']['n_primary_better_than_persistence_mean_mae']} of {R['patient_level']['n_patients']} patients.",
          f"- Abstention (incomplete 60-min window): {a['abstention_rate_among_observed']:.1%} of observed origins; out-of-distribution qualified: {a['qualified_rate_among_issued']:.2%}.",
          f"- Hyperglycaemia-onset event task (>{180} mg/dL within 2 h): primary F1 {e['f1']:.3f} (precision {e['precision']:.3f}, recall {e['recall']:.3f}); persistence recall 0 by construction.",
          "- Full tables, ablations, per-patient results and failure analysis: [`experiments/benchmark_report.md`](experiments/benchmark_report.md)."]
    return "\n".join(L)

START, END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"
def render(readme: str) -> str:
    return re.sub(re.escape(START) + r".*?" + re.escape(END), START + "\n" + block() + "\n" + END, readme, flags=re.S)

if __name__ == "__main__":
    p = ROOT / "README.md"; p.write_text(render(p.read_text())); print("README results block updated")
