"""The paper's contamination share (paper.py): the expected value under a uniform grid phase and the origin split.
A silent error here changes the paper's measure and its LANL numbers."""
import numpy as np

from tsfm_ad import paper


def test_kappa_hat_matches_every_grid_phase():
    for L, S in ((1, 30), (7, 30), (20, 30), (30, 30), (95, 30), (1440, 30), (20, 6)):
        shares = []
        for phase in range(S):                        # origins at onset - phase + k S
            t = np.arange(L)
            origin = -phase + S * ((t + phase) // S)
            shares.append((origin > 0).mean())
        assert np.isclose(paper.kappa_hat([L], S)[0], np.mean(shares)), (L, S)
    assert np.isclose(paper.kappa_hat([600], 600)[0], paper.kappa_r(1.0), atol=1e-3)   # continuous limit
    assert np.isclose(paper.kappa_r(4.0), 1 - 1 / 8) and np.isclose(paper.kappa_r(0.5), 0.25)


def test_origin_split_and_grid_phase():
    t = np.arange(100, 200)
    origin = 100 + 30 * ((t - 100) // 30)              # origins 100, 130, 160, 190
    alarm = np.zeros(len(t), bool)
    alarm[(t >= 135) & (t < 140)] = True               # contaminated steps (origin 130 > onset 125)
    alarm[(t >= 125) & (t < 127)] = True               # clean steps (origin 100)
    r = paper.origin_split(t, origin, alarm, 125, 165, width=np.ones(len(t)))
    assert r == {"L": 40, "n_post": 35, "n_pre": 5, "a_post": 5, "a_pre": 2, "w_post": 35.0, "w_pre": 5.0}
    r = paper.origin_split(t, origin, alarm, 130, 140)  # an onset on an origin: that forecast's context is clean
    assert r["n_pre"] == 10 and r["n_post"] == 0
    assert paper.grid_phase([150, 151, 179, 180], 150, 30).tolist() == [0, 1, 29, 0]
