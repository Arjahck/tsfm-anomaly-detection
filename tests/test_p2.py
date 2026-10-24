"""Phase 2 data and evaluation (lanl.py, p2_eval.py): top-N selection, normalization (fit days only), and the
injection detection and false-alarm logic. Silent errors here change every Phase 2 number."""
import numpy as np
import polars as pl

from tsfm_ad import lanl, p2_eval

CFG = {"data": {"fit_days": [0, 1], "top_n": 2, "groups": {"tenant": ["a", "b"]}},
       "score": {"grace_min": 30, "fa_exclude_before_min": 60, "fa_exclude_after_min": 360}}


def test_top_n_and_fit_stats_use_fit_minutes_only():
    df = pl.DataFrame({"minute": [10, 20, 30, 3000, 3000], "dst": ["x", "y", "y", "z", "z"], "n": [5, 1, 1, 100, 100]})
    top = lanl.top_n(df, "dst", "n", CFG)                    # fit = minutes 0..2879: z (test) is never selected
    assert top["dst"].to_list() == ["x", "y"] and top["rank"].to_list() == [1, 2]
    raw = pl.DataFrame({"minute": np.arange(4320), "a": np.r_[np.full(2880, 9.0), np.full(1440, 999.0)],
                        "b": np.r_[np.arange(2880.0), np.zeros(1440)]})
    st = lanl.fit_stats(raw, CFG)
    assert np.isclose(st["a"][0], np.log1p(9.0)) and st["a"][1] == 1.0     # constant on fit: std falls back to 1
    assert np.isclose(st["b"][0], np.log1p(np.arange(2880.0)).mean())
    z = lanl.transform(np.array([[9.0, 999.0]]), [st["a"]])
    assert np.isclose(z[0, 0], 0.0) and z[0, 1] > 0


def test_detect_window_latency_and_false_alarms():
    t = np.arange(1000, 1000 + 2 * 1440)
    band = np.zeros(len(t))
    band[(t >= 1100) & (t < 1105)] = 5.0                     # alarms inside the injection (start 1100)
    band[(t >= 1200) & (t < 1202)] = 5.0                     # inside the 6 h exclusion after it: not a false alarm
    band[(t >= 3000) & (t < 3003)] = 5.0                     # a false alarm on normal minutes
    sc = pl.DataFrame({"series": "a", "t": t, "label": 0, "band": band})
    man = pl.DataFrame([{"seed": 0, "inj_id": "s0-0", "type": "shift", "series": "a", "group": "tenant",
                         "magnitude": 0.5, "duration_min": 60, "start": 1100, "end": 1160}])
    det, fa = p2_eval.detect(sc, "band", {"a": 1.0}, man, CFG)
    assert det[0]["detected"] and det[0]["latency_min"] == 0 and np.isclose(det[0]["coverage"], 5 / 60)
    assert fa[0]["alarms"] == 3
    normal = len(t) - ((t >= 1040) & (t < 1520)).sum()
    assert fa[0]["normal_minutes"] == normal and np.isclose(fa[0]["fa_per_day"], 3 / (normal / 1440))
    man2 = man.with_columns(start=pl.lit(2000), end=pl.lit(2060))
    det2, _ = p2_eval.detect(sc, "band", {"a": 1.0}, man2, CFG)
    assert not det2[0]["detected"] and det2[0]["latency_min"] is None
    d = det[0]                                               # onset = first 30 min, interior = the other 30
    assert np.isclose(d["cov_onset"], 5 / 30) and d["cov_interior"] == 0 and d["cov_offset"] == 0
    # chance: 90-min windows on normal minutes; only those that hold one of minutes 3000-3002 have an alarm
    keep = ~((t >= 1040) & (t < 1520))
    starts = [s for s in range(len(t) - 89) if keep[s:s + 90].all()]
    hits = [s for s in starts if ((t[s:s + 90] >= 3000) & (t[s:s + 90] < 3003)).any()]
    assert np.isclose(d["chance"], len(hits) / len(starts))
