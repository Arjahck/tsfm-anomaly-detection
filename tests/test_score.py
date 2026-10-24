"""Scores, aggregation and thresholds (PLAN.md 7, D17-D20, D49), on hand values and a small synthetic cache."""
import copy
import json
from datetime import datetime, timedelta
from pathlib import Path
from statistics import NormalDist

import numpy as np
import polars as pl
import pytest

from tsfm_ad import cache, config, context, evaluate, score
from tsfm_ad.cache import QCOLS, QUANTILE_LEVELS
from tsfm_ad.config import load_config, with_variant
from tsfm_ad.data import SegmentData

ROOT = Path(__file__).resolve().parents[1]
Z = np.array([NormalDist().inv_cdf(q) for q in QUANTILE_LEVELS])   # q05 = -1.645, q95 = 1.645


def test_band_hand_values():
    s = score.band([2.0, 0.3, -3.0], [-1.0, -1.0, -1.0], [1.0, 1.0, 1.0], eps=0.1)
    assert s == pytest.approx([1 / 2.1, 0.0, 2 / 2.1])


def test_zero_width_band_gives_dev_over_eps():
    assert score.band([0.8, 0.5, 0.1], [0.5] * 3, [0.5] * 3, eps=0.1) == pytest.approx([3.0, 0.0, 4.0])


def test_midpoint_weights():
    w = score.midpoint_weights()
    assert w.sum() == pytest.approx(1.0)
    assert w[0] == pytest.approx(0.03) and w[1] == pytest.approx(0.045) and w[10] == pytest.approx(0.05)
    assert w == pytest.approx(w[::-1])


def test_crps_hand_values():
    # two levels 0.25, 0.75: edges 0, 0.5, 1 -> weights 0.5, 0.5
    Q = np.array([[0.0, 1.0], [0.0, 1.0]])
    got = score.crps([2.0, 0.5], Q, levels=(0.25, 0.75))
    assert got == pytest.approx([2 * (0.5 * 0.25 * 2 + 0.5 * 0.75 * 1), 2 * (0.5 * 0.125 + 0.5 * 0.125)])
    # a point forecast (all quantiles equal) gives the absolute error
    assert score.crps([1.0, -2.0], np.zeros((2, 21))) == pytest.approx([1.0, 2.0])


def test_mae_and_dual_hand_values():
    assert score.mae([1.0, -1.0], [0.5, 0.5]) == pytest.approx([0.5, 1.5])
    Qf = np.tile(Z / Z[19] * 0.95, (2, 1))       # frozen band q95 - q05 = 1.9
    assert score.dual(Qf + 1.0, Qf, eps=0.1) == pytest.approx([0.5, 0.5])
    assert score.dual(Qf, Qf, eps=0.1) == pytest.approx([0.0, 0.0])


def test_aggregate_topk_max_mean():
    S = np.array([[1.0, 5.0, 3.0, 2.0], [0.0, 0.0, 0.0, 4.0]])
    assert score.aggregate(S, "topk", k=3) == pytest.approx([10 / 3, 4 / 3])
    assert score.aggregate(S, "max") == pytest.approx([5.0, 4.0])
    assert score.aggregate(S, "mean") == pytest.approx([2.75, 1.0])
    assert score.aggregate(S[:, :2], "topk", k=3) == pytest.approx([3.0, 0.0])  # k > channels: mean of all


def test_smooth_and_threshold():
    assert score.smooth([1.0, 3.0, 5.0, 7.0], 2) == pytest.approx([1.0, 2.0, 4.0, 6.0])
    assert score.smooth([1.0, 3.0], None) == pytest.approx([1.0, 3.0])
    assert score.threshold(np.arange(200), 99.5) == pytest.approx(198.005)
    assert score.threshold(np.arange(1, 11), 50) == pytest.approx(5.5)


