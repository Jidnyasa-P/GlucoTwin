# Research and challenge verification notes

Research checked on 20 October 2026. This is a targeted engineering review, not a systematic review.

## Challenge requirements

The current Unstop listing for Happiest Health's Digital Twin Challenge 2026 describes a student proof of concept combining historical/simulated EHR data and dynamic sensor time series, predicting a localized health outcome, with a clinician-facing dashboard. Its submission checklist includes a public GitHub repository, team/institution information, problem/use case, technical stack/model, a video, open-source license, architecture diagram, and presentation. The listing states a prototype submission deadline of 20 October 2026 at 7:00 PM IST. The project specification supplied by the user requires at least a 20-minute demo video; the current listing also states a minimum 20-minute video. Verify the live official listing immediately before submission because deadlines and wording can change.

Source: https://unstop.com/hackathons/digital-twin-challenge-2026-happiest-health-1757873

## Research papers and data

1. Katsoulakis E, Wang Q, Wu H, et al. *Digital twins for health: a scoping review*. npj Digital Medicine 7, 77 (2024). DOI: https://doi.org/10.1038/s41746-024-01073-0. The review describes digital twins as evolving representations connected to a physical entity and highlights interoperability and privacy/security challenges. Article reports CC BY 4.0 licensing.
2. Ringeval M, Etindele Sosso FA, Cousineau M, Paré G. *Advancing Health Care With Digital Twins: Meta-Review of Applications and Implementation Challenges*. Journal of Medical Internet Research 27, e69544 (2025). DOI: https://doi.org/10.2196/69544. The review identifies data quality, ethical and socioeconomic barriers, and gaps in scalability, interoperability and clinical validation.
3. Prioleau T, Bartolome A, Comi R, et al. *DiaTrend: A dataset from advanced diabetes technology to enable development of novel analytic solutions*. Scientific Data 10, 556 (2023). DOI: https://doi.org/10.1038/s41597-023-02469-5. The paper describes clinical-grade CGM and insulin-pump data. Its paper is CC BY 4.0; this does not automatically grant blanket redistribution rights for every associated data file. This implementation does not access or redistribute the dataset.
4. Synthea: https://github.com/synthetichealth/synthea. A synthetic patient-record generator useful for EHR-format demos, but synthetic records do not validate glucose physiology.
5. Twin Health: https://www.twinhealth.com/. Commercial personalized metabolic-health example, included as context only; no product performance claims or direct comparison are made here.

## Technical gap assessment

- Interoperability and provenance are difficult when clinical history and time-series sensors have different structures; this project makes source labels and state updates explicit but does not implement FHIR ingestion.
- Stale and missing streams can create false confidence; the PoC implements a quality gate and a dashboard stale-stream toggle, but not a validated production alerting policy.
- Synthetic data enables reproducible code-path tests but cannot establish real-world forecasting performance. This project reports synthetic-only results and leaves authorized external evaluation as a submission/future-work requirement.
- Personalization and uncertainty need careful evaluation. The current interval is heuristic and not calibrated; patient-specific model adaptation and interval coverage studies remain future work.
- The benchmark is deliberately simple and patient-separated, but all held-out sequences come from the same synthetic generator family. It should be treated as a software pipeline test, not clinical evidence.
