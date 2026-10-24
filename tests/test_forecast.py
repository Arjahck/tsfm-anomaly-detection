"""Rolling, frozen and cf-onset forecasting with a stub forecaster (PLAN.md 6, 11 "Tests", D58). No model download.

The loop tests use `Stub` on the Timestral call path (fcfg without `model`); the run_forecast tests use the smoke
config, i.e. Chronos-2 (D117), with the fake pipeline of tests/fakes.py."""
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import polars as pl
import pytest
import torch

from fakes import FakeChronos2
from tsfm_ad import cache, context, data, ff_results, forecast
from tsfm_ad.cache import QCOLS
from tsfm_ad.config import load_config, with_variant
from tsfm_ad.data import Group, SegmentData

ROOT = Path(__file__).resolve().parents[1]
MED, LO = QCOLS.index("q50"), QCOLS.index("q01")
SMOKE_PREPARED = ROOT / "cache" / "hai2103-10s-smoke" / "prepared"


class Stub:
    """q50 = the last context value, every other quantile = the context length T. Records every call."""

    def __init__(self):
        self.calls = []

    def forecast(self, context, prediction_length, past_covariates=None, symmetric_averaging=True,
                 clip_nonnegative=True):
        x = np.asarray(context, np.float32)
        x = x[:, None] if x.ndim == 2 else x
        cov = None if past_covariates is None else np.asarray(past_covariates, np.float32).copy()
        self.calls.append({"ctx": x.copy(), "cov": cov, "H": prediction_length})
        q = np.full((*x.shape[:2], prediction_length, len(QCOLS)), x.shape[-1], np.float32)
        q[..., MED] = x[:, :, -1:]
        return SimpleNamespace(quantiles=torch.from_numpy(q))


CHANNELS = ["a", "b", "c", "d"]
UNI = [Group("all", ["a", "b", "c"], [])]
MV = [Group("P1", ["a", "b"], ["d"]), Group("P2", ["c"], [])]


def make_seg(L=40, name="f1", seed=None):
    """Z[c, t] = 1000 c + t, so every value names its channel and step."""
    Z = (1000 * np.arange(len(CHANNELS))[:, None] + np.arange(L)[None]).astype(np.float32)
    if seed is not None:
        Z += np.random.default_rng(seed).normal(size=Z.shape).astype(np.float32)
    time = np.datetime64("2020-07-07T15:00:00", "us") + np.arange(L) * np.timedelta64(10, "s")
    labels = np.zeros(L, np.int8)
    labels[22:26] = 1
    return SegmentData(name, "test", name, time, labels, np.zeros((3, L), np.int8), Z, list(CHANNELS))


def fcfg(H=5, W=10, cap=1000, multivariate=False):
    return {"H": H, "W": W, "cap": cap, "warmup": "in_file", "symmetric_averaging": True,
            "clip_nonnegative": False, "multivariate": multivariate}


def test_origins():
    assert forecast.origins(40, 10, 5).tolist() == [10, 15, 20, 25, 30, 35]


@pytest.mark.parametrize("cap", [1000, 7])
def test_rows_origin_h_ctx_len_one_row_per_step(cap):
    seg, f = make_seg(), fcfg(cap=cap)
    df = forecast.rolling(Stub(), seg, UNI, f)
    assert df.height == 3 * (40 - 10)
    for ch, g in df.group_by("channel"):
        assert sorted(g["t"].to_list()) == list(range(10, 40)), ch
    o = 10 + (df["t"] - 10) // 5 * 5
    assert (df["origin"] == o).all()
    assert (df["h"] == df["t"] - df["origin"] + 1).all() and df["h"].is_between(1, 5).all()
    assert np.array_equal(df["ctx_len"].to_numpy(), np.minimum(df["origin"].to_numpy(), cap))
    assert (df["q01"] == df["ctx_len"]).all()                     # the stub reports T
    assert not df["substituted"].any()


@pytest.mark.parametrize("cap", [1000, 7])
def test_context_ends_before_window_and_cap_slice(cap):
    seg, stub = make_seg(), Stub()
    df = forecast.rolling(stub, seg, UNI, fcfg(cap=cap))
    Z = seg.rows(["a", "b", "c"])
    for o, call in zip(forecast.origins(40, 10, 5), stub.calls):
        assert np.array_equal(call["ctx"][:, 0], Z[:, max(0, o - cap):o])    # never holds y(t), t >= o
    q50 = df["q50"].to_numpy()
    prev = seg.Z[[CHANNELS.index(c) for c in df["channel"]], df["origin"].to_numpy() - 1]
    assert np.array_equal(q50, prev)


