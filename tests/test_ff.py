"""Forecast Fallback hook, its effect on the rolling context, and FF attribution (PLAN.md 8 exp 3a, 11, D24, D25,
D44, D58). Stub forecaster only."""
import numpy as np
import polars as pl

from test_forecast import CHANNELS, MV, UNI, Stub, fcfg, make_seg
from tsfm_ad import context, ff_results, forecast
from tsfm_ad.context import Episode, Fallback


def run(fb, y, H=3):
    """Feed y (C, n) to the hook window by window with q50 = 0; returns the concatenated masks (C, n)."""
    y = np.atleast_2d(np.asarray(y, float))
    return np.concatenate([fb(o, np.zeros((len(y), min(H, y.shape[1] - o))), y[:, o:o + H])
                           for o in range(0, y.shape[1], H)], axis=1)


def test_two_exceedances_do_not_trigger():
    fb = Fallback([1.0])
    assert not run(fb, [[0, 2, 2, 0, 2, 2, 0, 0, 2, 2]]).any()
    assert fb.episodes() == []


def test_trigger_and_substitution_from_the_third_step():
    fb = Fallback([1.0])
    mask = run(fb, [[0, 2, 2, 2, 0, 0]], H=6)
    assert mask[0].tolist() == [False, False, False, True, True, True]
    assert fb.episodes() == [Episode(0, 3, 5, 3, "file_end")]


def test_run_counter_carries_across_window_boundary():
    fb = Fallback([1.0])
    m1 = fb(0, np.zeros((1, 3)), np.array([[0, 2, 2]]))
    m2 = fb(3, np.zeros((1, 3)), np.array([[2, 0, 0]]))
    assert not m1.any() and m2[0].tolist() == [True, True, True]
    assert fb.episodes()[0].start_t == 3


def test_persistence_without_exit_and_per_feature():
    fb = Fallback([1.0, 1.0])
    y = np.zeros((2, 30))
    y[0, 4:7] = 5                                     # channel 0 triggers at t = 6, then looks normal again
    mask = run(fb, y)
    assert mask[0, 6:].all() and not mask[0, :6].any() and not mask[1].any()
    assert fb.episodes() == [Episode(0, 6, 29, 24, "file_end")]


def test_exit_after_max_duration_and_reentry_needs_three_new():
    fb = Fallback([1.0], max_duration=4)
    y = np.full((1, 15), 5.0)                          # exceeds at every step
    mask = run(fb, y)
    # trigger t=2, substituted 2..5, exit, count restarts at 6: 6, 7, then 8 triggers again, 8..11, exit, 14
    assert np.flatnonzero(mask[0]).tolist() == [2, 3, 4, 5, 8, 9, 10, 11, 14]
    assert fb.episodes() == [Episode(0, 2, 5, 4, "max_duration"), Episode(0, 8, 11, 4, "max_duration"),
                             Episode(0, 14, 14, 1, "file_end")]


def test_reset_per_file():
    fb = Fallback([1.0])
    run(fb, [[0, 0, 0, 2, 2, 2]])
    assert fb.episodes() and fb.active.any()
    fb.reset()
    assert fb.episodes() == [] and not fb.active.any()
    fb(0, np.zeros((1, 3)), np.array([[0, 2, 2]]))     # file 2 ends with 2 exceedances
    fb.reset()                                         # file 3 starts with 1: without reset it would be the 3rd
    assert not fb(0, np.zeros((1, 3)), np.array([[2, 0, 0]])).any()


def test_scope_all_substitutes_every_channel():
    fb = Fallback([1.0, 1.0], scope="all")
    y = np.zeros((2, 6))
    y[1, :3] = 5
    assert np.flatnonzero(run(fb, y, H=6).all(axis=0)).tolist() == [2, 3, 4, 5]


def _ff_rolling(H=5, W=10):
    """mv setup on a file whose channel `a` jumps at t = 20; the persistence stub then exceeds tau = 0.5."""
    seg, stub = make_seg(L=50, seed=0), Stub()
    seg.Z[:, :] = np.round(seg.Z / 1000) * 1000         # flat levels per channel, so normal errors are 0
    seg.Z[0, 20:] += 10.0
    z_before = seg.Z.copy()
    fb = Fallback([0.5, 0.5, 0.5])
    df = forecast.rolling(stub, seg, MV, fcfg(H=H, W=W, multivariate=True), hook=fb)
    return seg, stub, fb, df, z_before


