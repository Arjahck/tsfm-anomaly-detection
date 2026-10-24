// The paper (PLAN.md D153). Build: `uv run --extra paper tsfm-ad paper` (tables and figures from results/, then
// this file to paper/paper.pdf). Every table is read from results/paper/*.csv; every number in the text comes from
// a file in results/ and is named next to it or in the table it belongs to.

#set document(title: "Contamination Share", author: "Arthur Rapp")
#set page(paper: "a4", margin: (x: 2.3cm, top: 2.4cm, bottom: 2.6cm), numbering: "1")
#set text(font: "New Computer Modern", size: 10pt, lang: "en")
#set par(justify: true, leading: 0.6em, spacing: 0.95em)
#set heading(numbering: "1.1")
#show heading.where(level: 1): set text(size: 11.5pt)
#show heading.where(level: 2): set text(size: 10.5pt)
#show heading: set block(above: 1.3em, below: 0.75em)
#set math.equation(numbering: "(1)")
#show figure.caption: set text(size: 8.8pt)
#show figure.where(kind: table): set figure.caption(position: top)
#show table: set text(size: 8.2pt)
#show raw: set text(size: 8.8pt)
#show link: set text(fill: rgb("#1f4e9c"))

#let csvtab(path, header, align: none, columns: none) = {
  let rows = csv(path).slice(1)
  let n = header.len()
  table(
    columns: if columns == none { n } else { columns },
    align: if align == none { (left,) + (right,) * (n - 1) } else { align },
    stroke: none,
    inset: (x: 4pt, y: 2.6pt),
    table.hline(stroke: 0.8pt),
    table.header(..header.map(h => text(weight: "bold", h))),
    table.hline(stroke: 0.4pt),
    ..rows.flatten(),
    table.hline(stroke: 0.8pt),
  )
}
#let R = "/results/paper/"

// ---- title ----
#align(center)[
  #block(text(size: 15pt, weight: "bold")[Contamination Share: Why Zero-Shot Forecasting Detectors \ See the Start of an Attack and Not the Rest])
  #v(0.3em)
  #text(size: 10.5pt)[Restarts per anomaly, a model-free measure, and a test of Forecast Fallback \ with Chronos-2 on HAI and LANL]
  #v(0.8em)
  #text(size: 10.5pt)[Arthur Rapp]
  #v(0.1em)
  #text(size: 9pt, style: "italic")[October 2026 · research demo, not peer reviewed]
]
#v(0.6em)

#block(inset: (x: 1.2cm))[
  #set par(justify: true)
  #set text(size: 9.2pt)
  *Abstract.* Zero-shot time-series foundation models can detect anomalies by forecasting a signal and alarming
  where the observation leaves the predicted band. Two recent papers report that such detectors catch the boundaries
  of an attack but miss its interior, because the anomalous data enters the model's context and is then forecast as
  normal. We test this with Chronos-2 on the 50 attacks of the HAI 21.03 industrial control dataset and on 144
  anomalies injected into per-minute authentication counts from the LANL cyber-security dataset. We introduce the
  _contamination share_ $kappa$: the share of anomalous steps that are scored by a forecast whose context already
  holds the anomaly. $kappa$ depends only on the labels and the forecast grid, and its expected value only on the
  anomaly lengths and the stride, so it can be computed before any model runs. In five settings, steps forecast from a contaminated context alarm at a rate of 0.000 to 0.087,
  against 0.118 to 0.610 for steps forecast from a clean context. On HAI, raising the number of forecast restarts per
  anomaly raises $kappa$ from 0.248 to 0.698 (a shorter horizon) and 0.860 (a finer resolution) and produces the
  reported collapse of interior coverage. A shorter history does not. On LANL, where $kappa = 0.956$, the detector
  covers 0.030 of anomalous minutes. Forecast Fallback, our interpretation of a published fix that keeps flagged observations out
  of the context, does not help. Where it stays finite it multiplies false alarms by 19 to 105. In the setting closest to
  the paper's (1 s, history 128) it diverges unless it exits after 120 steps. Chronos-2 behaves as a change detector
  here, and $kappa$ bounds in advance how much of an anomaly it can see.
]

= Introduction

