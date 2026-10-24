# Research notes (what was checked, what could not be)

Compiled while building the project (Oct 2026). Items are marked **verified** (read in a source during this work), **partly verified**
(seen only through search snippets or secondary coverage), or **not verified**. Please re-check anything you cite.

## Challenge
* Digital Twin Challenge 2026 (Happiest Health) is listed on Unstop. Search snippets indicated an Sept 18 - Nov 20, 2026 window and a summit showcase on 20 Nov (**partly verified**). The page is JavaScript-rendered and its full rules text **could not be read**; `GlucoTwin_Digital_Twin_Challenge_2026_Complete_Specification.md` was therefore used as the requirements source. Re-confirm dates, file rules and eligibility on the official page.
* The spec lists the deliverables: public repo, team/college details, demo video (>= 20 min), licence, architecture diagram and presentation (PDF/PPT).

## Existing public entries (same challenge)
* A repository titled **GlucoTwin_Dr_Ambedkar_Institute_of_Technology** already exists on GitHub (**verified exists; claims not audited**). **Name conflict** with this project: consider renaming before submission (the name is a single constant, `PROJECT_NAME` in `glucotwin/config.py`, plus docs).
* A repository titled **ThaliTwin** (IIIT Delhi team) describes an EHR + wearable twin predicting type 2 glucose spikes 2 h ahead (**verified exists; claims not audited**).
This project's code was written independently and does not reuse theirs.

## Datasets
* **DiaTrend** (Prioleau et al., Scientific Data 2023): type 1 diabetes; access via Synapse with a data-use agreement and no redistribution (**partly verified**). Not usable for a public repo or for type 2 claims.
* **ShanghaiT2DM / ShanghaiT1DM** (Zhao et al., Scientific Data 2023, "Chinese diabetes datasets for data-driven machine learning"): open datasets with 15-min CGM and clinical summaries; the T2DM set has 100 patients (**partly verified**). **Licence unclear**: the Glucose-ML survey (arXiv 2507.14077) reports these figshare releases carry no explicit licence, while another public repo states CC BY 4.0 (**conflict, unresolved**). figshare was unreachable from the build sandbox, so no real file was opened.
* **Glucose-ML** (arXiv 2507.14077): a collection/survey of longitudinal diabetes datasets (**partly verified**).

## Literature touched
* Katsoulakis et al., "Digital twins for health: a scoping review", npj Digital Medicine 2024 (**verified exists**; details not summarised here).
* Scoping review of human digital twins in healthcare (PMC12484800) (**verified exists**).
* CGM forecasting: GARNN (arXiv 2402.16230) and a Bayesian T2DM forecasting paper (arXiv 2409.07315) (**titles verified; methods and results not reviewed**).
* India burden: ICMR-INDIAB (Anjana et al., Lancet Diabetes Endocrinol 2023, DOI 10.1016/S2213-8587(23)00119-5): ~101 million with diabetes (11.4%), ~136 million with prediabetes (15.3%), 113,043 participants, 2008-2020 (**partly verified** via secondary coverage and a Natl Med J India commentary).

## Gaps this project addresses (design goals, not claims about others' work)
Leakage-resistant patient-level evaluation against simple baselines; explicit abstention on stale/incomplete input; model-faithful explanations with causal caveats; what-if functionality limited to inputs the model actually has.

## Technical findings from the build
* Persistence is a strong short-horizon baseline; the learned model's edge is largest at long horizons *on this synthetic data*, and most of that edge comes from time-of-day (an artifact of scheduled synthetic meals).
* Personalization from a 48 h baseline gave a tiny gain at +15 min only (-0.26 mg/dL, 95% CI excludes zero) and none from +30 min; static EHR fields gave no reliable gain at any horizon (bootstrap CIs include zero).
* Split-conformal intervals reach about nominal coverage on average but individual patients range roughly 71-85% at nominal 80%.
