// Builds docs/presentation.pptx from experiments/results.json (no hand-typed metrics).
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const R = JSON.parse(fs.readFileSync("experiments/results.json"));
const P = "lgbm_" + R.primary_variant, ph = R.per_horizon, f1 = (x) => x.toFixed(1);
const NAVY = "0B2A3A", TEAL = "0E8F86", MINT = "DDF3EF", CORAL = "C2410C", INK = "1F2937", GREY = "6B7280", SAND = "F7F5F0";
const pres = new pptxgen(); pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "GlucoTwin - Digital Twin Challenge 2026";
const W = 13.33, FOOT = "SYNTHETIC data  |  research prototype  |  not clinically validated";
let n = 0;

function base(title, kicker) {
  const s = pres.addSlide(); n++; s.background = { color: SAND };
  s.addText(title, { x: 0.6, y: 0.35, w: W - 1.2, h: 0.8, fontFace: "Calibri", fontSize: 28, bold: true, color: NAVY, margin: 0 });
  if (kicker) s.addText(kicker, { x: 0.6, y: 1.08, w: W - 1.2, h: 0.4, fontFace: "Calibri", fontSize: 14, color: TEAL, margin: 0 });
  s.addText(FOOT, { x: 0.6, y: 7.05, w: 9, h: 0.3, fontFace: "Calibri", fontSize: 10, color: GREY, margin: 0 });
  s.addText(String(n), { x: W - 1.0, y: 7.05, w: 0.4, h: 0.3, fontFace: "Calibri", fontSize: 10, color: GREY, align: "right", margin: 0 });
  return s;
}
const bullets = (items, o) => items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 6 } }));
const card = (s, x, y, w, h, head, body, color, fs) => {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: "FFFFFF" }, line: { color: color || TEAL, width: 1.5 }, rectRadius: 0.12 });
  s.addText(head, { x: x + 0.2, y: y + 0.12, w: w - 0.4, h: 0.4, fontFace: "Calibri", fontSize: 15, bold: true, color: color || TEAL, margin: 0 });
  s.addText(body, { x: x + 0.2, y: y + 0.55, w: w - 0.4, h: h - 0.65, fontFace: "Calibri", fontSize: fs || 16, color: INK, valign: "top", margin: 0, paraSpaceAfter: 6 });
};

// 1 title
{ const s = pres.addSlide(); n++; s.background = { color: NAVY };
  s.addShape(pres.shapes.OVAL, { x: 9.2, y: 1.2, w: 3.6, h: 3.6, fill: { color: TEAL, transparency: 55 }, line: { color: TEAL, width: 0 } });
  s.addShape(pres.shapes.OVAL, { x: 10.4, y: 3.2, w: 2.4, h: 2.4, fill: { color: "FFFFFF", transparency: 85 }, line: { color: "FFFFFF", width: 0 } });
  s.addText("GlucoTwin", { x: 0.8, y: 1.7, w: 9, h: 1.2, fontFace: "Calibri", fontSize: 60, bold: true, color: "FFFFFF", margin: 0 });
  s.addText("An explainable, personalized glucose Digital Twin\nfor type 2 diabetes care", { x: 0.8, y: 3.0, w: 9, h: 1.1, fontFace: "Calibri", fontSize: 24, color: "CFEDE9", margin: 0 });
  s.addText("Digital Twin Challenge 2026  |  research proof of concept", { x: 0.8, y: 4.4, w: 9, h: 0.4, fontFace: "Calibri", fontSize: 16, color: "FFFFFF", margin: 0 });
  s.addText("[TEAM NAME / INSTITUTION / MEMBERS - to be filled before submission]", { x: 0.8, y: 5.1, w: 9, h: 0.4, fontFace: "Calibri", fontSize: 14, italic: true, color: "F6C28B", margin: 0 });
  s.addText("All demonstration patients and all reported results are SYNTHETIC. Not clinically validated. Not a medical device.", { x: 0.8, y: 6.5, w: 11.5, h: 0.4, fontFace: "Calibri", fontSize: 13, color: "F6C28B", margin: 0 }); }