Security monitoring of industrial control systems (ICS) and IT systems produces thousands of time series: sensor
values, actuator commands, logins per minute. Training a detector per signal is costly, and labelled attacks are
rare. Pretrained time-series foundation models such as Chronos-2 @ansari2025 promise forecasts for unseen series
without training. A forecasting detector then alarms when the observation leaves the predicted band.

The catch is the context. The model reads the recent past and forecasts what comes next. Once an attack has run for
a while, its data is part of that past. Uray et al. @uray2026 report forecast-error spikes at the start and at the
end of anomalies with TimesFM on SWaT. Lowe, Fung and Bauer @lowe2026 run Chronos-2 and
Moirai-2.0 and show a spike at the onset only for Chronos-2 (their Fig. 3, on TEP), after which the model follows the
attack. They propose _Forecast Fallback_ (FF) to keep the attack out
of the context. We call the shared claim the _boundary hypothesis_: a zero-shot forecasting detector catches the
boundaries of an attack but misses its persistent interior, because anomalous data enters the context and is forecast
as normal.

Our first test of the hypothesis, on HAI 21.03 at 10 s resolution, did not show the pattern. Interior coverage
(0.290) was not below onset coverage (0.280). The reason was not the model. With a 30-step forecast at 10 s, 33
of 50 attacks fit inside one forecast issued before they began, so for those attacks the context never held attack
data. Whether
contamination can show at all depends on how often the forecast restarts relative to the length of the anomaly. This
paper turns that observation into a measure and tests it. Our contributions:

+ *A measure.* The contamination share $kappa$ is the share of anomaly steps that a rolling forecasting detector
  scores from a context that holds the anomaly. It needs only the labels and the forecast grid. Its expected value
  under a random grid phase has a closed form, approximately a function of the ratio of anomaly length to stride. Step coverage splits exactly
  into a clean part and a contaminated part, weighted by $kappa$ (@sec-kappa).
+ *More steps per anomaly.* We raise the number of forecast restarts per anomaly through the resolution (10 s to
  1 s) and the horizon (30 to 6 steps), with a history-length control. The interior collapses in both high-$kappa$ settings, with
  history 8,192 ($H = 6$) and 128 (1 s). At low $kappa$, cutting the history creates no drop (@sec-steps).
+ *Two domains.* On ICS attacks and injected IT anomalies,
  contaminated steps almost never alarm, while on HAI a clean-context counterfactual covers 0.437 to 0.459 of them. On HAI the blindness sits in the predicted band. On
  LANL it also sits in the median forecast (@sec-explain).
+ *Forecast Fallback.* We test our interpretation of FF in three settings. It does not fix the problem (@sec-ff).

Every table and figure in this paper is generated from result files by one command (@sec-repro).

= Background and related work

*Forecasting detectors.* A rolling detector issues a forecast at origin $o$ from the history before $o$ and scores
the next $H$ observations against it. Chronos-2 @ansari2025 forecasts univariate and multivariate series zero-shot and
returns 21 quantiles per step, so the score can use the predicted band as well as the median.

*The two papers* (@tab-papers). Neither released code. Both tune their F1 threshold on test labels, and Lowe et al.
chose their FF input and horizon on test ROC-AUC. No number of theirs is comparable with ours. We test their
qualitative claim on other data. Lowe et al. report a plain
Chronos-2 ROC-AUC of 0.239 to 0.517 over their datasets, inputs and horizons (their Table 2), which FF lifts to 0.523
to 0.903 in the best settings (their Fig. 4) @lowe2026.

#figure(
  table(
    columns: 3, align: left, stroke: none, inset: (x: 4pt, y: 2.6pt),
    table.hline(stroke: 0.8pt),
    table.header([], [*Uray et al. 2026* @uray2026], [*Lowe, Fung, Bauer 2026* @lowe2026]),
    table.hline(stroke: 0.4pt),
    [Model], [TimesFM 1.2.0, one channel at a time], [Chronos-2, Moirai-2.0],
    [Data], [SWaT], [SWaT, TEP, CTown],
    [Window], [context 100, horizon 32], [input 32, 64 or 128; horizon 1, 16 or 32],
    [Boundary claim], [error spikes at the start and the end], [error spikes at the onset, then the model follows],
    [Fix], [none], [Forecast Fallback],
    table.hline(stroke: 0.8pt),
  ),
  caption: [The two papers behind the boundary hypothesis.],
) <tab-papers>

