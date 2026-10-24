# Demo video plan (at least 20 minutes, unlisted YouTube)

The spec asks for **>= 20 minutes** (the challenge text is inconsistent; use the stricter figure). **The video has NOT been recorded** - this is the plan and script.
Before recording: `pip install -r requirements.txt`, `python scripts/init_demo.py --reset`, `streamlit run app/dashboard.py`, close other windows, hide notifications,
and make sure no personal data is visible. Everything on screen must say SYNTHETIC. Say aloud: "all patients and results are synthetic; this is not clinically validated."

| Time | Segment | On screen | Say / show |
|---|---|---|---|
| 00:00-02:00 | Problem and motivation | Slide 2 (India burden) | ICMR-INDIAB figures (~101 M diabetes, ~136 M prediabetes) with source; why CGM + a continuously updated patient state; motivation, not a proven benefit |
| 02:00-05:00 | Literature, limits, contribution | Slides 3-5 | Digital-twin reviews, CGM forecasting papers, open datasets; name-conflict note; gaps; what we do and do not claim |
| 05:00-08:00 | Architecture and data | Slides 6-7, `docs/architecture.pdf`, `data/README.md` | History vs dynamic stream; ingestion/quality; twin state in SQLite; forecaster; explainer; synthetic vs real boundary; why DiaTrend/ShanghaiT2DM were not used here |
| 08:00-12:00 | Live demo: load, forecast, update | Dashboard, patient SYNTH-001 | Overview tab (profile + provenance + SYNTHETIC badge, latest value, trend). Forecast tab (interval, model version, origin, unit, IST). Click **+15 min** several times: counters, forecast id, history table and audit trail change. Tick "Overlay recorded later values" and discuss a miss honestly. Explanation tab: horizon switch, contribution bars, additivity note, revision vs previous forecast |
| 12:00-14:00 | Data quality + scenario | Sidebar test buttons; Scenario tab | **Stop stream** -> forecast withheld with reason. Reset. **Corrupted value**, **future-dated**, **no timezone**, **conflicting duplicate** -> Quality & audit tab quarantine table. Scenario slider on latest vs window; read the HYPOTHETICAL banner; show disabled meal/exercise/medication controls and why |
| 14:00-17:00 | Evaluation | Model performance tab, `experiments/benchmark_report.md`, slide 9 | Split design (patient-disjoint, 48 h calibration, validation-only selection), identical cases, baselines, MAE table, bootstrap CIs, ablations (time-of-day by construction; personalization only a tiny gain at +15 min; static EHR no reliable gain), coverage per horizon and per patient, abstention rate, event task, failure analysis. Run `python -m pytest -q` live and show the pass count |
| 17:00-19:00 | Usefulness, privacy, safety | Slide 11 | Potential use as a review aid; no personal data; no diagnosis/medication advice; type 1 data and synthetic EHRs do not validate type 2 physiology; what clinical validation would need |
| 19:00-20:30+ | Repository and wrap-up | GitHub page | README tour, licence and notices, setup commands, how to replay (`python scripts/replay_stream.py --patient SYNTH-001 --steps 12 --stop-after 6`), train/evaluate commands, remaining limitations, thanks |

Tips: rehearse once with a timer; if under 20:00, extend the live-demo and evaluation sections (walk through `scripts/evaluate.py` output and the failure analysis) rather than padding.
After upload: set to **Unlisted**, open the link in a private/incognito window to confirm access, then paste it into the README (`[DEMO VIDEO URL]`) and the final slide.