const table = (s, rows, o) => s.addTable(rows.map((r, i) => r.map((c, j) => ({ text: c, options: { bold: i === 0 || (o.boldRow === i), color: i === 0 ? "FFFFFF" : INK, fill: { color: i === 0 ? NAVY : o.boldRow === i ? MINT : "FFFFFF" }, fontFace: "Calibri", fontSize: o.fs || 13, align: j && o.center ? "center" : "left" } }))),
  { x: o.x, y: o.y, w: o.w, colW: o.colW, border: { type: "solid", color: "CBD5E1", pt: 1 }, rowH: o.rowH || 0.5 });
const stat = (s, x, y, w, big, small, color) => { s.addText(big, { x, y, w, h: 1.0, fontFace: "Calibri", fontSize: 44, bold: true, color: color || TEAL, margin: 0 });
  s.addText(small, { x, y: y + 1.0, w, h: 0.9, fontFace: "Calibri", fontSize: 15, color: INK, valign: "top", margin: 0 }); };

// 2 India problem
{ const s = base("Healthcare problem: diabetes at national scale", "Type 2 diabetes dominates; day-to-day glucose between clinic visits is largely invisible");
  stat(s, 0.7, 1.8, 3.8, "~101 million", "people with diabetes in India (11.4% of the population), ICMR-INDIAB estimate");
  stat(s, 4.8, 1.8, 3.8, "~136 million", "people with prediabetes (15.3%), a pool that can convert to diabetes", CORAL);
  stat(s, 8.9, 1.8, 3.8, "113,043", "survey participants across states and UTs, 2008-2020");
  card(s, 0.7, 4.2, 12.0, 2.1, "Why forecasting + a twin?", "Continuous glucose monitors produce a reading every few minutes, but clinicians see snapshots. A continuously updated, explainable patient state with honest uncertainty could help a clinician review where a patient is heading. This is our motivation, not a demonstrated benefit.", TEAL, 15);
  s.addText("Source: Anjana et al., Lancet Diabetes Endocrinol 2023 (DOI 10.1016/S2213-8587(23)00119-5), figures as reported by secondary coverage and a Natl Med J India commentary; verify against the paper.", { x: 0.7, y: 6.45, w: 12, h: 0.5, fontFace: "Calibri", fontSize: 11, italic: true, color: GREY, margin: 0 }); }

// 3 literature
{ const s = base("Existing solutions and literature", "What we found - and what we could not verify");
  card(s, 0.6, 1.7, 5.9, 2.3, "Digital twins for health", "Scoping reviews (e.g. Katsoulakis et al., npj Digit Med 2024) survey health digital twins and their applications. We use the working idea of a personalised, continuously updated, predictive patient model.", TEAL, 15);
  card(s, 6.8, 1.7, 5.9, 2.3, "CGM forecasting", "Published work forecasts glucose from CGM history (e.g. GARNN, arXiv 2402.16230; a Bayesian T2DM approach, arXiv 2409.07315). We did not reproduce them; we benchmark only against persistence and ridge.", TEAL, 15);
  card(s, 0.6, 4.2, 5.9, 2.5, "Open datasets", "DiaTrend: type 1, controlled access. ShanghaiT2DM: type 2, 15-min CGM, public but licence terms conflict across sources. Glucose-ML (2025) surveys these collections.", TEAL, 15);
  card(s, 6.8, 4.2, 5.9, 2.5, "Other challenge entries", "Public repositories exist for this challenge, including one already named 'GlucoTwin' and one 'ThaliTwin'. We did not audit their claims; we flag the name conflict.", CORAL, 15); }

