# TSFM anomaly detection: Timestral on ICS, then IT

A research demo of what Mistral's Timestral time-series foundation models can and cannot do for security anomaly detection. Phase 1 is ICS on HAI, Phase 2 is IT on LANL with injected anomalies. `brief.md` is the spec, this file is how Claude Code works on it. This is a learning project, not a product. An honest negative result beats a good number.

The hypothesis under test (Uray et al. 2026, arXiv 2607.12454, and the ICML 2026 paper on long-context ICS anomalies): zero-shot TSFMs catch the boundaries of an attack but miss its persistent interior, because anomalous data enters the context and gets forecast as normal. Every experiment exists to confirm it, refute it or fix it.

**Timestral is paused (2026-10-20)** for licence reasons. Until Arthur lifts the pause, never download or run a Timestral model, and never publish Timestral results. Phase 1 runs on amazon/chronos-2 (Apache 2.0) through the same pipeline. The Timestral code and configs stay, switched off; the package is an optional extra and the weights were deleted
from the cache on 2026-10-21 (D152), so a switch back means `uv sync --extra timestral` and a fresh download.

## Session start

1. Read `PLAN.md` (state, decisions, open questions) and the `brief.md` section of the current phase.
2. `git log --oneline -15` to see where the last session stopped.
3. No `PLAN.md` yet means step 0.

`brief.md` wins over `PLAN.md`. If they conflict, say so and ask.

## Step 0: plan, then stop

This folder is not a git repo yet. First commit: `git init`, a `.gitignore` (`data/`, `cache/`, `.venv/`, `.DS_Store`), this file and `brief.md`.

1. Read the Timestral repo (github.com/mistralai/timestral) and the model cards (mistralai/Timestral-5M, -28M, -123M, -209M). Learn the real inference API: multivariate targets, past-only, known-future and categorical covariates, the quantile output format. Note in `PLAN.md` where each fact comes from.
2. Find both papers and any code, Forecast Fallback in particular.
3. Get HAI 21.03 into `data/hai/` and inspect it.
4. Write `PLAN.md`: data schema, channel split (continuous vs discrete, with a proposal for targets vs covariates), splits and warm-up, compute estimate, layout, open questions.
5. Stop. No pipeline code before Arthur has reviewed `PLAN.md`.

## Who decides

Only Arthur changes the brief: the hypothesis, phases, experiments, metrics, the split and threshold rules, and the sign-offs. Claude decides the rest (code, config schema, file formats, plots) and logs every choice the brief leaves open in the Decisions section of `PLAN.md`.

- **Two hard stops:** after `PLAN.md`, and after the Phase 1 `REPORT.md`. Wait for Arthur's OK before implementing, and again before any Phase 2 code.
  Both are passed: Arthur signed off Phase 1 on 2026-10-21 (option B as an addendum, REPORT.md 4.20).
- **Ask first** before deviating from the brief, deleting cached forecasts or data, adding a model or paid service the brief does not name, or pushing.
- LANL: Arthur lifted the manual-download rule on 2026-10-21 (D139) and approved the download form (his email and a
  usage note). Never submit Arthur's details to any other form or service without his explicit OK.

## A step is done when

1. It passed the smoke test on the small slice (2 h of one test file).
2. If it forecasts: scoring and evaluation re-run from the cache without inference.
3. Its open choices are in `PLAN.md`, its interpretations and deviations from the papers in `REPORT.md`.
4. A new command is in the table below and in `README.md`.
5. It is committed: `P<phase>: <what works now>`. Commit locally after each working step.

End of session: at most ten lines on what works, what was decided, what is an interpretation or broken, next step.

## Rules

Honesty

- Never fabricate results. Every number in `REPORT.md` comes from a file in `results/`. A run that did not happen is reported as not run.
- Strict time-based splits. Normalization statistics and thresholds come only from normal training data.
- Never tune on test labels: no threshold, horizon, top-k or smoothing picked by test score. Where the brief picks "the better" setup, `REPORT.md` says it was picked on test results.
- Point-adjusted F1 is never a headline metric. Label it whenever it is shown.
- A paper detail that cannot be confirmed (e.g. Forecast Fallback mechanics) becomes a clearly labelled interpretation, in the config name and in `REPORT.md`.
- Negative results go into `REPORT.md` as plainly as positive ones. Plain, critical tone.

Sources

- Never guess a model's API (Timestral, Chronos-2). Check the repo or the model card. If neither says, test it on a toy input and record what you found.
- TaPR only from the official implementation (github.com/saurf4ng/TaPR), vendored into `vendor/TaPR/` if it does not install. Report its parameters.

Engineering

- Python 3.11+, uv, polars or pandas, matplotlib. CPU inference by default, GPU when available.
- One CLI entry point, YAML configs, fixed seeds. Pin model revisions in the config.
- Every forecast is cached with all quantiles to parquet, keyed by dataset/model/setup/variant. Scoring, evaluation and plots read the cache, never the model.
- Smoke test on the small slice before every full run. Print the estimated runtime before any run over 10 minutes.
- LANL files are large. Stream them with polars or duckdb, never load a file whole.
- KISS. No abstraction for an experiment that is not built yet.
- Tests only where a silent bug changes results: downsampling and label aggregation, splits and normalization (no leakage), scores and thresholds, onset/interior/offset segmentation, and in Phase 2 the injections.
- `data/` and `cache/` stay out of git. CSVs and figures in `results/` are committed.

