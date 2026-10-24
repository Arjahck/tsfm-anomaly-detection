"""Official TaPR through tapr_wrap: the toy of research/tapr.md section 4, file joining, guards (PLAN.md 9, D30, D31)."""
import numpy as np
import pytest

from tsfm_ad import tapr_wrap


def toy():
    """n = 100; attacks [10, 19] and [50, 79]; predictions [12, 16], [45, 55], [85, 90] (inclusive)."""
    y, p = np.zeros(100, np.int8), np.zeros(100, np.int8)
    y[10:20] = y[50:80] = 1
    p[12:17] = p[45:56] = p[85:91] = 1
    return y, p


def test_toy_delta0():
    r = tapr_wrap.tapr(*toy(), theta=0.5, delta=0, alpha=0.5)
    assert r["TaP"] == pytest.approx(0.590909, abs=1e-6)
    assert r["TaR"] == pytest.approx(0.175, abs=1e-9)
    assert r["F1"] == pytest.approx(0.270030, abs=1e-6)
    assert r["TaR_d"] == 0.0                     # A1 is covered exactly 0.5 and the official test is `>` theta
    assert r["TaP_d"] == pytest.approx(2 / 3)
    assert r["n_pred_ranges"] == 3 and r["n_anomalies"] == 2


def test_toy_delta10():
    r = tapr_wrap.tapr(*toy(), theta=0.5, delta=10, alpha=0.5)
    assert r["TaP"] == pytest.approx(0.604928, abs=1e-6)
    assert r["TaR"] == pytest.approx(0.179206, abs=1e-6)
    assert r["F1"] == pytest.approx(0.276500, abs=1e-6)


def test_separate_thetas_use_one_object_each():
    y, p = toy()
    both = tapr_wrap.tapr(y, p, delta=0, theta_r=0.1, theta_p=0.7)
    assert both["TaR"] == pytest.approx(tapr_wrap.tapr(y, p, theta=0.1, delta=0)["TaR"])
    assert both["TaP"] == pytest.approx(tapr_wrap.tapr(y, p, theta=0.7, delta=0)["TaP"])
    assert both["TaR"] == pytest.approx(0.675) and both["TaP_d"] == pytest.approx(1 / 3)


def test_detector_that_never_fires_scores_zero():
    y, _ = toy()                                 # the official file loader would give TaR = 1.0 here (bug B1)
    r = tapr_wrap.tapr(y, np.zeros_like(y), delta=10)
    assert r["TaR"] == 0.0 and r["TaP"] == 0.0 and r["F1"] == 0.0 and r["n_pred_ranges"] == 0


def test_join_files_keeps_ranges_apart():
    # file 1 ends inside an attack with an alarm, file 2 starts inside one: a plain concat would merge them
    f1 = (np.array([0, 0, 1, 1]), np.array([0, 0, 0, 1]))
    f2 = (np.array([1, 1, 0, 0]), np.array([1, 0, 0, 0]))
    assert tapr_wrap.runs(np.concatenate([f1[0], f2[0]])) == [(2, 5)]
    delta = 3
    yt, yp = tapr_wrap.join_files([f1, f2], gap=delta + 1)
    assert len(yt) == len(yp) == 4 + delta + 1 + 4
    assert tapr_wrap.runs(yt) == [(2, 3), (8, 9)]
    assert tapr_wrap.runs(yp) == [(3, 3), (8, 8)]
    assert not yt[4:8].any() and not yp[4:8].any()
    # file 1's ambiguous zone (delta steps after its attack) ends inside the gap, before file 2 starts
    r = tapr_wrap.tapr(yt, yp, theta=0.5, delta=delta)
    assert r["n_anomalies"] == 2 and r["n_pred_ranges"] == 2


def test_guards():
    y, p = toy()
    with pytest.raises(ValueError, match="delta"):
        tapr_wrap.tapr(y, p, delta=1)
    short = y.copy()
    short[30] = 1                                # a length-1 attack crashes TaPR.py
    with pytest.raises(ValueError, match="length 1"):
        tapr_wrap.tapr(short, p, delta=0)
    with pytest.raises(ValueError):
        tapr_wrap.join_files([(y, p)], gap=0)


def test_vendored_file_is_checked():
    mod = tapr_wrap.load_official()
    assert hasattr(mod, "TaPR") and hasattr(mod, "Term")