// 4 gaps
{ const s = base("Research gaps and our contribution", "A small, carefully evaluated proof of concept");
  card(s, 0.6, 1.7, 5.9, 4.9, "Gaps we target", "Leakage-resistant, patient-level evaluation against simple baselines\nExplicit behaviour for stale, missing and corrupt input (abstain, not guess)\nExplanations that are faithful to the model, with causal limits stated\nWhat-if tools that do not invent physiology", CORAL, 17);
  card(s, 6.8, 1.7, 5.9, 4.9, "What this repository contributes", "Twin state engine: validation, quarantine, forecast history, audit, restart-safe\nPer-horizon forecasts (15-120 min) with conformal intervals\nExact additive explanations and revision tracking\nScenario lab limited to supported inputs\n54 tests; reproducible results with ablations reported even when negative", TEAL, 17); }

// 5 problem
{ const s = base("Problem statement and intended outcome", "One localised outcome, not the whole body");
  card(s, 0.6, 1.7, 12.1, 1.6, "Primary task", "Given the last 60 minutes of CGM readings (15-min grid) plus patient history, forecast glucose for the next 15-120 minutes with an uncertainty interval, an explanation and a data-quality status.", TEAL, 16);
  card(s, 0.6, 3.5, 5.9, 3.1, "Intended outcome", "A working data-to-forecast loop that a clinician-facing dashboard can show, test and audit - and an honest benchmark.", TEAL, 16);
  card(s, 6.8, 3.5, 5.9, 3.1, "Explicitly out of scope", "Diagnosis, treatment or insulin/medication advice. Alarms. Any claim of clinical validation.", CORAL, 16); }

// 6 data
{ const s = base("Data sources, privacy and limitations", "Research found hard limits; we documented a safe fallback");
  table(s, [["Dataset", "Population", "Access finding", "Used?"],
    ["DiaTrend", "Type 1, CGM", "Controlled access (Synapse + agreement); no redistribution", "No"],
    ["ShanghaiT2DM", "Type 2, 15-min CGM", "Public, but licence terms conflict across sources; host unreachable from the build sandbox", "Adapter only (untested on real files)"],
    ["Synthetic cohort", "T2D-like, 100 pts x 14 d", "Generated here, seeded, MIT, labelled SYNTHETIC on every record", "Yes - all results"]],
    { x: 0.6, y: 1.7, w: 12.1, colW: [2.1, 2.5, 5.2, 2.3], rowH: 0.7 });
  s.addText(bullets(["No real patient data in the repository, logs or figures", "Static-to-glucose links in the synthetic data exist by construction: they cannot validate physiology",
    "Real-data results must be produced and reported separately"]), { x: 0.7, y: 4.9, w: 12, h: 1.3, fontFace: "Calibri", fontSize: 16, color: INK, valign: "top", margin: 0 });
  s.addText("No result in this deck says anything about real patients.", { x: 0.7, y: 6.3, w: 12, h: 0.5, fontFace: "Calibri", fontSize: 18, bold: true, color: CORAL, margin: 0 }); }

// 7 architecture
{ const s = base("Architecture and data fusion", "History + stream -> quality gate -> twin state -> forecast -> explanation -> dashboard");
  s.addImage({ path: "docs/architecture.png", x: 0.9, y: 1.55, w: 11.5, h: 5.35 }); }

