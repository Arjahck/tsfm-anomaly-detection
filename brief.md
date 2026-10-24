# Project: TSFM anomaly detection demo — Timestral on ICS (HAI), then IT (LANL)

## Goal
Build a reproducible research demo to understand what Mistral's Timestral time-series
foundation models can and cannot do for security anomaly detection. This is a learning
project, not a product: honest results (including negative ones) matter more than good numbers.

Core hypothesis (from Uray et al. 2026, arXiv 2607.12454, and the ICML 2026 paper
"On the Application of Time-Series Foundation Models for Detecting Long-Context Anomalies
in Industrial Control Systems"): zero-shot TSFMs detect the *boundaries* of anomalies
(forecast error spikes at onset/offset) but miss the *persistent interior* of long-duration
attacks, because anomalous data enters the context and gets forecast as normal.

## Ground rules
- Before writing code, read the Timestral repo (github.com/mistralai/timestral) and the
  Hugging Face model cards (mistralai/Timestral-5M, -28M, -123M, -209M). Learn the real
  inference API: multivariate targets, past-only covariates, known-future covariates,
  categorical covariates, quantile output format. Do not guess the API.
- Then inspect the HAI data and write PLAN.md (data schema, splits, compute estimate,
  open questions). STOP and wait for my review before implementing.
- Python 3.11+, uv, polars or pandas, matplotlib. CPU inference by default
  (Timestral doesn't need a GPU); use a GPU if available.
- Config-driven (YAML), single CLI entry point, fixed seeds.
- Cache every forecast (all quantiles) to parquet, keyed by dataset/model/setup/variant.
  Scoring and evaluation must re-run from cache without re-running inference.
- Smoke-test every pipeline on a small slice (e.g. 2 h of one test file) before full runs.
  Print an estimated runtime before any run longer than 10 minutes.
- Strict time-based splits. Thresholds and normalization statistics come only from normal
  training data. Never tune on test labels.
- Never fabricate results. If a paper detail can't be confirmed (e.g. exact Forecast
  Fallback mechanics), implement a clearly labelled interpretation and note it in REPORT.md.
- Commit after each working step.

## Phase 1 — ICS on HAI

### Data
- HAI dataset: github.com/icsdataset/hai. Use HAI 21.03 as primary (the version used in
  the HAI anomaly detection contest, which scored with TaPR). From 22.04 on, files are in
  Git LFS (`git lfs pull`).
- Inspect and document: timestamp, channels prefixed by process (P1 boiler, P2 turbine,
  P3 water treatment, P4 HIL simulator), attack label columns (overall and per process
  if present).
- Drop constant columns. Separate continuous sensors from discrete/actuator channels and
  propose whether discrete ones should be targets or covariates.
- Resolution is 1 s. Timestral context = 32,768 steps (~9 h at 1 s, ~3.8 days at 10 s).
  Default: downsample to 10 s (mean for continuous, last/mode for discrete; label = 1 if
  any attack in the window). Keep 1 s as an optional config for a short-context comparison.
- Normalize per channel with training-data statistics.

### Forecasting & scoring (shared)
- Rolling evaluation per test file: context = history before t (capped at max context),
  horizon H (configurable, default 30 steps = 5 min at 10 s), step forward by H.
  Document how warm-up works if train and test files aren't contiguous.
- Point score per channel from the quantile forecast: distance outside the band,
  normalized by band width, e.g. max(0, y − q95, q05 − y) / (q95 − q05 + eps).
  Also log pinball/CRPS-approx loss as an alternative score.
- Aggregate across channels: max and mean-of-top-k (configurable), optional smoothing.
- Threshold: percentile of scores on a held-out slice of normal training data
  (configurable, default 99.5th).

### Experiments
1. Univariate zero-shot: every channel forecast independently. Goal: reproduce the
   boundary-vs-interior pattern.
2. Multivariate per process: P1, P2, P3 each as a joint forecast (targets = continuous
   channels; discrete/actuator channels as past-only covariates if the API supports it).
   Compare against experiment 1.
3. Context-protection variants, applied to the better of 1 and 2:
   a. Forecast Fallback — find the ICML paper/code first and match it if possible.
      Otherwise this interpretation: when a step's score exceeds threshold, replace the
      observed values in the context with the model's median forecast for subsequent
      forecasts, so suspected-anomalous data doesn't become the new normal. Add a
      max-fallback-duration parameter.
   b. Frozen reference context: forecast from a fixed clean context taken from normal
      training data instead of recent history.
   c. Dual-context disagreement: score = divergence between the forecast from recent
      context and the forecast from frozen clean context.
4. Model sizes: run the best setup with Timestral 5M, 28M and 123M (209M optional).
   Record wall-clock latency per forecast call.
5. Honesty baselines with identical scoring: rolling robust z-score per channel, and
   last-value/seasonal-naive forecast. Optional stretch: Chronos-2 or TimesFM zero-shot.

### Metrics
- ROC-AUC and PR-AUC on point scores.
- TaPR (time-series-aware precision/recall/F1) via the official implementation
  github.com/saurf4ng/TaPR (vendor it if it doesn't install). Report parameters used.
- Do NOT use point-adjusted F1 as a headline metric (it inflates results); label it if shown.
- Boundary-vs-interior analysis (the key result): split each attack into onset (first N
  steps), interior, and offset (N steps after end). Report detection rate per segment,
  detection latency and interior coverage, per attack and per method.
- Accuracy vs model size vs latency table.

### Outputs
- results/phase1/*.csv
- Figures: per-attack timelines (signals, forecast band, score, attack window shaded) for
  ~6 representative attacks including the longest; boundary-vs-interior bar chart per
  method; AUC vs model size vs latency.
- REPORT.md: setup, deviations from the papers, results, what the model does well and
  badly, open questions. Plain, critical tone.

## Phase 2 — IT with controlled ground truth (only after I sign off on Phase 1)

### Data
- LANL "Comprehensive, Multi-Source Cyber-Security Events" (csr.lanl.gov/data/cyber1/).
  I download it manually to data/lanl/ (auth, flows, redteam). Files are large: stream
  with polars or duckdb, never load fully into memory.
- Time is seconds from epoch 1; the real calendar is undisclosed. Derive hour-of-day and
  day index; note that the true weekday is unknown.
- Per-minute series:
  - tenant-level: total auth events, failed auth events, distinct source users
  - auth events per top-N destination computers by volume ("DC-like" hosts; LANL doesn't
    label DCs, so document the selection)
  - bytes out per top-N source hosts from flows
- Split: first ~70% of days for history/calibration, the rest for test.

### Anomaly injection (test portion only, labelled, multiple seeds, magnitude/duration grids)
- Silence: a log source drops to 0 (or x% of normal) for D minutes.
- Brute-force burst: failed auth += k × local baseline for D minutes.
- Slow exfiltration ramp: bytes out for one host ramps linearly up to +p% over hours.
- Baseline shift: a persistent step change of +y%.
Keep injections non-overlapping and save an injection manifest.

### Experiments & metrics
- Same pipeline (best Phase 1 setup plus context-protection variants), with
  hour-of-day/day-index as known-future covariates vs without: do covariates reduce
  false positives?
- Detection rate and latency per anomaly type × magnitude, as detection curves.
  Highlight slow ramp and baseline shift (the "boiling frog" cases).
- Sanity check: scores around the real red-team events. Report honestly even if they're
  invisible in aggregated counts.
- Same baselines as Phase 1. Add a Phase 2 section to REPORT.md.

## Final deliverable
README.md with setup and one-command reproduction per phase, REPORT.md with findings, and
a short "demo storyline" section naming the 3–4 plots that tell the story: boundary
detection → persistent miss → context-protection fix → IT injection detection curves.
