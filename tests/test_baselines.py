"""Baselines on hand-made segments: quantile values and no use of data at or after the forecast origin."""
from statistics import NormalDist

import numpy as np
import pytest

from tsfm_ad import baselines
from tsfm_ad.cache import QCOLS
from tsfm_ad.data import SegmentData

RES = 10
T0 = np.datetime64("2020-07-07T15:00:00", "us")


def seg(Z, name="test1", start=T0, labels=None):
    Z = np.asarray(Z, np.float32)
    L = Z.shape[1]
    time = start + np.arange(L) * np.timedelta64(RES, "s")
    lab = np.zeros(L, np.int8) if labels is None else np.asarray(labels, np.int8)
    return SegmentData(name, "test", name, time, lab, np.zeros((3, L), np.int8), Z,
                       [f"c{i}" for i in range(Z.shape[0])])


def quantiles(df, channel, t):
    row = df.filter((df["channel"] == channel) & (df["t"] == t))
    assert row.height == 1
    return row.select(QCOLS).to_numpy()[0]


def window_rows(df, o, H):
    return df.filter((df["origin"] == o)).sort(["channel", "h"]).select(["channel", "h", *QCOLS])


@pytest.fixture
def rng():
    return np.random.default_rng(0)


def test_grid_and_columns(rng):
    s = seg(rng.normal(size=(2, 20)), labels=[0] * 12 + [1] * 8)
    df = baselines.robust_z(s, H=3, W=5, window=4)
    assert df.height == 2 * 15                                   # one row per channel and scored step
    assert df.group_by(["channel", "t"]).len()["len"].max() == 1
    assert df["t"].min() == 5 and df["t"].max() == 19
    assert ((df["origin"] - 5) % 3 == 0).all()
    assert (df["h"] == df["t"] - df["origin"] + 1).all() and df["h"].max() == 3
    c1 = df.filter(df["channel"] == "c1").sort("t")
    np.testing.assert_array_equal(c1["y_true"].to_numpy(), s.Z[1, 5:])
    np.testing.assert_array_equal(c1["label"].to_numpy(), s.labels[5:])
    assert set(df["ctx_len"].to_list()) == {4}
    q = df.select(QCOLS).to_numpy()
    assert (np.diff(q, axis=1) >= 0).all()                     # quantiles sorted


def test_robust_z_values():
    x = np.array([[1, 2, 3, 4, 100, 0, 0, 0, 0, 0, 0]], float)  # window before o=5: 1, 2, 3, 4, 100
    df = baselines.robust_z(seg(x), H=3, W=5, window=5)
    q = quantiles(df, "c0", 6)                                   # t=6 comes from origin 5
    m, mad = 3.0, 1.0                                            # median 3, |x - 3| = 2, 1, 0, 1, 97 -> MAD 1
    assert q[QCOLS.index("q50")] == pytest.approx(m)
    z95 = NormalDist().inv_cdf(0.95)
    assert q[QCOLS.index("q95")] == pytest.approx(m + z95 * 1.4826 * mad, rel=1e-6)
    assert q[QCOLS.index("q05")] == pytest.approx(m - z95 * 1.4826 * mad, rel=1e-6)
    # window = 3 uses only steps 2..4 (3, 4, 100): median 4
    assert quantiles(baselines.robust_z(seg(x), 3, 5, window=3), "c0", 5)[10] == pytest.approx(4.0)


def test_last_value_values():
    fit = seg(0.5 * np.arange(50)[None, :], name="train2")       # Delta_h = 0.5 h exactly
    x = np.zeros((1, 14))
    x[0, 4] = 7.0                                                # y(o - 1) for o = 5
    df = baselines.last_value(seg(x), [fit], H=3, W=5)
    for h in (1, 2, 3):
        q = quantiles(df, "c0", 4 + h)
        np.testing.assert_allclose(q, 7.0 + 0.5 * h, rtol=1e-6)


def test_change_quantiles_never_cross_fit_segments():
    a = seg(np.zeros((1, 10)), name="train2")
    b = seg(np.full((1, 10), 100.0), name="train3")              # a jump between files would give 100
    dq = baselines.change_quantiles([a, b], H=3, channels=["c0"])
    assert np.all(dq == 0)


def test_seasonal_refday_values():
    season = 60                                                  # 6 steps at 10 s
    ref = seg(np.arange(6, dtype=float)[None, :] * 10, name="reference",
              start=np.datetime64("2020-08-09T11:00:00", "us"))
    pattern = np.tile(np.arange(6.0), 5)
    fit = seg((pattern + 2.0 * np.repeat(np.arange(5), 6))[None, :], name="train2")  # D = +2 every lag
    s = seg(np.zeros((1, 15)), start=np.datetime64("2020-07-07T15:00:20", "us"))      # clock offset 20 s
    df = baselines.seasonal_refday(s, ref, [fit], H=3, W=4, season_s=season)
    for t in range(4, 15):
        ref_idx = (2 + t) % 6                                    # ref day starts at :00, the segment at :20
        np.testing.assert_allclose(quantiles(df, "c0", t), ref.Z[0, ref_idx] + 2.0, rtol=1e-6)
    assert set(df["ctx_len"].to_list()) == {0}


@pytest.mark.parametrize("name", ["robustz", "lastvalue"])
def test_no_future_leakage(rng, name):
    fit = seg(rng.normal(size=(3, 200)), name="train2")
    x = rng.normal(size=(3, 41))
    H, W = 3, 8
    run = {"robustz": lambda s: baselines.robust_z(s, H, W, window=6),
           "lastvalue": lambda s: baselines.last_value(s, [fit], H, W)}[name]
    base = run(seg(x))
    for o in range(W, 41, H):
        y = x.copy()
        y[:, o:] = rng.normal(size=y[:, o:].shape) * 50 + 9      # everything from the origin on changes
        changed = run(seg(y))
        assert window_rows(changed, o, H).equals(window_rows(base, o, H)), f"origin {o} saw data at t >= o"


def test_seasonal_refday_reads_only_reference_and_fit(rng):
    ref = seg(rng.normal(size=(2, 6)), name="reference", start=np.datetime64("2020-08-09T11:00:00", "us"))
    fit = seg(rng.normal(size=(2, 60)), name="train2")
    a = baselines.seasonal_refday(seg(rng.normal(size=(2, 20))), ref, [fit], 3, 5, season_s=60)
    b = baselines.seasonal_refday(seg(rng.normal(size=(2, 20)) * 100), ref, [fit], 3, 5, season_s=60)
    assert a.select(QCOLS).equals(b.select(QCOLS))
    assert not a["y_true"].equals(b["y_true"])


def test_seasonal_refday_rejects_wrong_reference_length(rng):
    ref = seg(rng.normal(size=(1, 5)), name="reference")
    with pytest.raises(ValueError, match="season"):
        baselines.seasonal_refday(seg(rng.normal(size=(1, 20))), ref, [ref], 3, 5, season_s=60)