## Layout

Fixed by `PLAN.md` section 11, D60-D116 and, for the switch to Chronos-2, section 14 and D117-D153.

```
CLAUDE.md            this file
brief.md             the spec, Arthur only
PLAN.md              schema, splits, compute estimate, decisions D1-D153, open questions; section 14 = Chronos-2
README.md            setup, one-command reproduction per phase
REPORT.md            setup, deviations from the papers, results (written after the full Phase 1 runs)
pyproject.toml       uv project, Python 3.12; console script tsfm-ad; uv.lock pins everything (chronos-forecasting 2.3.2)
configs/             base.yaml (shared; model chronos2), smoke.yaml, smoke_1s.yaml, one YAML per planned run (exp1_*,
                     exp2_*, exp3*, exp5_baselines, res10s_uni_ff, res1s_*), optional opt_*; hai2103_attacks_pdf.csv
                     (PDF attack table, D56)
configs/timestral/   Timestral-only configs (exp4_* sizes, res10s_5m_ref, res1s_uni_c32k, smoke settings), PAUSED:
                     kept for a later switch back, never run by smoke or all (D123)
src/tsfm_ad/
  cli.py             entry point, one subcommand per step
  pipeline.py        smoke and all: run chains in PLAN.md section 8 / 14.7 order, resume, failure log
  config.py          YAML inheritance, run keys, forecast hash, `selected` resolution, seeds
  data.py tables.py  prepare: read, roles, downsample, normalize, segments, attacks; channels/attacks/splits CSVs
  cache.py           forecast cache paths, atomic writes, readers (never a stale hash)
  forecast.py        rolling / FF / frozen / prepend / cf-onset inference; one predict
                     interface, dispatched by model.name; the Timestral guard (D117)      [hashed source]
  model_chronos2.py  Chronos-2 adapter: load (pinned, float32), one call per group in the
                     cache layout, univariate rows as separate items, sorted quantiles
                     (D119), constant rows as exact zeros (D128)                           [hashed source, chronos2]
  context.py         Forecast Fallback hook, FF thresholds, frozen forecast                [hashed source]
  mps_shim.py        UNOFFICIAL float64-on-CPU patch so timestral runs on MPS (Timestral
                     only; paused)                                                         [hashed source, timestral]
  baselines.py       robustz, lastvalue, seasonal-refday in the cache schema               [hashed source]
  ff_results.py      FF episodes, activity, thresholds CSVs and per-attack FF attribution
  score.py           band, crps, mae, dual scores, aggregation, calib thresholds
  evaluate.py        AUCs, point metrics, TaPR, segments, h strata, band width
  summary.py         segments_summary (common-set latency) and cf_onset.csv
  tapr_wrap.py       official TaPR.py called in memory
  selection.py       the D21 pick (select --stage base|best)
  latency.py         latency.csv and size_latency.csv
  mps_check.py       the D54 CPU vs MPS check and the MPS guard (per model: chronos2, timestral)
  d128.py            size of the D128 constant-row guard: adapter vs raw Chronos-2 on the calls
                     with a constant row (D129); d128_effect*.csv
  diagnostics.py     quantile_diagnostics.csv: crossings, constant rows, band widths per split (D133)
  compare.py         fa_matched.csv, bootstrap_ci.csv, bootstrap_paired.csv: matched false alarms, paired bootstrap (D135)
  model_chronos2_small.py  chronos-2-small through the unchanged adapter, 13 -> 21 levels (D136)   [hashed, small only]
  lanl.py inject.py  Phase 2: LANL per-minute series (DuckDB), injections (PLAN.md 15)              [hashed, Phase 2]
  p2.py              Phase 2 forecasts and cache (rolling, FF, frozen, baselines)                        [hashed, Phase 2]
  p2_eval.py p2_plots.py  Phase 2 scores, detection, false alarms, red team, MPS check; figures (cache only)
  plots.py plot_util.py   figures from cache and results only
  paper.py           the paper's tables and figures (results/paper) and the PDF; contamination share (D153)
tests/               pytest, result-critical code only (data, splits, forecast, Chronos-2 adapter, FF, score,
                     segments, TaPR, selection); fakes.py = a fake Chronos-2 pipeline (no download)
vendor/TaPR/         official TaPR.py (unmodified, sha256 checked), LICENSE, SOURCE.md
data/hai/            HAI 21.03 (hai-21.03/*.csv.gz), README, technical-details PDF; git-ignored
cache/               git-ignored: hf/ (weights), <dataset>/prepared/, <dataset>/<model>/<setup>/<variant>@<hash8>/
                     (forecasts per split, calls_<split>.csv, meta.json, scores/), logs/; <model> =
                     chronos2-<rev7>-<device> (timestral-<size>-<rev7>-<device> when unpaused)
results/phase1/      CSVs and figures/ (1 s figures in figures/hai2103-1s/); committed
results/smoke/       smoke CSVs and figures; committed
results/phase2/      Phase 2 CSVs and figures (smoke/ for the smoke slice); cache/lanl/ holds its forecasts
results/paper/       the paper's tables and figures; paper/ holds paper.typ, refs.bib and the compiled paper.pdf
```