*Evaluation.* Point-adjusted F1 credits a whole anomaly once one step alarms and inflates results @kim2022. TaPR
@hwang2019 scores ranges. Neither says _where_ in an anomaly the alarms fall. We report coverage per segment (onset,
interior, offset) next to its chance level, and per forecast origin side (@sec-kappa).

= Method

== Detector

All series are normalized with statistics of normal training data (fit split). At origin $o$, Chronos-2 reads up to
$C$ past steps and forecasts $H$ steps. The next origin is $o + S$, with stride $S = H$ throughout. Per channel and
step, the band score is
$ s_t = max(0, y_t - q_(0.95,t), q_(0.05,t) - y_t) / (q_(0.95,t) - q_(0.05,t) + epsilon), quad epsilon = 0.1, $
and the median error is $m_t = |y_t - q_(0.5,t)|$. On HAI the channel scores are aggregated by the mean of the three
largest. On LANL each series is scored alone. An alarm is raised when the score exceeds the 99.5th percentile of
its scores on a calibration split of normal data. No threshold, horizon or aggregation was chosen on test labels.

== Segments, coverage and chance

For an anomaly $A = [a, b)$, the _onset_ is its first $N$ steps, the _interior_ the rest, and the _offset_ the $N$
steps after its end. $N$ is 60 s on HAI and 30 min on LANL. _Coverage_ is the share of a segment's steps that alarm.
A coverage is read against $p$, the share of normal steps that alarm. A detection rate is read against its
_chance level_, the rate that false alarms alone would give a window of the same length.

== Contamination share <sec-kappa>

Let $o(t)$ be the origin of the forecast that scores step $t$. The context of that forecast ends at $o(t) - 1$. It
holds anomalous data exactly when $o(t) > a$. We call such a step _contaminated_, and define
$ kappa = (sum_A |{t in A : o(t) > a_A}|) / (sum_A |A|). $
$kappa$ depends on the labels and the forecast grid only. It needs no forecast and no score. If the first origin
after the onset falls $d$ steps in, the last $L - d$ steps of an anomaly of length $L$ are contaminated. With a
random grid phase, $d$ is uniform on ${1, dots, S}$, and the expected share is
$ hat(kappa)(L, S) = 1/S sum_(d=1)^S max(0, L - d) / L approx cases(r slash 2 & "if" r <= 1, 1 - 1 slash (2 r) & "if" r >= 1), quad r = L / S. $
$r$ is the number of forecast restarts per anomaly. Let $c_"clean"$ and $c_"cont"$ be the coverages of clean and
contaminated anomaly steps. Then the coverage of all anomaly steps is exactly
$ c = (1 - kappa) thin c_"clean" + kappa thin c_"cont". $ <eq-split>
If contaminated steps do not alarm, $c$ is capped near $(1 - kappa) c_"clean"$, however good the forecaster is on
clean contexts. $kappa$ measures exposure to contamination. $c_"cont"$ measures the model's response to it.

#figure(
  image(R + "figures/fig1_schematic.svg", width: 100%),
  caption: [The same 20-step anomaly under two forecast grids (illustration, no data). (a) With a new forecast every
  30 steps, the first origin after the onset falls 18 steps in. Only 2 steps are forecast from a context that holds the
  anomaly ($kappa = 0.10$). (b) With a new forecast every 6 steps, 16 of 20 steps are ($kappa = 0.80$).],
) <fig-schematic>

== Clean-context counterfactual

To test whether contaminated steps are detectable at all, we issue one extra forecast per attack from the onset,
whose context is clean. We score it against the same threshold on the contaminated interior steps (_cf-onset_). Its
origin uses the test labels, so it is a diagnostic, never a detector. Two confounds remain: its horizon is longer than
the rolling one (up to the attack length plus $N$), and it uses a different number of Chronos-2 output patches.

== Forecast Fallback (our interpretation) <sec-ff-method>