// 8 workflow + dashboard
{ const s = base("Dynamic update workflow and dashboard", "Every new reading updates state, forecast, explanation and audit trail");
  const steps = ["New reading", "Validate", "Append / quarantine", "Quality check", "Forecast or withhold", "Explain + audit"];
  steps.forEach((t, i) => { const x = 0.6 + i * 2.05;
    s.addShape(pres.shapes.OVAL, { x: x + 0.6, y: 1.55, w: 0.5, h: 0.5, fill: { color: i === 4 ? CORAL : TEAL }, line: { color: "FFFFFF", width: 0 } });
    s.addText(String(i + 1), { x: x + 0.6, y: 1.55, w: 0.5, h: 0.5, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 14, bold: true, color: "FFFFFF", margin: 0 });
    s.addText(t, { x, y: 2.1, w: 1.85, h: 0.4, align: "center", fontFace: "Calibri", fontSize: 12, bold: true, color: NAVY, margin: 0 }); });
  s.addImage({ path: "docs/figures/demo_forecast.png", x: 0.5, y: 2.7, w: 4.3, h: 2.0 });
  s.addImage({ path: "docs/figures/demo_explanation.png", x: 4.95, y: 2.7, w: 4.2, h: 2.0 });
  s.addImage({ path: "docs/figures/demo_scenario.png", x: 9.3, y: 2.7, w: 4.0, h: 1.9 });
  s.addText(bullets(["Six tabs: overview, forecast, explanation, scenario lab, quality + audit, model performance",
    "Explanations are exact additive terms of the model output; scenario lab is labelled HYPOTHETICAL, meal/exercise/drug controls disabled",
    "Replay of a recorded SYNTHETIC stream; there is no live-device connection"]), { x: 0.7, y: 4.95, w: 12, h: 1.9, fontFace: "Calibri", fontSize: 15, color: INK, valign: "top", margin: 0 }); }

// 9 evaluation
{ const s = base("Model evaluation and baseline comparison", `Held-out SYNTHETIC test: ${R.split_patients.test} patients, ${R.test_origin_counts.complete_input_windows.toLocaleString()} windows, identical cases for all models`);
  s.addImage({ path: "docs/figures/mae_by_horizon.png", x: 0.5, y: 1.6, w: 5.6, h: 3.2 });
  const hs = ["15", "30", "60", "120"];
  table(s, [["MAE mg/dL", ...hs.map((h) => "+" + h + " min")], ["Persistence", ...hs.map((h) => f1(ph.persistence[h].mae))], ["Ridge", ...hs.map((h) => f1(ph.ridge_cgm[h].mae))],
    ["LightGBM (CGM only)", ...hs.map((h) => f1(ph.lgbm_cgm[h].mae))], ["LightGBM + time of day", ...hs.map((h) => f1(ph[P][h].mae))]],
    { x: 6.4, y: 1.7, w: 6.4, colW: [2.4, 1.0, 1.0, 1.0, 1.0], boldRow: 4, center: true, rowH: 0.42, fs: 13 });
  const b = R.bootstrap_primary_vs_persistence["60"], t = R.bootstrap_tod_vs_cgm["60"], p = R.bootstrap_personalization_vs_cgm["60"], st = R.bootstrap_static_vs_cgm["60"];
  const fmt = (x) => `${x.mae_diff >= 0 ? "+" : ""}${x.mae_diff.toFixed(2)} [${x.ci95_low.toFixed(2)}, ${x.ci95_high.toFixed(2)}]`;
  s.addText(bullets([`Primary vs persistence at +60 min: ${fmt(b)} mg/dL (95% patient-bootstrap CI); better for ${R.patient_level.n_primary_better_than_persistence_mean_mae} of ${R.patient_level.n_patients} patients`,
    `Ablations vs CGM-only at +60 min: time of day ${fmt(t)} (expected by construction: synthetic meals are scheduled); personal baseline ${fmt(p)}; static EHR ${fmt(st)} - no reliable gain at +60 min (personal baseline helps only ~0.3 mg/dL at +15 min)`]),
    { x: 0.6, y: 5.0, w: 12.2, h: 1.3, fontFace: "Calibri", fontSize: 14, color: INK, valign: "top", margin: 0 });
  s.addText("Synthetic data: shows the pipeline works and recovers the generator's dynamics - not clinical accuracy. Preliminary.", { x: 0.6, y: 6.4, w: 12.1, h: 0.5, fontFace: "Calibri", fontSize: 15, bold: true, color: CORAL, margin: 0 }); }