Editing a `[hashed source]` file changes every forecast hash of that kind (model_chronos2.py: Chronos-2 only,
mps_shim.py: Timestral only), so the next run writes new cache directories beside the old ones (nothing is
deleted). Reporting code lives elsewhere on purpose.

## Commands

All from the project root; every command takes `--config configs/<file>.yaml`, `--split` and `--device cpu|mps`.
Runtimes measured on the M5 (smoke) or estimated in PLAN.md section 14.8 (full data, Chronos-2 on MPS, D130).

| command | does | runtime |
|---|---|---|
| `uv sync` | install the pinned environment | about 1 min |
| `uv run pytest -q` | the test suite (121 tests) | about 12 s |
| `uv run tsfm-ad prepare --config configs/base.yaml` | prepared data, channels.csv, attacks.csv, splits.csv (10 s; `res1s_uni.yaml` for 1 s) | about 2 s |
| `uv run tsfm-ad forecast --config configs/X.yaml` | Chronos-2 inference of that run into the cache (Timestral refused unless `TSFM_ALLOW_TIMESTRAL=1`); estimate printed first; cached files skipped | seconds to about 1.7 h (10 s), about 24 h (1 s) |
| `uv run tsfm-ad baselines --config configs/exp5_baselines.yaml` | the three baselines into the cache | seconds (10 s), about a minute (1 s) |
| `uv run tsfm-ad score --config configs/X.yaml` | scores, aggregation, calib thresholds, from the cache | seconds (10 s) |
| `uv run tsfm-ad evaluate --config configs/X.yaml` | metrics, TaPR, segments, by-h, cf-onset, FF CSVs, from the scores | seconds (10 s), minutes (1 s) |
| `uv run tsfm-ad select --config configs/exp1_uni.yaml --stage base` | D21 pick into results/phase1/selection.csv (`--stage best` after exp 3) | under 1 s |
| `uv run tsfm-ad plot --config configs/base.yaml` | the Phase 1 figures | seconds |
| `uv run tsfm-ad restart-plot --config configs/exp1_uni.yaml` | the restart-rate figure `restart_timeline.png` (D154) | seconds |
| `uv run tsfm-ad d128 --config configs/exp2_mv.yaml` | the D128 guard's effect (adapter vs raw Chronos-2 on the calls with a constant row; rolling in-file, cf-onset, frozen) into d128_effect.csv and d128_effect_channels.csv; `all` runs it after exp 2 and 3b | seconds (smoke), about 1 min (10 s uni) to about 17 min (10 s mv-lit) on CPU |
| `uv run tsfm-ad diagnostics --config configs/X.yaml` | quantile crossings, D128 constant rows and band widths per split into quantile_diagnostics.csv (cache only); `all` and `smoke` write it with latency.csv | seconds (10 s) |
| `uv run tsfm-ad compare --config configs/base.yaml` | the methods of `compare.sets` at matched false-alarm rates (threshold from the test labels: evaluation only, never a pick) and paired block-bootstrap intervals into fa_matched.csv, bootstrap_ci.csv, bootstrap_paired.csv (scores only); `all` runs it after the 10 s plots | about 12 min (10 s) |
| `uv run tsfm-ad p2 --config configs/phase2.yaml [--stage prepare\|forecast\|evaluate\|redteam\|plot\|mps-check\|all] [--smoke] [--runs a,b]` | Phase 2 (PLAN.md 15): LANL per-minute series (DuckDB), injections, Chronos-2 mv / mv-cov / FF / frozen / dual and baselines, detection curves, red team; cache in cache/lanl, results in results/phase2 | prepare about 5 min; full about 4.7 h on a shared MPS GPU (REPORT.md 10.3) |
| `uv run --extra paper tsfm-ad paper` | the paper (D153): tables and figures into results/paper from results/ and the Phase 2 cache (no model call), then paper/paper.pdf (Typst; skipped without the extra) | about 4 s |
| `uv run tsfm-ad smoke` | whole chain on the 10 s and 1 s smoke slices (Chronos-2), then the MPS check | about 32 min on CPU from scratch (12 min the 4 prepend runs at T = 8,192, 13 min the 1 s rolling and FF runs); under 10 s when cached |
| `uv run tsfm-ad all [--optional [10s\|all]]` | smoke, then the Chronos-2 matrix of PLAN.md 14.7 (exp 4 deferred); resumable | about 4.8-4.9 h of inference on MPS plus smoke and scoring, about 5.5 h (CPU about 1.8x slower); `--optional 10s` (prepend, FF max30/120) about 2.6-2.9 h more; a bare `--optional` also the 1 s block, about 26.4-27.2 h more on MPS (D124, D131) |

Long runs: on AC power under `caffeinate -dims`, in the background with a log. Failures: `cache/logs/<cmd>_failures.csv`.