Lowe et al. state the trigger (a feature's error above its 99.5th percentile for 3 consecutive steps) and the action
(the model's forecast replaces the observation in the context). Everything else below is our interpretation. The
per-feature level $tau_c$ is the 99.5th percentile of $|q_(0.5) - y|$ on calibration data. From the third exceeding
step on, observations entering the context are replaced by the median forecast. For $H = 30$, substitution runs from
the trigger to the end of the window and then window by window. The exit is none, or after 30, 60 or 120 substituted
steps. Scoring is always against the real observation, and every FF run gets its own calibration threshold. The
60-step exit was set to exceed the longest test attack, so it uses test knowledge.

= Experimental setup

*HAI 21.03* @shin2021. Five test files with 50 attacks of 17 to 422 s: 934 steps at 10 s and 8,947 at 1 s. Fit:
train2 and train3. Calibration: two days of train1. The first 1,500 s of each file are an unscored warm-up, and the
forecast grid starts where the warm-up ends. Chronos-2 forecasts each of 51 channels alone (`uni`). We vary the
steps per anomaly in four settings (@tab-kappa): the headline (10 s, $H = 30$, history up to 8,192 steps); a history
control (128 steps); a shorter horizon ($H = 6$, a new forecast every minute); and 1 s with $H = 30$ and history 128,
the longest input of Lowe et al. A 1 s run with the full history was not run. The FF runs at 10 s use the multivariate
setup per process (`mv-lit`), which was picked over `uni` on test PR-AUC by 0.00012.

*LANL* @kent2015. 58 days of authentication events, aggregated to 13 per-minute series: tenant totals (events, failed
events, distinct users), the five busiest destination hosts and the five busiest other source hosts. Each series is log1p-
and z-transformed with fit-day statistics (days 0–33). Calibration: days 34–40. Test: days 41–57. We inject four
anomaly types into the raw counts, in test only: silences (to 0, 10 or 50 % of normal for 30 or 180 min), bursts of
failed logins (plus 2, 5 or 20 times the median of the hour before, for 10 or 60 min), ramps on one host (up to +50, +200 or +1,000 % over
2 or 8 h) and baseline shifts (+20, +50 or +100 % for 6 or 24 h). Three seeds with two replicas each give 144
injections. Chronos-2 forecasts each group of series jointly (`mv`), with $H = 30$ min, stride 30 and history up to
8,192 minutes. `mv` is the setup
that HAI picked on test results. We compare it with a variant using known-future covariates (time of day and a day
index), FF, a frozen time-of-day reference, a dual score and three baselines.

*Baselines.* `lastvalue` forecasts the last observation, with a band built from the spread of $h$-step changes on fit
data. `robustz` uses the median and MAD of the trailing hour. `seasonal-refday` (HAI) and `seasonal-naive` (LANL)
forecast the same clock time on a reference day or one day earlier.

*Implementation.* `amazon/chronos-2` (119M parameters, revision pinned), float32 on Apple MPS, checked against CPU.
Every forecast is cached with its 21 quantiles, and scoring and evaluation read only the cache.

= Results

== More steps per anomaly: the interior collapses <sec-steps>

#figure(
  csvtab(R + "table_kappa.csv", ([Setting], [Anomalies], [Steps], [$hat(kappa)$], [$kappa$], [$c_"clean"$],
    [$c_"cont"$], [$c$], [Onset], [Interior])),
  caption: [Contamination share and coverage per setting (Chronos-2, band score; `uni` on 51 channels for HAI, `mv`
  for LANL). $hat(kappa)$: expected under a random grid phase. $kappa$: observed. $c_"clean"$, $c_"cont"$, $c$: coverage
  of clean, contaminated and all anomaly steps. Onset and interior: mean coverage per anomaly. Sources:
  `origin_split.csv`, `segments.csv`.],
) <tab-kappa>

At 10 s with $H = 30$ there is no boundary pattern: interior coverage 0.290, onset 0.280 (@tab-kappa,
@fig-coverage a). Cutting the history from 8,192 to 128 steps lowers ROC-AUC from 0.894 to 0.853 and PR-AUC from
0.401 to 0.321 (@tab-hai), but creates no interior drop (0.249 against 0.247).

Restarting more often does. With a new forecast every minute ($H = 6$), onset coverage rises to 0.593 and interior
coverage falls to 0.079, at nearly the same normal alarm rate (0.0039 against 0.0034). At 1 s with $H = 30$, onset
coverage is 0.110 and interior coverage 0.022. There the interior detection rate (0.283) falls below its chance
level (0.451), while the onset rate (0.520) stays above it (0.270) (`segments.csv`). On LANL, with injections of 10
minutes to 24 hours and a forecast every 30 minutes, the interior coverage is 0.004 against 0.364 at the onset.

More restarts also find more attacks. With $H = 6$, 47 of 50 attacks raise an alarm, against 31 with $H = 30$
(@tab-hai). At one false alarm per hour, 46 are
found against 31 (an evaluation-only threshold set from the test labels). The difference in detection rate is 0.300,
with a 95 % interval of 0.146 to 0.422 (`fa_matched.csv`, `bootstrap_paired.csv`). But the ROC-AUC falls from 0.894 to
0.817, and step recall stays the same (0.245 against 0.251). More steps per anomaly turn the detector from one that
covers a state into one that flags an event. Only the onset half of the boundary hypothesis holds: with $H = 6$ the
offset coverage falls too (0.027 against 0.083, `segments_summary.csv`). The detector is also not better than simple
baselines. At 10 s `lastvalue` has the higher PR-AUC (0.412 against 0.401), and at 1 s Chronos-2's PR-AUC (0.081) is
below every baseline (0.172 to 0.341, `metrics.csv`).

#figure(
  csvtab(R + "table_hai.csv", ([HAI setting], [ROC-AUC], [PR-AUC], [Recall], [False alarms / h], [Attacks detected],
    [$p$])),
  caption: [Detection on HAI (band score, calibration threshold). PR-AUC chance is 0.024 at 10 s
  and 0.023 at 1 s. False alarms are steps per normal hour. $p$: share of normal steps that alarm. Sources: `metrics.csv`, `segments_summary.csv`.],
) <tab-hai>

