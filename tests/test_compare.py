"""Matched false-alarm thresholds and bootstrap blocks (compare.py, D135): a wrong cut or threshold silently changes
every compared number."""
import numpy as np
import pytest

from tsfm_ad import compare


def test_fa_threshold_allows_floor_of_target_normal_alarms():
    rng = np.random.default_rng(0)
    s = rng.normal(size=3600)                      # 3600 normal steps at 10 s = 10 h
    normal = np.ones(3600, bool)
    for F, k in ((0.5, 5), (1.0, 10), (2.5, 25)):
        thr = compare.fa_threshold(s, normal, F, 10)
        assert (s[normal] > thr).sum() == k        # no ties: exactly floor(F x 10 h)


def test_fa_threshold_ties_and_limits():
    s = np.array([0.0] * 90 + [1.0] * 10)          # 100 normal steps = 1000 s
    normal = np.ones(100, bool)
    assert compare.fa_threshold(s, normal, 3600 * 5 / 1000, 10) == 1.0       # k = 5 lands in the tie at 1.0: 0 alarms
    assert compare.fa_threshold(s, normal, 3600 * 10 / 1000, 10) == 0.0      # k = 10: the ten 1.0 steps alarm
    assert compare.fa_threshold(s, normal, 0.0, 10) == 1.0                   # k = 0: no normal alarm
    assert compare.fa_threshold(s, normal, 1e6, 10) == -np.inf               # every step alarms


def test_fa_threshold_ignores_attack_steps():
    s = np.array([5.0, 5.0, 1.0, 2.0, 3.0, 4.0])
    normal = np.array([False, False, True, True, True, True])
    thr = compare.fa_threshold(s, normal, 3600 * 1 / 40, 10)                  # 4 normal steps = 40 s, k = 1
    assert thr == 3.0 and (s[normal] > thr).sum() == 1


def test_blocks_cover_every_step_and_never_cut_an_attack():
    y = np.zeros(100, int)
    y[8:14] = 1                                    # attack 8..13, delta zone 14..16
    y[60:63] = 1
    bounds = np.array([0, 50, 100])                # two files
    blks = compare.blocks(y, bounds, block=10, delta=3)
    assert blks[0][0] == 0 and blks[-1][1] == 100
    assert all(a[1] == b[0] for a, b in zip(blks, blks[1:]))
    cuts = {a for a, _ in blks[1:]}
    assert 50 in cuts                              # every file boundary is a cut
    for s, e in ((8, 13), (60, 62)):
        assert not any(s < c <= e + 3 for c in cuts)
    assert 17 in cuts and 20 not in cuts           # the cut at 10 moved to 17, the next one 10 steps later


@pytest.mark.parametrize("seed", [0, 3])
def test_resamples_are_paired_and_reproducible(seed):
    a, b = compare.resamples(12, 50, seed), compare.resamples(12, 50, seed)
    assert a.shape == (50, 12) and (a == b).all() and a.min() >= 0 and a.max() < 12


def test_identity_resample_matches_full_data():
    rng = np.random.default_rng(1)
    y = np.zeros(400, bool)
    y[50:60] = y[200:215] = True
    s = rng.normal(size=400) + 3 * y
    tc = {"alpha": 0.5, "theta": 0.5}
    bounds = np.array([0, 400])
    blks = compare.blocks(y, bounds, block=100, delta=2)
    full = compare.sample_metrics(s, y, blks, 2.0, [1.0], 10, tc, 2)
    boot = compare._boot_worker((s, y, blks, np.array([list(range(len(blks)))]), 2.0, [1.0], 10, tc, 2))
    assert np.allclose(boot[0], list(full.values()))
