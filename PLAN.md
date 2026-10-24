# PLAN: Phase 1, Timestral on HAI 21.03

Written 2026-10-19. This is the single document the implementers follow. `brief.md` wins over this file. Where this
file fills a gap the brief leaves open, the choice is logged in section 13 (D1, D2, ...). Where it reads the brief
in a way Arthur may not intend, it says so in the Open questions.

---

## 0. Status

- 2026-10-19: Arthur asked in-session to "plan, prepare, execute, validate the phase 1 completly". He waived the
  PLAN.md review stop for Phase 1. Phase 1 runs end to end from this plan without a pause.
- The second hard stop stays (CLAUDE.md "Who decides"): after the Phase 1 `REPORT.md`, stop and wait for Arthur's OK.
  No Phase 2 code before that.
- Deviations from the brief still need Arthur. This plan follows the brief literally for every headline run, with one
  logged exception: experiment 1 forecasts 51 of the 57 non-constant channels (D39). The literal 57-channel run is a
  labelled secondary (`uni57`), and Q17 asks Arthur. Where the research suggests something else, the alternative runs
  as a labelled secondary variant or waits in the Open questions. A non-brief setup never becomes the base of
  experiments 3 and 4 (D21).
- 2026-10-20: revised after a methodology, API and completeness critique (30 issues, all checked against the sources).
  Revised: D8, D15, D21, D24, D25, D28, D29, D34, D37. New: D39-D59, Q17. The changes are in place in each section.
- Repo state: `git log` shows one commit, `8134f2c P0: project brief, CLAUDE.md, gitignore`. No code yet.
- HAI 21.03 is in `data/hai/hai-21.03/` (8 `.csv.gz` files) with `data/hai/README.md` and
  `data/hai/hai_dataset_technical_details.pdf`.
- 2026-10-20, integration: implementation steps 1-6 are done and `tsfm-ad smoke` passes at 10 s and 1 s. The MPS
  check failed the D54 tolerance, so every headline run uses CPU (D110). Next: step 7, `tsfm-ad all`. (Timestral;
  superseded by the model switch below.)
- 2026-10-20, model switch: **Timestral is paused** for licence reasons (CLAUDE.md). Arthur decided that Phase 1
  runs on `amazon/chronos-2` (Apache 2.0) through the same pipeline; section 14 and D117-D128 hold the API facts,
  the independence check, the run matrix and the estimate. The adapter, the Timestral guard, 100 tests and `tsfm-ad smoke` passed on
  Chronos-2 at 10 s and 1 s (32 min on CPU from scratch, 7 s cached). The Chronos-2 D54 check fails the strict rule
  in every row, only through `P1_PCV02Z`, so every headline run uses CPU (D121). Next: step 7, `tsfm-ad all`
  (about 9.5 h on CPU; the 1 s block runs only with `--optional`, D124).
- 2026-10-20, review 2 of the switch: two minor findings, both confirmed. (1) The size of the D128 constant-row guard
  on CPU against the raw model was not recorded; `tsfm-ad d128` now measures it (D129) and 14.5 / 14.9 item 5 give
  it: for the mv setups it is not a rounding-level fix (up to 65 z on `P1_PCV02Z` in test, band scores up to 3.4;
  Q22). (2) The optional total of 14.8 was attributed to the wrong base; corrected to 52.5 / 53.3 h on CPU.
  104 tests and `tsfm-ad smoke` pass.
- 2026-10-20 12:40, Q18 answered: Arthur wants the main matrix, the 10 s optional runs and `REPORT.md` done by
  midnight and accepted a relative MPS tolerance. The D54 rule becomes relative (D130) and every Chronos-2 row
  passes, so every headline run moves to MPS. The CPU `all` started at 12:23 was stopped at about 13:10 (exp 1 uni
  calib and calib2 and test1 done on CPU; they stay in the cpu cache directory, nothing deleted). The smoke stays on
  CPU (D132). `all --optional 10s` adds prepend and
  FF max30/120 before the tables and plots; the 1 s block runs after it with `all --optional` (D131).
- 2026-10-21 08:00, **Phase 1 signed off by Arthur** (option B, D138, still running, goes into REPORT.md as an
  addendum). Phase 2 starts (section 15). Arthur lifted the LANL manual-download rule and approved submitting the
  LANL download form with his email and a usage note (D139); auth, flows and redteam are downloaded into data/lanl/.
- 2026-10-21 14:12, option B and the full Phase 2 run (auth main study and flows sub-study) finished; REPORT.md
  4.20 (B) and section 10 (Phase 2) written from `results/phase1/` and `results/phase2/`; chance levels added
  after the run (D151).
- 2026-10-20 19:50, Arthur defers the 1 s block (D134): when `all --optional 10s` ends, `REPORT.md` is written
  from the 10 s results first; then Arthur and Claude decide how to continue. The 1 s block is not started tonight.

Implementation order. Commit after each step, message `P1: <what works now>`:

1. Scaffold: `pyproject.toml`, `uv.lock`, `vendor/TaPR/`, `configs/base.yaml`, `configs/smoke.yaml`, empty package.
2. `prepare` plus tests (downsampling, labels, splits, normalization, attack strata). Commit
   `configs/hai2103_attacks_pdf.csv` (D56).
3. `forecast` (univariate) plus cache plus `tests/test_forecast.py`, then the smoke run. Check MPS against CPU on the
   smoke slice for every size and setup that will run on MPS (D15, D54).
4. `score` and `evaluate` (AUCs, TaPR, segments) plus tests.
5. Multivariate, Forecast Fallback, frozen, dual, `cf-onset` and baselines plus tests. Smoke all of them, at 10 s and
   at 1 s (D59).
6. `select` and `plot`. `smoke` runs the whole chain.
7. Full runs in the order of section 8. Commit the result CSVs after each experiment.
8. `REPORT.md`, `README.md`, and the CLAUDE.md "Layout" and "Commands" sections. Commit. STOP for Arthur.

---

## 1. Sources

Research notes (session scratchpad, may be deleted later; the key facts are restated in this file):
`/private/tmp/claude-501/-Users-arthurrapp-Documents-07-Projects-TSFM-security-anomaly-detection/26bba48b-c154-4355-9f45-1e60f947c076/scratchpad/research/`
with `timestral_api.md`, `papers.md`, `hai_data.md`, `tapr.md`, `hai_channels.csv`, `hai_attacks.csv`.
Below, `SP` is the scratchpad root
`/private/tmp/claude-501/-Users-arthurrapp-Documents-07-Projects-TSFM-security-anomaly-detection/26bba48b-c154-4355-9f45-1e60f947c076/scratchpad`.

Citation keys used in this file:

| key | what |
|---|---|
| `TS:file:L` | github.com/mistralai/timestral at commit `a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff` (2026-10-15, the only commit on `main`), path and lines |
| `HF-209M:L` | `README.md` of huggingface.co/mistralai/Timestral-209M at revision `9874d252...`; the other three cards carry the same text minus the comparison table and usage section |
| `P:pNN` | probe script and output in `SP/timestral-probe/` (run on Python 3.12.13, torch 2.14.1) |
| `bench.csv` | `SP/timestral-probe/bench.csv` (102 timed rows) and `cov_cost.csv` |
| `HAI-R:L` | `data/hai/README.md`, line L |
| `HAI-PDF p.N` | `data/hai/hai_dataset_technical_details.pdf`, PDF page N |
| `probe NN` | `SP/hai-probe/NN_*.py`, outputs in `SP/hai-probe/out/` |
| `Lowe:fmsd:L` | Lowe, Fung, Bauer PDF, text line L of `SP/work/text/fmsd26.txt` |
| `Uray:tex:L` | Uray et al. LaTeX source `SP/dl/uray/src/2026-eurocast-mtsad-fm.tex`, line L |
| `TaPR.py:L` | official TaPR at commit `47d316127f6c96d2fb6e5e2acd91d61307de99ce` |

What was read:

