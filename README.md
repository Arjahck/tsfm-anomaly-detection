# Zero-shot time-series foundation models as anomaly detectors

This repository holds the code and the write-up of a study on one question: can a time-series foundation model (a
forecaster pretrained on many series and used without training) work as an anomaly detector for security data?
I ran Chronos-2 (`amazon/chronos-2`, 119M parameters, Apache 2.0) zero-shot as a rolling-forecast detector on two
datasets:

- **HAI 21.03:** industrial control data, 79 sensor and actuator tags, 50 labelled attacks.
- **LANL:** 13 per-minute series built from 1.05 billion enterprise authentication events, with 144 injected
  anomalies (silences, brute-force bursts, slow ramps and baseline shifts).

**Read the write-up:** [Time Series Foundation Model detectors are change detectors, like any rolling
forecast](https://arjahck.github.io/tsfm-anomaly-detection/) (also in this repository as [BLOG.md](BLOG.md)).

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
and configs (`configs/timestral/`) are kept but switched off, and no result comes from a Timestral model.

## Layout

| path | content |
| --- | --- |
| `src/tsfm_ad/` | the pipeline: data preparation, forecasting, scoring, evaluation, baselines, plots and the LANL phase (`p2*.py`) |
| `configs/` | one YAML per run; `base.yaml` holds the shared settings |
| `tests/` | 121 tests for the result-critical code |
| `vendor/TaPR/` | the official TaPR code (MIT), unmodified, vendored because it has no package |
| `BLOG.md`, `figures/` | the write-up and its two figures |
| `index.md`, `_layouts/`, `_config.yml` | the GitHub Pages site that shows the blog |

## Setup

Needs macOS or Linux, [uv](https://docs.astral.sh/uv/) and about 20 GB free disk for the forecast cache.

```bash
uv sync                                  # Python 3.12, chronos-forecasting 2.3.2, torch 2.14.1, polars, ...
```

**HAI:** release 21.03 from https://github.com/icsdataset/hai (folder `hai-21.03`, 8 `.csv.gz` files) goes to
`data/hai/hai-21.03/`.

**LANL:** `auth.txt.gz`, `flows.txt.gz` and `redteam.txt.gz` from https://csr.lanl.gov/data/cyber1/ (after a short
form: email and intended use) go to `data/lanl/`.

The Chronos-2 weights (revision pinned in `configs/base.yaml`, about 480 MB) download from Hugging Face into
`cache/hf/` on the first forecast. `data/`, `cache/` and `results/` are git-ignored; no dataset is redistributed here.

## Reproduce Phase 1 (HAI)

```bash
uv run pytest -q                          # 121 tests, about 10 s
uv run tsfm-ad smoke                      # the whole chain on two 2 h slices; about 32 min on CPU
uv run tsfm-ad all                        # smoke, then the Phase 1 matrix; about 5.5 h on an Apple GPU (MPS)
uv run tsfm-ad all --optional 10s         # also prepend and Forecast Fallback with 30/120-step exits; 2.6-2.9 h more
uv run tsfm-ad all --optional             # also the 1 s comparison; about 29 h more
```

Run long commands on AC power and keep the machine awake (`caffeinate -dims uv run tsfm-ad all`). `all` is
resumable: every forecast already in `cache/` is skipped, and scoring and evaluation are skipped when their inputs,
settings and code are unchanged. On CPU (`--device cpu`) runs take about 1.8 times longer.

The settings compared in the blog that are not in `all`. After each `forecast`, run `score` and `evaluate` with the
same `--config`:

```bash
# a new forecast every minute (H = 6) at 10 s
uv run tsfm-ad forecast --config configs/res10s_uni_h6.yaml
# the papers' setting: 1 s with a 128-step history, Forecast Fallback variants, and the 10 s control
for c in res1s_uni_c128 res1s_ff_interp_block_c128 res1s_ff_interp_block_c128_max30 res1s_ff_interp_block_c128_max120 \
    res10s_uni_c128; do uv run tsfm-ad forecast --config configs/$c.yaml; done
uv run tsfm-ad baselines --config configs/res1s_uni.yaml
# chronos-2-small: the device check on the smoke slice, then uni rolling on calib + test
uv run python -c "from tsfm_ad import model_chronos2_small as s, mps_check; from tsfm_ad.pipeline import CONFIGS, load_config, mps_csv; s.install(); mps_check.check_and_write(load_config(CONFIGS / 'smoke_small.yaml'), None, 'uni', mps_csv())"
for s in calib test; do uv run tsfm-ad forecast --config configs/opt_small_uni.yaml --split $s; done
# methods at equal false-alarm rates, paired bootstrap intervals, forecast accuracy
uv run tsfm-ad compare --config configs/base.yaml
```

## Reproduce Phase 2 (LANL)

```bash
uv run tsfm-ad p2 --config configs/phase2.yaml --stage prepare     # DuckDB scans of the gzip files -> per-minute series
uv run tsfm-ad p2 --config configs/phase2.yaml --smoke             # 2 test days: device check, forecasts, evaluation, plots
uv run tsfm-ad p2 --config configs/phase2.yaml --stage all         # 3 seeds x 17 test days, red team, figures (about 4.7 h)
uv run tsfm-ad p2 --config configs/phase2_flows.yaml --stage all \
    --runs mv,mv-cov,mv-frozen,lastvalue,seasonal-naive,robustz    # flows sub-study on days 0-14
```

Every stage after `prepare` reads the cache only and skips cached parts.

## Commands

Every command: `uv run tsfm-ad <cmd> --config configs/<file>.yaml [--split calib|calib2|test|ref|all] [--device cpu|mps]`.

| command | does |
| --- | --- |
| `prepare` | read HAI, drop constant tags, downsample, normalize, cut the splits |
| `forecast` | Chronos-2 inference into the cache (rolling, Forecast Fallback, frozen, cf-onset per the config); prints a time estimate first |
| `baselines` | last value, median of the last hour and seasonal reference day into the cache |
| `score` | channel scores, aggregation across channels, thresholds from calibration data (cache only) |
| `evaluate` | ROC-AUC, PR-AUC, TaPR, onset / interior / offset coverage and chance levels (scores only) |
| `compare` | the methods at equal false-alarm rates and paired bootstrap intervals |
| `plot`, `restart-plot` | figures from the cache and the result files |
| `p2` | Phase 2 on LANL: `--stage prepare`, `forecast`, `evaluate`, `redteam`, `plot` or `all`; `--smoke` for 2 test days |
| `smoke` | the whole chain on two small slices, then the device check |
| `all` | smoke, then the Phase 1 matrix; `--optional` adds the extra settings |

## Data and credits

- **HAI:** the HAI security dataset, release 21.03 (https://github.com/icsdataset/hai).
- **LANL:** Kent, A. D. Comprehensive, Multi-Source Cyber-Security Events. Los Alamos National Laboratory, 2015,
  doi 10.17021/1179829 (https://csr.lanl.gov/data/cyber1/).
- **Chronos-2:** `amazon/chronos-2` and `autogluon/chronos-2-small` on Hugging Face, Apache 2.0.
- **TaPR:** https://github.com/saurf4ng/TaPR, MIT, vendored unmodified.
- **Papers tested:** Uray et al. 2026 (https://arxiv.org/abs/2607.12454) and Lowe, Fung and Bauer 2026
  (https://clementfung.github.io/gallery/papers/fmsd26-tsfm.pdf).

Built by Arthur Rapp with Claude (Anthropic) through Claude Code.