== The contamination share explains the pattern <sec-explain>

*$kappa$ follows the restarts per anomaly.* @fig-kappa places every anomaly on the curve $hat(kappa)(r)$. On LANL,
whose injection starts are random, the observed $kappa$ (0.956) equals the expected one (0.956). On HAI, the observed
$kappa$ lies below $hat(kappa)$: 0.248 against 0.367, 0.698 against 0.814, and 0.860 against 0.914. The reason is in
the grid. 11 of 50 HAI attacks start in the first step of a 30-step forecast at 10 s, where a random phase would
place 1.7. With $H = 6$ the count is 40 against 8.3, and at 1 s it is 13 against 1.7 (`grid_phase.csv`). Our reading:
many attacks start at whole minutes, and our grid starts at a whole minute after the warm-up. An onset at an origin
delays contamination by a full stride, so $hat(kappa)$ overestimates $kappa$ when onsets cluster at forecast origins,
as here.

#figure(
  image(R + "figures/fig2_kappa.svg", width: 100%),
  caption: [Contamination share of each anomaly against its restarts per anomaly $r = L slash S$. The curve is
  the expectation under a random grid phase. Points below it started early in a forecast window, most at or just after
  an origin. Anomalies that end before the next origin have $kappa = 0$. HAI at 10 s
  with a 128-step history has the same grid as the headline and is not drawn. Source: `kappa_anomalies.csv`.],
) <fig-kappa>

*Contaminated steps almost never alarm* (@fig-coverage b). Their coverage is 0.000 to 0.087 in all five settings.
Clean steps alarm at 0.118 to 0.610 (@tab-kappa). @eq-split explains why the shorter horizon does not raise step
recall. Short-horizon forecasts are more accurate (median
error on calibration data 0.291 against 0.388, `forecast_accuracy.csv`) and nearly double $c_"clean"$ (0.610 against 0.332).
But $kappa$ rises from 0.248 to 0.698, and $c$ stays at 0.245 against 0.251. On LANL $1 - kappa = 0.044$: even a perfect clean-context detector
would cover under 5 % of the anomalous minutes unless contaminated minutes alarm.

*The contaminated steps are detectable.* On the contaminated interior steps, the clean-context counterfactual
covers 0.459 of 231 steps (17 attacks) at 10 s and 0.437 of 6,014 steps (46 attacks) at 1 s. Rolling covers 0.004
and 0.028 of the same steps, and the counterfactual scores higher in 16 of 17 and 42 of 46 attacks
(`cf_onset_split.csv`). Seen from a clean context, these steps alarm. The counterfactual's longer horizon and its
different number of output patches are confounds, and it has no normal-data alarm rate of its own.

#figure(
  image(R + "figures/fig3_coverage.svg", width: 100%),
  caption: [(a) Mean onset and interior coverage per anomaly. (b) Coverage of anomaly steps forecast from a clean and
  from a contaminated context, pooled over steps. The hollow markers show a forecast from the clean onset context on
  the contaminated interior steps. Settings are sorted by $kappa$. LANL segments use $N = 30$ min, HAI $N = 60$ s.
  Sources: `segments.csv`, `origin_split.csv`, `cf_onset_split.csv`.],
) <fig-coverage>