| item | where | pin |
|---|---|---|
| Timestral code | https://github.com/mistralai/timestral | commit `a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`, package `timestral` 1.0.0 (`TS:pyproject.toml:6-7`) |
| Timestral-5M | https://huggingface.co/mistralai/Timestral-5M | revision `bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f`; 5,208,960 params |
| Timestral-28M | https://huggingface.co/mistralai/Timestral-28M | revision `49b26409ac87b5935539a5d8ffe7f397b720db47`; 27,821,184 params |
| Timestral-123M | https://huggingface.co/mistralai/Timestral-123M | revision `5a147287addda85f6acd8da3fb8858fe9af7e8f7`; 122,606,720 params |
| Timestral-209M | https://huggingface.co/mistralai/Timestral-209M | revision `9874d252ab0aae16f7f7c999f98f98d6ad7d8365`; 209,312,256 params |
| Timestral blog | https://mistral.ai/news/timestral | "Two-stage training" section |
| Uray et al. 2026 | https://arxiv.org/abs/2607.12454 (PDF and LaTeX source) | v1, 14 Jul 2026, EUROCAST 2026 preprint |
| Lowe, Fung, Bauer 2026 (the brief's "ICML 2026 paper") | https://clementfung.github.io/gallery/papers/fmsd26-tsfm.pdf; https://icml.cc/virtual/2026/71439 (poster) | PDF sha256 `8adc07ae09962f34ebb767c3957ce035b67ccb9791a927419af952912b0fed92` |
| OpenReview forum | https://openreview.net/forum?id=zKWdTO8ART | NOT ACCESSIBLE (403 browser challenge) |
| HAI dataset | https://github.com/icsdataset/hai, folder `hai-21.03` | repo commit UNCONFIRMED (files were placed without git metadata); file SHA-256 in `research/hai_data.md` "Sources" |
| HAI technical details | `data/hai/hai_dataset_technical_details.pdf` | document v4.0, May 2023 (`HAI-PDF p.1`) |
| TaPR | https://github.com/saurf4ng/TaPR (redirects to wshw4ng/TaPR) | commit `47d316127f6c96d2fb6e5e2acd91d61307de99ce`; `TaPR.py` sha256 `0ada5df354e6f8d06581c5b19eaf659cee656be8c0f3a22ac32f55c66e74b6b1` |
| HAICon 2020 scoring | Shin et al., CSET'21, https://cset21.isi.edu/papers/cset21-1.pdf, §4.1, §4.1.2 | |

Facts about the papers that shape this plan (`research/papers.md` §1-§5):

- They are two different papers by different groups. Neither cites the other.
- The brief's "ICML 2026 paper" is a poster at the 2nd ICML Workshop on Foundation Models for Structured Data (FMSD),
  not an ICML main-track paper (`Lowe:fmsd:44-46`; icml.cc/virtual/2026/71439).
- Neither paper uses HAI, TaPR or point-adjust. No number in either paper can be reproduced on HAI. Phase 1 tests
  their qualitative claim on a new dataset.
- Both papers use short windows. Uray: context w = 100, horizon 32 (`Uray:tex:398-401`). Lowe: input I in {32, 64, 128},
  H in {1, 16, 32} (Table 2).
- Both tune the F1 threshold on test labels (`Uray:tex:422-424`; `Lowe:fmsd:327-330`). We do not.
- No code was released for either paper. GitHub searches found no Forecast Fallback code (`research/papers.md` §3.7).

---

## 2. Timestral API facts and the exact calls

Timestral is paused (CLAUDE.md, D117). This section is kept for a later switch back; the Chronos-2 facts and calls
of the Phase 1 runs are in section 14.3.

### 2.1 Facts (all verified by reading the code; behaviour also checked on toys where marked P)

| fact | source |
|---|---|
| Install from git only; Python >= 3.10; deps torch >= 2.4, numpy >= 1.24, safetensors >= 0.4, huggingface_hub >= 0.23. No pandas, no DataFrame API. | `TS:README.md:36-46`; `TS:pyproject.toml:12-18`; GitHub issue #1 |
| Load: `TimestralForecaster.from_pretrained(repo, device="cpu", max_context=None, revision=..., cache_dir, token, local_files_only)`. No `dtype` argument. Only float32 was validated upstream. | `TS:src/timestral/forecaster.py:122-142`; `TS:src/timestral/loading.py:57-74` (line 66) |
| Call: `fc.forecast(context, prediction_length, observation_mask, past_covariates, known_covariates, categorical_past_covariates, categorical_known_covariates, symmetric_averaging=True, clip_nonnegative=True)`. | `TS:src/timestral/forecaster.py:160-231` |
| `context` is `(B, V, T)`, `(B, T)` or `(T,)`, numpy or torch. NaN or inf = missing. All series in a call share T and V. | `TS:README.md:78-79`; `TS:src/timestral/forecaster.py:233-244, 240`; P:p01 §1, §6, §9 |
| Output `Forecast.quantiles`: torch tensor `(B, V, H, 21)`, float32, on the model's device, sorted along the last axis. Only targets are returned. | `TS:src/timestral/forecaster.py:36-57, 316`; P:p01 §1 |
| V > 1 variates of one series are forecast jointly (variate attention). The B series of a call are independent. | `TS:README.md:79`; `TS:src/timestral/masks.py:121-146`; P:p01 §9-10 |
| Past-only covariates: `(B, C, T)`, exactly T long (AssertionError otherwise), per series, never forecast, never read the targets. | `TS:README.md:95-106`; `TS:src/timestral/masks.py:104-118`; P:p01 §11 |
| Known-future covariates: `(B, C, T + H)`. Rows of only 0/1 are treated as indicators. Not used in Phase 1. | `TS:src/timestral/forecaster.py:182-183`; `TS:src/timestral/model.py:135-151`; P:p01 §12 |
| Categorical covariates are target-encoded for V = 1 and passed as raw codes for V > 1. Not used in Phase 1 (no categorical tags survive the drop, section 3). | `TS:README.md:108-124`; `TS:src/timestral/covariate_encoding.py:1-56` |
| Context is silently capped at 32,768 steps (the most recent are kept). Any T >= 1 works; it is left-padded to a multiple of 32. | `TS:README.md:81`; `TS:src/timestral/forecaster.py:70-77, 373-376`; P:p01 §4 |
| One decode block covers up to 1,024 steps. H is rounded up to whole 32-step patches, so H = 30 costs the same as H = 32. | `HF-209M:69, 79`; `TS:src/timestral/forecaster.py:344, 396-456`; P:p01 §3 |
| Internal normalization: causal expanding mean/std per patch (float64) plus asinh. The forecast is affine-equivariant (~1e-5 relative), so z-scoring inputs does not change forecasts, except through `clip_nonnegative` and the absolute std floor `minimum_scale = 1e-6`. The floor binds only for contexts that are flat to below 1e-6 in input units. | `TS:src/timestral/scaler.py:14-101`, `:45` (`clamp(min=minimum_scale)`), also `:200`, `:224`; `"minimum_scale": 1e-06` in all four `config.json`; `TS:src/timestral/model.py:122-133, 227-229`; P:p01 §5; `research/timestral_api.md:211-213` |
| `symmetric_averaging=True` runs 2 forward passes (x and -x). Off halves latency but changes the forecast and departs from the published protocol. | `TS:src/timestral/forecaster.py:1-18, 220-227`; `TS:README.md:132-133`; P:p01 §3, §8 |
| `clip_nonnegative=True` clamps at 0 every series whose observed context is all >= 0. | `TS:src/timestral/forecaster.py:84-87, 228-230` |
| An all-NaN series silently returns all-zero quantiles. A constant series gives q05 == q95 (zero-width band). | P:p01 §6-7 |
| Deterministic on CPU (bitwise). Batch layout and device change results by ~1e-5. | P:p01 §2, §9; P:p03 |
| Shape checks are `assert`s. Never run inference with `python -O`. | `TS:src/timestral/forecaster.py:239, 297-299, 352, 364` |
| MPS fails out of the box (`Cannot convert a MPS Tensor to float64`). GitHub issue #4 is open. Our unofficial shim moves 3 float64 functions to CPU. On toys it matched CPU within 3.4e-5 on the univariate H = 30 path for all sizes. The multivariate and covariate paths were checked on 5M only. The transformer itself (incl. variate attention with the covariate masks) runs as MPS kernels whose shapes depend on model size, so every (size, setup) that runs on MPS is checked on HAI first (D54). | `TS:src/timestral/scaler.py:29`; P:p02, P:p03 (`p03_mps_shim_check.out`: multivariate and covariate rows exist for 5M only); `SP/timestral-probe/mps_shim.py:41-44`; `TS:src/timestral/masks.py:104-146` |
| All-NaN padding rows are not neutral (shift real rows by up to 0.026). Do not pad groups to merge calls. | P:p05 |
| Any covariate switches to a path that costs 2.1-2.5x more per row. | `TS:src/timestral/model.py:191-273`; `cov_cost.csv` |
| Post-training used "a mix of real and synthetic data". Whether HAI or other ICS data was included: UNCONFIRMED (GitHub issue #3 unanswered). | https://mistral.ai/news/timestral "Two-stage training" |
| Weights licence "Modified MIT": no rights if the monthly revenue of "your company (or that of your employer)" exceeds $20M. | huggingface.co/mistralai/Timestral-5M/raw/main/LICENSE line 8 (same in all 4 repos) |

### 2.2 Quantile levels

The 21 native levels are 0.01, 0.05, 0.10, 0.15, ..., 0.90, 0.95, 0.99 (`config.json` of each repo;
`TS:src/timestral/forecaster.py:36-57`). q05 and q95 are native: q05 = index 1, median = index 10, q95 = index 19.
`forecast.quantile(level)` accepts exact levels only. Nothing is interpolated. Cache column names are
`q01, q05, q10, q15, q20, q25, q30, q35, q40, q45, q50, q55, q60, q65, q70, q75, q80, q85, q90, q95, q99`.

### 2.3 Load (all experiments)

```python
from timestral import TimestralForecaster
fc = TimestralForecaster.from_pretrained(
    "mistralai/Timestral-28M",
    revision="49b26409ac87b5935539a5d8ffe7f397b720db47",   # from config, never "main"
    device=device,                                         # "mps" only after tsfm_ad.mps_shim.install()
    max_context=32768,
    cache_dir="cache/hf",
)
```

### 2.4 Univariate batch forecast (experiment 1)

```python
# Z: (51, L) float32, z-scored targets of one file; o = forecast origin (first step of the window)
ctx = Z[:, max(0, o - cap):o]                  # (B=51, T): 51 independent univariate series
f = fc.forecast(ctx, prediction_length=30, symmetric_averaging=True, clip_nonnegative=False)
q = f.quantiles[:, 0].cpu().numpy()            # (51, 30, 21)
```

### 2.5 Multivariate joint forecast with past-only covariates (experiment 2)

```python
# one call per process group g; never merge groups with NaN padding
T = min(o, cap)
tgt = Z_tgt[g][:, o - T:o][None]               # (1, V_g, T) continuous targets of process g
cov = Z_cov[g][:, o - T:o][None]               # (1, C_g, T) past-only covariates, exactly T long
f = fc.forecast(tgt, 30, past_covariates=cov if cov.shape[1] else None,
                symmetric_averaging=True, clip_nonnegative=False)
q = f.quantiles[0].cpu().numpy()               # (V_g, 30, 21); covariates are not returned
```

---

## 3. Data schema (HAI 21.03)

All facts from `research/hai_data.md` (probes 01-11) unless cited otherwise.

### 3.1 Files

Every file has 84 columns in the same order: `time`, 79 tags (38 P1, 22 P2, 7 P3, 12 P4), then `attack`,
`attack_P1`, `attack_P2`, `attack_P3`. Timestamps are `yyyy-MM-dd hh:mm:ss`, no timezone (timezone UNCONFIRMED).
Each file is a strict 1 s grid with no duplicates, nulls or NaN (probe 01; `HAI-R:L257`; `HAI-PDF p.37`).
Each file includes both endpoints, so rows = hours x 3,600 + 1.

| time order | file | rows | start | end | hours | gap to next |
|---|---|---|---|---|---|---|
| 1 | test1 | 43,201 | 2020-07-07 15:00:00 | 2020-07-08 03:00:00 | 12.00 | +36.0 h |
| 2 | test2 | 118,801 | 2020-07-09 15:00:00 | 2020-07-11 00:00:00 | 33.00 | 0 (last row = train1's first row) |
| 3 | train1 | 216,001 | 2020-07-11 00:00:00 | 2020-07-13 12:00:00 | 60.00 | -12.0 h (overlap) |
| 4 | test3 | 108,001 | 2020-07-13 00:00:00 | 2020-07-14 06:00:00 | 30.00 | +342.0 h |
| 5 | test4 | 39,601 | 2020-07-28 12:00:00 | 2020-07-28 23:00:00 | 11.00 | +35.83 h |
| 6 | test5 | 92,401 | 2020-07-30 10:50:00 | 2020-07-31 12:30:00 | 25.67 | +9.5 h |
| 7 | train2 | 226,801 | 2020-07-31 22:00:00 | 2020-08-03 13:00:00 | 63.00 | +33.0 h |
| 8 | train3 | 478,801 | 2020-08-04 22:00:00 | 2020-08-10 11:00:00 | 133.00 | n/a |

- Train and test interleave in time. test1 and test2 come before any train file.
- train1's last 12 h (2020-07-13 00:00:00 to 12:00:00) are identical on all 79 tags to test3's first 12 h.
  No attack is labelled there (probe 02).
- Documentation mismatches (report, do not fix): the PDF lists 78 tags for 21.03, the files have 79 (`HAI-PDF p.13-16, p.37`).
  The README and PDF give train3 as 229 h, the file holds 133 h (`HAI-R:L172-215`; `HAI-PDF p.2`).
- Three tags change inferred dtype between files (`P1_PCV02D`, `P3_LCP01D`, `P3_LCV01D`). Read all tags as Float64.

### 3.2 Labels

- Train: 0 positive rows in all four label columns (probe 03).
- Test: `attack` = 1 in 8,947 rows (2.23 %). `attack_P1` 7,037, `attack_P2` 1,864, `attack_P3` 958.
- In 179 rows `attack` = 1 with no process label (short-term "-ST" attacks). The reverse never happens.
- Ground truth = `attack`. Process labels are used for diagnostics only.

### 3.3 Attacks

- 50 events: test1 5, test2 20, test3 8, test4 5, test5 12. All 50 match the PDF timetable one to one
  (`HAI-PDF p.37-39`; probe 04). Ids A101-A512 follow the PDF numbering. Full table: `research/hai_attacks.csv`.
- Duration at 1 s: min 17, median 162.5, mean 178.9, max 422 s. Total 8,947 s.
- Longest: A202 (test2, 422 s, P1-PC-SP1PV1), A210 (test2, 421 s, P1-PC-CO1PV1), A302 (test3, 421 s,
  P1-PC-SP1PV1+P1-FC-SP1). Next is A403 (263 s). Shortest: A203 (17 s, P1-LC-CO1-ST7).
- Processes from labels: P1 23, P2 11, P1+P2 8, P1+P3 3, P2+P3 3, P3 2.
- HAI 21.03 has no long-term (> 10 min) attack scenario (`HAI-PDF p.27-29`).
- A209: PDF 159 s, labels 199 s. Which is right is UNCONFIRMED. We use the labels.
- At 10 s (label = max over the bin): all 50 events survive, none merge (minimum gap 1,433 s). Duration 3 to
  43 steps, median 17. 934 attack bins out of 40,200 (2.32 %).

### 3.4 Channel roles

Rule, applied at 1 s to the `fit` + `calib` rows only (train2, train3, train1 up to 2020-07-12 23:59:59, last row of
each file dropped; D57), in this order (`research/hai_channels.csv`). On these rows the counts and tag sets are the same
as on all train rows: the same 22 constant tags, the same 6 step tags, step change rates at most 0.147 %
(`P1_B3005`), lowest other rate 4.64 % (`P1_FCV02D`) (`SP/plan-scripts/roles_fitcalib.py` on train data only).
`test_data.py` asserts the counts.

1. **dropped**: constant over all fit + calib rows (1 unique value). 22 tags.
2. **step covariate** (the brief's "discrete" channels): changes on fewer than 1 % of 1 s fit + calib steps. 6 tags.
   Their change rates are 0.0014 % to 0.15 % (all train rows, `research/hai_channels.csv`). The next lowest channel
   changes on 4.7 % (`P1_FCV02D`).
3. **actuator command**: tag name ends in `D` and the PDF describes it as a command to a valve or pump
   (`HAI-PDF p.13-16`). 7 tags, all continuous in 21.03 (1,531 to 780,359 unique train values).
4. **continuous target**: everything else. 44 tags.

| process | dropped | step covariate | actuator command | continuous target |
|---|---|---|---|---|
| P1 (38) | P1_PCV02D, P1_PP01AD, P1_PP01AR, P1_PP01BD, P1_PP01BR, P1_PP02D, P1_PP02R, P1_STSP | P1_B2004, P1_B3004, P1_B3005, P1_B4002 | P1_FCV01D, P1_FCV02D, P1_FCV03D, P1_LCV01D, P1_PCV01D | P1_B2016, P1_B4005, P1_B400B, P1_B4022, P1_FCV01Z, P1_FCV02Z, P1_FCV03Z, P1_FT01, P1_FT01Z, P1_FT02, P1_FT02Z, P1_FT03, P1_FT03Z, P1_LCV01Z, P1_LIT01, P1_PCV01Z, P1_PCV02Z, P1_PIT01, P1_PIT02, P1_TIT01, P1_TIT02 (21) |
| P2 (22) | P2_ASD, P2_AutoGO, P2_Emerg, P2_MSD, P2_ManualGO, P2_OnOff, P2_RTR, P2_TripEx, P2_VTR01, P2_VTR02, P2_VTR03, P2_VTR04 | none | none | P2_24Vdc, P2_CO_rpm, P2_HILout, P2_SIT01, P2_SIT02, P2_VT01, P2_VXT02, P2_VXT03, P2_VYT02, P2_VYT03 (10) |
| P3 (7) | P3_LH, P3_LL | none | P3_LCP01D, P3_LCV01D | P3_FIT01, P3_LIT01, P3_PIT01 (3) |
| P4 (12) | none | P4_HT_PS, P4_ST_PS | none | P4_HT_FD, P4_HT_LD, P4_HT_PO, P4_LD, P4_ST_FD, P4_ST_GOV, P4_ST_LD, P4_ST_PO, P4_ST_PT01, P4_ST_TT01 (10) |

How each experiment uses the roles. The channel-set name is written to every results CSV (`channel_set`, D49):

| channel set | channels | used by |
|---|---|---|
| `uni51` | 44 continuous + 7 actuator commands = 51 | experiment 1 headline (no covariates, D39) |
| `uni57` | `uni51` + the 6 step tags = 57 (every non-constant channel) | experiment 1 brief-literal secondary (D39) |
| `mvlit34` | P1: 21 targets + 9 covariates (4 step, 5 actuator). P2: 10 targets, no covariates. P3: 3 targets + 2 actuator covariates. 34 scored targets. | experiment 2 headline (`mv-lit`) |
| `mvacttgt41` | P1: 26 targets + 4 step covariates. P2: 10 targets. P3: 5 targets. 41 scored targets. | experiment 2 secondary (`mv-acttgt`, D22) |
| `<set>-noPCV02Z` | the same set without `P1_PCV02Z` | every run is also scored on it; needed for frozen, dual and `seasonal-refday` (D50) |
| unused | P4_HT_PS, P4_ST_PS | kept in the prepared data; forecast and scored only in `uni57` (D23) |

All sets are subsets of the 57 non-constant channels, so a restricted view of a run is scoring only. `uni` runs can be
scored on `mvlit34` and `mvacttgt41` (reported as `uni@mv-lit-channels`, `uni@mv-acttgt-channels`). Baselines forecast
all 57 channels and are scored on every set a TSFM run uses (D49).

Facts behind the roles (`research/hai_data.md` §3-§4). The first two come from test attack windows; they explain the
data but no role is assigned because of them (D8, D39):

- Setpoint attacks are invisible in the recorded setpoints: `P1_B3004` and `P1_B3005` have zero range in their 13
  attack windows (probe 11; `HAI-PDF p.26-28` "hiding SP changes in HMI").
- Actuator commands move strongly in control-variable attacks, e.g. `P1_LCV01D` median max|z| 10.6 inside vs 1.9 before.
  28 of 50 attacks list a `*D` target (probe 11). As past-only covariates they are not scored. That is why `mv-acttgt`
  exists, and why it is test-informed (D8).
- Three dropped tags vary in test only during or just after attacks: `P1_PCV02D` (5 attacks), `P2_OnOff` and `P2_Emerg`
  (9 turbine trips). Dropping them, as the brief says, removes trivial evidence for 14 attacks. REPORT.md says so.
- Step setpoints change only in the PDF's benign schedule slots (03:00, 04:30, ..., 22:00; `HAI-PDF p.37`). The plant has
  a daily cycle.
- Known quirks: `P1_PCV02Z` has a persistent level shift (about 12.02 to 11.78) after A302 and A512, in data labelled
  normal; train2 and train3 sit at the lower level (probe 08-09). Its `fit` std is tiny: mean 11.7892, std 0.00485 at
  1 s and 0.00429 at 10 s. `calib` (mean 12.0189) therefore sits at about +47 (1 s) / +54 (10 s) fit-z, the
  `reference` day at about -0.3 fit-z (`SP/plan-scripts/roles_fitcalib.py`, train data only). The test files at
  about 12.02 sit at the `calib` level (`research/hai_data.md` §7). Rolling forecasts do not care (affine
  equivariance, section 2.1). Methods that compare with the `reference` day do (D50).
- Heavy-tailed transients in normal data: `P4_HT_FD` has 5,929 train rows beyond 6 sd, `P1_PIT01` 1,455 (probe 07-08).
  Redundant pairs with |r| > 0.98 exist (probe 10); all are kept.

---

## 4. Preprocessing

1. Read each file with polars. `time` parsed with `%Y-%m-%d %H:%M:%S`. All 79 tags as Float64, labels as Int8.
2. Drop the last row of every file (the `+1` endpoint row). Files then hold whole hours. This also removes the row that
   test2 shares with train1.
3. Drop the 22 constant tags.
4. Resolution, default 10 s (`resolution_s: 10`). Bin = `floor(time, 10 s)`. All files start on a 10 s boundary.
   - continuous targets and actuator commands: mean over the bin;
   - step covariates: last value in the bin;
   - `attack` and the three process labels: max over the bin.
5. Optional 1 s (`resolution_s: 1`): no aggregation, steps 2-3 only.
6. Normalization: per-channel z-score, `z = (x - mean) / std`, applied to targets and covariates.
   Statistics come from the **fit set** only: train2 + train3, all rows, at the run's resolution (section 5).
   They are written to `cache/<dataset>/prepared/norm_stats.parquet` and `results/phase1/channels.csv` (one row per
   channel and `resolution_s`).
7. Inputs are checked to be finite before every forecast call. HAI has no NaN. An all-NaN context would silently
   return zeros (section 2.1).

Step counts at 10 s after step 2: test1 4,320, test2 11,880, test3 10,800, test4 3,960, test5 9,240 (total 40,200);
train1 21,600, train2 22,680, train3 47,880.

---

## 5. Splits and warm-up

"Strict time-based split" cannot mean chronological order here: test1 and test2 come before every train file.
This plan reads it as the per-file roles of the dataset authors. No test row is used to fit normalization statistics
or thresholds, and no test score or test metric tunes any hyperparameter (none exists before the runs). Several design
choices did use inspection of test files, test labels or the PDF attack timetable. D8 lists them; REPORT.md copies the
list into "Threats to validity".

| segment | source | time range (1 s rows kept) | 10 s steps | role |
|---|---|---|---|---|
| `fit` | train2 + train3 | 2020-07-31 22:00:00 to 2020-08-03 12:59:59; 2020-08-04 22:00:00 to 2020-08-10 10:59:59 | 22,680 + 47,880 | normalization statistics, baseline error quantiles |
| `reference` | train3, last 24 h | 2020-08-09 11:00:00 to 2020-08-10 10:59:59 | 8,640 | frozen context (exp 3b), `seasonal-refday` reference day, `prepend` warm-up source |
| `calib` | train1, trimmed, as two pseudo-files | `train1a` 2020-07-11 00:00:00 to 23:59:59; `train1b` 2020-07-12 00:00:00 to 23:59:59 | 8,640 + 8,640 | detection thresholds, FF per-feature thresholds |
| `calib2` | train2, two full days, as two pseudo-files | `train2a` 2020-08-01 00:00:00 to 23:59:59; `train2b` 2020-08-02 00:00:00 to 23:59:59 | 8,640 + 8,640 | sensitivity thresholds only (D51); overlaps `fit`, labelled as such |
| excluded | train1 | 2020-07-13 00:00:00 to 12:00:00 | 4,320 | identical to test3's first 12 h, used nowhere as train data |
| `test` | test1..test5 | whole files minus the last row | 40,200 | evaluation only |

Why this split (D9, D10):

- `calib` does not overlap `fit`. Thresholds come from data the normalization never saw.
- train1 is recorded inside the test period, between test2 and test3. It shares the `P1_PCV02Z` level (about 12.02)
  of test1, test2, test4 and the start of test5. train2 and train3 sit at about 11.79 (probe 08). So `calib` looks more
  like the test files than any slice of train2 or train3 would. This choice used test-file values (no labels), so it is
  on the D8 list. The `calib2` sensitivity threshold (D51) shows how much it matters.
- The 12 h duplicate is cut from train1, not from test3. test3 keeps its full in-file history.
- `calib` is cut into two 24 h pseudo-files so its context lengths look like the test files'. Step-weighted mean
  in-file context: test about 4,700 steps, `calib` about 4,300 steps.

### Warm-up policy

Default `warmup.mode: in_file` (D11):

- The context at origin `o` is the same file's own history `[max(0, o - cap), o)`. No data from another file is used.
- The first `W` steps of every file (test and calib pseudo-files) are context only and are not scored.
  `W` = 1,500 s: 150 steps at 10 s, 1,500 steps at 1 s. `W` is a multiple of H = 30.
- No attack falls in the warm-up. In-file history before the first attack, in 10 s steps: test1 211 (A101),
  test2 282 (A201), test3 4,986 (A301), test4 258 (A401), test5 156 (A501). The tightest margin is A501, which starts
  6 steps into the first scored window. At 1 s the margin is 60 s (test5: 1,560 s of history). W was checked against
  these test-label positions, so it is on the D8 list.
- Why: it uses only real history, which is what the brief's "context = history before t" says. It adds no artificial
  discontinuity. Prepending other files would put a jump into the context 156 to 282 steps before the first attack
  (e.g. `P1_PCV02Z` 11.79 vs 12.02). And `calib` gets exactly the same treatment, so thresholds match the test regime.
- Cost of the choice: contexts are short early in each file (150 steps = 25 min at 10 s). The longest in-file context is
  11,880 steps (test2). At 10 s the 32,768 cap never binds.

Alternative `warmup.mode: prepend` (config option, optional run, section 8): prepend the last `cap` steps of train3
(ending 2020-08-10 10:59:50) before every test and calib file. Scored steps stay the same (`t >= W`), so metrics are
comparable. The junction joins unrelated recordings: the train3 tail was recorded 10 to 34 days after the test files and
about 30 days after `calib`. REPORT.md documents it as such. No attack is lost.

test3 is truly contiguous with test2 + train1, but its predecessor holds 20 test2 attacks and the duplicated 12 h.
That history is not used.

---

## 6. Forecasting loop

- Rolling per file (test and calib alike). Origins `o = W, W + H, W + 2H, ...` while `o < L`. The window is
  `[o, o + H)`; the context ends at `o - 1`. Every scored step `t >= W` gets exactly one forecast, with horizon index
  `h = t - o + 1` in 1..30. All test and calib file lengths minus W are multiples of 30 at both resolutions.
- Context cap `cap = 32768` at 10 s (the model maximum, never binding in-file). At 1 s the planned runs use
  `cap = 8192` (D12); `cap = 32768` is an optional run.
- Horizon `H = 30` (5 min at 10 s, 30 s at 1 s), stride H, as in the brief. H = 30 costs the same as 32 (section 2.1).
- Arrays (D58). `rolling` keeps two arrays per file. `Z_obs` holds the prepared data. It is read-only and is the only
  source of `y_true`, the FF trigger statistic and every score. `Z_ctx = Z_obs.copy()` (targets only; covariates
  are always read from `Z_obs`) is the only array contexts are sliced from. A context-protection hook has the signature
  `hook(o, q50 (C, H), y (C, H)) -> mask (C, H) bool`. `rolling` applies `Z_ctx[:, o:o+H][mask] = q50[mask]` after
  the window is forecast and observed. The hook holds state only and never touches an array. `Z_ctx` is rebuilt for
  every file and every run, so nothing carries over between variants inside `all`.
- Flags: `symmetric_averaging=True` (upstream default and benchmark protocol), `clip_nonnegative=False` (inputs are
  z-scores; clipping at 0 has no meaning there), float32, no `observation_mask` (no missing data).
- Batching:
  - exp 1: one call per origin, B = 51 univariate rows (57 for `uni57`).
  - `cf-onset`: one call per attack (per process group for exp 2 setups), H = L + N.
  - exp 2: three calls per origin, one per process group. Groups are never merged (NaN padding is not neutral).
  - No batching across origins. At T >= 8,192 throughput is flat from B = 16 (`bench.csv`), and B = 51 already
    covers short contexts. FF cannot batch origins anyway.
- Device (D15, D54): `mps` with the unofficial shim `src/tsfm_ad/mps_shim.py` (our own re-implementation of
  `SP/timestral-probe/mps_shim.py`) if the smoke check passes. The check runs during the smoke step, before any
  headline run, on the smoke slice, CPU vs MPS, for every (size, setup) that will run on MPS: 5M uni and mv-lit;
  28M uni, uni57, mv-lit, mv-acttgt; 123M uni and mv-lit; 209M only before a 209M run. Pass = max
  |q_mps - q_cpu| <= 1e-3 in z units and identical alarms at the smoke threshold, for every row. Result goes to
  `results/phase1/mps_check.csv`. If any row fails: `cpu`, 4 threads (10 threads gain only 12 %, `bench.csv`). All
  headline 10 s runs use one device. The device is part of the cache key.
- Before each run, `forecast` times 3 real calls, prints the estimated wall-clock, and logs every call
  (T, rows, seconds) to `calls_<split>.csv` next to the cache.
- Seeds: `seed: 0` for `random`, numpy and torch. Timestral itself has no sampling (P:p01 §2).

### 6.1 Cache

Path: `cache/<dataset>/<model>/<setup>/<variant>@<hash8>/<split>/<file>.parquet`, plus `meta.json` in
`<variant>@<hash8>/` (D34). `<hash8>` is the first 8 hex characters of the forecast hash.

| key part | values |
|---|---|
| dataset | `hai2103-10s`, `hai2103-1s`; smoke uses its own keys `hai2103-10s-smoke`, `hai2103-1s-smoke`, each with its own `prepared/` directory |
| model | `timestral-<size>-<rev7>-<device>`, e.g. `timestral-28M-49b2640-mps`; `baseline` for experiment 5 |
| setup | `uni`, `uni57`, `mv-lit`, `mv-acttgt`; for baselines `robustz`, `lastvalue`, `seasonal-refday` |
| variant | `rolling`, `ff-interp-block`, `ff-interp-block-max60-testinf`, `frozen`, `dual`, `prepend`, `cf-onset`; suffix `-c8192` for 1 s caps |
| split | `calib`, `calib2`, `test`, `ref` (frozen only) |

Columns (one row per file, channel and scored step; long format):
`file` (str), `channel` (str), `t` (int32, step index in the file), `time` (datetime, bin start), `origin` (int32),
`h` (int16), `ctx_len` (int32), `q01` ... `q99` (21 x float32), `y_true` (float32, z units, always from `Z_obs`),
`label` (int8, binned `attack`), `substituted` (bool, FF only: the value at `t` was replaced by `q50` in `Z_ctx`, so
in the context of later forecasts).

`meta.json` holds the forecast hash: sha256 of
(a) every forecast-relevant setting (resolution, channel lists and roles, W, H, cap, warm-up mode, flags, timestral
commit, HF revision, device, FF parameters and the FF thresholds hash);
(b) the prepared input arrays the run reads (targets, covariates and labels of each segment, plus the normalization
stats), so any change in `prepare` changes the hash;
(c) the source of the forecasting code: `forecast.py`, `context.py`, `mps_shim.py` (`baselines.py` for baselines).
`data.py` is covered through (b), so editing a CSV writer in it does not invalidate hours of forecasts.
A changed setting or changed code writes a new `<variant>@<hash8>/` beside the old one. Nothing is overwritten, no
error is raised, and nothing is deleted. Cached forecasts are never deleted without Arthur (CLAUDE.md). Within one
directory, a file whose parquet exists is skipped. Each file is written to a temp name and renamed when complete.
Readers (`score`, `evaluate`, `plot`) recompute the hash from the config and current code and read that directory.
If it does not exist they stop and say "run forecast first" (they never fall back to a stale directory).

Scores are derived, cheap and not forecasts: `score` writes
`cache/<dataset>/<model>/<setup>/<variant>@<hash8>/scores/<channel_set>/{scores,agg}_<split>.parquet` and overwrites
them on every run.

How the context variants fit the cache:

- **Forecast Fallback** is sequential within a file: each forecast depends on earlier substitutions. It is its own
  variant with its own inference run, on `calib` and `test`. Its forecasts are conditional on `Z_ctx`. The
  `substituted` column records what was replaced. It needs the FF thresholds from the base `rolling` calib cache
  first (section 8, order). Scoring and triggering always use the real `y_true` from `Z_obs`.
- **Frozen**: one forecast per channel group from the `reference` slice, stored once as
  `frozen@<hash8>/ref/reference.parquet` (columns `channel`, `h`, `q01`...`q99`). The scorer takes
  `(file, t, origin, h, y_true, label)` from the prepared segment and the origin grid of section 6 (W, H), and joins
  the frozen quantiles on `(channel, h)`. No rolling cache is needed.
- **Dual**: no inference. The scorer reads the `rolling` cache (which carries `file, t, origin, h, y_true, label`) and
  the frozen `ref` cache of the same model and setup, joined on `(channel, h)`. Its score directory is
  `dual@<hash8>/scores/`, with hash = sha256 of the two source hashes.
- **cf-onset** (D46): one forecast per attack, written in the same schema (`origin` = onset step, `h` = t - origin + 1
  up to L + N), split `test` only.
- **Baselines** write the same schema under `model = baseline`, so one scorer handles everything.

---

## 7. Scoring

All scores are computed from the cache. Units are z units (train-fit std).

Per channel c and scored step t:

- **band** (headline): `max(0, y - q95, q05 - y) / (q95 - q05 + eps)`, `eps = 0.1` (D17).
- **crps** (alternative): `2 * sum_i w_i * pinball_{tau_i}(y - q_i)` over the 21 levels, with midpoint-rule weights:
  cell edges at 0, the midpoints between neighbouring levels, and 1, so `sum w_i = 1`.
  `pinball_tau(u) = u * (tau - 1[u < 0])`.
- **mae** (paper-comparable, Lowe et al. `fmsd:163-178`): `|q50 - y|`.
- **dual** (exp 3c only): quantile Wasserstein-1 between the recent-context and frozen forecasts,
  `sum_i w_i * |q_i_recent - q_i_frozen| / (q95_frozen - q05_frozen + eps)`. It does not use y.

Aggregation across the scored channels of a setup:

- **top-k mean** (headline), `k = 3`: mean of the 3 largest channel scores at t (D19).
- **max**: reported next to it.
- **mean over channels**: used only with `mae`, to mirror Lowe et al.
- Smoothing: off by default. Option `smooth: k` = trailing mean over k steps. Not used for any headline number.

Threshold (D20, D49): the 99.5th percentile (`threshold_pct: 99.5`) of the aggregated score over all scored `calib`
steps (16,980 at 10 s), computed separately for every (run key, channel set, score, aggregation, calib source). The
aggregation runs over the channels of that channel set, on calib and on test alike, so a restricted view (e.g. a
top-3 mean over 34 channels) never uses the 51-channel threshold. Calib source is `calib` (headline) or `calib2`
(sensitivity, D51). Alarm = score > threshold. Thresholds go to `results/phase1/thresholds.csv`. Nothing is tuned on
test labels.

---

## 8. Experiments and run matrix

Working model for experiments 1-3 and 5 (D16): Timestral-28M @ `49b2640`. **Paused (D117): Phase 1 runs on
Chronos-2 with the run matrix of section 14.7.** The table below is the Timestral plan, kept for a later switch back.

| exp | model | setup | variant | config | status |
|---|---|---|---|---|---|
| smoke 10 s | 5M (cpu and mps) | uni, uni57, mv-lit, mv-acttgt | rolling, ff-interp-block, ff-interp-block-max60-testinf, frozen, dual, prepend, cf-onset, baselines | `configs/smoke.yaml` | required first |
| smoke 1 s | 5M | uni | rolling, ff-interp-block, cf-onset, baselines; cap 2,048 so the cap binds (D59) | `configs/smoke_1s.yaml` | required first |
| MPS check | 5M, 28M, 123M (209M before any 209M run) | per D54 | rolling | part of `smoke` | required first |
| 1 | 28M | uni | rolling (+ calib2), cf-onset | `configs/exp1_uni.yaml` | planned (headline exp 1) |
| 1 | 28M | uni57 | rolling | `configs/exp1_uni57.yaml` | planned (brief-literal secondary, D39) |
| 2 | 28M | mv-lit | rolling (+ calib2), cf-onset | `configs/exp2_mv.yaml` | planned (headline exp 2) |
| 2 | 28M | mv-acttgt | rolling | `configs/exp2_mv_acttgt.yaml` | planned (secondary, labelled; never a base) |
| 3a | 28M | base | ff-interp-block | `configs/exp3a_ff_interp_block.yaml` | planned |
| 3a | 28M | base | ff-interp-block-max60-testinf | `configs/exp3a_ff_interp_block_max60.yaml` | planned (secondary, test-informed, not a candidate) |
| 3a | 28M | base | ff-interp-block-max30, -max120 | `configs/opt_ff_max_sens.yaml` | optional sensitivity, no pick (D25) |
| 3b | 28M | base | frozen | `configs/exp3b_frozen.yaml` | planned |
| 3c | 28M | base | dual | `configs/exp3c_dual.yaml` | planned (no inference) |
| 4 | 5M, 123M | best of 1-3 | best | `configs/exp4_5m.yaml`, `configs/exp4_123m.yaml` | planned (28M comes from exp 1-3) |
| 4 | 5M, 123M | uni | rolling | `configs/exp4_uni_5m.yaml`, `configs/exp4_uni_123m.yaml` | planned (unselected setup, D53; 5M = the 10 s reference row) |
| 4 | 209M | best of 1-3 | best | `configs/exp4_209m.yaml` | optional |
| 5 | baseline | robustz, lastvalue, seasonal-refday | rolling | `configs/exp5_baselines.yaml` | planned (all 57 channels, scored on every set) |
| 10 s ref | 5M | uni | rolling, ff-interp-block, cf-onset | `configs/res10s_5m_ref.yaml` | planned (10 s reference for the 1 s comparison, D52) |
| 1 s | 5M | uni | rolling-c8192 (+ baselines), cf-onset-c8192 | `configs/res1s_uni.yaml` | planned (brief: optional) |
| 1 s | 5M | uni | ff-interp-block-c8192 | `configs/res1s_ff_interp_block.yaml` | planned (brief: optional) |
| opt | 5M | uni | rolling, cap 32768 at 1 s | `configs/res1s_uni_c32k.yaml` | optional (5.5 h) |
| opt | 28M | base | prepend | `configs/opt_prepend.yaml` | optional |
| stretch | Chronos-2 or TimesFM | | | | stretch, decide later, needs Arthur |

"base" = the setup chosen by `select --stage base` and read from `results/phase1/selection.csv` (D41). "best of 1-3"
= the (setup, variant) chosen by `select --stage best`. No config is edited by hand during a run.

Order and dependencies (this is what `all` runs, D41):

1. smoke (10 s, 1 s, MPS check); 2. exp 1 (uni, uni57), exp 2 (mv-lit, mv-acttgt), exp 5, calib2 passes;
3. `select --stage base`; 4. exp 3b, 3c, then 3a (needs the FF thresholds from the base calib cache);
5. `select --stage best`; exp 4 (best, then uni rolling); 6. the 10 s 5M reference and the 1 s runs;
7. `evaluate` and `plot` over everything; 8. optional runs only if Arthur asks or time is left.

Selection rule (D21), fixed now:

- Metric: highest test **PR-AUC** of the headline score with top-3 mean aggregation, ties broken by ROC-AUC. The
  headline score is `band` for rolling, FF and frozen, and `dual` for 3c.
- "Better of 1 and 2": candidates `uni` and `mv-lit` only, compared on matched channels: `mv-lit` on `mvlit34`
  vs `uni` on `mvlit34` (`uni@mv-lit-channels`). If `mv-lit` wins, the base is `mv-lit` (scored on `mvlit34`).
  Otherwise the base is `uni` (scored on `uni51`). The unmatched comparison (each on its own set) and
  `mv-acttgt` vs `uni@mv-acttgt-channels` are reported in the same table. `mv-acttgt` and `uni57` are never
  candidates. Making `mv-acttgt` a base needs Arthur (Q1).
- "Best of 1-3": candidates are the base `rolling`, `ff-interp-block`, `frozen` and `dual`, all on the base setup
  and its full channel set (including `P1_PCV02Z`). `ff-interp-block-max60-testinf` is not a candidate (D25).
- REPORT.md states that both picks were made on test results and cites `selection.csv`.

### Experiment 1: univariate zero-shot

Headline `uni`: 51 channels (`uni51`, section 3.4), each forecast independently, no covariates. Goal: the
boundary-vs-interior pattern. This departs from the literal "every channel forecast independently", which would be all
57 non-constant channels (D39, Q17). Reason, from train data and toy checks only: the 6 step tags change on 0.0014 % to
0.147 % of train steps (section 3.4), so they are piecewise constant. A constant context gives a zero-width band
(P:p01 §6-7), so their band score is `dev / eps` at every scheduled setpoint change. The brief-literal reading runs as
the labelled secondary `uni57` (28M, rolling, calib + test) and is scored and reported like every other run.

### Experiment 2: multivariate per process

P1, P2, P3 each as one joint forecast (section 2.5). Headline `mv-lit` follows the brief: actuator commands and step
setpoints are past-only covariates. Secondary `mv-acttgt` makes the actuator commands targets. P4 is not a group (D23).
Comparison with exp 1 on matched channels: `mv-lit` vs `uni@mv-lit-channels` (both on `mvlit34`) and `mv-acttgt` vs
`uni@mv-acttgt-channels` (both on `mvacttgt41`), free from the cache. The matched pair decides "better of 1 and 2"
(D21). Each setup on its own set is reported beside it, with the note that those numbers mix forecasting mode with
channel choice (`mvlit34` has neither the actuator commands nor P4).

### Experiment 3a: Forecast Fallback

Our implementation is an interpretation, so the variant names say so (D24, CLAUDE.md "Rules"): `ff-interp-block`
(headline) and `ff-interp-block-max60-testinf` (bounded). "Paper" is used only for the parts Lowe et al. state:
the 3-step trigger and the 99.5th-percentile per-feature level (`Lowe:fmsd:300-319`; poster diagram).

| item | value | status |
|---|---|---|
| trigger statistic | per-feature absolute error `|q50 - y|`, y from `Z_obs` | paper (MAE per feature); median as the point forecast is our choice |
| per-feature threshold `tau_c` | 99.5th percentile of `|q50 - y|` on `calib` from the base `rolling` run | level from the paper; data source UNCONFIRMED in the paper, ours follows the brief's rule |
| trigger rule | 3 consecutive steps of a feature above `tau_c`. The run counter carries across window boundaries (a run may span two windows) | paper (3 steps); carry-over is ours |
| action | replace the observation in `Z_ctx` with the model's prediction (`q50`) from the 3rd exceeding step on; earlier exceeding steps stay observed | paper text and poster diagram |
| scoring during fallback | always against the real observation (`Z_obs`) | paper Fig. 3 |
| scope | per feature (`ff.scope: feature`); option `all` (whole time-step vector), not run | INTERPRETATION (text says "that time step", trigger is per feature) |
| block adaptation | after each 30-step window is observed, scan each feature's steps in order; substitute from the trigger step to the window end; while in fallback, every later window's observations are replaced by that window's `q50` before they enter `Z_ctx` | INTERPRETATION (paper shows one-step rolling only) |
| exit | `ff-interp-block`: none, state resets at each file start | INTERPRETATION (paper gives no exit rule) |
| exit, bounded | `ff-interp-block-max60-testinf`: leave fallback after 60 steps (10 min at 10 s); substituted values stay in `Z_ctx`; counting restarts; re-entry needs 3 new consecutive exceedances | brief's max-fallback-duration parameter; the value is test-informed (D25) |
| covariates | never substituted (they are observed exogenous inputs) | INTERPRETATION |

`max_duration = 60` steps was set to exceed the longest test attack (43 steps) plus the longest post-attack excursion
seen in the test files (52 s, `P2_SIT01`, probe 05). It was chosen with knowledge of test attack lengths, so the name
carries `-testinf`, it is on the D8 list, and it is not a candidate for "best of 1-3" (D25). An optional sensitivity
set, `-max30` and `-max120`, is fixed now and reported without picking among them.

What block FF can and cannot change. Substitution only feeds the context of later windows. 33 of 50 attacks at 10 s lie
inside one window issued before onset (section 8, 1 s comparison), so for them FF can only change the forecast
inside the attack if fallback was already active before onset. A false trigger on normal data makes the forecast
free-run for the rest of the file (in `ff-interp-block`), and a drifting free-run forecast can raise scores on its own
(`research/papers.md` §3.4, §5, on Lowe Fig. 3). That is expected and is reported, not fixed. To keep these effects
apart from detection (D44):

- `results/phase1/ff_episodes.csv` lists every fallback episode (file, channel, start, end, exit reason).
- Each attack gets `ff_active_at_onset` (any scored channel of the setup in fallback at the onset step),
  `ff_n_channels_active_at_onset`, `ff_fallback_age_at_onset_steps` (steps since the oldest still-active trigger)
  and `ff_first_trigger_after_onset_steps` (empty if no trigger from onset to end + N).
- Each attack falls in one FF group: `pre_active` (fallback active at onset), `triggered_in_attack` (no fallback at
  onset, a trigger in [onset, end + N]) or `none`. FF segment metrics are reported per group. For `none`,
  `ff-interp-block` gets the same inputs as `rolling` up to end + N (no earlier trigger in the file, since it has no
  exit). In the bounded variant, an episode that already ended can still leave substituted values in `Z_ctx`.
- FF's alarm rate on normal test steps is reported next to its interior coverage.
- REPORT.md credits FF with interior detection only on `triggered_in_attack` attacks. On `pre_active` attacks an
  interior alarm may come from drift after an unrelated trigger.

### Experiment 3b: frozen reference context

Literal reading of the brief (INTERPRETATION, label `frozen`): every window uses the forecast from one fixed clean
context, the `reference` slice (last 24 h of train3, 8,640 steps, covariates included for exp 2 setups). This gives one
30-step band per channel, the same for every window (indexed by h). It never sees test data. Its threshold comes from
`calib` scored against the same band. Expect false positives whenever the plant sits away from the reference operating
point; that is part of the result. One such offset is known from train data alone: `P1_PCV02Z` sits about 54 fit-z
higher in `calib` (and in the test files before the A302/A512 shifts) than on the `reference` day (section 3.4). So
3b, 3c and `seasonal-refday` are reported both on the full channel set (headline, same set as the other methods) and
on `<set>-noPCV02Z`. This was decided before any result exists (D50).

### Experiment 3c: dual-context disagreement

Score = `dual` (section 7) between the `rolling` forecast of the chosen setup and the `frozen` forecast, aggregated
(top-3 mean, max) and thresholded like every other score. It competes in "best of 1-3" with `dual`, top-3 mean
(D21). INTERPRETATION (neither paper proposes it).

### Experiment 4: model sizes

Two setups, each with 5M and 123M (28M is reused; 209M optional), same device:

- the best of experiments 1-3 (selected on 28M test results);
- `uni` `rolling`, not selected on any result (D53). Its 5M run is the 10 s reference row when both run on the same
  device.

The setup was picked on 28M test results, so the 28M row has a selection advantage (winner's curse). REPORT.md 4.4
says so, and the unselected `uni` rolling comparison is shown next to it.

Prerequisites per size, by the variant of the best setup (D21):

| best variant | needs at each size |
|---|---|
| rolling | rolling calib + test |
| ff-interp-block | rolling calib (for `tau_c`), then FF calib + test |
| frozen | the `ref` forecast; calib and test are scored against it (no rolling pass) |
| dual | rolling calib + test, plus the `ref` forecast |

Per-call wall-clock comes from `calls_<split>.csv`.

### Experiment 5: baselines (scored identically)

Every baseline writes 21 quantiles in the cache schema, so the band, crps and mae scores, the thresholds and all
metrics run unchanged. Baselines forecast all 57 non-constant channels and are scored on every channel set a TSFM run
uses (`uni51`, `uni57`, `mvlit34`, `mvacttgt41`, each also `-noPCV02Z`), with their own calib thresholds per set (D49).
This is scoring only. Each TSFM result is compared with the baselines on the same channel set.

| baseline | forecast for window `[o, o + 30)` | band (21 quantiles) |
|---|---|---|
| `robustz` | median `m` of the trailing 360 steps before `o` (1 h at 10 s; 3,600 at 1 s; at least W = 150 steps available) | `m + Phi^-1(tau) * 1.4826 * MAD` of the same window |
| `lastvalue` | `y(o - 1)` for all h | `y(o - 1) + Q_tau(Delta_h)`, where `Delta_h = y(s + h) - y(s)` over the `fit` set, per channel and h |
| `seasonal-refday` | value of the `reference` day at the same clock time | value plus `Q_tau(D)`, `D = y(s) - y(s - 24 h)` within train2 and within train3, per channel |

`seasonal-refday` (D28) is a reference-day model, not seasonal-naive on the series: every file is compared with one
fixed clean day (the last 24 h of train3). REPORT.md describes it that way. 24 h is the only periodicity documented
for HAI 21.03 (benign setpoint schedule, `HAI-PDF p.37`; P4 power schedule about 22:00-03:00, probe 07). In-file
history is shorter than 24 h for test1, test4, both `calib` pseudo-files and the first day of every file, so an
in-file 24 h lag would exist for only part of test2, test3 and test5. Mixing lag sources would treat `calib` and test
differently, so it is not used. Its known handicap is the `P1_PCV02Z` level offset (D50), so it is also reported on
`<set>-noPCV02Z`. The robust z-score uses windows anchored at the forecast origin, like the TSFM, so all methods share
the same protocol. Window length 1 h is fixed a priori: it never spans two scheduled setpoint changes, because the
schedule slots are 1.5 to 5 h apart (`HAI-PDF p.37`).

### 1 s comparison (the brief's optional short-context config)

5M, uni, cap 8,192 (2.3 h), W = 1,500, H = 30, baselines included, plus `ff-interp-block` on top (thresholds from its
own 1 s calib) and `cf-onset`. Fixed in advance; no selection. Why it matters: at 10 s with H = 30 only 24.8 % of
attack steps (232 of 934) are scored by a forecast whose context already holds attack data, and 33 of 50 attacks lie
inside one window issued before onset. At 1 s with H = 30 it is 86.0 % (7,698 of 8,947 s) and 49 of 50 attacks
(computed from `research/hai_attacks.csv` with the origins of section 6; throwaway script `SP/plan-scripts/windows.py`).
At 10 s, 406 of the 637 interior steps (N = 6) come from clean pre-onset contexts. At 1 s every interior step (N = 60)
comes from a post-onset origin (`SP/plan-scripts/critic_verify.py`). The 10 s setup can barely show the contamination
mechanism; the 1 s setup can.

The 10 s reference (D52): 5M, uni, `rolling` + `ff-interp-block` + `cf-onset` at 10 s, calib + test, on the same
device as the 1 s block. Without it, the only 10 s runs use 28M and the comparison would mix resolution with model
size. Even with it, 1 s vs 10 s changes more than the resolution. H = 30 is 30 s vs 300 s, the stride changes the
same way, and the context cap is 8,192 steps (2.3 h) vs 32,768 (never binding). REPORT.md 4.6 says all of this.

---

## 9. Metrics

All on scored test steps (t >= W), concatenated over the five files, label = binned `attack`.
Per run key, channel set, score and aggregation (D49):

- **ROC-AUC** and **PR-AUC** (average precision) on the continuous aggregated score (scikit-learn).
- **Point metrics at the calibrated threshold**: precision, recall, F1, alarm steps, false alarms per hour of normal test data.
- **TaPR**, official `TaPR.py` (vendored, unmodified), called in memory (D30, D31):
  - headline: `alpha = 0.5`, `theta = 0.5`, `delta = 180 s` = 18 steps at 10 s, 180 at 1 s;
  - strict: same with `delta = 0`;
  - HAICon-like: `alpha = 0.5`, `delta = 180 s`, TaR from `theta = 0.1`, TaP from `theta = 0.7` (two TaPR objects),
    labelled "official TaPR.py with HAICon 2020 thresholds; not eTaPR, not comparable to the leaderboard".
  - HAICon 2020 itself used eTaPR with alpha 0.5, rho 0.1, pi 0.7, delta 180 (CSET'21 §4.1.2). The brief says TaPR;
    eTaPR is not added (Open question Q6).
  - F1 = 2 TaP TaR / (TaP + TaR) is ours; `TaPR.py` does not compute it (`TaPR.py:353, 368`).
  - Files are joined with a gap of `delta + 1` normal steps between them, so ranges never merge and ambiguous zones
    never spill into the next file. One score over all 50 attacks; per-file scores optional.
  - Guards in the wrapper: `delta != 1`, every anomaly range has length >= 2 (HAI minimum is 3 at 10 s). The file
    loaders are not used (bugs B1/B2: a detector that never fires would get TaR = 1.0, `TaPR.py:104, 128-129`).
  - Known quirk kept as is: detection uses `>` theta, the paper uses `>=` (`TaPR.py:155, 178`; issue wshw4ng/TaPR#2).
- **Point-adjusted F1**: computed, always in a column named `pa_f1_inflated` and labelled in REPORT.md. Never a headline.

Boundary vs interior (the key result, D29):

- Segments per attack: onset = first N steps of the attack; interior = the rest of the attack; offset = the N steps
  after the attack end (labelled normal). N = 6 steps (60 s) at 10 s, N = 60 steps (60 s) at 1 s.
- Why 60 s: (a) it covers the 10 s binning shift (onset moves up to 9 s earlier); (b) it covers the documented
  post-attack excursions (turbine trips end up to 40 s, `P2_SIT01` up to 52 s after the labelled end, probe 05); (c) it
  leaves a non-empty interior for 47 of 50 attacks at 10 s. Empty interior at 10 s: A203 (3 steps), A211 (6), A508 (6).
  At 1 s: A104 (60), A203 (17), A211 (45), A508 (51).
- N was chosen partly from test labels and test-file excursions, so it is on the D8 list. Sensitivity N in {3, 12}
  steps at 10 s (and 30, 120 at 1 s) goes to an appendix table. N = 6 stays the headline.
- Equal-length interior (D45): `interior_eq` = attack steps N+1..2N, for attacks with L >= 2N (37 of 50 at 10 s,
  34 of 50 at 1 s). Onset, `interior_eq` and offset then all have N steps.

Headline segment metric (D45): **coverage** (share of steps in the segment with an alarm). "Detected" (any alarm in
the segment) depends on segment length. At 10 s, non-empty interiors are median 13 and max 37 steps, vs N = 6 for
onset and offset. At 1 s they are median 126.5 and max 362 vs N = 60. With p = 0.005 alarms per normal step and
independent alarms, the chance any-alarm rate is 3.0 % for a 10 s onset vs 6.3 % / 16.9 % for a median / max
interior, and 26 % vs 47 % / 84 % at 1 s (`SP/plan-scripts/critic_verify.py`). So every any-alarm rate is shown with
its chance level `1 - (1 - p)^n`, where p is the run's alarm rate on normal scored test steps and n the segment
length, averaged over the attacks. Alarms are autocorrelated, so the chance level is a reference, not a test.

Per attack and method (`segments_per_attack.csv`):

- detected and coverage per segment (onset, interior, `interior_eq`, offset), with each segment's chance level;
- detection latency: first alarm in the attack minus attack start, in seconds. A miss is censored at duration + N
  (`latency_censored_s`) and is also left empty in `latency_s`;
- coverage split by forecast origin, post-onset (context holds attack data) vs pre-onset;
- the offset stratum (D47): `trip` for the 9 turbine-trip attacks (A201, A207, A217, A304, A305, A307, A501, A507,
  A511), `pcv02d` for the 5 attacks where `P1_PCV02D` moves (A101, A202, A302, A402, A512), else `other`.
  `prepare` derives both flags from the raw 1 s test data of the dropped tags (`P2_OnOff` = 0, `P1_PCV02D` != 12
  inside the attack), and `test_data.py` checks that the lists match `research/hai_data.md` §3.2. In trip attacks,
  the post-attack "normal" seconds hold tripped-turbine data for up to 52 s (probe 05), so an offset alarm there may
  be a real process anomaly, not a context effect. A302 and A512 are also followed by the `P1_PCV02Z` level shift;
- FF columns and FF group (section 8, exp 3a; D44).

Per method (`segments_summary.csv`), for all attacks and per offset stratum and FF group:

- mean coverage per segment (headline), detection rate per segment next to its chance level, `p_normal`;
- latency (D48): median over the attacks that every compared method detects (`latency_common_median_s`, with
  `n_common`), and median of the censored latency over all attacks. `n_detected` is kept next to both. A median over
  each method's own detected subset is not reported, because methods detect different attacks.

Mechanism test (D46). The pre/post-onset origin split is confounded with horizon h and with time since onset. At 10 s,
interior steps from pre-onset origins have mean h = 19.5 (n = 406) and those from post-onset origins mean h = 9.7
(n = 231). Onset steps have mean h = 13.5, interior steps 15.9 (`SP/plan-scripts/critic_verify.py`). If bands widen
with h, a short-horizon step gets a higher band score for the same deviation, which can hide the hypothesised drop.
Whether Timestral bands widen with h on HAI is UNCONFIRMED; `band_width_by_h.csv` measures it from the calib cache.
So:

- `segments_by_h.csv` gives coverage and mean score by segment x origin side x h bucket (1-10, 11-20, 21-30)
  x time since onset (0-59 s, 60-119 s, 120-239 s, >= 240 s), pooled over attacks. The headline mechanism contrast is
  post- vs pre-onset coverage **within the same h bucket**.
- Clean-context counterfactual `cf-onset`: one extra forecast per attack, origin = the onset step s (off the rolling
  grid), context = the same file's history `[max(0, s - cap), s)` (no attack data), horizon L + N steps (at most 49
  at 10 s and 482 at 1 s, so one decode block of at most 1,024 steps, section 2.1). It is compared step by step with
  the rolling forecast of the same run (`cf_onset.csv`, split by the rolling step's origin side). Its origin uses the
  test labels, so it is a diagnostic only, never a detector, and it gets no threshold of its own. The contrast that
  tests contamination is on steps whose rolling origin is after onset. There the rolling context holds attack data,
  the counterfactual's does not, and the counterfactual horizon is longer (`t - s + 1 > t - o + 1`). If bands widen
  with h, that biases the counterfactual towards lower scores, so a higher counterfactual score there is conservative
  evidence of contamination, and a lower one is inconclusive. Long-horizon drift could bias the other way, so the
  subset with counterfactual h <= 30 is reported too. On steps with a pre-onset rolling origin both contexts are
  clean, so they serve as a horizon-only control. It runs for 28M `uni` and `mv-lit` at 10 s and for 5M `uni` at
  10 s and 1 s (50 calls each).
- REPORT.md states that the 10 s onset/interior split mostly does not test contamination: 406 of 637 interior steps
  are forecast from clean context.

Size vs latency: per model size and setup (best of 1-3 and unselected `uni` rolling), sec per call (median over the
run), test-pass wall-clock, ROC-AUC, PR-AUC, TaPR F1, onset coverage, mean interior coverage.

---

## 10. Compute estimate

This is the Timestral estimate (paused, D117). The Chronos-2 estimate is in section 14.8.

Method: per-row cost from the B = 64 univariate cells of `bench.csv` (median s/call / 64), log-log interpolated
between T = 2,048, 8,192 and 32,768, applied to every origin's real in-file context length. Covariate-path rows cost
2.4x (measured 2.1-2.5x, `cov_cost.csv`). Calls: 1,315 test origins + 566 calib origins at 10 s; 13,150 + 5,660 at 1 s.
The bench used random-walk inputs; `forecast` re-measures on HAI before each run. Throwaway script:
`SP/plan-scripts/estimate.py`.

Inference hours per run (test + calib), 10 s, in-file context, H = 30:

| setup | calls | series-forecasts | 5M MPS | 28M MPS | 123M MPS | 209M MPS | 28M CPU | 123M CPU |
|---|---|---|---|---|---|---|---|---|
| uni (51) | 1,881 | 95,931 | 0.07 | 0.24 | 0.89 | 1.38 | 0.45 | 1.66 |
| mv-lit | 5,643 | 63,954 targets | 0.13 | 0.45 | 1.64 | 2.54 | 0.83 | 3.05 |
| mv-acttgt | 5,643 | 77,121 targets | 0.12 | 0.42 | 1.52 | 2.35 | 0.77 | 2.82 |

An FF run costs the same as its base setup. Frozen is one call per group. Dual and baselines need no inference.

1 s, uni, 5M (13,150 + 5,660 calls): cap 8,192: 1.17 h MPS, 2.02 h CPU. Cap 32,768: 5.46 h MPS, 9.46 h CPU.
Prepend option at 10 s, 28M MPS: 2.35 h at cap 32,768, 0.42 h at cap 8,192.

Planned total on MPS (smoke and MPS check excluded, about 15 min). Same estimator (`SP/plan-scripts/estimate.py`):

| block | best = uni + FF | best = mv-lit + FF |
|---|---|---|
| exp 1 + exp 2 (uni, mv-lit, mv-acttgt) | 1.11 | 1.11 |
| exp 1 `uni57` (57/51 of uni) | 0.27 | 0.27 |
| `calib2` passes (uni 0.07, mv-lit 0.13) | 0.20 | 0.20 |
| exp 3a (two FF variants) | 0.48 | 0.90 |
| 10 s 5M reference (uni rolling + FF) | 0.14 | 0.14 |
| exp 4: 5M best (beyond the reference) | 0 | 0.17 |
| exp 4: 123M best | 1.14 | 2.10 |
| exp 4: 123M uni rolling (unselected) | 0.64 (calib pass shared) | 0.89 |
| `cf-onset` (4 x 50 calls) | < 0.05 | < 0.05 |
| 1 s: rolling + ff-interp-block | 2.34 | 2.34 |
| total | about 6.4 h | about 8.2 h |

Optional on top: 209M up to 3.3 h, 1 s cap 32,768 5.5 h, prepend 0.4-2.4 h, FF max30/max120 0.5-0.9 h.

Flags (> 2 h) and mitigations that keep the method intact:

- exp 4 at 123M with an mv setup (2.1 h): run only the best setup and `uni` rolling. The base test pass is skipped
  when the best is an FF variant (only its calib pass is needed for `tau_c`).
- 1 s block (2.3 h MPS): 5M only; cap 8,192 (D12). It may run on CPU (official code path, 4.0 h) in parallel with the
  10 s MPS queue. If it does, its 10 s 5M reference runs on CPU too (about 0.24 h), so the 1 s vs 10 s comparison
  uses one device (D52). Check on the smoke slice that running both at once does not slow MPS by more than 20 %;
  otherwise run them one after the other on MPS.
- 209M and 1 s cap 32,768: optional, run only if time is left.
- Not used as mitigations: fewer channels, `symmetric_averaging=False`, bf16, larger stride. Each changes the method.

Scoring, TaPR (0.23 s per call at 10 s, 2.25 s at 1 s, `research/tapr.md` §4) and plots take minutes.

---

## 11. Code layout and module interfaces

```
pyproject.toml        uv project, Python 3.12; console script tsfm-ad = tsfm_ad.cli:main
configs/              base.yaml, smoke.yaml, smoke_1s.yaml, exp1_uni.yaml, exp1_uni57.yaml, exp2_mv.yaml,
                      exp2_mv_acttgt.yaml, exp3a_ff_interp_block.yaml, exp3a_ff_interp_block_max60.yaml,
                      exp3b_frozen.yaml, exp3c_dual.yaml, exp4_5m.yaml, exp4_123m.yaml, exp4_209m.yaml,
                      exp4_uni_5m.yaml, exp4_uni_123m.yaml, exp5_baselines.yaml, res10s_5m_ref.yaml,
                      res1s_uni.yaml, res1s_ff_interp_block.yaml, res1s_uni_c32k.yaml, opt_prepend.yaml,
                      opt_ff_max_sens.yaml, hai2103_attacks_pdf.csv (D56)
src/tsfm_ad/          cli.py config.py data.py forecast.py cache.py mps_shim.py context.py
                      baselines.py score.py evaluate.py selection.py tapr_wrap.py plots.py
                      (+ model_chronos2.py, the Chronos-2 adapter, and d128.py, the size of its constant-row
                      guard; configs/timestral/ holds the paused Timestral configs; section 14, D117-D129)
tests/                test_data.py test_splits.py test_forecast.py test_score.py test_segments.py test_tapr.py
                      test_ff.py
vendor/TaPR/          TaPR.py (byte-identical, sha256 checked), LICENSE (MIT), SOURCE.md
cache/                prepared data, forecasts, scores, HF weights (cache/hf); git-ignored
results/phase1/       CSVs and figures/; committed
```

Dependencies: `timestral @ git+https://github.com/mistralai/timestral.git@a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`,
`torch==2.14.1` (the tested version), polars, numpy, pyyaml, matplotlib, scikit-learn; dev: pytest. `Phi^-1` comes
from `statistics.NormalDist` (no scipy). Keep every file under about 300 lines.

Config: YAML with `base: base.yaml` inheritance (deep merge). Main keys: `dataset` (key, resolution_s, files,
splits, smoke slice), `channels` (role rules, setup channel sets, extra scoring sets), `model` (size, repo, revision,
device, max_context), `forecast` (H, W, cap, `warmup: in_file | prepend`, flags), `variant` (`kind: rolling | ff |
frozen | dual | cf-onset`, FF parameters), `setup` (a name, or `selected` to read it from `selection.csv`), `score`
(eps, kinds, agg, k, smooth, threshold_pct, calib sources), `metrics` (tapr configs, N_onset, sensitivity Ns, h and
time-since-onset buckets), `seed`. The variant name in the run key is derived: `rolling` with `warmup: prepend`
becomes `prepend`; `ff` becomes `ff-interp-block[-max<k>]` (plus `-testinf` for max 60); 1 s caps add `-c<cap>`.
`prepend` is only a warm-up mode, never a `kind`.

| module | public functions | used by |
|---|---|---|
| `config.py` | `load_config(path) -> dict`; `run_key(cfg) -> RunKey(dataset, model, setup, variant)`; `forecast_hash(cfg, extra=None) -> str`; `set_seeds(seed) -> None` | all |
| `data.py` | `read_hai_file(path) -> pl.DataFrame` (typed, last row dropped); `channel_roles(train_df, rules) -> pl.DataFrame`; `downsample(df, roles, resolution_s) -> pl.DataFrame`; `fit_norm(dfs, channels) -> pl.DataFrame`; `apply_norm(df, stats) -> pl.DataFrame`; `make_segments(cfg) -> dict[str, list[Segment]]`; `prepare(cfg) -> None` (writes `cache/<dataset>/prepared/*.parquet`, `channels.csv`, `attacks.csv`, `splits.csv`); `load_segment(cfg, name) -> SegmentData(time, labels, Z_targets, Z_covs, channel names)`; `attack_events(labels, time, file) -> pl.DataFrame` | prepare; all experiments |
| `forecast.py` | `load_forecaster(model_cfg) -> TimestralForecaster`; `predict(fc, groups, ctx_slices, H, flags) -> np.ndarray (channels, H, 21)`; `origins(L, W, H) -> np.ndarray`; `rolling(fc, seg, setup, fcfg, hook=None) -> pl.DataFrame` (keeps `Z_obs` read-only and a per-file `Z_ctx` copy; `hook(o, q50, y) -> mask`; applies `Z_ctx[:, o:o+H][mask] = q50[mask]`; D58); `cf_onset(fc, seg, setup, fcfg, attacks, N) -> pl.DataFrame`; `estimate_runtime(fc, seg, setup, fcfg) -> float`; `run_forecast(cfg, split) -> None` | exp 1, 2, 3a, 3b, 4, 1 s |
| `d128.py` (D129) | `run_d128(cfg, split, skip_done) -> None` (writes `d128_effect.csv`, `d128_effect_channels.csv`); `raw_group(pipe, tgt, cov, H, multivariate)` (the adapter without the guard); `calls(segs, setup, kind, fcfg, attacks, N)` (the contexts of rolling, cf-onset, frozen) | `tsfm-ad d128`, `smoke`, `all` |
| `model_chronos2.py` (D119) | `load(model_cfg, cache_dir) -> Chronos2Pipeline`; `check(pipe, max_context)`; `predict_group(pipe, tgt (V, T), cov (C, T) or None, H, multivariate) -> np.ndarray (V, H, 21)`; `CROSSINGS` | `forecast.load_forecaster`, `forecast.predict` when `model.name` is chronos2 |
| `cache.py` | `run_dir(cfg, variant=None) -> Path` (`<variant>@<hash8>`); `cache_path(cfg, split, file, variant=None) -> Path`; `write(df, path, meta) -> None` (atomic); `read(cfg, split, variant=None, files=None) -> pl.DataFrame`; `read_ref(cfg) -> pl.DataFrame` (frozen); `log_call(path, T, rows, seconds) -> None` | forecast, baselines, score |
| `mps_shim.py` | `install() -> None` (moves the 3 float64 sites to CPU; UNOFFICIAL) | forecast on mps |
| `context.py` | `ff_thresholds(calib_df, pct=99.5) -> dict[str, float]`; `class Fallback(tau, k=3, max_duration=None, scope="feature")` with `reset()`, `__call__(o, q50, y) -> np.ndarray (C, H) bool` (the hook; state only, no arrays; the run counter carries across windows) and `episodes() -> list[Episode]`; `frozen_forecast(fc, ref_seg, setup, fcfg) -> pl.DataFrame` | exp 3a, 3b |
| `baselines.py` | `robust_z(seg, H, W, window=360) -> pl.DataFrame`; `last_value(seg, fit_segs, H, W) -> pl.DataFrame`; `seasonal_refday(seg, ref_seg, fit_segs, H, W, season_s=86400) -> pl.DataFrame`; `run_baselines(cfg, split) -> None` | exp 5, 1 s |
| `score.py` | `band(y, q05, q95, eps) -> np.ndarray`; `crps(y, Q, levels) -> np.ndarray`; `mae(y, q50) -> np.ndarray`; `dual(Q_recent, Q_frozen, levels, eps) -> np.ndarray`; `frozen_rows(seg, ref, W, H) -> pl.DataFrame` (y_true, label, origin, h from the prepared segment joined to the ref quantiles on (channel, h)); `aggregate(S, how, k=3) -> np.ndarray` (S is steps x channels of one channel set); `smooth(s, k) -> np.ndarray`; `threshold(calib_scores, pct) -> float`; `run_score(cfg) -> None` (writes `scores/<channel_set>/{scores,agg}_<split>.parquet` under the run directory and `thresholds.csv`) | all |
| `evaluate.py` | `point_metrics(score, label, thr) -> dict`; `pa_f1(alarm, label) -> float`; `segments(label, N) -> list[Attack]` (onset, interior, interior_eq, offset); `chance_level(p, n) -> float`; `segment_table(alarm, score, attacks, origin, h, steps_res, ff_state=None) -> pl.DataFrame`; `latency_summary(table) -> pl.DataFrame` (common set and censored); `run_evaluate(cfg) -> None` (writes the metrics CSVs) | all |
| `selection.py` | `select(stage, metrics_csv, rule) -> pl.DataFrame` (applies D21, writes `results/phase1/selection.csv`); `selected(stage) -> dict` (read by configs with `setup: selected`; error if missing) | `all`, exp 3, exp 4 |
| `tapr_wrap.py` | `load_official(path="vendor/TaPR/TaPR.py")`; `tapr(y_true, y_pred, theta=0.5, delta=0, alpha=0.5, theta_r=None, theta_p=None) -> dict`; `join_files(pairs, gap) -> tuple[np.ndarray, np.ndarray]` | evaluate |
| `plots.py` | `timeline(cfg, attack_id, run_keys, out) -> None`; `boundary_bars(summary_csv, out) -> None`; `size_latency(csv, out) -> None` | outputs |
| `cli.py` | `main()` | entry point |

CLI (`uv run tsfm-ad <cmd> --config configs/X.yaml [--split calib|calib2|test|ref|all] [--device cpu|mps]`):

| command | does |
|---|---|
| `prepare` | read, drop, downsample, normalize, segments; channel, attack (joined with `configs/hai2103_attacks_pdf.csv`, plus strata) and split CSVs |
| `forecast` | rolling / FF / frozen / prepend / cf-onset inference into the cache; prints the runtime estimate first |
| `baselines` | baseline quantiles into the cache |
| `score` | channel scores, aggregation per channel set, thresholds per calib source (cache only) |
| `evaluate` | AUCs, TaPR, point metrics, segments, h strata, cf-onset, FF attribution (cache only) |
| `select` | `--stage base|best`: applies D21 to `metrics.csv`, writes `results/phase1/selection.csv` |
| `plot` | figures (cache and results only) |
| `smoke` | the whole chain on both smoke slices (`smoke.yaml`, `smoke_1s.yaml`), plus the MPS check |
| `all` | the full Phase 1 matrix in the order of section 8, including both `select` stages; it never edits a config |

Smoke slices (dataset keys `hai2103-10s-smoke` and `hai2103-1s-smoke`, own `prepared/` directories, so smoke never
shares a cache directory or FF thresholds with a full run; D42):

- 10 s: test1 2020-07-07 15:00:00 to 16:59:59 (720 steps, contains A101, 20 steps, onset at step 211) and calib
  train1 2020-07-11 00:00:00 to 01:59:59. Same W, H and code paths as the full runs, 5M. All setups (uni, uni57,
  mv-lit, mv-acttgt) and all variants (rolling, ff-interp-block, ff-interp-block-max60-testinf, frozen, dual,
  prepend, cf-onset), baselines, `select` on smoke metrics (exercise only, never used).
- 1 s (D59): the same two 2 h slices at 1 s (7,200 steps each), W = 1,500, H = 30, N = 60, `cap: 2048` so the cap
  binds (a 2 h slice is below the 8,192 cap). 5M uni rolling, ff-interp-block, cf-onset, baselines.
- Plus the MPS check of D54. Target under 15 min; the estimate is printed first.

Tests (only where a silent bug changes results):

- `test_data.py`: last-row drop; 10 s mean/last/max on a hand-made frame; label max keeps a 1 s attack; Float64 dtypes;
  roles computed on fit + calib rows only and the counts 22/6/7/44; the attack PDF join gives 50 rows A101-A512 in
  order; the `trip` and `pcv02d` strata match `research/hai_data.md` §3.2.
- `test_splits.py`: `calib` and `fit` disjoint; no test row and no train1 row after 2020-07-12 23:59:59 in any fit,
  calib or calib2 segment; norm stats equal a recomputation on train2 + train3 only.
- `test_forecast.py` (stub forecaster that returns the last context value and the context length; D58): for every
  scored t, `origin`, `h = t - origin + 1` and `ctx_len` are right and each scored t has exactly one row; no context
  contains `y(t)` for any t in its window (the context ends at `o - 1`); the `max(0, o - cap)` slice when the cap
  binds; `y_true` equals the prepared data at every t; the frozen `(channel, h)` join; `cf-onset` origin = onset
  and context ends at onset - 1.
- `test_score.py`: band, crps, mae, dual on hand values; zero-width band gives `dev / eps`; top-k; threshold
  percentile; a restricted channel set gets its own threshold and never reuses the full-set one.
- `test_segments.py`: onset/interior/`interior_eq`/offset bounds, short attacks with empty interior; chance level
  `1 - (1 - p)^n` on hand values; latency, censoring at duration + N, the common-detected set; origin split; h and
  time-since-onset buckets.
- `test_tapr.py`: the toy from `research/tapr.md` §4 (theta 0.5, delta 0: TaP 0.590909, TaR 0.175, F1 0.270030;
  delta 10: TaP 0.604928, TaR 0.179206, F1 0.276500); file joining keeps ranges apart; guards fire.
- `test_ff.py`: no trigger on 2 exceedances; trigger and substitution from the 3rd; the run counter carries across a
  window boundary; persistence without exit; exit after `max_duration`; reset per file; covariates untouched;
  cached `y_true` equals `Z_obs` at substituted steps; the context at origin o + H holds q50 exactly where
  `substituted` is true; the FF group and `ff_active_at_onset` on a hand-made file.

---

## 12. Outputs

`results/phase1/`:

| file | columns |
|---|---|
Every row carries the run key (dataset, model, setup, variant, hash8). Every scored result carries `channel_set` (D49).

| file | columns |
|---|---|
| `channels.csv` | channel, resolution_s, process, role, rule, n_unique_train, change_rate_train, mean_fit, std_fit, varies_in_test, uni51, uni57, mvlit34, mvacttgt41 |
| `attacks.csv` | attack_id, file, event, start, end, duration_s, steps_10s, processes, pdf_scenarios, pdf_targets, pdf_page, stratum (trip / pcv02d / other), history_steps, n_windows_10s, post_onset_steps_10s, n_windows_1s, post_onset_steps_1s, interior_empty_10s, interior_eq_10s, in_timeline |
| `splits.csv` | segment, role, source_file, start, end, rows_1s, steps_10s, scored_steps |
| `runs.csv` | run_key, split, config, forecast_hash, device, model_code, revision, started, finished, wallclock_s, n_calls |
| `selection.csv` | stage, decided_at, rule, candidate_run_key, channel_set, score, agg, pr_auc, roc_auc, rank, selected, note ("picked on test results") |
| `latency.csv` | model, device, setup, ctx_bucket, rows_per_call, n_calls, sec_median, sec_p90 |
| `mps_check.csv` | model, setup, n_values, max_abs_diff, mean_abs_diff, alarms_equal, verdict |
| `d128_effect.csv` (D129) | run_key, hash8, split, device, calls, calls_const, forecasts, forecasts_rerun, values, max_dq, max_dq_channel, max_dq_file, max_dq_origin, share_dq_gt_0.01, share_dq_gt_0.1, share_dq_gt_1, max_dq_q05_q50_q95, max_dq_q05_q50_q95_channel, max_dq_band, max_dq_band_channel, max_dband, share_dband_gt_1 (dq = \|adapter - raw\| in fit-z; shares over all values of the split) |
| `d128_effect_channels.csv` (D129) | run_key, hash8, split, channel, forecasts_rerun, max_dq, max_dq_q05_q50_q95, share_dq_gt_0.1, max_dq_band, max_dband |
| `quantile_diagnostics.csv` (D133) | run_key, dataset, model, setup, variant, hash8, device, split, calls, forecasts, crossed, const_rows, share_crossed, rows, share_band_gt_10, share_band_gt_100, share_tail_gt_100, share_tail_gt_1000, band_max, band_max_channel, tail_max, top_channel_band_gt_10, and on test attack_rows, attack_share_band_gt_10, attack_share_band_gt_100, attack_share_tail_gt_100, attack_share_tail_gt_1000 (band = q95 - q05, tail = q99 - q01, fit-z; crossed and const_rows from calls_<split>.csv) |
| `thresholds.csv` | run_key, channel_set, score, agg, smooth, pct, calib_source, threshold, n_calib_steps |
| `ff_thresholds.csv` | run_key, channel, tau |
| `ff_activity.csv` | run_key, split, file, channel, n_triggers, fallback_steps, fallback_frac |
| `ff_episodes.csv` | run_key, split, file, channel, start_t, end_t, n_steps, exit (max_duration / file_end), overlaps_attack_id, active_at_onset_of |
| `metrics.csv` | run_key, channel_set, score, agg, calib_source, roc_auc, pr_auc, precision, recall, f1, alarm_steps, fa_per_hour, pa_f1_inflated |
| `tapr.csv` | run_key, channel_set, score, agg, config, alpha, theta_r, theta_p, delta_steps, delta_s, TaP, TaP_d, TaP_p, TaR, TaR_d, TaR_p, F1, n_pred_ranges |
| `segments_per_attack.csv` | run_key, channel_set, score, agg, N, attack_id, stratum, duration_steps, onset_n, onset_det, onset_cov, onset_chance, interior_n, interior_det, interior_cov, interior_chance, interior_eq_n, interior_eq_det, interior_eq_cov, interior_eq_chance, offset_n, offset_det, offset_cov, offset_chance, latency_s, latency_censored_s, n_post_origin, cov_post_origin, n_pre_origin, cov_pre_origin, ff_group, ff_active_at_onset, ff_n_channels_active_at_onset, ff_fallback_age_at_onset_steps, ff_first_trigger_after_onset_steps |
| `segments_summary.csv` | run_key, channel_set, score, agg, N, stratum (all / trip / pcv02d / other), ff_group (all / pre_active / triggered_in_attack / none), n_attacks, p_normal, onset_cov_mean, interior_cov_mean, interior_eq_cov_mean, offset_cov_mean, onset_rate, onset_chance, interior_rate, interior_chance, interior_eq_rate, interior_eq_chance, offset_rate, offset_chance, latency_common_median_s, n_common, latency_censored_median_s, n_detected, cov_post_origin_mean, cov_pre_origin_mean |
| `segments_by_h.csv` | run_key, channel_set, score, agg, N, segment, origin_side (pre / post), h_bucket, tso_bucket, n_steps, n_attacks, coverage, mean_score |
| `band_width_by_h.csv` | run_key, channel_set, split, h, band_median, band_mean (q95 - q05 in z units) |
| `cf_onset.csv` | run_key, channel_set, score, agg, attack_id, segment, origin_side (pre / post), n_steps, n_hcf_le30, score_rolling_mean, score_cf_mean, score_rolling_mean_hcf_le30, score_cf_mean_hcf_le30, cov_rolling, cov_cf |
| `size_latency.csv` | run_key, model, params, device, setup, variant, channel_set, selected (bool), sec_per_call_median, test_wallclock_s, roc_auc, pr_auc, tapr_f1, onset_cov_mean, interior_cov_mean |

Figures in `results/phase1/figures/`:

- Timelines (30 min before onset to 30 min after the end): 2-3 signals in z units, the aggregated score per method
  with its threshold, attack window shaded, onset/interior/offset marked. The median and the q05-q95 band are drawn
  only where the signal is a scored target of the setup; otherwise the raw signal is drawn and labelled "not scored
  in <setup>". The signals are fixed now from the PDF control loops, not from any score (D55): P1-PC = PV `P1_PIT01`,
  CV `P1_PCV01D`, SP `P1_B2016`; P1-LC = PV `P1_LIT01`, CV `P1_LCV01D`; P2 trip logic = `P2_SIT01` and vibration
  `P2_VYT02` (`P2_VIBTR01` in the PDF); P3-LC = PV `P3_LIT01`, CV `P3_LCP01D` (`HAI-PDF p.8, p.11, p.12, p.15`).
  Attacks, chosen by duration, process and attack type before any result exists (D33):
  - `timeline_A202.png`: longest (422 s), P1, setpoint + PV; `P1_PIT01`, `P1_PCV01D`, `P1_B2016`;
  - `timeline_A210.png`: 421 s, P1, control variable + PV; `P1_PIT01`, `P1_PCV01D`;
  - `timeline_A403.png`: longest outside the 421-422 s group (263 s), P1 + P3 combination; `P1_LIT01`, `P1_LCV01D`,
    `P3_LIT01`;
  - `timeline_A217.png`: longest P2-only attack (184 s), P2-TC-SP3, with a turbine trip; `P2_SIT01`, `P2_VYT02`;
  - `timeline_A219.png`: P3-only (119 s), P3-LC-CO1; `P3_LIT01`, `P3_LCP01D`;
  - `timeline_A203.png`: shortest (17 s), short-term attack; `P1_LIT01`, `P1_LCV01D`.
- `boundary_interior.png`: per method, mean coverage per segment (onset, interior, `interior_eq`, offset), with the
  detection rates and their chance levels as a second panel.
- `boundary_interior_origin.png`: interior coverage for post- vs pre-onset origins within each h bucket, plus the
  `cf-onset` vs rolling contrast.
- `size_latency.png`: ROC-AUC and PR-AUC vs sec per call for the model sizes, selected and unselected setups (one
  Chronos-2 size while experiment 4 is deferred, D123).

`REPORT.md` outline:

1. Summary in a few plain lines, negative results included.
2. Setup: data, roles, splits, warm-up, preprocessing; model, revisions, device, flags; forecasting protocol; scores,
   thresholds; metrics with all parameters.
3. Deviations from the brief and the papers, and labelled interpretations: exp 1 on 51 of 57 channels (D39, with the
   `uni57` result); FF details and the `ff-interp-block` names; max 60 is test-informed; frozen, dual,
   `seasonal-refday` (a reference-day model, not seasonal-naive), block FF, short attacks in 21.03, 10 s stride
   effect, "ICML" paper is an FMSD workshop poster, HAICon used eTaPR.
4. Results. Every number from a file in `results/phase1/`. Runs not done are reported as not run.
   - 4.1 exp 1 vs exp 2: the matched-channel comparison decides; the unmatched one mixes forecasting mode with channel
     choice and says so.
   - 4.2 boundary vs interior (key result): coverage first, rates with chance levels; the 10 s onset/interior split
     mostly does not test contamination (406 of 637 interior steps from clean context); the h-matched contrast and
     `cf-onset`; offset results per stratum, with the trip confound stated.
   - 4.3 context protection: FF per FF group, never crediting interior detection on `pre_active` attacks, with FF's
     normal-step alarm rate; frozen/dual/`seasonal-refday` with and without `P1_PCV02Z`.
   - 4.4 size vs latency: the setup was selected on 28M test results, so the comparison favours 28M; the unselected
     `uni` rolling sizes are shown next to it. (Chronos-2 run: experiment 4 deferred, D123; one size, latency only.)
   - 4.5 baselines on the same channel sets.
   - 4.6 1 s comparison against the 10 s 5M reference; 1 s vs 10 s also changes horizon and stride in seconds
     (30 s vs 300 s) and the context cap (8,192 vs 32,768). (Chronos-2 run: against the 10 s `uni` run, cap 8,192 at
     both resolutions, section 14.7; not run, D134.)
5. What the model does well and badly here (Chronos-2 for Phase 1, section 14).
6. Threats to validity: HAI in post-training data UNCONFIRMED; picks made on test results (`selection.csv`); the full
   D8 list of test-informed choices, copied verbatim; `calib2` sensitivity; device (MPS shim for Timestral, D130 for
   Chronos-2); label quirks (A209, dropped trip
   tags, PCV02Z shift and level offset); k and eps fixed a priori, N test-informed, alternatives untested.
7. Open questions.
8. Reproduction: commands, commit hash, runtimes.

---

## 13. Decisions and open questions

### Decisions (2026-10-19)

- **D1** HAI 21.03 only. 22.04/23.05 are out of scope (brief primary; git-lfs not installed).
- **D2** Ground truth = `attack`. Process labels for diagnostics only.
- **D3** The last row of every file is dropped.
- **D4** All tags read as Float64, labels as Int8.
- **D5** Channel roles by the rule in section 3.4: 22 dropped, 6 step covariates, 7 actuator commands, 44 continuous targets.
- **D6** 10 s default: mean for continuous and actuator channels, last for step covariates, max for labels. 1 s optional.
- **D7** z-score per channel with mean and std from `fit` = train2 + train3, at the run's resolution.
- **D8** (revised 2026-10-20) "Strict time-based split" = per-file roles; chronological order is impossible for
  HAI 21.03. No test row fits normalization statistics or thresholds, and no test score or test metric tuned any
  hyperparameter. These choices did use inspection of test files, test labels or the PDF attack timetable
  (test-informed). REPORT.md copies this list into "Threats to validity":
  1. `calib` = train1, because it shares the `P1_PCV02Z` level of test1, test2, test4 and the start of test5
     (test-file values, probe 08-09). Sensitivity: `calib2` (D51).
  2. `calib` cut into two 24 h pseudo-files so its context lengths look like the test files' (test-file lengths).
  3. W = 1,500 s, checked against the first-attack positions in the test labels (section 5).
  4. N = 60 s, from test post-attack excursions (probe 05) and empty-interior counts from the test labels.
  5. The 6 step tags left out of exp 1. D39 rests on train-data reasons only, but the first draft also cited test
     attack windows (probe 11).
  6. `mv-acttgt` exists because the actuator commands are attack targets (PDF timetable, probe 11).
  7. FF max duration 60 steps, from the longest test attack and the longest test post-attack excursion (D25).
  8. 1 s cap 8,192, argued in part by the 422 s longest attack being about 5 % of the context (D12).
  9. Display and diagnostics only: timeline attacks (D33), the smoke slice (chosen to contain A101), offset strata
     (D47) and `cf-onset` origins (D46).
- **D9** train1 after 2020-07-12 23:59:59 is excluded from all train-derived use; test3 is kept whole.
- **D10** `calib` = trimmed train1 as two 24 h pseudo-files; disjoint from `fit`.
- **D11** Warm-up `in_file`, W = 1,500 s unscored (150 steps at 10 s). No attack is lost. `prepend` is a config option.
- **D12** Context cap 32,768 at 10 s (never binding in-file). At 1 s, planned runs use 8,192 (cost, section 10;
  the step count stays comparable to the 10 s in-file contexts, and a 422 s attack is about 5 % of the context).
  The 32,768 run at 1 s is optional.
- **D13** H = 30, stride 30, origins at W + kH, one forecast per scored step.
- **D14** `symmetric_averaging=True`, `clip_nonnegative=False`, float32, no observation mask.
- **D15** (revised 2026-10-20) MPS with our unofficial shim if the HAI smoke check passes for every (size, setup) that
  will run on MPS (D54), else CPU. Device in the cache key. One device for all headline 10 s runs.
- **D16** Working model for experiments 1-3 and 5: Timestral-28M. It keeps every 10 s variant under 1 h on MPS.
- **D17** Band score `eps = 0.1` z units, fixed a priori. It bounds scores of zero-width bands.
- **D18** Alternative scores: `crps` (as specified by the brief) and `mae` (to mirror Lowe et al.; derived from the
  same cache, no extra inference).
- **D19** Headline aggregation: mean of top-3 channels; `max` reported beside it. Smoothing off.
- **D20** Threshold: 99.5th percentile on all scored `calib` steps, per run key, score and aggregation.
- **D21** (revised 2026-10-20) "Better" / "best" = highest test PR-AUC with top-3 mean aggregation (score `band`;
  `dual` for 3c), ties by ROC-AUC. "Better of 1 and 2" compares `mv-lit` with `uni` on the matched set `mvlit34`;
  candidates are `uni` and `mv-lit` only. "Best of 1-3" compares the base `rolling`, `ff-interp-block`, `frozen` and
  `dual` on the base setup and its full channel set. Picked on test; REPORT.md says so and cites `selection.csv`.
- **D22** Exp 2 headline follows the brief (actuator commands as past-only covariates). `mv-acttgt` (actuators as
  targets) runs as a labelled secondary, because the brief asks for a proposal on discrete channels and the data show
  actuator commands are continuous and the most directly attacked tags.
- **D23** P4 is not a group in experiment 2 and is not used as covariates. `P4_*_PS` are unused in Phase 1, except in
  the brief-literal secondary `uni57` (D39).
- **D24** (revised 2026-10-20) Forecast Fallback as in section 8 (exp 3a): paper rules where explicit (3-step trigger,
  99.5th-percentile per-feature level), labelled interpretations elsewhere. Variant names `ff-interp-block` (headline,
  no exit) and `ff-interp-block-max60-testinf`, in configs, cache keys, run keys and figure legends (D43).
- **D25** (revised 2026-10-20) Bounded FF: max duration 60 steps (10 min) at 10 s. The value is test-informed (D8
  item 7), so the variant is named `-testinf` and is not a "best of 1-3" candidate. Optional sensitivity
  `-max30`, `-max120`, fixed now, reported without a pick. Not run at 1 s.
- **D26** Frozen context = `reference` slice, last 24 h of train3 (2020-08-09 11:00:00 to 2020-08-10 10:59:59).
- **D27** Dual score = quantile W1 between recent and frozen forecasts, normalized by the frozen band width.
- **D28** (revised 2026-10-20) Baselines: `robustz` (1 h window at the origin), `lastvalue` (fit-set h-step change
  quantiles), `seasonal-refday` (a reference-day model: the clean `reference` day at the same clock time, fit-set
  day-over-day residual quantiles; not seasonal-naive on the series; no in-file lag). All in the cache schema, all 57
  channels.
- **D29** (revised 2026-10-20) Segments: N = 60 s (6 steps at 10 s, 60 at 1 s; test-informed, D8 item 4);
  sensitivity N in {3, 12} steps (30, 120 at 1 s) in an appendix. Headline segment metric = coverage (D45); the
  mechanism test is the h-matched origin contrast plus `cf-onset` (D46).
- **D30** TaPR: official `TaPR.py` vendored unmodified; headline alpha 0.5, theta 0.5, delta 180 s; also delta 0 and the
  HAICon-like threshold pair. No eTaPR.
- **D31** Multi-file TaPR: files joined with a `delta + 1` normal gap; one score over all 50 attacks.
- **D32** ROC-AUC and PR-AUC with scikit-learn on all scored test steps.
- **D33** Timeline attacks: A202, A210, A403, A217, A219, A203, chosen by duration, process and type.
- **D34** (revised 2026-10-20) Cache: long-format parquet per file, path and columns as in section 6.1. Directory
  `<variant>@<hash8>`; the hash covers the settings, the prepared input arrays and the forecasting source
  (`forecast.py`, `context.py`, `mps_shim.py`; `baselines.py` for baselines). A changed setting or changed code
  writes beside the old cache, so nothing is deleted or overwritten. Readers never fall back to a stale hash.
- **D35** Python 3.12 via uv; timestral pinned to commit `a534bdb`; torch 2.14.1; HF weights in `cache/hf`.
- **D36** The 3 dropped tags that vary in test (`P1_PCV02D`, `P2_OnOff`, `P2_Emerg`) are not used as a detector. REPORT.md
  states how many attacks they would reveal.
- **D37** (revised 2026-10-20) The 1 s comparison runs 5M `uni` rolling + `ff-interp-block` + `cf-onset`, fixed in
  advance, against the 10 s 5M reference (D52).
- **D38** Stretch models (Chronos-2, TimesFM) are not planned in this pass.

### Decisions (2026-10-20, after the critique)

- **D39** DEVIATION from the literal brief wording: experiment 1 headline forecasts 51 channels (`uni51`), not all 57
  non-constant channels. Reason, from train data and toy checks only: the 6 step tags change on at most 0.147 % of
  train steps, a constant context gives a zero-width band (P:p01 §6-7), so their band score is `dev / eps` at every
  scheduled setpoint change. The literal reading runs as the labelled secondary `uni57` (28M rolling, calib + test).
  Q17 asks Arthur which should be the headline.
- **D40** `mv-acttgt` and `uni57` are never candidates for a base or a "best" setup. A non-brief setup becomes the
  base of experiments 3 and 4 only with Arthur's OK (Q1).
- **D41** A `select` command applies D21 to `metrics.csv` and writes `results/phase1/selection.csv`. Exp 3 and 4
  configs read `setup: selected` from it. `all` runs both `select` stages and never edits a config.
- **D42** Smoke has its own dataset keys (`hai2103-10s-smoke`, `hai2103-1s-smoke`) and its own `prepared/`
  directories. It never shares a cache directory or FF thresholds with a full run.
- **D43** No FF variant name contains "paper". "Paper" is used only for the 3-step trigger and the 99.5th-percentile
  level, in descriptions.
- **D44** FF attribution: `ff_episodes.csv`; per attack `ff_active_at_onset`, `ff_n_channels_active_at_onset`,
  `ff_fallback_age_at_onset_steps`, `ff_first_trigger_after_onset_steps`; FF groups `pre_active`,
  `triggered_in_attack`, `none`; FF's normal-step alarm rate next to its coverage. Interior detection is credited to
  FF only on `triggered_in_attack` attacks.
- **D45** Headline segment metric = coverage. Every any-alarm rate is shown with its chance level `1 - (1 - p)^n`
  (p = the run's alarm rate on normal scored test steps). Equal-length `interior_eq` = attack steps N+1..2N.
- **D46** Mechanism test = post- vs pre-onset coverage within h buckets (1-10, 11-20, 21-30) and time-since-onset
  buckets, plus the `cf-onset` clean-context counterfactual (one forecast per attack from the onset step, H = L + N),
  plus `band_width_by_h.csv`. `cf-onset` is a diagnostic only.
- **D47** Offset strata: `trip` (9 attacks), `pcv02d` (5), `other`, derived in `prepare` from the dropped tags.
- **D48** Latency: median over the attacks every compared method detects, and median of the latency censored at
  duration + N. Never a median over each method's own detected subset.
- **D49** `channel_set` in every scored results CSV. Thresholds per (run key, channel set, score, agg, calib source).
  Baselines forecast all 57 channels and are scored on every set a TSFM run uses.
- **D50** Every run is also scored on `<set>-noPCV02Z`. For frozen, dual and `seasonal-refday` both versions are
  reported, because `P1_PCV02Z` in `calib` and test sits about +54 fit-z from the `reference` day (train data). The
  headline stays the full set. Decided before any result.
- **D51** `calib2` (train2, 2020-08-01 and 2020-08-02, as two pseudo-files) gives a sensitivity threshold for the
  28M `uni` and `mv-lit` rolling runs. It overlaps `fit` and is labelled so. Never used for a pick.
- **D52** The 10 s reference for the 1 s comparison: 5M `uni` rolling + `ff-interp-block` + `cf-onset` at 10 s, calib
  + test, on the same device as the 1 s block.
- **D53** Exp 4 also runs `uni` rolling at 5M and 123M (an unselected setup). REPORT.md 4.4 states that the best
  setup was selected on 28M test results.
- **D54** The MPS check covers every (size, setup) that will run on MPS (5M uni, mv-lit; 28M uni, uni57, mv-lit,
  mv-acttgt; 123M uni, mv-lit; 209M before any 209M run). It runs on the smoke slice, before any headline run.
- **D55** Timeline signals are fixed from the PDF control loops (section 12). No score picks a displayed signal.
- **D56** `configs/hai2103_attacks_pdf.csv` (50 rows: pdf_id, file, event, pdf_start, pdf_duration_s, scenarios,
  targets, pdf_page) is committed in step 2. Provenance: hand-transcribed from `HAI-PDF p.37-39`
  (`SP/hai-probe/pdf_attack_table.csv`) and matched to the label events by probe 04 (`research/hai_attacks.csv`).
  Transcription marks such as `P2_LCV01D(sic)` are kept. `prepare` joins it by (file, event index).
- **D57** Channel roles are computed on `fit` + `calib` rows only. Counts and sets are unchanged (section 3.4).
- **D58** `rolling` owns `Z_obs` (read-only, the only source of `y_true`) and a per-file `Z_ctx` copy. The FF hook
  holds state only and returns a mask. The 3-in-a-row counter carries across window boundaries.
- **D59** 1 s smoke: 2 h slices with `cap: 2048` so the cap binds, W = 1,500, H = 30, N = 60.

### Decisions (2026-10-20, implementation of steps 1-2)

- **D60** `SegmentData` holds every non-dropped channel (`Z` (C, L) float32, `channels`, `rows(names)`) plus `name`,
  `split`, `file`, `time`, `labels`, `labels_proc`; targets and covariates come from `data.setup_groups(cfg, setup)`
  (`Group(name, targets, covariates)`). Reason: `load_segment(cfg, name)` then serves every setup from one file.
- **D61** Setups are defined in `channels.setups` by process and role, not as channel lists; `prepare` asserts the
  role counts 22/6/7/44 and the set sizes 51/57/34/41. Reason: one source of truth, the roles computed from data.
- **D62** Actuator rule = name ends in `D` and is in `channels.rules.actuator_commands` (the 11 tags the PDF describes
  as valve/pump commands; 4 are dropped as constant). Reason: P4 `_FD`/`_LD` tags also end in `D` but are not commands.
- **D63** Change rate = changes / steps pooled over the 1 s fit + calib rows, within files. Step tags max 0.152 %,
  lowest other 5.01 % (`P1_FCV02D`); section 3.4's 0.147 % / 4.64 % averaged per-file rates. Same sets. Reason: literal rule.
- **D64** Prepared data in `cache/<dataset>/prepared/`: `<segment>.parquet`, `roles.parquet`, `norm_stats.parquet`,
  `attacks.parquet`, `manifest.json` (content sha256 per array, `digest`). Hash part (b) = `digest`. Reason: cheap, and
  stable across polars versions (hashes values, not parquet bytes).
- **D65** `forecast_hash(cfg, extra=None, sources=None)`: `sources` defaults to forecast.py, context.py, mps_shim.py
  (baselines.py for `model.name: baseline`) and a missing file raises. FF parameters enter only for kind `ff`, N only
  for `cf-onset`, score and metric settings never. Reason: the FF run finds its base cache via `run_dir(cfg, "rolling")`.
- **D66** `-testinf` is appended exactly when `max_duration == 60`; `-c<cap>` whenever `resolution_s == 1`. Reason:
  the literal naming rule of section 11.
- **D67** `channels.csv` and `splits.csv` carry `resolution_s` and keep rows of each prepared resolution; `splits.csv`
  adds `split` and an `excluded` row, `scored_steps` is at the row's resolution. Smoke CSVs go to `results/smoke/`.
  Reason: the 10 s and 1 s prepares must not overwrite each other, smoke must not overwrite Phase 1.
- **D68** Smoke keeps the full `fit` and `ref` segments and has no `calib2`; roles come from
  `channels.rules.roles_rows`, so smoke has the same roles and channel sets as the full runs. Reason: same code paths.
- **D69** The table code of `prepare` is in `src/tsfm_ad/tables.py`. Reason: keeps data.py under about 300 lines.
- **D70** W and N are set in seconds (`forecast.W_s`, `metrics.N_onset_s`; `config.steps()` converts), H in steps.
  The model is `model.size` + `model.revisions`; device default `mps` (D15), `--device` overrides. Reason: one value per resolution.
- **D71** `--split` (default `all`) is passed unchanged to `run_forecast` / `run_baselines`, which decide the splits a
  variant needs. `select` calls `selection.select(stage, <results>/metrics.csv, cfg["selection"])`. Reason: simplest dispatch.
- **D72** `configs/res1s_uni.yaml` exists from step 2 to prepare the 1 s data; the 1 s prepare of all files takes
  about 2 s, so it is not lazy. Reason: no cost to doing it eagerly.

### Decisions (2026-10-20, implementation of forecast, context, mps_shim)

- **D73** `setup` arguments of forecast.py/context.py are a setup's `list[Group]`; `fcfg = forecast.forecast_params(cfg)` (H, W, cap, warmup, the two flags, `multivariate` from the setup mode); `predict(fc, groups, ctx_slices, H, flags, log=None)` takes `(targets, covariates or None)` per group; `load_forecaster(model_cfg, cache_dir)`. Reason: the plan's signatures left the univariate/multivariate switch and the HF cache dir open.
- **D74** The cache `file` column and parquet name are the segment name (`train1a`, `test1`, `reference`). Reason: both calib pseudo-files come from raw file train1.
- **D75** Splits per kind (`forecast.splits_for`): rolling and ff forecast calib + test, plus calib2 when `score.calib_sources` lists it (an explicit `--split calib2` always works); frozen forecasts `ref`; cf-onset `test`; dual nothing. Reason: calib2 runs only where D51 uses it, with no config edit at run time.
- **D76** FF cache key: `extra = {ff_tau_sha256: sha256 of the sorted (channel, tau) JSON}`. `context.ff_extra(cfg)` recomputes it from the base rolling calib cache (None for other kinds), so readers use `cache.read(cfg, split, extra=context.ff_extra(cfg))`. Reason: readers must find the FF directory without inference.
- **D77** FF episodes are written per file to `<run_dir>/<split>/<file>.ff_episodes.csv` (start_t = trigger step = first substituted step, end_t inclusive, exit `max_duration` or `file_end`) and collected into `ff_episodes.csv` (+ `overlaps_attack_id`, `active_at_onset_of`) and `ff_thresholds.csv` (run_key, hash8, channel, tau), replacing rows of the same run_key and hash8. Per-attack FF attribution is `context.ff_attack_state(episodes, attacks, N, channels)`. Reason: one implementation for evaluate to call.
- **D78** Fallback details: `max_duration` counts substituted steps (an episode holds exactly that many), the run counter restarts at 0 on the next step; scope `all` puts every idle channel in fallback at any channel's trigger. Reason: section 8 leaves them open.
- **D79** `estimate_runtime`: one untimed warm-up call, then 3 timed calls at the shortest, median and longest context of the run, interpolated over every origin; printed before every rolling/ff forecast (frozen and cf-onset take seconds). Reason: the first MPS call of a shape compiles kernels.
- **D80** `calls_<split>.csv` rows = target + covariate rows of the call, seconds by `time.perf_counter` around the call and the `.cpu()` copy; `runs.csv` gets one row per forecast split. On macOS perf_counter stops during system sleep, so per-call latency excludes sleep and `runs.csv` wall-clock includes it. Reason: clean latency.csv.
- **D81** `prepend` takes the last `cap` steps of segment `train3`, all channels; it also applies to ff; cf-onset always uses in-file history. Reason: section 5 and D46.

### Decisions (2026-10-20, implementation of baselines, selection, plots)

- **D82** `run_baselines(cfg, split)` runs the baseline named by `cfg.setup`, or all three when `cfg.setup` is not a baseline name; each run's config is `baselines.baseline_cfg(cfg, name)` (model.name `baseline`, setup = name, kind rolling, so the variant is `rolling` or `rolling-c<cap>`). `--split all` = calib + test, `ref` is a no-op, `calib2` only on request; `warmup: prepend` is refused; one `runs.csv` row per written split (device cpu, n_calls 0); rows channel-major like forecast.py. Reason: one call per config; D51's calib2 is TSFM-only and baselines read in-file history only.
- **D83** Baseline details: `ctx_len` = in-file steps a forecast reads (robustz min(o, window), lastvalue 1, seasonal-refday 0); robustz uses the history that exists before o (at least W); lastvalue's Delta_h and seasonal-refday's D pool every start step within each fit segment, never across segments; seasonal-refday maps clock time to the reference day by seconds of day and refuses a reference that is not one contiguous `season_s`; quantiles use numpy's linear method. Reason: the cache schema needs `ctx_len` and section 8 leaves these open.
- **D84** `select` filters metrics.csv to `agg = topk` and `calib_source = calib` (AUCs do not depend on it). If several (dataset, model) pairs have both uni and mv-lit rolling rows on mvlit34, the 28M working model decides (D16; optional `selection.dataset`, `selection.model`, `selection.model_size` override). Exact ties keep uni (base) and the order rolling, ff-interp-block, frozen, dual (best). A missing candidate, an undefined metric or duplicate rows of one candidate are errors. Reported-only rows (uni on uni51, mv-acttgt and uni on mvacttgt41; ff-interp-block-max60-testinf) have an empty rank. `selection.csv` sits next to metrics.csv and keeps the other stage's rows. Reason: D21 applied deterministically, never on a partial candidate set.
- **D85** `selected(stage, path=None)` reads `<project>/results/phase1/selection.csv` by default (config.resolve_setup passes only the stage) and returns setup, variant, kind (rolling, ff, frozen, dual), channel_set (the setup's full set), score, dataset, model, hash8, run_key, pr_auc, roc_auc. `selected("best")` raises when the best pick is not on the current base pick. Reason: exp 4 needs the kind, and a re-run base must invalidate the old best.
- **D86** Plots: the methods are the base setup's (selection.csv base pick, else `cfg.setup`) rolling, ff-interp-block, frozen and dual runs plus the 3 baselines, and ff-interp-block-max60-testinf in the summary figures. Run directories come from the recomputed hash (`context.ff_extra` for FF, D76), CSV rows from the run key (the last hash8 if several, printed). Aggregated scores are read from `scores/<channel_set>/agg_test.parquet` as a column `<score>_<agg>` or long columns `score, agg, value`. The timeline band is the base rolling test forecast; score panels use a symlog axis, linear up to the calib threshold. A101 (smoke only) shows the P1-PC loop signals. Reason: figures from cache and results only, and every missing method is printed, never dropped silently.

### Decisions (2026-10-20, implementation of score, evaluate, tapr_wrap)

- **D87** A run is scored on every set of `data.channel_sets` (incl. `-noPCV02Z`) whose channels it all forecast: uni on uni51, mvlit34, mvacttgt41; uni57 and baselines on all 8; mv-lit on mvlit34; mv-acttgt on mvacttgt41 and mvlit34 (each + `-noPCV02Z`). Reason: one rule gives D49's restricted views and the baseline sets; extra views are scoring only and never candidates (D40).
- **D88** `score` writes `scores/manifest.json` (score settings, sets, columns, calib sources), and per set `agg_<split>.parquet` (one row per scored step: file, t, time, origin, h, label, `<score>_<agg>`) and `thresholds.parquet`; per-channel `scores_<split>.parquet` (file, t, origin, channel, band, crps, mae) only in the largest set's directory. `evaluate` stops with "run score first" if the manifest is missing or was made with other score settings. Reason: per-set channel files would take several GB at 1 s; the smaller sets are filters of the largest.
- **D89** Aggregations: `score.agg` (topk, max) for every score, `mean` only with mae; the dual variant scores only `dual`. Smoothing (`score.smooth: k > 1`) runs per file after aggregation, on calib and test alike, and is part of the agg label (`topk-s5`). The headline agg is the first of `score.agg`. Reason: smoothed and unsmoothed rows never share a key.
- **D90** Thresholds per listed `score.calib_sources`, plus `calib2` whenever the run's cache holds it (frozen: listed sources only). metrics.csv has a row per calib source; TaPR, segments, by-h and cf-onset use the first listed source (`calib`) only. Reason: those CSVs have no calib_source column (section 12), and calib2 is a sensitivity threshold (D51).
- **D91** Results CSVs are upserted by key (thresholds: run_key, channel_set, score, agg, smooth, pct, calib_source; the others: run_key, channel_set, score, agg plus calib_source / config / N, attack_id / N, segment, origin_side, h_bucket, tso_bucket / split, h / N, stratum, ff_group / attack_id, segment, origin_side). `run_key` = dataset/model/setup/variant, followed by separate dataset, model, setup, variant, hash8 columns; a new hash replaces the old hash's rows of the same key; rows stay grouped by run_key. Reason: re-running one run never touches another run's rows.
- **D92** Segments are cut per test file on the scored steps (t >= W) and must match attacks.parquet. Offset stops at the next attack and the file end. Latency = first alarm in [start, end]; a miss is censored at (L + N) steps x resolution. Origin side: post if origin > onset step; the per-attack pre/post coverage is over the attack steps, and by-h rows use the same rule for every segment. `p_normal` = alarm rate on label-0 scored test steps, also written to segments_per_attack.csv. Reason: section 9 leaves these open; the summary is recomputed from that CSV.
- **D93** The N sensitivity rows (`N_sensitivity_s`) are written only for the headline score and agg (band, or dual for dual; topk); segments_by_h only at the headline N. Reason: appendix use only, and the CSVs are committed.
- **D94** Latency comparison set (D48): every method in segments_per_attack.csv with the same dataset, channel_set, agg and N, and the same score, with band and dual counted as one headline score. `latency_common_median_s` is over the attacks all of them detect, within each summary subset (all, each stratum, each FF group; no stratum x FF-group cross). Evaluating a run recomputes the summary rows of every method in its groups. Reason: D48 needs a fixed comparison set; the last evaluate pass makes it consistent.
- **D95** `evaluate` takes FF attribution from `context.ff_attack_state` over every channel of the setup (D77), so an episode that starts at the onset step counts as active at onset (`pre_active`, no interior credit for FF); the FF directory comes from `context.ff_extra` (D76). Reason: one implementation, the conservative reading of D44.
- **D96** Point metrics: alarm = score > threshold; precision 0 without alarms; `fa_per_hour` = false-alarm steps per hour of label-0 test steps; AUCs NaN for one-class labels; `pa_f1_inflated` marks every label run with any alarm as detected. Reason: section 9 leaves these open.
- **D97** `cf-onset` is scored on test only, with no threshold of its own. Its evaluate compares it with the rolling run of the same model and setup, joined on (file, t), at the rolling run's calib threshold, per attack, segment and rolling origin side; the `h_cf <= 30` subset uses the counterfactual horizon. band_width_by_h covers the cached splits of forecast runs, `ref` for frozen, test for cf-onset, nothing for dual. Reason: D46.
- **D98** TaPR: delta_steps = steps(cfg, delta_s); files are joined in name order with delta + 1 normal steps between them; haicon_like uses one TaPR object for TaR (theta_r) and one for TaP (theta_p); tapr.csv records theta_r = theta_p = theta for single-theta configs. `load_official` checks the vendored TaPR.py sha256. Reason: D30, D31.

### Decisions (2026-10-20, integration and smoke: steps 3-6)

- **D99** (revises D77) The FF results CSVs and the per-attack FF attribution live in `ff_results.py`, not in `context.py`: `read_episodes`, `ff_attack_state`, `write_ff_results`. `evaluate` writes `ff_thresholds.csv`, `ff_episodes.csv` and the new `ff_activity.csv` for every FF run, so they rebuild from the cache; `forecast` writes only the cache and the per-file `<split>/<file>.ff_episodes.csv`. Rows are replaced by run_key (any older hash too, as D91). `ff_activity.csv`: one row per (split, file, channel) of the setup, zeros where a channel never triggered, plus `scored_steps`. Reason: editing reporting code must not change the forecast hash (section 6.1), and `ff_activity.csv` had no writer.
- **D100** `evaluate.py` and `plots.py` are split to stay near 300 lines: `summary.py` (segments_summary, the common-set latency, cf_onset.csv) and `plot_util.py` (style, colours, method list, run lookup, panels). `evaluate` and `plots` still expose every name of section 11. `data.py` stays at 317 lines. Reason: code style.
- **D101** `load_forecaster` first loads with `local_files_only=True` and downloads only when the pinned weights are not in `cache/hf`. Reason: no network call on every run; a fresh clone still works.
- **D102** `variant.kind: selected` (with `selection_stage: best`) joins `setup: selected`. `config.resolve_selected(cfg)` replaces both in memory from `<paths.results>/selection.csv` (the config's own results directory, so smoke reads `results/smoke/selection.csv`); the CLI does it for forecast, baselines, score, evaluate and plot. `selection.rule_for(cfg)` restricts `select` to the config's dataset and model tag (size and device), in the CLI and in `smoke`/`all`. Reason: experiment 4 needs the best kind, and other sizes or devices in one metrics.csv must not take part in a pick.
- **D103** Configs of section 11: `exp1_uni` and `exp2_mv` list `score.calib_sources: [calib, calib2]` (D51; `forecast` then runs calib2, D75); `exp3*`, `opt_prepend` and `opt_ff_max_sens` use `setup: selected` (stage base); `exp4_5m`, `exp4_123m`, `exp4_209m` use `setup` and `variant.kind: selected` (stage best); `exp5_baselines` sets `model.name: baseline`; `opt_ff_max_sens` holds `sweep.max_duration: [30, 120]`, which `all --optional` expands into two runs; `model.params` (section 1) feeds size_latency.csv. `smoke.yaml` draws the timeline of A101 only. Reason: one config per planned row, no config edited at run time (D41).
- **D104** `smoke`: prepare both smoke slices; at 10 s every setup (uni, uni57, mv-lit, mv-acttgt) times every variant (rolling, prepend, frozen, dual, ff-interp-block, ff-interp-block-max60-testinf, cf-onset), the baselines, `select` base and best on the smoke metrics (exercise only) and the selected best run (exercises `selected`); at 1 s uni rolling, ff-interp-block, cf-onset and the baselines; latency tables; figures; then the MPS check (D105). Smoke results go to `results/smoke/`, except `mps_check.csv`, which decides the device of the real runs and goes to `results/phase1/`. The chain runs on the configured device; the CPU vs MPS comparison is the check. Reason: section 11 lists these runs; running the whole chain twice adds nothing the check does not cover.
- **D105** MPS check (D54): every (size, setup) in `mps_check` of `smoke.yaml` (5M uni, mv-lit; 28M uni, uni57, mv-lit, mv-acttgt; 123M uni, mv-lit) and of `smoke_1s.yaml` (5M uni at 1 s, because the 1 s block may run on MPS): rolling on calib + test on cpu and on mps, each scored with its own smoke calib threshold. Pass exactly as D54: max |q_mps - q_cpu| <= 1e-3 z over the 21 quantiles of every cached row, and identical test alarms (band, top-3 mean, the setup's full channel set). `mps_check.csv` adds `dataset`, `max_abs_diff_excl_PCV02Z`, `max_rel_diff` (|diff| / (|q_cpu| + 1)), both thresholds and alarm counts as diagnostics only. 209M is checked only by `all --optional` on mps (`mps_check_optional`). `all` refuses any non-smoke Timestral run on mps while a check row fails or its (resolution, size, setup) has no row. Reason: D15 and D54, enforced in code.
- **D106** `all` order: smoke; prepare 10 s and 1 s; exp 1 uni rolling (+ calib2), uni cf-onset, uni57; exp 2 mv-lit rolling (+ calib2), mv-lit cf-onset, mv-acttgt; exp 5; select base; 3b, 3c, 3a (ff-interp-block, then -max60-testinf); select best; exp 4 (5M best, 123M best, 5M uni, 123M uni); the 10 s 5M reference (rolling, ff, cf-onset); 1 s (rolling, baselines, cf-onset, ff); the optional runs with `--optional`; then latency.csv, size_latency.csv and the 10 s and 1 s figures. One run = one chain: the forecasts its kind needs (ff: rolling calib; dual: rolling and frozen), its own forecast, score, evaluate. There is no final re-evaluate pass: every evaluate recomputes the summary rows of all methods in its comparison groups (D94), so the last one leaves them consistent. Section 8's items 7 and 8 are swapped so tables and figures include optional runs. Reason: section 8 order, with prerequisites explicit.
- **D107** Resumable and fault-tolerant: cached forecast files are skipped (D34); score + evaluate are skipped when `scores/done.json` holds the same fingerprint (score and metrics settings, results directory, sha256 of score.py, evaluate.py, summary.py, tapr_wrap.py, ff_results.py, and path, size and mtime of every input parquet) and the results CSV has the run's rows. A failing step prints its traceback, is listed in `cache/logs/<command>_failures.csv` (rewritten per invocation), and the next run goes on; the command exits 1 at the end if any step failed. Reason: hours of 1 s TaPR must not rerun on a restart, and one broken run must not stop the matrix.
- **D108** `latency.py` writes `latency.csv` (per Timestral run, split and context bucket 1-512, 513-2048, 2049-8192, 8193-32768 steps: median rows per call, n_calls, sec_median, sec_p90, from `calls_<split>.csv`) and `size_latency.csv` (per size the best (setup, variant) and the unselected uni rolling: sec_per_call_median from `calls_test.csv`, `calls_ref.csv` for frozen, the rolling run's for dual; `test_wallclock_s` from runs.csv at the matching forecast hash, sleep included; AUCs, headline TaPR F1 and onset/interior coverage at the headline N on the setup's full channel set, band or dual, top-3, calib). A multivariate call is one process group. A run that did not happen is not a row (printed as skipped). Reason: section 12 lists both files without a writer.
- **D109** Figures of a 1 s config go to `figures/<dataset key>/`, so they never overwrite the 10 s figures; `all` and `smoke` draw the 1 s figures with setup uni (the only 1 s setup); `size_latency.png` shows only rows of the config's dataset. Reason: one results directory holds both resolutions.
- **D110** Device: `cpu` for every headline run (D15), set in `configs/base.yaml`. The D54 check failed for 8 of its 9 (size, setup) rows (`results/phase1/mps_check.csv`): max |q_mps - q_cpu| 2.2e-3 to 1.95e-2 z, always on `P1_PCV02Z`, whose values reach hundreds of fit-z (tiny fit std, section 3.4), so the gap is float32 rounding (relative gap at most 7.6e-4). Without `P1_PCV02Z` every row stays at or below 9.8e-4 z, and the test alarms are identical in all 9 rows. Only 5M uni at 10 s passes (8.0e-4). Section 10's MPS hours grow by about 1.85x (its own CPU columns): about 12 h if the best setup is uni + FF, about 15 h if mv-lit + FF. Reason: D15 and D54 as written; relaxing the tolerance is Arthur's call (Q18).

### Decisions (2026-10-20, review fixes)

- **D111** Readers refuse an incomplete split: `cache.read` (by default), `score`, FF tau (`context.ff_tau`) and evaluate's band widths read the parquet of every segment the config lists for the split (`cache.split_paths`) and stop with "run forecast first" when one is missing; `score` checks every split before writing anything. `evaluate` stops when an attack of attacks.parquet is not in the scored test steps. Reason: thresholds and FF tau come from the whole calib and metrics from the whole test, never from what an interrupted forecast left behind.
- **D112** (revises D107) The score + evaluate fingerprint also holds `cfg.channels` and the sha256 of `data.py`. Reason: the scored channel sets (`extra_sets`, every setup's targets) and the attack table come from them, and neither is in the forecast hash.
- **D113** (revises D84, D85) `select` (the CLI and pipeline pass the config) recomputes each candidate's current forecast hash (`selection.run_cfg`: the config with the candidate's setup, kind, model size and device, in-file warm-up) and refuses metrics rows of any other hash; a reported-only row of another hash is left out and printed. A failed `select` removes that stage's rows from selection.csv. `resolve_selected` checks the pick's hash8 the same way and stops with "select again" when it is not current. Reason: D21 picks are made on, and used with, the current forecasts only (D34).
- **D114** (revises D86, D108) Figures take results rows only at the current hash8 of each method's run directory (FF via `context.ff_extra`); a method without a directory or without rows at that hash is skipped and printed. `size_latency.png` and the cf-onset panel keep only rows whose run (rebuilt from the row's run key) still has their hash8. `size_latency.csv` holds one row per (dataset, model, selected); an entry that is skipped, or whose run directory does not exist, also loses its old row. Reason: section 6.1, readers never fall back to a stale hash; a new best pick must replace the old one.
- **D115** `model.cpu_threads` is part of the forecast hash (settings (a)). Reason: torch's thread count changes CPU results (up to 1.9e-5 z between 4 and 10 threads on the smoke slice), and the MPS shim runs float64 statistics on CPU.
- **D116** (revises D80) A file's forecast calls are appended to `calls_<split>.csv` only after its parquet is written; `runs.csv` gets one row per invocation and split for the files that invocation wrote (also when a later file fails), with `wallclock_s` the sum of those files' times. `size_latency.csv` `test_wallclock_s` sums the rows of the run's hash and split. Reason: a resumed run neither counts the calls of an interrupted file twice nor loses the wall-clock of the files written before the interruption.

### Decisions (2026-10-20, model switch to Chronos-2, section 14)

- **D117** (Arthur's decision; supersedes D16, D35 and D38 for Phase 1 runs) Phase 1 runs on `amazon/chronos-2` @
  `29ec376` through `chronos-forecasting==2.3.2`, float32, `model.name: chronos2` in `configs/base.yaml`. Run-key model
  tag `chronos2-<rev7>-<device>`, e.g. `chronos2-29ec376-cpu`. Timestral is paused: `load_forecaster` raises for
  `model.name: timestral` unless `TSFM_ALLOW_TIMESTRAL=1` ("licence pause, see CLAUDE.md"); the `timestral` package
  stays installed (code only). Reason: the Timestral licence (CLAUDE.md, Q7).
- **D118** (revises D12 at 10 s) `model.max_context` = `forecast.cap` = 8,192, the Chronos-2 maximum, at 10 s and 1 s.
  Reason: the model cuts longer input silently, so `ctx_len` in the cache must be what the model read; the adapter
  also refuses T > 8,192. The cap binds at 10 s on 18.4 % of scored test steps (14.6).
- **D119** Adapter `model_chronos2.py`: the model is built with `Chronos2Model.from_pretrained` and wrapped in
  `Chronos2Pipeline` (no unpinned adapter lookup); at load it checks the package pin, the 21 levels against the
  cache levels, float32 weights and the context maximum. Univariate setups: one `(V, 1, T)` array (V items, V
  groups), `cross_learning=False`. Multivariate setups: one dict item per process group with the covariates as named
  1-D past covariates. `limit_prediction_length=True`. Output permuted to `(V, H, 21)`; non-finite output raises;
  crossing quantiles are sorted (monotone rearrangement) and counted. Reason: 14.3-14.5.
- **D120** (revises D65 and section 6.1 (c)) Hashed sources per model: `config.MODEL_SOURCES` = forecast.py,
  context.py plus model_chronos2.py (chronos2) or mps_shim.py (timestral); baselines.py for baselines. The Timestral
  flags `symmetric_averaging` and `clip_nonnegative` are left out of the Chronos-2 forecast hash; the hashed model
  settings are repo, revision, package, dtype, device, max_context and cpu_threads (kept, D115, although Chronos-2
  gives identical bits at 1, 4 and 10 threads). Reason: editing one model's adapter must not invalidate the other's
  caches, and settings the model ignores must not split caches.
- **D121** (Chronos-2 counterpart of D110) Device: `cpu` at 4 threads for every headline run (`model.device: cpu`,
  D15). The Chronos-2 D54 check fails the 1e-3 z rule in all 5 rows, every time on `P1_PCV02Z` (values up to about
  510 fit-z; 1.04e-3 to 2.69e-3 z), while every other channel stays at or below 8.2e-4 z and the test alarms are
  identical (14.8). MPS would be about 1.8x faster. Relaxing the rule (Q18) is Arthur's call and applies here too.
- **D122** `runs.csv` column `timestral_commit` becomes `model_code` (the Timestral commit or the
  chronos-forecasting pin), written by `cache.append_run` for forecasts and baselines; a file with the old header
  gets the new header in place, rows unchanged. Reason: the column must name the code of either model.
- **D123** (revises D37, D52, D54, D105, D106 for Chronos-2) Run matrix of 14.7. Experiment 4 is deferred until
  Timestral permission and its configs, the 5M 10 s reference, the 1 s cap 32,768 run and the Timestral smoke
  settings moved to `configs/timestral/` (with `configs/timestral/base.yaml` = Timestral, cap 32,768); `smoke` and
  `all` load only top-level configs (a test checks it). The 10 s reference of the 1 s comparison is the 10 s
  Chronos-2 `uni` run on the same device (`res10s_uni_ff.yaml` adds the FF run). The MPS check covers every
  setup that runs on MPS: uni, uni57, mv-lit, mv-acttgt at 10 s and uni at 1 s; `mps_check.csv` rows carry the
  model id (`chronos2-29ec376`), and the MPS guard reads only rows of the run's model family, so the failed
  Timestral rows (D110) neither block nor allow a Chronos-2 run. Reason: one model size; same-device reference.
- **D124** (moves D37's 1 s block; revises D106) The 1 s comparison block (1 s `uni` rolling, its baselines,
  cf-onset and ff-interp-block, plus the 10 s `uni` FF reference) runs only with `all --optional`, after the 10 s
  matrix, followed by prepend and FF max30/120. Reason: on CPU every 1 s TSFM run costs about 23.7 h (18,810 calls of
  51 rows, nearly all at 8,192 steps), so the default matrix would be about 56 h (32 h with only the 1 s FF moved)
  instead of 8.4-8.7 h of inference (14.8). It is the brief's optional config and no headline depends on it (Q20).
- **D125** (revises D104) `smoke` runs the same chain on Chronos-2 (no 5M); `smoke.yaml` and `smoke_1s.yaml` carry
  Chronos-2 MPS-check items without a `size` (a `size` names a Timestral size). Reason: same code paths as the full
  runs.
- **D126** `latency.csv` covers every TSFM run (chronos2 and timestral); `size_latency.csv` takes the parameter count
  from `config.model_params`; the size-latency figure labels the selected line "selected on test results" and
  names a point by its Timestral size or else its model name. Reason: one Chronos-2 size still needs its latency
  row.
- **D127** Adapter tests (`tests/test_chronos2.py`, `tests/fakes.py`): a fake pipeline with the input checks of the
  real one (column and row order, call shape, covariates, crossing, cap, constant rows), a tiny randomly initialised
  `Chronos2Model` for the bit-identical independence check and the constant-covariate level check (no download; a
  mutation script shows both fail when the adapter is broken), the same independence check with the pinned weights
  when they are in `cache/hf`, the Timestral guard, and the config layout. The run_forecast tests run the smoke
  config (Chronos-2) on the fake. Reason: CLAUDE.md "tests where a silent bug changes results".
- **D128** Constant rows: the adapter passes a row that is constant over its context as exact zeros and adds a
  constant target's value back to its quantiles; `calls_<split>.csv` logs `crossed`, `forecasts` and `const_rows`
  per call (old three-column files stay as they are). Reason: Chronos-2's exact `scale == 0` test misses most
  constant rows by one float32 rounding step, so such a row entered as +-0.88 or 0 depending on device and level,
  and moved mv-lit targets by up to 5.2 z between CPU and MPS on the smoke slice (14.5). INTERPRETATION of the
  model's own handling of constant series; REPORT.md states it, with its size against the raw model on CPU (D129).
- **D129** (review 2) `tsfm-ad d128` (`d128.py`, reporting code, not a hashed source; it never touches the forecast
  cache) measures the D128 guard against the raw model on the run's device. For every call whose context holds a
  constant row in a rolling (in-file warm-up), cf-onset or frozen run, it compares `model_chronos2.predict_group`
  with the same function with `_zero_constant_rows` switched to the identity (crossings still sorted); every other
  call is bit-identical by construction and counts as 0. A univariate call reruns only its constant rows, as a batch
  of their own (independent rows, 14.4). Output: `d128_effect.csv` (per run key, hash8 and split) and
  `d128_effect_channels.csv` (per target channel), columns in section 12. `smoke` runs it on the smoke slice (uni and
  mv-lit rolling, mv-lit cf-onset and frozen); `all` after experiment 2 (uni and mv-lit rolling and cf-onset,
  mv-acttgt rolling) and after 3b (frozen on the base), skipping a run key, hash and split already in the file. The
  10 s full set was measured on 2026-10-20 (these contexts depend on no result): 1,346 calls x 2, 20 min on CPU.
  FF and prepend runs are not measured. Reason: CLAUDE.md, the size of an interpretation must be reported; the
  CPU-vs-MPS gap of 14.5 was not that size.
- **D130** (Arthur, 2026-10-20, answer to Q18) The D54 rule is relative: pass = max |q_mps - q_cpu| / (|q_cpu| + 1)
  <= 1e-3 and identical test alarms (1e-3 z near zero, 0.1 % of the value for large values). Reason: the absolute
  rule fails only through `P1_PCV02Z`, whose values reach about 510 fit-z, where float32 rounding alone exceeds
  1e-3 z; Arthur wants the Phase 1 runs done the same night, and MPS is about 1.8x faster. All five Chronos-2 rows
  pass (max relative gap 5.6e-5 to 1.4e-4, at least 7x inside the rule; alarms identical; `mps_check.csv`). Every
  headline run is on MPS: `model.device: mps` in `configs/base.yaml`, cache keys `chronos2-29ec376-mps`
  (D15 still holds: one device for all headline runs). This rule was set after seeing the check's numbers, and
  REPORT.md says so. It replaces D121. The Timestral rows (D110) are unchanged and stay failed.
- **D131** `all --optional 10s` runs prepend and FF max30/120 after the matrix and before `latency.csv` and the
  10 s plots; a bare `--optional` (= `all`) then adds the 1 s block, then the tables again and the 1 s plots. Reason:
  the 10 s optional runs and the report can finish the same night while the 1 s block (about 27 h on MPS) runs on.
- **D132** `smoke` runs on cpu (`model.device: cpu` in `configs/smoke.yaml`), the reference device of the D54 check;
  the headline runs are on mps (D130), and the check runs every smoke rolling forecast on both devices. Reason: the
  smoke already passed on cpu, and re-running it on mps would cost about 20 minutes of the same night.
- **D133** `tsfm-ad diagnostics` (`diagnostics.py`, reporting code, not a hashed source) writes
  `quantile_diagnostics.csv`: per run key, hash8 and split, the quantile crossings the adapter sorted (D119) and
  the constant rows the D128 guard zeroed, both summed from `calls_<split>.csv`, and the share of cached forecasts
  whose band q95 - q05 exceeds 10 and 100 fit-z and whose tail q99 - q01 exceeds 100 and 1000 fit-z (all and, on
  test, attack steps only), with the widest band and its channel. Reason: 14.5 and 14.9 items 10-11 require
  REPORT.md to give the crossing rates and the prevalence of exploding outer quantiles, and every REPORT number
  must come from `results/`. The cut-offs are fixed and descriptive; nothing reads the file. `all` and `smoke`
  write it together with `latency.csv`.
- **D134** (Arthur, 2026-10-20 19:50) The 1 s block of D131 is not started after `all --optional 10s`.
  `REPORT.md` is written from the 10 s results first and reports the 1 s block as not run; whether and how it
  runs is decided with Arthur afterwards, together with the other next steps. Reason: Arthur wants the report
  and a discussion of how to continue before about 27 h of compute. No code changes: `all --optional` still
  runs it.
- **D135** (Arthur asked for both, 2026-10-20 21:50) `tsfm-ad compare` (`compare.py`, reporting code, not a hashed
  source; `all` runs it after the 10 s plots) writes `fa_matched.csv`, `bootstrap_ci.csv` and `bootstrap_paired.csv`.
  (a) Matched false-alarm rate: per method, channel set and score (band, the dual score for dual, crps, mae; top-3),
  the threshold that leaves at most floor(F x normal hours) normal test steps above it, for F = 0.5, 1, 2 and 5
  false-alarm steps per normal hour; precision, recall, TaPR (headline config), attacks detected and mean onset,
  interior and offset coverage (N = 6) at that threshold. It is set from the test labels, like a point of the ROC
  curve: an evaluation that compares methods at equal false alarms, with the same rule for every method. No pick
  reads it, REPORT.md labels it, and the headline stays the calib threshold (D20). (b) Paired block bootstrap of the
  test steps: 1 h blocks per file, a cut never inside an attack or its 180 s TaPR delta zone, B = 1000 resamples of
  the blocks with replacement, the same resamples for every method of a set, 95 % percentile intervals. Metrics:
  PR-AUC, ROC-AUC, TaPR F1 at the calib threshold, and recall, TaPR F1 and attack detection rate at each matched
  target (the threshold recomputed in every resample); paired differences against the set's Chronos-2 reference
  (`mv-lit` rolling on `mvlit34`, `uni` rolling on `uni51`). Methods: `compare.sets` in `configs/base.yaml`. The
  targets, B, block length and seed were fixed there before any compare result. Limits: TaPR of a resample joins
  blocks from different times; resampling 1 h blocks treats them as exchangeable; with 50 attacks the intervals are
  wide. Reason: Phase 1 had no measure of noise (REPORT.md 6.2 item 1), and the calib threshold puts the methods at
  different test false-alarm rates (1.1 to 6.4 per hour), so neither the uni-vs-mv tie nor the comparison with
  `lastvalue` could be judged.
- **D136** (Arthur, 2026-10-20 22:50: Q19 go, "ok for the small package") `autogluon/chronos-2-small` @ `ddec013`
  (27,934,624 parameters, Apache-2.0, context 8,192, 13 quantile levels 0.01, 0.05, 0.1, 0.2, ..., 0.9, 0.95, 0.99) runs
  experiment 1 `uni` rolling on calib and test (`configs/opt_small_uni.yaml`; no calib2). A size sensitivity, not
  experiment 4 (deferred, D123). It goes through the unchanged Chronos-2 adapter: `model_chronos2_small.py` wraps its
  pipeline so `predict` returns the 21 cache levels, the 8 missing ones (0.15, 0.25, ..., 0.85) interpolated linearly
  in the level between their native neighbours (no extrapolation). q01, q05, q50, q95 and q99 are native, so band and
  mae do not depend on the interpolation; crps does (INTERPRETATION). The CLI installs the wrapper when
  `model.chronos2.adapter` names it; `config.model_sources` adds that file to the small model's hashed sources only,
  and `model.chronos2.tag: small` gives the cache key `chronos2-small-ddec013-<device>`. `forecast.py` and
  `model_chronos2.py` stay byte-identical, so no `amazon/chronos-2` cache key changed (checked: c06bc843, 47703ec2,
  93cc0822, 0201a687 unchanged). The D54 check on the 10 s smoke slice (`configs/smoke_small.yaml`) passed on MPS
  (max relative gap 4.3e-5, alarms identical; `mps_check.csv`), so it runs on MPS. `tsfm-ad compare` adds it to the
  `uni51` pairs and writes `forecast_accuracy.csv` (mae, crps and q05-q95 coverage per method on calib, test normal
  and test attack steps). Not in `all`: the commands are in README.md.
- **D137** (Arthur, 2026-10-20: option A after C) Lowe et al.'s setting on HAI as a sensitivity: 1 s data, history
  capped at 128 steps (their longest input, Table 2), H = 30 (their 16 and 32 are not tested; ours steps by H),
  same warm-up W = 1,500 and scored steps as the planned 1 s run, `uni` only. Runs: rolling (calib, calib2, test),
  cf-onset, the three 1 s baselines (`res1s_uni.yaml`, cap-free) and `ff-interp-block` with thresholds from its own
  cap-128 calib (`configs/res1s_uni_c128.yaml`, `res1s_ff_interp_block_c128.yaml`; script order as in
  `pipeline.run_chain`). At 1 s a 128-step history is 128 s, so most HAI attacks (17-422 s) are longer than the
  window: the paper's "long-context" case. The cap is a method change against D118 and is reported as such, never
  as a headline. The planned 1 s block at cap 8,192 (D134) stays not run. Outcome: rolling, cf-onset and the baselines ran; `ff-interp-block`
  (no exit) failed on the first calib file with "Chronos-2 returned non-finite quantiles": once the 128-step context
  is all FF median forecasts, Chronos-2 extends its own trend and the values grow geometrically (about 3 % per call)
  to about 3e19 fit-z on `P4_ST_PT01` and 1e11 on `P3_PIT01` after 940 calls, then overflow (probe in REPORT.md 4.19).
  That is a property of our FF interpretation with a short window and no exit, reported as a result; the code was
  not changed. The planned bounded variants (max 30 and 120 steps, D25) then ran in the same setting
  (`res1s_ff_interp_block_c128_max{30,120}.yaml`). Control: 10 s `uni` rolling with cap 128
  (`res10s_uni_c128.yaml`), so context length (10 s, 8,192 vs 128) and resolution (128 steps, 10 s vs 1 s) can be
  separated. `config.variant_name` now appends `-c<cap>` also at 10 s when the cap is below `model.max_context`
  (otherwise that run would share the headline run key and overwrite its rows); no existing run key or hash changed.
- **D138** (Arthur, 2026-10-21 00:20: "start b"; Q4) Option B: experiment 1 `uni` rolling at 10 s with H = 6, stride
  6 (a new forecast every minute), history up to 8,192 as in the headline, calib and test only, thresholds from its
  own calib (`configs/res10s_uni_h6.yaml`). It isolates the restart rate at the headline resolution and history
  length, the cell section 4.19 leaves open. `config.variant_name` appends `-h<H>` when H is not 30 and
  `selection.run_cfg` parses it back; no existing run key or hash changed. `compare` pairs it, and the 10 s cap-128
  control, with `uni` rolling on `uni51`. A sensitivity, not a headline: H = 30 stays the brief's default.
- **D139** (Arthur, 2026-10-21 08:00) The brief's "I download it manually to data/lanl/" is lifted: Claude downloads
  the LANL files. The site's form (csr.lanl.gov/data/cyber1/, `/js/fence.js`) sends an email and a usage note to
  `/data-fence/token` and returns a download token; Arthur approved submitting his email address and "Personal,
  non-commercial research: testing time-series foundation models for anomaly detection on per-minute auth and flow
  counts with injected anomalies; results in a blog post, dataset cited." Files: auth.txt.gz (7,626,505,158 bytes),
  flows.txt.gz, redteam.txt.gz, fetched in parallel byte ranges and checked against Content-Length. Licence: LANL
  waived all copyright (page footer); cite Kent 2015 (doi 10.17021/1179829).
- **D140** Phase 2 series (PLAN.md 15.2): 13 per-minute series in three groups (tenant 3, dc 5, host 5); top-5
  destinations and flow sources by volume on the fit days only; machine accounts (`...$@...`) excluded from distinct
  users; a flow's bytes count at its start minute. Aggregated by DuckDB straight from the gzip files (`lanl.py`).
- **D141** Transform: log1p, then z with fit-day mean and std per series (a std below 1e-9 counts as 1).
- **D142** Splits: fit days 0-33, calib 34-40 (no red-team event), test 41-57 (29.3 %). One contiguous series, so
  contexts read the minutes before the origin across split boundaries.
- **D143** Injections (15.4): 4 types x 3 magnitudes x 2 durations x 2 replicas per seed, seeds 0-2, on raw values;
  no overlap within a group (1 h before, 6 h after blocked); burst only on `auth_failed` (the brief's "failed auth");
  its local baseline is the median of the 60 raw minutes before. All 48 per seed fit (none dropped, checked).
- **D144** Methods (15.5): `mv` per group as the Phase 1 best (`mv-lit`, a tie), with (`mv-cov`) and without
  known-future covariates (time of day as sin and cos, day index / 58; the true weekday is unknown); FF, frozen and
  dual on `mv`; baselines `lastvalue`, `seasonal-naive` (lag 1 day) and `robustz` (60 min). `uni` is not run. Rolling
  forecasts batch 32 origins per Chronos-2 call (independent items, `cross_learning=False`); FF goes origin by origin.
- **D145** Frozen in Phase 2 (INTERPRETATION): 48 fixed forecasts, one per 30-min time-of-day slot, each from the 8,192
  clean minutes that end at that slot on the last fit day. The literal Phase 1 frozen (one fixed context) would give
  one band for every time of day, which a daily cycle makes useless.
- **D146** Scores and evaluation (15.6): band (eps 0.1), mae, crps per series; per-series threshold = 99.5th
  percentile of that series' calib scores; detected = an alarm on the injected series in [start, end + 30 min);
  false alarms per series-day outside [start - 1 h, end + 6 h) of that series' injections; red-team check on clean
  history windows (+-3 h around each event cluster) against the `mv` thresholds. Phase 2 has its own D54-style
  CPU vs MPS check on the smoke days (`results/phase2/smoke/mps_check.csv`).
- **D147** (data constraint, found on 2026-10-21) `flows.txt.gz` covers minutes 0-52,115 only (about 36.2 days;
  `src_bytes_minute.parquet`), so Phase 2 uses days 0-35 for every series: fit 0-19, calib 20-24, test 25-35
  (30.6 %, the brief's ~70/30). 54 red-team events (days 26-29) fall in test: injections avoid +-3 h around every
  red-team cluster in every group (`inject.schedule(avoid=...)`), and the red-team check now covers events in test
  as well as in history. All 48 injections per seed still fit (checked for seeds 0-2). Supersedes the day ranges of
  D142.
- **D148** (Arthur, 2026-10-21 08:50, "Auth-only, 58 days") Replaces D147. Flows thin out after day 14 and nearly stop
  after day 23, so the brief's "bytes out per top-N source hosts from flows" is dropped (a deviation from the brief):
  the host group is auth events per source computer, the top 5 on the fit days outside the DC-like five (C625, C1065,
  C528, C2106, C2162; `results/phase2/series.csv`). The slow ramp ("exfiltration") is applied to one host's auth
  activity, so it tests a slow persistent rise, not data exfiltration. Window and split return to D142: fit 0-33,
  calib 34-40, test 41-57. `inject.schedule(avoid=...)` stays (red-team windows), but none falls in test.
- **D149** (Arthur, 2026-10-21 09:25: "do both auth and net flow") A flows sub-study keeps the brief's exfiltration
  ramp on flow bytes where flows are complete: days 0-14, fit 0-8, calib 9-10, test 11-14 (`configs/phase2_flows.yaml`,
  same code). Series: bytes out of the top-5 flow sources on the fit days (`fhost_1-5`: C1707, C5720, C1685, C20101,
  C5721; at most 5.2 % zero minutes on days 0-14). Each host is its own group (forecast alone), so ramps on different
  hosts may overlap in time; ramps only (3 magnitudes x 2 durations x 2 replicas, seeds 0-2), kept clear of the
  red-team windows of days 12-14: 11 of 12 per seed fit (one dropped and logged per seed). Results in
  `results/phase2/flows/`, cache in `cache/lanl_flows/`. 4 test days and 33 trials: noisier than the auth study, and
  reported as a sub-study.
- **D150** Run order and cost (2026-10-21 09:33): the GPU is shared with option B until about 12:00, which puts the
  full Phase 2 run at about 4.5 h. It runs in stages, each evaluated when it ends: `mv`, `mv-frozen`, dual and the
  baselines, then the red-team check and figures; `mv-cov`; the flows sub-study; `mv-ff` last (the slowest, origin by
  origin, and the variant Phase 1 found least useful). Evaluation code lives in `p2_eval.py`, outside the hashed
  sources, so an evaluation fix never changes a forecast key.
- **D151** (after the full run, 2026-10-21 14:30) Chance level and segments for Phase 2 detections. With about 7
  false alarms per series-day a 24 h window nearly always holds one, so `detect` adds per injection `chance` (share
  of same-length windows wholly on normal test minutes of that series and seed that hold an alarm) and onset /
  interior / offset coverage (first 30 min = grace_min, the rest, the 30 min after the end); `curves.csv` gets their
  means and the detection-curve figure shades `mv`'s chance. Evaluation only, from the cache; thresholds, scores and
  forecasts unchanged, nothing picked on them. The CLI gains `p2 --runs` (the flows sub-study as reported runs
  without `mv-ff`), skips the DuckDB scans and the red-team stage for `source: flows` (it reads the main scans).
- **D152** (Arthur, 2026-10-21 15:30: "remove in git any timestral ref"; scope chosen: results history, Q21)
  `git filter-branch --index-filter` over all 24 commits: in every text file under `results/`, lines naming
  Timestral are dropped and the old `timestral_commit` header becomes `model_code`; the three pre-pause commits lose
  their smoke figures (Timestral plots). The HEAD tree is unchanged (same tree hash), no commit's `results/` names
  Timestral, the old objects are pruned (`refs/original` deleted, reflog expired, gc). Commit messages, code,
  configs and docs keep Timestral (paused). Backup of the old history: `cache/git_backup_before_timestral_cleanup_
  20261021.bundle` (git-ignored) until Arthur says delete. Arthur also chose to delete Timestral outside git: the
  smoke forecasts in `cache/hai2103-*-smoke/timestral-*`, the four weight snapshots and blobs in `cache/hf/`, and the
  `timestral` package (now an optional extra, `uv sync --extra timestral`; no Chronos-2 hash changes). Phase 2
  thresholds and false alarms are written in a fixed row order (reruns byte-identical).
- **D153** (Arthur, 2026-10-21 evening: "for fun create a research paper in the repo focusing on increasing the
  steps, introducing a new measure and testing the forecast fallback") A paper in `paper/paper.typ`, compiled to
  `paper/paper.pdf`. No new forecast: every table and figure comes from `results/` through `tsfm-ad paper`
  (`paper.py`, not hashed), which writes `results/paper/`. The new measure is the contamination share kappa (the
  share of anomaly steps scored by a forecast whose origin lies after the onset, the `n_post_origin` rule of
  `evaluate.py`), with its expectation under a uniform grid phase and the split c = (1 - kappa) c_clean +
  kappa c_cont. New evaluation numbers, cache only: the LANL origin split for `mv`, `mv-cov`, `lastvalue` and
  `robustz` (band and mae, each at its calib threshold), the LANL band width by origin side, the HAI onset phase
  against the forecast grid, and the mae split on HAI from `segments_per_attack.csv`. Typesetting: Typst through
  the pinned `typst` package (optional extra `paper`), as no LaTeX is installed. Author line "Arthur Rapp" to be
  confirmed by Arthur.
- **D154** (Arthur, 2026-10-22: a Phase 1 picture like the LANL timelines, showing the interior, the false-alarm rate
  and "the interior goes quiet only when most forecasts start inside the attack") `restart_plot.py`, command
  `restart-plot`, writes `results/phase1/figures/restart_timeline.png` from the cache and the results CSVs: the
  `uni` rolling runs with H = 30 (`47703ec2`) and H = 6 (option B, `da581742`), channel `P1_PCV02Z`, 10 minutes
  either side. Attack A402 was picked from `segments_per_attack.csv` because it shows the contrast most plainly
  (interior coverage 0.95 with 0 contaminated steps against 0.24 with 21 of 27): an illustration picked on test
  results, not a result. The all-50-attack numbers in the panel titles come from `segments_summary.csv` and
  `metrics.csv`. The signal axis is clipped at twice the larger of the band median and the 90th percentile, and
  the clipped spike is labelled.

### Open questions (for Arthur; work proceeds on the defaults above)

**Answers of 2026-10-20 evening (Arthur, after reading REPORT.md):** Q1, Q2, Q3, Q6, Q11, Q12, Q15 and Q17: the
defaults stand (`mv-acttgt` secondary; P4 out of experiment 2; per-file split roles; no eTaPR; the literal frozen
reference; no separate diagnostic of the attack-only tags; no setpoint schedule covariates in Phase 1; `uni51` is
the experiment 1 headline). Q9: yes, describe the "ICML 2026 paper" as an FMSD workshop poster and arXiv 2607.12454
as a separate EUROCAST paper. Q21: yes; the Timestral rows were removed from every committed results file
(`results/smoke/*.csv`, `results/phase1/mps_check.csv`) on 2026-10-20, and git history is rewritten to drop them
once, right before the first push (rewriting now would change the commit hashes REPORT.md cites, and again at every
rewrite). Q22: no; the no-guard run is not done because `uni` and `mv-lit` tie (REPORT.md 4.17), so no conclusion
hangs on the guard. Q13: Arthur's screenshots (2026-10-20) are the paper's own Fig. 2, Fig. 4 and Sec. 3.1, which
match the PDF we have; no FF code. Still open: Q4, Q5, Q10, Q19, Q20 (with the proposals of the same evening).

- **Q1** Actuator commands: headline exp 2 follows the brief (covariates). Should `mv-acttgt` (targets) be the headline
  later, or a candidate for the exp 3/4 base? Until you say so it is a reported secondary only (D40).
- **Q2** P4 left out of experiment 2. Should it be its own group, or covariates for P1-P3?
- **Q3** OK to read "strict time-based split" as per-file roles (D8)?
- **Q4** (answered 2026-10-21: option B ran, D138, REPORT.md 4.20) At 10 s with H = 30 and stride H, only 24.8 % of attack steps come from forecasts that saw attack data, and
  406 of 637 interior steps are forecast from clean context. At 1 s it is 86.0 %, but 1 s also changes the horizon
  and stride in seconds (30 s vs 300 s) and the context cap, and runs on 5M (compared with a 10 s 5M reference,
  D52). Should the boundary-vs-interior headline move to 1 s, or should H/stride change at 10 s? Both are brief-level
  choices.
- **Q5** HAI 21.03 has no attack longer than 422 s. HAI 22.04/23.05 have long-term scenarios but need git-lfs.
  Worth a later run?
- **Q6** HAICon 2020 scored with eTaPR (alpha 0.5, rho 0.1, pi 0.7, delta 180), not plain TaPR. Add eTaPR as a secondary metric?
- **Q7** Does the Timestral weights licence (section 2.1, last row) allow this project?
- **Q8** 1 s cap 8,192 (planned) vs 32,768 (optional, about 5.5 h): which one should be the 1 s reference?
- **Q9** OK to describe the brief's "ICML 2026 paper" as an FMSD workshop poster at ICML 2026, and arXiv 2607.12454 as a
  separate EUROCAST paper?
- **Q10** FF headline: no exit (`ff-interp-block`) or bounded (`ff-interp-block-max60-testinf`, whose 60 steps were
  set knowing the test attack lengths)?
- **Q11** The literal frozen context gives a static band. Is a time-of-day-aligned clean reference closer to what you meant?
- **Q12** Should the three attack-only tags (`P1_PCV02D`, `P2_OnOff`, `P2_Emerg`) get a separate non-TSFM diagnostic?
- **Q13** OpenReview `zKWdTO8ART` was not reachable (browser challenge). Could you check it for FF code or details?
- **Q14** Stretch models: Chronos-2 or TimesFM later, or not at all?
- **Q15** The scheduled setpoints change at fixed clock times. Use them as known-future covariates later?
- **Q16** OK to use the unofficial MPS shim for headline runs, given it is checked against CPU on HAI?
- **Q17** Experiment 1 headline: 51 channels (`uni51`, our proposal: the 6 step tags are covariates, so a univariate
  run leaves them out) or the literal 57 (`uni57`, every non-constant channel)? Both run. The headline is `uni51`
  until you decide (D39).

- **Q18** ANSWERED 2026-10-20 (D130): MPS with a relative tolerance. The D54 MPS check fails only through `P1_PCV02Z` (max gap 2.2e-3 to 1.95e-2 z at values of hundreds of
  fit-z; relative gap below 7.6e-4; every other channel at or below 9.8e-4; identical alarms in every row, D110). So
  Phase 1 runs on CPU, about 1.85x slower (about 12-15 h instead of 6.4-8.2 h). Keep CPU, or accept MPS with a
  relative tolerance (the cache key would then carry `mps`)?

- **Q19** Experiment 4 is deferred until Timestral permission (D123). `autogluon/chronos-2-small` (28M, 13 native
  levels including q05, q50 and q95; the other 8 would be linear interpolations, which changes the crps score but
  not the band score) could give a two-size Chronos-2 comparison now. Run it, or wait for Timestral?
- **Q20** The 1 s comparison, where the contamination mechanism is visible at all (Q4), is behind `--optional`
  (D124): about 23.7 h per 1 s run on CPU (13.2 h on MPS). Run it anyway (rolling overnight, FF later), lower its
  cap (e.g. 2,048 steps, about 4x cheaper, a method change), or accept MPS for it (Q18)? Deferred by Arthur
  until after `REPORT.md` (D134).
- **Q21** (DONE 2026-10-21, D152) `results/smoke/*.csv` (e.g. 824 Timestral rows next to 824 Chronos-2 rows in `metrics.csv`) and
  `results/phase1/mps_check.csv` (9 Timestral rows) still hold the Timestral smoke results committed before the
  pause; the smoke figures are now Chronos-2 only, and git history keeps the Timestral ones. Nothing was pushed, and
  current readers skip those rows (D113, D114, D123). Remove them (and rewrite history) before anything is pushed,
  given "never publish Timestral results"?
- **Q22** Against the raw model on CPU the D128 guard moves mv-lit and mv-acttgt forecasts by up to 65 z
  (`P1_PCV02Z`) and test band scores by up to 3.4 (14.5, D129). Should a no-guard mv-lit rolling run (its own
  forecast hash, about 1.5 h on CPU with calib2) show that experiment 2 does not hinge on the guard? It needs a guard
  switch in `model_chronos2.py`, a hashed source, so every Chronos-2 cache key changes once (nothing is deleted).
  Not planned until you say so.

### UNCONFIRMED (carried into REPORT.md)

- Whether Timestral's post-training data included HAI or other ICS data (blog; GitHub issue #3). Zero-shot results
  could be optimistic.
- Forecast Fallback: threshold data source, exit rule, substitution scope, behaviour with H > 1 (`research/papers.md` §3.4).
- Timestamp timezone; train3 documented as 229 h but holds 133 h; A209 duration (PDF 159 s vs labels 199 s);
  meaning of `P2_CO_rpm`, `P2_HILout`, `P2_SIT02`; why `P1_PP01AD/AR` read 540833.
- That eTaPR 1.12 was the exact HAICon 2020 wheel.
- MPS shim validity on HAI: the smoke check (D54) failed the 1e-3 z tolerance on `P1_PCV02Z` only (D110), so all
  headline runs use CPU. CUDA untested (no GPU).
- Whether Timestral bands widen with h on HAI (measured from the calib cache, `band_width_by_h.csv`).
- HAI repo commit of the local data files.
- Chronos-2 (section 14): whether HAI or other ICS data are in its training corpus (not listed in the report's full
  training-data list, arXiv 2510.15821 App. A; not checkable against the weights); whether its bands widen with h on
  HAI (`band_width_by_h.csv`); which Chronos-2 checkpoint and revision Lowe et al. used.

---

## 14. Model switch to Chronos-2 (2026-10-20)

### 14.1 What changed and what did not

- **Why.** The Timestral weights licence (section 2.1 last row, Q7). Arthur decided that Phase 1 runs on `amazon/chronos-2` (Apache 2.0) for now, through the same pipeline,
  so Timestral can be switched back on later (CLAUDE.md). No Timestral model was downloaded, loaded or run for this
  switch; the Timestral weights already in `cache/hf` stay there unread.
- **Deviation from the brief, decided by Arthur.** The brief names Timestral as the model under test and its sizes
  for experiment 4. Phase 1 results are Chronos-2 results. REPORT.md says so in its title, summary and every table,
  and never presents them as Timestral results. The brief's "optional stretch: Chronos-2" becomes the main model, so
  D38 and Q14 are superseded.
- **Overlap with the papers.** Lowe et al. (the brief's "ICML 2026 paper", where Forecast Fallback comes from) ran
  Chronos-2 and Moirai-2.0 zero-shot (`Lowe:fmsd:67-70, 229-231`). Their Fig. 3, the onset-only pattern with the FF
  illustration, is Chronos-2 on TEP (`research/papers.md` §3.2). Their checkpoint and revision are UNCONFIRMED, they
  used inputs of 32-128 steps, and they tuned on test labels (section 1), so their numbers are still not comparable
  with ours.
- **Unchanged:** data, roles and channel sets (section 3), preprocessing (4), splits and warm-up (5), the forecasting
  loop (6) except the cap, the cache layout (6.1), scores, aggregation and thresholds (7), experiments 1, 2, 3a-c and
  5 with their configs and the D21 selection rule (8), metrics (9), outputs (12), and every decision D1-D116 that
  D117-D128 (section 13) do not revise. Where sections 2, 8, 10 and 11 say Timestral, 28M or 5M, they describe the
  paused Timestral plan. This section is the Phase 1 plan.
- **Timestral is switched off, not removed.** `forecast.load_forecaster` raises for `model.name: timestral` unless
  `TSFM_ALLOW_TIMESTRAL=1` is set (message: licence pause, see CLAUDE.md). The Timestral-only configs live in
  `configs/timestral/` and `smoke` and `all` never load them (D117, D123). The Timestral call path (`forecast.predict`
  with a `TimestralForecaster`, `mps_shim.py`) is unchanged apart from the dispatch, and its loop tests still run with
  the stub forecaster.

### 14.2 Sources and pins

Research notes: `SP/research/chronos2_api.md` (2026-10-20, written for this switch; toy outputs
`SP/c2-scripts/c2_toys.out` = T1, `SP/c2-scripts/c2_toys2.out` = T2, latency `SP/c2-scripts/bench.csv`). Checks
made during the switch: `SP/switch/` (scripts named below).

| key | what |
|---|---|
| `C2:<file>:L` | github.com/amazon-science/chronos-forecasting at tag `v2.3.2` = commit `0aba28e9360b6355d5a919596c90b16c25939f02`, under `src/chronos/`. Short forms: `PL` = `chronos2/pipeline.py`, `DS` = `chronos2/dataset.py`, `MD` = `chronos2/model.py`, `PP` = `chronos2/preprocess.py`, `LY` = `chronos2/layers.py`, `CB` = `chronos_bolt.py`, `BA` = `base.py` |
| `C2-CARD:L` | `README.md` of huggingface.co/amazon/chronos-2 at revision `29ec376` |
| `C2-TEX:L`, `C2-APP:L` | arXiv 2510.15821 v1 (Ansari et al., "Chronos-2: From Univariate to Universal Forecasting", 17 Oct 2025), `main.tex` and `sections/appendix.tex` |
| `T1 §N`, `T2 §N` | toy checks of the research notes (Python 3.12.13, torch 2.14.1, CPU at 4 threads unless marked MPS) |

| item | pin |
|---|---|
| package | `chronos-forecasting==2.3.2` from PyPI (`pyproject.toml`, `uv.lock`; checked at load against `model.chronos2.package`), with transformers 5.20.2, accelerate 1.15.0, einops 0.8.2, pandas 3.0.6 (`uv.lock`) |
| model | `amazon/chronos-2`, revision `29ec3766d36d6f73f0696f85560a422f50e8498c` (`configs/base.yaml`); 119,477,664 parameters, all float32; `model.safetensors` sha256 `ddcda3c7508bf2528087723e98a20707cc04b7f370ae275a9fd88078ddba4f42` (the blob name in `cache/hf`) |
| licence | Apache-2.0 (`C2-CARD:2`) |
| other checkpoints | `autogluon/chronos-2` has byte-identical weights. `autogluon/chronos-2-small` @ `ddec013` (27,934,624 params) and `autogluon/chronos-2-synth` @ `3607918` (118,985,888 params, synthetic training data only) have 13 quantile levels, not 21. No other Chronos-2 size exists on Hugging Face (searched 2026-10-20). |

### 14.3 API facts and the exact calls

| fact | source |
|---|---|
| `Chronos2Pipeline.from_pretrained(repo, revision, cache_dir, device_map, dtype)` forwards to transformers and, for a base model, builds `Chronos2Model.from_pretrained` and wraps it. Before that it looks up a LoRA adapter on the hub without passing the revision. Our loader builds the model and the pipeline itself, so no unpinned lookup happens (D119). | `C2:PL:1146-1191` (lookup at `:1158`) |
| The default dtype is float32 (config `torch_dtype`). bf16 moves quantiles by up to 0.028. We force float32 and check every parameter at load. | `C2:BA:366-376`; T1 §7 |
| `predict(inputs, prediction_length, batch_size=256, context_length=None, cross_learning=False, limit_prediction_length=False)`. Inputs: a 3-D array `(n_items, n_variates, T)`, a list of 1-D or 2-D arrays, or a list of dicts `{"target", "past_covariates", "future_covariates"}`. A 2-D `(51, T)` array is rejected. | `C2:PL:467-541`; `C2:DS:146-162`; T1 §1 |
| Output: a list with one tensor `(n_variates, 21, H)` per item, quantile axis before time, float32, on CPU. Only targets are returned. | `C2:PL:562-563, 714-718`; `C2:DS:262`; T1 §1, §4 |
| Each item gets its own group id. Group attention is masked by group equality with `finfo(float32).min`, so weights across groups are exactly 0; time attention never mixes rows. `cross_learning=True` sets every group id to 0. | `C2:DS:253-263`; `C2:MD:122-142`; `C2:LY:339-359, 388-411`; `C2:PL:639-640`; `C2-TEX:308-313` |
| Past-only covariates: a dict of 1-D arrays exactly T long. Names are sorted internally, so their order does not matter. Their future inputs are masked and their predictions dropped. Known-future covariates (`future_covariates: {name: (H,)}`, names also in `past_covariates`) and categorical covariates (string arrays; target-encoded for one target, ordinal codes for several) exist but are not used in Phase 1 (no categorical tags, section 3). | `C2:PP:271, 362-366, 414-446, 531-566, 612-686`; `C2:DS:225-231`; T1 §4 |
| The variates of one item interact (a step in variate 0 moved variates 1-4 by up to 0.60). An all-NaN row is not neutral (moves the others by up to 0.42) and its own output is garbage; `inf` gives NaN output. The finiteness guard of `forecast.predict` stays and groups are never padded. | T1 §3, §7; T2 §B |
| Maximum context 8,192 (config `context_length`; post-trained at 8,192). Longer input is cut from the left silently (T = 10,000 was bit-identical to its last 8,192 steps). Any T >= 1 works; T is left-padded to whole 16-step patches and masked. | `C2-CARD:51`; `C2-TEX:258`; `C2:DS:203-205`; `C2:MD:402-405`; `C2:CB:80-92`; T1 §5 |
| One forward pass covers up to 64 output patches x 16 = 1,024 steps; beyond that a warning and an autoregressive heuristic. `limit_prediction_length=True` raises instead (we set it). H is rounded up to 16-step patches: H = 30 is bit-identical to the first 30 steps of H = 32 and costs the same. The number of output patches changes the forecast: H = 48 moved the first 32 steps by up to 0.081. | `C2:PL:87-89, 599-607, 670-674, 689-712`; `C2-CARD:52`; T1 §6 |
| Scaling: per row, nan-mean and population std over the whole (truncated) context, std 0 replaced by 1e-5, then arcsinh. Forecasts are affine-equivariant to about 3e-6 relative, so the z-scored inputs change nothing. Unlike Timestral's causal expanding statistics, one level shift inside the context rescales the whole context. | `C2:CB:95-138`; `C2:MD:395-420, 754-768`; `C2-TEX:178-190`; T1 §7 |
| A constant context gives q05 == q95 (zero width), as with Timestral, so D17 and D39 hold unchanged. | T1 §7 |
| No `symmetric_averaging` or `clip_nonnegative` equivalent; no sampling. Bit-deterministic on CPU and MPS; 1, 4 and 10 CPU threads give identical bits (Timestral differed, D115). | `C2:MD:731-739`; T1 §7; T2 §D |
| MPS runs natively (scaling in float32; the RoPE helper already maps mps to a CPU autocast context). The Timestral `mps_shim` is not used. | `C2:CB:108-122`; `C2:LY:86`; T2 §D |
| Training data: real data only for univariate tasks, from a table the report calls the full list (23 datasets: energy, nature, transport, web, cloud ops, M4); multivariate and covariate tasks used synthetic data only. HAI, SWaT, WADI, SCADA and ICS are not mentioned (14.9 item 1). | `C2-TEX:323-343`; `C2-APP:1-38`; `C2-CARD:161-166` |

The calls, as implemented in `src/tsfm_ad/model_chronos2.py`:

```python
model = Chronos2Model.from_pretrained("amazon/chronos-2", revision="29ec3766d36d6f73f0696f85560a422f50e8498c",
                                      cache_dir="cache/hf", device_map=device, dtype=torch.float32,
                                      local_files_only=True)        # downloads only when missing (D101)
pipe = Chronos2Pipeline(model=model.eval())                        # 21 levels, float32, context 8192: checked

# experiment 1: ctx (V, T), T <= 8192, finite; V items of one variate each = V groups
out = pipe.predict(ctx[:, None, :], prediction_length=30, cross_learning=False, limit_prediction_length=True)
q = torch.cat(out).permute(0, 2, 1).numpy()                        # (V, 30, 21); row v = channel v

# experiment 2: one call per process group g; groups are never merged
item = {"target": tgt}                                             # (V_g, T) continuous targets
if C_g:
    item["past_covariates"] = {f"cov{j:03d}": cov[j] for j in range(C_g)}   # each exactly T long
q = pipe.predict([item], prediction_length=30, cross_learning=False, limit_prediction_length=True)[0]
q = q.permute(0, 2, 1).numpy()                                     # (V_g, 30, 21); covariates are not returned
```

### 14.4 Independence in experiment 1

- Mechanism (14.3): the adapter passes the V channels as V items of one variate, so each channel is its own group,
  and cross-group attention weights are exactly zero. `cross_learning=False` is passed explicitly.
- Toys: rows 1-50 stayed bit-identical when series 0 was scaled x50 (+100, noise), got a +30 step or a NaN gap, on
  CPU and on MPS. Passing `(1, 51, T)` (one multivariate item) or `cross_learning=True` moved the other rows by up
  to 0.097. The same series in another batch differs by float noise only (at most 5e-6) (T1 §2; T2 §D).
- In the pipeline (`tests/test_chronos2.py`, all download-free except (c)):
  (a) a fake pipeline checks that the adapter sends one `(V, 1, T)` array with `cross_learning=False` and maps rows
  and quantile columns back in order;
  (b) a tiny randomly initialised `Chronos2Model` (the real architecture and group-attention mask, no weights),
  called through `forecast.predict`: rows 1-5 bit-identical under three perturbations of row 0 (x50 + 100, a +30
  step, reversed and negated), while the cross-learning control moves them;
  (c) the same check with the pinned weights from `cache/hf` (skipped when they are not there).
  A mutation check (`SP/switch/mutation.py`: the adapter changed to send one joint item, or to cross-learn) makes
  test (b) fail, so the test has power (the same script shows the constant-row test of 14.5 fails without D128).
- Verdict: experiment 1 is truly univariate on Chronos-2. Experiment 2 keeps one item per process group with its
  targets joint and its covariates past-only, one call per group.

### 14.5 Quantile mapping

- The 21 native levels are the cache levels (0.01, 0.05, 0.10, ..., 0.90, 0.95, 0.99): q05 = index 1, q50 = 10,
  q95 = 19, so the cache columns `q01..q99`, every scorer and every threshold stay unchanged. The adapter permutes
  `(V, 21, H)` to `(V, H, 21)` and refuses at load a model whose levels differ (a 13-level `chronos-2-small` would
  be refused).
- Crossing quantiles. Nothing in Chronos-2 enforces monotone output (`C2:MD:731-768`), and on HAI it often is not.
  Raw output on the full 10 s `calib` (`SP/switch/crossings3.py`: 6 origins per
  pseudo-file and context length, CPU): 7.3 % of (channel, h) forecasts have at least one crossing at T = 150,
  16 % at 512, 19 % at 2,048 and 21 % at 8,192 (uni); mv-lit 4 %, 15 %, 18 % and 21 %. The crossings sit mostly
  next to the median: sorting changes q50 in up to 14.6 % of forecasts, by at most 0.06 z (0.09 of the band width
  + eps); it changes q05 in at most 0.83 % and q95 in at most 0.19 % of forecasts, by at most 0.16 z and 0.32 of
  (band width + eps). The smoke slice gives the same picture (`SP/switch/crossings2.py`: 8.0 % uni, 5.2 % mv-lit at
  contexts of 150-690 steps). Every call logs its count (`crossed` of `forecasts`) to `calls_<split>.csv`.
- **Constant rows (D128).** `InstanceNorm` replaces a zero scale by 1e-5, so that a constant row becomes 0
  (`C2:CB:95-122`), but it tests `scale == 0` exactly, and the float32 mean of a constant row often misses the
  value by one rounding step. The scale is then that residual (e.g. 5.96e-8) and the row enters as
  arcsinh(+-1) = +-0.88 instead of 0, with the sign set by rounding. On the smoke slice (test1, origin 270) the 5
  P1 covariates that were constant in the context (`P1_B2004`, `P1_B3004`, `P1_B3005`, `P1_B4002`, `P1_FCV02D`)
  entered as +0.88, +0.88, -0.88, +0.88, +0.88 on CPU and as +0.88, -0.88, 0, +0.88, 0 on MPS. That moved the
  mv-lit P1 targets by up to 5.17 z (`P1_PCV02Z`; 2.12 z for `P1_PIT01`) between the devices; with those 5 rows
  dropped the gap was 1.9e-3 (`SP/switch/constcov.py`). Constant rows are common in short early-file contexts (the
  step setpoints change every 1.5-5 h, actuator commands can sit still). The adapter therefore passes every
  constant row as exact zeros, the model's intended input for it, the same on every device and at every level,
  and adds a constant target's value back to its quantiles; every other row is passed unchanged. A constant target
  keeps a band of (near) zero width at its value (at most 6e-8 z over the 76 constant-context forecasts of the smoke
  uni run), so its band score stays dev / eps (D17). With the guard the same
  P1 item differed between CPU and MPS by at most 1.8e-3 z (`P1_PCV02Z`, about 440 fit-z) and 8.9e-5 z elsewhere
  (`SP/switch/constcov2.py`). A test checks that a constant covariate's level no longer changes the forecast; it
  fails without the guard. Every call logs its count (`const_rows`) to `calls_<split>.csv`. This is our fix of a
  numerical edge case of the model, labelled as such; REPORT.md states it, with its size below.
- **Size of the guard on CPU (D129, review 2).** The CPU-vs-MPS gap above is not what the guard changes on the
  device of the headline runs. `tsfm-ad d128` compares, for every call whose context holds a constant row, the
  adapter forecast with the same call without the guard (the model as shipped), on CPU at 4 threads; every other call
  is bit-identical by construction. 10 s full data, every rolling (in-file warm-up), cf-onset and frozen context of
  the planned runs, measured on 2026-10-20 before the full runs (`results/phase1/d128_effect.csv`,
  `d128_effect_channels.csv`; dq = |adapter - raw| in fit-z, shares over all (channel, h, level) values of the split;
  "band score" = the change of the D17 band score at the observed value):

  | run | split | calls with a constant row | max dq, all 21 levels | values with dq > 0.01 / 0.1 / 1 z | max dq at q05, q50, q95 | max band-score change |
  |---|---|---|---|---|---|---|
  | uni rolling | calib / calib2 / test | 71 / 338 / 16 of 566 / 566 / 1,315 | 6.6e-7 | 0 / 0 / 0 | 6e-8 | 5e-6 |
  | uni cf-onset | test | 3 of 50 | 1.8e-7 | 0 / 0 / 0 | 6e-8 | 1e-5 |
  | mv-lit rolling | calib | 85 of 1,698 | 14.2 (`P1_FT02`) | 0.74 % / 0.010 % / 0.0004 % | 0.60 | 0.21 |
  | mv-lit rolling | calib2 | 338 of 1,698 | 40,606 (`P1_B4005`, q01) | 4.8 % / 0.086 % / 0.00085 % | 44.7 (`P1_B4005`) | 0.52 |
  | mv-lit rolling | test | 201 of 3,945 | 65.4 (`P1_PCV02Z`) | 0.48 % / 0.025 % / 0.0032 % | 25.5 (`P1_PCV02Z`) | 3.44 |
  | mv-lit cf-onset | test | 8 of 150 | 5,658 (`P1_FT02`, q01) | 0.92 % / 0.10 % / 0.033 % | 64.7 (`P1_PIT02`) | 6.32 |
  | mv-acttgt rolling | calib / test | 85 / 201 of 1,698 / 3,945 | 14.2 / 65.4 | 0.70 / 0.009 / 0.0003 %; 0.46 / 0.023 / 0.0027 % | 0.60 / 25.5 | 0.21 / 3.44 |
  | uni and mv-lit frozen | ref | 0 of 1 / 0 of 3 | 0 | 0 | 0 | |

  So for the multivariate setups the guard is not a rounding-level change. The calls it touches are 5 % of the mv
  test calls and 20 % of the calib2 calls, all in the P1 group: constant covariates (`P1_B2004`, `P1_B3004`,
  `P1_B3005`, `P1_B4002`, `P1_FCV01D`, `P1_FCV02D`; at most 6 per call) and, in calib and calib2, constant targets
  (`P1_FCV01Z`, `P1_B4005`). In calib and test they sit early in a file (median context 750-780 steps, at most
  2,250), where the step setpoints and some actuator commands have not moved yet; in calib2 they reach full
  contexts (median 3,555, up to 8,192 steps). There the guard moves P1 targets by up to 65 z on `P1_PCV02Z` (test1,
  origin 480: q99 510 vs 445, q95 181 vs 155; 3.1 band widths), by up to 8.1 z on the other P1 channels in test
  (`P1_PIT01`) and 14.2 z in calib (`P1_FT02`; `d128_effect_channels.csv`), and changes a band score by up to 3.4
  in rolling test and 6.3 in cf-onset. Band-score changes above 1 are rare: 4 of 1,341,300 mv-lit test
  forecasts, 16 of 41,956 cf-onset forecasts. The largest all-level values (4.1e4 and 5.7e3 z) are q01 differences
  inside forecasts whose outer quantiles explode with and without the guard (next item). On the smoke slice (test1;
  contexts of 150-690 steps, 19 of 57 calls with a constant row) the shares are larger: 12.5 % / 1.3 % / 0.21 % of
  values above 0.01 / 0.1 / 1 z (`results/smoke/d128_effect.csv`, the reviewer's numbers exactly). Univariate
  setups: only the constant row itself changes, by at most 6.6e-7 z. Not measured: FF and prepend runs (their
  contexts are the rolling ones with substituted targets or a train3 prefix); FF on an mv base shares the rolling
  picture until its first substitution. Experiment 2 and every run on an mv base are therefore Chronos-2 with
  this input interpretation, not the unmodified model; whether a conclusion hinges on it needs a no-guard run
  (Q22). REPORT.md gives these numbers next to every mv result.
- **Exploding outer quantiles** (seen while measuring D129; not caused by the guard). On near-constant contexts the
  outer levels can be absurd. train2b, origin 660, `P1_B4005` (context std 5.1e-4 around 0.93, 6 constant P1
  covariates): q01 = -3.1e5 z and q05 = -558 z with the guard, -3.5e5 and -522 without, while q50 = 0.89. test5
  cf-onset at origin 156: q01 of `P1_FT02` is -5.9e7 z (guard) and -2.0e7 (raw). With a tiny context scale the
  inverse arcsinh scaling (14.3) turns a large scaled quantile into a huge one. Such a band is hundreds of z wide,
  so the band score there is 0, and the crps score is huge. On the smoke cache it shows only as `P1_PCV02Z` bands
  above 100 z (38 of 58,140 uni forecasts). Its prevalence on the full runs is not measured yet; REPORT.md must
  report it (14.9 item 10).
- D119: the adapter sorts each 21-level vector (monotone rearrangement). It is a no-op on monotone output, it keeps
  the cache contract `q01 <= ... <= q99` that Timestral's sorted output met by construction (section 2.1), and it
  never increases the pinball loss, so the crps score can only improve. Every forecast run prints how many
  (channel, h) forecasts were rearranged and logs it per call. Over the whole smoke (both resolutions, every
  variant): 454,903 of 2,020,380 (channel, h) forecasts (22.5 %) were sorted and 4,025 constant rows zeroed.
  REPORT.md states the rates of the full runs.

### 14.6 Context cap and what it changes

- `model.max_context` = `forecast.cap` = 8,192 at 10 s (D118) and at 1 s (as planned, D12). At 10 s that is 22.8 h.
- At 10 s with in-file warm-up the cap now binds from origin 8,220 on (it never bound for Timestral, section 5):
  test2 3,660, test3 2,580 and test5 1,020 scored steps, so 7,260 of 39,450 scored test steps (18.4 %) and 242 of
  1,315 test origins. 12 attacks have steps forecast from a capped context: A215-A220, A306-A308, A510-A512.
  `calib` and `calib2`: the last 420 steps of each pseudo-file, 840 of 16,980 scored steps (4.9 %). test1 and test4
  are shorter than the cap (`SP/switch/capeffect.py`). The cap is the model maximum, not a tuned value.
- Frozen (3b): the reference slice has 8,640 steps, so the frozen context is its last 8,192 (from 2020-08-09
  12:14:40; the first 74.7 min are dropped).
- Prepend (optional): the prefix is the last 8,192 steps of train3, so every context is exactly 8,192 steps; the
  prepended part shrinks as in-file history grows and is gone from origin 8,192 on.
- 1 s: cap 8,192 as planned. 92 % of scored 1 s calib and test steps come from capped contexts, as before. The
  optional Timestral 1 s run at cap 32,768 has no Chronos-2 counterpart (`configs/timestral/res1s_uni_c32k.yaml`).
- cf-onset: H = L + N is at most 49 steps at 10 s (4 output patches) and 482 at 1 s (31 patches), inside one forward
  pass, but the rolling forecast uses 2 patches (H = 30). The number of output patches alone changes the forecast
  (14.3), so the cf-onset vs rolling contrast also mixes the patch count; the `h_cf <= 30` subset does not remove
  it. REPORT.md says so next to every cf-onset number.

### 14.7 Run matrix (Chronos-2)

| exp | setup | variant | config | status |
|---|---|---|---|---|
| smoke 10 s | uni, uni57, mv-lit, mv-acttgt | rolling, prepend, frozen, dual, ff-interp-block, ff-interp-block-max60-testinf, cf-onset; baselines; select (exercise) | `configs/smoke.yaml` | required first |
| smoke 1 s | uni | rolling, ff-interp-block, cf-onset, baselines; cap 2,048 so it binds (D59) | `configs/smoke_1s.yaml` | required first |
| MPS check | uni, uni57, mv-lit, mv-acttgt at 10 s; uni at 1 s | rolling, cpu vs mps (D54, D123) | part of `smoke` | required first |
| 1 | uni | rolling (+ calib2), cf-onset | `configs/exp1_uni.yaml` | planned (headline) |
| 1 | uni57 | rolling | `configs/exp1_uni57.yaml` | planned (brief-literal secondary, D39) |
| 2 | mv-lit | rolling (+ calib2), cf-onset | `configs/exp2_mv.yaml` | planned (headline) |
| 2 | mv-acttgt | rolling | `configs/exp2_mv_acttgt.yaml` | planned (secondary, never a base) |
| 5 | robustz, lastvalue, seasonal-refday | rolling | `configs/exp5_baselines.yaml` | planned (unchanged) |
| 3b | base | frozen | `configs/exp3b_frozen.yaml` | planned |
| 3c | base | dual | `configs/exp3c_dual.yaml` | planned (no inference) |
| 3a | base | ff-interp-block | `configs/exp3a_ff_interp_block.yaml` | planned |
| 3a | base | ff-interp-block-max60-testinf | `configs/exp3a_ff_interp_block_max60.yaml` | planned (secondary, not a candidate) |
| 4 | | model sizes | `configs/timestral/exp4_*.yaml` | **deferred until Timestral permission** (D123) |
| 1 s | uni | rolling-c8192 (+ baselines), cf-onset-c8192 | `configs/res1s_uni.yaml` | optional, `all --optional` (D124) |
| 10 s ref | uni | ff-interp-block (rolling and cf-onset = the exp 1 runs) | `configs/res10s_uni_ff.yaml` | optional, with the 1 s block (D123) |
| 1 s | uni | ff-interp-block-c8192 | `configs/res1s_ff_interp_block.yaml` | optional (D124) |
| opt | base | prepend | `configs/opt_prepend.yaml` | optional |
| opt | base | ff-interp-block-max30, -max120 | `configs/opt_ff_max_sens.yaml` | optional, no pick (D25) |
| gone | | 1 s cap 32,768; 5M 10 s reference; 209M | `configs/timestral/` | Timestral only (paused) |

Order of `all` (`pipeline.run_all`): smoke (10 s, 1 s, MPS check); prepare 10 s and 1 s; exp 1 (uni rolling with
calib2, uni cf-onset, uni57); exp 2 (mv-lit rolling with calib2, mv-lit cf-onset, mv-acttgt); the D128 effect
of uni and mv-lit rolling and cf-onset and mv-acttgt rolling (D129); exp 5; `select --stage base`; 3b, 3c, 3a,
3a-max60, the D128 effect of frozen on the base; `select --stage best`; exp 4 printed as deferred; with `--optional`:
1 s uni rolling, 1 s baselines, 1 s cf-onset, the 10 s uni FF reference, 1 s FF, prepend, FF max30 and max120;
then latency.csv, size_latency.csv and the 10 s figures (the 1 s figures with `--optional`).

- **Experiment 4** cannot run with one model size: Chronos-2 has a single checkpoint with the 21 cache levels
  (14.2). It is deferred until Timestral permission. `chronos-2-small` (28M) has only 13 native levels; it was not
  planned as experiment 4 (Q19). `size_latency.csv` still gets the Chronos-2 rows (the selected best and the
  unselected `uni` rolling) and `latency.csv` every Chronos-2 run, so its latency is recorded as usual.
- **1 s comparison (D52 for Chronos-2).** Its 10 s reference is the 10 s Chronos-2 `uni` run on the same device:
  exp 1 rolling and cf-onset, plus `uni` ff-interp-block (`res10s_uni_ff.yaml`, which is the 3a run itself, same
  hash, when the base is `uni`). Model and size no longer differ between 1 s and 10 s. Still different: H and
  stride in seconds (30 s vs 300 s) and the context in time (8,192 steps = 2.3 h at 1 s vs 22.8 h at 10 s).

### 14.8 Device and compute estimate

**D54 check for Chronos-2** (`results/phase1/mps_check.csv`; smoke slices, rolling calib + test, CPU at 4 threads
vs MPS, each scored with its own smoke threshold; after the constant-row guard D128):

| dataset | setup | values | max abs diff (z) | without `P1_PCV02Z` | max rel diff | test alarms cpu / mps | verdict |
|---|---|---|---|---|---|---|---|
| hai2103-10s-smoke | uni | 1,220,940 | 1.04e-3 | 1.05e-4 | 5.6e-5 | 21 / 21, equal | fail |
| hai2103-10s-smoke | uni57 | 1,364,580 | 1.04e-3 | 1.05e-4 | 5.6e-5 | 21 / 21, equal | fail |
| hai2103-10s-smoke | mv-lit | 813,960 | 1.83e-3 | 8.15e-4 | 1.4e-4 | 21 / 21, equal | fail |
| hai2103-10s-smoke | mv-acttgt | 981,540 | 1.98e-3 | 8.11e-4 | 1.4e-4 | 21 / 21, equal | fail |
| hai2103-1s-smoke | uni | 12,209,400 | 2.69e-3 | 4.01e-4 | 8.6e-5 | 37 / 37, equal | fail |

Every failing value is on `P1_PCV02Z`, whose test values reach about 510 fit-z (tiny fit std, section 3.4), so the
gap is float32 rounding (as for Timestral, D110). Before the guard the mv rows differed by up to 5.17 z through
constant covariates (14.5); that run is superseded. D121: CPU at 4 threads for every headline run; the rule stays
as written (Q18 is Arthur's). The failed Timestral rows of D110 stay in the file under their own model ids.
Superseded by D130 (Q18 answered): under the relative rule every Chronos-2 row above passes (max relative gap
5.6e-5, 5.6e-5, 1.4e-4, 1.4e-4, 8.6e-5), and every headline run is on MPS.

**Latency on HAI** (smoke `calls_*.csv`, `SP/switch/latfit.py`; Chronos-2 120M, H = 30): seconds per call are close
to rows x T x 11.2 us on CPU at 4 threads (median 11.2 us per row-step at T = 8,192, 9.9 us at T = 2,048) and
rows x T x 6.1 us on MPS (T up to 2,048). That matches the toy bench (research notes §9: 11.4 and 6.2 us).
Covariate rows cost what target rows cost; there is no covariate surcharge.

**Estimate** (`SP/switch/estimate.py`): every origin's real in-file context length, capped at 8,192; rows per
origin 51 (uni), 57 (uni57), 45 (mv-lit and mv-acttgt: P1 30, P2 10, P3 5, in 3 calls); CPU 11.2 us per row-step
plus 0.01 s per call, MPS 6.2 us plus 0.018 s. Inference hours, test + calib (+ calib2 where listed):

| run | calls | CPU | MPS |
|---|---|---|---|
| exp 1 uni rolling (calib, calib2, test) | 2,447 | 1.73 | 0.97 |
| exp 1 uni cf-onset | 50 | 0.04 | 0.02 |
| exp 1 uni57 rolling | 1,881 | 1.49 | 0.83 |
| exp 2 mv-lit rolling (calib, calib2, test) | 7,341 | 1.54 | 0.88 |
| exp 2 mv-lit cf-onset | 150 | 0.03 | 0.02 |
| exp 2 mv-acttgt rolling | 5,643 | 1.19 | 0.68 |
| exp 3b frozen | 1-3 | < 0.01 | < 0.01 |
| exp 3a ff-interp-block (base uni / mv-lit) | 1,881 / 5,643 | 1.34 / 1.19 | 0.75 / 0.68 |
| exp 3a ff-interp-block-max60-testinf | same | 1.34 / 1.19 | 0.75 / 0.68 |
| D128 effect (D129), adapter + raw on the calls with a constant row | 1,346 x 2 | 0.34 (measured) | about 0.2 |
| **default `all`, inference** (without the D128 row, which `all` skips while `d128_effect.csv` has the run's hash; on MPS, D130, it runs again, about 0.2 h) | | **8.7 / 8.4** | **4.9 / 4.8** |
| optional: 1 s uni rolling (calib, test) | 18,810 | 23.7 | 13.2 |
| optional: 1 s uni cf-onset | 50 | 0.06 | 0.03 |
| optional: 10 s uni FF reference (0 when the base is uni) | 1,881 | 0 / 1.34 | 0 / 0.75 |
| optional: 1 s uni ff-interp-block | 18,810 | 23.7 | 13.2 |
| optional: prepend on the base | 1,881 / 5,643 | 2.45 / 2.17 | 1.36 / 1.22 |
| optional: FF max30 + max120 on the base | 2 x | 2.67 / 2.38 | 1.49 / 1.36 |
| **`--optional` on top** | | **52.5 / 53.3** | **29.2 / 29.7** |

Two values a / b are base uni / base mv-lit. Review 2: the optional total was first given as 54 / 52 because
`SP/switch/estimate.py` put the 10 s FF reference (0 h when the base is uni) in the base-uni column; every row was
right, the sum was not.

The default `all` on CPU: 8.4-8.7 h of inference, plus the smoke (32 min) and scoring (seconds to minutes per run
at 10 s), so about 9.5 h; `pipeline.run_all` prints this before it starts. With the 1 s block in the default matrix
it would have been about 56 h on CPU (8.7 + 2 x 23.7), and still about 32 h with only the 1 s FF moved, so the
whole 1 s comparison block moves behind `--optional` (D124); Q20 asks how to run it. Not used as mitigations:
fewer channels, bf16, a larger stride, `chronos-2-small`, or a shorter cap; each changes the method.

### 14.9 Threats to validity added by the switch (REPORT.md copies them)

1. **Training-corpus overlap: UNCONFIRMED.** HAI, SWaT, WADI and other ICS data are not listed in the report's full
   list of real training data (`C2-TEX:323-330`, `C2-APP:1-38`), and the report says multivariate and covariate
   tasks used synthetic data only (`C2-TEX:332-343`). That is the authors' statement and cannot be checked against
   the weights, so REPORT.md says "not listed in the Chronos-2 report's full training-data list", never "verified
   absent". `autogluon/chronos-2-synth` (synthetic data only) would be a contamination control; not planned.
2. **The model is not the brief's.** Nothing here transfers to Timestral (other architecture, normalization and
   training data). Experiment 4 (sizes) is not run.
3. **The cap binds at 10 s** on 18.4 % of scored test steps and 12 attacks (14.6). Late parts of test2, test3 and
   test5 see 22.8 h of history, early parts less. It is the model limit, chosen before any result.
4. **Quantile rearrangement** of crossing forecasts (14.5): the cached quantiles are sorted model output, not raw
   (up to about 21 % of (channel, h) forecasts at long contexts; q05 and q95 change in under 1 %).
5. **Constant rows are zeroed** before the model (D128, 14.5): our fix of a rounding edge case that otherwise
   decided, by device and level, how a constant covariate entered the model. Its size on CPU is not small for the
   mv setups (D129, `results/phase1/d128_effect.csv`): against the raw model it moves mv-lit and mv-acttgt test
   forecasts by up to 65 z (`P1_PCV02Z`, 3.1 band widths) and band scores by up to 3.4 (cf-onset 6.3), in 5 % of
   the test calls and 20 % of the calib2 calls; 0.48 % of the mv-lit test values move by more than 0.01 z, 0.025 %
   by more than 0.1 z. Univariate setups: at most 6.6e-7 z. Experiment 2 and every FF or frozen run on an mv base
   are Chronos-2 with this interpretation, not the unmodified model (Q22).
6. **Full-context normalization**: the `P1_PCV02Z` level shifts (section 3.4) inside a context rescale that
   channel's whole context; scores are still in fit-z units because the output is mapped back.
7. **cf-onset** also differs from rolling in the number of output patches (14.6).
8. **Contexts much longer than Lowe et al.'s** (up to 8,192 steps vs 32-128), so their Chronos-2 behaviour need
   not carry over.
9. **Device**: headline runs use MPS (D130, replacing D121's CPU). MPS matches CPU to float32 rounding once constant
   rows are zeroed; it fails the original absolute D54 rule on `P1_PCV02Z` and passes the relative rule, which was
   set after seeing the check's numbers (Arthur's decision). The D128 guard itself was needed because the raw model
   let rounding decide how constant inputs entered it.
10. **Exploding outer quantiles** on near-constant contexts (14.5): q01 down to -3e5 z (and q05 to -558 z) on a
   channel whose context sits at 0.93 +- 5e-4, with or without the guard. The band score is blind there and the crps
   score explodes. Prevalence on the full runs: not measured yet; REPORT.md reports it.

### 14.10 Open questions this changes

Q7 is answered (Timestral paused). Q14 is answered (Chronos-2 is the Phase 1 model while
Timestral is paused). Q16 concerns the Timestral MPS shim and is moot for Chronos-2; Q18 is answered (D130, MPS). Q8 (1 s cap
32,768) does not exist for Chronos-2. New: Q19-Q21 (section 13).

---

## 15. Phase 2: LANL with injected anomalies (started 2026-10-21, after the Phase 1 sign-off)

Brief: Phase 2. Decisions D140-D149 below; this section is the plan, `REPORT.md` section 10 the results.

### 15.1 Data (csr.lanl.gov/data/cyber1/, D139)

- 58 consecutive days, de-identified, time epoch 1 at 1 s resolution; the calendar is undisclosed (site text).
- `auth.txt.gz`: `time,source user@domain,destination user@domain,source computer,destination computer,auth type,
  logon type,auth orientation,success/failure`; `?` = no value. Failed events exist only for users with a success
  somewhere in the data (site text).
- `flows.txt.gz`: `time,duration,source computer,source port,destination computer,destination port,protocol,packet
  count,byte count`.
- `redteam.txt.gz`: 749 events `time,user@domain,source computer,destination computer`, all on days 1-29 (day =
  (time - 1) // 86400: day 8 has 273, day 12 has 209).
- Minute index m = (time - 1) // 60, 83,520 minutes; day d = m // 1440; time of day m % 1440. The time of day is
  relative to the undisclosed start, and the true weekday is unknown (brief).

### 15.2 Series (one value per minute; D140)

| series | definition |
|---|---|
| `auth_total` | auth events |
| `auth_failed` | auth events with `Fail` |
| `users_distinct` | distinct source users, machine accounts (`...$@...`) excluded |
| `dc_1` ... `dc_5` | auth events with that destination computer: the top 5 destinations by auth volume on the fit days ("DC-like"; LANL labels no domain controller, so the selection is by volume, on fit days only) |
| `host_1` ... `host_5` | auth events with that source computer, the top 5 sources by auth volume on the fit days, leaving out the 5 DC-like computers (D148; the brief's flow bytes could not be used, see 15.3) |

Groups for the multivariate setup: `tenant` (3 series), `dc` (5), `host` (5). Transform: y = log1p(value), then a
z-score with fit-day mean and std per series (D141: counts and bytes are heavy-tailed; a multiplicative injection
becomes an additive one).

### 15.3 Splits (brief: first ~70 % of days for history and calibration; D142, D147)

- **D148 (Arthur, 2026-10-21) replaces D147:** flows are complete only on days 0-14; from day 15 the number of source
  hosts drops from about 8,000 to about 900 per day, after day 23 the stream almost stops, and days 26-29 hold scraps
  (`src_bytes_minute.parquet` per day). Bytes-out series cannot carry a test period, so all 13 series come from
  `auth.txt.gz` over the full 58 days, and the host series count auth events per source computer.
- fit: days 0-33 (normalization, top-5 selection); calib: days 34-40 (thresholds; no red-team event); test: days 41-57
  (17 days, 29.3 %; the only place injections go). All 749 red-team events are in history (days 1-29).
- One contiguous series: every forecast reads the minutes before its origin (cap 8,192 = 5.7 days), across split
  boundaries, never after it.

### 15.4 Injections (test only, labelled, manifest; D143)

| type | target series | magnitude grid | durations |
|---|---|---|---|
| silence | `auth_total`, `users_distinct`, `dc_*`, `host_*` | kept fraction 0, 0.1, 0.5 | 30, 180 min |
| burst | `auth_failed` | + k x local baseline, k = 2, 5, 20 (baseline = median of the 60 raw minutes before) | 10, 60 min |
| ramp (slow exfiltration) | `host_*` | linear to + 50 %, + 200 %, + 1,000 % at the end, then back | 2 h, 8 h |
| shift (baseline shift) | `auth_total`, `dc_*` | + 20 %, + 50 %, + 100 % | 6 h, 24 h |

Applied to raw values before the transform. Each (type, magnitude, duration) twice per seed, seeds 0, 1, 2 (6 trials
per point). Placement: random start in the test days; no overlap with another injection of the same group (plus 6 h
after its end and 1 h before its start), so neither a joint forecast nor a series' own context mixes two injections
in the same window. A combination that cannot be placed is dropped and logged. Manifest: seed, type, series, group,
magnitude, duration, start, end, and the hours since the last injection on that series.

### 15.5 Methods (brief: the best Phase 1 setup plus the context-protection variants, with and without covariates;
same baselines; D144)

- Base: Chronos-2 multivariate per group (`mv`), the Phase 1 best (`mv-lit`, picked on test results; it ties `uni`,
  REPORT.md 4.17). H = 30 min, stride 30, cap 8,192. With known-future covariates (`mv-cov`: time of day as sin and
  cos, and the day index) and without (`mv`).
- Context protection on `mv`: `frozen` (INTERPRETATION, D145: a time-of-day aligned clean reference, the 8,192
  fit-day minutes that end at the origin's time of day on the last fit day, so 48 fixed forecasts; the literal
  Phase 1 frozen gives a static band, useless on a daily cycle), `dual` (rolling vs frozen, no inference) and
  `ff-interp-block` (no exit, Phase 1 interpretation, per-series tau from the calib rolling run).
- Baselines on the same series: `robustz` (median and MAD of the trailing 60 min), `lastvalue`, `seasonal-naive`
  (lag 1 day) with fit-day change quantiles as bands (as in Phase 1).
- `uni` is not run (cost; it ties `mv` in Phase 1).

### 15.6 Scores, alarms, metrics (D146)

- Band score per series (eps = 0.1), as Phase 1; mae and crps logged.
- Alarm per series: score above its own 99.5th percentile on calib (injections are per series, so the alarm is too).
- Injection detected: an alarm on the injected series in [start, end + 30 min); latency = first alarm - start.
- False alarms: alarms per day on test minutes of a series outside [start - 1 h, end + 6 h) of its injections.
- Detection curves: detection rate (of 6 trials) and median latency per (type, magnitude, duration) and method.
- Covariates: false alarms per day and detection with and without, at the calib threshold.
- Red team: the base's per-minute max band score over the 13 series in +-3 h around each red-team event cluster
  (days 1-29, history) against its 99.5th calib percentile, forecast for those windows only.

### 15.7 Compute and smoke

- Per seed one test pass (816 origins) per Chronos-2 run, calib once per run (336 origins). Estimated on MPS from the
  Phase 1 latency (a 10-row call at full context about 0.37 s): `mv` about 15 min per pass, so `mv`, `mv-cov` and
  FF over 3 seeds plus calib about 2.5 h. Baselines and frozen: minutes.
- Smoke: calib day 40 and test days 41-42, one seed, a reduced injection grid; the whole chain before the full run.