// 10 tests / DQ / uncertainty
{ const s = base("Tests, data-quality behaviour and uncertainty", "Fail safe, show uncertainty, admit misses");
  s.addImage({ path: "docs/figures/demo_withheld.png", x: 0.5, y: 1.6, w: 4.6, h: 1.84 });
  s.addImage({ path: "docs/figures/demo_forecast.png", x: 0.5, y: 3.6, w: 4.6, h: 2.15 });
  const c = R.intervals.per_horizon, pp = R.intervals.per_patient_mean_coverage;
  s.addText(bullets([`Stale (> 20 min) or incomplete 60-min window: forecast withheld; ${(R.abstention.abstention_rate_among_observed * 100).toFixed(1)}% of observed test origins (synthetic missingness)`,
    "Rejected / quarantined: naive or future timestamps, NaN, out-of-range values, conflicting duplicates",
    `80% intervals: coverage ${(c["15"].coverage * 100).toFixed(0)}-${(c["120"].coverage * 100).toFixed(0)}% on test; per patient ${(pp.min * 100).toFixed(0)}-${(pp.max * 100).toFixed(0)}% (marginal guarantee only)`,
    `Hardest case: flat glucose before a meal (MAE ${f1(R.failure_analysis.mae120_by_trend_phase["flat_|slope|<=30"])} vs ${f1(R.failure_analysis.mae120_by_trend_phase["rising_>30mgdl_per_h"])} mg/dL rising, +120 min); bottom-left: a breakfast spike escaping the interval`,
    "54 automated tests incl. leakage, restart, offline, additivity, dashboard; mutation-checked"]),
    { x: 5.4, y: 1.6, w: 7.4, h: 5.2, fontFace: "Calibri", fontSize: 15, color: INK, valign: "top", margin: 0 }); }

// 11 limitations
{ const s = base("Limitations, responsible use and next steps", "");
  card(s, 0.6, 1.5, 5.9, 5.2, "Not claimed", "Clinical validation or real-patient accuracy\nBenefit for type 2 populations (data are synthetic)\nCausal effects of food, exercise or drugs\nUse for diagnosis, treatment or medication decisions\nThat time-of-day or EHR gains transfer to real data", CORAL, 18);
  card(s, 6.8, 1.5, 5.9, 5.2, "Next steps", "1. Run the ShanghaiT2DM adapter locally; verify columns, units, licence\n2. Re-train and evaluate; report real-data results separately\n3. Add meal/activity inputs only if real data support them\n4. Clinician review and prospective evaluation before any clinical use\n5. Resolve the project-name conflict", TEAL, 18); }

// 12 conclusion
{ const s = pres.addSlide(); n++; s.background = { color: NAVY };
  s.addText("Conclusion", { x: 0.8, y: 0.7, w: 11, h: 0.8, fontFace: "Calibri", fontSize: 38, bold: true, color: "FFFFFF", margin: 0 });
  s.addText(bullets(["A reproducible twin pipeline: fused history + stream, versioned forecasts, explanations, safe withholding", `On held-out synthetic patients it beats persistence and ridge; value on real patients is untested`,
    "Negative and null findings are reported alongside positives"]), { x: 0.8, y: 1.7, w: 11.5, h: 2.4, fontFace: "Calibri", fontSize: 20, color: "CFEDE9", valign: "top", margin: 0 });
  s.addText("Repository: [PUBLIC GITHUB URL - to be filled]\nDemo video (20+ min, unlisted): [YOUTUBE URL - to be filled]\nTeam / college / incubator: [to be filled]", { x: 0.8, y: 4.5, w: 11.5, h: 1.4, fontFace: "Calibri", fontSize: 18, italic: true, color: "F6C28B", margin: 0 });
  s.addText("Research proof of concept. Synthetic data. Not clinically validated. Not a medical device.", { x: 0.8, y: 6.5, w: 11.5, h: 0.4, fontFace: "Calibri", fontSize: 13, color: "F6C28B", margin: 0 }); }

pres.writeFile({ fileName: "docs/presentation.pptx" }).then(() => console.log("deck written, slides:", n));
