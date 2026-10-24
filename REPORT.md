# REPORT: Chronos-2 zero-shot on HAI 21.03 (Phase 1) and LANL (Phase 2)

**Status: Phase 1 report, signed off by Arthur on 2026-10-21** (option B, section 4.20, added as an addendum). From `tsfm-ad all --optional 10s` (Chronos-2 on MPS,
13:15-20:49, commit `27d81f2`, every step passed). The 1 s comparison was not run (D134). Every result section was
filled from `results/phase1/` and each number was then recomputed independently from its file. Scoring and evaluation
were re-run from the cache into a scratch directory for three runs and matched exactly (section 9). Section 4.17
(bootstrap intervals and equal-false-alarm comparison, D135) was added after Arthur read the first version.

**Model.** Every result in this report is a **Chronos-2** result (`amazon/chronos-2`), not a Timestral result. The
project was planned for Mistral's Timestral. On 2026-10-20 Arthur switched Phase 1 to Chronos-2 for licence reasons
(CLAUDE.md; PLAN.md 14.1). No Timestral model was run for this report. Nothing here transfers to Timestral, which has a different
architecture, normalization and training data. Experiment 4 (model sizes) is deferred while Timestral is
paused.

**Number rule.** Every number here comes from a named file. Setup numbers come from the deterministic `prepare`
outputs (`results/phase1/attacks.csv`, `channels.csv`, `splits.csv`), from the Chronos-2 rows of
`results/phase1/mps_check.csv`, or from facts in `PLAN.md` that cite their own source. Results come from
`results/phase1/*.csv`.

Contents

1. [Summary](#1-summary)
2. [Setup](#2-setup)
3. [Deviations from the papers and the brief; labelled interpretations](#3-deviations-from-the-papers-and-the-brief-labelled-interpretations)
4. [Results](#4-results)
5. [What Chronos-2 does well and badly here](#5-what-chronos-2-does-well-and-badly-here)
6. [Threats to validity](#6-threats-to-validity)
7. [Not run, deferred, not measured](#7-not-run-deferred-not-measured)
8. [Open questions for Arthur](#8-open-questions-for-arthur)
9. [Reproduction](#9-reproduction)
10. [Phase 2: IT on LANL with injected anomalies](#10-phase-2-it-on-lanl-with-injected-anomalies)

---

## 1. Summary

- **Boundary vs interior: no boundary advantage in the segment means.** For the base `mv-lit` rolling run at N = 6, onset coverage is 0.263, interior coverage 0.295 and offset coverage 0.080, at a normal-step alarm rate of 0.003. The onset detection rate is 0.500 against a chance level of 0.018, and the interior rate 0.532 against 0.041 (`results/phase1/segments_summary.csv`). The predicted shape, high at both boundaries and low inside, is not there. The order of onset and interior flips with N: onset 0.107 and 0.318, interior 0.315 and 0.114, at N = 3 and N = 12. Only the 36 "other" attacks show onset above interior (0.236 against 0.108), and they get no offset alarm at all (same file). Offset alarms occur only in trip and pcv02d attacks, in 6 of those 14 (`segments_per_attack.csv`).
- **Context contamination: supported where it can be tested, but at 10 s that is a small part of the data.** The base raises no alarm on any of the 231 interior steps whose context holds attack data. It covers 0.367 of the 406 interior steps forecast from clean context. The zero holds in every h bucket; for h 1-10 it is 0.545 of 44 clean-context steps against 0.000 of 143 (`segments_by_h.csv`). The band widens with h (median q95 - q05 from 0.244 to 1.151 fit-z between h = 1 and h = 30, `band_width_by_h.csv`). That favours the short-horizon post-onset steps, so horizon does not explain the zero. A clean-context forecast from the onset (cf-onset, a labelled diagnostic) covers 0.459 of these steps at the same threshold and scores higher in 16 of 17 attacks (`cf_onset.csv`). But with H = 30, 406 of the 637 interior steps are forecast from clean, pre-onset context, and only 17 attacks (232 attack steps) have any post-onset step. On the clean-context majority, 0.633 of interior steps also get no alarm, and that is not contamination (section 3.9). The 10 s split is a weak test of the mechanism. At 1 s, 86.0 % of attack seconds come from post-onset contexts (section 3.9), but the 1 s block was not run (D134).
- **Univariate vs multivariate: a tie.** On the matched set `mvlit34`, `mv-lit` has a test PR-AUC of 0.39707 and `uni` 0.39695 (`selection.csv`). `uni` has the higher ROC-AUC, 0.880 against 0.862 (`metrics.csv`). `mv-lit` became the base, picked on test results, by 0.00012 PR-AUC. At three decimals the ROC-AUC tie-break would have picked `uni`. The D128 guard (an interpretation) moves no band-score calib threshold of the mv rolling runs by more than 0.214; the base threshold is 9.442. It moves the test band score by more than 1 on 3 of 1,341,300 forecasts (`d128_effect.csv`, `thresholds.csv`). Whether any alarm flips is not measured, so neither is whether the pick survives without the guard. A paired bootstrap (section 4.17) confirms it: the PR-AUC difference is +0.000 (95 % interval -0.017 to +0.020), while `uni`'s ROC-AUC is higher by 0.017 (0.003 to 0.032) (`bootstrap_paired.csv`).
- **Context protection makes things worse on the headline set.** The best of 1-3 is plain `mv-lit` rolling, picked on test results: PR-AUC 0.397, against 0.208 for `ff-interp-block`, 0.190 for frozen and 0.082 for dual (`selection.csv`). Forecast Fallback (our interpretation) alarms on 0.324 of normal test steps (`segments_summary.csv`), which is 116.489 false-alarm steps per hour against 1.112 for rolling (`metrics.csv`). It earns interior credit on only 3 `triggered_in_attack` attacks. There it covers 0.262 of the interior; rolling covers 0.480 of the same attacks (`segments_summary.csv`, `segments_per_attack.csv`). No max duration (30, 60, 120 steps) rescues it. Its higher PR-AUC without `P1_PCV02Z` (0.410 against 0.345) is not credited (section 4.6). Frozen (interpretation) has a PR-AUC of 0.190 with `P1_PCV02Z` and 0.192 without, against 0.397 and 0.345 for rolling. Dual (interpretation) is near chance: 0.082 and 0.036, against a chance level of 0.024 (`metrics.csv`). Frozen does alarm on 50 of the 232 post-onset attack steps where rolling raises none (`segments_per_attack.csv`). In the paired bootstrap all three are below rolling on PR-AUC and ROC-AUC, with intervals that exclude 0 (`bootstrap_paired.csv`).
- **Baselines: Chronos-2 does not beat `lastvalue` overall; at equal false alarms it depends on the alarm budget.** `lastvalue` forecasts the last observed value with fit-set change quantiles as its band. On the band score it has the higher PR-AUC on `uni51` (0.412 against 0.401) and on `mvlit34` (0.402 against 0.397). Its TaPR F1 is much higher: 0.554 against 0.398, and 0.538 against 0.400 (`metrics.csv`, `tapr.csv`). Chronos-2 leads only on `uni57`. It clearly beats `robustz` on the band score (`robustz` PR-AUC 0.171 and 0.142). On these two sets it also raises fewer false alarms than any baseline: 1.224 and 1.112 steps per hour, against 2.598 to 6.449. `seasonal-refday` nearly matches its PR-AUC (0.395 and 0.385) at 4.2x and 5.8x the false alarms (`metrics.csv`). The PR-AUC difference to `lastvalue` is -0.005 (95 % interval -0.129 to +0.103), a tie that 50 attacks cannot resolve. At the calib threshold the methods run at different false-alarm rates. At matched rates (threshold set from the test labels, evaluation only, section 4.17), `mv-lit` detects 28 attacks against 14 for `lastvalue` at 0.5 false alarms per hour (detection-rate difference 0.28, interval 0.15 to 0.58). At 5 per hour `lastvalue` covers more attack steps (recall 0.530 against 0.420, TaPR F1 0.654 against 0.499; both intervals exclude 0) (`fa_matched.csv`, `bootstrap_paired.csv`). With the mae score, which uses only the median forecast, Chronos-2 beats `lastvalue` on PR-AUC on both sets (+0.097, 0.048 to 0.146 on `mvlit34`; +0.053, 0.003 to 0.088 on `uni51`). The band score is the planned headline and stays so.
- **Forecast quality and model size are not the bottleneck.** On normal data Chronos-2's median forecast has about 25 % lower error than `lastvalue` (mae 0.388 against 0.508 on `uni51` calib, `forecast_accuracy.csv`), yet the two tie on the band score. `chronos-2-small` (28M against 119M parameters, D136) detects the same number of attacks at every equal false-alarm rate (30-40 against 31-40 of 50, band score), ties on PR-AUC (difference +0.010, 95 % interval -0.002 to +0.020) and runs 3.7x faster per call (0.344 against 1.268 s); only the big model's ROC-AUC is higher (+0.017, 0.006 to 0.030) (`fa_matched.csv`, `bootstrap_paired.csv`, `size_latency.csv`; section 4.18).
- **In the paper's own setting the paper's pattern appears, and Chronos-2 loses to every baseline.** At 1 s with a 128-step history (D137, section 4.19), interior coverage is 0.022 against 0.110 at the onset and the interior detection rate falls below chance (0.283 against 0.451), because 86.0 % of attack steps are forecast from a context that holds the attack. A clean-context forecast from the onset covers 0.437 of those interior steps, rolling 0.028 (6,014 steps, 46 attacks, `cf_onset.csv`). A 10 s control with the same 128-step history shows no interior drop, so the forecast restart rate relative to the attack length decides it, not the history length. Band PR-AUC there is 0.081 against 0.172-0.341 for the baselines (`metrics.csv`). Our Forecast Fallback diverges to non-finite values without an exit and with a 30-step exit; with a 120-step exit it alarms on 0.176 of normal steps and lowers ROC-AUC (0.666 against 0.764, the paper's mae score).
- **Option B: restarting every minute brings the pattern to 10 s (addendum, D138, section 4.20).** The headline `uni` run with H = 6 instead of 30 (a new forecast every minute, same 8,192-step history) has onset coverage 0.593 and interior coverage 0.079 (H = 30: 0.280 and 0.290), offset 0.027, at a normal-step alarm rate of 0.0039 (`segments_summary.csv`, band). 69.8 % of attack steps are now forecast from a context that holds the attack, and those alarm on 0.087 of steps against 0.610 for the clean-context steps (`segments_per_attack.csv`). It detects 47 of 50 attacks at the calib threshold (31 with H = 30) and 15 more at 1 false alarm per hour (interval excludes 0), but its ROC-AUC is lower (0.817 against 0.894; difference +0.077, 0.048 to 0.108) and PR-AUC is not resolved (`metrics.csv`, `fa_matched.csv`, `bootstrap_paired.csv`). The mae score shows no such drop. So the hypothesis holds for the onset and the interior, not for the offset, and only on the band score.
- **What fails.** At the calib threshold the base alarms on 0.244 of attack steps, with precision 0.657 (`metrics.csv`). It misses 20 of 50 attacks, all in the "other" stratum. On the band score (dual score for dual), no method detects 5 of them: A203, A205, A210, A214 and A220 (`segments_per_attack.csv`). Many misses depend on the score: with crps or mae the base itself detects 45 and 44 of 50 attacks, A203 and A210 among them, at 4.627 and 3.243 false-alarm steps per hour (`segments_per_attack.csv`, `metrics.csv`). A205 and A214 get no alarm in any row of `segments_per_attack.csv`. False alarms run at 1.112 steps per hour. That is 119 steps (alarm steps minus alarmed attack steps, `metrics.csv`), below the 1.8 per hour a calib-like test set would give. 24 of them fall in the 60 s after trip and pcv02d attacks (`segments_per_attack.csv`). No results file says which channels raise the rest. Bands wider than 10 fit-z are rare on calib (0.0026 % of `mv-lit` forecasts). They reach 0.38 % on test and 2.0 % on attack steps (`quantile_diagnostics.csv`), and on those forecasts the band score is nearly blind. Their effect on the metrics is not measured.
- **Scope.** One dataset, HAI 21.03, whose attacks are short (17-422 s, `attacks.csv`). One resolution (10 s), zero-shot, one Chronos-2 checkpoint, on MPS. Experiment 4 (model sizes) is deferred while Timestral is paused. The 1 s comparison was not run: Arthur deferred it until after this report (D134). Intervals come from one paired block bootstrap (section 4.17). They are wide: with 50 attacks, PR-AUC gaps under about 0.1 between Chronos-2 and the better baselines are not resolved. Nothing here transfers to Timestral.



---

## 2. Setup

### 2.1 Data: HAI 21.03

- Source: github.com/icsdataset/hai, folder `hai-21.03`, 8 `.csv.gz` files (3 train, 5 test), 1 s resolution
  (PLAN.md 3.1). The repository commit of the local copy is UNCONFIRMED; file SHA-256 sums are in the research notes
  (`hai_data.md`, "Sources").
- 79 tags in 4 processes: P1 boiler, P2 turbine, P3 water treatment, P4 HIL simulator (PLAN.md 3.1;
  `results/phase1/channels.csv`). Labels: `attack` (ground truth) plus `attack_P1..P3` (diagnostics only, D2).
- Train files hold no attack label. Test files hold 50 attacks: test1 5, test2 20, test3 8, test4 5, test5 12
  (`results/phase1/attacks.csv`).
- Attack durations: 17 s (A203) to 422 s (A202); 3 to 43 steps at 10 s. 8,947 attack seconds at 1 s; 934 attack
  steps at 10 s (`attacks.csv`, columns `duration_s`, `steps_10s`). Processes: P1 23, P2 11, P1+P2 8, P1+P3 3,
  P2+P3 3, P3 2 (`attacks.csv`, `processes`).
- **HAI 21.03 has no long-term attack.** The longest is 422 s. The dataset documents no scenario over 10 minutes for
  21.03 (PLAN.md 3.3, `HAI-PDF p.27-29`). The hypothesis is about a "persistent interior"; here the interior is at
  most 37 steps (6 min) at 10 s.

**Preprocessing** (PLAN.md 4; D3-D7):

1. Read every tag as Float64, labels as Int8. Drop the last row of each file (each file holds both endpoints).
2. Drop the 22 tags that are constant over the `fit` + `calib` rows (D57).
3. Default resolution 10 s (D6): mean over the bin for continuous targets and actuator commands, last value for step
   covariates, max for the labels (a bin is an attack bin if any second in it is). 1 s is the optional
   short-context config.
4. z-score per channel with mean and std from the `fit` segments only (train2 + train3), at the run's resolution
   (D7). The statistics are in `channels.csv` (`mean_fit`, `std_fit`).

**Channel roles** (PLAN.md 3.4; counts from `channels.csv` at 10 s):

| role | rule | count | tags |
|---|---|---|---|
| dropped | constant over fit + calib rows | 22 | P1 8, P2 12, P3 2 |
| step covariate (the brief's "discrete") | changes on < 1 % of 1 s fit + calib steps | 6 | P1_B2004, P1_B3004, P1_B3005, P1_B4002, P4_HT_PS, P4_ST_PS |
| actuator command | name ends in D and the PDF calls it a valve/pump command | 7 | P1_FCV01D, P1_FCV02D, P1_FCV03D, P1_LCV01D, P1_PCV01D, P3_LCP01D, P3_LCV01D |
| continuous target | everything else | 44 | P1 21, P2 10, P3 3, P4 10 |

**Channel sets** (`channels.csv`, columns `uni51` ... `mvacttgt41`; PLAN.md 3.4):

| set | channels | used by |
|---|---|---|
| `uni51` | 44 continuous + 7 actuator = 51 | experiment 1 headline (D39) |
| `uni57` | `uni51` + 6 step tags = 57, every non-constant channel | experiment 1 brief-literal secondary |
| `mvlit34` | P1 21 targets + 9 covariates (4 step, 5 actuator); P2 10 targets; P3 3 targets + 2 actuator covariates; 34 scored | experiment 2 headline `mv-lit` |
| `mvacttgt41` | P1 26 targets + 4 step covariates; P2 10; P3 5; 41 scored | experiment 2 secondary `mv-acttgt` |
| `<set>-noPCV02Z` | the same set without `P1_PCV02Z` | every run is also scored on it (D50) |

P4 is not a group in experiment 2 (D23). `P4_HT_PS` and `P4_ST_PS` are forecast only in `uni57`.

### 2.2 Splits and warm-up

The files interleave in time: test1, test2, train1, test3, test4, test5, train2, train3 (PLAN.md 3.1). test1 and
test2 come before any train file. So "strict time-based split" is read as per-file roles: no test row fits a
normalization statistic or a threshold, and no test score tunes a hyperparameter (D8, Q3). Several design choices did
use test files, test labels or the PDF timetable; section 6.3 lists them.

| segment | split | source | time range (1 s rows kept) | 10 s steps | scored 10 s steps | role |
|---|---|---|---|---|---|---|
| train2, train3 | fit | train2, train3 | 2020-07-31 22:00:00 to 2020-08-03 12:59:59; 2020-08-04 22:00:00 to 2020-08-10 10:59:59 | 22,680 + 47,880 | 0 | normalization statistics, baseline error quantiles |
| reference | ref | train3, last 24 h | 2020-08-09 11:00:00 to 2020-08-10 10:59:59 | 8,640 | 0 | frozen context (3b), seasonal-refday reference day, prepend source |
| train1a, train1b | calib | train1, two 24 h pseudo-files | 2020-07-11 00:00:00 to 23:59:59; 2020-07-12 00:00:00 to 23:59:59 | 8,640 + 8,640 | 8,490 + 8,490 | detection thresholds, FF per-feature thresholds |
| train2a, train2b | calib2 | train2, two full days | 2020-08-01; 2020-08-02 | 8,640 + 8,640 | 8,490 + 8,490 | sensitivity thresholds only; **overlaps fit** (D51) |
| train1_dup | excluded | train1 | 2020-07-13 00:00:00 to 11:59:59 | 4,320 | 0 | identical on all 79 tags to test3's first 12 h; used nowhere |
| test1 ... test5 | test | whole files | | 4,320 / 11,880 / 10,800 / 3,960 / 9,240 | 4,170 / 11,730 / 10,650 / 3,810 / 9,090 (39,450) | evaluation only |

All from `results/phase1/splits.csv`. `calib` does not overlap `fit`. train1 was recorded inside the test period
(between test2 and test3) and shares the `P1_PCV02Z` level of most test files; that is why it is `calib` (D10, a
test-informed choice). The 12 h duplicate is cut from train1, not from test3, so test3 keeps its full history (D9).

**Warm-up** (D11): `in_file`. The context at origin `o` is the same file's history only. The first `W` = 1,500 s
(150 steps at 10 s, 1,500 at 1 s) of every test and calib file are context only and are not scored. No attack falls
in the warm-up: the in-file history before the first attack is 211 (test1, A101), 282 (test2, A201), 4,986 (test3,
A301), 258 (test4, A401) and 156 steps (test5, A501) (`attacks.csv`, `history_steps`). A501 starts 6 steps into the
first scored window. The optional `prepend` run puts the last 8,192 steps of train3 before every calib and test file
instead (D81); its junction joins recordings made 10 to 34 days apart (PLAN.md 5).

### 2.3 Model: Chronos-2

| item | value | source |
|---|---|---|
| checkpoint | `amazon/chronos-2`, revision `29ec3766d36d6f73f0696f85560a422f50e8498c` | `configs/base.yaml` |
| parameters | 119,477,664, all float32 | `configs/base.yaml` `model.chronos2.params`; PLAN.md 14.2 |
| weights | `model.safetensors` sha256 `ddcda3c7508bf2528087723e98a20707cc04b7f370ae275a9fd88078ddba4f42` | PLAN.md 14.2 |
| package | `chronos-forecasting==2.3.2` (tag v2.3.2 = commit `0aba28e`), torch 2.14.1, transformers 5.20.2, Python 3.12 | `pyproject.toml`, `uv.lock`; PLAN.md 14.2 |
| licence | Apache-2.0 | PLAN.md 14.2 (`C2-CARD:2`) |
| dtype | float32, checked for every parameter at load | D119 |
| quantiles | 21 native levels 0.01, 0.05, 0.10, ..., 0.95, 0.99; q05, q50, q95 are native, nothing is interpolated | PLAN.md 14.5 |
| sampling | none; direct quantile output, bit-deterministic on CPU and MPS | PLAN.md 14.3 (T1 §7, T2 §D) |

**Context cap 8,192** (D118). That is the Chronos-2 maximum; longer input is cut silently from the left, so the
adapter refuses T > 8,192 and `ctx_len` in the cache is what the model read (PLAN.md 14.3). The brief's 32,768
steps is a Timestral figure. At 10 s, 8,192 steps are 22.8 h. With in-file warm-up the cap binds from origin 8,220
on: 3,660 scored steps of test2, 2,580 of test3 and 1,020 of test5, so 7,260 of 39,450 scored test steps (18.4 %)
and 242 of 1,315 test origins. 12 attacks have steps forecast from a capped context: A215-A220, A306-A308,
A510-A512. In `calib` and `calib2` the cap binds on the last 420 steps of each pseudo-file (840 of 16,980 scored
steps, 4.9 %). test1 and test4 are shorter than the cap. (PLAN.md 14.6; reproducible from the file lengths in
`splits.csv` and `history_steps` in `attacks.csv`.) The frozen context is the last 8,192 steps of the 8,640-step
reference day (from 2020-08-09 12:14:40). At 1 s the cap is 2.3 h and binds on 92 % of scored steps (PLAN.md 14.6).

**Univariate calls (`uni`, `uni57`).** One call per origin. The V channels go in as V items of one variate each,
`(V, 1, T)`, with `cross_learning=False` and `limit_prediction_length=True`. Each item is its own group, and
Chronos-2 masks group attention across groups with `finfo(float32).min`, so cross-channel attention weights are
exactly zero (PLAN.md 14.3, `C2:DS:253-263`, `C2:MD:122-142`). Independence was checked, not assumed (PLAN.md 14.4):
on toys, rows 1-50 stayed bit-identical when row 0 was scaled x50, stepped, or given a NaN gap, on CPU and MPS,
while a joint `(1, 51, T)` item or `cross_learning=True` moved them. In the test suite a tiny randomly initialised
`Chronos2Model` with the real attention mask keeps rows bit-identical under three perturbations of row 0, the
cross-learning control moves them, and a mutation script shows the test fails when the adapter is broken
(`tests/test_chronos2.py`, `SP/switch/mutation.py`). Experiment 1 is truly univariate.

**Multivariate calls (`mv-lit`, `mv-acttgt`).** One dict item per process group (P1, P2, P3) and origin:
`{"target": (V_g, T), "past_covariates": {name: (T,)}}`, the covariates exactly T long and never forecast. Targets of
one group are forecast jointly; groups are never merged into one call, because an all-NaN padding row is not neutral
(PLAN.md 14.3).

**Adapter changes to the raw model**, both labelled interpretations (sections 3.7 and 3.8): crossing quantiles are
sorted (D119), and rows that are constant over their context are passed as exact zeros (D128).

### 2.4 Forecasting loop

- Rolling per file, calib and test alike (PLAN.md 6). Origins `o = W, W + H, W + 2H, ...`. The window is
  `[o, o + H)`; the context is `[max(0, o - 8192), o)` of the same file and ends at `o - 1`.
- `H = 30` steps (5 min at 10 s), stride `H` (D13). Every scored step gets exactly one forecast, with horizon
  `h = t - o + 1` in 1..30. H = 30 costs the same as H = 32 and equals its first 30 steps bit for bit (PLAN.md 14.3).
- Calls at 10 s: 1,315 test origins, 566 calib origins, 566 calib2 origins (`splits.csv` scored steps / 30). The
  multivariate setups make three calls per origin.
- Two arrays per file (D58): `Z_obs`, read-only, the only source of `y_true`, of the FF trigger and of every score;
  and `Z_ctx`, the copy contexts are sliced from. Only Forecast Fallback writes to `Z_ctx`.
- Every forecast is cached with all 21 quantiles to parquet under
  `cache/<dataset>/<model>/<setup>/<variant>@<hash8>/`. The hash covers the settings, the prepared inputs and the
  forecasting source (D34, D120). Scoring, evaluation and figures read the cache only.
- Seeds fixed (`seed: 0`); Chronos-2 itself has no sampling.

### 2.5 Scoring and thresholds

All in z units of the `fit` std (PLAN.md 7). Per channel `c` and scored step `t`:

| score | formula | role |
|---|---|---|
| `band` | `max(0, y - q95, q05 - y) / (q95 - q05 + eps)`, `eps = 0.1` z (D17, fixed a priori) | headline |
| `crps` | `2 * sum_i w_i * pinball_tau_i(y - q_i)` over the 21 levels, midpoint-rule weights (edges at 0, the midpoints between levels, and 1; they sum to 1) | alternative (brief) |
| `mae` | `|q50 - y|` | comparable with Lowe et al. (`fmsd:163-178`) |
| `dual` (3c only) | `sum_i w_i * |q_i_recent - q_i_frozen| / (q95_frozen - q05_frozen + eps)`; does not use y | headline of 3c |

- A constant context gives a zero-width band, so a flat channel's band score is `deviation / eps` (D17, D39).
- Aggregation across the scored channels of a set: **mean of the top 3** (headline, `k = 3`, D19) and `max`
  beside it; `mean` over channels only with `mae`, to mirror Lowe et al. Smoothing is off.
- Threshold: the **99.5th percentile** of the aggregated score over all scored `calib` steps (16,980 at 10 s,
  `splits.csv`), separately for every run, channel set, score and aggregation (D20, D49). A restricted set never
  reuses the full set's threshold. Alarm = score > threshold. `calib2` gives a sensitivity threshold for the `uni`
  and `mv-lit` rolling runs only (D51). Thresholds go to `results/phase1/thresholds.csv`.
- If the test data behaved like `calib`, a 99.5th-percentile threshold would alarm on 0.5 % of normal steps, about
  1.8 false-alarm steps per hour at 10 s (0.005 x 360 steps). This is a reference, not a result.
- Normalization statistics and thresholds come only from normal training data. Nothing is tuned on test labels.
  The two D21 picks are made on test metrics and are marked so (section 3.10).

### 2.6 Metrics

All on the scored test steps (`t >= W`), concatenated over the five files; label = the binned `attack` column
(PLAN.md 9).

- **ROC-AUC** and **PR-AUC** (average precision, scikit-learn) on the continuous aggregated score. Chance levels:
  ROC-AUC 0.5; PR-AUC = the positive share, 934 / 39,450 = 0.024 at 10 s and 8,947 / 394,500 = 0.023 at 1 s
  (`attacks.csv`, `splits.csv`; every attack lies after the warm-up).
- **Point metrics at the calib threshold**: precision, recall, F1, alarm steps, false-alarm steps per hour of normal
  test data (38,516 normal scored steps = 107.0 h at 10 s).
- **TaPR**, the official `TaPR.py` (github.com/saurf4ng/TaPR, now wshw4ng/TaPR, commit `47d3161`, sha256
  `0ada5df354e6f8d06581c5b19eaf659cee656be8c0f3a22ac32f55c66e74b6b1`), vendored unmodified in `vendor/TaPR/` and
  called in memory (D30, D31). Parameters (`configs/base.yaml`, `metrics.tapr`):

  | config | alpha | theta | delta | note |
  |---|---|---|---|---|
  | headline | 0.5 | 0.5 | 180 s (18 steps at 10 s, 180 at 1 s) | |
  | strict | 0.5 | 0.5 | 0 | no post-attack credit |
  | haicon_like | 0.5 | TaR 0.1, TaP 0.7 (two TaPR objects) | 180 s | official TaPR.py with HAICon 2020 thresholds; **not eTaPR, not comparable to the HAICon leaderboard** |

  F1 = 2 TaP TaR / (TaP + TaR) is ours; TaPR.py does not compute it. Files are joined with `delta + 1` normal steps
  between them, so ranges never merge across files. The TaPR.py file loaders are not used (they give TaR = 1.0 to a
  detector that never fires). Kept as is: TaPR.py detects with `> theta` where the paper says `>=` (issue
  wshw4ng/TaPR#2).
- **Point-adjusted F1** is computed only in a column named `pa_f1_inflated`. It inflates results and is never a
  headline. Wherever it appears below it is labelled.
- **Boundary vs interior** (D29, D45): per attack, onset = the first N attack steps, interior = the rest of the
  attack, offset = the N steps after the end (labelled normal; cut at the next attack or the file end). N = 60 s
  (6 steps at 10 s, 60 at 1 s). `interior_eq` = attack steps N+1..2N, for attacks with L >= 2N (37 of 50 at 10 s,
  `attacks.csv` `interior_eq_10s`). Empty interior at 10 s: A203, A211, A508 (`interior_empty_10s`). N was chosen
  partly from test data (section 6.3); N = 30 s and 120 s go to the appendix.
  - Headline segment metric = **coverage** (share of the segment's steps with an alarm).
  - Detection rate (any alarm in the segment) is always shown with its chance level `1 - (1 - p)^n`, p = the run's
    alarm rate on normal scored test steps, n = segment length, averaged over the attacks. For illustration only, at
    p = 0.005 the chance any-alarm rate is 3.0 % for a 6-step onset and 6.3 % / 16.9 % for the median / longest
    10 s interior (PLAN.md 9). Alarms are autocorrelated, so the chance level is a reference, not a test.
  - Latency = first alarm in the attack minus attack start, in seconds. A miss is censored at duration + N. Medians
    are over the attacks that every compared method detects (`latency_common_median_s`, with `n_common`) and over
    the censored latencies of all attacks; never over each method's own detected subset (D48).
  - Origin side: a step is `post` if its forecast origin lies after the onset step (its context holds attack data),
    else `pre`.
  - Offset strata (D47): `trip` (9 turbine-trip attacks), `pcv02d` (5 attacks where `P1_PCV02D` moves), `other` (36)
    (`attacks.csv`, `stratum`).
- **Mechanism test** (D46): coverage by origin side within h buckets (1-10, 11-20, 21-30) and time-since-onset
  buckets (0-59, 60-119, 120-239, >= 240 s); the band width by h from the calib cache; and the `cf-onset`
  counterfactual (section 3.6).

### 2.7 Device

- **Headline runs: MPS** (Apple M5), cache key `chronos2-29ec376-mps`, one device for every headline run (D15, D130).
- **The rule that allowed MPS was set after seeing the check's numbers, at Arthur's decision** (D130, 2026-10-20
  12:40, answer to Q18). The planned rule (D54) was absolute: max |q_mps - q_cpu| <= 1e-3 z over all 21 quantiles of
  every cached row, plus identical test alarms. Every Chronos-2 row failed it, always through `P1_PCV02Z`, whose
  values reach about 510 fit-z because its fit std is tiny (0.00429 at 10 s, `channels.csv`), so float32 rounding
  alone exceeds 1e-3 z there. Arthur replaced it with a relative rule: max |q_mps - q_cpu| / (|q_cpu| + 1) <= 1e-3
  and identical test alarms. He wanted the runs done the same night; MPS is about 1.8x faster (D130).
- The check: smoke slices, rolling forecasts on calib and test, CPU (4 threads) vs MPS, each scored with its own
  smoke threshold (D105). From `results/phase1/mps_check.csv` (Chronos-2 rows, checked 2026-10-20 13:15):

  | dataset | setup | values | max abs diff (z) | max abs diff without `P1_PCV02Z` (z) | max rel diff | test alarms cpu / mps (test steps) | absolute rule (1e-3 z) | relative rule (D130) |
  |---|---|---|---|---|---|---|---|---|
  | hai2103-10s-smoke | uni | 1,220,940 | 1.04e-3 | 1.05e-4 | 5.6e-5 | 21 / 21 (570) | fail | pass |
  | hai2103-10s-smoke | uni57 | 1,364,580 | 1.04e-3 | 1.05e-4 | 5.6e-5 | 21 / 21 (570) | fail | pass |
  | hai2103-10s-smoke | mv-lit | 813,960 | 1.83e-3 | 8.15e-4 | 1.37e-4 | 21 / 21 (570) | fail | pass |
  | hai2103-10s-smoke | mv-acttgt | 981,540 | 1.98e-3 | 8.11e-4 | 1.36e-4 | 21 / 21 (570) | fail | pass |
  | hai2103-1s-smoke | uni | 12,209,400 | 2.69e-3 | 4.01e-4 | 8.57e-5 | 37 / 37 (5,700) | fail | pass |

  The file's `verdict` column records the relative rule; the absolute verdict is `max_abs_diff` against 1e-3. The
  largest relative gap is at least 7x inside the relative rule.
- **Smoke on CPU** (D132): the smoke chain runs on CPU, the reference device of the check, and the check runs every
  smoke rolling forecast on both devices. Only the smoke is on CPU.
- A CPU run of `all` started at 12:23 was stopped at about 13:10, after experiment 1 `uni` calib, calib2 and test1.
  Those forecasts stay in the `chronos2-29ec376-cpu` cache directory; no number in this report comes from them
  (PLAN.md 0).

### 2.8 Baselines (experiment 5)

Each writes 21 quantiles in the cache schema, forecasts all 57 non-constant channels and is scored exactly like
Chronos-2 on every channel set, with its own calib thresholds (D28, D49; PLAN.md 8).

| baseline | forecast for window `[o, o + 30)` | band (21 levels) |
|---|---|---|
| `robustz` | median `m` of the trailing 360 steps (1 h at 10 s) before `o` | `m + Phi^-1(tau) * 1.4826 * MAD` of the same window |
| `lastvalue` | `y(o - 1)` for all h | `y(o - 1) + Q_tau(Delta_h)`, `Delta_h` = h-step changes over the `fit` set, per channel and h |
| `seasonal-refday` | the `reference` day's value at the same clock time | value + `Q_tau(D)`, `D` = day-over-day differences within train2 and within train3, per channel |

`seasonal-refday` is a reference-day model, not seasonal-naive on the series (section 3.6).

### 2.9 Run matrix (PLAN.md 14.7)

"base" = the setup picked by `select --stage base` (D21, on test results).

| exp | setup | variant | config | run |
|---|---|---|---|---|
| 1 | uni | rolling (+ calib2), cf-onset | `exp1_uni.yaml` | yes |
| 1 | uni57 | rolling | `exp1_uni57.yaml` | yes |
| 2 | mv-lit | rolling (+ calib2), cf-onset | `exp2_mv.yaml` | yes |
| 2 | mv-acttgt | rolling | `exp2_mv_acttgt.yaml` | yes |
| 5 | robustz, lastvalue, seasonal-refday | rolling | `exp5_baselines.yaml` | yes |
| 3b | base | frozen | `exp3b_frozen.yaml` | yes |
| 3c | base | dual (no inference) | `exp3c_dual.yaml` | yes |
| 3a | base | ff-interp-block | `exp3a_ff_interp_block.yaml` | yes |
| 3a | base | ff-interp-block-max60-testinf | `exp3a_ff_interp_block_max60.yaml` | yes |
| opt | base | prepend | `opt_prepend.yaml` | yes (`--optional 10s`) |
| opt | base | ff-interp-block-max30, -max120 | `opt_ff_max_sens.yaml` | yes (`--optional 10s`) |
| 4 | | model sizes | `configs/timestral/exp4_*.yaml` | no, deferred |
| 1 s | uni | rolling-c8192 (+ baselines), cf-onset, ff-interp-block; the 10 s uni FF reference | `res1s_uni.yaml`, `res1s_ff_interp_block.yaml`, `res10s_uni_ff.yaml` | no, deferred (D134) |

Also run: the D128 effect of the uni, mv-lit and mv-acttgt runs and of frozen on the base (D129), and both
`select` stages.

---

## 3. Deviations from the papers and the brief; labelled interpretations

### 3.1 The papers, and what can be compared

- The brief's two sources are different papers by different groups; neither cites the other (PLAN.md 1).
  - Uray et al. 2026 (arXiv 2607.12454): EUROCAST 2026 preprint, TimesFM, SWaT, context w = 100, horizon 32.
  - Lowe, Fung, Bauer 2026 (the brief's "ICML 2026 paper"): a **poster at the 2nd ICML Workshop on Foundation Models
    for Structured Data**, not an ICML main-track paper (`Lowe:fmsd:44-46`). Chronos-2 and Moirai-2.0 zero-shot on
    SWaT, TEP and CTown, inputs of 32, 64 or 128 steps, H in {1, 16, 32}. It is the only source of Forecast Fallback.
- Neither paper uses HAI, TaPR or point-adjust. Both tune their F1 threshold on test labels (`Uray:tex:422-424`;
  `Lowe:fmsd:327-330`); we do not. Lowe et al. also chose their FF input and horizon settings on test ROC-AUC
  (`Lowe:fmsd:564-566`). No number in either paper is comparable with ours. ROC-AUC is the one metric we share with
  Lowe et al., on other data.
- Lowe et al. ran Chronos-2; their Fig. 3, the onset-only pattern with the FF illustration, is Chronos-2 on TEP
  (PLAN.md 14.1). So the model switch makes Phase 1 closer to their setup. Their checkpoint and revision are
  UNCONFIRMED, and our contexts are up to 8,192 steps against their 32-128, so their Chronos-2 behaviour need not
  carry over (PLAN.md 14.9 item 8).
- What "baseline" means there: Lowe et al.'s "Baseline" is the plain foundation-model forecast without FF (our
  `rolling`), scored by the MAE averaged over all features (our `mae` with `mean`). It has no non-AI baseline like our
  `lastvalue`. Their Chronos-2 baseline ROC-AUC is 0.239-0.517 over their datasets, inputs and horizons (Table 2,
  `Lowe:fmsd:446-522`), at or below chance, and FF lifts the best settings to 0.523-0.903 (Fig. 4, settings chosen on
  test ROC-AUC). Ours is far above chance at 10 s (band 0.862-0.894 for the rolling headline rows; mae 0.848-0.874 over
  every rolling setup, channel set and aggregation; `metrics.csv`, sections 4.1-4.2). Data, input
  length and resolution all differ, so the gap is not explained by any single factor (section 7).
- OpenReview (forum `zKWdTO8ART`) was not reachable, so reviews and any supplementary material were not checked (Q13).

### 3.2 The model switch (brief deviation, Arthur's decision)

- The brief names Timestral as the model under test and its sizes for experiment 4. Phase 1 runs `amazon/chronos-2`
  instead (D117). The brief's "optional stretch: Chronos-2" became the main model. TimesFM was not run.
- Experiment 4 cannot run with one model size: Chronos-2 has one checkpoint with the 21 cache quantile levels.
  `autogluon/chronos-2-small` (27,934,624 parameters) has 13 levels, not 21 (PLAN.md 14.2; Q19).
- The context cap drops from the brief's 32,768 (Timestral) to 8,192 (D118; section 2.3).

### 3.3 Experiment 1 on 51 of 57 channels (D39)

The brief says "every channel forecast independently", which would be all 57 non-constant channels. The headline
forecasts 51 (`uni51`). Reason, from train data only: the 6 step tags change on at most 0.15 % of train steps
(`channels.csv`, `change_rate_train`), so they are piecewise constant; a constant context gives a zero-width band and
a band score of `deviation / eps` at every scheduled setpoint change. The literal reading runs as the labelled
secondary `uni57` and is reported beside it. Which is the headline is open (Q17).

### 3.4 Experiment 2 roles (D22, D23)

- `mv-lit` follows the brief: actuator commands and step setpoints are past-only covariates, so they are never
  forecast or scored.
- `mv-acttgt` (actuator commands as targets) is a labelled secondary. It exists because the actuator commands are the
  tags most directly attacked (28 of 50 attacks list a `*D` target in the PDF timetable, PLAN.md 3.4, probe 11),
  which is test knowledge (section 6.3, item 6). It is never a base (D40, Q1).
- P4 is not a group and not a covariate (Q2).

### 3.5 Forecast Fallback (experiment 3a): our interpretation

Lowe et al. released no code (GitHub searches found none; PLAN.md 1). The paper states only the 3-step trigger and
the 99.5th-percentile per-feature level (`Lowe:fmsd:300-319`). Everything else is ours, so the variant names carry
`interp`, and none contains "paper" (D24, D43).

| item | our choice | status |
|---|---|---|
| trigger statistic | per-feature `|q50 - y|`, y from `Z_obs` | paper (per-feature error); the median as point forecast is ours |
| per-feature threshold `tau_c` | 99.5th percentile of `|q50 - y|` on `calib`, from the base rolling run | level from the paper; data source not stated in the paper |
| trigger rule | 3 consecutive steps of a feature above `tau_c`; the counter carries across window boundaries | paper (3 steps); carry-over ours |
| action | from the 3rd exceeding step on, replace the observation in `Z_ctx` by `q50`; the 2 earlier steps stay observed | paper text and poster diagram |
| block adaptation (H = 30) | after each window is observed, substitute from the trigger step to the window end; while in fallback, every later window's observations are replaced by that window's `q50` before they enter `Z_ctx` | INTERPRETATION (the paper shows one-step rolling only) |
| scope | per feature (`scope: feature`); option `all` not run | INTERPRETATION |
| exit | none; state resets at each file start | INTERPRETATION (the paper gives no exit rule) |
| covariates | never substituted | INTERPRETATION |
| scoring | always against the real observation (`Z_obs`) | paper Fig. 3 |
| detection threshold of an FF run | from the FF run's own calib scores | follows the brief's threshold rule |

Variants (D25, D66):

- `ff-interp-block`: no exit. Headline FF variant and a "best of 1-3" candidate.
- `ff-interp-block-max60-testinf`: leaves fallback after 60 substituted steps (10 min); substituted values stay in
  `Z_ctx`; re-entry needs 3 new exceedances (D78). **`-testinf` means test-informed:** 60 was set to exceed the
  longest test attack (43 steps) plus the longest post-attack excursion in the test files. So it is not a candidate.
- `ff-interp-block-max30`, `-max120`: optional sensitivity, fixed in advance, reported without a pick. They are half
  and double the test-informed 60, so they are not fully independent of test knowledge either.

What block FF can and cannot change: substitution only feeds the context of later windows. 33 of 50 attacks lie
inside one window issued before onset (`attacks.csv`, `n_windows_10s` = 1). For them FF can change the forecast
inside the attack only if fallback was already active before onset. A false trigger on normal data makes the forecast
free-run for the rest of the file, and a drifting free-run forecast can raise scores on its own. So each attack gets
an FF group (D44, D95): `pre_active` (fallback active at onset), `triggered_in_attack` (a trigger in [onset, end + N])
or `none`. **FF is credited with interior detection only on `triggered_in_attack` attacks**, and its alarm rate on
normal test steps is shown next to its coverage.

### 3.6 Frozen, dual, seasonal-refday, cf-onset

- **Frozen (3b), INTERPRETATION, literal reading of the brief**: every window is scored against one forecast from a
  fixed clean context, the last 8,192 steps of the `reference` day (covariates included for mv setups). That gives one
  30-step band per channel, the same for every window (indexed by h). It never sees test data. Its threshold comes
  from `calib` scored against the same band. The plant has a daily setpoint schedule, so a static band is expected to
  give false positives whenever the plant is away from the reference operating point. A time-of-day-aligned
  reference was not run (Q11).
- **Dual (3c), INTERPRETATION**: quantile Wasserstein-1 between the base rolling forecast and the frozen forecast,
  normalized by the frozen band width (D27). Neither paper proposes it. No extra inference.
- **The `P1_PCV02Z` offset** (D50, decided before any result): `calib` and the test files before the A302/A512
  shifts sit about +54 fit-z above the `reference` day (PLAN.md 3.4, train data). Frozen, dual and
  `seasonal-refday` compare with that day, so they are reported on the full set (headline) and on `-noPCV02Z`.
- **`seasonal-refday` is a reference-day model, not seasonal-naive on the series** (D28): every file is compared with
  the same clean day at the same clock time.
- **`cf-onset` is a diagnostic, never a detector** (D46). One extra forecast per attack from the onset step (off the
  rolling grid), context = the same file's history before onset (clean), horizon L + N (at most 49 steps at 10 s). Its
  origin uses the test labels. It is compared step by step with the rolling forecast. Two confounds: its horizon is
  longer than the rolling one, and the number of Chronos-2 output patches differs (up to 4 vs 2), which on its own
  changes a forecast (PLAN.md 14.3, 14.6). The `h_cf <= 30` subset removes the first, not the second.

### 3.7 The D128 constant-row guard (INTERPRETATION that changes multivariate forecasts)

- Chronos-2 replaces a zero context scale by 1e-5 so that a constant row enters as 0. It tests `scale == 0` exactly,
  and the float32 mean of a constant row often misses its value by one rounding step. Such a row then entered the
  model as about +-0.88 or 0, with the sign set by rounding, by device and by level (PLAN.md 14.5, `C2:CB:95-122`).
  On the smoke slice, before the guard, this moved `mv-lit` P1 targets by up to 5.17 z between CPU and MPS
  (PLAN.md 14.5, `SP/switch/constcov.py`).
- Our adapter passes every row that is constant over its context as exact zeros and adds a constant target's value
  back to its quantiles (D128). This is our fix of a numerical edge case of the model. Univariate forecasts change
  only in the constant row itself. Multivariate forecasts can change a lot: constant covariates are common in short,
  early-file P1 contexts, where the step setpoints and some actuator commands have not moved yet.
- On CPU, measured before the runs, the guard was far from a rounding-level change for the mv setups (PLAN.md 14.5,
  D129). The size that matters is on the MPS headline runs:

- **Univariate (`uni` rolling on calib, calib2 and test; `uni` cf-onset):** a rounding-level change. No quantile level
  moves by more than 6.6e-7 z and no band score by more than 1.4e-5 (`results/phase1/d128_effect.csv`, MPS rows).
  The `uni` run does not depend on the guard. `uni57`, whose six step tags are often constant, is not measured.
- **Multivariate rolling (`mv-lit`, `mv-acttgt`):** 201 of 3,945 test calls hold a constant row (85 of 1,698 calib;
  338 of 1,698 calib2, `mv-lit` only). All of them are P1 calls: only P1 targets are re-run (`d128_effect_channels.csv`). On
  `mv-lit` test the guard moves 0.022 % of all quantile values by more than 0.1 z and 0.0031 % by more than 1 z. The
  largest move is 65.4 z on `P1_PCV02Z` (test1, origin 480), 25.5 z on q05/q50/q95. The band score at the observed
  value moves by at most 3.44 (`P1_PCV02Z`) and by more than 1 on 3 of 1,341,300 test forecasts (`mv-acttgt`: 65.397
  z, 3.436, 3 of 1,617,450). On calib the band score moves by at most 0.214. The top-3 mean, the max and a percentile
  move by no more than their largest input, so no band-score calib threshold of these rolling runs moves by more than
  0.214 (the `mv-lit` band threshold on `mvlit34` is 9.442, `thresholds.csv`), and no aggregated test band score by
  more than 3.44. The crps and mae thresholds have no such bound: q50 moves by up to 0.411 z on calib, and single
  levels by up to 10.06 z (calib) and 33,275 z (`mv-lit` calib2). Whether any test alarm flips is not measured.
- **`mv-lit` cf-onset:** 8 of 150 calls hold a constant row; the band score moves by up to 6.32, and by more than 1
  on 6 of 41,956 forecasts.
- **Frozen on the base (`mv-lit`):** none of its 3 calls holds a constant row, so the frozen forecast is the
  unmodified model.

Full table and the channels in section 4.13.

- Experiment 2, and every FF run on an mv base, is therefore Chronos-2 with this input interpretation, not the
  unmodified model. The frozen and prepend forecasts are not: they passed no constant row, so the guard never acted
  on them (`d128_effect.csv`; `quantile_diagnostics.csv`, `const_rows` 0). Dual inherits the guard through its
  rolling side only. A no-guard run was not made (Q22). The guard's effect on the FF contexts is not measured (D129).

### 3.8 Quantile sorting (D119)

Nothing in Chronos-2 enforces monotone quantiles, and on HAI they often cross. The adapter sorts each 21-level
vector (monotone rearrangement). It is a no-op on monotone output, keeps the cache contract `q01 <= ... <= q99`, and
never increases the pinball loss. On a CPU sample of the 10 s `calib` contexts before the runs, 7.3 % (T = 150) to
21 % (T = 8,192) of (channel, h) forecasts had a crossing; sorting changed q05 in at most 0.83 % and q95 in at most
0.19 % of forecasts, so the band score is barely touched (PLAN.md 14.5, `SP/switch/crossings3.py`). The rates of
the full runs are in section 4.14.

### 3.9 H = 30 at 10 s: most of each interior is forecast from clean context

This is the main limit of the 10 s design. With H = 30 and stride 30, a forecast issued before onset covers most
attacks entirely.

- Only 232 of 934 attack steps (24.8 %) are scored by a forecast whose context already holds attack data
  (`attacks.csv`, sums of `post_onset_steps_10s` and `steps_10s`; PLAN.md 8).
- 33 of 50 attacks lie inside one window issued before onset; only 17 have any post-onset step (`attacks.csv`,
  `n_windows_10s`, `post_onset_steps_10s`).
- **406 of the 637 interior steps (N = 6) are forecast from clean pre-onset contexts** (PLAN.md 8 and 9,
  `SP/plan-scripts/critic_verify.py`; 637 = the sum of `steps_10s - 6` over the attacks in `attacks.csv`).
- So the 10 s onset/interior split mostly does not test contamination. A low interior coverage at 10 s says the
  model forgives the interior even from a clean context; it does not by itself show that attack data entered the
  context.
- The pre/post split is also confounded with h: interior steps from pre-onset origins have mean h = 19.5 (n = 406),
  those from post-onset origins mean h = 9.7 (n = 231) (PLAN.md 9). If bands widen with h, short-horizon steps get
  higher band scores for the same deviation. Hence the h-matched contrast and `cf-onset`.
- At 1 s with H = 30 (30 s), 7,698 of 8,947 attack seconds (86.0 %) come from post-onset contexts and 49 of 50
  attacks have post-onset steps (`attacks.csv`, `post_onset_steps_1s`, `n_windows_1s`). That is where the mechanism is
  visible at all. The 1 s block is not in this report (section 7); option B (10 s, H = 6, section 4.20) raises the
  post-onset share to 69.8 %.

### 3.10 Picks made on test results (D21)

- "Better of 1 and 2" (brief experiment 3): highest **test** PR-AUC of the band score, top-3 mean, on matched
  channels: `mv-lit` on `mvlit34` against `uni` scored on `mvlit34`. Ties go to ROC-AUC, exact ties to `uni`.
  `uni57` and `mv-acttgt` are never candidates (D40).
- "Best of 1-3": the base setup's `rolling`, `ff-interp-block`, `frozen` and `dual` (score `dual` for dual) on its
  full channel set, same rule. `ff-interp-block-max60-testinf` is not a candidate.
- **Both picks were made on test results** (`results/phase1/selection.csv`, column `note`). The picked setup's test
  numbers are therefore optimistic against the others (winner's curse).

### 3.11 Other brief-level readings

- "Strict time-based split" read as per-file roles (D8, Q3; section 2.2).
- Thresholds from `calib` = train1 days, a held-out slice of normal training data disjoint from `fit`; the choice of
  train1 used test-file values (section 6.3, item 1).
- The three dropped tags that vary in test only during or just after attacks (`P1_PCV02D` in 5 attacks, `P2_OnOff`
  and `P2_Emerg` in 9 turbine trips) are dropped as the brief says (constant in train). That removes the most trivial
  evidence for 14 attacks (`attacks.csv`, `stratum`: 5 `pcv02d` + 9 `trip`). A detector that kept them would get
  those attacks nearly for free (D36, Q12).
- HAICon 2020 scored HAI 21.03 with eTaPR (alpha 0.5, rho 0.1, pi 0.7, delta 180), not plain TaPR (CSET'21 §4.1.2;
  PLAN.md 9). We report plain TaPR as the brief says; eTaPR is not added (Q6).
- Optional smoothing exists (`score.smooth`) and is off in every reported run.

---

## 4. Results

All results are Chronos-2 (`amazon/chronos-2` @ `29ec376`), MPS, 10 s, unless a row says otherwise. Run keys are
`hai2103-10s/chronos2-29ec376-mps/<setup>/<variant>`. Point-adjusted F1 appears only in columns marked "inflated".

### 4.0 What ran

`tsfm-ad all --optional 10s` ran on MPS from commit `27d81f2`. The first forecast split started at 13:15:51 and the last one ended at 20:49:15 (`results/phase1/runs.csv`). The log ends with `all: every step passed`, `all done in 27226.4 s` and exit 0 (`cache/logs/all_mps_10s_20261020.log`). `cache/logs/all_failures.csv` holds only its header, so no step failed.

One row per run and split, all on 2026-10-20 (`results/phase1/runs.csv`). Chronos-2 run keys are `hai2103-10s/chronos2-29ec376-mps/<setup>/<variant>`, baseline keys `hai2103-10s/baseline/<name>/rolling`. The baselines run on CPU and call no model. `ok` = the step passed in the log. Wall-clock includes any system sleep (D80).

| run (setup / variant) | hash8 | split | device | started | finished | wallclock_s | n_calls | status |
|---|---|---|---|---|---|---|---|---|
| `uni / rolling` | `47703ec2` | calib | mps | 13:15:51 | 13:28:51 | 779.7 | 566 | ok |
| `uni / rolling` | `47703ec2` | calib2 | mps | 13:28:51 | 13:41:50 | 779.0 | 566 | ok |
| `uni / rolling` | `47703ec2` | test | mps | 13:41:50 | 14:12:47 | 1,857.8 | 1,315 | ok |
| `uni / cf-onset` | `6895546b` | test | mps | 14:12:52 | 14:14:04 | 71.6 | 50 | ok |
| `uni57 / rolling` | `98048bbf` | calib | mps | 14:14:09 | 14:28:23 | 854.1 | 566 | ok |
| `uni57 / rolling` | `98048bbf` | test | mps | 14:28:23 | 15:02:31 | 2,047.8 | 1,315 | ok |
| `mv-lit / rolling` | `c06bc843` | calib | mps | 15:02:41 | 15:14:47 | 726.5 | 1,698 | ok |
| `mv-lit / rolling` | `c06bc843` | calib2 | mps | 15:14:47 | 15:26:47 | 719.7 | 1,698 | ok |
| `mv-lit / rolling` | `c06bc843` | test | mps | 15:26:47 | 15:55:33 | 1,726.0 | 3,945 | ok |
| `mv-lit / cf-onset` | `225de558` | test | mps | 15:55:35 | 15:56:43 | 68.0 | 150 | ok |
| `mv-acttgt / rolling` | `7fc275e9` | calib | mps | 15:56:47 | 16:08:47 | 719.8 | 1,698 | ok |
| `mv-acttgt / rolling` | `7fc275e9` | test | mps | 16:08:47 | 16:37:32 | 1,725.2 | 3,945 | ok |
| `robustz / rolling` | `9433c30e` | calib | cpu | 16:49:55 | 16:49:55 | 0.2 | 0 | ok |
| `robustz / rolling` | `9433c30e` | test | cpu | 16:49:55 | 16:49:56 | 0.4 | 0 | ok |
| `lastvalue / rolling` | `d6ae24ee` | calib | cpu | 16:49:56 | 16:49:58 | 1.8 | 0 | ok |
| `lastvalue / rolling` | `d6ae24ee` | test | cpu | 16:49:58 | 16:49:58 | 0.2 | 0 | ok |
| `seasonal-refday / rolling` | `ebdf02d0` | calib | cpu | 16:49:58 | 16:49:58 | 0.1 | 0 | ok |
| `seasonal-refday / rolling` | `ebdf02d0` | test | cpu | 16:49:58 | 16:49:58 | 0.2 | 0 | ok |
| `mv-lit / frozen` | `401c71db` | ref | mps | 16:50:17 | 16:50:20 | 2.8 | 3 | ok |
| `mv-lit / ff-interp-block` | `93cc0822` | calib | mps | 16:50:28 | 17:02:28 | 720.3 | 1,698 | ok |
| `mv-lit / ff-interp-block` | `93cc0822` | test | mps | 17:02:28 | 17:31:16 | 1,727.1 | 3,945 | ok |
| `mv-lit / ff-interp-block-max60-testinf` | `e25a0539` | calib | mps | 17:31:21 | 17:43:21 | 720.2 | 1,698 | ok |
| `mv-lit / ff-interp-block-max60-testinf` | `e25a0539` | test | mps | 17:43:21 | 18:12:11 | 1,730.2 | 3,945 | ok |
| `mv-lit / prepend` | `d9b7cc2f` | calib | mps | 18:12:21 | 18:34:56 | 1,355.0 | 1,698 | ok |
| `mv-lit / prepend` | `d9b7cc2f` | test | mps | 18:34:56 | 19:27:23 | 3,147.6 | 3,945 | ok |
| `mv-lit / ff-interp-block-max30` | `3878b398` | calib | mps | 19:27:29 | 19:39:30 | 720.8 | 1,698 | ok |
| `mv-lit / ff-interp-block-max30` | `3878b398` | test | mps | 19:39:30 | 20:08:20 | 1,729.6 | 3,945 | ok |
| `mv-lit / ff-interp-block-max120` | `77efffc9` | calib | mps | 20:08:27 | 20:20:28 | 720.2 | 1,698 | ok |
| `mv-lit / ff-interp-block-max120` | `77efffc9` | test | mps | 20:20:28 | 20:49:15 | 1,727.5 | 3,945 | ok |

`n_calls`: one call per origin for `uni` and `uni57`, three (P1, P2, P3) for the mv setups. cf-onset makes one call per attack (50 for `uni`, 3 x 50 for `mv-lit`). Frozen makes one call per group from the reference day (3).

Steps without a forecast split of their own (no `runs.csv` row; durations from the log):

| step | log duration (s) | note |
|---|---|---|
| exp 3c `mv-lit / dual` (`0201a687`) | 1.1 | no inference; scored from the rolling and frozen caches |
| D128 effect (D129): `uni / rolling`; `uni / cf-onset` | 83.2; 0.6 | |
| D128 effect: `mv-lit / rolling`; `mv-lit / cf-onset` | 559.0; 2.5 | |
| D128 effect: `mv-acttgt / rolling` | 94.7 | |
| D128 effect: `mv-lit / frozen` | 0.2 | the log reports 0 calls with a constant row |
| `select --stage base`; `select --stage best` (D21, picked on test results) | 0.0; 0.1 | |
| smoke 10 s and 1 s with their prepare steps, MPS check | 5.8 in all | every smoke forecast was already in the smoke cache (the log prints `0 of 1` or `0 of 2 files to run` for all 55) |
| `latency.csv` and `size_latency.csv`; plot 10 s | 0.3; 2.3 | |

Not run: experiment 4 (the log prints `deferred until Timestral permission (D123); not run`) and the whole 1 s block, including the 10 s `uni` FF reference (D134, section 4.16). After the run, `tsfm-ad diagnostics` wrote `results/phase1/quantile_diagnostics.csv` from the cache over the same run list (commit `d0d6ee9`, reporting code, D133). It made no forecast call.

**Stopped CPU run, not part of any headline.** `runs.csv` also holds two rows of the CPU `all` that was stopped at about 13:10 (section 2.7):

| run_key | hash8 | split | device | started | finished | wallclock_s | n_calls | status |
|---|---|---|---|---|---|---|---|---|
| `chronos2-29ec376-cpu/uni/rolling` | `46eadd6b` | calib | cpu | 12:23:41 | 12:45:48 | 1,326.8 | 566 | stopped run; not a headline |
| `chronos2-29ec376-cpu/uni/rolling` | `46eadd6b` | calib2 | cpu | 12:45:48 | 13:07:43 | 1,315.8 | 566 | stopped run; not a headline |

That run also forecast test1 (`cache/hai2103-10s/chronos2-29ec376-cpu/uni/rolling@46eadd6b/test/test1.parquet`), but it was stopped before its test split ended, so `runs.csv` has no CPU test row. No number in section 4 comes from it.

### 4.1 Experiment 1: univariate zero-shot

From `results/phase1/metrics.csv`: model `chronos2-29ec376-mps`, variant `rolling`, calib_source `calib`; hash8 `47703ec2` (`uni`) and `98048bbf` (`uni57`). The headline score is in bold (band, top-3 mean). Chance: ROC-AUC 0.5, PR-AUC 0.024.

| model | setup | channel_set | score | agg | calib_source | roc_auc | pr_auc | precision | recall | f1 | alarm_steps | fa_per_hour | pa_f1_inflated (inflated, not a headline) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chronos2-29ec376-mps | uni | uni51 | **band** | topk | calib | 0.894 | 0.401 | 0.641 | 0.251 | 0.360 | 365 | 1.224 | 0.746 |
| chronos2-29ec376-mps | uni | uni51 | band | max | calib | 0.891 | 0.384 | 0.658 | 0.254 | 0.366 | 360 | 1.150 | 0.767 |
| chronos2-29ec376-mps | uni | uni51 | crps | topk | calib | 0.872 | 0.421 | 0.466 | 0.565 | 0.511 | 1,133 | 5.655 | 0.730 |
| chronos2-29ec376-mps | uni | uni51 | crps | max | calib | 0.861 | 0.377 | 0.453 | 0.575 | 0.507 | 1,185 | 6.057 | 0.717 |
| chronos2-29ec376-mps | uni | uni51 | mae | topk | calib | 0.858 | 0.430 | 0.521 | 0.570 | 0.544 | 1,022 | 4.580 | 0.752 |
| chronos2-29ec376-mps | uni | uni51 | mae | max | calib | 0.853 | 0.407 | 0.508 | 0.577 | 0.540 | 1,061 | 4.879 | 0.742 |
| chronos2-29ec376-mps | uni | uni51 | mae | mean | calib | 0.861 | 0.429 | 0.536 | 0.516 | 0.526 | 899 | 3.898 | 0.725 |
| chronos2-29ec376-mps | uni57 | uni57 | **band** | topk | calib | 0.892 | 0.340 | 0.604 | 0.181 | 0.278 | 280 | 1.037 | 0.670 |
| chronos2-29ec376-mps | uni57 | uni57 | band | max | calib | 0.889 | 0.332 | 0.531 | 0.184 | 0.273 | 324 | 1.421 | 0.602 |
| chronos2-29ec376-mps | uni57 | uni57 | crps | topk | calib | 0.872 | 0.419 | 0.467 | 0.566 | 0.512 | 1,133 | 5.645 | 0.730 |
| chronos2-29ec376-mps | uni57 | uni57 | crps | max | calib | 0.861 | 0.376 | 0.450 | 0.575 | 0.505 | 1,193 | 6.131 | 0.715 |
| chronos2-29ec376-mps | uni57 | uni57 | mae | topk | calib | 0.858 | 0.429 | 0.521 | 0.570 | 0.544 | 1,021 | 4.571 | 0.752 |
| chronos2-29ec376-mps | uni57 | uni57 | mae | max | calib | 0.853 | 0.407 | 0.508 | 0.577 | 0.540 | 1,061 | 4.879 | 0.742 |
| chronos2-29ec376-mps | uni57 | uni57 | mae | mean | calib | 0.861 | 0.424 | 0.545 | 0.496 | 0.519 | 850 | 3.617 | 0.729 |

- **Headline (`uni` on `uni51`):** ROC-AUC 0.894 and PR-AUC 0.401, well above chance (0.5, 0.024). At the calib threshold it raises 365 alarm steps with precision 0.641 and recall 0.251, so three in four attack steps get no alarm. It alarms on 1.224 normal steps per hour. That is below the 1.8 per hour the 99.5th percentile would give if the test data behaved like calib (section 2.5).
- **crps and mae alarm far more often.** On `uni51` they reach recall 0.516-0.577 and F1 0.507-0.544, at 3.898-6.057 false-alarm steps per hour, 3 to 5 times the headline rate. `mae` top-3 has the highest PR-AUC in the table (0.430) but a lower ROC-AUC (0.858). The headline score was fixed before any result (section 6.9); switching now would be a pick on test results. crps carries the outer-quantile caveat of section 4.15.
- **`uni57` (the brief-literal 57 channels) is worse on the band score:** PR-AUC 0.340 against 0.401 and recall 0.181 against 0.251, at about the same ROC-AUC (0.892 against 0.894). Its calib threshold is 19.512, against 11.589 for `uni51` (`thresholds.csv`, band, top-3). D39 expected this from the six flat step tags (section 3.3), but no results file shows which channels set the threshold. crps and mae barely change.

From `results/phase1/tapr.csv`: the same two runs, score band, agg top-3. Parameters as in section 2.6.

| model | setup | channel_set | config | alpha | theta_r | theta_p | delta_s | delta_steps | TaP | TaP_d | TaP_p | TaR | TaR_d | TaR_p | F1 | n_pred_ranges |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chronos2-29ec376-mps | uni | uni51 | headline | 0.5 | 0.5 | 0.5 | 180 | 18 | 0.735 | 0.736 | 0.735 | 0.273 | 0.240 | 0.306 | 0.398 | 53 |
| chronos2-29ec376-mps | uni | uni51 | strict | 0.5 | 0.5 | 0.5 | 0 | 0 | 0.687 | 0.698 | 0.675 | 0.252 | 0.240 | 0.265 | 0.369 | 53 |
| chronos2-29ec376-mps | uni | uni51 | haicon_like | 0.5 | 0.1 | 0.7 | 180 | 18 | 0.735 | 0.736 | 0.735 | 0.463 | 0.620 | 0.306 | 0.568 | 53 |
| chronos2-29ec376-mps | uni57 | uni57 | headline | 0.5 | 0.5 | 0.5 | 180 | 18 | 0.768 | 0.769 | 0.768 | 0.208 | 0.180 | 0.236 | 0.328 | 39 |
| chronos2-29ec376-mps | uni57 | uni57 | strict | 0.5 | 0.5 | 0.5 | 0 | 0 | 0.727 | 0.744 | 0.711 | 0.190 | 0.180 | 0.199 | 0.301 | 39 |
| chronos2-29ec376-mps | uni57 | uni57 | haicon_like | 0.5 | 0.1 | 0.7 | 180 | 18 | 0.768 | 0.769 | 0.768 | 0.358 | 0.480 | 0.236 | 0.489 | 39 |

- **Headline config, `uni51`:** TaP 0.735, TaR 0.273, TaPR F1 0.398. TaR_d 0.240 means TaPR counts 12 of the 50 attacks as detected (overlap above theta 0.5). TaP_d 0.736 means 39 of the 53 predicted ranges count as correct.
- **`haicon_like`** lowers theta_r to 0.1. TaR_d rises to 0.620 (31 of 50 attacks, the same count as the attacks with any alarm, `n_detected` in `segments_summary.csv`) and F1 to 0.568. It is plain TaPR with HAICon thresholds: not eTaPR, and not comparable to the HAICon leaderboard.
- **`strict`** (no post-attack credit) lowers TaP from 0.735 to 0.687 and F1 from 0.398 to 0.369. Part of the precision comes from alarms in the 180 s after an attack.
- **`uni57`** makes fewer predicted ranges (39) and detects fewer attacks (TaR_d 0.180, 9 of 50). Its TaP is higher (0.768), its headline F1 lower (0.328).

The `calib2` threshold (two train2 days, which overlap `fit`, D51) against the headline `calib` threshold, band score, top-3 (`metrics.csv`, `thresholds.csv`). The AUCs do not depend on the threshold and are not repeated.

| setup | channel_set | calib_source | threshold | n_calib_steps | precision | recall | f1 | alarm_steps | fa_per_hour |
|---|---|---|---|---|---|---|---|---|---|
| uni | uni51 | calib | 11.589 | 16,980 | 0.641 | 0.251 | 0.360 | 365 | 1.224 |
| uni | uni51 | calib2 | 8.719 | 16,980 | 0.609 | 0.278 | 0.382 | 427 | 1.561 |

The calib2 threshold is lower (8.719 against 11.589). It gives 62 more alarm steps, recall 0.278 against 0.251 and F1 0.382 against 0.360, at 1.561 false-alarm steps per hour against 1.224. This is a sensitivity check only; calib2 is never used for a pick.

### 4.2 Experiment 2: multivariate per process, and the comparison with experiment 1

The matched comparison decides (D21). The unmatched rows mix the forecasting mode with the channel choice
(`mvlit34` has neither the actuator commands nor P4) and are shown only for context. Every mv number carries the
D128 caveat (sections 3.7, 4.13).

Band score, top-3 mean, calib threshold. Metrics come from `metrics.csv`, TaPR F1 from `tapr.csv` (config `headline`), and coverages and `n_detected` from `segments_summary.csv` (stratum all, ff_group all, N = 6). `p_normal` is the run's alarm rate on normal scored test steps; alarms that ignored the label would cover about that share of any segment. `n_detected` = attacks with at least one alarm inside the attack. Chance: ROC-AUC 0.5, PR-AUC 0.024.

| comparison | model | setup | channel_set | roc_auc | pr_auc | TaPR F1 (headline) | fa_per_hour | p_normal | onset_cov_mean | interior_cov_mean | offset_cov_mean | n_detected / n_attacks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| matched (decides the base) | chronos2-29ec376-mps | uni | mvlit34 | 0.880 | 0.397 | 0.393 | 1.009 | 0.0028 | 0.247 | 0.281 | 0.080 | 30 / 50 |
| matched (decides the base) | chronos2-29ec376-mps | mv-lit | mvlit34 | 0.862 | 0.397 | 0.400 | 1.112 | 0.0031 | 0.263 | 0.295 | 0.080 | 30 / 50 |
| matched, secondary | chronos2-29ec376-mps | uni | mvacttgt41 | 0.889 | 0.388 | 0.393 | 1.215 | 0.0034 | 0.267 | 0.286 | 0.080 | 31 / 50 |
| matched, secondary | chronos2-29ec376-mps | mv-acttgt | mvacttgt41 | 0.874 | 0.394 | 0.413 | 1.206 | 0.0033 | 0.283 | 0.296 | 0.087 | 31 / 50 |
| unmatched, context only | chronos2-29ec376-mps | uni | uni51 | 0.894 | 0.401 | 0.398 | 1.224 | 0.0034 | 0.280 | 0.290 | 0.083 | 31 / 50 |

- **Matched, `mvlit34` (decides the base): a tie.** PR-AUC is 0.397 for both (0.39707 for `mv-lit`, 0.39695 for `uni`, `selection.csv`). `uni` has the higher ROC-AUC (0.880 against 0.862). `mv-lit` is slightly ahead on TaPR F1 (0.400 against 0.393), onset coverage (0.263 against 0.247) and interior coverage (0.295 against 0.281), and it alarms slightly more on normal data (1.112 against 1.009 false-alarm steps per hour). Both detect 30 of 50 attacks. Joint forecasting per process does not clearly beat independent forecasting on the same channels. With 50 attacks, gaps this small may be noise (section 6.2).
- **Matched, `mvacttgt41` (secondary): the same mixed picture.** `mv-acttgt` has the higher PR-AUC (0.394 against 0.388) and TaPR F1 (0.413 against 0.393). `uni` has the higher ROC-AUC (0.889 against 0.874), at nearly the same false-alarm rate (1.215 against 1.206). `mv-acttgt` is never a base (D40).
- **Unmatched.** `uni` on its full set `uni51` has the highest ROC-AUC (0.894) and PR-AUC (0.401) in the table; `uni51` adds the 7 actuator commands and the 10 P4 channels to `mvlit34`. It was not a candidate (D21, D40). `mvlit34` is `mv-lit`'s own full set, so its unmatched row is the matched `mv-lit` row above and is not repeated.
- In every row, interior coverage is at least as high as onset coverage (0.281-0.296 against 0.247-0.283), and offset coverage is low (0.080-0.087). Section 4.4 reads this against section 3.9.

The same check for `mv-lit` rolling on `mvlit34`, band score, top-3 (`metrics.csv`, `thresholds.csv`).

| setup | channel_set | calib_source | threshold | n_calib_steps | precision | recall | f1 | alarm_steps | fa_per_hour |
|---|---|---|---|---|---|---|---|---|---|
| mv-lit | mvlit34 | calib | 9.442 | 16,980 | 0.657 | 0.244 | 0.356 | 347 | 1.112 |
| mv-lit | mvlit34 | calib2 | 7.584 | 16,980 | 0.613 | 0.283 | 0.387 | 431 | 1.561 |

The direction is the same as for `uni`. calib2 gives a lower threshold (7.584 against 9.442), 84 more alarm steps and F1 0.387 against 0.356, at 1.561 false-alarm steps per hour against 1.112. So for both the experiment 1 and the experiment 2 headline runs, the calib threshold is the more conservative of the two. calib2 is never used for a pick.

### 4.3 Base pick: "better of 1 and 2" (picked on test results)

From `results/phase1/selection.csv`, stage `base`, decided 2026-10-20 16:50:17. The rule (column `rule`): `uni` against `mv-lit` rolling on `mvlit34`, highest test PR-AUC (band, top-3), ties broken by ROC-AUC, exact ties keep `uni`. PR-AUC is shown to 5 decimals because the pick turns on the fourth.

| stage | candidate_run_key | channel_set | score | agg | pr_auc (5 decimals) | roc_auc | rank | selected | note |
|---|---|---|---|---|---|---|---|---|---|
| base | `hai2103-10s/chronos2-29ec376-mps/uni/rolling@47703ec2` | mvlit34 | band | topk | 0.39695 | 0.880 | 2 | false | picked on test results |
| base | `hai2103-10s/chronos2-29ec376-mps/mv-lit/rolling@c06bc843` | mvlit34 | band | topk | 0.39707 | 0.862 | 1 | true | picked on test results |
| base | `hai2103-10s/chronos2-29ec376-mps/uni/rolling@47703ec2` | uni51 | band | topk | 0.40097 | 0.894 | | false | reported only, not a candidate (D21, D40); picked on test results |
| base | `hai2103-10s/chronos2-29ec376-mps/mv-acttgt/rolling@7fc275e9` | mvacttgt41 | band | topk | 0.39405 | 0.874 | | false | reported only, not a candidate (D21, D40); picked on test results |
| base | `hai2103-10s/chronos2-29ec376-mps/uni/rolling@47703ec2` | mvacttgt41 | band | topk | 0.38779 | 0.889 | | false | reported only, not a candidate (D21, D40); picked on test results |

**The base is `mv-lit`, picked on test results.** It won by 0.00012 of test PR-AUC (0.39707 against 0.39695). At three decimals the two tie at 0.397, and the ROC-AUC tie-break would then have picked `uni` (0.880 against 0.862). No confidence interval was computed (section 6.2). With 50 attacks a gap this small can decide the pick (section 6.4), and here the fourth decimal did. Every experiment 3 run, the optional prepend and FF max30/max120 runs, and the figures use `mv-lit` as the base (`runs.csv`; section 4.12). The three rows marked "reported only" were never candidates.

### 4.4 Boundary vs interior (the key result)

Read with section 3.9: at 10 s, 406 of 637 interior steps are forecast from clean context.

Source: `results/phase1/segments_summary.csv`, rows N = 6, stratum all, ff_group all, agg topk, score band (dual for dual), model `chronos2-29ec376-mps` or `baseline`. Each Chronos-2 method is on its own full set. The baselines are on `mvlit34` (the base's set) and `uni51`. Rates are "any alarm in the segment" over 50 attacks (onset, offset), 47 (interior; A203, A211, A508 are empty) and 37 (`interior_eq`). Chance = the mean over attacks of `1 - (1 - p_normal)^n`. The reference for coverage is `p_normal`. `cov_pre_origin_mean` / `cov_post_origin_mean` are means over the attacks that have such steps (post: 17 attacks). `latency_common_median_s` is taken over the attacks that every method on the same channel set detects (D94), so it compares rows of one channel set only. On `mvlit34` that common set is 6 attacks, mainly because dual detects only 15 and robustz 17.

| method | setup | channel_set | n_attacks | p_normal | onset_cov_mean | interior_cov_mean | interior_eq_cov_mean | offset_cov_mean | onset_rate / chance | interior_rate / chance | interior_eq_rate / chance | offset_rate / chance | cov_pre_origin_mean / cov_post_origin_mean | latency_common_median_s (n_common) | latency_censored_median_s | n_detected |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| uni rolling | uni | uni51 | 50 | 0.003 | 0.280 | 0.290 | 0.338 | 0.083 | 0.520 / 0.020 | 0.553 / 0.045 | 0.486 / 0.020 | 0.140 / 0.020 | 0.334 / 0.020 | 30 (22) | 40 | 31 |
| uni57 rolling | uni57 | uni57 | 50 | 0.003 | 0.190 | 0.234 | 0.261 | 0.067 | 0.420 / 0.017 | 0.447 / 0.038 | 0.378 / 0.017 | 0.120 / 0.017 | 0.249 / 0.000 | 40 (14) | 85 | 26 |
| **mv-lit rolling (base; also best of 1-3; both picked on test results)** | mv-lit | mvlit34 | 50 | 0.003 | 0.263 | 0.295 | 0.342 | 0.080 | 0.500 / 0.018 | 0.532 / 0.041 | 0.459 / 0.018 | 0.120 / 0.018 | 0.321 / 0.000 | 50 (6) | 50 | 30 |
| mv-acttgt rolling | mv-acttgt | mvacttgt41 | 50 | 0.003 | 0.283 | 0.296 | 0.342 | 0.087 | 0.520 / 0.020 | 0.532 / 0.044 | 0.459 / 0.020 | 0.140 / 0.020 | 0.332 / 0.020 | 30 (17) | 40 | 31 |
| ff-interp-block (INTERPRETATION) | mv-lit | mvlit34 | 50 | 0.324 | 0.527 | 0.574 | 0.586 | 0.427 | 0.720 / 0.900 | 0.809 / 0.910 | 0.730 / 0.904 | 0.520 / 0.904 | 0.547 / 0.521 | 40 (6) | 20 | 42 |
| ff-interp-block-max60-testinf (INTERPRETATION, test-informed) | mv-lit | mvlit34 | 50 | 0.101 | 0.217 | 0.258 | 0.239 | 0.090 | 0.420 / 0.469 | 0.426 / 0.660 | 0.324 / 0.473 | 0.160 / 0.473 | 0.258 / 0.113 | 50 (6) | 85 | 27 |
| frozen (INTERPRETATION) | mv-lit | mvlit34 | 50 | 0.011 | 0.147 | 0.258 | 0.275 | 0.087 | 0.320 / 0.062 | 0.489 / 0.133 | 0.378 / 0.063 | 0.200 / 0.063 | 0.180 / 0.265 | 55 (6) | 120 | 25 |
| dual (INTERPRETATION; dual score) | mv-lit | mvlit34 | 50 | 0.025 | 0.063 | 0.091 | 0.117 | 0.117 | 0.120 / 0.140 | 0.298 / 0.274 | 0.243 / 0.142 | 0.160 / 0.142 | 0.046 / 0.301 | 145 (6) | 175 | 15 |
| robustz | robustz | mvlit34 | 50 | 0.008 | 0.120 | 0.234 | 0.207 | 0.103 | 0.240 / 0.047 | 0.362 / 0.103 | 0.270 / 0.048 | 0.160 / 0.048 | 0.186 / 0.133 | 50 (6) | 185 | 17 |
| lastvalue | lastvalue | mvlit34 | 50 | 0.007 | 0.230 | 0.407 | 0.324 | 0.260 | 0.480 / 0.042 | 0.660 / 0.092 | 0.541 / 0.043 | 0.320 / 0.043 | 0.289 / 0.421 | 55 (6) | 60 | 33 |
| seasonal-refday | seasonal-refday | mvlit34 | 50 | 0.018 | 0.473 | 0.510 | 0.527 | 0.213 | 0.700 / 0.102 | 0.766 / 0.207 | 0.703 / 0.103 | 0.380 / 0.103 | 0.472 / 0.444 | 20 (6) | 25 | 38 |
| robustz | robustz | uni51 | 50 | 0.008 | 0.167 | 0.264 | 0.266 | 0.107 | 0.340 / 0.048 | 0.447 / 0.104 | 0.378 / 0.049 | 0.160 / 0.049 | 0.235 / 0.220 | 40 (22) | 135 | 23 |
| lastvalue | lastvalue | uni51 | 50 | 0.008 | 0.277 | 0.409 | 0.342 | 0.247 | 0.560 / 0.045 | 0.638 / 0.098 | 0.514 / 0.046 | 0.320 / 0.046 | 0.314 / 0.429 | 30 (22) | 40 | 36 |
| seasonal-refday | seasonal-refday | uni51 | 50 | 0.014 | 0.463 | 0.504 | 0.532 | 0.200 | 0.700 / 0.082 | 0.766 / 0.171 | 0.730 / 0.083 | 0.380 / 0.083 | 0.465 / 0.450 | 20 (22) | 25 | 39 |
| prepend (optional) | mv-lit | mvlit34 | 50 | 0.003 | 0.267 | 0.274 | 0.320 | 0.053 | 0.500 / 0.015 | 0.553 / 0.033 | 0.432 / 0.015 | 0.100 / 0.015 | 0.306 / 0.020 | 50 (6) | 50 | 31 |
| ff-interp-block-max30 (optional, INTERPRETATION) | mv-lit | mvlit34 | 50 | 0.059 | 0.200 | 0.278 | 0.279 | 0.150 | 0.360 / 0.303 | 0.532 / 0.499 | 0.432 / 0.306 | 0.200 / 0.306 | 0.258 / 0.163 | 60 (6) | 80 | 29 |
| ff-interp-block-max120 (optional, INTERPRETATION) | mv-lit | mvlit34 | 50 | 0.271 | 0.260 | 0.346 | 0.320 | 0.273 | 0.360 / 0.845 | 0.532 / 0.883 | 0.432 / 0.850 | 0.340 / 0.850 | 0.307 / 0.172 | 45 (6) | 100 | 26 |

Reading (all numbers from the table above):

- **Base (mv-lit rolling)**: coverage is 0.263 at onset, 0.295 in the interior, 0.342 on `interior_eq` and 0.080 at the offset, at `p_normal` 0.003. Detection rates are far above chance: onset 0.500 vs 0.018, interior 0.532 vs 0.041. It detects 30 of 50 attacks.
- **No boundary advantage at N = 6.** In all four Chronos-2 rolling setups, interior coverage is equal to or higher than onset coverage (uni 0.280 / 0.290, mv-lit 0.263 / 0.295, mv-acttgt 0.283 / 0.296, uni57 0.190 / 0.234). The offset is the weakest segment (0.067 to 0.087). The hypothesis predicts high coverage at both boundaries and low coverage inside. The segment means do not show that shape. The strata and N tables below show why: the interior mean is carried by the 14 trip and pcv02d attacks, and the order of onset and interior flips with N.
- **Split by origin side.** Steps whose context holds attack data get an attack-mean coverage of 0.000 (mv-lit, uni57) or 0.020 (uni, mv-acttgt), over 17 attacks. Clean-context steps of the same runs get 0.321 to 0.334 (uni57: 0.249). The mechanism tables below look at this split.
- **FF**: `ff-interp-block` alarms on 0.324 of normal test steps. Its detection rates (onset 0.720, interior 0.809) are below their chance levels (0.900, 0.910), so its high coverage is not evidence of detection. `-max60-testinf` and `-max120` are also below chance. `-max30` is just above it (onset 0.360 vs 0.303, interior 0.532 vs 0.499). FF is credited only on `triggered_in_attack` attacks (section 4.6).
- **Frozen** detects above chance (onset 0.320 vs 0.062, interior 0.489 vs 0.133) at `p_normal` 0.011, with lower coverage than the base. **Dual** is near chance: onset 0.120 vs 0.140 (below), interior 0.298 vs 0.274. Only on `interior_eq` is it clearly above chance (0.243 vs 0.142, 37 attacks).
- **Baselines**: seasonal-refday has the highest coverage of the rows with `p_normal` below 0.05 (onset 0.473, interior 0.510 on `mvlit34`), at `p_normal` 0.018, about 6 times the base's rate. Only `ff-interp-block` covers more (0.527, 0.574), at `p_normal` 0.324. Rows at different `p_normal` are not like for like. The comparison is in section 4.9.
- **Prepend** stays within 0.03 of in-file rolling on onset and interior (0.267, 0.274) and is lower at the offset (0.053 vs 0.080).

**Mechanism: the h-matched origin contrast.** The headline contrast is post- vs pre-onset interior coverage within
the same h bucket.

Base rolling run by h bucket and time-since-onset bucket. These are the rows of `results/phase1/segments_by_h.csv` for mv-lit rolling (hash `c06bc843`), `mvlit34`, band, topk, N 6, onset and interior. A bucket combination with no steps is not in the file.

| method | segment | origin_side | h_bucket | tso_bucket | n_steps | n_attacks | coverage | mean_score |
|---|---|---|---|---|---|---|---|---|
| mv-lit rolling (base) | onset | pre | 1-10 | 0-59 | 128 | 26 | 0.273 | 8.56 |
| mv-lit rolling (base) | onset | post | 1-10 | 0-59 | 1 | 1 | 0.000 | 0.07 |
| mv-lit rolling (base) | onset | pre | 11-20 | 0-59 | 86 | 31 | 0.116 | 13.91 |
| mv-lit rolling (base) | onset | pre | 21-30 | 0-59 | 82 | 18 | 0.415 | 19.73 |
| mv-lit rolling (base) | interior | pre | 1-10 | 60-119 | 44 | 12 | 0.545 | 26.80 |
| mv-lit rolling (base) | interior | post | 1-10 | 60-119 | 25 | 5 | 0.000 | 0.16 |
| mv-lit rolling (base) | interior | post | 1-10 | 120-239 | 91 | 15 | 0.000 | 0.41 |
| mv-lit rolling (base) | interior | post | 1-10 | 240+ | 27 | 7 | 0.000 | 0.72 |
| mv-lit rolling (base) | interior | pre | 11-20 | 60-119 | 102 | 29 | 0.353 | 123.67 |
| mv-lit rolling (base) | interior | pre | 11-20 | 120-239 | 72 | 18 | 0.292 | 72.99 |
| mv-lit rolling (base) | interior | post | 11-20 | 120-239 | 37 | 8 | 0.000 | 0.57 |
| mv-lit rolling (base) | interior | post | 11-20 | 240+ | 30 | 8 | 0.000 | 0.51 |
| mv-lit rolling (base) | interior | pre | 21-30 | 60-119 | 81 | 19 | 0.444 | 50.24 |
| mv-lit rolling (base) | interior | pre | 21-30 | 120-239 | 93 | 19 | 0.301 | 140.82 |
| mv-lit rolling (base) | interior | pre | 21-30 | 240+ | 14 | 6 | 0.286 | 62.25 |
| mv-lit rolling (base) | interior | post | 21-30 | 240+ | 21 | 3 | 0.000 | 0.42 |

Mean band scores are dominated by a few very large values (the band score is unbounded), so coverage is the metric to read.

Interior, pooled over the tso buckets, for every method of the table above: coverage (n_steps). Same file and filters (N 6, topk, band or dual, each method's set). Pooled coverage = the sum of coverage x n_steps over the tso cells divided by the sum of n_steps, i.e. alarmed steps / steps. `n_attacks` is not pooled, because one attack can sit in several cells. It is given per cell in the CSV; for the base, the post-onset interior cells hold 3 to 15 attacks each.

| method | channel_set | h 1-10 pre | h 1-10 post | h 11-20 pre | h 11-20 post | h 21-30 pre | h 21-30 post | all h pre | all h post |
|---|---|---|---|---|---|---|---|---|---|
| uni rolling | uni51 | 0.500 (44) | 0.007 (143) | 0.322 (174) | 0.000 (67) | 0.378 (188) | 0.000 (21) | 0.367 (406) | 0.004 (231) |
| uni57 rolling | uni57 | 0.205 (44) | 0.000 (143) | 0.247 (174) | 0.000 (67) | 0.319 (188) | 0.000 (21) | 0.276 (406) | 0.000 (231) |
| **mv-lit rolling (base; also best of 1-3; both picked on test results)** | mvlit34 | 0.545 (44) | 0.000 (143) | 0.328 (174) | 0.000 (67) | 0.362 (188) | 0.000 (21) | 0.367 (406) | 0.000 (231) |
| mv-acttgt rolling | mvacttgt41 | 0.568 (44) | 0.007 (143) | 0.328 (174) | 0.000 (67) | 0.356 (188) | 0.000 (21) | 0.367 (406) | 0.004 (231) |
| ff-interp-block (INTERPRETATION) | mvlit34 | 0.591 (44) | 0.566 (143) | 0.489 (174) | 0.463 (67) | 0.601 (188) | 0.048 (21) | 0.552 (406) | 0.489 (231) |
| ff-interp-block-max60-testinf (INTERPRETATION, test-informed) | mvlit34 | 0.136 (44) | 0.147 (143) | 0.207 (174) | 0.000 (67) | 0.287 (188) | 0.000 (21) | 0.236 (406) | 0.091 (231) |
| frozen (INTERPRETATION) | mvlit34 | 0.318 (44) | 0.287 (143) | 0.207 (174) | 0.104 (67) | 0.213 (188) | 0.048 (21) | 0.222 (406) | 0.212 (231) |
| dual (INTERPRETATION; dual score) | mvlit34 | 0.182 (44) | 0.280 (143) | 0.103 (174) | 0.284 (67) | 0.011 (188) | 0.476 (21) | 0.069 (406) | 0.299 (231) |
| robustz | mvlit34 | 0.182 (44) | 0.084 (143) | 0.259 (174) | 0.000 (67) | 0.282 (188) | 0.000 (21) | 0.261 (406) | 0.052 (231) |
| lastvalue | mvlit34 | 0.477 (44) | 0.413 (143) | 0.328 (174) | 0.657 (67) | 0.346 (188) | 0.524 (21) | 0.352 (406) | 0.494 (231) |
| seasonal-refday | mvlit34 | 0.636 (44) | 0.448 (143) | 0.517 (174) | 0.403 (67) | 0.441 (188) | 0.524 (21) | 0.495 (406) | 0.442 (231) |
| robustz | uni51 | 0.182 (44) | 0.196 (143) | 0.259 (174) | 0.060 (67) | 0.335 (188) | 0.000 (21) | 0.286 (406) | 0.139 (231) |
| lastvalue | uni51 | 0.568 (44) | 0.434 (143) | 0.322 (174) | 0.657 (67) | 0.346 (188) | 0.524 (21) | 0.360 (406) | 0.506 (231) |
| seasonal-refday | uni51 | 0.636 (44) | 0.462 (143) | 0.489 (174) | 0.403 (67) | 0.452 (188) | 0.524 (21) | 0.488 (406) | 0.450 (231) |
| prepend (optional) | mvlit34 | 0.545 (44) | 0.007 (143) | 0.218 (174) | 0.000 (67) | 0.330 (188) | 0.000 (21) | 0.305 (406) | 0.004 (231) |
| ff-interp-block-max30 (optional, INTERPRETATION) | mvlit34 | 0.227 (44) | 0.182 (143) | 0.270 (174) | 0.134 (67) | 0.346 (188) | 0.000 (21) | 0.300 (406) | 0.152 (231) |
| ff-interp-block-max120 (optional, INTERPRETATION) | mvlit34 | 0.295 (44) | 0.189 (143) | 0.345 (174) | 0.060 (67) | 0.410 (188) | 0.000 (21) | 0.369 (406) | 0.134 (231) |

Onset, `interior_eq` and offset, pooled over h and tso the same way: coverage (n_steps).

| method | channel_set | onset pre | onset post | interior_eq pre | interior_eq post | offset pre | offset post |
|---|---|---|---|---|---|---|---|
| uni rolling | uni51 | 0.284 (296) | 0.000 (1) | 0.381 (197) | 0.000 (25) | 0.158 (152) | 0.007 (148) |
| uni57 rolling | uni57 | 0.193 (296) | 0.000 (1) | 0.294 (197) | 0.000 (25) | 0.132 (152) | 0.000 (148) |
| **mv-lit rolling (base; also best of 1-3; both picked on test results)** | mvlit34 | 0.267 (296) | 0.000 (1) | 0.386 (197) | 0.000 (25) | 0.158 (152) | 0.000 (148) |
| mv-acttgt rolling | mvacttgt41 | 0.287 (296) | 0.000 (1) | 0.386 (197) | 0.000 (25) | 0.171 (152) | 0.000 (148) |
| ff-interp-block (INTERPRETATION) | mvlit34 | 0.530 (296) | 1.000 (1) | 0.574 (197) | 0.680 (25) | 0.375 (152) | 0.480 (148) |
| ff-interp-block-max60-testinf (INTERPRETATION, test-informed) | mvlit34 | 0.220 (296) | 0.000 (1) | 0.239 (197) | 0.240 (25) | 0.105 (152) | 0.074 (148) |
| frozen (INTERPRETATION) | mvlit34 | 0.145 (296) | 1.000 (1) | 0.234 (197) | 0.600 (25) | 0.079 (152) | 0.095 (148) |
| dual (INTERPRETATION; dual score) | mvlit34 | 0.061 (296) | 1.000 (1) | 0.081 (197) | 0.400 (25) | 0.039 (152) | 0.196 (148) |
| robustz | mvlit34 | 0.122 (296) | 0.000 (1) | 0.234 (197) | 0.000 (25) | 0.132 (152) | 0.074 (148) |
| lastvalue | mvlit34 | 0.233 (296) | 0.000 (1) | 0.345 (197) | 0.160 (25) | 0.158 (152) | 0.365 (148) |
| seasonal-refday | mvlit34 | 0.476 (296) | 1.000 (1) | 0.503 (197) | 0.720 (25) | 0.197 (152) | 0.230 (148) |
| robustz | uni51 | 0.166 (296) | 1.000 (1) | 0.279 (197) | 0.160 (25) | 0.112 (152) | 0.101 (148) |
| lastvalue | uni51 | 0.280 (296) | 0.000 (1) | 0.365 (197) | 0.160 (25) | 0.158 (152) | 0.338 (148) |
| seasonal-refday | uni51 | 0.466 (296) | 1.000 (1) | 0.508 (197) | 0.720 (25) | 0.184 (152) | 0.216 (148) |
| prepend (optional) | mvlit34 | 0.270 (296) | 0.000 (1) | 0.360 (197) | 0.000 (25) | 0.099 (152) | 0.007 (148) |
| ff-interp-block-max30 (optional, INTERPRETATION) | mvlit34 | 0.203 (296) | 0.000 (1) | 0.310 (197) | 0.040 (25) | 0.151 (152) | 0.149 (148) |
| ff-interp-block-max120 (optional, INTERPRETATION) | mvlit34 | 0.264 (296) | 0.000 (1) | 0.350 (197) | 0.080 (25) | 0.217 (152) | 0.331 (148) |

Small cells: onset post is 1 step (1 attack), `interior_eq` post is 25 steps (5 attacks), and interior h 21-30 post is 21 steps (3 attacks). None of these can carry a conclusion alone.

Reading:

- **In the base run, no interior step whose context holds attack data alarms: 0 of 231, in every h bucket and every tso bucket.** The same run covers 0.367 of its 406 clean-context interior steps. uni and mv-acttgt alarm on 1 of 231 (0.004) and uni57 on none. Prepend, which only changes the warm-up, is the same (0.004).
- **h-matched** (base): h 1-10, 0.545 pre (44 steps, 12 attacks) vs 0.000 post (143). h 11-20, 0.328 vs 0.000 (67). h 21-30, 0.362 vs 0.000 (21 steps, 3 attacks). **h- and tso-matched**: h 1-10, tso 60-119 s, 0.545 pre (44 steps, 12 attacks) vs 0.000 post (25 steps, 5 attacks).
- The post-onset interior steps of the base have a mean band score of 0.46 (`cf_onset.csv`, `score_rolling_mean`, pooled as in the cf-onset table), against a calib threshold of 9.442 (`thresholds.csv`, mv-lit rolling, `mvlit34`, band, topk, calib). In the base table every post-onset interior cell has a mean of 0.16 to 0.72.
- **The post-onset steps are not undetectable.** Two methods never forecast from the test context, and they cover these steps about as well as the clean-context ones: seasonal-refday 0.442 post vs 0.495 pre, frozen 0.212 vs 0.222 (`mvlit34`). Lastvalue also starts from the last observed value, which is attack data here, but keeps a band fixed from `fit`. It covers more post-onset than pre-onset steps (0.494 vs 0.352). Robustz also drops (0.052 vs 0.261). Its median and MAD come from the hour before the origin (section 2.8), so on these steps they include attack data. So the drop is tied to forecasting from a context that holds the attack, both for Chronos-2 and for robustz. It is not plain persistence of the last value. Each method has its own `p_normal` (first table).
- **Dual rises after onset** (0.299 post vs 0.069 pre). Dual measures how far the rolling forecast is from the frozen one, so this rise is what a contaminated rolling forecast would produce.
- **Time since onset** (base, onset + interior pooled over h and origin side): coverage is 0.266 at 0-59 s (297 steps), 0.381 at 60-119 s (252), 0.167 at 120-239 s (293) and 0.043 at 240 s and later (92). On clean-context steps alone it is 0.267, 0.423, 0.297 and 0.286 (the last bucket has 14 steps). Most of the fall after 2 min comes from the forecast origins moving past the onset. At 120-239 s, clean-context steps get 0.297 against 0.167 for all steps. Clean-context coverage also falls from its 60-119 s peak (0.423).
- **Offset**: offset steps forecast from a context that holds the attack get 0.000 (148 steps) in the base, against 0.158 for pre-onset offset steps (152). A context that holds the attack does not produce an alarm at the attack's end.
- **FF**: on post-onset interior steps, `-max30` / `-max60-testinf` / `-max120` cover 0.152 / 0.091 / 0.134, where rolling covers 0.000, at `p_normal` 0.059 / 0.101 / 0.271. `ff-interp-block` covers 0.489 at `p_normal` 0.324. Only `-max30` and `ff-interp-block` cover these steps more often than they alarm on normal steps. `-max60-testinf` and `-max120` do not. FF is credited only on `triggered_in_attack` attacks (section 4.6).

Rows of `results/phase1/band_width_by_h.csv`: model `chronos2-29ec376-mps`, variant rolling, split calib. The band is `q95 - q05` in fit-z units, as the median and mean over the set's channels and all calib forecasts at that h.

| method | channel_set | split | h | band_median | band_mean |
|---|---|---|---|---|---|
| uni rolling | uni51 | calib | 1 | 0.373 | 0.821 |
| uni rolling | uni51 | calib | 10 | 1.313 | 1.495 |
| uni rolling | uni51 | calib | 20 | 1.497 | 1.602 |
| uni rolling | uni51 | calib | 30 | 1.615 | 1.667 |
| uni rolling | mvlit34 | calib | 1 | 0.264 | 0.833 |
| uni rolling | mvlit34 | calib | 10 | 0.826 | 1.292 |
| uni rolling | mvlit34 | calib | 20 | 1.049 | 1.407 |
| uni rolling | mvlit34 | calib | 30 | 1.201 | 1.468 |
| mv-lit rolling | mvlit34 | calib | 1 | 0.244 | 0.813 |
| mv-lit rolling | mvlit34 | calib | 10 | 0.813 | 1.315 |
| mv-lit rolling | mvlit34 | calib | 20 | 1.039 | 1.426 |
| mv-lit rolling | mvlit34 | calib | 30 | 1.151 | 1.463 |

Yes, the Chronos-2 band widens with h on HAI. From h = 1 to h = 30 the median grows 4.7 times for mv-lit on `mvlit34` (0.244 to 1.151) and 4.3 times for uni on `uni51` (0.373 to 1.615). The rise is almost monotone. In the full table the median dips slightly at h = 15 and 28 for uni on `uni51` and at h = 28 for mv-lit. At h = 1 the median band of mv-lit on `mvlit34` is only 2.4 times `eps` = 0.1 z (3.7 times for uni on `uni51`), so `eps` matters most at short horizons.

What this means for the mechanism test: post-onset interior steps have short horizons (mean h 9.7 vs 19.5 for pre-onset, section 3.9). They get narrower bands, and so higher band scores for the same deviation. The h confound therefore favours coverage on post-onset steps. It cannot explain the zero coverage there.

**Mechanism: the cf-onset counterfactual** (diagnostic only; it also differs in horizon and output-patch count,
section 3.6). On steps whose rolling origin is post-onset, a higher counterfactual score is conservative evidence of
contamination; a lower one is inconclusive. Pre-onset rows are a horizon-only control.

Pooled from `results/phase1/cf_onset.csv`: cf-onset runs `6895546b` (uni) and `225de558` (mv-lit), model `chronos2-29ec376-mps`, band, topk, rows with `n_steps` > 0. Scores and coverages are step-weighted means of the per-attack rows (the sum of mean x `n_steps` divided by the sum of `n_steps`). The `h_cf <= 30` columns are weighted by `n_hcf_le30`. Both coverages use the rolling run's calib threshold (D97). cf-onset is a diagnostic whose origin comes from the test labels (INTERPRETATION, section 3.6).

| setup | channel_set | segment | origin_side | n_attacks | n_steps | n_hcf_le30 | score_rolling_mean | score_cf_mean | score_rolling_mean_hcf_le30 | score_cf_mean_hcf_le30 | cov_rolling | cov_cf | attacks with cf mean > rolling mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| uni | uni51 | onset | pre | 50 | 296 | 296 | 13.85 | 15.68 | 13.85 | 15.68 | 0.284 | 0.318 | 36 of 50 |
| uni | uni51 | onset | post | 1 | 1 | 1 | 0.04 | 32.72 | 0.04 | 32.72 | 0.000 | 1.000 | 1 of 1 |
| uni | uni51 | interior | pre | 43 | 406 | 406 | 110.73 | 123.26 | 110.73 | 123.26 | 0.367 | 0.377 | 27 of 43 |
| uni | uni51 | interior | post | 17 | 231 | 192 | 0.82 | 47.92 | 0.86 | 51.57 | 0.004 | 0.459 | 16 of 17 |
| uni | uni51 | interior_eq | pre | 33 | 197 | 197 | 103.38 | 115.48 | 103.38 | 115.48 | 0.381 | 0.396 | 22 of 33 |
| uni | uni51 | interior_eq | post | 5 | 25 | 25 | 0.56 | 20.00 | 0.56 | 20.00 | 0.000 | 0.680 | 5 of 5 |
| uni | uni51 | offset | pre | 33 | 152 | 152 | 9.72 | 9.45 | 9.72 | 9.45 | 0.158 | 0.151 | 20 of 33 |
| uni | uni51 | offset | post | 33 | 148 | 95 | 0.85 | 10.21 | 0.53 | 8.23 | 0.007 | 0.189 | 28 of 33 |
| mv-lit | mvlit34 | onset | pre | 50 | 296 | 296 | 13.21 | 14.56 | 13.21 | 14.56 | 0.267 | 0.324 | 34 of 50 |
| mv-lit | mvlit34 | onset | post | 1 | 1 | 1 | 0.07 | 25.04 | 0.07 | 25.04 | 0.000 | 1.000 | 1 of 1 |
| mv-lit | mvlit34 | interior | pre | 43 | 406 | 406 | 91.35 | 102.30 | 91.35 | 102.30 | 0.367 | 0.392 | 21 of 43 |
| mv-lit | mvlit34 | interior | post | 17 | 231 | 192 | 0.46 | 41.55 | 0.47 | 45.81 | 0.000 | 0.459 | 16 of 17 |
| mv-lit | mvlit34 | interior_eq | pre | 33 | 197 | 197 | 83.79 | 95.97 | 83.79 | 95.97 | 0.386 | 0.411 | 16 of 33 |
| mv-lit | mvlit34 | interior_eq | post | 5 | 25 | 25 | 0.16 | 14.36 | 0.16 | 14.36 | 0.000 | 0.680 | 5 of 5 |
| mv-lit | mvlit34 | offset | pre | 33 | 152 | 152 | 9.53 | 8.50 | 9.53 | 8.50 | 0.158 | 0.151 | 15 of 33 |
| mv-lit | mvlit34 | offset | post | 33 | 148 | 95 | 0.51 | 8.46 | 0.38 | 7.30 | 0.000 | 0.176 | 29 of 33 |

Reading:

- **Post-onset interior** (231 steps, 17 attacks): in 16 of 17 attacks the clean-context counterfactual scores higher than the rolling forecast, for both uni and mv-lit. The mean band score is 41.55 vs 0.46 for mv-lit and 47.92 vs 0.82 for uni. At the rolling threshold the counterfactual covers 0.459 of these steps; rolling covers 0.000 (mv-lit) and 0.004 (uni). On the 192 steps with `h_cf <= 30` the score is 45.81 vs 0.47 (mv-lit).
- By PLAN.md 9, a higher counterfactual score on these steps is conservative evidence of contamination, because wider bands at longer h push the counterfactual's score down. The `h_cf <= 30` subset removes the horizon difference. It does not remove the difference in output-patch count.
- **Pre-onset control** (both contexts clean): the two forecasts are close. Interior scores are 102.30 vs 91.35 with coverage 0.392 vs 0.367 (mv-lit); onset coverage is 0.324 vs 0.267. With both contexts clean, the counterfactual's mean interior score is about 1.1 times the rolling one. That is the combined effect of its other differences (origin, horizon, patch count). On post-onset steps the ratio is about 90.
- **Post-onset offset** (148 steps, 33 attacks): the counterfactual covers 0.176 (mv-lit) and 0.189 (uni), where rolling covers 0.000 and 0.007. It scores higher in 29 and 28 of 33 attacks.
- **Not every miss is contamination.** For mv-lit the counterfactual also has zero coverage on the post-onset interior steps of A206, A210, A212, A401 and A509 (per-attack rows of the CSV). Those attacks are missed even from a clean context.
- The post-onset onset row is one step of one attack and says nothing.

**What the 10 s data say about context contamination.** They support it, on the steps where it can be tested. Every Chronos-2 rolling setup alarms on 0 or 1 of the 231 interior steps whose context holds attack data. This holds in every h bucket and every time-since-onset bucket. The same model covers 0.367 of the interior steps forecast from clean context. The h confound works the other way, because bands widen with h. The post-onset steps are detectable: a clean-context forecast from the onset covers 0.459 of them at the same threshold, and the methods that never forecast from test context (seasonal-refday, frozen) cover them about as well as the clean-context steps. **But at 10 s this is a weak test of the hypothesis as a whole** (section 3.9). With H = 30, 406 of the 637 interior steps are forecast from pre-onset, clean contexts. Only 17 attacks have any post-onset step, so the effect rests on 232 attack steps. On the clean-context majority, 0.633 of interior steps get no alarm, and that is not contamination. The segment means do not show the predicted boundary-vs-interior shape either: onset and interior coverage are close at N = 6 (base 0.263 vs 0.295), their order flips with N, and the offset is not caught outside the trip and pcv02d attacks (tables below). The 1 s block, where 86.0 % of attack seconds come from post-onset contexts, was not run (D134). No 1 s result is claimed.

**Offset per stratum.** In the 9 trip attacks the post-attack "normal" seconds hold tripped-turbine data for up to
52 s (PLAN.md 9), so an offset alarm there may be a real process anomaly, not a context effect. A302 and A512 are
followed by the `P1_PCV02Z` level shift.

Rows of `results/phase1/segments_summary.csv`: N 6, ff_group all, topk, band (dual for dual), the same runs and sets as the first table. Rates are over the attacks whose segment is not empty: trip 9, pcv02d 5, other 36 for onset and offset and 33 for the interior. n = 5 and n = 9 are small.

| method | channel_set | stratum | n_attacks | p_normal | onset_cov_mean | interior_cov_mean | offset_cov_mean | onset_rate / chance | interior_rate / chance | offset_rate | offset_chance |
|---|---|---|---|---|---|---|---|---|---|---|---|
| uni rolling | uni51 | trip | 9 | 0.003 | 0.444 | 0.772 | 0.278 | 0.889 / 0.020 | 1.000 / 0.019 | 0.444 | 0.020 |
| uni rolling | uni51 | pcv02d | 5 | 0.003 | 0.067 | 0.673 | 0.333 | 0.200 / 0.020 | 1.000 / 0.085 | 0.600 | 0.020 |
| uni rolling | uni51 | other | 36 | 0.003 | 0.269 | 0.101 | 0.000 | 0.472 / 0.020 | 0.364 / 0.045 | 0.000 | 0.020 |
| uni57 rolling | uni57 | trip | 9 | 0.003 | 0.444 | 0.753 | 0.241 | 0.889 / 0.017 | 1.000 / 0.016 | 0.444 | 0.017 |
| uni57 rolling | uni57 | pcv02d | 5 | 0.003 | 0.033 | 0.526 | 0.233 | 0.200 / 0.017 | 1.000 / 0.072 | 0.400 | 0.017 |
| uni57 rolling | uni57 | other | 36 | 0.003 | 0.148 | 0.048 | 0.000 | 0.333 / 0.017 | 0.212 / 0.039 | 0.000 | 0.017 |
| **mv-lit rolling (base; also best of 1-3; both picked on test results)** | mvlit34 | trip | 9 | 0.003 | 0.444 | 0.772 | 0.278 | 0.889 / 0.018 | 1.000 / 0.018 | 0.444 | 0.018 |
| **mv-lit rolling (base; also best of 1-3; both picked on test results)** | mvlit34 | pcv02d | 5 | 0.003 | 0.133 | 0.674 | 0.300 | 0.400 / 0.018 | 1.000 / 0.077 | 0.400 | 0.018 |
| **mv-lit rolling (base; also best of 1-3; both picked on test results)** | mvlit34 | other | 36 | 0.003 | 0.236 | 0.108 | 0.000 | 0.417 / 0.018 | 0.333 / 0.041 | 0.000 | 0.018 |
| mv-acttgt rolling | mvacttgt41 | trip | 9 | 0.003 | 0.463 | 0.772 | 0.315 | 0.889 / 0.020 | 1.000 / 0.019 | 0.556 | 0.020 |
| mv-acttgt rolling | mvacttgt41 | pcv02d | 5 | 0.003 | 0.167 | 0.683 | 0.300 | 0.400 / 0.020 | 1.000 / 0.084 | 0.400 | 0.020 |
| mv-acttgt rolling | mvacttgt41 | other | 36 | 0.003 | 0.255 | 0.108 | 0.000 | 0.444 / 0.020 | 0.333 / 0.045 | 0.000 | 0.020 |
| ff-interp-block (INTERPRETATION) | mvlit34 | trip | 9 | 0.324 | 0.593 | 0.830 | 0.630 | 0.889 / 0.904 | 1.000 / 0.783 | 0.889 | 0.904 |
| ff-interp-block (INTERPRETATION) | mvlit34 | pcv02d | 5 | 0.324 | 0.233 | 0.662 | 0.400 | 0.400 / 0.904 | 1.000 / 0.999 | 0.400 | 0.904 |
| ff-interp-block (INTERPRETATION) | mvlit34 | other | 36 | 0.324 | 0.551 | 0.490 | 0.380 | 0.722 / 0.898 | 0.727 / 0.931 | 0.444 | 0.904 |
| ff-interp-block-max60-testinf (INTERPRETATION, test-informed) | mvlit34 | trip | 9 | 0.101 | 0.426 | 0.753 | 0.241 | 0.889 / 0.473 | 1.000 / 0.417 | 0.444 | 0.473 |
| ff-interp-block-max60-testinf (INTERPRETATION, test-informed) | mvlit34 | pcv02d | 5 | 0.101 | 0.067 | 0.460 | 0.300 | 0.200 / 0.473 | 1.000 / 0.907 | 0.400 | 0.473 |
| ff-interp-block-max60-testinf (INTERPRETATION, test-informed) | mvlit34 | other | 36 | 0.101 | 0.185 | 0.092 | 0.023 | 0.333 / 0.468 | 0.182 / 0.688 | 0.056 | 0.473 |
| frozen (INTERPRETATION) | mvlit34 | trip | 9 | 0.011 | 0.481 | 0.780 | 0.259 | 0.889 / 0.063 | 1.000 / 0.060 | 0.556 | 0.063 |
| frozen (INTERPRETATION) | mvlit34 | pcv02d | 5 | 0.011 | 0.300 | 0.531 | 0.233 | 0.600 / 0.063 | 1.000 / 0.244 | 0.400 | 0.063 |
| frozen (INTERPRETATION) | mvlit34 | other | 36 | 0.011 | 0.042 | 0.075 | 0.023 | 0.139 / 0.062 | 0.273 / 0.136 | 0.083 | 0.063 |
| dual (INTERPRETATION; dual score) | mvlit34 | trip | 9 | 0.025 | 0.074 | 0.046 | 0.185 | 0.111 / 0.142 | 0.222 / 0.133 | 0.333 | 0.142 |
| dual (INTERPRETATION; dual score) | mvlit34 | pcv02d | 5 | 0.025 | 0.233 | 0.512 | 0.800 | 0.400 / 0.142 | 0.800 / 0.473 | 0.800 | 0.142 |
| dual (INTERPRETATION; dual score) | mvlit34 | other | 36 | 0.025 | 0.037 | 0.040 | 0.005 | 0.083 / 0.140 | 0.242 / 0.282 | 0.028 | 0.142 |
| robustz | mvlit34 | trip | 9 | 0.008 | 0.444 | 0.762 | 0.315 | 0.889 / 0.048 | 1.000 / 0.046 | 0.556 | 0.048 |
| robustz | mvlit34 | pcv02d | 5 | 0.008 | 0.067 | 0.604 | 0.400 | 0.200 / 0.048 | 1.000 / 0.191 | 0.400 | 0.048 |
| robustz | mvlit34 | other | 36 | 0.008 | 0.046 | 0.033 | 0.009 | 0.083 / 0.047 | 0.091 / 0.105 | 0.028 | 0.048 |
| lastvalue | mvlit34 | trip | 9 | 0.007 | 0.444 | 0.772 | 0.500 | 0.889 / 0.043 | 1.000 / 0.041 | 0.556 | 0.043 |
| lastvalue | mvlit34 | pcv02d | 5 | 0.007 | 0.067 | 0.913 | 0.900 | 0.200 / 0.043 | 1.000 / 0.171 | 1.000 | 0.043 |
| lastvalue | mvlit34 | other | 36 | 0.007 | 0.199 | 0.231 | 0.111 | 0.417 / 0.042 | 0.515 / 0.093 | 0.167 | 0.043 |
| seasonal-refday | mvlit34 | trip | 9 | 0.018 | 0.463 | 0.830 | 0.389 | 0.889 / 0.103 | 1.000 / 0.097 | 0.667 | 0.103 |
| seasonal-refday | mvlit34 | pcv02d | 5 | 0.018 | 0.567 | 0.840 | 0.333 | 0.600 / 0.103 | 1.000 / 0.369 | 0.600 | 0.103 |
| seasonal-refday | mvlit34 | other | 36 | 0.018 | 0.463 | 0.372 | 0.153 | 0.667 / 0.101 | 0.667 / 0.213 | 0.278 | 0.103 |
| robustz | uni51 | trip | 9 | 0.008 | 0.444 | 0.762 | 0.296 | 0.889 / 0.049 | 1.000 / 0.047 | 0.556 | 0.049 |
| robustz | uni51 | pcv02d | 5 | 0.008 | 0.067 | 0.604 | 0.400 | 0.200 / 0.049 | 1.000 / 0.194 | 0.400 | 0.049 |
| robustz | uni51 | other | 36 | 0.008 | 0.111 | 0.077 | 0.019 | 0.222 / 0.048 | 0.212 / 0.107 | 0.028 | 0.049 |
| lastvalue | uni51 | trip | 9 | 0.008 | 0.463 | 0.772 | 0.500 | 0.889 / 0.046 | 1.000 / 0.043 | 0.556 | 0.046 |
| lastvalue | uni51 | pcv02d | 5 | 0.008 | 0.133 | 0.939 | 0.900 | 0.400 / 0.046 | 1.000 / 0.182 | 1.000 | 0.046 |
| lastvalue | uni51 | other | 36 | 0.008 | 0.250 | 0.230 | 0.093 | 0.500 / 0.045 | 0.485 / 0.100 | 0.167 | 0.046 |
| seasonal-refday | uni51 | trip | 9 | 0.014 | 0.463 | 0.830 | 0.370 | 0.889 / 0.083 | 1.000 / 0.079 | 0.667 | 0.083 |
| seasonal-refday | uni51 | pcv02d | 5 | 0.014 | 0.567 | 0.841 | 0.333 | 0.600 / 0.083 | 1.000 / 0.310 | 0.600 | 0.083 |
| seasonal-refday | uni51 | other | 36 | 0.014 | 0.449 | 0.364 | 0.139 | 0.667 / 0.082 | 0.667 / 0.176 | 0.278 | 0.083 |
| prepend (optional) | mvlit34 | trip | 9 | 0.003 | 0.444 | 0.772 | 0.278 | 0.889 / 0.015 | 1.000 / 0.014 | 0.444 | 0.015 |
| prepend (optional) | mvlit34 | pcv02d | 5 | 0.003 | 0.067 | 0.354 | 0.033 | 0.200 / 0.015 | 0.800 / 0.064 | 0.200 | 0.015 |
| prepend (optional) | mvlit34 | other | 36 | 0.003 | 0.250 | 0.126 | 0.000 | 0.444 / 0.015 | 0.394 / 0.034 | 0.000 | 0.015 |
| ff-interp-block-max30 (optional, INTERPRETATION) | mvlit34 | trip | 9 | 0.059 | 0.519 | 0.753 | 0.352 | 0.889 / 0.306 | 1.000 / 0.277 | 0.556 | 0.306 |
| ff-interp-block-max30 (optional, INTERPRETATION) | mvlit34 | pcv02d | 5 | 0.059 | 0.033 | 0.571 | 0.367 | 0.200 / 0.306 | 1.000 / 0.764 | 0.400 | 0.306 |
| ff-interp-block-max30 (optional, INTERPRETATION) | mvlit34 | other | 36 | 0.059 | 0.144 | 0.104 | 0.069 | 0.250 / 0.302 | 0.333 / 0.519 | 0.083 | 0.306 |
| ff-interp-block-max120 (optional, INTERPRETATION) | mvlit34 | trip | 9 | 0.271 | 0.519 | 0.766 | 0.426 | 0.889 / 0.850 | 1.000 / 0.730 | 0.667 | 0.850 |
| ff-interp-block-max120 (optional, INTERPRETATION) | mvlit34 | pcv02d | 5 | 0.271 | 0.133 | 0.471 | 0.200 | 0.200 / 0.850 | 1.000 / 0.997 | 0.200 | 0.850 |
| ff-interp-block-max120 (optional, INTERPRETATION) | mvlit34 | other | 36 | 0.271 | 0.213 | 0.212 | 0.245 | 0.250 / 0.844 | 0.333 / 0.908 | 0.278 | 0.850 |

Reading:

- The interior coverage of the Chronos-2 rolling runs comes from the 14 trip and pcv02d attacks. In the base it is 0.772 (trip) and 0.674 (pcv02d), against 0.108 for the 36 other attacks. Every trip and pcv02d attack has an interior alarm (rate 1.000).
- For the 36 other attacks the base has the onset-over-interior shape the hypothesis predicts: coverage 0.236 vs 0.108, and rates 0.417 vs 0.333 (chance 0.018 and 0.041). But it has no offset signal at all: offset coverage and rate are 0.000. uni, uni57, mv-acttgt and prepend show the same.
- Every offset alarm of the Chronos-2 rolling runs falls in a trip or pcv02d attack (base offset rate 0.444 for trip, 0.400 for pcv02d). In trip attacks the post-attack "normal" steps hold tripped-turbine data, so those offset alarms may be real process deviations, not a boundary effect of the context. In the base the two pcv02d offset alarms are in A101 and A402. A302 and A512, which are followed by the `P1_PCV02Z` level shift, have none (`segments_per_attack.csv`, section 4.5).
- The baselines share the trip pattern: trip interior coverage is 0.762 to 0.830 for every baseline. Unlike the Chronos-2 rolling runs, they also alarm at some offsets of other attacks (offset rate 0.028 to 0.278). On the other attacks, only seasonal-refday (interior 0.372 on `mvlit34`) and lastvalue (0.231) keep substantial interior coverage.

**Appendix: N sensitivity** (N = 3 and 12 steps; headline score and agg only, D93).

Rows of `results/phase1/segments_summary.csv`: N 3 and N 12 steps, stratum all, ff_group all, topk, band (dual for dual). The file has these rows only for the headline score and agg (D93). The N = 6 rows are in the first table of this section. The number of attacks per segment changes with N (`segments_per_attack.csv`, base): interior 49 / 47 / 34 and `interior_eq` 49 / 37 / 18 for N = 3 / 6 / 12; onset and offset 50 at every N. The N = 12 `interior_eq` rates rest on 18 attacks.

| method | channel_set | N | onset_cov_mean | interior_cov_mean | interior_eq_cov_mean | offset_cov_mean | onset_rate / chance | interior_rate / chance | interior_eq_rate / chance | offset_rate / chance |
|---|---|---|---|---|---|---|---|---|---|---|
| uni rolling | uni51 | 3 | 0.120 | 0.315 | 0.449 | 0.127 | 0.260 / 0.010 | 0.633 / 0.053 | 0.510 / 0.010 | 0.140 / 0.010 |
| uni rolling | uni51 | 12 | 0.323 | 0.121 | 0.185 | 0.047 | 0.600 / 0.037 | 0.235 / 0.037 | 0.278 / 0.040 | 0.140 / 0.040 |
| uni57 rolling | uni57 | 3 | 0.047 | 0.254 | 0.340 | 0.100 | 0.120 / 0.009 | 0.531 / 0.045 | 0.429 / 0.009 | 0.120 / 0.009 |
| uni57 rolling | uni57 | 12 | 0.238 | 0.086 | 0.111 | 0.038 | 0.500 / 0.031 | 0.176 / 0.032 | 0.111 / 0.034 | 0.120 / 0.034 |
| **mv-lit rolling (base; also best of 1-3; both picked on test results)** | mvlit34 | 3 | 0.107 | 0.315 | 0.429 | 0.120 | 0.220 / 0.009 | 0.612 / 0.048 | 0.490 / 0.009 | 0.120 / 0.009 |
| **mv-lit rolling (base; also best of 1-3; both picked on test results)** | mvlit34 | 12 | 0.318 | 0.114 | 0.171 | 0.045 | 0.580 / 0.033 | 0.206 / 0.034 | 0.222 / 0.036 | 0.120 / 0.036 |
| mv-acttgt rolling | mvacttgt41 | 3 | 0.133 | 0.317 | 0.442 | 0.127 | 0.260 / 0.010 | 0.612 / 0.052 | 0.490 / 0.010 | 0.140 / 0.010 |
| mv-acttgt rolling | mvacttgt41 | 12 | 0.331 | 0.116 | 0.171 | 0.048 | 0.600 / 0.036 | 0.206 / 0.037 | 0.222 / 0.039 | 0.140 / 0.039 |
| ff-interp-block (INTERPRETATION) | mvlit34 | 3 | 0.427 | 0.582 | 0.639 | 0.473 | 0.540 / 0.691 | 0.857 / 0.961 | 0.714 / 0.691 | 0.520 / 0.691 |
| ff-interp-block (INTERPRETATION) | mvlit34 | 12 | 0.575 | 0.391 | 0.532 | 0.378 | 0.800 / 0.976 | 0.559 / 0.870 | 0.722 / 0.991 | 0.520 / 0.991 |
| ff-interp-block-max60-testinf (INTERPRETATION, test-informed) | mvlit34 | 3 | 0.127 | 0.258 | 0.313 | 0.113 | 0.220 / 0.274 | 0.531 / 0.734 | 0.408 / 0.274 | 0.140 / 0.274 |
| ff-interp-block-max60-testinf (INTERPRETATION, test-informed) | mvlit34 | 12 | 0.255 | 0.079 | 0.157 | 0.078 | 0.520 / 0.682 | 0.206 / 0.605 | 0.222 / 0.722 | 0.200 / 0.722 |
| frozen (INTERPRETATION) | mvlit34 | 3 | 0.067 | 0.244 | 0.231 | 0.140 | 0.100 / 0.032 | 0.510 / 0.155 | 0.306 / 0.032 | 0.180 / 0.032 |
| frozen (INTERPRETATION) | mvlit34 | 12 | 0.217 | 0.109 | 0.194 | 0.048 | 0.440 / 0.112 | 0.294 / 0.113 | 0.278 / 0.122 | 0.200 / 0.122 |
| dual (INTERPRETATION; dual score) | mvlit34 | 3 | 0.067 | 0.086 | 0.061 | 0.100 | 0.080 / 0.074 | 0.286 / 0.317 | 0.102 / 0.074 | 0.100 / 0.074 |
| dual (INTERPRETATION; dual score) | mvlit34 | 12 | 0.075 | 0.108 | 0.083 | 0.108 | 0.200 / 0.243 | 0.294 / 0.236 | 0.222 / 0.263 | 0.180 / 0.263 |
| robustz | mvlit34 | 3 | 0.027 | 0.229 | 0.218 | 0.147 | 0.080 / 0.024 | 0.347 / 0.120 | 0.245 / 0.024 | 0.160 / 0.024 |
| robustz | mvlit34 | 12 | 0.182 | 0.102 | 0.204 | 0.072 | 0.320 / 0.086 | 0.206 / 0.087 | 0.278 / 0.094 | 0.160 / 0.094 |
| lastvalue | mvlit34 | 3 | 0.093 | 0.390 | 0.374 | 0.293 | 0.200 / 0.021 | 0.673 / 0.107 | 0.449 / 0.021 | 0.320 / 0.021 |
| lastvalue | mvlit34 | 12 | 0.295 | 0.318 | 0.407 | 0.215 | 0.600 / 0.076 | 0.412 / 0.077 | 0.444 / 0.083 | 0.320 / 0.083 |
| seasonal-refday | mvlit34 | 3 | 0.313 | 0.535 | 0.646 | 0.280 | 0.500 / 0.053 | 0.776 / 0.241 | 0.714 / 0.053 | 0.360 / 0.053 |
| seasonal-refday | mvlit34 | 12 | 0.510 | 0.324 | 0.468 | 0.133 | 0.740 / 0.179 | 0.529 / 0.177 | 0.667 / 0.195 | 0.400 / 0.195 |
| robustz | uni51 | 3 | 0.040 | 0.273 | 0.299 | 0.147 | 0.120 / 0.025 | 0.469 / 0.122 | 0.347 / 0.025 | 0.160 / 0.025 |
| robustz | uni51 | 12 | 0.227 | 0.149 | 0.255 | 0.073 | 0.440 / 0.087 | 0.265 / 0.088 | 0.333 / 0.095 | 0.160 / 0.095 |
| lastvalue | uni51 | 3 | 0.133 | 0.402 | 0.429 | 0.280 | 0.260 / 0.023 | 0.694 / 0.115 | 0.510 / 0.023 | 0.320 / 0.023 |
| lastvalue | uni51 | 12 | 0.327 | 0.321 | 0.412 | 0.212 | 0.660 / 0.082 | 0.412 / 0.082 | 0.444 / 0.089 | 0.320 / 0.089 |
| seasonal-refday | uni51 | 3 | 0.293 | 0.531 | 0.646 | 0.273 | 0.500 / 0.043 | 0.796 / 0.200 | 0.714 / 0.043 | 0.360 / 0.043 |
| seasonal-refday | uni51 | 12 | 0.504 | 0.319 | 0.458 | 0.125 | 0.760 / 0.147 | 0.529 / 0.146 | 0.667 / 0.160 | 0.380 / 0.160 |
| prepend (optional) | mvlit34 | 3 | 0.113 | 0.300 | 0.429 | 0.087 | 0.240 / 0.008 | 0.633 / 0.039 | 0.490 / 0.008 | 0.100 / 0.008 |
| prepend (optional) | mvlit34 | 12 | 0.317 | 0.060 | 0.116 | 0.027 | 0.580 / 0.027 | 0.176 / 0.028 | 0.167 / 0.030 | 0.100 / 0.030 |
| ff-interp-block-max30 (optional, INTERPRETATION) | mvlit34 | 3 | 0.107 | 0.275 | 0.299 | 0.167 | 0.160 / 0.167 | 0.571 / 0.565 | 0.347 / 0.167 | 0.200 / 0.167 |
| ff-interp-block-max30 (optional, INTERPRETATION) | mvlit34 | 12 | 0.254 | 0.139 | 0.199 | 0.123 | 0.540 / 0.483 | 0.324 / 0.445 | 0.333 / 0.518 | 0.220 / 0.518 |
| ff-interp-block-max120 (optional, INTERPRETATION) | mvlit34 | 3 | 0.193 | 0.331 | 0.333 | 0.273 | 0.220 / 0.613 | 0.531 / 0.941 | 0.367 / 0.613 | 0.320 / 0.613 |
| ff-interp-block-max120 (optional, INTERPRETATION) | mvlit34 | 12 | 0.310 | 0.202 | 0.296 | 0.265 | 0.500 / 0.957 | 0.324 / 0.842 | 0.389 / 0.978 | 0.360 / 0.978 |

Reading:

- For every Chronos-2 rolling run, onset coverage rises with N and interior coverage falls. In the base, onset coverage is 0.107 / 0.263 / 0.318 and interior coverage 0.315 / 0.295 / 0.114 for N = 3 / 6 / 12. The order of onset and interior flips between N = 3 and N = 12. So whether "the boundary" beats "the interior" at 10 s depends on N, and N was chosen partly from test data (section 6.3). Part of the N = 12 interior drop is a different attack set (34 attacks with an interior, not 47).
- The first 30 s of an attack rarely get an alarm: at N = 3 the base's onset coverage is 0.107 (rate 0.220 vs chance 0.009). Alarms build up over the first one to two minutes. At N = 3, `interior_eq` (attack steps 4-6) has the base's highest coverage, 0.429.
- The detection rates of the Chronos-2 rolling runs stay above chance at both N.

### 4.5 Per attack

Rows of `results/phase1/segments_per_attack.csv` for the base mv-lit rolling run (hash `c06bc843`, `mvlit34`, band, topk, N 6). The best-of-1-3 pick is the same run (`selection.csv`, stage best; picked on test results), so one table covers both. `ff_group` is empty for a rolling run and is left out. Conventions: "empty" = no interior at N = 6 (A203, A211, A508). A blank `interior_eq_cov` = the attack is shorter than 12 steps. Latency "miss" = no alarm in the attack (`latency_s` is empty); `latency_censored_s` is then duration + N. A blank `cov_post_origin` = the attack has no post-onset step. `n_pre_origin + n_post_origin = duration_steps`.

| attack_id | stratum | duration_steps | onset_cov | interior_n | interior_cov | interior_eq_cov | offset_cov | latency_s | latency_censored_s | n_pre_origin | cov_pre_origin | n_post_origin | cov_post_origin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A101 | pcv02d | 20 | 0.000 | 14 | 0.857 | 0.667 | 1.000 | 80 | 80 | 20 | 0.600 | 0 |  |
| A102 | other | 10 | 0.000 | 4 | 0.000 |  | 0.000 | miss | 160 | 10 | 0.000 | 0 |  |
| A103 | other | 20 | 0.500 | 14 | 0.000 | 0.000 | 0.000 | 20 | 20 | 5 | 0.600 | 15 | 0.000 |
| A104 | other | 7 | 0.000 | 1 | 0.000 |  | 0.000 | miss | 130 | 7 | 0.000 | 0 |  |
| A105 | other | 9 | 0.833 | 3 | 0.667 |  | 0.000 | 10 | 10 | 9 | 0.778 | 0 |  |
| A201 | trip | 9 | 0.333 | 3 | 1.000 |  | 0.667 | 40 | 40 | 9 | 0.556 | 0 |  |
| A202 | pcv02d | 43 | 0.000 | 37 | 0.162 | 1.000 | 0.000 | 60 | 60 | 12 | 0.500 | 31 | 0.000 |
| A203 | other | 3 | 0.000 | 0 | empty |  | 0.000 | miss | 90 | 3 | 0.000 | 0 |  |
| A204 | other | 26 | 0.500 | 20 | 0.200 | 0.500 | 0.000 | 30 | 30 | 26 | 0.269 | 0 |  |
| A205 | other | 13 | 0.000 | 7 | 0.000 | 0.000 | 0.000 | miss | 190 | 13 | 0.000 | 0 |  |
| A206 | other | 26 | 0.000 | 20 | 0.000 | 0.000 | 0.000 | miss | 320 | 18 | 0.000 | 8 | 0.000 |
| A207 | trip | 7 | 0.500 | 1 | 1.000 |  | 0.833 | 30 | 30 | 7 | 0.571 | 0 |  |
| A208 | other | 27 | 0.500 | 21 | 0.286 | 1.000 | 0.000 | 30 | 30 | 12 | 0.750 | 15 | 0.000 |
| A209 | other | 20 | 0.000 | 14 | 0.000 | 0.000 | 0.000 | miss | 260 | 11 | 0.000 | 9 | 0.000 |
| A210 | other | 43 | 0.000 | 37 | 0.000 | 0.000 | 0.000 | miss | 490 | 6 | 0.000 | 37 | 0.000 |
| A211 | other | 6 | 0.000 | 0 | empty |  | 0.000 | miss | 120 | 6 | 0.000 | 0 |  |
| A212 | other | 16 | 0.000 | 10 | 0.000 | 0.000 | 0.000 | miss | 220 | 12 | 0.000 | 4 | 0.000 |
| A213 | other | 26 | 0.500 | 20 | 0.000 | 0.000 | 0.000 | 30 | 30 | 6 | 0.500 | 20 | 0.000 |
| A214 | other | 16 | 0.000 | 10 | 0.000 | 0.000 | 0.000 | miss | 220 | 16 | 0.000 | 0 |  |
| A215 | other | 16 | 0.000 | 10 | 0.000 | 0.000 | 0.000 | miss | 220 | 16 | 0.000 | 0 |  |
| A216 | other | 8 | 0.000 | 2 | 0.000 |  | 0.000 | miss | 140 | 8 | 0.000 | 0 |  |
| A217 | trip | 19 | 0.000 | 13 | 0.231 | 0.000 | 0.000 | 150 | 150 | 18 | 0.167 | 1 | 0.000 |
| A218 | other | 11 | 0.167 | 5 | 0.800 |  | 0.000 | 20 | 20 | 11 | 0.455 | 0 |  |
| A219 | other | 13 | 0.000 | 7 | 0.000 | 0.000 | 0.000 | miss | 190 | 13 | 0.000 | 0 |  |
| A220 | other | 13 | 0.000 | 7 | 0.000 | 0.000 | 0.000 | miss | 190 | 13 | 0.000 | 0 |  |
| A301 | other | 14 | 0.000 | 8 | 0.000 | 0.000 | 0.000 | miss | 200 | 14 | 0.000 | 0 |  |
| A302 | pcv02d | 43 | 0.000 | 37 | 0.486 | 1.000 | 0.000 | 60 | 60 | 24 | 0.750 | 19 | 0.000 |
| A303 | other | 20 | 0.000 | 14 | 0.000 | 0.000 | 0.000 | miss | 260 | 20 | 0.000 | 0 |  |
| A304 | trip | 11 | 0.667 | 5 | 0.800 |  | 0.000 | 20 | 20 | 11 | 0.727 | 0 |  |
| A305 | trip | 9 | 0.500 | 3 | 1.000 |  | 0.500 | 30 | 30 | 9 | 0.667 | 0 |  |
| A306 | other | 24 | 0.833 | 18 | 0.111 | 0.333 | 0.000 | 10 | 10 | 24 | 0.292 | 0 |  |
| A307 | trip | 12 | 0.667 | 6 | 0.667 | 0.667 | 0.000 | 20 | 20 | 12 | 0.667 | 0 |  |
| A308 | other | 26 | 0.833 | 20 | 0.250 | 0.833 | 0.000 | 10 | 10 | 12 | 0.833 | 14 | 0.000 |
| A401 | other | 26 | 0.000 | 20 | 0.000 | 0.000 | 0.000 | miss | 320 | 12 | 0.000 | 14 | 0.000 |
| A402 | pcv02d | 27 | 0.333 | 21 | 1.000 | 1.000 | 0.500 | 40 | 40 | 27 | 0.852 | 0 |  |
| A403 | other | 27 | 0.333 | 21 | 0.286 | 1.000 | 0.000 | 40 | 40 | 18 | 0.444 | 9 | 0.000 |
| A404 | other | 26 | 0.667 | 20 | 0.150 | 0.500 | 0.000 | 20 | 20 | 26 | 0.269 | 0 |  |
| A405 | other | 13 | 0.000 | 7 | 0.000 | 0.000 | 0.000 | miss | 190 | 13 | 0.000 | 0 |  |
| A501 | trip | 18 | 0.333 | 12 | 0.583 | 1.000 | 0.000 | 40 | 40 | 18 | 0.500 | 0 |  |
| A502 | other | 27 | 0.833 | 21 | 0.000 | 0.000 | 0.000 | 10 | 10 | 27 | 0.185 | 0 |  |
| A503 | other | 27 | 0.333 | 21 | 0.238 | 0.833 | 0.000 | 40 | 40 | 27 | 0.259 | 0 |  |
| A504 | other | 12 | 0.500 | 6 | 0.500 | 0.500 | 0.000 | 20 | 20 | 12 | 0.500 | 0 |  |
| A505 | other | 22 | 0.000 | 16 | 0.062 | 0.167 | 0.000 | 110 | 110 | 12 | 0.083 | 10 | 0.000 |
| A506 | other | 16 | 0.000 | 10 | 0.000 | 0.000 | 0.000 | miss | 220 | 16 | 0.000 | 0 |  |
| A507 | trip | 9 | 0.500 | 3 | 1.000 |  | 0.500 | 30 | 30 | 9 | 0.667 | 0 |  |
| A508 | other | 6 | 0.667 | 0 | empty |  | 0.000 | 10 | 10 | 6 | 0.667 | 0 |  |
| A509 | other | 25 | 0.000 | 19 | 0.000 | 0.000 | 0.000 | miss | 310 | 23 | 0.000 | 2 | 0.000 |
| A510 | other | 27 | 0.500 | 21 | 0.000 | 0.000 | 0.000 | 30 | 30 | 6 | 0.500 | 21 | 0.000 |
| A511 | trip | 12 | 0.500 | 6 | 0.667 | 0.667 | 0.000 | 30 | 30 | 12 | 0.583 | 0 |  |
| A512 | pcv02d | 28 | 0.333 | 22 | 0.864 | 1.000 | 0.000 | 40 | 40 | 25 | 0.840 | 3 | 0.000 |

Reading (counts and pooled values aggregated from the rows above):

- 30 of 50 attacks get an alarm. All 20 misses are "other" attacks. All 9 trip and all 5 pcv02d attacks are detected.
- Of the 17 attacks with post-onset steps, none has an alarm on a post-onset step (0 of 232 steps). 11 of them have alarms on their pre-onset steps. Pooled over these 17 attacks, pre-onset coverage is 0.366 (232 steps). The long attacks show this most clearly. A202 alarms on all 6 `interior_eq` steps, which are forecast before onset, and on none of its 31 post-onset steps. A302 covers 0.750 of its pre-onset steps and 0.000 of its 19 post-onset steps; A308 covers 0.833 and 0.000 of 14.
- The 33 attacks with no post-onset step have a pooled coverage of 0.304 over 470 steps.
- Some misses are not contamination. A210, one of the three 43-step attacks (with A202 and A302), gets no alarm on any step, including its 6 clean-context onset steps. The clean-context counterfactual also misses its post-onset steps (`cf_onset.csv`).
- Offset alarms occur in 6 attacks: A101 and A402 (pcv02d), and A201, A207, A305 and A507 (trip). None occurs in an "other" attack.

### 4.6 Experiment 3a: Forecast Fallback (interpretation)

Base setup `mv-lit` (picked on test results, section 4.3), score `band`, agg `topk`, thresholds from `calib`. Metrics and thresholds come from `results/phase1/metrics.csv` and `results/phase1/thresholds.csv` (calib_source calib, pct 99.5). TaP, TaR and TaPR F1 come from `results/phase1/tapr.csv` (config headline). Chance: ROC-AUC 0.5, PR-AUC 0.024. The full set `mvlit34` is the headline. The `-noPCV02Z` rows (D50) are secondary; they are shown because they show where FF's false alarms come from.

| variant | setup | channel_set | roc_auc | pr_auc | precision | recall | f1 | alarm_steps | fa_per_hour | threshold | TaP | TaR | TaPR F1 (headline) | pa_f1_inflated (inflated) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `rolling` | mv-lit | `mvlit34` | 0.862 | 0.397 | 0.657 | 0.244 | 0.356 | 347 | 1.112 | 9.442 | 0.772 | 0.270 | 0.400 | 0.734 |
| `ff-interp-block` | mv-lit | `mvlit34` | 0.637 | 0.208 | 0.038 | 0.530 | 0.071 | 12,958 | 116.489 | 34.045 | 0.215 | 0.580 | 0.313 | 0.111 |
| `ff-interp-block-max60-testinf` | mv-lit | `mvlit34` | 0.659 | 0.147 | 0.045 | 0.195 | 0.073 | 4,084 | 36.471 | 23.444 | 0.083 | 0.228 | 0.121 | 0.201 |
| `rolling` | mv-lit | `mvlit34-noPCV02Z` | 0.864 | 0.345 | 0.609 | 0.179 | 0.276 | 274 | 1.000 | 9.442 | 0.762 | 0.213 | 0.333 | 0.689 |
| `ff-interp-block` | mv-lit | `mvlit34-noPCV02Z` | 0.730 | 0.410 | 0.675 | 0.422 | 0.519 | 584 | 1.776 | 34.045 | 0.481 | 0.491 | 0.486 | 0.778 |
| `ff-interp-block-max60-testinf` | mv-lit | `mvlit34-noPCV02Z` | 0.702 | 0.135 | 0.614 | 0.087 | 0.152 | 132 | 0.477 | 23.444 | 0.493 | 0.135 | 0.212 | 0.544 |

- On the full set both FF variants are far worse than rolling. PR-AUC is 0.208 and 0.147 against 0.397, ROC-AUC 0.637 and 0.659 against 0.862, and TaPR F1 0.313 and 0.121 against 0.400.
- `ff-interp-block` alarms on 12,958 test steps: 116.489 false-alarm steps per hour of normal data, against 1.112 for rolling. Its TaR rises (0.580 against 0.270), but it also alarms on 0.324 of all normal test steps (`p_normal`, `segments_summary.csv`), and its TaP falls to 0.215. The bounded `-max60-testinf` alarms less (36.471 per hour) and detects less (recall 0.195, TaR 0.228).
- Each FF run has its own calib threshold: 34.045 and 23.444, against 9.442 for rolling. Those thresholds are set on calib scores that already include fallback (activity table below).
- Without `P1_PCV02Z`, `ff-interp-block` looks different. Its threshold is the same on both sets (34.045), and its false-alarm rate falls from 116.489 to 1.776 per hour. Its PR-AUC (0.410) and TaPR F1 (0.486) are above rolling's on either set (0.345 and 0.333 here, 0.397 and 0.400 on the full set). This gain is not credited to context protection. In 47 of 50 attacks, fallback was already active at onset (next table). FF's extra alarms also fall on attack steps forecast from pre-onset origins, where neither run's context holds attack data: 304 of those 702 steps, against 167 for rolling (`results/phase1/segments_per_attack.csv`, `n_pre_origin` x `cov_pre_origin` summed over attacks). A mostly free-running forecast is a different detector, not a protected rolling forecast. `-noPCV02Z` is not the set the pick uses (D21). `-max60-testinf` does not share the gain (PR-AUC 0.135).

From `results/phase1/segments_summary.csv`: `mvlit34`, band, topk, N 6, stratum all. `n_attacks` counts the attacks in the group; the number in brackets counts those with a non-empty interior, and the interior means are over those. `p_normal` is the run's alarm share on normal scored test steps, which is the reference for a coverage. `interior_chance` is as defined in section 2.6. The last column pools the base rolling run's rows of `results/phase1/segments_per_attack.csv` (same set, score, agg and N) over the same attacks: mean onset / interior / offset coverage.

| variant | ff_group | n_attacks | p_normal | onset_cov_mean | interior_cov_mean | offset_cov_mean | interior_rate | interior_chance | rolling, same attacks (onset / interior / offset) |
|---|---|---|---|---|---|---|---|---|---|
| `ff-interp-block` | all | 50 (47) | 0.324 | 0.527 | 0.574 | 0.427 | 0.809 | 0.910 | 0.263 / 0.295 / 0.080 |
| `ff-interp-block` | pre_active | 47 (44) | 0.324 | 0.553 | 0.595 | 0.454 | 0.818 | 0.904 | 0.273 / 0.282 / 0.064 |
| `ff-interp-block` | triggered_in_attack (A101, A401, A501) | 3 (3) | 0.324 | 0.111 | 0.262 | 0.000 | 0.667 | 0.995 | 0.111 / 0.480 / 0.333 |
| `ff-interp-block` | none | 0 | no row in the file (empty group) | | | | | | |
| `ff-interp-block-max60-testinf` | all | 50 (47) | 0.101 | 0.217 | 0.258 | 0.090 | 0.426 | 0.660 | 0.263 / 0.295 / 0.080 |
| `ff-interp-block-max60-testinf` | pre_active | 42 (39) | 0.101 | 0.234 | 0.255 | 0.091 | 0.385 | 0.655 | 0.274 / 0.260 / 0.040 |
| `ff-interp-block-max60-testinf` | triggered_in_attack (A101, A207, A208, A401, A402, A501, A506) | 7 (7) | 0.101 | 0.143 | 0.308 | 0.095 | 0.714 | 0.704 | 0.238 / 0.532 / 0.333 |
| `ff-interp-block-max60-testinf` | none (A205) | 1 (1) | 0.101 | 0.000 | 0.000 | 0.000 | 0.000 | 0.527 | 0.000 / 0.000 / 0.000 |

- **Interior credit (D44).** `ff-interp-block` earns it on 3 attacks only. Its interior coverage there is 0.262. That is below its own normal-step alarm share (0.324) and below rolling's 0.480 on the same attacks. It detects 2 of the 3 interiors (0.667), against a chance level of 0.995. No interior detection can be credited to FF.
- Two of those three, A101 and A501, lie inside one window issued before onset (`attacks.csv`, `n_windows_10s` = 1). In `ff-interp-block` nothing was in fallback before them, so FF cannot change their forecast (section 3.5). The gap to rolling there comes from FF's higher threshold (34.045 against 9.442, `thresholds.csv`), not from the context. Only A401 has post-onset steps (14), and neither run alarms in its interior.
- `-max60-testinf` earns interior credit on 7 attacks. Its interior coverage there is 0.308, against rolling's 0.532 on the same attacks and its own `p_normal` of 0.101. Its interior detection rate is 0.714, against a chance level of 0.704.
- **pre_active** holds 47 of 50 attacks for `ff-interp-block` and 42 for `-max60-testinf`. The first trigger in every test file falls between steps 162 and 262 (`ff_episodes.csv`; warm-up ends at 150). With no exit, that trigger puts every later attack of the file in this group. The group's coverages (interior 0.595 and offset 0.454, against rolling's 0.282 and 0.064) come from a forecast with at least one channel already free-running before onset, so they are not credited (section 3.5). The offset coverage shows the free run alarming after attacks as well.

From `results/phase1/ff_activity.csv` (one row per split, file and channel; the 34 channels are the scored targets of `mvlit34`) and `results/phase1/ff_episodes.csv`.

- Fallback share = the sum of `fallback_steps` divided by the sum of `scored_steps`, over all files and channels of the split.
- Every trigger opens one episode.
- "Overlapping" means `overlaps_attack_id` is not empty.
- "Started in an attack" means `start_t` (the trigger step) lies within [onset, end + 6] of an attack in the same file. Onset and end come from `attacks.csv` (`history_steps`, `steps_10s`). All other episodes started on normal steps.
- calib holds no attacks.

| variant | split | files | channels with a trigger (of 34) | triggers = episodes | fallback share | exit max_duration | exit file_end | episodes overlapping an attack | started in an attack | started on normal steps |
|---|---|---|---|---|---|---|---|---|---|---|
| `ff-interp-block` | calib | 2 | 30 | 53 | 0.565 | 0 | 53 | - | - | 53 |
| `ff-interp-block` | test | 5 | 34 | 153 | 0.766 | 0 | 153 | 144 | 64 | 89 |
| `ff-interp-block-max60-testinf` | calib | 2 | 30 | 1,181 | 0.123 | 1,178 | 3 | - | - | 1,181 |
| `ff-interp-block-max60-testinf` | test | 5 | 34 | 2,641 | 0.118 | 2,611 | 30 | 463 | 329 | 2,312 |

- **FF free-runs on normal data.** `ff-interp-block` has no exit, so each false trigger keeps that channel in fallback until the file ends. calib holds no attack, yet 30 of 34 channels trigger there and 0.565 of all calib channel-steps run in fallback. In test the share is 0.766, and 89 of the 153 test episodes start on normal steps. The overlap count (144) is inflated by design, because an episode that runs to the file end overlaps every later attack.
- **`P1_PCV02Z` drives the false alarms on the full set.** It never triggers in calib, in any of the four FF runs (0 triggers in train1a and train1b, `ff_activity.csv`). In `ff-interp-block` it triggers once in every test file and then stays in fallback for 0.983, 0.950, 0.704, 0.872 and 0.836 of the scored steps of test1 to test5. Its trigger falls inside A101 (test1) and A402 (test4), both `pcv02d` attacks, and on normal steps in test2, test3 and test5. So the calib threshold never saw a free-running `P1_PCV02Z`. The threshold is the same with and without that channel (34.045, `thresholds.csv`). Removing it from the set cuts the false-alarm rate from 116.489 to 1.776 per hour (`metrics.csv`). Our reading, not measured per channel: a free-running forecast of a channel with a tiny fit std (0.00429 at 10 s, `channels.csv`) gives large z deviations.
- So FF free-runs into false alarms after a trigger, whether the trigger was true or false. On the full set, `ff-interp-block` alarms on 0.324 of normal test steps (`p_normal`, `segments_summary.csv`). The 60-step exit cuts the fallback share to 0.118 and the rate to 36.471 per hour, which is still far above rolling's 1.112. It also opens far more episodes (2,641 in test, 2,312 of them on normal steps), because re-entry needs only 3 new exceedances.

From `results/phase1/ff_thresholds.csv`. `tau` is per channel, in fit-z units of `|q50 - y|`: the 99.5th percentile over the calib steps of the base rolling run (`mv-lit/rolling@c06bc843`). The 34 values are identical in all four FF runs (`ff-interp-block`, `-max60-testinf`, `-max30`, `-max120`).

| run | n_channels | tau_min | tau_median | tau_max |
|---|---|---|---|---|
| `mv-lit` rolling, calib (used by all four FF runs) | 34 | 0.398 (`P1_B4005`) | 2.200 | 4.381 (`P1_PIT01`) |

`P1_PCV02Z` has tau 0.740, the 7th lowest. The full list is in the CSV. The effect of the D128 guard on FF contexts is not measured (section 3.7).

### 4.7 Experiments 3b and 3c: frozen and dual (interpretations)

Base `mv-lit`. Frozen is scored with `band` and dual with its own `dual` score, both with agg `topk` and calib thresholds. Sources: `results/phase1/metrics.csv` (calib_source calib), `thresholds.csv`, `tapr.csv` (config headline) and `segments_summary.csv` (N 6, stratum all, ff_group all). The coverage means are as in section 2.6. `cov_pre_origin_mean` and `cov_post_origin_mean` are attack-step coverage split by whether the forecast origin lies before or after onset. They are averaged over the attacks that have such steps: 50 for pre-onset, 17 for post-onset. Chance: ROC-AUC 0.5, PR-AUC 0.024. Both variants are labelled interpretations (section 3.6).

| variant | channel_set | score | roc_auc | pr_auc | fa_per_hour | threshold | TaPR F1 (headline) | onset_cov_mean | interior_cov_mean | offset_cov_mean | onset_rate / chance | interior_rate / chance | cov_pre_origin_mean | cov_post_origin_mean | latency_censored_median_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `rolling` | `mvlit34` | band | 0.862 | 0.397 | 1.112 | 9.442 | 0.400 | 0.263 | 0.295 | 0.080 | 0.500 / 0.018 | 0.532 / 0.041 | 0.321 | 0.000 | 50 |
| `frozen` | `mvlit34` | band | 0.649 | 0.190 | 3.888 | 60.625 | 0.185 | 0.147 | 0.258 | 0.087 | 0.320 / 0.062 | 0.489 / 0.133 | 0.180 | 0.265 | 120 |
| `dual` | `mvlit34` | dual | 0.570 | 0.082 | 9.057 | 60.902 | 0.091 | 0.063 | 0.091 | 0.117 | 0.120 / 0.140 | 0.298 / 0.274 | 0.046 | 0.301 | 175 |
| `rolling` | `mvlit34-noPCV02Z` | band | 0.864 | 0.345 | 1.000 | 9.442 | 0.333 | 0.257 | 0.236 | 0.050 | 0.480 / 0.016 | 0.489 / 0.037 | 0.265 | 0.000 | 85 |
| `frozen` | `mvlit34-noPCV02Z` | band | 0.663 | 0.192 | 1.271 | 20.984 | 0.262 | 0.120 | 0.241 | 0.093 | 0.280 / 0.021 | 0.511 / 0.046 | 0.149 | 0.302 | 120 |
| `dual` | `mvlit34-noPCV02Z` | dual | 0.544 | 0.036 | 3.430 | 21.679 | 0.077 | 0.003 | 0.038 | 0.043 | 0.020 / 0.055 | 0.213 / 0.118 | 0.002 | 0.242 | 185 |

- **Frozen (3b) loses to rolling on every headline metric, on both sets.** PR-AUC is 0.190 and 0.192 against 0.397 and 0.345. ROC-AUC is 0.649 and 0.663 against 0.862 and 0.864. TaPR F1 is 0.185 and 0.262 against 0.400 and 0.333. Frozen also alarms more on normal data: 3.888 against 1.112 per hour on the full set. Its threshold is 60.625 on the full set and 20.984 without `P1_PCV02Z`, as expected from that channel's known +54 fit-z offset between calib and the reference day (section 3.6).
- A context that never sees test data does not raise mean interior coverage at 10 s. Frozen's interior coverage is lower than rolling's on the full set (0.258 against 0.295) and about the same on `-noPCV02Z` (0.241 against 0.236). Its onset coverage is lower (0.147 against 0.263).
- **Split by forecast origin, frozen catches what rolling misses.** In 17 attacks, 232 attack steps are forecast by rolling from an origin after onset. Rolling raises no alarm on any of them, on either set. On the same steps, frozen raises 50 alarms (full set) and 61 (`-noPCV02Z`), and dual 70 and 50 (`results/phase1/segments_per_attack.csv`, `n_post_origin` x `cov_post_origin` summed over attacks). On the 702 attack steps forecast from pre-onset origins, rolling raises 228 and 167, frozen 133 and 94. Frozen's band is indexed by h on the same window grid, so the two runs are compared at the same h, and frozen gets these alarms despite its higher threshold. This is the pattern that context contamination predicts. It is not a clean test: only 232 steps in 17 longer attacks are involved, and frozen's static band alarms more often on normal steps (`p_normal` 0.011 against 0.003, `segments_summary.csv`). Section 4.4 holds the direct tests (h-matched contrast, cf-onset).
- **Dual (3c) is near chance.** PR-AUC is 0.082 on the full set and 0.036 on `-noPCV02Z`, against 0.024. ROC-AUC is 0.570 and 0.544. Its onset detection rate is at or below chance (0.120 against 0.140; 0.020 against 0.055). By construction it fires only once the rolling forecast moves away from the frozen one: `cov_post_origin_mean` is 0.301 against `cov_pre_origin_mean` 0.046 on the full set, and 0.242 against 0.002 on `-noPCV02Z`. It is late (censored median latency 175 and 185 s, against 50 and 85 s for rolling) and alarms 9.057 and 3.430 times per hour of normal data.
- Dropping `P1_PCV02Z` lowers frozen's false-alarm rate (3.888 to 1.271 per hour) and raises its TaPR F1 (0.185 to 0.262), but leaves its PR-AUC almost unchanged (0.190 to 0.192). For dual, dropping it lowers both the alarm rate and PR-AUC.
- Frozen on the mv base runs with the D128 guard (sections 3.7 and 4.13).

### 4.8 Best of 1-3 (picked on test results)

From `results/phase1/selection.csv`, stage `best`, decided at 2026-10-20T18:12:16. The rule, as written in the file: rolling, ff-interp-block, frozen, dual of base mv-lit on mvlit34, highest test pr_auc (topk; band, dual score for dual), ties by roc_auc. Run keys are shown without the prefix `hai2103-10s/chronos2-29ec376-mps/`.

| stage | candidate_run_key | channel_set | score | agg | pr_auc | roc_auc | rank | selected | note |
|---|---|---|---|---|---|---|---|---|---|
| best | `mv-lit/rolling@c06bc843` | mvlit34 | band | topk | 0.397 | 0.862 | 1 | true | picked on test results |
| best | `mv-lit/ff-interp-block@93cc0822` | mvlit34 | band | topk | 0.208 | 0.637 | 2 | false | picked on test results |
| best | `mv-lit/frozen@401c71db` | mvlit34 | band | topk | 0.190 | 0.649 | 3 | false | picked on test results |
| best | `mv-lit/dual@0201a687` | mvlit34 | dual | topk | 0.082 | 0.570 | 4 | false | picked on test results |
| best | `mv-lit/ff-interp-block-max60-testinf@e25a0539` | mvlit34 | band | topk | 0.147 | 0.659 | | false | reported only, not a candidate (D21, D40); picked on test results |

**Picked on test results.** The best of 1-3 is plain `mv-lit` rolling, which is the base run itself. No context-protection variant beats it on the pick metric. Its lead over the next candidate is 0.189 PR-AUC (0.397 against 0.208), so this pick is not close. The base pick before it was close to a tie: `mv-lit` led `uni` on `mvlit34` by about 0.0001 PR-AUC (0.39707 against 0.39695, stage base). The rule uses the full set. On `-noPCV02Z`, `ff-interp-block` has a higher PR-AUC (0.410, section 4.6) than the selected run. Switching to that set now would be a choice made on test results. The selected run's test numbers are optimistic against the others (section 3.10).

### 4.9 Experiment 5: baselines on the same channel sets

Baselines forecast all 57 channels and are scored on every set a Chronos-2 run uses, with their own thresholds
(D49). Each Chronos-2 row is compared with the baselines on the same set.

Band score, top-3 mean, calib threshold, test split. Sources: `results/phase1/metrics.csv` (calib_source calib),
`tapr.csv` (config headline), `segments_summary.csv` (N 6, stratum all, ff_group all). Chance: ROC-AUC 0.5, PR-AUC
0.024. `p_normal` is each method's alarm rate on normal scored test steps; the detection-rate chance levels (section
2.6) come from it. Chronos-2 rows are the MPS runs; the baselines are `hai2103-10s/baseline/<name>/rolling`.

| method | channel_set | roc_auc | pr_auc | fa_per_hour | TaPR F1 (headline) | p_normal | onset_cov_mean | interior_cov_mean | offset_cov_mean | onset_rate / chance | interior_rate / chance | n_detected (of 50) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Chronos-2 `uni` rolling | `uni51` | 0.894 | 0.401 | 1.224 | 0.398 | 0.003 | 0.280 | 0.290 | 0.083 | 0.520 / 0.020 | 0.553 / 0.045 | 31 |
| `robustz` | `uni51` | 0.708 | 0.171 | 2.991 | 0.324 | 0.008 | 0.167 | 0.264 | 0.107 | 0.340 / 0.048 | 0.447 / 0.104 | 23 |
| `lastvalue` | `uni51` | 0.891 | 0.412 | 2.785 | 0.554 | 0.008 | 0.277 | 0.409 | 0.247 | 0.560 / 0.045 | 0.638 / 0.098 | 36 |
| `seasonal-refday` | `uni51` | 0.748 | 0.395 | 5.178 | 0.384 | 0.014 | 0.463 | 0.504 | 0.200 | 0.700 / 0.082 | 0.766 / 0.171 | 39 |
| Chronos-2 `mv-lit` rolling (base, picked on test results) | `mvlit34` | 0.862 | 0.397 | 1.112 | 0.400 | 0.003 | 0.263 | 0.295 | 0.080 | 0.500 / 0.018 | 0.532 / 0.041 | 30 |
| Chronos-2 `uni` rolling | `mvlit34` | 0.880 | 0.397 | 1.009 | 0.393 | 0.003 | 0.247 | 0.281 | 0.080 | 0.480 / 0.017 | 0.532 / 0.037 | 30 |
| `robustz` | `mvlit34` | 0.694 | 0.142 | 2.935 | 0.230 | 0.008 | 0.120 | 0.234 | 0.103 | 0.240 / 0.047 | 0.362 / 0.103 | 17 |
| `lastvalue` | `mvlit34` | 0.883 | 0.402 | 2.598 | 0.538 | 0.007 | 0.230 | 0.407 | 0.260 | 0.480 / 0.042 | 0.660 / 0.092 | 33 |
| `seasonal-refday` | `mvlit34` | 0.728 | 0.385 | 6.449 | 0.328 | 0.018 | 0.473 | 0.510 | 0.213 | 0.700 / 0.102 | 0.766 / 0.207 | 38 |

- **Chronos-2 does not beat `lastvalue` on the headline score.** On `uni51`, `lastvalue` has the higher PR-AUC
  (0.412 vs 0.401), nearly the same ROC-AUC (0.891 vs 0.894), a much higher TaPR F1 (0.554 vs 0.398), more interior
  coverage (0.409 vs 0.290), and it detects more attacks (36 vs 31). On `mvlit34` it beats the base `mv-lit` on the
  same five (PR-AUC 0.402 vs 0.397, ROC-AUC 0.883 vs 0.862, TaPR F1 0.538 vs 0.400, interior 0.407 vs 0.295, 33 vs
  30 attacks). The PR-AUC gaps (0.011 and 0.005) are small for 50 attacks (section 6.2). The TaPR F1 gaps are not.
- **What Chronos-2 has is fewer false alarms:** 1.224 and 1.112 per hour against 2.785 and 2.598 for `lastvalue`
  (`p_normal` 0.003 against 0.008 and 0.007), and a higher precision at the calib threshold (0.641 vs 0.537 on
  `uni51`, 0.657 vs 0.540 on `mvlit34`, `metrics.csv`). Its chance levels are lower throughout. On `uni51` its
  detection rates are also lower than `lastvalue`'s (onset 0.520 against chance 0.020; `lastvalue` 0.560 against
  0.045). On `mvlit34` the base `mv-lit` has the higher onset rate and coverage (0.500 against chance 0.018, coverage
  0.263; `lastvalue` 0.480 against 0.042, 0.230) but the lower interior rate (0.532 vs 0.660).
- **`robustz` loses clearly** on the band score: PR-AUC 0.171 and 0.142, ROC-AUC 0.708 and 0.694, 23 and 17 attacks
  detected.
- **`seasonal-refday` nearly matches Chronos-2's PR-AUC** (0.395, 0.385) and has the highest onset and interior
  coverage of all methods (0.463-0.473 and 0.504-0.510). But its ROC-AUC is low (0.748, 0.728) and it raises 4.2x and
  5.8x the false alarms (5.178 and 6.449 per hour, `p_normal` 0.014 and 0.018). Part of its coverage is its alarm
  rate.
- **The other two sets** (same files and filters): on `mvacttgt41`, `lastvalue` leads again (PR-AUC 0.416 vs 0.394
  for `mv-acttgt`, TaPR F1 0.560 vs 0.413). On `uni57`, Chronos-2 `uni57` leads (PR-AUC 0.340 vs 0.316 `lastvalue`,
  0.154 `robustz`, 0.150 `seasonal-refday`; TaPR F1 0.328 vs 0.305, 0.306, 0.216). The six step tags cost `lastvalue`
  and `seasonal-refday` more PR-AUC than Chronos-2 (from `uni51` to `uni57`: `lastvalue` 0.412 to 0.316,
  `seasonal-refday` 0.395 to 0.150, Chronos-2 0.401 to 0.340). `robustz` loses less (0.171 to 0.154).

**The band score of a baseline reads its own constructed band** (section 2.8). `robustz` uses a Gaussian band from
the MAD of the trailing hour. `lastvalue` and `seasonal-refday` use empirical quantiles of fit-set changes, fixed per
channel (and per h for `lastvalue`), which do not react to the current context. So `band` compares each method's
point forecast together with its own uncertainty model. `mae` reads only q50, the same yardstick for every method.
`crps` reads all 21 levels, so it also depends on the constructed quantiles. A `robustz` band has zero width on a
channel that was flat over the trailing hour, which gives a band score of deviation / eps there (section 2.5). Its
band threshold is 26.276 on `uni51`, against 6.573 for `lastvalue` and 11.589 for Chronos-2 `uni`
(`thresholds.csv`).

Top-3 mean, calib threshold, by score (`metrics.csv`; TaPR F1 from `tapr.csv`, config headline):

| method | channel_set | pr_auc band / crps / mae | roc_auc band / crps / mae | TaPR F1 (headline) band / crps / mae | fa_per_hour band / crps / mae |
|---|---|---|---|---|---|
| Chronos-2 `uni` rolling | `uni51` | 0.401 / 0.421 / 0.430 | 0.894 / 0.872 / 0.858 | 0.398 / 0.572 / 0.566 | 1.224 / 5.655 / 4.580 |
| `robustz` | `uni51` | 0.171 / 0.367 / 0.367 | 0.708 / 0.838 / 0.842 | 0.324 / 0.626 / 0.604 | 2.991 / 8.263 / 8.375 |
| `lastvalue` | `uni51` | 0.412 / 0.385 / 0.377 | 0.891 / 0.852 / 0.836 | 0.554 / 0.642 / 0.635 | 2.785 / 5.010 / 5.038 |
| `seasonal-refday` | `uni51` | 0.395 / 0.400 / 0.399 | 0.748 / 0.744 / 0.742 | 0.384 / 0.403 / 0.415 | 5.178 / 3.608 / 3.290 |
| Chronos-2 `mv-lit` rolling (base, picked on test results) | `mvlit34` | 0.397 / 0.444 / 0.476 | 0.862 / 0.867 / 0.858 | 0.400 / 0.572 / 0.596 | 1.112 / 4.627 / 3.243 |
| Chronos-2 `uni` rolling | `mvlit34` | 0.397 / 0.414 / 0.428 | 0.880 / 0.866 / 0.857 | 0.393 / 0.584 / 0.571 | 1.009 / 5.748 / 4.608 |
| `robustz` | `mvlit34` | 0.142 / 0.354 / 0.355 | 0.694 / 0.836 / 0.837 | 0.230 / 0.645 / 0.629 | 2.935 / 8.206 / 8.263 |
| `lastvalue` | `mvlit34` | 0.402 / 0.386 / 0.379 | 0.883 / 0.849 / 0.835 | 0.538 / 0.614 / 0.564 | 2.598 / 5.318 / 5.552 |
| `seasonal-refday` | `mvlit34` | 0.385 / 0.388 / 0.388 | 0.728 / 0.724 / 0.723 | 0.328 / 0.375 / 0.384 | 6.449 / 4.309 / 3.692 |

- On these two sets, with `mae` and `crps`, Chronos-2 has the highest PR-AUC (mae: 0.430 vs at most 0.399 on
  `uni51`, 0.476 vs at most 0.388 on `mvlit34`). Here its median separates attack steps better than y(o - 1), the
  trailing-hour median or the reference day. Its band is not a better normalizer than the fit-set change quantiles
  of `lastvalue`.
- That lead does not survive dropping `P1_PCV02Z`. On every `-noPCV02Z` set `robustz` has the highest mae and crps
  PR-AUC: mae 0.544 vs 0.403 for Chronos-2 `uni` (`uni51-noPCV02Z`) and 0.546 vs 0.475 for `mv-lit`
  (`mvlit34-noPCV02Z`); crps 0.544 vs 0.408 and 0.543 vs 0.423 (`metrics.csv`). Its mae threshold is the same on
  both sets (4.253 on `uni51`, `thresholds.csv`), and its mae false alarms fall from 8.375 to 1.720 per hour. So
  `P1_PCV02Z` drives most of `robustz`'s mae false alarms on test, and the mae/crps ranking depends on that one
  channel.
- `robustz` gains most when its band is left out (PR-AUC 0.171 with band, 0.367 with mae, `uni51`). That is
  consistent with the zero-width MAD bands above; it is not measured per channel.
- At the calib threshold, `crps` and `mae` alarm far more often on test than `band` (Chronos-2 `uni`: 5.655 and 4.580
  vs 1.224 per hour). With them the TaPR F1 ranking turns against Chronos-2: `robustz` reaches 0.604-0.645 against
  0.566-0.596. `lastvalue` beats Chronos-2 on TaPR F1 in 5 of the 6 (set, score) pairs; the exception is mae on
  `mvlit34` (0.564 vs 0.596).

**Without `P1_PCV02Z`.** This is not a headline. The `-noPCV02Z` view was fixed before any result, for frozen, dual
and `seasonal-refday` (D50). Same files and filters:

| method | channel_set | roc_auc | pr_auc | fa_per_hour | TaPR F1 (headline) | p_normal | onset_cov_mean | interior_cov_mean | offset_cov_mean | onset_rate / chance | interior_rate / chance | n_detected (of 50) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Chronos-2 `uni` rolling | `uni51-noPCV02Z` | 0.890 | 0.347 | 1.112 | 0.331 | 0.003 | 0.273 | 0.229 | 0.053 | 0.500 / 0.018 | 0.489 / 0.041 | 28 |
| `robustz` | `uni51-noPCV02Z` | 0.692 | 0.151 | 1.505 | 0.279 | 0.004 | 0.160 | 0.200 | 0.067 | 0.320 / 0.025 | 0.340 / 0.055 | 18 |
| `lastvalue` | `uni51-noPCV02Z` | 0.890 | 0.364 | 2.421 | 0.501 | 0.007 | 0.273 | 0.352 | 0.197 | 0.560 / 0.039 | 0.617 / 0.086 | 35 |
| `seasonal-refday` | `uni51-noPCV02Z` | 0.794 | 0.485 | 3.318 | 0.420 | 0.009 | 0.490 | 0.544 | 0.253 | 0.760 / 0.054 | 0.809 / 0.115 | 41 |
| Chronos-2 `mv-lit` rolling (base, picked on test results) | `mvlit34-noPCV02Z` | 0.864 | 0.345 | 1.000 | 0.333 | 0.003 | 0.257 | 0.236 | 0.050 | 0.480 / 0.016 | 0.489 / 0.037 | 28 |
| Chronos-2 `uni` rolling | `mvlit34-noPCV02Z` | 0.877 | 0.346 | 0.897 | 0.322 | 0.002 | 0.240 | 0.217 | 0.050 | 0.460 / 0.015 | 0.468 / 0.033 | 27 |
| `robustz` | `mvlit34-noPCV02Z` | 0.676 | 0.105 | 1.281 | 0.189 | 0.004 | 0.113 | 0.169 | 0.063 | 0.220 / 0.021 | 0.255 / 0.047 | 12 |
| `lastvalue` | `mvlit34-noPCV02Z` | 0.883 | 0.349 | 2.234 | 0.482 | 0.006 | 0.223 | 0.345 | 0.210 | 0.460 / 0.036 | 0.638 / 0.079 | 32 |
| `seasonal-refday` | `mvlit34-noPCV02Z` | 0.780 | 0.475 | 5.374 | 0.330 | 0.015 | 0.517 | 0.552 | 0.250 | 0.800 / 0.085 | 0.809 / 0.177 | 43 |

- Only `seasonal-refday` gains band-score PR-AUC without `P1_PCV02Z`: 0.395 to 0.485 (`uni51`) and 0.385 to 0.475
  (`mvlit34`). Its ROC-AUC goes 0.748 to 0.794 and 0.728 to 0.780, and its false alarms 5.178 to 3.318 and 6.449 to
  5.374 per hour. Chronos-2, `lastvalue` and `robustz` all lose PR-AUC (`uni` 0.401 to 0.347, `lastvalue` 0.412 to
  0.364).
- What drives it: `P1_PCV02Z` sits about +54 fit-z above the reference day in calib and in the test files before
  the A302/A512 level shifts (section 3.6), and `seasonal-refday` compares every file with that day. The offset sits
  in its calib top-3 score: without `P1_PCV02Z` its calib threshold falls from 5.409 to 0.828 (`uni51`) and from
  5.354 to 0.717 (`mvlit34`), while the thresholds of Chronos-2, `lastvalue` and `robustz` do not change
  (`thresholds.csv`). Pooled per test file from `segments_per_attack.csv` (mean over the file's attacks, `uni51`,
  N 6), most of the gain sits in test3, the file where `P1_PCV02Z` drops to the reference-day level after A302:
  interior coverage 0.474 to 0.738, attacks detected 6 to 8 of 8. A303 and A308 are detected only without
  `P1_PCV02Z`. test4 gains less (0.521 to 0.574, 5 of 5 detected both ways). test1, test2 and test5 do not gain
  (interior coverage 0.743 to 0.743, 0.370 to 0.378, 0.628 to 0.571). So the full-set `seasonal-refday` score
  partly measures which `P1_PCV02Z` level a file sits at.
- The rolling methods track the level, and for them `P1_PCV02Z` carries attack signal: without it, the interior
  coverage of Chronos-2 `uni` falls in test1 (0.305 to 0.133) and test4 (0.296 to 0.106) (same pooling).
- On this restricted view `seasonal-refday` beats Chronos-2 on PR-AUC (0.485 vs 0.347 for `uni`, 0.475 vs 0.345 for
  `mv-lit`) and on coverage, and on TaPR F1 on `uni51-noPCV02Z` (0.420 vs 0.331; 0.330 vs 0.333 on
  `mvlit34-noPCV02Z`), at 3.0x and 5.4x the false alarms per hour. The view drops one channel because of a known
  offset; it is reported, not used as a headline.

**Verdict.** On the headline score Chronos-2 does not beat the simplest baseline. `lastvalue` has the higher PR-AUC
on three of the four channel sets and a higher TaPR F1 on the same three; Chronos-2 leads only on `uni57`. Chronos-2
beats `robustz` on every band-score AUC and has the fewest false alarms of all methods on `uni51` and `mvlit34`. On
those two sets it also has the highest mae and crps PR-AUC, but `robustz` takes that lead once `P1_PCV02Z` is
dropped. At the calib threshold, `lastvalue` has the higher TaPR F1 in 5 of the 6 (set, score) pairs on `uni51` and
`mvlit34`.

### 4.10 Optional 10 s runs: prepend warm-up and FF max-duration sensitivity

Both on the base setup. Prepend joins recordings made 10 to 34 days apart at the junction (section 2.2). The max30
and max120 runs are reported without a pick (D25).

Base `mv-lit` on `mvlit34`, band, topk, calib thresholds. Metrics and thresholds come from `results/phase1/metrics.csv` and `thresholds.csv`, TaPR F1 from `tapr.csv` (config headline), and segments from `segments_summary.csv` (N 6, stratum all, ff_group all). The last column uses the triggered_in_attack group instead, with the number of its attacks that have an interior. Chance: ROC-AUC 0.5, PR-AUC 0.024. No row here is picked (D25), and `prepend` is not a pick candidate either.

| variant | channel_set | roc_auc | pr_auc | fa_per_hour | threshold | TaPR F1 (headline) | onset_cov_mean | interior_cov_mean | offset_cov_mean | p_normal | interior_cov_mean, triggered_in_attack (attacks with an interior) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `rolling` (in-file) | `mvlit34` | 0.862 | 0.397 | 1.112 | 9.442 | 0.400 | 0.263 | 0.295 | 0.080 | 0.003 | |
| `prepend` | `mvlit34` | 0.867 | 0.404 | 0.907 | 9.006 | 0.378 | 0.267 | 0.274 | 0.053 | 0.003 | |
| `ff-interp-block` (no exit) | `mvlit34` | 0.637 | 0.208 | 116.489 | 34.045 | 0.313 | 0.527 | 0.574 | 0.427 | 0.324 | 0.262 (3) |
| `ff-interp-block-max30` | `mvlit34` | 0.753 | 0.175 | 21.236 | 17.555 | 0.161 | 0.200 | 0.278 | 0.150 | 0.059 | 0.255 (9 of 11) |
| `ff-interp-block-max60-testinf` | `mvlit34` | 0.659 | 0.147 | 36.471 | 23.444 | 0.121 | 0.217 | 0.258 | 0.090 | 0.101 | 0.308 (7) |
| `ff-interp-block-max120` | `mvlit34` | 0.560 | 0.090 | 97.655 | 25.856 | 0.135 | 0.260 | 0.346 | 0.273 | 0.271 | 0.313 (6) |

The next table shows FF activity and attribution in test, from `ff_activity.csv`, `ff_episodes.csv` and `segments_summary.csv`. Fallback share and "started on normal steps" are defined as in section 4.6. The last column pools the base rolling run's rows of `segments_per_attack.csv` over the same triggered_in_attack attacks that have an interior.

| variant | max_duration (steps) | test fallback share | test episodes (started on normal steps) | pre_active / triggered_in_attack / none | interior_cov_mean, triggered_in_attack | rolling interior_cov, same attacks |
|---|---|---|---|---|---|---|
| `ff-interp-block` | none | 0.766 | 153 (89) | 47 / 3 / 0 | 0.262 | 0.480 |
| `ff-interp-block-max30` | 30 | 0.067 | 3,025 (2,669) | 39 / 11 / 0 | 0.255 | 0.399 |
| `ff-interp-block-max60-testinf` | 60 | 0.118 | 2,641 (2,312) | 42 / 7 / 1 | 0.308 | 0.532 |
| `ff-interp-block-max120` | 120 | 0.163 | 1,834 (1,543) | 44 / 6 / 0 | 0.313 | 0.573 |

- **Prepend changes little.** Against in-file rolling:
  - PR-AUC 0.404 against 0.397, ROC-AUC 0.867 against 0.862.
  - False alarms 0.907 against 1.112 per hour; TaPR F1 0.378 against 0.400.
  - Interior coverage 0.274 against 0.295; offset coverage 0.053 against 0.080.
  - On the 232 attack steps forecast from post-onset origins, prepend raises 1 alarm and rolling 0 (`segments_per_attack.csv`).

  A long clean history before each file does not change detection at 10 s. The small PR-AUC gain is no reason to prefer prepend; choosing it now would be a pick on test results. The effect of the D128 guard on its contexts is not measured (section 3.7).
- **No max duration rescues FF.** All four FF variants are below rolling on ROC-AUC, PR-AUC and TaPR F1. All of them alarm far more on normal data: 21.236, 36.471, 97.655 and 116.489 per hour for 30, 60 and 120 steps and no exit, against 1.112 for rolling. The false-alarm rate grows with the allowed fallback length. PR-AUC does not (0.175, 0.147, 0.090, 0.208).
- Shorter episodes mean more of them. `-max30` opens 3,025 test episodes, 2,669 of them on normal steps, and still keeps 0.067 of test channel-steps in fallback.
- **No variant earns interior credit.** On its triggered_in_attack attacks, every variant covers less of the interior than rolling does on the same attacks: 0.255 to 0.313 for FF, against 0.399 to 0.573 for rolling. Each group is small (3 to 11 attacks).
- `-max30` and `-max120` are half and double the test-informed 60 (section 3.5).

### 4.11 Size and latency (experiment 4 deferred)

Experiment 4 is not run (section 7). After the first report, `autogluon/chronos-2-small` (28M) ran experiment 1 `uni`
rolling as a size sensitivity (D136, section 4.18), so `size_latency.csv` has two Chronos-2 sizes for `uni` and one
for the selected `mv-lit`.

Seconds per forecast call on MPS from `results/phase1/latency.csv`: test split (`ref` for frozen); the calib and calib2 rows are in the same file. Per-call seconds exclude system sleep (D80). T is the context length the model read. `rows_per_call` is the median over calls. Every `uni` call has 51 rows and every `uni57` call 57. An mv call is one process group with 30 (P1), 10 (P2) or 5 (P3) rows, targets plus covariates (section 2.1, D80), so the mv median is 10 and the mv seconds mix three group sizes. Each cell gives n_calls; sec_median; sec_p90.

| run (setup / variant) | split | rows_per_call (median) | T 1-512 | T 513-2048 | T 2049-8192 |
|---|---|---|---|---|---|
| `uni / rolling` | test | 51 | 65; 0.122; 0.164 | 255; 0.405; 0.590 | 995; 1.770; 2.599 |
| `uni57 / rolling` | test | 57 | 65; 0.133; 0.183 | 255; 0.445; 0.648 | 995; 1.939; 2.868 |
| `uni / cf-onset` | test | 51 | 4; 0.106; 0.135 | 10; 0.447; 0.591 | 36; 1.963; 2.601 |
| `mv-lit / rolling` | test | 10 | 195; 0.032; 0.089 | 765; 0.094; 0.289 | 2,985; 0.372; 1.380 |
| `mv-lit / cf-onset` | test | 10 | 12; 0.034; 0.074 | 30; 0.112; 0.332 | 108; 0.392; 1.487 |
| `mv-acttgt / rolling` | test | 10 | 195; 0.032; 0.089 | 765; 0.094; 0.290 | 2,985; 0.373; 1.381 |
| `mv-lit / ff-interp-block` | test | 10 | 195; 0.032; 0.090 | 765; 0.094; 0.290 | 2,985; 0.373; 1.380 |
| `mv-lit / ff-interp-block-max60-testinf` | test | 10 | 195; 0.032; 0.090 | 765; 0.094; 0.291 | 2,985; 0.373; 1.387 |
| `mv-lit / ff-interp-block-max30` | test | 10 | 195; 0.032; 0.089 | 765; 0.094; 0.288 | 2,985; 0.373; 1.390 |
| `mv-lit / ff-interp-block-max120` | test | 10 | 195; 0.032; 0.089 | 765; 0.094; 0.290 | 2,985; 0.373; 1.382 |
| `mv-lit / frozen` | ref | 10 | no calls | no calls | 3; 0.550; 1.618 |
| `mv-lit / prepend` | test | 10 | no calls | no calls | 3,945; 0.547; 1.489 |

- Cost grows with T and with rows. In the top bucket a `uni` call takes 1.770 s (median) and a `mv-lit` call 0.372 s. A `mv-lit` origin needs three calls, so per origin the two cost about the same: their test splits cover the same 1,315 origins in 1,857.8 s (`uni`) and 1,726.0 s (`mv-lit`) of wall-clock (`runs.csv`).
- `prepend` always reads T = 8,192 (section 2.2) and takes 0.547 s per call. In-file `mv-lit` calls in the same bucket take 0.372 s, but their T ranges from 2,049 to 8,192.
- The FF variants cost the same as `mv-lit` rolling. cf-onset calls cost more in the same bucket (1.963 against 1.770 s for `uni`, 0.392 against 0.372 s for `mv-lit`). They forecast up to 49 steps instead of 30, with up to 4 output patches instead of 2 (section 3.6), and their context lengths within the bucket differ from the rolling ones. The file does not separate these causes.
- Because the top bucket spans T = 2,049 to 8,192, its p90 is far above its median (1.380 against 0.372 s for `mv-lit`).
- There is no 1 s latency: the 1 s block was not run (D134).

From `results/phase1/size_latency.csv`: two Chronos-2 sizes for `uni` (D136). `selected` = the best-of-1-3 pick, `mv-lit` rolling (picked on test results, `selection.csv` stage `best`); the other row is the unselected `uni` rolling. `sec_per_call_median` is the median over all test calls of the run, and `test_wallclock_s` comes from `runs.csv`.

| model | params | device | setup | variant | channel_set | selected | sec_per_call_median | test_wallclock_s | roc_auc | pr_auc | tapr_f1 | onset_cov_mean | interior_cov_mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chronos2-29ec376-mps | 119,477,664 | mps | mv-lit | rolling | mvlit34 | true | 0.314 | 1,726.0 | 0.862 | 0.397 | 0.400 | 0.263 | 0.295 |
| chronos2-29ec376-mps | 119,477,664 | mps | uni | rolling | uni51 | false | 1.268 | 1,857.8 | 0.894 | 0.401 | 0.398 | 0.280 | 0.290 |
| chronos2-small-ddec013-mps | 27,934,624 | mps | uni | rolling | uni51 | false | 0.344 | 499.5 | 0.876 | 0.391 | 0.393 | 0.280 | 0.290 |

- Two sizes of one model family on one setup: the 4x smaller model is 3.7x faster per call and close in accuracy (section 4.18). That is not experiment 4 (Timestral sizes, deferred, section 7).
- The two rows use different channel sets (`mvlit34` against `uni51`), so the accuracy columns are not a matched comparison; that comparison is in section 4.2.
- A `mv-lit` call forecasts one process group, and three calls make one origin. Its lower seconds per call (0.314 against 1.268) is therefore not a 4x lower cost: its test split took 1,726.0 s against 1,857.8 s for the same 1,315 origins.

### 4.12 Figures

Drawn by `tsfm-ad plot` from the cache and the CSVs, for the base setup's methods (rolling, ff-interp-block,
ff-interp-block-max60-testinf in the summary figures, frozen, dual, three baselines). The timeline attacks and their
signals were fixed from duration, process and the PDF control loops before any result (D33, D55).

All nine files exist in `results/phase1/figures/`; each was opened and checked after the run. `tsfm-ad plot` read the base from `selection.csv` (log line `plots: base setup mv-lit, from selection.csv`). So every figure is drawn for the base setup **`mv-lit`** (picked on test results, section 4.3), and the baselines are scored on its set `mvlit34`.

Each timeline runs from 30 min before onset to 30 min after the end. It shows the `mv-lit` rolling median and q05-q95 band on the signals that are `mv-lit` targets. Below them are the scores of `mv-lit` rolling, ff-interp-block, frozen, dual (dual score), robustz, lastvalue and seasonal-refday, each with its calib threshold (dashed, symlog axis; the values match `thresholds.csv`). The per-attack notes come from `segments_per_attack.csv` (`mvlit34`, band or dual score, top-3, N = 6). ff-interp-block is `pre_active` on all six timeline attacks, so none of its interior alarms there is credited (section 3.5).

| figure | content (base setup `mv-lit`) | what it shows |
|---|---|---|
| `results/phase1/figures/timeline_A202.png` | A202, the longest attack (422 s, 43 steps), P1, test2, P1-PC-SP1PV1; `P1_PIT01`, `P1_PCV01D` (covariate, not scored in `mv-lit`), `P1_B2016` | No method alarms in the 6 onset steps. `mv-lit` rolling alarms only on interior steps 7-12 (first alarm 60 s after onset; 6 of 37 interior steps), all forecast from a pre-onset origin. None of the 31 steps scored from post-onset origins alarms. The other methods shown cover 0.351 (robustz) to 1.000 (seasonal-refday) of the interior (ff-interp-block 0.405, not credited). |
| `results/phase1/figures/timeline_A210.png` | A210, 421 s (43 steps), P1, test2, P1-PC-CO1PV1; `P1_PIT01`, `P1_PCV01D` (not scored in `mv-lit`) | Missed by every method shown: no alarm in onset, interior or offset. 37 of the 43 `mv-lit` rolling steps are scored from post-onset origins; its score stays below its threshold (9.44) over the whole window. |
| `results/phase1/figures/timeline_A403.png` | A403, 263 s (27 steps), P1 + P3, test4; `P1_LIT01`, `P1_LCV01D` (not scored in `mv-lit`), `P3_LIT01` | `mv-lit` rolling: first alarm 40 s after onset, onset coverage 0.333, interior coverage 0.286 (6 of 21). Every alarmed step comes from a pre-onset origin; 0 of the 9 post-onset steps alarm. The ff-interp-block score sits near its threshold (34) on normal data through the whole window. |
| `results/phase1/figures/timeline_A217.png` | A217, the longest P2-only attack (184 s, 19 steps), test2, turbine trip (stratum `trip`); `P2_SIT01`, `P2_VYT02` | No method alarms in the onset. All of them alarm late in the interior, first at 150 s (dual at 180 s; ff-interp-block's alarms are not credited). `mv-lit` rolling covers 3 of 13 interior steps; 18 of its 19 steps come from a pre-onset origin. After the attack, the `mv-lit` band of `P2_SIT01` widens to several hundred z for about 5 minutes. |
| `results/phase1/figures/timeline_A219.png` | A219, P3-only (119 s, 13 steps), test2, P3-LC-CO1; `P3_LIT01`, `P3_LCP01D` (not scored in `mv-lit`) | Missed by `mv-lit` rolling, frozen, dual and the three baselines. Only ff-interp-block alarms, on 1 of 7 interior steps. A219 is in its `pre_active` group, so that alarm is not credited (section 3.5). All 13 `mv-lit` rolling steps come from a pre-onset origin. |
| `results/phase1/figures/timeline_A203.png` | A203, the shortest attack (17 s, 3 steps; empty interior at 10 s), P1, test2; `P1_LIT01`, `P1_LCV01D` (not scored in `mv-lit`) | No method shown alarms inside the attack; ff-interp-block and seasonal-refday alarm only in the offset. `mv-lit` rolling stays below its threshold over the whole window. |
| `results/phase1/figures/boundary_interior.png` | Top: mean coverage per segment (onset, interior, interior_eq, offset). Bottom: detection rate (attacks with any alarm in the segment), with the chance level 1-(1-p)^n as a black mark. Eight methods: `mv-lit` rolling, ff-interp-block, ff-interp-block-max60-testinf, frozen, dual and the three baselines, all on `mvlit34`, N = 6, band score (dual score for dual), top-3, calib threshold | Read each bar against its own mark. ff-interp-block alarms on 0.324 of normal test steps (`p_normal`, `segments_summary.csv`), so its marks sit at 0.900-0.910, above its detection rates (0.720 onset, 0.809 interior). ff-interp-block-max60-testinf (p 0.101) is also below its chance level in all four segments, and dual is below its chance level in the onset (0.120 against 0.140). `uni` rolling and the optional runs (prepend, FF max30 and max120) are not drawn; their rows are in `segments_summary.csv`. |
| `results/phase1/figures/boundary_interior_origin.png` | Top: interior coverage by forecast-origin side (light = pre-onset origin, solid = post-onset origin) in each h bucket, pooled over the time-since-onset buckets by step count. One panel per method of the figure above, `mvlit34`, N = 6. Interior steps pre / post per bucket: 44 / 143 (h 1-10), 174 / 67 (h 11-20), 188 / 21 (h 21-30). Bottom: cf-onset against rolling, mean band score (top-3) of interior steps in three groups (pre-onset origin, 406 steps; post-onset origin, 231; post-onset with h_cf <= 30, 192), for `mv-lit` (`mvlit34`) and `uni` (`uni51`) | The `mv-lit` rolling panel has no solid bars because they are zero, not because data is missing: none of its 231 post-onset interior steps alarms (`segments_by_h.csv`). The rolling bars on post-onset steps in the cf panels are near zero, not missing: mean score 0.459 (`mv-lit`) and 0.824 (`uni`), against 41.5 and 47.9 for cf-onset (`cf_onset.csv`, pooled over attacks by step count). cf-onset is a diagnostic, not a detector (section 3.6). In each cf panel the two right-hand tick labels overlap (cosmetic). |
| `results/phase1/figures/size_latency.png` | Test ROC-AUC (left) and PR-AUC (right) against the median seconds per forecast call (log axis), from `size_latency.csv`: `mv-lit` rolling (selected on test results; 119M) and `uni` rolling (unselected) at 28M and 119M, labelled by parameter count | The dashed `uni` line is the only size comparison (D136, section 4.18; not experiment 4). The `mv-lit` point uses another channel set (`mvlit34`). The y-axes span only 0.862-0.894 and 0.391-0.401, which makes small gaps look large. A `mv-lit` call is one process group, three per origin, so its lower seconds per call is not a lower cost per origin (section 4.11). |



A timeline draws the median and q05-q95 band only where the signal is a scored target of the setup; elsewhere it
draws the raw signal, labelled `not scored in <setup>` (for example `P1_PCV01D` is a covariate in `mv-lit`).

### 4.13 Size of the D128 guard on the MPS runs

MPS rows of `results/phase1/d128_effect.csv` (model `chronos2-29ec376-mps`, device mps; the hashes are those of
`runs.csv`). dq = |adapter - raw model| in fit-z. The `share_dq` columns are over all (channel, h, level) values of
the split (forecasts x 21); `share_dband_gt_1` is over all forecasts of the split, with the count in brackets. The
guard is an INTERPRETATION (D128, section 3.7).

| run (setup / variant @hash8) | split | calls | calls_const | forecasts_rerun | max_dq, z (channel) | share_dq_gt_0.01 | share_dq_gt_0.1 | share_dq_gt_1 | max_dq_q05_q50_q95, z (channel) | max_dband | share_dband_gt_1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| uni / rolling @47703ec2 | calib | 566 | 71 | 6,360 | 6.6e-7 (`P1_B4005`) | 0 | 0 | 0 | 6.0e-8 (`P1_B4005`) | 1.4e-5 | 0 |
| uni / rolling @47703ec2 | calib2 | 566 | 338 | 20,760 | 6.6e-7 (`P1_B4005`) | 0 | 0 | 0 | 6.0e-8 (`P1_FCV02D`) | 3.4e-8 | 0 |
| uni / rolling @47703ec2 | test | 1,315 | 16 | 540 | 6.6e-7 (`P1_FCV02D`) | 0 | 0 | 0 | 6.0e-8 (`P1_FCV02D`) | 9.2e-6 | 0 |
| uni / cf-onset @6895546b | test | 50 | 3 | 65 | 1.8e-7 (`P1_FCV02D`) | 0 | 0 | 0 | 6.0e-8 (`P1_FCV02D`) | 1.1e-5 | 0 |
| mv-lit / rolling @c06bc843 | calib | 1,698 | 85 | 53,550 | 10.060 (`P1_FT02`) | 0.71 % | 0.010 % | 0.00035 % | 0.411 (`P1_FT02`) | 0.214 | 0 |
| mv-lit / rolling @c06bc843 | calib2 | 1,698 | 338 | 212,940 | 33,275 (`P1_B4005`) | 2.2 % | 0.029 % | 0.00076 % | 41.447 (`P1_B4005`) | 0.160 | 0 |
| mv-lit / rolling @c06bc843 | test | 3,945 | 201 | 126,630 | 65.398 (`P1_PCV02Z`) | 0.41 % | 0.022 % | 0.0031 % | 25.547 (`P1_PCV02Z`) | 3.436 | 0.00022 % (3) |
| mv-lit / cf-onset @225de558 | test | 150 | 8 | 4,809 | 4,898 (`P1_FT02`) | 0.60 % | 0.078 % | 0.030 % | 43.718 (`P1_PIT02`) | 6.322 | 0.014 % (6) |
| mv-acttgt / rolling @7fc275e9 | calib | 1,698 | 85 | 66,300 | 10.060 (`P1_FT02`) | 0.67 % | 0.0094 % | 0.00037 % | 0.411 (`P1_FT02`) | 0.214 | 0 |
| mv-acttgt / rolling @7fc275e9 | test | 3,945 | 201 | 156,780 | 65.397 (`P1_PCV02Z`) | 0.39 % | 0.020 % | 0.0027 % | 25.547 (`P1_PCV02Z`) | 3.436 | 0.00019 % (3) |
| mv-lit / frozen @401c71db | ref | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a (no observed window) | n/a |

- Univariate: the moves are at float32 rounding level.
- Multivariate: the guard re-runs the whole P1 call, so 9.4 % of the `mv-lit` test forecasts (126,630 of 1,341,300)
  can change. The largest moves are on the outer levels and in short early-file contexts. The maxima sit at origin
  480 (test1), 630 (train1b) and 660 (train2b), and for cf-onset at A501's onset (test5, origin 156). On q05/q50/q95,
  which the band score and FF read, the largest move is 25.5 z on test, 0.411 z on calib and 41.4 z on calib2
  (`P1_B4005`). Over all 21 levels it reaches 33,275 z on calib2 (`P1_B4005`), an exploding outer level (section
  4.15).
- The bound on band-score thresholds and aggregated band scores is in section 3.7: at most 0.214 on calib and 3.44
  on test. No such bound is measured for crps or mae.

Test rows of `results/phase1/d128_effect_channels.csv` at the MPS hashes. For `mv-lit`: the union of the five
largest `max_dq_q05_q50_q95` and the five largest `max_dband`, sorted by `max_dq_q05_q50_q95`. For `mv-acttgt`: the
two of its five actuator-command targets with the largest moves. Its other 21 targets match `mv-lit` within 6.1e-4 z
in `max_dq` and 1.1e-4 in `max_dband` (same file). `share_dq_gt_0.1` is over the channel's re-run values
(forecasts_rerun x 21). `max_dq_band` is the largest move of any level in band widths (q95 - q05 + eps).

| run | split | channel | forecasts_rerun | max_dq | max_dq_q05_q50_q95 | share_dq_gt_0.1 | max_dq_band | max_dband |
|---|---|---|---|---|---|---|---|---|
| mv-lit / rolling | test | `P1_PCV02Z` | 6,030 | 65.398 | 25.547 | 2.1 % | 2.411 | 3.436 |
| mv-lit / rolling | test | `P1_PIT01` | 6,030 | 6.024 | 0.981 | 0.71 % | 0.608 | 0.092 |
| mv-lit / rolling | test | `P1_LCV01Z` | 6,030 | 1.383 | 0.728 | 0.49 % | 0.532 | 0.228 |
| mv-lit / rolling | test | `P1_FT01Z` | 6,030 | 1.010 | 0.416 | 0.48 % | 0.196 | 0.315 |
| mv-lit / rolling | test | `P1_PIT02` | 6,030 | 0.634 | 0.266 | 0.55 % | 1.457 | 0.154 |
| mv-lit / rolling | test | `P1_FT01` | 6,030 | 0.520 | 0.212 | 0.21 % | 0.138 | 0.472 |
| mv-lit / rolling | test | `P1_FT02` | 6,030 | 0.145 | 0.051 | 0.017 % | 0.490 | 0.335 |
| mv-lit / rolling | test | `P1_B400B` | 6,030 | 0.111 | 0.047 | 0.00079 % | 0.351 | 0.447 |
| mv-lit / rolling | test | `P1_FT02Z` | 6,030 | 0.097 | 0.045 | 0 | 0.346 | 0.410 |
| mv-acttgt / rolling | test | `P1_LCV01D` | 6,030 | 1.490 | 0.571 | 0.30 % | 0.691 | 0.259 |
| mv-acttgt / rolling | test | `P1_FCV02D` | 6,030 | 0.477 | 0.403 | 0.21 % | 0.711 | 0.134 |

- Every re-run channel is a P1 target (21 in `mv-lit`, 26 in `mv-acttgt`), each on 6,030 forecasts = 201 calls x 30
  steps.
- `P1_PCV02Z` stands out: 2.1 % of its re-run values move by more than 0.1 z, its levels by up to 2.4 band widths,
  its band score by up to 3.44. Every other channel's band score moves by less than 0.48. `P1_PCV02Z` has the tiny
  fit std (0.00429 at 10 s, `channels.csv`), so small raw differences are large in fit-z.

Not measured: the FF runs (D129) and `uni57` (univariate: the guard can move only its constant rows, which are
forecast independently of the others, section 2.3). The prepend run passed no constant row (`quantile_diagnostics.csv`,
`const_rows` 0), so the guard never acted on it.

### 4.14 Quantile crossing rate of the full runs (D119)

`results/phase1/quantile_diagnostics.csv` (D133) sums the per-call counts of the cache's `calls_<split>.csv` per run
and split. It was written after the run from the cache, with no inference. `crossed` counts the (channel, h)
forecasts whose 21 raw levels were not monotone and were sorted (D119); `const_rows` counts the target and covariate
rows the D128 guard passed as exact zeros.

From `results/phase1/quantile_diagnostics.csv` (D133), MPS rows, one per run, hash8 and split. The input rows (the
target and covariate rows passed to the model, the denominator of `const_rows`) are summed from the `rows` column of
each run's `cache/hai2103-10s/chronos2-29ec376-mps/<setup>/<variant>@<hash8>/calls_<split>.csv`: 51 per call for
`uni`, 57 for `uni57`, 45 per origin over the three P1-P3 calls of the mv setups.

| run (setup / variant @hash8) | split | calls | forecasts | crossed | crossed share | input rows | const_rows | const share |
|---|---|---|---|---|---|---|---|---|
| uni / rolling @47703ec2 | calib | 566 | 865,980 | 171,905 | 19.9 % | 28,866 | 212 | 0.73 % |
| uni / rolling @47703ec2 | calib2 | 566 | 865,980 | 137,379 | 15.9 % | 28,866 | 692 | 2.4 % |
| uni / rolling @47703ec2 | test | 1,315 | 2,011,950 | 426,162 | 21.2 % | 67,065 | 18 | 0.027 % |
| uni57 / rolling @98048bbf | calib | 566 | 967,860 | 259,215 | 26.8 % | 32,262 | 1,630 | 5.1 % |
| uni57 / rolling @98048bbf | test | 1,315 | 2,248,650 | 635,927 | 28.3 % | 74,955 | 1,614 | 2.2 % |
| uni / cf-onset @6895546b | test | 50 | 62,934 | 13,693 | 21.8 % | 2,550 | 3 | 0.12 % |
| mv-lit / rolling @c06bc843 | calib | 1,698 | 577,320 | 106,888 | 18.5 % | 25,470 | 544 | 2.1 % |
| mv-lit / rolling @c06bc843 | calib2 | 1,698 | 577,320 | 68,292 | 11.8 % | 25,470 | 1,956 | 7.7 % |
| mv-lit / rolling @c06bc843 | test | 3,945 | 1,341,300 | 273,685 | 20.4 % | 59,175 | 468 | 0.79 % |
| mv-acttgt / rolling @7fc275e9 | calib | 1,698 | 696,180 | 138,611 | 19.9 % | 25,470 | 544 | 2.1 % |
| mv-acttgt / rolling @7fc275e9 | test | 3,945 | 1,617,450 | 344,611 | 21.3 % | 59,175 | 468 | 0.79 % |
| mv-lit / cf-onset @225de558 | test | 150 | 41,956 | 9,063 | 21.6 % | 2,250 | 20 | 0.89 % |
| mv-lit / frozen @401c71db | ref | 3 | 1,020 | 272 | 26.7 % | 45 | 0 | 0 |
| mv-lit / ff-interp-block @93cc0822 | calib | 1,698 | 577,320 | 176,509 | 30.6 % | 25,470 | 544 | 2.1 % |
| mv-lit / ff-interp-block @93cc0822 | test | 3,945 | 1,341,300 | 592,060 | 44.1 % | 59,175 | 468 | 0.79 % |
| mv-lit / ff-interp-block-max60-testinf @e25a0539 | calib | 1,698 | 577,320 | 82,136 | 14.2 % | 25,470 | 544 | 2.1 % |
| mv-lit / ff-interp-block-max60-testinf @e25a0539 | test | 3,945 | 1,341,300 | 227,615 | 17.0 % | 59,175 | 468 | 0.79 % |
| mv-lit / ff-interp-block-max30 @3878b398 | calib | 1,698 | 577,320 | 98,580 | 17.1 % | 25,470 | 544 | 2.1 % |
| mv-lit / ff-interp-block-max30 @3878b398 | test | 3,945 | 1,341,300 | 242,632 | 18.1 % | 59,175 | 468 | 0.79 % |
| mv-lit / ff-interp-block-max120 @77efffc9 | calib | 1,698 | 577,320 | 73,130 | 12.7 % | 25,470 | 544 | 2.1 % |
| mv-lit / ff-interp-block-max120 @77efffc9 | test | 3,945 | 1,341,300 | 239,207 | 17.8 % | 59,175 | 468 | 0.79 % |
| mv-lit / prepend @d9b7cc2f | calib | 1,698 | 577,320 | 128,994 | 22.3 % | 25,470 | 0 | 0 |
| mv-lit / prepend @d9b7cc2f | test | 3,945 | 1,341,300 | 289,904 | 21.6 % | 59,175 | 0 | 0 |

- Crossings are common in every run. Between 11.8 % (`mv-lit` calib2) and 44.1 % (`ff-interp-block` test) of the
  (channel, h) forecasts had at least one crossed pair among the 21 raw levels and were sorted. The headline rolling
  runs (`uni`, `mv-lit`, `mv-acttgt`) sit at 18.5-21.3 % on calib and test, at the top of the 7.3-21 % of the pre-run
  CPU sample (section 3.8).
- The six step tags of `uni57` cross in 85.7 % (calib) and 88.6 % (test) of their forecasts, and 41.8 % (calib) and
  20.2 % (test) of their input rows are constant. These are `uni57` minus `uni` counts. The subtraction holds because
  the 51 shared channels are forecast independently (section 2.3) and score identically in both runs to full
  precision (`metrics.csv`, `uni51` rows).
- `ff-interp-block` (no exit) crosses 1.7x (calib) and 2.2x (test) as often as its rolling base. The bounded FF runs
  cross less often than the base (12.7-18.1 %). The file does not show why.
- The D128 guard zeroed 0.027 % of the `uni` test input rows and 0.79 % of the mv test input rows (2.1 % on calib,
  7.7 % on `mv-lit` calib2). Prepend and frozen passed no constant row, so the guard never acted on them.
- Not in the file: how far sorting moved q05 and q95. The only size estimate is the pre-run CPU sample of section 3.8
  (q05 changed in at most 0.83 % and q95 in at most 0.19 % of forecasts), not the full runs.

### 4.15 Exploding outer quantiles (PLAN.md 14.9 item 10)

**Measured after the run** in `results/phase1/quantile_diagnostics.csv` (D133; from the cache, no inference). On
near-constant contexts the outer levels (q01, q05) can lie orders of magnitude beyond the data range, with or without
the D128 guard, because a tiny context scale is inverted through arcsinh scaling (PLAN.md 14.5). A band much wider
than the deviation drives that channel's band score toward 0; a huge tail inflates its crps whatever the
observation; mae reads q50 only and is not affected. The file counts forecasts with a band (q95 - q05) above 10 and
100 fit-z and a tail (q99 - q01) above 100 and 1000 fit-z, over all scored steps and, on test, over attack steps.
The cut-offs are fixed and descriptive (nothing reads the file). They are fit-z, not physical widths: 10 fit-z is
0.043 raw units on `P1_PCV02Z` (fit std 0.00429, `channels.csv`). The measurement shows the effect is rare overall
but concentrated on test and on attack steps. It does not show how much it changes any metric.

From `results/phase1/quantile_diagnostics.csv` (D133), MPS rows. band = q95 - q05 and tail = q99 - q01, in fit-z,
over all cached (channel, step) forecasts of the split (scored steps only).

| run (setup / variant) | split | forecasts | band > 10 z | band > 100 z | tail > 100 z | tail > 1000 z | widest band, z (channel) | widest tail, z | most bands > 10 z on |
|---|---|---|---|---|---|---|---|---|---|
| uni / rolling | calib | 865,980 | 0.0066 % | 0.0016 % | 0.0065 % | 0.0016 % | 183.612 (`P1_PIT02`) | 34,554 | `P1_PIT02` |
| uni / rolling | calib2 | 865,980 | 0.0069 % | 0.0016 % | 0.0043 % | 0.0027 % | 303.785 (`P1_B4005`) | 119,290 | `P1_B4005` |
| uni / rolling | test | 2,011,950 | 0.41 % | 0.064 % | 0.28 % | 0.049 % | 35,307 (`P1_PCV02Z`) | 2,481,252 | `P1_PCV02Z` |
| uni57 / rolling | calib | 967,860 | 0.0059 % | 0.0014 % | 0.0058 % | 0.0014 % | 183.612 (`P1_PIT02`) | 34,554 | `P1_PIT02` |
| uni57 / rolling | test | 2,248,650 | 0.37 % | 0.058 % | 0.25 % | 0.045 % | 35,307 (`P1_PCV02Z`) | 2,481,252 | `P1_PCV02Z` |
| uni / cf-onset | test | 62,934 | 0.56 % | 0.12 % | 0.62 % | 0.083 % | 12,823 (`P1_PIT02`) | 1,756,736 | `P2_SIT01` |
| mv-lit / rolling | calib | 577,320 | 0.0026 % | 0 | 0.00052 % | 0 | 10.974 (`P1_PIT02`) | 106.621 | `P1_PIT01` |
| mv-lit / rolling | calib2 | 577,320 | 0.011 % | 0.0024 % | 0.0052 % | 0.0024 % | 555.341 (`P1_B4005`) | 339,979 | `P1_PIT02` |
| mv-lit / rolling | test | 1,341,300 | 0.38 % | 0.073 % | 0.24 % | 0.060 % | 35,146 (`P1_PCV02Z`) | 110,023 | `P1_PCV02Z` |
| mv-acttgt / rolling | calib | 696,180 | 0.0022 % | 0 | 0.00043 % | 0 | 10.974 (`P1_PIT02`) | 106.621 | `P1_PIT01` |
| mv-acttgt / rolling | test | 1,617,450 | 0.32 % | 0.061 % | 0.20 % | 0.050 % | 35,146 (`P1_PCV02Z`) | 110,023 | `P1_PCV02Z` |
| mv-lit / cf-onset | test | 41,956 | 0.81 % | 0.16 % | 0.60 % | 0.15 % | 1,814 (`P1_PIT02`) | 309,572 | `P2_SIT01` |
| mv-lit / frozen | ref | 1,020 | 0 | 0 | 0 | 0 | 3.397 (`P3_PIT01`) | 5.460 | none |
| mv-lit / ff-interp-block | calib | 577,320 | 1.1 % | 0.045 % | 0.21 % | 0 | 247.450 (`P1_FCV02Z`) | 435.840 | `P1_FCV02Z` |
| mv-lit / ff-interp-block | test | 1,341,300 | 0.00097 % | 0 | 0.0028 % | 0 | 12.636 (`P1_PIT01`) | 445.577 | `P1_TIT02` |
| mv-lit / ff-interp-block-max60-testinf | calib | 577,320 | 0.0095 % | 0 | 0 | 0 | 15.834 (`P1_FCV03Z`) | 85.405 | `P1_PIT01` |
| mv-lit / ff-interp-block-max60-testinf | test | 1,341,300 | 0.34 % | 0.062 % | 0.14 % | 0.0061 % | 1,204 (`P1_PCV02Z`) | 8,327 | `P1_PCV02Z` |
| mv-lit / ff-interp-block-max30 | calib | 577,320 | 0.038 % | 0 | 0 | 0 | 27.577 (`P1_TIT01`) | 97.248 | `P2_VXT03` |
| mv-lit / ff-interp-block-max30 | test | 1,341,300 | 0.12 % | 0.0047 % | 0.043 % | 0.0034 % | 761.625 (`P2_VT01`) | 7,039 | `P1_PCV02Z` |
| mv-lit / ff-interp-block-max120 | calib | 577,320 | 0.018 % | 0 | 0.0035 % | 0 | 45.213 (`P1_FCV02Z`) | 264.378 | `P1_FCV02Z` |
| mv-lit / ff-interp-block-max120 | test | 1,341,300 | 0.097 % | 0.0028 % | 0.037 % | 0.0019 % | 572.067 (`P2_VT01`) | 10,356 | `P1_PCV02Z` |
| mv-lit / prepend | calib | 577,320 | 0.0040 % | 0 | 0 | 0 | 11.936 (`P1_PCV02Z`) | 56.025 | `P1_PCV02Z` |
| mv-lit / prepend | test | 1,341,300 | 0.25 % | 0.031 % | 0.12 % | 0.023 % | 31,704 (`P1_PCV02Z`) | 130,894 | `P1_PCV02Z` |

Test, attack steps (label 1) against all test steps. The last column is the count (share x attack-step forecasts):

| run (setup / variant) | attack-step forecasts | band > 10 z: attack / all test | band > 100 z: attack / all | tail > 100 z: attack / all | tail > 1000 z: attack / all | attack forecasts with band > 10 z |
|---|---|---|---|---|---|---|
| uni / rolling | 47,634 | 2.3 % / 0.41 % | 0.21 % / 0.064 % | 0.66 % / 0.28 % | 0.21 % / 0.049 % | 1,111 |
| uni57 / rolling | 53,238 | 2.1 % / 0.37 % | 0.19 % / 0.058 % | 0.59 % / 0.25 % | 0.18 % / 0.045 % | 1,111 |
| uni / cf-onset | 47,634 | 0.60 % / 0.56 % | 0.099 % / 0.12 % | 0.64 % / 0.62 % | 0.059 % / 0.083 % | 284 |
| mv-lit / rolling | 31,756 | 2.0 % / 0.38 % | 0.20 % / 0.073 % | 0.60 % / 0.24 % | 0.20 % / 0.060 % | 634 |
| mv-acttgt / rolling | 38,294 | 1.9 % / 0.32 % | 0.19 % / 0.061 % | 0.57 % / 0.20 % | 0.17 % / 0.050 % | 714 |
| mv-lit / cf-onset | 31,756 | 0.86 % / 0.81 % | 0.14 % / 0.16 % | 0.68 % / 0.60 % | 0.13 % / 0.15 % | 273 |
| mv-lit / ff-interp-block | 31,756 | 0.0094 % / 0.00097 % | 0 / 0 | 0 / 0.0028 % | 0 / 0 | 3 |
| mv-lit / ff-interp-block-max60-testinf | 31,756 | 0.41 % / 0.34 % | 0.019 % / 0.062 % | 0.13 % / 0.14 % | 0.013 % / 0.0061 % | 131 |
| mv-lit / ff-interp-block-max30 | 31,756 | 0.26 % / 0.12 % | 0.050 % / 0.0047 % | 0.17 % / 0.043 % | 0.050 % / 0.0034 % | 84 |
| mv-lit / ff-interp-block-max120 | 31,756 | 0.19 % / 0.097 % | 0.0063 % / 0.0028 % | 0.082 % / 0.037 % | 0.0094 % / 0.0019 % | 61 |
| mv-lit / prepend | 31,756 | 2.1 % / 0.25 % | 0.21 % / 0.031 % | 0.36 % / 0.12 % | 0.17 % / 0.023 % | 660 |

- **Rare on calib, frequent on test.** In the headline rolling runs a band wider than 10 z is 62x (`uni`, 0.0066 % to
  0.41 %) and 145x (`mv-lit`, 0.0026 % to 0.38 %) more frequent on test than on calib. It stays that frequent on
  normal test steps alone (0.36 % and 0.34 %, all-step minus attack-step counts). Tails over 1000 z: 0.0016 % of
  `uni` calib forecasts, none in `mv-lit` calib, 0.049 % and 0.060 % of test. So the calib thresholds come from data
  where this hardly happens.
- **Where.** On test the widest bands (35,307 z `uni`, 35,146 z `mv-lit`) and the most bands over 10 z are on
  `P1_PCV02Z` in every rolling run; on calib they are on `P1_PIT02` and `P1_PIT01`. The file names one channel per
  row, and none for the attack-step cases.
- **Attack steps.** Bands wider than 10 z are 5.7x (`uni`) and 5.3x (`mv-lit`) more frequent on attack steps than over
  all test steps (2.3 %, 1,111 of 47,634; 2.0 %, 634 of 31,756). The cf-onset forecasts of the same attack steps,
  whose context ends at onset, have them on 0.60 % and 0.86 %, close to their own all-step rate. So the rolling
  forecasts carry wide bands on attack steps 3.9x (`uni`) and 2.3x (`mv-lit`) as often as the clean-context
  forecasts of the same steps. INTERPRETATION: this is consistent with attack data in the rolling context widening
  the band, sometimes explosively. It is not a test of it: the file does not split by origin side, and cf-onset also
  differs in horizon and output-patch count (section 3.6).
- **Band score.** A channel whose band is wider than 10 z adds less than one band-score unit per 10 z of excess
  (band = excess / (width + 0.1)), against top-3 calib thresholds of 11.589 (`uni` on `uni51`) and 9.442 (`mv-lit` on
  `mvlit34`) (`thresholds.csv`). On those forecasts the channel is close to blind. How many alarms that removes is
  not measured.
- **crps.** When the observation lies inside them, q01 and q99 enter crps with 2 x 0.03 x 0.01 = 0.0006 per z of
  distance, and q05 and q95 with 2 x 0.045 x 0.05 = 0.0045 per z (section 2.5 formula and weights). A 1000 z tail
  with the observation in the middle thus adds about 0.6 to that channel's crps, against top-3 crps calib
  thresholds of 3.545 (`uni` on `uni51`) and 2.858 (`mv-lit` on `mvlit34`) (`thresholds.csv`). The widest test
  tails (2,481,252 z `uni`, 110,023 z `mv-lit`) dominate any crps score they enter. Tails over 1000 z are 30x more
  frequent on `uni` test than on `uni` calib, and 4.2x (`uni`) and 3.4x (`mv-lit`) more frequent on attack steps than
  over all test steps. So crps is not suspect wholesale, but a crps alarm on one channel can come from an exploded
  tail rather than from the observation, mostly on test and on attack steps. Not measured: how much of the crps AUCs,
  or of the higher crps test alarm rate (5.655 per hour against 1.224 for band, `uni` on `uni51`, `metrics.csv`), this
  explains. mae reads q50 only and is not affected.
- **FF, prepend, frozen.** `ff-interp-block` is the only run with many wide bands on calib (1.1 %, most on
  `P1_FCV02Z`) and almost none on test (0.00097 %), the reverse of every other run. Prepend has fewer wide bands than
  in-file rolling over all test steps (0.25 % vs 0.38 %) but as many on attack steps (2.1 % vs 2.0 %). The frozen
  forecast has none (widest band 3.397 z).

### 4.16 1 s comparison

The planned 1 s block (history up to 8,192 steps) was not run: Arthur deferred it (PLAN.md D134; section 8, Q20).
A 1 s run with the paper's 128-step history did run afterwards, with a 10 s control: section 4.19.
1 s vs 10 s also changes H and stride in
seconds (30 s vs 300 s) and the context in time (8,192 steps = 2.3 h at 1 s vs 22.8 h at 10 s) (PLAN.md 14.7).

### 4.17 Uncertainty and equal false alarms (added after the report, D135)

Two checks Arthur asked for after reading sections 1-5, written by `tsfm-ad compare` (`compare.py`, D135) from the
cached scores: `results/phase1/bootstrap_paired.csv`, `bootstrap_ci.csv` and `fa_matched.csv`. Their point estimates
equal `metrics.csv` and `tapr.csv` exactly.

- **Paired block bootstrap.** Each test file is cut into 1 h blocks (112 blocks); a cut never falls inside an attack or
  the 180 s TaPR zone after it. 1,000 resamples draw 112 blocks with replacement, the same draws for every method of
  a channel set. Intervals are 95 % percentile intervals of the difference "Chronos-2 reference minus other". The
  parameters were fixed in `configs/base.yaml` before any result. Limits: resampled blocks are treated as
  exchangeable, TaPR of a resample joins blocks from different times, and 50 attacks make every interval wide.
- **Equal false alarms.** At the calib threshold the methods run at different test false-alarm rates (1.0 to 6.4 steps
  per hour for rolling Chronos-2 and the baselines, 9.1 for dual, 116.5 for `ff-interp-block`, `metrics.csv`), so their
  recall and TaPR F1 are not comparable. Here every method gets the threshold that
  leaves at most 0.5, 1, 2 or 5 false-alarm steps per normal test hour. **This threshold is set from the test labels,
  like reading one point of a ROC curve: it compares methods at equal false alarms and is not a detector.** No pick
  uses it; the headline stays the calib threshold. Every target was reached to within 1 % (`fa_matched.csv`, `fa_per_hour`).

**Band score (dual score for dual), top-3: reference minus other, with 95 % intervals** (`bootstrap_paired.csv`):

| set | reference minus | PR-AUC | ROC-AUC | TaPR F1 at the calib threshold |
|---|---|---|---|---|
| `mvlit34` | `mv-lit` - `uni` | +0.000 (-0.017 to +0.020) | -0.017 (-0.032 to -0.003) | +0.007 (-0.004 to +0.018) |
| `mvlit34` | `mv-lit` - `mv-lit ff-interp-block` | +0.189 (+0.094 to +0.288) | +0.226 (+0.159 to +0.298) | +0.087 (-0.052 to +0.263) |
| `mvlit34` | `mv-lit` - `mv-lit frozen` | +0.207 (+0.108 to +0.298) | +0.214 (+0.131 to +0.290) | +0.215 (+0.108 to +0.320) |
| `mvlit34` | `mv-lit` - `mv-lit dual` (dual score) | +0.315 (+0.195 to +0.429) | +0.292 (+0.200 to +0.387) | +0.310 (+0.192 to +0.426) |
| `mvlit34` | `mv-lit` - `lastvalue` | -0.005 (-0.129 to +0.103) | -0.021 (-0.070 to +0.026) | -0.137 (-0.237 to -0.037) |
| `mvlit34` | `mv-lit` - `seasonal-refday` | +0.013 (-0.123 to +0.115) | +0.134 (+0.040 to +0.216) | +0.072 (-0.074 to +0.203) |
| `mvlit34` | `mv-lit` - `robustz` | +0.255 (+0.160 to +0.321) | +0.169 (+0.109 to +0.224) | +0.170 (+0.100 to +0.250) |
| `uni51` | `uni` - `lastvalue` | -0.011 (-0.131 to +0.100) | +0.003 (-0.029 to +0.036) | -0.156 (-0.245 to -0.066) |
| `uni51` | `uni` - `seasonal-refday` | +0.006 (-0.118 to +0.105) | +0.145 (+0.068 to +0.217) | +0.015 (-0.145 to +0.154) |
| `uni51` | `uni` - `robustz` | +0.229 (+0.124 to +0.297) | +0.185 (+0.132 to +0.241) | +0.074 (-0.019 to +0.159) |

**Equal false alarms, band score (dual for dual), top-3: attacks detected (of 50) / recall / TaPR F1 at each target**
(`fa_matched.csv`):

| set | method | 0.5 / h | 1 / h | 2 / h | 5 / h |
|---|---|---|---|---|---|
| `mvlit34` | `mv-lit` | 28 / 0.188 / 0.322 | 29 / 0.232 / 0.392 | 35 / 0.313 / 0.473 | 42 / 0.420 / 0.499 |
| `mvlit34` | `uni` | 28 / 0.200 / 0.344 | 30 / 0.231 / 0.393 | 35 / 0.299 / 0.448 | 40 / 0.407 / 0.492 |
| `mvlit34` | `mv-lit ff-interp-block` | 19 / 0.186 / 0.323 | 19 / 0.190 / 0.278 | 20 / 0.199 / 0.241 | 20 / 0.210 / 0.178 |
| `mvlit34` | `mv-lit frozen` | 14 / 0.117 / 0.245 | 23 / 0.162 / 0.292 | 24 / 0.177 / 0.240 | 26 / 0.204 / 0.180 |
| `mvlit34` | `mv-lit dual` | 3 / 0.041 / 0.046 | 3 / 0.046 / 0.045 | 6 / 0.066 / 0.097 | 12 / 0.104 / 0.125 |
| `mvlit34` | `lastvalue` | 14 / 0.115 / 0.245 | 14 / 0.149 / 0.324 | 29 / 0.287 / 0.468 | 41 / 0.530 / 0.654 |
| `mvlit34` | `seasonal-refday` | 16 / 0.142 / 0.285 | 36 / 0.331 / 0.514 | 38 / 0.408 / 0.517 | 38 / 0.461 / 0.393 |
| `mvlit34` | `robustz` | 4 / 0.047 / 0.048 | 13 / 0.117 / 0.233 | 17 / 0.163 / 0.285 | 19 / 0.172 / 0.196 |
| `uni51` | `uni` | 31 / 0.224 / 0.356 | 31 / 0.242 / 0.385 | 37 / 0.304 / 0.437 | 40 / 0.389 / 0.433 |
| `uni51` | `lastvalue` | 14 / 0.115 / 0.245 | 14 / 0.149 / 0.324 | 31 / 0.290 / 0.466 | 39 / 0.542 / 0.673 |
| `uni51` | `seasonal-refday` | 16 / 0.143 / 0.285 | 36 / 0.337 / 0.517 | 38 / 0.416 / 0.534 | 39 / 0.469 / 0.391 |
| `uni51` | `robustz` | 4 / 0.047 / 0.048 | 13 / 0.117 / 0.233 | 22 / 0.208 / 0.351 | 26 / 0.225 / 0.274 |

**Chronos-2 minus `lastvalue` at equal false alarms, with 95 % intervals** (`bootstrap_paired.csv`; reference `mv-lit`
on `mvlit34`, `uni` on `uni51`; same score on both sides):

| set | score | metric | 0.5 / h | 1 / h | 2 / h | 5 / h |
|---|---|---|---|---|---|---|
| `mvlit34` | band | attack detection rate | +0.280 (+0.154 to +0.582) | +0.300 (-0.020 to +0.489) | +0.120 (-0.045 to +0.420) | +0.020 (-0.045 to +0.174) |
| `mvlit34` | band | recall | +0.074 (-0.029 to +0.221) | +0.084 (-0.073 to +0.200) | +0.026 (-0.119 to +0.190) | -0.110 (-0.210 to -0.006) |
| `mvlit34` | band | TaPR F1 | +0.077 (-0.067 to +0.371) | +0.068 (-0.105 to +0.245) | +0.005 (-0.158 to +0.173) | -0.155 (-0.227 to -0.035) |
| `uni51` | band | attack detection rate | +0.340 (+0.173 to +0.608) | +0.340 (-0.063 to +0.522) | +0.120 (-0.098 to +0.412) | +0.020 (-0.104 to +0.111) |
| `uni51` | band | recall | +0.109 (+0.001 to +0.242) | +0.093 (-0.072 to +0.193) | +0.014 (-0.139 to +0.162) | -0.153 (-0.264 to -0.034) |
| `uni51` | band | TaPR F1 | +0.111 (-0.027 to +0.384) | +0.061 (-0.115 to +0.224) | -0.029 (-0.196 to +0.111) | -0.240 (-0.319 to -0.105) |
| `mvlit34` | mae | attack detection rate | +0.080 (+0.000 to +0.431) | +0.360 (+0.019 to +0.587) | +0.220 (+0.042 to +0.568) | +0.040 (+0.000 to +0.131) |
| `mvlit34` | mae | recall | +0.049 (+0.007 to +0.166) | +0.134 (+0.017 to +0.317) | +0.186 (+0.058 to +0.392) | +0.043 (+0.005 to +0.117) |
| `mvlit34` | mae | TaPR F1 | +0.108 (+0.007 to +0.225) | +0.156 (-0.009 to +0.341) | +0.182 (-0.022 to +0.378) | -0.165 (-0.261 to -0.026) |
| `uni51` | mae | attack detection rate | +0.020 (-0.076 to +0.160) | +0.040 (-0.244 to +0.341) | +0.060 (-0.086 to +0.429) | +0.080 (+0.000 to +0.135) |
| `uni51` | mae | recall | +0.009 (-0.026 to +0.047) | +0.021 (-0.103 to +0.131) | +0.052 (-0.059 to +0.237) | +0.041 (+0.005 to +0.084) |
| `uni51` | mae | TaPR F1 | +0.005 (-0.077 to +0.113) | +0.031 (-0.158 to +0.144) | -0.000 (-0.130 to +0.197) | -0.098 (-0.148 to -0.010) |

**Mean segment coverage at equal false alarms, `mvlit34`, band, N = 6** (`fa_matched.csv`; no intervals computed):

| method | target | onset_cov | interior_cov | offset_cov |
|---|---|---|---|---|
| `mv-lit` | 0.5 / h | 0.183 | 0.249 | 0.057 |
| `mv-lit` | 1 / h | 0.250 | 0.281 | 0.080 |
| `mv-lit` | 2 / h | 0.387 | 0.359 | 0.117 |
| `mv-lit` | 5 / h | 0.493 | 0.494 | 0.187 |
| `lastvalue` | 0.5 / h | 0.057 | 0.175 | 0.060 |
| `lastvalue` | 1 / h | 0.077 | 0.212 | 0.110 |
| `lastvalue` | 2 / h | 0.170 | 0.357 | 0.203 |
| `lastvalue` | 5 / h | 0.447 | 0.559 | 0.373 |
| `seasonal-refday` | 0.5 / h | 0.120 | 0.215 | 0.063 |
| `seasonal-refday` | 1 / h | 0.340 | 0.370 | 0.103 |
| `seasonal-refday` | 2 / h | 0.400 | 0.446 | 0.177 |
| `seasonal-refday` | 5 / h | 0.460 | 0.491 | 0.197 |

What this shows:

- **`uni` vs `mv-lit` is a tie on PR-AUC** (+0.000, -0.017 to +0.020). On ROC-AUC `uni` is higher, and that interval
  excludes 0 (-0.017, -0.032 to -0.003). The base pick (`mv-lit`, picked on test results, section 4.3) rests on noise.
- **Every context protection is worse than plain rolling** on PR-AUC and ROC-AUC, with intervals that exclude 0
  (`ff-interp-block` +0.189 and +0.226, frozen +0.207 and +0.214, dual +0.315 and +0.292). At equal false alarms
  `ff-interp-block` and frozen hardly gain from a larger alarm budget (19-20 and 14-26 attacks from 0.5 to 5 per hour).
- **Against `lastvalue` the answer depends on the alarm budget.** PR-AUC and ROC-AUC are ties with wide intervals
  (`mv-lit` -0.005, -0.129 to +0.103). `lastvalue`'s higher TaPR F1 at the calib threshold (-0.137, -0.237 to -0.037)
  comes at 2.3 times the false alarms (2.598 against 1.112 per hour, `metrics.csv`). At 0.5 false alarms per hour
  Chronos-2 detects twice as many attacks (28 against 14 on `mvlit34`, 31 against 14 on `uni51`), and the
  detection-rate intervals exclude 0. At 5 per hour both detect about the same number (42 and 41), but `lastvalue`
  covers more attack steps: recall -0.110 (-0.210 to -0.006) and TaPR F1 -0.155 (-0.227 to -0.035) on `mvlit34`.
- **Where the difference sits.** At low budgets Chronos-2 catches onsets much more often than `lastvalue` (onset
  coverage 0.183 against 0.057 at 0.5 per hour, 0.387 against 0.170 at 2 per hour). At 5 per hour `lastvalue` covers
  more of the interior (0.559 against 0.494) and the offset (0.373 against 0.187). No interval was computed for these
  coverages.
- **With the mae score, which uses only the median forecast, Chronos-2 beats `lastvalue`**: PR-AUC +0.097 (0.048 to
  0.146) on `mvlit34` and +0.053 (0.003 to 0.088) on `uni51`, and higher recall at all four targets on `mvlit34`
  (all four intervals exclude 0). All three
  scores were planned and reported from the start; the band score stays the headline, and this comparison was read
  on test results.
- **`seasonal-refday` vs Chronos-2:** PR-AUC ties (+0.013, -0.123 to +0.115); Chronos-2 has the higher ROC-AUC
  (+0.134, 0.040 to 0.216). At 1-2 false alarms per hour `seasonal-refday` detects more attacks (36-38 against
  29-35), but those differences have intervals that include 0. `robustz` is below Chronos-2 everywhere on the band
  score.

### 4.18 Forecast accuracy and model size (added after the report, D136)

**Forecast accuracy** (`results/phase1/forecast_accuracy.csv`, written by `tsfm-ad compare`): mean mae (|q50 - y|)
and crps per (channel, step) in fit-z, and the share of (channel, step) with y inside the method's own [q05, q95]
band (nominal 0.90). This compares forecasts, not detectors.

| set | method | calib mae / crps / coverage | test normal mae / crps / coverage | test attack mae / coverage |
|---|---|---|---|---|
| `mvlit34` | `mv-lit` | 0.316 / 0.232 / 0.887 | 0.360 / 0.273 / 0.888 | 8.106 / 0.773 |
| `mvlit34` | `uni` | 0.322 / 0.238 / 0.869 | 0.386 / 0.289 / 0.876 | 9.960 / 0.748 |
| `mvlit34` | `mv-lit frozen` | 2.528 / 2.390 / 0.409 | 2.355 / 2.219 / 0.420 | 6.925 / 0.394 |
| `mvlit34` | `mv-lit ff-interp-block` | 5.161 / 5.021 / 0.400 | 1.676 / 1.640 / 0.226 | 6.104 / 0.189 |
| `mvlit34` | `lastvalue` | 0.434 / 0.326 / 0.906 | 0.516 / 0.406 / 0.899 | 6.790 / 0.758 |
| `mvlit34` | `seasonal-refday` | 2.630 / 2.340 / 0.828 | 2.472 / 2.165 / 0.832 | 7.102 / 0.754 |
| `mvlit34` | `robustz` | 0.565 / 0.460 / 0.719 | 0.585 / 0.478 / 0.720 | 5.242 / 0.601 |
| `uni51` | `uni` | 0.388 / 0.277 / 0.870 | 0.430 / 0.311 / 0.876 | 6.955 / 0.761 |
| `uni51` | `uni (chronos-2-small)` | 0.391 / 0.279 / 0.883 | 0.448 / 0.330 / 0.889 | 6.768 / 0.775 |
| `uni51` | `lastvalue` | 0.508 / 0.379 / 0.905 | 0.566 / 0.435 / 0.899 | 4.912 / 0.771 |
| `uni51` | `seasonal-refday` | 2.099 / 1.816 / 0.850 | 1.996 / 1.700 / 0.855 | 5.237 / 0.783 |
| `uni51` | `robustz` | 0.615 / 0.489 / 0.726 | 0.622 / 0.495 / 0.729 | 3.875 / 0.622 |

- **Chronos-2 forecasts normal data clearly better than `lastvalue`** (mae 0.316 against 0.434 on `mvlit34` calib,
  0.388 against 0.508 on `uni51`, about 25 % lower), and its band covers 0.87-0.89 of normal steps, slightly
  narrower than nominal. Yet on the band score it only ties `lastvalue` on PR-AUC (section 4.17). A better forecast
  does not by itself rank attack steps better here; with the mae score, which uses the median directly, it does
  (section 4.17).
- **Frozen and FF forecast normal data badly** (calib mae 2.528 and 5.161, coverage 0.409 and 0.400). That is the
  cost behind their false alarms (section 4.6-4.7): a fixed reference day does not predict the process, and FF's
  forecasts drift once they replace the data. `seasonal-refday` forecasts poorly too (mae 2.1-2.6) but keeps a wide
  band (coverage 0.83-0.85).

**Model size: `autogluon/chronos-2-small` against `amazon/chronos-2`** (Arthur's go for Q19, D136). Experiment 1
`uni` rolling on `uni51`, calib and test, MPS (its D54 check passed, `mps_check.csv`). A size sensitivity, not
experiment 4: one setup, no selection, no calib2. The small model has 13 native quantile levels; the 8 others are
interpolated (D136), which changes crps but not band or mae.

| model | params | sec per call (median, test) | test wall-clock s | ROC-AUC | PR-AUC | TaPR F1 | attacks detected | onset / interior / offset cov | post- / pre-onset interior cov | crossed share (test) |
|---|---|---|---|---|---|---|---|---|---|---|
| `amazon/chronos-2` | 119,477,664 | 1.268 | 1,857.8 | 0.894 | 0.401 | 0.398 | 31 | 0.280 / 0.290 / 0.083 | 0.0196 / 0.334 | 0.212 |
| `autogluon/chronos-2-small` | 27,934,624 | 0.344 | 499.5 | 0.876 | 0.391 | 0.393 | 32 | 0.280 / 0.290 / 0.083 | 0.0019 / 0.333 | 0.071 |

Sources: `size_latency.csv`, `metrics.csv` (band, top-3, calib), `tapr.csv` (headline), `segments_summary.csv`
(N = 6, all attacks), `quantile_diagnostics.csv`.

**Big minus small, paired bootstrap with 95 % intervals** (`bootstrap_paired.csv`):

| score | PR-AUC | ROC-AUC | TaPR F1 (calib threshold) | attack detection rate at 1 / h | recall at 2 / h |
|---|---|---|---|---|---|
| band | +0.010 (-0.002 to +0.020) | +0.017 (+0.006 to +0.030) | +0.005 (-0.002 to +0.015) | +0.000 (-0.061 to +0.061) | +0.010 (-0.017 to +0.033) |
| crps | +0.034 (-0.003 to +0.073) | +0.001 (-0.005 to +0.008) | +0.051 (+0.010 to +0.085) | +0.000 (-0.091 to +0.132) | +0.069 (-0.048 to +0.162) |
| mae | -0.000 (-0.035 to +0.036) | -0.005 (-0.015 to +0.004) | +0.023 (-0.011 to +0.053) | -0.040 (-0.311 to +0.231) | -0.045 (-0.127 to +0.084) |

**Equal false alarms: attacks detected (of 50) / recall** (`fa_matched.csv`; threshold from the test labels,
evaluation only):

| score | model | 0.5 / h | 1 / h | 2 / h | 5 / h |
|---|---|---|---|---|---|
| band | `chronos-2` | 31 / 0.224 | 31 / 0.242 | 37 / 0.304 | 40 / 0.389 |
| band | `chronos-2-small` | 30 / 0.223 | 31 / 0.234 | 37 / 0.294 | 40 / 0.383 |
| crps | `chronos-2` | 13 / 0.115 | 16 / 0.151 | 33 / 0.298 | 45 / 0.537 |
| crps | `chronos-2-small` | 13 / 0.104 | 16 / 0.153 | 23 / 0.229 | 41 / 0.485 |
| mae | `chronos-2` | 13 / 0.104 | 16 / 0.150 | 36 / 0.367 | 47 / 0.584 |
| mae | `chronos-2-small` | 3 / 0.052 | 18 / 0.188 | 38 / 0.412 | 45 / 0.578 |

- **The 4x smaller model detects about as well and runs 3.7x faster** (median 0.344 against 1.268 s per call on test;
  499.5 against 1,857.8 s for the test split). On the band score PR-AUC and TaPR F1 tie (intervals include 0), and at
  every false-alarm target both detect the same number of attacks within one. The big model's ROC-AUC is higher by
  0.017 (0.006 to 0.030).
- **Its forecasts are only slightly worse:** normal test mae 0.448 against 0.430 (+4 %), calib 0.391 against 0.388,
  with band coverage closer to nominal (0.883-0.889 against 0.870-0.876).
- **The same contamination signature:** interior coverage from post-onset contexts 0.0019 against 0.0196, from
  pre-onset contexts 0.333 against 0.334 (`segments_summary.csv`).
- **Fewer quantile crossings:** 7.1 % of test forecasts against 21.2 % (`quantile_diagnostics.csv`).
- crps rows mix the size effect with the interpolated levels and are not a clean size comparison.
- So, on this data, model capacity is not what limits detection. That fits the rest of section 4: the misses come
  from the score, the threshold and the context, not from forecast quality.

### 4.19 Lowe et al.'s setting on HAI: 1 s, history 128 steps (added after the report, D137)

Option A of the evening of 2026-10-20: the paper's longest input (I = 128 steps) at 1 s, H = 30, `uni` on `uni51`,
plus a control at 10 s with the same 128-step cap (`configs/res1s_uni_c128.yaml`, `res10s_uni_c128.yaml`). At 1 s
a 128-step history is 128 s, so most HAI attacks (17-422 s) are longer than the window: the paper's "long-context"
case. The cap is a method change against D118, reported as a sensitivity, never as a headline. The planned 1 s run
with the full 8,192-step history was not run (D134).

How to read the 1 s rows: an hour has 3,600 steps at 1 s, so the calib 99.5th percentile alone gives about 18
false-alarm steps per normal hour (1.8 at 10 s); compare resolutions with `p_normal`, the share of normal steps that
alarm. Segment chance levels are high at 1 s because N = 60 steps (`onset_chance`, `interior_chance`).

**Detection** (`metrics.csv`, calib threshold; TaPR F1 from `tapr.csv`, headline config):

| run | score | ROC-AUC | PR-AUC | TaPR F1 | precision / recall | false-alarm steps per normal hour |
|---|---|---|---|---|---|---|
| 10 s, history up to 8,192 (headline) | band (topk) | 0.894 | 0.401 | 0.398 | 0.641 / 0.251 | 1.22 |
| 10 s, history up to 8,192 (headline) | mae (mean) | 0.861 | 0.429 | 0.593 | 0.536 / 0.516 | 3.90 |
| 10 s, history 128 (control) | band (topk) | 0.853 | 0.321 | 0.328 | 0.581 / 0.215 | 1.36 |
| 10 s, history 128 (control) | mae (mean) | 0.848 | 0.456 | 0.609 | 0.588 / 0.502 | 3.08 |
| 1 s, history 128 (paper setting) | band (topk) | 0.618 | 0.081 | 0.062 | 0.190 / 0.054 | 19.27 |
| 1 s, history 128 (paper setting) | mae (mean) | 0.764 | 0.322 | 0.414 | 0.541 / 0.343 | 24.29 |
| 1 s, history 128, `ff-interp-block-max120` | band (topk) | 0.591 | 0.097 | 0.078 | 0.035 / 0.275 | 633.08 |
| 1 s, history 128, `ff-interp-block-max120` | mae (mean) | 0.666 | 0.159 | 0.091 | 0.035 / 0.524 | 1218.07 |
| 1 s `lastvalue` | band (topk) | 0.857 | 0.301 | 0.262 | 0.518 / 0.220 | 17.14 |
| 1 s `lastvalue` | mae (mean) | 0.736 | 0.303 | 0.344 | 0.502 / 0.296 | 24.48 |
| 1 s `seasonal-refday` | band (topk) | 0.752 | 0.341 | 0.181 | 0.527 / 0.341 | 25.54 |
| 1 s `seasonal-refday` | mae (mean) | 0.793 | 0.369 | 0.307 | 0.513 / 0.363 | 28.79 |
| 1 s `robustz` | band (topk) | 0.691 | 0.172 | 0.169 | 0.320 / 0.249 | 44.10 |
| 1 s `robustz` | mae (mean) | 0.824 | 0.397 | 0.431 | 0.390 / 0.441 | 57.65 |

**Segments** (`segments_summary.csv`, all attacks, N = 60 s; "post- / pre-onset" = mean per-attack coverage of attack
steps forecast from a context that does / does not hold attack data):

| run | score | attacks detected | onset / interior / offset cov | onset rate / chance | interior rate / chance | p_normal | post- / pre-onset attack-step cov |
|---|---|---|---|---|---|---|---|
| 10 s, history up to 8,192 (headline) | band | 31 | 0.280 / 0.290 / 0.083 | 0.520 / 0.020 | 0.553 / 0.045 | 0.0034 | 0.020 / 0.334 |
| 10 s, history up to 8,192 (headline) | mae | 45 | 0.530 / 0.589 / 0.360 | 0.800 / 0.073 | 0.872 / 0.154 | 0.0127 | 0.563 / 0.563 |
| 10 s, history 128 (control) | band | 29 | 0.247 / 0.249 / 0.070 | 0.440 / 0.022 | 0.511 / 0.049 | 0.0038 | 0.000 / 0.297 |
| 10 s, history 128 (control) | mae | 44 | 0.503 / 0.574 / 0.367 | 0.760 / 0.071 | 0.851 / 0.149 | 0.0123 | 0.609 / 0.534 |
| 1 s, history 128 (paper setting) | band | 32 | 0.110 / 0.022 / 0.014 | 0.520 / 0.270 | 0.283 / 0.451 | 0.0054 | 0.067 / 0.127 |
| 1 s, history 128 (paper setting) | mae | 47 | 0.357 / 0.273 / 0.205 | 0.860 / 0.326 | 0.783 / 0.516 | 0.0067 | 0.337 / 0.311 |
| 1 s, history 128, `ff-interp-block-max120` | band | 40 | 0.251 / 0.331 / 0.257 | 0.700 / 0.999 | 0.739 / 0.986 | 0.1759 | 0.287 / 0.179 |
| 1 s, history 128, `ff-interp-block-max120` | mae | 47 | 0.713 / 0.733 / 0.669 | 0.820 / 1.000 | 0.935 / 1.000 | 0.5745 | 0.750 / 0.671 |
| 1 s `lastvalue` | band | 38 | 0.214 / 0.229 / 0.149 | 0.640 / 0.244 | 0.652 / 0.418 | 0.0048 | 0.248 / 0.155 |
| 1 s `lastvalue` | mae | 46 | 0.320 / 0.228 / 0.177 | 0.820 / 0.308 | 0.739 / 0.496 | 0.0063 | 0.285 / 0.285 |
| 1 s `seasonal-refday` | band | 43 | 0.327 / 0.381 / 0.136 | 0.760 / 0.341 | 0.783 / 0.531 | 0.0071 | 0.399 / 0.164 |
| 1 s `seasonal-refday` | mae | 44 | 0.429 / 0.446 / 0.180 | 0.780 / 0.342 | 0.848 / 0.533 | 0.0071 | 0.478 / 0.259 |
| 1 s `robustz` | band | 26 | 0.159 / 0.309 / 0.147 | 0.360 / 0.513 | 0.522 / 0.684 | 0.0122 | 0.285 / 0.041 |
| 1 s `robustz` | mae | 47 | 0.500 / 0.538 / 0.292 | 0.860 / 0.737 | 0.891 / 0.821 | 0.0227 | 0.561 / 0.326 |

Pooled over attack steps (`segments_per_attack.csv`, band): at 10 s 232 attack steps (24.8 %) are forecast from a
post-onset context, with either cap; at 1 s 7,698 (86.0 %). Coverage of those steps: 0.004 (10 s, 8,192), 0.000
(10 s, 128) and 0.044 (1 s, 128), against 0.332, 0.286 and 0.118 for the pre-onset steps.

**cf-onset** (a labelled diagnostic, `cf_onset.csv`, band, top-3, rolling threshold): on the interior steps forecast
from a post-onset context, rolling covers 0.004 of 231 steps in 17 attacks at 10 s and 0.028 of 6,014 steps in 46
attacks at 1 s; a clean-context forecast from the onset covers 0.459 and 0.437 of the same steps.

**Forecast Fallback in this setting** (our interpretation, `ff-interp-block`):

- **No exit: diverged.** The run stopped on the first calib file with "Chronos-2 returned non-finite quantiles". A
  probe of that file (`SP/ff_probe.py`, not a results file) showed why: once the 128-step context is all FF median
  forecasts, Chronos-2 extends its own trend, the values grow by about 3 % per call, and after 940 calls
  `P4_ST_PT01` reaches about 3e19 fit-z and `P3_PIT01` about 1e11 before the model overflows. With the 8,192-step
  context at 10 s FF drifted but stayed finite (calib mae 5.161, section 4.18).
- **Max 30 steps: diverged too**, on the second calib file (`cache/logs/paper_setting_ffmax_failures.csv`).
- **Max 120 steps: finite, but worse than rolling.** It alarms on 0.176 of normal test steps (633 false-alarm steps
  per normal hour) and has a lower ROC-AUC on both scores (0.591 against 0.618 band; 0.666 against 0.764 mae mean).
  Fallback is active on 0.385 of test channel-steps and at the onset of 49 of 50 attacks (`ff_activity.csv`,
  `segments_summary.csv` ff_group), so interior coverage can be credited on 1 attack only (0.348). Lowe et al. report
  ROC-AUC gains from FF of +0.27 to +0.60 (their Fig. 4, settings chosen on test ROC-AUC); our interpretation shows
  none on HAI.

What this shows:

- **The paper's pattern appears in the paper's setting.** At 1 s with a 128-step history the onset is caught above
  chance (rate 0.520 against 0.270) while the interior is not (0.283 against 0.451); interior coverage is 0.022
  against 0.110 at the onset (band). At 10 s, with either history length, interior coverage is not below onset
  coverage (0.290 against 0.280; 0.249 against 0.247).
- **The history length does not decide it.** At 10 s, cutting the history from up to 8,192 to 128 steps lowers
  ROC-AUC from 0.894 to 0.853 and PR-AUC from 0.401 to 0.321 (band), but creates no interior drop, and post-onset
  steps alarm almost never with either cap. What differs at 1 s is how often a forecast starts inside an attack:
  every 30 s instead of every 5 minutes, so 86.0 % of attack steps come from contaminated contexts instead of 24.8 %.
  Contamination is present in every setting; it dominates detection only when forecasts restart often relative to
  the attack length. (Option B, section 4.20, confirms it at 10 s; still untested: 1 s with the full history, Q20.)
- **In this setting Chronos-2 loses to every baseline.** Band score PR-AUC 0.081 against 0.301 (`lastvalue`), 0.341
  (`seasonal-refday`) and 0.172 (`robustz`); with the paper's mae (mean over features) 0.322 against 0.303, 0.369 and
  0.397. Its ROC-AUC with that score (0.764) is still far above the paper's Chronos-2 baselines on SWaT, TEP and
  CTown (0.239-0.517, Table 2); data and input lengths differ, so this is not a like-for-like comparison.
- With the mae score, post-onset coverage at 1 s is not lower than pre-onset coverage (0.337 against 0.311), so in
  this setting the contamination signature shows on the band score, not on the paper's score. Why is not measured.

Cost (`runs.csv`): the 1 s cap-128 rolling run took 371.0 s (calib) and 884.6 s (test, 13,150 calls), 0.067 s per
call; the 10 s control took 249.7 s in all (`cache/logs/c128_10s_20261020.log`).

### 4.20 Option B: 10 s, a new forecast every minute (addendum after the sign-off, D138)

Option B (Q4): the headline experiment 1 run (`uni` rolling on `uni51`, history up to 8,192 steps) with H = 6 and
stride 6, so a new forecast starts every minute instead of every 5 minutes (`configs/res10s_uni_h6.yaml`, run key
`.../uni/rolling-h6`). Thresholds come from its own calib forecasts (99.5th percentile, as everywhere). It is the
cell section 4.19 left open: the headline resolution and history length, with frequent restarts as a deployment
would run them. H = 6 is a method change against D20; it is a sensitivity, never a headline, and it was not picked
on any score.

**Detection** (`metrics.csv`, calib threshold; TaPR F1 from `tapr.csv`, headline config):

| run | score | ROC-AUC | PR-AUC | TaPR F1 | precision / recall | false-alarm steps per hour |
|---|---|---|---|---|---|---|
| H = 30, history 8,192 (headline) | band (topk) | 0.894 | 0.401 | 0.398 | 0.641 / 0.251 | 1.22 |
| H = 30, history 8,192 (headline) | mae (mean) | 0.861 | 0.429 | 0.593 | 0.536 / 0.516 | 3.90 |
| **H = 6, history 8,192 (option B)** | band (topk) | 0.817 | 0.338 | 0.317 | 0.603 / 0.245 | 1.41 |
| **H = 6, history 8,192 (option B)** | mae (mean) | 0.840 | 0.484 | 0.583 | 0.608 / 0.535 | 3.01 |
| H = 30, history 128 (control, section 4.19) | band (topk) | 0.853 | 0.321 | 0.328 | 0.581 / 0.215 | 1.36 |
| H = 30, history 128 (control, section 4.19) | mae (mean) | 0.848 | 0.456 | 0.609 | 0.588 / 0.502 | 3.08 |

**Segments** (`segments_summary.csv`, all 50 attacks, N = 6 steps; post- / pre-onset = mean per-attack coverage of
attack steps forecast from a context that does / does not hold attack data; the mae rows use topk, as in 4.19):

| run | score | attacks detected | onset / interior / offset cov | onset rate / chance | interior rate / chance | p_normal | post- / pre-onset attack-step cov |
|---|---|---|---|---|---|---|---|
| H = 30 (headline) | band | 31 | 0.280 / 0.290 / 0.083 | 0.520 / 0.020 | 0.553 / 0.045 | 0.0034 | 0.020 / 0.334 |
| H = 30 (headline) | mae | 45 | 0.530 / 0.589 / 0.360 | 0.800 / 0.073 | 0.872 / 0.154 | 0.0127 | 0.563 / 0.563 |
| **H = 6 (option B)** | band | **47** | **0.593 / 0.079 / 0.027** | 0.860 / 0.023 | 0.319 / 0.051 | 0.0039 | **0.078 / 0.602** |
| **H = 6 (option B)** | mae | 45 | 0.550 / 0.599 / 0.373 | 0.800 / 0.046 | 0.872 / 0.100 | 0.0079 | 0.596 / 0.545 |
| H = 30, history 128 (control) | band | 29 | 0.247 / 0.249 / 0.070 | 0.440 / 0.022 | 0.511 / 0.049 | 0.0038 | 0.000 / 0.297 |

Pooled over attack steps (`segments_per_attack.csv`, band, N = 6): with H = 6, 652 of 934 attack steps (69.8 %) are
forecast from a post-onset context, against 232 (24.8 %) with H = 30. Their coverage is 0.087, against 0.610 for the
pre-onset steps (H = 30: 0.004 against 0.332). By N (band): onset / interior coverage 0.447 / 0.273 at N = 3, 0.593 /
0.079 at N = 6 and 0.405 / 0.038 at N = 12, so with H = 6 the interior is below the onset at every N (H = 30:
0.120 / 0.315, 0.280 / 0.290, 0.323 / 0.121). By stratum (band, N = 6): trip interior coverage falls from 0.772 to
0.100, pcv02d from 0.673 to 0.230, "other" from 0.101 to 0.050, while onset coverage rises in all three (0.444 to
0.500, 0.067 to 0.400, 0.269 to 0.644). cf-onset was not run for option B.

**At equal false alarms** (`fa_matched.csv`, threshold from the test labels, evaluation only, section 4.17; band,
attacks detected of 50, recall):

| false alarms per hour | H = 30 (headline) | H = 6 (option B) | H = 30, history 128 |
|---|---|---|---|
| 0.5 | 31, 0.224 | 43, 0.193 | 27, 0.190 |
| 1 | 31, 0.242 | 46, 0.227 | 28, 0.200 |
| 2 | 37, 0.304 | 47, 0.266 | 33, 0.253 |
| 5 | 40, 0.389 | 47, 0.336 | 34, 0.296 |

**Paired bootstrap** (`bootstrap_paired.csv`, band, headline minus option B, 95 % interval): ROC-AUC +0.077 (+0.048
to +0.108), PR-AUC +0.063 (-0.005 to +0.123), TaPR F1 at the calib threshold +0.081 (-0.057 to +0.211), recall at 2
false alarms per hour +0.039 (-0.041 to +0.104), attack detection rate at 1 false alarm per hour -0.300 (-0.422 to
-0.146).

Forecast accuracy (`forecast_accuracy.csv`, `uni51` calib): median-forecast mae 0.291 with H = 6 against 0.388 with
H = 30; band score mean on attack steps 1.227 against 3.349.

What this shows:

- **With a forecast every minute, the paper's pattern appears at 10 s too.** Onset coverage doubles (0.593 against
  0.280) and interior coverage drops to 0.079 (from 0.290), at about the same normal-step alarm rate (0.0039 against
  0.0034). Attack steps forecast from a context that holds the attack alarm on 0.087 of steps, those forecast from a
  clean context on 0.610. So the restart rate relative to the attack length decides whether contamination shows,
  as section 4.19 suggested; this run isolates it at the headline resolution and history length.
- **The boundary is the onset only.** Offset coverage falls too (0.027 against 0.083). The hypothesis says the
  boundaries are caught; here the end of an attack is caught less often than with H = 30, not more.
- **More attacks found, fewer attack steps covered.** Option B detects 47 of 50 attacks at the calib threshold (31
  with H = 30), and 15 more at 1 false alarm per hour (interval excludes 0). Its ROC-AUC is lower (interval excludes
  0); PR-AUC, TaPR F1 and recall are not resolved. For an operator who needs one alarm per attack, frequent
  restarts help; for step-wise coverage they cost the interior.
- **On the mae score there is no contamination signature** (post- / pre-onset coverage 0.596 against 0.545), as at
  1 s (section 4.19). The band score, which uses the forecast's own uncertainty, is the score that forgives a
  contaminated context; the median error does not.
- Better short-horizon forecasts (mae 0.291 against 0.388) do not give better step-wise detection.

Cost (`runs.csv`): calib 4,320.0 s (2,830 calls), test 16,984.8 s (6,575 calls), 1.53 and 2.58 s per call. The
estimate was 158 min for test (`cache/logs/option_b_20261021.log`); the run took 283 min because it shared the MPS
GPU with the Phase 2 runs, so these times are not a latency measurement.

---

## 5. What Chronos-2 does well and badly here

**Overall.** These points come from the answers below, and they cover one dataset, short attacks, 10 s, zero-shot and one model.

- On the headline score, Chronos-2 zero-shot does not beat the simplest baseline. `lastvalue` matches or beats it on PR-AUC and clearly beats it on TaPR F1 on three of four channel sets (question 6). What Chronos-2 adds is a low false-alarm rate. At equal false alarms (section 4.17) it finds twice as many attacks as `lastvalue` at 0.5 per hour and covers less attack time at 5 per hour; on PR-AUC the two tie within wide bootstrap intervals.
- On the headline set, every context protection we tried makes detection worse than plain rolling: Forecast Fallback, frozen and dual, all labelled interpretations (question 5).
- The contamination signature is clear on the few steps that can show it. Forecasts whose context holds attack data almost never alarm. At 10 s these are only 232 attack steps in 17 attacks. Most misses happen on clean context (questions 2, 3, 8).

**1. Does it catch attack onsets above chance, and on which attack types?** Yes, far above chance overall. The base `mv-lit` rolling run covers 0.263 of onset steps. Its onset detection rate is 0.500 against a chance level of 0.018 (`results/phase1/segments_summary.csv`, N 6). The first 30 s are rarely caught: at N = 3 the onset coverage is 0.107 (same file). By stratum, the onset rate is 0.889 for trip, 0.400 for pcv02d and 0.417 for other (same file).

By attack type and process: base rows of `results/phase1/segments_per_attack.csv` (`mvlit34`, band, top-3, N 6), as means over the attacks of each group. The groups are our reading of the PDF scenario codes in `attacks.csv` (`pdf_scenarios`, `processes`). "Any PV" = at least one sub-scenario manipulates a process variable (e.g. `SP1PV1`, `CO1PV1`). The type groups and the process groups each cover all 50 attacks. Trip and pcv02d attacks are counted in brackets.

| group | attacks | onset rate / chance | onset_cov mean | attacks detected (any alarm) |
|---|---|---|---|---|
| any PV | 19 (4 pcv02d) | 0.579 / 0.018 | 0.298 | 13 |
| SP only | 13 (5 trip, 1 pcv02d) | 0.462 / 0.018 | 0.282 | 9 |
| SP + CO, no PV | 7 (4 trip) | 0.571 / 0.018 | 0.286 | 4 |
| CO only | 11 | 0.364 / 0.018 | 0.167 | 4 |
| P1 only | 23 (4 pcv02d) | 0.348 / 0.018 | 0.159 | 11 |
| P2 only | 11 (6 trip) | 0.545 / 0.018 | 0.303 | 7 |
| P3 only | 2 | 0.000 / 0.018 | 0.000 | 0 |
| P1+P2 | 8 (2 trip) | 0.875 / 0.018 | 0.563 | 8 |
| P1+P3 | 3 (1 pcv02d) | 1.000 / 0.018 | 0.389 | 3 |
| P2+P3 | 3 (1 trip) | 0.333 / 0.018 | 0.167 | 1 |

- Attacks that manipulate a process variable (0.579) and SP + CO attacks (0.571, 7 attacks) have the highest onset rates of the type groups. CO-only attacks are caught least (0.364), and only 4 of 11 are detected at all. None of their PDF targets is a scored `mvlit34` channel: each is an actuator covariate or a PDF name that is not a column (`channels.csv`).
- The trip attacks lift the SP groups and the P2-only group (6 of its 11 attacks). In the "other" stratum alone, the onset rate is 0.286 for SP-only (7 attacks), 0.000 for SP + CO (3) and 0.600 for any PV (15) (same rows).
- P1-only attacks are the weakest large group (onset rate 0.348, 11 of 23 detected). Both P3-only attacks are missed. Groups of 2 or 3 attacks carry no conclusion.

**2. Does interior coverage fall below onset coverage? More for post-onset origins? Does `cf-onset` score higher?**

- **Interior vs onset: not at N = 6.** Interior coverage is 0.295 against 0.263 at onset, and the interior rate is 0.532 against 0.500 (`segments_summary.csv`). The answer depends on N. At N = 3 onset coverage is 0.107 and interior 0.315; at N = 12 onset is 0.318 and interior 0.114 (same file). In the 36 "other" attacks the interior is below the onset: 0.108 against 0.236 (same file, stratum other).
- **By origin side: yes, to zero in every h bucket.** In the same h bucket, interior coverage is 0.545 pre-onset against 0.000 post-onset at h 1-10 (44 and 143 steps), 0.328 against 0.000 at h 11-20 (174 and 67), and 0.362 against 0.000 at h 21-30 (188 and 21) (`segments_by_h.csv`).
- **`cf-onset`: yes** (a labelled diagnostic whose origin comes from the test labels). On the 231 post-onset interior steps it scores higher than rolling in 16 of 17 attacks, with a mean band score of 41.55 against 0.46. At the rolling threshold it covers 0.459 of these steps; rolling covers 0.000 (`cf_onset.csv`, `mv-lit`). `uni` shows the same: 47.92 against 0.82, coverage 0.459 against 0.004.

**3. Is it contamination, horizon, or the model forgiving the interior from a clean context?** At 10 s it is both contamination and forgiveness. Horizon is not the cause.

- **Horizon is ruled out for the post-onset zero.** The band widens about 4.7x from h = 1 to h = 30 (median 0.244 to 1.151 fit-z, `band_width_by_h.csv`, `mv-lit` calib). Post-onset interior steps have shorter horizons: mean h 9.7 against 19.5 for pre-onset (section 3.9). The h confound therefore favours alarms on the post-onset steps.
- **Contamination explains the post-onset zero.** When both contexts are clean (the pre-onset control), the cf-onset interior score is about 1.1 times the rolling one (102.30 against 91.35). On post-onset steps the ratio is about 90 (`cf_onset.csv`). Methods that never forecast from test context cover the post-onset steps about as well as the clean ones: seasonal-refday 0.442 against 0.495, frozen 0.212 against 0.222 (`segments_by_h.csv`). This covers 232 attack steps in 17 attacks.
- **Forgiveness, or plain insensitivity, explains most of the rest.** On clean context, 0.633 of interior steps get no alarm (`segments_by_h.csv`, 406 steps). Clean-context coverage itself falls after its 60-119 s peak, from 0.423 to 0.297 at 120-239 s (same file, onset and interior pooled). For mv-lit, cf-onset also has zero coverage on the post-onset interior steps of A206, A210, A212, A401 and A509 (`cf_onset.csv`). Those attacks are missed even from a clean context.

**4. Does joint forecasting per process (`mv-lit`) beat independent forecasting on matched channels, and does that survive D128?**

- **No, it is a tie.** On `mvlit34` the test PR-AUC is 0.39707 for `mv-lit` and 0.39695 for `uni` (`selection.csv`); the paired bootstrap difference is +0.000 (-0.017 to +0.020), and `uni`'s ROC-AUC is higher with an interval that excludes 0 (section 4.17). `uni` has the higher ROC-AUC (0.880 against 0.862). `mv-lit` is slightly ahead on TaPR F1 (0.400 against 0.393), onset coverage (0.263 against 0.247) and interior coverage (0.295 against 0.281). Both detect 30 of 50 attacks (`metrics.csv`, `tapr.csv`, `segments_summary.csv`).
- On `mvacttgt41` the picture is mixed in the same way (PR-AUC 0.394 against 0.388, ROC-AUC 0.874 against 0.889, `metrics.csv`).
- The base pick (`mv-lit`, picked on test results) turned on the fourth decimal of PR-AUC.
- Within the multivariate setup, it hardly matters whether the actuator commands enter as covariates or as targets. `mv-acttgt` scored on `mvlit34` gives the same PR-AUC as `mv-lit` to six decimals (0.397065, `metrics.csv`).
- **D128:** the guard is an interpretation. It moves no band-score calib threshold of the mv rolling runs by more than 0.214 (base threshold 9.442). It moves no aggregated test band score by more than 3.44, and the band score by more than 1 on only 3 of 1,341,300 test forecasts (`d128_effect.csv`, `thresholds.csv`). The univariate runs move at rounding level only (6.6e-7 z, same file). Whether any alarm flips is not measured, and no no-guard run was made (Q22). With a 0.00012 margin, the data cannot say whether the pick survives the caveat. The moves are small, so a large change to the tie is unlikely, but its effect on the PR-AUCs is not measured either.

**5. Which context protection raises interior coverage on `triggered_in_attack` attacks, at what normal-step alarm rate? Does FF free-run into false alarms? Do frozen and dual only work without `P1_PCV02Z`?** None raises it. All are labelled interpretations. Base `mv-lit`, `mvlit34`, band (dual score for dual), top-3, calib threshold:

| variant | pr_auc | fa_per_hour | p_normal | triggered_in_attack attacks | interior_cov there | rolling, same attacks |
|---|---|---|---|---|---|---|
| rolling | 0.397 | 1.112 | 0.003 | | | |
| ff-interp-block (no exit) | 0.208 | 116.489 | 0.324 | 3 | 0.262 | 0.480 |
| ff-interp-block-max30 | 0.175 | 21.236 | 0.059 | 11 (9 with an interior) | 0.255 | 0.399 |
| ff-interp-block-max60-testinf | 0.147 | 36.471 | 0.101 | 7 | 0.308 | 0.532 |
| ff-interp-block-max120 | 0.090 | 97.655 | 0.271 | 6 | 0.313 | 0.573 |
| frozen | 0.190 | 3.888 | 0.011 | | | |
| dual | 0.082 | 9.057 | 0.025 | | | |

Sources: `metrics.csv` for pr_auc and fa_per_hour; `segments_summary.csv` for p_normal, the FF groups and their interior coverage; `segments_per_attack.csv` for rolling on the same attacks. Chance PR-AUC is 0.024.

- **FF: worse on every headline metric, and it free-runs into false alarms after false triggers.** The calib split holds no attack, yet 30 of 34 channels trigger there. 0.565 of calib channel-steps and 0.766 of test channel-steps run in fallback, and 89 of the 153 test episodes start on normal steps (`ff_activity.csv`, `ff_episodes.csv`). `P1_PCV02Z` never triggers in calib, but it triggers in every test file. Without it, `ff-interp-block`'s false alarms fall from 116.489 to 1.776 per hour (`metrics.csv`). Its higher PR-AUC on that view (0.410) is not credited. In 47 of 50 attacks fallback was already active at onset (section 4.6).
- **Frozen and dual do not beat rolling on either set.** Frozen's PR-AUC is 0.190 with `P1_PCV02Z` and 0.192 without, against 0.397 and 0.345 for rolling. Dual's is 0.082 and 0.036 (`metrics.csv`), near chance. Frozen still detects above chance (onset rate 0.320 against 0.062, `segments_summary.csv`). Dropping `P1_PCV02Z` cuts frozen's false alarms from 3.888 to 1.271 per hour and raises its TaPR F1 from 0.185 to 0.262 (`metrics.csv`, `tapr.csv`). Its PR-AUC barely moves.
- **Where frozen does help.** On the 232 post-onset attack steps, frozen alarms on 50 and dual on 70; rolling alarms on none (`segments_per_attack.csv`, `n_post_origin` x `cov_post_origin` summed). That is the contamination pattern. It is not enough to make either a better detector.

**6. Does it beat `robustz`, `lastvalue` and `seasonal-refday` on the same channel sets?** Not `lastvalue`. Band score, top-3, calib threshold (`metrics.csv`; TaPR F1 from `tapr.csv`, config headline). Each cell is PR-AUC / TaPR F1 / false-alarm steps per hour.

| channel_set | Chronos-2 run | Chronos-2 | lastvalue | seasonal-refday | robustz |
|---|---|---|---|---|---|
| `uni51` | uni | 0.401 / 0.398 / 1.224 | 0.412 / 0.554 / 2.785 | 0.395 / 0.384 / 5.178 | 0.171 / 0.324 / 2.991 |
| `mvlit34` | mv-lit (base, picked on test results) | 0.397 / 0.400 / 1.112 | 0.402 / 0.538 / 2.598 | 0.385 / 0.328 / 6.449 | 0.142 / 0.230 / 2.935 |
| `mvacttgt41` | mv-acttgt | 0.394 / 0.413 / 1.206 | 0.416 / 0.560 / 2.795 | 0.389 / 0.325 / 6.468 | 0.140 / 0.234 / 3.150 |
| `uni57` | uni57 | 0.340 / 0.328 / 1.037 | 0.316 / 0.305 / 2.477 | 0.150 / 0.216 / 0.430 | 0.154 / 0.306 / 2.131 |

- A 1 h robust z-score does not match Chronos-2 on the band score. `lastvalue` does, on three of four sets: the last observed value plus a fixed band of fit-set changes. The PR-AUC gaps are small for 50 attacks; the TaPR F1 gaps are not. Chronos-2 leads only on `uni57`. Its advantage is the false-alarm rate, the lowest in every row except `seasonal-refday` on `uni57`.
- The ranking depends on the score. With `mae`, Chronos-2 has the highest PR-AUC on `uni51` and `mvlit34` (0.430 and 0.476, `metrics.csv`). On every `-noPCV02Z` set `robustz` takes that lead (mae 0.544 against 0.403 for `uni`, same file). At the calib threshold, `lastvalue` has the higher TaPR F1 in 5 of 6 (set, score) pairs (`tapr.csv`, section 4.9).
- On the headline score, the foundation model adds little over a last-value forecast here, except fewer false alarms. At equal false alarms that turns into an advantage at small alarm budgets: 28 against 14 attacks detected at 0.5 per hour on `mvlit34`, and about the same number at 5 per hour, where `lastvalue` covers more attack steps (section 4.17). With the mae score Chronos-2's median forecast beats `lastvalue` on PR-AUC on both sets (section 4.17).

**7. Where are the false alarms on normal data?** Mostly not attributable from the results files. No file splits false alarms by channel or by time.

- **How many.** The base has 119 false-alarm steps on 38,516 normal steps: 1.112 per hour, alarm steps minus alarmed attack steps (`metrics.csv`). That is below the 1.8 per hour a test set that behaved like calib would give (section 2.5).
- **Offsets.** 24 of the 119 fall in the 60 s after an attack: 15 after trip and 9 after pcv02d attacks (`segments_per_attack.csv`, `offset_n` x `offset_cov` summed). They count as false alarms because those steps are labelled normal.
- **`P1_PCV02Z`.** On the set without it, the base raises 107 false-alarm steps instead of 119, at the same threshold of 9.442 (`metrics.csv`, `thresholds.csv`). This is a set-level comparison, not a per-channel attribution. A302 and A512, the two attacks followed by its level shift, have no offset alarm (`segments_per_attack.csv`). The channel dominates the false alarms of other methods, not of rolling Chronos-2: FF (116.489 to 1.776 per hour), frozen (3.888 to 1.271) and `robustz` with mae (8.375 to 1.720) (`metrics.csv`).
- **Flat channels with zero-width bands.** Scoring the six step tags (`uni57`) raises the calib threshold from 11.589 to 19.512 (`thresholds.csv`). The 51 shared channels score identically in both runs, so the rise comes from the six tags. At that threshold `uni57` raises fewer test false alarms than `uni51` (1.037 against 1.224 per hour), but recall falls from 0.251 to 0.181 (`metrics.csv`). Net, at the calib threshold the flat tags cost recall and do not add test false alarms. Their effect at a fixed threshold is not measured.
- **Heavy-tailed transients (`P4_HT_FD`, `P1_PIT01`) and scheduled setpoint changes: not measured.** The only indirect hint is in `metrics.csv`. `uni` scored on `uni51` alarms 1.224 times per hour; scored on `mvlit34` it alarms 1.009 times. `mvlit34` lacks the 7 actuator commands and the 10 P4 channels, and each set has its own threshold. On calib, the widest Chronos-2 bands are on `P1_PIT02` and `P1_PIT01`, and on test on `P1_PCV02Z` (`quantile_diagnostics.csv`). Those are band-width events, not alarms.

**8. Which attacks does it miss entirely, and why?** The base misses 20 of 50 attacks, all in the "other" stratum. The table shows each miss with the methods that do detect it, each on its own full set (`segments_per_attack.csv`, band or dual score, top-3, N 6; durations, processes and scenarios from `attacks.csv`). "Scored target" = at least one PDF target is a scored channel of `mvlit34` (`channels.csv`). FF = `ff-interp-block`; its detections mean little at `p_normal` 0.324.

| attack | duration s (steps) | processes | pdf_scenarios | scored target | post-onset steps | detected by |
|---|---|---|---|---|---|---|
| A102 | 98 (10) | P1 | P1-FC-SP1 | no | 0 | prepend; lastvalue and seasonal-refday (both sets); FF, FF-max120 |
| A104 | 60 (7) | P2 | P2-SC-CO1 | no | 0 | seasonal-refday (both); FF, FF-max60 |
| A203 | 17 (3) | P1 | P1-LC-CO1-ST7 | no | 0 | none |
| A205 | 123 (13) | P1 | P1-PC-SP1-ST10 | yes | 0 | none |
| A206 | 256 (26) | P1 | P1-FC-CO1PV1 | yes | 8 | `uni`; lastvalue (`uni51`) |
| A209 | 199 (20) | P1 | P1-LC-SP1 | no | 9 | `uni`, `uni57`, frozen, dual; lastvalue and seasonal-refday (both); robustz (`uni51`); all FF variants |
| A210 | 421 (43) | P1 | P1-PC-CO1PV1 | yes | 37 | none |
| A211 | 45 (6) | P2 | P2-SC-SP1-ST5 | no | 0 | seasonal-refday (both); FF |
| A212 | 152 (16) | P2 | P2-SC-SP1PV1 | yes | 4 | `uni57`; seasonal-refday (both); FF |
| A214 | 152 (16) | P1 | P1-PC-CO1 | no | 0 | none |
| A215 | 151 (16) | P2 | P2-SC-CO1PV1 | yes | 0 | seasonal-refday (both); FF |
| A216 | 65 (8) | P1 | P1-FC-CO1-ST10 | no | 0 | `mv-acttgt`; lastvalue (`uni51`) |
| A219 | 119 (13) | P3 | P3-LC-CO1 | no | 0 | FF only (`pre_active`, not credited) |
| A220 | 119 (13) | P3 | P3-LC-CO2 | no | 0 | none |
| A301 | 132 (14) | P1 | P1-LC-CO1-ST+P1-FC-SP1 | no | 0 | frozen; lastvalue and seasonal-refday (both); FF |
| A303 | 189 (20) | P1 | P1-PC-CO1+P1-LC-CO1 | no | 0 | prepend; all FF variants |
| A401 | 254 (26) | P1 | P1-PC-CO1+P1-LC-SP1PV1 | yes | 14 | lastvalue (both); seasonal-refday (`uni51`) |
| A405 | 120 (13) | P2+P3 | P2-SC-SP1-ST+P3-LC-CO2 | no | 0 | seasonal-refday (both); FF, FF-max60, FF-max120 |
| A506 | 153 (16) | P2+P3 | P2-SC-CO1PV1+P3-LC-CO2 | yes | 0 | seasonal-refday (both); FF |
| A509 | 241 (25) | P1 | P1-PC-SP1+P1-PC-CO1 | yes | 2 | FF only (`pre_active`, not credited) |

- **On the band score, no method shown detects five attacks:** A203, A205, A210, A214 and A220.
- **The score matters as much as the attack.** With crps or mae, at the same calib percentile, the base itself detects 45 and 44 of 50 attacks, A203 and A210 among them, but at 4.627 and 3.243 false-alarm steps per hour against 1.112 (`segments_per_attack.csv`, `metrics.csv`). So many band-score misses come from the conservative band threshold, not from an invisible attack. A205 and A214 get no alarm in any row of `segments_per_attack.csv` (any method, score, aggregation, channel set or N). A220 is caught only in rows that are not headlines (e.g. frozen with crps).
- **Short attacks are part of it, not all of it.** The misses last 17 to 421 s, with a median of 141.5 s; the 30 detected attacks have a median of 197.5 s (`attacks.csv`). Four misses are under 70 s (A203, A211, A104, A216), but four last over 4 minutes (A206, A210, A401, A509).
- **The attacked tag is often not scored.** In 12 of the 20 misses, no PDF target is a scored `mvlit34` channel: it is an actuator or step covariate, or a PDF name that is not a column of `channels.csv`. Among the 36 "other" attacks, 6 of the 18 without a scored target are detected, against 10 of the 18 with one.
- **Setpoint attacks invisible in the recorded setpoints do not explain much.** 13 attacks target `P1_B3004` or `P1_B3005` (`attacks.csv`; section 6.2 item 7). The base detects 9 of them. It misses A102, A209, A301 and A401, and `lastvalue` on `mvlit34` detects all four.
- **Dropped tags explain no miss.** The attacks whose PDF target is a dropped tag are the 9 trip attacks, and all of them are detected.
- **Most misses are not contamination.** Only 6 of the 20 misses have any post-onset step. The other 14 are missed from a clean context.
- `seasonal-refday` on `mvlit34` detects 9 of the 20 misses, but at `p_normal` 0.018 (`segments_summary.csv`), so part of that is its alarm rate.

**9. Are offset alarms in trip attacks process anomalies rather than context effects?** They are not context effects. The data cannot confirm that they are process anomalies.

- Every offset alarm of the base comes from a forecast issued before onset. Offset coverage is 0.158 on 152 pre-onset-origin steps and 0.000 on 148 post-onset-origin steps (`segments_by_h.csv`). The context-adaptation effect would show at the offset as alarms from forecasts whose context holds the attack; there are none.
- All base offset alarms fall in trip attacks (A201, A207, A305, A507) and pcv02d attacks (A101, A402), never in an "other" attack (`segments_per_attack.csv`).
- The baselines, which do not learn from the context, also alarm in trip offsets. On `mvlit34`: `lastvalue` 27 offset alarm steps, `seasonal-refday` 21, `robustz` 17 (same file, trip stratum).
- In trip attacks the post-attack steps hold tripped-turbine data (section 6.2 item 4). That is consistent with real process deviations, but no file checks it.
- The one context effect at the offset goes the other way. cf-onset covers 0.176 of the post-onset offset steps, where rolling covers 0.000 (`cf_onset.csv`, `mv-lit`). Attack data in the context suppresses offset alarms.

**10. Cost: seconds per call on MPS against context length.**

- Cost grows with T. A `uni` call (51 rows) takes 0.122, 0.405 and 1.770 s (median) at T 1-512, 513-2,048 and 2,049-8,192 (`latency.csv`, test). A `mv-lit` call (one process group, median 10 rows) takes 0.032, 0.094 and 0.372 s. That is about 14x and 12x from the lowest to the top bucket.
- Per origin the two setups cost about the same, because `mv-lit` makes three calls per origin. Their test splits took 1,857.8 s (`uni`) and 1,726.0 s (`mv-lit`) for 1,315 origins (`runs.csv`). That is about 1.4 and 1.3 s per 300 s of data, fast enough to run online at 10 s.
- Prepend, at T = 8,192, takes 0.547 s per call (`latency.csv`).
- The default 10 s matrix took 4.72 h of inference and `--optional 10s` another 2.61 h (`runs.csv`). MPS was 1.7x faster than CPU on the same splits (`runs.csv`).
- There is no size axis (experiment 4 deferred) and no 1 s latency (D134).



---

## 6. Threats to validity

### 6.1 Model and training data

1. **Training-corpus overlap: UNCONFIRMED.** HAI, SWaT, WADI and other ICS data are **not listed in the Chronos-2
   report's full training-data list** (arXiv 2510.15821, `C2-TEX:323-330`, App. A `C2-APP:1-38`). The report says
   multivariate and covariate tasks used synthetic data only (`C2-TEX:332-343`). That is the authors' statement; it
   cannot be checked against the weights. It is not "verified absent". `autogluon/chronos-2-synth` (synthetic data
   only) would be a contamination control; it was not run (PLAN.md 14.9 item 1).
2. **Not the brief's model.** Nothing here transfers to Timestral. One model size, so no size effect can be read.
3. **Zero-shot only.** No fine-tuning and no tuning of anything on HAI. Results speak for this checkpoint used as
   shipped (plus the two adapter changes of sections 3.7-3.8).
4. **Contexts much longer than the papers'** (up to 8,192 steps against 32-128 and 100). The papers' mechanism is a
   short-window statement ("once the window lies entirely within the anomalous segment, the FM adapts to the new
   dynamics and the score collapses", `Uray:tex:469-472`); a context of up to 22.8 h is a different regime.
5. **The cap binds at 10 s** on 18.4 % of scored test steps and 12 attacks (section 2.3). It is the model limit,
   chosen before any result.
6. **Full-context normalization.** Chronos-2 scales each row by one mean and std over the whole context. A
   `P1_PCV02Z` level shift inside a context rescales that channel's whole context (PLAN.md 14.9 item 6). Scores are
   still in fit-z units because the output is mapped back.

### 6.2 Data and labels

1. **Single dataset, single plant, 50 attacks in 5 files.** Section 4.17 adds one paired block
   bootstrap (1 h blocks, D135); no other significance test is computed, and segment coverages and strata have no
   intervals. With 50 attacks, a difference of a few attacks between methods may be noise.
2. **No long-term attacks** in HAI 21.03 (17-422 s; at most 43 steps at 10 s, `attacks.csv`). The brief's
   "persistent interior" is short here. HAI 22.04 and 23.05 have long-term scenarios (Q5).
3. **10 s binning.** A bin is an attack bin if any second is; onsets move up to 9 s earlier and positive time grows
   from 8,947 s to 9,340 s (+4.4 %; `attacks.csv`, 934 x 10 s).
4. **Dropped attack-only tags** (`P1_PCV02D`, `P2_OnOff`, `P2_Emerg`): trivial evidence for 14 attacks is removed;
   in the 9 trip attacks the post-attack "normal" seconds hold tripped-turbine data (sections 3.11, 4.4).
5. **`P1_PCV02Z`**: fit std 0.00429 at 10 s (`channels.csv`); values up to about 510 fit-z. `calib` and most test
   files sit about +54 fit-z above the `fit` mean at 10 s, while the `reference` day sits near it (about -0.3 fit-z).
   A persistent level shift after A302 and A512 sits in data labelled normal (PLAN.md 3.4).
6. **Normal data is heavy-tailed** (`P4_HT_FD`, `P1_PIT01` and others, PLAN.md 3.4). A 99.5th-percentile threshold
   from `calib` is set by such transients. Many normal-labelled test rows also lie outside the train range
   (`research/hai_data.md` §7), so some false positives come from mild covariate shift, independent of the model.
7. **Setpoint attacks are invisible in the recorded setpoints** (`P1_B3004` and `P1_B3005` have zero range in their
   13 attack windows; PLAN.md 3.4, probe 11). They show only through the process variables.
8. **Label and documentation quirks, UNCONFIRMED**: A209 lasts 159 s in the PDF and 199 s in the labels (the labels
   are used); timestamp timezone; train3 documented as 229 h but holds 133 h; the PDF lists 78 tags for 21.03, the
   files have 79; meaning of `P2_CO_rpm`, `P2_HILout`, `P2_SIT02`; why `P1_PP01AD/AR` read 540833; the HAI repository
   commit of the local files (PLAN.md 3.1, 13).

### 6.3 Design choices informed by the test data (D8, copied verbatim; section references point to PLAN.md)

No test row fits normalization statistics or thresholds, and no test score or test metric tuned any hyperparameter.
These choices did use inspection of test files, test labels or the PDF attack timetable (test-informed):

1. `calib` = train1, because it shares the `P1_PCV02Z` level of test1, test2, test4 and the start of test5
   (test-file values, probe 08-09). Sensitivity: `calib2` (D51).
2. `calib` cut into two 24 h pseudo-files so its context lengths look like the test files' (test-file lengths).
3. W = 1,500 s, checked against the first-attack positions in the test labels (PLAN.md section 5).
4. N = 60 s, from test post-attack excursions (probe 05) and empty-interior counts from the test labels.
5. The 6 step tags left out of exp 1. D39 rests on train-data reasons only, but the first draft also cited test
   attack windows (probe 11).
6. `mv-acttgt` exists because the actuator commands are attack targets (PDF timetable, probe 11).
7. FF max duration 60 steps, from the longest test attack and the longest test post-attack excursion (D25).
8. 1 s cap 8,192, argued in part by the 422 s longest attack being about 5 % of the context (D12).
9. Display and diagnostics only: timeline attacks (D33), the smoke slice (chosen to contain A101), offset strata
   (D47) and `cf-onset` origins (D46).

Notes: for Chronos-2, 8,192 is also the model maximum (D118), so the 1 s cap no longer rests on item 8. Item 7 also
bounds the FF max30 and max120 values, which are half and double 60.

### 6.4 Picks on test results

Both D21 picks ("better of 1 and 2" and "best of 1-3") were made on test PR-AUC (`selection.csv`). The picked
setup's test numbers are optimistic against the others. With 50 attacks, a small PR-AUC gap can decide the pick.

### 6.5 Parameters fixed a priori, alternatives untested

`k = 3`, `eps = 0.1`, the 99.5th percentile, H = 30, stride 30 and W = 1,500 s were fixed before any result (D13,
D17, D19, D20). No alternative was run, except the N sensitivity (30 s, 120 s), the `calib2` threshold and the FF
max-duration values. Another H or stride at 10 s does change the boundary-vs-interior picture: with H = 6 the interior
drops below the onset (option B, section 4.20).

### 6.6 Interpretations that change forecasts

- D128 constant-row guard: the multivariate results are Chronos-2 with this input interpretation (section 3.7; size
  on the MPS runs in 4.13; no no-guard run, Q22).
- D119 quantile sorting: cached quantiles are sorted model output, not raw (section 3.8).
- Forecast Fallback block adaptation, scope, exit and threshold source are ours (section 3.5).
- Frozen and dual are literal readings of the brief (section 3.6).

### 6.7 Mechanism-test confounds

- The 10 s onset/interior split mostly does not test contamination (406 of 637 interior steps from clean context;
  section 3.9).
- Origin side is confounded with h and with time since onset; the h-matched contrast reduces but does not remove it.
- `cf-onset` differs from rolling in horizon and in the number of output patches (PLAN.md 14.6, 14.9 item 7).
- Whether Chronos-2 bands widen with h on HAI is measured, not assumed (`band_width_by_h.csv`, section 4.4).

### 6.8 Device and numerics

- **The MPS rule (D130) was set after seeing the check's numbers**, at Arthur's decision, so that the runs could
  finish the same night. Under the planned absolute rule every Chronos-2 row failed (section 2.7).
- The check covers rolling forecasts on the smoke slices only: contexts of at most 690 steps at 10 s, and a cap of
  2,048 at 1 s. The full runs use contexts up to 8,192 steps. FF, frozen, cf-onset and prepend contexts were not
  compared across devices. Toy checks on synthetic data at longer contexts showed only float-noise gaps
  (`research/chronos2_api.md` §7); that is not HAI evidence.
- Mixed devices: only the smoke runs on CPU (D132); every headline run is on MPS. The partial CPU run of experiment
  1 and the pre-run CPU rows of `d128_effect.csv` exist but feed no number in section 4.
- Exploding outer quantiles blind the band score and inflate crps where they occur. Bands wider than 10 fit-z are
  rare on `calib` (at most 0.0066 % of the forecasts of the headline rolling runs), 62-145x more frequent on test
  (`uni`, `mv-lit`) and about 5x more frequent again on attack steps (section 4.15). Their effect on the metrics is
  not measured.

### 6.9 Metrics

- TaPR.py detects with `> theta` (the paper says `>=`); TaPR F1 is our formula; the `haicon_like` configuration is
  not eTaPR and not comparable to the HAICon leaderboard.
- Point-adjusted F1 inflates results; it is only shown labelled.
- Chance levels assume independent alarms; alarms are autocorrelated.
- AUCs pool the per-step scores of five files; a file with a different score scale can dominate.
- Many comparisons (runs x channel sets x scores x aggregations). The headline combination (band, top-3 mean, calib,
  N = 6) was fixed before any result; the rest are secondary.

### 6.10 UNCONFIRMED items carried from PLAN.md (Chronos-2 and data)

- Whether HAI or other ICS data are in the Chronos-2 training corpus (6.1 item 1).
- Whether Chronos-2 bands widen with h on HAI (measured in `band_width_by_h.csv`).
- Which Chronos-2 checkpoint and revision Lowe et al. used.
- Forecast Fallback: threshold data source, exit rule, substitution scope, behaviour with H > 1.
- Timestamp timezone; train3 hours; A209 duration; meaning of `P2_CO_rpm`, `P2_HILout`, `P2_SIT02`; why
  `P1_PP01AD/AR` read 540833; the HAI repository commit of the local files.
- That eTaPR 1.12 was the exact HAICon 2020 wheel (relevant only to the eTaPR question, Q6).

---

## 7. Not run, deferred, not measured

| item | status | why |
|---|---|---|
| Experiment 4 (model sizes, latency vs size) | **deferred**; a two-size Chronos-2 sensitivity of `uni` rolling ran instead (section 4.18, D136) | needs Timestral, paused (D123). Chronos-2 has one checkpoint with 21 levels; `chronos-2-small` (28M) has 13 native levels, so 8 levels would be interpolated (changes crps, not band) (Q19) |
| 1 s comparison block at cap 8,192: 1 s `uni` rolling, cf-onset, the 10 s `uni` FF reference, 1 s `ff-interp-block` (the 1 s baselines ran with D137) | **not run**: deferred by Arthur until after this report (D134); `tsfm-ad all --optional`, about 26.4-27.2 h on MPS (PLAN.md 14.8 estimate; D124, D131) | cost; it is the brief's optional config, no headline depends on it, and Arthur wants this report first (section 4.16) |
| Timestral-only runs: 1 s cap 32,768, the 5M 10 s reference, 209M | gone for Chronos-2 | no Chronos-2 counterpart (`configs/timestral/`, paused) |
| No-guard `mv-lit` run (D128 off) | not run (Arthur, Q22) | `uni` and `mv-lit` tie (section 4.17), so no conclusion depends on the guard |
| D128 effect on FF runs and `uni57` | not measured | D129; the prepend run passed no constant row, so the guard never acted on it (section 4.13) |
| Size of the quantile-sorting change in the full runs | not measured | `quantile_diagnostics.csv` (D133) counts the sorted forecasts, 11.8-44.1 % per run and split (section 4.14), but not how far sorting moved q05 and q95; the only size estimate is the pre-run CPU sample (section 3.8) |
| Effect of exploding outer quantiles on the metrics | not measured | their prevalence is measured (`quantile_diagnostics.csv`, D133; section 4.15), not their effect on band or crps scores, AUCs or alarms |
| eTaPR (HAICon 2020 metric) | not added | brief says TaPR (Q6) |
| Non-TSFM diagnostic on the three attack-only tags | not run | Q12 |
| P4 as a group or as covariates in experiment 2 | not run | Q2 |
| Time-of-day-aligned frozen reference | not run | Q11 |
| FF scope `all` | not run | option exists; per-feature is the planned interpretation |
| Smoothing of scores | off | option exists, never used for a reported number |
| `chronos-2-synth` contamination control | not run | not planned (6.1 item 1) |
| TimesFM | not run | the brief's stretch; Chronos-2 is now the main model |
| Confidence intervals / significance tests | partly: one paired block bootstrap for AUCs, TaPR F1, recall and attack detection (section 4.17, D135) | no intervals for segment coverage, strata or per-attack numbers (6.2 item 1) |
| HAI 22.04 / 23.05 (long-term attacks) | not run | out of scope (D1, Q5) |

---

## 8. Open questions for Arthur

Answered by Arthur on 2026-10-20, after the first version of this report: Q1, Q2, Q3, Q6, Q11, Q12, Q15 and Q17
keep their defaults (`mv-acttgt` secondary, P4 out of experiment 2, per-file split roles, no eTaPR, the literal
frozen reference, no diagnostic of the attack-only tags, no setpoint covariates, `uni51` as the experiment 1
headline). Q9: yes (section 3.1 already describes the papers that way). Q21: yes; the Timestral rows are removed from
every committed results file, and git history was cleaned on 2026-10-21 (no commit's `results/` holds a Timestral
row, PLAN.md D152). Q22: no; the no-guard
`mv-lit` run is not done, because `uni` and `mv-lit` tie (section 4.17) and no conclusion depends on the D128 guard.
Q13: the screenshots Arthur added are the paper's Fig. 2, Fig. 4 and Sec. 3.1, the PDF we used; no FF code. Q19: yes,
run `chronos-2-small` now (section 4.18, D136). Q4: yes, option B ran (section 4.20, D138).

Still open (PLAN.md 13):

- **Q20** The 1 s run with the full 8,192-step history (about 13 h for rolling): still needed after section 4.19?
- **Q5** Run HAI 22.04 / 23.05 (a few attacks of 8-34 min, git-lfs)?
- **Q10** FF headline: no exit (`ff-interp-block`) or bounded (`ff-interp-block-max60-testinf`, test-informed)?
  Every FF variant scores below rolling (section 4.17), so the choice changes no conclusion.

Answered or moot: Q7 (Timestral paused), Q8 (no Chronos-2 counterpart), Q14 (Chronos-2 is the
Phase 1 model), Q16 (Timestral MPS shim; moot), Q18 (MPS with the relative rule, D130).

---

## 9. Reproduction

- Code: commit `27d81f2` (the run started from it). The next commit, `d0d6ee9`, changed only reporting code (`cli.py`, `pipeline.py`, new `diagnostics.py`, D133). It touched no hashed source and no config, so no forecast hash changed.
- Results: the commit `P1: Phase 1 REPORT.md ...` adds the Phase 1 result CSVs, figures and this report.
- `results/phase1/quantile_diagnostics.csv` was written after the run, from the cache, with `diagnostics.py` (commit
  `d0d6ee9`) over the same run list (D133). It made no forecast call.
- Setup and data: `README.md`.
- Commands, from the project root:

  ```bash
  uv sync
  uv run pytest -q
  uv run tsfm-ad all --optional 10s     # smoke, the 10 s matrix of PLAN.md 14.7, prepend and FF max30/120
  uv run tsfm-ad all --optional         # also the 1 s comparison block (about 27 h more on MPS)
  ```

- Estimated inference time on MPS (PLAN.md 14.8, estimates, not measurements): the default 10 s matrix about
  4.8-4.9 h; `--optional 10s` about 2.6-2.9 h more; the 1 s block about 26.4-27.2 h more.

Measured on MPS. Per-run wall-clock is `wallclock_s` from `results/phase1/runs.csv`, summed over the run's splits (section 4.0 gives it per split). It includes any system sleep (D80). The D128 steps and the whole-run total come from `cache/logs/all_mps_10s_20261020.log`. Estimates are from PLAN.md 14.8, base `mv-lit` column.

| block / run | splits | measured wall-clock (h) | measured (s) | PLAN.md 14.8 estimate (h) |
|---|---|---|---|---|
| exp 1 `uni` rolling | calib, calib2, test | 0.95 | 3,416.5 | 0.97 |
| exp 1 `uni` cf-onset | test | 0.02 | 71.6 | 0.02 |
| exp 1 `uni57` rolling | calib, test | 0.81 | 2,901.9 | 0.83 |
| exp 2 `mv-lit` rolling | calib, calib2, test | 0.88 | 3,172.2 | 0.88 |
| exp 2 `mv-lit` cf-onset | test | 0.02 | 68.0 | 0.02 |
| exp 2 `mv-acttgt` rolling | calib, test | 0.68 | 2,445.0 | 0.68 |
| exp 5 baselines (3 runs) | calib, test | < 0.01 | 2.9 | not estimated |
| exp 3b `mv-lit` frozen | ref | < 0.01 | 2.8 | < 0.01 |
| exp 3c `mv-lit` dual | none (no inference) | 0 | 0 | 0 |
| exp 3a `mv-lit` ff-interp-block | calib, test | 0.68 | 2,447.4 | 0.68 |
| exp 3a `mv-lit` ff-interp-block-max60-testinf | calib, test | 0.68 | 2,450.4 | 0.68 |
| **default 10 s matrix, inference** | 23 splits | **4.72** | **16,978.7** | **4.8** |
| D128 effect (D129), 6 steps (log) | | 0.21 | 740.2 | about 0.2 |
| optional `mv-lit` prepend | calib, test | 1.25 | 4,502.6 | 1.22 |
| optional `mv-lit` ff-interp-block-max30 + -max120 | calib, test each | 1.36 | 4,898.1 | 1.36 |
| **`--optional 10s`, inference** | 6 splits | **2.61** | **9,400.7** | **2.58** (1.22 + 1.36) |
| everything else: smoke from cache, prepare, scoring, evaluation, select, tables, plots (log total minus the rows above) | | 0.03 | 106.8 | not estimated |
| **whole `tsfm-ad all --optional 10s`** (log: `all done in 27226.4 s`) | | **7.56** | **27,226.4** | |
| 1 s block (1 s `uni` rolling, baselines, cf-onset, FF; 10 s `uni` FF reference) | | not run (D134) | | 26.4-27.2 |

- Measured inference matches the estimate: 4.72 h against 4.8 h for the default 10 s matrix, and 2.61 h against 2.58 h for `--optional 10s`. No run is off by more than about 0.03 h (the largest gap is prepend, 1.25 h against 1.22 h).
- Inference and the D128 re-runs take 99.6 % of the 7.56 h. Scoring, evaluation and plots at 10 s take seconds.
- MPS against CPU on the same splits: the stopped CPU run took 1,326.8 s (calib) and 1,315.8 s (calib2) for `uni` rolling, against 779.7 s and 779.0 s on MPS (`runs.csv`). MPS was 1.7x faster; D130 assumed about 1.8x.

Reproduction check (2026-10-20, after the run). For `mv-lit` rolling (`c06bc843`), `uni` rolling (`47703ec2`) and
the `lastvalue` baseline (`d6ae24ee`), `tsfm-ad score` and `tsfm-ad evaluate` were re-run from the cached forecasts
into a scratch cache and results directory (symlinks to the forecasts, fresh `scores/`), with the same forecast hashes
and no model import. `metrics.csv`, `tapr.csv`, `thresholds.csv`, `segments_per_attack.csv`, `segments_by_h.csv`,
`band_width_by_h.csv` and every cached score parquet matched exactly (max abs difference 0). Two columns of
`segments_summary.csv`, `latency_common_median_s` and `n_common`, use the attacks that every method of the comparison
group detects (D48). They depend on which other runs are in the results directory, so they reproduce only together
with the whole group; recomputed over the full groups, all 576 rows matched. `uv run pytest -q`: 104 passed. Not
re-run: `cf_onset.csv`, the `ff_*` CSVs, `latency.csv`, `quantile_diagnostics.csv`, `selection.csv` and the figures.

Known gap: `tsfm-ad score` or `evaluate --config configs/exp5_baselines.yaml` does not reach a baseline run, because
that config leaves `setup` at the base default `uni`. `all` and `smoke` score each baseline through
`baselines.baseline_cfg`. By hand, use a config that inherits `exp5_baselines.yaml` and sets `setup: lastvalue`
(or `robustz`, `seasonal-refday`) and `variant: {kind: rolling}`.

---

## 10. Phase 2: IT on LANL with injected anomalies

**Status:** Phase 2 ran on 2026-10-21 after Arthur's Phase 1 sign-off; every stage finished. Plan: PLAN.md section 15, decisions
D139-D150. Model: Chronos-2 (`amazon/chronos-2`, the Phase 1 checkpoint), not Timestral. Every number comes from
`results/phase2/` (main study) or `results/phase2/flows/` (flows sub-study).

### 10.1 Setup

**Data.** LANL "Comprehensive, Multi-Source Cyber-Security Events" (Kent 2015, doi 10.17021/1179829): 58 days of
de-identified events at 1 s resolution, calendar undisclosed. Downloaded on 2026-10-21 through LANL's form with
Arthur's approval (D139): `auth.txt.gz` (7,626,505,158 bytes, 1,051,430,459 events), `flows.txt.gz`
(1,083,479,090 bytes) and `redteam.txt.gz` (749 events, all on days 1-29). DuckDB streamed the gzip files into
per-minute tables (`lanl.py`); no file was loaded whole.

**Series** (`results/phase2/series.csv`, D140, D148). 13 per-minute series from `auth.txt.gz`, in three groups:

| group | series | definition |
|---|---|---|
| tenant | `auth_total`, `auth_failed`, `users_distinct` | auth events; events with `Fail`; distinct source users without machine accounts |
| dc | `dc_1`-`dc_5` | auth events with destination C586, C612, C529, C467, C457: the top 5 destinations by volume on the fit days ("DC-like"; LANL labels no domain controller) |
| host | `host_1`-`host_5` | auth events with source computer C625, C1065, C528, C2106, C2162: the top 5 sources on the fit days outside the DC-like five |

Transform: log1p, then a z-score with fit-day mean and std per series (D141).

**Splits** (`results/phase2/splits.csv`, D142, D148): fit days 0-33 (normalization, top-5 selection), calib days
34-40 (thresholds), test days 41-57 (17 days, 29.3 %, the only days with injections). One contiguous series: each
forecast reads up to 8,192 minutes (5.7 days) before its origin, across split boundaries, never after it.

**Injections** (`results/phase2/injections.csv`, `inject.py`, D143). On raw values, in test only, labelled per
series, seeds 0, 1 and 2, each (type, magnitude, duration) twice per seed (6 trials per point), no overlap within a
group (blocked from 1 h before to 6 h after each injection):

| type | targets | magnitudes | durations |
|---|---|---|---|
| silence | `auth_total`, `users_distinct`, `dc_*`, `host_*` | kept fraction 0, 0.1, 0.5 of normal | 30, 180 min |
| burst (brute force) | `auth_failed` | + k x the median of the 60 minutes before, k = 2, 5, 20 | 10, 60 min |
| ramp (slow rise) | `host_*` | linear to + 50 %, + 200 %, + 1,000 % at the last minute | 2 h, 8 h |
| shift (baseline shift) | `auth_total`, `dc_*` | + 20 %, + 50 %, + 100 % | 6 h, 24 h |

**Methods** (D144, D145): Chronos-2 multivariate per group (`mv`, the Phase 1 best setup, picked on test results
and tied with `uni`), H = 30 min, stride 30, history up to 8,192 minutes; `mv-cov` adds known-future covariates
(time of day as sin and cos, day index / 58; the true weekday is unknown); context protection on `mv`: `mv-ff`
(ff-interp-block, the Phase 1 interpretation), `mv-frozen` (INTERPRETATION: 48 fixed forecasts, one per 30-min
time-of-day slot, from the clean minutes ending at that slot on the last fit day) and `mv-dual` (rolling vs frozen).
Baselines on the same series: `lastvalue`, `seasonal-naive` (lag 1 day) and `robustz` (median and MAD of the
trailing 60 min), with fit-day change quantiles as bands.

**Scores and metrics** (D146): band score per series (eps 0.1; mae and crps logged); an alarm when a series' score
exceeds the 99.5th percentile of its own calib scores. An injection is detected by an alarm on its series in
[start, end + 30 min); latency = first alarm minus start; coverage = share of injected minutes that alarm. False
alarms are counted per series-day on test minutes outside [start - 1 h, end + 6 h) of that series' injections; the
calib 99.5th percentile alone gives 7.2 per series-day.

**Device.** MPS; the Phase 2 D54-style check on the smoke days passed (`mv` rolling on calib day 40 and test days
41-42, 1,179,360 values, max relative gap 6.6e-6, identical alarms; `results/phase2/smoke/mps_check.csv`).

### 10.2 Deviations from the brief and labelled interpretations

- **Flow bytes replaced by auth activity per source host (D148, Arthur's decision).** Flows are complete only on days
  0-14: from day 15 the number of source hosts drops from about 8,000 to about 900 per day, after day 23 the stream
  almost stops, and days 26-29 hold scraps (`cache/lanl/prepared/src_bytes_minute.parquet` per day). The brief's
  "bytes out per top-N source hosts" cannot carry a test period, so the main study's host group counts auth events
  per source computer, and its ramp is a slow rise of one host's auth activity, not data exfiltration.
- **Flows sub-study (D149, Arthur's request).** The exfiltration ramp on flow bytes runs separately on days 0-14 (fit
  0-8, calib 9-10, test 11-14), on the top-5 flow sources of the fit days (C1707, C5720, C1685, C20101, C5721), each
  forecast alone, ramps only, kept clear of the red-team windows of days 12-14; 11 of 12 ramps per seed fit
  (`results/phase2/flows/injections_dropped.txt`). 4 test days and 33 trials: reported as a sub-study.
- **Interpretations:** the frozen reference aligned to time of day (D145); burst only on `auth_failed`, as the brief
  says "failed auth", so `auth_total` does not rise with it (D143); top-N by volume as "DC-like" (the brief's own
  caveat); a fixed 99.5th-percentile threshold per series rather than per group.
- **Not run:** `uni` (cost; it ties `mv` in Phase 1); Timestral (paused).

**Run.** 2026-10-21 09:33-14:12 on MPS, in stages through a driver script that calls the same `p2` functions (D150;
`tsfm-ad p2 --stage all` runs the same steps in one go): `mv`, `mv-frozen`, dual and the
baselines, red team and figures; then `mv-cov`; the flows sub-study; `mv-ff` last. Every stage finished. The GPU was
shared with option B (section 4.20) for most of the run, so the times below are not latency measurements. Inference
(`results/phase2/runs.csv`, calib plus 3 seeds): `mv` 3,768.1 s (267 calls), `mv-cov` 6,015.2 s, `mv-frozen` 62.7 s,
`mv-ff` 4,756.1 s (8,352 calls, origin by origin), the baselines seconds. Crossed quantiles were sorted in 1.8 % of
`mv` forecasts, 1.7 % of `mv-cov` and 31.4 % of `mv-ff` forecasts (same file). All 48 injections per seed fit the
schedule (`injections.csv`, 144 trials, 36 per type).

**Chance level (added after the run, D151).** An injection counts as detected when any alarm falls in
[start, end + 30 min). With about 7 false alarms per series-day, a 24 h window holds a false alarm most of the time,
so detection rates of long injections mean little on their own. `chance` is the share of windows of the same length,
placed on normal test minutes of the same series and seed, that hold at least one alarm. Onset coverage = share of
alarming minutes in the first 30 min of an injection, interior = the rest of it (injections longer than 30 min only),
offset = the 30 min after its end. The coverage chance level is `p_normal`, the share of normal test minutes that
alarm. Both come from the cached scores, with no new forecast; the thresholds are unchanged.

### 10.3 Results: injections in the auth series (main study)

**All 144 trials per method** (`results/phase2/detections.csv`, `false_alarms.csv`, `false_alarms_summary.csv`; band
score, dual score for `mv-dual`; per-series calib 99.5th percentile; calib rate by construction 7.2 per series-day):

| run | detected / trials | chance | median latency (min) | onset / interior / offset cov | false alarms per series-day | p_normal |
|---|---|---|---|---|---|---|
| `mv` | 128/144 | 0.40 | 0 | 0.364 / **0.004** / 0.288 | 6.70 | 0.0047 |
| `mv-cov` | 129/144 | 0.40 | 0 | 0.359 / 0.004 / 0.272 | 6.38 | 0.0044 |
| `mv-frozen` (interpretation) | 91/144 | 0.24 | 0 | 0.376 / 0.313 / 0.023 | 41.83 | 0.0290 |
| `mv-dual` (interpretation) | 82/144 | 0.19 | 17 | 0.183 / 0.340 / 0.231 | 47.48 | 0.0330 |
| `mv-ff` (interpretation) | 72/144 | 0.28 | 0 | 0.321 / 0.312 / 0.210 | 254.95 | 0.1771 |
| `lastvalue` | 102/144 | 0.22 | 0 | 0.316 / 0.018 / 0.284 | 11.03 | 0.0077 |
| `seasonal-naive` | 87/144 | 0.18 | 1 | 0.316 / 0.297 / 0.044 | 42.91 | 0.0298 |
| `robustz` | 121/144 | 0.35 | 0 | 0.549 / 0.080 / 0.392 | 8.83 | 0.0061 |

**Per type** (same files; detected / trials, chance, onset / interior / offset coverage):

| run | silence | burst (`auth_failed`) | ramp (`host_*`) | shift (`auth_total`, `dc_*`) |
|---|---|---|---|---|
| `mv` | 33/36, 0.25, 0.470 / 0.007 / 0.404 | 35/36, 0.15, 0.644 / 0.000 / 0.244 | 29/36, 0.51, 0.069 / 0.007 / 0.259 | 31/36, 0.67, 0.272 / 0.002 / 0.247 |
| `mv-cov` | 33/36, 0.25, 0.468 / 0.002 / 0.368 | 35/36, 0.15, 0.645 / 0.000 / 0.227 | 29/36, 0.50, 0.065 / 0.008 / 0.243 | 32/36, 0.70, 0.259 / 0.002 / 0.249 |
| `mv-frozen` | 23/36, 0.16, 0.456 / 0.341 / 0.003 | 32/36, 0.24, 0.750 / 0.696 / 0.037 | 22/36, 0.35, 0.120 / 0.268 / 0.040 | 14/36, 0.20, 0.177 / 0.154 / 0.012 |
| `mv-dual` | 24/36, 0.13, 0.267 / 0.440 / 0.253 | 23/36, 0.21, 0.284 / 0.615 / 0.259 | 22/36, 0.27, 0.079 / 0.325 / 0.324 | 13/36, 0.15, 0.101 / 0.167 / 0.086 |
| `mv-ff` | 20/36, 0.27, 0.444 / 0.513 / 0.156 | 24/36, 0.23, 0.428 / 0.465 / 0.244 | 23/36, 0.55, 0.327 / 0.379 / 0.404 | 5/36, 0.08, 0.086 / 0.069 / 0.037 |
| `lastvalue` | 29/36, 0.16, 0.423 / 0.008 / 0.419 | 35/36, 0.03, 0.646 / 0.000 / 0.370 | 20/36, 0.38, 0.081 / 0.047 / 0.224 | 18/36, 0.32, 0.113 / 0.004 / 0.124 |
| `seasonal-naive` | 24/36, 0.14, 0.576 / 0.549 / 0.002 | 24/36, 0.05, 0.498 / 0.467 / 0.019 | 24/36, 0.29, 0.098 / 0.265 / 0.058 | 15/36, 0.24, 0.094 / 0.117 / 0.099 |
| `robustz` | 33/36, 0.22, 0.769 / 0.063 / 0.380 | 36/36, 0.19, 0.974 / 0.359 / 0.508 | 24/36, 0.49, 0.096 / 0.022 / 0.341 | 28/36, 0.52, 0.357 / 0.007 / 0.341 |

**Detection rate / chance per (type, duration)**, magnitudes pooled, 18 trials each (`detections.csv`):

| type | duration | `mv` | `mv-cov` | `mv-frozen` | `mv-dual` | `mv-ff` | `lastvalue` | `seasonal-naive` | `robustz` |
|---|---|---|---|---|---|---|---|---|---|
| burst | 10 | 0.94 / 0.10 | 0.94 / 0.10 | 0.83 / 0.22 | 0.33 / 0.19 | 0.67 / 0.22 | 0.94 / 0.02 | 0.67 / 0.04 | 1.00 / 0.13 |
| burst | 60 | 1.00 / 0.20 | 1.00 / 0.20 | 0.94 / 0.27 | 0.94 / 0.23 | 0.67 / 0.24 | 1.00 / 0.04 | 0.67 / 0.06 | 1.00 / 0.25 |
| ramp | 120 | 0.72 / 0.33 | 0.72 / 0.31 | 0.50 / 0.22 | 0.56 / 0.18 | 0.56 / 0.45 | 0.39 / 0.21 | 0.56 / 0.19 | 0.50 / 0.33 |
| ramp | 480 | 0.89 / 0.69 | 0.89 / 0.69 | 0.72 / 0.48 | 0.67 / 0.37 | 0.72 / 0.66 | 0.72 / 0.55 | 0.78 / 0.39 | 0.83 / 0.65 |
| shift | 360 | 0.83 / 0.50 | 0.94 / 0.54 | 0.44 / 0.20 | 0.44 / 0.14 | 0.22 / 0.14 | 0.50 / 0.25 | 0.33 / 0.21 | 0.78 / 0.41 |
| shift | 1440 | 0.89 / 0.84 | 0.83 / 0.87 | 0.33 / 0.21 | 0.28 / 0.16 | 0.06 / 0.03 | 0.50 / 0.39 | 0.50 / 0.27 | 0.78 / 0.62 |
| silence | 30 | 0.89 / 0.15 | 0.89 / 0.14 | 0.67 / 0.11 | 0.72 / 0.10 | 0.44 / 0.25 | 0.83 / 0.09 | 0.72 / 0.11 | 0.89 / 0.14 |
| silence | 180 | 0.94 / 0.36 | 0.94 / 0.36 | 0.61 / 0.20 | 0.61 / 0.15 | 0.67 / 0.29 | 0.78 / 0.22 | 0.61 / 0.17 | 0.94 / 0.31 |

**Detection curves: detected / trials per (type, duration, magnitude)**, 6 trials each (`curves.csv`; figure
`results/phase2/figures/detection_curves.png`, with `mv`'s chance level shaded):

| type | duration (min) | magnitude | `mv` | `mv-cov` | `mv-frozen` | `mv-dual` | `mv-ff` | `lastvalue` | `seasonal-naive` | `robustz` |
|---|---|---|---|---|---|---|---|---|---|---|
| burst | 10 | 2 | 5/6 | 5/6 | 4/6 | 3/6 | 4/6 | 5/6 | 2/6 | 6/6 |
| burst | 10 | 5 | 6/6 | 6/6 | 5/6 | 1/6 | 4/6 | 6/6 | 4/6 | 6/6 |
| burst | 10 | 20 | 6/6 | 6/6 | 6/6 | 2/6 | 4/6 | 6/6 | 6/6 | 6/6 |
| burst | 60 | 2 | 6/6 | 6/6 | 5/6 | 5/6 | 3/6 | 6/6 | 1/6 | 6/6 |
| burst | 60 | 5 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 5/6 | 6/6 |
| burst | 60 | 20 | 6/6 | 6/6 | 6/6 | 6/6 | 3/6 | 6/6 | 6/6 | 6/6 |
| ramp | 120 | 0.5 | 3/6 | 3/6 | 2/6 | 2/6 | 2/6 | 1/6 | 2/6 | 2/6 |
| ramp | 120 | 2 | 4/6 | 4/6 | 4/6 | 4/6 | 4/6 | 4/6 | 5/6 | 4/6 |
| ramp | 120 | 10 | 6/6 | 6/6 | 3/6 | 4/6 | 4/6 | 2/6 | 3/6 | 3/6 |
| ramp | 480 | 0.5 | 5/6 | 5/6 | 3/6 | 3/6 | 5/6 | 4/6 | 4/6 | 5/6 |
| ramp | 480 | 2 | 5/6 | 5/6 | 5/6 | 4/6 | 3/6 | 5/6 | 5/6 | 5/6 |
| ramp | 480 | 10 | 6/6 | 6/6 | 5/6 | 5/6 | 5/6 | 4/6 | 5/6 | 5/6 |
| shift | 360 | 0.2 | 5/6 | 6/6 | 3/6 | 3/6 | 0/6 | 3/6 | 0/6 | 5/6 |
| shift | 360 | 0.5 | 4/6 | 5/6 | 2/6 | 2/6 | 1/6 | 3/6 | 3/6 | 4/6 |
| shift | 360 | 1 | 6/6 | 6/6 | 3/6 | 3/6 | 3/6 | 3/6 | 3/6 | 5/6 |
| shift | 1440 | 0.2 | 4/6 | 3/6 | 0/6 | 0/6 | 0/6 | 1/6 | 2/6 | 3/6 |
| shift | 1440 | 0.5 | 6/6 | 6/6 | 3/6 | 2/6 | 1/6 | 4/6 | 3/6 | 6/6 |
| shift | 1440 | 1 | 6/6 | 6/6 | 3/6 | 3/6 | 0/6 | 4/6 | 4/6 | 5/6 |
| silence | 30 | 0 | 6/6 | 6/6 | 5/6 | 5/6 | 4/6 | 6/6 | 6/6 | 6/6 |
| silence | 30 | 0.1 | 5/6 | 5/6 | 4/6 | 5/6 | 2/6 | 5/6 | 3/6 | 5/6 |
| silence | 30 | 0.5 | 5/6 | 5/6 | 3/6 | 3/6 | 2/6 | 4/6 | 4/6 | 5/6 |
| silence | 180 | 0 | 6/6 | 6/6 | 5/6 | 5/6 | 6/6 | 6/6 | 6/6 | 6/6 |
| silence | 180 | 0.1 | 6/6 | 6/6 | 3/6 | 3/6 | 4/6 | 4/6 | 1/6 | 6/6 |
| silence | 180 | 0.5 | 5/6 | 5/6 | 3/6 | 3/6 | 2/6 | 4/6 | 4/6 | 5/6 |

**False alarms per series-day by series** (`false_alarms.csv`, all seeds; figure `false_alarms.png`):

| run | `auth_total` | `users_distinct` | `dc_2` | `dc_1` | `dc_4` | `auth_failed` | `host_5` | `host_4` | `dc_5` | `dc_3` | `host_2` | `host_1` | `host_3` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `mv` | 3.7 | 4.2 | 3.0 | 8.4 | 3.2 | 7.8 | 16.9 | 10.6 | 5.3 | 13.6 | 4.5 | 5.3 | 0.1 |
| `mv-cov` | 4.6 | 4.5 | 3.9 | 8.0 | 2.6 | 7.8 | 14.1 | 10.1 | 4.8 | 11.5 | 5.1 | 5.3 | 0.2 |
| `mv-frozen` | 13.3 | 47.1 | 0.8 | 31.1 | 0.0 | 71.2 | 302.4 | 8.6 | 43.7 | 5.6 | 7.1 | 9.2 | 0.0 |
| `mv-dual` | 16.6 | 61.4 | 0.4 | 38.3 | 0.0 | 66.0 | 311.7 | 13.2 | 71.1 | 6.6 | 13.2 | 10.3 | 0.0 |
| `mv-ff` | 0.0 | 6.8 | 0.4 | 200.4 | 0.1 | 213.2 | 624.0 | 991.4 | 60.6 | 1.8 | 273.2 | 873.8 | 0.0 |
| `lastvalue` | 5.4 | 6.0 | 3.5 | 38.9 | 0.5 | 2.2 | 46.2 | 3.2 | 4.2 | 7.9 | 7.1 | 14.0 | 0.1 |
| `seasonal-naive` | 50.8 | 4.7 | 2.1 | 39.5 | 0.5 | 29.5 | 317.6 | 8.7 | 32.0 | 11.1 | 36.3 | 18.6 | 3.6 |
| `robustz` | 5.1 | 6.4 | 2.5 | 10.7 | 0.7 | 11.6 | 26.6 | 16.7 | 5.7 | 11.5 | 6.2 | 10.2 | 0.0 |

Timing of the boiling-frog detections (`detections.csv`, band): of the 31 shifts `mv` detects, 26 alarm within 30
min of the start and none only after the end. Of its 29 detected ramps, 10 alarm within 30 min of the start and 7
only at or after the end, when the ramp drops back to normal (5 of 13 for 2 h ramps, 2 of 16 for 8 h ramps); median
latency 45 min (2 h) and 95 min (8 h).

Four example timelines (`results/phase2/figures/timelines.png`, seed 0, largest magnitude and longest duration per
type): `mv`'s band follows a 24 h shift of `auth_total` within one 30-min forecast and its band score alarms only at
the step up and the step down; the burst and the silence are flagged at their start and end, not in between; the 8 h
ramp of `host_5` alarms near its start and at its end. The frozen band stays where it was, far from the observed
level of `auth_failed` in the burst panel.

### 10.4 Results: red team and the flows sub-study

**Red team** (`results/phase2/redteam.csv`): `mv` rolling around the 20 clusters of red-team events (days 1-29, so in
the fit period, with no injection), with each cluster widened by 3 h on both sides, against the `mv` calib thresholds.
From the calib rate alone 13 series give about 3.9 alarms per hour.

| day | events | window (min) | alarm series-minutes | alarms per hour | during the events, per hour | max score / threshold | series |
|---|---|---|---|---|---|---|---|
| 1 | 10 | 457 | 31 | 4.1 | 5.6 | 6.33 | `users_distinct` |
| 2 | 15 | 771 | 31 | 2.4 | 1.8 | 2.27 | `host_4` |
| 5 | 21 | 887 | 72 | 4.9 | 3.3 | 3.64 | `dc_5` |
| 6 | 3 | 463 | 23 | 3.0 | 3.5 | 4.07 | `dc_5` |
| 7 | 1 | 361 | 56 | 9.3 | 0.0 | 7.96 | `users_distinct` |
| 8 | 273 | 1178 | 116 | 5.9 | 5.9 | 38.64 | `host_5` |
| 9 | 15 | 366 | 27 | 4.4 | 0.0 | 2.75 | `auth_total` |
| 12 | 209 | 943 | 100 | 6.4 | 6.4 | 6.85 | `host_5` |
| 13 | 81 | 901 | 81 | 5.4 | 4.8 | 35.04 | `host_5` |
| 14 | 35 | 725 | 293 | 24.2 | 19.2 | 45.78 | `host_5` |
| 15 | 4 | 366 | 29 | 4.8 | 0.0 | 4.94 | `users_distinct` |
| 15 | 22 | 558 | 18 | 1.9 | 2.4 | 9.12 | `host_5` |
| 20 | 1 | 361 | 30 | 5.0 | 0.0 | 4.48 | `users_distinct` |
| 21 | 4 | 437 | 55 | 7.6 | 6.2 | 41.44 | `host_5` |
| 22 | 1 | 361 | 27 | 4.5 | 0.0 | 4.21 | `users_distinct` |
| 26 | 26 | 544 | 30 | 3.3 | 3.6 | 1.92 | `dc_3` |
| 27 | 9 | 690 | 49 | 4.3 | 5.3 | 4.52 | `host_4` |
| 28 | 3 | 472 | 50 | 6.4 | 4.3 | 53.61 | `dc_1` |
| 29 | 1 | 361 | 29 | 4.8 | 0.0 | 3.79 | `dc_4` |
| 29 | 15 | 476 | 50 | 6.3 | 6.2 | 4.22 | `dc_4` |

Alarms per hour in the windows range from 1.9 to 24.2 and during the events from 0.0 to 19.2. Only day 14 stands
out (24.2 per hour, max score 45.8x the threshold on `host_5`), and its alarms are spread over the whole 725-min
window, not concentrated in the events (19.2 per hour during them). The same `host_5` (C2162) gives the highest ratio
on days 8, 12, 13, 15 and 21, and it is the series with the most false alarms in test (16.9 per day for `mv`). 701 of the
749 red-team events have source computer C17693 (`data/lanl/redteam.txt.gz`), which is none of the 13 series'
entities, and at tenant level they are a vanishing share of the auth events. **The red team is invisible in these
aggregates**, as the brief anticipated.

**Flows sub-study** (D149; `results/phase2/flows/`, days 0-14, ramps on flow bytes of the top-5 flow sources, each
series forecast alone; 33 trials, 3 dropped by the scheduler, `injections_dropped.txt`; `mv-ff` not run here):

| run | detected / trials | chance | median latency (min) | onset / interior / offset cov | false alarms per series-day | p_normal |
|---|---|---|---|---|---|---|
| `mv` | 23/33 | 0.55 | 97 | 0.013 / 0.016 / 0.018 | 13.75 | 0.0096 |
| `mv-cov` | 21/33 | 0.56 | 104 | 0.014 / 0.016 / 0.016 | 14.26 | 0.0099 |
| `mv-frozen` | 24/33 | 0.43 | 24 | 0.125 / 0.150 / 0.149 | 27.48 | 0.0191 |
| `mv-dual` | 20/33 | 0.25 | 24 | 0.141 / 0.161 / 0.171 | 43.65 | 0.0303 |
| `lastvalue` | 21/33 | 0.35 | 50 | 0.039 / 0.062 / 0.064 | 15.60 | 0.0108 |
| `seasonal-naive` | 25/33 | 0.47 | 75 | 0.133 / 0.152 / 0.169 | 24.61 | 0.0171 |
| `robustz` | 17/33 | 0.40 | 25 | 0.060 / 0.061 / 0.082 | 20.19 | 0.0140 |

Per duration (detection rate / chance, `flows/detections.csv`): 2 h ramps `mv` 0.50 / 0.39, `mv-frozen` 0.78 /
0.31, `mv-dual` 0.67 / 0.18, `seasonal-naive` 0.67 / 0.32; 8 h ramps `mv` 0.93 / 0.74, `mv-frozen` 0.67 / 0.57,
`seasonal-naive` 0.87 / 0.66. Flow bytes are noisier than auth counts: even `mv` raises 13.75 false alarms per
series-day in test, almost twice its calib rate.

### 10.5 What Phase 2 shows

- **The hypothesis holds on LANL, plainly.** Rolling Chronos-2 (`mv`) catches the start (onset coverage 0.364) and
  the end (offset 0.288) of injected anomalies and misses their interior: 0.004, which is its normal-minute alarm
  rate (0.0047). It adapts to a new level within one 30-min forecast. That is the shape the hypothesis predicts. On
  HAI at 10 s with H = 30 it did not appear (section 4.4); here the injections last 30 min to 24 h against a 30-min
  forecast, as in the 1 s and option B settings (sections 4.19, 4.20).
- **Boiling frog: a step is seen once, a ramp mostly at its end.** A baseline shift is flagged at the step (26 of 31
  detections within 30 min) and then accepted as normal for the rest of its 6 or 24 h (interior coverage 0.002). A
  slow rise of one host's auth activity has onset coverage 0.069 and interior 0.007; 7 of 29 detected ramps alarm only
  when the ramp drops back, and the 8 h ramps beat chance only narrowly (0.89 against 0.69). Detection rates near 1
  for 24 h shifts (0.89) sit on a chance level of 0.84: on long injections, "detected" alone says almost nothing.
- **Protecting the context buys the interior at a high false-alarm price.** The frozen reference (an interpretation:
  fixed forecasts per time-of-day slot from the last fit day) does not adapt, so it covers the interior (0.313 overall,
  0.154 on shifts, 0.268 on ramps), but it alarms on 0.029 of normal minutes, 6x the `mv` rate. Its reference ages over
  17 test days, and on `host_5` it raises 302 false alarms per day. Dual is similar (0.0330). Forecast Fallback (our
  interpretation, no exit) runs away as in Phase 1: 255 false alarms per series-day, 0.177 of normal minutes.
- **Covariates do not reduce false alarms materially.** With time of day and day index as known-future covariates,
  `mv-cov` raises 6.38 false alarms per series-day against 6.70 (lower in each seed: 6.34-6.43 against 6.64-6.73, but
  the seeds share most normal minutes) and detects 129 against 128 trials. On flow bytes it raises more, 14.26 against
  13.75. The weekday is unknown in LANL, so the strongest calendar covariate is missing.
- **Baselines: `robustz` is close and covers more.** A rolling median and MAD over 60 min detects 121 of 144 (`mv`
  128) at 8.83 against 6.70 false alarms per series-day, with higher onset (0.549) and interior (0.080) coverage.
  `lastvalue` detects 102 at 11.03. Chronos-2 detects the most trials at the lowest false-alarm rate, but no
  equal-false-alarm comparison was built for Phase 2, so the ranking is at different alarm rates.
- **Flow bytes: the exfiltration ramp is invisible to rolling Chronos-2.** Coverage 0.013-0.018 in every segment,
  against a normal alarm rate of 0.0096, and detection 23/33 against a chance of 0.55. The non-adapting references see
  it: `mv-frozen` and `seasonal-naive` cover 0.15 of the ramp minutes at about 2x the false alarms. 33 trials on 4 test
  days: a sub-study, not a result to lean on.
- **The red team is invisible** in per-minute tenant, DC-like and host counts (above).

### 10.6 Not run, deferred, limits

- `uni` on LANL: not run (cost; it ties `mv` in Phase 1). Timestral: paused. `mv-ff` on flows: not run.
- No equal-false-alarm comparison and no bootstrap intervals for Phase 2; 6 trials per curve point.
- Chance levels and onset/interior/offset coverage were added after the run (D151). They are evaluation only; no
  threshold, horizon or score was changed after seeing them.
- The real-data smoke (2 test days) ran the MPS check and `mv` / `mv-cov`; its FF step failed because `p2.py` was
  edited during the smoke run (a new cache key). The full run started after the commit, so its keys are consistent;
  the FF code path was first exercised on real data by the full run.
- Injections are synthetic and applied to raw counts; real attacks change several series at once. Thresholds are per
  series at a fixed 99.5th percentile; the per-series false-alarm rates in test range from 0.1 to 16.9 per day for
  `mv`, so one percentile does not fit every series.
- Two baseline thresholds are 0: `lastvalue` on `dc_5` and `seasonal-naive` on `users_distinct` (over 99.5 % of
  calib minutes lie inside their bands, `thresholds.csv`), so any excursion alarms there.
