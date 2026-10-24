# Submission checklist (status as of the last build)

Legend: DONE = produced and verified here; TODO = needs the team (cannot be produced or verified by the build).

## Done and verified
- [x] Runnable pipeline: synthetic data -> train -> evaluate -> twin engine -> dashboard (`make all`)
- [x] 54 automated tests passing, also in a fresh virtualenv from `requirements.txt` only
- [x] Results regenerate bit-identically from the seed (metrics, model hash, data fingerprint)
- [x] Leakage controls tested (patient-disjoint splits, calibration period, no future-dependence, train-only scaler)
- [x] Benchmark report with baselines, CIs, ablations, intervals, abstention, failure analysis (`experiments/benchmark_report.md`)
- [x] Architecture diagram PDF (`docs/architecture.pdf`) and presentation PDF + PPTX (`docs/presentation.pdf`, `.pptx`)
- [x] MIT licence + `THIRD_PARTY_NOTICES.md`; data documentation; model documentation
- [x] Demo-video plan >= 20 minutes (`docs/DEMO_VIDEO_PLAN.md`)

## TODO (team)
- [ ] **Team details, college/incubator, project title decision** - placeholders in README and slides 1 and 12
- [ ] **Project name**: another public repo is called "GlucoTwin" for this challenge; decide whether to rename
- [ ] **Create the public GitHub repository**, push, and confirm it is public in a logged-out browser
- [ ] **Record and upload the demo video (>= 20 min, unlisted)**; test the link in incognito; paste into README and slide 12
- [ ] **Real browser screenshots** of the dashboard into `docs/demo_screenshots/` (the build had no browser; `docs/figures/demo_*.png` are matplotlib renders of the same engine outputs, not screenshots) and into slides 8 and 10
- [ ] **Re-read the official challenge page** (it could not be read here): confirm dates, file rules, eligibility, video length
- [ ] **Real-data run** (optional but valuable): ShanghaiT2DM via `scripts/prepare_real_data.py`; verify the licence first; the adapter is untested on real files; report real results separately
- [ ] Clinician review of wording/limitations before making any usefulness claim
- [ ] Team leader's name, phone, email and repo link on the submission platform
- [ ] Confirm all linked files/links are publicly accessible (README item 12)
- [ ] Re-run `python -m pytest -q`, `scripts/train.py`, `scripts/evaluate.py` on the submission machine and confirm the README numbers still match (a test checks this)
