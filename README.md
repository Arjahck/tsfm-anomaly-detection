# Zero-shot time-series foundation models as anomaly detectors

This repository holds the code, results and write-up of a study on one question: can a time-series foundation model
(a forecaster pretrained on many series and used without training) work as an anomaly detector for security data?
I ran Chronos-2 (`amazon/chronos-2`, 119M parameters, Apache 2.0) zero-shot as a rolling-forecast detector on two
datasets:

- **HAI 21.03:** industrial control data, 79 sensor and actuator tags, 50 labelled attacks.
- **LANL:** 13 per-minute series built from 1.05 billion enterprise authentication events, with 144 injected
  anomalies (silences, brute-force bursts, slow ramps and baseline shifts).

## Read first

- [BLOG.md](BLOG.md): the write-up, "Time Series Foundation Model detectors are change detectors, like any rolling
  forecast".
- [EXPLANATION.md](EXPLANATION.md): the full explanation of both phases, from the papers and the data to the
  methods, the runs and every result.
- [paper/paper.pdf](paper/paper.pdf): the paper on the contamination share.
- [REPORT.md](REPORT.md): the full results of both phases. Every number points to a file in `results/`.

## The findings in short

- **The detector sees changes.** On LANL, Chronos-2 alarmed on 36.4 % of the minutes at the start of an anomaly and
  on 28.8 % of the minutes after its end, but on 0.4 % inside it, no more than on normal minutes (0.5 %).
- **Any rolling forecast does this.** The last value (a forecast that repeats the most recent observation) shows the
  same shape: 31.6 % at the start, 1.8 % inside.
- **The contaminated share decides how much of an attack is missed.** It is the share of attack steps forecast from a
  context that already holds the attack. On HAI with a new forecast every 5 minutes it is 24.8 %, and the inside of
  an attack alarms as often as its start (29.0 % against 28.0 %). With a new forecast every minute it is 69.8 %, and
  interior coverage drops to 7.9 %.
- **Protecting the context costs false alarms.** Forecast Fallback (Lowe et al.), a frozen reference and a dual score
  raised interior coverage on LANL to 31–34 %, at 42 to 255 false alarms per series-day against 6.7.
- **Chronos-2's edge is fewer false alarms:** 1.2 false-alarm steps per hour on HAI against 2.8 for the last value,
  and 6.7 per series-day on LANL against 11.0.

*Note:* every result is a Chronos-2 result. The project was first planned around Mistral's Timestral. Its code paths
and configs (`configs/timestral/`) are kept but switched off, and no result here comes from a Timestral model.

## Layout

| path | content |
| --- | --- |
| `src/tsfm_ad/` | the pipeline: data preparation, forecasting, scoring, evaluation, baselines, plots, the LANL phase (`p2*.py`) and the paper (`paper.py`) |
| `configs/` | one YAML per run; `base.yaml` holds the shared settings |
| `results/` | result CSVs and figures: `phase1/` (HAI), `phase2/` (LANL), `paper/`, `smoke/` |
| `figures/` | the two figures of BLOG.md |
| `paper/` | the paper source (Typst), its references and the PDF |
| `tests/` | 121 tests for the decision code |
| `vendor/TaPR/` | the official TaPR code (MIT), unmodified |
| `brief.md`, `PLAN.md`, `CLAUDE.md` | the project brief, the implementation plan with every numbered decision (D1, D2, ...), and the working rules for Claude Code |

## Setup