def test_y_true_label_time_equal_prepared_data():
    seg = make_seg(seed=1)
    df = forecast.rolling(Stub(), seg, UNI, fcfg())
    rows = [CHANNELS.index(c) for c in df["channel"]]
    t = df["t"].to_numpy()
    assert np.array_equal(df["y_true"].to_numpy(), seg.Z[rows, t])
    assert np.array_equal(df["label"].to_numpy(), seg.labels[t])
    assert np.array_equal(df["time"].to_numpy(), seg.time[t])


def test_multivariate_one_call_per_group_covariates_from_data():
    seg, stub = make_seg(), Stub()
    df = forecast.rolling(stub, seg, MV, fcfg(multivariate=True))
    assert len(stub.calls) == 2 * 6
    assert df["channel"].unique(maintain_order=True).to_list() == ["a", "b", "c"]
    for i, o in enumerate(forecast.origins(40, 10, 5)):
        p1, p2 = stub.calls[2 * i], stub.calls[2 * i + 1]
        assert p1["ctx"].shape == (1, 2, o) and p2["ctx"].shape == (1, 1, o)
        assert np.array_equal(p1["cov"][0], seg.rows(["d"])[:, :o]) and p2["cov"] is None


def test_prepend_shifts_context_not_scored_steps():
    seg, stub = make_seg(), Stub()
    prefix = -np.ones((4, 12), np.float32) * np.arange(1, 13)
    df = forecast.rolling(stub, seg, UNI, fcfg(cap=15), prefix=prefix)
    assert df["t"].min() == 10 and (df["ctx_len"] == 15).all()
    full = np.concatenate([prefix, seg.Z], axis=1)[:3]
    for o, call in zip(forecast.origins(40, 10, 5), stub.calls):
        assert np.array_equal(call["ctx"][:, 0], full[:, 12 + o - 15:12 + o])


def test_non_finite_context_raises():
    seg = make_seg()
    seg.Z[1, 3] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        forecast.rolling(Stub(), seg, UNI, fcfg())


def test_frozen_forecast_and_channel_h_join():
    ref, stub = make_seg(L=50, name="reference"), Stub()
    f = fcfg(cap=20, multivariate=True)
    ref_df = context.frozen_forecast(stub, ref, MV, f)
    assert ref_df.height == 3 * 5 and ref_df.columns == ["channel", "h", *QCOLS]
    assert stub.calls[0]["ctx"].shape == (1, 2, 20) and np.array_equal(stub.calls[0]["cov"][0], ref.rows(["d"])[:, 30:])
    last = dict(zip(["a", "b", "c"], ref.rows(["a", "b", "c"])[:, -1]))
    assert all(r["q50"] == last[r["channel"]] and r["q01"] == 20 for r in ref_df.iter_rows(named=True))
    roll = forecast.rolling(Stub(), make_seg(), MV, f)
    joined = roll.select("channel", "t", "h").join(ref_df.with_columns(pl.col("h").cast(pl.Int64)),
                                                   on=["channel", "h"], how="left")
    assert joined.height == roll.height and joined["q50"].null_count() == 0


def test_cf_onset_origin_is_onset_and_context_ends_before_it():
    seg, stub = make_seg(), Stub()
    attacks = pl.DataFrame({"attack_id": ["X1", "X2", "Y"], "segment": ["f1", "f1", "other"],
                            "start_idx": [22, 37, 5], "n_steps": [4, 2, 3]})
    df = forecast.cf_onset(stub, seg, UNI, fcfg(cap=15), attacks, N=3)
    assert len(stub.calls) == 2 and [c["H"] for c in stub.calls] == [7, 3]   # the second is cut at the file end
    assert np.array_equal(stub.calls[0]["ctx"][:, 0], seg.rows(["a", "b", "c"])[:, 7:22])
    first = df.filter(pl.col("origin") == 22)
    assert sorted(first["t"].unique().to_list()) == list(range(22, 29))
    assert (first["h"] == first["t"] - 21).all() and (first["ctx_len"] == 15).all()
    assert (first["q50"] == first["channel"].replace_strict({"a": 21.0, "b": 1021.0, "c": 2021.0})).all()