def test_context_holds_q50_exactly_where_substituted_and_covariates_untouched():
    seg, stub, fb, df, z_before = _ff_rolling()
    assert np.array_equal(seg.Z, z_before)                         # Z_obs is never written
    sub = df.filter(pl.col("substituted"))
    assert set(sub["channel"]) == {"a"} and sub["t"].min() == 22  # 20, 21 observed, the 3rd exceeding step on
    names = ["a", "b"]
    q50 = {(r["channel"], r["t"]): r["q50"] for r in df.iter_rows(named=True)}
    subst = {(r["channel"], r["t"]) for r in sub.iter_rows(named=True)}
    for i, o in enumerate(forecast.origins(50, 10, 5)):
        p1 = stub.calls[2 * i]
        assert np.array_equal(p1["cov"][0], seg.rows(["d"])[:, :o])            # covariates from Z_obs
        for c, name in enumerate(names):
            want = [q50[(name, t)] if (name, t) in subst else seg.Z[CHANNELS.index(name), t] for t in range(o)]
            assert np.array_equal(p1["ctx"][0, c], np.array(want, np.float32)), (name, o)


def test_cached_y_true_is_observed_at_substituted_steps():
    seg, _, _, df, _ = _ff_rolling()
    sub = df.filter(pl.col("substituted"))
    assert sub.height > 0
    assert np.array_equal(sub["y_true"].to_numpy(), seg.Z[0, sub["t"].to_numpy()])
    assert (sub["y_true"] != sub["q50"]).any()


def test_hook_that_never_fires_equals_plain_rolling():
    seg = make_seg(seed=3)
    plain = forecast.rolling(Stub(), seg, UNI, fcfg())
    ff = forecast.rolling(Stub(), seg, UNI, fcfg(), hook=Fallback([1e9] * 3))
    assert plain.equals(ff)


def test_ff_thresholds_are_per_channel_percentiles():
    rng = np.random.default_rng(0)
    e = rng.normal(size=(2, 1000))
    df = pl.DataFrame({"channel": ["x"] * 1000 + ["y"] * 1000, "q50": np.zeros(2000), "y_true": e.reshape(-1)})
    tau = context.ff_thresholds(df, 99.5)
    assert np.isclose(tau["x"], np.percentile(np.abs(e[0]), 99.5))
    assert np.isclose(tau["y"], np.percentile(np.abs(e[1]), 99.5))
    assert context.ff_extra({"variant": {"kind": "rolling"}}) is None


def test_ff_group_and_active_at_onset_on_hand_made_file():
    eps = pl.concat([
        context.episodes_frame("f1", [Episode(0, 100, 130, 31, "file_end"), Episode(1, 90, 104, 15, "max_duration")],
                               ["a", "b"]),
        context.episodes_frame("f1", [Episode(0, 212, 260, 49, "file_end")], ["a"]),
        context.episodes_frame("f2", [Episode(0, 5, 9, 5, "max_duration")], ["a"]),
    ])
    attacks = pl.DataFrame({"attack_id": ["A", "B", "C", "D"], "segment": ["f1", "f1", "f1", "f2"],
                            "start_idx": [102, 200, 300, 50], "end_idx": [110, 206, 320, 60]})
    st = ff_results.ff_attack_state(eps, attacks, N=6).sort("attack_id")
    assert st["ff_group"].to_list() == ["pre_active", "triggered_in_attack", "none", "none"]
    assert st["ff_active_at_onset"].to_list() == [True, False, False, False]
    assert st["ff_n_channels_active_at_onset"].to_list() == [2, 0, 0, 0]
    assert st["ff_fallback_age_at_onset_steps"].to_list() == [12, None, None, None]
    assert st["ff_first_trigger_after_onset_steps"].to_list() == [None, 12, None, None]   # 212 <= 206 + 6
    only_a = ff_results.ff_attack_state(eps, attacks, N=6, channels=["a"]).sort("attack_id")
    assert only_a["ff_n_channels_active_at_onset"].to_list() == [1, 0, 0, 0]
    assert only_a["ff_fallback_age_at_onset_steps"].to_list() == [2, None, None, None]