Needs macOS or Linux, [uv](https://docs.astral.sh/uv/) and about 20 GB free disk for the forecast cache.

```bash
uv sync                                  # Python 3.12, chronos-forecasting 2.3.2, torch 2.14.1, polars, ...
```

Data: HAI 21.03 from https://github.com/icsdataset/hai (folder `hai-21.03`, 8 `.csv.gz` files) goes to
`data/hai/hai-21.03/`. The Chronos-2 weights (`amazon/chronos-2`, revision pinned in `configs/base.yaml`, about
480 MB) download from Hugging Face into `cache/hf/` on the first forecast, and are read offline after that. Neither
dataset is redistributed here; `data/` and `cache/` are git-ignored.

Timestral is not installed by default (optional extra `timestral`) and is refused at load time unless
`TSFM_ALLOW_TIMESTRAL=1` is set. Its configs in `configs/timestral/` never run in `smoke` or `all`.

The official TaPR (`vendor/TaPR/TaPR.py`, unmodified, sha256 checked) is vendored because it has no package.

## Reproduce Phase 1 (HAI)

```bash
uv run pytest -q                          # 121 tests, about 12 s
uv run tsfm-ad smoke                      # whole chain on two 2 h slices + the MPS check; about 32 min on CPU
uv run tsfm-ad all                        # smoke, then the Phase 1 matrix (PLAN.md 14.7); about 5.5 h on MPS
uv run tsfm-ad all --optional 10s         # also prepend and FF max30/120; about 2.6-2.9 h more on MPS
uv run tsfm-ad all --optional             # also those, then the 1 s comparison; about 29.2-29.7 h more on MPS
```

Run long commands on AC power and keep the machine awake (`caffeinate -dims uv run tsfm-ad all`); on battery the
Mac sleeps and a run crawls. `all` is resumable: every forecast file already in `cache/` is skipped, and score and
evaluate are skipped when their inputs, settings and code are unchanged. A failing run is logged, the next one goes
on, and the command exits 1 at the end with the list (also in `cache/logs/all_failures.csv`).

Expected runtimes (PLAN.md 14.8, from the latency measured on HAI): Chronos-2 passes the relative D54 MPS check
(D130, `results/phase1/mps_check.csv`), so `configs/base.yaml` runs on MPS; `--device cpu` is about 1.8x slower.
The default matrix takes about 4.8-4.9 h of inference on MPS (8.4-8.7 h on CPU). A 1 s run costs about 13.2 h on
MPS (23.7 h on CPU), so the 1 s comparison block runs only with `--optional` (D124, D131). Experiment 4 (model sizes) is
deferred while Timestral is paused: Chronos-2 has one size with the 21 cache quantile levels. Scoring, TaPR and
figures add minutes per run at 10 s and several minutes per run at 1 s. Each forecast prints a measured estimate
before it starts. The size of the D128 constant-row guard against the raw model (`d128`, D129) is already in
`results/phase1/d128_effect.csv` for the CPU hashes only; on MPS (D130) `all` measures it again, about 0.2 h.

Three sensitivities added after the first report (not in `all`):

```bash
# chronos-2-small (D136): the MPS check on the 10 s smoke slice, then uni rolling on calib + test (about 13 min on MPS)
uv run python -c "from tsfm_ad import model_chronos2_small as s, mps_check; from tsfm_ad.pipeline import CONFIGS, load_config, mps_csv; s.install(); mps_check.check_and_write(load_config(CONFIGS / 'smoke_small.yaml'), None, 'uni', mps_csv())"
for s in calib test; do uv run tsfm-ad forecast --config configs/opt_small_uni.yaml --split $s; done
for c in score evaluate diagnostics; do uv run tsfm-ad $c --config configs/opt_small_uni.yaml; done
# the paper's setting (D137): 1 s, history 128 steps, H = 30: rolling, cf-onset, 1 s baselines, ff-interp-block
for c in res1s_uni_c128 res1s_ff_interp_block_c128 res1s_ff_interp_block_c128_max30 res1s_ff_interp_block_c128_max120 \
    res10s_uni_c128; do uv run tsfm-ad forecast --config configs/$c.yaml; done       # the last one: the 10 s control
uv run tsfm-ad baselines --config configs/res1s_uni.yaml   # then score + evaluate each run as in pipeline.run_chain
# option B (D138): 10 s, H = 6, a new forecast every minute (283 min on a shared MPS GPU), then score + evaluate
uv run tsfm-ad forecast --config configs/res10s_uni_h6.yaml
uv run tsfm-ad compare --config configs/base.yaml          # paired bootstrap, equal false alarms, forecast accuracy
```

Outputs: result CSVs in `results/phase1/`, figures in `results/phase1/figures/` (1 s figures in
`results/phase1/figures/hai2103-1s/`), smoke outputs in `results/smoke/`. Forecasts, scores and prepared data stay
in `cache/` (git-ignored).

## Reproduce Phase 2 (LANL)

The LANL files come from csr.lanl.gov/data/cyber1/ after a short form (email and intended use); put `auth.txt.gz`,
`flows.txt.gz` and `redteam.txt.gz` in `data/lanl/` (PLAN.md D139). Phase 2 has its own config, `configs/phase2.yaml`.

```bash
uv run tsfm-ad p2 --config configs/phase2.yaml --stage prepare     # DuckDB scans of the gzip files -> per-minute series
uv run tsfm-ad p2 --config configs/phase2.yaml --smoke             # 2 test days: MPS check, forecasts, evaluation, plots
uv run tsfm-ad p2 --config configs/phase2.yaml --stage all         # 3 seeds x 17 test days, red team, figures
uv run tsfm-ad p2 --config configs/phase2_flows.yaml --stage all \
    --runs mv,mv-cov,mv-frozen,lastvalue,seasonal-naive,robustz    # flows sub-study (D149), as reported: no mv-ff
```

Outputs in `results/phase2/` (injection manifest, thresholds, detections, false alarms, curves, red team, figures);
forecasts in `cache/lanl/`. Every stage after `prepare` reads the cache only and skips cached parts.

## Build the paper

`paper/paper.pdf` ("Contamination Share: Why Zero-Shot Forecasting Detectors See the Start of an Attack and Not the
Rest", PLAN.md D153) is built from the result files and the cached LANL forecasts, with no model call:

```bash
uv run --extra paper tsfm-ad paper      # results/paper/ (tables, figures), then paper/paper.typ -> paper/paper.pdf
```

Without the `paper` extra (Typst) the command still writes the tables and figures and skips the PDF.

## Commands

Every command: `uv run tsfm-ad <cmd> --config configs/<file>.yaml [--split calib|calib2|test|ref|all] [--device cpu|mps]`.

| command | does | runtime |
|---|---|---|
| `prepare` | read HAI, drop constant tags, downsample, normalize, cut segments; channels.csv, attacks.csv, splits.csv | about 2 s per resolution |
| `forecast` | Chronos-2 inference into the cache (rolling, FF, frozen, prepend, cf-onset per the config); prints an estimate first | seconds (smoke) to about 1.7 h (10 s) or 24 h (1 s) on CPU |
| `baselines` | robustz, lastvalue and seasonal-refday quantiles into the cache | seconds at 10 s, about a minute at 1 s |
| `score` | channel scores, aggregation per channel set, thresholds from calib (cache only) | seconds at 10 s |
| `evaluate` | AUCs, TaPR, point metrics, segments, h strata, cf-onset, FF attribution (scores only) | seconds at 10 s, minutes at 1 s |
| `select --stage base\|best` | the D21 pick on test metrics, written to selection.csv | under 1 s |
| `plot` | figures from the cache and the results CSVs | seconds |
| `restart-plot` | `results/phase1/figures/restart_timeline.png`: attack A402 with a forecast every 5 minutes (H = 30) and every minute (H = 6), bands, scores, thresholds and the false-alarm rates (D154; cache and results only) | seconds |
| `d128` | the D128 guard's effect: adapter vs raw Chronos-2 on the calls with a constant row (rolling in-file, cf-onset, frozen), `d128_effect.csv` and `d128_effect_channels.csv`; `all` runs it after exp 2 and 3b | seconds (smoke), about 1 min (10 s uni) to about 17 min (10 s mv-lit) on CPU |
| `diagnostics` | quantile crossings (D119), D128 constant rows and forecast band widths per split into `quantile_diagnostics.csv`; `all` and `smoke` write it with `latency.csv` | seconds (10 s) |
| `compare` | the methods at matched false-alarm rates (threshold from the test labels, evaluation only) and paired bootstrap intervals into `fa_matched.csv`, `bootstrap_ci.csv`, `bootstrap_paired.csv` (D135, scores only); `all` runs it after the 10 s plots | about 12 min (10 s) |
| `p2` | Phase 2 on LANL (`--config configs/phase2.yaml`): `--stage prepare` (DuckDB scans to per-minute series), `forecast`, `evaluate`, `redteam`, `plot`, `mps-check` or `all`; `--smoke` = 2 test days; `--runs mv,mv-cov,...` limits the forecast runs; `configs/phase2_flows.yaml` = flows sub-study | prepare about 5 min; full forecasts about 4.7 h on a shared MPS GPU (REPORT.md 10.3) |
| `paper` | the paper (PLAN.md D153): tables and figures into `results/paper/` from the result files and the Phase 2 cache, no model call; with `uv run --extra paper` also `paper/paper.pdf` | about 4 s |
| `smoke` | the whole chain on both smoke slices, then the MPS check (ignores `--config`) | about 32 min on CPU from scratch (12 min of it the 4 prepend runs at T = 8,192, 13 min the 1 s rolling and FF runs); under 10 s when cached |
| `all [--optional [10s\|all]]` | smoke, then the Phase 1 matrix of PLAN.md 14.7 (ignores `--config`); `10s` adds prepend and FF max30/120, a bare `--optional` also the 1 s block | about 5.5 h on MPS (9.5 h on CPU); `10s` about 2.6-2.9 h more, the 1 s block about 26.4-27.2 h more on MPS |

Configs (`configs/`): `base.yaml` (shared settings, model `chronos2`), `smoke.yaml`, `smoke_1s.yaml`, one per planned
run (`exp1_*`, `exp2_*`, `exp3*`, `exp5_baselines`, `res10s_uni_ff`, `res1s_*`) and the optional `opt_*`.
Configs with `setup: selected` or `variant.kind: selected` read their pick from `results/phase1/selection.csv`.

## Data and credits

- **HAI:** the HAI security dataset, release 21.03 (https://github.com/icsdataset/hai).
- **LANL:** Kent, A. D. Comprehensive, Multi-Source Cyber-Security Events. Los Alamos National Laboratory, 2015,
  doi 10.17021/1179829 (https://csr.lanl.gov/data/cyber1/).
- **Chronos-2:** `amazon/chronos-2` and `autogluon/chronos-2-small` on Hugging Face, Apache 2.0.
- **TaPR:** https://github.com/saurf4ng/TaPR, MIT, vendored unmodified.
- **Papers tested:** Uray et al. 2026 (https://arxiv.org/abs/2607.12454) and Lowe, Fung and Bauer 2026
  (https://clementfung.github.io/gallery/papers/fmsd26-tsfm.pdf).

Built by Arthur Rapp with Claude (Anthropic) through Claude Code.