@pytest.mark.skipif(not (SMOKE_PREPARED / "manifest.json").exists(), reason="run `tsfm-ad prepare` on smoke.yaml")
def test_run_forecast_with_stub_writes_and_skips(tmp_path, monkeypatch):
    cfg = load_config(ROOT / "configs" / "smoke.yaml")
    cfg["paths"] = {k: str(ROOT / v) for k, v in cfg["paths"].items()}
    cfg["paths"].update(cache=str(tmp_path / "cache"), results=str(tmp_path / "results"))
    cfg["model"]["device"] = "cpu"
    assert cfg["model"]["name"] == "chronos2"
    shutil.copytree(SMOKE_PREPARED, tmp_path / "cache" / "hai2103-10s-smoke" / "prepared")
    stub = FakeChronos2()
    monkeypatch.setattr(forecast, "load_forecaster", lambda *a, **k: stub)

    forecast.run_forecast(cfg, "all")
    test = cache.read(cfg, "test")
    seg = data.load_segment(cfg, "test1")
    n_scored = len(seg) - forecast.forecast_params(cfg)["W"]
    assert test.height == n_scored * 51 and cache.read(cfg, "calib").height == n_scored * 51
    assert test["h"].is_between(1, 30).all()
    t = test["t"].to_numpy()
    assert np.array_equal(test["y_true"].to_numpy(), seg.Z[[seg.channels.index(c) for c in test["channel"]], t])
    rdir = cache.run_dir(cfg)
    assert (rdir / "meta.json").exists() and pl.read_csv(rdir / "calls_test.csv").height == n_scored // 30
    assert all(c["array_input"] and not c["cross_learning"] for c in stub.calls)   # 51 one-variate items per call
    assert pl.read_csv(tmp_path / "results" / "runs.csv")["model_code"].to_list() == ["chronos-forecasting==2.3.2"] * 2
    n_calls = len(stub.calls)
    forecast.run_forecast(cfg, "all")                              # every parquet exists: nothing runs
    assert len(stub.calls) == n_calls

    ff = with_variant(cfg, "ff")
    forecast.run_forecast(ff, "all")
    assert cache.read(ff, "test", extra=context.ff_extra(ff)).height == n_scored * 51
    ff_dir = cache.run_dir(ff, extra=context.ff_extra(ff))
    names = [c for g in data.setup_groups(ff, "uni") for c in g.targets]
    ff_results.write_ff_results(ff, ff_dir, {"run_key": "rk", "hash8": "h"}, context.ff_tau(ff), names)
    assert pl.read_csv(tmp_path / "results" / "ff_thresholds.csv").height == 51
    act = pl.read_csv(tmp_path / "results" / "ff_activity.csv")
    assert act.height == 51 * 2 and (act["scored_steps"] == n_scored).all()
    forecast.run_forecast(with_variant(cfg, "cf-onset"), "all")
    assert cache.read(with_variant(cfg, "cf-onset"), "test").height == 51 * (20 + 6)
    forecast.run_forecast(with_variant(cfg, "frozen"), "all")
    assert cache.read_ref(cfg).height == 51 * 30


class FailingFake(FakeChronos2):
    """Raises on call number `fail_at` (1-based), as an interrupted run would."""

    def __init__(self, fail_at):
        super().__init__()
        self.fail_at = fail_at

    def predict(self, *a, **k):
        if len(self.calls) + 1 == self.fail_at:
            raise RuntimeError("interrupted")
        return super().predict(*a, **k)


@pytest.mark.skipif(not (SMOKE_PREPARED / "manifest.json").exists(), reason="run `tsfm-ad prepare` on smoke.yaml")
def test_resumed_forecast_logs_each_file_once(tmp_path, monkeypatch):
    """D116: calls of an interrupted file are not logged, and runs.csv keeps the files written before it."""
    cfg = load_config(ROOT / "configs" / "smoke.yaml")
    cfg["paths"] = {k: str(ROOT / v) for k, v in cfg["paths"].items()}
    cfg["paths"].update(cache=str(tmp_path / "cache"), results=str(tmp_path / "results"))
    cfg["model"]["device"] = "cpu"
    shutil.copytree(SMOKE_PREPARED, tmp_path / "cache" / "hai2103-10s-smoke" / "prepared")
    n = (len(data.load_segment(cfg, "test1")) - forecast.forecast_params(cfg)["W"]) // 30   # calls per file
    monkeypatch.setattr(forecast, "load_forecaster", lambda *a, **k: FailingFake(n + 5))   # fails inside test1
    monkeypatch.setattr(forecast, "estimate_runtime", lambda *a, **k: 0.0)
    with pytest.raises(RuntimeError):
        forecast.run_forecast(cfg, "all")
    rdir, runs = cache.run_dir(cfg), tmp_path / "results" / "runs.csv"
    assert pl.read_csv(rdir / "calls_calib.csv").height == n and not (rdir / "calls_test.csv").exists()
    assert pl.read_csv(runs)["split"].to_list() == ["calib"]
    monkeypatch.setattr(forecast, "load_forecaster", lambda *a, **k: FakeChronos2())
    forecast.run_forecast(cfg, "all")
    assert pl.read_csv(rdir / "calls_test.csv").height == n
    r = pl.read_csv(runs)
    assert r["split"].to_list() == ["calib", "test"] and r["n_calls"].to_list() == [n, n]
