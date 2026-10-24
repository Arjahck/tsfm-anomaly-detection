"""The D128 effect diagnostic (PLAN.md 14.5, D129): its raw path is the adapter minus the constant-row guard and
nothing else, and it rebuilds exactly the contexts that forecast.rolling, forecast.cf_onset and
context.frozen_forecast send to the model. A silent mismatch would misreport the size of the guard."""
import numpy as np
import polars as pl
import pytest

from fakes import FakeChronos2
from test_chronos2 import MV, series, tiny_pipeline
from tsfm_ad import context, d128, forecast, model_chronos2
from tsfm_ad.data import Group, SegmentData

SETUP = [Group("P1", ["a", "b"], ["c"]), Group("P2", ["d"], ["e"])]


def make_seg(L=137):
    Z = series(5, L, seed=7)                                       # random walks: no constant row
    time = np.datetime64("2020-07-07T15:00:00", "us") + np.arange(L) * np.timedelta64(10, "s")
    return SegmentData("f1", "test", "f1", time, np.zeros(L, np.int8), np.zeros((3, L), np.int8), Z,
                       ["a", "b", "c", "d", "e"])


def fcfg(cap):
    return {"H": 30, "W": 20, "cap": cap, "warmup": "in_file", "model": "chronos2", "symmetric_averaging": None,
            "clip_nonnegative": None, "multivariate": True}


def sent(fake):
    """(target, covariate rows, H) of every item the fake pipeline received, in call order."""
    return [(it["target"], np.stack([it["cov"][k] for k in sorted(it["cov"])]), c["H"])
            for c in fake.calls for it in c["items"]]


@pytest.mark.parametrize("cap", [1000, 40])                       # 40: the cap binds from origin 40 on
def test_contexts_are_the_ones_the_forecast_code_sends(cap):
    seg, f = make_seg(), fcfg(cap)
    attacks = pl.DataFrame({"segment": ["f1", "f1", "f2"], "start_idx": [90, 35, 50], "n_steps": [8, 12, 5]})
    runs = {"rolling": lambda fk: forecast.rolling(fk, seg, SETUP, f),
            "cf-onset": lambda fk: forecast.cf_onset(fk, seg, SETUP, f, attacks, 4),
            "frozen": lambda fk: context.frozen_forecast(fk, seg, SETUP, f)}
    for kind, run in runs.items():
        fake = FakeChronos2()
        run(fake)
        ours = [(tgt, cov, H) for *_, tgt, cov, _, H in d128.calls([seg], SETUP, kind, f, attacks, 4)]
        assert len(ours) == len(sent(fake)) > 0
        for (t1, c1, h1), (t2, c2, h2) in zip(ours, sent(fake)):
            assert np.array_equal(t1, t2) and np.array_equal(c1, c2) and h1 == h2, kind


def test_raw_group_is_the_adapter_without_the_guard_only():
    pipe, X = tiny_pipeline(), series(4, 120, seed=5)
    keep = model_chronos2._zero_constant_rows
    tgt, cov = X[:2], X[2:]
    assert not d128.has_constant_row(tgt, cov)
    assert np.array_equal(d128.raw_group(pipe, tgt, cov, 30, True), model_chronos2.predict_group(pipe, tgt, cov, 30,
                                                                                                 True))
    moved = []
    for level in (0.43639088, -1.1848395, 12.0189):                # HAI levels whose float32 mean is inexact
        c = cov.copy()
        c[0] = level
        assert d128.has_constant_row(tgt, c)
        moved.append(not np.array_equal(d128.raw_group(pipe, tgt, c, 30, True),
                                        model_chronos2.predict_group(pipe, tgt, c, 30, True)))
    assert any(moved)                                              # the guard changes these calls, so it is measured
    assert model_chronos2._zero_constant_rows is keep              # the guard is back on afterwards
    assert forecast.predict(pipe, [SETUP[0]], [(tgt, c[:1])], 30, MV).shape == (2, 30, 21)


def test_a_univariate_call_reruns_only_its_constant_rows():
    X = series(4, 50, seed=8)
    X[2] = 0.43639088
    g = Group("all", ["a", "b", "c", "d"], [])
    names, tgt, cov, y = d128.changed_part(g, X, None, X[:, :5], False)
    assert names == ["c"] and np.array_equal(tgt, X[2:3]) and cov is None and np.array_equal(y, X[2:3, :5])
    assert d128.changed_part(g, X, None, None, True)[0] == ["a", "b", "c", "d"]   # multivariate: the whole call
    assert d128.changed_part(g, series(4, 50, seed=8), None, None, False) is None