*Where the blindness sits.* @tab-scores repeats the split for the median error $|y - q_(0.5)|$. On HAI the median
error shows no contamination gap. In all four settings contaminated steps alarm at least as often as clean ones
(for example 0.603 against 0.558 in the headline). The median error also alarms more often on normal steps (0.0127
against 0.0034 in the headline), so the two scores run at different alarm rates. Still, the gap that the band score
shows (0.004 against 0.332) is absent. Our reading: the median forecast still misses the attack, and the band
forgives it because after contamination the band moved or widened. We did not measure the band width by
origin side on HAI. On LANL both scores are blind (median error 0.024 against 0.521). An injected silence or shift
is a level change, and the median follows the new level. The band of contaminated LANL minutes is also wider: 1.54
fit-z against 1.28 for clean anomaly minutes and 1.29 for normal minutes (`lanl_band_width.csv`).

#figure(
  table(
    columns: 8, align: (left,) + (right,) * 7, stroke: none, inset: (x: 4pt, y: 2.6pt),
    table.hline(stroke: 0.8pt),
    table.header(
      table.cell(rowspan: 2, align: bottom)[*Setting*], table.cell(rowspan: 2, align: bottom)[*$kappa$*],
      table.cell(colspan: 3, align: center)[*band score*], table.cell(colspan: 3, align: center)[*median error*],
      table.hline(start: 2, stroke: 0.4pt),
      [*$p$*], [*$c_"clean"$*], [*$c_"cont"$*], [*$p$*], [*$c_"clean"$*], [*$c_"cont"$*],
    ),
    table.hline(stroke: 0.4pt),
    ..csv(R + "table_scores.csv").slice(1).flatten(),
    table.hline(stroke: 0.8pt),
  ),
  caption: [Coverage by origin side for the band score and the median-error score $|y - q_(0.5)|$, each at its own
  calibration threshold (HAI: mean of the three largest channels). $p$: share of normal steps that alarm with that
  score. Sources: `origin_split.csv`, `segments_summary.csv`, `false_alarms.csv`.],
) <tab-scores>

*Simple forecasters differ on HAI.* `lastvalue` covers more contaminated than clean steps on HAI (0.504 against 0.326
at 10 s, 0.231 against 0.154 at 1 s). `robustz` covers 0.142 against 0.235 at 10 s and 0.282 against 0.045 at 1 s
(@tab-split). Our reading: `lastvalue`'s band is fixed from fit data, so it keeps alarming
while an ICS attack keeps moving the signal. At 1 s, `robustz`'s one-hour window is far longer than every HAI attack.
We have no reading for its drop at 10 s. On LANL both are blind too
(0.009 and 0.033 against 0.484 and 0.539), as is Chronos-2 with covariates (0.004). There most anomalous minutes belong to shifts and ramps that last
hours, longer than the window. Of the methods in @tab-split and @tab-kappa,
Chronos-2 is the only one blind to contaminated steps in both domains.

#figure(
  csvtab(R + "table_split_baselines.csv", ([Setting], [Method], [$kappa$], [$c_"clean"$], [$c_"cont"$]),
    align: (left, left, right, right, right)),
  caption: [Coverage by origin side for the other methods that forecast from the recent context (band score, same
  forecast grid). Source: `origin_split.csv`.],
) <tab-split>

== Forecast Fallback <sec-ff>

FF tries to lower the effective $kappa$ by keeping the anomaly out of the context. @tab-ff and @fig-ff show that our
interpretation does not work in any setting.

#figure(
  csvtab(R + "table_ff.csv", ([Setting], [Method], [Exit], [False alarms], [Ratio], [ROC-AUC], [PR-AUC], [$p$],
    [Detected]), align: (left, left, left) + (right,) * 6),
  caption: [Forecast Fallback (our interpretation) against plain rolling. False alarms: steps per normal hour (HAI) or
  alarms per series-day (LANL). Ratio: against the rolling row of the same setting. Detected: attacks or injections
  with at least one alarm, which at high $p$ is mostly chance. HAI at 10 s uses `mv-lit`, the multivariate setup picked
  on test PR-AUC, so its rolling row differs from @tab-hai. The 60-step exit was set from test knowledge, and the 30-
  and 120-step exits are half and double it. Source: `ff.csv`.],
) <tab-ff>

