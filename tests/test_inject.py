"""Phase 2 injections (inject.py, D143): wrong placement or arithmetic silently changes every detection curve."""
import numpy as np
import pytest

from tsfm_ad import inject

ICFG = {"replicas": 2, "gap_after_min": 360, "gap_before_min": 60, "types": {
    "silence": {"targets": ["auth_total", "dc_*"], "magnitudes": [0.0, 0.5], "durations": [30, 180]},
    "burst": {"targets": ["auth_failed"], "magnitudes": [2, 20], "durations": [10, 60], "baseline_min": 60},
    "ramp": {"targets": ["host_*"], "magnitudes": [0.5, 10.0], "durations": [120, 480]},
    "shift": {"targets": ["auth_total", "dc_*"], "magnitudes": [0.2, 1.0], "durations": [360, 1440]}}}
GROUP_OF = {"auth_total": "tenant", "auth_failed": "tenant", "users_distinct": "tenant",
            **{f"dc_{i}": "dc" for i in range(1, 6)}, **{f"host_{i}": "host" for i in range(1, 6)}}
LO, HI = 41 * 1440, 58 * 1440


def test_schedule_is_seeded_inside_test_and_never_overlaps_in_a_group():
    a, drop_a = inject.schedule(ICFG, 3, LO, HI, GROUP_OF)
    b, _ = inject.schedule(ICFG, 3, LO, HI, GROUP_OF)
    assert a.equals(b) and not drop_a
    assert a.height == 4 * 2 * 2 * 2                       # types x magnitudes x durations x replicas
    assert (a["start"] >= LO).all() and (a["end"] <= HI).all()
    for g, part in a.group_by("group"):
        iv = sorted(zip(part["start"].to_list(), part["end"].to_list()))
        for (s0, e0), (s1, e1) in zip(iv, iv[1:]):
            assert s1 - 60 >= e0 + 360, (g, e0, s1)        # blocked window: 1 h before, 6 h after
    assert set(a.filter(a["type"] == "burst")["series"]) == {"auth_failed"}
    assert set(a.filter(a["type"] == "ramp")["series"]) <= {f"host_{i}" for i in range(1, 6)}
    assert a["inj_id"].n_unique() == a.height
    c, _ = inject.schedule(ICFG, 4, LO, HI, GROUP_OF)
    assert not c.equals(a)


def test_apply_arithmetic_and_labels():
    n = 1000
    raw = {"auth_total": np.full(n, 100.0), "auth_failed": np.r_[np.full(60, 4.0), np.full(n - 60, 3.0)],
           "host_1": np.full(n, 50.0), "dc_1": np.full(n, 10.0)}
    import polars as pl
    man = pl.DataFrame([
        {"seed": 0, "inj_id": "a", "type": "silence", "series": "dc_1", "group": "dc", "magnitude": 0.1,
         "duration_min": 5, "replica": 0, "start": 100, "end": 105},
        {"seed": 0, "inj_id": "b", "type": "burst", "series": "auth_failed", "group": "tenant", "magnitude": 5.0,
         "duration_min": 10, "replica": 0, "start": 60, "end": 70},
        {"seed": 0, "inj_id": "c", "type": "ramp", "series": "host_1", "group": "host", "magnitude": 2.0,
         "duration_min": 4, "replica": 0, "start": 200, "end": 204},
        {"seed": 0, "inj_id": "d", "type": "shift", "series": "auth_total", "group": "tenant", "magnitude": 0.5,
         "duration_min": 3, "replica": 0, "start": 300, "end": 303}], schema=inject.MANIFEST_SCHEMA)
    out, lab = inject.apply(raw, man, ICFG)
    assert np.allclose(out["dc_1"][100:105], 1.0) and out["dc_1"][105] == 10.0
    assert np.allclose(out["auth_failed"][60:70], 3.0 + 5 * 4.0)      # baseline = median of the 60 minutes before
    assert np.allclose(out["host_1"][200:204], 50.0 * (1 + 2.0 * np.array([1, 2, 3, 4]) / 4))
    assert out["host_1"][204] == 50.0
    assert np.allclose(out["auth_total"][300:303], 150.0) and out["auth_total"][303] == 100.0
    assert lab["dc_1"][100:105].all() and lab["dc_1"].sum() == 5 and lab["auth_total"].sum() == 3
    assert raw["dc_1"][100] == 10.0                                     # inputs untouched


def test_apply_refuses_overlap_on_a_series():
    import polars as pl
    man = pl.DataFrame([{"seed": 0, "inj_id": i, "type": "shift", "series": "dc_1", "group": "dc",
                         "magnitude": 0.5, "duration_min": 10, "replica": 0, "start": s, "end": s + 10}
                        for i, s in (("a", 10), ("b", 15))], schema=inject.MANIFEST_SCHEMA)
    with pytest.raises(ValueError, match="overlap"):
        inject.apply({"dc_1": np.ones(100)}, man, ICFG)
