"""Onset / interior / interior_eq / offset, chance levels, latency and the origin and horizon splits (PLAN.md 9,
D29, D45, D46, D48), on hand-made arrays."""
from dataclasses import replace

import numpy as np
import polars as pl
import pytest

from tsfm_ad import evaluate
from tsfm_ad.evaluate import chance_level, latency_summary, segment_table, segments, segments_by_h


def test_segment_bounds():
    y = np.zeros(60, np.int8)
    y[10:25] = 1                                   # L = 15 > 2N
    y[40:44] = 1                                   # L = 4 < N: empty interior
    a, b = segments(y, 6)
    assert (a.start, a.end, a.N) == (10, 24, 6)
    assert (a.onset, a.interior, a.interior_eq, a.offset) == (range(10, 16), range(16, 25), range(16, 22),
                                                              range(25, 31))
    assert (b.start, b.end) == (40, 43)
    assert b.onset == range(40, 44) and len(b.interior) == 0 and len(b.interior_eq) == 0
    assert b.offset == range(44, 50)


def test_short_attacks_and_cut_offsets():
    y = np.zeros(30, np.int8)
    y[2:8] = 1                                     # L = N: empty interior (A211, A508 at 10 s)
    y[10:22] = 1                                   # L = 2N: interior_eq is the whole interior
    y[27:29] = 1
    a, b, c = segments(y, 6)
    assert a.onset == range(2, 8) and len(a.interior) == 0 and len(a.interior_eq) == 0
    assert a.offset == range(8, 10)                # cut at the next attack's onset
    assert b.interior == range(16, 22) and b.interior_eq == range(16, 22)
    assert c.offset == range(29, 30)               # cut at the end of the array
    sh = b.shifted(100)
    assert (sh.start, sh.end, sh.onset, sh.offset) == (110, 121, range(110, 116), range(122, 127))


def test_chance_level_hand_values():
    assert chance_level(0.5, 2) == pytest.approx(0.75)
    assert chance_level(0.1, 3) == pytest.approx(0.271)
    assert chance_level(0.005, 6) == pytest.approx(0.029627, abs=1e-6)
    assert chance_level(0.0, 10) == 0.0 and chance_level(0.3, 0) == 0.0