def test_frozen_rows_join_on_channel_and_h():
    L, W, H = 10, 4, 3
    t0 = datetime(2020, 7, 11)
    seg = SegmentData("train1a", "calib", "train1", np.array([t0 + timedelta(seconds=10 * i) for i in range(L)],
                      dtype="datetime64[us]"), np.zeros(L, np.int8), np.zeros((3, L), np.int8),
                      np.vstack([np.arange(L), 100 + np.arange(L)]).astype(np.float32), ["A", "B"])
    ref = pl.DataFrame({"channel": ["A"] * H + ["B"] * H, "h": [1, 2, 3] * 2,
                        **{q: [10.0 * i + h for i in range(2) for h in (1, 2, 3)] for q in QCOLS}})
    df = score.frozen_rows(seg, ref, W, H).sort("channel", "t")
    a = df.filter(pl.col("channel") == "A")
    assert a["t"].to_list() == list(range(W, L))
    assert a["origin"].to_list() == [4, 4, 4, 7, 7, 7]
    assert a["h"].to_list() == [1, 2, 3, 1, 2, 3]
    assert a["y_true"].to_list() == [4, 5, 6, 7, 8, 9]
    assert a["q50"].to_list() == [1, 2, 3, 1, 2, 3]
    assert df.filter(pl.col("channel") == "B")["q50"].to_list() == [11, 12, 13, 11, 12, 13]
    assert df["file"].unique().to_list() == ["train1a"]


# ---- a synthetic run: tiny config, prepared stubs and a hand-made cache ----

CHANNELS = ["P1_A", "P1_B", "P1_PCV02Z", "P2_C", "P2_D"]
W, H, L_CALIB, L_TEST, ATT = 3, 3, 40, 60, (20, 29)