*HAI at 10 s.* Every variant is below rolling on ROC-AUC and PR-AUC and raises 19.1 to 104.7 times the false alarms.
Without an exit, 30 of 34 channels trigger on calibration data, which holds no attack, and 0.565 of calibration
channel-steps run in fallback. In test the share is 0.766. The first trigger in every test file falls between steps
162 and 262, just after the warm-up ends at step 150, so 47 of 50 attacks begin with fallback already active. FF
could be credited with the interior of only 3 attacks, where it covers 0.262 against 0.480 for rolling
(`ff_activity.csv`, `ff_episodes.csv`, `segments_summary.csv`). With exits, re-entry needs only 3 new exceedances, so
episodes multiply: the 30-step exit opens 3,025 episodes in test, 2,669 of them on normal steps.

*HAI at 1 s* (the setting closest to the paper's). Without an exit and with a 30-step exit, the run stopped: Chronos-2 returned
non-finite quantiles. A diagnostic probe of the no-exit run (outside the result files, REPORT.md 4.19) shows
why: once the 128-step context holds only FF medians, the model extends its own trend until the values overflow. The
120-step exit stays finite but alarms on 0.176 of normal steps (633 false-alarm steps per hour, 32.8 times rolling). It lowers ROC-AUC (0.591 against 0.618) and raises PR-AUC slightly (0.097
against 0.081). Fallback is active at the onset of 49 of 50 attacks.

*LANL.* FF raises 254.95 false alarms per series-day against 6.70 and detects 72 of 144 injections against 128.
Two host series alone reach 991.4 and 873.8 false alarms per day (`false_alarms.csv`). Its interior coverage is 0.312, of
which 0.177 would be expected from its normal-minute alarm rate alone.

#figure(
  placement: auto,
  image(R + "figures/fig4_ff.svg", width: 92%),
  caption: [False alarms of Forecast Fallback relative to plain rolling in the same setting (log scale). Source:
  `ff.csv`.],
) <fig-ff>

The failure is structural. To keep an attack out of the context, FF must first recognise it, which is the detection
problem it was meant to solve. A false trigger on normal data turns a channel into a free-running
forecast, and without an exit nothing brings it back. With an exit, three new exceedances start it again. A trigger inside an attack comes too late to matter if the attack fits in one forecast.
These results test our interpretation. They cannot refute the published FF, whose exit, scope and block handling are
not stated and whose gains were tuned on test ROC-AUC.

== LANL in full <sec-lanl>

#figure(
  csvtab(R + "table_lanl.csv", ([Method], [Detected], [Trials], [Chance], [Onset], [Interior], [Offset],
    [False alarms / series-day], [$p$])),
  caption: [All methods on the 144 LANL injections (band score; dual score for `mv-dual`). Chance: mean detection rate
  from false alarms alone in windows of the same length. Onset, interior, offset: mean coverage, $N = 30$ min. The
  calibration threshold alone gives 7.2 false alarms per series-day. Sources: `detections.csv`, `false_alarms.csv`.],
) <tab-lanl>

@tab-lanl and @fig-timelines show the change-detector profile plainly. Chronos-2 detects 128 (`mv`) and 129 (`mv-cov`) of 144
injections with the fewest false alarms (6.70 and 6.38 per series-day). Its alarms sit at the start (onset coverage 0.364) and the end (offset
0.288), and almost never in between (0.004). Detection rates must be read against chance. For a 24-hour shift, false
alarms alone would hit the window with probability 0.84, and `mv` detects 0.89 (`detections.csv`). The methods that do
not adapt cover the interior at a price. The frozen reference covers 0.313 at 41.83 false alarms per series-day, six
times `mv`'s normal alarm rate. `seasonal-naive` covers 0.297 at 42.91. Of the baselines,
`robustz` comes closest: 121 detected at 8.83 false alarms, with higher onset coverage (0.549). No equal-false-alarm comparison was built for LANL,
so these rankings are at different alarm rates.