def _grid(n=60, H=10):
    """Rolling grid with origins every H steps: origin and h per step (W = 0)."""
    i = np.arange(n)
    origin = (i // H) * H
    return origin, i - origin + 1


def _case():
    y = np.zeros(60, np.int8)
    y[12:27] = 1                                   # onset 12 inside the window of origin 10
    y[40:44] = 1                                   # missed
    alarm = np.zeros(60, bool)
    alarm[[14, 15, 21, 50]] = True                 # 50 is a false alarm on a normal step
    return y, alarm


def test_segment_table_latency_coverage_origin_split():
    y, alarm = _case()
    origin, h = _grid()
    attacks = segments(y, 6)
    tab = segment_table(alarm, alarm * 2.0, attacks, origin, h, steps_res=10)
    p = 1 / 41                                     # 1 alarm on 60 - 15 - 4 normal steps
    a, b = tab.row(0, named=True), tab.row(1, named=True)
    assert a["p_normal"] == pytest.approx(p) and a["duration_steps"] == 15
    assert (a["onset_n"], a["onset_det"], a["onset_cov"]) == (6, True, pytest.approx(2 / 6))
    assert a["onset_chance"] == pytest.approx(1 - (1 - p) ** 6)
    assert (a["interior_n"], a["interior_cov"], a["interior_chance"]) == (9, pytest.approx(1 / 9),
                                                                          pytest.approx(1 - (1 - p) ** 9))
    assert (a["interior_eq_n"], a["interior_eq_cov"]) == (6, pytest.approx(1 / 6))
    assert (a["offset_n"], a["offset_det"], a["offset_cov"]) == (6, False, 0.0)
    assert a["latency_s"] == 20 and a["latency_censored_s"] == 20
    # steps 12-19 come from origin 10 (context ends before onset), 20-26 from origin 20 (holds attack data)
    assert (a["n_pre_origin"], a["cov_pre_origin"]) == (8, pytest.approx(2 / 8))
    assert (a["n_post_origin"], a["cov_post_origin"]) == (7, pytest.approx(1 / 7))
    assert b["latency_s"] is None and b["latency_censored_s"] == (4 + 6) * 10    # censored at duration + N
    assert b["interior_n"] == 0 and b["interior_det"] is None and b["interior_chance"] is None
    assert tab["ff_group"].null_count() == 2       # no FF state given


def test_segment_table_takes_ff_state():
    y, alarm = _case()
    origin, h = _grid()
    attacks = [replace(a, attack_id=f"A{i}") for i, a in enumerate(segments(y, 6))]
    ff = pl.DataFrame({"attack_id": ["A0", "A1"], "ff_group": ["pre_active", "none"],
                       "ff_active_at_onset": [True, False], "ff_n_channels_active_at_onset": [2, 0],
                       "ff_fallback_age_at_onset_steps": [7, None], "ff_first_trigger_after_onset_steps": [None, None]})
    tab = segment_table(alarm, alarm * 1.0, attacks, origin, h, 10, ff_state=ff)
    assert tab["ff_group"].to_list() == ["pre_active", "none"]
    assert tab["ff_fallback_age_at_onset_steps"].to_list() == [7, None]


def test_latency_common_detected_set():
    tab = pl.DataFrame({"run_key": ["a"] * 3 + ["b"] * 3, "attack_id": ["x", "y", "z"] * 2,
                        "latency_s": [10, 30, None, 50, None, None],
                        "latency_censored_s": [10, 30, 200, 50, 120, 200]})
    s = latency_summary(tab).sort("run_key")
    assert s["n_common"].to_list() == [1, 1]       # only x is detected by both
    assert s["latency_common_median_s"].to_list() == [10.0, 50.0]
    assert s["latency_censored_median_s"].to_list() == [30.0, 120.0]
    assert s["n_detected"].to_list() == [2, 1]


def test_h_and_time_since_onset_buckets():
    y, alarm = _case()
    y[40:44] = 0
    origin, h = _grid()
    score = np.where(alarm, 3.0, 1.0)
    out = segments_by_h(alarm, score, segments(y, 6), origin, h, 10, [[1, 5], [6, 10]], [[0, 59], [60, None]])

    def row(segment, side, hb, tb):
        r = out.filter((pl.col("segment") == segment) & (pl.col("origin_side") == side)
                       & (pl.col("h_bucket") == hb) & (pl.col("tso_bucket") == tb))
        assert r.height == 1
        return r.row(0, named=True)

    r = row("onset", "pre", "1-5", "0-59")         # steps 12-14, h 3-5, alarm at 14
    assert (r["n_steps"], r["coverage"], r["mean_score"]) == (3, pytest.approx(1 / 3), pytest.approx(5 / 3))
    assert row("onset", "pre", "6-10", "0-59")["n_steps"] == 3      # steps 15-17, h 6-8
    assert row("interior", "pre", "6-10", "60+")["n_steps"] == 2    # steps 18-19, 60-70 s after onset
    r = row("interior", "post", "1-5", "60+")      # steps 20-24 from origin 20, alarm at 21
    assert (r["n_steps"], r["coverage"], r["n_attacks"]) == (5, pytest.approx(0.2), 1)
    assert row("interior", "post", "6-10", "60+")["n_steps"] == 2   # steps 25-26
    assert out.filter(pl.col("segment") == "offset")["origin_side"].unique().to_list() == ["post"]


def test_pa_f1_is_point_adjusted():
    label = np.array([0, 1, 1, 1, 0, 0, 1, 1, 0])
    alarm = np.array([0, 0, 1, 0, 0, 1, 0, 0, 0])
    assert evaluate.pa_f1(alarm, label) == pytest.approx(2 * 3 / (2 * 3 + 1 + 2))
    m = evaluate.point_metrics(np.array([0.1, 0.9, 0.8, 0.2]), np.array([0, 1, 1, 0]), 0.5, res_s=10)
    assert (m["precision"], m["recall"], m["roc_auc"], m["alarm_steps"], m["fa_per_hour"]) == (1, 1, 1, 2, 0)