def _rows(file, L, dev, label=None):
    """Cache rows of one file: every channel forecast N(0, 1) quantiles; y = dev[channel](t)."""
    t = np.arange(W, L)
    origin = W + ((t - W) // H) * H
    lab = np.zeros(L, np.int8) if label is None else label
    parts = []
    for c in CHANNELS:
        y = np.array([dev(c, int(i)) for i in t])
        parts.append(pl.DataFrame({"file": file, "channel": c, "t": t, "time": datetime(2020, 7, 7),
                                   "origin": origin, "h": t - origin + 1, "ctx_len": origin,
                                   **{q: np.full(len(t), Z[i]) for i, q in enumerate(QCOLS)},
                                   "y_true": y, "label": lab[t]}))
    return pl.concat(parts)


@pytest.fixture
def toy(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MODEL_SOURCES, "chronos2", ("config.py",))  # independent of the forecasting code
    cfg = load_config(ROOT / "configs" / "base.yaml")
    cfg["paths"].update(cache=str(tmp_path / "cache"), results=str(tmp_path / "results"))
    cfg["dataset"]["key"] = "toy"
    cfg["dataset"]["splits"]["test"] = [{"name": "test1", "file": "test1"}]   # calib: train1a, train1b
    cfg["forecast"].update(W_s=W * 10, H=H)
    cfg["channels"]["setups"] = {
        "uni": {"mode": "univariate", "processes": ["P1", "P2"], "targets": ["continuous", "actuator"],
                "covariates": [], "channel_set": "all5"},
        "mv": {"mode": "multivariate", "processes": ["P1"], "targets": ["continuous"], "covariates": [],
               "channel_set": "p1three"}}
    prep = tmp_path / "cache" / "toy" / "prepared"
    prep.mkdir(parents=True)
    (prep / "manifest.json").write_text(json.dumps({"digest": "toy"}))
    pl.DataFrame({"channel": CHANNELS, "process": [c[:2] for c in CHANNELS],
                  "role": ["continuous"] * 4 + ["actuator"]}).write_parquet(prep / "roles.parquet")
    pl.DataFrame({"attack_id": ["A101"], "segment": ["test1"], "start_idx": [ATT[0]], "end_idx": [ATT[1]],
                  "n_steps": [ATT[1] - ATT[0] + 1], "stratum": ["other"]}).write_parquet(prep / "attacks.parquet")
    rng = np.random.default_rng(0)
    noise = {c: rng.normal(0, 0.5, 200) for c in CHANNELS}
    calib_dev = lambda c, t: 9.0 if (c == "P2_D" and t % 5 == 0) else noise[c][t]  # noqa: E731
    lab = np.zeros(L_TEST, np.int8)
    lab[ATT[0]:ATT[1] + 1] = 1
    test_dev = lambda c, t: 20.0 if (c == "P1_A" and ATT[0] <= t <= ATT[1] + 2) else noise[c][t] / 4  # noqa: E731
    meta = cache.meta(cfg)
    for f in ("train1a", "train1b"):
        cache.write(_rows(f, L_CALIB, calib_dev), cache.cache_path(cfg, "calib", f), meta)
    cache.write(_rows("test1", L_TEST, test_dev, lab), cache.cache_path(cfg, "test", "test1"), meta)
    return cfg


def _thr(cfg, channel_set, agg="topk"):
    t = pl.read_csv(Path(cfg["paths"]["results"]) / "thresholds.csv")
    return t.filter((pl.col("channel_set") == channel_set) & (pl.col("score") == "band") & (pl.col("agg") == agg))


def test_restricted_set_gets_its_own_threshold(toy):
    score.run_score(toy)
    d = score.source_dir(toy)
    man = json.loads((d / "scores" / "manifest.json").read_text())
    assert sorted(man["sets"]) == ["all5", "all5-noPCV02Z", "p1three", "p1three-noPCV02Z"]
    assert man["full_set"] == "all5" and man["calib_sources"] == ["calib"]
    full, sub = _thr(toy, "all5"), _thr(toy, "p1three")
    assert full.height == sub.height == 1 and sub["n_calib_steps"][0] == 2 * (L_CALIB - W)
    # recompute the restricted threshold by hand from the calib cache: top-3 over its own 3 channels only
    rows = cache.read(toy, "calib").filter(pl.col("channel").is_in(["P1_A", "P1_B", "P1_PCV02Z"]))
    rows = rows.with_columns(s=pl.Series(score.band(rows["y_true"], rows["q05"], rows["q95"], 0.1)))
    S = rows.pivot(on="channel", index=["file", "t"], values="s").drop("file", "t").to_numpy()
    assert sub["threshold"][0] == pytest.approx(np.percentile(score.aggregate(S, "topk", 3), 99.5))
    assert sub["threshold"][0] < full["threshold"][0] / 2      # P2_D's calib spikes only enter the full set
    agg = pl.read_parquet(d / "scores" / "p1three" / "agg_test.parquet")
    assert agg.columns[:6] == ["file", "t", "time", "origin", "h", "label"]
    assert {"band_topk", "band_max", "crps_topk", "mae_mean"} <= set(agg.columns) and "band_mean" not in agg.columns
    assert agg.height == L_TEST - W
    chan = pl.read_parquet(d / "scores" / "all5" / "scores_test.parquet")
    assert chan.height == (L_TEST - W) * 5 and {"band", "crps", "mae"} <= set(chan.columns)
    # re-running replaces this run's rows instead of appending
    score.run_score(toy)
    assert _thr(toy, "p1three").height == 1


def test_readers_stop_without_forecasts(toy):
    other = with_variant(toy, "cf-onset")
    with pytest.raises(FileNotFoundError, match="run forecast first"):
        score.run_score(other)
    with pytest.raises(FileNotFoundError, match="run score first"):
        evaluate.run_evaluate(toy)


def test_readers_refuse_a_partly_forecast_split(toy):
    """D111: an interrupted forecast leaves train1a only; tau, thresholds and reads must not use half of calib."""
    (cache.run_dir(toy) / "calib" / "train1b.parquet").unlink()
    for fn in (lambda: cache.read(toy, "calib"), lambda: context.ff_tau(with_variant(toy, "ff")),
               lambda: score.run_score(toy)):
        with pytest.raises(FileNotFoundError, match=r"train1b\.parquet.*run forecast first"):
            fn()
    assert not (cache.run_dir(toy) / "scores").exists()             # nothing written from the partial split
    assert cache.read(toy, "calib", files=["train1a"]).height > 0    # a named file is still readable


def test_attacks_missing_from_the_scored_steps_raise():
    test = pl.DataFrame({"file": ["test1"] * 6, "t": np.arange(6), "label": [0, 1, 1, 0, 0, 0]})
    tab = pl.DataFrame({"attack_id": ["A1", "A2"], "segment": ["test1", "test2"], "start_idx": [1, 3],
                        "end_idx": [2, 4], "stratum": ["other", "other"]})
    assert [a.attack_id for a in evaluate._attacks_in(test, tab[:1], 2)] == ["A1"]
    with pytest.raises(ValueError, match="A2"):
        evaluate._attacks_in(test, tab, 2)


def test_fingerprint_covers_the_channel_sets(toy):
    """D112: a new extra set or another setup's targets must re-run score + evaluate."""
    from tsfm_ad import pipeline

    fp = pipeline._fingerprint(toy)
    extra = copy.deepcopy(toy)
    extra["channels"]["extra_sets"]["noP2"] = ["P2_C", "P2_D"]
    other = copy.deepcopy(toy)
    other["channels"]["setups"]["mv"]["processes"] = ["P1", "P2"]
    assert score.source_dir(extra) == score.source_dir(other) == score.source_dir(toy)   # same forecasts
    assert pipeline._fingerprint(extra) != fp and pipeline._fingerprint(other) != fp


def test_dual_joins_rolling_and_frozen(toy):
    fz = with_variant(toy, "frozen")
    ref = pl.DataFrame({"channel": np.repeat(CHANNELS, H), "h": np.tile(np.arange(1, H + 1), len(CHANNELS)),
                        **{q: np.full(H * len(CHANNELS), Z[i] + 1.0) for i, q in enumerate(QCOLS)}})
    cache.write(ref, cache.run_dir(fz) / "ref" / "reference.parquet", cache.meta(fz))
    du = with_variant(toy, "dual")
    score.run_score(du)
    agg = pl.read_parquet(score.source_dir(du) / "scores" / "all5" / "agg_test.parquet")
    expected = 1.0 / (Z[19] - Z[1] + 0.1)              # every quantile shifted by 1 over the frozen band width
    assert agg["dual_topk"].to_numpy() == pytest.approx(np.full(agg.height, expected))
    assert [c for c in agg.columns if c.startswith(("band", "crps", "mae"))] == []


def test_evaluate_end_to_end(toy):
    score.run_score(toy)
    evaluate.run_evaluate(toy)
    res = Path(toy["paths"]["results"])
    m = pl.read_csv(res / "metrics.csv")
    row = m.filter((pl.col("channel_set") == "all5") & (pl.col("score") == "band") & (pl.col("agg") == "topk"))
    assert row.height == 1 and row["recall"][0] == 1.0 and row["roc_auc"][0] > 0.9
    assert {"run_key", "hash8", "dataset", "model", "setup", "variant", "pa_f1_inflated"} <= set(m.columns)
    seg = pl.read_csv(res / "segments_per_attack.csv")
    head = seg.filter((pl.col("channel_set") == "all5") & (pl.col("score") == "band") & (pl.col("agg") == "topk"))
    assert sorted(head["N"].to_list()) == [3, 6, 12]           # sensitivity Ns for the headline score only
    r = head.filter(pl.col("N") == 6).row(0, named=True)
    assert (r["onset_n"], r["interior_n"], r["interior_eq_n"], r["offset_n"]) == (6, 4, 0, 6)
    assert r["onset_cov"] == 1.0 and r["latency_s"] == 0 and r["offset_det"] is True
    tp = pl.read_csv(res / "tapr.csv")
    assert set(tp["config"]) == {"headline", "strict", "haicon_like"}
    s = pl.read_csv(res / "segments_summary.csv")
    assert s.filter((pl.col("stratum") == "all") & (pl.col("channel_set") == "all5")).height > 0
    assert (res / "segments_by_h.csv").exists() and (res / "band_width_by_h.csv").exists()
    n_before = m.height
    evaluate.run_evaluate(toy)                                   # upsert: same rows, nothing appended
    assert pl.read_csv(res / "metrics.csv").height == n_before