#figure(
  placement: auto,
  image("/results/phase2/figures/timelines.png", width: 100%),
  caption: [Four LANL injections, seed 0, longest
  duration per type: a silence to 50 % of normal for 3 h, a burst of 20 times the median for 1 h, a ramp to +1,000 %
  over 8 h and a +100 % shift for 24 h. Top: observation, `mv` band (blue) and frozen band (green). Bottom: `mv` band
  score and its threshold. The band follows each step change within one forecast, and the score alarms at the step up
  and the step down. The ramp alarms near its start and at its end. Source: `results/phase2/figures/timelines.png`.],
) <fig-timelines>

= Discussion

*Change detectors, not state detectors.* A rolling forecaster compares the present with the recent past. It sees a
change. It does not remember that a state is abnormal. $kappa$ says how much of an anomaly lies after the change from
the forecaster's point of view, and @eq-split says what that costs in coverage.

*What to do with it.*
- Compute $kappa$ for the anomaly lengths and the stride before evaluating. A benchmark with low $kappa$ cannot test
  context contamination. HAI at 10 s with $H = 30$ has $kappa = 0.248$, which is why our first test was inconclusive.
- Report coverage split by origin side, with the clean-context counterfactual where it can be run.
- Choose the restart rate for the task. Frequent restarts find more attacks: 47 of 50 with $H = 6$, 43 of them at the onset. Persistent
  states need a reference that does not adapt, such as a frozen or seasonal one, and that reference costs false alarms.
- Treat context protection as a second detector whose errors compound. A protection that depends on the first
  detector's alarms inherits its misses and adds its false alarms.

= Limitations

- One model (Chronos-2, zero-shot, one checkpoint) on two datasets. HAI has 50 short attacks, so intervals are wide.
- LANL anomalies are synthetic injections into aggregate counts. The LANL red-team events were not visible in these
  counts, and a flows sub-study is not part of this paper.
- $kappa$ assumes the stride equals the horizon and counts a context as contaminated if it holds any anomaly step. It
  ignores how much of the anomaly the context holds and how long the history is. It measures exposure, not response.
- The contaminated steps have shorter horizons than the clean ones, because their origins lie after the onset. Bands
  widen with the horizon (`uni` at 10 s, test: median width 0.386 fit-z at $h = 1$ and 1.725 at $h = 30$,
  `band_width_by_h.csv`).
  That favours alarms on contaminated steps, so it does not explain the gap.
- FF and the frozen reference are our interpretations. The multivariate setup (`mv-lit` on HAI, `mv` on LANL) was
  picked on HAI test results, and the 60-step FF exit was set from test knowledge.
- We did not measure the HAI band width by origin side, so "the band moved or widened" on HAI is an inference from
  the median-error split.

= Conclusion

Zero-shot forecasting detectors do lose the interior of an attack, as reported. But whether that shows depends on the
evaluation design, not only on the model: the contamination share decides it. With few restarts per anomaly
($kappa = 0.248$) the pattern is absent. With many ($kappa = 0.698$ to $0.956$) the interior collapses, and the steps
forecast from a contaminated context almost never alarm in any setting. Forecast Fallback, as we interpret it, does
not change this and adds false alarms. Chronos-2 behaves as a change detector, and a simple forecaster with a fixed
band need not. Before using a forecasting detector for persistent threats, compute $kappa$ and measure $c_"cont"$.

= Reproduction <sec-repro>

The repository holds the code, configs and result files. `uv run --extra paper tsfm-ad paper` rebuilds every table
and Figures 1 to 4 from `results/phase1`, `results/phase2` and the cached LANL forecasts, without calling the model,
and compiles this PDF. Figure 5 comes from `tsfm-ad p2 --stage plot`. The HAI forecasts come from `tsfm-ad all --optional 10s`
(the headline, the FF runs at 10 s and the baselines) and from `tsfm-ad forecast` with `configs/res10s_uni_c128.yaml`,
`res10s_uni_h6.yaml`, `res1s_uni_c128.yaml` and `res1s_ff_interp_block_c128*.yaml` (the sensitivity runs; commands
in the README). The
LANL forecasts come from `tsfm-ad p2`. The
report `REPORT.md` holds every run, decision and deviation.

*Acknowledgements.* The analysis code and a first draft of this text were written with Claude Code (Anthropic). HAI
21.03 is published by the HAI dataset authors @shin2021. The LANL data are published by Los Alamos National
Laboratory @kent2015.

#bibliography("refs.bib", style: "ieee", title: "References")
